"""Recovery transaction fault simulation; no native IO or device commands."""
import ctypes as c
from pathlib import Path
import subprocess
import pytest

READ = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_int)
WRITE = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_uint)
SYNC = c.CFUNCTYPE(None, c.c_void_p)
PUT = c.CFUNCTYPE(None, c.c_void_p, c.c_uint, c.c_ubyte)
GET = c.CFUNCTYPE(c.c_ubyte, c.c_void_p, c.c_uint)


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ), ('write', WRITE),
                ('sync', SYNC), ('put', PUT), ('get', GET)]


class State(c.Structure):
    _fields_ = [('io', IO), ('limit', c.c_uint), ('attempted', c.c_uint),
                ('failed', c.c_uint)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path_factory.mktemp('recovery') / 'request.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                    '-fPIC', str(root / 'firmware/recovery/request.c'),
                    '-o', str(output)], check=True)
    library = c.CDLL(str(output))
    library.lunar_recovery_bind.argtypes = [c.POINTER(State), c.POINTER(IO), c.c_uint]
    library.lunar_recovery_request.argtypes = [c.POINTER(State)]
    return library


class Bus:
    def __init__(self, lib, initial=0x8, ready=1, fail_byte=None, corrupt=None, limit=4, held_start=False):
        self.lib, self.con = lib, initial
        self.ready, self.fail_byte, self.corrupt = ready, fail_byte, corrupt
        self.held_start = held_start
        self.trace, self.bytes, self.polls = [], [], []
        self.mailbox = bytearray(16)
        self.running, self.count = False, 0
        self.callbacks = (READ(self.read), WRITE(self.write), SYNC(self.sync),
                          PUT(self.put), GET(self.get))
        self.io, self.state = IO(None, *self.callbacks), State()
        assert lib.lunar_recovery_bind(c.byref(self.state), c.byref(self.io), limit)
        assert not self.trace

    def read(self, _, reg):
        self.trace.append(('read', reg))
        assert reg == 0
        if self.running:
            self.count += 1
            self.polls[-1] += 1
            if len(self.bytes) != self.fail_byte and self.count >= self.ready:
                self.con &= ~(2 | 16)
                self.running = False
        return self.con

    def write(self, _, reg, value):
        self.trace.append(('write', reg, value))
        if reg == 1:
            assert self.con & 1
            assert not self.con & 2
            self.bytes.append(value)
        else:
            if value & 16:
                assert not self.running
                self.running, self.count = True, 0
                self.polls.append(0)
                value = (value if self.held_start else value & ~16) | 2
            self.con = value

    def sync(self, _):
        self.trace.append(('sync',))

    def put(self, _, offset, value):
        assert offset < 16
        self.trace.append(('put', offset, value))
        self.mailbox[offset] = value

    def get(self, _, offset):
        self.trace.append(('get', offset))
        return self.mailbox[offset] ^ (1 if offset == self.corrupt else 0)

    def request(self):
        return self.lib.lunar_recovery_request(c.byref(self.state))


def test_marker_verified_before_reset_and_no_implicit_retry(lib):
    bus = Bus(lib, ready=4)
    assert bus.request() == 1
    assert bus.mailbox == b'usb_update_mode\0'
    assert bus.bytes == [0x20, 0xa0, 0x10]
    assert bus.polls == [4, 4, 4]
    assert bus.con == 0x8
    first_data = next(i for i, e in enumerate(bus.trace) if e[:2] == ('write', 1))
    assert len([e for e in bus.trace[:first_data] if e[0] == 'get']) == 16
    assert bus.state.attempted and not bus.state.failed
    old_trace = bus.trace[:]
    assert not bus.request()
    assert bus.trace == old_trace


@pytest.mark.parametrize('byte', [1, 2, 3])
def test_timeout_stops_later_bytes_deselects_and_latches(lib, byte):
    bus = Bus(lib, fail_byte=byte)
    assert not bus.request()
    assert len(bus.bytes) == byte
    # Four completion polls plus the one control read for CS cleanup.
    assert bus.polls[-1] == 5
    assert not bus.con & 1
    assert bus.con & 8
    assert bus.state.failed
    trace = bus.trace[:]
    assert not bus.request()
    assert trace == bus.trace


@pytest.mark.parametrize('initial', [1, 0x100, 2])
def test_existing_selection_or_stuck_bus_never_writes_marker_or_registers(lib, initial):
    bus = Bus(lib, initial=initial)
    assert not bus.request()
    assert not any(e[0] in ('put', 'write') for e in bus.trace)
    assert bus.state.failed


@pytest.mark.parametrize('offset', [0, 8, 15])
def test_mailbox_verification_failure_never_requests_reset(lib, offset):
    bus = Bus(lib, corrupt=offset)
    assert not bus.request()
    assert not bus.bytes
    assert not any(e[0] == 'write' for e in bus.trace)
    assert bus.state.failed


def test_invalid_binding_and_unbound_request_have_no_io(lib):
    bus = Bus(lib)
    for limit in (0, 65537):
        assert not lib.lunar_recovery_bind(c.byref(bus.state), c.byref(bus.io), limit)
    assert not lib.lunar_recovery_bind(None, c.byref(bus.io), 4)
    assert not lib.lunar_recovery_bind(c.byref(bus.state), None, 4)
    assert not lib.lunar_recovery_request(c.byref(State()))
    assert not lib.lunar_recovery_request(None)
    assert not bus.trace


@pytest.mark.parametrize('byte', [1, 2, 3])
def test_timeout_cleanup_never_replays_held_start_strobe(lib, byte):
    bus = Bus(lib, fail_byte=byte, held_start=True)
    assert not bus.request()
    assert len(bus.bytes) == byte
    assert len(bus.polls) == byte
    assert bus.con & 2
    assert not bus.con & (1 | 16)
    assert bus.state.failed

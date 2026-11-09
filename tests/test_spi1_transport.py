"""MMIO simulation: no native register access or device traffic."""
import ctypes as c
from pathlib import Path
import subprocess
import pytest
from tests.test_panel_probe import BEGIN, WRITE, END, WAIT, Transport

READ_REG = c.CFUNCTYPE(c.c_uint, c.c_void_p, c.c_int)
WRITE_REG = c.CFUNCTYPE(None, c.c_void_p, c.c_int, c.c_uint)


class IO(c.Structure):
    _fields_ = [('context', c.c_void_p), ('read', READ_REG),
                ('write', WRITE_REG), ('wait_ms', WAIT)]


class State(c.Structure):
    _fields_ = [('io', IO), ('poll_limit', c.c_uint), ('configured', c.c_uint),
                ('active', c.c_uint), ('failed', c.c_uint)]


@pytest.fixture(scope='module')
def lib(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    path = tmp_path_factory.mktemp('spi1') / 'spi1.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                    '-fPIC', str(root / 'firmware/display/spi1_transport.c'),
                    str(root / 'firmware/display/panel_probe.c'), '-o', str(path)],
                   check=True)
    library = c.CDLL(str(path))
    library.lunar_spi1_bind.argtypes = [c.POINTER(State), c.POINTER(IO), c.c_uint,
                                       c.POINTER(Transport)]
    library.lunar_spi1_configure.argtypes = [c.POINTER(State)]
    library.lunar_panel_probe.argtypes = [c.POINTER(Transport)]
    library.lunar_spi1_native_io.argtypes = [c.POINTER(IO), c.c_void_p, WAIT]
    return library


class Board:
    def __init__(self, lib, ready_after=1, polls=4, fail_byte=None, delay_ok=True):
        self.lib = lib
        self.regs = [0, 0, 0, 0x80000000, 0xffffffff, 0x40000000]
        self.trace = []
        self.reads = 0
        self.byte_reads = []
        self.bytes = []
        self.pending = False
        self.stuck_pending = False
        self.active_byte = False
        self.ready_after = ready_after
        self.fail_byte = fail_byte
        self.delay_ok = delay_ok
        self.callbacks = (READ_REG(self.read), WRITE_REG(self.write), WAIT(self.wait))
        self.io = IO(None, *self.callbacks)
        self.state, self.bus = State(), Transport()
        assert lib.lunar_spi1_bind(c.byref(self.state), c.byref(self.io), polls,
                                   c.byref(self.bus))
        assert not self.trace

    def read(self, _, reg):
        self.trace.append(('read', reg))
        if reg == 0 and self.active_byte:
            self.reads += 1
            self.byte_reads[-1] += 1
            if self.fail_byte != len(self.bytes) and self.reads >= self.ready_after:
                self.pending = True
        return self.regs[reg] | ((1 << 15) if reg == 0 and (self.pending or self.stuck_pending) else 0)

    def write(self, _, reg, value):
        self.trace.append(('write', reg, value))
        if reg == 0:
            if value & (1 << 14):
                self.pending = False
                self.active_byte = False
            if not value & 1:
                self.active_byte = False
        if reg == 2:
            assert not self.pending  # Never accept completion from an older byte.
            assert not self.regs[3] & (1 << 7)  # CS asserted for every byte.
            self.bytes.append((bool(self.regs[3] & (1 << 8)), value))
            self.reads = 0
            self.byte_reads.append(0)
            self.active_byte = True
        self.regs[reg] = value & ~(1 << 14) if reg == 0 else value

    def wait(self, _, ms):
        self.trace.append(('wait', ms))
        assert self.regs[3] & (1 << 7)
        return self.delay_ok

    def configure(self):
        assert self.lib.lunar_spi1_configure(c.byref(self.state))

    def probe(self):
        return self.lib.lunar_panel_probe(c.byref(self.bus))


def test_binding_and_unconfigured_probe_have_no_hardware_effect(lib):
    board = Board(lib)
    assert board.probe() == 3
    assert not board.trace
    # The native factory also only binds function pointers.
    io = IO()
    lib.lunar_spi1_native_io(c.byref(io), None, board.callbacks[2])
    assert io.read and io.write and io.wait_ms
    assert not board.trace


@pytest.mark.parametrize('polls', [0, 65537, 0xffffffff])
def test_invalid_poll_limits_do_not_touch_hardware(lib, polls):
    board = Board(lib)
    assert not lib.lunar_spi1_bind(c.byref(board.state), c.byref(board.io), polls,
                                   c.byref(board.bus))
    assert not board.trace


def test_configuration_preserves_other_gpio_and_mux_bits(lib):
    board = Board(lib)
    board.configure()
    assert board.regs[3] == 0x80000080
    assert board.regs[4] == 0xfffff87f
    assert board.regs[5] == 0x40000010
    assert board.regs[:2] == [0x21, 4]  # Clear-pending is a strobe.
    before = list(board.trace)
    assert not lib.lunar_spi1_configure(c.byref(board.state))
    assert board.trace == before


def test_completion_at_last_allowed_read_and_stale_pending_are_handled(lib):
    board = Board(lib, ready_after=4)
    board.configure()
    board.pending = True
    assert board.bus.begin(board.bus.context, 0x2a)
    assert board.bus.write(board.bus.context, 0xef)
    board.bus.end(board.bus.context)
    assert board.bytes == [(False, 0x2a), (True, 0xef)]
    assert board.byte_reads == [4, 4]
    assert board.regs[3] & (1 << 7)
    assert not board.state.failed


@pytest.mark.parametrize('fail_byte', [1, 2, 77])
def test_command_or_data_timeout_stops_spi_and_never_retries(lib, fail_byte):
    board = Board(lib, fail_byte=fail_byte)
    board.configure()
    assert board.probe() == 2
    assert len(board.bytes) == fail_byte
    assert board.byte_reads[-1] == 4
    assert board.state.failed and not board.state.active
    assert not board.regs[0] & 1
    assert board.regs[3] & (1 << 7)
    before = list(board.trace)
    assert not board.bus.begin(board.bus.context, 0x29)
    assert not board.bus.write(board.bus.context, 0xff)
    board.bus.end(board.bus.context)
    assert not board.bus.wait_ms(board.bus.context, 100)
    assert board.trace == before


def test_delay_failure_sends_no_panel_commands(lib):
    board = Board(lib, delay_ok=False)
    board.configure()
    assert board.probe() == 3
    assert not board.bytes
    assert board.state.failed and board.regs[3] & (1 << 7)


def test_full_probe_on_simulated_spi_releases_cs_and_sends_expected_pixels(lib):
    board = Board(lib)
    board.configure()
    assert board.probe() == 0
    assert len(board.bytes) == 115276  # 22 commands plus 115254 data bytes.
    assert board.bytes[0] == (False, 0x11)
    assert board.bytes[-1] == (False, 0x29)
    start = board.bytes.index((False, 0x2c)) + 1
    pixels = bytes(value for data, value in board.bytes[start:-1] if data)
    assert pixels == b''.join(word * (60 * 240) for word in
                             (b'\xff\xff', b'\xf8\0', b'\x07\xe0', b'\0\x1f'))
    assert not board.state.failed and not board.state.active
    assert board.regs[3] & (1 << 7)


def test_stuck_old_completion_flag_is_rejected_before_new_byte(lib):
    board = Board(lib)
    board.configure()
    board.stuck_pending = True
    before = len(board.trace)
    assert not board.bus.begin(board.bus.context, 0x11)
    assert not board.bytes
    reads = [event for event in board.trace[before:] if event == ('read', 0)]
    assert len(reads) == 4
    assert board.state.failed and board.regs[3] & (1 << 7)


def test_nested_begin_aborts_instead_of_merging_commands(lib):
    board = Board(lib)
    board.configure()
    assert board.bus.begin(board.bus.context, 0x2a)
    assert not board.bus.begin(board.bus.context, 0x29)
    assert board.bytes == [(False, 0x2a)]
    assert board.state.failed and not board.state.active
    assert board.regs[3] & (1 << 7)

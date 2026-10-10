"""Protocol/abort evidence only: callbacks never contact hardware."""
import ctypes as c
import hashlib
import os
from pathlib import Path
import subprocess

import pytest

BEGIN = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_ubyte)
WRITE = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_ubyte)
END = c.CFUNCTYPE(None, c.c_void_p)
WAIT = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_uint)


class Transport(c.Structure):
    _fields_ = [('context', c.c_void_p), ('begin', BEGIN), ('write', WRITE),
                ('end', END), ('wait_ms', WAIT)]


@pytest.fixture(scope='module')
def probe(tmp_path_factory):
    root = Path(__file__).resolve().parents[1]
    library = tmp_path_factory.mktemp('panel-probe') / 'probe.so'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                    '-fPIC', str(root / 'firmware/display/panel_probe.c'),
                    '-o', str(library)], check=True)
    function = c.CDLL(str(library)).lunar_panel_probe
    function.argtypes = [c.POINTER(Transport)]
    function.restype = c.c_int
    return function


def run(probe, failure=None):
    trace = []
    counts = dict(begin=0, write=0, end=0, wait=0)
    stopped = []
    after_failure = []

    def event(kind, value=None):
        if stopped and kind != 'end':
            after_failure.append(kind)
        counts[kind] += 1
        if kind == 'begin':
            trace.append([value, bytearray()])
        elif kind == 'write':
            trace[-1][1].append(value)
        elif kind == 'wait':
            trace.append(['wait', value])
        if failure == (kind, counts[kind]):
            stopped.append(kind)
            return 0
        return 1

    callbacks = (BEGIN(lambda _, value: event('begin', value)),
                 WRITE(lambda _, value: event('write', value)),
                 END(lambda _: event('end')),
                 WAIT(lambda _, value: event('wait', value)))
    transport = Transport(None, *callbacks)
    result = probe(c.byref(transport))
    assert not after_failure
    return result, trace, counts


def test_complete_probe_is_bounded_and_pixels_have_big_endian_word_order(probe):
    result, trace, counts = run(probe)
    assert result == 0
    assert trace[:3] == [['wait', 100], [0x11, bytearray()], ['wait', 120]]
    commands = [row for row in trace if row[0] != 'wait']
    assert [row[0] for row in commands] == [
        0x11, 0x2a, 0x2b, 0xb2, 0x20, 0xb7, 0xbb, 0xc0, 0xc2, 0xc3,
        0xc4, 0xc6, 0xd0, 0xe0, 0xe1, 0x36, 0x3a, 0xe7, 0x51, 0x21,
        0x2c, 0x29]
    assert commands[1][1] == bytes.fromhex('000000ef')
    assert commands[2][1] == bytes.fromhex('00280117')
    assert commands[3][1] == bytes.fromhex('0c0c0c0033')
    assert commands[20][1] == b''.join(
        word * (60 * 240) for word in (b'\xff\xff', b'\xf8\0', b'\x07\xe0', b'\0\x1f'))
    assert counts == dict(begin=22, end=22, write=115254, wait=2)


@pytest.mark.parametrize('kind,index', [('begin', 1), ('begin', 14),
    ('begin', 21), ('begin', 22), ('write', 1), ('write', 54),
    ('write', 55), ('write', 57654), ('write', 115254), ('wait', 1), ('wait', 2)])
def test_failure_stops_traffic_and_releases_every_attempted_transaction(probe, kind, index):
    result, _, counts = run(probe, (kind, index))
    assert result == (3 if kind == 'wait' else 2)
    assert counts[kind] == index
    assert counts['begin'] == counts['end']


def test_missing_callback_rejected_before_any_callback(probe):
    assert probe(None) == 1
    for missing in range(4):
        unexpected = []
        callbacks = [BEGIN(lambda *_: unexpected.append('begin') or 0),
                     WRITE(lambda *_: unexpected.append('write') or 0),
                     END(lambda *_: unexpected.append('end')),
                     WAIT(lambda *_: unexpected.append('wait') or 0)]
        callbacks[missing] = (BEGIN, WRITE, END, WAIT)[missing]()
        assert probe(c.byref(Transport(None, *callbacks))) == 1
        assert not unexpected


def test_setup_matches_guarded_stock_v15_table_when_supplied(probe):
    path = os.environ.get('LUNAR_STOCK_APP')
    if not path:
        pytest.skip('private guarded V15 app was not supplied')
    raw = Path(path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == '306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203'
    records = [raw[0x4f76c + i * 18:0x4f76c + (i + 1) * 18] for i in range(21)]
    assert records[1][:2] == b'\x45\x78'  # loop handles this as a 120 ms delay
    result, trace, _ = run(probe)
    assert result == 0
    actual = [row for row in trace if row[0] != 'wait'][:20]
    expected = [[row[0], bytearray(row[2:2 + row[1]])]
                for i, row in enumerate(records) if i != 1]
    assert actual == expected

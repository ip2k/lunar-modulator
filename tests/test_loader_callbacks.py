"""Offline tests for the separate callback metadata proposal; no device opening."""
import ctypes
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_loader_callbacks as p


def reader():
    r = p.LoaderCallbackReader.__new__(p.LoaderCallbackReader)
    r.phase = 'loader'
    r._callbacks_ready, r._callbacks_used = True, False
    r.fd = -1
    r.log = lambda *a, **k: None
    return r


def test_exact_eight_byte_read_has_no_write_data():
    assert p.callback_request(0xFD07, 'loader', address=p.CALLBACK_ADDRESS) == (
        bytes.fromhex('fd0701c097240008ffffffffffffffff'), b'', 8)
    # Destination [01c09600,01c09608) cannot overlap the source slots.
    assert 0x01C09600 + p.CALLBACK_BYTES <= p.CALLBACK_ADDRESS


def test_other_opcodes_phases_ranges_and_payloads_are_rejected():
    for op in range(65536):
        if op != 0xFD07:
            with pytest.raises(ValueError):
                p.callback_request(op, 'loader', address=p.CALLBACK_ADDRESS)
    for phase in ('rom', '', 'unknown'):
        with pytest.raises(ValueError):
            p.callback_request(0xFD07, phase, address=p.CALLBACK_ADDRESS)
    for address in (0, -1, 0x01C043DE, 0x01C09720, 0x01C09728,
                    0xFFC00000, 0x02000000, 0x51000, 0x01C80108):
        with pytest.raises(ValueError):
            p.callback_request(0xFD07, 'loader', address=address)
    with pytest.raises(ValueError):
        p.callback_request(0xFD07, 'loader', address=p.CALLBACK_ADDRESS, payload=b'x')


def test_requires_complete_loader_validation_and_cannot_reload_to_retry(monkeypatch):
    r = reader()
    def fail(*a):
        raise ValueError('loader validation failed')
    monkeypatch.setattr(p.Reader, 'load', fail)
    with pytest.raises(ValueError):
        r.load(b'bad loader')
    with pytest.raises(ValueError):
        r.build_request(0xFD07, p.CALLBACK_ADDRESS, b'')
    monkeypatch.setattr(p.Reader, 'load', lambda *a: None)
    r.load(b'mocked loader')
    r.build_request(0xFD07, p.CALLBACK_ADDRESS, b'')
    r.load(b'mocked loader')
    with pytest.raises(ValueError):
        r.build_request(0xFD07, p.CALLBACK_ADDRESS, b'')


@pytest.mark.parametrize('data', [b'', bytes(7), bytes(9)])
def test_wrong_length_cannot_record_a_metadata_observation(data):
    r = reader()
    r.cmd = lambda *a, **k: data
    r.log = lambda *a, **k: pytest.fail('incomplete metadata cannot be observed')
    with pytest.raises(ValueError):
        r.callbacks()


@pytest.mark.parametrize('field,value', [('status', 2), ('host', 1),
                                        ('driver', 1), ('info', 1),
                                        ('resid', 1), ('resid', -1)])
def test_sg_io_error_consumes_attempt_without_retry(monkeypatch, field, value):
    r = reader()
    def ioctl(fd, operation, header):
        assert fd == -1 and operation == 0x2285
        assert header.data_len == 8 and header.direction == -3
        assert ctypes.string_at(header.cmd, header.cmd_len) == bytes.fromhex(
            'fd0701c097240008ffffffffffffffff')
        setattr(header, field, value)
    monkeypatch.setattr(p.Reader.cmd.__globals__['fcntl'], 'ioctl', ioctl)
    with pytest.raises(OSError):
        r.callbacks()
    with pytest.raises(ValueError):
        r.callbacks()


def test_values_are_observations_without_range_guessing_or_address_bit_changes(monkeypatch):
    r = reader()
    data = b'\x01\x23\x45\x67\xff\xff\xff\xff'
    def ioctl(fd, operation, header):
        assert fd == -1
        ctypes.memmove(header.data, data, 8)
    monkeypatch.setattr(p.Reader.cmd.__globals__['fcntl'], 'ioctl', ioctl)
    events = []
    r.log = lambda *a, **k: events.append((a, k))
    assert r.callbacks() == {'send': 0x67452301, 'receive': 0xFFFFFFFF}
    assert events[0][0] == ('command',)
    assert events[-1][0] == ('loader_callback_slots_observed',)
    assert events[-1][1]['bytes'] == 8
    with pytest.raises(ValueError):
        r.callbacks()

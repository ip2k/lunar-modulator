"""Offline guards for the prepared fixed RAM readback; no USB device is opened."""
import hashlib
import ctypes
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_loader_readback as p


def reader():
    r = p.LoaderReadbackReader.__new__(p.LoaderReadbackReader)
    r.phase = 'loader'
    r._readback_ready = True
    r._readback_used = False
    r.log = lambda *a, **k: None
    return r


def test_fixed_cdb_has_no_write_data_and_matches_audited_fields():
    assert p.readback_request(0xFD07, 'loader', address=p.READBACK_ADDRESS) == (
        bytes.fromhex('fd0701c043de0040ffffffffffffffff'), b'', 64)
    assert p.RAM <= p.READBACK_ADDRESS < p.READBACK_ADDRESS + 64 <= p.RAM + 24064
    assert p.READBACK_BYTES <= 256


def test_no_other_opcode_or_phase_can_use_readback_path():
    for op in range(65536):
        if op != 0xFD07:
            with pytest.raises(ValueError):
                p.readback_request(op, 'loader', address=p.READBACK_ADDRESS)
    for phase in ('rom', '', 'unknown'):
        with pytest.raises(ValueError):
            p.readback_request(0xFD07, phase, address=p.READBACK_ADDRESS)


def test_no_adjacent_ram_rom_mmio_flash_or_payload_is_accepted():
    for address in (0, -1, p.RAM, p.READBACK_ADDRESS-1, p.READBACK_ADDRESS+1,
                    0x01C09600, 0x02000000, 0xFFC00000, 0x51000, 0x01C80108):
        with pytest.raises(ValueError):
            p.readback_request(0xFD07, 'loader', address=address)
    with pytest.raises(ValueError):
        p.readback_request(0xFD07, 'loader', address=p.READBACK_ADDRESS, payload=b'x')


def test_readback_cannot_precede_successful_full_loader_validation(monkeypatch):
    r = reader()
    def fail(*a):
        raise ValueError('loader validation failed')
    monkeypatch.setattr(p.Reader, 'load', fail)
    with pytest.raises(ValueError):
        r.load(b'bad loader')
    with pytest.raises(ValueError):
        r.build_request(0xFD07, p.READBACK_ADDRESS, b'')
    monkeypatch.setattr(p.Reader, 'load', lambda *a: None)
    r.load(b'mocked audited loader')
    assert r.build_request(0xFD07, p.READBACK_ADDRESS, b'')[2] == 64


def test_transport_failure_consumes_the_one_attempt():
    r = reader()
    def transport(*a, **k):
        r.build_request(a[0], k['address'], b'')
        raise OSError('mock SG_IO failure')
    r.cmd = transport
    with pytest.raises(OSError):
        r.readback()
    with pytest.raises(ValueError):
        r.readback()


@pytest.mark.parametrize('data', [b'', bytes(63), bytes(64), bytes(65)])
def test_short_long_or_wrong_code_stops_without_a_success_record(data):
    r = reader()
    r.cmd = lambda *a, **k: data
    r.log = lambda *a, **k: pytest.fail('must not record unverified bytes')
    with pytest.raises(ValueError):
        r.readback()


def test_verified_raw_bytes_are_not_deciphered_or_echo_checked(monkeypatch):
    # Synthetic bytes test the verification behavior; these are not vendor bytes.
    data = bytes(range(64))
    monkeypatch.setattr(p, 'READBACK_SHA', hashlib.sha256(data).hexdigest())
    r = reader()
    r.cmd = lambda *a, **k: data
    events = []
    r.log = lambda *a, **k: events.append((a, k))
    assert r.readback() == data
    assert events[0][1]['sha256'] == p.READBACK_SHA


@pytest.mark.parametrize('field,value', [('status', 2), ('host', 1),
                                        ('driver', 1), ('info', 1),
                                        ('resid', 1), ('resid', -1)])
def test_sg_io_fault_or_incomplete_transfer_fails_closed(monkeypatch, field, value):
    r = reader()
    r.fd = -1  # Mock ioctl intercepts it; no device can be opened here.
    def ioctl(fd, operation, header):
        assert fd == -1 and operation == 0x2285
        assert header.data_len == 64 and header.direction == -3
        assert ctypes.string_at(header.cmd, header.cmd_len) == bytes.fromhex(
            'fd0701c043de0040ffffffffffffffff')
        setattr(header, field, value)
    monkeypatch.setattr(p.Reader.cmd.__globals__['fcntl'], 'ioctl', ioctl)
    with pytest.raises(OSError):
        r.readback()
    assert r._readback_used
    with pytest.raises(ValueError):
        r.readback()


def test_sg_io_success_verifies_exact_raw_transfer(monkeypatch):
    data = bytes(range(64))
    monkeypatch.setattr(p, 'READBACK_SHA', hashlib.sha256(data).hexdigest())
    r = reader()
    r.fd = -1
    def ioctl(fd, operation, header):
        assert fd == -1 and operation == 0x2285
        assert header.data_len == len(data)
        ctypes.memmove(header.data, data, len(data))
    monkeypatch.setattr(p.Reader.cmd.__globals__['fcntl'], 'ioctl', ioctl)
    assert r.readback() == data
    with pytest.raises(ValueError):
        r.readback()

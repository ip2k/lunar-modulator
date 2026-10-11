"""Exact probe transport guard, offline only; no USB opened by these checks."""
import sys
from pathlib import Path
import hashlib
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_ram_recovery as p


def fake():
    r = p.RamRecoveryReader.__new__(p.RamRecoveryReader)
    r._blocks = (bytes(512), bytes([1])*512)
    r._stage, r._next_block, r.phase = 'inquiry', 0, 'rom'
    r.log = lambda *a, **k: None
    return r


def test_bad_image_rejected_before_device_open(monkeypatch):
    monkeypatch.setattr(p.Reader, '__init__', lambda *a: pytest.fail('device opened'))
    for blob in (b'', bytes(700), bytes(1024)):
        with pytest.raises(ValueError):
            p.RamRecoveryReader('/dev/sg0', lambda *a: None, blob, [])


def test_cipher_vector_and_block_seed():
    # Frozen SHA from kagaimiq's independently executed jl_crc_cipher.
    assert hashlib.sha256(p.scramble_block(bytes(512))).hexdigest() == '40a6686839ae71bed8120b543998bde8fa7019a93a02332b9b183c2d50ebe194'
    assert p.scramble_block(p.scramble_block(bytes(range(256))*2)) == bytes(range(256))*2
    with pytest.raises(ValueError):
        p.scramble_block(bytes(511))


def test_only_expected_upload_bytes_address_and_order():
    r = fake()
    for op in (0xFB08, 0xFB06, 0xFC14, 0xFD05, 0xFD07, 0xFC12, 0xFB42):
        with pytest.raises(ValueError):
            r.build_request(op, p.RAM, b'')
    r.build_request(0x12, 0, b'')
    with pytest.raises(ValueError):
        r.build_request(0x12, 0, b'')
    r._stage = 'upload'
    for address, data in ((p.RAM+512, bytes(512)), (p.RAM, bytes([1])*512)):
        with pytest.raises(ValueError):
            r.build_request(0xFB06, address, data)
    r.build_request(0xFB06, p.RAM, bytes(512))
    with pytest.raises(ValueError):
        r.build_request(0xFB06, p.RAM, bytes(512))
    r._stage = 'upload'
    r.build_request(0xFB06, p.RAM+512, bytes([1])*512)
    r._stage = 'jump'
    cdb, _, _ = r.build_request(0xFB08, p.RAM, b'')
    assert cdb[6:8] == b'\x00\x01'
    with pytest.raises(ValueError):
        r.build_request(0xFB08, p.RAM, b'')


@pytest.mark.parametrize('fail_at', [0, 1, 2, 3])
def test_transport_failure_never_retries(fail_at):
    r = fake()
    calls = []
    def cmd(op, *, address=0, payload=b''):
        r.build_request(op, address, payload)
        calls.append(op)
        if len(calls)-1 == fail_at:
            raise OSError('timeout')
        return b'\0'*8 + b'WL82    ' + b'UBOOT1.00       ' + b'\0'*4
    r.cmd = cmd
    with pytest.raises(OSError):
        r.run_probe()
    assert len(calls) == fail_at+1
    with pytest.raises(ValueError):
        r.run_probe()
    assert len(calls) == fail_at+1


def test_wrong_inquiry_never_uploads():
    r = fake()
    calls = []
    def cmd(op, **kwargs):
        r.build_request(op, 0, b'')
        calls.append(op)
        return bytes(36)
    r.cmd = cmd
    with pytest.raises(ValueError):
        r.run_probe()
    assert calls == [0x12]


def test_no_jump_before_two_blocks_or_loader_phase():
    r = fake()
    r._stage = 'jump'
    with pytest.raises(ValueError):
        r.build_request(0xFB08, p.RAM, b'')
    r._stage, r.phase = 'inquiry', 'loader'
    with pytest.raises(ValueError):
        r.build_request(0x12, 0, b'')


def test_all_unlisted_opcodes_rejected():
    r = fake()
    for op in range(65536):
        if op not in (0x12, 0xFB06, 0xFB08):
            with pytest.raises(ValueError):
                r.build_request(op, 0, b'')


def entry():
    return [dict(time=99, event='before', usb_path='3-2', usb=[
        dict(path='3-2', vid='4c4a', pid='c755', devnum='19')]),
        dict(time=99, event='identity', reply=p.KNOWN_092.hex()),
        dict(time=99, event='sending_soft_key', hex=p.SOFT_KEY.hex()),
        dict(time=100, event='uboot_enumerated', usb=[
            dict(path='3-2', vid='4c4a', pid='8057', devnum='20')])]


def test_fresh_owner_entry_bound_to_same_port():
    assert p.checked_entry(entry(), now=100)['devnum'] == '20'
    for now in (98, 221):
        with pytest.raises(ValueError):
            p.checked_entry(entry(), now=now)
    e=entry(); e[-1]['usb'][0]['path']='3-1'
    with pytest.raises(ValueError):
        p.checked_entry(e, now=100)
    e=entry(); e[-1]['usb'][0]['devnum']='19'
    with pytest.raises(ValueError):
        p.checked_entry(e, now=100)
    e=entry(); e[1]['reply']='00'
    with pytest.raises(ValueError):
        p.checked_entry(e, now=100)
    with pytest.raises(ValueError):
        p.checked_entry(entry()+[entry()[1]], now=100)

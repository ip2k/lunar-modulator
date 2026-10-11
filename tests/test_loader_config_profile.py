"""Offline patch guard checks; no device opener or traffic."""
import binascii
import hashlib
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from jieli import loader_config_profile as p


def synthetic(monkeypatch):
    # Synthetic, deliberately nonzero surrounding bytes detect unintended edits.
    decoded = bytearray([0xA5]*p.LOADER_SIZE)
    for offset, before, _ in p.PATCHES:
        decoded[offset:offset+len(before)] = before
    start = p.ZERO_BASE-p.RAM
    decoded[start:start+p.ZERO_SIZE] = bytes(p.ZERO_SIZE)
    decoded = bytes(decoded)
    encrypted = p.crypt_blocks(decoded)
    monkeypatch.setattr(p, 'LOADER_SHA', p.digest(encrypted))
    monkeypatch.setattr(p, 'DECODED_SHA', p.digest(decoded))
    return encrypted, decoded


@pytest.mark.parametrize('bad', [b'', bytes(512), bytes(p.LOADER_SIZE), bytes(p.LOADER_SIZE+512)])
def test_wrong_original_rejected_before_decode(monkeypatch, bad):
    monkeypatch.setattr(p, 'crypt_blocks', lambda _: pytest.fail('decoded unpinned input'))
    with pytest.raises(ValueError):
        p.prepare_loader(bad)


def test_exact_patch_only_and_fixed_upload_inventory(monkeypatch):
    source, original = synthetic(monkeypatch)
    candidate = p.prepare_loader(source)
    allowed = {i for offset, before, _ in p.PATCHES
               for i in range(offset, offset+len(before))}
    assert {i for i, (a,b) in enumerate(zip(original,candidate.decoded)) if a!=b} <= allowed
    assert p.crypt_blocks(candidate.encrypted) == candidate.decoded
    assert source != candidate.encrypted
    requests = candidate.upload_requests()
    assert len(requests) == 47
    for i, (cdb, payload, read_size) in enumerate(requests):
        assert len(cdb)==16 and cdb[:2]==b'\xfb\x06'
        assert int.from_bytes(cdb[2:6],'big')==p.RAM+i*512
        assert cdb[6:9]==b'\x02\x00\x00'
        assert cdb[9:11]==binascii.crc_hqx(payload,0).to_bytes(2,'little')
        assert cdb[11:]==b'\xff'*5 and read_size==0
        assert payload==candidate.encrypted[i*512:(i+1)*512]
    assert int.from_bytes(requests[-1][0][2:6],'big')+512==p.RAM+p.LOADER_SIZE
    report = json.loads(candidate.report_json)
    assert report['extra_rom_uploads']==0
    assert len(report['upload_inventory'])==47
    for row, (cdb, payload, read_size) in zip(report['upload_inventory'], requests):
        assert row['cdb_sha256']==p.digest(cdb)
        assert row['payload_sha256']==p.digest(payload)
        assert row['address']==int.from_bytes(cdb[2:6], 'big')
        assert row['bytes']==512 and row['read_size']==read_size==0
    assert report['direct_traced_selector_reads_retained_windows'] is False
    assert all(report[k] is False for k in ('hardware_ready',
        'patched_vendor_listing_independently_reviewed',
        'external_initializer_effects_verified', 'physical_execution_verified'))


def test_mutated_instruction_premise_rejected_even_when_hashes_match(monkeypatch):
    source, decoded = synthetic(monkeypatch)
    altered=bytearray(decoded)
    altered[p.PATCHES[0][0]] ^= 1
    mutated=p.crypt_blocks(bytes(altered))
    monkeypatch.setattr(p,'LOADER_SHA',p.digest(mutated))
    monkeypatch.setattr(p,'DECODED_SHA',p.digest(altered))
    with pytest.raises(ValueError, match='instruction premise'):
        p.prepare_loader(mutated)


def test_nonzero_image_config_rejected_even_when_hashes_match(monkeypatch):
    source, decoded = synthetic(monkeypatch)
    altered=bytearray(decoded)
    altered[p.ZERO_BASE-p.RAM+34]=4
    mutated=p.crypt_blocks(bytes(altered))
    monkeypatch.setattr(p,'LOADER_SHA',p.digest(mutated))
    monkeypatch.setattr(p,'DECODED_SHA',p.digest(altered))
    with pytest.raises(ValueError, match='zero padding'):
        p.prepare_loader(mutated)


def test_decoded_pin_independent(monkeypatch):
    source, _=synthetic(monkeypatch)
    monkeypatch.setattr(p,'DECODED_SHA','0'*64)
    with pytest.raises(ValueError,match='decoded-loader pin'):
        p.prepare_loader(source)


def test_outputs_private_and_never_replace(monkeypatch,tmp_path):
    source,_=synthetic(monkeypatch)
    loader=tmp_path/'input.bin'
    loader.write_bytes(source)
    destination=tmp_path/'private'
    report=p.emit_private(loader,destination)
    assert destination.stat().st_mode & 0o777==0o700
    for name in ('loader.patched.encrypted.bin','loader.patched.decoded.bin','profile.json'):
        assert (destination/name).stat().st_mode & 0o777==0o600
    assert p.digest((destination/'loader.patched.encrypted.bin').read_bytes())==report['patched_encrypted_sha256']
    with pytest.raises(FileExistsError):
        p.emit_private(loader,destination)


def test_private_recorded_loader_when_explicitly_available():
    path=os.environ.get('FM1_LOADER_PRIVATE')
    if not path:
        pytest.skip('private vendor loader not supplied')
    candidate=p.prepare_loader(Path(path).read_bytes())
    assert len(candidate.encrypted)==24064
    assert p.digest(candidate.decoded)=='a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af'
    assert p.digest(candidate.encrypted)=='fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c'

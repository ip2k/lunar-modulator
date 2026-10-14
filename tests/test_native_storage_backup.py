# SPDX-License-Identifier: MIT
"""Lossless archives for both VM layouts; no synthetic firmware admission."""
from pathlib import Path
import json
import struct
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools/native'))
from storage_backup import (prepare, emit, verify, digest, PROFILES, FLASH_BYTES,
                            header_decode, sfc_decode, crc16)


def descriptor(name, address, size, flags, terminal=0):
    body = struct.pack('<HIIBBH16s', 0xffff, address, size, flags, 0, terminal,
                       name.encode().ljust(16, b'\0'))
    return struct.pack('<H', crc16(body))+body


def image(profile):
    start, size = PROFILES[profile]
    raw = bytearray(b'\xff'*FLASH_BYTES)
    head = bytearray(32); struct.pack_into('<H', head, 0, crc16(head[2:]))
    raw[:32] = header_decode(head)
    top = [descriptor('uboot.boot', 0xa0, 14384, 0),
           descriptor('isd_config.ini', 0x38d0, 699, 2),
           descriptor('app_dir_head', 0x4000, 0xffffffff, 0x81),
           descriptor('key_mac', 0xff000, 4096, 0x12, 1)]
    for i, item in enumerate(top): raw[32+i*32:64+i*32] = header_decode(item)
    table = b''.join([descriptor('app_area_head', 0x02000120, 224, 0x83),
                     descriptor('app.bin', 0x120, 4, 0x82),
                     descriptor('cfg_tool.bin', 0x124, 4, 0x82),
                     descriptor('VM', start, size, 0x12),
                     descriptor('PRCT', 0, start, 0x92),
                     descriptor('BTIF', 0xe9000, 4096, 0x92),
                     descriptor('USR', 0xea000, 0x12000, 0x92, 1)])
    raw[0x4000:0x40e0] = sfc_decode(table, 0)
    # Opaque data at both edges catches truncation/tail loss without interpreting it.
    for lo, n in [(start,size),(0xe9000,4096),(0xea000,0x12000),(0xfc000,0x3000)]:
        raw[lo:lo+4] = b'HEAD'; raw[lo+n-4:lo+n] = b'TAIL'
    return bytes(raw)


FAULTS = ['roundtrip','mismatched','digest','reservation','header','profile',
          'missing','bank','baseline','manifest-pin','forged-manifest',
          'extra','symlink','existing','short']


@pytest.mark.parametrize('profile', PROFILES)
@pytest.mark.parametrize('fault', FAULTS)
def test_lossless_storage_archive(tmp_path, profile, fault):
    raw = image(profile); pin = digest(raw)
    if fault in ['mismatched','digest','reservation','header','profile','short']:
        other, selected, expected = raw, profile, pin
        if fault == 'mismatched': other = raw[:-1]+b'\0'
        if fault == 'digest': expected = '0'*64
        if fault == 'reservation':
            patched = bytearray(raw)
            decoded = bytearray(sfc_decode(raw[0x4000:0x40e0],0))
            decoded[96:128] = descriptor('VM', 0xd8000, PROFILES[profile][1], 0x12)
            patched[0x4000:0x40e0] = sfc_decode(decoded,0)
            raw = other = bytes(patched); expected = digest(raw)
        if fault == 'header':
            raw = other = bytes([raw[0] ^ 1])+raw[1:]; expected = digest(raw)
        if fault == 'profile': selected = next(x for x in PROFILES if x != profile)
        if fault == 'short': raw = other = raw[:-1]; expected = digest(raw)
        with pytest.raises(ValueError): prepare(raw, other, selected, expected)
        return
    files, receipt = prepare(raw, raw, profile, pin)
    directory = tmp_path/'private'
    manifest_pin = emit(directory, files, receipt)
    assert (directory.stat().st_mode & 0o077) == 0
    assert all((p.stat().st_mode & 0o077) == 0 for p in directory.iterdir())
    if fault == 'roundtrip':
        result = verify(directory, pin, manifest_pin)
        assert result['status']=='lossless-storage-backup-verified'
        assert not result['semantic_migration_verified'] and not result['hardware_admitted']
        assert result['hardware_operations']==0
        assert (directory/'vm.bin').read_bytes() == raw[PROFILES[profile][0]:0xe9000]
        return
    if fault == 'existing':
        with pytest.raises(FileExistsError): emit(directory, files, receipt)
        assert verify(directory,pin,manifest_pin)['hardware_operations']==0
        return
    if fault == 'missing': (directory/'usr.bin').unlink()
    if fault == 'bank':
        p = directory/'vm.bin'; p.write_bytes(p.read_bytes()[:-1]+b'\0')
    if fault == 'baseline':
        p = directory/'baseline.bin'; p.write_bytes(p.read_bytes()[:-1]+b'\0')
    if fault == 'manifest-pin': manifest_pin = '0'*64
    if fault == 'forged-manifest':
        p = directory/'manifest.json'; edited = json.loads(p.read_bytes())
        edited['semantic_migration_verified']=True
        p.write_text(json.dumps(edited)); manifest_pin=digest(p.read_bytes())
    if fault == 'extra': (directory/'unexpected.bin').write_bytes(b'')
    if fault == 'symlink':
        p = directory/'vm.bin'; outside=tmp_path/'outside'; p.rename(outside)
        p.symlink_to(outside)
    with pytest.raises(ValueError): verify(directory,pin,manifest_pin)

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Lossless private stock-storage export, never a migration/write admission.

Require matching complete backups and a separately retained full-backup digest.
Inspect known reservation descriptors, archive the full image plus opaque bank
copies, and verify every byte against the retained digest before rollback use.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'jieli'))
from inspect_fwsc import header_decode, sfc_decode, crc16
from inspect_stock_flash import record

FLASH_BYTES = 0x100000
PROFILES = {
    'stock-v15': (0x93000, 0x56000),
    'recorded-092': (0xD9000, 0x10000),
}
FIXED_BANKS = {'btif.bin': (0xE9000, 0x1000),
               'usr.bin': (0xEA000, 0x12000),
               'globals-gap.bin': (0xFC000, 0x3000)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def expected_digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Explicit lowercase SHA256 required')
    return value


def inspect_reservations(image, profile):
    """Reservation geometry only, not full firmware/provenance validation."""
    if profile not in PROFILES or not isinstance(image, bytes) or len(image) != FLASH_BYTES:
        raise ValueError('Named profile and complete 1 MiB raw image required')
    head = header_decode(image[:32])
    if crc16(head[2:]) != int.from_bytes(head[:2], 'little'):
        raise ValueError('Physical image header CRC differs')
    top = [record(header_decode(image[32+i*32:64+i*32]), 0) for i in range(4)]
    if ([x['name'] for x in top] != ['uboot.boot', 'isd_config.ini', 'app_dir_head', 'key_mac']
            or [bool(x['terminal']) for x in top] != [False, False, False, True]
            or (top[2]['address'], top[2]['bytes'], top[2]['flags'], top[2]['crc16'])
            != (0x4000, 0xFFFFFFFF, 0x81, 0xFFFF)
            or (top[3]['address'], top[3]['bytes'], top[3]['flags'], top[3]['crc16'])
            != (0xFF000, 0x1000, 0x12, 0xFFFF)):
        raise ValueError('Unsupported physical directory/reservation layout')
    decoded = sfc_decode(image[0x4000:0x40E0], 0)
    area = record(decoded, 0)
    if (area['name'], area['address'], area['flags'], area['terminal']) != (
            'app_area_head', 0x02000120, 0x83, 0):
        raise ValueError('Unsupported application directory')
    children = [record(decoded, 32+i*32) for i in range(6)]
    if ([x['name'] for x in children] != ['app.bin', 'cfg_tool.bin', 'VM', 'PRCT', 'BTIF', 'USR']
            or [bool(x['terminal']) for x in children] != [False]*5+[True]):
        raise ValueError('Unsupported application reservation table')
    start, length = PROFILES[profile]
    if not 224 <= area['bytes'] <= start - 0x4000:
        raise ValueError('Application directory overlaps reserved storage')
    reservations = [(start, length, 0x12), (0, start, 0x92),
                    (0xE9000, 0x1000, 0x92), (0xEA000, 0x12000, 0x92)]
    for item, expected in zip(children[2:], reservations):
        if (item['address'], item['bytes'], item['flags']) != expected or item['crc16'] != 0xFFFF:
            raise ValueError('Reservation descriptor disagrees with named profile')
    return {'vm.bin': (start, length), **FIXED_BANKS}


def prepare(a, b, profile, baseline_sha256):
    expected_digest(baseline_sha256)
    if not isinstance(a, bytes) or a != b or digest(a) != baseline_sha256:
        raise ValueError('Two matching backups bound to retained digest required')
    banks = inspect_reservations(a, profile)
    files = {'baseline.bin': a}
    for name, (off, n) in banks.items():
        files[name] = a[off:off+n]
    receipt = dict(schema=1, kind='fm1-lossless-private-storage-backup',
                   profile=profile, baseline_sha256=baseline_sha256,
                   files={name: dict(bytes=len(data), sha256=digest(data),
                         offset=0 if name == 'baseline.bin' else banks[name][0])
                         for name, data in files.items()},
                   reservations_checked=True, full_firmware_verified=False,
                   backup_provenance_verified=False, semantic_migration_verified=False,
                   hardware_admitted=False, hardware_operations=0)
    return files, receipt


def emit(directory, files, receipt):
    """Exclusive owner-only output; receipt written last, directory fsynced."""
    directory = Path(directory)
    # Recompute rather than trust caller-supplied receipt or component bytes.
    rebuilt, checked = prepare(files['baseline.bin'], files['baseline.bin'],
                               receipt['profile'], receipt['baseline_sha256'])
    if files != rebuilt or receipt != checked:
        raise ValueError('Archive input differs from independently reconstructed backup')
    directory.mkdir(mode=0o700)
    encoded = (json.dumps(receipt, sort_keys=True, indent=2)+'\n').encode()
    for name, data in [*files.items(), ('manifest.json', encoded)]:
        fd = os.open(directory/name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return digest(encoded)


def verify(directory, baseline_sha256, manifest_sha256):
    """External digest pins prevent an edited manifest from blessing lost bytes."""
    expected_digest(baseline_sha256); expected_digest(manifest_sha256)
    directory = Path(directory)
    names = {'baseline.bin', 'vm.bin', *FIXED_BANKS, 'manifest.json'}
    if directory.is_symlink() or {p.name for p in directory.iterdir()} != names:
        raise ValueError('Complete exact archive inventory required')
    for name in names:
        path = directory/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > FLASH_BYTES:
            raise ValueError('Regular bounded private archive files required')
    encoded = (directory/'manifest.json').read_bytes()
    if digest(encoded) != manifest_sha256:
        raise ValueError('Retained manifest digest differs')
    receipt = json.loads(encoded)
    image = (directory/'baseline.bin').read_bytes()
    files, checked = prepare(image, image, receipt['profile'], baseline_sha256)
    if receipt != checked:
        raise ValueError('Manifest differs from reconstructed baseline')
    if any((directory/name).read_bytes() != data for name, data in files.items()):
        raise ValueError('Opaque bank differs from complete baseline')
    return dict(status='lossless-storage-backup-verified', baseline_sha256=baseline_sha256,
                manifest_sha256=manifest_sha256, profile=receipt['profile'],
                semantic_migration_verified=False, physical_rollback_verified=False,
                hardware_admitted=False, hardware_operations=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=PROFILES, required=True)
    parser.add_argument('--backup-a', type=Path, required=True)
    parser.add_argument('--backup-b', type=Path, required=True)
    parser.add_argument('--expected-backup-sha256', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    files, receipt = prepare(args.backup_a.read_bytes(), args.backup_b.read_bytes(),
                             args.profile, args.expected_backup_sha256)
    manifest_sha = emit(args.out, files, receipt)
    print(json.dumps(verify(args.out, args.expected_backup_sha256, manifest_sha), sort_keys=True))


if __name__ == '__main__':
    main()

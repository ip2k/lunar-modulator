#!/usr/bin/env python3
"""MIT. Construct a private, offline FM-1_092 application target.

No USB, loader, flash writer or hardware approval. Retain the recorded raw
layout and independently validate the finished target before emitting it.
The target contains private stock bytes and belongs in an ignored directory.
"""
import argparse
import json
import os
from pathlib import Path
import struct

import raw_flash_profile as raw


def construct(baseline_a, baseline_b, manifest, identity, reference, app, elf,
              diagnostic_profile='inert', expected_audit=None):
    """Return validated target bytes and a receipt, without any file/device I/O.

    Reference file reads and strict validation reuse the existing parser.
    Construction is intentionally separate from its independent target check.
    """
    raw.profile_dump(baseline_a, baseline_b, manifest, identity, reference)
    target = _replace_application(baseline_a, reference, app)
    receipt = raw.validate_target(baseline_a, baseline_b, target, manifest,
                                  identity, reference, app, elf,
                                  diagnostic_profile, expected_audit)
    receipt.update(status='private-raw-diagnostic-constructed-offline',
                   target_bytes=len(target), binary_emitted=False,
                   directory_sector=raw.APP_BASE,
                   installation_order='application data sectors before directory sector',
                   distribution='private stock-derived target; never commit or publish',
                   hardware_approval=False)
    return target, receipt


def _replace_application(baseline_a, reference, app):
    """Pure geometry operation; the caller must validate before emitting bytes."""
    if not isinstance(app, bytes) or not 0 < len(app) <= raw.APP_BYTES:
        raise ValueError('Nonempty immutable app must fit the recorded extent')
    decoded, _ = raw._parse(baseline_a, reference)
    decoded = bytearray(decoded)
    decoded[0x4120:0x4120 + len(app)] = app
    # app.bin: payload CRC, length, then its directory-record CRC.
    struct.pack_into('<H', decoded, 0x4022, raw.crc16(app))
    struct.pack_into('<I', decoded, 0x4028, len(app))
    struct.pack_into('<H', decoded, 0x4020, raw.crc16(decoded[0x4022:0x4040]))
    # app_area_head includes the child directory and preserved original tail.
    struct.pack_into('<H', decoded, 0x4002, raw.crc16(decoded[0x4020:raw.CFG_OFFSET]))
    struct.pack_into('<H', decoded, 0x4000, raw.crc16(decoded[0x4002:0x4020]))
    target = (baseline_a[:raw.APP_BASE]
              + raw.sfc_decode(decoded[raw.APP_BASE:raw.PAYLOAD_END], 0)
              + baseline_a[raw.PAYLOAD_END:])
    return target


def _save(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def emit(directory, target, receipt):
    """Write a new private directory; receipt is the last completion marker.

    A failed/interrupted write leaves an incomplete directory for inspection.
    Never overwrite it or present a target-only directory as completed.
    """
    return _emit_private(directory, target, receipt, 'private-raw-diagnostic-constructed-offline')


def _emit_private(directory, target, receipt, expected_status):
    """Publish a receipt last; only reviewed runtime-specific emitters call this."""
    if (not isinstance(target, bytes) or len(target) != raw.FLASH_BYTES
            or receipt.get('status') != expected_status
            or receipt.get('target_sha256') != raw.digest(target)
            or receipt.get('binary_emitted') is not False
            or receipt.get('hardware_approval') is not False):
        raise ValueError('Exact constructed target and receipt required')
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    _sync_directory(directory.parent)
    _save(directory / 'target.bin', target)
    _sync_directory(directory)
    completed = dict(receipt, binary_emitted=True)
    pending = directory / '.receipt.json.pending'
    _save(pending, (json.dumps(completed, indent=2) + '\n').encode())
    # An exclusive hard link atomically publishes only complete, fsynced bytes.
    # Unlike rename(), it cannot replace an unexpectedly existing final marker.
    os.link(pending, directory / 'receipt.json')
    pending.unlink()
    _sync_directory(directory)
    return completed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-a', 'baseline-b', 'manifest', 'identity',
                 'reference', 'app', 'elf', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--audit', type=Path)
    parser.add_argument('--diagnostic-profile', default='inert')
    args = parser.parse_args()
    target, receipt = construct(
        args.baseline_a.read_bytes(), args.baseline_b.read_bytes(),
        json.loads(args.manifest.read_bytes()), json.loads(args.identity.read_bytes()),
        args.reference, args.app.read_bytes(), args.elf.read_bytes(),
        args.diagnostic_profile,
        json.loads(args.audit.read_bytes()) if args.audit else None)
    result = emit(args.out, target, receipt)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()

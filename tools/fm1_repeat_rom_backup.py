#!/usr/bin/env python3
"""MIT. Single-use dual read after the recorded V8 repeat boot returned to USB.

The old reset stays ambiguous. A fresh passive binding admits only the fixed
RAM-loader inventory, whose inquiry must establish ROM before upload. No reset,
erase, program, eFuse command or retry is present. Pinned isolated modules reuse
the existing SG exchange and durable read worker; their original files and
registries remain untouched. Python and ancestor directories are trusted.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet

BACKUP_SHA = '420288e39757d417f65778d0cb9e802035242466a5ac0a4b1c41b2014ff16b14'
REPEAT_SHA = '74497d2fa5a697a8472ea4d8fcabd7b99ad01daffa96dde062a89357213bd5fc'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
KIND = 'fm1-repeat-returned-rom-fixed-loader-dual-backup'
STATE = 'repeat-request-ambiguous-returned-usb-no-later-device-commands'
_AUTHORIZED = WeakSet()
_OPENING = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular evidence required')
        raw = fp.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('Evidence exceeds bound')
    return raw


def load_source(path, pin, name):
    raw = read_file(path)
    if digest(raw) != pin:
        raise ValueError('Pinned source differs')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def finite(value):
    return type(value) in (float, int) and math.isfinite(value)


def validate_repeat_receipt(raw, campaign, campaign_sha, completed_at, evaluated_at):
    """Evidence only: accept this exact ambiguous three-event attempt, no success inference."""
    rows = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    if len(rows) != 3:
        raise ValueError('Exact single ambiguous repeat request required')
    times = [r.get('time') for r in rows]
    if (not finite(completed_at) or not finite(evaluated_at) or
            not all(finite(t) for t in times) or times != sorted(times) or
            not completed_at <= times[0] <= times[-1] <= evaluated_at):
        raise ValueError('Chronological completed-backup lineage required')
    expected = [dict(event='trace_repeat_reset_prepared', campaign_sha256=campaign_sha,
        returned_backup_campaign_sha256=campaign['returned_backup_campaign_sha256'],
        returned_backup_commands_sha256=campaign['returned_backup_commands_sha256'],
        backup_manifest_sha256=campaign['returned_backup_manifest_sha256'],
        adapter_sha256=REPEAT_SHA, commands=1, flash_operations=0, upload_operations=0,
        kernel_exclusivity=False, boot_observed=False),
        dict(event='reset_submit_intent', phase='trace-repeat-fixed-loader',
            cdb='fc0c00000001ffffffffffffffffffff', in_len=16, out_len=0, retry=False,
            boot_observed=False),
        dict(event='reset_stopped_ambiguous', error='ValueError',
            detail='Exactly one SG device on pinned topology required', retry=False,
            core_reset_observed=False, boot_observed=False)]
    if any(canonical({k: v for k, v in row.items() if k != 'time'}) != canonical(want)
           for row, want in zip(rows, expected)):
        raise ValueError('Exact ambiguous repeat transport transcript required')
    return times[-1]


def validate_snapshot(snapshot, original_usb, terminal_at, now):
    if (set(snapshot) != {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding'} or
            type(snapshot['schema']) is not int or snapshot['schema'] != 1 or
            snapshot['kind'] != 'fm1-passive-repeat-returned-usb' or
            not finite(snapshot['observed_at']) or not finite(now) or
            not terminal_at <= snapshot['observed_at'] <= now or
            not 0 <= now - snapshot['observed_at'] <= 120):
        raise ValueError('Fresh separate passive returned USB snapshot required')
    usb = snapshot['usb_binding']
    if (usb['path'] != original_usb['path'] or usb['busnum'] != original_usb['busnum'] or
            usb['devnum'] == original_usb['devnum'] or usb['vid'] != '4c4a' or usb['pid'] != '8057'):
        raise ValueError('Returned enumeration on exact original port required')


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    snapshot: bytes
    evidence: tuple
    policies: tuple
    bridge: object
    header_type: type
    operations: tuple
    request_inventory_sha256: str
    original_manifest_sha256: str
    parent: Path
    provenance: object
    connection_witness: object
    native: object
    runner: object
    repeat_sha256: str

    def check(self):
        require_prepared(self, check=False)
        for path, data, limit in self.evidence:
            if read_file(path, limit) != data:
                raise ValueError('Frozen repeat-return backup evidence changed')
        for policy in self.policies:
            policy.check_files()
        self.provenance.check()
        if self.request_inventory_sha256 != self.bridge.inventory_digest(self.operations):
            raise ValueError('Frozen fixed inventory changed')


def require_prepared(p, *, check=True):
    if type(p) is not Prepared or p not in _AUTHORIZED:
        raise ValueError('Exact prepared repeat-return backup required')
    if check:
        p.check()


def marker_path(p):
    return p.parent / ('.repeat-return-loader-' + p.repeat_sha256 + '.consumed')


def prepare_campaign(path):
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        raw = read_file(path, limit)
        if expected is not None and digest(raw) != expected:
            raise ValueError('Pinned repeat-return evidence differs')
        evidence.append((path, raw, limit))
        return raw
    raw = freeze(Path(path).absolute(), limit=65536)
    c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'repeat_campaign_path', 'repeat_campaign_sha256',
        'repeat_commands_sha256', 'snapshot_path', 'snapshot_sha256', 'active_session_state',
        'continuous_power_attested', 'no_later_device_commands_attested', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or c['kind'] != KIND or
            c['active_session_state'] != STATE or c['continuous_power_attested'] is not True or
            c['no_later_device_commands_attested'] is not True):
        raise ValueError('Exact separate repeat-return envelope required')
    for key in ('adapter_sha256', 'repeat_campaign_sha256', 'repeat_commands_sha256', 'snapshot_sha256'):
        pin = c[key]
        if not isinstance(pin, str) or len(pin) != 64 or any(ch not in '0123456789abcdef' for ch in pin):
            raise ValueError('Exact lowercase SHA256 pins required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    freeze(root / 'fm1_sdk_trace_repeat_boot.py', REPEAT_SHA)
    freeze(root / 'fm1_sdk_trace_admitted_backup.py', BACKUP_SHA)
    backup = load_source(root / 'fm1_sdk_trace_admitted_backup.py', BACKUP_SHA, '_repeat_return_backup')
    repeat_raw = freeze(c['repeat_campaign_path'], c['repeat_campaign_sha256'], 65536)
    repeat = json.loads(repeat_raw)
    repeat_keys = {'schema', 'kind', 'adapter_sha256', 'returned_backup_campaign_path',
        'returned_backup_campaign_sha256', 'returned_backup_manifest_sha256',
        'returned_backup_commands_sha256', 'continuous_power_attested',
        'no_later_device_commands_attested', 'active_session_state', 'receipt_path'}
    if (set(repeat) != repeat_keys or type(repeat['schema']) is not int or repeat['schema'] != 1 or
            repeat['kind'] != 'fm1-sdk-trace-fixed-loader-repeat-boot' or repeat['adapter_sha256'] != REPEAT_SHA or
            repeat['continuous_power_attested'] is not True or repeat['no_later_device_commands_attested'] is not True or
            repeat['active_session_state'] != 'admitted-trace-fixed-loader-dual-target-backup-no-later-commands'):
        raise ValueError('Exact original repeat campaign required')
    proof = backup.validate_completed_backup(repeat['returned_backup_campaign_path'],
        campaign_sha256=repeat['returned_backup_campaign_sha256'],
        manifest_sha256=repeat['returned_backup_manifest_sha256'],
        commands_sha256=repeat['returned_backup_commands_sha256'], freeze=freeze)
    repeat_receipt = Path(repeat['receipt_path'])
    if repeat_receipt.parent != Path(proof['receipt_path']):
        raise ValueError('Original repeat private origin differs')
    if freeze(repeat_receipt.parent / '.trace-repeat-core-reset.consumed', limit=256) != c['repeat_campaign_sha256'].encode('ascii'):
        raise ValueError('Original repeat consumption required')
    terminal = validate_repeat_receipt(freeze(repeat_receipt / 'commands.jsonl', c['repeat_commands_sha256'], 65536),
        repeat, c['repeat_campaign_sha256'], proof['completed_at'], time.time())
    snapshot_raw = freeze(c['snapshot_path'], c['snapshot_sha256'], 65536)
    snapshot = json.loads(snapshot_raw)
    validate_snapshot(snapshot, proof['usb_binding'], terminal, time.time())
    # Recreate only the historically completed prepared inventory, never its opener.
    old_log = json.loads(read_file(Path(proof['receipt_path']) / 'commands.jsonl', 8 * 1048576).splitlines()[0])
    old, _ = backup._validate_campaign(repeat['returned_backup_campaign_path'], evaluated_at=old_log['time'], completed=True)
    old.bridge.validate_usb(snapshot['usb_binding'])
    if canonical(old.bridge.discover_sg(snapshot['usb_binding'])) != canonical(snapshot['sg_binding']):
        raise ValueError('Fresh passive SG mapping differs')
    destination = Path(c['receipt_path'])
    if (not destination.is_absolute() or destination.parent != repeat_receipt or
            not stat.S_ISDIR(repeat_receipt.lstat().st_mode) or
            stat.S_IMODE(repeat_receipt.stat().st_mode) != 0o700 or os.path.lexists(destination)):
        raise ValueError('Fresh private repeat receipt required')
    p = Prepared(canonical(c), digest(raw), canonical(snapshot), tuple(evidence), old.policies,
        old.bridge, old.header_type, old.operations, old.request_inventory_sha256,
        repeat['returned_backup_manifest_sha256'], repeat_receipt, old.provenance, None,
        old.native, backup, c['repeat_campaign_sha256'])
    if os.path.lexists(marker_path(p)):
        raise ValueError('Repeat-return upload already consumed')
    p.native.Prepared = Prepared
    p.native.require_prepared = require_prepared
    p.native.__file__ = __file__
    _AUTHORIZED.add(p)
    p.check()
    return p


def FixedSG(p, log):
    require_prepared(p)
    if p not in _OPENING or sys.platform != 'linux':
        raise ValueError('Open only inside single-use Linux worker')
    _OPENING.discard(p)
    if read_file(marker_path(p), 256) != p.campaign_sha256.encode('ascii'):
        raise ValueError('Durable single-use marker required before open')
    return p.native.FixedSG(p, log)


def manifest(p, dumps, mapping):
    return dict(schema=1, kind=KIND, campaign_sha256=p.campaign_sha256,
        repeat_campaign_sha256=p.repeat_sha256, repeat_reset_transport_ambiguous=True,
        boot_observed=False, snapshot_sha256=json.loads(p.campaign)['snapshot_sha256'],
        usb_binding=json.loads(p.snapshot)['usb_binding'], sg_binding=mapping,
        current_flash_sha256=TARGET_SHA, identical=True, flash_bytes=1048576,
        commands=8757, flash_readback_only=True, command_completions=True,
        loader_sha256=p.bridge.LOADER_SHA, request_inventory_sha256=p.request_inventory_sha256,
        dumps=dumps, flash_operations=0, reset_operations=0, physical_recovery_verified=False,
        adapter_sha256=json.loads(p.campaign)['adapter_sha256'], worker_sha256=BACKUP_SHA)


def run_campaign(p):
    require_prepared(p)
    runner = p.runner
    runner.require_prepared = require_prepared
    runner.FixedSG = FixedSG
    runner.marker_path = lambda parent, proof: marker_path(p)
    runner.first_event = lambda candidate: dict(event='repeat_return_backup_prepared',
        campaign_sha256=candidate.campaign_sha256, repeat_campaign_sha256=candidate.repeat_sha256,
        commands=8757, flash_operations=0, reset_operations=0, retry=False)
    runner.manifest = manifest
    _OPENING.add(p)
    try:
        return runner.run_campaign(p)
    finally:
        _OPENING.discard(p)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    p = prepare_campaign(args.campaign)
    if args.preflight:
        print(json.dumps(dict(kind=KIND, commands=len(p.operations), flash_operations=0,
            reset_operations=0, campaign_sha256=p.campaign_sha256)))
    else:
        run_campaign(p)


if __name__ == '__main__':
    main()

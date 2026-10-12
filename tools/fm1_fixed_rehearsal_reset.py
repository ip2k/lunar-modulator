#!/usr/bin/env python3
"""MIT. One fixed-loader FC0C arg1 after this exact SDK rehearsal restored NOR.

No upload, status/read probe, flash write, retry or diagnostic boot permission.
Successful request completion does not prove reset or boot. The operator must
attest that the original loader connection has received no later commands.
"""
import argparse
import binascii
import ctypes as C
from dataclasses import dataclass
import fcntl
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

RESET_SOURCE_SHA = 'dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116'
REHEARSAL_SOURCE_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
_AUTHORIZED = WeakSet()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd)
        raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
            raise ValueError('Direct regular evidence required')
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence size bound exceeded')
    return data


def load_source(path, expected, name):
    source = read_file(path)
    if digest(source) != expected:
        raise ValueError('Reviewed executable source changed')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module  # dataclasses inspect their defining module.
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


# Validate the exact incumbent bytes before executing reused SG methods.
reset = load_source(Path(__file__).absolute().with_name('fm1_fixed_loader_reset.py'),
                    RESET_SOURCE_SHA, '_fm1_post_rehearsal_verified_reset')


def wire(op, address=0, payload=b''):
    if op == 0xFC0A:
        return bytes.fromhex('fc0a' + 'ff' * 14), b'', 16
    prefix = op.to_bytes(2, 'big') + address.to_bytes(4, 'big')
    if op == 0xFD05:
        prefix += b'\x01\x00'
    elif op == 0xFB04:
        prefix += b'\x01\x00\x00' + binascii.crc_hqx(payload, 0).to_bytes(2, 'little')
    return prefix.ljust(16, b'\xff'), payload, 256 if op == 0xFD05 else 0 if payload else 16


class Replay:
    """Strict transcript cursor; this performs no transport or device reads."""
    def __init__(self, events):
        self.events, self.position, self.index, self.direction = events, 0, 0, None

    def event(self, name, **fields):
        if self.position >= len(self.events):
            raise ValueError('Incomplete rehearsal transcript')
        actual = dict(self.events[self.position]); actual.pop('time', None)
        if canonical(actual) != canonical(dict(event=name, **fields)):
            raise ValueError('Rehearsal event/order differs at ' + str(self.position))
        self.position += 1

    def command(self, op, address=0, payload=b'', response=None):
        cdb, payload, size = wire(op, address, payload)
        self.event('sg_submit_intent', index=self.index, direction=self.direction,
            cdb=cdb.hex(), out_len=len(payload), in_len=size,
            payload_sha256=digest(payload) if payload else None, retry=False)
        if self.position >= len(self.events):
            raise ValueError('Missing SG completion')
        sha = self.events[self.position].get('response_sha256')
        if (size and (not isinstance(sha, str) or len(sha) != 64 or
                any(c not in '0123456789abcdef' for c in sha)) or not size and sha is not None or
                response is not None and sha != digest(response)):
            raise ValueError('Actual response hash differs')
        self.event('sg_completion', index=self.index, direction=self.direction,
            status=0, masked=0, msg=0, host=0, driver=0, resid=0, info=0,
            sense_len=0, sense_hex='', retry=False, response_sha256=sha)
        self.index += 1

    def read(self, image, address, size):
        for page in range(address, address + size, 256):
            # The reviewed bound reader inserts at most one FC0A before a
            # page when its 0.5-second live timer expires. No other gaps allowed.
            if (self.position < len(self.events) and
                    self.events[self.position].get('cdb') == wire(0xFC0A)[0].hex()):
                self.command(0xFC0A)
            self.command(0xFD05, page, response=image[page:page + 256])


def verify_rehearsal(raw, result, campaign, campaign_sha, sources, baseline, target, order):
    events = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    if not events or len(events) > 100000:
        raise ValueError('Bounded complete rehearsal transcript required')
    times = [e.get('time') for e in events]
    if (not all(type(t) in (int, float) and math.isfinite(t) for t in times) or
            times != sorted(times) or times[-1] > time.time()):
        raise ValueError('Invalid rehearsal chronology')
    r = Replay(events)
    r.event('rehearsal_prepared', campaign_sha256=campaign_sha,
        adapter_sha256=REHEARSAL_SOURCE_SHA, source_sha256=sources,
        sg_binding=campaign['sg_binding'], kernel_exclusivity=False,
        boot_observed=False, physical_recovery_verified=False)
    current, directions = baseline, []
    for direction, desired in (('install', target), ('restore', baseline)):
        r.direction, r.index = direction, 0
        r.command(0xFC0A)
        r.read(current, 0, 1048576)
        changed = 0
        for address in order:
            sector = desired[address:address + 4096]
            actual = current[address:address + 4096]
            r.read(current, address, 4096)
            if actual == sector:
                continue
            if actual != b'\xff' * 4096:
                r.event('durable_intent', operation='erase', address=address)
                r.command(0xFC0A); r.command(0xFB01, address)
                r.event('operation_returned', operation='erase', address=address)
            blank = current[:address] + b'\xff' * 4096 + current[address + 4096:]
            r.read(blank, address, 4096)
            for page in range(address, address + 4096, 256):
                payload = desired[page:page + 256]
                if payload != b'\xff' * 256:
                    r.event('durable_intent', operation='program', address=page)
                    r.command(0xFC0A); r.command(0xFB04, page, payload)
                    r.event('operation_returned', operation='program', address=page)
            current = current[:address] + sector + current[address + 4096:]
            r.read(current, address, 4096)
            r.event('sector_verified', address=address)
            changed += 1
        r.read(desired, 0, 1048576)
        accepted = dict(direction=direction, verified_sha256=digest(desired),
            full_flash_readback_verified=True, sectors_written=changed,
            boot_observed=False, kernel_exclusivity=False)
        r.event('direction_verified', **accepted)
        directions.append(accepted)
    r.event('rehearsal_completed', directions=directions, stock_baseline_restored=True,
            boot_observed=False, physical_recovery_verified=False)
    if r.position != len(events) or canonical(result) != canonical(dict(
            campaign_sha256=campaign_sha, directions=directions, stock_baseline_restored=True,
            boot_observed=False, physical_recovery_verified=False)):
        raise ValueError('Exact successful rehearsal result and terminal completion required')
    return times[-1]


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    backup_manifest_sha256: str
    expected_mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple
    policies: tuple

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact prepared post-rehearsal instance required')
        for path, data, limit in self.evidence:
            if read_file(path, limit) != data:
                raise ValueError('Frozen reset evidence changed')
        for policy in self.policies:
            policy.check_files()


def prepare_campaign(path):
    evidence = []

    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        data = read_file(path, limit)
        if expected is not None and digest(data) != expected:
            raise ValueError('Pinned reset evidence differs')
        evidence.append((path, data, limit))
        return data

    raw = freeze(Path(path).absolute(), limit=65536)
    c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'rehearsal_adapter_path',
        'rehearsal_campaign_path', 'rehearsal_campaign_sha256', 'rehearsal_commands_sha256',
        'rehearsal_result_sha256', 'rehearsal_exit_status', 'journal_sha256',
        'active_session_state', 'usb_binding', 'sg_binding', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-fixed-loader-post-rehearsal-stock-reset' or
            type(c['rehearsal_exit_status']) is not int or c['rehearsal_exit_status'] != 0 or
            c['active_session_state'] != 'same-fixed-loader-restored-rehearsal-no-later-commands'):
        raise ValueError('Exact completed stock-return rehearsal policy required')
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    root = Path(__file__).absolute().parent
    adapter_path = Path(c['rehearsal_adapter_path'])
    if adapter_path != root / 'fm1_sdk_rehearsal.py':
        raise ValueError('Same reviewed source root required')
    freeze(root / 'fm1_fixed_loader_reset.py', RESET_SOURCE_SHA)
    freeze(adapter_path, REHEARSAL_SOURCE_SHA)
    rehearsal = load_source(adapter_path, REHEARSAL_SOURCE_SHA, '_fm1_post_verified_rehearsal')
    for name, sha in rehearsal.SOURCES.items():
        freeze(root / name, sha)
    modules = rehearsal.imports()
    campaign_raw = freeze(c['rehearsal_campaign_path'], c['rehearsal_campaign_sha256'], 65536)
    campaign = json.loads(campaign_raw)
    required = {'schema', 'kind', 'adapter_sha256', 'policy_inputs', 'backup_exit_status',
        'backup_commands_sha256', 'active_session_state', 'sg_binding', 'receipt_path'}
    if (set(campaign) != required or type(campaign['schema']) is not int or campaign['schema'] != 1 or
            campaign['kind'] != 'fm1-exact-sdk-install-restore-rehearsal' or
            campaign['adapter_sha256'] != REHEARSAL_SOURCE_SHA or
            type(campaign['backup_exit_status']) is not int or campaign['backup_exit_status'] != 0 or
            campaign['active_session_state'] != 'matching-backup-no-later-commands' or
            canonical(campaign['sg_binding']) != canonical(c['sg_binding'])):
        raise ValueError('Exact original rehearsal campaign required')
    inputs = campaign['policy_inputs']
    policies = tuple(modules['fm1_bound_sdk_diagnostic'].load_policy(**inputs,
        direction=d, baseline_profile='fixed-loader') for d in ('install', 'restore'))
    plan, journal, baseline, target = modules['fm1_flash_transaction'].load_transaction(inputs['directory'])
    freeze(Path(inputs['directory']) / 'journal.json', c['journal_sha256'], 65536)
    if (digest(baseline) != rehearsal.BASELINE_SHA or digest(target) != rehearsal.TARGET_SHA or
            journal['state'] != 'complete' or journal['direction'] != 'restore' or
            journal['intent'] is not None or journal['verified_sha256'] != rehearsal.BASELINE_SHA or
            plan['writable_ranges'] != [[a, a + 4096] for a in range(0x4000, 0x22000, 4096)] or
            plan['commit_sector'] != 0x4000 or plan['sector_order'] != list(range(0x5000, 0x22000, 4096)) + [0x4000]):
        raise ValueError('Exact complete baseline restore journal required')
    manifest = json.loads(freeze(inputs['manifest_path'], limit=65536))
    bridge = modules['fm1_fixed_loader_backup']
    bridge.validate_usb(c['usb_binding'])
    if (canonical(manifest['usb_binding']) != canonical(c['usb_binding']) or
            canonical(manifest['sg_binding']) != canonical(c['sg_binding'])):
        raise ValueError('Original backup connection required')
    backup_campaign = json.loads(freeze(inputs['campaign_path'], limit=65536))
    backup_log = freeze(inputs['backup_log_path'], campaign['backup_commands_sha256'], 8 * 1048576)
    backup_completed = reset.validate_commands(backup_log, manifest,
        dict(backup_campaign, entry_log_path=inputs['entry_log_path']), bridge)
    receipt = Path(campaign['receipt_path'])
    parent = Path(inputs['manifest_path']).parent
    if receipt.parent != parent or not stat.S_ISDIR(receipt.lstat().st_mode):
        raise ValueError('Original direct rehearsal receipt required')
    result = json.loads(freeze(receipt / 'result.json', c['rehearsal_result_sha256'], 65536))
    commands = freeze(receipt / 'commands.jsonl', c['rehearsal_commands_sha256'], 32 * 1048576)
    first_time = json.loads(commands.splitlines()[0]).get('time')
    if type(first_time) not in (int, float) or first_time < backup_completed:
        raise ValueError('Rehearsal must follow original backup completion')
    verify_rehearsal(commands, result, campaign, c['rehearsal_campaign_sha256'],
                     rehearsal.SOURCES, baseline, target, plan['sector_order'])
    marker = freeze(parent / '.sdk-rehearsal.consumed', limit=256)
    if marker != c['rehearsal_campaign_sha256'].encode('ascii'):
        raise ValueError('Original one-use rehearsal marker required')
    destination = Path(c['receipt_path'])
    if (not destination.is_absolute() or destination.exists() or destination.parent != parent or
            not stat.S_ISDIR(parent.lstat().st_mode) or stat.S_IMODE(parent.stat().st_mode) != 0o700 or
            (parent / '.baseline-core-reset.consumed').exists()):
        raise ValueError('New private stock-return receipt and unreset session required')
    p = Prepared(canonical(c), digest(raw), digest(read_file(inputs['manifest_path'])),
        canonical(c['sg_binding']), bridge, modules['fm1_uboot_read'].SGHeader, tuple(evidence), policies)
    if C.sizeof(p.header_type) != 88:
        raise ValueError('Reviewed Linux SG layout required')
    _AUTHORIZED.add(p); p.check()
    return p


def require_prepared(prepared):
    if not isinstance(prepared, Prepared) or prepared not in _AUTHORIZED:
        raise ValueError('Exact prepared post-rehearsal instance required')
    prepared.check()


class ResetSG(reset.ResetSG):
    """Reuse exact pinned single-request methods with independent authority."""
    def __init__(self, prepared, log):
        require_prepared(prepared)
        self.prepared, self.log = prepared, log
        self.fd, self.consumed, self.failed, self.ioctl_attempts = None, False, False, 0
        self.phase, self.started = 'restored-fixed-loader', time.monotonic()
        self.usb = json.loads(prepared.campaign)['usb_binding']
        try:
            self.mapping = prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping) != prepared.expected_mapping:
                raise ValueError('Original SG connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True; self.close(); raise

    def binding(self):
        self.prepared.check()  # Includes the durable intent-to-ioctl boundary.
        return super().binding()

    def request_reset(self):
        try:
            self.prepared.check()
        except BaseException:
            self.failed = True; self.close(); raise
        return super().request_reset()


def run_campaign(prepared):
    require_prepared(prepared)
    c, bridge = json.loads(prepared.campaign), prepared.bridge
    receipt = Path(c['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False); bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt.parent / '.post-rehearsal-core-reset.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush(); os.fsync(events.fileno()); bridge.sync_dir(receipt)
        transport = None
        try:
            log('post_rehearsal_reset_prepared', campaign_sha256=prepared.campaign_sha256,
                rehearsal_campaign_sha256=c['rehearsal_campaign_sha256'],
                rehearsal_commands_sha256=c['rehearsal_commands_sha256'],
                backup_manifest_sha256=prepared.backup_manifest_sha256,
                adapter_sha256=c['adapter_sha256'], commands=1, flash_operations=0,
                upload_operations=0, kernel_exclusivity=False, boot_observed=False)
            transport = ResetSG(prepared, log)
            result = transport.request_reset()
            log('reset_request_completed', **result, retry=False)
            return result
        except BaseException as exc:
            try:
                log('reset_stopped_ambiguous', error=type(exc).__name__, detail=str(exc),
                    retry=False, core_reset_observed=False, boot_observed=False)
            except OSError:
                pass
            raise
        finally:
            if transport is not None:
                transport.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__':
    main()

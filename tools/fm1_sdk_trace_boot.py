#!/usr/bin/env python3
"""MIT. One trace-target FC0C request, plus separate evidence-only read lineage.

The new install and wire-verifier pins remain closed until independent review.
This module never uploads a loader or reads/writes NOR. A reset request or its
completion does not establish a boot, display result, or physical recovery.
"""
import argparse
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

INSTALL_SHA = None
POLICY_SHA = None
WIRE_VERIFIER_SHA = None
LEGACY_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
APP_SHA = '76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44'
ELF_SHA = 'e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035'
NONCE = '6b5482dbb66b5f45ed73e2f26c4a4657'
_INSTALLS = WeakSet()
_PREPARED = WeakSet()
_CONSUMED = WeakSet()
_LINEAGES = WeakSet()


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
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Direct regular evidence required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp:
            raw = fp.read(limit + 1)
        if len(raw) > limit:
            raise ValueError('Evidence size bound exceeded')
        return raw
    finally:
        if fd is not None:
            os.close(fd)


IMPORTED_SOURCE_SHA256 = digest(read_file(Path(__file__).absolute()))


def pin(value):
    if (not isinstance(value, str) or len(value) != 64
            or any(c not in '0123456789abcdef' for c in value)):
        raise ValueError('Independent successor activation is closed')
    return value


def load_source(path, expected, name):
    raw = read_file(path)
    if digest(raw) != pin(expected):
        raise ValueError('Reviewed executable source changed')
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


# This immutable primitive supplies the strict transcript cursor and the
# previously reviewed single-reset SG methods. Its old factory is never called.
legacy = load_source(Path(__file__).absolute().with_name('fm1_fixed_target_reset.py'),
                     LEGACY_SHA, '_trace_boot_legacy_primitives')


def events_from(raw, maximum=100000):
    events = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    if not events or len(events) > maximum or any(not isinstance(e, dict) for e in events):
        raise ValueError('Bounded complete transcript required')
    times = [e.get('time') for e in events]
    if (not all(type(t) in (int, float) and math.isfinite(t) for t in times)
            or times != sorted(times) or times[-1] > time.time()):
        raise ValueError('Finite chronological actual transcript required')
    return events, times


def verify_install(raw, result, config, campaign_sha, sources, baseline, target, order):
    """Replay every actual baseline, sector and final target response page hash."""
    events, times = events_from(raw)
    r = legacy.Replay(events)
    r.event('trace_install_prepared', campaign_sha256=campaign_sha,
        adapter_sha256=INSTALL_SHA, policy_sha256=POLICY_SHA,
        rehearsal_sha256=legacy.REHEARSAL_SOURCE_SHA, source_sha256=sources,
        target_sha256=TARGET_SHA, trace_nonce=NONCE, sg_binding=config['sg_binding'],
        kernel_exclusivity=False, boot_observed=False,
        physical_recovery_verified=False, stock_restore_preflighted=True)
    r.direction = 'install'
    r.command(0xFC0A); r.read(baseline, 0, 1048576)
    current, changed = baseline, 0
    for address in order:
        sector = target[address:address + 4096]
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
            payload = target[page:page + 256]
            if payload != b'\xff' * 256:
                r.event('durable_intent', operation='program', address=page)
                r.command(0xFC0A); r.command(0xFB04, page, payload)
                r.event('operation_returned', operation='program', address=page)
        current = current[:address] + sector + current[address + 4096:]
        r.read(current, address, 4096)
        r.event('sector_verified', address=address)
        changed += 1
    r.read(target, 0, 1048576)
    accepted = dict(campaign_sha256=campaign_sha, adapter_sha256=INSTALL_SHA,
        policy_sha256=POLICY_SHA, rehearsal_sha256=legacy.REHEARSAL_SOURCE_SHA,
        direction='install', verified_sha256=TARGET_SHA, baseline_sha256=BASELINE_SHA,
        trace_nonce=NONCE, trace_address=0x01c02880, trace_bytes=64,
        full_flash_readback_verified=True, sectors_written=changed, sector_order=order,
        stock_restore_preflighted=True, stock_baseline_restored=False,
        boot_observed=False, display_observed=False, physical_recovery_verified=False,
        kernel_exclusivity=False)
    r.event('trace_install_completed', **accepted)
    if r.position != len(events) or canonical(result) != canonical(accepted) or changed != 30:
        raise ValueError('Exact terminal trace install and all thirty sectors required')
    return times[0], times[-1]


@dataclass(frozen=True, eq=False)
class CompletedInstall:
    config: bytes
    campaign_sha256: str
    completed_at: float
    parent: Path
    manifest_sha256: str
    usb: bytes
    mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple
    policies: tuple

    def check(self):
        if self not in _INSTALLS:
            raise ValueError('Exact replay-created completed install required')
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen completed install evidence changed')
        for policy in self.policies:
            policy.check_files()


def validate_completed_install(path, *, campaign_sha256, commands_sha256,
                               result_sha256, journal_sha256):
    """Offline actual-file replay; grants no physical open or new install."""
    pin(INSTALL_SHA); pin(POLICY_SHA)
    evidence = []
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        raw = read_file(path, limit)
        if expected is not None and digest(raw) != pin(expected):
            raise ValueError('Pinned completed install evidence differs')
        evidence.append((path, raw, limit)); return raw
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), IMPORTED_SOURCE_SHA256)
    freeze(root / 'fm1_fixed_target_reset.py', LEGACY_SHA)
    freeze(root / 'fm1_fixed_loader_reset.py', legacy.RESET_SOURCE_SHA)
    freeze(root / 'fm1_sdk_trace_install.py', INSTALL_SHA)
    freeze(root / 'fm1_bound_sdk_trace.py', POLICY_SHA)
    policy = load_source(root / 'fm1_bound_sdk_trace.py', POLICY_SHA, '_trace_boot_policy')
    policy.require_candidate_pins()
    if (policy.TARGET_SHA != TARGET_SHA or policy.BASELINE_SHA != BASELINE_SHA
            or policy.APP_SHA != APP_SHA or policy.ELF_SHA != ELF_SHA or policy.TRACE_NONCE != NONCE):
        raise ValueError('Exact accepted trace candidate differs')
    runtime, modules = policy.core_modules()
    for name, sha in runtime.SOURCES.items(): freeze(root / name, sha)
    config = json.loads(freeze(path, campaign_sha256, 65536))
    required = {'schema', 'kind', 'adapter_sha256', 'policy_sha256', 'policy_inputs',
        'backup_exit_status', 'backup_commands_sha256', 'active_session_state',
        'sg_binding', 'receipt_path'}
    if (not isinstance(config, dict) or set(config) != required
            or type(config['schema']) is not int or config['schema'] != 1
            or config['kind'] != 'fm1-exact-sdk-recovery-trace-install'
            or config['adapter_sha256'] != INSTALL_SHA or config['policy_sha256'] != POLICY_SHA
            or type(config['backup_exit_status']) is not int or config['backup_exit_status'] != 0
            or config['active_session_state'] != 'matching-fresh-stock-backup-no-later-commands'):
        raise ValueError('Exact completed trace install campaign required')
    inputs = config['policy_inputs']
    policies = tuple(policy.load_policy(**inputs, direction=d, baseline_profile='fixed-loader')
                     for d in ('install', 'restore'))
    plan, journal, baseline, target = modules['fm1_flash_transaction'].load_transaction(inputs['directory'])
    freeze(Path(inputs['directory']) / 'journal.json', journal_sha256, 65536)
    order = list(range(0x5000, 0x22000, 4096)) + [0x4000]
    if (digest(baseline) != BASELINE_SHA or digest(target) != TARGET_SHA
            or journal['state'] != 'complete' or journal['direction'] != 'install'
            or journal['intent'] is not None or journal['verified_sha256'] != TARGET_SHA
            or plan['writable_ranges'] != [[a, a + 4096] for a in range(0x4000, 0x22000, 4096)]
            or plan['commit_sector'] != 0x4000 or plan['sector_order'] != order):
        raise ValueError('Exact complete trace target journal required')
    manifest = json.loads(freeze(inputs['manifest_path'], limit=65536))
    backup_campaign = json.loads(freeze(inputs['campaign_path'], limit=65536))
    backup_log = freeze(inputs['backup_log_path'], config['backup_commands_sha256'], 16 * 1048576)
    bridge = modules['fm1_fixed_loader_backup']
    bridge.validate_usb(manifest['usb_binding'])
    if canonical(manifest['sg_binding']) != canonical(config['sg_binding']):
        raise ValueError('Original complete backup SG binding required')
    backup_completed = legacy.reset.validate_commands(backup_log, manifest,
        dict(backup_campaign, entry_log_path=inputs['entry_log_path']), bridge)
    parent = Path(inputs['manifest_path']).parent
    receipt = Path(config['receipt_path'])
    if (not receipt.is_absolute() or receipt.parent != parent
            or not stat.S_ISDIR(receipt.lstat().st_mode)
            or stat.S_IMODE(receipt.stat().st_mode) != 0o700
            or not stat.S_ISDIR(parent.lstat().st_mode)
            or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('Original direct private completed install receipt required')
    result = json.loads(freeze(receipt / 'result.json', result_sha256, 65536))
    commands = freeze(receipt / 'commands.jsonl', commands_sha256, 32 * 1048576)
    first, ended = verify_install(commands, result, config, campaign_sha256,
        runtime.SOURCES, baseline, target, order)
    if first < backup_completed or first - backup_completed > 130:
        raise ValueError('Completed install must follow its fresh backup admission')
    if freeze(parent / '.sdk-rehearsal.consumed', limit=64) != campaign_sha256.encode('ascii'):
        raise ValueError('Original one-use trace install marker required')
    obj = CompletedInstall(canonical(config), campaign_sha256, ended, parent,
        digest(read_file(inputs['manifest_path'])), canonical(manifest['usb_binding']),
        canonical(config['sg_binding']), bridge, modules['fm1_uboot_read'].SGHeader,
        tuple(evidence), policies)
    if C.sizeof(obj.header_type) != 88:
        raise ValueError('Reviewed Linux SG layout required')
    _INSTALLS.add(obj); obj.check(); return obj


@dataclass(frozen=True, eq=False)
class Prepared:
    campaign: bytes
    campaign_path: Path
    campaign_sha256: str
    install: CompletedInstall
    expected_mapping: bytes
    bridge: object
    header_type: type
    evidence: tuple
    receipt: Path
    marker: Path

    def check(self):
        if self not in _PREPARED:
            raise ValueError('Exact prepared trace boot required')
        self.install.check()
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen trace boot evidence changed')
        if self in _CONSUMED:
            if (read_file(self.marker, 64) != self.campaign_sha256.encode('ascii')
                    or not stat.S_ISDIR(self.receipt.lstat().st_mode)
                    or stat.S_IMODE(self.receipt.stat().st_mode) != 0o700):
                raise ValueError('Consumed trace boot receipt/marker differs')
        elif os.path.lexists(self.marker) or os.path.lexists(self.receipt):
            raise ValueError('Trace boot session already consumed')


def prepare_campaign(path):
    path = Path(path).absolute(); raw = read_file(path, 65536); c = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'install_campaign_path',
        'install_campaign_sha256', 'install_commands_sha256', 'install_result_sha256',
        'install_exit_status', 'journal_sha256', 'active_session_state', 'usb_binding',
        'sg_binding', 'receipt_path', 'target_sha256', 'target_boot_authorization'}
    if (not isinstance(c, dict) or set(c) != required
            or type(c['schema']) is not int or c['schema'] != 1
            or c['kind'] != 'fm1-fixed-loader-sdk-trace-target-reset'
            or c['adapter_sha256'] != IMPORTED_SOURCE_SHA256
            or type(c['install_exit_status']) is not int or c['install_exit_status'] != 0
            or c['active_session_state'] != 'same-fixed-loader-installed-trace-target-no-later-commands'
            or c['target_sha256'] != TARGET_SHA
            or c['target_boot_authorization'] != 'exact-sdk-recovery-trace-diagnostic'):
        raise ValueError('Exact completed trace target boot campaign required')
    installed = validate_completed_install(c['install_campaign_path'],
        campaign_sha256=c['install_campaign_sha256'], commands_sha256=c['install_commands_sha256'],
        result_sha256=c['install_result_sha256'], journal_sha256=c['journal_sha256'])
    if canonical(c['usb_binding']) != installed.usb or canonical(c['sg_binding']) != installed.mapping:
        raise ValueError('Same completed trace install connection required')
    receipt = Path(c['receipt_path']); marker = installed.parent / '.target-core-reset.consumed'
    if (not receipt.is_absolute() or receipt.parent != installed.parent
            or any(os.path.lexists(installed.parent / name) for name in
                ('.baseline-core-reset.consumed', '.post-rehearsal-core-reset.consumed',
                 '.target-core-reset.consumed'))):
        raise ValueError('New private boot receipt and unreset loader session required')
    obj = Prepared(canonical(c), path, digest(raw), installed, installed.mapping,
        installed.bridge, installed.header_type,
        ((path, raw, 65536), (Path(__file__).absolute(), read_file(Path(__file__).absolute()), 2 * 1048576)),
        receipt, marker)
    _PREPARED.add(obj); obj.check(); return obj


def require_prepared(obj):
    if not isinstance(obj, Prepared) or obj not in _PREPARED:
        raise ValueError('Exact prepared trace boot instance required')
    obj.check()


class ResetSG(legacy.reset.ResetSG):
    """Only the frozen single-request methods; separate exact new authority."""
    def __init__(self, prepared, log):
        require_prepared(prepared)
        if prepared not in _CONSUMED:
            raise ValueError('Open only after durable one-use trace boot marker')
        self.prepared, self.log = prepared, log
        self.fd, self.consumed, self.failed, self.ioctl_attempts = None, False, False, 0
        self.phase, self.started = 'installed-fixed-loader', time.monotonic()
        self.usb = json.loads(prepared.campaign)['usb_binding']
        try:
            self.mapping = prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping) != prepared.expected_mapping:
                raise ValueError('Original trace SG connection replaced')
            self.fd = os.open(self.mapping['node'], os.O_RDWR | os.O_NOFOLLOW | os.O_CLOEXEC)
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.binding()
        except BaseException:
            self.failed = True; self.close(); raise

    def binding(self):
        require_prepared(self.prepared)
        return super().binding()

    def request_reset(self):
        try:
            require_prepared(self.prepared)
        except BaseException:
            self.failed = True; self.close(); raise
        return super().request_reset()


def run_campaign(prepared):
    require_prepared(prepared)
    c, bridge, receipt = json.loads(prepared.campaign), prepared.bridge, prepared.receipt
    receipt.mkdir(mode=0o700, exist_ok=False); bridge.sync_dir(receipt.parent)
    with bridge.private_file(prepared.marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent); _CONSUMED.add(prepared)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush(); os.fsync(events.fileno()); bridge.sync_dir(receipt)
        transport = None
        try:
            log('trace_target_reset_prepared', campaign_sha256=prepared.campaign_sha256,
                install_campaign_sha256=c['install_campaign_sha256'],
                install_commands_sha256=c['install_commands_sha256'], target_sha256=TARGET_SHA,
                trace_nonce=NONCE, backup_manifest_sha256=prepared.install.manifest_sha256,
                adapter_sha256=c['adapter_sha256'], usb_binding=c['usb_binding'], sg_binding=c['sg_binding'],
                commands=1, flash_operations=0, upload_operations=0, kernel_exclusivity=False,
                boot_observed=False, display_observed=False, physical_recovery_verified=False)
            transport = ResetSG(prepared, log)
            result = transport.request_reset()
            log('reset_request_completed', **result, retry=False,
                display_observed=False, physical_recovery_verified=False)
            return result
        except BaseException as exc:
            try:
                log('reset_stopped_ambiguous', error=type(exc).__name__, detail=str(exc), retry=False,
                    core_reset_observed=False, boot_observed=False, display_observed=False,
                    physical_recovery_verified=False)
            except OSError: pass
            raise
        finally:
            if transport is not None: transport.close()


@dataclass(frozen=True, eq=False)
class ReadLineage:
    binding: bytes
    parent: Path
    installed: CompletedInstall
    evidence: tuple

    def check(self):
        if self not in _LINEAGES:
            raise ValueError('Exact replay-created trace read lineage required')
        self.installed.check()
        for path, raw, limit in self.evidence:
            if read_file(path, limit) != raw:
                raise ValueError('Frozen terminal trace boot evidence changed')

    def read_binding(self):
        self.check(); return json.loads(self.binding)

    def read_receipt_parent(self):
        self.check(); return self.parent


def require_read_lineage(obj):
    if not isinstance(obj, ReadLineage) or obj not in _LINEAGES:
        raise ValueError('Exact independently registered trace boot lineage required')
    obj.check()


def prepare_read_lineage(path):
    """Closed until a reviewed actual-wire verifier exists; no caller proof flags."""
    pin(WIRE_VERIFIER_SHA)
    raise ValueError('Actual wire/terminal boot lineage successor not yet implemented')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux': raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__': main()

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
import re
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
                               result_sha256, journal_sha256, journal_path=None):
    """Offline actual-file replay; grants no physical open or new install.

    A preserved original journal permits historical proof after a later stock
    restoration. The executable reset factory always uses the current journal.
    """
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
    transaction = modules['fm1_flash_transaction']
    plan, journal, baseline, target = transaction.load_transaction(inputs['directory'])
    original_journal = (Path(inputs['directory']) / 'journal.json'
                        if journal_path is None else Path(journal_path))
    if journal_path is not None:
        if (not original_journal.is_absolute()
                or not stat.S_ISDIR(original_journal.parent.lstat().st_mode)
                or stat.S_IMODE(original_journal.parent.stat().st_mode) != 0o700
                or stat.S_IMODE(original_journal.lstat().st_mode) != 0o600):
            raise ValueError('Direct private preserved install journal required')
    journal = json.loads(freeze(original_journal, journal_sha256, 65536))
    verify_install_journal(journal, plan, transaction)
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


def verify_install_journal(journal, plan, transaction):
    """Validate the original journal against the still sealed transaction plan."""
    if (type(journal) is not dict or type(journal.get('schema')) is not int
            or journal['schema'] != 1
            or journal.get('record_sha256') != digest(transaction.encoded(
                {k: v for k, v in journal.items() if k != 'record_sha256'}))
            or journal.get('plan_sha256') != digest(transaction.encoded(plan))
            or journal.get('sector_order') != plan['sector_order']
            or journal.get('state') != 'complete' or journal.get('direction') != 'install'
            or journal.get('intent') is not None or journal.get('verified_sha256') != TARGET_SHA):
        raise ValueError('Exact original completed install journal required')


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


def boot_config(raw):
    c = json.loads(raw)
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
    return c


def prepare_campaign(path):
    path = Path(path).absolute(); raw = read_file(path, 65536); c = boot_config(raw)
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


def verify_capture_lifecycle(opened, stopped, exited, times, snapshot, campaign_sha):
    """Bind the child attempt to its owned, open USBmon capture process group."""
    if (type(opened) is not dict or set(opened) !=
            {'time', 'timeout_pid', 'cat_pid', 'process_group', 'open_capture_fd'}
            or type(stopped) is not dict or set(stopped) !=
            {'time', 'process_group', 'returncode', 'owned_processes_only'}
            or type(exited) is not dict or set(exited) !=
            {'time', 'campaign_sha256', 'exit_status', 'capture_alive_after_child',
             'retry', 'reset_completed_attested', 'boot_cause_proven'}
            or any(type(opened[k]) is not int or opened[k] <= 0
                   for k in ('timeout_pid', 'cat_pid', 'process_group'))
            or opened['timeout_pid'] != opened['process_group']
            or opened['cat_pid'] == opened['process_group']
            or type(stopped['process_group']) is not int
            or stopped['process_group'] != opened['process_group']
            or type(stopped['returncode']) is not int or stopped['returncode'] != -15
            or opened['open_capture_fd'] is not True or stopped['owned_processes_only'] is not True
            or exited['capture_alive_after_child'] is not True
            or exited['campaign_sha256'] != campaign_sha
            or type(exited['exit_status']) is not int or exited['exit_status'] not in (0, 1)
            or any(exited[k] is not False for k in
                   ('retry', 'reset_completed_attested', 'boot_cause_proven'))):
        raise ValueError('Exact owned capture and child-exit lifecycle required')
    sequence = [opened['time'], times[0], times[1], times[-1], exited['time'],
                snapshot['observed_at'], stopped['time']]
    if (any(type(t) not in (int, float) or not math.isfinite(t) or t < 0 for t in sequence)
            or sequence != sorted(sequence) or stopped['time'] > time.time()
            or opened['time'] == times[0] or times[-1] == exited['time']):
        raise ValueError('Capture must bracket the actual reset and returned-ROM observation')


def verify_rom_snapshot(snapshot, binding):
    """Check historical passive mapping; the live reader enforces freshness anew."""
    if (type(snapshot) is not dict or set(snapshot) !=
            {'schema', 'kind', 'observed_at', 'usb_binding', 'sg_binding',
             'target_boot_campaign_sha256', 'quiet_state'}
            or type(snapshot['schema']) is not int or snapshot['schema'] != 1
            or snapshot['kind'] != 'fm1-passive-post-trace-boot-rom'
            or snapshot['quiet_state'] != 'initial-rom-no-later-commands-no-loader-upload'
            or snapshot['target_boot_campaign_sha256'] != binding['boot_campaign_sha256']
            or type(snapshot['observed_at']) not in (int, float)
            or not math.isfinite(snapshot['observed_at'])
            or not binding['boot_completed_at'] <= snapshot['observed_at'] <= time.time()):
        raise ValueError('Original passive post-trace-boot ROM snapshot required')
    usb, old = snapshot['usb_binding'], binding['usb_binding']
    if (type(usb) is not dict or set(usb) != {'path', 'busnum', 'devnum', 'vid', 'pid'}
            or type(usb['path']) is not str
            or not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*(?:\.[1-9][0-9]*)*', usb['path'])
            or any(type(usb[n]) is not str or not re.fullmatch('[1-9][0-9]*', usb[n])
                   for n in ('busnum', 'devnum'))
            or usb['path'].split('-')[0] != usb['busnum']
            or usb['vid'] != '4c4a' or usb['pid'] != '8057'
            or any(usb[n] != old[n] for n in ('path', 'busnum', 'vid', 'pid'))
            or usb['devnum'] == old['devnum']):
        raise ValueError('Original port and changed ROM USB address required')
    sg, old_sg = snapshot['sg_binding'], binding['sg_binding']
    paths = ('node', 'class', 'device', 'usb')
    identities = ('node_identity', 'class_identity', 'device_identity', 'usb_identity')
    if (type(sg) is not dict or set(sg) != set(paths + identities)
            or any(type(sg[n]) is not str or not Path(sg[n]).is_absolute() for n in paths)
            or any(type(sg[n]) is not list or len(sg[n]) != 3
                   or any(type(v) is not int or v < 0 for v in sg[n]) for n in identities)
            or Path(sg['usb']).name != usb['path']
            or sg['usb_identity'] == old_sg['usb_identity']
            or sg['node_identity'] == old_sg['node_identity']):
        raise ValueError('Changed full passive SG/sysfs mapping required')


def prepare_read_lineage(path, *, install_journal_path=None):
    """Replay original files and wire traffic; grants no device opener itself."""
    pin(WIRE_VERIFIER_SHA); pin(INSTALL_SHA); pin(POLICY_SHA)
    evidence = []
    def freeze(path, expected=None, limit=65536):
        path = Path(path); raw = read_file(path, limit)
        if expected is not None and digest(raw) != pin(expected):
            raise ValueError('Pinned trace boot lineage evidence differs')
        evidence.append((path, raw, limit)); return raw
    own = Path(__file__).absolute(); root = own.parent
    freeze(own, IMPORTED_SOURCE_SHA256, 2 * 1048576)
    freeze(root / 'fm1_reset_wire.py', WIRE_VERIFIER_SHA, 2 * 1048576)
    wire = load_source(root / 'fm1_reset_wire.py', WIRE_VERIFIER_SHA, '_trace_boot_wire')
    raw = freeze(path); c = json.loads(raw)
    pairs = ('capture', 'capture_open', 'capture_stop', 'boot_exit', 'rom_snapshot')
    required = {'schema', 'kind', 'adapter_sha256', 'boot_campaign_path',
                'boot_campaign_sha256', 'boot_commands_sha256', 'wire_verifier_sha256'}
    required.update(key for name in pairs for key in (name + '_path', name + '_sha256'))
    if (type(c) is not dict or set(c) != required
            or type(c['schema']) is not int or c['schema'] != 1
            or c['kind'] != 'fm1-exact-sdk-trace-boot-read-lineage'
            or c['adapter_sha256'] != IMPORTED_SOURCE_SHA256
            or c['wire_verifier_sha256'] != WIRE_VERIFIER_SHA):
        raise ValueError('Exact trace boot/read lineage campaign required')
    boot_raw = freeze(c['boot_campaign_path'], c['boot_campaign_sha256'])
    boot = boot_config(boot_raw)
    installed = validate_completed_install(boot['install_campaign_path'],
        campaign_sha256=boot['install_campaign_sha256'], commands_sha256=boot['install_commands_sha256'],
        result_sha256=boot['install_result_sha256'], journal_sha256=boot['journal_sha256'],
        journal_path=install_journal_path)
    if canonical(boot['usb_binding']) != installed.usb or canonical(boot['sg_binding']) != installed.mapping:
        raise ValueError('Original completed trace installation connection required')
    receipt = Path(boot['receipt_path'])
    if (not receipt.is_absolute() or receipt.parent != installed.parent
            or not stat.S_ISDIR(receipt.lstat().st_mode)
            or stat.S_IMODE(receipt.stat().st_mode) != 0o700):
        raise ValueError('Original direct private trace boot receipt required')
    if freeze(installed.parent / '.target-core-reset.consumed', limit=64) != c['boot_campaign_sha256'].encode('ascii'):
        raise ValueError('Original consumed trace boot marker required')
    commands = freeze(receipt / 'commands.jsonl', c['boot_commands_sha256'])
    events, times = events_from(commands)
    if (times[0] < installed.completed_at or events[0].get('trace_nonce') != NONCE
            or events[0].get('backup_manifest_sha256') != installed.manifest_sha256):
        raise ValueError('Trace reset must follow exact verified installation')
    originals = {name: freeze(c[name + '_path'], c[name + '_sha256'],
                             16 * 1048576 if name == 'capture' else 65536) for name in pairs}
    snapshot = json.loads(originals['rom_snapshot'])
    binding = dict(boot_campaign_sha256=c['boot_campaign_sha256'], boot_completed_at=times[-1],
                   usb_binding=boot['usb_binding'], sg_binding=boot['sg_binding'],
                   app_sha256=APP_SHA, elf_sha256=ELF_SHA, nonce_hex=NONCE)
    verify_rom_snapshot(snapshot, binding)
    wire.validate(originals['capture'], commands, boot_raw, boot['usb_binding'], snapshot, times[-1])
    exited = json.loads(originals['boot_exit'])
    verify_capture_lifecycle(json.loads(originals['capture_open']), json.loads(originals['capture_stop']),
                             exited, times, snapshot, c['boot_campaign_sha256'])
    expected_exit = 0 if events[-1]['event'] == 'reset_request_completed' else 1
    if exited['exit_status'] != expected_exit:
        raise ValueError('Original child exit disagrees with terminal reset event')
    obj = ReadLineage(canonical(binding), installed.parent, installed, tuple(evidence))
    _LINEAGES.add(obj); obj.check(); return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux': raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__ == '__main__': main()

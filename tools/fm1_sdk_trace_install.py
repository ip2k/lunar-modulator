#!/usr/bin/env python3
"""MIT. One exact private recovery-trace install from a fresh stock backup.

No entry/upload/reset/boot or retry. The separate actual-file policy must be
independently accepted before POLICY_SHA is bound. This new factory reuses only
the pinned SG implementation, without changing its globals or old factories.
"""
import argparse
import ctypes
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

POLICY_SHA = '54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835'
BACKUP_ADMISSION_SECONDS = 120
_AUTHORIZED = WeakSet()
_CONSUMED = WeakSet()
STATE = 'matching-fresh-stock-backup-no-later-commands'
KIND = 'fm1-exact-sdk-recovery-trace-install'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute():
        raise ValueError('Absolute direct input required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError('Bounded regular input required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp:
            data = fp.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Input exceeds size bound')
        return data
    finally:
        if fd is not None:
            os.close(fd)


def policy_module():
    if not isinstance(POLICY_SHA, str) or len(POLICY_SHA) != 64:
        raise ValueError('Reviewed trace policy activation is closed')
    path = Path(__file__).absolute().with_name('fm1_bound_sdk_trace.py')
    source = read_file(path)
    if digest(source) != POLICY_SHA:
        raise ValueError('Exact trace policy source changed')
    name = '_verified_sdk_trace_policy'
    module = types.ModuleType(name); module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    module.require_candidate_pins()
    return module


@dataclass(frozen=True, eq=False)
class Prepared:
    config: bytes
    campaign_path: Path
    campaign_sha256: str
    adapter_sha256: str
    policy_sha256: str
    policies: tuple
    mapping: bytes
    bridge: object
    header_type: type
    runtime: object
    policy_module: object
    admission_time: float
    source: bytes
    policy_source: bytes
    receipt: Path
    marker: Path

    def check_absence(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact new prepared trace install required')
        if self in _CONSUMED:
            if read_file(self.marker, 64) != self.campaign_sha256.encode('ascii'):
                raise ValueError('Consumed trace marker changed')
        elif os.path.lexists(self.receipt) or os.path.lexists(self.marker):
            raise ValueError('Backup session or destination already consumed')

    def check(self):
        self.check_absence()
        if (read_file(Path(__file__).absolute()) != self.source
                or read_file(Path(self.policy_module.__file__).absolute()) != self.policy_source
                or digest(read_file(self.campaign_path, 65536)) != self.campaign_sha256):
            raise ValueError('Frozen trace install source/campaign changed')
        self.runtime.check_sources()
        if (len(self.policies) != 2 or self.policies[0].direction != 'install'
                or self.policies[1].direction != 'restore'):
            raise ValueError('Install plus independently preflighted restore required')
        for policy in self.policies:
            policy.check_files()


def prepare_campaign(path):
    """Fresh backup gate is admission-only; immutable files persist during install."""
    p = policy_module()
    r, modules = p.core_modules()
    path = Path(path).absolute(); raw = read_file(path, 65536)
    config = json.loads(raw)
    required = {'schema', 'kind', 'adapter_sha256', 'policy_sha256', 'policy_inputs',
                'backup_exit_status', 'backup_commands_sha256', 'active_session_state',
                'sg_binding', 'receipt_path'}
    if (not isinstance(config, dict) or set(config) != required
            or type(config['schema']) is not int or config['schema'] != 1
            or config['kind'] != KIND or config['policy_sha256'] != POLICY_SHA
            or type(config['backup_exit_status']) is not int or config['backup_exit_status'] != 0
            or config['active_session_state'] != STATE
            or config['adapter_sha256'] != digest(read_file(Path(__file__).absolute()))):
        raise ValueError('Exact reviewed trace install campaign required')
    inputs = config['policy_inputs']
    expected = {'directory', 'manifest_path', 'identity_path', 'reference', 'app_path',
                'elf_path', 'campaign_path', 'entry_log_path', 'backup_log_path',
                'loader_path', 'profile_path', 'audit_path', 'build_manifest_path', 'trace_review_path'}
    if (not isinstance(inputs, dict) or set(inputs) != expected
            or any(not isinstance(v, str) or not Path(v).is_absolute() for v in inputs.values())):
        raise ValueError('Exact absolute trace policy paths required')
    policies = tuple(p.load_policy(**inputs, direction=d, baseline_profile='fixed-loader')
                     for d in ('install', 'restore'))
    install, restore = policies
    plan, journal, baseline, target = modules['fm1_flash_transaction'].load_transaction(inputs['directory'])
    if (digest(baseline) != p.BASELINE_SHA or digest(target) != p.TARGET_SHA
            or journal['state'] != 'prepared' or journal['direction'] is not None
            or install.plan_bytes != restore.plan_bytes
            or list(install.sectors) != [a for a, _ in plan['writable_ranges']]):
        raise ValueError('Exact untouched new trace transaction required')
    manifest = json.loads(read_file(inputs['manifest_path'], 65536))
    backup_campaign = json.loads(read_file(inputs['campaign_path'], 65536))
    log = read_file(inputs['backup_log_path'], 16 * 1048576)
    if (digest(log) != config['backup_commands_sha256']
            or r.canonical(manifest['sg_binding']) != r.canonical(config['sg_binding'])
            or manifest['dumps'][0]['sha256'] != p.BASELINE_SHA
            or manifest['dumps'][1]['sha256'] != p.BASELINE_SHA):
        raise ValueError('Exact full stock backup and bound connection required')
    bridge = modules['fm1_fixed_loader_backup']
    replay_campaign = dict(backup_campaign, entry_log_path=inputs['entry_log_path'])
    modules['fm1_fixed_loader_reset'].validate_commands(log, manifest, replay_campaign, bridge)
    ended = json.loads(log.splitlines()[-1])['time']; now = time.time()
    if (not math.isfinite(now) or type(ended) not in (int, float)
            or not math.isfinite(ended) or not 0 <= now - ended <= BACKUP_ADMISSION_SECONDS):
        raise ValueError('Fresh completed backup admission required')
    header = modules['fm1_uboot_read'].SGHeader
    if ctypes.sizeof(header) != 88:
        raise ValueError('Reviewed Linux SG_IO layout required')
    parent = Path(inputs['manifest_path']).parent
    destination = Path(config['receipt_path'])
    if (not destination.is_absolute() or destination.parent != parent
            or Path(backup_campaign['receipt_path']) != parent
            or not stat.S_ISDIR(parent.lstat().st_mode)
            or stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New direct receipt under exact private backup parent required')
    result = Prepared(r.canonical(config), path, digest(raw), config['adapter_sha256'], POLICY_SHA,
        policies, r.canonical(config['sg_binding']), bridge, header, r, p, now,
        read_file(Path(__file__).absolute()), read_file(Path(p.__file__).absolute()),
        destination, parent / '.sdk-rehearsal.consumed')
    _AUTHORIZED.add(result); result.check()
    return result


def run_campaign(prepared):
    prepared.check()
    # No physical handle may open before the exact exclusive durable marker.
    bridge, r, p = prepared.bridge, prepared.runtime, prepared.policy_module
    receipt = prepared.receipt
    receipt.mkdir(mode=0o700, exist_ok=False); bridge.sync_dir(receipt.parent)
    with bridge.private_file(prepared.marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt.parent); _CONSUMED.add(prepared)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields)) + '\n')
            events.flush(); os.fsync(events.fileno()); bridge.sync_dir(receipt)
        class TraceSG(r.RehearsalSG):
            def binding(self):
                prepared.check_absence()
                return super().binding()
        try:
            log('trace_install_prepared', campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=prepared.adapter_sha256, policy_sha256=prepared.policy_sha256,
                rehearsal_sha256=p.REHEARSAL_SHA, source_sha256=r.SOURCES,
                target_sha256=p.TARGET_SHA, trace_nonce=p.TRACE_NONCE,
                sg_binding=json.loads(prepared.mapping), kernel_exclusivity=False,
                boot_observed=False, physical_recovery_verified=False, stock_restore_preflighted=True)
            if not 0 <= time.time() - prepared.admission_time <= 10:
                raise ValueError('Prepared trace opening window expired')
            policy = prepared.policies[0]
            transport = TraceSG(prepared, policy, log)
            try:
                result = policy.bind(transport).run(checkpoint=log)
            finally:
                transport.close()
            prepared.check()
            if result['verified_sha256'] != p.TARGET_SHA:
                raise ValueError('Final complete trace NOR verification differs')
            result = dict(campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=prepared.adapter_sha256, policy_sha256=prepared.policy_sha256,
                rehearsal_sha256=p.REHEARSAL_SHA, direction='install',
                verified_sha256=p.TARGET_SHA, baseline_sha256=p.BASELINE_SHA,
                trace_nonce=p.TRACE_NONCE, trace_address=p.TRACE_ADDRESS, trace_bytes=p.TRACE_BYTES,
                full_flash_readback_verified=True, sectors_written=result['sectors_written'],
                sector_order=json.loads(policy.plan_bytes)['sector_order'],
                stock_restore_preflighted=True, stock_baseline_restored=False,
                boot_observed=False, display_observed=False, physical_recovery_verified=False,
                kernel_exclusivity=False)
            log('trace_install_completed', **result)
            with bridge.private_file(receipt / 'result.json', 'w') as fp:
                json.dump(result, fp, indent=2); fp.write('\n'); fp.flush(); os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            try:
                (receipt / 'result.json').unlink(missing_ok=True); bridge.sync_dir(receipt)
            except OSError: pass
            try:
                log('trace_install_stopped_ambiguous', error=type(exc).__name__, detail=str(exc),
                    retry=False, stock_baseline_restored=False, boot_observed=False)
            except OSError: pass
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    args = parser.parse_args()
    if sys.platform != 'linux': raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))

if __name__ == '__main__': main()

#!/usr/bin/env python3
"""MIT. Distinct closed stock restore after canonical preparation-stop target backup.

Pinned private f583 policy/transport/replay kernels; own envelope, registry,
receipt and marker. No upload/reset/retry. New backup source is independently pinned
after source/runtime review. Private-host operator premises apply.
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

KERNEL_SOURCE_SHA = 'f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33'
BACKUP_SOURCE_SHA = None  # Closed until genuine preparation-stop backup is verified.
POLICY_SOURCE_SHA = '54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835'  # New trace policy independently accepted first.
REHEARSAL_SOURCE_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
BASELINE_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
REPLAY_SOURCE_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
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
            raise ValueError('Regular evidence required')
        data = fp.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Evidence exceeds bound')
    return data


def load_source(path, expected, name):
    source = read_file(path)
    if not isinstance(expected, str) or digest(source) != expected:
        raise ValueError('Reviewed dependency has not frozen or changed')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


@dataclass(frozen=True, eq=False)
class Prepared:
    legacy: object
    kernel: object
    provenance: object

    def __getattr__(self, name):
        return getattr(self.legacy, name)

    def check(self):
        require_prepared(self, check=False)
        self.legacy.check()


def require_prepared(prepared, *, check=True):
    if type(prepared) is not Prepared or prepared not in _AUTHORIZED:
        raise ValueError('Exact trace-target stock-restore factory instance required')
    if check:
        prepared.check()


def transport_type(prepared):
    require_prepared(prepared)
    base = prepared.kernel.transport_type(prepared.legacy)
    class RestoreSG(base):
        def __init__(self, policy, log):
            require_prepared(prepared)
            super().__init__(policy, log)
        def binding(self):
            require_prepared(prepared, check=False)
            prepared.provenance.check_pending()
            return super().binding()
        def validate_wire(self, cdb, payload, in_size):
            require_prepared(prepared, check=False)
            return super().validate_wire(cdb, payload, in_size)
    return RestoreSG


def prepare_campaign(path):
    """All evidence gates precede discovery/open. Only a completed target start."""
    if BACKUP_SOURCE_SHA is None or POLICY_SOURCE_SHA is None:
        raise ValueError('Reviewed trace-target backup dependency is not frozen')
    kernel_path = Path(__file__).absolute().parent / 'fm1_returned_rom_stock_restore.py'
    kernel = load_source(kernel_path, KERNEL_SOURCE_SHA, '_preparation_stop_stock_restore_kernel')
    evidence = [(kernel_path, read_file(kernel_path), 2 * 1048576)]
    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        data = read_file(path, limit)
        if expected is not None and digest(data) != expected:
            raise ValueError('Pinned actual evidence differs')
        evidence.append((path, data, limit))
        return data
    raw = freeze(Path(path).absolute(), limit=65536)
    c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'returned_backup_campaign_path',
        'returned_backup_campaign_sha256', 'returned_backup_manifest_sha256',
        'returned_backup_commands_sha256', 'returned_backup_exit_status',
        'original_install_campaign_path', 'original_install_campaign_sha256',
        'install_journal_sha256', 'active_session_state', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-sdk-preparation-stop-stock-restore-only' or
            type(c['returned_backup_exit_status']) is not int or c['returned_backup_exit_status'] != 0 or
            c['active_session_state'] != 'preparation-stop-fixed-loader-dual-target-backup-no-later-commands'):
        raise ValueError('Exact restore-only returned-loader campaign required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    backup_path = root / 'fm1_sdk_prepare_stop_backup.py'
    freeze(backup_path, BACKUP_SOURCE_SHA)
    backup = load_source(backup_path, BACKUP_SOURCE_SHA, '_returned_restore_backup')
    # This evidence-only helper replays completed receipts without old opener
    # authority or absent-marker checks. It must not be replaced by prepare().
    proof = backup.validate_completed_backup(c['returned_backup_campaign_path'],
        campaign_sha256=c['returned_backup_campaign_sha256'],
        manifest_sha256=c['returned_backup_manifest_sha256'],
        commands_sha256=c['returned_backup_commands_sha256'], freeze=freeze)
    rehearsal_path = root / 'fm1_sdk_rehearsal.py'
    freeze(rehearsal_path, REHEARSAL_SOURCE_SHA)
    rehearsal = load_source(rehearsal_path, REHEARSAL_SOURCE_SHA, '_returned_restore_rehearsal')
    for name, sha in rehearsal.SOURCES.items(): freeze(root / name, sha)
    modules = rehearsal.imports()
    original = json.loads(freeze(c['original_install_campaign_path'],
        c['original_install_campaign_sha256'], 65536))
    if (c['original_install_campaign_sha256'] != proof['original_install_campaign_sha256'] or
            canonical(original['policy_inputs']) != canonical(proof['policy_inputs'])):
        raise ValueError('Genuine original SDK/stock campaign lineage differs')
    policy_path = root / 'fm1_bound_sdk_trace.py'
    freeze(policy_path, POLICY_SOURCE_SHA)
    trace_policy = load_source(policy_path, POLICY_SOURCE_SHA, '_trace_restore_policy')
    old = trace_policy.load_policy(**original['policy_inputs'],
        direction='restore', baseline_profile='fixed-loader')
    tx = modules['fm1_flash_transaction']
    plan, journal, baseline, target = tx.load_transaction(old.directory)
    journal_path = old.directory / 'journal.json'
    initial_journal = read_file(journal_path, 65536)
    if (digest(initial_journal) != c['install_journal_sha256'] or
            digest(initial_journal) != proof['install_journal_sha256'] or
            journal['state'] != 'complete' or journal['direction'] != 'install' or journal['intent'] is not None or
            journal['verified_sha256'] != TARGET_SHA or journal['sector_order'] != plan['sector_order'] or
            plan['sector_order'] != list(range(0x5000, 0x22000, 4096)) + [0x4000] or
            digest(baseline) != BASELINE_SHA or digest(target) != TARGET_SHA):
        raise ValueError('Exact genuine completed installation and 30-sector plan required')
    # The original journal is deliberately mutable during the genuine restore.
    # Its initial accepted bytes are retained privately before any SG open.
    evidence = tuple(e for e in evidence if e[0] != journal_path)
    binding = dict(returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],
        returned_backup_campaign_sha256=c['returned_backup_campaign_sha256'],
        usb_binding=proof['usb_binding'], request_inventory_sha256=proof['request_inventory_sha256'])
    base = modules['fm1_bound_diagnostic'].BoundDiagnosticSession
    class RestoreSession(base):
        def __init__(self, policy, transport):
            if policy not in kernel._POLICIES:
                raise ValueError('Exact returned policy required')
            self._policy, self._transport = policy, transport
            self._latched, self._running, self._binding = False, False, None
            try:
                observed = self._capture_binding()
                if (observed.get('phase') != 'loader' or observed.get('loader_sha256') != proof['loader_sha256'] or
                        not isinstance(observed.get('session_id'), str) or not observed['session_id'].strip() or
                        observed.get('identity') != plan['identity'] or
                        any(canonical(observed.get(k)) != canonical(v) for k,v in binding.items())):
                    raise ValueError('New returned-loader provenance/binding differs')
                self._binding = canonical(observed)
            except BaseException:
                self._stop(); raise
        def read(self, address, size):
            data = super().read(address, size)
            if not self._transport.initial_verified:
                raise ValueError('Initial full target NOR has not been verified')
            return data
    policy = kernel.Policy(old, canonical(binding), evidence, RestoreSession, proof['_absent_paths'])
    kernel._POLICIES.add(policy)
    receipt = Path(c['receipt_path'])
    parent = Path(proof['receipt_path'])
    if (not receipt.is_absolute() or receipt.parent != parent or receipt.exists() or
            not stat.S_ISDIR(parent.lstat().st_mode) or parent.stat().st_mode & 0o777 != 0o700):
        raise ValueError('New private restore receipt must belong to new target backup')
    legacy = kernel.Prepared(canonical(c), digest(raw), (policy,), canonical(proof['sg_binding']),
        modules['fm1_fixed_loader_backup'], modules['fm1_uboot_read'].SGHeader,
        rehearsal, initial_journal, parent)
    kernel._AUTHORIZED.add(legacy)
    p = Prepared(legacy, kernel, proof['_proof'])
    _AUTHORIZED.add(p); p.check()
    return p


def verify_restore_receipt(raw, result, c, campaign_sha, mapping, baseline, target,
        order, replay_type):
    """Strict one-restore replay, including initial target and final stock pages."""
    events=[json.loads(line) for line in raw.decode('utf8').splitlines()]
    times=[e.get('time') for e in events]
    if (not events or len(events)>100000 or
            not all(type(t) in (int,float) and math.isfinite(t) for t in times) or
            times!=sorted(times) or times[-1]>time.time() or
            digest(baseline)!=BASELINE_SHA or digest(target)!=TARGET_SHA or
            order!=list(range(0x5000,0x22000,4096))+[0x4000]):
        raise ValueError('Exact chronological returned-stock restore required')
    cursor=replay_type(events)
    cursor.event('preparation_stop_stock_restore_prepared',campaign_sha256=campaign_sha,
        adapter_sha256=c['adapter_sha256'],returned_backup_campaign_sha256=c['returned_backup_campaign_sha256'],
        returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],sg_binding=mapping,
        initial_journal_sha256=c['install_journal_sha256'],target_sha256=TARGET_SHA,
        baseline_sha256=BASELINE_SHA,direction='restore',boot_observed=False,
        physical_recovery_verified=False,kernel_exclusivity=False)
    cursor.direction,cursor.index='restore',0
    cursor.command(0xFC0A);cursor.read(target,0,1048576)
    current,changed=target,0
    for address in order:
        sector,actual=baseline[address:address+4096],current[address:address+4096]
        cursor.read(current,address,4096)
        if actual==sector:continue
        if actual!=b'\xff'*4096:
            cursor.event('durable_intent',operation='erase',address=address)
            cursor.command(0xFC0A);cursor.command(0xFB01,address)
            cursor.event('operation_returned',operation='erase',address=address)
        blank=current[:address]+b'\xff'*4096+current[address+4096:]
        cursor.read(blank,address,4096)
        for page in range(address,address+4096,256):
            payload=baseline[page:page+256]
            if payload!=b'\xff'*256:
                cursor.event('durable_intent',operation='program',address=page)
                cursor.command(0xFC0A);cursor.command(0xFB04,page,payload)
                cursor.event('operation_returned',operation='program',address=page)
        current=current[:address]+sector+current[address+4096:]
        cursor.read(current,address,4096)
        cursor.event('sector_verified',address=address);changed+=1
    cursor.read(baseline,0,1048576)
    expected=dict(campaign_sha256=campaign_sha,direction='restore',
        initial_full_target_readback_verified=True,verified_sha256=BASELINE_SHA,
        full_flash_readback_verified=True,sectors_written=changed,stock_baseline_restored=True,
        boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
    cursor.event('preparation_stop_stock_restore_completed',**expected)
    if changed!=30 or cursor.position!=len(events) or canonical(result)!=canonical(expected):
        raise ValueError('Exact 30-sector terminal restore result required')
    return times[0],times[-1]


def validate_completed_restore(path, *, campaign_sha256, commands_sha256,
        result_sha256, journal_sha256, freeze):
    """Evidence only: no live factory, marker absence, discovery or SG opener.

    Historical install is reconstructed from the preserved pre-restore journal;
    the current journal independently proves complete/restore. Exit zero and no
    later commands remain explicit trusted operator premises at the caller.
    """
    if BACKUP_SOURCE_SHA is None or POLICY_SOURCE_SHA is None:
        raise ValueError('Reviewed trace-target backup dependency is not frozen')
    kernel_path=Path(__file__).absolute().parent/'fm1_returned_rom_stock_restore.py'
    freeze(kernel_path,KERNEL_SOURCE_SHA)
    kernel=load_source(kernel_path,KERNEL_SOURCE_SHA,'_trace_stock_completed_restore_kernel')
    raw=freeze(Path(path),campaign_sha256,65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','returned_backup_campaign_path',
        'returned_backup_campaign_sha256','returned_backup_manifest_sha256',
        'returned_backup_commands_sha256','returned_backup_exit_status',
        'original_install_campaign_path','original_install_campaign_sha256',
        'install_journal_sha256','active_session_state','receipt_path'}
    if (set(c)!=keys or type(c['schema']) is not int or c['schema']!=1 or
            c['kind']!='fm1-sdk-preparation-stop-stock-restore-only' or
            type(c['returned_backup_exit_status']) is not int or c['returned_backup_exit_status']!=0 or
            c['active_session_state']!='preparation-stop-fixed-loader-dual-target-backup-no-later-commands'):
        raise ValueError('Exact completed restore campaign required')
    root=Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(),c['adapter_sha256'])
    backup_path=root/'fm1_sdk_prepare_stop_backup.py';freeze(backup_path,BACKUP_SOURCE_SHA)
    backup=load_source(backup_path,BACKUP_SOURCE_SHA,'_returned_completed_backup')
    receipt=Path(c['receipt_path'])
    initial_path=receipt/'journal-before-restore.json'
    freeze(initial_path,c['install_journal_sha256'],65536)
    proof=backup.validate_completed_backup(c['returned_backup_campaign_path'],
        campaign_sha256=c['returned_backup_campaign_sha256'],
        manifest_sha256=c['returned_backup_manifest_sha256'],
        commands_sha256=c['returned_backup_commands_sha256'],freeze=freeze,
        install_journal_path=initial_path)
    parent=Path(proof['receipt_path'])
    if (not receipt.is_absolute() or receipt.parent!=parent or
            not stat.S_ISDIR(receipt.lstat().st_mode) or receipt.stat().st_mode&0o777!=0o700 or
            freeze(parent/'.sdk-preparation-stop-stock-restore.consumed',limit=256)!=campaign_sha256.encode('ascii') or
            c['original_install_campaign_sha256']!=proof['original_install_campaign_sha256'] or
            c['install_journal_sha256']!=proof['install_journal_sha256']):
        raise ValueError('Genuine direct consumed restore lineage required')
    original=json.loads(freeze(c['original_install_campaign_path'],
        c['original_install_campaign_sha256'],65536))
    if canonical(original['policy_inputs'])!=canonical(proof['policy_inputs']):
        raise ValueError('Original restore SDK inputs differ')
    rehearsal_path=root/'fm1_sdk_rehearsal.py';freeze(rehearsal_path,REHEARSAL_SOURCE_SHA)
    rehearsal=load_source(rehearsal_path,REHEARSAL_SOURCE_SHA,'_returned_completed_rehearsal')
    for name,sha in rehearsal.SOURCES.items():freeze(root/name,sha)
    modules=rehearsal.imports()
    policy_path=root/'fm1_bound_sdk_trace.py';freeze(policy_path,POLICY_SOURCE_SHA)
    trace_policy=load_source(policy_path,POLICY_SOURCE_SHA,'_trace_completed_restore_policy')
    policy=trace_policy.load_policy(**original['policy_inputs'],
        direction='restore',baseline_profile='fixed-loader')
    plan,journal,baseline,target=modules['fm1_flash_transaction'].load_transaction(policy.directory)
    frozen_journal=freeze(policy.directory/'journal.json',journal_sha256,65536)
    if canonical(json.loads(frozen_journal))!=canonical(journal):
        raise ValueError('Current restore journal changed during validation')
    if (journal['state']!='complete' or journal['direction']!='restore' or journal['intent'] is not None or
            journal['verified_sha256']!=BASELINE_SHA or journal['sector_order']!=plan['sector_order']):
        raise ValueError('Current actual complete stock-restore journal required')
    replay_path=root/'fm1_fixed_target_reset.py';freeze(replay_path,REPLAY_SOURCE_SHA)
    replay=load_source(replay_path,REPLAY_SOURCE_SHA,'_returned_completed_replay')
    result=json.loads(freeze(receipt/'result.json',result_sha256,65536))
    commands=freeze(receipt/'commands.jsonl',commands_sha256,32*1048576)
    started,_=verify_restore_receipt(commands,result,c,campaign_sha256,proof['sg_binding'],
        baseline,target,plan['sector_order'],replay.Replay)
    if started<proof['completed_at']:
        raise ValueError('Restore preceded completed target backups')
    policy.check_files()
    return dict(usb_binding=proof['usb_binding'],sg_binding=proof['sg_binding'],
        returned_backup_receipt_path=str(parent),
        returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],
        baseline_sha256=BASELINE_SHA,target_sha256=TARGET_SHA,sectors_written=30,
        sector_order=plan['sector_order'],_absent_paths=tuple(proof['_absent_paths']),
        _proof=proof['_proof'])


def run_campaign(prepared):
    require_prepared(prepared)
    c = json.loads(prepared.config); bridge = prepared.bridge
    receipt = Path(c['receipt_path'])
    receipt.mkdir(mode=0o700, exist_ok=False); bridge.sync_dir(receipt.parent)
    with bridge.private_file(prepared.parent / '.sdk-preparation-stop-stock-restore.consumed') as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(prepared.parent)
    with bridge.private_file(receipt / 'journal-before-restore.json') as fp:
        fp.write(prepared.initial_journal); fp.flush(); os.fsync(fp.fileno())
    bridge.sync_dir(receipt)
    with bridge.private_file(receipt / 'commands.jsonl', 'w') as events:
        def log(event, **fields):
            events.write(json.dumps(dict(time=time.time(), event=event, **fields), allow_nan=False)+'\n')
            events.flush(); os.fsync(events.fileno()); bridge.sync_dir(receipt)
        transport = None
        try:
            log('preparation_stop_stock_restore_prepared', campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=c['adapter_sha256'], returned_backup_campaign_sha256=c['returned_backup_campaign_sha256'],
                returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],
                sg_binding=json.loads(prepared.mapping), initial_journal_sha256=digest(prepared.initial_journal),
                target_sha256=TARGET_SHA, baseline_sha256=BASELINE_SHA, direction='restore',
                boot_observed=False, physical_recovery_verified=False, kernel_exclusivity=False)
            policy = prepared.policies[0]
            transport = transport_type(prepared)(policy, log)
            try: result = policy.bind(transport).run(checkpoint=log)
            finally: transport.close()
            prepared.check()
            if (result['verified_sha256'] != BASELINE_SHA or result['sectors_written']!=30 or
                    not transport.initial_verified):
                raise ValueError('Final full stock baseline verification differs')
            result = dict(campaign_sha256=prepared.campaign_sha256, direction='restore',
                initial_full_target_readback_verified=True, verified_sha256=BASELINE_SHA,
                full_flash_readback_verified=True, sectors_written=result['sectors_written'],
                stock_baseline_restored=True, boot_observed=False, physical_recovery_verified=False,
                kernel_exclusivity=False)
            log('preparation_stop_stock_restore_completed', **result)
            with bridge.private_file(receipt/'result.json','w') as fp:
                json.dump(result,fp,sort_keys=True,allow_nan=False);fp.write('\n');fp.flush();os.fsync(fp.fileno())
            bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            if transport is not None:
                transport.failed=True
                try:transport.close()
                except BaseException:pass
            try:
                (receipt/'result.json').unlink(missing_ok=True);bridge.sync_dir(receipt)
                log('preparation_stop_stock_restore_stopped_ambiguous',error=type(exc).__name__,retry=False,
                    stock_baseline_restored=False,boot_observed=False)
            except BaseException:pass
            raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True,type=Path)
    args=parser.parse_args()
    if sys.platform!='linux':raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__=='__main__': main()

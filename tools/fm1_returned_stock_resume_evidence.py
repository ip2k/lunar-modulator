#!/usr/bin/env python3
"""MIT. Closed evidence-only lineage for a caught returned-stock restore stop.

This validates actual source/artifact/marker/journal provenance; it deliberately
cannot establish owned terminal capture or current loader acquisition. There is
no transport, opener, execution policy or reset authority in this module.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
from weakref import WeakSet

KERNEL_SHA = 'cef2d0ea48c2ceb9c4441a7b9042aae05643f3db01f217787339cace31575277'
RESTORE_SHA = 'f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33'
_AUTHORIZED = WeakSet()


def digest(data): return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def read_file(path, limit=2 * 1048576):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Absolute direct evidence required')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try: fp = os.fdopen(fd, 'rb')
    except BaseException:
        os.close(fd); raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode): raise ValueError('Regular evidence required')
        data = fp.read(limit + 1)
    if len(data) > limit: raise ValueError('Evidence exceeds bound')
    return data


def load_source(path, sha, name):
    raw = read_file(path)
    if digest(raw) != sha: raise ValueError('Frozen source differs')
    module = types.ModuleType(name); module.__file__ = str(path); sys.modules[name] = module
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


def private_directory(path):
    path = Path(path)
    if (not path.is_absolute() or not stat.S_ISDIR(path.lstat().st_mode) or
            stat.S_IMODE(path.stat().st_mode) != 0o700):
        raise ValueError('Direct private evidence directory required')


def validate_journal(current, initial, plan, proof, kernel):
    """Source publication semantics only; journal never substitutes for NOR."""
    if (not isinstance(current, dict) or not isinstance(initial, dict) or
            current.get('record_sha256') != digest(canonical({k:v for k,v in current.items() if k!='record_sha256'})) or
            current.get('schema') != 1 or current.get('plan_sha256') != digest(canonical(plan)) or
            current.get('sector_order') != list(kernel.ORDER) or plan.get('sector_order') != list(kernel.ORDER)):
        raise ValueError('Exact sealed current journal record required')
    # Constructor/identity/online failures outside the transaction try block may
    # preserve the accepted original completed installation without any mutation.
    if canonical(current) == canonical(initial):
        if proof.initial_verified or proof.uncertainty or proof.sectors_verified:
            raise ValueError('Unchanged install journal cannot describe later restore progress')
        return 'unchanged-install-before-worker'
    if (not set(initial).issubset(current) or set(current) - set(initial) - {'error'} or
            any(canonical(current.get(k)) != canonical(v) for k,v in initial.items()
                if k not in {'state','direction','intent','verified_sha256','record_sha256'}) or
            current.get('direction') != 'restore' or
            canonical(current.get('intent')) not in [canonical(i) for i in json.loads(proof.journal_intents)]):
        raise ValueError('Current journal differs from exact stopped publication boundary')
    if current.get('state') == 'recovery_required':
        error = current.get('error')
        if (not isinstance(error,str) or not error or len(error)>128 or
                current.get('verified_sha256') != initial.get('verified_sha256')):
            raise ValueError('Caught worker failure journal required')
        return 'worker-stopped-recovery-required'
    if (current.get('state') == 'complete' and current.get('intent') is None and
            current.get('verified_sha256') == kernel.BASELINE_SHA and proof.final_stock_verified):
        return 'stock-readback-complete-publication-stopped'
    raise ValueError('Running/crashed or unrelated journal is not this caught-stop branch')


@dataclass(frozen=True, eq=False)
class StoppedLineage:
    prefix: object
    kernel: object
    evidence: tuple
    policies: tuple
    absent_paths: tuple
    lineage: bytes
    journal_state: str

    def check(self):
        if self not in _AUTHORIZED: raise ValueError('Exact evidence-factory instance required')
        for path,data,limit in self.evidence:
            if read_file(path,limit) != data: raise ValueError('Stopped lineage evidence changed')
        if any(os.path.lexists(path) for path in self.absent_paths):
            raise ValueError('Stopped lineage negative evidence changed')
        for policy in self.policies: policy.check_files()

    def check_partial_dumps(self, dump_a, dump_b):
        self.check()
        result = self.kernel.check_partial_dumps(self.prefix,dump_a,dump_b)
        return dict(result, actual_original_lineage_verified=True,
            owned_terminal_capture_verified=False,live_acquisition_verified=False,execution_authorized=False)


def validate_stopped_restore(path, *, campaign_sha256, commands_sha256, journal_sha256):
    """Actual-file evidence only. Caller still needs reviewed capture/acquisition."""
    evidence=[]
    def freeze(path, expected=None, limit=2*1048576):
        path=Path(path);raw=read_file(path,limit)
        if expected is not None and digest(raw)!=expected: raise ValueError('Pinned stopped evidence differs')
        evidence.append((path,raw,limit));return raw
    root=Path(__file__).absolute().parent
    freeze(Path(__file__).absolute())
    kernel_path=root/'fm1_returned_stock_resume.py';freeze(kernel_path,KERNEL_SHA)
    kernel=load_source(kernel_path,KERNEL_SHA,'_returned_resume_evidence_kernel')
    restore_path=root/'fm1_returned_rom_stock_restore.py';freeze(restore_path,RESTORE_SHA)
    restore=load_source(restore_path,RESTORE_SHA,'_returned_resume_evidence_restore')
    raw=freeze(Path(path),campaign_sha256,65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','returned_backup_campaign_path',
        'returned_backup_campaign_sha256','returned_backup_manifest_sha256',
        'returned_backup_commands_sha256','returned_backup_exit_status',
        'original_rehearsal_campaign_path','original_rehearsal_campaign_sha256',
        'install_journal_sha256','active_session_state','receipt_path'}
    if (set(c)!=keys or type(c['schema']) is not int or c['schema']!=1 or
            c['kind']!='fm1-returned-rom-stock-restore-only' or c['adapter_sha256']!=RESTORE_SHA or
            type(c['returned_backup_exit_status']) is not int or c['returned_backup_exit_status']!=0 or
            c['active_session_state']!='returned-fixed-loader-dual-target-backup-no-later-commands'):
        raise ValueError('Exact original returned-stock restore campaign required')
    receipt=Path(c['receipt_path']);private_directory(receipt);private_directory(receipt.parent)
    initial_path=receipt/'journal-before-restore.json'
    initial_raw=freeze(initial_path,c['install_journal_sha256'],65536);initial=json.loads(initial_raw)
    original=json.loads(freeze(c['original_rehearsal_campaign_path'],c['original_rehearsal_campaign_sha256'],65536))
    directory=Path(original['policy_inputs']['directory'])
    for name,limit in [('plan.json',65536),('backupA.bin',1048576),('backupB.bin',1048576),('target.bin',1048576)]:
        freeze(directory/name,limit=limit)
    current_raw=freeze(directory/'journal.json',journal_sha256,65536)
    backup_path=root/'fm1_returned_rom_backup.py';freeze(backup_path,restore.BACKUP_SOURCE_SHA)
    backup=load_source(backup_path,restore.BACKUP_SOURCE_SHA,'_returned_resume_evidence_backup')
    proof=backup.validate_completed_backup(c['returned_backup_campaign_path'],
        campaign_sha256=c['returned_backup_campaign_sha256'],manifest_sha256=c['returned_backup_manifest_sha256'],
        commands_sha256=c['returned_backup_commands_sha256'],freeze=freeze,install_journal_path=initial_path)
    if (receipt.parent!=Path(proof['receipt_path']) or
            freeze(receipt.parent/'.returned-stock-restore.consumed',limit=256)!=campaign_sha256.encode('ascii') or
            c['original_rehearsal_campaign_sha256']!=proof['original_rehearsal_campaign_sha256'] or
            c['install_journal_sha256']!=proof['install_journal_sha256'] or
            canonical(original['policy_inputs'])!=canonical(proof['policy_inputs'])):
        raise ValueError('Genuine consumed original restore/SDK lineage differs')
    rehearsal_path=root/'fm1_sdk_rehearsal.py';freeze(rehearsal_path,restore.REHEARSAL_SOURCE_SHA)
    rehearsal=load_source(rehearsal_path,restore.REHEARSAL_SOURCE_SHA,'_returned_resume_evidence_rehearsal')
    for name,sha in rehearsal.SOURCES.items():freeze(root/name,sha)
    modules=rehearsal.imports()
    policy=modules['fm1_bound_sdk_diagnostic'].load_policy(**original['policy_inputs'],direction='restore',baseline_profile='fixed-loader')
    for support_path,data,limit in policy.evidence:freeze(support_path,digest(data),limit)
    plan,journal,baseline,target=modules['fm1_flash_transaction'].load_transaction(directory)
    if (canonical(journal)!=canonical(json.loads(current_raw)) or
            initial.get('state')!='complete' or initial.get('direction')!='install' or
            initial.get('intent') is not None or initial.get('verified_sha256')!=kernel.TARGET_SHA or
            initial.get('plan_sha256')!=digest(canonical(plan)) or initial.get('sector_order')!=list(kernel.ORDER)):
        raise ValueError('Preserved original install/current journal differs')
    commands=freeze(receipt/'commands.jsonl',commands_sha256,32*1048576)
    prefix=kernel.verify_interrupted_prefix(commands,c,campaign_sha256,proof['sg_binding'],baseline,target)
    if json.loads(commands.splitlines()[0])['time']<proof['completed_at']:
        raise ValueError('Stopped restore preceded completed target backup')
    state=validate_journal(journal,initial,plan,prefix,kernel)
    absent=tuple(dict.fromkeys((*proof['_absent_paths'],receipt/'result.json')))
    lineage=canonical(dict(usb_binding=proof['usb_binding'],sg_binding=proof['sg_binding'],
        returned_backup_receipt_path=proof['receipt_path'],returned_backup_manifest_sha256=c['returned_backup_manifest_sha256'],
        stopped_restore_campaign_sha256=campaign_sha256,commands_sha256=commands_sha256,journal_sha256=journal_sha256,
        baseline_sha256=kernel.BASELINE_SHA,target_sha256=kernel.TARGET_SHA,
        owned_terminal_capture_verified=False,live_acquisition_verified=False,execution_authorized=False))
    p=StoppedLineage(prefix,kernel,tuple(evidence),(policy,),absent,lineage,state)
    _AUTHORIZED.add(p);p.check();return p


def prepare_campaign(path):
    raise ValueError('Evidence-only stopped lineage cannot authorize execution')

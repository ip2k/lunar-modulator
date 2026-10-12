#!/usr/bin/env python3
"""MIT. Distinct retained-fixed-loader partial NOR acquisition and stock restore.

Actual caught install/restore, owned terminal capture, fresh unchanged SG and two
new complete dumps are required. No upload, reset, new-ROM admission or retries.
Unbound capture/restore literals fail before evidence IO; implemented factories
become usable only after those separate exact dependencies receive review.
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

INSTALL_SHA = '6be77170f28fff7d7ca9c794ac44592a9c4bd4bae2cc2affd22a1cebf0936720'
POLICY_SHA = '54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835'
REHEARSAL_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
KERNEL_SHA = '89cd7cd68ec9151357fa5622aa1956c0157e549d1a486ddac4c8f3f73831f781'
RESET_WIRE_SHA = '9c81a30a7f8741a606961315d0689341d3ce2e29775d395e05e81d5dbdedfd92'
PREFIX_SHA = '37794ff6caf9992fb6809cdd179a858d1b500b18aa26187e4cb8888b1479f056'  # Separate new cursor review precedes its literal binding.
INSTALL_CAPTURE_SHA = '7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'  # Reviewed install wrapper, never a caller-chosen source.
INSTALL_CAPTURE_SUCCESSOR_SHA = '59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d'  # Separately reviewed lifecycle successor; historical receipts remain distinct.
RESTORE_SHA = '7d84f0d8699deded1990fc9758bc9580dcca771918c79a19d8ac31208f6c7a59'  # Accepted admitted stock restore successor.
BACKUP_SHA = '1694733ce448a6f368938f251c4d5b4f639a37004dd6623035379953de9b775b'   # That successor's actual canonical completed-backup helper.
RESTORE_CAPTURE_SHA = 'b1e8e3ca0d50daa438df9715208095f67b2a1babc8efe24d1535fd3eb2071ed5'
ACQUIRE_CAPTURE_SHA = '9d69134b11552f63a245c0a6870230e47bda4e6d80006b0bd61a47b938b22c34'
STOCK_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
TARGET_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
FLASH = 1048576
ORDER = tuple(range(0x5000, 0x22000, 4096)) + (0x4000,)
_LINEAGES, _PREPARED, _CONSUMED = WeakSet(), WeakSet(), WeakSet()


def digest(data): return hashlib.sha256(data).hexdigest()
def canonical(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')

def read_file(path, limit=2*FLASH):
    path = Path(path)
    if not path.is_absolute(): raise ValueError('Absolute direct evidence path required')
    fd = os.open(path, os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode): raise ValueError('Bounded regular evidence required')
        fp = os.fdopen(fd, 'rb'); fd = None
        with fp: data = fp.read(limit+1)
        if len(data)>limit: raise ValueError('Evidence exceeds bound')
        return data
    finally:
        if fd is not None: os.close(fd)

def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)

def exclusive(path, data):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:
        fp=os.fdopen(fd,'wb');fd=None
        with fp: fp.write(data);fp.flush();os.fsync(fp.fileno())
    finally:
        if fd is not None: os.close(fd)
    sync_dir(Path(path).parent)

def private_directory(path):
    p=Path(path)
    st=p.lstat()
    if not p.is_absolute() or not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode)!=0o700:
        raise ValueError('Direct private directory required')
    return p

def source(path, pin, label):
    if type(pin) is not str or len(pin)!=64: raise ValueError('Reviewed dependency literal remains closed')
    data=read_file(path)
    if digest(data)!=pin: raise ValueError('Reviewed source changed: '+str(path))
    name='_retained_partial_'+label
    m=types.ModuleType(name);m.__file__=str(path);sys.modules[name]=m
    exec(compile(data,str(path),'exec'),m.__dict__)
    return m

class _Frozen:
    def __init__(self): self.files={};self.absent=set()
    def freeze(self,path,sha=None,limit=2*FLASH):
        p=Path(path);data=read_file(p,limit)
        if sha is not None and digest(data)!=sha: raise ValueError('Pinned evidence differs: '+str(p))
        previous=self.files.get(p)
        if previous is not None and previous[0]!=data: raise ValueError('Evidence changed during admission')
        self.files[p]=(data,max(limit,previous[1] if previous else 0));return data
    def missing(self,path):
        p=Path(path)
        if not p.is_absolute() or os.path.lexists(p): raise ValueError('Required absent artifact exists')
        self.absent.add(p)
    def check(self,deep=True):
        if any(os.path.lexists(p) for p in self.absent): raise ValueError('Required absent artifact appeared')
        for p,(data,limit) in self.files.items():
            # Large immutable captures/images are rechecked before open,
            # mutation and publication; every request rechecks sources/small
            # journal/markers and all negatives without multi-MiB hashing.
            if (deep or len(data)<=65536 or p.suffix=='.py') and read_file(p,limit)!=data:
                raise ValueError('Frozen evidence changed: '+str(p))

@dataclass(frozen=True,eq=False)
class Lineage:
    campaign_sha256: str
    direction: str
    directory: Path
    parent: Path
    usb: bytes
    mapping: bytes
    stock: bytes
    target: bytes
    identity: bytes
    prefix: object
    cursor: object
    frozen: object
    runtime: object
    bridge: object
    header_type: type
    kernel: object
    wire_parser: object
    terminal_time: float
    def check(self,deep=True):
        if type(self) is not Lineage or self not in _LINEAGES: raise ValueError('Exact actual stopped lineage required')
        self.frozen.check(deep)


def install_capture_pin(f, inputs):
    """Select only exact reviewed bytes; never a caller-supplied hash/version."""
    if type(inputs) is not dict or set(inputs)!={'wrapper_path','packet_path','run'}:
        raise ValueError('Exact owned capture paths required')
    actual=digest(f.freeze(inputs['wrapper_path'],limit=2*FLASH))
    if actual not in (INSTALL_CAPTURE_SHA,INSTALL_CAPTURE_SUCCESSOR_SHA):
        raise ValueError('Unreviewed install capture source')
    return actual


def capture(f, inputs, *, pin, kind, campaign_sha, adapter_sha, usb, times, exit_status):
    """Immutable owned terminal envelope. Setup/cleanup failures grant nothing."""
    if type(inputs) is not dict or set(inputs)!={'wrapper_path','packet_path','run'}:
        raise ValueError('Exact owned capture paths required')
    run=private_directory(inputs['run'])
    f.freeze(inputs['wrapper_path'],pin)
    packet=json.loads(f.freeze(inputs['packet_path'],limit=65536))
    expected={'schema','kind','campaign_path','campaign_sha256','adapter_path','adapter_sha256','source_pins','usb_binding'}
    if (set(packet)!=expected or type(packet['schema']) is not int or packet['schema']!=1
            or packet['kind']!=kind or packet['campaign_sha256']!=campaign_sha
            or packet['adapter_sha256']!=adapter_sha or canonical(packet['usb_binding'])!=usb):
        raise ValueError('Original owned capture packet differs')
    f.freeze(packet['campaign_path'],campaign_sha,65536);f.freeze(packet['adapter_path'],adapter_sha)
    stage=Path(packet['adapter_path']).parent.parent
    if not isinstance(packet['source_pins'],dict) or not packet['source_pins']: raise ValueError('Source packet required')
    for rel,sha in packet['source_pins'].items():
        path=Path(rel)
        if path.is_absolute() or not path.parts or any(x in ('.','..') for x in path.parts) or '\\' in rel:
            raise ValueError('Contained source inventory required')
        f.freeze(stage/path,sha)
    names=('wrapper-attempt.json','capture-open.json','execution-exit.json','capture-stop.json')
    a,o,e,s=(json.loads(f.freeze(run/n,limit=65536)) for n in names)
    if (set(a)!={'schema','kind','time','campaign_sha256','adapter_sha256','retry'} or a['schema']!=1
            or type(a['schema']) is not int or a['kind']!=kind or a['campaign_sha256']!=campaign_sha or a['adapter_sha256']!=adapter_sha or a['retry'] is not False
            or set(o)!={'schema','time','timeout_pid','cat_pid','process_group','open_capture_fd'} or type(o['schema']) is not int or o['schema']!=1 or o['open_capture_fd'] is not True
            or any(type(o[k]) is not int or o[k]<=1 for k in ('timeout_pid','cat_pid','process_group'))
            or o['timeout_pid']!=o['process_group'] or o['cat_pid']==o['timeout_pid']
            or set(e)!={'schema','time','child_started_at','child_finished_at','exit_status','campaign_sha256','adapter_sha256','capture_alive_after_child','retry'}
            or type(e['schema']) is not int or e['schema']!=1 or type(e['exit_status']) is not int or e['exit_status']!=exit_status
            or e['campaign_sha256']!=campaign_sha or e['adapter_sha256']!=adapter_sha or e['capture_alive_after_child'] is not True or e['retry'] is not False
            or set(s)!={'schema','time','process_group','returncode','owned_processes_only'} or type(s['schema']) is not int or s['schema']!=1
            or type(s['process_group']) is not int or s['process_group']!=o['process_group'] or type(s['returncode']) is not int or s['returncode']!=-15 or s['owned_processes_only'] is not True):
        raise ValueError('Exact clean owned terminal lifecycle required')
    timeline=(a['time'],o['time'],e['child_started_at'],*times,e['child_finished_at'],e['time'],s['time'])
    if any(type(t) not in (int,float) or not math.isfinite(t) or t<0 for t in timeline) or tuple(sorted(timeline))!=timeline:
        raise ValueError('Child timestamps do not bracket actual ordered commands')
    f.freeze(run/'execution.stdout',limit=2*FLASH)
    if f.freeze(run/'usbmon1.stderr',limit=65536): raise ValueError('Capture stderr is not clean')
    f.missing(run/'wrapper-stopped-ambiguous.json');f.missing(run/'wrapper-cleanup-ambiguous.json')
    return f.freeze(run/'usbmon1.txt',limit=16*FLASH)


def _journal(journal,prefix,plan,direction):
    if journal.get('sector_order')!=list(ORDER) or journal.get('plan_sha256')!=digest(canonical(plan)):
        raise ValueError('Original journal plan/order differs')
    if journal.get('intent') not in json.loads(prefix.journal_intents): raise ValueError('Journal intent is not possible at this caught publication boundary')
    state=journal.get('state')
    if state=='complete':
        if not prefix.final_verified or journal.get('intent') is not None or journal.get('direction')!=direction:
            raise ValueError('Completed journal lacks actual full final readback')
    elif state=='prepared':
        if prefix.uncertainty or prefix.sectors_verified or journal.get('intent') is not None or journal.get('direction') not in (None,direction):
            raise ValueError('Prepared journal cannot follow attempted mutation')
    elif state=='recovery_required':
        if journal.get('direction')!=direction or type(journal.get('error')) is not str or not 0<len(journal['error'])<=128:
            raise ValueError('Caught worker journal required')
    else: raise ValueError('Running/crash journal is not a caught terminal lineage')


def validate_stopped(path):
    # All new authority dependencies gate before evidence interpretation.
    if PREFIX_SHA is None or INSTALL_CAPTURE_SHA is None: raise ValueError('Prefix and actual capture sources await independent literal binding')
    root=Path(__file__).absolute().parent;f=_Frozen()
    raw=f.freeze(Path(path).absolute(),limit=65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','direction','original_campaign_path','original_campaign_sha256','commands_sha256','journal_sha256','capture','quiet_state'}
    if (set(c)!=keys or type(c['schema']) is not int or c['schema']!=1 or c['kind']!='fm1-retained-fixed-loader-caught-partial'
            or c['direction'] not in ('install','restore') or c['quiet_state']!='caught-child-stopped-same-fixed-loader-no-later-commands'):
        raise ValueError('Exact stopped retained-loader envelope required')
    f.freeze(Path(__file__).absolute(),c['adapter_sha256'])
    prefix=source(root/'fm1_partial_nor_prefix.py',PREFIX_SHA,'prefix');f.freeze(root/'fm1_partial_nor_prefix.py',PREFIX_SHA)
    p=source(root/'fm1_bound_sdk_trace.py',POLICY_SHA,'policy');f.freeze(root/'fm1_bound_sdk_trace.py',POLICY_SHA)
    r,modules=p.core_modules()
    f.freeze(root/'fm1_sdk_rehearsal.py',REHEARSAL_SHA)
    for name,sha in r.SOURCES.items(): f.freeze(root/name,sha)
    kernel=source(root/'fm1_partial_stock_restore.py',KERNEL_SHA,'kernel');f.freeze(root/'fm1_partial_stock_restore.py',KERNEL_SHA)
    parser=source(root/'fm1_reset_wire.py',RESET_WIRE_SHA,'wire');f.freeze(root/'fm1_reset_wire.py',RESET_WIRE_SHA)
    original_raw=f.freeze(c['original_campaign_path'],c['original_campaign_sha256'],65536);original=json.loads(original_raw)
    if c['direction']=='install':
        adapter=INSTALL_SHA;f.freeze(root/'fm1_sdk_trace_install.py',adapter)
        required={'schema','kind','adapter_sha256','policy_sha256','policy_inputs','backup_exit_status','backup_commands_sha256','active_session_state','sg_binding','receipt_path'}
        if set(original)!=required or type(original['schema'])is not int or original['schema']!=1 or type(original['backup_exit_status'])is not int or original['backup_exit_status']!=0 or original['active_session_state']!='matching-fresh-stock-backup-no-later-commands':
            raise ValueError('Actual emitted install campaign schema/admission required')
        if original.get('adapter_sha256')!=adapter or original.get('policy_sha256')!=POLICY_SHA or original.get('kind')!='fm1-exact-sdk-recovery-trace-install': raise ValueError('Exact trace install campaign required')
        inputs=original['policy_inputs'];mapping=original['sg_binding'];parent=Path(inputs['manifest_path']).parent
        receipt=Path(original['receipt_path']);marker=parent/'.sdk-rehearsal.consumed'
        capture_pin,kind=install_capture_pin(f,c['capture']),'fm1-sdk-trace-install-one-shot'
        first=dict(event='trace_install_prepared',campaign_sha256=c['original_campaign_sha256'],adapter_sha256=adapter,
            policy_sha256=POLICY_SHA,rehearsal_sha256=REHEARSAL_SHA,source_sha256=r.SOURCES,target_sha256=TARGET_SHA,
            trace_nonce=p.TRACE_NONCE,sg_binding=mapping,kernel_exclusivity=False,boot_observed=False,physical_recovery_verified=False,stock_restore_preflighted=True)
        final=dict(event='trace_install_completed',campaign_sha256=c['original_campaign_sha256'],adapter_sha256=adapter,policy_sha256=POLICY_SHA,
            rehearsal_sha256=REHEARSAL_SHA,direction='install',verified_sha256=TARGET_SHA,baseline_sha256=STOCK_SHA,trace_nonce=p.TRACE_NONCE,
            trace_address=p.TRACE_ADDRESS,trace_bytes=p.TRACE_BYTES,full_flash_readback_verified=True,sectors_written=30,sector_order=list(ORDER),
            stock_restore_preflighted=True,stock_baseline_restored=False,boot_observed=False,display_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
        stop='trace_install_stopped_ambiguous';initial_sha=STOCK_SHA
    else:
        if RESTORE_SHA is None or BACKUP_SHA is None or RESTORE_CAPTURE_SHA is None: raise ValueError('Reviewed admitted restore lineage is closed')
        adapter=RESTORE_SHA;f.freeze(root/'fm1_sdk_trace_admitted_stock_restore.py',adapter)
        required={'schema','kind','adapter_sha256','returned_backup_campaign_path','returned_backup_campaign_sha256','returned_backup_manifest_sha256','returned_backup_commands_sha256','returned_backup_exit_status','original_install_campaign_path','original_install_campaign_sha256','install_journal_sha256','active_session_state','receipt_path'}
        if set(original)!=required or type(original['schema'])is not int or original['schema']!=1 or type(original['returned_backup_exit_status'])is not int or original['returned_backup_exit_status']!=0 or original['active_session_state']!='admitted-trace-fixed-loader-dual-target-backup-no-later-commands':
            raise ValueError('Actual admitted restore campaign schema required')
        backup=source(root/'fm1_sdk_trace_admitted_backup.py',BACKUP_SHA,'backup');f.freeze(root/'fm1_sdk_trace_admitted_backup.py',BACKUP_SHA)
        receipt=Path(original['receipt_path']);saved=receipt/'journal-before-restore.json'
        f.freeze(saved,original['install_journal_sha256'],65536)
        proof=backup.validate_completed_backup(original['returned_backup_campaign_path'],campaign_sha256=original['returned_backup_campaign_sha256'],
            manifest_sha256=original['returned_backup_manifest_sha256'],commands_sha256=original['returned_backup_commands_sha256'],freeze=f.freeze,install_journal_path=saved)
        for absent in proof['_absent_paths']: f.missing(absent)
        inputs=proof['policy_inputs'];mapping=proof['sg_binding'];usb=proof['usb_binding'];parent=Path(proof['receipt_path'])
        if original.get('adapter_sha256')!=adapter or original.get('kind')!='fm1-sdk-trace-admitted-stock-restore-only' or original.get('original_install_campaign_sha256')!=proof['original_install_campaign_sha256']:
            raise ValueError('Exact admitted restore original lineage required')
        f.freeze(original['original_install_campaign_path'],proof['original_install_campaign_sha256'],65536)
        marker=parent/'.sdk-trace-admitted-stock-restore.consumed';capture_pin,kind=RESTORE_CAPTURE_SHA,'fm1-sdk-trace-restore-one-shot'
        first=dict(event='trace_admitted_stock_restore_prepared',campaign_sha256=c['original_campaign_sha256'],adapter_sha256=adapter,
            returned_backup_campaign_sha256=original['returned_backup_campaign_sha256'],returned_backup_manifest_sha256=original['returned_backup_manifest_sha256'],
            sg_binding=mapping,initial_journal_sha256=original['install_journal_sha256'],target_sha256=TARGET_SHA,baseline_sha256=STOCK_SHA,
            direction='restore',boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
        final=dict(event='trace_admitted_stock_restore_completed',campaign_sha256=c['original_campaign_sha256'],direction='restore',initial_full_target_readback_verified=True,
            verified_sha256=STOCK_SHA,full_flash_readback_verified=True,sectors_written=30,stock_baseline_restored=True,boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
        stop='trace_admitted_stock_restore_stopped_ambiguous';initial_sha=TARGET_SHA
    private_directory(parent);private_directory(receipt)
    if receipt.parent!=parent: raise ValueError('Original receipt must be direct private child')
    f.freeze(marker,limit=64)
    if read_file(marker,64)!=c['original_campaign_sha256'].encode('ascii'): raise ValueError('Actual consumed original marker required')
    f.missing(receipt/'result.json')
    directory=Path(inputs['directory'])
    # Bound the generic policy/transaction reader inputs before invoking it.
    for name in ('plan.json','backupA.bin','backupB.bin','target.bin','journal.json'):
        f.freeze(directory/name, c['journal_sha256'] if name=='journal.json' else None,65536 if name.endswith('.json') else FLASH)
    policy=p.load_policy(**inputs,direction=c['direction'],baseline_profile='fixed-loader')
    for path,data,limit in policy.evidence: f.freeze(path,digest(data),limit)
    plan,journal,stock,target=modules['fm1_flash_transaction'].load_transaction(directory)
    if digest(stock)!=STOCK_SHA or digest(target)!=TARGET_SHA or plan['sector_order']!=list(ORDER) or plan['writable_ranges']!=[[a,a+4096] for a in sorted(ORDER)]:
        raise ValueError('Exact stock/trace 30-sector immutable geometry required')
    manifest=json.loads(f.freeze(inputs['manifest_path'],limit=65536))
    if c['direction']=='install':
        usb=manifest['usb_binding']
        if canonical(manifest['sg_binding'])!=canonical(mapping): raise ValueError('Original complete backup connection differs')
    base_campaign=json.loads(f.freeze(inputs['campaign_path'],limit=65536))
    base_log=f.freeze(inputs['backup_log_path'],limit=16*FLASH)
    modules['fm1_fixed_loader_reset'].validate_commands(base_log,manifest,dict(base_campaign,entry_log_path=inputs['entry_log_path']),modules['fm1_fixed_loader_backup'])
    commands=f.freeze(receipt/'commands.jsonl',c['commands_sha256'],32*FLASH)
    if c['direction']=='install':
        ended=json.loads(base_log.splitlines()[-1])['time'];started=json.loads(commands.splitlines()[0])['time']
        if digest(base_log)!=original['backup_commands_sha256'] or type(ended)not in(int,float) or not math.isfinite(ended) or not 0<=started-ended<=120:
            raise ValueError('Original successful stock backup/fresh install admission differs')
    replay=prefix.verify(commands,stock if initial_sha==STOCK_SHA else target,target if c['direction']=='install' else stock,
        direction=c['direction'],prepared_fields=first,completed_fields=final,stop_event=stop)
    _journal(journal,replay,plan,c['direction'])
    if journal['state']=='complete' and journal.get('verified_sha256')!=(TARGET_SHA if c['direction']=='install' else STOCK_SHA): raise ValueError('Final journal digest differs')
    captured=capture(f,c['capture'],pin=capture_pin,kind=kind,campaign_sha=c['original_campaign_sha256'],adapter_sha=adapter,usb=canonical(usb),times=replay.times,exit_status=1)
    prefix.verify_wire(parser._records(captured,usb,usb),replay.requests,stopped=True)
    # These new filenames are defined by the separately reviewed physical plan;
    # their absence prevents acquiring over a boot/reset/retry attempt.
    for name in ('rom-snapshot.json','wrapper-cleanup-ambiguous.json'):
        f.missing(Path(c['capture']['run'])/name)
    result=Lineage(c['original_campaign_sha256'],c['direction'],directory,parent,canonical(usb),canonical(mapping),stock,target,canonical(plan['identity']),
        replay,prefix,f,r,modules['fm1_fixed_loader_backup'],modules['fm1_uboot_read'].SGHeader,kernel,parser,replay.times[-1])
    _LINEAGES.add(result);result.check();return result


def witness(raw,lineage,now):
    v=json.loads(raw)
    required={'schema','kind','observed_at','usb_binding','sg_binding','original_campaign_sha256','quiet_state'}
    if (set(v)!=required or type(v['schema']) is not int or v['schema']!=1 or v['kind']!='fm1-current-retained-fixed-loader'
            or canonical(v['usb_binding'])!=lineage.usb or canonical(v['sg_binding'])!=lineage.mapping
            or v['original_campaign_sha256']!=lineage.campaign_sha256 or v['quiet_state']!='same-original-fixed-loader-no-later-commands'
            or type(v['observed_at']) not in (int,float) or not math.isfinite(v['observed_at']) or not math.isfinite(now)
            or v['observed_at']<lineage.terminal_time or not 0<=now-v['observed_at']<=120):
        raise ValueError('Fresh unchanged retained fixed-loader witness required')
    return v

def acquisition_operations(cursor):
    operations=[('online',*cursor.wire(0xFC0A))]
    for name in ('dumpA.bin','dumpB.bin'):
        for a in range(0,FLASH,256):
            if a%4096==0: operations.append(('online',*cursor.wire(0xFC0A)))
            operations.append((name,*cursor.wire(0xFD05,a)))
        operations.append((name+'.end',*cursor.wire(0xFC0A)))
    return tuple(operations)

@dataclass(frozen=True,eq=False)
class Prepared:
    mode: str
    campaign_path: Path
    campaign: bytes
    campaign_sha256: str
    receipt: Path
    marker: Path
    lineage: Lineage
    frozen: object
    admission_time: float
    directory: Path
    plan_bytes: bytes
    preimage: bytes
    stock: bytes
    operations: tuple
    runtime: object
    bridge: object
    header_type: type
    mapping: bytes
    policies: tuple
    binding: bytes
    def check(self,deep=False):
        if type(self) is not Prepared or self not in _PREPARED: raise ValueError('Exact new retained recovery factory instance required')
        if self in _CONSUMED:
            if read_file(self.marker,64)!=self.campaign_sha256.encode('ascii'): raise ValueError('Consumed recovery marker changed')
        elif os.path.lexists(self.marker) or os.path.lexists(self.receipt): raise ValueError('Retained recovery authority already consumed')
        self.lineage.check(deep);self.frozen.check(deep)
        if self.mode=='restore':
            for name,data in (('plan.json',self.plan_bytes),('backupA.bin',self.preimage),('backupB.bin',self.preimage),('target.bin',self.stock)):
                if (deep or name=='plan.json') and read_file(self.directory/name)!=data: raise ValueError('New actual partial transaction changed')
            journal=json.loads(read_file(self.directory/'journal.json',65536))
            if (journal.get('record_sha256')!=digest(canonical({k:v for k,v in journal.items() if k!='record_sha256'}))
                    or type(journal.get('schema')) is not int or journal.get('schema')!=1 or journal.get('plan_sha256')!=digest(self.plan_bytes)
                    or journal.get('state') not in ('prepared','running','recovery_required','complete')
                    or journal.get('direction') not in (None,'install') or journal.get('sector_order')!=json.loads(self.plan_bytes)['sector_order']):
                raise ValueError('New journal self hash/state/order differs')
            if deep:
                tx=self.lineage.kernel.transaction_module();plan,_,a,b=tx.load_transaction(self.directory)
                if tx.encoded(plan)!=self.plan_bytes or a!=self.preimage or b!=self.stock: raise ValueError('New partial transaction changed')
            return journal

class _Policy:
    # Only constructed inside this module's exact registered Prepared factory.
    def __init__(self,prepared,binding,plan):
        self.prepared=prepared;self.binding_bytes=binding;self.plan_bytes=plan
        self.direction='install' if prepared.mode=='restore' else 'acquire'
        self.sectors=tuple(a for a,_ in json.loads(plan).get('writable_ranges',[]))
        self.target=prepared.stock;self.baseline=prepared.preimage
    def check_files(self): return self.prepared.check(deep=True)


def _prepared(c,path,raw,lineage,f,mode,directory=None,plan=None,preimage=b''):
    parent=lineage.parent if mode=='acquire' else Path(c['acquisition_receipt'])
    private_directory(parent);receipt=Path(c['receipt_path'])
    if not receipt.is_absolute() or receipt.parent!=parent: raise ValueError('Distinct direct recovery receipt required')
    marker=parent/('.retained-partial-'+lineage.campaign_sha256+'.'+mode+'.consumed')
    b=canonical(dict(usb_binding=json.loads(lineage.usb),original_campaign_sha256=lineage.campaign_sha256))
    bound=canonical(dict(json.loads(b),phase='loader',loader_sha256=lineage.bridge.LOADER_SHA,session_id=digest(raw)+':'+('install' if mode=='restore' else 'acquire'),identity=json.loads(lineage.identity)))
    initial_plan=plan or canonical(dict(identity=json.loads(lineage.identity),writable_ranges=[]))
    p=Prepared(mode,path,canonical(c),digest(raw),receipt,marker,lineage,f,time.time(),directory,initial_plan,preimage,lineage.stock,
        acquisition_operations(lineage.cursor) if mode=='acquire' else (),lineage.runtime,lineage.bridge,lineage.header_type,lineage.mapping,(),bound)
    policy=_Policy(p,b,initial_plan)
    # No foreign registry mutation or caller-replaced token; the new instance
    # becomes authoritative only at the end of this exact actual-file factory.
    object.__setattr__(p,'policies',(policy,));_PREPARED.add(p);p.check(deep=True);return p


def prepare_acquisition(path):
    if PREFIX_SHA is None or INSTALL_CAPTURE_SHA is None:raise ValueError('Reviewed caught-prefix/capture dependencies remain closed')
    path=Path(path).absolute();f=_Frozen();raw=f.freeze(path,limit=65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','stopped_path','stopped_sha256','witness_path','witness_sha256','receipt_path'}
    if set(c)!=keys or type(c['schema']) is not int or c['schema']!=1 or c['kind']!='fm1-retained-partial-dual-read': raise ValueError('Exact distinct acquisition campaign required')
    f.freeze(Path(__file__).absolute(),c['adapter_sha256']);f.freeze(c['stopped_path'],c['stopped_sha256'],65536)
    lineage=validate_stopped(c['stopped_path']);witness(f.freeze(c['witness_path'],c['witness_sha256'],65536),lineage,time.time())
    if ctypes.sizeof(lineage.header_type)!=88: raise ValueError('Reviewed 64-bit SG_IO layout required')
    return _prepared(c,path,raw,lineage,f,'acquire')


def native_type(prepared):
    prepared.check(deep=True)
    base=prepared.runtime.RehearsalSG
    class RetainedSG(base):
        def __init__(self,log):
            if prepared not in _CONSUMED or not 0<=time.time()-prepared.admission_time<=10:
                raise ValueError('One-use consumed opening window required')
            self.next=0
            super().__init__(prepared,prepared.policies[0],log)
        def binding(self):
            prepared.check()
            return super().binding()
        def validate_wire(self,cdb,payload,in_size):
            if prepared.mode=='acquire':
                if self.next>=len(prepared.operations) or (cdb,payload,in_size)!=prepared.operations[self.next][1:]:
                    raise ValueError('Exact ordered read-only dual inventory required')
            else: super().validate_wire(cdb,payload,in_size)
        def exchange(self,cdb,payload=b'',in_size=0):
            # next advances only after the entire exact successful exchange;
            # inherited sticky failure closes the handle, so no retry is possible.
            result=super().exchange(cdb,payload,in_size)
            if prepared.mode=='acquire': self.next+=1
            return result
    return RetainedSG


def _run(prepared,body):
    prepared.check(deep=True);prepared.receipt.mkdir(mode=0o700,exist_ok=False);sync_dir(prepared.receipt.parent)
    exclusive(prepared.marker,prepared.campaign_sha256.encode('ascii'));_CONSUMED.add(prepared)
    fd=os.open(prepared.receipt/'commands.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try: events=os.fdopen(fd,'w');fd=None
    finally:
        if fd is not None: os.close(fd)
    transport=None
    with events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush();os.fsync(events.fileno());sync_dir(prepared.receipt)
        try:
            log('retained_partial_prepared',campaign_sha256=prepared.campaign_sha256,mode=prepared.mode,
                original_campaign_sha256=prepared.lineage.campaign_sha256,sg_binding=json.loads(prepared.mapping),retry=False)
            transport=native_type(prepared)(log)
            return body(transport,log)
        except BaseException as exc:
            if transport is not None:
                transport.failed=True
                try:transport.close()
                except BaseException:pass
            for n in ('manifest.json','result.json'):
                try:(prepared.receipt/n).unlink(missing_ok=True);sync_dir(prepared.receipt)
                except OSError:pass
            try:log('retained_partial_stopped_ambiguous',error=type(exc).__name__,mode=prepared.mode,retry=False,stock_baseline_restored=False,boot_observed=False)
            except OSError:pass
            raise
        finally:
            if transport is not None:transport.close()


def run_acquisition(prepared):
    if type(prepared) is not Prepared or prepared.mode!='acquire': raise ValueError('Exact acquisition required')
    def body(transport,log):
        dumps=[]
        for name in ('dumpA.bin','dumpB.bin'):
            chunks=[]
            while transport.next<len(prepared.operations):
                label,cdb,payload,size=prepared.operations[transport.next]
                if label not in ('online',name,name+'.end'): raise ValueError('Acquisition pass order differs')
                data=transport.exchange(cdb,payload,size)
                if label==name:chunks.append(data)
                if label==name+'.end':break
            data=b''.join(chunks)
            if len(data)!=FLASH:raise ValueError('Full bounded dual pass required')
            exclusive(prepared.receipt/name,data);dumps.append(data)
        prepared.lineage.cursor.check_dumps(prepared.lineage.prefix,*dumps,prepared.stock)
        transport.binding();transport.close();prepared.check(deep=True)
        if transport.next!=8707:raise ValueError('Complete exact dual inventory required')
        result=dict(schema=1,kind='fm1-retained-partial-completed-dual-read',campaign_sha256=prepared.campaign_sha256,
            original_campaign_sha256=prepared.lineage.campaign_sha256,adapter_sha256=digest(read_file(Path(__file__).absolute())),
            usb_binding=json.loads(prepared.lineage.usb),sg_binding=json.loads(prepared.mapping),commands=8707,
            dumps=[dict(file=n,bytes=FLASH,sha256=digest(d),complete=True) for n,d in zip(('dumpA.bin','dumpB.bin'),dumps)],
            loader_uploaded=False,flash_written=False,physical_recovery_verified=False)
        log('retained_partial_acquisition_completed',identical=True,bytes_per_dump=FLASH,partial_sha256=digest(dumps[0]),retry=False)
        exclusive(prepared.receipt/'manifest.json',canonical(result)+b'\n');return result
    return _run(prepared,body)

@dataclass(frozen=True,eq=False)
class Acquired:
    lineage: Lineage
    frozen: object
    receipt: Path
    campaign_sha256: str
    a: bytes
    b: bytes
    completed_at: float
    def check(self,deep=True):
        if type(self) is not Acquired or self not in _ACQUIRED:raise ValueError('Exact independently replayed acquisition required')
        self.lineage.check(deep);self.frozen.check(deep)
_ACQUIRED=WeakSet()


def validate_acquisition(path, *, campaign_sha256, manifest_sha256, commands_sha256, capture_inputs):
    """Historical completed dual read only; no opener or witness refresh."""
    if ACQUIRE_CAPTURE_SHA is None:raise ValueError('Reviewed acquisition capture source remains closed')
    f=_Frozen();raw=f.freeze(Path(path).absolute(),campaign_sha256,65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','stopped_path','stopped_sha256','witness_path','witness_sha256','receipt_path'}
    if set(c)!=keys or type(c['schema'])is not int or c['schema']!=1 or c['kind']!='fm1-retained-partial-dual-read':raise ValueError('Exact acquisition campaign required')
    f.freeze(Path(__file__).absolute(),c['adapter_sha256']);f.freeze(c['stopped_path'],c['stopped_sha256'],65536)
    lineage=validate_stopped(c['stopped_path']);receipt=private_directory(c['receipt_path'])
    if receipt.parent!=lineage.parent:raise ValueError('Original private acquisition parent differs')
    marker=receipt.parent/('.retained-partial-'+lineage.campaign_sha256+'.acquire.consumed')
    if f.freeze(marker,limit=64)!=campaign_sha256.encode('ascii'):raise ValueError('Actual exclusive acquisition marker required')
    saved=json.loads(f.freeze(receipt/'manifest.json',manifest_sha256,65536))
    commands=f.freeze(receipt/'commands.jsonl',commands_sha256,16*FLASH)
    rows=[json.loads(x) for x in commands.decode('utf8').splitlines()]
    times=tuple(x.get('time') for x in rows)
    if any(type(t)not in(int,float) or not math.isfinite(t) or t<0 for t in times) or tuple(sorted(times))!=times:raise ValueError('Finite complete read chronology required')
    witness(f.freeze(c['witness_path'],c['witness_sha256'],65536),lineage,times[0])
    a,b=(f.freeze(receipt/n,limit=FLASH) for n in ('dumpA.bin','dumpB.bin'))
    lineage.cursor.check_dumps(lineage.prefix,a,b,lineage.stock)
    cursor=lineage.cursor._Cursor(rows,lineage.stock,a,'acquire')
    cursor.event('retained_partial_prepared',campaign_sha256=campaign_sha256,mode='acquire',original_campaign_sha256=lineage.campaign_sha256,sg_binding=json.loads(lineage.mapping),retry=False)
    ops=acquisition_operations(lineage.cursor)
    requests=[]
    for label,cdb,payload,size in ops:
        offset=int.from_bytes(cdb[2:6],'big')
        response=(a if label=='dumpA.bin' else b)[offset:offset+256] if cdb[:2]==b'\xfd\x05' else None
        cursor.command(int.from_bytes(cdb[:2],'big'),offset if response is not None else 0,response=response)
        requests.append((cdb,payload,size,response))
    cursor.event('retained_partial_acquisition_completed',identical=True,bytes_per_dump=FLASH,partial_sha256=digest(a),retry=False)
    if cursor.position!=len(rows) or len(ops)!=8707:raise ValueError('Exact complete dual request inventory required')
    expected=dict(schema=1,kind='fm1-retained-partial-completed-dual-read',campaign_sha256=campaign_sha256,
        original_campaign_sha256=lineage.campaign_sha256,adapter_sha256=c['adapter_sha256'],usb_binding=json.loads(lineage.usb),sg_binding=json.loads(lineage.mapping),commands=8707,
        dumps=[dict(file=n,bytes=FLASH,sha256=digest(d),complete=True) for n,d in zip(('dumpA.bin','dumpB.bin'),(a,b))],
        loader_uploaded=False,flash_written=False,physical_recovery_verified=False)
    if canonical(saved)!=canonical(expected):raise ValueError('Exact completed acquisition manifest required')
    captured=capture(f,capture_inputs,pin=ACQUIRE_CAPTURE_SHA,kind='fm1-retained-partial-acquire-one-shot',campaign_sha=campaign_sha256,
        adapter_sha=c['adapter_sha256'],usb=lineage.usb,times=times,exit_status=0)
    lineage.cursor.verify_wire(lineage.wire_parser._records(captured,json.loads(lineage.usb),json.loads(lineage.usb)),tuple(requests),stopped=False)
    p=Acquired(lineage,f,receipt,campaign_sha256,a,b,times[-1]);_ACQUIRED.add(p);p.check();return p


def create_restore_transaction(directory, acquisition):
    """File-only genuine partial preimage -> stock; never clones old journal."""
    acquisition.check()
    l=acquisition.lineage
    return l.kernel.prepare_transaction(Path(directory).absolute(),acquisition.a,acquisition.b,l.stock,json.loads(l.identity),tuple(sorted(ORDER)))


def prepare_restore(path):
    if ACQUIRE_CAPTURE_SHA is None:raise ValueError('Reviewed complete acquisition capture remains closed')
    path=Path(path).absolute();f=_Frozen();raw=f.freeze(path,limit=65536);c=json.loads(raw)
    keys={'schema','kind','adapter_sha256','acquisition_campaign_path','acquisition_campaign_sha256','acquisition_manifest_sha256','acquisition_commands_sha256',
        'acquisition_capture','acquisition_receipt','directory','witness_path','witness_sha256','receipt_path'}
    if set(c)!=keys or type(c['schema'])is not int or c['schema']!=1 or c['kind']!='fm1-retained-partial-to-stock-only':raise ValueError('Exact separate stock-recovery campaign required')
    f.freeze(Path(__file__).absolute(),c['adapter_sha256'])
    acquired=validate_acquisition(c['acquisition_campaign_path'],campaign_sha256=c['acquisition_campaign_sha256'],manifest_sha256=c['acquisition_manifest_sha256'],
        commands_sha256=c['acquisition_commands_sha256'],capture_inputs=c['acquisition_capture'])
    if str(acquired.receipt)!=c['acquisition_receipt']:raise ValueError('Actual acquired receipt differs')
    l=acquired.lineage
    w=witness(f.freeze(c['witness_path'],c['witness_sha256'],65536),l,time.time())
    if w['observed_at']<acquired.completed_at:raise ValueError('Restore witness precedes full new acquisition')
    directory=Path(c['directory'])
    for name in ('plan.json','backupA.bin','backupB.bin','target.bin','journal.json'):
        f.freeze(directory/name,limit=65536 if name.endswith('.json') else FLASH)
    # The new journal intentionally changes during restoration. All other
    # artifacts and the original failed journal remain immutable.
    f.files.pop(directory/'journal.json')
    tx=l.kernel.transaction_module();plan,journal,a,b=tx.load_transaction(directory)
    geometry=l.kernel.geometry(acquired.a,acquired.b,l.stock,tuple(sorted(ORDER)))
    if (a!=acquired.a or b!=l.stock or plan['scope']!=l.kernel.SCOPE or plan['identity']!=json.loads(l.identity)
            or plan['writable_ranges']!=[[x,x+4096] for x in geometry['dirty_sectors']] or plan['sector_order']!=geometry['sector_order']
            or plan.get('commit_sector')!=(0x4000 if 0x4000 in geometry['dirty_sectors'] else None)
            or journal['state']!='prepared' or journal['direction'] is not None or journal['intent'] is not None):
        raise ValueError('New untouched genuine partial->stock transaction required')
    # Retain every positive/negative from independently replayed acquisition.
    for p,(data,limit) in acquired.frozen.files.items():f.freeze(p,digest(data),limit)
    for p in acquired.frozen.absent:f.missing(p)
    return _prepared(c,path,raw,l,f,'restore',directory,tx.encoded(plan),a)


def run_restore(prepared):
    if type(prepared)is not Prepared or prepared.mode!='restore':raise ValueError('Exact stock restoration required')
    journal=prepared.check(deep=True)
    if journal['state']!='prepared' or journal['direction'] is not None or journal['intent'] is not None:raise ValueError('New unused partial transaction required')
    def body(transport,log):
        class StockSession(prepared.lineage.kernel.Session):
            def mutation(self,operation,address,payload=b''):
                prepared.check(deep=True)
                return super().mutation(operation,address,payload)
        session=StockSession(prepared,transport,log)
        try:
            result=prepared.lineage.kernel.transaction_module().run_transaction(prepared.directory,session,'install',checkpoint=log)
            session.close();prepared.check(deep=True)
            if result['verified_sha256']!=STOCK_SHA or session.uncertain:raise ValueError('Full exact stock and no unresolved write spans required')
            output=dict(schema=1,kind='fm1-retained-partial-stock-completed',campaign_sha256=prepared.campaign_sha256,purpose='stock_restore',internal_action='install',
                verified_sha256=STOCK_SHA,preimage_sha256=digest(prepared.preimage),full_flash_readback_verified=True,sectors_written=result['sectors_written'],
                sector_order=result['sector_order'],stock_baseline_restored=True,boot_observed=False,physical_recovery_verified=False,kernel_exclusivity=False)
            log('retained_partial_stock_completed',**output);exclusive(prepared.receipt/'result.json',canonical(output)+b'\n');return output
        finally:session.close()
    return _run(prepared,body)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=('acquire','restore'));ap.add_argument('--campaign',type=Path,required=True);a=ap.parse_args()
    if sys.platform!='linux' or sys.flags.optimize!=0:raise SystemExit('Non-optimized Linux SG_IO only')
    os.umask(0o077)
    run_acquisition(prepare_acquisition(a.campaign)) if a.mode=='acquire' else run_restore(prepare_restore(a.campaign))
if __name__=='__main__':main()

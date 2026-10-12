#!/usr/bin/env python3
"""MIT. One exact fixed-loader upload and dual target backups after returned ROM.

Separate provenance factory; no forged softkey entry, erase/program/reset,
extra ROM reads or retry. Loader/ROM protocol credit: Andrey Grigoryev's
kagaimiq/jl-uboot-tool via the pinned reviewed reader and fixed-backup bridge.
Stock identity is historical lineage, not a fresh running-application query.
"""
import argparse
import ctypes as C
import fcntl
import binascii
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct
import sys
import time
import types
from weakref import WeakSet

REHEARSAL_SHA = 'f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
TARGET_RESET_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
APP_SHA = '991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9'
ELF_SHA = '8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2'
TARGET_SHA = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
MAX_SNAPSHOT_AGE = 120
LIVE_SECONDS = 10
BACKUP_SOURCE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
PROVENANCE_SOURCE_SHA = '8fb33694f3daa26e3a824f33f1b9fa8d646dc5e9295795ea8fff6ea3a983b733'
PROBE_WRAPPER_SHAS = {
    'successful': 'b3b8186eb5bf11f359b09ff54a0f5f63a1ca317ad7341a6db5bd2f321573eaee',
    'detached': 'f88c09edcc0466005c5d6739546697b9ea6ea24555f58bddcf31910629736528',
}
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
    if digest(source) != expected:
        raise ValueError('Reviewed source differs')
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(source, str(path), 'exec'), module.__dict__)
    return module


def finite_time(value):
    return type(value) in (int, float) and math.isfinite(value)


def verify_boot(raw, c, boot_sha, manifest_sha, install_completed):
    """Exact four-event target-reset envelope; completion is not boot proof."""
    events = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    times = [e.get('time') for e in events]
    if (len(events) != 4 or not all(finite_time(t) for t in times) or
            times != sorted(times) or times[0] < install_completed or times[-1] > time.time()):
        raise ValueError('Exact chronological target-boot receipt required')
    expected = [dict(event='target_reset_prepared', campaign_sha256=boot_sha,
        install_campaign_sha256=c['install_campaign_sha256'],
        install_commands_sha256=c['install_commands_sha256'], target_sha256=TARGET_SHA,
        target_boot_authorization='exact-sdk-display-diagnostic',
        backup_manifest_sha256=manifest_sha, adapter_sha256=TARGET_RESET_SHA,
        commands=1, flash_operations=0, upload_operations=0, kernel_exclusivity=False,
        boot_observed=False, display_observed=False, physical_recovery_verified=False),
        dict(event='reset_submit_intent', phase='installed-fixed-loader',
            cdb='fc0c00000001ffffffffffffffffffff', in_len=16, out_len=0,
            retry=False, boot_observed=False),
        dict(event='reset_sg_completion', status=0, masked=0, msg=0, host=0, driver=0,
            resid=0, info=0, sense_len=0, sense_hex='', retry=False, boot_observed=False),
        dict(event='reset_request_completed', request_completion=True, core_reset_observed=False,
            boot_observed=False, retry=False, display_observed=False, physical_recovery_verified=False)]
    for event, wanted in zip(events, expected):
        event = dict(event); event.pop('time')
        if canonical(event) != canonical(wanted):
            raise ValueError('Target-boot event/order differs')
    return times[-1]


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
    provenance: object = None
    connection_witness: bytes = None

    def check(self):
        require_prepared(self, check=False)
        for path,data,limit in self.evidence:
            if read_file(path,limit) != data:
                raise ValueError('Frozen returned-ROM evidence changed')
        for policy in self.policies:
            policy.check_files()
        if self.provenance is not None:
            self.provenance.check()
        if self.request_inventory_sha256 != self.bridge.inventory_digest(self.operations):
            raise ValueError('Frozen command inventory changed')


def require_prepared(prepared, *, check=True):
    if not isinstance(prepared,Prepared) or prepared not in _AUTHORIZED:
        raise ValueError('Exact prepared returned-ROM instance required')
    if check:
        prepared.check()


def inventory(bridge,reader,loader,profile):
    operations=[]
    def add(op,phase,label,address=0,payload=b''):
        cdb,data,size=reader.request(op,phase,address=address,payload=payload)
        operations.append(bridge.Operation(phase,cdb,data,size,label))
    add(0x12,'rom','inquiry')
    for index,offset in enumerate(range(0,bridge.LOADER_SIZE,512)):
        add(0xFB06,'rom','upload',bridge.RAM+offset,loader[offset:offset+512])
        op=operations[-1]
        if profile['upload_inventory'][index] != dict(index=index,address=bridge.RAM+offset,
                bytes=512,cdb_sha256=digest(op.cdb),payload_sha256=digest(op.payload),read_size=0):
            raise ValueError('Fixed upload inventory differs')
    if (len(profile['upload_inventory'])!=47 or profile['patched_encrypted_sha256']!=bridge.LOADER_SHA
            or profile['original_encrypted_sha256']!=bridge.ORIGINAL_SHA):
        raise ValueError('Fixed profile identity differs')
    add(0xFB08,'rom','jump',bridge.RAM)
    add(0xFC14,'loader','buffer');add(0xFC0A,'loader','online')
    for name in ('dumpA.bin','dumpB.bin'):
        for address in range(0,bridge.FLASH_SIZE,bridge.PAGE):
            if address%4096==0:add(0xFC0A,'loader','online')
            add(0xFD05,'loader',name,address)
        add(0xFC0A,'loader',name+'.end')
    return tuple(operations)



def validate_read_receipt(raw, manifest, config, operations, dump_a, dump_b):
    """Replay all completed reads; evidence only, never an opener capability.

    Source/provenance/marker validation belongs to the completed-backup factory.
    This independently checks command framing, chronology, SG status and every
    returned target page hash against the two actual complete dump files.
    """
    rows = [json.loads(line) for line in raw.decode('utf8').splitlines()]
    times = [row.get('time') for row in rows]
    if (len(operations) != 8757 or len(rows) != 17516 or
            not all(finite_time(t) for t in times) or times != sorted(times) or times[-1] > time.time() or
            len(dump_a) != 1048576 or dump_a != dump_b or digest(dump_a) != TARGET_SHA or
            manifest.get('current_flash_sha256') != TARGET_SHA or manifest.get('identical') is not True or
            manifest.get('command_completions') is not True or manifest.get('commands') != 8757 or
            manifest.get('flash_bytes') != 1048576 or manifest.get('flash_readback_only') is not True or
            manifest.get('historical_unit_identity') != 'FM-1_092'):
        raise ValueError('Complete chronological exact dual-target read receipt required')
    first = dict(event='returned_backup_prepared', campaign_sha256=manifest['campaign_sha256'],
        adapter_sha256=config['adapter_sha256'],
        target_boot_campaign_sha256=config['target_boot_campaign_sha256'],
        rom_snapshot_sha256=config['rom_snapshot_sha256'],
        original_manifest_sha256=manifest['original_manifest_sha256'],
        usb_binding=manifest['usb_binding'], commands=8757,
        request_inventory_sha256=manifest['request_inventory_sha256'],
        loader_sha256=manifest['loader_sha256'], profile_sha256=manifest['loader_profile_sha256'],
        kernel_exclusivity=False, physical_recovery_verified=False)
    last = dict(event='returned_backup_completed', identical=True, bytes_per_dump=1048576,
        target_sha256=TARGET_SHA, physical_recovery_verified=False, retry=False)
    def same(row, expected):
        return canonical({k:v for k,v in row.items() if k != 'time'}) == canonical(expected)
    if (not same(rows[0], first) or not same(rows[-1], last) or
            any(manifest.get(k) is not False for k in ('physical_recovery_verified',
                'boot_observed','display_observed','kernel_exclusivity'))):
        raise ValueError('Returned-backup envelope or acceptance flags differ')
    for index, op in enumerate(operations):
        intent, completed = rows[1+index*2:3+index*2]
        wanted = dict(event='sg_submit_intent', index=index, phase=op.phase, label=op.label,
            cdb=op.cdb.hex(), payload_sha256=digest(op.payload) if op.payload else None,
            out_len=len(op.payload), in_len=op.read_size, retry=False)
        response = completed.get('response_sha256')
        if op.label in ('dumpA.bin','dumpB.bin'):
            address = int.from_bytes(op.cdb[2:6], 'big')
            expected_response = digest(dump_a[address:address+256])
        elif not op.read_size:
            expected_response = None
        else:
            if not isinstance(response,str) or len(response) != 64 or any(c not in '0123456789abcdef' for c in response):
                raise ValueError('Bounded protocol reply digest missing')
            expected_response = response  # Flags/JEDEC/echo are guarded at execution; bytes unavailable here.
        status = dict(event='sg_completion',index=index,status=0,masked=0,msg=0,host=0,
            driver=0,resid=0,info=0,sense_len=0,sense_hex='',response_sha256=expected_response,retry=False)
        if not same(intent,wanted) or not same(completed,status):
            raise ValueError('Exact returned read command/completion/page hash differs')
    dumps = [dict(file=name,bytes=1048576,sha256=TARGET_SHA,complete=True)
             for name in ('dumpA.bin','dumpB.bin')]
    if canonical(manifest.get('dumps')) != canonical(dumps):
        raise ValueError('Durable complete dump records differ')
    return times[0], times[-1]

def historical_probe_admission(config, state, freeze, backup_admission):
    """Use the validated original probe boundary, never restamp its snapshot."""
    path, expected = config['probe_admission_path'], config['probe_admission_sha256']
    if config['optional_stage_probe'] is None:
        if path is not None or expected is not None or config['probe_capture_path'] is not None:
            raise ValueError('No-probe admission cannot invent historical evidence')
        return backup_admission
    if config['optional_stage_probe'] != config['returned_state_campaign_path']:
        raise ValueError('Exact original probe campaign required')
    if config['probe_capture_path'] is not None:
        envelope = json.loads(freeze(config['probe_capture_path'], limit=65536))
        native_path = Path(envelope['native_campaign_path'])
        native = json.loads(freeze(native_path, envelope['native_campaign_sha256'], 65536))
        if native.get('probe_campaign_path') != config['optional_stage_probe']:
            raise ValueError('Original stopped native probe identity differs')
        wanted = native_path.parent / 'preflight.json'
        raw = freeze(path, expected, 65536)
        admission = json.loads(raw)['time']
    else:
        wanted = Path(state['receipt_path']) / 'commands.jsonl'
        raw = freeze(path, expected, 1048576)
        first = json.loads(raw.splitlines()[0])
        if first.get('event') != 'stage_probe_prepared':
            raise ValueError('Original completed probe admission event required')
        admission = first['time']
    if (Path(path) != wanted or not finite_time(admission) or
            not admission <= backup_admission <= time.time()):
        raise ValueError('Exact historical original probe admission required')
    # The shared helper independently validates all bytes, original120s age,
    # completion or owned stopped-capture evidence and the consumed marker.
    return admission


def validate_connection_witness(witness, snapshot, snapshot_sha256, evaluated_at):
    """Fresh passive observation of the unchanged original ROM connection."""
    keys = {'schema','kind','observed_at','usb_binding','sg_binding',
        'rom_snapshot_sha256','quiet_state'}
    if (set(witness) != keys or type(witness['schema']) is not int or witness['schema'] != 1 or
            witness['kind'] != 'fm1-passive-returned-rom-backup-connection' or
            witness['quiet_state'] != 'returned-rom-after-read-only-probe-no-loader-upload' or
            witness['rom_snapshot_sha256'] != snapshot_sha256 or
            not finite_time(witness['observed_at']) or not finite_time(evaluated_at) or
            not snapshot['observed_at'] <= witness['observed_at'] <= evaluated_at or
            not 0 <= evaluated_at - witness['observed_at'] <= MAX_SNAPSHOT_AGE or
            canonical(witness['usb_binding']) != canonical(snapshot['usb_binding']) or
            canonical(witness['sg_binding']) != canonical(snapshot['sg_binding'])):
        raise ValueError('Fresh passive unchanged ROM connection witness required')


def _validate_campaign(path, *, evaluated_at, completed=False, install_journal_path=None):
    """Shared file proof; returned Prepared is not registered as authority."""
    if not finite_time(evaluated_at) or evaluated_at > time.time():
        raise ValueError('Finite historical admission time required')
    evidence = []

    def freeze(path, expected=None, limit=2 * 1048576):
        path = Path(path)
        data = read_file(path, limit)
        if expected is not None and digest(data) != expected:
            raise ValueError('Pinned probe evidence differs')
        evidence.append((path, data, limit))
        return data

    raw = freeze(Path(path).absolute(), limit=65536)
    c = json.loads(raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'target_boot_campaign_path',
        'target_boot_campaign_sha256', 'target_boot_commands_sha256', 'target_boot_exit_status',
        'loader_path', 'profile_path', 'profile_source_path', 'optional_stage_probe',
        'rom_snapshot_path', 'rom_snapshot_sha256', 'active_session_state', 'receipt_path',
        'returned_state_campaign_path', 'returned_state_campaign_sha256', 'provenance_mode', 'probe_capture_path', 'connection_witness_path',
        'connection_witness_sha256', 'probe_admission_path', 'probe_admission_sha256'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-exact-target-returned-rom-backup' or
            type(c['target_boot_exit_status']) is not int or c['target_boot_exit_status'] != (1 if c.get('provenance_mode') == 'detached' else 0) or
            c['active_session_state'] != 'returned-rom-no-later-commands-no-loader-upload'):
        raise ValueError('Exact returned-ROM backup policy required')
    if c['provenance_mode'] not in ('successful','detached'):
        raise ValueError('Exact returned reset provenance mode required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    helper_path = root / 'fm1_diagnostic_detached_probe.py'
    freeze(helper_path, PROVENANCE_SOURCE_SHA)
    helper = load_source(helper_path, PROVENANCE_SOURCE_SHA, '_fm1_returned_state_proof')
    state_raw = freeze(c['returned_state_campaign_path'], c['returned_state_campaign_sha256'], 65536)
    state = json.loads(state_raw)
    for field in ('target_boot_campaign_path','target_boot_campaign_sha256',
            'target_boot_commands_sha256','target_boot_exit_status','rom_snapshot_path','rom_snapshot_sha256'):
        if state.get(field) != c[field]:
            raise ValueError('Exact returned-state envelope identity differs')
    if install_journal_path is not None and not completed:
        raise ValueError('Historical journal cannot grant fresh opener authority')
    admission_time = historical_probe_admission(c, state, freeze, evaluated_at)
    proof = helper.validate_returned_state(c['returned_state_campaign_path'], evaluated_at=admission_time,
        completed_probe=c['optional_stage_probe'], probe_capture=c['probe_capture_path'],
        provenance_mode=c['provenance_mode'], install_journal_path=install_journal_path,
        probe_wrapper_sha256=PROBE_WRAPPER_SHAS[c['provenance_mode']] if c['probe_capture_path'] is not None else None)
    for item in proof.evidence:
        freeze(item[0],digest(item[1]),item[2])
    policies = proof.policies
    for policy in policies:
        for item in policy.evidence:
            freeze(item[0],digest(item[1]),item[2])
        for name in ('plan.json','backupA.bin','backupB.bin','target.bin'):
            freeze(policy.directory/name)
        policy.check_files()
    # Mutable transaction journal is excluded by the evidence-only proof, while
    # genuine SDK policy checks retain all immutable plan/image/artifact gates.
    snapshot_raw = freeze(c['rom_snapshot_path'],c['rom_snapshot_sha256'],65536)
    snapshot = json.loads(snapshot_raw)
    if canonical(snapshot) != proof.snapshot:
        raise ValueError('Returned-state passive binding differs')
    parent = Path(proof.private_parent)
    mapping = snapshot['sg_binding']
    witness_raw = freeze(c['connection_witness_path'], c['connection_witness_sha256'], 65536)
    witness = json.loads(witness_raw)
    validate_connection_witness(witness, snapshot, c['rom_snapshot_sha256'], evaluated_at)
    rehearsal_path = root / 'fm1_sdk_rehearsal.py'
    freeze(rehearsal_path, REHEARSAL_SHA)
    rehearsal = load_source(rehearsal_path,REHEARSAL_SHA,'_fm1_returned_state_rehearsal')
    for name,sha in rehearsal.SOURCES.items():freeze(root/name,sha)
    modules = rehearsal.imports()
    bridge = modules['fm1_fixed_loader_backup']
    destination = Path(c['receipt_path'])
    marker = parent/('.returned-rom-'+c['target_boot_campaign_sha256']+'.consumed')
    if (not destination.is_absolute() or destination.parent != parent or
            (not completed and (destination.exists() or marker.exists())) or
            not stat.S_ISDIR(parent.lstat().st_mode) or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New private returned-ROM receipt and unconsumed origin required')
    if completed and (not stat.S_ISDIR(destination.lstat().st_mode) or
            stat.S_IMODE(destination.stat().st_mode) != 0o700 or
            freeze(marker,limit=256) != digest(raw).encode('ascii')):
        raise ValueError('Exact consumed returned-ROM receipt required')
    loader = freeze(c['loader_path'], bridge.LOADER_SHA)
    profile = json.loads(freeze(c['profile_path'],bridge.PROFILE_SHA))
    if len(loader) != bridge.LOADER_SIZE:
        raise ValueError('Exact reviewed fixed loader length required')
    freeze(c['profile_source_path'],bridge.PROFILE_SOURCE_SHA)
    operations = inventory(bridge,modules['fm1_uboot_read'],loader,profile)
    p = Prepared(canonical(c),digest(raw),canonical(snapshot),tuple(evidence),policies,
        bridge,modules['fm1_uboot_read'].SGHeader,operations,bridge.inventory_digest(operations),
        proof.manifest_sha256,parent,proof,canonical(witness))
    if C.sizeof(p.header_type) != 88:
        raise ValueError('Reviewed Linux SG layout required')
    lineage = dict(original_rehearsal_campaign_sha256=proof.original_rehearsal_campaign_sha256,
        policy_inputs=json.loads(proof.original_inputs), install_journal_sha256=proof.install_journal_sha256)
    return p, lineage


def prepare_campaign(path):
    """Offline fresh admission; only this factory grants opener authority."""
    p, _ = _validate_campaign(path,evaluated_at=time.time())
    _AUTHORIZED.add(p);p.check()
    return p


def validate_completed_backup(path, *, campaign_sha256, manifest_sha256,
        commands_sha256, freeze, install_journal_path=None):
    """Evidence-only replay at recorded admission, never register or open SG.

    Full dual dumps and all request/completion/page hashes are checked. A trusted
    caller still attests exit zero and no later commands; files do not establish
    current topology or exclusive kernel ownership. No old marker is rewritten.
    """
    raw=freeze(Path(path),campaign_sha256,65536)
    c=json.loads(raw)
    receipt=Path(c['receipt_path'])
    manifest=json.loads(freeze(receipt/'manifest.json',manifest_sha256,65536))
    commands=freeze(receipt/'commands.jsonl',commands_sha256,8*1048576)
    first=json.loads(commands.splitlines()[0])
    p,lineage=_validate_campaign(path,evaluated_at=first.get('time'),completed=True,
        install_journal_path=install_journal_path)
    snapshot=json.loads(p.snapshot)
    dumps=[freeze(receipt/name,TARGET_SHA,1048576) for name in ('dumpA.bin','dumpB.bin')]
    expected=dict(schema=1,kind='fm1-returned-rom-fixed-loader-target-backup',
        campaign_sha256=p.campaign_sha256,adapter_sha256=c['adapter_sha256'],
        target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
        rom_snapshot_sha256=c['rom_snapshot_sha256'],optional_stage_probe=c['optional_stage_probe'],
        returned_state_campaign_sha256=c['returned_state_campaign_sha256'],
        provenance_mode=c['provenance_mode'],provenance_source_sha256=PROVENANCE_SOURCE_SHA,
        probe_capture_path=c['probe_capture_path'],probe_wrapper_sha256=PROBE_WRAPPER_SHAS[c['provenance_mode']] if c['probe_capture_path'] is not None else None,
        connection_witness_sha256=c['connection_witness_sha256'],
        probe_admission_sha256=c['probe_admission_sha256'],
        original_manifest_sha256=p.original_manifest_sha256,
        loader_sha256=p.bridge.LOADER_SHA,original_loader_sha256=p.bridge.ORIGINAL_SHA,
        loader_profile_sha256=p.bridge.PROFILE_SHA,profile_source_sha256=p.bridge.PROFILE_SOURCE_SHA,
        dependency_sha256=dict(fixed_loader_backup=BACKUP_SOURCE_SHA,reader=p.bridge.READER_SHA),
        request_inventory_sha256=p.request_inventory_sha256,
        usb_binding=snapshot['usb_binding'],sg_binding=snapshot['sg_binding'],
        flash_bytes=1048576,dumps=[dict(file=name,bytes=1048576,sha256=TARGET_SHA,complete=True)
            for name in ('dumpA.bin','dumpB.bin')],identical=True,command_completions=True,commands=8757,
        flash_readback_only=True,historical_unit_identity='FM-1_092',current_flash_sha256=TARGET_SHA,
        physical_recovery_verified=False,boot_observed=False,display_observed=False,kernel_exclusivity=False)
    if canonical(manifest)!=canonical(expected):
        raise ValueError('Exact completed returned-backup manifest required')
    started,ended=validate_read_receipt(commands,manifest,c,p.operations,*dumps)
    if not snapshot['observed_at']<=started<=ended or ended-started>900:
        raise ValueError('Returned-backup admission/whole-campaign chronology differs')
    for evidence_path,data,limit in p.evidence:
        if freeze(evidence_path,digest(data),limit)!=data:
            raise ValueError('Completed provenance changed during validation')
    for policy in p.policies:policy.check_files()
    p.provenance.check()
    return dict(**lineage,usb_binding=snapshot['usb_binding'],sg_binding=snapshot['sg_binding'],
        request_inventory_sha256=p.request_inventory_sha256,loader_sha256=p.bridge.LOADER_SHA,
        receipt_path=str(receipt),completed_at=ended,_absent_paths=tuple(p.provenance.absent))


class FixedSG:
    """One consumed ordered envelope with fail-closed FD and topology binding."""
    def __init__(self, prepared, log):
        require_prepared(prepared)
        self.prepared,self.log=prepared,log
        self.fd,self.next,self.ioctl_attempts,self.phase=None,0,0,'rom'
        self.failed,self.close_error=False,None
        self.started=time.monotonic()
        snapshot=json.loads(prepared.snapshot)
        self.usb=snapshot['usb_binding']
        try:
            if prepared.connection_witness is not None:
                validate_connection_witness(json.loads(prepared.connection_witness), snapshot,
                    json.loads(prepared.campaign)['rom_snapshot_sha256'], time.time())
            elif not 0 <= time.time()-snapshot['observed_at'] <= MAX_SNAPSHOT_AGE:
                raise ValueError('Returned-ROM snapshot stale before open')
            self.mapping=prepared.bridge.discover_sg(self.usb)
            if canonical(self.mapping)!=canonical(snapshot['sg_binding']):
                raise ValueError('New ROM SG binding replaced')
            self.fd=os.open(self.mapping['node'],os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            opened=os.fstat(self.fd)
            self.fd_identity=opened.st_dev,opened.st_ino,opened.st_rdev
            if not stat.S_ISCHR(opened.st_mode) or canonical(self.fd_identity)!=canonical(self.mapping['node_identity']):
                raise ValueError('Opened SG descriptor differs')
            self.binding()
        except BaseException:
            self.failed=True;self.close();raise

    def close(self):
        if self.close_error is not None:
            raise self.close_error
        if self.fd is not None:
            fd,self.fd=self.fd,None
            try:
                os.close(fd)
            except BaseException as exc:
                self.failed=True;self.close_error=exc;raise

    def binding(self):
        require_prepared(self.prepared,check=False)
        if self.failed or self.fd is None or not 0<=time.monotonic()-self.started<=900:
            raise ValueError('Closed, failed or stale returned-loader connection')
        if (self.prepared.provenance is not None and
                any(os.path.lexists(path) for path in self.prepared.provenance.absent)):
            raise ValueError('Returned provenance absent evidence appeared')
        opened=os.fstat(self.fd)
        if ((opened.st_dev,opened.st_ino,opened.st_rdev)!=self.fd_identity or
                not stat.S_ISCHR(opened.st_mode) or
                canonical(self.prepared.bridge.discover_sg(self.usb))!=canonical(self.mapping)):
            raise ValueError('New SG/sysfs/USB connection replaced')
        # Read-only phase has no writer authority; source drift still closes.
        root=Path(__file__).absolute().parent
        for name,sha in ((Path(__file__).name,json.loads(self.prepared.campaign)['adapter_sha256']),
                ('fm1_fixed_loader_backup.py',BACKUP_SOURCE_SHA),
                ('fm1_uboot_read.py',self.prepared.bridge.READER_SHA)):
            if digest(read_file(root/name))!=sha:
                raise ValueError('Reviewed backup source changed')

    def exchange_next(self):
        try:
            if self.failed or self.fd is None or self.next >= len(self.prepared.operations):
                raise ValueError('Closed, failed, or consumed campaign')
            index = self.next
            op = self.prepared.operations[index]
            self.next += 1  # Consume before logging, binding, or syscall.
            if op.phase != self.phase:
                raise ValueError('Campaign phase differs')
            command, sense = C.create_string_buffer(op.cdb), C.create_string_buffer(32)
            data = C.create_string_buffer(op.payload) if op.payload else C.create_string_buffer(op.read_size)
            h = self.prepared.header_type(interface_id=ord('S'), direction=-2 if op.payload else -3,
                cmd_len=len(op.cdb), sense_max=32, data_len=len(op.payload) or op.read_size,
                data=C.addressof(data), cmd=C.addressof(command), sense=C.addressof(sense), timeout=3000)
            self.log('sg_submit_intent', index=index, phase=self.phase, label=op.label,
                     cdb=op.cdb.hex(), payload_sha256=digest(op.payload) if op.payload else None,
                     out_len=len(op.payload), in_len=op.read_size, retry=False)
            self.binding()
            if self.phase=='rom':
                self.prepared.check()
                if index==0 and not 0<=time.monotonic()-self.started<=LIVE_SECONDS:
                    raise ValueError('Initial ROM upload window stale')
            self.ioctl_attempts += 1
            fcntl.ioctl(self.fd, 0x2285, h)
            self.binding()  # Re-enumeration is ambiguous even following a reply.
            self.log('sg_completion', index=index, status=h.status, masked=h.masked, msg=h.msg,
                     host=h.host, driver=h.driver, resid=h.resid, info=h.info,
                     sense_len=h.sense_len, sense_hex=sense.raw[:min(h.sense_len, 32)].hex(),
                     response_sha256=digest(data.raw[:op.read_size]) if op.read_size else None,retry=False)
            if (h.status or h.masked or h.msg or h.host or h.driver or h.resid or h.info or h.sense_len):
                raise OSError('Incomplete or unsuccessful SG_IO completion')
            result = data.raw[:op.read_size]
            if op.read_size == 16 and result[:2] != op.cdb[:2]:
                raise ValueError('Response command echo differs')
            if op.label == 'inquiry' and (result[8:16].strip() != b'WL82' or
                                           result[16:32].strip() != b'UBOOT1.00'):
                raise ValueError('Inquiry chip/boot mode differs')
            if op.label == 'buffer' and not self.prepared.bridge.PAGE <= int.from_bytes(result[2:6], 'big') <= 65535:
                raise ValueError('Unexpected loader buffer size')
            if op.cdb[:2] == b'\xfc\x0a' and (result[2] != 3 or int.from_bytes(result[4:8], 'little') != 0x856014):
                raise ValueError('Unexpected flash type/JEDEC')
            if op.label == 'jump':
                self.phase = 'loader'
            return op, result
        except BaseException:
            self.failed = True
            self.phase = 'failed'
            self.close()
            raise


def run_campaign(prepared):
    require_prepared(prepared)
    c=json.loads(prepared.campaign)
    receipt=Path(c['receipt_path'])
    marker=prepared.parent/('.returned-rom-'+c['target_boot_campaign_sha256']+'.consumed')
    receipt.mkdir(mode=0o700,exist_ok=False);prepared.bridge.sync_dir(receipt.parent)
    with prepared.bridge.private_file(marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii'));fp.flush();os.fsync(fp.fileno())
    prepared.bridge.sync_dir(marker.parent)
    with prepared.bridge.private_file(receipt/'commands.jsonl','w') as events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush()
            if event!='sg_completion' and (event!='sg_submit_intent' or
                    fields.get('phase')=='rom'):
                os.fsync(events.fileno());prepared.bridge.sync_dir(receipt)
        transport=None
        try:
            log('returned_backup_prepared',campaign_sha256=prepared.campaign_sha256,
                adapter_sha256=c['adapter_sha256'],target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
                rom_snapshot_sha256=c['rom_snapshot_sha256'],original_manifest_sha256=prepared.original_manifest_sha256,
                usb_binding=json.loads(prepared.snapshot)['usb_binding'],commands=8757,
                request_inventory_sha256=prepared.request_inventory_sha256,
                loader_sha256=prepared.bridge.LOADER_SHA,profile_sha256=prepared.bridge.PROFILE_SHA,
                kernel_exclusivity=False,physical_recovery_verified=False)
            transport=FixedSG(prepared,log)
            dumps=[]
            for name in ('dumpA.bin','dumpB.bin'):
                hasher,count=hashlib.sha256(),0
                with prepared.bridge.private_file(receipt/name) as fp:
                    while transport.next<len(prepared.operations):
                        pending=prepared.operations[transport.next]
                        if pending.label not in ('inquiry','upload','jump','buffer','online',name,name+'.end'):
                            break
                        op,data=transport.exchange_next()
                        if op.label==name:
                            fp.write(data);hasher.update(data);count+=len(data)
                        if op.label==name+'.end':break
                    fp.flush();os.fsync(fp.fileno())
                prepared.bridge.sync_dir(receipt)
                if count!=1048576 or hasher.hexdigest()!=TARGET_SHA:
                    raise ValueError('Complete exact target dump required')
                dumps.append(dict(file=name,bytes=count,sha256=hasher.hexdigest(),complete=True))
            transport.binding();transport.close()  # Close failure invalidates publication.
            prepared.check()
            if transport.next!=8757 or dumps[0]['sha256']!=dumps[1]['sha256']:
                raise ValueError('Exact complete dual inventory required')
            for entry in dumps:
                if digest(read_file(receipt/entry['file']))!=TARGET_SHA:
                    raise ValueError('Durable target dump differs')
            result=dict(schema=1,kind='fm1-returned-rom-fixed-loader-target-backup',
                campaign_sha256=prepared.campaign_sha256,adapter_sha256=c['adapter_sha256'],
                target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
                rom_snapshot_sha256=c['rom_snapshot_sha256'],optional_stage_probe=c['optional_stage_probe'],
        returned_state_campaign_sha256=c['returned_state_campaign_sha256'],
        provenance_mode=c['provenance_mode'],provenance_source_sha256=PROVENANCE_SOURCE_SHA,
        probe_capture_path=c['probe_capture_path'],probe_wrapper_sha256=PROBE_WRAPPER_SHAS[c['provenance_mode']] if c['probe_capture_path'] is not None else None,
        connection_witness_sha256=c['connection_witness_sha256'],
        probe_admission_sha256=c['probe_admission_sha256'],
                original_manifest_sha256=prepared.original_manifest_sha256,
                loader_sha256=prepared.bridge.LOADER_SHA,original_loader_sha256=prepared.bridge.ORIGINAL_SHA,
                loader_profile_sha256=prepared.bridge.PROFILE_SHA,
                profile_source_sha256=prepared.bridge.PROFILE_SOURCE_SHA,
                dependency_sha256=dict(fixed_loader_backup=BACKUP_SOURCE_SHA,reader=prepared.bridge.READER_SHA),
                request_inventory_sha256=prepared.request_inventory_sha256,
                usb_binding=json.loads(prepared.snapshot)['usb_binding'],sg_binding=transport.mapping,
                flash_bytes=1048576,dumps=dumps,identical=True,command_completions=True,commands=8757,
                flash_readback_only=True,historical_unit_identity='FM-1_092',current_flash_sha256=TARGET_SHA,
                physical_recovery_verified=False,boot_observed=False,display_observed=False,kernel_exclusivity=False)
            log('returned_backup_completed',identical=True,bytes_per_dump=1048576,
                target_sha256=TARGET_SHA,physical_recovery_verified=False,retry=False)
            with prepared.bridge.private_file(receipt/'manifest.json','w') as fp:
                json.dump(result,fp,sort_keys=True,allow_nan=False);fp.write('\n');fp.flush();os.fsync(fp.fileno())
            prepared.bridge.sync_dir(receipt)
            return result
        except BaseException as exc:
            if transport is not None:
                transport.failed=True
                try:transport.close()
                except BaseException:pass
            try:
                (receipt/'manifest.json').unlink(missing_ok=True);prepared.bridge.sync_dir(receipt)
                log('returned_backup_stopped_ambiguous',error=type(exc).__name__,retry=False)
            except BaseException:pass
            raise
        finally:
            if transport is not None:transport.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign',required=True,type=Path)
    args=parser.parse_args()
    if sys.platform!='linux':raise SystemExit('Linux SG_IO only')
    os.umask(0o077)
    run_campaign(prepare_campaign(args.campaign))


if __name__=='__main__':main()

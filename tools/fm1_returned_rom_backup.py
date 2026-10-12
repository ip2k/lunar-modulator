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

TARGET_RESET_SHA = 'b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a'
APP_SHA = '991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9'
ELF_SHA = '8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2'
TARGET_SHA = 'df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db'
MAX_SNAPSHOT_AGE = 120
LIVE_SECONDS = 10
BACKUP_SOURCE_SHA = '79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb'
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

    def check(self):
        require_prepared(self, check=False)
        for path,data,limit in self.evidence:
            if read_file(path,limit) != data:
                raise ValueError('Frozen returned-ROM evidence changed')
        for policy in self.policies:
            policy.check_files()
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


def prepare_campaign(path):
    """Offline file validation only. No discovery, SG open, or injected call."""
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
        'rom_snapshot_path', 'rom_snapshot_sha256', 'active_session_state', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-exact-target-returned-rom-backup' or
            type(c['target_boot_exit_status']) is not int or c['target_boot_exit_status'] != 0 or
            c['active_session_state'] != 'returned-rom-no-later-commands-no-loader-upload'):
        raise ValueError('Exact returned-ROM backup policy required')
    if c['optional_stage_probe'] is not None:
        raise ValueError('Optional probe requires its separately frozen receipt gate')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'])
    reset_path = root / 'fm1_fixed_target_reset.py'
    freeze(reset_path, TARGET_RESET_SHA)
    r = load_source(reset_path, TARGET_RESET_SHA, '_fm1_stage_verified_target_reset')
    freeze(root / 'fm1_fixed_loader_reset.py', r.RESET_SOURCE_SHA)
    freeze(root / 'fm1_sdk_install.py', r.INSTALL_SOURCE_SHA)
    rehearsal_path = root / 'fm1_sdk_rehearsal.py'
    freeze(rehearsal_path, r.REHEARSAL_SOURCE_SHA)
    rehearsal = load_source(rehearsal_path, r.REHEARSAL_SOURCE_SHA, '_fm1_stage_verified_rehearsal')
    for name, sha in rehearsal.SOURCES.items():
        freeze(root / name, sha)
    modules = rehearsal.imports()
    boot_raw = freeze(c['target_boot_campaign_path'], c['target_boot_campaign_sha256'], 65536)
    boot = json.loads(boot_raw)
    keys = {'schema', 'kind', 'adapter_sha256', 'install_adapter_path',
        'install_campaign_path', 'install_campaign_sha256', 'install_commands_sha256',
        'install_result_sha256', 'install_exit_status', 'journal_sha256',
        'active_session_state', 'usb_binding', 'sg_binding', 'receipt_path',
        'target_sha256', 'target_boot_authorization'}
    if (set(boot) != keys or type(boot['schema']) is not int or boot['schema'] != 1 or
            boot['kind'] != 'fm1-fixed-loader-sdk-target-reset' or boot['adapter_sha256'] != TARGET_RESET_SHA or
            Path(boot['install_adapter_path']) != root / 'fm1_sdk_install.py' or
            type(boot['install_exit_status']) is not int or boot['install_exit_status'] != 0 or
            boot['active_session_state'] != 'same-fixed-loader-installed-target-no-later-commands' or
            boot['target_sha256'] != TARGET_SHA or boot['target_boot_authorization'] != 'exact-sdk-display-diagnostic'):
        raise ValueError('Exact target-boot campaign required')
    install = json.loads(freeze(boot['install_campaign_path'], boot['install_campaign_sha256'], 65536))
    if (set(install) != {'schema','kind','adapter_sha256','rehearsal_campaign_path','rehearsal_campaign_sha256','receipt_path'} or
            type(install['schema']) is not int or install['schema'] != 1 or
            install['kind'] != 'fm1-exact-sdk-install-only' or install['adapter_sha256'] != r.INSTALL_SOURCE_SHA):
        raise ValueError('Exact install-only envelope required')
    campaign = json.loads(freeze(install['rehearsal_campaign_path'], install['rehearsal_campaign_sha256'], 65536))
    if (set(campaign) != {'schema','kind','adapter_sha256','policy_inputs','backup_exit_status',
            'backup_commands_sha256','active_session_state','sg_binding','receipt_path'} or
            type(campaign['schema']) is not int or campaign['schema'] != 1 or
            campaign['kind'] != 'fm1-exact-sdk-install-restore-rehearsal' or
            campaign['adapter_sha256'] != r.REHEARSAL_SOURCE_SHA or
            type(campaign['backup_exit_status']) is not int or campaign['backup_exit_status'] != 0 or
            campaign['active_session_state'] != 'matching-backup-no-later-commands' or
            canonical(campaign['sg_binding']) != canonical(boot['sg_binding'])):
        raise ValueError('Exact backing rehearsal envelope required')
    inputs = campaign['policy_inputs']
    policies = tuple(modules['fm1_bound_sdk_diagnostic'].load_policy(**inputs,
        direction=d, baseline_profile='fixed-loader') for d in ('install','restore'))
    plan, journal, baseline, target = modules['fm1_flash_transaction'].load_transaction(inputs['directory'])
    freeze(Path(inputs['directory']) / 'journal.json', boot['journal_sha256'], 65536)
    if (digest(baseline) != rehearsal.BASELINE_SHA or digest(target) != TARGET_SHA or
            journal['state'] != 'complete' or journal['direction'] != 'install' or
            journal['intent'] is not None or journal['verified_sha256'] != TARGET_SHA or
            plan['writable_ranges'] != [[a,a+4096] for a in range(0x4000,0x22000,4096)] or
            plan['commit_sector'] != 0x4000 or plan['sector_order'] != list(range(0x5000,0x22000,4096))+[0x4000]):
        raise ValueError('Exact completed target transaction required')
    # The pinned SDK policy checks the actual APP/ELF, not only manifest assertions.
    if digest(read_file(inputs['app_path'])) != APP_SHA or digest(read_file(inputs['elf_path'])) != ELF_SHA:
        raise ValueError('Exact current diagnostic native bytes required')
    manifest_raw = freeze(inputs['manifest_path'], limit=65536)
    manifest = json.loads(manifest_raw)
    bridge = modules['fm1_fixed_loader_backup']
    bridge.validate_usb(boot['usb_binding'])
    if (canonical(manifest['usb_binding']) != canonical(boot['usb_binding']) or
            canonical(manifest['sg_binding']) != canonical(boot['sg_binding'])):
        raise ValueError('Original install connection differs')
    backup = json.loads(freeze(inputs['campaign_path'], limit=65536))
    backup_raw = freeze(inputs['backup_log_path'], campaign['backup_commands_sha256'], 8*1048576)
    backup_done = r.reset.validate_commands(backup_raw, manifest,
        dict(backup, entry_log_path=inputs['entry_log_path']), bridge)
    parent = Path(inputs['manifest_path']).parent
    install_receipt, boot_receipt = Path(install['receipt_path']), Path(boot['receipt_path'])
    if (install['receipt_path'] != campaign['receipt_path'] or
            install_receipt.parent != parent or boot_receipt.parent != parent or
            not stat.S_ISDIR(install_receipt.lstat().st_mode) or not stat.S_ISDIR(boot_receipt.lstat().st_mode)):
        raise ValueError('Original direct receipts required')
    result = json.loads(freeze(install_receipt/'result.json', boot['install_result_sha256'],65536))
    commands = freeze(install_receipt/'commands.jsonl', boot['install_commands_sha256'],32*1048576)
    if not finite_time(json.loads(commands.splitlines()[0]).get('time')) or json.loads(commands.splitlines()[0])['time'] < backup_done:
        raise ValueError('Install chronology differs')
    install_done = r.verify_install(commands,result,install,boot['install_campaign_sha256'],
        campaign,rehearsal.SOURCES,baseline,target,plan['sector_order'])
    if freeze(parent/'.sdk-rehearsal.consumed',limit=256) != boot['install_campaign_sha256'].encode('ascii'):
        raise ValueError('Original consumed install required')
    if freeze(parent/'.target-core-reset.consumed',limit=256) != c['target_boot_campaign_sha256'].encode('ascii'):
        raise ValueError('Original consumed target boot required')
    boot_done = verify_boot(freeze(boot_receipt/'commands.jsonl',c['target_boot_commands_sha256'],65536),
        boot,c['target_boot_campaign_sha256'],digest(manifest_raw),install_done)
    snapshot_raw = freeze(c['rom_snapshot_path'],c['rom_snapshot_sha256'],65536)
    snapshot = json.loads(snapshot_raw)
    if (set(snapshot) != {'schema','kind','observed_at','usb_binding','sg_binding',
            'target_boot_campaign_sha256','quiet_state'} or
            type(snapshot['schema']) is not int or snapshot['schema'] != 1 or
            snapshot['kind'] != 'fm1-passive-post-target-boot-rom' or
            snapshot['target_boot_campaign_sha256'] != c['target_boot_campaign_sha256'] or
            snapshot['quiet_state'] != 'initial-rom-no-later-commands-no-loader-upload' or
            not finite_time(snapshot['observed_at']) or snapshot['observed_at'] < boot_done or
            not 0 <= time.time()-snapshot['observed_at'] <= MAX_SNAPSHOT_AGE):
        raise ValueError('Fresh passive initial-ROM snapshot required')
    bridge.validate_usb(snapshot['usb_binding'])
    usb, previous = snapshot['usb_binding'], boot['usb_binding']
    if (any(usb[k] != previous[k] for k in ('path','busnum','vid','pid')) or
            usb['devnum'] == previous['devnum'] or
            canonical(snapshot['sg_binding']) == canonical(boot['sg_binding'])):
        raise ValueError('Fresh ROM enumeration on original port required')
    mapping=snapshot['sg_binding']
    if (set(mapping) != {'node','class','device','usb','node_identity','class_identity','device_identity','usb_identity'} or
            not all(type(mapping[k]) is str and Path(mapping[k]).is_absolute() for k in ('node','class','device','usb')) or
            not all(type(mapping[k]) is list and len(mapping[k])==3 and
                all(type(v) is int and v>=0 for v in mapping[k]) for k in
                ('node_identity','class_identity','device_identity','usb_identity')) or
            mapping['usb_identity']==boot['sg_binding']['usb_identity']):
        raise ValueError('Complete fresh passive SG/sysfs mapping required')
    destination = Path(c['receipt_path'])
    marker = parent/('.returned-rom-'+c['target_boot_campaign_sha256']+'.consumed')
    if (not destination.is_absolute() or destination.parent != parent or destination.exists() or
            marker.exists() or not stat.S_ISDIR(parent.lstat().st_mode) or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New private returned-ROM receipt and unconsumed origin required')
    loader = freeze(c['loader_path'], bridge.LOADER_SHA)
    profile = json.loads(freeze(c['profile_path'],bridge.PROFILE_SHA))
    if len(loader) != bridge.LOADER_SIZE:
        raise ValueError('Exact reviewed fixed loader length required')
    freeze(c['profile_source_path'],bridge.PROFILE_SOURCE_SHA)
    operations = inventory(bridge,modules['fm1_uboot_read'],loader,profile)
    p = Prepared(canonical(c),digest(raw),canonical(snapshot),tuple(evidence),policies,
        bridge,modules['fm1_uboot_read'].SGHeader,operations,bridge.inventory_digest(operations),
        digest(manifest_raw),parent)
    if C.sizeof(p.header_type) != 88:
        raise ValueError('Reviewed Linux SG layout required')
    _AUTHORIZED.add(p); p.check()
    return p


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
            if not 0 <= time.time()-snapshot['observed_at'] <= MAX_SNAPSHOT_AGE:
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
                rom_snapshot_sha256=c['rom_snapshot_sha256'],optional_stage_probe=None,
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

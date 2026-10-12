"""MIT. Injected-only, one bare-ROM read of the exact diagnostic BSS span.

No SG opener, ioctl, loader upload, arbitrary memory API, reset, or flash I/O.
Protocol/codec facts: kagaimiq's MIT jl-uboot-tool adb3f188 (Andrey Grigoryev),
jltech/{uboot,cipher,crc}.py and docs/usb-loader-v2.md. This independent codec
uses Python's CRC primitive; no third-party executable source is imported.
WL82's in-place RAM cipher and retention across P33 are reported, not proved.
"""
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
INQUIRY = bytes.fromhex('120000002400')
READ_STAGE = bytes.fromhex('fd0701c033d80020ffffffffffffffff')
OPERATIONS = ((INQUIRY, b'', 36), (READ_STAGE, b'', 32))
MAX_SNAPSHOT_AGE = 120
LIVE_SECONDS = 10
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


def decode_stage(data):
    """Exactly one 32-byte MengLi transfer, seed FFFFFFFF; never auto-detect."""
    if type(data) is not bytes or len(data) != 32:
        raise ValueError('Exactly 32 raw bytes required')
    magic = bytes.fromhex('c3cfc0e8ced2b0aec4e3a3acd3f1c1d6')
    crc = binascii.crc_hqx(b'\xff\xff', 0xffff)
    out = bytearray()
    for index, byte in enumerate(data):
        crc = binascii.crc_hqx(magic[index % len(magic):index % len(magic) + 1], crc)
        out.append(byte ^ (crc & 255))
    return bytes(out)


def interpret_stage(decoded):
    if type(decoded) is not bytes or len(decoded) != 32:
        raise ValueError('Exactly 32 decoded bytes required')
    names = ('stage', 'result', 'sys_hz', 'lsb_hz', 'raw_write', 'elapsed_ms',
             'heartbeat', 'recovery_result')
    fields = dict(zip(names, struct.unpack('<IiiiIIIi', decoded)))
    coherent = (fields['stage'] in (6, 7) and fields['result'] == 0 and
        24000000 <= fields['sys_hz'] <= 480000000 and
        0 < fields['lsb_hz'] <= 60000000 and fields['raw_write'] == 0x02002d82 and
        fields['elapsed_ms'] >= 20000 and fields['heartbeat'] != 0 and
        fields['recovery_result'] == (0 if fields['stage'] == 6 else 1))
    return dict(fields=fields,
        classification='conditional-diagnostic-execution-evidence' if coherent else 'inconclusive',
        codec='wl82-reported-mengli-one-transfer-seed-ffffffff',
        retention_verified=False, rom_handler_verified=False, display_observed=False,
        recovery_cause_verified=False, physical_recovery_verified=False)


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

    def check(self):
        if self not in _AUTHORIZED:
            raise ValueError('Exact prepared stage-probe instance required')
        for path, data, limit in self.evidence:
            if read_file(path, limit) != data:
                raise ValueError('Frozen stage-probe evidence changed')
        for policy in self.policies:
            policy.check_files()
        observed = json.loads(self.snapshot)['observed_at']
        if not 0 <= time.time() - observed <= MAX_SNAPSHOT_AGE:
            raise ValueError('Post-boot ROM snapshot became stale')


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
        'rom_snapshot_path', 'rom_snapshot_sha256', 'active_session_state', 'receipt_path'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != 'fm1-exact-diagnostic-stage-probe' or
            type(c['target_boot_exit_status']) is not int or c['target_boot_exit_status'] != 0 or
            c['active_session_state'] != 'post-target-boot-rom-no-later-commands-no-loader-upload'):
        raise ValueError('Exact initial-ROM stage-probe policy required')
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
    marker = parent/('.diagnostic-stage-'+c['target_boot_campaign_sha256']+'.consumed')
    if (not destination.is_absolute() or destination.parent != parent or destination.exists() or
            marker.exists() or not stat.S_ISDIR(parent.lstat().st_mode) or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New private probe receipt and unconsumed target boot required')
    prepared = Prepared(canonical(c),digest(raw),canonical(snapshot),tuple(evidence),policies)
    _AUTHORIZED.add(prepared); prepared.check()
    return prepared


@dataclass(frozen=True)
class Completion:
    data: bytes
    status: int = 0
    masked: int = 0
    msg: int = 0
    host: int = 0
    driver: int = 0
    resid: int = 0
    info: int = 0
    sense_len: int = 0
    sense: bytes = b''


class ProbeSession:
    """Trusted injected transport: binding(), exchange(cdb,out,in_len), close().

    binding returns usb_binding, sg_binding, fd_identity, fd_mode. A concrete
    SG opener is a separate review gate; this class never discovers or opens SG.
    Every exchange requires binding on both sides and source/evidence rechecks.
    """
    def __init__(self, prepared, transport, log):
        if not isinstance(prepared, Prepared):
            raise ValueError('Exact prepared probe required')
        self.prepared,self.transport,self.log = prepared,transport,log
        self.next,self.failed,self.closed = 0,False,False
        self.started = time.monotonic()
        self.close_error = None
        try:
            self.binding()
        except BaseException:
            self.failed=True; self.close(); raise

    def close(self):
        if not self.closed:
            self.closed=True
            try:
                self.transport.close()
            except BaseException as exc:
                self.failed=True; self.close_error=exc; raise
        if self.close_error is not None:
            raise self.close_error

    def binding(self):
        self.prepared.check()
        if self.closed or not 0 <= time.monotonic()-self.started <= LIVE_SECONDS:
            raise ValueError('Closed or stale probe window')
        actual = self.transport.binding()
        snapshot = json.loads(self.prepared.snapshot)
        if (set(actual) != {'usb_binding','sg_binding','fd_identity','fd_mode'} or
                canonical(actual['usb_binding']) != canonical(snapshot['usb_binding']) or
                canonical(actual['sg_binding']) != canonical(snapshot['sg_binding']) or
                canonical(actual['fd_identity']) != canonical(snapshot['sg_binding']['node_identity']) or
                type(actual['fd_mode']) is not int or not stat.S_ISCHR(actual['fd_mode'])):
            raise ValueError('Opened SG/USB/sysfs identity changed')

    def exchange(self, cdb, payload=b'', in_len=None):
        try:
            if self.failed or self.closed or self.next >= 2:
                raise ValueError('Closed, failed, or consumed probe')
            index=self.next; self.next+=1
            wanted=OPERATIONS[index]
            if type(cdb) is not bytes or type(payload) is not bytes or type(in_len) is not int or (cdb,payload,in_len)!=wanted:
                raise ValueError('Only exact ordered probe requests permitted')
            self.log('sg_submit_intent',index=index,cdb=cdb.hex(),out_len=0,in_len=in_len,retry=False)
            self.binding()  # Includes durable-intent-to-exchange source recheck.
            reply=self.transport.exchange(cdb,payload,in_len)
            self.binding()
            if not isinstance(reply,Completion):
                raise ValueError('Structured SG completion required')
            fields={name:getattr(reply,name) for name in ('status','masked','msg','host','driver','resid','info','sense_len')}
            self.log('sg_completion',index=index,**fields,sense_hex=reply.sense.hex(),
                response_sha256=digest(reply.data),retry=False)
            if (any(type(v) is not int or v!=0 for v in fields.values()) or
                    type(reply.sense) is not bytes or reply.sense or type(reply.data) is not bytes or len(reply.data)!=in_len):
                raise OSError('Incomplete or unsuccessful SG completion')
            if index==0 and (reply.data[8:16].strip()!=b'WL82' or reply.data[16:32].strip()!=b'UBOOT1.00'):
                raise ValueError('Initial-ROM inquiry differs')
            return reply.data
        except BaseException:
            self.failed=True; self.close(); raise


def sync_dir(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)


def private_file(path, mode='wb'):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try: return os.fdopen(fd,mode)
    except BaseException: os.close(fd); raise


def run_campaign(prepared, transport_factory):
    """Injected-only one-use run. Caller factory is trusted Python, not sandboxed."""
    if not isinstance(prepared,Prepared): raise ValueError('Exact prepared probe required')
    prepared.check()
    c=json.loads(prepared.campaign); receipt=Path(c['receipt_path'])
    receipt.mkdir(mode=0o700,exist_ok=False); sync_dir(receipt.parent)
    marker=receipt.parent/('.diagnostic-stage-'+c['target_boot_campaign_sha256']+'.consumed')
    with private_file(marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii')); fp.flush(); os.fsync(fp.fileno())
    sync_dir(receipt.parent)
    prepared.check()
    with private_file(receipt/'commands.jsonl','w') as events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush(); os.fsync(events.fileno()); sync_dir(receipt)
        session=None
        try:
            log('stage_probe_prepared',campaign_sha256=prepared.campaign_sha256,
                target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
                rom_snapshot_sha256=c['rom_snapshot_sha256'],target_sha256=TARGET_SHA,
                app_sha256=APP_SHA,elf_sha256=ELF_SHA,commands=2,upload_operations=0,
                flash_operations=0,reset_operations=0,kernel_exclusivity=False)
            prepared.check()
            session=ProbeSession(prepared,transport_factory(prepared),log)
            inquiry=session.exchange(INQUIRY,in_len=36)
            raw=session.exchange(READ_STAGE,in_len=32)
            session.close()  # No publication after even a swallowed close failure.
            decoded=decode_stage(raw)
            result=dict(campaign_sha256=prepared.campaign_sha256,raw_sha256=digest(raw),
                decoded_sha256=digest(decoded),inquiry_sha256=digest(inquiry),
                **interpret_stage(decoded))
            for name,data in (('raw.bin',raw),('decoded.bin',decoded)):
                with private_file(receipt/name) as fp:
                    fp.write(data); fp.flush(); os.fsync(fp.fileno())
            sync_dir(receipt)
            log('stage_capture_completed',**result,retry=False)
            with private_file(receipt/'.result.json.pending') as fp:
                fp.write(canonical(result));fp.flush();os.fsync(fp.fileno())
            os.link(receipt/'.result.json.pending',receipt/'result.json',follow_symlinks=False)
            (receipt/'.result.json.pending').unlink();sync_dir(receipt)
            return result
        except BaseException as exc:
            # Result publication is invalid if any durability/cleanup step fails.
            try:
                (receipt/'result.json').unlink(missing_ok=True);sync_dir(receipt)
                log('stage_probe_stopped_ambiguous',error=type(exc).__name__,retry=False,
                    classification='inconclusive',display_observed=False,physical_recovery_verified=False)
            except BaseException: pass
            raise
        finally:
            if session is not None: session.close()

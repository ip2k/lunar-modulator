"""MIT. Separate detached-reset proof and injected exact diagnostic BSS probe.

Own first-party mechanics retained from the frozen ff593 successful policy.
No successful reset transcript is synthesized or substituted. Historical
ReturnedProof validates evidence only; it grants no transport authority.

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
import re
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
_PROOFS = WeakSet()
SUCCESSFUL_PROBE_SHA = 'ff5938530de5b9ca62c2361bfad024d64073168bc4c3bfedb77ea7c9eca56007'
SUCCESSFUL_NATIVE_SHA = '13d7c647724cffb06876ca5e996f50f7a3844b2b39f961bf5a5c0404c3da32ef'
BOOT_CAMPAIGN_SHA = "6d7bf62825b117dd21537499bc4dfd41d397c98d804f59c205863d3d6d862778"
BOOT_WRAPPER_SHA = "ce7129a4ab980f8f41915b865993f42e83c26d5e5cb56a21b728d281c2f54e85"


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


def verify_detached_boot(raw, c, boot_sha, manifest_sha, install_completed):
    """Exactly actual prepared/intent/terminal-stop; no command completion claim."""
    events=[json.loads(line) for line in raw.decode('utf8').splitlines()]
    if len(events)!=3:raise ValueError('Exactly three detached reset events required')
    # Reuse the source-backed first two successful-policy predicates, with an
    # independent terminal schema. Never pass synthetic bytes to verify_boot.
    first=dict(event='target_reset_prepared',campaign_sha256=boot_sha,
        install_campaign_sha256=c['install_campaign_sha256'],install_commands_sha256=c['install_commands_sha256'],
        target_sha256=TARGET_SHA,target_boot_authorization='exact-sdk-display-diagnostic',
        backup_manifest_sha256=manifest_sha,adapter_sha256=TARGET_RESET_SHA,commands=1,
        flash_operations=0,upload_operations=0,kernel_exclusivity=False,boot_observed=False,
        display_observed=False,physical_recovery_verified=False)
    second=dict(event='reset_submit_intent',phase='installed-fixed-loader',
        cdb='fc0c00000001ffffffffffffffffffff',in_len=16,out_len=0,retry=False,boot_observed=False)
    for event,wanted in zip(events,(first,second)):
        value=dict(event);value.pop('time',None)
        if canonical(value)!=canonical(wanted):raise ValueError('Detached reset preparation/intent differs')
    terminal=dict(events[-1]);terminal.pop('time',None)
    if (set(terminal)!={'event','error','detail','retry','core_reset_observed','boot_observed',
            'display_observed','physical_recovery_verified'} or
            terminal['event']!='reset_stopped_ambiguous' or terminal['error']!='ValueError' or
            terminal['detail']!='Exactly one SG device on pinned topology required' or
            any(terminal[k] is not False for k in ('retry','core_reset_observed','boot_observed',
                'display_observed','physical_recovery_verified'))):
        raise ValueError('Only exact detached discovery-stop envelope admitted')
    times=[e.get('time') for e in events]
    if (not all(finite_time(t) for t in times) or times!=sorted(times) or
            times[0]<install_completed or times[-1]>time.time()):
        raise ValueError('Detached reset chronology differs')
    return times[-1]


def verify_wire(raw, usb, new_usb):
    """Strict text USBmon BOT witness: complete CBW then terminal disconnect.

    Kernel TUR/REQUEST SENSE/INQUIRY before reset/new ROM are permitted only
    in their exact standard shapes. No later vendor CBW is admitted. Other
    devices on the captured bus do not grant authority and are ignored.
    """
    records=[]
    for line in raw.decode('ascii').splitlines():
        parts=line.split()
        if len(parts)<6 or parts[2] not in ('S','C'):continue
        address=parts[3].split(':')
        if len(address)!=4 or address[0] not in ('Bo','Bi'):continue
        if address[1]!=usb['busnum'] or int(address[2]) not in (int(usb['devnum']),int(new_usb['devnum'])):continue
        try:status,length=int(parts[4]),int(parts[5])
        except ValueError:raise ValueError('Malformed relevant USBmon transfer')
        data=b''
        if len(parts)>6 and parts[6]=='=':
            try:data=bytes.fromhex(''.join(parts[7:]))
            except ValueError:raise ValueError('Malformed USBmon data')
        records.append((parts[0],parts[2],address[0],int(address[2]),int(address[3]),status,length,data))
    resets=[]
    for index,r in enumerate(records):
        token,action,direction,dev,ep,status,length,data=r
        if action!='S' or direction!='Bo':continue
        if length!=31 or len(data)!=31 or data[:4]!=b'USBC':raise ValueError('Unexpected outbound transfer')
        cdb=data[15:];n=data[14]
        if cdb==bytes.fromhex('fc0c00000001ffffffffffffffffffff'):
            if dev!=int(usb['devnum']) or data[8:15]!=bytes.fromhex('10000000800010') or ep!=1:
                raise ValueError('Reset CBW direction/geometry differs')
            resets.append(index)
        else:
            # Exact standard BOT control forms, no payload OUT.
            allowed=(n==6 and data[13]==0 and cdb in
                (bytes.fromhex('000000000000')+bytes(10),
                 bytes.fromhex('030000001200')+bytes(10),
                 bytes.fromhex('120000002400')+bytes(10)))
            expected=(0,0) if cdb[0]==0 else ((18,128) if cdb[0]==3 else (36,128))
            if not allowed or (int.from_bytes(data[8:12],'little'),data[12])!=expected:
                raise ValueError('Nonallowlisted CBW in owned capture')
            if resets and dev==int(usb['devnum']):raise ValueError('Later command on reset device')
    if len(resets)!=1:raise ValueError('Exactly one reset CBW required')
    i=resets[0];request=records[i]
    relevant=[r for r in records[i+1:] if r[3]==int(usb['devnum'])]
    if len(relevant)!=3:raise ValueError('Exact transmitted/detached reset tail required')
    out,inp,end=relevant
    if (out[:5]!=(request[0],'C','Bo',request[3],1) or out[5:7]!=(0,31) or out[7] or
            inp[1:7]!=('S','Bi',request[3],1,-115,16) or inp[7] or
            end[:5]!=(inp[0],'C','Bi',request[3],1) or end[5:7]!=(-108,0) or end[7]):
        raise ValueError('Reset transfer not transmitted then disconnected without reply')
    return dict(reset_cbw_transmitted=True,reset_request_completed=False,
        reset_core_observed=False,no_later_vendor_cbw=True)


def verify_wrapper(c,boot,freeze,boot_done):
    run=Path(c['target_boot_campaign_path']).parent
    names={'execute-once.py','wrapper-attempt.json','capture-open.json','capture-stop.json',
        'execution-exit.json','execution.stdout','usbmon3.txt','usbmon3.stderr','rom-observations.json'}
    pins=c['wrapper_files_sha256']
    if type(pins) is not dict or set(pins)!=names or pins['execute-once.py']!=BOOT_WRAPPER_SHA:
        raise ValueError('Exact owned target-reset wrapper evidence required')
    files={name:freeze(run/name,sha,32*1048576 if name=='usbmon3.txt' else 2*1048576) for name,sha in pins.items()}
    for name in ('wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'):
        if (run/name).exists():raise ValueError('Wrapper capture lifecycle ambiguous')
    attempt=json.loads(files['wrapper-attempt.json'])
    if (set(attempt)!={'time','campaign_sha256','adapter_sha256','retry'} or
            attempt['campaign_sha256']!=BOOT_CAMPAIGN_SHA or attempt['adapter_sha256']!=TARGET_RESET_SHA or
            attempt['retry'] is not False or not finite_time(attempt['time']) or attempt['time']>boot_done or
            files['usbmon3.stderr']):raise ValueError('Owned wrapper attempt/capture differs')
    exit_record=json.loads(files['execution-exit.json'])
    if (set(exit_record)!={'time','exit_status','campaign_sha256','capture_alive_after_child','retry'} or
            type(exit_record['exit_status']) is not int or exit_record['exit_status']!=1 or
            exit_record['campaign_sha256']!=BOOT_CAMPAIGN_SHA or
            exit_record['capture_alive_after_child'] is not True or exit_record['retry'] is not False or
            not finite_time(exit_record['time']) or exit_record['time']<boot_done):
        raise ValueError('Exact stopped child and live owned capture required')
    opened=json.loads(files['capture-open.json']);stopped=json.loads(files['capture-stop.json'])
    if (set(opened)!={'time','timeout_pid','cat_pid','process_group','open_capture_fd'} or
            set(stopped)!={'time','process_group','returncode','owned_processes_only'} or
            any(type(opened[k]) is not int or opened[k]<=0 for k in ('timeout_pid','cat_pid','process_group')) or
            opened['timeout_pid']!=opened['process_group'] or opened['cat_pid']==opened['timeout_pid'] or
            opened['open_capture_fd'] is not True or stopped['owned_processes_only'] is not True or
            stopped['process_group']!=opened['process_group'] or type(stopped['returncode']) is not int or
            stopped['returncode']!=-15 or not finite_time(opened['time']) or not finite_time(stopped['time']) or
            not opened['time']<=boot_done<=exit_record['time']<=stopped['time']<=time.time()):
        raise ValueError('Exact owned capture lifecycle required')
    snap=json.loads(freeze(c['rom_snapshot_path'],c['rom_snapshot_sha256'],65536))
    if Path(c['rom_snapshot_path'])!=run/'rom-snapshot.json':raise ValueError('Original passive snapshot required')
    if not exit_record['time']<=snap['observed_at']<=stopped['time']:raise ValueError('ROM observation chronology differs')
    observations=json.loads(files['rom-observations.json'])
    if (set(observations)!={'time','found','observations','passive_sysfs_only','no_later_device_commands'} or
            observations['found'] is not True or observations['passive_sysfs_only'] is not True or
            observations['no_later_device_commands'] is not True or type(observations['observations']) is not list or
            not finite_time(observations['time']) or not snap['observed_at']<=observations['time']<=stopped['time'] or
            not any(type(o) is dict and set(o)=={'time','usb_binding'} and
                finite_time(o['time']) and exit_record['time']<=o['time']<=snap['observed_at'] and
                canonical(o['usb_binding'])==canonical(snap['usb_binding']) for o in observations['observations'])):
        raise ValueError('Original passive ROM observations required')
    verify_wire(files['usbmon3.txt'],boot['usb_binding'],snap['usb_binding'])


@dataclass(frozen=True,eq=False)
class ReturnedProof:
    snapshot: bytes
    original_inputs: bytes
    manifest_sha256: str
    private_parent: str
    evidence: tuple
    policies: tuple
    reset_terminal_time: float
    original_rehearsal_campaign_sha256: str
    install_journal_sha256: str
    probe_outcome: str
    absent: tuple

    def check(self):
        if self not in _PROOFS:raise ValueError('Exact evidence-only proof required')
        for path,data,limit in self.evidence:
            if read_file(path,limit)!=data:raise ValueError('Returned-state evidence changed')
        for path in self.absent:
            if os.path.lexists(path):raise ValueError('Previously absent probe evidence appeared')
        for policy in self.policies:policy.check_files()


def validate_returned_state(path, *, evaluated_at=None, completed_probe=None,
                            probe_capture=None, provenance_mode='detached', install_journal_path=None,
                            probe_wrapper_sha256=None):
    """Evidence only. Fresh initial admission is evaluated historically once.

    The optional preserved journal must be the exact original completed-install
    bytes pinned by the boot campaign. It never substitutes for live journal
    checks in an opener. A consumed failed probe requires its actual stopped
    transcript and owned read-only capture; it grants no retry or success claim.
    Successful mode reads the unchanged ff593 schema, with no new admission API.
    """
    return _prepare(path, admission=False,
        evaluated_at=time.time() if evaluated_at is None else evaluated_at,
        completed_probe=completed_probe, probe_capture=probe_capture,
        provenance_mode=provenance_mode, install_journal_path=install_journal_path,
        probe_wrapper_sha256=probe_wrapper_sha256)


def prepare_campaign(path):
    return _prepare(path, admission=True, evaluated_at=time.time(), completed_probe=None)


def verify_completed_probe(path,c,snapshot,parent,freeze,mode):
    raw=freeze(Path(path),limit=65536);probe=json.loads(raw)
    if probe!=c:raise ValueError('Exact original probe campaign required')
    marker=parent/('.diagnostic-stage-'+c['target_boot_campaign_sha256']+'.consumed')
    if freeze(marker,limit=256)!=digest(raw).encode('ascii'):raise ValueError('Original consumed probe required')
    receipt=Path(c['receipt_path'])
    data=freeze(receipt/'raw.bin',limit=32);decoded=freeze(receipt/'decoded.bin',limit=32)
    if decode_stage(data)!=decoded:raise ValueError('Probe codec evidence differs')
    result=json.loads(freeze(receipt/'result.json',limit=65536))
    expected=dict(campaign_sha256=digest(raw),raw_sha256=digest(data),decoded_sha256=digest(decoded),
        inquiry_sha256=result.get('inquiry_sha256'),**interpret_stage(decoded))
    if mode=='detached':
        expected.update(target_reset_outcome='transmitted-detached-not-completed',reset_request_completed=False)
    if canonical(result)!=canonical(expected):raise ValueError('Probe result differs')
    events=[json.loads(line) for line in freeze(receipt/'commands.jsonl',limit=65536).splitlines()]
    if len(events)!=6 or [e.get('event') for e in events]!=['stage_probe_prepared','sg_submit_intent',
        'sg_completion','sg_submit_intent','sg_completion','stage_capture_completed']:
        raise ValueError('Exactly completed two-read probe required')
    for index,(cdb,_,length) in enumerate(OPERATIONS):
        intent=dict(events[1+index*2]);intent.pop('time',None)
        if intent!=dict(event='sg_submit_intent',index=index,cdb=cdb.hex(),out_len=0,in_len=length,retry=False):
            raise ValueError('Probe request differs')
        completion=dict(events[2+index*2]);completion.pop('time',None)
        wanted=dict(event='sg_completion',index=index,status=0,masked=0,msg=0,host=0,driver=0,
            resid=0,info=0,sense_len=0,sense_hex='',retry=False,
            response_sha256=result['inquiry_sha256'] if index==0 else digest(data))
        if canonical(completion)!=canonical(wanted):raise ValueError('Probe completion differs')
    first=dict(events[0]);first.pop('time',None)
    wanted=dict(event='stage_probe_prepared',campaign_sha256=digest(raw),target_boot_campaign_sha256=c['target_boot_campaign_sha256'],
        rom_snapshot_sha256=c['rom_snapshot_sha256'],target_sha256=TARGET_SHA,app_sha256=APP_SHA,elf_sha256=ELF_SHA,
        commands=2,upload_operations=0,flash_operations=0,reset_operations=0,kernel_exclusivity=False)
    last=dict(events[-1]);last.pop('time',None)
    if canonical(first)!=canonical(wanted) or canonical(last)!=canonical(dict(event='stage_capture_completed',**result,retry=False)):
        raise ValueError('Probe envelope differs')
    times=[e.get('time') for e in events]
    if not all(finite_time(t) for t in times) or times!=sorted(times) or not snapshot['observed_at']<=times[0]<=times[-1]<=time.time():
        raise ValueError('Probe chronology differs')


def verify_probe_readonly_wire(raw, usb, intents, zero_commands=False):
    """Owned BOT capture inventory, never a proof of ROM handler or retention.

    Standard kernel commands are permitted. FD07 must be the exact 32-byte
    request and can occur at most once, after its durable intent. No other
    outbound payload, reset, upload, NOR, vendor CDB or retry is accepted.
    """
    fd07=0
    for line in raw.decode('ascii').splitlines():
        parts=line.split()
        if len(parts)<6 or parts[2]!='S':continue
        address=parts[3].split(':')
        if len(address)!=4 or address[0]!='Bo' or address[1]!=usb['busnum'] or int(address[2])!=int(usb['devnum']):continue
        if zero_commands:raise ValueError('Pre-open stop capture contains an outbound command')
        if address[3]!='1':raise ValueError('Probe capture endpoint differs')
        try:
            data=bytes.fromhex(''.join(parts[7:])) if len(parts)>6 and parts[6]=='=' else b''
            length=int(parts[5])
        except ValueError:raise ValueError('Malformed probe capture')
        if length!=31 or len(data)!=31 or data[:4]!=b'USBC' or data[13]!=0:
            raise ValueError('Non-CBW outbound probe transfer')
        cdb=data[15:];n=data[14];geometry=(int.from_bytes(data[8:12],'little'),data[12])
        if cdb==READ_STAGE:
            fd07+=1
            if n!=16 or geometry!=(32,128) or fd07>1 or intents<2:
                raise ValueError('Unintended or repeated stage read')
        else:
            forms={bytes(16):(0,0),bytes.fromhex('030000001200')+bytes(10):(18,128),
                   INQUIRY+bytes(10):(36,128)}
            if n!=6 or cdb not in forms or geometry!=forms[cdb]:
                raise ValueError('Nonallowlisted command in probe capture')
            if intents==0 and cdb==INQUIRY+bytes(10):
                raise ValueError('Zero-intent stop has ambiguous inquiry submission')
    return fd07


def verify_stopped_probe(path,c,snapshot,parent,freeze,capture_path,mode,wrapper_sha):
    raw=freeze(Path(path),limit=65536)
    if json.loads(raw)!=c:raise ValueError('Original stopped probe campaign required')
    marker=parent/('.diagnostic-stage-'+c['target_boot_campaign_sha256']+'.consumed')
    if freeze(marker,limit=256)!=digest(raw).encode('ascii'):raise ValueError('Original consumed probe marker required')
    receipt=Path(c['receipt_path'])
    if os.path.lexists(receipt/'result.json'):raise ValueError('Stopped probe has a published result')
    log_path=receipt/'commands.jsonl'
    log_raw=freeze(log_path,limit=65536) if os.path.lexists(log_path) else b''
    events=[json.loads(line) for line in log_raw.splitlines()]
    times=[];intents=0
    if not events and any(os.path.lexists(receipt/name) for name in ('raw.bin','decoded.bin','.result.json.pending')):
        raise ValueError('Pre-open stop contains later publication artifacts')
    if events:
        if not 2<=len(events)<=7:raise ValueError('Bounded stopped probe transcript required')
        wanted=dict(event='stage_probe_prepared',campaign_sha256=digest(raw),
            target_boot_campaign_sha256=c['target_boot_campaign_sha256'],rom_snapshot_sha256=c['rom_snapshot_sha256'],
            target_sha256=TARGET_SHA,app_sha256=APP_SHA,elf_sha256=ELF_SHA,commands=2,
            upload_operations=0,flash_operations=0,reset_operations=0,kernel_exclusivity=False)
        first=dict(events[0]);first.pop('time',None)
        terminal=dict(events[-1]);terminal.pop('time',None)
        if canonical(first)!=canonical(wanted) or set(terminal)!={'event','error','retry','classification','display_observed','physical_recovery_verified'} or (
                terminal['event']!='stage_probe_stopped_ambiguous' or type(terminal['error']) is not str or
                not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,127}',terminal['error']) or
                terminal['retry'] is not False or terminal['classification']!='inconclusive' or
                terminal['display_observed'] is not False or terminal['physical_recovery_verified'] is not False):
            raise ValueError('Exact inconclusive stop envelope required')
        times=[e.get('time') for e in events]
        if not all(finite_time(t) for t in times) or times!=sorted(times) or not snapshot['observed_at']<=times[0]<=times[-1]<=time.time():
            raise ValueError('Stopped probe chronology differs')
        middle=events[1:-1];position=0;intents=0
        for index,(cdb,_,length) in enumerate(OPERATIONS):
            if position==len(middle):break
            intent=dict(middle[position]);intent.pop('time',None)
            if intent!=dict(event='sg_submit_intent',index=index,cdb=cdb.hex(),out_len=0,in_len=length,retry=False):
                raise ValueError('Stopped probe request/order differs')
            position+=1;intents+=1
            if position==len(middle):break
            completion=dict(middle[position]);completion.pop('time',None)
            keys={'event','index','status','masked','msg','host','driver','resid','info','sense_len','sense_hex','response_sha256','retry'}
            if (set(completion)!=keys or completion['event']!='sg_completion' or type(completion['index']) is not int or completion['index']!=index or
                    completion['retry'] is not False or any(type(completion[k]) is not int or not -2**31<=completion[k]<2**32 for k in
                        ('status','masked','msg','host','driver','resid','info')) or
                    type(completion['sense_len']) is not int or not 0<=completion['sense_len']<=255 or
                    type(completion['sense_hex']) is not str or not re.fullmatch(r'[0-9a-f]*',completion['sense_hex']) or
                    len(completion['sense_hex'])!=2*min(completion['sense_len'],32) or
                    type(completion['response_sha256']) is not str or not re.fullmatch(r'[0-9a-f]{64}',completion['response_sha256'])):
                raise ValueError('Actual structured completion required')
            position+=1
            good=all(completion[k]==0 for k in ('status','masked','msg','host','driver','resid','info','sense_len')) and completion['sense_hex']==''
            if not good and position<len(middle):raise ValueError('No next request after failed completion')
        if position<len(middle):
            captured=dict(middle[position]);captured.pop('time',None)
            if position!=4 or captured.get('event')!='stage_capture_completed' or captured.get('retry') is not False:
                raise ValueError('Extra stopped probe event')
            data=freeze(receipt/'raw.bin',limit=32);decoded=freeze(receipt/'decoded.bin',limit=32)
            result=dict(campaign_sha256=digest(raw),raw_sha256=digest(data),decoded_sha256=digest(decoded),
                        inquiry_sha256=middle[1]['response_sha256'],**interpret_stage(decoded))
            if mode=='detached':result.update(target_reset_outcome='transmitted-detached-not-completed',reset_request_completed=False)
            if (digest(data)!=middle[3]['response_sha256'] or decode_stage(data)!=decoded or
                    captured!=dict(event='stage_capture_completed',**result,retry=False)):
                raise ValueError('Unpublished decoded evidence differs')
            position+=1
        if position!=len(middle):raise ValueError('Probe transcript has later commands')
    envelope=json.loads(freeze(Path(capture_path),limit=65536))
    if (set(envelope)!={'schema','kind','native_campaign_path','native_campaign_sha256','wrapper_files_sha256'} or
            type(envelope['schema']) is not int or envelope['schema']!=1 or envelope['kind']!='fm1-owned-stopped-stage-probe-capture'):
        raise ValueError('Owned stopped probe capture envelope required')
    native_path=Path(envelope['native_campaign_path']);run=native_path.parent
    native=json.loads(freeze(native_path,envelope['native_campaign_sha256'],65536))
    if (set(native)!={'schema','kind','adapter_sha256','probe_campaign_path','probe_campaign_sha256'} or
            type(native['schema']) is not int or native['schema']!=1 or
            native['kind']!=('fm1-exact-native-detached-diagnostic-stage-probe' if mode=='detached' else 'fm1-exact-native-diagnostic-stage-probe') or
            Path(native['probe_campaign_path'])!=Path(path) or native['probe_campaign_sha256']!=digest(raw)):
        raise ValueError('Original native probe envelope differs')
    root=Path(__file__).absolute().parent
    freeze(root/('fm1_diagnostic_detached_sg.py' if mode=='detached' else 'fm1_diagnostic_stage_sg.py'),
           native['adapter_sha256'] if mode=='detached' else SUCCESSFUL_NATIVE_SHA)
    if mode=='successful' and native['adapter_sha256']!=SUCCESSFUL_NATIVE_SHA:raise ValueError('Original native source differs')
    pins=envelope['wrapper_files_sha256']
    names={'execute-once.py','wrapper-attempt.json','preflight.json','capture-open.json','capture-stop.json',
           'execution-exit.json','execution.stdout','usbmon3.txt','usbmon3.stderr'}
    if (type(pins) is not dict or set(pins)!=names or type(wrapper_sha) is not str or
            not re.fullmatch(r'[0-9a-f]{64}',wrapper_sha) or pins['execute-once.py']!=wrapper_sha):
        raise ValueError('Caller-pinned reviewed probe wrapper capture required')
    files={name:freeze(run/name,sha,32*1048576 if name=='usbmon3.txt' else 2*1048576) for name,sha in pins.items()}
    for name in ('wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'):
        if os.path.lexists(run/name):raise ValueError('Owned probe capture lifecycle ambiguous')
    attempt=json.loads(files['wrapper-attempt.json']);preflight=json.loads(files['preflight.json'])
    attempt_wanted=dict(target_boot_campaign_sha256=c['target_boot_campaign_sha256'],adapter_sha256=native['adapter_sha256'],probe_sha256=c['adapter_sha256'],retry=False)
    if mode=='detached':attempt_wanted['transmitted_detached_only']=True
    else:attempt_wanted['successful_reset_only']=True
    without_time=dict(attempt);without_time.pop('time',None)
    if canonical(without_time)!=canonical(attempt_wanted) or not finite_time(attempt.get('time')):
        raise ValueError('Owned probe wrapper attempt differs')
    if (set(preflight)!={'time','factory_seconds','campaign_sha256','rom_snapshot_sha256','snapshot_age_seconds','hardware_access'} or
            not finite_time(preflight['time']) or not finite_time(preflight['factory_seconds']) or preflight['factory_seconds']<0 or
            preflight['campaign_sha256']!=envelope['native_campaign_sha256'] or preflight['rom_snapshot_sha256']!=c['rom_snapshot_sha256'] or
            not finite_time(preflight['snapshot_age_seconds']) or not 0<=preflight['snapshot_age_seconds']<=MAX_SNAPSHOT_AGE or preflight['hardware_access'] is not False or
            not 0<=preflight['time']-snapshot['observed_at']<=MAX_SNAPSHOT_AGE):raise ValueError('Original fresh preflight required')
    opened=json.loads(files['capture-open.json']);stopped=json.loads(files['capture-stop.json']);exit_record=json.loads(files['execution-exit.json'])
    if (set(opened)!={'time','timeout_pid','cat_pid','process_group','open_capture_fd'} or
            set(stopped)!={'time','process_group','returncode','owned_processes_only'} or
            set(exit_record)!={'time','exit_status','campaign_sha256','capture_alive_after_child','retry','display_observed','physical_recovery_verified'} or
            any(type(opened[k]) is not int or opened[k]<=0 for k in ('timeout_pid','cat_pid','process_group')) or
            opened['timeout_pid']!=opened['process_group'] or opened['cat_pid']==opened['timeout_pid'] or opened['open_capture_fd'] is not True or
            stopped['owned_processes_only'] is not True or stopped['process_group']!=opened['process_group'] or type(stopped['returncode']) is not int or stopped['returncode']!=-15 or
            type(exit_record['exit_status']) is not int or exit_record['exit_status']==0 or exit_record['campaign_sha256']!=envelope['native_campaign_sha256'] or
            exit_record['capture_alive_after_child'] is not True or any(exit_record[k] is not False for k in ('retry','display_observed','physical_recovery_verified')) or
            not all(finite_time(x) for x in (opened['time'],stopped['time'],exit_record['time'])) or
            not attempt['time']<=preflight['time']<=opened['time']<=exit_record['time']<=stopped['time']<=time.time() or
            (times and not opened['time']<=times[0]<=times[-1]<=exit_record['time']) or files['usbmon3.stderr']):
        raise ValueError('Owned stopped probe lifecycle differs')
    verify_probe_readonly_wire(files['usbmon3.txt'],snapshot['usb_binding'],intents,zero_commands=not events)
    return 'stopped-read-only-probe-inconclusive' if events else 'pre-open-zero-command-stop'


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


def _prepare(path, *, admission, evaluated_at, completed_probe, probe_capture=None,
             provenance_mode='detached', install_journal_path=None, probe_wrapper_sha256=None):
    """Offline file validation only. No discovery, SG open, or injected call."""
    if provenance_mode not in ('detached','successful') or (admission and
            (provenance_mode!='detached' or probe_capture is not None or install_journal_path is not None)):
        raise ValueError('Only distinct detached opener admission permitted')
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
        'rom_snapshot_path', 'rom_snapshot_sha256', 'active_session_state', 'receipt_path',
        'reset_outcome', 'wrapper_files_sha256'}
    if provenance_mode=='successful':keys-= {'reset_outcome','wrapper_files_sha256'}
    if (set(c) != keys or type(c['schema']) is not int or c['schema'] != 1 or
            c['kind'] != ('fm1-exact-detached-diagnostic-stage-probe' if provenance_mode=='detached' else 'fm1-exact-diagnostic-stage-probe') or
            type(c['target_boot_exit_status']) is not int or c['target_boot_exit_status'] != (1 if provenance_mode=='detached' else 0) or
            (provenance_mode=='detached' and c['reset_outcome'] != 'transmitted-detached-not-completed') or
            c['target_boot_campaign_sha256'] != BOOT_CAMPAIGN_SHA or
            c['active_session_state'] != 'post-target-boot-rom-no-later-commands-no-loader-upload'):
        raise ValueError('Exact initial-ROM stage-probe policy required')
    root = Path(__file__).absolute().parent
    freeze(Path(__file__).absolute(), c['adapter_sha256'] if provenance_mode=='detached' else None)
    if provenance_mode=='successful':freeze(root/'fm1_diagnostic_stage_probe.py',SUCCESSFUL_PROBE_SHA)
    if provenance_mode=='successful' and c['adapter_sha256']!=SUCCESSFUL_PROBE_SHA:
        raise ValueError('Original successful source required')
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
    original_journal=freeze(Path(inputs['directory'])/'journal.json' if install_journal_path is None
        else Path(install_journal_path),boot['journal_sha256'],65536)
    if install_journal_path is not None:
        journal=json.loads(original_journal)
        if (journal.get('schema')!=1 or journal.get('plan_sha256')!=modules['fm1_flash_transaction'].digest(modules['fm1_flash_transaction'].encoded(plan)) or
                journal.get('record_sha256')!=modules['fm1_flash_transaction'].digest(modules['fm1_flash_transaction'].encoded(
                    {k:v for k,v in journal.items() if k!='record_sha256'})) or journal.get('sector_order')!=plan['sector_order']):
            raise ValueError('Preserved original install journal differs')
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
    boot_done = (verify_detached_boot if provenance_mode=='detached' else verify_boot)(
        freeze(boot_receipt/'commands.jsonl',c['target_boot_commands_sha256'],65536),
        boot,c['target_boot_campaign_sha256'],digest(manifest_raw),install_done)
    if provenance_mode=='detached':verify_wrapper(c, boot, freeze, boot_done)
    snapshot_raw = freeze(c['rom_snapshot_path'],c['rom_snapshot_sha256'],65536)
    snapshot = json.loads(snapshot_raw)
    if (set(snapshot) != {'schema','kind','observed_at','usb_binding','sg_binding',
            'target_boot_campaign_sha256','quiet_state'} or
            type(snapshot['schema']) is not int or snapshot['schema'] != 1 or
            snapshot['kind'] != 'fm1-passive-post-target-boot-rom' or
            snapshot['target_boot_campaign_sha256'] != c['target_boot_campaign_sha256'] or
            snapshot['quiet_state'] != 'initial-rom-no-later-commands-no-loader-upload' or
            not finite_time(snapshot['observed_at']) or snapshot['observed_at'] < boot_done or
            not finite_time(evaluated_at) or not 0 <= evaluated_at-snapshot['observed_at'] <= MAX_SNAPSHOT_AGE or evaluated_at > time.time()):
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
    if (not destination.is_absolute() or destination.parent != parent or (admission and destination.exists()) or
            (admission and marker.exists()) or not stat.S_ISDIR(parent.lstat().st_mode) or
            stat.S_IMODE(parent.stat().st_mode) != 0o700):
        raise ValueError('New private probe receipt and unconsumed target boot required')
    if not admission:
        outcome='not-attempted';absent=[]
        if completed_probe is None and (os.path.lexists(marker) or os.path.lexists(destination) or probe_capture is not None or probe_wrapper_sha256 is not None):
            raise ValueError('Actual probe evidence required for consumed session')
        if completed_probe is None:absent.extend((marker,destination))
        if completed_probe is not None:
            if os.path.lexists(destination/'result.json'):
                if probe_capture is not None or probe_wrapper_sha256 is not None:raise ValueError('Stopped capture cannot relabel completed probe')
                verify_completed_probe(completed_probe,c,snapshot,parent,freeze,provenance_mode)
                outcome='completed-read-only-probe'
            else:
                if probe_capture is None:raise ValueError('Owned capture required for stopped probe')
                outcome=verify_stopped_probe(completed_probe,c,snapshot,parent,freeze,probe_capture,provenance_mode,probe_wrapper_sha256)
                absent.append(destination/'result.json')
                capture_run=Path(json.loads(read_file(probe_capture,65536))['native_campaign_path']).parent
                absent.extend(capture_run/name for name in ('wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'))
                if not os.path.lexists(destination/'commands.jsonl'):absent.append(destination/'commands.jsonl')
        journal_path = Path(inputs['directory'])/'journal.json'
        obj=ReturnedProof(canonical(snapshot), canonical(inputs), digest(manifest_raw), str(parent),
            tuple(item for item in evidence if item[0] != journal_path), policies, boot_done,
            install['rehearsal_campaign_sha256'],boot['journal_sha256'],outcome,tuple(absent))
        _PROOFS.add(obj);obj.check();return obj
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
                target_reset_outcome='transmitted-detached-not-completed',reset_request_completed=False,
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

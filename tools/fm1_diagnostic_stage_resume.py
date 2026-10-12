"""MIT. Separate one-use stage read after the exact actual stopped chooser.

Old ff593/8fb/8ad/747 files and their admission rules remain unchanged. An
isolated pinned 8fb instance supplies historical install/reset validation and
the two-read session; pinned 8ad supplies the Linux SG transport. Only this
module's historical wire callback and Prepared type are substituted in that
private instance. This is trusted Python composition, not a security sandbox.

Linux v6.12 scsi_ioctl.{c,h}/sd.c explains the exact 1e prevent=1 form. Its
matching failed CSW and 05/24/00 sense are capture evidence, not a claim about
kernel process origin or the mask ROM implementation. Current passive binding
does not refresh the original snapshot or prove BSS retention.
"""
import argparse
from dataclasses import dataclass
import json
import hashlib
import os
from pathlib import Path
import stat
import sys
import time
import types
from weakref import WeakSet


HELPER_SHA='8fb33694f3daa26e3a824f33f1b9fa8d646dc5e9295795ea8fff6ea3a983b733'
NATIVE_SHA='8ad32e4203afe2ee61c0864d292abc5d66133ad25f4109974cefd67f0d096f33'
BOOT_SHA='6d7bf62825b117dd21537499bc4dfd41d397c98d804f59c205863d3d6d862778'
CAPTURE_SHA='c5223ee8795534695d4471500c11ebc5be4787e116bdfdd2e7b2878d9d9b264d'
SNAPSHOT_SHA='e79dcad1d199a4c6a4785f1212527a1caedccddf290697871c2befc19f1b14ff'
CHOICE_PINS={
 'execute-once.py':'747ce680bc41de87bc1b229af12316de25cbb708982766db4383ba760d6753e3',
 'selection-campaign.json':'5fac881fec9849908290b4acb064d6d8de415be173b79ad00a360d2a82a7b190',
 'pre-selection.json':'96b8a116e7709a8e176dc3fecf40f310048ae623c98402dcf4b8b599e0765315',
 'chooser-stopped-ambiguous.json':'2da738a9d28075b1d5ce662cf2029dc4f19a5423b2ce5fb4c4dce02fcc8ce384'}
WRAPPERS={'diagnostic-stage-v2':'b3b8186eb5bf11f359b09ff54a0f5f63a1ca317ad7341a6db5bd2f321573eaee',
 'diagnostic-detached-stage-v1':'f88c09edcc0466005c5d6739546697b9ea6ea24555f58bddcf31910629736528'}
ATTEMPT_NAMES=('wrapper-attempt.json','probe-campaign.json','native-campaign.json','preflight.json',
 'capture-open.json','capture-stop.json','execution-exit.json','execution.stdout','usbmon3.txt',
 'usbmon3.stderr','stopped-capture.json','wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json')
OPERATIONS=((bytes.fromhex('120000002400'),b'',36),
            (bytes.fromhex('fd0701c033d80020ffffffffffffffff'),b'',32))


def digest(data):return hashlib.sha256(data).hexdigest()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',', ':'),allow_nan=False).encode('ascii')


def read_file(path,limit=2*1048576):
    path=Path(path)
    if not path.is_absolute():raise ValueError('Absolute direct evidence required')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:fp=os.fdopen(fd,'rb')
    except BaseException:os.close(fd);raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):raise ValueError('Regular direct evidence required')
        data=fp.read(limit+1)
    if len(data)>limit:raise ValueError('Evidence exceeds bound')
    return data


def load_source(path,pin,name):
    raw=read_file(path)
    if digest(raw)!=pin:raise ValueError('Frozen source differs')
    module=types.ModuleType(name);module.__file__=str(path);sys.modules[name]=module
    exec(compile(raw,str(path),'exec'),module.__dict__)
    if read_file(path)!=raw:raise ValueError('Source changed while importing')
    return module
_AUTHORIZED=WeakSet()
_RUNNING=WeakSet()
_PROOFS=WeakSet()


def records(raw,usb,new_usb):
    result=[]
    for line in raw.decode('ascii').splitlines():
        parts=line.split()
        if len(parts)<6 or parts[2] not in ('S','C'):continue
        a=parts[3].split(':')
        if len(a)!=4 or a[0] not in ('Bo','Bi'):continue
        if a[1]!=usb['busnum'] or int(a[2]) not in (int(usb['devnum']),int(new_usb['devnum'])):continue
        data=bytes.fromhex(''.join(parts[7:])) if len(parts)>6 and parts[6]=='=' else b''
        result.append((parts[0],parts[2],a[0],int(a[2]),int(a[3]),int(parts[4]),int(parts[5]),data))
    return result


def verify_wire(raw,usb,new_usb):
    """Pair every relevant URB. Exactly one rejected new-ROM media lock.

    Accepts no outgoing data except exact CBWs; no read/write opcode beyond
    TUR, SENSE, INQUIRY and the unique old-device FC0C. The media-lock opcode
    is historical only and is never among the two submitted probe operations.
    """
    rs=records(raw,usb,new_usb);i=0;tx=[];seen_reset=False
    def pair(pos,dev,direction,length,completion_status=0,completion_length=None):
        if pos+1>=len(rs):raise ValueError('Missing paired transfer')
        s,e=rs[pos:pos+2]
        if (s[1:7]!=('S',direction,dev,1,-115,length) or s[7] or
                e[:5]!=(s[0],'C',direction,dev,1) or
                e[5:7]!=(completion_status,length if completion_length is None else completion_length)):
            raise ValueError('Transfer pair/status/geometry differs')
        return e[7]
    while i<len(rs):
        s=rs[i];dev=s[3];cbw=s[7]
        if (s[1:7]!=('S','Bo',dev,1,-115,31) or len(cbw)!=31 or cbw[:4]!=b'USBC'):
            raise ValueError('Exact CBW submission required')
        if i+1>=len(rs) or rs[i+1][:5]!=(s[0],'C','Bo',dev,1) or rs[i+1][5:7]!=(0,31) or rs[i+1][7]:
            raise ValueError('Exact completed CBW required')
        cdb=cbw[15:];tag=cbw[4:8];length=int.from_bytes(cbw[8:12],'little');direction=cbw[12]
        i+=2
        if cdb==bytes.fromhex('fc0c00000001ffffffffffffffffffff'):
            if seen_reset or dev!=int(usb['devnum']) or cbw[8:15]!=bytes.fromhex('10000000800010'):
                raise ValueError('Unique old-device reset required')
            data=pair(i,dev,'Bi',16,-108,0)
            if data:raise ValueError('Detached reset returned data')
            seen_reset=True;i+=2;tx.append((dev,cdb,b'',None));continue
        forms={bytes(16):(0,0),bytes.fromhex('030000001200')+bytes(10):(18,128),
            bytes.fromhex('120000002400')+bytes(10):(36,128),bytes.fromhex('1e0000000100')+bytes(10):(0,0)}
        if (cbw[13:15]!=bytes.fromhex('0006') or cdb not in forms or forms[cdb]!=(length,direction) or
                (seen_reset and dev==int(usb['devnum'])) or
                (dev==int(new_usb['devnum']) and not seen_reset)):
            raise ValueError('Nonallowlisted historical command/order')
        if cdb[0]==0x1e and dev!=int(new_usb['devnum']):raise ValueError('Lock must be on new ROM')
        data=pair(i,dev,'Bi',length) if length else b''
        if length:
            if len(data)!=min(length,32):raise ValueError('Exact USBmon capture data bound required')
            i+=2
        csw=pair(i,dev,'Bi',13);i+=2
        if len(csw)!=13 or csw[:8]!=b'USBS'+tag or csw[8:12]!=bytes(4) or csw[12] not in (0,1):
            raise ValueError('Matching zero-residue CSW required')
        if cdb[0] in (3,0x12) and csw[12]!=0:raise ValueError('Standard data command failed')
        tx.append((dev,cdb,data,csw[12]))
    locks=[index for index,t in enumerate(tx) if t[1][0]==0x1e]
    if not seen_reset or len(locks)!=1:raise ValueError('Unique reset and rejected lock required')
    index=locks[0];lock=tx[index]
    if (lock[3]!=1 or index+1>=len(tx) or tx[index+1][:3]!=(int(new_usb['devnum']),
            bytes.fromhex('030000001200')+bytes(10),bytes.fromhex('700005000000000a00000000240000000000')) or
            tx[index+1][3]!=0):raise ValueError('Immediate exact illegal-field sense required')
    return dict(reset_cbw_transmitted=True,reset_request_completed=False,reset_core_observed=False,
        no_later_vendor_cbw=True,kernel_compatible_rejected_lock=True,process_origin_verified=False,
        paired_records=len(rs),cbws=len(tx))


@dataclass(frozen=True,eq=False)
class ReturnedProof:
    historical: object
    evidence: tuple
    absent: tuple
    historical_admission_time: float

    def check(self):
        if self not in _PROOFS:raise ValueError('Exact resumed evidence proof required')
        self.historical.check()
        for p,b,n in self.evidence:
            if read_file(p,n)!=b:raise ValueError('Resumed evidence drift')
        for p in self.absent:
            if os.path.lexists(p):raise ValueError('Previously absent probe evidence appeared')

    @property
    def snapshot(self):return self.historical.snapshot
    @property
    def original_inputs(self):return self.historical.original_inputs
    @property
    def private_parent(self):return self.historical.private_parent
    @property
    def manifest_sha256(self):return self.historical.manifest_sha256
    @property
    def policies(self):return self.historical.policies


def validate_returned_state(choice_path):
    """Historical actual stopped choice only; no transport authority or age reset."""
    root=Path(__file__).absolute().parent;choice=Path(choice_path)
    evidence=[];absent=[]
    def freeze(path,pin=None,limit=2*1048576):
        path=Path(path);data=read_file(path,limit)
        if pin is not None and digest(data)!=pin:raise ValueError('Actual stopped-choice/source pin differs')
        evidence.append((path,data,limit));return data
    freeze(Path(__file__).absolute())
    helper_path=root/'fm1_diagnostic_detached_probe.py';freeze(helper_path,HELPER_SHA)
    helper=load_source(helper_path,HELPER_SHA,'_fm1_resume_historical')
    files={name:freeze(choice/name,pin,65536) for name,pin in CHOICE_PINS.items()}
    selection=json.loads(files['selection-campaign.json']);pre=json.loads(files['pre-selection.json']);stop=json.loads(files['chooser-stopped-ambiguous.json'])
    stage=Path(selection['target_boot_campaign_path']).parent.parent;parent=stage.parent
    if choice!=stage/'diagnostic-probe-choice-v1':raise ValueError('Original choice directory required')
    if (pre['time']!=1791775862.0725162 or stop!=dict(detail='Nonallowlisted CBW in owned capture',
            error='ValueError',no_fallback=True,retry=False,time=1791775865.1165452) or
            pre['hardware_access'] is not False or pre['retry'] is not False or pre['mode']!='detached' or
            pre['original_observed_at']!=1791775855.3214695 or selection['rom_snapshot_sha256']!=SNAPSHOT_SHA or
            selection['wrapper_files_sha256']['usbmon3.txt']!=CAPTURE_SHA):
        raise ValueError('Exact actual historical stop required')
    marker=parent/('.diagnostic-probe-choice-'+BOOT_SHA+'.consumed')
    if freeze(marker,limit=256)!=CHOICE_PINS['selection-campaign.json'].encode('ascii'):
        raise ValueError('Original consumed chooser required')
    absent.extend(choice/name for name in ('launch-intent.json','execution.stdout','execution-exit.json'))
    for directory,pin in WRAPPERS.items():
        freeze(stage/directory/'execute-once.py',pin)
        absent.extend(stage/directory/name for name in ATTEMPT_NAMES)
    for p in absent:
        if os.path.lexists(p):raise ValueError('Original chooser launched or probe attempted')
    # Only the private source instance gets this stronger paired callback.
    helper.verify_wire=verify_wire
    historical=helper.validate_returned_state(choice/'selection-campaign.json',evaluated_at=pre['time'])
    obj=ReturnedProof(historical,tuple(evidence),tuple(absent),pre['time'])
    _PROOFS.add(obj);obj.check();return obj


@dataclass(frozen=True,eq=False)
class Prepared:
    campaign: bytes
    campaign_sha256: str
    snapshot: bytes
    proof: ReturnedProof
    witness: bytes
    evidence: tuple
    helper: object
    native: object
    bridge: object
    header_type: type

    def check(self):
        if self not in _AUTHORIZED:raise ValueError('Exact resumed Prepared required')
        self.proof.check()
        for p,b,n in self.evidence:
            if read_file(p,n)!=b:raise ValueError('Resume campaign/witness/source changed')
        witness=json.loads(self.witness)
        if not 0<=time.time()-witness['observed_at']<=120:raise ValueError('Current connection witness stale')
        c=json.loads(self.campaign);dest=Path(c['receipt_path']);marker=dest.parent/('.diagnostic-stage-resume-'+BOOT_SHA+'.consumed')
        if self not in _RUNNING:
            if os.path.lexists(dest) or os.path.lexists(marker):raise ValueError('Resume already attempted')
        else:
            if (read_file(marker,256)!=self.campaign_sha256.encode('ascii') or
                    not stat.S_ISDIR(dest.lstat().st_mode) or stat.S_IMODE(dest.stat().st_mode)!=0o700):
                raise ValueError('Exact consumed resumed receipt required')


def prepare_campaign(path):
    """Device-free factory. The current witness is separate, passive and same-FD lineage."""
    evidence=[]
    def freeze(path,pin=None,limit=2*1048576):
        path=Path(path);raw=read_file(path,limit)
        if pin is not None and digest(raw)!=pin:raise ValueError('Resume source/evidence pin differs')
        evidence.append((path,raw,limit));return raw
    root=Path(__file__).absolute().parent;raw=freeze(Path(path),limit=65536);c=json.loads(raw)
    if (set(c)!={'schema','kind','adapter_sha256','choice_path','witness_path','witness_sha256','receipt_path'} or
            type(c['schema']) is not int or c['schema']!=1 or c['kind']!='fm1-actual-stopped-choice-stage-read'):
        raise ValueError('Distinct actual stopped-choice campaign required')
    freeze(Path(__file__).absolute(),c['adapter_sha256'])
    freeze(root/'fm1_diagnostic_detached_sg.py',NATIVE_SHA)
    proof=validate_returned_state(c['choice_path']);snap=json.loads(proof.snapshot)
    witness_raw=freeze(c['witness_path'],c['witness_sha256'],65536);w=json.loads(witness_raw)
    if (set(w)!={'schema','kind','observed_at','usb_binding','sg_binding','original_rom_snapshot_sha256','choice_stop_sha256','quiet_state'} or
            type(w['schema']) is not int or w['schema']!=1 or w['kind']!='fm1-passive-current-same-rom-after-stopped-choice' or
            type(w['observed_at']) not in (float,int) or not 0<=time.time()-w['observed_at']<=120 or
            w['observed_at']<1791775865.1165452 or w['quiet_state']!='no-later-device-commands-no-loader-upload' or
            w['original_rom_snapshot_sha256']!=SNAPSHOT_SHA or w['choice_stop_sha256']!=CHOICE_PINS['chooser-stopped-ambiguous.json'] or
            canonical(w['usb_binding'])!=canonical(snap['usb_binding']) or canonical(w['sg_binding'])!=canonical(snap['sg_binding'])):
        raise ValueError('Separate fresh same-ROM connection witness required')
    dest=Path(c['receipt_path'])
    if dest!=Path(proof.private_parent)/'diagnostic-stage-resume-001':raise ValueError('Distinct private resumed receipt required')
    native=load_source(root/'fm1_diagnostic_detached_sg.py',NATIVE_SHA,'_fm1_resume_native')
    helper=load_source(root/'fm1_diagnostic_detached_probe.py',HELPER_SHA,'_fm1_resume_session')
    # Retain exactly the reviewed session body; only its instance-type boundary
    # names this module's stronger, separately registered admission object.
    helper.Prepared=Prepared
    bridge_path=root/'fm1_fixed_loader_backup.py';reader_path=root/'fm1_uboot_read.py'
    freeze(bridge_path,native.BRIDGE_SHA);freeze(reader_path,native.READER_SHA)
    bridge=native.load_source(bridge_path,native.BRIDGE_SHA,'_fm1_resume_bridge')
    reader=native.load_source(reader_path,native.READER_SHA,'_fm1_resume_reader')
    if native.C.sizeof(reader.SGHeader)!=88 or native.C.sizeof(native.C.c_void_p)!=8 or native.OPERATIONS!=OPERATIONS:
        raise ValueError('Exact native transport geometry required')
    obj=Prepared(canonical(c),digest(raw),proof.snapshot,proof,witness_raw,tuple(evidence),helper,native,bridge,reader.SGHeader)
    _AUTHORIZED.add(obj);obj.check();return obj


def run_campaign(prepared,transport_factory=None):
    """Distinct marker, exact two reads, no fallback. Root alone activates SG."""
    if prepared not in _AUTHORIZED:raise ValueError('Exact resumed Prepared required')
    prepared.check();h=prepared.helper;c=json.loads(prepared.campaign);receipt=Path(c['receipt_path'])
    receipt.mkdir(mode=0o700,exist_ok=False);h.sync_dir(receipt.parent)
    marker=receipt.parent/('.diagnostic-stage-resume-'+BOOT_SHA+'.consumed')
    with h.private_file(marker) as fp:
        fp.write(prepared.campaign_sha256.encode('ascii'));fp.flush();os.fsync(fp.fileno())
    h.sync_dir(receipt.parent);_RUNNING.add(prepared);prepared.check()
    if transport_factory is None:
        n=prepared.native
        proxy=types.SimpleNamespace(Completion=h.Completion)
        np=n.Prepared(prepared.campaign,prepared.campaign_sha256,prepared,proxy,prepared.bridge,prepared.header_type,prepared.evidence)
        n._AUTHORIZED.add(np)
        def transport_factory(p):
            if p is not prepared:raise ValueError('Exact resumed instance required')
            permit=n._OpenPermit(np);n._OPENING.add(permit)
            try:return n.NativeSG(np,permit)
            finally:n._OPENING.discard(permit)
    with h.private_file(receipt/'commands.jsonl','w') as events:
        def log(event,**fields):
            events.write(json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n')
            events.flush();os.fsync(events.fileno());h.sync_dir(receipt)
        session=None
        try:
            log('resumed_stage_probe_prepared',campaign_sha256=prepared.campaign_sha256,
                original_rom_snapshot_sha256=SNAPSHOT_SHA,choice_stop_sha256=CHOICE_PINS['chooser-stopped-ambiguous.json'],
                current_witness_sha256=digest(prepared.witness),original_snapshot_refreshed=False,
                commands=2,upload_operations=0,flash_operations=0,reset_operations=0,kernel_exclusivity=False)
            prepared.check();session=h.ProbeSession(prepared,transport_factory(prepared),log)
            inquiry=session.exchange(h.INQUIRY,in_len=36);raw=session.exchange(h.READ_STAGE,in_len=32);session.close()
            decoded=h.decode_stage(raw)
            result=dict(campaign_sha256=prepared.campaign_sha256,raw_sha256=digest(raw),decoded_sha256=digest(decoded),
                inquiry_sha256=digest(inquiry),current_witness_sha256=digest(prepared.witness),
                original_rom_snapshot_sha256=SNAPSHOT_SHA,choice_stop_sha256=CHOICE_PINS['chooser-stopped-ambiguous.json'],
                original_snapshot_refreshed=False,target_reset_outcome='transmitted-detached-not-completed',
                reset_request_completed=False,**h.interpret_stage(decoded))
            for name,data in (('raw.bin',raw),('decoded.bin',decoded)):
                with h.private_file(receipt/name) as fp:fp.write(data);fp.flush();os.fsync(fp.fileno())
            h.sync_dir(receipt);log('stage_capture_completed',**result,retry=False)
            with h.private_file(receipt/'.result.json.pending') as fp:fp.write(canonical(result));fp.flush();os.fsync(fp.fileno())
            os.link(receipt/'.result.json.pending',receipt/'result.json',follow_symlinks=False)
            (receipt/'.result.json.pending').unlink();h.sync_dir(receipt);return result
        except BaseException as exc:
            try:
                (receipt/'result.json').unlink(missing_ok=True);h.sync_dir(receipt)
                log('stage_probe_stopped_ambiguous',error=type(exc).__name__,retry=False,
                    classification='inconclusive',display_observed=False,physical_recovery_verified=False)
            except BaseException:pass
            raise
        finally:
            if session is not None:session.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--campaign',type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!='linux':raise SystemExit('Linux SG_IO only')
    print(json.dumps(run_campaign(prepare_campaign(args.campaign)),sort_keys=True))


if __name__=='__main__':main()

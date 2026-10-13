#!/usr/bin/python3
"""CLOSED completed-stop-trace stock reset wrapper. Root owns future binding/activation.

One genuine returned-stock-reset child; owned USBmon; passive same-port normal
enumeration; one fixed identity query only after that enumeration. No soft key,
loader, fallback or retry. None pins deliberately prevent all runtime activity.
"""
import fcntl,hashlib,json,os,re,select,signal,stat,subprocess,sys,time,types
from pathlib import Path

STAGE=Path('/home/claude/fm1-completed-trace-recovery-20261012')
RUN=STAGE/'run/physical-stock-reset-003'
RECOVERY=STAGE/'run/physical-restore-001'
BACKUP=Path('/home/claude/fm1-sdk-trace-entry-20261012-v7/stock-backup-001/physical-completed-trace-backup-001')
JOURNAL_PATH=Path('/home/claude/fm1-sdk-trace-campaign-20261012-v7/transaction/journal.json')
ADAPTER_PATH=STAGE/'tools/fm1_completed_stop_trace_stock_reset_check_v3.py'
# A separately reviewed concrete successor must bind actual completed restore
# receipts and a final adapter with its genuine RESTORE_SOURCE_SHA pinned.
PACKET_SHA=None
PACKET_MEMBERS=None
RESET_CAMPAIGN_SHA=None
RESET_ADAPTER_SHA=None
RESTORE_CAMPAIGN_SHA=None
RESTORE_COMMANDS_SHA=None
RESTORE_RESULT_SHA=None
RESTORE_JOURNAL_SHA=None
IDENTIFY_SHA='684342b034b1a97b0e070ff758edf9bff20714523316a968952ccf48f52c0de0'
IDENTITY=bytes.fromhex('f0 00 32 45 00 00 00 40 7f f7')
KNOWN_092=bytes.fromhex('f0 00 32 45 58 01 00 00 23 4d 5a 44 79 05 26 0e 19 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20 06 f7')
ARTIFACTS=('wrapper-attempt.json','capture-open.json','capture-stop.json',
 'execution.stdout','execution-exit.json','usbmon1.txt','usbmon1.stderr',
 'normal-observations.json','normal-snapshot.json','stock-identity.jsonl',
 'wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json')

def require_frozen():
    pins=(PACKET_SHA,RESET_CAMPAIGN_SHA,RESET_ADAPTER_SHA,RESTORE_CAMPAIGN_SHA,
          RESTORE_COMMANDS_SHA,RESTORE_RESULT_SHA,RESTORE_JOURNAL_SHA)
    if (any(type(p) is not str or re.fullmatch('[0-9a-f]{64}',p) is None for p in pins)
            or type(PACKET_MEMBERS) is not int or PACKET_MEMBERS<=0):
        raise ValueError('Closed template: genuine restore/final adapter/actual packet pins not reviewed')

def read(p,limit=2*1048576):
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:fp=os.fdopen(fd,'rb')
    except BaseException:os.close(fd);raise
    with fp:
        if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):raise ValueError('Direct regular evidence required')
        data=fp.read(limit+1)
    if len(data)>limit:raise ValueError('Evidence exceeds fixed bound')
    return data

def sha(p,limit=2*1048576):return hashlib.sha256(read(p,limit)).hexdigest()

def sync(p):
    fd=os.open(p,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:os.fsync(fd)
    finally:os.close(fd)

def save(p,obj):
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
    try:fp=os.fdopen(fd,'w')
    except BaseException:os.close(fd);raise
    with fp:
        json.dump(obj,fp,sort_keys=True,allow_nan=False);fp.write('\n');fp.flush();os.fsync(fp.fileno())
    sync(p.parent)

def load(p,pin,name):
    raw=read(p)
    if hashlib.sha256(raw).hexdigest()!=pin:raise ValueError('Reviewed source differs')
    module=types.ModuleType(name);module.__file__=str(p);sys.modules[name]=module
    exec(compile(raw,str(p),'exec'),module.__dict__)
    if read(p)!=raw:raise ValueError('Source drift during import')
    return module

def packet_check():
    if sha(RUN/'packet-pins.json',65536)!=PACKET_SHA:raise ValueError('Concrete restore packet differs')
    pins=json.loads(read(RUN/'packet-pins.json',65536))
    if type(pins) is not dict or len(pins)!=PACKET_MEMBERS:raise ValueError('Exact packet inventory required')
    for name,pin in pins.items():
        path=Path(name)
        if path.is_absolute() or '..' in path.parts:raise ValueError('Direct stage-relative member required')
        if sha(STAGE/path,32*1048576)!=pin:raise ValueError('Actual restore packet member differs: '+name)
    if (sha(RUN/'campaign.json',65536)!=RESET_CAMPAIGN_SHA or sha(ADAPTER_PATH)!=RESET_ADAPTER_SHA
            or sha(RECOVERY/'campaign.json',65536)!=RESTORE_CAMPAIGN_SHA
            or sha(BACKUP/'stock-restore/commands.jsonl',16*1048576)!=RESTORE_COMMANDS_SHA
            or sha(BACKUP/'stock-restore/result.json',65536)!=RESTORE_RESULT_SHA
            or sha(JOURNAL_PATH)!=RESTORE_JOURNAL_SHA
            or sha(STAGE/'tools/fm1_identify.py')!=IDENTIFY_SHA):
        raise ValueError('Actual completed restore/final reset/identity pins differ')

def capture_alive(process):
    if process.poll() is not None:raise RuntimeError('Owned capture exited')
    pid=process.pid
    if os.getpgid(pid)!=pid:raise ValueError('Owned capture PGID differs')
    proc=Path('/proc')/str(pid)
    if read(proc/'cmdline',65536).split(b'\0')[:4]!=[b'/usr/bin/timeout',b'300',b'/bin/cat',b'/sys/kernel/debug/usb/usbmon/1u']:
        raise ValueError('Capture command differs')
    children=read(proc/'task'/str(pid)/'children',65536).split()
    if len(children)!=1:raise ValueError('One owned cat required')
    child=int(children[0]);childproc=Path('/proc')/str(child)
    if os.getpgid(child)!=pid or read(childproc/'cmdline',65536).split(b'\0')[:2]!=[b'/bin/cat',b'/sys/kernel/debug/usb/usbmon/1u']:
        raise ValueError('Owned cat differs')
    links=[]
    for fd in (childproc/'fd').iterdir():
        try:links.append(os.readlink(fd))
        except FileNotFoundError:pass
    if '/sys/kernel/debug/usb/usbmon/1u' not in links:raise ValueError('Capture FD not open')
    return dict(timeout_pid=pid,cat_pid=child,process_group=pid,open_capture_fd=True)

def midi_for(usb):
    target=(Path('/sys/bus/usb/devices')/usb['path']).resolve(strict=True)
    hits=[]
    for sound in Path('/sys/class/sound').glob('midiC*D*'):
        if re.fullmatch(r'midiC[0-9]+D[0-9]+',sound.name) is None:continue
        node=sound/'device'
        try:anc=node.resolve(strict=True)
        except FileNotFoundError:continue
        if target in (anc,*anc.parents):hits.append(Path('/dev/snd')/sound.name)
    if len(hits)!=1:raise ValueError('Exactly one same-port raw MIDI endpoint required')
    return hits[0]


def wait_for_midi(bridge,usb,capture):
    """Bounded passive host readiness; no command submission or reset retry."""
    deadline=time.monotonic()+10
    while True:
        capture_alive(capture)
        if bridge.usb_snapshot(Path('/sys/bus/usb/devices')/usb['path'])!=usb:
            raise ValueError('Normal USB changed while awaiting MIDI')
        try:return midi_for(usb)
        except (FileNotFoundError,ValueError):
            if time.monotonic()>=deadline:
                raise ValueError('Same-port MIDI readiness deadline expired; no identity query')
            time.sleep(.1)

def identity_once(bridge,usb,decoder,capture):
    """One fixed read-only identity write, bounded reads; never send a soft key."""
    midi=midi_for(usb)
    fd=os.open(midi,os.O_RDWR|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        original=os.fstat(fd)
        def binding():
            capture_alive(capture)
            now=bridge.usb_snapshot(Path('/sys/bus/usb/devices')/usb['path'])
            if now!=usb or midi_for(usb)!=midi:raise ValueError('Normal MIDI connection changed')
            actual=os.fstat(fd);node=midi.lstat()
            if (not stat.S_ISCHR(actual.st_mode) or not stat.S_ISCHR(node.st_mode)
                    or (actual.st_dev,actual.st_ino,actual.st_rdev)!=(original.st_dev,original.st_ino,original.st_rdev)
                    or (node.st_dev,node.st_ino,node.st_rdev)!=(original.st_dev,original.st_ino,original.st_rdev)):
                raise ValueError('Normal MIDI FD replaced')
        def log(event,**fields):
            logfd=os.open(RUN/'stock-identity.jsonl',os.O_WRONLY|os.O_APPEND|os.O_NOFOLLOW|os.O_CLOEXEC)
            try:fp=os.fdopen(logfd,'ab',buffering=0)
            except BaseException:os.close(logfd);raise
            with fp:
                if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):raise ValueError('Direct identity receipt required')
                fp.write((json.dumps(dict(time=time.time(),event=event,**fields),allow_nan=False)+'\n').encode())
                os.fsync(fp.fileno())
            sync(RUN)
        # Open the identity receipt exclusively before any message submission.
        receipt=os.open(RUN/'stock-identity.jsonl',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
        try:os.fsync(receipt)
        finally:os.close(receipt)
        sync(RUN);binding()
        # Bounded stale-input drain. A stream that never quiesces is rejected.
        for attempt in range(16):
            if not select.select([fd],[],[],0)[0]:break
            if not os.read(fd,4096):raise OSError('MIDI disconnected before identity')
        else:raise ValueError('MIDI stale input did not quiesce')
        log('identity_intent',hex=IDENTITY.hex(' '),usb_binding=usb,midi=str(midi),retry=False)
        packet_check();binding()
        count=os.write(fd,IDENTITY)
        binding()
        log('identity_write_returned',length=count,retry=False)
        if count!=len(IDENTITY):raise OSError('Partial identity write; no retry')
        data=bytearray();deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            binding()
            if select.select([fd],[],[],min(.1,max(0,deadline-time.monotonic())))[0]:
                chunk=os.read(fd,4096)
                if not chunk:raise OSError('MIDI disconnected during identity')
                data.extend(chunk)
                if len(data)>65536:raise ValueError('Identity reply exceeds bound')
                start=data.find(b'\xf0');end=data.find(b'\xf7',max(0,start))
                if start>=0 and end>=start:
                    reply=bytes(data[start:end+1]);info=decoder.decode(reply)
                    log('identity_response',received=data.hex(' '),reply=reply.hex(' '),decoded=info)
                    if info.get('identity')!='FM-1_092' or info.get('error') or not (info.get('checksum_ok') is True or reply==KNOWN_092):
                        raise ValueError('Exact known stock identity not received')
                    binding();log('identity_observed',reply=reply.hex(' '),decoded=info,
                        checksum_exception=reply==KNOWN_092,boot_cause_proven=False)
                    return info
        log('identity_not_proven',received=data.hex(' '),retry=False)
        raise ValueError('Fresh exact stock identity not received; no retry')
    finally:os.close(fd)

def main():
    # Keep this first, before any file, process, device or persistent activity.
    require_frozen()
    if sys.platform!='linux' or os.geteuid()!=0 or sys.flags.optimize!=0:
        raise ValueError('Nonoptimized reviewed Linux root interpreter required')
    os.umask(0o077)
    for path in (STAGE,RUN,RECOVERY,BACKUP):
        if not stat.S_ISDIR(path.lstat().st_mode) or stat.S_IMODE(path.stat().st_mode)!=0o700:raise ValueError('Private direct dirs required')
    if any(os.path.lexists(RUN/name) for name in ARTIFACTS):raise ValueError('Wrapper already attempted')
    packet_check()
    sys.path.insert(0,str(STAGE/'tools'))
    adapter=load(ADAPTER_PATH,RESET_ADAPTER_SHA,'_returned_stock_reset_wrapper_adapter')
    if adapter.RESTORE_SOURCE_SHA is None:raise ValueError('Genuine completed restore source not pinned')
    decoder=load(STAGE/'tools/fm1_identify.py',IDENTIFY_SHA,'_returned_stock_identity_decoder')
    prepared=adapter.prepare_campaign(RUN/'campaign.json')
    if prepared.campaign_sha256!=RESET_CAMPAIGN_SHA:raise ValueError('Actual reset campaign differs')
    original=json.loads(prepared.usb_binding)
    if set(original)!={'path','busnum','devnum','vid','pid'}:raise ValueError('Exact inherited USB binding required')
    if original['busnum']!='1' or original['vid']!='4c4a' or original['pid']!='8057':
        raise ValueError('Inherited loader must match captured USB bus 1')
    save(RUN/'wrapper-attempt.json',dict(time=time.time(),campaign_sha256=RESET_CAMPAIGN_SHA,
        adapter_sha256=RESET_ADAPTER_SHA,retry=False,identity_query_limit=1))
    capture=None;status=1
    try:
        with open(RUN/'usbmon1.txt','xb',buffering=0) as output,open(RUN/'usbmon1.stderr','xb',buffering=0) as error:
            capture=subprocess.Popen(['/usr/bin/timeout','300','/bin/cat','/sys/kernel/debug/usb/usbmon/1u'],stdout=output,stderr=error,start_new_session=True)
            opened=None
            for attempt in range(50):
                try:opened=capture_alive(capture);break
                except (ValueError,FileNotFoundError):time.sleep(.02)
            if opened is None:raise RuntimeError('Owned capture did not open')
            save(RUN/'capture-open.json',dict(time=time.time(),**opened))
            packet_check();prepared.check();capture_alive(capture)
            with open(RUN/'execution.stdout','xb',buffering=0) as log:
                result=subprocess.run(['/usr/bin/python3','-B','-E','-s','-S',str(ADAPTER_PATH),'--campaign',str(RUN/'campaign.json')],
                    cwd=STAGE,env={'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8'},stdout=log,stderr=subprocess.STDOUT,timeout=180)
                os.fsync(log.fileno())
            status=result.returncode;capture_alive(capture);os.fsync(output.fileno())
            save(RUN/'execution-exit.json',dict(time=time.time(),exit_status=status,campaign_sha256=RESET_CAMPAIGN_SHA,
                capture_alive_after_child=True,retry=False,reset_completed_attested=False,boot_cause_proven=False))
            observations=[];normal=None;deadline=time.monotonic()+45
            while time.monotonic()<deadline:
                capture_alive(capture)
                try:
                    usb=prepared.bridge.usb_snapshot(Path('/sys/bus/usb/devices')/original['path'])
                    if not observations or observations[-1]['usb_binding']!=usb:observations.append(dict(time=time.time(),usb_binding=usb))
                    if (usb['path']==original['path'] and usb['busnum']==original['busnum'] and usb['devnum']!=original['devnum']
                            and set(usb)==set(original) and usb['vid']=='4c4a' and usb['pid']=='c755'):
                        normal=usb;break
                except (FileNotFoundError,ValueError):pass
                time.sleep(.1)
            save(RUN/'normal-observations.json',dict(time=time.time(),observations=observations,found=normal is not None,passive_sysfs_only=True))
            if normal is None:raise ValueError('Same-port fresh normal USB not observed; no identity query')
            save(RUN/'normal-snapshot.json',dict(time=time.time(),usb_binding=normal,reset_campaign_sha256=RESET_CAMPAIGN_SHA,
                normal_enumeration_only=True,reset_completion_proven=False,boot_cause_proven=False))
            wait_for_midi(prepared.bridge,normal,capture)
            identity_once(prepared.bridge,normal,decoder,capture)
    except BaseException as exc:
        save(RUN/'wrapper-stopped-ambiguous.json',dict(time=time.time(),error=type(exc).__name__,detail=str(exc),retry=False))
        raise
    finally:
        if capture is not None:
            try:
                capture_alive(capture);os.killpg(capture.pid,signal.SIGTERM);capture.wait(timeout=5)
                with open(RUN/'usbmon1.txt','rb') as fp:os.fsync(fp.fileno())
                with open(RUN/'usbmon1.stderr','rb') as fp:os.fsync(fp.fileno())
                save(RUN/'capture-stop.json',dict(time=time.time(),process_group=capture.pid,returncode=capture.returncode,owned_processes_only=True))
            except BaseException as exc:
                save(RUN/'wrapper-cleanup-ambiguous.json',dict(time=time.time(),error=type(exc).__name__,detail=str(exc),retry=False))
                raise
    return status

if __name__=='__main__':sys.exit(main())

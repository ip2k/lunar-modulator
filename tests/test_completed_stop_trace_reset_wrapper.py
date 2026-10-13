"""Private wrapper models; all activation pins substituted only in tests.

No hardware: reset child/capture/sysfs/MIDI are injected. Actual backup/restore provenance is exercised separately by the adapter tests.
"""
import hashlib,importlib.util,json,os,stat,sys,time
from pathlib import Path
from types import SimpleNamespace
import pytest

REPO=Path(__file__).resolve().parents[1]
SOURCE=REPO/'tools/fm1_completed_stop_trace_reset_wrapper.py'
sys.path[:0]=[str(REPO/'tools'),str(REPO/'tests')]
import fm1_identify as decoder

def digest(data):return hashlib.sha256(data).hexdigest()
def save(p,o):p.write_text(json.dumps(o))
def module(path=SOURCE):
    spec=importlib.util.spec_from_file_location('_returned_wrapper_model',path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

@pytest.fixture
def model(tmp_path,monkeypatch):
    m=module();stage=tmp_path/'stage';stage.mkdir(mode=0o700)
    run=stage/'stopped-choice-stock-reset-v1';run.mkdir(mode=0o700)
    recovery=stage/'stopped-choice-recovery-v2';recovery.mkdir(mode=0o700)
    backup=tmp_path/'stopped-choice-target-backup-002';backup.mkdir(mode=0o700)
    restore=backup/'stock-restore';restore.mkdir(mode=0o700)
    (stage/'tools').mkdir(mode=0o700);(stage/'transaction').mkdir(mode=0o700)
    m.STAGE,m.RUN,m.RECOVERY,m.BACKUP=stage,run,recovery,backup
    m.JOURNAL_PATH=stage/'transaction/journal.json'
    m.ADAPTER_PATH=stage/'tools/fm1_completed_stop_trace_stock_reset_check_v3.py'
    m.ADAPTER_PATH.write_bytes(b'modeled root adapter');m.RESET_ADAPTER_SHA=digest(m.ADAPTER_PATH.read_bytes())
    (stage/'tools/fm1_identify.py').write_bytes(Path(decoder.__file__).read_bytes())
    config=dict(adapter_sha256=m.RESET_ADAPTER_SHA,receipt_path=str(backup/'reset'))
    save(run/'campaign.json',config);m.RESET_CAMPAIGN_SHA=digest((run/'campaign.json').read_bytes())
    for path,pin in ((recovery/'campaign.json','RESTORE_CAMPAIGN_SHA'),(restore/'commands.jsonl','RESTORE_COMMANDS_SHA'),
                     (restore/'result.json','RESTORE_RESULT_SHA'),(stage/'transaction/journal.json','RESTORE_JOURNAL_SHA')):
        path.write_bytes(b'modeled-'+pin.encode());setattr(m,pin,digest(path.read_bytes()))
    pins={str(p.relative_to(stage)):digest(p.read_bytes()) for p in stage.rglob('*') if p.is_file()}
    save(run/'packet-pins.json',pins);m.PACKET_SHA=digest((run/'packet-pins.json').read_bytes());m.PACKET_MEMBERS=len(pins)
    usb=dict(path='1-1',busnum='1',devnum='30',vid='4c4a',pid='8057')
    normal=dict(usb,devnum='31',pid='c755')
    state=SimpleNamespace(m=m,calls=[],status=0,normal=normal,usb=usb,identity=[],capture_checks=0,killed=[],
                          capture_dead=False,cleanup_error=False,preflight_calls=0,checks=0)
    bridge=SimpleNamespace(usb_snapshot=lambda _:dict(state.normal))
    def check():state.checks+=1
    prepared=SimpleNamespace(campaign_sha256=m.RESET_CAMPAIGN_SHA,usb_binding=json.dumps(usb).encode(),bridge=bridge,check=check)
    def prepare(_):state.preflight_calls+=1;return prepared
    adapter=SimpleNamespace(RESTORE_SOURCE_SHA='modeled-accepted-source',prepare_campaign=prepare)
    state.adapter=adapter;state.prepared=prepared
    def load(path,pin,name):
        assert m.sha(path)==pin
        return adapter if path==m.ADAPTER_PATH else decoder
    monkeypatch.setattr(m,'load',load)
    monkeypatch.setattr(m.sys,'platform','linux');monkeypatch.setattr(m.os,'geteuid',lambda:0)
    monkeypatch.setattr(m.os,'umask',lambda _:0o077)
    monkeypatch.setattr(m.time,'sleep',lambda _:None)
    process=SimpleNamespace(pid=42,returncode=-15,poll=lambda:None,wait=lambda timeout:-15)
    def popen(argv,**kwargs):
        assert argv==['/usr/bin/timeout','300','/bin/cat','/sys/kernel/debug/usb/usbmon/1u']
        assert kwargs['start_new_session'] is True
        kwargs['stdout'].write(b'modeled owned wire');kwargs['stderr'].write(b'modeled stderr')
        return process
    def alive(p):
        assert p is process;state.capture_checks+=1
        if state.capture_dead:raise RuntimeError('Modeled capture dead')
        return dict(timeout_pid=42,cat_pid=43,process_group=42,open_capture_fd=True)
    def child(argv,**kwargs):
        assert argv==['/usr/bin/python3','-B','-E','-s','-S',str(m.ADAPTER_PATH),'--campaign',str(m.RUN/'campaign.json')]
        state.calls.append(argv);kwargs['stdout'].write(b'modeled reset child')
        return SimpleNamespace(returncode=state.status)
    def kill(pid,sig):
        state.killed.append((pid,sig))
        if state.cleanup_error:raise OSError('Modeled cleanup failure')
    def identity(*args):state.identity.append(args);return dict(identity='FM-1_092')
    monkeypatch.setattr(m.subprocess,'Popen',popen);monkeypatch.setattr(m.subprocess,'run',child)
    monkeypatch.setattr(m,'capture_alive',alive);monkeypatch.setattr(m.os,'killpg',kill)
    monkeypatch.setattr(m,'identity_once',identity)
    monkeypatch.setattr(m,'midi_for',lambda usb:Path('/dev/snd/midiC2D0'))
    return state

def test_closed_first_gate_no_activity(monkeypatch):
    m=module()
    monkeypatch.setattr(m.os,'open',lambda *a,**k:pytest.fail('Closed template opened something'))
    with pytest.raises(ValueError,match='Closed template'):m.main()

@pytest.mark.parametrize('status',[0,1])
def test_exact_one_child_then_passive_normal_identity_no_reset_claim(model,status):
    s=model;m=s.m;s.status=status
    assert m.main()==status and len(s.calls)==len(s.identity)==s.preflight_calls==1
    exit=json.loads((m.RUN/'execution-exit.json').read_bytes())
    assert exit['exit_status']==status and exit['reset_completed_attested'] is exit['boot_cause_proven'] is False
    snapshot=json.loads((m.RUN/'normal-snapshot.json').read_bytes())
    assert snapshot['usb_binding']==s.normal and snapshot['reset_completion_proven'] is False
    assert json.loads((m.RUN/'capture-stop.json').read_bytes())['owned_processes_only'] is True
    assert s.killed==[(42,m.signal.SIGTERM)]
    with pytest.raises(ValueError,match='already attempted'):m.main()
    assert len(s.calls)==len(s.identity)==1

@pytest.mark.parametrize('fault',['packet','adapter','restore_campaign','restore_commands','restore_result','journal','identify',
                                  'old_attempt','symlink_attempt','bad_dir','nonlinux','not_root','unfrozen_helper','wrong_bus'])
def test_preflight_rejects_without_capture_or_child(model,monkeypatch,fault):
    s=model;m=s.m
    paths=dict(packet=m.RUN/'packet-pins.json',adapter=m.ADAPTER_PATH,restore_campaign=m.RECOVERY/'campaign.json',
               restore_commands=m.BACKUP/'stock-restore/commands.jsonl',restore_result=m.BACKUP/'stock-restore/result.json',
               journal=m.STAGE/'transaction/journal.json',identify=m.STAGE/'tools/fm1_identify.py')
    if fault in paths:paths[fault].write_bytes(b'changed')
    elif fault=='old_attempt':(m.RUN/'wrapper-attempt.json').write_bytes(b'old')
    elif fault=='symlink_attempt':(m.RUN/'wrapper-attempt.json').symlink_to('/nonexistent')
    elif fault=='bad_dir':m.RUN.chmod(0o755)
    elif fault=='nonlinux':monkeypatch.setattr(m.sys,'platform','darwin')
    elif fault=='not_root':monkeypatch.setattr(m.os,'geteuid',lambda:1000)
    elif fault=='wrong_bus':s.prepared.usb_binding=json.dumps(dict(s.usb,busnum='3')).encode()
    else:s.adapter.RESTORE_SOURCE_SHA=None
    with pytest.raises(ValueError):m.main()
    assert not s.calls and not s.identity and not s.capture_checks

@pytest.mark.parametrize('fault',['child_timeout','child_exception','dead_capture','cleanup','source_after_capture','identity_failure','normal_missing'])
def test_failure_stays_consumed_no_fallback(model,monkeypatch,fault):
    s=model;m=s.m
    if fault in ('child_timeout','child_exception'):
        def failed(*args,**kwargs):
            s.calls.append(args[0])
            if fault=='child_timeout':raise m.subprocess.TimeoutExpired(args[0],180)
            raise OSError('Modeled child failure')
        monkeypatch.setattr(m.subprocess,'run',failed)
    elif fault=='dead_capture':s.capture_dead=True
    elif fault=='cleanup':s.cleanup_error=True
    elif fault=='source_after_capture':
        original=m.capture_alive
        def drift(p):
            result=original(p);m.ADAPTER_PATH.write_bytes(b'changed after capture');return result
        monkeypatch.setattr(m,'capture_alive',drift)
    elif fault=='identity_failure':monkeypatch.setattr(m,'identity_once',lambda *a:(_ for _ in ()).throw(ValueError('wrong identity')))
    else:
        s.normal=dict(s.usb)
        clock=iter([0,46]);monkeypatch.setattr(m.time,'monotonic',lambda:next(clock))
    with pytest.raises((OSError,ValueError,RuntimeError,m.subprocess.TimeoutExpired)):m.main()
    assert len(s.calls)<=1 and (m.RUN/'wrapper-attempt.json').exists()
    assert (m.RUN/('wrapper-cleanup-ambiguous.json' if fault in ('cleanup','dead_capture') else 'wrapper-stopped-ambiguous.json')).exists()
    if fault=='normal_missing':assert not s.identity
    with pytest.raises(ValueError,match='already attempted'):m.main()
    assert len(s.calls)<=1

@pytest.fixture
def identity(tmp_path,monkeypatch):
    m=module();m.RUN=tmp_path;usb=dict(path='1-1',busnum='1',devnum='31',vid='4c4a',pid='c755')
    node=tmp_path/'midiC1D0';node.write_bytes(b'modeled char')
    state=SimpleNamespace(m=m,usb=usb,node=node,writes=[],reads=[],closed=[],bindings=0,reply=m.KNOWN_092,write_fault=None,drift=None)
    fake=991;real_open=m.os.open;real_close=m.os.close;real_fstat=m.os.fstat;real_write=m.os.write;real_read=m.os.read
    def open_(p,flags,*a,**k):
        if Path(p)==node:return fake
        return real_open(p,flags,*a,**k)
    fs=SimpleNamespace(st_mode=stat.S_IFCHR|0o600,st_dev=1,st_ino=2,st_rdev=3)
    def fstat(fd):return SimpleNamespace(**vars(fs)) if fd==fake else real_fstat(fd)
    real_lstat=m.Path.lstat
    monkeypatch.setattr(m.Path,'lstat',lambda p,*a,**k:fs if p==node else real_lstat(p,*a,**k))
    def close(fd):
        if fd==fake:state.closed.append(fd)
        else:real_close(fd)
    def write(fd,data):
        if fd!=fake:return real_write(fd,data)
        state.writes.append(data)
        if state.write_fault=='partial':return len(data)-1
        if state.write_fault=='eagain':raise BlockingIOError('Modeled EAGAIN')
        return len(data)
    def read(fd,length):
        if fd!=fake:return real_read(fd,length)
        state.reads.append(length);return state.reply
    monkeypatch.setattr(m.os,'open',open_);monkeypatch.setattr(m.os,'close',close)
    monkeypatch.setattr(m.os,'fstat',fstat);monkeypatch.setattr(m.os,'write',write);monkeypatch.setattr(m.os,'read',read)
    monkeypatch.setattr(m.fcntl,'flock',lambda fd,flags:None)
    def midi_for(_):
        state.bindings+=1
        if state.drift=='topology' and state.bindings>=2:return tmp_path/'replaced'
        if state.drift=='fd' and state.bindings>=2:fs.st_ino=999
        return node
    monkeypatch.setattr(m,'midi_for',midi_for);monkeypatch.setattr(m,'capture_alive',lambda _:dict())
    monkeypatch.setattr(m,'packet_check',lambda:None)
    monkeypatch.setattr(m.select,'select',lambda r,w,e,t:([fake] if t>0 else [],[],[]))
    state.bridge=SimpleNamespace(usb_snapshot=lambda _:dict(state.usb));state.capture=object()
    return state

def test_identity_exact_known092_once_and_fd_close(identity):
    s=identity;m=s.m
    assert m.identity_once(s.bridge,s.usb,decoder,s.capture)['identity']=='FM-1_092'
    assert s.writes==[m.IDENTITY] and s.closed==[991]
    rows=[json.loads(x) for x in (m.RUN/'stock-identity.jsonl').read_bytes().splitlines()]
    assert [r['event'] for r in rows]==['identity_intent','identity_write_returned','identity_response','identity_observed']
    assert rows[-1]['checksum_exception'] and rows[-1]['boot_cause_proven'] is False

@pytest.mark.parametrize('fault',['partial','eagain','wrong','checksum','oversize','eof','topology','fd','capture','source','stale','timeout'])
def test_identity_failure_never_retries(identity,monkeypatch,fault):
    s=identity;m=s.m
    if fault in ('partial','eagain'):s.write_fault=fault
    elif fault=='wrong':s.reply=m.KNOWN_092.replace(b'\x19',b'\x18',1)
    elif fault=='checksum':s.reply=m.KNOWN_092[:-2]+b'\x07\xf7'
    elif fault=='oversize':s.reply=b'a'*65537
    elif fault=='eof':s.reply=b''
    elif fault in ('topology','fd'):s.drift=fault
    elif fault=='capture':monkeypatch.setattr(m,'capture_alive',lambda _:(_ for _ in ()).throw(RuntimeError('dead')))
    elif fault=='source':monkeypatch.setattr(m,'packet_check',lambda:(_ for _ in ()).throw(ValueError('source drift')))
    elif fault=='stale':monkeypatch.setattr(m.select,'select',lambda *a:([991],[],[]))
    else:
        ticks=iter([0,4]);monkeypatch.setattr(m.time,'monotonic',lambda:next(ticks))
    with pytest.raises((ValueError,OSError,RuntimeError)):m.identity_once(s.bridge,s.usb,decoder,s.capture)
    assert len(s.writes)<=1 and s.closed==[991]
    if fault in ('source','topology','fd','capture','stale'):assert not s.writes

@pytest.mark.parametrize('fault',['none','exited','pgid','command','children','cat_group','cat_command','fd'])
def test_owned_capture_proc_checks(monkeypatch,fault):
    m=module();process=SimpleNamespace(pid=42,poll=lambda:0 if fault=='exited' else None)
    files={'/proc/42/cmdline':b'/usr/bin/timeout\x00300\x00/bin/cat\x00/sys/kernel/debug/usb/usbmon/1u\x00',
        '/proc/42/task/42/children':b'43', '/proc/43/cmdline':b'/bin/cat\x00/sys/kernel/debug/usb/usbmon/1u\x00'}
    if fault=='command':files['/proc/42/cmdline']=b'other'
    if fault=='children':files['/proc/42/task/42/children']=b'43 44'
    if fault=='cat_command':files['/proc/43/cmdline']=b'other'
    monkeypatch.setattr(m,'read',lambda p,limit:files[str(p)])
    monkeypatch.setattr(m.os,'getpgid',lambda pid:0 if (fault=='pgid' and pid==42) or (fault=='cat_group' and pid==43) else 42)
    monkeypatch.setattr(m.Path,'iterdir',lambda p:iter([Path('/proc/43/fd/5')]))
    monkeypatch.setattr(m.os,'readlink',lambda p:'other' if fault=='fd' else '/sys/kernel/debug/usb/usbmon/1u')
    if fault=='none':assert m.capture_alive(process)==dict(timeout_pid=42,cat_pid=43,process_group=42,open_capture_fd=True)
    else:
        with pytest.raises((ValueError,RuntimeError)):m.capture_alive(process)

@pytest.mark.parametrize('fault',['none','missing','duplicate','different_usb','malformed'])
def test_midi_unique_same_port_topology(monkeypatch,fault):
    m=module();target=Path('/private/sysfs/1-1');sound=Path('/sys/class/sound/midiC1D0')
    hits=[sound]
    if fault=='missing':hits=[]
    elif fault=='duplicate':hits.append(Path('/sys/class/sound/midiC2D0'))
    elif fault=='malformed':hits=[Path('/sys/class/sound/midiC1D0extra')]
    monkeypatch.setattr(m.Path,'glob',lambda p,pattern:iter(hits))
    def resolved(path,**kwargs):
        if path==Path('/sys/bus/usb/devices/1-1'):return target
        return (Path('/private/other') if fault=='different_usb' else target)/'interface/alsa'
    monkeypatch.setattr(m.Path,'resolve',resolved)
    if fault=='none':assert m.midi_for(dict(path='1-1'))==Path('/dev/snd/midiC1D0')
    else:
        with pytest.raises(ValueError):m.midi_for(dict(path='1-1'))

def test_stderr_cleanup_fsync_failure_invalidates_wrapper_success(model,monkeypatch):
    m=model.m;original=m.os.fsync
    def fsync(fd):
        if m.os.readlink('/proc/self/fd/'+str(fd))==str(m.RUN/'usbmon1.stderr'):raise OSError('Modeled final stderr fsync failure')
        return original(fd)
    monkeypatch.setattr(m.os,'fsync',fsync)
    with pytest.raises(OSError,match='stderr fsync'):m.main()
    assert len(model.calls)==len(model.identity)==1
    assert (m.RUN/'wrapper-cleanup-ambiguous.json').exists() and not (m.RUN/'capture-stop.json').exists()



@pytest.mark.parametrize('fault',['ready','late','timeout','changed','capture','duplicate'])
def test_bounded_passive_midi_readiness(monkeypatch,fault):
    m=module();usb=dict(path='1-1',busnum='1',devnum='11',vid='4c4a',pid='c755')
    calls=[];ticks=iter(range(0,100,2))
    monkeypatch.setattr(m.time,'monotonic',lambda:next(ticks))
    monkeypatch.setattr(m.time,'sleep',lambda _:None)
    monkeypatch.setattr(m.os,'write',lambda *a:pytest.fail('Readiness sent a device command'))
    def alive(capture):
        if fault=='capture':raise RuntimeError('capture ended')
    monkeypatch.setattr(m,'capture_alive',alive)
    bridge=SimpleNamespace(usb_snapshot=lambda _:dict(usb,devnum='12') if fault=='changed' else dict(usb))
    def midi(binding):
        assert binding==usb;calls.append(binding)
        if fault in ('timeout','duplicate') or (fault=='late' and len(calls)<3):
            raise ValueError('Endpoint absent or ambiguous')
        return Path('/dev/snd/midiC2D0')
    monkeypatch.setattr(m,'midi_for',midi)
    if fault in ('ready','late'):
        assert m.wait_for_midi(bridge,usb,object())==Path('/dev/snd/midiC2D0')
        assert len(calls)==(1 if fault=='ready' else 3)
    else:
        with pytest.raises((ValueError,RuntimeError)):m.wait_for_midi(bridge,usb,object())
        assert len(calls)<=5

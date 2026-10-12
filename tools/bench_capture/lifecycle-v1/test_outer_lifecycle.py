"""Source-control models only. No canonical factory or device authority substituted.

Temporary orchestrator source pins bind tiny failure emitters for adoption paths;
successor capture body is compiled unchanged from AST after the real-factory prelude.
These models deliberately expose source gaps, rather than assert physical cleanup.
"""
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import types
import shutil
import pytest

HERE=Path(__file__).parent
PINS=json.loads((HERE/'source-pins.json').read_text())

def load(name):
    path=HERE/name
    assert hashlib.sha256(path.read_bytes()).hexdigest()==PINS[name]
    spec=importlib.util.spec_from_file_location('model_'+name.replace('.','_').replace('-','_'),path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def j(path):return json.loads(path.read_text())
def put(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value)+'\n')

class Clock:
    def __init__(self):self.now=1000.
    def time(self):return self.now
    def monotonic(self):return self.now
    def sleep(self,n):self.now+=n

class Capture:
    def __init__(self):self.pid=81001;self.returncode=None;self.waits=[];self.wait_error=None
    def poll(self):return self.returncode
    def wait(self,timeout):
        self.waits.append(timeout)
        if self.wait_error:raise self.wait_error
        self.returncode=-15;return -15

class ProcModel:
    """Real regular proc-shaped files; only proc paths/PGIDs/FD links are modeled."""
    def __init__(self,m,tmp,monkeypatch):
        self.m=m;self.cap=Capture();self.parent=71000;self.reader=81002
        self.proc=tmp/'proc';self.out=tmp/'out';self.err=tmp/'err';self.out.write_bytes(b'captured');self.err.write_bytes(b'')
        self.groups={81001:81001,81002:81001};self.links={};self.signals=[]
        self.clock=Clock();monkeypatch.setattr(m,'time',self.clock)
        actual_path=Path
        def routed(value,*parts):
            p=actual_path(value,*parts)
            if str(p)=='/proc':return self.proc
            return p
        monkeypatch.setattr(m,'Path',routed)
        monkeypatch.setattr(m.os,'getpid',lambda:self.parent)
        def pgid(pid):
            if pid not in self.groups:raise ProcessLookupError(pid)
            return self.groups[pid]
        monkeypatch.setattr(m.os,'getpgid',pgid)
        original_readlink=os.readlink
        monkeypatch.setattr(m.os,'readlink',lambda p:self.links[str(p)] if str(p) in self.links else original_readlink(p))
        monkeypatch.setattr(m.os,'killpg',lambda pg,sig:self.signals.append((pg,sig)))
        self.file(81001,'status','PPid:\t71000\n')
        self.file(81002,'status','PPid:\t81001\n')
        self.file(81001,'cmdline',b'/usr/bin/timeout\x001800s\x00/usr/bin/cat\x00'+m.USBMON.encode()+b'\x00')
        self.file(81002,'cmdline',b'/usr/bin/cat\x00'+m.USBMON.encode()+b'\x00')
        self.file(81001,'task/81001/children','81002 ')
        for pid,fd,link in [(81002,'3',m.USBMON),(81001,'1',str(self.out)),(81001,'2',str(self.err))]:
            p=self.proc/str(pid)/'fd'/fd;p.parent.mkdir(parents=True,exist_ok=True);p.touch();self.links[str(p)]=link
        # A wait represents leader reaping; group disappearance remains independent.
        original_wait=self.cap.wait
        def wait(timeout):
            rc=original_wait(timeout)
            if not getattr(self,'linger',False):
                self.groups.clear()
                for pid in (81001,81002):
                    if pid != getattr(self,'escaped',None):shutil.rmtree(self.proc/str(pid),ignore_errors=True)
            if getattr(self,'escaped',None):self.groups[self.escaped]=999
            if getattr(self,'non_sigterm',False):self.cap.returncode=0;return 0
            return rc
        self.cap.wait=wait
    def file(self,pid,name,value):
        p=self.proc/str(pid)/name;p.parent.mkdir(parents=True,exist_ok=True)
        if isinstance(value,bytes):p.write_bytes(value)
        else:p.write_text(value)

@pytest.mark.parametrize('drift',['none','leader_parent','leader_group','leader_argv','children','reader_parent','reader_group','reader_argv','reader_fd','stdout_fd','stderr_fd','extra_group','leader_exit'])
def test_actual_capture_identity_proc_contract(tmp_path,monkeypatch,drift):
    m=load('orchestrate-entry-backup.py');p=ProcModel(m,tmp_path,monkeypatch)
    if drift=='leader_parent':p.file(81001,'status','PPid: 123\n')
    if drift=='leader_group':p.groups[81001]=9
    if drift=='leader_argv':p.file(81001,'cmdline',b'other\0')
    if drift=='children':p.file(81001,'task/81001/children','81002 81003')
    if drift=='reader_parent':p.file(81002,'status','PPid: 123\n')
    if drift=='reader_group':p.groups[81002]=9
    if drift=='reader_argv':p.file(81002,'cmdline',b'other\0')
    if drift=='reader_fd':p.links[str(p.proc/'81002/fd/3')]='other'
    if drift=='stdout_fd':p.links[str(p.proc/'81001/fd/1')]='other'
    if drift=='stderr_fd':p.links[str(p.proc/'81001/fd/2')]='other'
    if drift=='extra_group':p.groups[81003]=81001;(p.proc/'81003').mkdir()
    if drift=='leader_exit':p.cap.returncode=124
    if drift=='none':
        ident=m.capture_identity(p.cap,p.out,p.err);assert ident['timeout_ppid']==71000 and ident['group_members']==[81001,81002]
    else:
        with pytest.raises(RuntimeError):m.capture_identity(p.cap,p.out,p.err)
    assert p.signals==[] and p.cap.waits==[]

@pytest.mark.parametrize('outcome',['clean','reader_lingers','escaped_reader','leader_pid_lingers','non_sigterm','wait_timeout','identity_changed','leader_exit'])
def test_actual_stop_requires_matching_owned_group_absent(tmp_path,monkeypatch,outcome):
    m=load('orchestrate-entry-backup.py');p=ProcModel(m,tmp_path,monkeypatch)
    opened=m.capture_identity(p.cap,p.out,p.err)
    if outcome=='reader_lingers':p.linger=True
    if outcome=='escaped_reader':p.escaped=81002
    if outcome=='leader_pid_lingers':p.escaped=81001
    if outcome=='non_sigterm':p.non_sigterm=True
    if outcome=='wait_timeout':p.cap.wait_error=subprocess.TimeoutExpired('capture',8)
    if outcome=='identity_changed':opened['reader_pid']=999
    if outcome=='leader_exit':p.cap.returncode=124
    if outcome=='clean':
        stopped=m.stop_capture(p.cap,p.out,p.err,opened)
        assert stopped['leader_and_reader_absent'] and stopped['returncode']==-15 and p.groups=={}
    else:
        with pytest.raises((RuntimeError,subprocess.TimeoutExpired)):m.stop_capture(p.cap,p.out,p.err,opened)
    assert len(p.signals)==(0 if outcome in ('identity_changed','leader_exit') else 1)
    assert p.cap.waits==([] if outcome in ('identity_changed','leader_exit') else [8])


def model_temporary_root(m,monkeypatch,directories=()):
    """Model UID/ownership only for exact disposable dirs; actual guards execute."""
    monkeypatch.setattr(m.os,'geteuid',lambda:0)
    if directories:
        owned=set(directories);real_lstat=Path.lstat
        def lstat(path,*args,**kwargs):
            info=real_lstat(path,*args,**kwargs)
            if path in owned:
                values=list(info);values[4]=0 # st_uid in os.stat_result
                return os.stat_result(values)
            return info
        monkeypatch.setattr(Path,'lstat',lstat)

def temporary_orchestrator(m,tmp,monkeypatch,branch):
    """Bind real preflight to exact temporary sources, never a production factory."""
    root=tmp/'entry';root.mkdir(mode=0o700);er=root/'entry-once';er.mkdir(mode=0o700)
    model_temporary_root(m,monkeypatch,(root,))
    for attr,rel in [('ROOT','.'),('RUN','initial-entry-backup-v3-2'),('ENTRY_SOURCE','entry-once/entry.py'),('PREPARE_SOURCE','prepare.py'),('BACKUP_SOURCE','backup.py'),('READER_SOURCE','reader.py')]:monkeypatch.setattr(m,attr,root/rel)
    cap=Capture();calls=[];clock=Clock();monkeypatch.setattr(m,'time',clock)
    # Only failure/adoption emitters, deliberately no normal/ROM/device operations.
    source="import subprocess\n"
    if branch=='before_proc':source+="raise OSError('entry before capture')\n"
    else:
        source+="proc=subprocess.Popen(['modeled-owned-capture'])\n"
        if branch=='after_proc':source+="raise OSError('entry after capture')\n"
        elif branch=='unexpected_return':source+="pass\n"
        elif branch=='string_exit':source+="raise SystemExit('invalid')\n"
        else:source+="raise SystemExit("+('1' if branch=='nonzero_entry' else '0')+")\n"
    m.ENTRY_SOURCE.write_text(source)
    for attr in ('PREPARE_SOURCE','BACKUP_SOURCE','READER_SOURCE'):getattr(m,attr).write_text('# temporary non-device source\n')
    for pathattr,pinattr in [('ENTRY_SOURCE','ENTRY_SHA'),('PREPARE_SOURCE','PREPARE_SHA'),('BACKUP_SOURCE','BACKUP_SHA'),('READER_SOURCE','READER_SHA')]:monkeypatch.setattr(m,pinattr,m.sha_bytes(getattr(m,pathattr).read_bytes()))
    pins={'entry-once/entry.py':m.ENTRY_SHA,'prepare.py':m.PREPARE_SHA,'backup.py':m.BACKUP_SHA,'reader.py':m.READER_SHA};put(root/'pins.json',pins);monkeypatch.setattr(m,'PINS_SHA',m.sha_bytes((root/'pins.json').read_bytes()))
    put(root/'inputs/normal-binding.json',dict(kind='fm1-passive-normal-binding',schema=1,speed='12',midi_path='/modeled/midi',observed_at=1000))
    capout=er/'usbmon1.txt';caperr=er/'usbmon1.stderr'
    opened=dict(timeout_pid=cap.pid,timeout_ppid=os.getpid(),reader_pid=81002,process_group=cap.pid,endpoint=m.USBMON)
    class ModelPopen(Capture):
        def __init__(self,*a,**kw):self.__dict__=cap.__dict__;calls.append(('capture',a[0]));capout.write_bytes(b'usbmon model');caperr.write_bytes(b'')
    def popen_side_receipts():
        put(er/'entry-exit.json',dict(exit_code=1 if branch=='nonzero_entry' else 0,capture_running=True))
        put(er/'capture-pid.json',dict(pid=cap.pid,argv=['/usr/bin/timeout','1800s','/usr/bin/cat',m.USBMON],stop_deadline=2599 if branch=='deadline' else 2800))
        put(er/'capture-open.json',opened);(er/'entry.jsonl').write_text('{}\n')
    old_init=ModelPopen.__init__
    def init(self,*a,**kw):old_init(self,*a,**kw);popen_side_receipts()
    ModelPopen.__init__=init
    monkeypatch.setattr(m,'subprocess',types.SimpleNamespace(Popen=ModelPopen,DEVNULL=subprocess.DEVNULL,STDOUT=subprocess.STDOUT))
    monkeypatch.setattr(sys.modules['subprocess'],'Popen',ModelPopen)
    # Actual ownership predicate is separately tested against proc-shaped files above.
    monkeypatch.setattr(m,'capture_identity',lambda *a,**kw:opened.copy())
    monkeypatch.setattr(m,'wait_for_entry_rom_sg',lambda *a,**kw:{'passive_sysfs_only':True})
    def stop(c,*args):calls.append(('stop',c.pid));c.returncode=-15;return dict(returncode=-15,leader_and_reader_absent=True)
    monkeypatch.setattr(m,'stop_capture',stop)
    synced=[];real_fsync=os.fsync;real_link=os.readlink
    def fsync(fd):
        try:synced.append(real_link('/proc/self/fd/'+str(fd)))
        except OSError:pass
        return real_fsync(fd)
    monkeypatch.setattr(m.os,'fsync',fsync)
    def run(argv,**kwargs):
        calls.append(('child',argv,kwargs['timeout']));kwargs['stdout'].write(b'partial child stdout')
        phase='prep' if argv[-1]==str(m.PREPARE_SOURCE) else 'backup'
        if branch==phase+'_timeout':raise subprocess.TimeoutExpired(argv,kwargs['timeout'])
        if branch==phase+'_oserror':raise OSError('child exec')
        return types.SimpleNamespace(returncode=1 if branch==phase+'_nonzero' else 0)
    m.subprocess.run=run
    monkeypatch.setattr(sys,'argv',['orchestrate','--reviewed-self-sha256',m.sha_bytes(Path(m.__file__).read_bytes())])
    return root,calls,synced

@pytest.mark.parametrize('branch',['before_proc','after_proc','unexpected_return','string_exit','nonzero_entry','deadline','prep_timeout','prep_oserror','prep_nonzero','backup_timeout','backup_oserror','backup_nonzero'])
def test_actual_orchestrator_main_failure_adoption_and_no_retry(tmp_path,monkeypatch,branch):
    m=load('orchestrate-entry-backup.py');root,calls,synced=temporary_orchestrator(m,tmp_path,monkeypatch,branch)
    with pytest.raises((RuntimeError,OSError,subprocess.TimeoutExpired)):m.main()
    run=m.RUN;assert (run/'wrapper-attempt.json').exists() and (run/'wrapper-stopped-ambiguous.json').exists() and not (run/'result.json').exists()
    assert j(run/'wrapper-stopped-ambiguous.json')['retry'] is False
    stops=[v for v in calls if v[0]=='stop'];assert len(stops)==(0 if branch=='before_proc' else 1)
    children=[v for v in calls if v[0]=='child'];assert len(children)==(2 if branch.startswith('backup_') else 1 if branch.startswith('prep_') else 0)
    if children:assert [v[2] for v in children]==([60,1500] if len(children)==2 else [60])
    if branch.endswith(('timeout','oserror')):
        name='backup-execution.stdout' if branch.startswith('backup_') else 'backup-preparation.stdout'
        assert (run/name).read_bytes()==b'partial child stdout'
        # Successor guarantees durable partial output before outer ambiguity publication.
        assert str(run/name) in synced
    with pytest.raises(ValueError,match='prior|one-shot'):m.main()
    assert len([v for v in calls if v[0]=='stop'])==len(stops)

@pytest.mark.parametrize('outcome',['success','nonzero','accepted_nonzero','exception'])
def test_sequence_command_real_child_wait_or_exception_stdout(tmp_path,monkeypatch,outcome):
    m=load('sequence-once.py');stage=tmp_path/'stage';stage.mkdir(mode=0o700);entry=tmp_path/'entry';entry.mkdir(mode=0o700);run=entry/'run';run.mkdir(mode=0o700)
    for key,value in [('STAGE',stage),('ENTRY',entry),('RUN',run)]:monkeypatch.setattr(m,key,value)
    script=stage/'child.py';script.write_text("import sys\nprint('child-evidence',flush=True)\nraise SystemExit("+('0' if outcome=='success' else '7')+")\n")
    for name in ['wire.py','root-launch-acceptance.json','partial-recovery-plan.json']:(entry/name).write_text('{}\n')
    monkeypatch.setattr(m,'WIRE_PATH',entry/'wire.py')
    closure=dict(entry_root=str(entry),unchanged_stage=str(stage),stage_files={'child.py':m.digest(script.read_bytes())},entry_files={},entry_derivatives={},inputs={});put(entry/'source-closure.json',closure)
    for key,file in [('WIRE_SHA','wire.py'),('CLOSURE_SHA','source-closure.json'),('ROOT_ACCEPTANCE_SHA','root-launch-acceptance.json'),('RECOVERY_PLAN_SHA','partial-recovery-plan.json')]:monkeypatch.setattr(m,key,m.digest((entry/file).read_bytes()))
    real_fsync=os.fsync;real_link=os.readlink;synced=[]
    def fsync(fd):
        try:synced.append(real_link('/proc/self/fd/'+str(fd)))
        except OSError:pass
        return real_fsync(fd)
    monkeypatch.setattr(m.os,'fsync',fsync)
    if outcome=='exception':
        def fail(argv,**kw):kw['stdout'].write(b'partial');raise subprocess.TimeoutExpired(argv,1)
        monkeypatch.setattr(m.subprocess,'run',fail)
    if outcome in ('exception','nonzero'):
        with pytest.raises((RuntimeError,subprocess.TimeoutExpired)):m.command('child',script)
    else:assert m.command('child',script,accept_nonzero=outcome=='accepted_nonzero')==(0 if outcome=='success' else 7)
    stdout=run/'00-child.stdout';assert str(stdout) in synced
    intent=j(run/'00-child.intent.json');assert intent['argv'][0]=='/usr/bin/python3' and intent['env']==m.ENV and intent['retry'] is False
    exitpath=run/'00-child.exit.json'
    if outcome=='exception':assert not exitpath.exists() and stdout.read_bytes()==b'partial'
    else:assert j(exitpath)['exit_status']==(0 if outcome=='success' else 7)


def test_actual_closed_sequence_cli_runs_no_child(tmp_path):
    path=HERE/'sequence-once.py';result=subprocess.run(['/usr/bin/python3','-B','-E','-s','-S',str(path),'--reviewed-self-sha256',PINS['sequence-once.py']],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode!=0 and 'Closed proposal' in result.stderr and list(tmp_path.iterdir())==[]


def capture_body(m):
    """Exact unchanged AST suffix of successor main after canonical prelude, no fake factory."""
    tree=ast.parse(Path(m.__file__).read_text());main=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='main')
    start=next(i for i,n in enumerate(main.body) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='capture' for t in n.targets))
    fn=ast.FunctionDef(name='source_capture_body',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=main.body[start:],decorator_list=[])
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),m.__file__,'exec'),m.__dict__)
    return m.source_capture_body

@pytest.mark.parametrize('mode,outcome',[(mode,outcome) for mode in ('install','boot') for outcome in ('normal','timeout','oserror','swapped_reader','reader_lingers','escaped_reader','leader_pid_lingers','group_unexpected','wait_timeout','non_sigterm','leader_early_exit')])
def test_successor_source_capture_suffix_durability_and_exact_cleanup(tmp_path,monkeypatch,mode,outcome):
    m=load('owned-install-boot-once.py');run=tmp_path/'run';run.mkdir(mode=0o700);stage=tmp_path/'stage';stage.mkdir(mode=0o700)
    m.run=run;m.stage=stage;m.cfg={'campaign_path':str(stage/'campaign.json'),'campaign_sha256':'a'*64,'adapter_sha256':'b'*64};m.a=types.SimpleNamespace(mode=mode);m.cap_seconds=900 if mode=='install' else 120;m.timeout=850 if mode=='install' else 45;m.script_name='not-device.py'
    p=ProcModel(m,tmp_path,monkeypatch);cap=p.cap
    p.file(81001,'cmdline',b'/usr/bin/timeout\x00'+str(m.cap_seconds).encode()+b'\x00/bin/cat\x00'+m.USBMON.encode()+b'\x00')
    p.file(81002,'cmdline',b'/bin/cat\x00'+m.USBMON.encode()+b'\x00')
    monkeypatch.setattr(m.subprocess,'Popen',lambda *args,**kwargs:cap)
    # Pure passive ROM observation is outside this lifecycle suffix gate.
    # No fake factory is installed: the suffix never calls a factory.
    monkeypatch.setattr(m,'observe_rom',lambda *args:None);m.factory=None;m.prepared=None
    synced=[];real_fsync=os.fsync;real_link=os.readlink
    def fsync(fd):
        try:synced.append(real_link('/proc/self/fd/'+str(fd)))
        except OSError:pass
        return real_fsync(fd)
    monkeypatch.setattr(m.os,'fsync',fsync)
    def child(argv,**kwargs):
        kwargs['stdout'].write(b'partial output');assert kwargs['timeout']==m.timeout
        if outcome=='timeout':raise subprocess.TimeoutExpired(argv,m.timeout)
        if outcome=='oserror':raise OSError('exec failed')
        if outcome=='reader_lingers':p.linger=True
        if outcome=='escaped_reader':p.escaped=81002
        if outcome=='leader_pid_lingers':p.escaped=81001
        if outcome=='non_sigterm':p.non_sigterm=True
        if outcome=='wait_timeout':cap.wait_error=subprocess.TimeoutExpired('capture',5)
        if outcome=='leader_early_exit':cap.returncode=124
        if outcome=='group_unexpected':p.groups[81003]=81001;(p.proc/'81003').mkdir()
        if outcome=='swapped_reader':
            p.file(81001,'task/81001/children','81003 ');p.file(81003,'cmdline',b'/bin/cat\x00'+m.USBMON.encode()+b'\x00');p.groups[81003]=81001
            fd=p.proc/'81003/fd/3';fd.parent.mkdir(parents=True);fd.touch();p.links[str(fd)]=m.USBMON
        return types.SimpleNamespace(returncode=0)
    monkeypatch.setattr(m.subprocess,'run',child);call=capture_body(m)
    if outcome=='normal':assert call()==0
    else:
        with pytest.raises((OSError,RuntimeError,subprocess.TimeoutExpired)):call()
    assert str(run/'execution.stdout') in synced
    stopped=run/'capture-stop.json';ambiguous=run/'wrapper-cleanup-ambiguous.json'
    if outcome in ('normal','timeout','oserror'):
        assert stopped.exists() and not ambiguous.exists() and p.groups=={}
        stop=j(stopped);keys={'time','process_group','returncode','owned_processes_only'}
        if mode=='install':keys.add('schema')
        assert set(stop)==keys and stop['returncode']==-15 and stop['owned_processes_only'] is True
        assert p.signals==[(cap.pid,signal.SIGTERM)] and cap.waits==[5]
        if outcome!='normal':assert (run/'wrapper-stopped-ambiguous.json').exists()
    else:
        assert not stopped.exists() and ambiguous.exists()
        assert j(ambiguous)['retry'] is False
        no_signal=outcome in ('swapped_reader','group_unexpected','leader_early_exit')
        assert len(p.signals)==(0 if no_signal else 1)
        assert cap.waits==([] if no_signal else [5])


def test_actual_orchestrator_rejects_nonroot_before_activity(tmp_path,monkeypatch):
    m=load('orchestrate-entry-backup.py')
    monkeypatch.setattr(m.os,'geteuid',lambda:1001)
    def forbidden(*args,**kwargs):raise AssertionError('No child before root admission')
    monkeypatch.setattr(m.subprocess,'Popen',forbidden)
    monkeypatch.setattr(m.subprocess,'run',forbidden)
    with pytest.raises(ValueError,match='Linux root required'):
        m.verify_stage(m.sha_bytes(Path(m.__file__).read_bytes()))
    assert list(tmp_path.iterdir())==[]

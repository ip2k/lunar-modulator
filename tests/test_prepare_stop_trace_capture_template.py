"""MIT. Distinct preparation-stop capture: injected lifecycle, never provenance/device proof.

Default tests require tracked source files. An explicit private template directory
may be supplied for an exact rendered derivative; absent inputs always fail.
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest


@pytest.fixture
def template():
    selected = os.environ.get('LUNAR_STOP_TRACE_CAPTURE_TEMPLATE_DIR')
    project = Path(__file__).resolve().parents[1]
    paths = ([Path(selected) / name for name in ('execute-once.py', 'execute-child.py')]
             if selected is not None else
             [project / 'tools' / name for name in ('fm1_prepare_stop_trace_capture.py', 'fm1_prepare_stop_trace_capture_child.py')])
    if any(not path.is_file() for path in paths):
        pytest.fail('Required tracked exact trace capture sources absent')
    modules = []
    for index, path in enumerate(paths):
        spec = importlib.util.spec_from_file_location('_stop_trace_capture_template_' + str(index), path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        modules.append(module)
    return modules


@pytest.fixture
def bound(template, tmp_path, monkeypatch):
    w, child = template
    stage = tmp_path / 'stage'; stage.mkdir(mode=0o700)
    run = stage / 'read'; run.mkdir(mode=0o700)
    tools = stage / 'tools'; tools.mkdir()
    members = {}
    for name, raw in {
        'read/execute-child.py': b'# synthetic unit child', 'read/campaign.json': b'{}',
        'read/preparation-stop.json': b'{}', 'read/preflight.json': b'{}',
        'tools/fm1_sdk_prepare_stop_trace_read.py': b'# synthetic unit native',
        'tools/fm1_sdk_trace_sg.py': b'# synthetic unit primitives',
        'tools/fm1_sdk_trace_read.py': b'# synthetic unit reader',
        'tools/fm1_sdk_trace_prepare_stop.py': b'# synthetic unit boot',
    }.items():
        (stage / name).write_bytes(raw); members[name] = w.digest(raw)
    (run / 'execute-once.py').write_bytes(Path(w.__file__).read_bytes())
    raw = json.dumps(members).encode(); (run / 'packet-pins.json').write_bytes(raw)
    for module in (w, child):
        module.STAGE, module.RUN = stage, run
        for key, name in [('NATIVE_SHA','tools/fm1_sdk_prepare_stop_trace_read.py'),
                          ('READER_SHA','tools/fm1_sdk_trace_read.py'),
                          ('PROOF_SHA','tools/fm1_sdk_trace_prepare_stop.py'),
                          ('CAMPAIGN_SHA','read/campaign.json'), ('STOP_SHA','read/preparation-stop.json')]:
            setattr(module, key, members[name])
    w.CHILD_SHA = members['read/execute-child.py']; w.PACKET_SHA = w.digest(raw)
    w.PACKET_MEMBERS = len(members)
    monkeypatch.setattr(w.sys, 'platform', 'linux'); monkeypatch.setattr(w.os, 'geteuid', lambda: 0)
    state = dict(children=0, captures=0, kills=0, checks=0, status=0, capture_return=-15)
    class Capture:
        pid = 435000
        returncode = None
        def poll(self): return self.returncode
        def wait(self, timeout):
            assert timeout == 5
            self.returncode = state['capture_return']; return self.returncode
    def popen(args, **kw):
        assert args == ['/usr/bin/timeout','60','/bin/cat','/sys/kernel/debug/usb/usbmon/1u']
        assert kw['start_new_session'] is True
        state['captures'] += 1; return Capture()
    def execute(args, **kw):
        assert args == ['/usr/bin/python3','-B','-E','-s','-S',str(run/'execute-child.py')]
        assert kw['timeout'] == 40 and kw['cwd'] == stage
        assert kw['env'] == {'PATH':'/usr/bin:/bin','LC_ALL':'C.UTF-8'}
        state['children'] += 1
        return SimpleNamespace(returncode=state['status'])
    def capture_alive(process, bus):
        assert bus == '1'
        return dict(timeout_pid=process.pid,cat_pid=435001,process_group=process.pid,open_capture_fd=True)
    def check(): state['checks'] += 1
    prepared = SimpleNamespace(read=SimpleNamespace(snapshot=b'{"usb_binding":{"busnum":"1"}}'), check=check,
        stop_sha256=w.STOP_SHA, seal=json.dumps({'preparation_stop_path':str(run/'preparation-stop.json')}).encode())
    native = SimpleNamespace(READ_SOURCE_SHA=w.READER_SHA, PROOF_SOURCE_SHA=w.PROOF_SHA, prepare_campaign=lambda p: prepared)
    monkeypatch.setattr(w, 'load', lambda p,pin,name: native)
    monkeypatch.setattr(w, 'capture_alive', capture_alive)
    monkeypatch.setattr(w.subprocess, 'Popen', popen); monkeypatch.setattr(w.subprocess, 'run', execute)
    monkeypatch.setattr(w.os, 'killpg', lambda p,s: state.__setitem__('kills',state['kills']+1))
    return w, child, state, prepared, members


@pytest.mark.parametrize('mismatch', ['hash', 'path'])
def test_canonical_stop_mismatch_blocks_before_capture(bound, mismatch):
    w, _, state, prepared, _ = bound
    if mismatch == 'hash':
        prepared.stop_sha256 = '0' * 64
    else:
        prepared.seal = json.dumps({'preparation_stop_path': str(w.RUN / 'other-stop.json')}).encode()
    with pytest.raises(ValueError, match='must match canonical reader evidence'):
        w.main()
    assert state['captures'] == state['children'] == 0
    assert not (w.RUN / 'wrapper-attempt.json').exists()


@pytest.mark.parametrize('index',[0,1])
def test_default_closed_before_files_processes_or_devices(template,monkeypatch,index):
    module=template[index]
    monkeypatch.setattr(module.os,'open',lambda *a,**k:pytest.fail('open before closure'))
    with pytest.raises(ValueError,match='Closed'): module.main()


@pytest.mark.parametrize('pin',['PACKET_SHA','NATIVE_SHA','READER_SHA','PROOF_SHA','CHILD_SHA','CAMPAIGN_SHA','STOP_SHA'])
def test_each_missing_activation_pin_closed(bound,pin):
    w,_,state,_,_=bound; setattr(w,pin,None)
    with pytest.raises(ValueError,match='Closed'):w.main()
    assert state['children']==state['captures']==0


@pytest.mark.parametrize('status',[0,1,2,-15])
def test_one_child_owned_cleanup_publishes_without_upgrading_exit(bound,status):
    w,_,state,_,_=bound; state['status']=status
    assert w.main()==status
    assert state['children']==state['captures']==state['kills']==1
    exit_record=json.loads((w.RUN/'execution-exit.json').read_bytes())
    assert exit_record['exit_status']==status and exit_record['read_completion_attested'] is False
    envelope=json.loads((w.RUN/'owned-capture.json').read_bytes())
    assert set(envelope['wrapper_files_sha256'])==set(w.OWNED_FILES)
    for name,pin in envelope['wrapper_files_sha256'].items():assert w.digest((w.RUN/name).read_bytes())==pin
    assert json.loads((w.RUN/'capture-stop.json').read_bytes())['returncode']==-15
    with pytest.raises(ValueError,match='already attempted'):w.main()
    assert state['children']==1


@pytest.mark.parametrize('artifact',['wrapper-attempt.json','capture-open.json','owned-capture.json','wrapper-cleanup-ambiguous.json'])
def test_existing_or_dangling_artifact_blocks_all_capture(bound,artifact):
    w,_,state,_,_=bound;(w.RUN/artifact).symlink_to(w.RUN/'absent')
    with pytest.raises(ValueError,match='already attempted'):w.main()
    assert state['captures']==state['children']==0


@pytest.mark.parametrize('returncode',[0,1,-9])
def test_wrong_capture_terminal_status_preserves_ambiguity(bound,returncode):
    w,_,state,_,_=bound;state['capture_return']=returncode
    with pytest.raises(ValueError,match='terminal status'):w.main()
    assert state['children']==1 and (w.RUN/'wrapper-cleanup-ambiguous.json').is_file()
    assert not (w.RUN/'owned-capture.json').exists()


def test_child_timeout_never_retries_and_cleans_owned_capture(bound,monkeypatch):
    w,_,state,_,_=bound
    def timeout(*a,**kw):
        state['children']+=1;raise subprocess.TimeoutExpired(a[0],40)
    monkeypatch.setattr(w.subprocess,'run',timeout)
    with pytest.raises(subprocess.TimeoutExpired):w.main()
    assert state['children']==state['captures']==state['kills']==1
    assert (w.RUN/'wrapper-stopped-ambiguous.json').is_file() and (w.RUN/'capture-stop.json').is_file()
    assert not (w.RUN/'owned-capture.json').exists()


def test_source_drift_after_durable_open_receipt_blocks_child(bound,monkeypatch):
    w,_,state,_,_=bound;original=w.save
    def save(path,value):
        original(path,value)
        if path.name=='capture-open.json':(w.STAGE/'tools/fm1_sdk_prepare_stop_trace_read.py').write_bytes(b'changed')
    monkeypatch.setattr(w,'save',save)
    with pytest.raises(ValueError,match='packet member'):w.main()
    assert state['children']==0 and state['captures']==state['kills']==1
    assert not (w.RUN/'owned-capture.json').exists()


@pytest.mark.parametrize('fault',['extra','missing','traversal','absolute','changed','bool-count'])
def test_exact_packet_member_inventory(bound,fault):
    w,_,state,_,members=bound
    if fault=='extra':members['read/unknown']=w.digest(b'')
    elif fault=='missing':members.pop('tools/fm1_sdk_trace_read.py')
    elif fault=='traversal':members['../unknown']=members.pop('read/preflight.json')
    elif fault=='absolute':members[str(w.RUN/'preflight.json')]=members.pop('read/preflight.json')
    elif fault=='changed':(w.RUN/'preflight.json').write_bytes(b'changed')
    else:w.PACKET_MEMBERS=True
    raw=json.dumps(members).encode();(w.RUN/'packet-pins.json').write_bytes(raw);w.PACKET_SHA=w.digest(raw)
    with pytest.raises(ValueError):w.main()
    assert state['children']==state['captures']==0


@pytest.mark.parametrize('kind',['link','fifo','dir','oversized'])
def test_bounded_direct_evidence_reader(template,tmp_path,kind):
    w,_=template;p=tmp_path/'input'
    if kind=='link':p.symlink_to(tmp_path/'missing')
    elif kind=='fifo':os.mkfifo(p)
    elif kind=='dir':p.mkdir()
    else:p.write_bytes(b'12345')
    with pytest.raises((ValueError,OSError)):w.read(p,4)


def test_stderr_refuses_owned_envelope_after_cleanup(bound,monkeypatch):
    w,_,state,_,_=bound;original=w.capture_alive
    def alive(p,bus):
        if state['children']:(w.RUN/'usbmon.stderr').write_bytes(b'capture warning')
        return original(p,bus)
    monkeypatch.setattr(w,'capture_alive',alive)
    with pytest.raises(ValueError,match='lifecycle ambiguous'):w.main()
    assert state['children']==state['kills']==1 and not(w.RUN/'owned-capture.json').exists()


@pytest.mark.parametrize('fault',['none','exited','parent-group','parent-command','children-zero',
    'children-two','child-group','child-command','extra-parent-arg','extra-child-arg','fd-missing','fd-raced'])
def test_actual_owned_process_inspection_is_bounded(template,monkeypatch,fault):
    w,_=template
    process=SimpleNamespace(pid=435000,poll=lambda:None if fault!='exited' else 0)
    target='/sys/kernel/debug/usb/usbmon/1u'
    parent=b'/usr/bin/timeout\0' + b'60\0/bin/cat\0'+target.encode()+b'\0'
    child=b'/bin/cat\0'+target.encode()+b'\0'
    if fault=='parent-command':parent=b'other\0'
    if fault=='child-command':child=b'other\0'
    if fault=='extra-parent-arg':parent+=b'extra\0'
    if fault=='extra-child-arg':child+=b'extra\0'
    contents={ '/proc/435000/cmdline':parent, '/proc/435001/cmdline':child,
        '/proc/435000/task/435000/children': b'' if fault=='children-zero' else
        b'435001 435002' if fault=='children-two' else b'435001' }
    def read(path,limit):
        assert limit==65536
        return contents[str(path)]
    def pgid(pid):
        if (pid==435000 and fault=='parent-group') or (pid==435001 and fault=='child-group'):return 1
        assert pid in (435000,435001);return 435000
    monkeypatch.setattr(w,'read',read);monkeypatch.setattr(w.os,'getpgid',pgid)
    monkeypatch.setattr(Path,'iterdir',lambda p:iter([p/'4',p/'5']) if str(p)=='/proc/435001/fd' else pytest.fail('unbounded proc traversal'))
    def readlink(path):
        if fault=='fd-raced' and path.name=='4':raise FileNotFoundError
        return target if fault not in ('fd-missing','fd-raced') and path.name=='4' else 'pipe:123'
    monkeypatch.setattr(w.os,'readlink',readlink)
    if fault=='none':
        assert w.capture_alive(process,'1')==dict(timeout_pid=435000,cat_pid=435001,process_group=435000,open_capture_fd=True)
    else:
        with pytest.raises((ValueError,RuntimeError)):w.capture_alive(process,'1')


def test_unprovable_capture_ownership_does_not_signal_arbitrary_group(bound,monkeypatch):
    w,_,state,_,_=bound;calls=0;original=w.capture_alive
    def alive(p,b):
        nonlocal calls
        calls+=1
        if calls>2:raise RuntimeError('ownership lost')
        return original(p,b)
    monkeypatch.setattr(w,'capture_alive',alive)
    with pytest.raises(RuntimeError,match='ownership lost'):w.main()
    assert state['children']==1 and state['kills']==0
    assert (w.RUN/'wrapper-cleanup-ambiguous.json').is_file()
    assert not(w.RUN/'owned-capture.json').exists()

"""Pure exact-source/capture kernel tests; no Prepared/factory authority granted.

Both wrappers must be supplied as real pinned read-only files on Hera. Lifecycle
receipts below are explicitly modeled; this is not owned-process acceptance.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

HISTORICAL = '7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b'
SUCCESSOR = '59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d'


@pytest.fixture(scope='module')
def adapter():
    path = Path(os.environ.get('LUNAR_PARTIAL_CAPTURE_CANDIDATE',
                               str(Path(__file__).with_name('fm1_retained_partial_recovery.py'))))
    spec = importlib.util.spec_from_file_location('_actual_capture_allowlist_candidate', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.INSTALL_CAPTURE_SHA == HISTORICAL
    assert module.INSTALL_CAPTURE_SUCCESSOR_SHA == SUCCESSOR
    return module


@pytest.fixture(params=['historical', 'successor'])
def reviewed_wrapper(request):
    variable = {'historical': 'LUNAR_PARTIAL_INSTALL_CAPTURE',
                'successor': 'LUNAR_PARTIAL_INSTALL_CAPTURE_SUCCESSOR'}[request.param]
    path = Path(os.environ[variable])
    expected = HISTORICAL if request.param == 'historical' else SUCCESSOR
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == expected
    return expected, data


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')
    return path


def envelope(tmp_path, reviewed_wrapper):
    expected, data = reviewed_wrapper
    wrapper = tmp_path / 'arbitrary-wrapper-name.py'
    wrapper.write_bytes(data)
    stage = tmp_path / 'stage'; stage.mkdir()
    tools = stage / 'tools'; tools.mkdir()
    module = tools / 'adapter.py'; module.write_bytes(b'# modeled lifecycle source\n')
    campaign = stage / 'campaign.json'; campaign.write_bytes(b'{}\n')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    csha, asha = sha(campaign), sha(module)
    usb = dict(path='1-1', busnum='1', devnum='6', vid='4c4a', pid='8057')
    kind = 'fm1-sdk-trace-install-one-shot'
    run = tmp_path / 'capture'; run.mkdir(mode=0o700)
    packet = write(tmp_path / 'packet.json', dict(schema=1, kind=kind,
        campaign_path=str(campaign), campaign_sha256=csha,
        adapter_path=str(module), adapter_sha256=asha,
        source_pins={'tools/adapter.py': asha}, usb_binding=usb))
    write(run / 'wrapper-attempt.json', dict(schema=1,kind=kind,time=1,
        campaign_sha256=csha,adapter_sha256=asha,retry=False))
    write(run / 'capture-open.json', dict(schema=1,time=2,
        timeout_pid=5001,cat_pid=5002,process_group=5001,open_capture_fd=True))
    write(run / 'execution-exit.json', dict(schema=1,time=7,
        child_started_at=3,child_finished_at=6,exit_status=1,
        campaign_sha256=csha,adapter_sha256=asha,capture_alive_after_child=True,retry=False))
    write(run / 'capture-stop.json', dict(schema=1,time=8,
        process_group=5001,returncode=-15,owned_processes_only=True))
    (run / 'execution.stdout').write_bytes(b'explicitly modeled child\n')
    (run / 'usbmon1.stderr').write_bytes(b'')
    (run / 'usbmon1.txt').write_bytes(b'explicitly modeled capture\n')
    inputs = dict(wrapper_path=str(wrapper),packet_path=str(packet),run=str(run))
    args = dict(kind=kind,campaign_sha=csha,adapter_sha=asha,
                usb=json.dumps(usb,sort_keys=True,separators=(',',':')).encode(),times=(4,5),exit_status=1)
    return expected, wrapper, inputs, args


def test_both_exact_versions_keep_capture_grammar(tmp_path, adapter, reviewed_wrapper):
    expected, wrapper, inputs, args = envelope(tmp_path, reviewed_wrapper)
    frozen = adapter._Frozen()
    selected = adapter.install_capture_pin(frozen, inputs)
    assert selected == expected
    assert frozen.files[wrapper][0] == reviewed_wrapper[1]
    assert adapter.capture(frozen,inputs,pin=selected,**args) == b'explicitly modeled capture\n'
    frozen.check(False)


def test_late_wrapper_drift_rejected_before_capture(tmp_path, adapter, reviewed_wrapper):
    _, wrapper, inputs, args = envelope(tmp_path, reviewed_wrapper)
    frozen = adapter._Frozen(); selected = adapter.install_capture_pin(frozen,inputs)
    wrapper.write_bytes(reviewed_wrapper[1] + b'\n# changed\n')
    with pytest.raises(ValueError): adapter.capture(frozen,inputs,pin=selected,**args)
    with pytest.raises(ValueError,match='changed'): frozen.check(False)


@pytest.mark.parametrize('data',[b'',HISTORICAL.encode(),b'# unreviewed wrapper\n'])
def test_unknown_source_rejected(tmp_path,adapter,data):
    p=tmp_path/'wrapper.py';p.write_bytes(data)
    with pytest.raises(ValueError,match='Unreviewed'):
        adapter.install_capture_pin(adapter._Frozen(),dict(wrapper_path=str(p),packet_path='unused',run='unused'))


def test_altered_exact_source_rejected(tmp_path,adapter,reviewed_wrapper):
    p=tmp_path/'wrapper.py';p.write_bytes(reviewed_wrapper[1]+b'\n# changed\n')
    with pytest.raises(ValueError,match='Unreviewed'):
        adapter.install_capture_pin(adapter._Frozen(),dict(wrapper_path=str(p),packet_path='unused',run='unused'))


def test_caller_hash_is_not_an_input(tmp_path,adapter):
    inputs=dict(wrapper_path=str(tmp_path/'absent'),packet_path='unused',run='unused',wrapper_sha256=SUCCESSOR)
    with pytest.raises(ValueError,match='Exact owned capture paths'):
        adapter.install_capture_pin(adapter._Frozen(),inputs)


@pytest.mark.parametrize('kind',['symlink','fifo','directory','oversize'])
def test_selection_uses_bounded_direct_regular_reader(tmp_path,adapter,kind):
    p=tmp_path/'wrapper.py'
    if kind=='symlink': p.symlink_to(tmp_path/'absent')
    elif kind=='fifo': os.mkfifo(p)
    elif kind=='directory': p.mkdir()
    else: p.write_bytes(bytes(2*adapter.FLASH+1))
    with pytest.raises((OSError,ValueError)):
        adapter.install_capture_pin(adapter._Frozen(),dict(wrapper_path=str(p),packet_path='unused',run='unused'))


@pytest.mark.parametrize('artifact',['wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'])
def test_existing_ambiguity_rejected(tmp_path,adapter,artifact):
    reviewed=(SUCCESSOR,Path(os.environ['LUNAR_PARTIAL_INSTALL_CAPTURE_SUCCESSOR']).read_bytes())
    assert hashlib.sha256(reviewed[1]).hexdigest()==SUCCESSOR
    _,_,inputs,args=envelope(tmp_path,reviewed)
    (Path(inputs['run'])/artifact).write_bytes(b'{}')
    f=adapter._Frozen();selected=adapter.install_capture_pin(f,inputs)
    with pytest.raises(ValueError,match='absent'):adapter.capture(f,inputs,pin=selected,**args)


@pytest.mark.parametrize('artifact',['wrapper-stopped-ambiguous.json','wrapper-cleanup-ambiguous.json'])
def test_late_ambiguity_appearance_rejected(tmp_path,adapter,artifact):
    reviewed=(SUCCESSOR,Path(os.environ['LUNAR_PARTIAL_INSTALL_CAPTURE_SUCCESSOR']).read_bytes())
    assert hashlib.sha256(reviewed[1]).hexdigest()==SUCCESSOR
    _,_,inputs,args=envelope(tmp_path,reviewed)
    f=adapter._Frozen();selected=adapter.install_capture_pin(f,inputs)
    adapter.capture(f,inputs,pin=selected,**args)
    (Path(inputs['run'])/artifact).write_bytes(b'{}')
    with pytest.raises(ValueError,match='appeared'):f.check(False)


@pytest.mark.parametrize('file,key,value',[
    ('capture-stop.json','returncode',0),
    ('capture-stop.json','process_group',5002),
    ('execution-exit.json','retry',True),
    ('execution-exit.json','child_finished_at',4),
])
def test_unchanged_lifecycle_negatives(tmp_path,adapter,file,key,value):
    reviewed=(SUCCESSOR,Path(os.environ['LUNAR_PARTIAL_INSTALL_CAPTURE_SUCCESSOR']).read_bytes())
    assert hashlib.sha256(reviewed[1]).hexdigest()==SUCCESSOR
    _,_,inputs,args=envelope(tmp_path,reviewed)
    path=Path(inputs['run'])/file;data=json.loads(path.read_bytes());data[key]=value;write(path,data)
    f=adapter._Frozen();selected=adapter.install_capture_pin(f,inputs)
    with pytest.raises(ValueError):adapter.capture(f,inputs,pin=selected,**args)


def test_late_switch_to_other_reviewed_version_is_not_fallback(tmp_path,adapter,reviewed_wrapper):
    expected,wrapper,inputs,args=envelope(tmp_path,reviewed_wrapper)
    f=adapter._Frozen();selected=adapter.install_capture_pin(f,inputs)
    variable=('LUNAR_PARTIAL_INSTALL_CAPTURE_SUCCESSOR' if expected==HISTORICAL
              else 'LUNAR_PARTIAL_INSTALL_CAPTURE')
    other=Path(os.environ[variable]).read_bytes()
    assert hashlib.sha256(other).hexdigest()==(SUCCESSOR if expected==HISTORICAL else HISTORICAL)
    wrapper.write_bytes(other)
    with pytest.raises(ValueError,match='changed during admission'):
        adapter.install_capture_pin(f,inputs)
    with pytest.raises(ValueError):adapter.capture(f,inputs,pin=selected,**args)
    with pytest.raises(ValueError,match='changed'):f.check(False)

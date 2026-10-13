"""Modeled receipts test strict evidence classification; no factory authority."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_admitted_backup_postchild_evidence as evidence


@pytest.fixture
def retained(tmp_path, monkeypatch):
    run=tmp_path/'run';run.mkdir(mode=0o700)
    wrapper=tmp_path/'wrapper.py';wrapper.write_bytes(b'modeled source');wrapper.chmod(0o600)
    monkeypatch.setattr(evidence,'WRAPPER_SHA',evidence.digest(wrapper.read_bytes()))
    campaign='a'*64;usb={'path':'1-1','devnum':'13'}
    values={
        'wrapper-attempt.json':dict(schema=1,time=1,kind='fm1-sdk-trace-admitted-backup-one-shot',campaign_sha256=campaign,adapter_sha256=evidence.ADAPTER_SHA,usb_binding=usb,retry=False),
        'capture-open.json':dict(schema=1,time=2,process_group=40,timeout_pid=40,cat_pid=41,open_capture_fd=True),
        'execution-exit.json':dict(schema=1,time=5,child_started_at=3,child_finished_at=4,exit_status=0,campaign_sha256=campaign,adapter_sha256=evidence.ADAPTER_SHA,capture_alive_after_child=True,retry=False),
        'wrapper-stopped-ambiguous.json':dict(schema=1,time=6,error='ValueError',detail='passive SG mapping changed during campaign',retry=False),
        'capture-stop.json':dict(schema=1,time=7,process_group=40,returncode=-15,owned_processes_only=True),
    }
    def save(name,value):
        p=run/name;p.write_text(json.dumps(value));p.chmod(0o600)
    for name,value in values.items():save(name,value)
    for name in ('usbmon1.txt','usbmon1.stderr','execution.stdout'):
        p=run/name;p.write_bytes(b'modeled retained payload');p.chmod(0o600)
    return run,wrapper,campaign,usb,values,save


def test_exact_postchild_failure_remains_failure_and_grants_no_authority(retained):
    run,wrapper,campaign,usb,_,_=retained
    result=evidence.validate(run,wrapper,campaign,usb)
    assert result['capture_cleanup_verified'] is True
    for field in ('wrapper_succeeded','restore_authorized','device_io','current_connection_verified'):
        assert result[field] is False
    assert len(result['retained_sha256'])==8


@pytest.mark.parametrize('name,key,value',[
    ('wrapper-attempt.json','campaign_sha256','b'*64),
    ('wrapper-attempt.json','adapter_sha256','b'*64),
    ('wrapper-attempt.json','retry',True),
    ('wrapper-attempt.json','usb_binding',{'devnum':'14'}),
    ('capture-open.json','open_capture_fd',False),
    ('capture-open.json','process_group',True),
    ('capture-open.json','cat_pid',40),
    ('execution-exit.json','exit_status',1),
    ('execution-exit.json','exit_status',False),
    ('execution-exit.json','capture_alive_after_child',False),
    ('execution-exit.json','adapter_sha256','b'*64),
    ('execution-exit.json','retry',True),
    ('wrapper-stopped-ambiguous.json','detail','different error'),
    ('wrapper-stopped-ambiguous.json','error','RuntimeError'),
    ('wrapper-stopped-ambiguous.json','time',2),
    ('capture-stop.json','returncode',0),
    ('capture-stop.json','process_group',41),
    ('capture-stop.json','owned_processes_only',False),
    ('capture-stop.json','time',float('inf')),
])
def test_changed_lifecycle_rejected(retained,name,key,value):
    run,wrapper,campaign,usb,values,save=retained
    values[name][key]=value;save(name,values[name])
    with pytest.raises(ValueError):evidence.validate(run,wrapper,campaign,usb)


@pytest.mark.parametrize('name',['wrapper-cleanup-ambiguous.json','passive-snapshot.json'])
def test_different_outcome_rejected(retained,name):
    run,wrapper,campaign,usb,_,save=retained;save(name,{'schema':1})
    with pytest.raises(ValueError):evidence.validate(run,wrapper,campaign,usb)


@pytest.mark.parametrize('name',['wrapper-attempt.json','capture-open.json','execution-exit.json',
    'wrapper-stopped-ambiguous.json','capture-stop.json','usbmon1.txt','usbmon1.stderr','execution.stdout'])
def test_missing_receipt_rejected(retained,name):
    run,wrapper,campaign,usb,_,_=retained;(run/name).unlink()
    with pytest.raises(FileNotFoundError):evidence.validate(run,wrapper,campaign,usb)


@pytest.mark.parametrize('raw',[b'{"schema":1,"schema":1}',b'{"schema":true}',b'{"schema":1,"time":NaN}'])
def test_noncanonical_json_rejected(raw):
    with pytest.raises(ValueError):evidence.strict_json(raw)


def test_changed_wrapper_source_rejected(retained):
    run,wrapper,campaign,usb,_,_=retained;wrapper.write_bytes(b'changed source')
    with pytest.raises(ValueError,match='wrapper source'):evidence.validate(run,wrapper,campaign,usb)


def test_silent_successful_child_is_admissible(retained):
    run,wrapper,campaign,usb,_,_=retained
    (run/'execution.stdout').write_bytes(b'')
    assert evidence.validate(run,wrapper,campaign,usb)['child_exit_status']==0


def test_empty_capture_payload_rejected(retained):
    run,wrapper,campaign,usb,_,_=retained
    (run/'usbmon1.txt').write_bytes(b'')
    with pytest.raises(ValueError,match='capture payload'):evidence.validate(run,wrapper,campaign,usb)


def test_symlink_receipt_rejected(retained):
    run,wrapper,campaign,usb,_,_=retained
    p=run/'execution.stdout';p.unlink();p.symlink_to(wrapper)
    with pytest.raises(OSError):evidence.validate(run,wrapper,campaign,usb)

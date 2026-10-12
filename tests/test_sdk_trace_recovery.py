"""MIT. Closed successor mechanics; pure reader transcript/publication model."""
from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import fm1_sdk_trace_recovery_evidence as e
import fm1_sdk_trace_returned_backup as b
import fm1_sdk_trace_stock_restore as s


@pytest.fixture
def receipt():
    seal, plan = b'campaign seal', b'fixed plan'
    operations = tuple((bytes([i + 1]), b'', size) for i,size in enumerate((36,64,4,64,4)))
    inquiry = bytearray(36); inquiry[8:16] = b'WL82    '; inquiry[16:32] = b'UBOOT1.00       '
    replies = (bytes(inquiry), b'a'*64, b'b'*4, b'a'*64, b'b'*4)
    files = dict(zip(e._NAMES,replies))
    decoded = dict(classification='synthetic-unit-coherent', reset_cause_proven=False)
    def interpret(*args):
        assert args == replies[1:]
        return decoded.copy()
    result = dict(decoded, campaign_sha256=e.digest(seal),plan_sha256=e.digest(plan),
                  raw_sha256=[e.digest(v) for v in replies])
    rows = [dict(event='read_prepared',campaign_sha256=e.digest(seal),plan_sha256=e.digest(plan),
                 commands=5,upload_operations=0,reset_operations=0,flash_operations=0)]
    for i,(cdb,out,count) in enumerate(operations):
        rows.append(dict(event='submit_intent',index=i,cdb=cdb.hex(),in_len=count,out_len=0,retry=False))
        rows.append(dict(event='completion',index=i,status=0,masked=0,msg=0,host=0,driver=0,resid=0,
                         info=0,sense_len=0,sense_hex='',actual_sense_bytes=0,actual_response_bytes=count,
                         response_sha256=e.digest(replies[i]),retry=False))
    rows.append(dict(event='coherent_capture_completed',**result,retry=False))
    return dict(seal=seal,plan=plan,operations=operations,raw_files=files,interpret=interpret,
                result_raw=e.canonical(result),pending_raw=None,evaluated_at=100),rows,result


def raw(rows):
    return b'\n'.join(e.canonical(dict(time=i+1,**row)) for i,row in enumerate(rows))


def stopped():
    return dict(event='capture_stopped_ambiguous',error='OSError',retry=False,classification='inconclusive')


def verify(data,rows):
    return e.verify_read_receipt(raw(rows),**data)


def test_exact_completed_publication(receipt):
    data,rows,result=receipt
    proof=verify(data,rows)
    assert proof['outcome']=='completed' and proof['successful_completions']==5
    assert not proof['result']['reset_cause_proven']


@pytest.mark.parametrize('end',range(1,12))
def test_each_stopped_prefix_retains_only_phase_allowed_artifacts(receipt,end):
    data,rows,_=receipt
    data=dict(data,result_raw=None,raw_files={})
    assert verify(data,rows[:end]+[stopped()])['outcome']=='stopped-ambiguous'
    if end<11:
        data['raw_files']={'trace-a':b'a'*64}
        with pytest.raises(ValueError):verify(data,rows[:end]+[stopped()])


@pytest.mark.parametrize('name',e._NAMES)
def test_late_raw_publication_after_five_completions_is_hash_checked(receipt,name):
    data,rows,_=receipt
    data=dict(data,result_raw=None,raw_files={name:data['raw_files'][name]})
    assert verify(data,rows[:11]+[stopped()])['outcome']=='stopped-ambiguous'
    data['raw_files'][name]=b'x'*len(data['raw_files'][name])
    with pytest.raises(ValueError):verify(data,rows[:11]+[stopped()])


@pytest.mark.parametrize('phase',['early','all-replies','captured','completed'])
def test_pending_phase_rules(receipt,phase):
    data,rows,result=receipt
    pending=e.canonical(result)
    if phase=='early':
        data=dict(data,result_raw=None,raw_files={},pending_raw=pending)
        with pytest.raises(ValueError):verify(data,rows[:3]+[stopped()])
    elif phase=='all-replies':
        data=dict(data,result_raw=None,pending_raw=pending)
        with pytest.raises(ValueError):verify(data,rows[:11]+[stopped()])
    elif phase=='captured':
        data=dict(data,result_raw=None,pending_raw=pending)
        assert verify(data,rows+[stopped()])['outcome']=='stopped-ambiguous'
        data['pending_raw']=b'changed'
        with pytest.raises(ValueError):verify(data,rows+[stopped()])
    else:
        data=dict(data,pending_raw=pending)
        with pytest.raises(ValueError):verify(data,rows)


@pytest.mark.parametrize('field',['status','masked','msg','host','driver','resid','info','sense_len'])
def test_failed_completion_stops_publication(receipt,field):
    data,rows,_=receipt;rows[2][field]=1
    data=dict(data,result_raw=None,raw_files={})
    assert verify(data,rows[:3]+[stopped()])['outcome']=='stopped-ambiguous'
    with pytest.raises(ValueError):verify(data,rows)


@pytest.mark.parametrize('fault',['extra','index','cdb','count','retry','response','publication','later','future','bool-time'])
def test_exhaustive_sequence_and_bytes(receipt,fault):
    data,rows,_=receipt
    if fault=='extra':rows[2]['surprise']=1
    elif fault=='index':rows[1]['index']=True
    elif fault=='cdb':rows[1]['cdb']='fc12'
    elif fault=='count':rows[1]['in_len']+=1
    elif fault=='retry':rows[1]['retry']=True
    elif fault=='response':rows[2]['response_sha256']='0'*64
    elif fault=='publication':data['result_raw']=b'{}'
    elif fault=='later':rows.append(stopped())
    elif fault=='future':data['evaluated_at']=0
    else:
        payload=raw(rows).splitlines();first=json.loads(payload[0]);first['time']=True
        payload[0]=e.canonical(first)
        with pytest.raises(ValueError):e.verify_read_receipt(b'\n'.join(payload),**data)
        return
    with pytest.raises(ValueError):verify(data,rows)


@pytest.mark.parametrize('module,fn',[(e,'validate_returned_state'),(b,'prepare_campaign'),(s,'prepare_campaign')])
def test_closed_factory_never_reads_campaign_or_opens_device(monkeypatch,module,fn):
    monkeypatch.setattr(module,'read_file',lambda *a,**k:pytest.fail('read before closed gate'))
    with pytest.raises(ValueError,match='[Cc]losed|reviewed|Reviewed'):
        getattr(module,fn)('/not-a-device-campaign')


def test_copied_or_handmade_proof_has_no_authority():
    p=e.ReturnedProof(b'{}','a'*64,b'{}','b'*64,'/tmp',(),(),'c'*64,'d'*64,1,
                      'completed',(),None)
    for obj in (p,replace(p)):
        with pytest.raises(ValueError):obj.check()


@pytest.mark.parametrize('module',[e,b,s])
def test_direct_evidence_reader_rejects_symlink_and_fifo(tmp_path,module):
    source=tmp_path/'regular';source.write_bytes(b'private evidence')
    link=tmp_path/'link';link.symlink_to(source)
    import os
    fifo=tmp_path/'fifo';os.mkfifo(fifo)
    for path in (link,fifo,tmp_path,Path('relative')):
        with pytest.raises((ValueError,OSError)):module.read_file(path)


@pytest.mark.parametrize('bad_digest',[None,True,'g'*64,'A'*64,'0'*63])
def test_bad_final_digest_never_classifies_five_good_completions(receipt,bad_digest):
    data,rows,_=receipt
    rows[10]['response_sha256']=bad_digest
    data=dict(data,result_raw=None,raw_files={})
    outcome=verify(data,rows[:11]+[stopped()])
    assert outcome['outcome']=='stopped-ambiguous'
    assert outcome['successful_completions']==0
    data['raw_files']={'stage-b':b'b'*4}
    with pytest.raises(ValueError,match='before five good'):
        verify(data,rows[:11]+[stopped()])


@pytest.fixture
def capture_lifecycle():
    files={name:b'' for name in e._CAPTURE_FILES}
    files.update({'execute-once.py':b'unit closed wrapper','execute-child.py':b'unit closed child',
        'preflight.json':b'{"factory_only":true}','usbmon.txt':b'unit wire not verified'})
    expected=dict(wrapper_sha256=e.digest(files['execute-once.py']),child_sha256=e.digest(files['execute-child.py']),
        native_campaign_path='/private/stage/read/campaign.json',native_campaign_sha256='1'*64,
        boot_lineage_path='/private/stage/read/lineage.json',boot_lineage_sha256='2'*64,
        native_sha256='3'*64,reader_sha256='4'*64,boot_sha256='5'*64,
        usb_binding={'usb_path':'3-2','busnum':'3','devnum':'26'})
    attempt=dict(time=10,campaign_sha256='1'*64,lineage_sha256='2'*64,native_sha256='3'*64,
        reader_sha256='4'*64,boot_sha256='5'*64,usb_binding=expected['usb_binding'],retry=False,
        commands=5,upload_operations=0,reset_operations=0,flash_operations=0)
    records={'wrapper-attempt.json':attempt,
        'capture-open.json':dict(time=11,timeout_pid=100,cat_pid=101,process_group=100,open_capture_fd=True),
        'capture-stop.json':dict(time=15,process_group=100,returncode=-15,owned_processes_only=True),
        'execution-exit.json':dict(time=14,exit_status=0,campaign_sha256='1'*64,
            capture_alive_after_child=True,retry=False,read_completion_attested=False,recovery_proven=False,boot_cause_proven=False)}
    def publish():
        for name,value in records.items():files[name]=json.dumps(value,sort_keys=True,separators=(',',':')).encode()
        return e.canonical(dict(schema=1,kind='fm1-owned-sdk-trace-read-capture',
            native_campaign_path=expected['native_campaign_path'],native_campaign_sha256='1'*64,
            boot_lineage_path=expected['boot_lineage_path'],boot_lineage_sha256='2'*64,
            wrapper_files_sha256={name:e.digest(value) for name,value in files.items()}))
    return files,expected,records,publish


@pytest.mark.parametrize('outcome',['completed','stopped-ambiguous','consumed-pretransport-zero-cbw'])
def test_capture_lifecycle_keeps_exit_and_value_checks_separate_from_authority(capture_lifecycle,outcome):
    files,expected,records,publish=capture_lifecycle
    if outcome!='completed':records['execution-exit.json']['exit_status']=1
    times={} if outcome=='consumed-pretransport-zero-cbw' else dict(read_started=12,read_terminal=13)
    proof=e.verify_capture_lifecycle(publish(),files,expected,read_outcome=outcome,**times)
    assert proof['exit_status']==(0 if outcome=='completed' else 1)
    assert proof['wire_inventory_verified'] is False and proof['returned_proof_granted'] is False


@pytest.mark.parametrize('name,field,value',[
    ('wrapper-attempt.json','retry',True),('wrapper-attempt.json','commands',6),
    ('wrapper-attempt.json','flash_operations',1),('wrapper-attempt.json','native_sha256','6'*64),
    ('capture-open.json','timeout_pid',True),('capture-open.json','cat_pid',100),
    ('capture-open.json','process_group',101),('capture-open.json','open_capture_fd',False),
    ('capture-stop.json','process_group',101),('capture-stop.json','returncode',0),
    ('capture-stop.json','owned_processes_only',False),('capture-stop.json','time',10),
    ('execution-exit.json','exit_status',True),('execution-exit.json','exit_status',1),
    ('execution-exit.json','capture_alive_after_child',False),('execution-exit.json','retry',True),
    ('execution-exit.json','read_completion_attested',True),('execution-exit.json','recovery_proven',True),
    ('execution-exit.json','boot_cause_proven',True),('execution-exit.json','time',float('inf'))])
def test_capture_lifecycle_exact_records_reject_resealed_contradictions(capture_lifecycle,name,field,value):
    files,expected,records,publish=capture_lifecycle;records[name][field]=value
    envelope=publish()
    with pytest.raises(ValueError):e.verify_capture_lifecycle(envelope,files,expected,read_outcome='completed',read_started=12,read_terminal=13)


@pytest.mark.parametrize('fault',['extra','missing','wrapper','child','stderr','envelope-kind','envelope-hash','relative-path',
    'invalid-source-pin','reader-before-capture','reader-after-capture','invent-zero-time','zero-child-with-stopped'])
def test_capture_envelope_and_chronology_cannot_grant_forged_admission(capture_lifecycle,fault):
    files,expected,records,publish=capture_lifecycle;outcome='completed';times=dict(read_started=12,read_terminal=13)
    if fault=='extra':files['unexplained']=b''
    elif fault=='missing':files.pop('preflight.json')
    elif fault=='wrapper':files['execute-once.py']=b'other'
    elif fault=='child':files['execute-child.py']=b'other'
    elif fault=='stderr':files['usbmon.stderr']=b'warning'
    elif fault=='relative-path':expected['native_campaign_path']='relative'
    elif fault=='invalid-source-pin':expected['native_sha256']='A'*64
    elif fault=='reader-before-capture':times['read_started']=10
    elif fault=='reader-after-capture':times['read_terminal']=15
    elif fault=='invent-zero-time':outcome='consumed-pretransport-zero-cbw';records['execution-exit.json']['exit_status']=1
    elif fault=='zero-child-with-stopped':outcome='stopped-ambiguous'
    envelope=publish()
    if fault=='envelope-kind':v=json.loads(envelope);v['kind']='other';envelope=e.canonical(v)
    if fault=='envelope-hash':v=json.loads(envelope);v['wrapper_files_sha256']['usbmon.txt']='0'*64;envelope=e.canonical(v)
    with pytest.raises(ValueError):e.verify_capture_lifecycle(envelope,files,expected,read_outcome=outcome,**times)

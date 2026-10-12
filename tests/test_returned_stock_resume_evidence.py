"""MIT. Actual-file stopped lineage; container-only interrupted NOR model."""
from dataclasses import replace
import copy
import ctypes as C
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import fm1_returned_stock_resume_evidence as e
import fm1_returned_stock_resume as kernel
from test_sdk_rehearsal import actual


def sealed(record):
    record=copy.deepcopy(record);record.pop('record_sha256',None)
    record['record_sha256']=e.digest(e.canonical(record));return record


@pytest.fixture
def journal_case():
    plan=dict(schema=1,sector_order=list(kernel.ORDER))
    initial=sealed(dict(schema=1,plan_sha256=e.digest(e.canonical(plan)),state='complete',
        direction='install',intent=None,sector_order=list(kernel.ORDER),verified_sha256=kernel.TARGET_SHA))
    proof=SimpleNamespace(initial_verified=True,uncertainty=((0x5000,0x5100),),sectors_verified=0,
        journal_intents=e.canonical([dict(operation='program',address=0x5000)]),final_stock_verified=False)
    current=sealed(dict(initial,state='recovery_required',direction='restore',
        intent=dict(operation='program',address=0x5000),error='OSError'))
    return current,initial,plan,proof


def test_caught_worker_journal_keeps_historical_target_hash(journal_case):
    assert e.validate_journal(*journal_case,kernel)=='worker-stopped-recovery-required'


@pytest.mark.parametrize('fault',['record','plan','order','state','direction','intent','error-empty',
    'error-type','error-long','verified','deleted-intent','deleted-schema','extra','immutable'])
def test_journal_cannot_forge_stopped_publication(journal_case,fault):
    current,initial,plan,proof=journal_case
    if fault=='record':current['record_sha256']='0'*64
    else:
        if fault=='plan':current['plan_sha256']='0'*64
        elif fault=='order':current['sector_order'].reverse()
        elif fault=='state':current['state']='running'
        elif fault=='direction':current['direction']='install'
        elif fault=='intent':current['intent']=dict(operation='erase',address=0x4000)
        elif fault=='error-empty':current['error']=''
        elif fault=='error-type':current['error']=True
        elif fault=='error-long':current['error']='x'*129
        elif fault=='verified':current['verified_sha256']=kernel.BASELINE_SHA
        elif fault=='deleted-intent':del current['intent']
        elif fault=='deleted-schema':del current['schema']
        elif fault=='extra':current['unrelated']=True
        elif fault=='immutable':initial['extra']=1;current['extra']=2
        current=sealed(current)
    with pytest.raises(ValueError):e.validate_journal(current,initial,plan,proof,kernel)


@pytest.mark.parametrize('later',['none','initial','uncertain','sector'])
def test_unchanged_install_only_admits_pre_worker_stop(journal_case,later):
    _,initial,plan,proof=journal_case
    proof.initial_verified=later=='initial';proof.uncertainty=((0x5000,0x5100),) if later=='uncertain' else ()
    proof.sectors_verified=int(later=='sector')
    if later=='none':assert e.validate_journal(initial,initial,plan,proof,kernel)=='unchanged-install-before-worker'
    else:
        with pytest.raises(ValueError):e.validate_journal(initial,initial,plan,proof,kernel)


@pytest.mark.parametrize('readback',[False,True])
def test_complete_journal_requires_final_actual_stock_readback(journal_case,readback):
    _,initial,plan,proof=journal_case
    proof.final_stock_verified=readback;proof.journal_intents=e.canonical([None])
    current=sealed(dict(initial,direction='restore',verified_sha256=kernel.BASELINE_SHA))
    if readback:assert e.validate_journal(current,initial,plan,proof,kernel)=='stock-readback-complete-publication-stopped'
    else:
        with pytest.raises(ValueError):e.validate_journal(current,initial,plan,proof,kernel)


@pytest.mark.parametrize('fault',['relative','symlink','fifo','directory','oversize'])
def test_evidence_reads_are_direct_regular_and_bounded(tmp_path,fault):
    p=tmp_path/'evidence'
    if fault=='relative':p=Path('relative')
    elif fault=='symlink':p.symlink_to(tmp_path/'missing')
    elif fault=='fifo':os.mkfifo(p)
    elif fault=='directory':p.mkdir()
    else:p.write_bytes(b'x'*9)
    with pytest.raises((ValueError,OSError)):e.read_file(p,8)


def test_source_pin_rejected_before_module_execution(tmp_path):
    p=tmp_path/'source.py';p.write_text('raise AssertionError("executed")')
    with pytest.raises(ValueError,match='Frozen source'):e.load_source(p,'0'*64,'bad_source')


@pytest.mark.parametrize('drift',['file','absent','copy','policy'])
def test_lineage_freezes_positive_negative_and_exact_instance(tmp_path,drift):
    p=tmp_path/'p';p.write_bytes(b'p');absent=tmp_path/'absent'
    def policy_check():
        if drift=='policy':raise ValueError('policy drift')
    proof=e.StoppedLineage(None,None,((p,b'p',8),),(SimpleNamespace(check_files=policy_check),),(absent,),b'{}','model')
    e._AUTHORIZED.add(proof)
    if drift=='file':p.write_bytes(b'q')
    elif drift=='absent':absent.symlink_to(tmp_path/'missing')
    elif drift=='copy':proof=replace(proof)
    with pytest.raises(ValueError):proof.check()


def test_execution_has_no_file_or_transport_admission(monkeypatch,tmp_path):
    monkeypatch.setattr(e.os,'open',lambda *a,**k:pytest.fail('opened evidence/device'))
    with pytest.raises(ValueError,match='cannot authorize'):e.prepare_campaign(tmp_path/'campaign')


def test_actual_private_interrupted_restore_lineage(actual,monkeypatch,tmp_path):
    """One real-source/private-input chain; only experiment identity and SG modeled."""
    import test_returned_rom_actual as composed
    import fm1_returned_rom_stock_restore as restore
    import fm1_diagnostic_detached_probe as returned
    original_run=restore.run_campaign;original_ioctl=composed.ReturnedSGModel.ioctl
    armed=False;mutated=[]
    class EvidenceFinished(Exception):pass
    def interrupted_ioctl(model,fd,code,h):
        op=int.from_bytes(C.string_at(h.cmd,2),'big')
        result=original_ioctl(model,fd,code,h)
        if armed and op==0xFB04 and not mutated:
            address=model.calls[-1]['address']
            # First half applies; second half remains erased despite attempted
            # program. No successful readback clears this exact-page uncertainty.
            model.flash[address+128:address+256]=b'\xff'*128
            mutated.append((model,address))
            raise OSError('modeled ambiguous program completion')
        return result
    monkeypatch.setattr(composed.ReturnedSGModel,'ioctl',interrupted_ioctl)
    def stopped_run(prepared):
        nonlocal armed
        armed=True
        with pytest.raises(OSError):original_run(prepared)
        assert len(mutated)==1
        model,address=mutated[0];rp=tmp_path/'restore.json';c=json.loads(rp.read_bytes())
        receipt=Path(c['receipt_path']);journal=actual.inputs['directory']/'journal.json'
        boot_sha=e.digest((tmp_path/'boot-run/campaign.json').read_bytes())
        def modeled_loader(original):
            def load(path,sha,name):
                module=original(path,sha,name)
                if Path(path)==Path(returned.__file__):module.BOOT_CAMPAIGN_SHA=boot_sha
                if Path(path).name in ('fm1_returned_rom_backup.py','fm1_returned_rom_stock_restore.py'):
                    module.load_source=modeled_loader(module.load_source)
                return module
            return load
        monkeypatch.setattr(e,'load_source',modeled_loader(e.load_source))
        kwargs=dict(campaign_sha256=e.digest(rp.read_bytes()),commands_sha256=e.digest((receipt/'commands.jsonl').read_bytes()),
            journal_sha256=e.digest(journal.read_bytes()))
        proof=e.validate_stopped_restore(rp,**kwargs)
        assert proof.journal_state=='worker-stopped-recovery-required'
        assert proof.prefix.uncertainty==((address,address+256),)
        result=proof.check_partial_dumps(bytes(model.flash),bytes(model.flash))
        assert result['actual_original_lineage_verified'] and not result['execution_authorized']
        assert not result['owned_terminal_capture_verified'] and not result['live_acquisition_verified']
        assert not (receipt/'result.json').exists()
        marker=receipt.parent/'.returned-stock-restore.consumed';assert marker.exists()
        with pytest.raises(ValueError):restore.prepare_campaign(rp)
        corrupted=bytearray(model.flash);corrupted[0]^=1
        with pytest.raises(ValueError):proof.check_partial_dumps(bytes(corrupted),bytes(corrupted))
        with pytest.raises(ValueError):replace(proof).check()
        (receipt/'result.json').write_bytes(b'late publication')
        with pytest.raises(ValueError):proof.check()
        if os.environ.get('LUNAR_REHEARSAL_EVIDENCE'):
            out=Path(os.environ['LUNAR_REHEARSAL_EVIDENCE'])
            (out/'actual-interrupted-lineage-summary.json').write_bytes(e.canonical(dict(
                actual_private_inputs=True,actual_pinned_sources=True,sg_mocked=True,hardware_access=False,
                boot_campaign_literal_modeled=True,usb_and_reset_evidence_modeled=True,
                exact_initial_target_readback=True,one_ambiguous_program=True,uncertain_ranges=[[address,address+256]],
                journal_state=proof.journal_state,immutable_files=len(proof.evidence),marker_preserved=True,retry=False,
                actual_original_lineage_verified=True,owned_terminal_capture_verified=False,live_acquisition_verified=False,
                execution_authorized=False,boot_observed=False,display_observed=False,physical_recovery_verified=False)))
        raise EvidenceFinished()
    monkeypatch.setattr(restore,'run_campaign',stopped_run)
    with pytest.raises(EvidenceFinished):
        composed.test_actual_private_returned_backup_restore_and_completed_helper(actual,monkeypatch,tmp_path,'successful','none')

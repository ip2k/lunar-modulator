"""MIT. Interrupted-prefix evidence tests only: no physical transport."""
from dataclasses import replace
import copy

import pytest

import fm1_returned_stock_resume as r
from test_returned_rom_stock_restore import restore_transcript


@pytest.fixture
def replay(restore_transcript,monkeypatch):
    rows,result,c,mapping,baseline,target,order,replay_type=restore_transcript
    monkeypatch.setattr(r,'BASELINE_SHA',r.digest(baseline))
    monkeypatch.setattr(r,'TARGET_SHA',r.digest(target))
    return rows,c,mapping,baseline,target


def prefix(fixture,end,mutate=None):
    rows,c,mapping,baseline,target=fixture
    selected=copy.deepcopy(rows[:end])
    if mutate:mutate(selected)
    selected.append(dict(time=rows[end-1]['time']+0.0001,event='returned_restore_stopped_ambiguous',
        error='OSError',retry=False,stock_baseline_restored=False,boot_observed=False))
    raw=b'\n'.join(r.canonical(e) for e in selected)+b'\n'
    return r.verify_interrupted_prefix(raw,c,'campaign',mapping,baseline,target)


def mutation_index(rows,op):
    return next(i for i,e in enumerate(rows) if e['event']=='sg_submit_intent' and e['cdb'].startswith(op))


@pytest.mark.parametrize('boundary',['prepared','initial-read','before-erase','erase-intent',
    'erase-completion','erase-returned','program-intent','program-completion','program-returned',
    'sector-verified','directory-intent','final-read','completed'])
def test_exact_stop_boundaries_and_uncertainty(replay,boundary):
    rows,c,mapping,baseline,target=replay
    erase=mutation_index(rows,'fb01');program=mutation_index(rows,'fb04')
    directory=next(i for i,e in enumerate(rows) if e['event']=='sg_submit_intent' and e['cdb'].startswith('fb0100004000'))
    sector=next(i for i,e in enumerate(rows) if e['event']=='sector_verified')
    ends=dict(prepared=1,**{'initial-read':4,'before-erase':erase-1,'erase-intent':erase+1,
        'erase-completion':erase+2,'erase-returned':erase+3,'program-intent':program+1,
        'program-completion':program+2,'program-returned':program+3,'sector-verified':sector+1,
        'directory-intent':directory+1,'final-read':len(rows)-1,'completed':len(rows)})
    proof=prefix(replay,ends[boundary])
    if boundary.startswith('erase-'):assert proof.uncertainty==((0x5000,0x6000),)
    elif boundary.startswith('program-'):assert proof.uncertainty==((0x5000,0x5100),)
    elif boundary=='directory-intent':assert proof.uncertainty==((0x4000,0x5000),)
    else:assert proof.uncertainty==()
    if boundary=='erase-returned':assert proof.expected_nor[0x5000:0x6000]==b'\xff'*4096
    if boundary=='program-returned':assert proof.expected_nor[0x5000:0x5100]==baseline[0x5000:0x5100]
    if boundary in ('final-read','completed'):assert proof.final_stock_verified and proof.expected_nor==baseline
    r.check_partial_dumps(proof,proof.expected_nor,proof.expected_nor)


@pytest.mark.parametrize('fault',['cdb','crc','payload','retry','direction','index','initial-hash',
    'extra','order','sense-shape','future','nan','stop-success','stop-missing','two-commands'])
def test_corrupt_prefix_is_rejected(replay,fault):
    rows,c,mapping,baseline,target=replay
    program=mutation_index(rows,'fb04')
    def corrupt(selected):
        if fault=='cdb':selected[program]['cdb']='fb04'+'00'*14
        elif fault=='crc':selected[program]['cdb']=selected[program]['cdb'][:18]+'0000'+selected[program]['cdb'][22:]
        elif fault=='payload':selected[program]['payload_sha256']='0'*64
        elif fault=='retry':selected[program]['retry']=True
        elif fault=='direction':selected[program]['direction']='install'
        elif fault=='index':selected[program]['index']+=1
        elif fault=='initial-hash':selected[4]['response_sha256']='0'*64
        elif fault=='extra':selected.insert(4,copy.deepcopy(selected[3]))
        elif fault=='order':selected[3],selected[4]=selected[4],selected[3]
        elif fault=='sense-shape':selected[4]['sense_len']=1
        elif fault=='future':selected[1]['time']=1e20
        elif fault=='nan':selected[1]['time']=float('nan')
        elif fault=='two-commands':selected[-2]['host']=1
    if fault in ('stop-success','stop-missing'):
        raw=rows[:program+2]+([dict(time=100,event='returned_restore_completed')] if fault=='stop-success' else [])
        with pytest.raises(ValueError):r.verify_interrupted_prefix(b'\n'.join(r.canonical(e) for e in raw),c,'campaign',mapping,baseline,target)
    else:
        with pytest.raises(ValueError):prefix(replay,program+3,corrupt)


@pytest.mark.parametrize('status',['status','masked','msg','host','driver','resid','info','sense_len'])
def test_terminal_ambiguous_completion_keeps_only_program_page(replay,status):
    rows,*_=replay;program=mutation_index(rows,'fb04')
    def bad(selected):
        selected[-1][status]=1
        if status=='sense_len':selected[-1]['sense_hex']='00'
    proof=prefix(replay,program+2,bad)
    assert proof.uncertainty==((0x5000,0x5100),)


@pytest.mark.parametrize('delta',[-1,0,255,256,4096,-0x1001])
def test_dual_dump_difference_limited_to_final_submitted_page(replay,delta):
    rows,*_=replay;proof=prefix(replay,mutation_index(rows,'fb04')+1)
    image=bytearray(proof.expected_nor);image[0x5000+delta]^=1;image=bytes(image)
    if 0<=delta<256:assert r.check_partial_dumps(proof,image,image)['uncertain_ranges']==[[0x5000,0x5100]]
    else:
        with pytest.raises(ValueError):r.check_partial_dumps(proof,image,image)


@pytest.mark.parametrize('fault',['short','mismatch','protected','copied-proof'])
def test_partial_backup_has_no_inferred_padding_or_copied_authority(replay,fault):
    proof=prefix(replay,1);a=b=proof.expected_nor
    if fault=='short':a=a[:-1];b=a
    elif fault=='mismatch':b=b'\x00'+b[1:]
    elif fault=='protected':a=b=b'\x00'+b[1:]
    elif fault=='copied-proof':proof=replace(proof)
    with pytest.raises(ValueError):r.check_partial_dumps(proof,a,b)


def test_execution_stays_closed_without_reading_or_opening(tmp_path,monkeypatch):
    monkeypatch.setattr(r.os,'open',lambda *a,**k:pytest.fail('any evidence/device open'))
    assert r.EXECUTION_POLICY_SHA is None
    with pytest.raises(ValueError,match='not reviewed'):r.prepare_campaign(tmp_path/'untrusted.json')


def test_replay_dependency_pin_checked_before_execution(monkeypatch):
    monkeypatch.setattr(r,'REPLAY_SOURCE_SHA','0'*64)
    with pytest.raises(ValueError,match='Frozen replay'):r.load_replay()


@pytest.mark.parametrize('stage',['erase-returned','blank-page','blank-sector','two-programs',
    'all-programs','sector-page','sector-read'])
def test_only_actual_matching_readback_clears_attempted_write_spans(replay,stage):
    rows,*_=replay;erase=mutation_index(rows,'fb01');program=mutation_index(rows,'fb04')
    second=next(i for i,e in enumerate(rows) if i>program and e['event']=='sg_submit_intent' and e['cdb'].startswith('fb04'))
    sector=next(i for i,e in enumerate(rows) if e['event']=='sector_verified')
    end={'erase-returned':erase+3,'blank-page':erase+5,'blank-sector':program-3,
        'two-programs':second+3,'all-programs':sector-32,'sector-page':sector-30,'sector-read':sector}[stage]
    proof=prefix(replay,end)
    expected={'erase-returned':((0x5000,0x6000),),'blank-page':((0x5100,0x6000),),
        'blank-sector':(),'two-programs':((0x5000,0x5200),),'all-programs':((0x5000,0x6000),),
        'sector-page':((0x5100,0x6000),),'sector-read':()}[stage]
    assert proof.uncertainty==expected
    # Prior attempted programs may be unapplied despite adapter return. That
    # difference stays recoverable until the actual affected-page readback.
    image=bytearray(proof.expected_nor)
    if expected:image[expected[0][0]]^=1
    image=bytes(image);r.check_partial_dumps(proof,image,image)

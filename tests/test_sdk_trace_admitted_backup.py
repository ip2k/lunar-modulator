"""MIT. Closed successor mechanics only; no admission authority or device calls."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import ast
import os

import pytest

import fm1_sdk_trace_admitted_backup as b


@pytest.mark.parametrize('entry', ['prepare', 'completed'])
def test_closed_proof_before_evidence_or_canonical_import(monkeypatch, entry):
    monkeypatch.setattr(b, 'PROOF_SOURCE_SHA', None)
    monkeypatch.setattr(b, 'read_file', lambda *a, **k: pytest.fail('closed read'))
    monkeypatch.setattr(b.importlib, 'import_module', lambda *a, **k: pytest.fail('closed import'))
    with pytest.raises(ValueError, match='Closed'):
        if entry == 'prepare': b.prepare_campaign('/never-read')
        else: b.validate_completed_backup('/never-read', campaign_sha256='c', manifest_sha256='m',
            commands_sha256='l', freeze=lambda *a, **k: pytest.fail('closed freeze'))


@pytest.fixture
def witness():
    snapshot = dict(observed_at=1, usb_binding=dict(usb_path='1-2', busnum='1', devnum='4'),
        sg_binding=dict(node='/dev/sgMODEL', node_identity=[1,2,3]))
    w = dict(schema=1, kind='fm1-passive-sdk-trace-admitted-backup-connection',
        observed_at=100, usb_binding=snapshot['usb_binding'].copy(),
        sg_binding=snapshot['sg_binding'].copy(), original_rom_snapshot_sha256='a'*64,
        returned_admission_sha256='b'*64, quiet_state=b.STATE)
    return w, snapshot


def test_original_old_snapshot_not_refreshed_by_fresh_witness(witness):
    w, snapshot = witness
    b.validate_connection_witness(w, snapshot, 'a'*64, 200)
    assert snapshot['observed_at'] == 1  # Historical age199, distinct current age100.


@pytest.mark.parametrize('fault', ['extra','schema-bool','kind','state','future','stale',
    'before-original','bool-time','nan','usb-devnum','usb-path','sg-inode','sg-node','snapshot-sha'])
def test_exact_current_witness_rejects_drift(witness, fault):
    w, snapshot = witness
    if fault == 'extra': w['unexpected'] = 1
    elif fault == 'schema-bool': w['schema'] = True
    elif fault == 'kind': w['kind'] = 'fm1-passive-sdk-trace-backup-connection'
    elif fault == 'state': w['quiet_state'] = 'quiet'
    elif fault == 'future': w['observed_at'] = 201
    elif fault == 'stale': w['observed_at'] = 79
    elif fault == 'before-original': w['observed_at'] = 0
    elif fault == 'bool-time': w['observed_at'] = True
    elif fault == 'nan': w['observed_at'] = float('nan')
    elif fault == 'usb-devnum': w['usb_binding']['devnum'] = '5'
    elif fault == 'usb-path': w['usb_binding']['usb_path'] = '1-3'
    elif fault == 'sg-inode': w['sg_binding']['node_identity'] = [1,2,4]
    elif fault == 'sg-node': w['sg_binding']['node'] = '/dev/sgOTHER'
    else: w['original_rom_snapshot_sha256'] = 'c'*64
    with pytest.raises(ValueError): b.validate_connection_witness(w, snapshot, 'a'*64, 200)


def proof(boot):
    # Pure marker function input, never fed to prepare or a registry.
    return SimpleNamespace(lineage=SimpleNamespace(read_binding=lambda:dict(boot_campaign_sha256=boot)))


def test_marker_is_one_original_boot_even_with_different_admission_aliases(tmp_path):
    first = b.marker_path(tmp_path, proof('a'*64))
    assert first == b.marker_path(tmp_path, proof('a'*64))
    assert first != b.marker_path(tmp_path, proof('b'*64))
    assert first.name == '.sdk-trace-admitted-loader-'+'a'*64+'.consumed'
    first.write_bytes(b'consumed')
    with pytest.raises(FileExistsError): os.open(first, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)


@pytest.mark.parametrize('pin', [None, True, 'A'*64, '0'*63])
def test_marker_rejects_noncanonical_boot_pin(tmp_path, pin):
    with pytest.raises(ValueError): b.marker_path(tmp_path, proof(pin))


@pytest.mark.parametrize('fault', ['positive','negative','policy','inventory'])
def test_pure_evidence_check_retains_all_boundaries(tmp_path, fault):
    p = tmp_path/'positive'; p.write_bytes(b'original')
    absent = tmp_path/'late'
    def provenance_check():
        if os.path.lexists(absent): raise ValueError('negative drift')
    def policy_check():
        if fault == 'policy': raise ValueError('policy drift')
    modeled = SimpleNamespace(evidence=((p,b'original',32),), policies=(SimpleNamespace(check_files=policy_check),),
        provenance=SimpleNamespace(check=provenance_check), operations=('fixed',),
        request_inventory_sha256='sealed', bridge=SimpleNamespace(inventory_digest=lambda ops:'sealed'))
    if fault == 'positive': p.write_bytes(b'changed')
    elif fault == 'negative': absent.write_bytes(b'late')
    elif fault == 'inventory': modeled.request_inventory_sha256='changed'
    with pytest.raises(ValueError): b.check_evidence(modeled)


@pytest.mark.parametrize('entry', ['require','transport','worker'])
def test_unregistered_and_copied_prepared_are_not_authority(entry):
    p = b.Prepared(b'{}','c',b'{}',(),(),None,None,(),'i','m',Path('/private'),None,b'{}',None)
    for other in (p, replace(p)):
        with pytest.raises(ValueError):
            if entry == 'require': b.require_prepared(other)
            elif entry == 'transport': b.FixedSG(other, None)
            else: b.run_campaign(other)


@pytest.mark.parametrize('fault', ['relative','directory','symlink','fifo','oversize'])
def test_direct_bounded_evidence_inputs(tmp_path, fault):
    p=tmp_path/'input'
    if fault=='relative': p=Path('relative')
    elif fault=='directory': p.mkdir()
    elif fault=='symlink': p.symlink_to(__file__)
    elif fault=='fifo': os.mkfifo(p)
    else: p.write_bytes(b'x'*9)
    with pytest.raises((ValueError,OSError)): b.read_file(p,8)


def test_closed_source_uses_canonical_new_proof_and_exact_original_kernels():
    source=Path(b.__file__).read_text(); tree=ast.parse(source)
    constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body
        if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name)
        and isinstance(n.value,ast.Constant)}
    assert constants['PROOF_SOURCE_SHA']=='6eb30cfd770a596c838b454bd2e79a4a39f4929274477aed193da24a036dd60e'
    assert b.digest((Path(b.__file__).parent/'fm1_sdk_trace_return_admission.py').read_bytes())==constants['PROOF_SOURCE_SHA']
    assert constants['BASE_SOURCE_SHA']=='afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be'
    assert constants['REHEARSAL_SHA']=='f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4'
    assert "importlib.import_module('fm1_sdk_trace_return_admission')" in source
    assert 'proof.lineage.installed.evidence' in source
    assert 'fm1_sdk_trace_recovery_evidence.py' not in source
    assert 'trace_admitted_backup_completed' in source

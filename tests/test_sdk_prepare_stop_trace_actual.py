"""Genuine V7 provenance in disposable Hera containers; every SG syscall modeled.

Only the new closed source pin is proposed. No canonical factory or authority
registry is replaced. Private input files never become public test fixtures.
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

CASES = ('valid', 'expired', 'future', 'usb_changed', 'sg_changed', 'status',
         'ioctl', 'changed', 'postmap', 'initialmap', 'lock', 'close',
         'late_intent', 'marker_reuse', 'elf_changed', 'source_changed')


@pytest.mark.parametrize('case', CASES)
def test_actual_preparation_stop_trace(monkeypatch, tmp_path, case):
    if os.environ.get('LUNAR_PREPARATION_STOP_DISPOSABLE') != '1':
        pytest.skip('Private V7 provenance in disposable Linux container required')
    root = Path(__file__).resolve().parents[1]
    assert root == Path('/tmp/packet-work') and sys.platform == 'linux'
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    path = root / 'tools/fm1_sdk_prepare_stop_trace_read.py'
    before = path.read_text(); assert before.count('PROOF_SOURCE_SHA = None') == 1
    pin = sha(root / 'tools/fm1_sdk_trace_prepare_stop.py')
    proposal = before.replace('PROOF_SOURCE_SHA = None', 'PROOF_SOURCE_SHA = ' + repr(pin))
    assert proposal.replace('PROOF_SOURCE_SHA = ' + repr(pin), 'PROOF_SOURCE_SHA = None') == before
    path.write_text(proposal)
    import fm1_sdk_prepare_stop_trace_read as n
    import fm1_sdk_trace_prepare_stop as stop
    from test_sdk_trace_sg import mock_sg
    stage = Path('/home/claude/fm1-sdk-trace-campaign-20261012-v7')
    entry = Path('/home/claude/fm1-sdk-trace-entry-20261012-v7')
    lineage = stage / 'boot-lineage.json'; chain = entry / 'automatic-trace-chain-v7'
    proof = stop.validate_preparation_stop(lineage, chain)
    historical = proof.snapshot
    snapshot = json.loads(historical)
    sp = tmp_path / 'stop.json'
    sp.write_bytes(n.canonical(dict(schema=1, kind='fm1-native-preparation-stop-evidence',
        boot_lineage_path=str(lineage), boot_lineage_sha256=sha(lineage), chain_path=str(chain))))
    witness = dict(schema=1, kind='fm1-passive-sdk-preparation-stop-trace-connection',
        observed_at=time.time(), usb_binding=snapshot['usb_binding'], sg_binding=snapshot['sg_binding'],
        original_rom_snapshot_sha256=proof.snapshot_sha256, preparation_stop_sha256=sha(sp),
        quiet_state=n.STATE)
    if case == 'expired': witness['observed_at'] -= 121
    # Provenance validation takes several seconds; remain future-dated at admission.
    if case == 'future': witness['observed_at'] += 3600
    if case == 'usb_changed': witness['usb_binding']['devnum'] = '11'
    if case == 'sg_changed': witness['sg_binding']['node_identity'][1] += 1
    wp = tmp_path / 'witness.json'; wp.write_bytes(n.canonical(witness))
    cp = tmp_path / 'campaign.json'
    c = dict(schema=1, kind=n.KIND, adapter_sha256=sha(path),
        preparation_stop_path=str(sp), preparation_stop_sha256=sha(sp),
        connection_witness_path=str(wp), connection_witness_sha256=sha(wp),
        elf_path=str(stage / 'assets/native/lunar-sdk-diagnostic.elf'),
        app_path=str(stage / 'assets/native/lunar-sdk-diagnostic.app.bin'),
        manifest_path=str(stage / 'assets/native/build-manifest.json'),
        receipt_path=str(proof.lineage.parent / 'modeled-distinct-stop-trace'),
        active_session_state=n.STATE)
    cp.write_bytes(n.canonical(c))
    if case == 'elf_changed':
        elf = Path(c['elf_path']); elf.write_bytes(elf.read_bytes() + b'changed')
    if case in ('expired', 'future', 'usb_changed', 'sg_changed', 'elf_changed'):
        with pytest.raises(ValueError): n.prepare_campaign(cp)
        assert not Path(c['receipt_path']).exists()
        return
    prepared = n.prepare_campaign(cp)
    state = mock_sg(prepared, monkeypatch,
        fault=case if case in ('status', 'ioctl', 'changed', 'postmap', 'initialmap', 'lock', 'close') else None)
    if case == 'source_changed': path.write_text(path.read_text() + '\n# unexpected change\n')
    if case == 'late_intent':
        real_sync = os.fsync; published = []
        def sync(fd):
            real_sync(fd)
            journal = prepared.receipt / 'native.jsonl'
            if journal.exists() and not published:
                events = [json.loads(line) for line in journal.read_text().splitlines()]
                if events[-1]['event'] == 'native_ioctl_intent':
                    (chain / '09-unexpected.intent.json').write_text('{}')
                    published.append(True)
        monkeypatch.setattr(os, 'fsync', sync)
    if case in ('valid', 'marker_reuse'):
        result = n.run_campaign(prepared)
        assert len(state.calls) == 5
        assert result['progress'] == 'final-start-intent'
        assert result['display_observed'] is result['physical_recovery_verified'] is False
        assert result['retention_verified'] is result['nonce_identifies_boot'] is False
        assert (prepared.receipt / 'result.json').exists()
        assert len(list(prepared.receipt.glob('*.raw.bin'))) == 5
        if case == 'marker_reuse':
            before_calls = len(state.calls)
            with pytest.raises((ValueError, FileExistsError)): n.run_campaign(prepared)
            with pytest.raises(ValueError): n.prepare_campaign(cp)
            assert len(state.calls) == before_calls
    else:
        with pytest.raises((ValueError, OSError)): n.run_campaign(prepared)
        assert not (prepared.receipt / 'result.json').exists()
        if case in ('late_intent', 'source_changed', 'initialmap', 'lock'):
            assert len(state.calls) == 0
        if case in ('status', 'postmap'):
            assert (prepared.receipt / 'inquiry.raw.bin').exists()
        if case == 'changed':
            assert len(list(prepared.receipt.glob('*.raw.bin'))) == 5
        if case != 'source_changed': assert prepared.marker.exists()
    assert proof.snapshot == historical
    original_snapshot = json.loads(lineage.read_bytes())['rom_snapshot_path']
    assert Path(original_snapshot).read_bytes() == historical
    assert all(op in n.OPERATIONS for op in state.calls)
    assert len(state.calls) <= 5
    if case != 'source_changed':
        from fm1_prepare_stop_trace_receipt import verify_receipt
        receipt = prepared.receipt
        result_path = receipt / 'result.json'
        pending = receipt / '.result.json.pending'
        replay = verify_receipt((receipt / 'commands.jsonl').read_bytes(),
            (receipt / 'native.jsonl').read_bytes(), prepared.seal,
            {p.name.removesuffix('.raw.bin'): p.read_bytes() for p in receipt.glob('*.raw.bin')},
            snapshot['sg_binding'], interpret=prepared.module.interpret_repeated,
            evaluated_at=time.time(),
            result_raw=result_path.read_bytes() if result_path.exists() else None,
            pending_raw=pending.read_bytes() if pending.exists() else None)
        assert replay['outcome'] == ('completed' if case in ('valid', 'marker_reuse') else 'stopped-ambiguous')
        assert replay['recovery_authorized'] is replay['physical_boot_verified'] is False


def test_stop_trace_closed_without_device(tmp_path):
    import fm1_sdk_prepare_stop_trace_read as n
    with pytest.raises(ValueError, match='Closed'):
        n.prepare_campaign(tmp_path / 'absent.json')


def test_native_sg_mechanics_unchanged():
    """The new authority does not change the reviewed transport implementation."""
    root = Path(__file__).resolve().parents[1] / 'tools'
    old = (root / 'fm1_sdk_trace_sg.py').read_text()
    new = (root / 'fm1_sdk_prepare_stop_trace_read.py').read_text()
    body = lambda s: s[s.index('class NativeSG:'):s.index('\n\ndef run_campaign(prepared):')].rstrip()
    assert body(old) == body(new)

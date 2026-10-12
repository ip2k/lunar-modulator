"""MIT. Actual canonical factories, modeled device syscalls/clock/USB evidence.

Run the expensive composition once in a disposable device-free Hera container
with strict private/native fixtures and real reviewed literal activations. This
test never patches production hashes, factories or authority registries.
"""
from dataclasses import replace
import json
import os
from pathlib import Path
import sys

import pytest

from test_sdk_rehearsal import actual
from sdk_trace_read_fixture import digest, genuine_trace_read_ready, model_native_reads, private_write


def test_genuine_canonical_install_boot_reader_native_composition(actual, tmp_path, monkeypatch):
    f = genuine_trace_read_ready(actual, tmp_path, monkeypatch)
    native, boot = f.modules.native, f.modules.boot
    boot.require_read_lineage(f.lineage)
    with pytest.raises(ValueError):
        boot.require_read_lineage(replace(f.lineage))
    with pytest.raises(ValueError):
        replace(f.prepared).check()
    state = model_native_reads(f, monkeypatch)
    # A real copied native authority fails before any discovery/open/ioctl.
    with pytest.raises(ValueError):
        native.run_campaign(replace(f.prepared))
    assert not state.opens and not state.calls
    snapshot_path = Path(json.loads(f.prepared.campaign)['inputs']['snapshot_path'])
    original = snapshot_path.read_bytes()
    snapshot_path.write_bytes(b'{}')
    try:
        with pytest.raises(ValueError):
            f.prepared.check()
        assert not state.opens and not state.calls
    finally:
        snapshot_path.write_bytes(original)
    result = native.run_campaign(f.prepared)
    assert state.calls == list(native.OPERATIONS)
    assert len(state.opens) == len(state.closes) == len(state.locks) == 1
    assert result['progress'] == 'final-start-intent'
    assert result['new_ranges_hardware_verified'] is False
    receipt = f.prepared.read.receipt
    events = [json.loads(row) for row in (receipt/'commands.jsonl').read_bytes().splitlines()]
    assert [e['event'] for e in events] == ['read_prepared',
        *[event for _ in range(5) for event in ('submit_intent', 'completion')],
        'coherent_capture_completed']
    completed = [e for e in events if e['event'] == 'completion']
    assert [e['response_sha256'] for e in completed] == [digest(raw) for raw in state.replies]
    assert result['raw_sha256'] == [digest(raw) for raw in state.replies]
    assert json.loads((receipt/'result.json').read_bytes()) == result
    assert not (receipt/'.result.json.pending').exists()
    assert f.prepared.read.marker.read_text() == digest(f.prepared.read.seal)
    with pytest.raises(FileExistsError):
        native.run_campaign(f.prepared)
    assert len(state.calls) == 5
    for name, module in f.modules.modules.items():
        assert sys.modules[name] is module
    boot.require_read_lineage(f.lineage)
    assert len(f.reset_calls) == 1
    assert len(f.g.model.calls) == 10653
    assert len(f.g.model.opened) == len(f.g.model.closed) == 2
    summary = dict(schema=1, actual_private_install_factory_and_worker=True,
        actual_canonical_boot_factory_worker_and_lineage=True,
        actual_native_reader_factory_and_worker=True,
        canonical_boot_registry_identity_preserved=True,
        fabricated_authority=False, source_pin_overrides=False,
        clock_device_syscalls_and_passive_capture_modeled=True,
        hardware_access=False, physical_boot_proven=False,
        install_commands=len(f.g.model.calls), reset_commands=len(f.reset_calls),
        read_commands=len(state.calls), read_result=result,
        source_sha256={name: digest(Path(module.__file__).read_bytes())
                       for name, module in f.modules.modules.items()},
        install_summary=f.g.summary,
        boot_campaign_sha256=f.reset.campaign_sha256,
        read_lineage_path=str(f.lineage_path), native_campaign_path=str(f.native_campaign),
        reader_receipt_path=str(receipt))
    evidence = Path(os.environ.get('LUNAR_REHEARSAL_EVIDENCE', str(tmp_path)))
    evidence.mkdir(exist_ok=True)
    saved = evidence/'canonical-composed-artifacts'
    saved.mkdir(mode=0o700)
    inputs = dict(install_campaign=f.g.campaign, install_commands=f.g.commands,
        install_result=f.g.result_path, install_marker=f.g.marker, install_journal=f.g.journal,
        sealed_plan=f.g.journal.parent/'plan.json', boot_commands=f.reset.receipt/'commands.jsonl',
        boot_marker=f.reset.marker, lineage_campaign=f.lineage_path,
        native_campaign=f.native_campaign, read_marker=f.prepared.read.marker)
    lineage = json.loads(f.lineage_path.read_bytes())
    inputs['boot_campaign'] = Path(lineage['boot_campaign_path'])
    for name in ('capture', 'capture_open', 'capture_stop', 'boot_exit', 'rom_snapshot'):
        inputs[name] = Path(lineage[name+'_path'])
    for path in receipt.iterdir():
        assert path.is_file()
        inputs['read-'+path.name] = path
    summary['artifact_sha256'] = {}
    for name, path in inputs.items():
        raw = path.read_bytes()
        private_write(saved/name, raw)
        summary['artifact_sha256'][name] = digest(raw)
    (evidence/'canonical-composed-summary.json').write_text(json.dumps(summary, indent=2)+'\n')

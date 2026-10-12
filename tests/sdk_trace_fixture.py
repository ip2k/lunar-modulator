"""Private device-free genuine trace-install fixture for boot composition.

Adapted from test_sdk_trace_install.test_actual_private_trace_factory_full_install.
No CompletedInstall fabrication, registry injection, pin substitution, or
live_prepare patch. Caller supplies pytest monkeypatch and the genuine `actual`
fixture from test_sdk_rehearsal in an isolated Hera container with no devices.
All source/native/target/reference/private fixtures must be mounted read-only;
the historical backup is copied to its exact historical path inside that
container by the supervisor before invoking the existing actual fixture.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace


def genuine_completed_trace_install(actual, tmp_path, monkeypatch):
    """Run real prepare + worker, with only historical clock and SG modeled.

    Leaves exact campaign/consumed marker/log/result/current install journal
    available for root's unchanged boot.validate_completed_install. This helper
    does not call a boot factory or grant a real transport authority.
    """
    if os.environ.get('LUNAR_REHEARSAL_DISPOSABLE') != '1':
        raise ValueError('Only an explicitly disposable device-free fixture allowed')
    from test_sdk_rehearsal import SGModel, rehearsal
    import fm1_sdk_trace_install as install

    tmp_path = Path(tmp_path).absolute()
    native = Path(os.environ['LUNAR_TRACE_NATIVE'])
    target_path = Path(os.environ['LUNAR_TRACE_TARGET'])
    review = Path(os.environ['LUNAR_TRACE_REVIEW'])
    policy = install.policy_module()
    policy.require_candidate_pins()
    inputs = dict(actual.inputs)
    inputs.update(directory=tmp_path/'trace-transaction',
        app_path=native/'lunar-sdk-diagnostic.app.bin',
        elf_path=native/'lunar-sdk-diagnostic.elf',
        audit_path=native/'sdk-image-audit.json',
        build_manifest_path=native/'build-manifest.json', trace_review_path=review)
    target = target_path.read_bytes()
    assert install.digest(target) == policy.TARGET_SHA
    ranges = [[a, a+4096] for a in range(0x4000, 0x22000, 4096)]
    policy.prepare_transaction(inputs['directory'], actual.baseline, actual.baseline,
        target, json.loads(inputs['identity_path'].read_bytes()), ranges)
    manifest = json.loads(inputs['manifest_path'].read_bytes())
    backup_log = inputs['backup_log_path'].read_bytes()
    backup_ended = json.loads(backup_log.splitlines()[-1])['time']
    monkeypatch.setattr(install.time, 'time', lambda: backup_ended+1)
    receipt = Path(actual.config['receipt_path']).with_name('test-trace-boot-'+tmp_path.name)
    config = dict(schema=1, kind=install.KIND,
        adapter_sha256=install.digest(Path(install.__file__).read_bytes()),
        policy_sha256=install.POLICY_SHA,
        policy_inputs={k: str(v) for k, v in inputs.items()},
        backup_exit_status=0, backup_commands_sha256=install.digest(backup_log),
        active_session_state=install.STATE, sg_binding=manifest['sg_binding'],
        receipt_path=str(receipt))
    campaign = tmp_path/'trace-campaign.json'
    campaign.write_bytes(rehearsal.canonical(config))
    prepared = install.prepare_campaign(campaign)
    assert [p.direction for p in prepared.policies] == ['install', 'restore']
    assert prepared.policy_module.APP_SHA == policy.APP_SHA
    assert prepared.policy_module.ELF_SHA == policy.ELF_SHA
    model = SGModel(monkeypatch, config['sg_binding'], actual.baseline)
    monkeypatch.setattr(prepared.bridge, 'discover_sg', model.discover)
    result = install.run_campaign(prepared)
    assert bytes(model.flash) == target
    assert result['verified_sha256'] == policy.TARGET_SHA
    erases = [c['address'] for c in model.calls if c['op'] == 0xfb01]
    assert erases == list(range(0x5000, 0x22000, 4096))+[0x4000]
    assert len([c for c in model.calls if c['op'] == 0xfb04]) == 480
    assert len(model.calls) == 10653
    assert len(model.opened) == len(model.closed) == 1
    assert not result['boot_observed'] and not result['physical_recovery_verified']
    journal = inputs['directory']/'journal.json'
    commands = receipt/'commands.jsonl'
    result_path = receipt/'result.json'
    assert prepared.marker.read_text() == prepared.campaign_sha256
    pins = dict(campaign_sha256=install.digest(campaign.read_bytes()),
        commands_sha256=install.digest(commands.read_bytes()),
        result_sha256=install.digest(result_path.read_bytes()),
        journal_sha256=install.digest(journal.read_bytes()))
    summary = dict(schema=1, production_prepare_and_run=True,
        fabricated_completed_install=False, source_pin_overrides=False,
        clock_and_sg_modeled=True, hardware_access=False,
        commands=len(model.calls), erases=erases, programs=480,
        target_sha256=policy.TARGET_SHA, baseline_sha256=policy.BASELINE_SHA,
        campaign_path=str(campaign), receipt_path=str(receipt),
        journal_path=str(journal), marker_path=str(prepared.marker), **pins)
    (tmp_path/'genuine-install-helper-summary.json').write_text(
        json.dumps(summary, indent=2)+'\n')
    return SimpleNamespace(campaign=campaign, config=config, inputs=inputs,
        prepared=prepared, result=result, receipt=receipt, journal=journal,
        commands=commands, result_path=result_path, marker=prepared.marker,
        model=model, policy=policy, install=install, pins=pins, summary=summary)

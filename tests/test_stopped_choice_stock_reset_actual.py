"""MIT. Actual private successor lineage through one modeled core-reset request.

Physical RAM receipt and all production source pins remain exact. Only SG
syscalls/NOR/reply are modeled inside a device-free Hera container. A successful
model reply does not establish physical reset, stock boot, display or recovery.
"""
import ctypes as C
import json
import os
from pathlib import Path
import shutil

import pytest

import fm1_stopped_choice_stock_reset as reset_source
import test_stopped_choice_restore_actual as composition
from test_stopped_choice_restore_actual import successor_factory, actual_tree


def test_actual_private_backup_restore_helper_and_one_reset(successor_factory, monkeypatch):
    backup, restore, original, cp, proof, stage = successor_factory
    captured = {}
    real_model = composition.ReturnedSGModel
    real_validate = restore.validate_completed_restore

    class CompletedHelperCaptured(Exception):
        pass

    def model(*args, **kwargs):
        captured['model'] = real_model(*args, **kwargs)
        return captured['model']

    def completed(path, **kwargs):
        captured['proof'] = real_validate(path, **kwargs)
        captured['campaign'] = Path(path)
        raise CompletedHelperCaptured

    monkeypatch.setattr(composition, 'ReturnedSGModel', model)
    monkeypatch.setattr(restore, 'validate_completed_restore', completed)
    # Stop only after the exact unchanged completed helper has independently
    # admitted the genuine restore; avoid repeating its seven corruption cases.
    with pytest.raises(CompletedHelperCaptured):
        composition.test_actual_successor_backup_restore_and_preserved_completed_helper(
            successor_factory, monkeypatch, 'complete')
    sg = captured['model']
    lineage = captured['proof']
    rc = captured['campaign']
    config = json.loads(rc.read_bytes())
    receipt = Path(config['receipt_path'])
    journal = original.policies[0].directory / 'journal.json'
    assert bytes(sg.flash) == original.policies[0].baseline
    assert json.loads(journal.read_bytes())['direction'] == 'restore'
    assert lineage['baseline_sha256'] == reset_source.BASELINE_SHA
    assert lineage['target_sha256'] == reset_source.TARGET_SHA
    assert len(sg.opened) == len(sg.closed) == 2

    source = stage / 'tools/fm1_stopped_choice_stock_reset.py'
    shutil.copyfile(reset_source.__file__, source)
    reset = backup.load_source(source, backup.digest(source.read_bytes()), '_actual_stopped_choice_stock_reset')
    assert reset.RESTORE_SOURCE_SHA == backup.digest(Path(restore.__file__).read_bytes())
    c = dict(schema=1, kind='fm1-stopped-choice-fixed-loader-stock-reset',
        adapter_sha256=reset.digest(source.read_bytes()), restore_campaign_path=str(rc),
        restore_campaign_sha256=reset.digest(rc.read_bytes()),
        restore_commands_sha256=reset.digest((receipt / 'commands.jsonl').read_bytes()),
        restore_result_sha256=reset.digest((receipt / 'result.json').read_bytes()),
        restore_journal_sha256=reset.digest(journal.read_bytes()), restore_exit_status=0,
        active_session_state='stopped-choice-fixed-loader-stock-restored-no-later-commands',
        receipt_path=str(Path(lineage['returned_backup_receipt_path']) / 'stock-reset'))
    path = stage / 'stopped-choice-reset.json'
    path.write_bytes(reset.canonical(c))
    prepared = reset.prepare_campaign(path)
    assert prepared.absent_paths == lineage['_absent_paths']
    monkeypatch.setattr(prepared.bridge, 'discover_sg', sg.discover)
    before = len(sg.calls)

    def ioctl(fd, code, header):
        cdb = C.string_at(header.cmd, header.cmd_len)
        assert fd == sg.FD and code == 0x2285
        assert cdb == prepared.reset.RESET_CDB
        assert header.interface_id == ord('S') and header.cmd_len == 16
        assert header.direction == -3 and header.data_len == 16 and header.timeout == 3000
        assert header.sense_max == 32 and header.iovec_count == header.flags == header.pack_id == 0
        sg.calls.append(dict(op=0xFC0C, cdb=cdb.hex(), direction=-3, data_len=16))
        C.memmove(header.data, cdb[:2] + b'\0' * 14, 16)
        return 0

    monkeypatch.setattr(reset.fcntl, 'ioctl', ioctl)
    result = reset.run_campaign(prepared)
    assert result == dict(request_completion=True, core_reset_observed=False, boot_observed=False)
    assert len(sg.calls) == before + 1 and sg.calls[-1]['op'] == 0xFC0C
    assert bytes(sg.flash) == original.policies[0].baseline
    assert len(sg.opened) == len(sg.closed) == 3
    rr = Path(c['receipt_path'])
    rows = [json.loads(row) for row in (rr / 'commands.jsonl').read_bytes().splitlines()]
    assert [row['event'] for row in rows] == ['stopped_choice_stock_reset_prepared',
        'reset_submit_intent', 'reset_sg_completion', 'reset_request_completed']
    assert rows[1]['cdb'] == 'fc0c00000001ffffffffffffffffffff'
    assert all(row['boot_observed'] is False for row in rows)
    marker = rr.parent / '.stopped-choice-stock-core-reset.consumed'
    assert marker.read_text() == prepared.campaign_sha256
    with pytest.raises(FileExistsError):
        reset.run_campaign(prepared)
    assert len(sg.calls) == before + 1
    out = Path(os.environ['LUNAR_ADMISSION_EVIDENCE'])
    (out / 'actual-stock-reset-summary.json').write_bytes(reset.canonical(dict(
        actual_private_factories_verified=True, actual_physical_ram_receipt_admitted=True,
        production_activation_pins_unchanged=True, reset_source_sha256=reset.digest(source.read_bytes()),
        restore_source_sha256=reset.RESTORE_SOURCE_SHA, backup_source_sha256=restore.BACKUP_SOURCE_SHA,
        backup_commands=8757, modeled_commands_before_reset=before, reset_requests=1,
        reset_cdb=rows[1]['cdb'], handles_opened=3, handles_closed=3,
        preserved_install_journal_sha256=proof.install_journal_sha256,
        baseline_sha256=reset.BASELINE_SHA, target_sha256=reset.TARGET_SHA,
        required_absent_paths=len(prepared.absent_paths), marker_preserved=True,
        request_completion=True, hardware_access=False, physical_reset_observed=False,
        boot_observed=False, display_observed=False, physical_recovery_verified=False)))

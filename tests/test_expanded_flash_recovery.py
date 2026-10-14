"""Expanded synthetic NOR recovery; boot/USB_KEY remain model assumptions."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.test_raw_flash_profile import sample
from tests.test_commit_last_recovery import loader_session
import expanded_flash_profile as expanded
from fm1_flash_transaction import create_transaction, run_transaction, digest
from fm1_simulated_device import SimulatedDevice
from fm1_recovery_campaign import LOADER_SHA256

ROOT = Path(__file__).resolve().parents[1]
APP = (0x4000, 0xD9000)


@pytest.mark.parametrize('direction', ['install', 'restore'])
@pytest.mark.parametrize('fault', ['erase-torn', 'program-torn', 'program-ack', 'commit-erase'])
def test_expanded_image_process_loss_and_rollback(sample, tmp_path, direction, fault):
    baseline = sample['baseline']
    app = b'A' * 838712
    target, _ = expanded.construct_geometry(baseline, baseline, sample['reference'], app)
    device = SimulatedDevice(baseline, path=tmp_path / 'device',
                             writable_ranges=(APP,), app_range=APP,
                             protected_ranges=((0, APP[0]), (APP[1], len(baseline))),
                             simulator_loader_sha256=LOADER_SHA256)
    device.register_bootable_image(target)
    transaction = tmp_path / 'transaction'
    create_transaction(transaction, baseline, baseline, target,
                       loader_session(device).identity(), (APP,),
                       'synthetic-expanded-092', commit_sector=APP[0])
    if direction == 'restore':
        run_transaction(transaction, loader_session(device))
    device.reset()
    sectors = [offset for offset in range(APP[0], APP[1], 4096)
               if baseline[offset:offset + 4096] != target[offset:offset + 4096]]
    operation = 'program' if fault.startswith('program') else 'erase'
    kind = 'ack_loss' if fault == 'program-ack' else 'torn'
    occurrence = len(sectors) if fault == 'commit-erase' else 1
    case = dict(kind='fault', direction=direction, operation=operation,
                fault=kind, occurrence=occurrence, after_bytes=127)
    (tmp_path / 'worker-case.json').write_text(json.dumps(case))
    worker = subprocess.run([sys.executable, str(ROOT / 'tools/fm1_recovery_campaign.py'),
                             '--worker', str(tmp_path)], capture_output=True, text=True, timeout=900)
    assert worker.returncode == 0, worker.stderr
    result = json.loads((tmp_path / 'worker-result.json').read_text())
    assert result == dict(status='rejected', error_type='SimulatedAckLoss' if kind == 'ack_loss' else 'SimulatedPowerLoss')
    assert json.loads((transaction / 'journal.json').read_text())['state'] == 'recovery_required'
    reopened = SimulatedDevice(path=tmp_path / 'device')
    assert reopened.flash[:APP[0]] == baseline[:APP[0]]
    assert reopened.flash[APP[1]:] == baseline[APP[1]:]
    if reopened.mode == 'app_unavailable':
        with pytest.raises(ValueError):
            reopened.soft_key()
        reopened.usb_key()
    desired = target if direction == 'install' else baseline
    initial = baseline if direction == 'install' else target
    address = APP[0] if fault == 'commit-erase' else APP[0] + 4096
    if operation == 'erase':
        torn = bytearray(initial[address:address + 4096])
        torn[:127] = b'\xff' * 127
    else:
        torn = bytearray(b'\xff' * 4096)
        written = 256 if kind == 'ack_loss' else 127
        torn[:written] = desired[address:address + written]
    assert reopened.flash[address:address + 4096] == torn
    if fault == 'commit-erase':
        assert reopened.flash[APP[0] + 4096:APP[1]] == desired[APP[0] + 4096:APP[1]]
    receipt = run_transaction(transaction, loader_session(reopened), direction)
    assert receipt['verified_sha256'] == digest(desired)
    assert receipt['sector_order'][-1] == APP[0]
    assert reopened.flash == desired
    if direction == 'install':
        expanded.validate_geometry(baseline, reopened.flash, sample['reference'], app)
    reopened.reset()
    assert reopened.mode == 'app'
    run_transaction(transaction, loader_session(reopened), 'restore')
    assert reopened.flash == baseline
    reopened.reset()
    assert reopened.mode == 'app'

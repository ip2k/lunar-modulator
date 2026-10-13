"""Process-reopened commit-last NOR recovery; synthetic device only."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from fm1_flash_transaction import create_transaction, run_transaction, digest
from fm1_simulated_device import SimulatedDevice
from fm1_recovery_campaign import LOADER, LOADER_SHA256

APP = (4096, 12288)
# Commit-sector first/last page and erase boundaries, in both directions.
FAULTS = [(operation, kind, occurrence, prefix)
          for operation, kind, occurrence, prefix in [
              ('erase', 'torn', 2, 0), ('erase', 'torn', 2, 2047),
              ('erase', 'torn', 2, 4096), ('erase', 'ack_loss', 2, 0),
              ('erase', 'disconnect_before', 2, 0),
              ('program', 'torn', 17, 0), ('program', 'torn', 17, 1),
              ('program', 'torn', 17, 127), ('program', 'torn', 17, 256),
              ('program', 'torn', 32, 0), ('program', 'torn', 32, 255),
              ('program', 'torn', 32, 256), ('program', 'ack_loss', 17, 0),
              ('program', 'ack_loss', 32, 0),
              ('program', 'disconnect_before', 17, 0),
              ('program', 'disconnect_before', 32, 0)]]


def loader_session(device):
    if device.mode == 'app' and device.connected:
        device.soft_key()
    return device.recovery_session(LOADER)


@pytest.mark.parametrize('direction', ['install', 'restore'])
@pytest.mark.parametrize('operation,kind,occurrence,prefix', FAULTS)
def test_commit_last_fault_reopens_and_recovers(tmp_path, direction, operation,
                                               kind, occurrence, prefix):
    stock = b'\xa5' * (1024 * 1024)
    target = stock[:APP[0]] + b'\x3c' * (APP[1] - APP[0]) + stock[APP[1]:]
    device = SimulatedDevice(stock, path=tmp_path / 'device',
                             writable_ranges=(APP,), app_range=APP,
                             protected_ranges=((0, APP[0]), (APP[1], len(stock))),
                             simulator_loader_sha256=LOADER_SHA256)
    device.register_bootable_image(target)
    transaction = tmp_path / 'transaction'
    create_transaction(transaction, stock, stock, target,
                       loader_session(device).identity(), (APP,),
                       'synthetic-commit-last', commit_sector=APP[0])
    if direction == 'restore':
        run_transaction(transaction, loader_session(device))
    device.reset()
    desired = target if direction == 'install' else stock
    case = dict(kind='fault', direction=direction, operation=operation,
                fault=kind, occurrence=occurrence, after_bytes=prefix)
    (tmp_path / 'worker-case.json').write_text(json.dumps(case))
    # Existing worker runs the real transaction engine against the persistent
    # protocol model. Exit discards every live handle and RAM loader instance.
    worker = ROOT / 'tools/fm1_recovery_campaign.py'
    result = subprocess.run([sys.executable, str(worker), '--worker', str(tmp_path)],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    worker_result = json.loads((tmp_path / 'worker-result.json').read_text())
    assert worker_result['status'] == 'rejected'
    assert worker_result['error_type'] == {
        'torn': 'SimulatedPowerLoss', 'ack_loss': 'SimulatedAckLoss',
        'disconnect_before': 'SimulatedDisconnect'}[kind]
    assert json.loads((transaction / 'journal.json').read_text())['state'] == 'recovery_required'
    reopened = SimulatedDevice(path=tmp_path / 'device')
    # The noncommit sector was fully verified before any commit-sector command.
    assert reopened.flash[8192:12288] == desired[8192:12288]
    initial = stock if direction == 'install' else target
    commit = bytearray(initial[4096:8192])
    if operation == 'erase':
        written = prefix if kind == 'torn' else 4096 if kind == 'ack_loss' else 0
        commit[:written] = b'\xff' * written
    else:
        commit[:] = b'\xff' * 4096
        previous = (occurrence - 17) * 256
        commit[:previous] = desired[4096:4096 + previous]
        written = prefix if kind == 'torn' else 256 if kind == 'ack_loss' else 0
        commit[previous:previous + written] = desired[4096 + previous:4096 + previous + written]
    assert reopened.flash[4096:8192] == commit
    assert reopened.flash[:APP[0]] == stock[:APP[0]]
    assert reopened.flash[APP[1]:] == stock[APP[1]:]
    if reopened.mode == 'app_unavailable':
        with pytest.raises(ValueError):
            reopened.soft_key()
        reopened.usb_key()
    receipt = run_transaction(transaction, loader_session(reopened), direction)
    assert receipt['sector_order'] == [8192, 4096]
    assert receipt['verified_sha256'] == digest(desired)
    assert reopened.flash == desired
    # Roll back through a fresh modeled boot/loader boundary, verifying all NOR.
    reopened.reset()
    assert reopened.mode == 'app'
    run_transaction(transaction, loader_session(reopened), 'restore')
    assert reopened.flash == stock
    reopened.reset()
    assert reopened.mode == 'app'

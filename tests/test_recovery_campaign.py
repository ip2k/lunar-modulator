"""Synthetic recovery campaign checks; never open a physical transport."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fm1_recovery_campaign as campaign


def test_catalog_is_stable_complete_and_unique():
    cases = campaign.case_catalog()
    assert 256 <= len(cases) <= 500
    assert len({c["name"] for c in cases}) == len(cases)
    assert [c["index"] for c in cases] == list(range(len(cases)))
    for direction in ("install", "restore"):
        torn = [c for c in cases if c.get("operation") == "program"
                and c.get("fault") == "torn" and c["direction"] == direction]
        assert {(c["occurrence"], c["after_bytes"]) for c in torn} == {
            (page, prefix) for page in range(1, 33) for prefix in (0, 1, 127, 255, 256)}


def test_public_fixture_only_changes_two_app_sectors():
    stock, target = campaign.fixtures()
    assert len(stock) == len(target) == 1024 * 1024
    assert stock[:0x4000] == target[:0x4000]
    assert stock[0x6000:] == target[0x6000:]
    assert stock[0x4000:0x6000] != target[0x4000:0x6000]
    assert len(campaign.LOADER) == 24064
    assert campaign.LOADER_SHA256 == hashlib.sha256(campaign.LOADER).hexdigest()
    assert campaign.fixtures() == (stock, target)
    assert campaign.fixtures(campaign.SEED + 1) != (stock, target)


def test_baseline_round_trip_and_receipt_are_reproducible(tmp_path):
    a = campaign.run_campaign(tmp_path / "a", [0])
    b = campaign.run_campaign(tmp_path / "b", [0])
    assert a == b
    assert a["model_only"] is True
    assert a["hardware_validated"] is False
    assert a["receipts"][0]["process_reopened"] is True
    assert a["baseline_receipt_sha256"] == campaign.digest(
        campaign.canonical(a["receipts"][0]))
    assert "flash.bin" not in json.dumps(a)


@pytest.mark.parametrize("name", [
    "install-torn-page-00-0", "install-torn-page-15-127", "restore-torn-page-31-256",
    "install-erase-1-ack_loss", "restore-program-32-disconnect_before",
    "install-torn-erase-2-4096", "install-verify_corruption", "restore-verify_corruption",
    "install-crash_intent", "restore-crash_after_write", "usb_key_recovery",
    "stale_handle", "completed_journal_readback", "corrupt_backup_a", "corrupt_backup_b",
    "corrupt_target", "corrupt_journal", "corrupt_plan", "wrong_unit", "out_of_range",
    "unexpected_preflight_change",
    "corrupt_journal_state", "corrupt_journal_direction", "corrupt_journal_intent",
])
def test_representative_faults_restore_all_bytes(tmp_path, name):
    case = next(c for c in campaign.case_catalog() if c["name"] == name)
    result = campaign.run_case(tmp_path, case)
    assert result["outcome"] == "passed"
    assert result["full_image_preserved"] is True
    assert result["final_flash_sha256"] == result["stock_sha256"]
    assert result["hardware_validated"] is False


def test_cli_range_selection_and_output(tmp_path):
    output = tmp_path / "receipt.json"
    result = subprocess.run([sys.executable, str(Path(campaign.__file__)),
                             "--case-range", "1:3", "--state-dir", str(tmp_path / "state"),
                             "--output", str(output)], capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_text())
    assert receipt == json.loads(result.stdout)
    assert [r["index"] for r in receipt["receipts"]] == [1, 2]
    assert len(receipt["baseline_receipt_sha256"]) == 64


@pytest.mark.parametrize("selection", ["-1", "999", "0:0", "bad"])
def test_cli_rejects_invalid_selection_without_a_device(tmp_path, selection):
    option = "--case" if ":" not in selection and selection != "bad" else "--case-range"
    state = tmp_path / "absent"
    result = subprocess.run([sys.executable, str(Path(campaign.__file__)), option, selection,
                             "--state-dir", str(state)], capture_output=True, text=True)
    assert result.returncode == 2
    assert not state.exists()

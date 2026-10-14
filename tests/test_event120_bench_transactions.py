"""Offline Event Horizon transaction boundaries and interruption recovery model."""
import json
from pathlib import Path

import pytest

from tools.native.event120_bench_transactions import (
    APP_BASE, AREA_END, BASELINE_SHA, changed_ranges)
from tools.fm1_flash_transaction import (FLASH_SIZE, SECTOR_BYTES, create_transaction,
                                         load_transaction, run_transaction)


def image(changes=()):
    data = bytearray(b"\xff" * FLASH_SIZE)
    for offset, value in changes:
        data[offset:offset + SECTOR_BYTES] = bytes([value]) * SECTOR_BYTES
    return bytes(data)


def test_changed_ranges_refuse_protected_or_non_directory_first_changes():
    before = image()
    assert changed_ranges(before, image(((APP_BASE, 0x11),
                                         (APP_BASE + SECTOR_BYTES, 0x22)))) == [
        [APP_BASE, APP_BASE + 2 * SECTOR_BYTES]]
    with pytest.raises(ValueError, match="Protected"):
        changed_ranges(before, image(((0, 0x33), (APP_BASE, 0x11))))
    with pytest.raises(ValueError, match="directory"):
        changed_ranges(before, image(((APP_BASE + SECTOR_BYTES, 0x11),)))


class FakeSession:
    def __init__(self, flash, identity, fail_once=False):
        self.flash = bytearray(flash)
        self.unit = identity
        self.fail_once = fail_once
        self.writes = []

    def identity(self):
        return self.unit

    def online(self):
        return 3, 0x856014

    def read(self, address, size):
        return bytes(self.flash[address:address + size])

    def erase(self, address):
        self.writes.append(("erase", address))
        self.flash[address:address + SECTOR_BYTES] = b"\xff" * SECTOR_BYTES

    def program(self, address, data):
        self.writes.append(("program", address))
        if self.fail_once:
            self.fail_once = False
            self.flash[address:address + 17] = data[:17]
            raise OSError("synthetic interrupted page")
        self.flash[address:address + len(data)] = data


def test_interrupted_candidate_journal_restores_fresh_current_then_stock(tmp_path):
    baseline = image(((APP_BASE, 0x10),))
    candidate = image(((APP_BASE, 0x20), (APP_BASE + SECTOR_BYTES, 0x21)))
    stock = image(((APP_BASE, 0x30),))
    identity = dict(unit_id="synthetic-device38", flash_size=FLASH_SIZE,
        sector_size=SECTOR_BYTES, page_size=256, jedec=0x856014, simulated=True)
    candidate_dir = tmp_path / "candidate"
    plan = create_transaction(candidate_dir, baseline, baseline, candidate, identity,
        changed_ranges(baseline, candidate), "offline candidate fault model",
        commit_sector=APP_BASE)
    assert plan["sector_order"][-1] == APP_BASE
    interrupted = FakeSession(baseline, identity, fail_once=True)
    with pytest.raises(OSError, match="synthetic interrupted"):
        run_transaction(candidate_dir, interrupted)
    journal = json.loads((candidate_dir / "journal.json").read_text())
    assert journal["state"] == "recovery_required"
    recovered = FakeSession(interrupted.flash, identity)
    run_transaction(candidate_dir, recovered, direction="restore")
    assert bytes(recovered.flash) == baseline

    stock_dir = tmp_path / "stock"
    stock_plan = create_transaction(stock_dir, baseline, baseline, stock, identity,
        changed_ranges(baseline, stock), "offline stock rollback fault model",
        commit_sector=APP_BASE)
    assert stock_plan["sector_order"][-1] == APP_BASE
    apply_stock = FakeSession(baseline, identity)
    run_transaction(stock_dir, apply_stock)
    assert bytes(apply_stock.flash) == stock
    assert load_transaction(candidate_dir)[1]["state"] == "complete"
    assert load_transaction(candidate_dir)[1]["direction"] == "restore"


@pytest.fixture(scope="module")
def private_transaction_report(tmp_path_factory):
    import os
    root = os.environ.get("FM1_DEVICE38_EVENT120_INPUTS")
    if not root:
        pytest.skip("Exact private device38 and candidate evidence not mounted")
    from tools.native.event120_bench_transactions import prepare
    root = Path(root)
    if not os.access(root / "manifest.json", os.R_OK):
        pytest.skip("Container UID cannot read private evidence mount")
    stock = Path(os.environ.get("FM1_DEVICE38_STOCK_INPUTS",
        "/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1"))
    output = tmp_path_factory.mktemp("event120-plans") / "session"
    target = Path(os.environ.get("FM1_EVENT120_TARGET",
        "/home/claude/.local/share/codex-private/shapes8-event120-expanded-candidate-20261014/target.bin"))
    return prepare(output, root, target, stock / "stockA.bin", stock / "stockB.bin")


def test_exact_device38_private_inputs_prepare_only_disarmed_plans(private_transaction_report):
    report = private_transaction_report
    assert report["baseline_sha256"] == BASELINE_SHA
    assert report["candidate_transport_manifest_admitted"] is False
    assert report["hardware_admitted"] is False
    assert report["physical_writer_ready"] is False
    assert report["installable"] is False
    assert report["physical_recovery_verified"] is False
    assert report["plans"]["event120-candidate"]["commit_sector"] == APP_BASE
    assert report["plans"]["stock-rollback"]["commit_sector"] == APP_BASE

"""Synthetic-only checks for the distinct cold-ROM backup admission path."""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import fm1_cold_rom_backup as adapter


USB = {"path": "1-2.3", "busnum": "1", "devnum": "17",
       "vid": "4c4a", "pid": "8057"}
FW = "a" * 64
BUILD = "b" * 64


def entry(*, usb=None, observed=1030.0, firmware=FW, build=BUILD):
    return {
        "schema": adapter.SCHEMA,
        "kind": adapter.ENTRY_KIND,
        "source": adapter.SOURCE,
        "owner_attestation": {
            "performed_usb_key_once": True,
            "selected_physical_unit": True,
            "rom_device_is_selected_unit": True,
            "identity_basis": "owner-attested-physical-selection",
            "usb_serial": None,
            "status_observation": {"method": "status-leds",
                                   "value": "operator recorded amber indicator, then dark"},
        },
        "dongle_upload": {
            "firmware_sha256": firmware,
            "build_receipt_sha256": build,
            "owner_confirmed_exact_image_uploaded": True,
        },
        "attempt_started_at": 1000.0,
        "status_observed_at": 1010.0,
        "rom_enumeration": {"observed_at": observed,
                            "candidates": [dict(USB if usb is None else usb)]},
        "target_port": {"path": USB["path"], "was_absent_before_attempt": True},
        "rom_usb": dict(USB if usb is None else usb),
    }


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def test_owner_observation_and_fresh_rom_binding_validate():
    assert adapter.validate_entry(encoded(entry()), USB, FW, now=1050.0) == 1030.0


@pytest.mark.parametrize("mutate", [
    lambda e: e["owner_attestation"].update(performed_usb_key_once=False),
    lambda e: e["owner_attestation"].update(selected_physical_unit=False),
    lambda e: e["owner_attestation"].update(rom_device_is_selected_unit=False),
    lambda e: e["owner_attestation"].update(usb_serial="guessed-serial"),
    lambda e: e["owner_attestation"]["status_observation"].update(value=""),
    lambda e: e["dongle_upload"].update(owner_confirmed_exact_image_uploaded=False),
    lambda e: e["dongle_upload"].update(firmware_sha256="c" * 64),
    lambda e: e["dongle_upload"].update(build_receipt_sha256="not-a-hash"),
    lambda e: e["rom_enumeration"].update(observed_at=999.0),
    lambda e: e["rom_enumeration"]["candidates"].append(dict(USB)),
    lambda e: e["target_port"].update(was_absent_before_attempt=False),
    lambda e: e["rom_usb"].update(devnum="18"),
])
def test_invalid_or_uncorrelated_entry_is_rejected(mutate):
    ev = entry()
    mutate(ev)
    with pytest.raises(ValueError):
        adapter.validate_entry(encoded(ev), USB, FW, now=1050.0)


def test_entry_expiry_is_admission_time_bounded():
    with pytest.raises(ValueError, match="stale"):
        adapter.validate_entry(encoded(entry()), USB, FW, now=1200.0)


def operations():
    ops = [SimpleNamespace(label="inquiry")]
    ops += [SimpleNamespace(label="upload") for _ in range(47)]
    ops += [SimpleNamespace(label=x) for x in ("jump", "buffer", "online")]
    for name in ("dumpA.bin", "dumpB.bin"):
        for address in range(0, adapter.fixed.FLASH_SIZE, adapter.fixed.PAGE):
            if address % 4096 == 0:
                ops.append(SimpleNamespace(label="online"))
            ops.append(SimpleNamespace(label=name))
        ops.append(SimpleNamespace(label=name + ".end"))
    return tuple(ops)


class FakeTransport:
    """No USB, SG_IO, or device access; deterministic synthetic page stream."""
    def __init__(self, prepared, log):
        self.prepared = prepared
        self.next = 0
        self.mapping = {"synthetic": True}
        self.failed = False

    def exchange_next(self):
        op = self.prepared.operations[self.next]
        self.next += 1
        data = b"R" * adapter.fixed.PAGE if op.label in ("dumpA.bin", "dumpB.bin") else b""
        return op, data

    def binding(self):
        return None

    def close(self):
        pass


def prepared(tmp_path, *, entered=1990.0):
    return SimpleNamespace(
        config={"usb_binding": dict(USB), "entry_path": str(tmp_path / "entry.json"),
                "dongle_build_receipt_sha256": BUILD},
        manifest_sha256="d" * 64, entered_at=entered,
        operations=operations(), request_inventory_sha256="e" * 64,
        owner_status_observation={"method": "status-leds", "value": "synthetic"})


def test_campaign_runs_one_synthetic_paired_full_flash_read(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    (tmp_path / "entry.json").write_text("{}")
    monkeypatch.setattr(adapter.fixed, "FixedSG", FakeTransport)
    now = [2000.0]
    monkeypatch.setattr(adapter.time, "time", lambda: now[0])
    result = adapter.run_campaign(prepared(tmp_path), tmp_path / "receipt",
                                  "f" * 64, FW)
    assert result["flash_bytes"] == 0x100000
    assert result["identical"] is True
    assert result["dumps"][0]["sha256"] == result["dumps"][1]["sha256"]
    assert result["write_admission"] is False
    assert result["physical_recovery_verified"] is False
    assert (tmp_path / "receipt" / "dumpA.bin").stat().st_size == 0x100000
    assert (tmp_path / (".cold-rom-" + "f" * 64 + ".consumed")).exists()


def test_campaign_claims_entry_once_even_if_output_path_changes(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    (tmp_path / "entry.json").write_text("{}")
    monkeypatch.setattr(adapter.fixed, "FixedSG", FakeTransport)
    monkeypatch.setattr(adapter.time, "time", lambda: 2000.0)
    p = prepared(tmp_path)
    adapter.run_campaign(p, tmp_path / "first", "f" * 64, FW)
    with pytest.raises(FileExistsError):
        adapter.run_campaign(p, tmp_path / "second", "f" * 64, FW)
    assert not (tmp_path / "second" / "manifest.json").exists()


def test_expired_admission_fails_before_transport_open(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    opened = []
    monkeypatch.setattr(adapter.fixed, "FixedSG", lambda *args: opened.append(True))
    monkeypatch.setattr(adapter.time, "time", lambda: 2000.0)
    with pytest.raises(ValueError, match="expired"):
        adapter.run_campaign(prepared(tmp_path, entered=100.0),
                             tmp_path / "receipt", "f" * 64, FW)
    assert opened == []


def test_unknown_operation_cannot_be_consumed_as_a_successful_campaign(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    (tmp_path / "entry.json").write_text("{}")
    monkeypatch.setattr(adapter.fixed, "FixedSG", FakeTransport)
    monkeypatch.setattr(adapter.time, "time", lambda: 2000.0)
    p = prepared(tmp_path)
    p.operations = (SimpleNamespace(label="erase-all"),) + p.operations[1:]
    with pytest.raises(ValueError, match="Full 1 MiB"):
        adapter.run_campaign(p, tmp_path / "receipt", "f" * 64, FW)
    assert not (tmp_path / "receipt" / "manifest.json").exists()

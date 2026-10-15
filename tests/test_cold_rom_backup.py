"""Synthetic-only checks for the distinct cold-ROM backup admission path."""
import hashlib
import json
from pathlib import Path
import types
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
        },
        "dongle_upload": {
            "firmware_sha256": firmware,
            "build_receipt_sha256": build,
            "coordinator_uploaded_exact_image": True,
        },
        "attempt_started_at": 1000.0,
        "uploaded_at": 1005.0,
        "owner_key_action_at": 1008.0,
        "status_observed_at": 1010.0,
        "status_observation": {"method": "owner-leds",
                                "value": "operator recorded amber indicator, then dark"},
        "rom_enumeration": {"observed_at": observed,
                            "candidates": [dict(USB if usb is None else usb)]},
        "target_port": {"path": USB["path"], "was_absent_before_attempt": True},
        "rom_usb": dict(USB if usb is None else usb),
    }


def encoded(value):
    return json.dumps(value, sort_keys=True).encode()


def test_owner_observation_and_fresh_rom_binding_validate():
    assert adapter.validate_entry(encoded(entry()), USB, FW, now=1050.0) == 1030.0


def test_coordinator_jtag_status_is_literal_and_does_not_require_an_abi():
    ev = entry()
    ev["status_observation"] = {"method": "coordinator-read-jtag",
                                "value": "operator captured raw status bytes 02 00 01"}
    assert adapter.validate_entry(encoded(ev), USB, FW, now=1050.0) == 1030.0


def test_old_pinned_upload_can_precede_a_fresh_physical_entry():
    ev = entry(observed=5030.0)
    ev.update(attempt_started_at=1000.0, uploaded_at=1005.0,
              owner_key_action_at=5008.0, status_observed_at=5010.0)
    assert adapter.validate_entry(encoded(ev), USB, FW, now=5050.0) == 5030.0


def test_stale_key_action_is_rejected_even_when_enumeration_is_fresh():
    ev = entry(observed=5030.0)
    ev.update(attempt_started_at=1000.0, uploaded_at=1005.0,
              owner_key_action_at=4900.0, status_observed_at=5020.0)
    with pytest.raises(ValueError, match="stale"):
        adapter.validate_entry(encoded(ev), USB, FW, now=5050.0)


def test_stale_enumeration_is_rejected():
    with pytest.raises(ValueError, match="stale"):
        adapter.validate_entry(encoded(entry()), USB, FW, now=1200.0)


@pytest.mark.parametrize("mutate", [
    lambda e: e["owner_attestation"].update(performed_usb_key_once=False),
    lambda e: e["owner_attestation"].update(selected_physical_unit=False),
    lambda e: e["owner_attestation"].update(rom_device_is_selected_unit=False),
    lambda e: e["owner_attestation"].update(usb_serial="guessed-serial"),
    lambda e: e["status_observation"].update(value=""),
    lambda e: e["status_observation"].update(method="invented-console-ack"),
    lambda e: e["dongle_upload"].update(coordinator_uploaded_exact_image=False),
    lambda e: e["dongle_upload"].update(firmware_sha256="c" * 64),
    lambda e: e["dongle_upload"].update(build_receipt_sha256="not-a-hash"),
    lambda e: e["rom_enumeration"].update(observed_at=999.0),
    lambda e: e["rom_enumeration"]["candidates"].append(dict(USB)),
    lambda e: e.update(owner_key_action_at=1004.0),
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


def test_prepare_pins_cold_entry_and_builds_exact_read_inventory(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    loader = b"L" * adapter.fixed.LOADER_SIZE
    loader_sha = hashlib.sha256(loader).hexdigest()
    monkeypatch.setattr(adapter.fixed, "LOADER_SHA", loader_sha)
    monkeypatch.setattr(adapter.fixed, "ORIGINAL_SHA", "f" * 64)
    reader_path = Path(adapter.fixed.__file__).with_name("fm1_uboot_read.py")
    reader_source = reader_path.read_bytes()
    reader = types.ModuleType("_test_cold_reader")
    exec(compile(reader_source, str(reader_path), "exec"), reader.__dict__)
    # Create the pinned upload profile expected by the fixed loader adapter.
    profile_inventory = []
    for index, offset in enumerate(range(0, len(loader), 512)):
        payload = loader[offset:offset + 512]
        cdb, _data, read_size = reader.request(0xFB06, "rom",
            address=adapter.fixed.RAM + offset, payload=payload)
        profile_inventory.append({"index": index, "address": adapter.fixed.RAM + offset,
            "bytes": 512, "cdb_sha256": adapter.fixed.digest(cdb),
            "payload_sha256": adapter.fixed.digest(payload), "read_size": read_size})
    profile_bytes = json.dumps({"upload_inventory": profile_inventory,
        "patched_encrypted_sha256": adapter.fixed.LOADER_SHA,
        "original_encrypted_sha256": adapter.fixed.ORIGINAL_SHA}).encode()
    monkeypatch.setattr(adapter.fixed, "PROFILE_SHA", hashlib.sha256(profile_bytes).hexdigest())
    monkeypatch.setattr(adapter.fixed, "PROFILE_SOURCE_SHA",
                        hashlib.sha256(b"profile-source").hexdigest())
    firmware, build = b"firmware image", b"build receipt"
    firmware_sha = hashlib.sha256(firmware).hexdigest()
    build_sha = hashlib.sha256(build).hexdigest()
    ev = entry(firmware=firmware_sha, build=build_sha)
    entry_bytes = encoded(ev)
    entry_path = tmp_path / "entry.json"
    entry_path.write_bytes(entry_bytes)

    paths = {
        "adapter": tmp_path / "adapter.py", "fixed": tmp_path / "fixed.py",
        "reader": tmp_path / "reader.py", "loader": tmp_path / "loader.bin",
        "profile": tmp_path / "profile.json", "profile_source": tmp_path / "profile.py",
        "firmware": tmp_path / "dongle.uf2", "build": tmp_path / "build.json",
    }
    source_data = {"loader": loader, "profile": profile_bytes,
        "profile_source": b"profile-source", "firmware": firmware, "build": build}
    source_hash = {name: hashlib.sha256(data).hexdigest()
                   for name, data in source_data.items()}
    source_hash["adapter"] = hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest()
    real_pinned_file = adapter.fixed.pinned_file

    def pinned(path, expected):
        candidate = Path(path)
        name = next((key for key, value in paths.items() if value == candidate), None)
        if (candidate in (Path(adapter.__file__).absolute(),
                          Path(adapter.fixed.__file__).absolute(), reader_path.absolute()) or
                candidate == entry_path):
            return real_pinned_file(path, expected)
        if name is None:
            raise AssertionError(Path(path))
        value = source_data[name]
        assert hashlib.sha256(value).hexdigest() == expected
        return value

    monkeypatch.setattr(adapter.fixed, "pinned_file", pinned)
    monkeypatch.setattr(adapter.time, "time", lambda: 1050.0)
    config = {"schema": 1, "kind": adapter.KIND,
        "adapter_sha256": source_hash["adapter"],
        "fixed_adapter_sha256": adapter.FIXED_ADAPTER_SHA256,
        "reader_sha256": adapter.fixed.READER_SHA,
        "loader_path": str(paths["loader"]), "profile_path": str(paths["profile"]),
        "profile_source_path": str(paths["profile_source"]),
        "entry_path": str(entry_path), "entry_sha256": hashlib.sha256(entry_bytes).hexdigest(),
        "dongle_firmware_path": str(paths["firmware"]),
        "dongle_firmware_sha256": firmware_sha,
        "dongle_build_receipt_path": str(paths["build"]),
        "dongle_build_receipt_sha256": build_sha,
        "usb_binding": dict(USB), "receipt_path": str(tmp_path / "receipt")}
    campaign = tmp_path / "campaign.json"
    campaign.write_text(json.dumps(config))
    prepared, receipt, entry_sha, image_sha = adapter.prepare_campaign(campaign, now=1050.0)
    assert len(prepared.operations) == 8757
    assert prepared.config["_status_observation"] == ev["status_observation"]
    assert receipt == tmp_path / "receipt"
    assert entry_sha == hashlib.sha256(entry_bytes).hexdigest()
    assert image_sha == firmware_sha
    assert sum(op.label == "dumpA.bin" for op in prepared.operations) == 4096
    assert sum(op.label == "dumpB.bin" for op in prepared.operations) == 4096
    assert {op.cdb[:2] for op in prepared.operations} == {
        b"\x12\x00", b"\xfb\x06", b"\xfb\x08", b"\xfc\x14",
        b"\xfc\x0a", b"\xfd\x05"}


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
                "dongle_build_receipt_sha256": BUILD,
                "_owner_physical_attestation": {"selected_physical_unit": True,
                                                 "performed_usb_key_once": True},
                "_status_observation": {"method": "owner-leds", "value": "synthetic"},
                "_coordinator_upload_record": {"coordinator_uploaded_exact_image": True}},
        manifest_sha256="d" * 64, entered_at=entered,
        operations=operations(), request_inventory_sha256="e" * 64,
        )


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

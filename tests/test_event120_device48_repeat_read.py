"""Exercise full-read acceptance/refusal with an in-memory transport seam."""
from contextlib import contextmanager
import ctypes
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_event120_device48_repeat_boot import read_adapter


@pytest.mark.parametrize("devnum", ["42", "44", "45", "46", "47"])
def test_read_snapshot_rejects_foreign_enumeration(devnum):
    raw = read_adapter.canonical({
        "schema": 1, "kind": read_adapter.SNAPSHOT_KIND, "observed_at": 1000,
        "usb_binding": dict(read_adapter.USB, devnum=devnum), "sg_binding": {},
    })
    with pytest.raises(ValueError, match="Fresh exact passive"):
        read_adapter._snapshot(raw, 1000)


def _run_with_memory_transport(monkeypatch, tmp_path, *, fault=None):
    image = b"\xa5" * (1048576 if fault != "short" else 1048575)
    expected = hashlib.sha256(image).hexdigest()
    if fault == "hash":
        expected = "0" * 64
    monkeypatch.setattr(read_adapter, "TARGET_SHA", expected)
    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    receipt = parent / "read-receipt"
    marker = parent / ".consumed"
    mapping = {"node": "/dev/sg-mock"}

    class Op:
        def __init__(self, label):
            self.label = label

    operations = [Op("dumpA.bin"), Op("dumpA.bin.end"), Op("dumpB.bin"), Op("dumpB.bin.end")]
    p = SimpleNamespace(
        config={"receipt_path": str(receipt), "adapter_sha256": "1" * 64,
                "snapshot_sha256": "2" * 64,
                "snapshot_path": str(parent / "rom-snapshot.json")},
        manifest_sha256="b" * 64, request_inventory_sha256="c" * 64,
        operations=operations,
    )

    class Transport:
        def __init__(self, *_args):
            self.mapping, self.next, self.failed = mapping, 0, False

        def exchange_next(self):
            op = operations[self.next]
            self.next += 1
            return op, image if op.label in ("dumpA.bin", "dumpB.bin") else b""

        def binding(self):
            return None

        def close(self):
            return None

    bridge = SimpleNamespace(
        FixedSG=Transport, FLASH_SIZE=1048576,
        LOADER_SHA="d" * 64, PROFILE_SHA="e" * 64,
        PROFILE_SOURCE_SHA="f" * 64,
        private_file=lambda path, mode="wb": open(path, mode),
        sync_dir=lambda _path: None,
    )
    monkeypatch.setattr(read_adapter, "prepare",
        lambda _path: (bridge, p, mapping, marker, {}))
    result = read_adapter.run(parent / "read-campaign.json")
    return result, receipt


@pytest.mark.parametrize("fault", [None, "short", "hash"])
def test_read_accepts_only_two_complete_matching_full_images(monkeypatch, tmp_path, fault):
    if fault is None:
        manifest, receipt = _run_with_memory_transport(monkeypatch, tmp_path)
        assert manifest["identical"] is True
        assert manifest["flash_operations"] == 0 and manifest["reset_operations"] == 0
        assert manifest["install_history_proven"] is False
        assert [entry["bytes"] for entry in manifest["dumps"]] == [1048576, 1048576]
        assert (receipt / "dumpA.bin").read_bytes() == (receipt / "dumpB.bin").read_bytes()
        return
    with pytest.raises(ValueError, match="Full dump differs"):
        _run_with_memory_transport(monkeypatch, tmp_path, fault=fault)
    receipt = tmp_path / "private" / "read-receipt"
    assert not (receipt / "manifest.json").exists()
    assert (tmp_path / "private" / ".consumed").exists()


def test_read_marker_is_bound_to_enumeration_not_snapshot_timestamp(tmp_path):
    usb = dict(read_adapter.USB)
    sg = {"node": "/dev/sg4", "node_identity": [0, 5, 14]}
    first = read_adapter.marker_path(tmp_path, usb, sg)
    assert first.name.startswith('.event12048-rom-')
    refreshed_snapshot = {"observed_at": 1234567890, "usb_binding": usb, "sg_binding": sg}
    second = read_adapter.marker_path(
        tmp_path, refreshed_snapshot["usb_binding"], refreshed_snapshot["sg_binding"])
    assert first == second
    first.write_bytes(b"consumed")
    assert second.exists()


def test_prepare_refuses_refreshed_snapshot_for_consumed_enumeration(monkeypatch, tmp_path):
    import json
    import os
    import stat

    parent = tmp_path / "private"
    parent.mkdir(mode=0o700)
    os.chmod(parent, 0o700)
    usb = dict(read_adapter.USB)
    mapping = {"node": "/dev/sg-test", "node_identity": [1, 2, 3]}

    class Bridge:
        LOADER_SHA = "a" * 64
        PROFILE_SHA = "b" * 64
        PROFILE_SOURCE_SHA = "c" * 64
        LOADER_SIZE = 4
        PreparedCampaign = lambda *args: SimpleNamespace(config=args[0])

        @staticmethod
        def validate_usb(_usb):
            return None

        @staticmethod
        def discover_sg(_usb):
            return mapping

        @staticmethod
        def pinned_file(_path, expected):
            return b"load" if expected == Bridge.LOADER_SHA else b"{}"

        @staticmethod
        def inventory_digest(_ops):
            return read_adapter.INVENTORY_SHA

    class Header(ctypes.Structure):
        _fields_ = [("raw", ctypes.c_uint8 * 88)]

    modules = {
        "fm1_fixed_loader_backup.py": Bridge,
        "fm1_uboot_read.py": SimpleNamespace(SGHeader=Header),
        "fm1_returned_rom_backup.py": SimpleNamespace(
            inventory=lambda *_args: [object()] * 8757),
    }
    # The production loader requests the three pinned sources by basename.
    monkeypatch.setattr(read_adapter, "load_source",
        lambda path, _sha, _name: modules[Path(path).name])
    original_open = read_adapter.os.open
    device_opens = []

    def tracked_open(path, *args, **kwargs):
        if str(path).startswith("/dev/"):
            device_opens.append(str(path))
            raise AssertionError("Device open attempted after consumed enumeration")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(read_adapter.os, "open", tracked_open)
    campaign_path = parent / "read-campaign.json"
    receipt = parent / "read-receipt"
    snapshot_path = parent / "snapshot.json"
    for observed_at in (1000, 1100):
        snapshot = {"schema": 1, "kind": read_adapter.SNAPSHOT_KIND,
                    "observed_at": observed_at, "usb_binding": usb, "sg_binding": mapping}
        snapshot_raw = read_adapter.canonical(snapshot)
        snapshot_path.write_bytes(snapshot_raw)
        campaign = {
            "schema": 1, "kind": read_adapter.KIND,
            "adapter_sha256": read_adapter.digest(read_adapter.read_file(
                Path(read_adapter.__file__).absolute())),
            "snapshot_path": str(snapshot_path),
            "snapshot_sha256": read_adapter.digest(snapshot_raw),
            "loader_path": "/unused/loader", "profile_path": "/unused/profile",
            "profile_source_path": "/unused/profile.c", "usb_binding": usb,
            "receipt_path": str(receipt),
        }
        campaign_path.write_text(json.dumps(campaign))
        marker = read_adapter.marker_path(parent, usb, mapping)
        marker.write_bytes(b"previously consumed")
        with pytest.raises(ValueError, match="enumeration is already consumed"):
            read_adapter.prepare(campaign_path, now=observed_at)
        marker.unlink()
    assert device_opens == []

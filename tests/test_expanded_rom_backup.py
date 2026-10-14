"""Offline admission checks for the exact device38 dual-read adapter."""
import ctypes
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import fm1_expanded_rom_backup as adapter

ROOT = Path(__file__).resolve().parents[1]
USB = {"path": "1-1", "busnum": "1", "devnum": "38", "vid": "4c4a", "pid": "8057"}


class Header(ctypes.Structure):
    _fields_ = [("raw", ctypes.c_ubyte * 88)]


class Bridge:
    LOADER_SHA = "fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c"
    PROFILE_SHA = "3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe"
    PROFILE_SOURCE_SHA = "9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8"
    LOADER_SIZE = 24064

    @staticmethod
    def validate_usb(usb):
        assert usb == USB

    @staticmethod
    def discover_sg(usb):
        assert usb == USB
        return {"node": "/dev/sg-test", "simulated": True}

    @staticmethod
    def pinned_file(path, expected):
        if expected == Bridge.LOADER_SHA:
            return b"L" * Bridge.LOADER_SIZE
        if expected == Bridge.PROFILE_SHA:
            return json.dumps({"profile": "test"}).encode()
        if expected == Bridge.PROFILE_SOURCE_SHA:
            return b"profile-source"
        raise AssertionError("unexpected pin")

    @staticmethod
    def inventory_digest(operations):
        return adapter.INVENTORY_SHA256

    class PreparedCampaign:
        def __init__(self, config, manifest_sha256, loader, operations,
                     header_type, observed_at, request_inventory_sha256):
            self.config = config
            self.manifest_sha256 = manifest_sha256
            self.loader = loader
            self.operations = operations
            self.header_type = header_type
            self.observed_at = observed_at
            self.request_inventory_sha256 = request_inventory_sha256


def make_campaign(tmp_path):
    tmp_path.chmod(0o700)
    c = {
        "schema": 1,
        "kind": adapter.KIND,
        "adapter_sha256": hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),
        "observed_at": 100.0,
        "usb_binding": dict(USB),
        "loader_path": str(tmp_path / "loader.bin"),
        "profile_path": str(tmp_path / "profile.json"),
        "profile_source_path": str(tmp_path / "loader_config_profile.py"),
        "receipt_path": str(tmp_path / "receipt"),
    }
    path = tmp_path / "campaign.json"
    path.write_text(json.dumps(c))
    return path, c


@pytest.fixture
def fake_sources(monkeypatch):
    operations = [SimpleNamespace(label=f"op-{i}", cdb=bytes.fromhex("fd05"))
                  for i in range(adapter.COMMANDS)]
    bridge = Bridge()
    reader = SimpleNamespace(SGHeader=Header)
    returned = SimpleNamespace(inventory=lambda *args: operations)

    def load_source(path, pin, name):
        if Path(path).name == "fm1_fixed_loader_backup.py":
            return bridge
        if Path(path).name == "fm1_uboot_read.py":
            return reader
        if Path(path).name == "fm1_returned_rom_backup.py":
            return returned
        raise AssertionError(Path(path).name)

    monkeypatch.setattr(adapter, "load_source", load_source)
    monkeypatch.setattr(adapter.time, "time", lambda: 110.0)
    return operations


def test_exact_install_target_and_device38_observation_admitted(tmp_path, fake_sources):
    path, c = make_campaign(tmp_path)
    bridge, prepared, mapping, marker, proof_sha = adapter.prepare(path)
    assert len(prepared.operations) == adapter.COMMANDS == 8757
    assert mapping["simulated"] is True
    assert proof_sha == adapter.INSTALL_PROOF_SHA
    assert marker.name == ".device38-rom-1-1-38.consumed"
    assert prepared.config["usb_binding"] == USB
    assert adapter.TARGET_SHA == "c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903"


@pytest.mark.parametrize("mutation", [
    lambda c: c["usb_binding"].update(path="1-2"),
    lambda c: c["usb_binding"].update(busnum="2"),
    lambda c: c["usb_binding"].update(pid="c755"),
    lambda c: c["usb_binding"].update(devnum="038"),
    lambda c: c.update(kind="fm1-fresh-observed-rom-fixed-loader-dual-read"),
    lambda c: c.update(adapter_sha256="0" * 64),
])
def test_device_or_provenance_mismatch_refused(tmp_path, fake_sources, mutation):
    path, c = make_campaign(tmp_path)
    mutation(c)
    path.write_text(json.dumps(c))
    with pytest.raises((ValueError, AssertionError)):
        adapter.prepare(path)


def test_stale_observation_refused(tmp_path):
    path, c = make_campaign(tmp_path)
    with pytest.raises(ValueError, match="Fresh passive"):
        adapter.validate_observation(c, 221.0)


def test_enumeration_cannot_be_replayed_by_renaming_campaign(tmp_path, fake_sources):
    path, c = make_campaign(tmp_path)
    _, prepared, _, marker, _ = adapter.prepare(path)
    marker.write_text(prepared.manifest_sha256)
    c["receipt_path"] = str(tmp_path / "renamed-receipt")
    path.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="already consumed"):
        adapter.prepare(path)


def test_historical_adapters_and_dependencies_remain_pinned():
    expected = {
        "fm1_fixed_loader_backup.py": "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
        "fm1_returned_rom_backup.py": "afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be",
        "fm1_uboot_read.py": "28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57",
    }
    assert adapter.SOURCES == expected
    for name, sha in expected.items():
        assert hashlib.sha256((ROOT / "tools" / name).read_bytes()).hexdigest() == sha
    old = (ROOT / "tools/fm1_fresh_rom_backup.py").read_text()
    assert "5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d" in old

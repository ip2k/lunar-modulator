"""Offline refusal and one-shot contract tests for the device-44 repeat adapter."""
import ctypes
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fm1_event120_device44_rom_backup as read_adapter
import fm1_uboot_read as reader
from native import event120_device44_repeat_boot as module
from native import event120_reset as completion


def test_adapter_is_bound_to_enumeration_44_and_exact_event120_flash():
    assert read_adapter.USB == {
        "path": "1-1", "busnum": "1", "devnum": "44",
        "vid": "4c4a", "pid": "8057",
    }
    assert module.USB == read_adapter.USB
    assert read_adapter.TARGET_SHA == "145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657"
    assert module.TARGET_SHA == read_adapter.TARGET_SHA
    assert read_adapter.INVENTORY_SHA == module.INVENTORY_SHA
    assert read_adapter.MAX_AGE == module.MAX_AGE == 120
    assert module.RESET_CDB == bytes.fromhex("fc0c00000001ffffffffffffffffffff")
    assert module.READ_ADAPTER_SHA == read_adapter.digest(Path(read_adapter.__file__).read_bytes())
    assert module.READ_KIND == read_adapter.KIND


def test_read_snapshot_rejects_changed_device_number():
    raw = read_adapter.canonical({
        "schema": 1, "kind": read_adapter.SNAPSHOT_KIND, "observed_at": 1000,
        "usb_binding": dict(read_adapter.USB, devnum="40"), "sg_binding": {},
    })
    with pytest.raises(ValueError, match="Fresh exact passive"):
        read_adapter._snapshot(raw, 1000)


def test_boot_campaign_policy_rejects_before_open(tmp_path, monkeypatch):
    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    campaign = root / "boot-campaign.json"
    campaign.write_text('{"schema":1,"kind":"wrong"}')
    original_open = module.os.open
    device_opens = []

    def tracked_open(path, *args, **kwargs):
        if str(path).startswith("/dev/"):
            device_opens.append(str(path))
            raise AssertionError("SG opened before campaign policy validation")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", tracked_open)
    with pytest.raises(ValueError, match="same-session device-44 reset policy"):
        module.prepare(campaign)
    assert device_opens == []


def _fake_authorized(monkeypatch, *, ioctl_fault=None):
    mapping = {
        "node": "/dev/sg-test", "node_identity": [1, 2, 3],
        "usb_binding": read_adapter.USB,
    }
    bridge = SimpleNamespace(discover_sg=lambda usb: mapping)
    target = SimpleNamespace(check=lambda: None)
    now = time.time()
    p = module.Prepared(
        campaign=b"{}", campaign_sha256="a" * 64,
        expected_mapping=module.canonical(mapping), target_prepared=target,
        bridge=bridge, header_type=reader.SGHeader,
        evidence=(), snapshot_observed_at=now, boot_marker=Path("/unused"),
    )
    module._AUTHORIZED.add(p)
    opened, closed, ioctls = [], [], []
    monkeypatch.setattr(module, "_live_mapping", lambda _bridge, usb: mapping)
    monkeypatch.setattr(module.os, "open", lambda path, *args: opened.append(path) or 73)
    monkeypatch.setattr(module.os, "close", lambda fd: closed.append(fd))
    monkeypatch.setattr(module.fcntl, "flock", lambda *args: None)
    monkeypatch.setattr(module.os, "fstat", lambda fd: SimpleNamespace(
        st_mode=stat.S_IFCHR, st_dev=1, st_ino=2, st_rdev=3))

    def ioctl(fd, request, header):
        ioctls.append((fd, request))
        ctypes.memmove(header.data, module.RESET_CDB, 2)
        if ioctl_fault == "status":
            header.host = 7

    monkeypatch.setattr(completion.fcntl, "ioctl", ioctl)
    Session = module.session_class(completion)
    events = []
    session = Session(p, lambda event, **fields: events.append((event, fields)))
    return session, opened, closed, ioctls, events


def test_real_completion_adapter_sends_once_and_never_claims_boot(monkeypatch):
    session, opened, closed, ioctls, events = _fake_authorized(monkeypatch)
    result = session.request_reset()
    assert opened == ["/dev/sg-test"]
    assert len(ioctls) == 1 and ioctls[0][1] == 0x2285
    assert result == {"request_completion": True, "core_reset_observed": False,
                      "boot_observed": False}
    assert [event for event, _ in events] == ["reset_submit_intent", "reset_sg_completion"]
    assert events[-1][1]["boot_observed"] is False
    assert session.fd is None and closed == [73]
    with pytest.raises(ValueError):
        session.request_reset()
    assert len(ioctls) == 1


def test_incomplete_reset_reply_is_latched_and_closed_without_retry(monkeypatch):
    session, opened, closed, ioctls, events = _fake_authorized(monkeypatch, ioctl_fault="status")
    with pytest.raises(OSError, match="incomplete or ambiguous"):
        session.request_reset()
    assert opened == ["/dev/sg-test"]
    assert len(ioctls) == 1
    assert [event for event, _ in events] == ["reset_submit_intent", "reset_sg_completion"]
    assert session.fd is None and session.failed and closed == [73]
    with pytest.raises(ValueError):
        session.request_reset()
    assert len(ioctls) == 1


def test_boot_snapshot_rejects_device42_binding():
    raw = read_adapter.canonical({
        "schema": 1, "kind": module.BOOT_SNAPSHOT_KIND, "observed_at": 1000,
        "usb_binding": dict(read_adapter.USB, devnum="42"), "sg_binding": {},
    })
    with pytest.raises(ValueError, match="Fresh exact same-session"):
        module._snapshot(raw, now=1000, earliest=1000)


def test_read_snapshot_freshness_is_measured_at_read_start():
    # A full dual read can outlast the 120-second passive-snapshot age window.
    # The separate boot-stage snapshot must still be fresh after completion.
    assert module._read_snapshot_fresh_at_start(1000, 1110)
    assert not module._read_snapshot_fresh_at_start(989, 1110)
    assert not module._read_snapshot_fresh_at_start(1111, 1110)
    with pytest.raises(ValueError, match="Fresh exact same-session"):
        module._snapshot(read_adapter.canonical({
            "schema": 1, "kind": module.BOOT_SNAPSHOT_KIND, "observed_at": 1000,
            "usb_binding": read_adapter.USB, "sg_binding": {},
        }), now=1110, earliest=1110)


def test_positive_prepare_loads_pinned_modules_from_real_tools_layout(tmp_path, monkeypatch):
    """Exercise the real tools/native -> tools module layout without opening SG."""
    evidence_root = tmp_path / "private"
    evidence_root.mkdir(mode=0o700)
    evidence_root.chmod(0o700)
    read_receipt = evidence_root / "read"
    read_receipt.mkdir(mode=0o700)
    read_receipt.chmod(0o700)
    boot_receipt = evidence_root / "boot"
    campaign_path = evidence_root / "boot-campaign.json"
    now = time.time()
    mapping = {
        "node": "/dev/sg-test", "class": "/sys/class/scsi_generic/sg-test",
        "device": "/sys/devices/pci0000:00/usb1/1-1/1-1:1.0/host0/target0:0:0/0:0:0:0",
        "usb": "/sys/devices/pci0000:00/usb1/1-1",
        "node_identity": (1, 2, 3), "class_identity": (4, 5, 0),
        "device_identity": (6, 7, 0), "usb_identity": (8, 9, 0),
    }
    snapshot = {
        "schema": 1, "kind": module.BOOT_SNAPSHOT_KIND, "observed_at": now,
        "usb_binding": read_adapter.USB, "sg_binding": mapping,
    }
    snapshot_path = evidence_root / "boot-snapshot.json"
    snapshot_raw = read_adapter.canonical(snapshot)
    snapshot_path.write_bytes(snapshot_raw)
    adapter_sha = read_adapter.digest(Path(module.__file__).read_bytes())
    campaign = {
        "schema": 1, "kind": module.KIND, "adapter_sha256": adapter_sha,
        "read_manifest_path": str(evidence_root / "manifest.json"),
        "read_manifest_sha256": "a" * 64, "read_commands_sha256": "b" * 64,
        "snapshot_path": str(snapshot_path),
        "snapshot_sha256": read_adapter.digest(snapshot_raw),
        "snapshot_observed_at": now, "usb_binding": read_adapter.USB,
        "sg_binding": mapping, "active_session_state": module.ACTIVE_SESSION,
        "no_later_commands_attested": True, "receipt_path": str(boot_receipt),
    }
    campaign_path.write_bytes(read_adapter.canonical(campaign))
    bridge = SimpleNamespace(discover_sg=lambda usb: mapping)
    verified_read = {
        "manifest": {"sg_binding": mapping}, "completed_at": now - 1,
        "receipt": read_receipt, "bridge": bridge, "reader": reader,
        "evidence": (),
    }
    monkeypatch.setattr(module, "verify_read_bundle", lambda *args, **kwargs: verified_read)

    prepared, completion_module = module.prepare(campaign_path, now=now)

    assert module.ROOT == Path(module.__file__).resolve().parents[1]
    assert module.ROOT.name == "tools"
    assert prepared in module._AUTHORIZED
    assert prepared.target_prepared in sys.modules["_event12044_fixed_target_reset"]._AUTHORIZED
    assert completion_module.__file__ == str(module.ROOT / "native/event120_reset.py")
    frozen_paths = {path for path, _data, _limit in prepared.evidence}
    assert {
        module.ROOT / "fm1_fixed_target_reset.py",
        module.ROOT / "fm1_fixed_loader_reset.py",
        module.ROOT / "native/event120_reset.py",
    } <= frozen_paths
    assert not boot_receipt.exists()
    assert not list(evidence_root.glob("*.consumed"))

    marker = evidence_root / (".event12044-boot-" + "a" * 64 + ".consumed")
    marker.write_bytes(b"consumed")
    with pytest.raises(ValueError, match="authorization already consumed"):
        module.prepare(campaign_path, now=now)


def test_prepare_rejects_live_mapping_change_before_sg_open(tmp_path, monkeypatch):
    # The passive snapshot and verified-read bundle identify one exact node.
    # A changed live sysfs mapping must fail before the reset descriptor opens.
    evidence_root = tmp_path / 'private'
    evidence_root.mkdir(mode=0o700)
    evidence_root.chmod(0o700)
    read_receipt = evidence_root / 'read'
    read_receipt.mkdir(mode=0o700)
    read_receipt.chmod(0o700)
    now = time.time()
    expected = {
        'node': '/dev/sg-test', 'class': '/sys/class/scsi_generic/sg-test',
        'device': '/sys/devices/pci0000:00/usb1/1-1/1-1:1.0/host0/target0:0:0/0:0:0:0',
        'usb': '/sys/devices/pci0000:00/usb1/1-1',
        'node_identity': (1, 2, 3), 'class_identity': (4, 5, 0),
        'device_identity': (6, 7, 0), 'usb_identity': (8, 9, 0),
    }
    changed = dict(expected, node='/dev/sg-other', node_identity=(9, 9, 9))
    snapshot = {'schema': 1, 'kind': module.BOOT_SNAPSHOT_KIND,
                'observed_at': now, 'usb_binding': read_adapter.USB,
                'sg_binding': expected}
    snapshot_path = evidence_root / 'snapshot.json'
    snapshot_raw = read_adapter.canonical(snapshot)
    snapshot_path.write_bytes(snapshot_raw)
    campaign_path = evidence_root / 'boot-campaign.json'
    campaign = {
        'schema': 1, 'kind': module.KIND,
        'adapter_sha256': read_adapter.digest(Path(module.__file__).read_bytes()),
        'read_manifest_path': str(evidence_root / 'manifest.json'),
        'read_manifest_sha256': 'a' * 64, 'read_commands_sha256': 'b' * 64,
        'snapshot_path': str(snapshot_path),
        'snapshot_sha256': read_adapter.digest(snapshot_raw),
        'snapshot_observed_at': now, 'usb_binding': read_adapter.USB,
        'sg_binding': expected, 'active_session_state': module.ACTIVE_SESSION,
        'no_later_commands_attested': True,
        'receipt_path': str(evidence_root / 'boot'),
    }
    campaign_path.write_bytes(read_adapter.canonical(campaign))
    bridge = SimpleNamespace(discover_sg=lambda usb: changed)
    verified_read = {
        'manifest': {'sg_binding': expected}, 'completed_at': now - 1,
        'receipt': read_receipt, 'bridge': bridge, 'reader': reader,
        'evidence': (),
    }
    monkeypatch.setattr(module, 'verify_read_bundle', lambda *args, **kwargs: verified_read)
    original_open = module.os.open
    device_opens = []

    def tracked_open(path, *args, **kwargs):
        if str(path).startswith('/dev/'):
            device_opens.append(str(path))
            raise AssertionError('SG descriptor opened before mapping validation')
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(module.os, 'open', tracked_open)
    with pytest.raises(ValueError, match='Live USB/SG mapping differs'):
        module.prepare(campaign_path, now=now)
    assert device_opens == []


def test_read_bundle_rejects_altered_manifest_hash_before_device_access(tmp_path, monkeypatch):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{}", encoding="ascii")
    device_opens = []
    original_open = module.os.open

    def tracked_open(path, *args, **kwargs):
        if str(path).startswith("/dev/"):
            device_opens.append(str(path))
            raise AssertionError("Device access before read-manifest hash validation")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", tracked_open)
    with pytest.raises(ValueError, match="Pinned evidence hash differs"):
        module.verify_read_bundle(manifest_path, "0" * 64, "1" * 64)
    assert device_opens == []


def test_read_bundle_resolves_the_pinned_device44_reader(tmp_path, monkeypatch):
    """Exercise the real reader-file dependency before any loader/device access."""
    import json

    receipt = tmp_path / 'fresh-read'
    manifest_path = receipt / 'manifest.json'
    snapshot_path = tmp_path / 'read-snapshot.json'
    campaign_path = tmp_path / 'read-campaign.json'
    campaign = {
        'schema': 1, 'kind': module.READ_KIND,
        'adapter_sha256': module.READ_ADAPTER_SHA,
        'snapshot_path': str(snapshot_path), 'snapshot_sha256': 'a' * 64,
        'loader_path': '/unused-loader', 'profile_path': '/unused-profile',
        'profile_source_path': '/unused-profile-source',
        'usb_binding': module.USB, 'receipt_path': str(receipt),
    }
    campaign_raw = json.dumps(campaign).encode()
    campaign_path.write_bytes(campaign_raw)
    manifest = {
        'schema': 1, 'kind': module.READ_KIND,
        'campaign_path': str(campaign_path),
        'campaign_sha256': module.digest(campaign_raw),
        'adapter_sha256': module.READ_ADAPTER_SHA,
        'source_sha256': module.READ_SOURCES,
        'snapshot_path': str(snapshot_path), 'snapshot_sha256': 'a' * 64,
        'usb_binding': module.USB, 'sg_binding': {},
        'loader_sha256': 'fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c',
        'loader_profile_sha256': '3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe',
        'profile_source_sha256': '9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8',
        'reader_sha256': module.READ_SOURCES['fm1_uboot_read.py'],
        'request_inventory_sha256': module.INVENTORY_SHA,
        'commands': 8757, 'flash_bytes': 1048576,
        'expected_current_flash_sha256': module.TARGET_SHA,
        'current_flash_sha256': module.TARGET_SHA,
        'commands_sha256': 'b' * 64, 'dumps': [], 'identical': True,
        'flash_operations': 0, 'reset_operations': 0,
        'install_history_proven': False, 'boot_observed': False,
        'physical_recovery_verified': False, 'kernel_exclusivity': False,
    }
    manifest_raw = json.dumps(manifest).encode()

    class ReachedSnapshot(Exception):
        pass

    def hash_pin(path, sha, limit):
        if Path(path) == manifest_path:
            assert sha == module.digest(manifest_raw)
            return manifest_raw
        assert Path(path) == snapshot_path
        # Reaching here proves the actual on-disk reader passed its SHA pin.
        raise ReachedSnapshot

    monkeypatch.setattr(module, '_hash_pin', hash_pin)
    with pytest.raises(ReachedSnapshot):
        module.verify_read_bundle(manifest_path, module.digest(manifest_raw), 'b' * 64)

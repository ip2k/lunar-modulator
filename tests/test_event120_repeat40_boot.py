"""Offline refusal and one-shot contract tests for the device-40 repeat adapter."""
import ctypes
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fm1_event120_rom_backup as read_adapter
import fm1_uboot_read as reader
from native import event120_repeat_boot as module
from native import event120_reset as completion


def test_read_snapshot_rejects_changed_device_number():
    raw = read_adapter.canonical({
        "schema": 1, "kind": read_adapter.SNAPSHOT_KIND, "observed_at": 1000,
        "usb_binding": dict(read_adapter.USB, devnum="41"), "sg_binding": {},
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
    with pytest.raises(ValueError, match="same-session device-40 reset policy"):
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

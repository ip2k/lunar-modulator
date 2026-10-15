import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native import generic_diagnostic_boot as boot


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def transcript(path, target, write=None):
    response = sha(bytes(256))
    rows = []
    for index, address in enumerate(range(0, boot.FLASH_BYTES, 256)):
        cdb = (b"\xfd\x05" + address.to_bytes(4, "big") + b"\x01\x00").ljust(16, b"\xff")
        base = {"index": index, "direction": "install", "retry": False,
                "cdb": cdb.hex(), "in_len": 256, "out_len": 0, "payload_sha256": None}
        done = {"index": index, "direction": "install", "retry": False,
                "status": 0, "masked": 0, "msg": 0, "host": 0, "driver": 0,
                "resid": 0, "info": 0, "sense_len": 0, "sense_hex": "",
                "response_sha256": response}
        rows.extend(({"event": "sg_submit_intent", **base},
                     {"event": "sg_completion", **done}))
    if write is None:
        path.write_bytes(b"".join(canon(row) + b"\n" for row in rows))
    else:
        for row in rows:
            event = row.pop("event")
            write(event, **row)


class FakeTransport:
    def __init__(self, binding, prepared):
        self._binding = binding
        self.prepared = prepared
        self.closed = False

    def binding(self):
        return dict(self._binding, session_id="test-session")

    def close(self):
        self.closed = True


def fixture(monkeypatch, tmp_path):
    target = bytes(boot.FLASH_BYTES)
    usb = {"path": "1-1", "busnum": "1", "devnum": "55", "vid": "4c4a", "pid": "8057"}
    sg = {"node": "/dev/sg0", "node_identity": [1, 2, 3]}
    identity = {"application": "FM-1_500", "recovery": "FM-1_000"}
    binding = {"phase": "loader", "loader_sha256": "a" * 64,
               "usb_binding": usb, "sg_binding": sg, "identity": identity}
    journal = {"state": "complete", "direction": "install", "intent": None,
               "verified_sha256": sha(target)}
    policy = boot.flash.Policy(tmp_path, canon({"identity": identity}), target, target,
                               canon({}), canon(binding), (), (), 0.0,
                               boot.flash._VALIDATED)
    boot.flash._POLICIES.add(policy)
    monkeypatch.setattr(boot.flash.Policy, "check_files", lambda self, **kwargs: dict(journal))
    monkeypatch.setattr(boot.flash, "_POLICIES", {policy})
    log_path = tmp_path / "install.jsonl"
    from native import generic_diagnostic_sg_adapter as sg_adapter
    # Real DurableLog writes the 8,192-row fixture; omit fsync latency in this
    # unit test while still exercising its actual file/close interface.
    monkeypatch.setattr(sg_adapter.os, "fsync", lambda fd: None)
    durable_log = sg_adapter.DurableLog(log_path)
    transcript(log_path, target, durable_log)
    bridge = SimpleNamespace(discover_sg=lambda usb: sg, LOADER_SHA="a" * 64)
    import fm1_uboot_read
    prepared = SimpleNamespace(bridge=bridge, mapping=canon(sg),
                               header_type=fm1_uboot_read.SGHeader)
    inner = FakeTransport(binding, prepared)
    wrapped = sg_adapter._LoggedTransport(inner, durable_log)
    session = boot.flash.DiagnosticSession(policy, wrapped)
    session.did_run = False

    def run():
        session.did_run = True
        result = {"direction": "install", "verified_sha256": sha(target),
                  "hardware_admitted": False, "installable": False}
        session._stop()
        return result
    session.run = run
    root = tmp_path / "evidence"
    root.mkdir(mode=0o700)
    root.chmod(0o700)
    state = {"after_install": False, "reset_calls": 0}

    def after_install(result):
        assert session.did_run and result["verified_sha256"] == sha(target)
        state["after_install"] = True

    snapshot = root / "snapshot.json"
    def provide_snapshot():
        assert state["after_install"]
        raw = canon({"schema": 1, "kind": boot.SNAPSHOT_KIND, "observed_at": time.time(),
                     "usb_binding": usb, "sg_binding": sg})
        snapshot.write_bytes(raw)
        return snapshot, sha(raw)

    # Exercise the actual pinned generic boot session class and completion-first
    # reset helper, with only the OS SG endpoint and ioctl replaced by fakes.
    import fcntl
    real_open, real_close, real_fstat = os.open, os.close, os.fstat
    fake_fd = 9271
    monkeypatch.setattr(boot.generic_boot, "_live_mapping", lambda bridge, usb: sg)
    monkeypatch.setattr(os, "open", lambda path, *args, **kwargs:
                        fake_fd if str(path) == sg["node"] else real_open(path, *args, **kwargs))
    monkeypatch.setattr(os, "close", lambda fd: None if fd == fake_fd else real_close(fd))
    monkeypatch.setattr(os, "fstat", lambda fd: SimpleNamespace(
        st_mode=stat.S_IFCHR | 0o600, st_dev=1, st_ino=2, st_rdev=3)
        if fd == fake_fd else real_fstat(fd))
    monkeypatch.setattr(fcntl, "flock", lambda fd, operation: None if fd == fake_fd else None)
    from native import event120_reset
    def fake_ioctl(fd, request, header):
        import ctypes
        assert fd == fake_fd and request == 0x2285
        assert ctypes.string_at(header.cmd, 16) == bytes.fromhex("fc0c00000001ffffffffffffffffffff")
        ctypes.memmove(header.data, bytes.fromhex("fc0c") + bytes(14), 16)
        state["reset_calls"] += 1
    monkeypatch.setattr(event120_reset.fcntl, "ioctl", fake_ioctl)
    return policy, session, root, log_path, provide_snapshot, after_install, state, durable_log


def test_completed_transaction_reaches_single_reset_only_after_marker(monkeypatch, tmp_path):
    policy, session, root, log_path, snapshot, after_install, state, durable_log = fixture(monkeypatch, tmp_path)
    result = boot.run_completed(policy, session, evidence_root=root, install_log_path=log_path,
                                snapshot_provider=snapshot, after_install=after_install)
    assert result == {"request_completion": True, "core_reset_observed": False,
                      "boot_observed": False}
    assert state["reset_calls"] == 1
    assert (root / ".generic-diagnostic-boot.consumed").exists()
    assert (root / "generic-diagnostic-boot" / "campaign.json").exists()
    assert not result["boot_observed"]
    assert durable_log.fd is None


def test_rejects_bad_completion_before_consuming_or_resetting(monkeypatch, tmp_path):
    policy, session, root, log_path, snapshot, after_install, state, _ = fixture(monkeypatch, tmp_path)
    session.run = lambda: {"direction": "install", "verified_sha256": "0" * 64}
    with pytest.raises(ValueError, match="exact transaction target"):
        boot.run_completed(policy, session, evidence_root=root, install_log_path=log_path,
                           snapshot_provider=snapshot, after_install=after_install)
    assert state["reset_calls"] == 0
    assert not (root / ".generic-diagnostic-boot.consumed").exists()


def test_sg_replay_requires_exact_final_full_readback(monkeypatch, tmp_path):
    target = bytes(boot.FLASH_BYTES)
    path = tmp_path / "commands.jsonl"
    transcript(path, target)
    raw, count = boot._successful_sg_log(path, SimpleNamespace(target=target, sectors=()))
    assert len(raw) == path.stat().st_size and count == 4096
    last = json.loads(path.read_text().splitlines()[-1])
    last["response_sha256"] = "0" * 64
    lines = path.read_text().splitlines()
    lines[-1] = json.dumps(last, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match="final complete target readback"):
        boot._successful_sg_log(path, SimpleNamespace(target=target, sectors=()))


def test_snapshot_must_be_post_completion_and_same_mapping(tmp_path):
    usb = {"path": "1-1", "busnum": "1", "devnum": "55", "vid": "4c4a", "pid": "8057"}
    sg = {"node": "/dev/sg0"}
    path = tmp_path / "snapshot.json"
    raw = canon({"schema": 1, "kind": boot.SNAPSHOT_KIND, "observed_at": 99.0,
                 "usb_binding": usb, "sg_binding": sg})
    path.write_bytes(raw)
    with pytest.raises(ValueError, match="Fresh same-loader"):
        boot._load_snapshot(lambda: (path, sha(raw)),
                            {"usb_binding": usb, "sg_binding": sg}, 100.0, 101.0)


def test_completion_first_reset_sends_exact_fc0c_once(monkeypatch):
    import ctypes
    from native import event120_reset
    reset = object.__new__(event120_reset.CompletionFirstReset)
    calls = []
    # This is the same checked 88-byte SG_IO header used by the ROM reader.
    import fm1_uboot_read
    reset.prepared = SimpleNamespace(check=lambda: None, header_type=fm1_uboot_read.SGHeader)
    reset.log = lambda event, **fields: calls.append((event, fields))
    reset.fd, reset.consumed, reset.failed, reset.ioctl_attempts = 10, False, False, 0
    reset.phase = "completed-diagnostic-same-loader"
    reset.binding = lambda: None
    reset.close = lambda: None

    def ioctl(fd, request, header):
        assert fd == 10 and request == 0x2285
        assert ctypes.string_at(header.cmd, 16) == bytes.fromhex("fc0c00000001ffffffffffffffffffff")
        ctypes.memmove(header.data, bytes.fromhex("fc0c") + bytes(14), 16)
        calls.append(("ioctl", {}))
    monkeypatch.setattr(event120_reset.fcntl, "ioctl", ioctl)
    result = reset.request_reset()
    assert result == {"request_completion": True, "core_reset_observed": False,
                      "boot_observed": False}
    assert [event for event, _ in calls].count("ioctl") == 1
    assert reset.consumed and reset.ioctl_attempts == 1


def test_real_source_pins_and_tamper_refusal(tmp_path, monkeypatch):
    evidence = boot._source_evidence()
    assert len(evidence) == len(boot.SOURCE_PINS) + 1
    # Exercise real hashes against a private copy; no transport is constructed.
    for name in boot.SOURCE_PINS:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((boot.ROOT / name).read_bytes())
    monkeypatch.setattr(boot, "ROOT", tmp_path)
    boot._source_evidence()
    (tmp_path / "native/generic_diagnostic_flash.py").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="Reviewed install/reset source changed"):
        boot._source_evidence()

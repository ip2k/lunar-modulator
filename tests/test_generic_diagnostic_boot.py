import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from native import generic_diagnostic_boot as boot


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def transcript(path, target):
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
    path.write_bytes(b"".join(canon(row) + b"\n" for row in rows))


class FakePolicy:
    def __init__(self, root, target, identity):
        self.target = target
        self.plan_bytes = canon({"identity": identity})
        self.evidence = ()
        self.sectors = ()
        self.directory = root
        self.journal = {"state": "complete", "direction": "install", "intent": None,
                        "verified_sha256": sha(target)}

    def check_files(self, **kwargs):
        return dict(self.journal)

    def receipt(self):
        return {"target_sha256": sha(self.target)}


class FakeSession:
    def __init__(self, policy, log_path, binding):
        self._policy = SimpleNamespace(policy=policy, direction="install")
        self._latched = self._running = False
        self._binding = canon(binding)
        self._transport = SimpleNamespace(
            closed=True,
            log=SimpleNamespace(path=log_path, closed=True),
            inner=SimpleNamespace(prepared=SimpleNamespace(
                bridge=SimpleNamespace(discover_sg=lambda usb: binding["sg_binding"]),
                mapping=canon(binding["sg_binding"]))),
        )
        self.did_run = False

    def _capture_binding(self):
        return self._binding

    def run(self):
        self.did_run = True
        return {"direction": "install", "verified_sha256": sha(self._policy.policy.target),
                "hardware_admitted": False, "installable": False}


def fixture(monkeypatch, tmp_path):
    target = bytes(boot.FLASH_BYTES)
    usb = {"path": "1-1", "busnum": "1", "devnum": "55", "vid": "4c4a", "pid": "8057"}
    sg = {"node": "/dev/sg0", "node_identity": [1, 2, 3]}
    identity = {"application": "FM-1_500", "recovery": "FM-1_000"}
    binding = {"phase": "loader", "loader_sha256": "a" * 64,
               "usb_binding": usb, "sg_binding": sg, "identity": identity}
    policy = FakePolicy(tmp_path, target, identity)
    monkeypatch.setattr(boot.flash, "Policy", FakePolicy)
    monkeypatch.setattr(boot.flash, "DiagnosticSession", FakeSession)
    monkeypatch.setattr(boot.flash, "_POLICIES", {policy})
    log_path = tmp_path / "install.jsonl"
    transcript(log_path, target)
    session = FakeSession(policy, log_path, binding)
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
        raw = canon({"schema": 1, "kind": boot.SNAPSHOT_KIND, "observed_at": 1001.0,
                     "usb_binding": usb, "sg_binding": sg})
        snapshot.write_bytes(raw)
        return snapshot, sha(raw)

    def factory(prepared, log):
        assert (root / ".generic-diagnostic-boot.consumed").exists()
        assert json.loads(prepared.campaign)["target_sha256"] == sha(target)
        class Reset:
            fd = 10
            def __init__(self): self.closed = False
            def binding(self):
                prepared.check()
                return json.loads(prepared.expected_binding)
            def request_reset(self):
                state["reset_calls"] += 1
                log("reset_submit_intent", retry=False)
                log("reset_sg_completion", status=0, retry=False)
                return {"request_completion": True, "core_reset_observed": False,
                        "boot_observed": False}
            def close(self): self.closed = True
        return Reset()
    monkeypatch.setattr(boot, "generic_boot", SimpleNamespace(
        session_class=lambda _completion: lambda prepared, log: factory(prepared, log)))
    return policy, session, root, log_path, provide_snapshot, after_install, state


def test_completed_transaction_reaches_single_reset_only_after_marker(monkeypatch, tmp_path):
    policy, session, root, log_path, snapshot, after_install, state = fixture(monkeypatch, tmp_path)
    result = boot.run_completed(policy, session, evidence_root=root, install_log_path=log_path,
                                snapshot_provider=snapshot, after_install=after_install, now=1001.0)
    assert result == {"request_completion": True, "core_reset_observed": False,
                      "boot_observed": False}
    assert state["reset_calls"] == 1
    assert (root / ".generic-diagnostic-boot.consumed").exists()
    assert (root / "generic-diagnostic-boot" / "campaign.json").exists()
    assert not result["boot_observed"]


def test_rejects_bad_completion_before_consuming_or_resetting(monkeypatch, tmp_path):
    policy, session, root, log_path, snapshot, after_install, state = fixture(monkeypatch, tmp_path)
    session.run = lambda: {"direction": "install", "verified_sha256": "0" * 64}
    with pytest.raises(ValueError, match="exact transaction target"):
        boot.run_completed(policy, session, evidence_root=root, install_log_path=log_path,
                           snapshot_provider=snapshot, after_install=after_install, now=1001.0)
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

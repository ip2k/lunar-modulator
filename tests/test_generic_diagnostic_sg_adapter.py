import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/native"))
import generic_diagnostic_flash as policy_module
import generic_diagnostic_sg_adapter as adapter


def sha(data):
    return hashlib.sha256(data).hexdigest()


def setup_policy(tmp_path, monkeypatch, *, bad_port=False):
    usb = {"path": "1-1", "busnum": 1, "devnum": 55, "vid": 0x4C4A, "pid": 0x8057}
    sg = {"node": "/dev/sg-test", "node_identity": [1, 2, 3]}
    manifest = {"usb_binding": dict(usb), "sg_binding": dict(sg),
                "commands_sha256": "c" * 64, "loader_sha256": "d" * 64,
                "current_flash_sha256": "e" * 64}
    if bad_port:
        manifest["usb_binding"]["path"] = "2-9"
    raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    path = tmp_path / "read-manifest.json"
    path.write_bytes(raw)
    receipt = {"live_manifest_sha256": sha(raw), "live_campaign_sha256": "b" * 64,
               "live_baseline_sha256": manifest["current_flash_sha256"]}
    plan = {"identity": {"candidate_sha256": "a" * 64}}
    binding = {"phase": "loader", "loader_sha256": manifest["loader_sha256"],
               "usb_binding": usb, "sg_binding": sg,
               "read_campaign_sha256": receipt["live_campaign_sha256"],
               "read_manifest_sha256": sha(raw), "read_commands_sha256": manifest["commands_sha256"],
               "baseline_sha256": manifest["current_flash_sha256"], "identity": plan["identity"]}
    policy = policy_module.Policy(tmp_path, json.dumps(plan, sort_keys=True).encode(),
        b"baseline", b"target", json.dumps(receipt).encode(),
        json.dumps(binding, sort_keys=True).encode(), (0x4000,),
        ((path, raw, 4096),), policy_module.generic_boot.time.time(), policy_module._VALIDATED)
    policy_module._POLICIES.add(policy)
    monkeypatch.setattr(policy_module.Policy, "check_files", lambda self, **kwargs: {"state": "prepared"})
    bridge = SimpleNamespace(LOADER_SHA=manifest["loader_sha256"])
    reader = SimpleNamespace(SGHeader=object)
    verified = {"manifest": manifest, "bridge": bridge, "reader": reader,
                "evidence": ((path, raw, 4096),)}
    monkeypatch.setattr(policy_module.generic_boot, "verify_read_bundle", lambda *a, **k: verified)
    return policy, manifest, plan, binding


class FakeTransport:
    def __init__(self, binding):
        self._binding, self.closed = binding, False
    def binding(self):
        return self._binding
    def exchange(self, *args, **kwargs):
        return b"ok"
    def close(self):
        self.closed = True


def test_install_adapter_binds_shim_and_closes_log(tmp_path, monkeypatch):
    policy, manifest, plan, binding = setup_policy(tmp_path, monkeypatch)
    log_path = tmp_path / "adapter.jsonl"
    made = []
    def factory(prepared, direction_policy, log):
        assert prepared.check()
        assert prepared.mapping == adapter._canon(manifest["sg_binding"])
        assert direction_policy.direction == "install"
        assert direction_policy.plan_bytes == policy.plan_bytes
        assert direction_policy.baseline == policy.baseline
        assert direction_policy.target == policy.target
        assert direction_policy.sectors == policy.sectors
        assert direction_policy.check_files()["state"] == "prepared"
        log("adapter_factory", direction="install")
        transport = FakeTransport(dict(binding, session_id=prepared.campaign_sha256 + ":install"))
        made.append(transport)
        return transport
    session = adapter.bind(policy, policy_module=policy_module,
        sg_module=SimpleNamespace(__file__=str(ROOT / "tools/native/expanded_sg.py")),
        transport_factory=factory, log_path=log_path)
    assert session.identity() == plan["identity"]
    assert made[0].exchange(b"request") == b"ok"
    session.close()
    assert made[0].closed
    assert log_path.stat().st_mode & 0o777 == 0o600
    assert [json.loads(line) for line in log_path.read_text().splitlines()] == [
        {"direction": "install", "event": "adapter_factory"}]
    with pytest.raises(ValueError, match="Log closed"):
        session._transport.log("after-close")


def test_wrong_stable_port_refuses_before_injected_transport(tmp_path, monkeypatch):
    policy, _, _, _ = setup_policy(tmp_path, monkeypatch, bad_port=True)
    called = []
    with pytest.raises(ValueError, match="Policy/read binding differs"):
        adapter.bind(policy, policy_module=policy_module,
            sg_module=SimpleNamespace(__file__=str(ROOT / "tools/native/expanded_sg.py")),
            transport_factory=lambda *a: called.append(a), log_path=tmp_path / "never.jsonl")
    assert called == []
    assert not (tmp_path / "never.jsonl").exists()


def test_changed_source_pin_refuses_before_factory(tmp_path, monkeypatch):
    policy, *_ = setup_policy(tmp_path, monkeypatch)
    monkeypatch.setitem(adapter.SOURCE_SHA256, "expanded_sg.py", "0" * 64)
    called = []
    with pytest.raises(ValueError, match="Reviewed adapter dependency changed"):
        adapter.bind(policy, policy_module=policy_module,
            sg_module=SimpleNamespace(__file__=str(ROOT / "tools/native/expanded_sg.py")),
            transport_factory=lambda *a: called.append(a), log_path=tmp_path / "never.jsonl")
    assert called == []
    assert not (tmp_path / "never.jsonl").exists()


def test_policy_binding_failure_closes_transport_and_log(tmp_path, monkeypatch):
    policy, _, _, binding = setup_policy(tmp_path, monkeypatch)
    transport = FakeTransport(dict(binding, session_id="bound", loader_sha256="f" * 64))
    with pytest.raises(ValueError, match="Fresh generic ROM read"):
        adapter.bind(policy, policy_module=policy_module,
            sg_module=SimpleNamespace(__file__=str(ROOT / "tools/native/expanded_sg.py")),
            transport_factory=lambda *_: transport, log_path=tmp_path / "failed.jsonl")
    assert transport.closed
    assert (tmp_path / "failed.jsonl").exists()

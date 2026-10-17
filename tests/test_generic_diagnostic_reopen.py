"""Private/offline reopen only; all transports are synthetic MemoryROM."""
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path
from dataclasses import replace

import pytest

from test_generic_diagnostic_flash import interrupted_policy, fresh_restore_read, MemoryROM, module


def sealed(tmp_path):
    policy, baseline, target, binding, partial = interrupted_policy(tmp_path)
    stale = replace(policy, read_completed_at=policy.read_completed_at - 1000)
    module._POLICIES.add(stale)
    path = tmp_path / "policy-seal.json"
    pin = stale.seal(path)
    return stale, baseline, target, binding, partial, path, pin


def test_true_subprocess_restart_reopens_and_requires_fresh_admission(tmp_path, monkeypatch):
    policy, _, target, binding, partial, seal, pin = sealed(tmp_path)
    (tmp_path / "partial.bin").write_bytes(partial)
    read, _ = fresh_restore_read(monkeypatch, binding, partial)
    admission = policy.admit_resume(read)
    (tmp_path / "old-capability.pickle").write_bytes(pickle.dumps(admission))
    script = r'''
import json,pickle,sys
from pathlib import Path
import pytest
from test_generic_diagnostic_flash import fresh_restore_read,MemoryROM,module
seal,pin,partial_path,old_cap=sys.argv[1:]
assert not list(module._POLICIES)
policy=module.reopen_policy(Path(seal),pin)
binding=json.loads(policy.binding_bytes)
partial=Path(partial_path).read_bytes()
try: policy.bind(MemoryROM(partial,binding))
except ValueError as exc: assert "expired" in str(exc)
else: raise AssertionError("old initial read admitted")
for forged in ({"resume":True},pickle.loads(Path(old_cap).read_bytes())):
    try: policy.bind(MemoryROM(partial,binding),resume=forged)
    except ValueError: pass
    else: raise AssertionError("serialized authority admitted")
mp=pytest.MonkeyPatch()
read,new_binding=fresh_restore_read(mp,binding,partial,
    usb=dict(binding["usb_binding"],devnum="91"),sg={"node":"/dev/sg-new-process","inode":90})
capability=policy.admit_resume(read)
rom=MemoryROM(partial,new_binding)
result=policy.bind(rom,resume=capability).run()
assert bytes(rom.flash)==policy.target and rom.closed
print(json.dumps({"verified_sha256":result["verified_sha256"],"mutations":len(rom.mutations)}))
'''
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(Path(__file__).parent), str(Path(__file__).parents[1])]))
    result = subprocess.run([sys.executable, "-c", script, str(seal), pin,
                             str(tmp_path / "partial.bin"), str(tmp_path / "old-capability.pickle")],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verified_sha256"] == module.digest(target)
    assert json.loads(result.stdout)["mutations"] > 0


@pytest.mark.parametrize("name", ["plan.json", "diagnostic-receipt.json", "backupA.bin", "backupB.bin", "target.bin", "journal.json", "evidence"])
def test_reopen_rejects_changed_or_missing_artifacts(tmp_path, name):
    policy, _, _, _, _, seal, pin = sealed(tmp_path)
    path = Path(policy.evidence[0][0]) if name == "evidence" else policy.directory / name
    path.write_bytes(b"changed")
    with pytest.raises((ValueError, KeyError, TypeError)):
        module.reopen_policy(seal, pin)
    path.unlink()
    with pytest.raises((ValueError, OSError)):
        module.reopen_policy(seal, pin)


def test_rehashed_replacement_seal_cannot_replace_external_pin(tmp_path):
    _, _, _, _, _, seal, pin = sealed(tmp_path)
    value = json.loads(seal.read_bytes())
    value["read_completed_at"] = module.generic_boot.time.time()
    raw = module.encoded(value)
    seal.write_bytes(raw)
    seal.with_suffix(".sha256").write_text(module.digest(raw))
    with pytest.raises(ValueError, match="independent pin"):
        module.reopen_policy(seal, pin)
    with pytest.raises(ValueError, match="Independent"):
        module.reopen_policy(seal, None)


@pytest.mark.parametrize("where,kind", [(where, kind) for where in ("seal", "evidence", "transaction")
    for kind in ("symlink", "fifo", "oversize")] + [("parent", "symlink")])
def test_reopen_rejects_unsafe_input_files_without_blocking(tmp_path, where, kind):
    policy, _, _, _, _, seal, pin = sealed(tmp_path)
    if where == "parent":
        alias = tmp_path / "alias"
        alias.symlink_to(policy.directory, target_is_directory=True)
        value = json.loads(seal.read_bytes()); value["directory"] = str(alias)
        seal.write_bytes(module.encoded(value)); pin = module.digest(seal.read_bytes())
        with pytest.raises((ValueError, OSError)): module.reopen_policy(seal, pin)
        return
    path = seal if where == "seal" else (Path(policy.evidence[0][0]) if where == "evidence" else policy.directory / "plan.json")
    original = path.read_bytes()
    path.unlink()
    if kind == "symlink":
        backing = tmp_path / "backing"; backing.write_bytes(original); path.symlink_to(backing)
    elif kind == "fifo": os.mkfifo(path)
    else:
        with path.open("wb") as stream: stream.truncate(module._META_LIMIT + 1 if where != "evidence" else len(original) + 1)
    with pytest.raises((ValueError, OSError)): module.reopen_policy(seal, pin)


@pytest.mark.parametrize("change", ["stale", "loader", "port", "mapping", "reread", "immutable"])
def test_reopened_policy_preserves_fresh_resume_guards(tmp_path, monkeypatch, change):
    _, _, _, binding, partial, seal, pin = sealed(tmp_path)
    policy = module.reopen_policy(seal, pin)
    actual = bytearray(partial)
    if change == "immutable": actual[0] ^= 1
    read, new_binding = fresh_restore_read(monkeypatch, binding, bytes(actual),
        usb=dict(binding["usb_binding"], devnum="92"), sg={"node": "/dev/sg-reopened", "inode": 92})
    verified = module.generic_boot.verify_read_bundle()
    if change == "stale": verified["completed_at"] -= 1000
    if change == "loader": verified["manifest"]["loader_sha256"] = "f" * 64
    if change == "port": verified["manifest"]["usb_binding"]["path"] = "different"
    monkeypatch.setattr(module.generic_boot, "verify_read_bundle", lambda *a, **k: verified)
    if change in ("stale", "loader", "port"):
        with pytest.raises(ValueError): policy.admit_resume(read)
        return
    capability = policy.admit_resume(read)
    if change == "mapping": new_binding["sg_binding"] = {"node": "/dev/sg-wrong"}
    if change == "reread": actual[module.APP_BASE + 4096] ^= 1
    rom = MemoryROM(bytes(actual), new_binding)
    with pytest.raises(ValueError): policy.bind(rom, resume=capability).run()
    assert not rom.mutations and rom.closed



def test_reopen_rejects_changed_validation_source_inventory(tmp_path):
    _, _, _, _, _, seal, _ = sealed(tmp_path)
    value = json.loads(seal.read_bytes())
    value["validation_sources"]["transaction"] = "0" * 64
    raw = module.encoded(value); seal.write_bytes(raw)
    with pytest.raises(ValueError, match="validation sources"):
        module.reopen_policy(seal, module.digest(raw))


def test_reopen_cannot_upgrade_hardware_claims(tmp_path):
    policy, _, _, _, _, seal, _ = sealed(tmp_path)
    receipt = json.loads(policy.receipt_bytes)
    receipt["hardware_admitted"] = True
    raw = module.encoded(receipt)
    (policy.directory / "diagnostic-receipt.json").write_bytes(raw)
    value = json.loads(seal.read_bytes()); value["receipt_sha256"] = module.digest(raw)
    seal.write_bytes(module.encoded(value))
    with pytest.raises(ValueError, match="unadmitted hardware"):
        module.reopen_policy(seal, module.digest(seal.read_bytes()))


@pytest.mark.parametrize("change", ["too_many", "too_large", "total", "duplicate", "noncanonical"])
def test_reopen_bounds_metadata_inventory_before_evidence_reads(tmp_path, change):
    _, _, _, _, _, seal, _ = sealed(tmp_path)
    value = json.loads(seal.read_bytes())
    if change == "too_many": value["evidence"] *= module._EVIDENCE_COUNT + 1
    if change == "too_large": value["evidence"][0]["size"] = module._EVIDENCE_LIMIT + 1
    if change == "total":
        value["evidence"] = [{"path": str(tmp_path / str(i)), "size": module._EVIDENCE_LIMIT,
                              "sha256": "0" * 64} for i in range(5)]
    if change == "duplicate": value["evidence"] *= 2
    raw = module.encoded(value) + (b"\n" if change == "noncanonical" else b"")
    seal.write_bytes(raw)
    with pytest.raises((ValueError, OSError)):
        module.reopen_policy(seal, module.digest(raw))

# SPDX-License-Identifier: MIT
"""Offline worker boundaries. No Docker daemon, target compiler or service runs."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tools.installer_service import docker_adapter as adapter
from tools.installer_service import docker_worker as worker
from tools.installer_service import selected_trio_profile as profile
from tools.installer_service.api import QueueFull, WorkerResult, WorkerSnapshot
from tests.test_installer_selected_trio_profile import evidence


def request(**changes):
    value = dict(version=2, profile_id=worker.SELECTED_TRIO_PROFILE, runtime_mode="offline",
                 flash_layout="stock-sized-diagnostic", engines=["trio"], effects=[],
                 midi=[], modulation=[], project_ids=["init-starter-trio"], startup_index=0)
    value.update(changes)
    return json.dumps(value).encode()


@pytest.fixture
def config(tmp_path, monkeypatch):
    source = tmp_path / "source"
    for name in ("source", "runtime", "toolchain", "headers"):
        (tmp_path / name).mkdir(mode=0o700)
    path = source / "tools/installer_service/docker_worker.py"
    path.parent.mkdir(parents=True)
    path.write_text("# pinned synthetic worker\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"]).decode().strip()
    archive = tmp_path / "toolchain.tar"
    archive.write_bytes(b"synthetic archive")
    monkeypatch.setattr(adapter, "selected_external_inputs", lambda *args: dict(
        source_manifest={"unit.c": "1" * 64},
        toolchain_binding={"archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest()},
        cxx_headers_manifest={"__config": "2" * 64},
        configured_cxx_headers_manifest={"__config": "3" * 64}))
    return adapter.DockerWorkerConfig(source, tmp_path / "toolchain", tmp_path / "runtime", commit,
        profile_id=worker.SELECTED_TRIO_PROFILE, toolchain_archive=archive, cxx_headers=tmp_path / "headers")


def test_fixed_selected_config_requires_original_inputs_and_disjoint_storage(config):
    assert config.catalogue_root is None
    for delta in ({"profile_id": "other"}, {"toolchain_archive": None}, {"cxx_headers": None},
                  {"profile_id": None}, {"runtime_root": config.source_root},
                  {"runtime_root": config.toolchain_root}):
        with pytest.raises(ValueError):
            replace(config, **delta)
    alias = config.runtime_root.parent / "alias"
    alias.symlink_to(config.cxx_headers, target_is_directory=True)
    with pytest.raises(ValueError, match="canonical"):
        replace(config, cxx_headers=alias)


def test_fixed_worker_commands_and_readonly_mounts(config):
    make, target = worker.selected_build_commands()
    assert "FM1_MODULES=trio" in make and "FM1_GPL_MODS=1" in make and "-j4" in make
    assert str(worker.SCRATCH / "host/fm1-state") in make
    assert target[target.index("--jobs") + 1] == "4"
    assert "--catalogue" not in target and "--request" not in target
    command = adapter.DockerJobAdapter(config)._command("a" * 32, config.runtime_root / "a")
    mounts = [command[i + 1] for i, value in enumerate(command) if value == "--mount"]
    assert not any("dst=/catalogue" in mount for mount in mounts)
    for destination in ("/opt/pi32v2", "/opt/lunar-toolchain.tar", "/opt/original-libcxx",
                        "/input/source.tar", "/input/docker_worker.py", "/input/host-bindings.json"):
        assert any(mount.endswith("dst=" + destination + ",readonly") for mount in mounts)
    for flag in ("--network=none", "--pull=never", "--cpuset-cpus=4-7", "--cpus=4",
                 "--memory=6g", "--memory-swap=6g", "--cgroup-parent=docker-batch.slice"):
        assert flag in command


@pytest.mark.parametrize("changes", [{"version": True}, {"version": 2.0}, {"startup_index": False},
    {"engines": ["dx7"]}, {"midi": ["arp"]}, {"path": "/arbitrary"}, {"set_ids": ["x"]}])
def test_worker_bootstrap_matches_strict_fixed_host_request(changes):
    with pytest.raises(ValueError):
        worker.verify_selected_request(request(**changes))
    with pytest.raises(ValueError):
        profile.validate_request(request(**changes))
    worker.verify_selected_request(request())
    worker.verify_selected_request(request(set_ids=[]))


def submit(job, build_id, raw=None):
    raw = request() if raw is None else raw
    job.submit(build_id, raw, hashlib.sha256(raw).hexdigest(), SimpleNamespace(image_digest=adapter._IMAGE_ID))


def finish_without_docker(job, build_id):
    # Keep the real admission/source-archive path, replace only thread execution.
    job.jobs[build_id] = WorkerSnapshot("failed")
    job.cleanup_confirmed.add(build_id)
    job.semaphore.release()


def test_retained_capacity_releases_only_after_confirmed_owned_removal(config, monkeypatch):
    monkeypatch.setattr(adapter.threading.Thread, "start", lambda self: None)
    job = adapter.DockerJobAdapter(config)
    for index in range(4):
        build_id = str(index) * 32
        submit(job, build_id)
        finish_without_docker(job, build_id)
    with pytest.raises(QueueFull):
        submit(job, "4" * 32)
    first = "0" * 32
    binding = json.loads((job.job_dirs[first] / "input/host-bindings.json").read_bytes())
    assert binding["schema"] == 2 and binding["profile_id"] == worker.SELECTED_TRIO_PROFILE
    assert "catalogue_manifest_sha256" not in binding
    assert binding["toolchain_archive_sha256"] == hashlib.sha256(config.toolchain_archive.read_bytes()).hexdigest()
    original_remove = adapter.shutil.rmtree
    def refuse(*args, **kwargs):
        raise PermissionError("injected removal refusal")
    monkeypatch.setattr(adapter.shutil, "rmtree", refuse)
    job.delete(first)
    assert job.get(first) is not None and first in job.selected_inputs
    with pytest.raises(QueueFull):
        submit(job, "4" * 32)
    monkeypatch.setattr(adapter.shutil, "rmtree", original_remove)
    job.delete(first)
    assert job.get(first) is None and first not in job.selected_inputs
    submit(job, "4" * 32)
    finish_without_docker(job, "4" * 32)
    for build_id in list(job.jobs):
        job.delete(build_id)
    assert list(config.runtime_root.iterdir()) == []


def test_cleanup_uncertainty_preserves_private_state_and_blocks_admission(config, monkeypatch):
    monkeypatch.setattr(adapter.threading.Thread, "start", lambda self: None)
    job = adapter.DockerJobAdapter(config)
    build_id = "a" * 32
    submit(job, build_id)
    finish_without_docker(job, build_id)
    job.cleanup_confirmed.discard(build_id)
    job.cleanup_unconfirmed.add(build_id)
    job.delete(build_id)
    assert job.get(build_id) is not None and job.job_dirs[build_id].exists()
    with pytest.raises(RuntimeError, match="cleanup"):
        submit(job, "b" * 32)
    job.cleanup_unconfirmed.clear()
    job.cleanup_confirmed.add(build_id)
    job.delete(build_id)


def test_request_refuses_before_source_exchange(config, monkeypatch):
    job = adapter.DockerJobAdapter(config)
    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: pytest.fail("process started"))
    with pytest.raises(ValueError):
        submit(job, "a" * 32, request(command="arbitrary"))
    assert not job.jobs and list(config.runtime_root.iterdir()) == []


@pytest.fixture
def recorded(config, evidence):
    receipt, app, elf, trusted = evidence
    raw = json.dumps(receipt).encode()
    result = WorkerResult(app, raw, elf, b'{"validation":"untrusted envelope"}', {"obj/unit.o": b"actual"})
    job = adapter.DockerJobAdapter(config)
    build_id = "a" * 32
    job.jobs[build_id] = WorkerSnapshot("succeeded", result)
    job.cleanup_confirmed.add(build_id)
    job.selected_verified[build_id] = (request(), trusted, job._selected_result_fingerprint(result))
    return job, build_id, result, trusted


def test_verification_is_pure_and_uses_recorded_trust_not_envelope(recorded, monkeypatch):
    job, build_id, result, _ = recorded
    monkeypatch.setattr(adapter.subprocess, "run", lambda *a, **k: pytest.fail("verification launched process"))
    monkeypatch.setattr(Path, "open", lambda *a, **k: pytest.fail("verification read external file"))
    summary = job.verify_selected_trio_result(build_id, request(), result)
    assert summary["artifact_sha256"] == hashlib.sha256(result.artifact).hexdigest()
    assert all(summary[name] is False for name in profile.DENIED)


@pytest.mark.parametrize("field", ["artifact", "receipt", "elf", "provenance", "private_evidence"])
def test_recorded_verification_refuses_changed_result_bytes(recorded, field):
    job, build_id, result, _ = recorded
    changed = dict(result.private_evidence, extra=b"changed") if field == "private_evidence" else b"changed"
    with pytest.raises(ValueError, match="recorded job"):
        job.verify_selected_trio_result(build_id, request(), replace(result, **{field: changed}))


def test_verification_requires_exact_job_request_and_confirmed_cleanup(recorded):
    job, build_id, result, _ = recorded
    for unknown in ("b" * 32, ""):
        with pytest.raises(ValueError):
            job.verify_selected_trio_result(unknown, request(), result)
    with pytest.raises(ValueError):
        job.verify_selected_trio_result(build_id, request(set_ids=[]), result)
    job.cleanup_unconfirmed.add(build_id)
    with pytest.raises(ValueError, match="no verified"):
        job.verify_selected_trio_result(build_id, request(), result)


def evidence_tree(root, values):
    root.mkdir(parents=True)
    manifest = {}
    for name, raw in values.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        manifest[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (root / "manifest.json").write_text(json.dumps(manifest))
    return manifest


@pytest.fixture
def private_tree(tmp_path):
    values = {name: b"actual" for name in ("host-bindings.json", "anchors.json", "metadata.json",
        "host-build.log", "build.log", "objects/unit.o", "prepared/selected_project.bin",
        "prepared/selected_project_blob.c", "prepared/selected_project_blob.h", "prepared/receipt.json")}
    values.update({"request.json": request(), "image_receipt.json": b"receipt"})
    root = tmp_path / "result/evidence"
    manifest = evidence_tree(root, values)
    return root.parent, values, manifest


def test_selected_evidence_closed_inventory_and_real_bytes(private_tree):
    result, values, _ = private_tree
    assert adapter.read_private_evidence(result, request(), b"receipt", None, selected=True) == values
    (result / "evidence/undeclared").write_bytes(b"unlisted")
    with pytest.raises(ValueError, match="files differ"):
        adapter.read_private_evidence(result, request(), b"receipt", None, selected=True)


@pytest.mark.parametrize("mutation", ["missing", "symlink", "wrong_bytes", "extra", "over_cap"])
def test_selected_evidence_refusals_are_causal(private_tree, mutation):
    result, values, manifest = private_tree
    root = result / "evidence"
    path = root / "objects/unit.o"
    if mutation == "missing":
        path.unlink()
    elif mutation == "symlink":
        path.unlink(); path.symlink_to(root / "build.log")
    elif mutation == "wrong_bytes":
        path.write_bytes(b"CHANGED")
    elif mutation == "extra":
        values["arbitrary"] = b"extra"
        manifest["arbitrary"] = dict(bytes=5, sha256=hashlib.sha256(b"extra").hexdigest())
        (root / "arbitrary").write_bytes(b"extra")
    else:
        manifest["objects/unit.o"]["bytes"] = adapter._SELECTED_EVIDENCE_CAP + 1
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        adapter.read_private_evidence(result, request(), b"receipt", None, selected=True)


def test_selected_capture_actual_timeout_retains_private_diagnostic(tmp_path, monkeypatch):
    monkeypatch.setattr(worker, "SOURCE", tmp_path)
    monkeypatch.setattr(worker, "RESULT", tmp_path)
    with pytest.raises(ValueError, match="timeout"):
        worker._selected_capture([sys.executable, "-c", "import time; print('before',flush=True); time.sleep(10)"], timeout=.1)
    assert b"before" in (tmp_path / "diagnostic.log").read_bytes()

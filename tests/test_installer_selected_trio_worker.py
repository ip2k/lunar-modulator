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


@pytest.fixture
def collected(config, evidence, monkeypatch):
    """Synthetic pi32 ELF plus real byte collection; no target build is implied."""
    from copy import deepcopy
    receipt, app, elf, trusted = evidence
    receipt = deepcopy(receipt)
    metadata = b'{"synthetic":true}'
    receipt["selected_project"]["metadata_sha256"] = hashlib.sha256(metadata).hexdigest()
    prepared = dict(trusted.prepared_files)
    prepared["receipt.json"] = json.dumps(receipt["selected_project"]).encode()
    receipt["prepared_input_manifest"] = {k: hashlib.sha256(v).hexdigest() for k, v in prepared.items()}
    receipt["compile_flags"] = worker.selected_compile_flags()
    external = dict(source_manifest=dict(trusted.source_manifest),
                    toolchain_binding=trusted.toolchain_binding,
                    cxx_headers_manifest=dict(trusted.cxx_headers_manifest),
                    configured_cxx_headers_manifest=dict(trusted.configured_cxx_headers_manifest))
    monkeypatch.setattr(adapter, "selected_external_inputs", lambda *args: external)
    monkeypatch.setattr(adapter.threading.Thread, "start", lambda self: None)
    job = adapter.DockerJobAdapter(config)
    build_id = "a" * 32
    submit(job, build_id)
    base = job.job_dirs[build_id]
    audit = [("/workspace/firmware/native/unit.c", 1, "void unit(void) {}")]
    local_audit = [(str(config.source_root / "firmware/native/unit.c"), 1, "void unit(void) {}")]
    monkeypatch.setattr(adapter, "load_selected_builder", lambda root:
        SimpleNamespace(collect_sources=lambda paths: local_audit))
    anchors = dict(external, compile_flags=worker.selected_compile_flags(),
                   compiler_version=trusted.compiler_version, audit_sources=audit,
                   host_tools=dict(trusted.host_tools, metadata=hashlib.sha256(metadata).hexdigest()))
    raw = json.dumps(receipt).encode()
    values = {"request.json": request(),
        "image_receipt.json": raw, "host-bindings.json": job.selected_inputs[build_id]["binding_raw"],
        "anchors.json": json.dumps(anchors).encode(), "metadata.json": metadata,
        "build.log": b"synthetic build", "host-build.log": b"synthetic host"}
    values.update({"prepared/" + k: v for k, v in prepared.items()})
    values.update({"objects/" + k: v for k, v in trusted.objects.items()})
    evidence_tree(base / "result/evidence", values)
    yield job, build_id, base, app, elf, raw, values, anchors
    finish_without_docker(job, build_id)
    job.delete(build_id)


def test_actual_collection_and_full_pure_validation_share_immutable_object_bytes(collected):
    job, build_id, base, app, elf, receipt, _, _ = collected
    result = job._collect_selected_result(build_id, base, app, elf, receipt)
    request_bytes, trusted, _ = job.selected_verified[build_id]
    assert trusted.objects["obj/unit.o"] is result.private_evidence["objects/obj/unit.o"]
    assert trusted.prepared_files["selected_project.bin"] is result.private_evidence["prepared/selected_project.bin"]
    envelope = json.loads(result.provenance)
    assert envelope["schema"] == 2 and "catalogue_manifest_sha256" not in envelope["host_bindings"]
    job.jobs[build_id] = WorkerSnapshot("succeeded", result)
    job.cleanup_confirmed.add(build_id)
    summary = job.verify_selected_trio_result(build_id, request_bytes, result)
    assert summary == envelope["validation"]
    assert summary["source_commit"] == job.config.source_commit


@pytest.mark.parametrize("mutation", ["source_archive", "host_binding", "operator_inputs", "worker_flags",
    "worker_source", "worker_audit", "worker_tools", "worker_metadata", "receipt_self_claim"])
def test_collection_refuses_changed_inputs_and_self_claims(collected, monkeypatch, mutation):
    job, build_id, base, app, elf, receipt, values, anchors = collected
    if mutation == "source_archive":
        path = base / "input/source.tar"
        path.chmod(0o600); path.write_bytes(b"changed archive")
    elif mutation == "host_binding":
        path = base / "input/host-bindings.json"
        path.chmod(0o600); path.write_bytes(b"{}")
    elif mutation == "operator_inputs":
        monkeypatch.setattr(adapter, "selected_external_inputs", lambda *args: {})
    else:
        if mutation == "worker_flags": anchors["compile_flags"] = ["-O2"]
        elif mutation == "worker_source": anchors["source_manifest"] = {"claimed": "0" * 64}
        elif mutation == "worker_audit": anchors["audit_sources"][0] = ("/workspace/other.c", 1, "changed")
        elif mutation == "worker_tools": anchors["host_tools"]["renderer"] = "0" * 64
        elif mutation == "worker_metadata": values["metadata.json"] = b"substituted metadata"
        else:
            claim = json.loads(receipt); claim["source_manifest"] = {"claimed": "0" * 64}
            receipt = json.dumps(claim).encode(); values["image_receipt.json"] = receipt
        values["anchors.json"] = json.dumps(anchors).encode()
        root = base / "result/evidence"
        adapter.shutil.rmtree(root)
        evidence_tree(root, values)
    with pytest.raises(ValueError):
        job._collect_selected_result(build_id, base, app, elf, receipt)
    assert build_id not in job.selected_verified


@pytest.mark.parametrize("relative", ["tools/installer_service/process_capture.py",
                                      "tools/installer_service/__init__.py"])
def test_capture_imports_are_mandatory_committed_prerequisites(tmp_path, relative):
    from tools.installer_service import build_capabilities as capabilities
    assert relative in capabilities.SELECTED_TRIO_PREREQUISITES
    source = tmp_path / "source"
    source.mkdir()
    for name in capabilities.SELECTED_TRIO_PREREQUISITES:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pinned source")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"]).decode().strip()
    capabilities.check_profile_prerequisites(source, commit, worker.SELECTED_TRIO_PROFILE)
    (source / relative).write_text("changed execution source")
    with pytest.raises(ValueError, match="differs from pinned"):
        capabilities.check_profile_prerequisites(source, commit, worker.SELECTED_TRIO_PROFILE)


def test_selected_imports_refuse_cached_module_from_other_root(tmp_path):
    with pytest.raises(ValueError, match="outside extracted source"):
        worker.verify_selected_imports(tmp_path)


@pytest.mark.parametrize("failure", ["stdout", "stderr", "nonzero"])
def test_selected_capture_actual_failure_is_bounded_and_causal(tmp_path, monkeypatch, failure):
    from tools.installer_service import process_capture
    original = process_capture.run_bounded
    def small_capture(command, **kwargs):
        assert kwargs["max_stream_bytes"] == 16 * 1024**2
        return original(command, **(kwargs | dict(max_stream_bytes=128)))
    monkeypatch.setattr(process_capture, "run_bounded", small_capture)
    monkeypatch.setattr(worker, "SOURCE", tmp_path)
    monkeypatch.setattr(worker, "RESULT", tmp_path)
    scripts = {"stdout": "print('x'*1024)", "stderr": "import sys;sys.stderr.write('x'*1024)",
               "nonzero": "raise SystemExit(3)"}
    # Preserve the observed-vs-cap check while avoiding a 16 MiB test product.
    if failure != "nonzero":
        def overflow(command, **kwargs):
            result = small_capture(command, **kwargs)
            result.observed[failure] = 16 * 1024**2 + 1
            return result
        monkeypatch.setattr(process_capture, "run_bounded", overflow)
    reason = "nonzero_exit" if failure == "nonzero" else "output_limit"
    with pytest.raises(ValueError, match=reason):
        worker._selected_capture([sys.executable, "-c", scripts[failure]])
    assert (tmp_path / "diagnostic.log").stat().st_size <= 256


@pytest.mark.parametrize("failure", ["bytes", "count"])
def test_worker_evidence_budget_refuses_before_next_file_read(tmp_path, monkeypatch, failure):
    first, second = tmp_path / "first.o", tmp_path / "second.o"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    captured = worker.SelectedEvidence(max_bytes=7 if failure == "bytes" else 100,
                                       max_files=1 if failure == "count" else 10)
    captured.retain_file("objects/first.o", first, 100)
    original_open = worker.os.open
    opened = []
    def spy(path, *args, **kwargs):
        opened.append(Path(path))
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(worker.os, "open", spy)
    with pytest.raises(ValueError):
        captured.retain_file("objects/second.o", second, 100)
    assert opened == []
    assert captured.values == {"objects/first.o": b"first"} and captured.total == 5


def test_worker_evidence_json_and_existing_bytes_share_one_budget():
    captured = worker.SelectedEvidence(max_bytes=16)
    captured.retain_bytes("request.json", b"request")
    with pytest.raises(ValueError, match="byte bound"):
        captured.retain_json("anchors.json", {"over": "budget"})
    with pytest.raises(ValueError, match="byte bound"):
        captured.retain_bytes("log", b"0123456789")
    assert list(captured.values) == ["request.json"] and captured.total == 7


@pytest.mark.parametrize("failure", ["input_preparation", "thread_start"])
def test_submit_rollback_failure_retains_owned_record_and_capacity(config, monkeypatch, failure):
    job = adapter.DockerJobAdapter(config)
    original_remove = adapter.shutil.rmtree
    def refuse_remove(*args, **kwargs):
        raise PermissionError("injected rollback removal refusal")
    monkeypatch.setattr(adapter.shutil, "rmtree", refuse_remove)
    if failure == "input_preparation":
        monkeypatch.setattr(adapter, "selected_external_inputs",
                            lambda *args: (_ for _ in ()).throw(ValueError("injected input failure")))
        expected = ValueError
    else:
        monkeypatch.setattr(adapter.threading.Thread, "start",
                            lambda self: (_ for _ in ()).throw(RuntimeError("injected thread failure")))
        expected = RuntimeError
    for index in range(4):
        build_id = str(index) * 32
        with pytest.raises(expected, match="injected"):
            submit(job, build_id)
        assert job.get(build_id).status == "failed"
        assert job.job_dirs[build_id].is_dir() and build_id not in job.threads
        assert build_id in job.cleanup_confirmed
        assert (build_id in job.selected_inputs) is (failure == "thread_start")
    with pytest.raises(QueueFull):
        submit(job, "4" * 32)
    monkeypatch.setattr(adapter.shutil, "rmtree", original_remove)
    for build_id in list(job.jobs):
        job.delete(build_id)
    assert not job.jobs and not job.selected_inputs and list(config.runtime_root.iterdir()) == []
    # Rollback released the execution semaphore as well as cleaning records.
    assert job.semaphore.acquire(blocking=False)
    job.semaphore.release()


def test_selected_delete_can_confirm_already_absent_owned_storage(config, monkeypatch):
    monkeypatch.setattr(adapter.threading.Thread, "start", lambda self: None)
    job = adapter.DockerJobAdapter(config)
    build_id = "a" * 32
    submit(job, build_id)
    finish_without_docker(job, build_id)
    adapter.shutil.rmtree(job.job_dirs[build_id])
    job.delete(build_id)
    assert job.get(build_id) is None and build_id not in job.selected_inputs

# SPDX-License-Identifier: MIT
"""Fake Docker responses for the private service container cleanup boundary."""
import json
import hashlib
import os
import time
from types import SimpleNamespace

import pytest

from tools.installer_service import docker_adapter as module
from tools.installer_service.api import WorkerTemplate
from tools.installer_service.process_capture import Capture
from tests.test_installer_service import _FakeDockerClientProcess, _docker_lifecycle_adapter

CID = "a" * 64


def _result(raw=b"", *, code=0, reason=None):
    return Capture(code, {"stdout": raw, "stderr": b""},
                   {"stdout": len(raw), "stderr": 0}, reason)


def _inspect(build_id, *, cid=CID, name=None, labels=None):
    owner = "lunar-private-" + build_id
    return json.dumps({"Id": cid, "Name": name or "/" + owner,
        "Config": {"Labels": labels if labels is not None else {
            "lan.project": "lunar-modulator",
            "lan.session": "installer-diagnostic-worker",
            "lan.owner": owner}}}).encode()


def _owned_root(tmp_path, build_id="B" * 32, cid=CID):
    base = tmp_path / build_id
    (base / "input").mkdir(parents=True)
    (base / "input/container.id").write_text(cid + "\n")
    return build_id, base


def _fake_docker(monkeypatch, inspection, removal=_result()):
    calls = []
    def capture(command, **limits):
        calls.append(command)
        assert limits["timeout_seconds"] == 10
        assert limits["max_stream_bytes"] == module._DOCKER_CAPTURE_CAP
        if command[1:3] == ["container", "inspect"]:
            return inspection
        assert command[1:3] == ["rm", "--force"]
        return removal
    monkeypatch.setattr(module, "run_bounded", capture)
    return calls


def test_failed_docker_run_name_collision_never_removes_foreign_container(tmp_path, monkeypatch):
    adapter, build_id, _base = _docker_lifecycle_adapter(tmp_path)
    proc = _FakeDockerClientProcess(initial_returncode=125)
    commands = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: (
        commands.append(args) or SimpleNamespace(returncode=0)))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert not any(command[1:3] == ["rm", "--force"] for command in commands)
    assert build_id in adapter.cleanup_unconfirmed
    adapter.delete(build_id)
    assert _base.exists()  # Preserve the ambiguous job for operator review.
    assert adapter.get(build_id).status == "failed"


def test_failed_run_with_preexisting_symlink_cidfile_preserves_foreign_path(tmp_path, monkeypatch):
    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    external = tmp_path / "foreign.id"
    external.write_text(CID + "\n")
    cidfile = base / "input/container.id"
    cidfile.symlink_to(external)
    proc = _FakeDockerClientProcess(initial_returncode=125)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_kw: proc)
    monkeypatch.setattr(module, "run_bounded", lambda *_a, **_kw: pytest.fail("no Docker cleanup"))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert build_id in adapter.cleanup_unconfirmed
    assert cidfile.is_symlink() and external.read_text() == CID + "\n"


@pytest.mark.parametrize("cid", [None, "bad", "A" * 64, "a" * 63])
def test_missing_or_malformed_cidfile_never_calls_docker(tmp_path, monkeypatch, cid):
    build_id, base = _owned_root(tmp_path)
    path = base / "input/container.id"
    if cid is None:
        path.unlink()
    else:
        path.write_text(cid)
    monkeypatch.setattr(module, "run_bounded", lambda *_a, **_kw: pytest.fail("no Docker call"))
    assert not module._remove_owned_container("docker", build_id, base)


def test_cidfile_symlink_cannot_redirect_cleanup(tmp_path, monkeypatch):
    build_id, base = _owned_root(tmp_path)
    external = tmp_path / "foreign.id"
    external.write_text(CID + "\n")
    (base / "input/container.id").unlink()
    (base / "input/container.id").symlink_to(external)
    monkeypatch.setattr(module, "run_bounded", lambda *_a, **_kw: pytest.fail("no Docker call"))
    assert not module._remove_owned_container("docker", build_id, base)
    assert external.read_text() == CID + "\n"


def test_cidfile_fifo_fails_promptly_without_docker(tmp_path, monkeypatch):
    build_id, base = _owned_root(tmp_path)
    cidfile = base / "input/container.id"
    cidfile.unlink()
    os.mkfifo(cidfile)
    monkeypatch.setattr(module, "run_bounded", lambda *_a, **_kw: pytest.fail("no Docker call"))
    started = time.monotonic()
    assert not module._remove_owned_container("docker", build_id, base)
    assert time.monotonic() - started < 1.0


@pytest.mark.parametrize("change", ["id", "name", "owner", "session", "project", "shape", "inspect_failure"])
def test_identity_or_label_mismatch_never_removes_container(tmp_path, monkeypatch, change):
    build_id, base = _owned_root(tmp_path)
    labels = {"lan.project": "lunar-modulator", "lan.session": "installer-diagnostic-worker",
              "lan.owner": "lunar-private-" + build_id}
    cid, name = CID, None
    if change == "id":
        cid = "b" * 64
    elif change == "name":
        name = "/different"
    elif change in ("owner", "session", "project"):
        labels["lan." + change] = "other"
    inspection = (_result(code=1) if change == "inspect_failure" else
                  _result(b"[]" if change == "shape" else
                          _inspect(build_id, cid=cid, name=name, labels=labels)))
    calls = _fake_docker(monkeypatch, inspection)
    assert not module._remove_owned_container("docker", build_id, base)
    assert len(calls) == 1
    assert calls[0][-1] == CID


def test_owned_container_is_inspected_and_removed_by_immutable_id(tmp_path, monkeypatch):
    build_id, base = _owned_root(tmp_path)
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id)))
    assert module._remove_owned_container("docker", build_id, base)
    assert calls == [
        ["docker", "container", "inspect", "--format", "{{json .}}", CID],
        ["docker", "rm", "--force", CID],
    ]


def test_shutdown_and_worker_share_one_verified_cleanup(tmp_path, monkeypatch):
    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    (base / "input/container.id").write_text(CID + "\n")
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id)))
    assert adapter._cleanup_container(build_id, base)  # Shutdown's survivor path.
    assert adapter._cleanup_container(build_id, base)  # Later worker finalizer.
    assert [command[1:3] for command in calls] == [
        ["container", "inspect"], ["rm", "--force"]]
    assert build_id in adapter.cleanup_confirmed
    assert build_id not in adapter.cleanup_unconfirmed


def test_failed_owned_removal_stays_unconfirmed(tmp_path, monkeypatch):
    build_id, base = _owned_root(tmp_path)
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id)), _result(code=1))
    assert not module._remove_owned_container("docker", build_id, base)
    assert calls[-1][-1] == CID


def test_partial_start_with_cidfile_cleans_only_verified_id(tmp_path, monkeypatch):
    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    proc = _FakeDockerClientProcess(initial_returncode=125)
    def start(command, **_kwargs):
        assert command[command.index("--cidfile") + 1] == str(base / "input/container.id")
        assert "lan.owner=lunar-private-" + build_id in command
        (base / "input/container.id").write_text(CID + "\n")
        return proc
    monkeypatch.setattr(module.subprocess, "Popen", start)
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id)))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"  # The failed run cannot yield an artifact.
    assert build_id not in adapter.cleanup_unconfirmed
    assert calls[-1] == ["docker", "rm", "--force", CID]


def test_timeout_cancels_verified_owner_by_id(tmp_path, monkeypatch):
    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    (base / "input/container.id").write_text(CID + "\n")
    proc = _FakeDockerClientProcess(initial_returncode=None)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_kw: proc)
    ticks = iter([10.0, 12.0])
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id)))
    adapter._run(build_id)
    assert proc.killed and proc.waited
    assert adapter.get(build_id).status == "failed"
    assert build_id not in adapter.cleanup_unconfirmed
    assert calls[-1] == ["docker", "rm", "--force", CID]


def test_teardown_mismatch_retains_job_and_refuses_shutdown(tmp_path, monkeypatch):
    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    (base / "input/container.id").write_text(CID + "\n")
    proc = _FakeDockerClientProcess(initial_returncode=0)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *_a, **_kw: proc)
    calls = _fake_docker(monkeypatch, _result(_inspect(build_id, cid="b" * 64)))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert build_id in adapter.cleanup_unconfirmed
    adapter.delete(build_id)
    assert base.exists()
    assert adapter.get(build_id).status == "failed"
    request = b"{}"
    with pytest.raises(RuntimeError, match="cleanup is unconfirmed"):
        adapter.submit("C" * 32, request, hashlib.sha256(request).hexdigest(),
                       WorkerTemplate(module._IMAGE_ID, "private-test"))
    assert not (adapter.config.runtime_root / ("C" * 32)).exists()
    with pytest.raises(RuntimeError, match="cleanup was not confirmed"):
        adapter.shutdown(timeout_seconds=1)
    assert len(calls) == 1

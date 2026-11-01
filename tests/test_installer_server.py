# SPDX-License-Identifier: MIT
"""Launcher tests never start a listener, native builder or Docker process."""
from dataclasses import replace
from pathlib import Path
import subprocess
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from tools.installer_service import server
from tools.installer_service.api import FakeJobAdapter


def config(tmp_path):
    return server.ServiceConfig(server.ROOT, "a" * 40, tmp_path, tmp_path, tmp_path)


def test_private_service_is_disabled_without_operator_enablement(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "check_native_prerequisites", lambda *_: pytest.fail("must refuse first"))
    with pytest.raises(ValueError, match="explicit operator enablement"):
        server.create_private_app(config(tmp_path))


def test_current_integration_refuses_missing_native_runtime_before_adapter(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DockerJobAdapter", lambda *_args, **_kw: pytest.fail("must not create adapter"))
    monkeypatch.setattr(server, "check_native_audit", lambda *_: None)
    commit = subprocess.run(["git", "-C", str(server.ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    with pytest.raises(ValueError, match="native build prerequisites are unavailable"):
        server.create_private_app(replace(config(tmp_path), source_commit=commit, enable_private_builds=True))


def test_local_untracked_runtime_files_cannot_satisfy_source_archive_gate(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=test@example.invalid",
                    "-c", "user.name=Test", "commit", "--allow-empty", "-qm", "fixture"], check=True)
    commit = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    for relative in server.NATIVE_PREREQUISITES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic untracked fixture")
    with pytest.raises(ValueError, match="unavailable"):
        server.check_native_prerequisites(tmp_path, commit)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=test@example.invalid",
                    "-c", "user.name=Test", "commit", "-qm", "fixture inventory"], check=True)
    commit = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True).stdout.strip()
    server.check_native_prerequisites(tmp_path, commit)
    path = tmp_path / server.NATIVE_PREREQUISITES[0]
    path.unlink()
    path.symlink_to(tmp_path / server.NATIVE_PREREQUISITES[1])
    with pytest.raises(ValueError, match="unavailable"):
        server.check_native_prerequisites(tmp_path, commit)


def test_explicit_test_adapter_exercises_queue_with_host_and_download_guards(tmp_path, monkeypatch):
    # Only this test replaces production dependencies; the launcher has no fake mode.
    monkeypatch.setattr(server, "check_native_prerequisites", lambda *_: None)
    monkeypatch.setattr(server, "check_native_audit", lambda *_: None)
    def worker(**values):
        assert values["cpu_limit"] == "4" and values["memory_limit"] == "6g"
        return SimpleNamespace(**values)
    monkeypatch.setattr(server, "DockerWorkerConfig", worker)
    adapter = FakeJobAdapter(1)
    monkeypatch.setattr(server, "DockerJobAdapter", lambda _worker, capacity: adapter)
    monkeypatch.setattr(server, "load_trusted_catalogue", lambda *_a, **_kw: ({"trio": "sound"}, {"song"}, {}))
    app = server.create_private_app(replace(config(tmp_path), enable_private_builds=True))
    request = {"version": 1, "engines": ["trio"], "effects": [], "midi": [],
               "modulation": [], "project_ids": ["song"], "startup_index": 0}
    with TestClient(app, base_url="http://127.0.0.1") as client:
        response = client.post("/api/v1/builds", json=request)
        assert response.status_code == 202
        identifier = response.json()["id"]
        status = client.get("/api/v1/builds/" + identifier)
        assert status.status_code == 200 and status.json()["status"] == "queued"
        assert client.post("/api/v1/builds", json=request).status_code == 429
        assert client.get("/api/v1/builds/" + identifier + "/artifact").status_code == 404
        assert client.post("/api/v1/builds", json=request, headers={"Host": "attacker.invalid"}).status_code == 400
        preflight = client.options("/api/v1/builds", headers={"Origin": "https://attacker.invalid",
                   "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
        assert "access-control-allow-origin" not in preflight.headers


def test_cli_always_binds_loopback_with_one_worker(tmp_path, monkeypatch):
    import uvicorn
    marker = object()
    monkeypatch.setattr(server, "create_private_app", lambda _config: marker)
    calls = []
    monkeypatch.setattr(uvicorn, "run", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert server.main(["--source-commit", "a" * 40, "--toolchain", str(tmp_path),
                        "--catalogue", str(tmp_path), "--runtime", str(tmp_path)]) == 0
    assert calls == [((marker,), {"host": "127.0.0.1", "port": 8765, "workers": 1,
                                  "proxy_headers": False, "server_header": False})]


def test_missing_audit_capability_refuses_before_native_checks(tmp_path, monkeypatch):
    audit_path = tmp_path / "tools/jieli/audit_link.py"
    audit_path.parent.mkdir(parents=True)
    audit_path.write_text("def audit(elves, flat_images, linked, sources=None, runtime='sdk'):\n    pass\n")
    actual_check_native_audit = server.check_native_audit
    monkeypatch.setattr(server, "check_native_audit", lambda _root: actual_check_native_audit(tmp_path))
    monkeypatch.setattr(server, "check_native_prerequisites", lambda *_: pytest.fail("audit must refuse first"))
    monkeypatch.setattr(server, "DockerJobAdapter", lambda *_args, **_kw: pytest.fail("must not create adapter"))
    with pytest.raises(ValueError, match="native audit prerequisites are unavailable") as error:
        server.create_private_app(replace(config(tmp_path), enable_private_builds=True))
    for missing in ("relative_call_payloads", "stub_call_boundary_patterns", "--objdump"):
        assert missing in str(error.value)


def test_current_audit_capability_reaches_native_prerequisite_refusal(tmp_path, monkeypatch):
    server.check_native_audit(server.ROOT)
    monkeypatch.setattr(server, "DockerJobAdapter", lambda *_args, **_kw: pytest.fail("must not create adapter"))
    commit = subprocess.run(["git", "-C", str(server.ROOT), "rev-parse", "HEAD"],
                            capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    with pytest.raises(ValueError, match="native build prerequisites are unavailable"):
        server.create_private_app(replace(config(tmp_path), source_commit=commit, enable_private_builds=True))


def test_audit_capability_gate_rejects_unsafe_path_without_importing_it(tmp_path):
    directory = tmp_path / "tools/jieli"
    directory.mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("raise AssertionError('must not execute source')")
    (directory / "audit_link.py").symlink_to(outside)
    with pytest.raises(ValueError, match="audit_link.py"):
        server.check_native_audit(tmp_path)

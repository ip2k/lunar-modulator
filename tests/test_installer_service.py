# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.installer_service.api import FakeJobAdapter, WorkerTemplate, canonical_request, create_app
from tools.installer_service.catalogue import load_trusted_catalogue

MODULES = {"sound-a": "sound", "fx-a": "audio_fx", "midi-a": "midi_fx", "mod-a": "mod"}
PROJECTS = {"song-one", "song-two"}
TEMPLATE = WorkerTemplate("sha256:" + "a" * 64, "lunar-private-builds")


def client(capacity=1, queue_cap=1):
    adapter = FakeJobAdapter(capacity)
    app = create_app(adapter=adapter, template=TEMPLATE, module_kinds=MODULES,
                     project_ids=PROJECTS, queue_cap=queue_cap)
    return TestClient(app), adapter


def request_doc():
    return {"version": 1, "engines": ["sound-a"], "effects": ["fx-a"],
            "midi": ["midi-a"], "modulation": ["mod-a"],
            "project_ids": ["song-one", "song-two"], "startup_index": 1}


def raw(client, text, **headers):
    return client.post("/api/v1/builds", content=text,
                       headers={"content-type": "application/json", **headers})


def test_accepts_canonical_request_with_opaque_id_and_fixed_template():
    c, adapter = client()
    response = c.post("/api/v1/builds", json=request_doc())
    assert response.status_code == 202
    build_id = response.json()["id"]
    assert len(build_id) == 32 and build_id != "song-one"
    data, digest, template = adapter.submissions[build_id]
    assert data == canonical_request(request_doc())
    assert digest == hashlib.sha256(data).hexdigest()
    assert template == TEMPLATE
    assert c.get(response.json()["status_url"]).json()["status"] == "queued"


def test_rejects_duplicate_json_keys_before_queueing():
    c, adapter = client()
    body = json.dumps(request_doc(), separators=(",", ":")).replace(
        '"version":1', '"version":1,"version":1')
    assert raw(c, body).status_code == 422
    assert adapter.jobs == {}


@pytest.mark.parametrize("patch", [
    {"unknown": True}, {"version": True}, {"version": "1"},
    {"startup_index": True}, {"startup_index": 2}, {"engines": []},
    {"engines": ["sound-a", "sound-a"]}, {"engines": ["fx-a"]},
    {"effects": ["unknown"]}, {"project_ids": ["unknown"]},
    {"project_ids": ["song-one", "song-one"]},
])
def test_rejects_invalid_schema_or_catalogue(patch):
    c, adapter = client()
    doc = request_doc()
    doc.update(patch)
    assert c.post("/api/v1/builds", json=doc).status_code == 422
    assert adapter.jobs == {}


def test_rejects_type_encoding_and_content_encoding():
    c, adapter = client()
    assert c.post("/api/v1/builds", content="{}", headers={"content-type": "text/plain"}).status_code == 415
    assert raw(c, "{}", **{"content-encoding": "gzip"}).status_code == 415
    assert adapter.jobs == {}


def test_body_limit_streaming_and_nonfinite_values():
    c, adapter = client()
    assert raw(c, " " * (65536 + 1)).status_code == 413
    assert raw(c, '{"n":NaN}').status_code == 422
    assert adapter.jobs == {}


def test_queue_cap_opaque_lookup_and_state_transitions():
    c, adapter = client(capacity=4, queue_cap=1)
    first = c.post("/api/v1/builds", json=request_doc())
    second = c.post("/api/v1/builds", json=request_doc())
    assert first.status_code == 202
    assert second.status_code == 429
    assert second.headers["retry-after"] == "30"
    assert len(adapter.jobs) == 1
    assert c.get("/api/v1/builds/not-an-id").status_code == 404
    build_id = first.json()["id"]
    adapter.set_running(build_id)
    assert c.get(first.json()["status_url"]).json()["status"] == "running"
    adapter.fail(build_id)
    assert c.get(first.json()["status_url"]).json()["status"] == "failed"
    assert c.post("/api/v1/builds", json=request_doc()).status_code == 202


def result_receipt(doc, req_sha, artifact):
    prepared_sha = "1" * 64
    content = [{"kind": "project", "bytes": 128, "packed_sha256": "2" * 64} for _ in doc["project_ids"]]
    return json.dumps({
        "version": 1, "status": "linked-private-diagnostic",
        "request_sha256": req_sha, "prepared_profile_sha256": prepared_sha,
        "project_ids": doc["project_ids"], "startup_index": doc["startup_index"],
        "startup_project_id": doc["project_ids"][doc["startup_index"]],
        "module_selection": {"selected": [m for g in ("engines", "effects", "midi", "modulation") for m in doc[g]]},
        "content": content,
        "embedded_content": {"prepared_sha256": prepared_sha, "assets": content,
            "asset_count": len(content), "packed_content_bytes": 128 * len(content),
            "packed_sha256": [a["packed_sha256"] for a in content],
            "native_playback_verified": False, "sequence_semantics_verified": False},
        "app_sha256": hashlib.sha256(artifact).hexdigest(), "elf_sha256": "3" * 64,
        "app_bytes": len(artifact), "app_budget_bytes": 1048576,
        "installable": False, "hardware_admitted": False, "hardware_tested": False,
        "native_ram_verified": False, "native_playback_verified": False,
        "full_song_default_accepted": False,
        "project_save_service": {"linked": True, "compile_definition": "LUNAR_PROJECT_SAVE_SERVICE=1",
            "storage_admitted": False, "flash_io_bound": False, "save_service_armed": False,
            "runtime_verified": False, "hardware_tested": False},
        "state_bin_codec": {"mode": "compact-writer", "compile_definition": "FM1_STATE_BIN_COMPACT_WRITER=1",
            "replaced_exactly_one": True, "source_sha256": "4" * 64,
            "fresh_object": "/worker/fresh.o", "fresh_object_sha256": "5" * 64,
            "cached_object": "/worker/cached.o", "cached_object_sha256": "6" * 64},
        "verification_sha256": "7" * 64, "artifact_receipt_sha256": "8" * 64,
    }).encode()


def accept_and_succeed(c, adapter, receipt_transform=None, artifact=b"diagnostic-app"):
    accepted = c.post("/api/v1/builds", json=request_doc())
    build_id = accepted.json()["id"]
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    receipt = json.loads(result_receipt(doc, req_sha, artifact))
    if receipt_transform:
        receipt_transform(receipt)
    if isinstance(receipt, dict):
        encoded = json.dumps(receipt).encode()
    else:
        encoded = receipt
    adapter.succeed(build_id, artifact, encoded)
    return accepted


def test_success_verifies_exact_request_and_app_bytes():
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["artifact_sha256"] == hashlib.sha256(b"diagnostic-app").hexdigest()
    assert result["installable"] is False
    assert result["hardware_tested"] is False


@pytest.mark.parametrize("mutation", [
    lambda d: d.update(request_sha256="0" * 64),
    lambda d: d.update(app_sha256="0" * 64),
    lambda d: d.update(app_bytes=True),
    lambda d: d.update(project_ids=["song-two"]),
    lambda d: d.update(installable=True),
    lambda d: d.update(status="release"),
    lambda d: d["module_selection"].update(selected=["other"]),
    lambda d: d.pop("state_bin_codec"),
    lambda d: d.update(startup_project_id="song-one"),
    lambda d: d["project_save_service"].update(save_service_armed=True),
    lambda d: d["content"].__setitem__(0, None),
    lambda d: d["content"][0].update(bytes="128"),
    lambda d: d["content"][0].update(bytes=[128]),
])
def test_rejects_unbound_or_overclaiming_result(mutation):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, mutation)
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_result_cap_and_unknown_ids_do_not_expose_artifact():
    c, adapter = client()
    assert c.get("/api/v1/builds/" + "a" * 32).status_code == 404
    accepted = c.post("/api/v1/builds", json=request_doc())
    adapter.succeed(accepted.json()["id"], b"x" * (1048576 + 1), b"{}")
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_trusted_catalogue_loader_uses_make_ids_and_project_constants():
    modules, projects = load_trusted_catalogue()
    assert modules["macro"] == "sound"
    assert modules["plate"] == "audio_fx"
    assert "test-sine" not in modules
    assert "replacement-showcase-candidate-satellite-hearts" in projects
    assert len(projects) == 8


def test_rejects_over_budget_even_when_artifact_hash_matches():
    c, adapter = client()
    accepted = c.post("/api/v1/builds", json=request_doc())
    build_id = accepted.json()["id"]
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    artifact = b"x" * 500
    receipt = json.loads(result_receipt(doc, req_sha, artifact))
    receipt["app_budget_bytes"] = len(artifact) - 1
    adapter.succeed(build_id, artifact, json.dumps(receipt).encode())
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_worker_image_digest_requires_hex_sha256():
    with pytest.raises(ValueError):
        WorkerTemplate("sha256:" + "g" * 64, "lunar-private-builds")
    with pytest.raises(ValueError):
        WorkerTemplate("sha256:" + "A" * 64, "lunar-private-builds")


def test_terminal_admissions_expire_and_record_count_stays_bounded():
    now = [0.0]
    adapter = FakeJobAdapter(2)
    app = create_app(adapter=adapter, template=TEMPLATE, module_kinds=MODULES,
                     project_ids=PROJECTS, queue_cap=1, record_cap=1,
                     retention_seconds=60, clock=lambda: now[0])
    c = TestClient(app)
    accepted = c.post("/api/v1/builds", json=request_doc())
    build_id = accepted.json()["id"]
    adapter.fail(build_id)
    assert c.get(accepted.json()["status_url"]).status_code == 200
    assert c.post("/api/v1/builds", json=request_doc()).status_code == 429
    now[0] += 60
    assert c.post("/api/v1/builds", json=request_doc()).status_code == 202
    assert len(adapter.jobs) == len(adapter.submissions) == 1
    assert c.get(accepted.json()["status_url"]).status_code == 404


def test_record_retention_does_not_expire_active_work():
    now = [0.0]
    adapter = FakeJobAdapter(2)
    app = create_app(adapter=adapter, template=TEMPLATE, module_kinds=MODULES,
                     project_ids=PROJECTS, queue_cap=1, record_cap=1,
                     retention_seconds=60, clock=lambda: now[0])
    c = TestClient(app)
    accepted = c.post("/api/v1/builds", json=request_doc())
    now[0] += 120
    assert c.get(accepted.json()["status_url"]).json()["status"] == "queued"
    assert c.post("/api/v1/builds", json=request_doc()).status_code == 429


@pytest.mark.skipif(not __import__("os").environ.get("LUNAR_RETAINED_BUILD"),
                    reason="set LUNAR_RETAINED_BUILD to use the Hera retained real build")
def test_actual_retained_controller_receipt_through_testclient():
    import os
    from tools.installer_service.catalogue import load_trusted_catalogue
    root = Path(os.environ["LUNAR_RETAINED_BUILD"])
    sys.path.insert(0, str(ROOT / "tools/native"))
    from build_demo_image import read_report, checked_link_receipt
    from verify_image_profile import load_prepared_profile

    selection = read_report(root / "selection/selection.json")
    prepared = load_prepared_profile(root / "selection/prepared", selection["prepared_profile_sha256"])
    verification = read_report(root / "link/verification.json")
    artifact = read_report(root / "link/artifact/artifact.json")
    app_bytes = (root / "link/artifact/app.bin").read_bytes()
    elf = (root / "link/lunar-app-probe.elf").read_bytes()
    receipt = checked_link_receipt(selection, prepared, verification, artifact,
                                   app_bytes, elf, require_save_service=True)
    # This regenerated current-format receipt adds fields absent from the older saved image.json.
    receipt.update(project_save_service=verification["project_save_service"],
                   state_bin_codec=verification["state_bin_codec"],
                   verification_sha256=hashlib.sha256((root / "link/verification.json").read_bytes()).hexdigest(),
                   artifact_receipt_sha256=hashlib.sha256((root / "link/artifact/artifact.json").read_bytes()).hexdigest())
    request = read_report(root / "selection/request.json")
    modules, projects = load_trusted_catalogue()
    adapter = FakeJobAdapter(1)
    client = TestClient(create_app(adapter=adapter, template=TEMPLATE,
                                   module_kinds=modules, project_ids=projects))
    accepted = client.post("/api/v1/builds", json=request)
    assert accepted.status_code == 202
    build_id = accepted.json()["id"]
    request_bytes, req_sha, _ = adapter.submissions[build_id]
    assert req_sha == selection["request_sha256"]
    assert hashlib.sha256(request_bytes).hexdigest() == req_sha
    adapter.succeed(build_id, app_bytes, json.dumps(receipt).encode())
    response = client.get(accepted.json()["status_url"])
    assert response.status_code == 200, response.text
    assert response.json()["result"]["artifact_sha256"] == hashlib.sha256(app_bytes).hexdigest()

    mutations = [
        lambda item: item["module_selection"].update(selected=[]),
        lambda item: item.pop("state_bin_codec"),
        lambda item: item.update(startup_project_id="wrong-project"),
        lambda item: item.update(app_budget_bytes=len(app_bytes) - 1),
    ]
    for mutate in mutations:
        rejected = client.post("/api/v1/builds", json=request)
        assert rejected.status_code == 202
        rejected_id = rejected.json()["id"]
        bad_receipt = json.loads(json.dumps(receipt))
        mutate(bad_receipt)
        adapter.succeed(rejected_id, app_bytes, json.dumps(bad_receipt).encode())
        assert client.get(rejected.json()["status_url"]).status_code == 502

def test_docker_adapter_uses_fixed_container_contract_and_pinned_source(tmp_path, monkeypatch):
    import subprocess
    from tools.installer_service.docker_adapter import DockerJobAdapter, DockerWorkerConfig

    source = tmp_path / "source"
    toolchain = tmp_path / "toolchain"
    runtime = tmp_path / "runtime"
    source.mkdir()
    toolchain.mkdir()
    runtime.mkdir()
    (source / "tracked.txt").write_text("tracked")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    config = DockerWorkerConfig(source, toolchain, runtime, commit)
    adapter = DockerJobAdapter(config)
    monkeypatch.setattr(adapter, "_run", lambda _build_id: None)
    data = canonical_request(request_doc())
    build_id = "A" * 32
    pinned_template = WorkerTemplate("sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d",
                                    "lunar-private-builds")
    adapter.submit(build_id, data, hashlib.sha256(data).hexdigest(), pinned_template)
    base = runtime / build_id
    assert adapter.get(build_id).status == "queued"
    assert (base / "input/request.json").read_bytes() == data
    assert (base / "input/source.tar").stat().st_size > 0
    command = adapter._command(build_id, base, base / "container.id")
    joined = " ".join(command)
    for option in ("--cgroup-parent=docker-batch.slice", "--network=none", "--cpus=4", "--memory=8g",
                   "--memory-swap=8g", "--pids-limit=512", "--read-only",
                   "--cap-drop=ALL", "--security-opt=no-new-privileges",
                   "--user 1001:1001"):
        assert option in joined
    assert config.image_reference in command
    assert "/output/build" not in joined
    assert "request.json" in joined and "source.tar" in joined
    adapter.delete(build_id)
    assert not base.exists()


def test_docker_adapter_rejects_mutable_source_and_unpinned_image(tmp_path):
    import subprocess
    from tools.installer_service.docker_adapter import DockerWorkerConfig

    source = tmp_path / "source"
    toolchain = tmp_path / "toolchain"
    runtime = tmp_path / "runtime"
    source.mkdir()
    toolchain.mkdir()
    runtime.mkdir()
    (source / "tracked.txt").write_text("tracked")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    (source / "tracked.txt").write_text("modified")
    with pytest.raises(ValueError, match="clean commit"):
        DockerWorkerConfig(source, toolchain, runtime, commit)
    (source / "tracked.txt").write_text("tracked")
    with pytest.raises(ValueError, match="immutable image"):
        DockerWorkerConfig(source, toolchain, runtime, commit,
                           image_reference="lunar-recovery-pytest:latest")

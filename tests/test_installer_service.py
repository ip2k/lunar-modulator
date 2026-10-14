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
    return json.dumps({
        "version": 1, "status": "linked-private-diagnostic",
        "request_sha256": req_sha, "project_ids": doc["project_ids"],
        "startup_index": doc["startup_index"],
        "app_sha256": hashlib.sha256(artifact).hexdigest(),
        "app_bytes": len(artifact), "installable": False,
        "hardware_admitted": False, "hardware_tested": False,
        "native_ram_verified": False, "native_playback_verified": False,
        "full_song_default_accepted": False,
    }).encode()


def accept_and_succeed(c, adapter, receipt_transform=None, artifact=b"diagnostic-app"):
    accepted = c.post("/api/v1/builds", json=request_doc())
    build_id = accepted.json()["id"]
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    receipt = json.loads(result_receipt(doc, req_sha, artifact))
    if receipt_transform:
        receipt_transform(receipt)
    adapter.succeed(build_id, artifact, json.dumps(receipt).encode())
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

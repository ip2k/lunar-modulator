"""End-to-end local development API checks with synthetic firmware only."""

import hashlib
import http.client
import json
import threading

import pytest

from tools.fm1_workbench import make_server
from tools.fm1_workspace import DevelopmentWorkspace, WorkspaceError, MAX_SOURCES


APP = b"FM-1_015\0" + bytes(range(256)) * 2


class NoDevice:
    def ports(self):
        raise AssertionError("offline development must not access MIDI")

    identify = ports


@pytest.fixture
def service(tmp_path):
    server = make_server(0, NoDevice(), tmp_path / "projects")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()
    thread.join(2)


def request(server, method, path, body=None, content_type=None, origin=True):
    host, port = server.server_address
    headers = {}
    if origin:
        headers["Origin"] = f"http://{host}:{port}"
    if isinstance(body, dict):
        body = json.dumps(body).encode()
        content_type = "application/json"
    if content_type:
        headers["Content-Type"] = content_type
    connection = http.client.HTTPConnection(host, port, timeout=20)
    try:
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        payload = response.read()
        return response.status, dict(response.headers), payload
    finally:
        connection.close()


def post(server, path, body, content_type=None):
    status, _, data = request(server, "POST", path, body, content_type)
    assert status == 200, data.decode()
    return json.loads(data)


def test_inspect_modify_download_restore_and_reload_project(service):
    original = post(service, "/api/analyze?kind=app", APP, "application/octet-stream")
    assert original["sha256"] == hashlib.sha256(APP).hexdigest()
    assert original["application_size"] == len(APP)
    status, _, data = request(service, "GET", f"/api/hex?source_id={original['source_id']}&offset=9&length=16")
    assert status == 200
    assert bytes.fromhex(json.loads(data)["hex"]) == APP[9:25]
    project = post(service, "/api/projects/create", {"source_id": original["source_id"], "label": "Synthetic test"})
    modified = post(service, "/api/rebuild", {"source_id": original["source_id"],
        "expected_source_sha256": original["sha256"],
        "patches": [{"offset": 9, "expected_hex": "00", "replacement_hex": "ff", "label": "Byte probe"}]})
    status, headers, firmware = request(service, "GET", modified["download_url"])
    assert status == 200 and headers["Content-Disposition"].startswith("attachment;")
    assert firmware == APP[:9] + b"\xff" + APP[10:]
    _, manifest_headers, manifest_data = request(service, "GET", modified["manifest_download_url"])
    assert manifest_headers["Content-Disposition"].startswith("attachment;")
    assert json.loads(manifest_data) == modified["manifest"]
    updated_project = post(service, "/api/projects/revision", {"project_id": project["id"], "parent_id": 1,
        "source_id": modified["source_id"], "manifest": modified["manifest"], "label": "Byte probe"})
    revision_id = updated_project["revision_id"]
    restored = post(service, "/api/rollback", {"source_id": modified["source_id"], "manifest": modified["manifest"]})
    assert restored["sha256"] == original["sha256"]
    # A fresh service state recovers actual project bytes after the transient cache is gone.
    fresh = DevelopmentWorkspace(service.workspace.project_dir)
    loaded = fresh.load_project({"project_id": project["id"], "revision_id": revision_id})
    assert fresh.source(loaded["source_id"])["raw"] == firmware
    assert loaded["manifest"] == modified["manifest"]
    status, project_headers, project_bytes = request(service, "GET", project["download_url"])
    assert status == 200 and project_headers["Content-Disposition"].endswith('.fm1proj"')
    imported = post(service, "/api/projects/import", project_bytes, "application/octet-stream")
    assert imported["id"] != project["id"]
    assert imported["summary"]["source_sha256"] == original["sha256"]
    assert len(imported["revisions"]) == 2


def test_wrong_origin_cannot_rebuild_or_persist(service):
    for path, body in [("/api/rebuild", {}), ("/api/projects/create", {}), ("/api/projects/import", b"invalid")]:
        status, _, _ = request(service, "POST", path, body, "application/octet-stream", origin=False)
        assert status == 403
    assert service.workspace.projects() == {"projects": []}


def test_reject_unknown_source_paths_and_stale_preimage(service):
    original = post(service, "/api/analyze?kind=app", APP, "application/octet-stream")
    for body in [
        {"source_id": original["source_id"], "expected_source_sha256": "0" * 64, "patches": []},
        {"source_id": "../../private", "expected_source_sha256": original["sha256"], "patches": []},
        {"source_id": original["source_id"], "expected_source_sha256": original["sha256"],
         "patches": [{"offset": 9, "expected_hex": "01", "replacement_hex": "ff"}]},
    ]:
        status, _, _ = request(service, "POST", "/api/rebuild", body)
        assert status == 400
    assert service.workspace.source(original["source_id"])["raw"] == APP
    assert len(service.workspace.sources) == 1


def test_cache_is_bounded_and_expired_ids_fail_clearly(tmp_path):
    workspace = DevelopmentWorkspace(tmp_path)
    first = workspace.analyze(APP, "app")["source_id"]
    for index in range(MAX_SOURCES):
        workspace.analyze(APP + bytes([index]), "app")
    assert len(workspace.sources) == MAX_SOURCES
    with pytest.raises(WorkspaceError, match="no longer loaded"):
        workspace.source(first)


def test_invalid_project_upload_is_not_retained(service):
    status, _, _ = request(service, "POST", "/api/projects/import", b"not a SQLite database", "application/octet-stream")
    assert status == 400
    assert service.workspace.projects() == {"projects": []}

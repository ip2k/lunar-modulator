# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools/native"))
from build_demo_image import (BASE_INSTANCE_POOL_BYTES as BUILDER_BASE_INSTANCE_POOL_BYTES,
                              BRAIDS_TABLE as BUILDER_BRAIDS_TABLE,
                              SHAPES_VOICES as BUILDER_SHAPES_VOICES,
                              TARGET_STORAGE as BUILDER_TARGET_STORAGE,
                              WAVETABLE_PROFILE as BUILDER_WAVETABLE_PROFILE)
from tools.installer_service.api import (BASE_INSTANCE_POOL_BYTES, SHAPES_VOICES,
    TARGET_STORAGE, WAVETABLES, WAVETABLE_PROFILE, FakeJobAdapter, WorkerTemplate,
    canonical_request, create_app)
from tools.installer_service.catalogue import load_trusted_catalogue
from tools.native.runtime_mode import runtime_configuration

MODULES = {"sound-a": "sound", "shapes": "sound", "fx-a": "audio_fx", "midi-a": "midi_fx", "mod-a": "mod"}
PROJECTS = {"song-one", "song-two"}
SETS = {"companion-one": "song-one"}
TEMPLATE = WorkerTemplate("sha256:" + "a" * 64, "lunar-private-builds")
TEST_ELF = b"diagnostic-elf"


def client(capacity=1, queue_cap=1, set_parents=None):
    adapter = FakeJobAdapter(capacity)
    app = create_app(adapter=adapter, template=TEMPLATE, module_kinds=MODULES,
                     project_ids=PROJECTS, set_parents=set_parents, queue_cap=queue_cap)
    return TestClient(app), adapter


def request_doc():
    return {"version": 1, "engines": ["sound-a"], "effects": ["fx-a"],
            "midi": ["midi-a"], "modulation": ["mod-a"],
            "project_ids": ["song-one", "song-two"], "startup_index": 1}


def raw(client, text, **headers):
    return client.post("/api/v1/builds", content=text,
                       headers={"content-type": "application/json", **headers})


def test_service_and_builder_share_the_fixed_wavetable_contract():
    assert WAVETABLE_PROFILE == BUILDER_WAVETABLE_PROFILE
    assert WAVETABLES["braids"] == BUILDER_BRAIDS_TABLE
    assert TARGET_STORAGE == BUILDER_TARGET_STORAGE
    assert BASE_INSTANCE_POOL_BYTES == BUILDER_BASE_INSTANCE_POOL_BYTES
    assert SHAPES_VOICES == BUILDER_SHAPES_VOICES


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


def result_receipt(doc, req_sha, artifact, elf=TEST_ELF):
    prepared_sha = "1" * 64
    content = [{"kind": "project", "id": project, "bytes": 128,
                "packed_sha256": "2" * 64} for project in doc["project_ids"]]
    content += [{"kind": "set", "id": set_id, "parent_project_id": "song-one",
                 "bytes": 64, "packed_sha256": "3" * 64}
                for set_id in doc.get("set_ids", [])]
    selected = [m for g in ("engines", "effects", "midi", "modulation") for m in doc[g]]
    set_ids = doc.get("set_ids", [])
    selected_content = ([{"kind": "project", "id": project} for project in doc["project_ids"]]
                        + [{"kind": "set", "id": set_id, "parent_project_id": "song-one"}
                           for set_id in set_ids])
    wave_rows = ([{"namespace": "braids", "symbol": "wt_waves", "width": 1,
                   "raw_bytes": 33024,
                   "raw_sha256": "c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634",
                   "packed_bytes": 24159, "packed_sha256": "9" * 64,
                   "fnv32": 3119621762, "generated_source_sha256": "a" * 64}]
                 if "shapes" in selected else [])
    pool_bytes = 249088 - (33024 if wave_rows else 0)
    return json.dumps({
        "version": 1, "status": "linked-private-diagnostic",
        "request_sha256": req_sha, "prepared_profile_sha256": prepared_sha,
        "project_ids": doc["project_ids"], "set_ids": set_ids,
        "set_parents": {set_id: "song-one" for set_id in set_ids},
        "selected_content": selected_content, "startup_index": doc["startup_index"],
        "startup_project_id": doc["project_ids"][doc["startup_index"]],
        "runtime_hook_linked": len(doc["project_ids"]) > 1,
        "runtime_configuration": runtime_configuration("diagnostic"),
        "module_selection": {"selected": selected},
        "wavetable_profile": "compressed-required-banks-flash-plaits-v1",
        "compressed_wave_tables": wave_rows, "indexed_tft": True,
        "flash_plaits_wavetables": True, "shapes_voices": 12,
        "instance_pool_bytes": pool_bytes,
        "target_app_storage": {"rgb565_bytes": 220832, "indexed_bytes": 163744,
                               "pool_credit_bytes": 57088},
        "content": content,
        "embedded_content": {"prepared_sha256": prepared_sha, "assets": content,
            "asset_count": len(content), "packed_content_bytes": sum(a["bytes"] for a in content),
            "packed_sha256": [a["packed_sha256"] for a in content],
            "native_playback_verified": False, "sequence_semantics_verified": False},
        "app_sha256": hashlib.sha256(artifact).hexdigest(),
        "elf_sha256": hashlib.sha256(elf).hexdigest(),
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


def accept_and_succeed(c, adapter, receipt_transform=None, artifact=b"diagnostic-app", doc=None):
    doc = request_doc() if doc is None else doc
    accepted = c.post("/api/v1/builds", json=doc)
    build_id = accepted.json()["id"]
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    receipt = json.loads(result_receipt(doc, req_sha, artifact))
    if receipt_transform:
        receipt_transform(receipt)
    if isinstance(receipt, dict):
        encoded = json.dumps(receipt).encode()
    else:
        encoded = receipt
    adapter.succeed(build_id, artifact, encoded, TEST_ELF)
    return accepted


def test_success_verifies_exact_request_and_app_bytes():
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["artifact_sha256"] == hashlib.sha256(b"diagnostic-app").hexdigest()
    assert result["elf_sha256"] == hashlib.sha256(TEST_ELF).hexdigest()
    assert result["elf_bytes"] == len(TEST_ELF)
    assert result["app_budget_bytes"] == 1048576
    assert result["remaining_bytes"] == result["app_budget_bytes"] - len(b"diagnostic-app")
    assert result["installable"] is False
    assert result["hardware_tested"] is False


def test_shapes_receipt_binds_compressed_braids_bank_and_pool():
    c, adapter = client()
    doc = request_doc()
    doc["engines"].append("shapes")
    accepted = accept_and_succeed(c, adapter, doc=doc)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    receipt = json.loads(adapter.jobs[accepted.json()["id"]].result.receipt)
    assert [row["namespace"] for row in receipt["compressed_wave_tables"]] == ["braids"]
    assert receipt["instance_pool_bytes"] == 216064
    assert receipt["indexed_tft"] is True and receipt["shapes_voices"] == 12
    assert response.json()["result"]["installable"] is False


@pytest.mark.parametrize("fault", [
    "missing", "duplicate", "extra", "extra-field", "raw-size", "raw-hash", "packed-size",
    "indexed", "voices", "pool", "storage", "profile",
])
def test_service_refuses_wavetable_receipt_drift(fault):
    c, adapter = client()
    doc = request_doc()
    doc["engines"].append("shapes")

    def tamper(receipt):
        row = receipt["compressed_wave_tables"][0]
        if fault == "missing": receipt.pop("compressed_wave_tables")
        elif fault == "duplicate": receipt["compressed_wave_tables"].append(dict(row))
        elif fault == "extra": receipt["compressed_wave_tables"].append({**row, "namespace": "plaits"})
        elif fault == "extra-field": row["surprise"] = "unrecognized"
        elif fault == "raw-size": row["raw_bytes"] += 1
        elif fault == "raw-hash": row["raw_sha256"] = "b" * 64
        elif fault == "packed-size": row["packed_bytes"] = True
        elif fault == "indexed": receipt["indexed_tft"] = False
        elif fault == "voices": receipt["shapes_voices"] = True
        elif fault == "pool": receipt["instance_pool_bytes"] += 1
        elif fault == "storage": receipt["target_app_storage"]["pool_credit_bytes"] += 1
        elif fault == "profile": receipt["wavetable_profile"] = "caller-selected"
    accepted = accept_and_succeed(c, adapter, tamper, doc=doc)
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_one_project_receipt_requires_selector_bypass():
    c, adapter = client()
    doc = request_doc()
    doc["project_ids"] = ["song-one"]
    doc["startup_index"] = 0
    accepted = accept_and_succeed(c, adapter, doc=doc)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    receipt = json.loads(adapter.jobs[accepted.json()["id"]].result.receipt)
    assert receipt["runtime_hook_linked"] is False


def test_wrong_selector_hook_receipt_is_refused():
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, lambda d: d.update(runtime_hook_linked=False))
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_song_diagnostic_runtime_receipt_is_accepted():
    c, adapter = client()
    accepted = accept_and_succeed(
        c, adapter,
        lambda receipt: receipt.update(runtime_configuration=runtime_configuration("song-diagnostic")))
    assert c.get(accepted.json()["status_url"]).status_code == 200


@pytest.mark.parametrize("mutation", [
    lambda d: d.pop("runtime_configuration"),
    lambda d: d["runtime_configuration"].update(runtime_mode="continuous"),
    lambda d: d["runtime_configuration"].update(runtime_mode="song-diagnostic"),
    lambda d: d["runtime_configuration"].update(return_to_rom_seconds=120),
    lambda d: d["runtime_configuration"].update(return_to_rom_seconds=True),
    lambda d: d["runtime_configuration"].update(define="-DLUNAR_RETURN_TO_ROM_SECONDS=120"),
    lambda d: d["runtime_configuration"].update(release_accepted=True),
    lambda d: d["runtime_configuration"].update(extra="unexpected"),
    lambda d: d["runtime_configuration"].update(
        runtime_mode="song-diagnostic", return_to_rom_seconds=20,
        define="-DLUNAR_RETURN_TO_ROM_SECONDS=20"),
])
def test_service_rejects_noncanonical_runtime_receipt(mutation):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, mutation)
    assert c.get(accepted.json()["status_url"]).status_code == 502


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
    adapter.succeed(accepted.json()["id"], b"x" * (1048576 + 1), b"{}", TEST_ELF)
    assert c.get(accepted.json()["status_url"]).status_code == 502


@pytest.mark.parametrize("elf", [b"", b"x" * (16 * 1024 * 1024 + 1)])
def test_service_rejects_missing_or_oversized_elf(elf):
    c, adapter = client()
    accepted = c.post("/api/v1/builds", json=request_doc())
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    receipt = result_receipt(doc, req_sha, b"diagnostic-app", elf=TEST_ELF)
    adapter.succeed(accepted.json()["id"], b"diagnostic-app", receipt, elf)
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_service_rejects_elf_not_matching_receipt_digest():
    c, adapter = client()
    accepted = c.post("/api/v1/builds", json=request_doc())
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    receipt = result_receipt(doc, req_sha, b"diagnostic-app", elf=TEST_ELF)
    adapter.succeed(accepted.json()["id"], b"diagnostic-app", receipt, b"tampered-elf")
    assert c.get(accepted.json()["status_url"]).status_code == 502



def test_companion_set_requires_trusted_parent_startup_and_receipt_binding():
    c, adapter = client(set_parents=SETS)
    doc = request_doc()
    doc["project_ids"] = ["song-one", "song-two"]
    doc["startup_index"] = 0
    doc["set_ids"] = ["companion-one"]
    accepted = accept_and_succeed(c, adapter, doc=doc)
    assert accepted.status_code == 202
    assert c.get(accepted.json()["status_url"]).status_code == 200
    assert adapter.submissions[accepted.json()["id"]][0] == canonical_request(doc)

    c2, adapter2 = client(set_parents=SETS)
    wrong_parent = dict(doc, startup_index=1)
    assert c2.post("/api/v1/builds", json=wrong_parent).status_code == 422
    assert adapter2.jobs == {}

    c3, adapter3 = client(set_parents=SETS)
    unknown = dict(doc, set_ids=["unknown"])
    assert c3.post("/api/v1/builds", json=unknown).status_code == 422
    assert adapter3.jobs == {}

    c4, adapter4 = client(set_parents=SETS)
    rejected = accept_and_succeed(c4, adapter4,
        lambda receipt: receipt["set_parents"].update({"companion-one": "song-two"}), doc=doc)
    assert c4.get(rejected.json()["status_url"]).status_code == 502

    c5, adapter5 = client(set_parents=SETS)
    changed_identity = accept_and_succeed(
        c5, adapter5,
        lambda receipt: receipt["content"][1].update({"id": "different-set"}), doc=doc)
    assert c5.get(changed_identity.json()["status_url"]).status_code == 502


def test_default_request_encoding_is_unchanged_when_set_ids_are_omitted_or_empty():
    assert canonical_request(request_doc()) == canonical_request(dict(request_doc(), set_ids=[]))

def test_trusted_catalogue_loader_uses_make_ids_and_project_constants():
    modules, projects = load_trusted_catalogue()
    assert modules["macro"] == "sound"
    assert modules["plate"] == "audio_fx"
    assert "test-sine" not in modules
    assert "replacement-showcase-candidate-satellite-hearts" in projects
    assert len(projects) == 8
    modules, projects, sets = load_trusted_catalogue(include_sets=True)
    assert sets == {"replacement-showcase-event-horizon-companion-set":
                    "replacement-showcase-candidate-event-horizon"}


def test_rejects_over_budget_even_when_artifact_hash_matches():
    c, adapter = client()
    accepted = c.post("/api/v1/builds", json=request_doc())
    build_id = accepted.json()["id"]
    doc = request_doc()
    req_sha = hashlib.sha256(canonical_request(doc)).hexdigest()
    artifact = b"x" * 500
    receipt = json.loads(result_receipt(doc, req_sha, artifact))
    receipt["app_budget_bytes"] = len(artifact) - 1
    adapter.succeed(build_id, artifact, json.dumps(receipt).encode(), TEST_ELF)
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
    runtime = verification["runtime_configuration"]
    # The retained controller build is explicitly a 120-second song diagnostic.
    # Bind receipt construction to that reviewed mode instead of the default.
    assert runtime["runtime_mode"] == "song-diagnostic"
    assert runtime["return_to_rom_seconds"] == verification["probe_return_to_rom_seconds"] == 120
    receipt = checked_link_receipt(
        selection, prepared, verification, artifact, app_bytes, elf,
        runtime_mode=runtime["runtime_mode"], require_save_service=True)
    with pytest.raises(ValueError, match="runtime configuration mismatch"):
        checked_link_receipt(selection, prepared, verification, artifact,
                             app_bytes, elf, runtime_mode="diagnostic",
                             require_save_service=True)
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
    adapter.succeed(build_id, app_bytes, json.dumps(receipt).encode(), elf)
    response = client.get(accepted.json()["status_url"])
    assert response.status_code == 200, response.text
    assert response.json()["result"]["artifact_sha256"] == hashlib.sha256(app_bytes).hexdigest()

    mutations = [
        lambda item: item["module_selection"].update(selected=[]),
        lambda item: item.pop("state_bin_codec"),
        lambda item: item.update(startup_project_id="wrong-project"),
        lambda item: item.update(app_budget_bytes=len(app_bytes) - 1),
    ]
    for mutation_index, mutate in enumerate(mutations):
        rejected = client.post("/api/v1/builds", json=request)
        assert rejected.status_code == 202
        rejected_id = rejected.json()["id"]
        bad_receipt = json.loads(json.dumps(receipt))
        mutate(bad_receipt)
        adapter.succeed(rejected_id, app_bytes, json.dumps(bad_receipt).encode(), elf)
        assert client.get(rejected.json()["status_url"]).status_code == 502, f"mutation {mutation_index} unexpectedly accepted"

def test_docker_adapter_uses_fixed_container_contract_and_pinned_source(tmp_path, monkeypatch):
    import subprocess
    from tools.installer_service.docker_adapter import DockerJobAdapter, DockerWorkerConfig

    source = tmp_path / "source"
    toolchain = tmp_path / "toolchain"
    runtime = tmp_path / "runtime"
    catalogue = tmp_path / "catalogue"
    source.mkdir()
    toolchain.mkdir()
    runtime.mkdir()
    catalogue.mkdir()
    (source / "tracked.txt").write_text("tracked")
    worker_source = source / "tools/installer_service/docker_worker.py"
    worker_source.parent.mkdir(parents=True)
    worker_source.write_text("# pinned fixture worker\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt",
                    "tools/installer_service/docker_worker.py"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    config = DockerWorkerConfig(source, toolchain, runtime, commit, catalogue_root=catalogue)
    adapter = DockerJobAdapter(config)
    # The worker entrypoint must come from the pinned commit even if the live
    # checkout changes after configuration validation.
    worker_source.write_text("# changed live checkout\n")
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
    pinned_worker = subprocess.run(
        ["git", "-C", str(source), "show", commit + ":tools/installer_service/docker_worker.py"],
        check=True, capture_output=True).stdout
    assert (base / "input/docker_worker.py").read_bytes() == pinned_worker
    assert (base / "input/docker_worker.sha256").read_text().strip() == hashlib.sha256(pinned_worker).hexdigest()
    assert (base / "input/docker_worker.py").stat().st_mode & 0o777 == 0o400
    command = adapter._command(build_id, base)
    joined = " ".join(command)
    for option in ("--cgroup-parent=docker-batch.slice", "--network=none", "--cpus=4", "--memory=8g",
                   "--memory-swap=8g", "--pids-limit=512", "--read-only",
                   "--cap-drop=ALL", "--security-opt=no-new-privileges",
                   "--user 1001:1001"):
        assert option in joined
    assert config.image_reference in command
    assert "/output/build" not in joined
    assert "request.json" in joined and "source.tar" in joined
    assert "/input/docker_worker.py" in joined
    assert str(base / "input/docker_worker.py") in joined
    assert str(config.source_root / "tools/installer_service/docker_worker.py") not in joined
    assert str(config.catalogue_root) + ",dst=/input/catalogue,readonly" in joined
    adapter.delete(build_id)
    assert not base.exists()


def test_docker_adapter_rejects_mutable_source_and_unpinned_image(tmp_path):
    import subprocess
    from tools.installer_service.docker_adapter import DockerWorkerConfig

    source = tmp_path / "source"
    toolchain = tmp_path / "toolchain"
    runtime = tmp_path / "runtime"
    catalogue = tmp_path / "catalogue"
    source.mkdir()
    toolchain.mkdir()
    runtime.mkdir()
    catalogue.mkdir()
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
        DockerWorkerConfig(source, toolchain, runtime, commit, catalogue_root=catalogue)
    (source / "tracked.txt").write_text("tracked")
    with pytest.raises(ValueError, match="immutable image"):
        DockerWorkerConfig(source, toolchain, runtime, commit, catalogue_root=catalogue,
                           image_reference="lunar-recovery-pytest:latest")


def _docker_lifecycle_adapter(tmp_path):
    import subprocess
    from tools.installer_service.docker_adapter import DockerJobAdapter, DockerWorkerConfig

    source = tmp_path / "source"
    toolchain = tmp_path / "toolchain"
    runtime = tmp_path / "runtime"
    catalogue = tmp_path / "catalogue"
    for path in (source, toolchain, runtime, catalogue):
        path.mkdir()
    worker = source / "tools/installer_service/docker_worker.py"
    worker.parent.mkdir(parents=True)
    worker.write_text("# worker\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-qm", "fixture"], check=True)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            check=True, capture_output=True, text=True).stdout.strip()
    config = DockerWorkerConfig(source, toolchain, runtime, commit, catalogue_root=catalogue,
                                timeout_seconds=1)
    adapter = DockerJobAdapter(config, clock=lambda: 0)
    build_id = "B" * 32
    base = runtime / build_id
    (base / "input").mkdir(parents=True)
    (base / "result").mkdir()
    (base / "result/app.bin").write_bytes(b"app")
    (base / "result/elf.bin").write_bytes(TEST_ELF)
    (base / "result/image.json").write_bytes(b"{}")
    adapter.semaphore.acquire()
    adapter.job_dirs[build_id] = base
    adapter.jobs[build_id] = __import__(
        "tools.installer_service.api", fromlist=["WorkerSnapshot"]).WorkerSnapshot("queued")
    return adapter, build_id, base


class _FakeDockerClientProcess:
    def __init__(self, output=b"", initial_returncode=0, *, keep_pipe_open=False):
        import os
        import tempfile
        if keep_pipe_open:
            read_fd, self.writer_fd = os.pipe()
            self.stdout = os.fdopen(read_fd, "rb", buffering=0)
            if output:
                os.write(self.writer_fd, output)
        else:
            self.writer_fd = None
            self.stdout = tempfile.TemporaryFile()
            self.stdout.write(output)
            self.stdout.seek(0)
        self.returncode = initial_returncode
        self.killed = False
        self.waited = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        if self.returncode is None:
            self.returncode = -9

    def wait(self, timeout=None):
        self.waited = True
        if self.returncode is None:
            self.returncode = -9
        return self.returncode


def test_worker_binds_regular_app_and_elf_to_exact_receipt(tmp_path):
    from tools.installer_service import docker_worker

    build = tmp_path / "build"
    artifact_dir = build / "link/artifact"
    artifact_dir.mkdir(parents=True)
    app = b"diagnostic-app"
    elf = b"diagnostic-elf"
    (artifact_dir / "app.bin").write_bytes(app)
    (build / "link/lunar-app-probe.elf").write_bytes(elf)
    receipt_path = build / "image.json"

    def receipt_for(app_bytes, elf_bytes):
        return json.dumps({"app_sha256": hashlib.sha256(app_bytes).hexdigest(),
                           "elf_sha256": hashlib.sha256(elf_bytes).hexdigest()}).encode()

    receipt_path.write_bytes(receipt_for(app, elf))
    assert docker_worker.verified_build_outputs(build) == (app, elf, receipt_path.read_bytes())

    receipt_path.write_text('{"app_sha256":"' + hashlib.sha256(app).hexdigest()
                            + '","app_sha256":"' + hashlib.sha256(app).hexdigest()
                            + '","elf_sha256":"' + hashlib.sha256(elf).hexdigest() + '"}')
    with pytest.raises(ValueError, match="malformed"):
        docker_worker.verified_build_outputs(build)
    receipt_path.write_bytes(receipt_for(app, b"different-elf"))
    with pytest.raises(ValueError, match="does not match"):
        docker_worker.verified_build_outputs(build)
    (build / "link/lunar-app-probe.elf").unlink()
    with pytest.raises(ValueError, match="regular file"):
        docker_worker.verified_build_outputs(build)


def test_docker_adapter_retains_bounded_elf_and_rejects_bad_elf_outputs(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module
    from tools.installer_service.api import MAX_ELF_BYTES

    def run_case(root, bad=None):
        root.mkdir()
        adapter, build_id, base = _docker_lifecycle_adapter(root)
        path = base / "result/elf.bin"
        if bad == "missing":
            path.unlink()
        elif bad == "empty":
            path.write_bytes(b"")
        elif bad == "oversized":
            with path.open("wb") as handle:
                handle.truncate(MAX_ELF_BYTES + 1)
        elif bad == "symlink":
            path.unlink()
            target = base / "outside-elf"
            target.write_bytes(TEST_ELF)
            path.symlink_to(target)
        proc = _FakeDockerClientProcess(initial_returncode=0)
        with monkeypatch.context() as patch:
            patch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
            patch.setattr(module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
            adapter._run(build_id)
        return adapter.get(build_id)

    good = run_case(tmp_path / "good")
    assert good.status == "succeeded"
    assert good.result.elf == TEST_ELF
    for bad in ("missing", "empty", "oversized", "symlink"):
        failed = run_case(tmp_path / bad, bad)
        assert failed.status == "failed", bad


def test_docker_log_overflow_fails_even_if_client_exits_zero(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module

    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    adapter.config = __import__("dataclasses").replace(adapter.config, max_log_bytes=65536)
    proc = _FakeDockerClientProcess(b"x" * 65537, initial_returncode=0)
    cleanup = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: (
        cleanup.append(args) or SimpleNamespace(returncode=0)))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert proc.stdout.closed
    assert cleanup == [[adapter.config.docker_binary, "rm", "--force", "lunar-private-" + build_id]]
    assert (base / "worker.log").stat().st_size <= adapter.config.max_log_bytes


def test_docker_timeout_kills_client_and_removes_named_container_without_cidfile(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module

    adapter, build_id, base = _docker_lifecycle_adapter(tmp_path)
    proc = _FakeDockerClientProcess(initial_returncode=None)
    cleanup = []
    ticks = iter([10.0, 12.0])
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: (
        cleanup.append(args) or SimpleNamespace(returncode=0)))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert proc.killed and proc.waited
    assert not (base / "container.id").exists()
    assert cleanup == [[adapter.config.docker_binary, "rm", "--force", "lunar-private-" + build_id]]


def test_docker_pipe_drain_is_bounded_after_client_exit(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module

    adapter, build_id, _base = _docker_lifecycle_adapter(tmp_path)
    proc = _FakeDockerClientProcess(initial_returncode=0, keep_pipe_open=True)
    cleanup = []
    ticks = iter([10.0, 10.0, 10.0, 16.0])
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: (
        cleanup.append(args) or SimpleNamespace(returncode=0)))
    monkeypatch.setattr(module.select, "select", lambda *a, **k: ([], [], []))
    monkeypatch.setattr(module.time, "monotonic", lambda: next(ticks))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"
    assert proc.stdout.closed
    assert cleanup == [[adapter.config.docker_binary, "rm", "--force", "lunar-private-" + build_id]]
    __import__("os").close(proc.writer_fd)


def test_shutdown_kills_active_process_removes_named_container_and_drains(tmp_path, monkeypatch):
    import threading
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module
    from tools.installer_service.api import WorkerSnapshot

    adapter, build_id, _base = _docker_lifecycle_adapter(tmp_path)
    stopped = threading.Event()
    worker = threading.Thread(target=stopped.wait)
    worker.start()

    class ActiveProcess:
        returncode = None
        def poll(self): return self.returncode
        def kill(self):
            self.returncode = -9
            stopped.set()

    proc = ActiveProcess()
    adapter.threads[build_id] = worker
    adapter.processes[build_id] = proc
    adapter.jobs[build_id] = WorkerSnapshot("running")
    cleanup = []
    monkeypatch.setattr(module.subprocess, "run", lambda args, **kwargs: (
        cleanup.append(args) or SimpleNamespace(returncode=0)))
    adapter.shutdown(timeout_seconds=1)
    assert adapter.stopping
    assert proc.returncode == -9
    assert not worker.is_alive()
    assert cleanup == [[adapter.config.docker_binary, "rm", "--force", "lunar-private-" + build_id]]


def test_fastapi_lifespan_invokes_adapter_shutdown():
    class ShutdownAdapter(FakeJobAdapter):
        def __init__(self):
            super().__init__(1)
            self.did_shutdown = False
        def shutdown(self):
            self.did_shutdown = True

    adapter = ShutdownAdapter()
    app = __import__("tools.installer_service.api", fromlist=["create_app"]).create_app(
        adapter=adapter, template=TEMPLATE, module_kinds=MODULES, project_ids=PROJECTS)
    with TestClient(app):
        pass
    assert adapter.did_shutdown

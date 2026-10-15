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
                              SHAPES8_TABLES as BUILDER_SHAPES8_TABLES,
                              SHAPES8_WAVETABLE_PROFILE as BUILDER_SHAPES8_PROFILE,
                              SHAPES_VOICES as BUILDER_SHAPES_VOICES,
                              TARGET_STORAGE as BUILDER_TARGET_STORAGE,
                              WAVETABLE_PROFILE as BUILDER_WAVETABLE_PROFILE)
from tools.installer_service.api import (BASE_INSTANCE_POOL_BYTES, SHAPES_VOICES,
    SCHEMA2_PROFILE_ID, SCHEMA2_TUPLE_SCHEMA, SHAPES8_TABLES, SHAPES8_WAVETABLE_PROFILE,
    TARGET_STORAGE, WAVETABLES, WAVETABLE_PROFILE, FakeJobAdapter, WorkerTemplate,
    canonical_request, create_app)
from tools.installer_service.catalogue import load_trusted_catalogue
from tools.native.runtime_mode import runtime_configuration
from tools.native.flash_layout import app_budget

MODULES = {"sound-a": "sound", "macro": "sound", "shapes": "sound",
           "fx-a": "audio_fx", "midi-a": "midi_fx", "mod-a": "mod"}
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
    assert SHAPES8_WAVETABLE_PROFILE == BUILDER_SHAPES8_PROFILE
    assert SHAPES8_TABLES == BUILDER_SHAPES8_TABLES
    sys.path.insert(0, str(ROOT / "tools/jieli"))
    from trusted_fwsc_package import PROFILE_ID, TUPLE_SCHEMA
    assert SCHEMA2_PROFILE_ID == PROFILE_ID
    assert SCHEMA2_TUPLE_SCHEMA == TUPLE_SCHEMA


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


def d7000_request_doc():
    return {**request_doc(), "engines": ["macro", "shapes"],
            "flash_layout": "expanded-d7000", "runtime_mode": "song-diagnostic"}


def test_explicit_d7000_request_binds_layout_and_schema2_profile():
    doc = d7000_request_doc()
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, doc=doc)
    build_id = accepted.json()["id"]
    request_bytes, request_sha, _ = adapter.submissions[build_id]
    assert json.loads(request_bytes) == doc
    assert request_sha == hashlib.sha256(request_bytes).hexdigest()
    legacy_bytes = canonical_request(request_doc())
    assert b'"flash_layout"' not in legacy_bytes
    assert b'"runtime_mode"' not in legacy_bytes

    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    result = response.json()["result"]
    assert result["app_budget_bytes"] == app_budget("expanded-d7000") == 860644
    profile = result["provenance"]["profile"]
    assert profile == {"flash_layout": "expanded-d7000", "runtime_mode": "song-diagnostic",
                       "shapes_voices": 8, "tuple_schema": SCHEMA2_TUPLE_SCHEMA,
                       "profile_id": SCHEMA2_PROFILE_ID}
    assert result["provenance"]["trusted_fwsc_packager_compatible"] is False


@pytest.mark.parametrize("patch", [
    {"runtime_mode": "diagnostic"},
    {"engines": ["sound-a"]},
    {"flash_layout": "protected"},
])
def test_d7000_requires_explicit_schema2_runtime_and_fixed_modules(patch):
    doc = d7000_request_doc()
    doc.update(patch)
    c, adapter = client()
    assert c.post("/api/v1/builds", json=doc).status_code == 422
    assert adapter.jobs == {}


@pytest.mark.parametrize("mutation", [
    lambda receipt: receipt.update(flash_layout="expanded-d9000"),
    lambda receipt: receipt.update(app_budget_bytes=1048576),
    lambda receipt: receipt.update(app_budget_bytes=860645),
    lambda receipt: receipt.update(shapes_voices=12),
    lambda receipt: receipt.update(wavetable_profile="compressed-required-banks-flash-plaits-v1"),
    lambda receipt: receipt["compressed_wave_tables"][0].update(packed_sha256="0" * 64),
    lambda receipt: receipt["compressed_wave_tables"][0].update(width=True),
])
def test_d7000_result_rejects_layout_budget_or_profile_tampering(mutation):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, doc=d7000_request_doc())
    build_id = accepted.json()["id"]
    snapshot = adapter.jobs[build_id]
    result = snapshot.result
    receipt = json.loads(result.receipt)
    mutation(receipt)
    adapter.jobs[build_id] = type(snapshot)(snapshot.status, type(result)(
        result.artifact, json.dumps(receipt).encode(), result.elf, result.provenance))
    assert c.get(accepted.json()["status_url"]).status_code == 502


@pytest.mark.parametrize("mutation", [
    lambda envelope: envelope["profile"].update(tuple_schema=3),
    lambda envelope: envelope["profile"].update(profile_id="other-profile"),
    lambda envelope: envelope.update(trusted_fwsc_packager_compatible=True),
])
def test_d7000_provenance_cannot_claim_an_unanchored_schema2_tuple(mutation):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter, doc=d7000_request_doc())
    build_id = accepted.json()["id"]
    snapshot = adapter.jobs[build_id]
    result = snapshot.result
    envelope = json.loads(result.provenance)
    mutation(envelope)
    adapter.jobs[build_id] = type(snapshot)(snapshot.status, type(result)(
        result.artifact, result.receipt, result.elf,
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")))
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_d7000_result_must_fit_the_actual_named_layout_budget():
    c, adapter = client()
    oversized = b"x" * (app_budget("expanded-d7000") + 1)
    accepted = accept_and_succeed(c, adapter, artifact=oversized, doc=d7000_request_doc())
    assert c.get(accepted.json()["status_url"]).status_code == 502


def test_default_d9000_encoding_remains_legacy_and_worker_flags_are_fixed():
    from tools.installer_service.docker_worker import build_profile_arguments
    legacy_bytes = canonical_request(request_doc())
    assert b'"flash_layout"' not in legacy_bytes
    assert b'"runtime_mode"' not in legacy_bytes
    assert build_profile_arguments(request_doc()) == [
        "--flash-layout", "expanded-d9000", "--runtime-mode", "diagnostic",
        "--wavetable-profile", "compressed-required-banks-flash-plaits-v1"]
    assert build_profile_arguments(d7000_request_doc()) == [
        "--flash-layout", "expanded-d7000", "--runtime-mode", "song-diagnostic",
        "--wavetable-profile", SHAPES8_WAVETABLE_PROFILE,
        "--diagnostic-profile", "hall-o2-stage7-v1"]


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
    d7000 = doc.get("flash_layout") == "expanded-d7000"
    if d7000:
        wave_rows = [dict(row) for row in SHAPES8_TABLES]
    pool_bytes = 249088 - sum(row["raw_bytes"] for row in wave_rows)
    flash_layout = "expanded-d7000" if d7000 else "expanded-d9000"
    runtime_mode = doc.get("runtime_mode", "diagnostic")
    return json.dumps({
        "version": 1, "status": "linked-private-diagnostic",
        "flash_layout": flash_layout,
        "request_sha256": req_sha, "prepared_profile_sha256": prepared_sha,
        "project_ids": doc["project_ids"], "set_ids": set_ids,
        "set_parents": {set_id: "song-one" for set_id in set_ids},
        "selected_content": selected_content, "startup_index": doc["startup_index"],
        "startup_project_id": doc["project_ids"][doc["startup_index"]],
        "runtime_hook_linked": len(doc["project_ids"]) > 1,
        "runtime_configuration": runtime_configuration(runtime_mode),
        "module_selection": {"selected": selected},
        "wavetable_profile": SHAPES8_WAVETABLE_PROFILE if d7000 else "compressed-required-banks-flash-plaits-v1",
        "compressed_wave_tables": wave_rows, "indexed_tft": True,
        "flash_plaits_wavetables": not d7000, "shapes_voices": 8 if d7000 else 12,
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
        "app_bytes": len(artifact), "app_budget_bytes": app_budget(flash_layout) if d7000 else 1048576,
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
    build_id = accepted.json()["id"]
    snapshot = adapter.jobs[build_id]
    result = snapshot.result
    adapter.jobs[build_id] = type(snapshot)(snapshot.status, type(result)(
        result.artifact, result.receipt, result.elf, result.provenance,
        {"private/build_receipt.json": b"secret evidence"}))
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
    assert "private_evidence" not in result
    assert b"secret evidence" not in response.content


@pytest.mark.parametrize("mutation", ["request", "artifact", "image", "compatible", "installable"])
def test_service_rejects_stale_or_overstated_diagnostic_provenance(mutation):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter)
    build_id = accepted.json()["id"]
    snapshot = adapter.jobs[build_id]
    result = snapshot.result
    envelope = json.loads(result.provenance)
    if mutation == "request":
        envelope["bindings"]["request_sha256"] = "f" * 64
    elif mutation == "artifact":
        envelope["outputs"]["artifact_sha256"] = "f" * 64
    elif mutation == "image":
        envelope["bindings"]["worker_image_digest"] = "sha256:" + "f" * 64
    elif mutation == "compatible":
        envelope["trusted_fwsc_packager_compatible"] = True
    else:
        envelope["installable"] = True
    adapter.jobs[build_id] = type(snapshot)(snapshot.status, type(result)(
        result.artifact, result.receipt, result.elf,
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")))
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 502


def test_success_status_exposes_only_bounded_provenance_bindings():
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 200
    summary = response.json()["result"]["provenance"]
    assert summary["kind"] == "private-diagnostic-build-provenance"
    assert summary["source_tree_oid"] == "2" * 40
    assert summary["trusted_fwsc_packager_compatible"] is False
    assert set(summary) == {"sha256", "kind", "source_commit", "source_tree_oid",
                            "source_archive_sha256", "worker_sha256", "worker_image_digest",
                            "catalogue_manifest_sha256", "toolchain_manifest_sha256",
                            "request_sha256", "output_bindings", "profile",
                            "trusted_fwsc_packager_compatible"}
    assert "artifact" not in summary and "receipt" not in summary


@pytest.mark.parametrize("provenance", [b"", b" " * (65536 + 1)])
def test_service_rejects_empty_or_oversized_provenance_before_json_parse(provenance):
    c, adapter = client()
    accepted = accept_and_succeed(c, adapter)
    build_id = accepted.json()["id"]
    snapshot = adapter.jobs[build_id]
    result = snapshot.result
    adapter.jobs[build_id] = type(snapshot)(snapshot.status, type(result)(
        result.artifact, result.receipt, result.elf, provenance))
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 502


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


@pytest.mark.parametrize("receipt", [
    b'{"nested":' + b'[' * 10000 + b'0' + b']' * 10000 + b'}',
    b'{"duplicate":1,"duplicate":2}',
    b'{"invalid_utf8":"\xff"}',
])
def test_malformed_worker_receipt_is_a_controlled_refusal(receipt):
    c, adapter = client()
    accepted = c.post("/api/v1/builds", json=request_doc())
    assert len(receipt) < 65536
    adapter.succeed(accepted.json()["id"], b"diagnostic-app", receipt, TEST_ELF)
    response = c.get(accepted.json()["status_url"])
    assert response.status_code == 502
    assert response.json() == {"detail": "build result failed verification"}


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
    app_bytes = b"app"
    request_bytes = canonical_request(request_doc())
    request_sha = hashlib.sha256(request_bytes).hexdigest()
    receipt_object = json.loads(result_receipt(request_doc(), request_sha, app_bytes, TEST_ELF))
    cat_bytes, link_bytes = b"catalogue-object", b"link-object"
    (catalogue / "object.o").write_bytes(cat_bytes)
    catalogue_row = {"path": "/input/catalogue/object.o", "sha256": hashlib.sha256(cat_bytes).hexdigest()}
    linked_rows = [catalogue_row,
                   {"path": "/tmp/lunar-worker/output/build/link/object.o", "sha256": hashlib.sha256(link_bytes).hexdigest()}]
    build_receipt = json.dumps({"catalogue_objects": [catalogue_row], "linked_objects": linked_rows},
                               sort_keys=True, separators=(",", ":")).encode()
    artifact_receipt = json.dumps({"app_sha256": hashlib.sha256(app_bytes).hexdigest(),
                                   "app_bytes": len(app_bytes),
                                   "elf_sha256": hashlib.sha256(TEST_ELF).hexdigest()},
                                  sort_keys=True, separators=(",", ":")).encode()
    prepared_profile, source_profile = b'{"prepared":1}', b'{"source":1}'
    receipt_object.update({"verification_sha256": hashlib.sha256(build_receipt).hexdigest(),
                           "artifact_receipt_sha256": hashlib.sha256(artifact_receipt).hexdigest(),
                           "prepared_profile_sha256": hashlib.sha256(prepared_profile).hexdigest()})
    receipt = json.dumps(receipt_object).encode()
    (base / "input/request.json").write_bytes(request_bytes)
    archive_bytes = b"fixture source archive"
    (base / "input/source.tar").write_bytes(archive_bytes)
    pinned_worker = subprocess.run(
        ["git", "-C", str(source), "show", commit + ":tools/installer_service/docker_worker.py"],
        check=True, capture_output=True).stdout
    (base / "input/docker_worker.py").write_bytes(pinned_worker)
    from tools.installer_service.provenance import sha256 as prov_sha, tree_manifest
    catalogue_manifest = tree_manifest(catalogue)
    toolchain_manifest = tree_manifest(toolchain)
    (base / "input/catalogue-tree-manifest.json").write_bytes(catalogue_manifest)
    (base / "input/toolchain-tree-manifest.json").write_bytes(toolchain_manifest)
    bindings = {
        "schema": 1, "source_commit": commit, "source_tree_oid": config.source_tree_oid,
        "source_archive_sha256": prov_sha(archive_bytes),
        "worker_sha256": prov_sha(pinned_worker),
        "worker_image_digest": config.image_reference.split("@", 1)[1],
        "catalogue_manifest_sha256": prov_sha(catalogue_manifest),
        "toolchain_manifest_sha256": prov_sha(toolchain_manifest),
        "request_sha256": request_sha,
    }
    (base / "input/host-bindings.json").write_text(json.dumps(bindings), encoding="ascii")
    (base / "result/app.bin").write_bytes(app_bytes)
    (base / "result/elf.bin").write_bytes(TEST_ELF)
    (base / "result/image.json").write_bytes(receipt)
    contents = {
        "request.json": request_bytes, "prepared_profile.json": prepared_profile,
        "source_profile.json": source_profile, "artifact_receipt.json": artifact_receipt,
        "build_receipt.json": build_receipt, "image_receipt.json": receipt,
        "catalogue_manifest.json": json.dumps({"schema": 1, "objects": [catalogue_row]},
            sort_keys=True, separators=(",", ":")).encode(),
        "linked_objects.json": json.dumps({"schema": 1, "objects": linked_rows},
            sort_keys=True, separators=(",", ":")).encode(),
        "catalogue/object.o": cat_bytes, "linked/catalogue/object.o": cat_bytes,
        "linked/link/object.o": link_bytes,
    }
    from tools.installer_service.docker_worker import GENERATED_EVIDENCE_PATHS
    contents.update({"generated/" + path: b"generated:" + path.encode()
                     for path in GENERATED_EVIDENCE_PATHS})
    evidence_root = base / "result/evidence"
    manifest = {}
    for rel, content in contents.items():
        path = evidence_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest[rel] = {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()}
    (evidence_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="ascii")
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
    receipt_path.write_bytes(b'{"nested":' + b'[' * 10000 + b'0' + b']' * 10000 + b'}')
    with pytest.raises(ValueError, match="malformed"):
        docker_worker.verified_build_outputs(build)
    receipt_path.write_bytes(receipt_for(app, b"different-elf"))
    with pytest.raises(ValueError, match="does not match"):
        docker_worker.verified_build_outputs(build)
    (build / "link/lunar-app-probe.elf").unlink()
    with pytest.raises(ValueError, match="regular file"):
        docker_worker.verified_build_outputs(build)


def test_private_evidence_contract_checks_receipts_catalogue_and_linked_bytes(tmp_path):
    from tools.installer_service.docker_adapter import read_private_evidence
    from tools.installer_service.provenance import sha256

    result = tmp_path / "result"
    evidence_root = result / "evidence"
    catalogue_root = tmp_path / "catalogue"
    evidence_root.mkdir(parents=True)
    catalogue_root.mkdir()
    request = b'{"version":1}\n'
    cat = b"catalogue object"
    link = b"linked object"
    generated = b"generated header"
    (catalogue_root / "object.o").write_bytes(cat)
    catalogue_rows = [{"path": "/input/catalogue/object.o", "sha256": sha256(cat)}]
    linked_rows = catalogue_rows + [{"path": "/tmp/lunar-worker/output/build/link/object.o", "sha256": sha256(link)}]
    build = {"catalogue_objects": catalogue_rows, "linked_objects": linked_rows}
    build_raw = json.dumps(build, sort_keys=True, separators=(",", ":")).encode()
    artifact_raw = b'{"artifact":1}'
    prepared = b'{"profile_sha256":"unused"}'
    source = b'{"source":1}'
    image = {"request_sha256": sha256(request), "prepared_profile_sha256": sha256(prepared),
             "verification_sha256": sha256(build_raw), "artifact_receipt_sha256": sha256(artifact_raw)}
    image_raw = json.dumps(image, sort_keys=True, separators=(",", ":")).encode()
    contents = {
        "request.json": request, "prepared_profile.json": prepared,
        "source_profile.json": source, "artifact_receipt.json": artifact_raw,
        "build_receipt.json": build_raw, "image_receipt.json": image_raw,
        "catalogue_manifest.json": json.dumps({"schema": 1, "objects": catalogue_rows},
            sort_keys=True, separators=(",", ":")).encode(),
        "linked_objects.json": json.dumps({"schema": 1, "objects": linked_rows},
            sort_keys=True, separators=(",", ":")).encode(),
        "catalogue/object.o": cat, "linked/catalogue/object.o": cat,
        "linked/link/object.o": link,
    }
    from tools.installer_service.docker_worker import GENERATED_EVIDENCE_PATHS
    contents.update({"generated/" + path: generated + b":" + path.encode()
                     for path in GENERATED_EVIDENCE_PATHS})
    manifest = {}
    for rel, content in contents.items():
        path = evidence_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        manifest[rel] = {"bytes": len(content), "sha256": sha256(content)}
    (evidence_root / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="ascii")

    retained = read_private_evidence(result, request, image_raw, catalogue_root)
    assert retained == contents

    (evidence_root / "linked/link/object.o").write_bytes(b"altered")
    with pytest.raises(ValueError, match="manifest"):
        read_private_evidence(result, request, image_raw, catalogue_root)


def test_worker_retains_real_builder_namespace_and_receipt_order(tmp_path, monkeypatch):
    from tools.installer_service import docker_worker
    from tools.installer_service.docker_adapter import read_private_evidence
    from tools.installer_service.provenance import sha256

    catalogue = tmp_path / "catalogue"
    result = tmp_path / "result"
    build = tmp_path / "tmp/lunar-worker/output/build"
    catalogue.mkdir()
    result.mkdir()
    (build / "selection/prepared").mkdir(parents=True)
    (build / "selection/staged").mkdir(parents=True)
    (build / "link/artifact").mkdir(parents=True)
    request = b'{"version":1}\n'
    prepared, source = b'{"prepared":true}', b'{"source":true}'
    app, elf = b"private app", b"private ELF"
    (build / "selection/prepared/profile.json").write_bytes(prepared)
    (build / "selection/staged/profile.json").write_bytes(source)
    (build / "link/artifact/app.bin").write_bytes(app)
    (build / "link/lunar-app-probe.elf").write_bytes(elf)
    artifact = b'{"artifact":true}'
    (build / "link/artifact/artifact.json").write_bytes(artifact)

    # Receipt order mirrors checked_catalogue's index order and the linker's
    # object traversal. It is intentionally not lexicographically sorted.
    cat_items = [("z-last.o", b"catalogue-z"), ("a-first.o", b"catalogue-a")]
    catalogue_rows = []
    linked_rows = []
    for name, content in cat_items:
        (catalogue / name).write_bytes(content)
        row = {"path": "/input/catalogue/" + name, "sha256": sha256(content),
               "optimization": "-Oz"}
        catalogue_rows.append(row)
        linked_rows.append({"path": row["path"], "sha256": row["sha256"]})
    link_items = [("z-linked.o", b"linked-z"), ("a-linked.o", b"linked-a")]
    for name, content in link_items:
        (build / "link" / name).write_bytes(content)
        linked_rows.append({"path": "/tmp/lunar-worker/output/build/link/" + name,
                            "sha256": sha256(content)})
    for rel in docker_worker.GENERATED_EVIDENCE_PATHS:
        path = build / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("generated:" + rel).encode())
    build_receipt = json.dumps({"catalogue_objects": catalogue_rows,
                                "linked_objects": linked_rows}, separators=(",", ":")).encode()
    (build / "link/verification.json").write_bytes(build_receipt)
    image = {"request_sha256": sha256(request),
             "prepared_profile_sha256": sha256(prepared),
             "verification_sha256": sha256(build_receipt),
             "artifact_receipt_sha256": sha256(artifact),
             "app_sha256": sha256(app), "elf_sha256": sha256(elf)}
    image_raw = json.dumps(image, separators=(",", ":")).encode()
    (build / "image.json").write_bytes(image_raw)

    monkeypatch.setattr(docker_worker, "CATALOGUE", catalogue)
    monkeypatch.setattr(docker_worker, "RESULT", result)
    docker_worker.retain_private_evidence(build, request)
    retained = read_private_evidence(result, request, image_raw, catalogue)
    assert json.loads(retained["catalogue_manifest.json"])["objects"] == catalogue_rows
    assert json.loads(retained["linked_objects.json"])["objects"] == linked_rows
    assert set(path.removeprefix("generated/") for path in retained
               if path.startswith("generated/")) == set(docker_worker.GENERATED_EVIDENCE_PATHS)


@pytest.mark.parametrize("raw", ["a//b", "a/./b", "a/../b", "a\\b"])
def test_private_evidence_rejects_noncanonical_manifest_aliases(tmp_path, raw):
    from tools.installer_service.docker_adapter import read_private_evidence

    root = tmp_path / "result/evidence"
    root.mkdir(parents=True)
    (root / "payload").write_bytes(b"x")
    manifest = {raw: {"bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="ascii")
    with pytest.raises(ValueError, match="canonical"):
        read_private_evidence(root.parent, b"", b"", tmp_path)


def test_private_evidence_aggregate_manifest_cap_precedes_file_reads(tmp_path, monkeypatch):
    from tools.installer_service.docker_adapter import read_private_evidence, _MAX_PRIVATE_EVIDENCE_FILE

    root = tmp_path / "result/evidence"
    root.mkdir(parents=True)
    row = {"bytes": _MAX_PRIVATE_EVIDENCE_FILE, "sha256": "0" * 64}
    manifest = {"payload-%d.bin" % i: row for i in range(5)}
    for name in manifest:
        with (root / name).open("wb") as stream:
            stream.truncate(_MAX_PRIVATE_EVIDENCE_FILE)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="ascii")
    original = Path.read_bytes
    reads = []

    def tracked_read(path):
        if path.parent == root and path.name != "manifest.json":
            reads.append(path.name)
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", tracked_read)
    with pytest.raises(ValueError, match="aggregate cap"):
        read_private_evidence(root.parent, b"", b"", tmp_path)
    assert reads == []


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


def test_docker_adapter_rejects_catalogue_changed_after_submission(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from tools.installer_service import docker_adapter as module

    adapter, build_id, _base = _docker_lifecycle_adapter(tmp_path)
    (adapter.config.catalogue_root / "late-object.o").write_bytes(b"changed after pin")
    proc = _FakeDockerClientProcess(initial_returncode=0)
    monkeypatch.setattr(module.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    adapter._run(build_id)
    assert adapter.get(build_id).status == "failed"


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

# SPDX-License-Identifier: MIT
"""Selected continuous service contract: no admission or artifact-byte route."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tools.installer_service import continuous_profile as policy
from tools.installer_service.api import (BuildRequest, FakeJobAdapter, WorkerResult,
    WorkerSnapshot, canonical_request, create_app)
from tools.installer_service.catalogue import load_trusted_catalogue
from tools.installer_service.docker_worker import build_profile_arguments
from test_installer_service import TEMPLATE, TEST_ELF, result_receipt
from tools.native.build_demo_image import (BASE_INSTANCE_POOL_BYTES, CONTINUOUS_TARGET_STORAGE,
    SHAPES8_TABLES, native_midi_input_configuration)
from tools.native.module_selection import wavetable_namespaces


@pytest.fixture(scope="module")
def kinds():
    return load_trusted_catalogue()[0]


def request_doc(engines=("trio",)):
    return dict(version=1, engines=list(engines), effects=[], midi=[], modulation=[],
                project_ids=["song-one", "song-two"], startup_index=0,
                flash_layout="expanded-d7000", runtime_mode="continuous")


def receipt(doc, app=b"continuous-app"):
    value = json.loads(result_receipt(doc, hashlib.sha256(canonical_request(doc)).hexdigest(), app))
    selected = value["module_selection"]["selected"]
    value.update(policy._helpers()[0].continuous_link_configuration())
    value["status"] = "linked-private-continuous"
    value["firmware_identity"] = policy._helpers()[1]("FM-1_500")
    value["native_midi_input"] = native_midi_input_configuration(True)
    value["compressed_wave_tables"] = [dict(row) for row in SHAPES8_TABLES
        if row["namespace"] in wavetable_namespaces(selected)]
    value["instance_pool_bytes"] = BASE_INSTANCE_POOL_BYTES + CONTINUOUS_TARGET_STORAGE["pool_credit_bytes"] - sum(
        row["raw_bytes"] for row in value["compressed_wave_tables"])
    return value


def prepared_profile_bytes(doc, outer):
    identities = ([('project', project, f'projects/{project}.lunar')
                   for project in doc['project_ids']]
                  + [('set', set_id, f'sets/{set_id}.movy1')
                     for set_id in doc.get('set_ids', [])])
    rows = []
    for index, ((kind, _identity, source), measured) in enumerate(
            zip(identities, outer['content'])):
        rows.append({"kind": kind, "source": source,
                     "packed": f"content-{index:02d}.bin",
                     "bytes": measured["bytes"],
                     "packed_sha256": measured["packed_sha256"]})
    return json.dumps({"content": rows, "installable": False,
                       "hardware_tested": False},
                      sort_keys=True, separators=(",", ":")).encode()


def api_evidence(doc, outer, app=b"continuous-app", elf=TEST_ELF):
    """Small complete-shaped fake payload for the API boundary (adapter tests use disk evidence)."""
    from tools.installer_service.docker_worker import generated_evidence_paths
    request = canonical_request(doc)
    prepared = prepared_profile_bytes(doc, outer)
    source = b'{"source":true}'
    selected = outer["module_selection"]["selected"]
    linked = [{"path": "/tmp/lunar-worker/output/build/link/" + name,
               "sha256": hashlib.sha256(name.encode()).hexdigest()}
              for name in ("midi_uart_stream.o", "midi_stream.o")]
    lower = deepcopy(outer)
    # The actual capture schema keeps request/app-byte bindings in the outer
    # image and artifact receipt. Its lower link receipt carries ELF SHA but
    # has no request_sha256/app_sha256/app_bytes/elf_bytes fields.
    lower.pop("request_sha256", None)
    lower.pop("app_sha256", None)
    lower.pop("app_bytes", None)
    lower.pop("elf_bytes", None)
    lower.update(elf_sha256=hashlib.sha256(elf).hexdigest(),
                 flash_write_range="empty", boot_ota_cleanup=False,
                 hardware_candidate=False, catalogue_source_freshness_verified=True,
                 catalogue_objects=[], linked_objects=linked)
    artifact_receipt = json.dumps({"app_sha256": hashlib.sha256(app).hexdigest(),
                                   "app_bytes": len(app),
                                   "elf_sha256": lower["elf_sha256"],
                                   "flash_layout": lower["flash_layout"],
                                   "app_budget_bytes": lower["app_budget_bytes"],
                                   "layout_passed": True},
                                  sort_keys=True, separators=(",", ":")).encode()
    lower_raw = json.dumps(lower, sort_keys=True, separators=(",", ":")).encode()
    outer = deepcopy(outer)
    outer["prepared_profile_sha256"] = hashlib.sha256(prepared).hexdigest()
    outer["verification_sha256"] = hashlib.sha256(lower_raw).hexdigest()
    outer["artifact_receipt_sha256"] = hashlib.sha256(artifact_receipt).hexdigest()
    outer["embedded_content"]["prepared_sha256"] = outer["prepared_profile_sha256"]
    outer.pop("flash_layout", None)
    # Captured image.json reports content measurements separately from the
    # ordered selected_content identity list; IDs are absent from these rows.
    for row in outer["content"] + outer["embedded_content"]["assets"]:
        row.pop("id", None)
        row.pop("parent_project_id", None)
    image_raw = json.dumps(outer, sort_keys=True, separators=(",", ":")).encode()
    evidence = {
        "request.json": request,
        "prepared_profile.json": prepared,
        "source_profile.json": source,
        "artifact_receipt.json": artifact_receipt,
        "build_receipt.json": lower_raw,
        "image_receipt.json": image_raw,
        "catalogue_manifest.json": b'{"objects":[],"schema":1}',
        "linked_objects.json": json.dumps({"schema": 1, "objects": linked},
                                           sort_keys=True, separators=(",", ":")).encode(),
    }
    evidence["native_profile.json"] = policy.evidence_manifest(lower_raw)
    for path in generated_evidence_paths(lower):
        evidence["generated/" + path] = ("generated:" + path).encode()
    return image_raw, evidence


def service(kinds):
    adapter = FakeJobAdapter(1)
    return TestClient(create_app(adapter=adapter, template=TEMPLATE, module_kinds=kinds,
        project_ids={"song-one", "song-two"}, set_parents={"companion-one": "song-one"})), adapter


def succeed(client, adapter, doc, mutate=None):
    accepted = client.post("/api/v1/builds", json=doc)
    assert accepted.status_code == 202
    value = receipt(doc)
    if mutate:
        mutate(value)
    raw, evidence = api_evidence(doc, value)
    adapter.succeed(accepted.json()["id"], b"continuous-app", raw, TEST_ELF,
                    private_evidence=evidence)
    return accepted.json()


@pytest.mark.parametrize("engines,expected", [
    (["trio"], []), (["macro"], ["plaits"]), (["shapes"], ["braids"]),
    (["macro", "shapes"], ["plaits", "braids"]),
])
def test_continuous_service_accepts_exact_selected_banks_and_measures_only_that_link(kinds, engines, expected):
    c, adapter = service(kinds)
    doc = request_doc(engines)
    accepted = succeed(c, adapter, doc)
    assert c.get(accepted["status_url"]).status_code == 200
    body = c.get(accepted["status_url"]).json()
    assert body["kind"] == "private-continuous-build"
    result = body["result"]
    assert result["status"] == "linked-private-continuous"
    assert result["app_budget_bytes"] == 860644
    assert result["remaining_bytes"] == 860644 - len(b"continuous-app")
    assert result["provenance"]["profile"] == policy.profile_summary()
    assert result["provenance"]["kind"] == policy.PROVENANCE_KIND
    assert result["provenance"]["trusted_fwsc_packager_compatible"] is False
    assert all(result[key] is False for key in ("installable", "hardware_tested", "hardware_admitted",
        "native_ram_verified", "native_playback_verified", "full_song_default_accepted"))
    value = receipt(doc)
    assert [row["namespace"] for row in value["compressed_wave_tables"]] == expected
    assert result["instance_pool_bytes"] == value["instance_pool_bytes"]
    assert "artifact" not in result and "private_evidence" not in result
    assert c.get(accepted["status_url"] + "/download").status_code == 404


def test_all_production_groups_are_selectable_without_test_modules(kinds):
    assert len(kinds) == 55
    doc = request_doc()
    for group, kind in zip(("engines", "effects", "midi", "modulation"), ("sound", "audio_fx", "midi_fx", "mod")):
        doc[group] = [name for name, actual in kinds.items() if actual == kind]
    assert len(doc["engines"]) == 13
    c, adapter = service(kinds)
    accepted = succeed(c, adapter, doc)
    assert c.get(accepted["status_url"]).status_code == 200
    assert json.loads(adapter.submissions[accepted["id"]][0]) == doc
    assert not any(name.startswith("test-") for name in kinds)


def test_continuous_api_refuses_missing_private_evidence(kinds):
    c, adapter = service(kinds)
    doc = request_doc()
    accepted = c.post("/api/v1/builds", json=doc).json()
    image, evidence = api_evidence(doc, receipt(doc))
    adapter.succeed(accepted["id"], b"continuous-app", image, TEST_ELF)
    assert c.get(accepted["status_url"]).status_code == 502


def test_continuous_api_binds_lower_receipt_digest(kinds):
    c, adapter = service(kinds)
    doc = request_doc()
    accepted = c.post("/api/v1/builds", json=doc).json()
    image, evidence = api_evidence(doc, receipt(doc))
    evidence["build_receipt.json"] += b" "
    adapter.succeed(accepted["id"], b"continuous-app", image, TEST_ELF,
                    private_evidence=evidence)
    assert c.get(accepted["status_url"]).status_code == 502


@pytest.mark.parametrize("patch", [
    {"flash_layout": "expanded-d9000"}, {"runtime_mode": "continuous", "firmware_identity": "FM-1_501"},
    {"engines": ["test-dummy"]}, {"engines": ["hall"]}, {"engines": ["trio", "trio"]},
    {"engines": []}, {"effects": ["trio"]}, {"startup_index": True}, {"version": True},
    {"return_to_rom_seconds": 0}, {"toolchain": "/private/host"}, {"profile_id": policy.PROFILE_ID},
    {"set_ids": ["companion-one"], "startup_index": 1},
])
def test_request_rejects_tampering_before_adapter_submit(kinds, patch):
    c, adapter = service(kinds)
    response = c.post("/api/v1/builds", json={**request_doc(), **patch})
    assert response.status_code == 422
    assert not adapter.submissions


@pytest.mark.parametrize("path,value", [
    (("status",), "linked-private-diagnostic"),
    (("runtime_configuration", "return_to_rom_seconds"), 0),
    (("runtime_configuration", "define"), "-DLUNAR_RETURN_TO_ROM_SECONDS=120"),
    (("runtime_configuration", "release_accepted"), 0),
    (("firmware_identity", "application_identity"), "FM-1_501"),
    (("firmware_identity", "explicit"), 1),
    (("firmware_identity", "recovery_identity"), "FM-1_092"),
    (("native_midi_input", "enabled"), False),
    (("native_midi_input", "ring_bytes"), 255),
    (("native_midi_input", "bytes_per_poll"), True),
    (("native_midi_input", "usb_midi_preserved"), False),
    (("project_save_service", "save_service_armed"), True),
    (("diagnostic_telemetry", "enabled"), True),
    (("diagnostic_telemetry", "compile_definition"), "LUNAR_DIAGNOSTIC_TELEMETRY=1"),
    (("diagnostic_song_play", "start_ms"), 2000),
    (("diagnostic_trio_pulse", "enabled"), True),
    (("render_stage_profile",), {"enabled": True, "schema": 2}),
    (("probe_return_to_rom_seconds",), 120),
    (("catalogue_hall_o2",), True),
    (("hot_dsp_ram", "enabled"), True),
    (("installable",), True), (("hardware_admitted",), True),
    (("native_playback_verified",), True), (("app_bytes",), True),
    (("app_budget_bytes",), 860645), (("instance_pool_bytes",), 249087),
    (("compressed_wave_tables",), [dict(row) for row in SHAPES8_TABLES]),
])
def test_response_rejects_runtime_identity_midi_storage_and_admission_tampering(kinds, path, value):
    def mutate(doc):
        owner = doc
        for key in path[:-1]:
            owner = owner[key]
        owner[path[-1]] = value
    c, adapter = service(kinds)
    accepted = succeed(c, adapter, request_doc(), mutate)
    assert c.get(accepted["status_url"]).status_code == 502


@pytest.mark.parametrize("path,value", [
    (("kind",), "private-diagnostic-build-provenance"),
    (("profile", "profile_id"), "fm1-092-d7000"),
    (("profile", "profile_sha256"), "f" * 64),
    (("bindings", "request_sha256"), "f" * 64),
    (("bindings", "worker_image_digest"), "sha256:" + "f" * 64),
    (("bindings", "source_commit"), "invalid"),
    (("bindings", "source_archive_sha256"), True),
    (("bindings", "catalogue_manifest_sha256"), "invalid"),
    (("bindings", "toolchain_manifest_sha256"), "invalid"),
    (("outputs", "elf_sha256"), "f" * 64),
    (("outputs", "image_receipt_sha256"), "f" * 64),
    (("outputs", "verification_sha256"), "f" * 64),
    (("trusted_fwsc_packager_compatible",), True),
])
def test_continuous_provenance_is_distinct_and_bound(kinds, path, value):
    c, adapter = service(kinds)
    accepted = succeed(c, adapter, request_doc())
    result = adapter.jobs[accepted["id"]].result
    provenance = json.loads(result.provenance)
    owner = provenance
    for key in path[:-1]:
        owner = owner[key]
    owner[path[-1]] = value
    adapter.jobs[accepted["id"]] = WorkerSnapshot("succeeded", WorkerResult(
        result.artifact, result.receipt, result.elf, json.dumps(provenance).encode(),
        result.private_evidence))
    assert c.get(accepted["status_url"]).status_code == 502


def test_worker_fixed_arguments_and_extracted_production_preflight(kinds):
    from tools.installer_service.docker_worker import verify_extracted_profile_contract
    root = Path(__file__).resolve().parents[1]
    doc = request_doc()
    doc["project_ids"] = ["replacement-showcase-candidate-event-horizon"]
    assert build_profile_arguments(doc) == list(policy.BUILD_ARGUMENTS)
    assert "--diagnostic-profile" not in build_profile_arguments(doc)
    assert build_profile_arguments(doc)[-2:] == ["--firmware-identity", "FM-1_500"]
    verify_extracted_profile_contract(root, doc)
    with pytest.raises(ValueError, match="catalogue groups"):
        verify_extracted_profile_contract(root, {**doc, "engines": ["test-bad"]})
    with pytest.raises(ValueError, match="catalogue groups"):
        policy.validate_request({**doc, "engines": ["hall"]}, kinds, set(doc["project_ids"]), {})
    with pytest.raises(ValueError, match="malformed"):
        policy.validate_request({**doc, "toolchain": "/tmp"}, kinds, set(doc["project_ids"]), {})


@pytest.mark.parametrize("name", ["tools.installer_service.continuous_profile", "tools.installer_service.catalogue"])
def test_worker_rejects_preloaded_module_from_another_archive(monkeypatch, tmp_path, name):
    import sys
    from types import ModuleType
    from tools.installer_service.docker_worker import verify_extracted_profile_contract
    wrong = ModuleType(name)
    wrong.__file__ = str(tmp_path / "untrusted.py")
    monkeypatch.setitem(sys.modules, name, wrong)
    with pytest.raises(ValueError, match="not loaded from the extracted pinned source"):
        verify_extracted_profile_contract(Path(__file__).resolve().parents[1], request_doc())


@pytest.mark.parametrize("engines", [["trio"], ["macro"], ["shapes"], ["macro", "shapes"]])
def test_selected_request_worker_retention_evidence_and_api_roundtrip(tmp_path, monkeypatch, kinds, engines):
    from tools.installer_service import docker_worker
    from tools.installer_service.docker_adapter import read_private_evidence
    from tools.native.prepare_wavetables import prepare
    doc = request_doc(engines)
    request = canonical_request(doc)
    assert docker_worker.build_profile_arguments(doc) == list(policy.BUILD_ARGUMENTS)
    policy.validate_request(doc, kinds, set(doc["project_ids"]), {})
    catalogue, result, build = (tmp_path / part for part in ("catalogue", "result", "build"))
    catalogue.mkdir()
    result.mkdir()
    for rel in ("selection/prepared", "selection/staged", "link/artifact"):
        (build / rel).mkdir(parents=True)
    image = receipt(doc)
    prepared, source = prepared_profile_bytes(doc, image), b'{"source":true}'
    (build / "selection/prepared/profile.json").write_bytes(prepared)
    (build / "selection/staged/profile.json").write_bytes(source)
    artifact = json.dumps({"app_sha256": hashlib.sha256(b"continuous-app").hexdigest(),
                           "elf_sha256": hashlib.sha256(TEST_ELF).hexdigest(),
                           "app_bytes": len(b"continuous-app"),
                           "flash_layout": "expanded-d7000",
                           "app_budget_bytes": 860644,
                           "layout_passed": True},
                          sort_keys=True, separators=(",", ":")).encode()
    (build / "link/artifact/artifact.json").write_bytes(artifact)
    lower = deepcopy(image)
    lower.update(flash_write_range="empty", boot_ota_cleanup=False, hardware_candidate=False,
                 catalogue_source_freshness_verified=True)
    catalogue_rows, linked_rows = [], []
    for name in ("selected-engine.o",):
        content = ("catalogue:" + name).encode()
        (catalogue / name).write_bytes(content)
        row = dict(path=docker_worker.CATALOGUE_MOUNT + name, sha256=hashlib.sha256(content).hexdigest())
        catalogue_rows.append(dict(row, optimization="-Oz"))
        linked_rows.append(row)
    for name in ("midi_uart_stream.o", "midi_stream.o"):
        content = ("linked:" + name).encode()
        (build / "link" / name).write_bytes(content)
        linked_rows.append(dict(path=docker_worker.BUILD_LINK_MOUNT + name,
                                sha256=hashlib.sha256(content).hexdigest()))
    lower.update(catalogue_objects=catalogue_rows, linked_objects=linked_rows)
    lower.update(app_sha256=hashlib.sha256(b"continuous-app").hexdigest(),
                 app_bytes=len(b"continuous-app"),
                 elf_sha256=hashlib.sha256(TEST_ELF).hexdigest(), elf_bytes=len(TEST_ELF),
                 request_sha256=hashlib.sha256(request).hexdigest())
    lower_raw = json.dumps(lower).encode()
    (build / "link/verification.json").write_bytes(lower_raw)
    image.update(prepared_profile_sha256=hashlib.sha256(prepared).hexdigest(),
                 verification_sha256=hashlib.sha256(lower_raw).hexdigest(),
                 artifact_receipt_sha256=hashlib.sha256(artifact).hexdigest())
    image["embedded_content"]["prepared_sha256"] = image["prepared_profile_sha256"]
    image.pop("flash_layout")  # actual outer image.json omits this lower-link field
    image_raw = json.dumps(image).encode()
    (build / "image.json").write_bytes(image_raw)
    # Exercise the actual source generator; empty, one-bank and two-bank
    # selections must retain their exact namespace inventory.
    records = prepare(build / "link", namespaces=wavetable_namespaces(engines))
    assert records == image["compressed_wave_tables"]
    for rel in docker_worker.generated_evidence_paths(lower):
        path = build / rel
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("generated:" + rel).encode())
    monkeypatch.setattr(docker_worker, "CATALOGUE", catalogue)
    monkeypatch.setattr(docker_worker, "RESULT", result)
    docker_worker.retain_private_evidence(build, request)
    retained = read_private_evidence(result, request, image_raw, catalogue)
    assert retained["native_profile.json"] == policy.evidence_manifest(lower_raw)
    assert {key for key in retained if key.startswith("generated/link/resources_")} == {
        "generated/link/resources_" + namespace + extension
        for namespace in wavetable_namespaces(engines) for extension in (".cc", ".h")}
    c, adapter = service(kinds)
    accepted = c.post("/api/v1/builds", json=doc).json()
    adapter.succeed(accepted["id"], b"continuous-app", image_raw, TEST_ELF,
                    private_evidence=retained)
    assert c.get(accepted["status_url"]).status_code == 200
    # Re-hashing a forged lower receipt cannot change the fixed profile policy.
    lower["render_stage_profile"] = {"enabled": True, "schema": 2}
    with pytest.raises(ValueError, match="instrumentation/policy"):
        policy.validate_receipt(lower)
    profile_path = result / "evidence/native_profile.json"
    profile_path.write_bytes(profile_path.read_bytes().replace(policy.profile_sha256().encode(), b"f" * 64))
    with pytest.raises(ValueError, match="manifest"):
        read_private_evidence(result, request, image_raw, catalogue)


def test_browser_continuous_contract_digest_matches_server_policy():
    source = (Path(__file__).resolve().parents[1] / "sim/web/www/native-build-selection.js").read_text()
    assert "profileId: '" + policy.PROFILE_ID + "'" in source
    assert "profileSha256: '" + policy.profile_sha256() + "'" in source

# SPDX-License-Identifier: MIT
"""The private adapter only packages an exact trusted-wrapper result."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from tools.installer_service import private_package_candidate as adapter
from tools.installer_service.api import WorkerResult, canonical_request
from tools.jieli.trusted_fwsc_package import HASH_FIELDS, TUPLE_KEYS


def _write(path: Path, raw: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def _trusted_output(output: Path, catalogue_root: Path, request: bytes, source_commit: str,
                    app: bytes, elf: bytes):
    build = output / "build"
    generated = b"generated-input"
    catalogue = b"catalogue-object"
    files = {
        "selection/request.json": request,
        "selection/prepared/profile.json": b"prepared-profile",
        "selection/staged/profile.json": b"source-profile",
        "link/artifact/artifact.json": b"artifact-receipt",
        "link/verification.json": b"build-receipt",
        "image.json": b"image-receipt",
        "link/artifact/app.bin": app,
        "link/lunar-app-probe.elf": elf,
        "link/generated.cc": generated,
    }
    for relative, raw in files.items():
        _write(build / relative, raw)
    catalogue_path = catalogue_root / "object.o"
    _write(catalogue_path, catalogue)
    catalogue_manifest = {"schema": 1, "objects": [{
        "path": "/catalogue/object.o", "sha256": hashlib.sha256(catalogue).hexdigest()}]}
    catalogue_raw = json.dumps(catalogue_manifest, sort_keys=True, separators=(",", ":")).encode()
    _write(build / "catalogue-manifest.json", catalogue_raw)
    provenance = {"source_commit": source_commit,
                  "module_and_generated_inputs": [{
        "path": "link/generated.cc", "sha256": hashlib.sha256(generated).hexdigest()}]}
    provenance_raw = json.dumps(provenance, sort_keys=True, separators=(",", ":")).encode()
    _write(build / "build-provenance.json", provenance_raw)
    tuple_value = {key: "e" * 64 for key in HASH_FIELDS}
    tuple_value.update({"schema": 2, "profile_id": "fm1-092-d7000",
                        "flash_layout": "expanded-d7000", "app_bytes": len(app),
                        "application_identity": "FM-1_500", "recovery_identity": "FM-1_000",
                        "runtime_mode": "continuous", "hardware_admitted": False,
                        "hardware_tested": False, "installable": False,
                        "tuple_id": "continuous-test-shape"})
    tuple_value.update(catalogue_sha256=hashlib.sha256(catalogue_raw).hexdigest(),
                       source_tree_sha256="d" * 64,
                       request_sha256=hashlib.sha256(request).hexdigest(),
                       app_sha256=hashlib.sha256(app).hexdigest(),
                       elf_sha256=hashlib.sha256(elf).hexdigest(),
                       build_provenance_sha256=hashlib.sha256(provenance_raw).hexdigest())
    assert set(tuple_value) == TUPLE_KEYS and "source_commit" not in tuple_value
    tuple_raw = json.dumps(tuple_value,
                           sort_keys=True, separators=(",", ":")).encode()
    _write(build / "build_tuple.json", tuple_raw)
    capture = {"tuple_sha256": hashlib.sha256(tuple_raw).hexdigest(),
               "provenance_sha256": hashlib.sha256(provenance_raw).hexdigest(),
               "catalogue_sha256": hashlib.sha256(catalogue_raw).hexdigest(),
               "source_tree_sha256": "d" * 64,
               "schema": 1,
               "source_commit": source_commit,
               "hardware_admitted": False, "hardware_tested": False,
               "installable": False}
    _write(build / "tuple-capture.json", json.dumps(capture).encode())


def _request():
    return canonical_request({
        "version": 1, "engines": ["trio"], "effects": [], "midi": [],
        "modulation": [], "project_ids": ["song-one"], "startup_index": 0,
        "flash_layout": "expanded-d7000", "runtime_mode": "continuous",
    })


def _minimal_preview(app=b"preview-app", elf=b"preview-elf"):
    return WorkerResult(app, b"service-receipt", elf, b"service-provenance", {"evidence": b"bytes"})


def test_service_preview_must_match_trusted_wrapper_outputs_before_packaging(tmp_path, monkeypatch):
    request = _request()
    source_commit = "a" * 40
    source = tmp_path / "source"
    source.mkdir()
    (tmp_path / "restricted").mkdir(mode=0o700)
    catalogue = tmp_path / "catalogue"
    catalogue.mkdir()
    toolchain = tmp_path / "toolchain"
    toolchain.mkdir()
    source_fwsc = tmp_path / "source.fwsc"
    source_fwsc.write_bytes(b"model")
    reference = tmp_path / "reference"
    reference.mkdir()

    monkeypatch.setattr(adapter, "_verify_source_binding", lambda *_args: None)
    monkeypatch.setattr(adapter, "_validate_preview", lambda *_args: {
        "artifact_sha256": hashlib.sha256(b"preview-app").hexdigest(),
        "elf_sha256": hashlib.sha256(b"preview-elf").hexdigest(),
    })
    wrapper_calls = []

    def fake_wrapper(_source, request_path, _toolchain, catalogue_root, output):
        wrapper_calls.append(Path(request_path).read_bytes())
        _trusted_output(Path(output), Path(catalogue_root), request, source_commit,
                        b"different-app", b"preview-elf")

    monkeypatch.setattr(adapter, "_run_trusted_wrapper", fake_wrapper)
    with pytest.raises(ValueError, match="preview app/ELF differs"):
        adapter.compose_private_candidate(
            request_raw=request, service_result=_minimal_preview(),
            service_image_digest=adapter.SERVICE_IMAGE_DIGEST, set_parents={},
            source_root=source, expected_source_commit=source_commit,
            toolchain_root=toolchain, catalogue_root=catalogue,
            source_fwsc=source_fwsc, reference_dir=reference,
            private_run_dir=tmp_path / "restricted" / "run")
    assert wrapper_calls == [request]
    assert not (tmp_path / "restricted/run/candidate.fwsc").exists()


def test_candidate_writes_only_false_status_receipt_from_trusted_packager(tmp_path, monkeypatch):
    request = _request()
    source_commit = "b" * 40
    source = tmp_path / "source"
    source.mkdir()
    restricted = tmp_path / "restricted"
    restricted.mkdir(mode=0o700)
    catalogue = tmp_path / "catalogue"
    catalogue.mkdir()
    toolchain = tmp_path / "toolchain"
    toolchain.mkdir()
    source_fwsc = tmp_path / "source.fwsc"
    source_fwsc.write_bytes(b"model")
    reference = tmp_path / "reference"
    reference.mkdir()

    monkeypatch.setattr(adapter, "_verify_source_binding", lambda *_args: None)
    monkeypatch.setattr(adapter, "_validate_preview", lambda *_args: {
        "artifact_sha256": hashlib.sha256(b"same-app").hexdigest(),
        "elf_sha256": hashlib.sha256(b"same-elf").hexdigest(),
    })
    monkeypatch.setattr(adapter, "_run_trusted_wrapper",
                        lambda _source, _request, _toolchain, catalogue, output:
                        _trusted_output(Path(output), Path(catalogue), request, source_commit,
                                        b"same-app", b"same-elf"))

    package_report = {key: False for key in (
        "hardware_admitted", "hardware_tested", "installable",
        "updater_acceptance_verified", "release_admitted")}
    monkeypatch.setattr("tools.jieli.trusted_fwsc_package.package_bytes",
                        lambda **_kwargs: (b"private-candidate", package_report))
    receipt = adapter.compose_private_candidate(
        request_raw=request, service_result=_minimal_preview(b"same-app", b"same-elf"),
        service_image_digest=adapter.SERVICE_IMAGE_DIGEST, set_parents={},
        source_root=source, expected_source_commit=source_commit,
        toolchain_root=toolchain, catalogue_root=catalogue,
        source_fwsc=source_fwsc, reference_dir=reference,
        private_run_dir=restricted / "run")
    candidate = restricted / "run/candidate.fwsc"
    assert candidate.read_bytes() == b"private-candidate"
    assert os.stat(candidate).st_mode & 0o777 == 0o600
    assert receipt["service_preview_matches_trusted_build"] is True
    assert all(receipt[key] is False for key in (
        "hardware_admitted", "hardware_tested", "installable",
        "updater_acceptance_verified", "release_admitted"))


def test_private_adapter_requires_canonical_continuous_d7000_request():
    request = json.loads(_request())
    request["flash_layout"] = "expanded-d9000"
    raw = json.dumps(request, sort_keys=True, separators=(",", ":")).encode() + b"\n"
    with pytest.raises(ValueError, match="explicit continuous D7000"):
        adapter._validate_request(raw)


def test_service_image_pin_is_the_configured_worker_image():
    from tools.installer_service.docker_adapter import _IMAGE_ID

    assert adapter.SERVICE_IMAGE_DIGEST == _IMAGE_ID
    assert adapter.SERVICE_IMAGE_DIGEST == "sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495"


def test_trusted_catalogue_loader_accepts_retained_schema2_shape_without_stripping_metadata():
    retained_row = {
        "optimization": "-Oz",
        "path": "/catalogue/shard-00/obj/c/seq/fx_host.o",
        "sha256": "aeb1075514383489d05ad788fb50440bddc4f4296e3782203b962a1fe3a9860f",
    }
    manifest = {"schema": 2, "objects": [retained_row]}
    assert adapter._catalogue_rows(manifest) == [retained_row]
    assert manifest["objects"][0] == retained_row

    legacy = {"schema": 1, "objects": [{key: value for key, value in retained_row.items()
                                          if key != "optimization"}]}
    assert adapter._catalogue_rows(legacy) == legacy["objects"]
    for invalid in (
        {"schema": 1, "objects": [retained_row]},
        {"schema": 2, "objects": [legacy["objects"][0]]},
        {"schema": True, "objects": [retained_row]},
        {"schema": 2, "objects": [dict(retained_row, extra="x")]},
    ):
        with pytest.raises(ValueError):
            adapter._catalogue_rows(invalid)


def test_trusted_generated_input_cannot_escape_build_root(tmp_path):
    request = _request()
    output = tmp_path / "trusted"
    output.mkdir()
    build = output / "build"
    external = tmp_path / "external"
    external.mkdir()
    _write(external / "generated.cc", b"outside")
    _trusted_output(output, tmp_path / "catalogue", request, "c" * 40,
                    b"app", b"elf")
    (build / "link").rename(build / "link-original")
    (build / "link").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="parent is missing or unsafe"):
        adapter._load_trusted_package_inputs(output, tmp_path / "catalogue", "c" * 40)


def test_special_file_input_is_rejected_without_blocking(tmp_path):
    fifo = tmp_path / "input.fifo"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="bounded regular file"):
        adapter._read_regular(fifo, 1024)


def test_source_binding_requires_clean_pinned_commit_and_archive(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "pinned.txt").write_text("source\n")
    subprocess.run(["git", "-C", str(source), "add", "pinned.txt"], check=True)
    subprocess.run(["git", "-C", str(source), "-c", "user.name=Test",
                    "-c", "user.email=test@example.invalid", "commit", "-qm", "pin"], check=True)
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    tree = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD^{tree}"],
                          check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    archive = subprocess.run(["git", "-C", str(source), "archive", "--format=tar", commit],
                             check=True, stdout=subprocess.PIPE).stdout
    provenance = {"bindings": {
        "source_commit": commit, "source_tree_oid": tree,
        "source_archive_sha256": hashlib.sha256(archive).hexdigest(),
    }}
    result = _minimal_preview()
    result = WorkerResult(result.artifact, result.receipt, result.elf,
                          json.dumps(provenance).encode(), result.private_evidence)
    adapter._verify_source_binding(source, commit, result)
    (source / "pinned.txt").write_text("changed\n")
    with pytest.raises(ValueError, match="dirty or differs"):
        adapter._verify_source_binding(source, commit, result)

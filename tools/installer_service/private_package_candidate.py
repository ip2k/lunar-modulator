# SPDX-License-Identifier: MIT
"""Create a private FWSC candidate through the independently pinned wrapper.

The web service result remains a preview. This adapter requires a trusted
continuous-wrapper build of the identical request and byte-identical app/ELF,
then packages only the wrapper's captured tuple and receipts. It does not
change admission, hardware, installability, updater, or release status.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Mapping

from .api import Admission, WorkerResult, _reject_constant, _unique_object, _verify_result, canonical_request
from .docker_adapter import _IMAGE, _canonical_relative, read_private_evidence
from .provenance import canonical, sha256

MAX_REQUEST_BYTES = 65_536
MAX_EVIDENCE_FILES = 8192
MAX_EVIDENCE_BYTES = 512 * 1024 * 1024
MAX_EVIDENCE_FILE_BYTES = 128 * 1024 * 1024
MAX_APP_BYTES = 1024 * 1024
MAX_ELF_BYTES = 32 * 1024 * 1024
MAX_JSON_BYTES = 32 * 1024 * 1024
_SHA = re.compile(r"[0-9a-f]{64}\Z")
SERVICE_IMAGE_DIGEST = _IMAGE.split("@", 1)[1]


def _json(raw: bytes, label: str) -> dict:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError(label + " is malformed JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(label + " must be an object")
    return value


def _read_regular(path: Path, limit: int, *, root: Path | None = None) -> bytes:
    path = Path(path)
    if root is not None:
        root = Path(root)
        if root.is_symlink() or not root.is_dir():
            raise ValueError("trusted build input root is not a regular directory")
        root = root.resolve(strict=True)
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise ValueError("trusted build input escapes its pinned root") from exc
        parent = root
        for part in relative.parts[:-1]:
            parent = parent / part
            if parent.is_symlink() or not parent.is_dir():
                raise ValueError("trusted build input parent is missing or unsafe")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise ValueError("trusted build input is not a bounded regular file")
        raw = stream.read(info.st_size + 1)
        if len(raw) != info.st_size:
            raise ValueError("trusted build input changed while reading")
        return raw


def _write_exclusive(path: Path, raw: bytes, mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _validate_request(request_raw: bytes) -> dict:
    if not isinstance(request_raw, bytes) or not 0 < len(request_raw) <= MAX_REQUEST_BYTES:
        raise ValueError("service request is outside the fixed size bound")
    request = _json(request_raw, "service request")
    if canonical_request(request) != request_raw:
        raise ValueError("service request bytes are not the exact canonical request")
    if request.get("runtime_mode") != "continuous" or request.get("flash_layout") != "expanded-d7000":
        raise ValueError("private package candidates require the explicit continuous D7000 request")
    return request


def _verify_source_binding(source_root: Path, expected_source_commit: str,
                           service_result: WorkerResult) -> None:
    if not isinstance(expected_source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", expected_source_commit):
        raise ValueError("expected source commit must be a full immutable SHA")
    source_root = Path(source_root)
    if source_root.is_symlink():
        raise ValueError("trusted build source may not be a symlink")
    source_root = source_root.resolve(strict=True)
    status = subprocess.run(
        ["git", "-C", str(source_root), "status", "--porcelain=v1", "--untracked-files=all"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=10).stdout
    commit = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=10,
        text=True).stdout.strip()
    if status or commit != expected_source_commit:
        raise ValueError("trusted build source is dirty or differs from the pinned commit")

    provenance = _json(service_result.provenance, "service provenance")
    bindings = provenance.get("bindings")
    if not isinstance(bindings, dict) or bindings.get("source_commit") != expected_source_commit:
        raise ValueError("service result belongs to a different source commit")
    expected_tree = subprocess.run(
        ["git", "-C", str(source_root), "rev-parse", expected_source_commit + "^{tree}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=10,
        text=True).stdout.strip()
    if bindings.get("source_tree_oid") != expected_tree:
        raise ValueError("service result source tree binding differs from the pinned commit")
    archive = subprocess.run(
        ["git", "-C", str(source_root), "archive", "--format=tar", expected_source_commit],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True, timeout=30).stdout
    if not 0 < len(archive) <= 128 * 1024 * 1024 or bindings.get("source_archive_sha256") != sha256(archive):
        raise ValueError("service result source archive binding differs from the pinned commit")


def _validate_preview(request_raw: bytes, request: dict, service_result: WorkerResult,
                      service_image_digest: str, set_parents: Mapping[str, str],
                      catalogue_root: Path) -> dict:
    if not isinstance(service_result, WorkerResult):
        raise ValueError("service result is missing")
    if (not isinstance(service_result.private_evidence, dict)
            or not isinstance(service_image_digest, str)
            or service_image_digest != SERVICE_IMAGE_DIGEST):
        raise ValueError("service result lacks bounded evidence or the configured fixed image pin")
    admission = Admission(sha256(request_raw), request, 0.0, service_image_digest)
    summary = _verify_result(admission, service_result, dict(set_parents))

    evidence = service_result.private_evidence
    if not 1 <= len(evidence) <= MAX_EVIDENCE_FILES:
        raise ValueError("service private evidence has an invalid file count")
    manifest = {}
    total = 0
    for relative, raw in evidence.items():
        if not isinstance(relative, str) or not isinstance(raw, bytes) or not raw:
            raise ValueError("service private evidence entry is malformed")
        rel = _canonical_relative(relative)
        if relative == "manifest.json" or len(raw) > MAX_EVIDENCE_FILE_BYTES:
            raise ValueError("service private evidence entry is outside fixed bounds")
        total += len(raw)
        if total > MAX_EVIDENCE_BYTES:
            raise ValueError("service private evidence exceeds the aggregate bound")
        manifest[rel.as_posix()] = {"bytes": len(raw), "sha256": sha256(raw)}

    # Reuse the service's established full manifest/receipt/catalogue/linked-
    # object validator instead of reimplementing its path and evidence rules.
    with tempfile.TemporaryDirectory(prefix="lunar-service-evidence-") as temporary:
        result_dir = Path(temporary)
        evidence_root = result_dir / "evidence"
        evidence_root.mkdir(mode=0o700)
        _write_exclusive(evidence_root / "manifest.json", canonical(manifest))
        for relative, raw in evidence.items():
            rel = _canonical_relative(relative)
            destination = evidence_root.joinpath(*rel.parts)
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            _write_exclusive(destination, raw)
        validated = read_private_evidence(result_dir, request_raw, service_result.receipt,
                                          Path(catalogue_root))
        if validated != evidence:
            raise ValueError("service private evidence changed during validation")
    return summary


def _load_trusted_package_inputs(trusted_output: Path, catalogue_root: Path):
    build = trusted_output / "build"
    tuple_raw = _read_regular(build / "build_tuple.json", MAX_JSON_BYTES, root=build)
    capture = _json(_read_regular(build / "tuple-capture.json", 65536, root=build), "tuple capture")
    tuple_value = _json(tuple_raw, "build tuple")
    tuple_sha = sha256(tuple_raw)
    if (capture.get("tuple_sha256") != tuple_sha
            or capture.get("source_commit") != tuple_value.get("source_commit")
            or any(capture.get(key) is not False for key in
                   ("hardware_admitted", "hardware_tested", "installable"))):
        raise ValueError("trusted wrapper capture does not bind its tuple or acceptance flags")

    provenance_raw = _read_regular(build / "build-provenance.json", MAX_JSON_BYTES, root=build)
    provenance = _json(provenance_raw, "trusted build provenance")
    if (capture.get("schema") != 1 or type(capture.get("schema")) is not int
            or capture.get("provenance_sha256") != sha256(provenance_raw)
            or capture.get("catalogue_sha256") != tuple_value.get("catalogue_sha256")
            or capture.get("source_tree_sha256") != tuple_value.get("source_tree_sha256")):
        raise ValueError("trusted wrapper capture does not bind provenance and source/catalogue inputs")
    catalogue_raw = _read_regular(build / "catalogue-manifest.json", MAX_JSON_BYTES, root=build)
    catalogue_manifest = _json(catalogue_raw, "trusted catalogue manifest")
    rows = catalogue_manifest.get("objects")
    if (catalogue_manifest.get("schema") != 1 or not isinstance(rows, list)
            or not 1 <= len(rows) <= MAX_EVIDENCE_FILES):
        raise ValueError("trusted catalogue manifest is malformed")
    catalogue_files = {}
    catalogue_total = 0
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                or not row["path"].startswith("/catalogue/")
                or not isinstance(row.get("sha256"), str) or not _SHA.fullmatch(row["sha256"])):
            raise ValueError("trusted catalogue object row is malformed")
        relative = row["path"][len("/catalogue/"):]
        rel = _canonical_relative(relative)
        if row["path"] in catalogue_files:
            raise ValueError("trusted catalogue manifest repeats an object path")
        file_path = Path(catalogue_root).joinpath(*rel.parts)
        raw = _read_regular(file_path, min(MAX_EVIDENCE_FILE_BYTES,
                                           MAX_EVIDENCE_BYTES - catalogue_total),
                            root=catalogue_root)
        catalogue_total += len(raw)
        if sha256(raw) != row["sha256"]:
            raise ValueError("trusted catalogue bytes differ from the wrapper receipt")
        catalogue_files[row["path"]] = raw

    generated_rows = provenance.get("module_and_generated_inputs")
    if (not isinstance(generated_rows, list)
            or not 1 <= len(generated_rows) <= MAX_EVIDENCE_FILES):
        raise ValueError("trusted wrapper provenance omits generated inputs")
    generated_files = {}
    generated_total = 0
    for row in generated_rows:
        if (not isinstance(row, dict) or not isinstance(row.get("path"), str)
                or not isinstance(row.get("sha256"), str) or not _SHA.fullmatch(row["sha256"])):
            raise ValueError("trusted generated-input row is malformed")
        rel = _canonical_relative(row["path"])
        if row["path"] in generated_files:
            raise ValueError("trusted provenance repeats a generated input path")
        raw = _read_regular(build.joinpath(*rel.parts),
                            min(MAX_EVIDENCE_FILE_BYTES,
                                MAX_EVIDENCE_BYTES - generated_total), root=build)
        generated_total += len(raw)
        if sha256(raw) != row["sha256"]:
            raise ValueError("trusted generated input differs from wrapper provenance")
        generated_files[row["path"]] = raw

    values = {
        "build_tuple": tuple_raw,
        "expected_tuple_sha256": tuple_sha,
        "request": _read_regular(build / "selection/request.json", 65536, root=build),
        "prepared_profile": _read_regular(build / "selection/prepared/profile.json", 4 * 1024 * 1024, root=build),
        "source_profile": _read_regular(build / "selection/staged/profile.json", 4 * 1024 * 1024, root=build),
        "artifact_receipt": _read_regular(build / "link/artifact/artifact.json", 65536, root=build),
        "build_receipt": _read_regular(build / "link/verification.json", MAX_JSON_BYTES, root=build),
        "image_receipt": _read_regular(build / "image.json", 65536, root=build),
        "build_provenance": provenance_raw,
        "catalogue_manifest": catalogue_raw,
        "app": _read_regular(build / "link/artifact/app.bin", MAX_APP_BYTES, root=build),
        "elf": _read_regular(build / "link/lunar-app-probe.elf", MAX_ELF_BYTES, root=build),
        "catalogue_files": catalogue_files,
        "generated_files": generated_files,
        "reference_dir": None,
        "_tuple_capture": capture,
        "_build_dir": build,
    }
    return values


def _run_trusted_wrapper(source_root: Path, request_path: Path, toolchain_root: Path,
                         catalogue_root: Path, output_path: Path) -> None:
    wrapper = Path(source_root) / "tools/native/run_trusted_continuous_build.py"
    command = [sys.executable, str(wrapper), "--request", str(request_path),
               "--toolchain", str(toolchain_root), "--catalogue", str(catalogue_root),
               "--out", str(output_path)]
    completed = subprocess.run(command, cwd=source_root, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=1500, check=False)
    if completed.returncode != 0:
        raise ValueError("pinned trusted continuous wrapper refused or failed this request")


def compose_private_candidate(*, request_raw: bytes, service_result: WorkerResult,
                              service_image_digest: str, set_parents: Mapping[str, str],
                              source_root: Path, expected_source_commit: str,
                              toolchain_root: Path, catalogue_root: Path,
                              source_fwsc: Path, reference_dir: Path,
                              private_run_dir: Path) -> dict:
    """Rerun one canonical service request under the trusted wrapper and package it privately.

    The service app and ELF must match the wrapper's outputs byte-for-byte.
    Service receipts are validated for their own bindings but are never
    translated into tuple provenance; the package consumes only the wrapper's
    captured tuple, receipts, catalogue, and generated inputs.
    """
    request = _validate_request(request_raw)
    input_paths = tuple(map(Path, (source_root, toolchain_root, catalogue_root,
                                   source_fwsc, reference_dir)))
    if any(path.is_symlink() for path in input_paths):
        raise ValueError("private package inputs may not be symlinks")
    source_root, toolchain_root, catalogue_root, source_fwsc, reference_dir = (
        path.resolve(strict=True) for path in input_paths)
    private_run_dir = Path(private_run_dir).absolute()
    parent = private_run_dir.parent.resolve(strict=True)
    if (private_run_dir.exists() or private_run_dir.is_symlink()
            or not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077):
        raise ValueError("private output must be a new child of an owner-only directory")

    _verify_source_binding(source_root, expected_source_commit, service_result)
    summary = _validate_preview(request_raw, request, service_result, service_image_digest,
                                set_parents, catalogue_root)
    private_run_dir.mkdir(mode=0o700)
    request_path = private_run_dir / "service-request.json"
    _write_exclusive(request_path, request_raw, 0o400)
    trusted_output = private_run_dir / "trusted-build"
    _run_trusted_wrapper(source_root, request_path, toolchain_root, catalogue_root, trusted_output)

    package_values = _load_trusted_package_inputs(trusted_output, catalogue_root)
    capture = package_values.pop("_tuple_capture")
    build_dir = package_values.pop("_build_dir")
    capture_request = package_values["request"]
    if capture_request != request_raw:
        raise ValueError("trusted wrapper captured a different request")
    if (capture.get("source_commit") != expected_source_commit
            or _json(package_values["build_tuple"], "build tuple").get("request_sha256") != sha256(request_raw)):
        raise ValueError("trusted tuple source/request binding differs from the service job")
    if (package_values["app"] != service_result.artifact
            or package_values["elf"] != service_result.elf):
        raise ValueError("service preview app/ELF differs from the independent trusted build")

    package_values["source_fwsc"] = _read_regular(source_fwsc, 16 * 1024 * 1024)
    package_values["reference_dir"] = reference_dir
    from tools.jieli.trusted_fwsc_package import package_bytes
    package, report = package_bytes(**package_values)
    if any(report.get(key) is not False for key in
           ("hardware_admitted", "hardware_tested", "installable",
            "updater_acceptance_verified", "release_admitted")):
        raise ValueError("trusted packager report overstates hardware or release acceptance")

    package_sha = sha256(package)
    package_report_raw = json.dumps(report, sort_keys=True, indent=2).encode("ascii") + b"\n"
    candidate_receipt = {
        "schema": 1,
        "status": "private-offline-candidate-composed-and-structurally-verified",
        "request_sha256": sha256(request_raw),
        "trusted_tuple_sha256": capture["tuple_sha256"],
        "service_preview_app_sha256": summary["artifact_sha256"],
        "service_preview_elf_sha256": summary["elf_sha256"],
        "service_preview_matches_trusted_build": True,
        "package_sha256": package_sha,
        "package_bytes": len(package),
        "hardware_admitted": False,
        "hardware_tested": False,
        "installable": False,
        "updater_acceptance_verified": False,
        "release_admitted": False,
    }
    _write_exclusive(private_run_dir / "candidate.fwsc", package)
    _write_exclusive(private_run_dir / "package-report.json", package_report_raw)
    _write_exclusive(private_run_dir / "candidate-receipt.json", canonical(candidate_receipt) + b"\n")
    return candidate_receipt

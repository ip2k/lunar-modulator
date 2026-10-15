#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Container entrypoint. Inputs/paths are constants, never request-controlled."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from pathlib import PurePosixPath

SOURCE = Path("/workspace")
SOURCE_ARCHIVE = Path("/input/source.tar")
REQUEST = Path("/input/request.json")
TOOLCHAIN = Path("/opt/pi32v2")
CATALOGUE = Path("/input/catalogue")
RESULT = Path("/result")
SCRATCH = Path("/tmp/lunar-worker")
MAX_REQUEST = 65536
MAX_APP = 1048576
MAX_ELF = 16 * 1024 * 1024
MAX_RECEIPT = 65536
MAX_EVIDENCE_FILE = 128 * 1024 * 1024
MAX_EVIDENCE_TOTAL = 512 * 1024 * 1024
GENERATED_EVIDENCE_PATHS = (
    "selection/prepared/fm1_modules.h",
    "selection/prepared/modules/gen/fm1_modules.h",
    "link/gen/fm1_modules.h",
    "link/module-all/gen/fm1_modules.h",
    "link/module-selection/gen/fm1_modules.h",
    "link/wave_tables.json",
    "link/resources_braids.cc",
    "link/resources_plaits.cc",
    "link/resources_braids.h",
    "link/resources_plaits.h",
)


def build_profile_arguments(request: dict) -> list[str]:
    """Map only validated layout/profile selections to fixed native flags."""
    layout = request.get("flash_layout", "expanded-d9000")
    runtime = request.get("runtime_mode", "diagnostic")
    if layout == "expanded-d9000" and runtime == "diagnostic":
        return ["--flash-layout", "expanded-d9000", "--runtime-mode", "diagnostic",
                "--wavetable-profile", "compressed-required-banks-flash-plaits-v1"]
    if layout == "expanded-d7000" and runtime == "song-diagnostic":
        selected = [module for group in ("engines", "effects", "midi", "modulation")
                    for module in request.get(group, [])]
        if not {"macro", "shapes"}.issubset(set(selected)):
            raise ValueError("expanded-d7000 requires the fixed Macro+Shapes8 profile")
        return ["--flash-layout", "expanded-d7000", "--runtime-mode", "song-diagnostic",
                "--wavetable-profile", "compressed-required-banks-ram-plaits-braids-shapes8-v1"]
    raise ValueError("unsupported diagnostic layout/runtime profile")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate receipt field")
        result[key] = value
    return result


def regular_file(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected regular file")
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise ValueError("input/output exceeds cap")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("file changed while reading")
    return data


def verified_build_outputs(build_root: Path) -> tuple[bytes, bytes, bytes]:
    """Load the app, matching linker ELF, and its receipt as bounded files."""
    app = regular_file(build_root / "link/artifact/app.bin", MAX_APP)
    elf = regular_file(build_root / "link/lunar-app-probe.elf", MAX_ELF)
    receipt = regular_file(build_root / "image.json", MAX_RECEIPT)
    try:
        report = json.loads(receipt.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ValueError("build receipt is malformed") from exc
    if (not isinstance(report, dict)
            or report.get("app_sha256") != hashlib.sha256(app).hexdigest()
            or report.get("elf_sha256") != hashlib.sha256(elf).hexdigest()):
        raise ValueError("build receipt does not match app/ELF bytes")
    return app, elf, receipt


def retain_private_evidence(build_root: Path, request_bytes: bytes) -> dict[str, str]:
    """Copy the bounded receipt/profile/object inputs used by the offline packager."""
    evidence_root = RESULT / "evidence"
    evidence_root.mkdir(mode=0o700)
    evidence: dict[str, bytes] = {
        "request.json": request_bytes,
        "prepared_profile.json": regular_file(build_root / "selection/prepared/profile.json", 4 * 1024 * 1024),
        "source_profile.json": regular_file(build_root / "selection/staged/profile.json", 4 * 1024 * 1024),
        "artifact_receipt.json": regular_file(build_root / "link/artifact/artifact.json", MAX_EVIDENCE_FILE),
        "build_receipt.json": regular_file(build_root / "link/verification.json", MAX_EVIDENCE_FILE),
        "image_receipt.json": regular_file(build_root / "image.json", MAX_RECEIPT),
    }
    receipt = json.loads(evidence["build_receipt.json"].decode("utf-8"),
                         object_pairs_hook=_unique_object)
    catalogue_rows = receipt.get("catalogue_objects")
    linked_rows = receipt.get("linked_objects")
    if not isinstance(catalogue_rows, list) or not isinstance(linked_rows, list):
        raise ValueError("build receipts omit catalogue or linked-object inventory")
    evidence["catalogue_manifest.json"] = json.dumps(
        {"schema": 1, "objects": sorted(catalogue_rows, key=lambda row: row.get("path", ""))},
        sort_keys=True, separators=(",", ":")).encode("ascii")
    evidence["linked_objects.json"] = json.dumps(
        {"schema": 1, "objects": sorted(linked_rows, key=lambda row: row.get("path", ""))},
        sort_keys=True, separators=(",", ":")).encode("ascii")
    for row in catalogue_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("catalogue object row is malformed")
        path = row["path"]
        if not isinstance(path, str) or not path.startswith("/catalogue/"):
            raise ValueError("catalogue object path is outside the fixed namespace")
        rel = PurePosixPath(path.removeprefix("/catalogue/"))
        if "\\" in str(rel) or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
            raise ValueError("catalogue object path is unsafe")
        key = "catalogue/" + rel.as_posix()
        evidence[key] = regular_file(CATALOGUE.joinpath(*rel.parts), MAX_EVIDENCE_FILE)
    for rel in GENERATED_EVIDENCE_PATHS:
        if (build_root / rel).exists():
            evidence["generated/" + rel] = regular_file(build_root / rel, MAX_EVIDENCE_FILE)
    for row in linked_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("linked object row is malformed")
        path = row["path"]
        if not isinstance(path, str):
            raise ValueError("linked object path is malformed")
        if path.startswith("/catalogue/"):
            root = CATALOGUE
            rel = PurePosixPath(path.removeprefix("/catalogue/"))
            key = "linked/catalogue/" + rel.as_posix()
        elif path.startswith("/output/build/link/"):
            root = build_root
            rel = PurePosixPath("link/" + path.removeprefix("/output/build/link/"))
            key = "linked/link/" + path.removeprefix("/output/build/link/")
        else:
            raise ValueError("linked object path is outside the fixed worker mounts")
        if "\\" in str(rel) or rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
            raise ValueError("linked object path is unsafe")
        evidence[key] = regular_file(root.joinpath(*rel.parts), MAX_EVIDENCE_FILE)
    if len(evidence) > 8192 or sum(map(len, evidence.values())) > MAX_EVIDENCE_TOTAL:
        raise ValueError("private build evidence exceeds fixed bounds")
    manifest = {}
    for rel, raw in sorted(evidence.items()):
        path = evidence_root / rel
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(raw)
        os.chmod(path, 0o600)
        manifest[rel] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    manifest_raw = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("ascii")
    (evidence_root / "manifest.json").write_bytes(manifest_raw)
    os.chmod(evidence_root / "manifest.json", 0o600)
    return {"files": len(evidence), "bytes": sum(map(len, evidence.values())),
            "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest()}


def main() -> int:
    request_bytes = regular_file(REQUEST, MAX_REQUEST)
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ValueError("request must be object")
    profile_args = build_profile_arguments(request)
    archive_bytes = regular_file(SOURCE_ARCHIVE, 128 * 1024 * 1024)
    if not TOOLCHAIN.is_dir() or not (CATALOGUE / "shard-00/objects.json").is_file():
        raise ValueError("fixed worker inputs are unavailable")
    if RESULT.is_symlink() or not RESULT.is_dir() or any(RESULT.iterdir()):
        raise ValueError("result mount is not an empty service directory")

    # Extract only the server-created git archive into bounded tmpfs. Reject
    # links and path traversal even though the archive is generated locally.
    SCRATCH.mkdir(mode=0o700, parents=True, exist_ok=False)
    work = SCRATCH / "source"
    work.mkdir(mode=0o700)
    seen = set()
    with tarfile.open(SOURCE_ARCHIVE, "r:") as archive:
        members = archive.getmembers()
        if len(members) > 200000:
            raise ValueError("source archive contains too many entries")
        for member in members:
            parts = Path(member.name).parts
            if (not member.name or Path(member.name).is_absolute()
                    or any(part in ("", ".", "..") for part in parts)
                    or member.name in seen or member.issym() or member.islnk()
                    or not (member.isdir() or member.isfile())):
                raise ValueError("source archive contains an unsafe entry")
            seen.add(member.name)
            destination = work.joinpath(*parts)
            if destination.resolve().is_relative_to(work.resolve()) is False:
                raise ValueError("source archive escapes workspace")
            if member.isdir():
                destination.mkdir(mode=0o755, parents=True, exist_ok=True)
            else:
                if member.size < 0 or member.size > 128 * 1024 * 1024:
                    raise ValueError("source archive member exceeds cap")
                destination.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
                source_file = archive.extractfile(member)
                if source_file is None:
                    raise ValueError("source archive member is unreadable")
                with source_file, destination.open("xb") as target:
                    shutil.copyfileobj(source_file, target, length=1024 * 1024)
                os.chmod(destination, 0o755 if member.mode & 0o111 else 0o644)
    subprocess.run(["make", "-C", str(work / "engines"), "build/fm1-state"],
                   check=True, timeout=120)
    output = SCRATCH / "output"
    (output / "build").parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(work / "tools/native/build_demo_image.py"),
        "--request", str(REQUEST),
        "--state-tool", str(work / "engines/build/fm1-state"),
        "--toolchain", str(TOOLCHAIN),
        "--catalogue", str(CATALOGUE),
        "--out", str(output / "build"),
        *profile_args,
    ], check=True, timeout=1200)
    app, elf, receipt = verified_build_outputs(output / "build")
    evidence_summary = retain_private_evidence(output / "build", request_bytes)
    (RESULT / "app.bin").write_bytes(app)
    (RESULT / "elf.bin").write_bytes(elf)
    (RESULT / "image.json").write_bytes(receipt)
    print(json.dumps({"app_bytes": len(app), "app_sha256": hashlib.sha256(app).hexdigest(),
                      "elf_bytes": len(elf), "elf_sha256": hashlib.sha256(elf).hexdigest(),
                      "receipt_bytes": len(receipt),
                      "private_evidence": evidence_summary}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("diagnostic worker failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1)

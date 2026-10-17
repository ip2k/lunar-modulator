#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Container entrypoint. Inputs/paths are constants, never request-controlled."""
from __future__ import annotations

import hashlib
import importlib.util
import importlib
import json
import os
from pathlib import Path
import shutil
import re
import stat
import subprocess
import sys
import tarfile
from pathlib import PurePosixPath

INPUT = Path(__file__).resolve().parent
SOURCE = Path("/workspace")
SOURCE_ARCHIVE = INPUT / "source.tar"
REQUEST = INPUT / "request.json"
TOOLCHAIN = Path("/opt/pi32v2")
CATALOGUE = Path("/catalogue")
OUTPUT = Path("/output")
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
    "link/wave_tables.inc",
)
CATALOGUE_MOUNT = "/catalogue/"
BUILD_LINK_MOUNT = "/output/build/link/"
_BOOTSTRAP_CONTINUOUS_ARGUMENTS = (
    "--flash-layout", "expanded-d7000", "--runtime-mode", "continuous",
    "--wavetable-profile", "compressed-required-banks-ram-plaits-braids-shapes8-v1",
    "--firmware-identity", "FM-1_500",
)
_BOOTSTRAP_HALL_PROFILE = "hall-o2-stage7-v1"
_BOOTSTRAP_HALL_REQUIRED_BY_GROUP = {
    "engines": frozenset(("macro", "shapes", "sixop", "drums")),
    "effects": frozenset(("hall",)),
}


def build_profile_arguments(request: dict) -> list[str]:
    """Map only validated layout/profile selections to fixed native flags."""
    layout = request.get("flash_layout", "expanded-d9000")
    runtime = request.get("runtime_mode", "diagnostic")
    if layout == "expanded-d9000" and runtime == "diagnostic":
        return ["--flash-layout", "expanded-d9000", "--runtime-mode", "diagnostic",
                "--wavetable-profile", "compressed-required-banks-flash-plaits-v1"]
    if layout == "expanded-d7000" and runtime == "continuous":
        return list(_BOOTSTRAP_CONTINUOUS_ARGUMENTS)
    if layout == "expanded-d7000" and runtime == "song-diagnostic":
        for group, required in _BOOTSTRAP_HALL_REQUIRED_BY_GROUP.items():
            selected = request.get(group, ())
            if not isinstance(selected, (list, tuple)) or not all(
                    isinstance(module, str) for module in selected):
                raise ValueError("unsupported private build layout/runtime profile")
        missing = {
            group: sorted(required - set(request.get(group, ())))
            for group, required in _BOOTSTRAP_HALL_REQUIRED_BY_GROUP.items()
        }
        missing = {group: ids for group, ids in missing.items() if ids}
        if missing:
            details = "; ".join(
                f"{group}: {', '.join(ids)}" for group, ids in sorted(missing.items())
            )
            raise ValueError(
                f"Named diagnostic profile {_BOOTSTRAP_HALL_PROFILE} requires caller-selected "
                f"modules in their catalogue groups ({details})"
            )
        return ["--flash-layout", "expanded-d7000", "--runtime-mode", "song-diagnostic",
                "--wavetable-profile", "compressed-required-banks-ram-plaits-braids-shapes8-v1",
                "--diagnostic-profile", _BOOTSTRAP_HALL_PROFILE]
    raise ValueError("unsupported private build layout/runtime profile")


def verify_extracted_profile_contract(source_root: Path, request=None) -> None:
    """Require the pinned source archive to agree with this standalone bootstrap."""
    source_root = source_root.resolve()
    sys.path.insert(0, str(source_root))
    contract_path = source_root / "tools/native/diagnostic_profile_contract.py"
    if contract_path.is_symlink() or not contract_path.is_file():
        raise ValueError("extracted diagnostic profile contract is unavailable")
    spec = importlib.util.spec_from_file_location("_worker_profile_contract", contract_path)
    if spec is None or spec.loader is None:
        raise ValueError("extracted diagnostic profile contract is unavailable")
    contract = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(contract)
    required = getattr(contract, "HALL_O2_STAGE7_REQUIRED_BY_GROUP", None)
    if (getattr(contract, "HALL_O2_STAGE7_PROFILE", None) != _BOOTSTRAP_HALL_PROFILE
            or not isinstance(required, dict)
            or {group: frozenset(modules) for group, modules in required.items()}
            != _BOOTSTRAP_HALL_REQUIRED_BY_GROUP):
        raise ValueError("worker and extracted diagnostic profile contracts differ")

    if request is not None and request.get("runtime_mode") == "continuous":
        # The bootstrap has no source imports until the pinned archive is extracted.
        # Import from that exact archive, never the container's mutable /workspace.
        modules = {}
        for name in ("tools.installer_service", "tools.installer_service.continuous_profile",
                     "tools.installer_service.catalogue"):
            module = importlib.import_module(name)
            expected = source_root.joinpath(*name.split("."))
            expected = expected / "__init__.py" if name == "tools.installer_service" else expected.with_suffix(".py")
            if (not getattr(module, "__file__", None)
                    or Path(module.__file__).resolve() != expected
                    or expected.is_symlink() or not expected.is_file()):
                raise ValueError("worker import was not loaded from the extracted pinned source: " + name)
            modules[name] = module
        continuous_profile = modules["tools.installer_service.continuous_profile"]
        load_trusted_catalogue = modules["tools.installer_service.catalogue"].load_trusted_catalogue
        if tuple(continuous_profile.BUILD_ARGUMENTS) != _BOOTSTRAP_CONTINUOUS_ARGUMENTS:
            raise ValueError("worker and extracted continuous profile contracts differ")
        kinds, projects, parents = load_trusted_catalogue(source_root, include_sets=True)
        continuous_profile.validate_request(request, kinds, projects, parents)


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
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size != size:
            raise ValueError("file changed while opening")
        data = stream.read(size + 1)
    if len(data) != size:
        raise ValueError("file changed while reading")
    return data


def _receipt_relative(path: str, prefix: str) -> PurePosixPath:
    """Accept only a canonical path below the literal builder mount."""
    if not isinstance(path, str) or not path.startswith(prefix):
        raise ValueError("receipt path is outside the fixed worker namespace")
    raw = path[len(prefix):]
    parts = raw.split("/")
    if (not raw or "\\" in raw or any(part in ("", ".", "..") for part in parts)):
        raise ValueError("receipt path is not canonical")
    rel = PurePosixPath(raw)
    if rel.as_posix() != raw or rel.is_absolute():
        raise ValueError("receipt path is not canonical")
    return rel


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
    evidence: dict[str, bytes] = {}
    total = 0

    def retain(key: str, path: Path, limit: int = MAX_EVIDENCE_FILE) -> bytes:
        nonlocal total
        if path.is_symlink() or not path.is_file():
            raise ValueError("expected regular evidence file")
        size = path.stat().st_size
        if not 0 < size <= limit or size > MAX_EVIDENCE_TOTAL - total:
            raise ValueError("private build evidence exceeds fixed bounds")
        if len(evidence) >= 8192:
            raise ValueError("private build evidence has too many files")
        raw = regular_file(path, limit)
        total += size
        evidence[key] = raw
        return raw

    def retain_bytes(key: str, raw: bytes, limit: int = 32 * 1024 * 1024) -> None:
        nonlocal total
        if not 0 < len(raw) <= limit or len(raw) > MAX_EVIDENCE_TOTAL - total:
            raise ValueError("derived private evidence exceeds fixed bounds")
        if len(evidence) >= 8192:
            raise ValueError("private build evidence has too many files")
        total += len(raw)
        evidence[key] = raw

    if not 0 < len(request_bytes) <= MAX_REQUEST:
        raise ValueError("request evidence exceeds fixed bounds")
    evidence["request.json"] = request_bytes
    total = len(request_bytes)
    retain("prepared_profile.json", build_root / "selection/prepared/profile.json", 4 * 1024 * 1024)
    retain("source_profile.json", build_root / "selection/staged/profile.json", 4 * 1024 * 1024)
    retain("artifact_receipt.json", build_root / "link/artifact/artifact.json")
    build_receipt_raw = retain("build_receipt.json", build_root / "link/verification.json")
    retain("image_receipt.json", build_root / "image.json", MAX_RECEIPT)
    receipt = json.loads(evidence["build_receipt.json"].decode("utf-8"),
                         object_pairs_hook=_unique_object)
    if receipt.get("flash_layout") == "expanded-d7000":
        if (receipt.get("runtime_configuration") or {}).get("runtime_mode") == "continuous":
            from tools.installer_service.continuous_profile import evidence_manifest, validate_receipt
        else:
            from tools.installer_service.native_profile import evidence_manifest, validate_receipt
        validate_receipt(receipt)
        retain_bytes("native_profile.json", evidence_manifest(build_receipt_raw))
    catalogue_rows = receipt.get("catalogue_objects")
    linked_rows = receipt.get("linked_objects")
    if (not isinstance(catalogue_rows, list) or not isinstance(linked_rows, list)
            or not 0 < len(catalogue_rows) <= 8192 or not 0 < len(linked_rows) <= 8192):
        raise ValueError("build receipts omit catalogue or linked-object inventory")
    for row in catalogue_rows:
        if (not isinstance(row, dict) or set(row) not in
                ({"path", "sha256"}, {"path", "sha256", "optimization"})
                or not isinstance(row.get("path"), str) or not row["path"].isascii()
                or not isinstance(row.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                or ("optimization" in row and row["optimization"] not in ("-Oz", "-Os", "-O2"))):
            raise ValueError("catalogue object row is malformed")
    for row in linked_rows:
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or not isinstance(row.get("path"), str) or not row["path"].isascii()
                or not isinstance(row.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("linked object row is malformed")
    projected_size = sum(len(row["path"]) + 112 for row in (*catalogue_rows, *linked_rows))
    if projected_size > 32 * 1024 * 1024:
        raise ValueError("private object inventories exceed derived manifest cap")
    retain_bytes("catalogue_manifest.json", json.dumps(
        {"schema": 1, "objects": catalogue_rows},
        sort_keys=True, separators=(",", ":")).encode("ascii"))
    retain_bytes("linked_objects.json", json.dumps(
        {"schema": 1, "objects": linked_rows},
        sort_keys=True, separators=(",", ":")).encode("ascii"))
    for row in catalogue_rows:
        path = row["path"]
        rel = _receipt_relative(path, CATALOGUE_MOUNT)
        key = "catalogue/" + rel.as_posix()
        retain(key, CATALOGUE.joinpath(*rel.parts))
    for rel in generated_evidence_paths(receipt):
        retain("generated/" + rel, build_root / rel, 32 * 1024 * 1024)
    for row in linked_rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("linked object row is malformed")
        path = row["path"]
        if not isinstance(path, str):
            raise ValueError("linked object path is malformed")
        if path.startswith(CATALOGUE_MOUNT):
            root = CATALOGUE
            rel = _receipt_relative(path, CATALOGUE_MOUNT)
            key = "linked/catalogue/" + rel.as_posix()
        elif path.startswith(BUILD_LINK_MOUNT):
            root = build_root
            suffix = _receipt_relative(path, BUILD_LINK_MOUNT)
            rel = PurePosixPath("link") / suffix
            key = "linked/link/" + suffix.as_posix()
        else:
            raise ValueError("linked object path is outside the fixed worker mounts")
        retain(key, root.joinpath(*rel.parts))
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


def generated_evidence_paths(receipt):
    """Continuous subsets retain exactly their generated wavetable sources."""
    if (receipt.get("runtime_configuration") or {}).get("runtime_mode") != "continuous":
        return GENERATED_EVIDENCE_PATHS
    namespaces = {row["namespace"] for row in receipt["compressed_wave_tables"]}
    return tuple(path for path in GENERATED_EVIDENCE_PATHS
                 if not path.startswith("link/resources_")
                 or path.split("resources_", 1)[1].split(".", 1)[0] in namespaces)


def require_private_empty_root(path: Path) -> None:
    """Require an adapter-created canonical tmpfs root, never a path alias."""
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or path.resolve() != path
            or info.st_uid != os.getuid() or info.st_gid != os.getgid()
            or stat.S_IMODE(info.st_mode) != 0o700
            or any(path.iterdir())):
        raise ValueError("canonical build mount is not an empty private owned directory")


def freeze_source_tree(root: Path) -> None:
    """Keep extracted pinned source bytes read-only; build products live elsewhere."""
    for path in root.rglob("*"):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            os.chmod(path, 0o555)
        elif stat.S_ISREG(info.st_mode):
            os.chmod(path, 0o555 if info.st_mode & 0o111 else 0o444)
        else:
            raise ValueError("source tree contains an unsafe entry")
    os.chmod(root, 0o555)


def build_commands(work: Path, output: Path, profile_args: list[str]) -> tuple[list[str], list[str]]:
    """Use the trusted worker's canonical source/output paths and host codec recipe."""
    state_dir = SCRATCH / "state"
    state_tool = state_dir / "fm1-state"
    state_command = ["make", "-C", str(work / "engines"), "BUILD=" + str(state_dir),
                     "FM1_GPL_MODS=1", "-j4", str(state_tool)]
    image_command = [
        sys.executable, str(work / "tools/native/build_demo_image.py"),
        "--request", str(REQUEST), "--state-tool", str(state_tool),
        "--toolchain", str(TOOLCHAIN), "--catalogue", str(CATALOGUE),
        "--out", str(output / "build"), *profile_args,
    ]
    return state_command, image_command


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
    work = SOURCE
    output = OUTPUT
    require_private_empty_root(work)
    require_private_empty_root(output)
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
    freeze_source_tree(work)
    verify_extracted_profile_contract(work, request)
    state_command, image_command = build_commands(work, output, profile_args)
    subprocess.run(state_command, check=True, timeout=180)
    subprocess.run(image_command, check=True, timeout=1200)
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

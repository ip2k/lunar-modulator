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


# This fixed profile never uses the historical catalogue or receipt namespace.
SELECTED_TRIO_PROFILE = "sdk-free-selected-trio-offline-diagnostic-v1"
TOOLCHAIN_ARCHIVE = Path("/opt/lunar-toolchain.tar")
CXX_HEADERS = Path("/opt/original-libcxx")
SELECTED_RECEIPT_CAP = 4 * 1024 * 1024
SELECTED_EVIDENCE_CAP = 16 * 1024 * 1024


def load_selected_builder(source_root: Path):
    """Load only the operator-pinned, read-only builder; no tool is run here."""
    path = source_root / "tools/native/build_diagnostic.py"
    if path.is_symlink() or not path.is_file():
        raise ValueError("selected builder is unavailable")
    spec = importlib.util.spec_from_file_location("_selected_worker_builder", path)
    if spec is None or spec.loader is None:
        raise ValueError("selected builder is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.ROOT != source_root:
        raise ValueError("selected builder root differs from pinned source")
    return module


def selected_external_inputs(source_root: Path, toolchain: Path, archive: Path,
                             headers: Path) -> dict:
    """Acquire independent input anchors without consulting a build receipt."""
    builder = load_selected_builder(source_root)
    original = builder.header_manifest(headers)
    config = headers / "__config"
    text = config.read_text()
    pthread = "#define _LIBCPP_HAS_THREAD_API_PTHREAD\n"
    if text.count(pthread) != 1:
        raise ValueError("original libc++ configuration differs from fixed recipe")
    configured = dict(original)
    configured["__config"] = hashlib.sha256(text.replace(
        pthread, "/* Diagnostic: no thread API. */\n").encode()).hexdigest()
    return dict(source_manifest=builder.manifest(True),
                toolchain_binding=builder.bind_toolchain(toolchain, archive),
                cxx_headers_manifest=original,
                configured_cxx_headers_manifest=configured)


def selected_compile_flags() -> list[str]:
    """Independent fixed worker recipe, never recovered from a checked receipt."""
    return ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-Oz", "-ffreestanding",
            "-fno-builtin", "-ffunction-sections", "-fdata-sections",
            "-DFM1_APP_EXTERNAL_ARENAS=1", "-DNDEBUG", "-D_GNU_SOURCE", "-D_XOPEN_SOURCE=700",
            "-DFM1_APP_STATE_EXTERNAL_WORKSPACE=1", "-D_LIBCPP_HAS_NO_THREADS",
            "-D_LIBCPP_DISABLE_EXTERN_TEMPLATE", "-isystem", str(OUTPUT / "build/cxx"),
            "-isystem", str(TOOLCHAIN / "pi32v2/include")]


def selected_build_commands() -> tuple[list[str], list[str]]:
    host = SCRATCH / "host"
    make = ["make", "-s", "-C", str(SOURCE / "engines"), "-f", "Makefile",
            "-f", str(SOURCE / "sim/web/mk/sim.mk"), "SIM=" + str(SOURCE / "sim/web"),
            "BUILD=" + str(host), "FM1_MODULES=trio", "FM1_GPL_MODS=1", "-j4",
            str(host / "fm1-render"), str(host / "fm1-state")]
    target = [sys.executable, str(SOURCE / "tools/native/build_selected_trio_diagnostic.py"),
              "--toolchain", str(TOOLCHAIN), "--toolchain-archive", str(TOOLCHAIN_ARCHIVE),
              "--cxx-headers", str(CXX_HEADERS), "--renderer", str(host / "fm1-render"),
              "--state-tool", str(host / "fm1-state"), "--out", str(OUTPUT / "build"),
              "--jobs", "4"]
    return make, target


def _selected_capture(command: list[str], *, timeout=600) -> bytes:
    from tools.installer_service.process_capture import run_bounded
    cap = 16 * 1024 * 1024
    result = run_bounded(command, cwd=SOURCE, timeout_seconds=timeout, max_stream_bytes=cap)
    overflow = any(n > cap for n in result.observed.values())
    if overflow or result.failure_reason or result.returncode:
        # Private fixed destination; no stdout leak and no truncated success.
        diagnostic = result.logs["stdout"] + result.logs["stderr"]
        (RESULT / "diagnostic.log").write_bytes(diagnostic[:1024 * 1024])
        raise ValueError("selected command refused: " +
                         ("output_limit" if overflow else result.failure_reason or "nonzero_exit"))
    return result.logs["stdout"]


def verify_selected_imports(source_root: Path) -> None:
    """Reject interpreter module-cache imports outside the extracted source."""
    for name in ("tools.installer_service", "tools.installer_service.process_capture",
                 "tools.jieli.audit_link"):
        module = importlib.import_module(name)
        expected = source_root.joinpath(*name.split("."))
        expected = (expected / "__init__.py" if name == "tools.installer_service"
                    else expected.with_suffix(".py"))
        if (not getattr(module, "__file__", None) or expected.is_symlink() or
                not expected.is_file() or Path(module.__file__).resolve() != expected):
            raise ValueError("selected import is outside extracted source: " + name)


def verify_selected_request(request_bytes: bytes) -> None:
    """Standard-library bootstrap for the one host-validated fixed request.

    The target image need not install the host API's Pydantic dependency. No
    client fields become paths, flags or commands even if this check refuses.
    """
    expected = dict(version=2, profile_id=SELECTED_TRIO_PROFILE, runtime_mode="offline",
                    flash_layout="stock-sized-diagnostic", engines=["trio"], effects=[],
                    midi=[], modulation=[], project_ids=["init-starter-trio"], startup_index=0)
    request = json.loads(request_bytes, object_pairs_hook=_unique_object)
    if isinstance(request, dict) and request.get("set_ids") == []:
        request.pop("set_ids")
    # JSON serialization distinguishes booleans/floats from the strict integer
    # literals, unlike Python's ordinary mapping equality.
    if json.dumps(request, sort_keys=True) != json.dumps(expected, sort_keys=True):
        raise ValueError("unsupported selected worker request")


class SelectedEvidence:
    """Charge every retained byte and entry before acquiring another file."""
    def __init__(self, *, max_bytes=SELECTED_EVIDENCE_CAP, max_files=8192):
        self.max_bytes = max_bytes
        self.max_files = max_files
        self.values: dict[str, bytes] = {}
        self.total = 0

    def remaining(self, name: str) -> int:
        if name in self.values or len(self.values) >= self.max_files:
            raise ValueError("selected evidence exceeds entry bound")
        return self.max_bytes - self.total

    def retain_bytes(self, name: str, raw: bytes) -> None:
        remaining = self.remaining(name)
        if not raw or len(raw) > remaining:
            raise ValueError("selected evidence exceeds byte bound")
        self.values[name] = raw
        self.total += len(raw)

    def retain_file(self, name: str, path: Path, limit: int) -> bytes:
        remaining = self.remaining(name)
        # regular_file checks the actual file size against this remaining
        # budget before opening/reading it. Count refusal also precedes I/O.
        raw = regular_file(path, min(limit, remaining))
        self.retain_bytes(name, raw)
        return raw

    def retain_json(self, name: str, value) -> None:
        remaining = self.remaining(name)
        encoded = bytearray()
        for part in json.JSONEncoder(sort_keys=True).iterencode(value):
            raw = part.encode()
            if len(raw) > remaining - len(encoded):
                raise ValueError("selected evidence exceeds byte bound")
            encoded.extend(raw)
        self.retain_bytes(name, bytes(encoded))


def run_selected_trio(request_bytes: bytes) -> None:
    verify_selected_imports(SOURCE)
    from tools.jieli.audit_link import collect_sources
    verify_selected_request(request_bytes)
    binding_raw = regular_file(INPUT / "host-bindings.json", 4 * 1024 * 1024)
    binding = json.loads(binding_raw, object_pairs_hook=_unique_object)
    if (not isinstance(binding, dict) or binding.get("schema") != 2 or
            binding.get("profile_id") != SELECTED_TRIO_PROFILE or
            binding.get("request_sha256") != hashlib.sha256(request_bytes).hexdigest()):
        raise ValueError("selected host binding differs from request")
    captured = SelectedEvidence()
    captured.retain_bytes("request.json", request_bytes)
    captured.retain_bytes("host-bindings.json", binding_raw)
    before = selected_external_inputs(SOURCE, TOOLCHAIN, TOOLCHAIN_ARCHIVE, CXX_HEADERS)
    host_command, target_command = selected_build_commands()
    host_log = _selected_capture(host_command)
    captured.retain_bytes("host-build.log", host_log or b"\n")
    host = SCRATCH / "host"
    renderer, state = host / "fm1-render", host / "fm1-state"
    renderer_bytes = regular_file(renderer, 64 * 1024 * 1024)
    state_bytes = regular_file(state, 64 * 1024 * 1024)
    metadata = _selected_capture([str(renderer), "--meta"], timeout=90)
    if metadata != _selected_capture([str(state), "meta"], timeout=90) or len(metadata) > 1048576:
        raise ValueError("fixed host tools have mismatched or excessive metadata")
    captured.retain_bytes("metadata.json", metadata)
    version = _selected_capture([str(TOOLCHAIN / "common/bin/clang"), "--version"], timeout=90)
    try:
        _selected_capture(target_command, timeout=1200)
    except BaseException:
        log = OUTPUT / "build/build.log"
        if log.is_file() and not log.is_symlink():
            with log.open("rb") as stream:
                diagnostic = RESULT / "diagnostic.log"
                used = diagnostic.stat().st_size if diagnostic.is_file() else 0
                (RESULT / "failed-build.log").write_bytes(stream.read(SELECTED_EVIDENCE_CAP - used))
        raise
    if selected_external_inputs(SOURCE, TOOLCHAIN, TOOLCHAIN_ARCHIVE, CXX_HEADERS) != before:
        raise ValueError("selected external inputs changed while building")
    if regular_file(renderer, 64 * 1024 * 1024) != renderer_bytes or \
            regular_file(state, 64 * 1024 * 1024) != state_bytes:
        raise ValueError("fresh host tools changed while building")
    build = OUTPUT / "build"
    captured.retain_file("image_receipt.json", build / "receipt.json", SELECTED_RECEIPT_CAP)
    captured.retain_file("build.log", build / "build.log", SELECTED_EVIDENCE_CAP)
    anchors = dict(before, compiler_version=version.decode(), compile_flags=selected_compile_flags(),
                   host_tools=dict(renderer=hashlib.sha256(renderer_bytes).hexdigest(),
                                   state_tool=hashlib.sha256(state_bytes).hexdigest(),
                                   metadata=hashlib.sha256(metadata).hexdigest()),
                   audit_sources=collect_sources([str(SOURCE / "firmware/native"),
                                                 str(SOURCE / "firmware/third_party/dinghy")]))
    captured.retain_json("anchors.json", anchors)
    # Iterate lazily: the entry ceiling must stop acquisition before an
    # unbounded sorted list of output paths or object bytes is constructed.
    for path in build.rglob("*.o"):
        captured.retain_file("objects/" + path.relative_to(build).as_posix(), path, SELECTED_EVIDENCE_CAP)
    for name in ("selected_project.bin", "selected_project_blob.c", "selected_project_blob.h", "receipt.json"):
        captured.retain_file("prepared/" + name, build / "selected_project" / name, SELECTED_RECEIPT_CAP)
    evidence = captured.values
    destination = RESULT / "evidence"
    destination.mkdir(mode=0o700)
    manifest = {}
    for name, raw in evidence.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.write_bytes(raw)
        manifest[name] = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    (destination / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    (RESULT / "app.bin").write_bytes(regular_file(build / "app.bin", MAX_APP))
    (RESULT / "elf.bin").write_bytes(regular_file(build / "lunar-selected-trio.elf", MAX_ELF))
    (RESULT / "image.json").write_bytes(evidence["image_receipt.json"])


def main() -> int:
    request_bytes = regular_file(REQUEST, MAX_REQUEST)
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ValueError("request must be object")
    selected = request.get("version") == 2 and request.get("profile_id") == SELECTED_TRIO_PROFILE
    profile_args = [] if selected else build_profile_arguments(request)
    archive_bytes = regular_file(SOURCE_ARCHIVE, 128 * 1024 * 1024)
    if (not TOOLCHAIN.is_dir() or
            (not selected and not (CATALOGUE / "shard-00/objects.json").is_file()) or
            (selected and (not TOOLCHAIN_ARCHIVE.is_file() or not CXX_HEADERS.is_dir()))):
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
    if selected:
        sys.path.insert(0, str(work))
        run_selected_trio(request_bytes)
        return 0
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

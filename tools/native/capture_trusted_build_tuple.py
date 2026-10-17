#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture strict provenance for an operator-run continuous Shapes8 D7000 link.

This is build evidence only. It does not admit storage, a package, hardware, or
installation. It refuses dirty source trees and mismatched generated receipts.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

from compile_catalogue import optimization_overrides
from build_demo_image import (
    CONTINUOUS_TARGET_STORAGE,
    checked_continuous_midi_input,
    checked_wavetable_profile,
)
from module_selection import wavetable_namespaces

TUPLE_SCHEMA = 2
PROVENANCE_SCHEMA = 1

# Aeon image contract v2. Independently pinned here as well as in the wrapper.
PINNED_TOOLCHAIN_IMAGE = "bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495"
PROFILE_ID = "fm1-092-d7000"
WAVETABLE_PROFILE = "compressed-required-banks-ram-plaits-braids-shapes8-v1"
MAX_JSON = 32 * 1024 * 1024
MAX_APP = 1024 * 1024
MAX_TREE_ENTRIES = 8192
MAX_TREE_BYTES = 512 * 1024 * 1024
_HASH = re.compile(r"^[0-9a-f]{64}$")
GENERATED_FIXED_PATHS = (
    "selection/prepared/fm1_modules.h",
    "selection/prepared/modules/gen/fm1_modules.h",
    "link/gen/fm1_modules.h",
    "link/module-all/gen/fm1_modules.h",
    "link/module-selection/gen/fm1_modules.h",
    "link/wave_tables.json",
    "link/wave_tables.inc",
)
RESOURCE_NAMESPACE_ORDER = ("braids", "plaits")
_WAVETABLE_GENERATOR = r'''import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
output = Path(sys.argv[2]).resolve(strict=True)
namespaces = json.loads(sys.argv[3])
sys.path.insert(0, str(root / "tools/native"))
import prepare_wavetables
import evaluate_wavetables

expected_prepare = (root / "tools/native/prepare_wavetables.py").resolve(strict=True)
expected_evaluate = (root / "tools/native/evaluate_wavetables.py").resolve(strict=True)
if (Path(prepare_wavetables.__file__).resolve(strict=True) != expected_prepare
        or Path(evaluate_wavetables.__file__).resolve(strict=True) != expected_evaluate
        or Path(evaluate_wavetables.ROOT).resolve(strict=True) != root):
    raise SystemExit("wavetable modules escaped captured source root")
rows = prepare_wavetables.prepare(output, namespaces)
sys.stdout.write(json.dumps(rows, separators=(",", ":")))
'''


def _generate_wavetables_from_source(root: Path, output: Path, namespaces):
    """Run the pinned checkout's deterministic generator in an isolated Python."""
    root = Path(root).resolve(strict=True)
    output = Path(output).resolve(strict=True)
    completed = subprocess.run(
        [sys.executable, "-I", "-B", "-c", _WAVETABLE_GENERATOR,
         str(root), str(output), json.dumps(namespaces)],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=60, check=False,
    )
    if completed.returncode != 0 or len(completed.stdout) > 1024 * 1024:
        raise ValueError("captured-source wavetable regeneration failed")
    try:
        rows = json.loads(completed.stdout.decode("utf-8"), object_pairs_hook=_unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("captured-source wavetable generator returned invalid metadata") from error
    if not isinstance(rows, list):
        raise ValueError("captured-source wavetable generator returned invalid metadata")
    expected_files = {"wave_tables.json", "wave_tables.inc"}
    for namespace in namespaces:
        expected_files.update((f"resources_{namespace}.cc", f"resources_{namespace}.h"))
    if {entry.name for entry in output.iterdir()} != expected_files:
        raise ValueError("captured-source wavetable generator emitted an unexpected file set")
    return rows


def _verified_generated_inputs(root: Path, output: Path, prepared, image, verification):
    """Verify only resource banks selected by the digest-bound module profile."""
    module_selection = prepared.get("module_selection")
    if (not isinstance(module_selection, dict)
            or image.get("module_selection") != module_selection
            or verification.get("module_selection") != module_selection):
        raise ValueError("prepared, image and link module selections differ")
    selected = module_selection.get("selected")
    if (not isinstance(selected, list) or not selected
            or any(not isinstance(module, str) or not re.fullmatch(r"[a-z][a-z0-9-]*", module)
                   for module in selected)
            or len(selected) != len(set(selected))):
        raise ValueError("prepared module selection is malformed")
    module_header = read(_safe_rel(output, "selection/prepared/fm1_modules.h"), 65536)
    if module_selection.get("header_sha256") != sha(module_header):
        raise ValueError("prepared module selection does not bind its generated header")

    namespaces = wavetable_namespaces(selected, flash_plaits=False)
    wavetable = checked_wavetable_profile(
        verification, selected, target_storage=CONTINUOUS_TARGET_STORAGE,
        selected_shapes8=True,
    )
    if (image.get("wavetable_profile") != WAVETABLE_PROFILE
            or image.get("compressed_wave_tables") != wavetable["compressed_wave_tables"]
            or image.get("shapes_voices") != 8
            or image.get("flash_plaits_wavetables") is not False):
        raise ValueError("image wavetable metadata differs from the selected linked profile")

    # Regenerate these small deterministic files from the source tree that is
    # later required to be clean and commit-pinned. This checks the no-bank
    # wave_tables.inc/json case too, and prevents an unselected bank from being
    # smuggled into the tuple inventory.
    with tempfile.TemporaryDirectory(prefix="lunar-tuple-wave-") as temporary:
        expected_root = Path(temporary)
        expected_rows = _generate_wavetables_from_source(root, expected_root, namespaces)
        if expected_rows != wavetable["compressed_wave_tables"]:
            raise ValueError("linked wavetable metadata differs from regenerated selected banks")

        expected_resources = {
            f"resources_{namespace}.{suffix}"
            for namespace in namespaces for suffix in ("cc", "h")
        }
        link_dir = output / "link"
        if link_dir.is_symlink() or not link_dir.is_dir():
            raise ValueError("generated link output must be a real directory")
        with os.scandir(link_dir) as entries:
            actual_resources = {
                entry.name for entry in entries
                if re.fullmatch(r"resources_[A-Za-z0-9_-]+\.(?:cc|h)", entry.name)
            }
        if actual_resources != expected_resources:
            raise ValueError("generated resource banks differ from selected module namespaces")

        generated = {
            rel: read(_safe_rel(output, rel), 32 * 1024 * 1024)
            for rel in GENERATED_FIXED_PATHS
            if rel != "link/wave_tables.json" and rel != "link/wave_tables.inc"
        }
        generated["link/wave_tables.json"] = read(_safe_rel(output, "link/wave_tables.json"), 32 * 1024 * 1024)
        generated["link/wave_tables.inc"] = read(_safe_rel(output, "link/wave_tables.inc"), 32 * 1024 * 1024)
        if json.loads(generated["link/wave_tables.json"].decode("utf-8"), object_pairs_hook=_unique) != expected_rows:
            raise ValueError("wave_tables.json differs from regenerated selected bank metadata")
        if generated["link/wave_tables.json"] != (expected_root / "wave_tables.json").read_bytes():
            raise ValueError("wave_tables.json is not the exact generated metadata file")
        if generated["link/wave_tables.inc"] != (expected_root / "wave_tables.inc").read_bytes():
            raise ValueError("wave_tables.inc is not the exact generated table file")

        resource_paths = [f"link/resources_{n}.cc" for n in RESOURCE_NAMESPACE_ORDER if n in namespaces]
        resource_paths += [f"link/resources_{n}.h" for n in RESOURCE_NAMESPACE_ORDER if n in namespaces]
        for rel in resource_paths:
            name = Path(rel).name
            actual = read(_safe_rel(output, rel), 32 * 1024 * 1024)
            if actual != (expected_root / name).read_bytes():
                raise ValueError("generated selected resource differs from pinned source: " + name)
            generated[rel] = actual

    # Preserve the historic all-bank field ordering, so an all-55 capture has
    # identical tuple/provenance bytes when all generated contents are equal.
    paths = [rel for rel in GENERATED_FIXED_PATHS
             if rel not in ("link/wave_tables.json", "link/wave_tables.inc")]
    paths += ["link/wave_tables.json"]
    paths += [f"link/resources_{n}.cc" for n in RESOURCE_NAMESPACE_ORDER if n in namespaces]
    paths += [f"link/resources_{n}.h" for n in RESOURCE_NAMESPACE_ORDER if n in namespaces]
    paths += ["link/wave_tables.inc"]
    generated_rows = [{"path": rel, "sha256": sha(generated[rel])} for rel in paths]
    return generated, generated_rows


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def _tuple_envelope(fields, provenance_sha, source_commit, app_sha, request_sha):
    value = dict(fields)
    value["schema"] = TUPLE_SCHEMA
    value.update({
        "build_provenance_sha256": provenance_sha,
        "tuple_id": "continuous-" + sha((source_commit + app_sha + request_sha).encode("ascii"))[:24],
    })
    return canonical(value)


def read(path: Path, limit=MAX_JSON) -> bytes:
    if path.is_symlink():
        raise ValueError(f"symlink input refused: {path.name}")
    st = path.stat()
    if not path.is_file() or st.st_size > limit:
        raise ValueError(f"invalid or oversized input: {path.name}")
    return path.read_bytes()


def json_obj(path: Path):
    raw = read(path)
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return raw, value


def _unique(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate JSON key: {key}")
        out[key] = value
    return out


def _require_sha(value, label):
    if not isinstance(value, str) or not _HASH.fullmatch(value):
        raise ValueError(f"{label} is not a lowercase SHA-256")


def _verify_selection_receipt(selection, image, request_sha):
    if (type(selection.get("version")) is not int or selection.get("version") != 1
            or selection.get("status") != "prepared-build-inputs"
            or selection.get("prepared_profile_sha256") != image.get("prepared_profile_sha256")
            or selection.get("selected_content") != image.get("selected_content")
            or selection.get("startup_project_id") != image.get("startup_project_id")
            or selection.get("set_ids") != image.get("set_ids")
            or selection.get("request_sha256") != request_sha):
        raise ValueError("selection receipt differs from linked image selection")


def _safe_rel(root: Path, rel: str) -> Path:
    p = PurePosixPath(rel)
    if p.is_absolute() or not p.parts or any(x in ("", ".", "..") for x in p.parts):
        raise ValueError("unsafe relative path in provenance")
    current = root
    for part in p.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink input refused: {rel}")
    if not current.is_file():
        raise ValueError(f"missing regular input: {rel}")
    return current


def _file_sha(path: Path, limit: int):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("invalid or oversized toolchain file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _toolchain_manifest(root: Path):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("toolchain root must be a directory")
    rows = [{"path": ".", "kind": "directory", "mode": root.stat().st_mode & 0o777}]
    total_bytes = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        symlink_dirs = [name for name in dirs if (current_path / name).is_symlink()]
        for name in symlink_dirs:
            link = current_path / name
            resolved = link.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_dir():
                raise ValueError("toolchain symlink directory escapes root")
            rows.append({"path": link.relative_to(root).as_posix(), "kind": "symlink-dir",
                         "target": os.readlink(link),
                         "resolved": resolved.relative_to(root).as_posix(),
                         "mode": link.lstat().st_mode & 0o777})
            dirs.remove(name)
        dirs.sort()
        for name in dirs:
            directory = current_path / name
            rows.append({"path": directory.relative_to(root).as_posix(),
                         "kind": "directory", "mode": directory.stat().st_mode & 0o777})
        for name in sorted(files):
            path = current_path / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    raise ValueError("toolchain symlink file escapes root")
                size = resolved.stat().st_size
                total_bytes += size
                rows.append({"path": rel, "kind": "symlink-file", "target": os.readlink(path),
                             "resolved": resolved.relative_to(root).as_posix(), "bytes": size,
                             "sha256": _file_sha(resolved, 256 * 1024 * 1024),
                             "mode": path.lstat().st_mode & 0o777})
            else:
                if not path.is_file():
                    raise ValueError("toolchain contains a non-regular entry")
                size = path.stat().st_size
                total_bytes += size
                rows.append({"path": rel, "kind": "file", "bytes": size,
                             "sha256": _file_sha(path, 256 * 1024 * 1024),
                             "mode": path.stat().st_mode & 0o777})
            if len(rows) > MAX_TREE_ENTRIES or total_bytes > MAX_TREE_BYTES:
                raise ValueError("tree exceeds the fixed manifest bounds")
    rows.sort(key=lambda row: row["path"])
    return canonical({"schema": 1, "objects": rows})


def _verify_catalogue_subset(tree_raw: bytes, selected_raw: bytes):
    tree = json.loads(tree_raw.decode("ascii"))
    selected = json.loads(selected_raw.decode("ascii"))["objects"]
    if tree.get("schema") != 1 or not isinstance(tree.get("objects"), list):
        raise ValueError("private catalogue snapshot manifest is malformed")
    tree_hashes = {row["path"]: row["sha256"] for row in tree["objects"]
                   if isinstance(row, dict) and row.get("kind") in ("file", "symlink-file")}
    if any(tree_hashes.get(row["path"][len("/catalogue/"):]) != row["sha256"]
           for row in selected):
        raise ValueError("selected catalogue receipt is not a subset of the immutable snapshot")


def _linked_object_manifest(output: Path, catalogue: Path, verification):
    linked = verification.get("linked_objects")
    catalogue_rows = verification.get("catalogue_objects")
    if not isinstance(linked, list) or not linked or len(linked) > 4096:
        raise ValueError("build receipt has no bounded linked object inventory")
    if not isinstance(catalogue_rows, list):
        raise ValueError("build receipt has no catalogue object inventory")
    catalogue_hashes = {}
    for row in catalogue_rows:
        if not isinstance(row, dict) or set(row) not in (
                {"path", "sha256"}, {"path", "sha256", "optimization"}):
            raise ValueError("catalogue receipt rows have an unsupported metadata shape")
        if row["path"] in catalogue_hashes:
            raise ValueError("duplicate catalogue object path")
        catalogue_hashes[row["path"]] = row["sha256"]
    rows = []
    seen = set()
    for row in linked:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("linked object rows must contain path and sha256")
        path, expected = row["path"], row["sha256"]
        if not isinstance(path, str):
            raise ValueError("linked object path is invalid")
        _require_sha(expected, "linked object")
        if path in seen:
            raise ValueError("duplicate linked object path")
        seen.add(path)
        if path.startswith("/catalogue/"):
            if catalogue_hashes.get(path) != expected:
                raise ValueError("linked catalogue object is absent from catalogue receipt")
            local = _safe_rel(catalogue, path[len("/catalogue/"):])
        elif path.startswith("/output/build/link/"):
            suffix = path[len("/output/build/link/"):]
            local = _safe_rel(output, "link/" + suffix)
        else:
            raise ValueError("linked object path is outside the fixed mounts")
        if _file_sha(local, 128 * 1024 * 1024) != expected:
            raise ValueError("linked object bytes differ from the build receipt")
        rows.append({"path": path, "sha256": expected})
    rows.sort(key=lambda row: row["path"])
    return canonical({"schema": 1, "objects": rows})


def _source_manifest(root: Path):
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=True, stdout=subprocess.PIPE, text=True).stdout
    if status:
        raise ValueError("tracked source tree must be clean before tuple capture")
    commit = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
    paths = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True, stdout=subprocess.PIPE).stdout.split(b"\0")
    rows = []
    for item in paths:
        if not item:
            continue
        rel = item.decode("utf-8")
        p = _safe_rel(root, rel)
        rows.append({"path": rel, "sha256": sha(read(p, 128 * 1024 * 1024))})
    rows.sort(key=lambda row: row["path"])
    raw = canonical({"schema": 1, "commit": commit, "objects": rows})
    return commit, raw


def _pinned_source_manifest(root: Path, expected_commit: str, expected_sha256: str):
    commit, manifest = _source_manifest(root)
    if commit != expected_commit:
        raise ValueError("captured source snapshot commit differs before regeneration")
    _require_sha(expected_sha256, "post-build source manifest")
    if sha(manifest) != expected_sha256:
        raise ValueError("captured source snapshot differs before regeneration")
    return commit, manifest


def _catalogue_manifest(catalogue: Path, verification):
    objects = verification.get("catalogue_objects")
    if not isinstance(objects, list) or not objects:
        raise ValueError("build receipt has no catalogue object inventory")
    rows = []
    seen = set()
    row_shape = None
    override_map = verification.get("catalogue_optimization_overrides")
    legacy_rows = "catalogue_optimization_overrides" not in verification
    if override_map is not None and (
            not isinstance(override_map, dict)
            or any(not isinstance(path, str) or not isinstance(opt, str)
                   for path, opt in override_map.items())):
        raise ValueError("catalogue optimization overrides must be an object")
    allowed_maps = {
        tuple(sorted(optimization_overrides("z", hot_dsp_os=hot, limiter_os=limiter,
                                             hall_o2=hall).items()))
        for hot in (False, True) for limiter in (False, True) for hall in (False, True)
    }
    if override_map is not None and tuple(sorted(override_map.items())) not in allowed_maps:
        raise ValueError("catalogue optimization override map is not a supported policy")
    if override_map is not None:
        limiter_flag = verification.get("catalogue_limiter_os")
        hall_flag = verification.get("catalogue_hall_o2")
        if (type(limiter_flag) is not bool or type(hall_flag) is not bool
                or ("our/src/fx_limit.o" in override_map) is not limiter_flag
                or (override_map.get("our/src/fx_hall.o") == "-O2") is not hall_flag):
            raise ValueError("catalogue optimization flags conflict with the override map")
    for row in objects:
        if not isinstance(row, dict) or set(row) not in (
                {"path", "sha256"}, {"path", "sha256", "optimization"}):
            raise ValueError("catalogue receipt rows have an unsupported metadata shape")
        shape = frozenset(row)
        if row_shape is None:
            row_shape = shape
        elif row_shape != shape:
            raise ValueError("catalogue receipt rows must use one consistent schema")
        rel = row["path"]
        if not isinstance(rel, str) or not rel.startswith("/catalogue/"):
            raise ValueError("catalogue object is outside the fixed /catalogue namespace")
        _require_sha(row["sha256"], "catalogue object")
        if rel in seen:
            raise ValueError("duplicate catalogue object path")
        seen.add(rel)
        suffix = rel[len("/catalogue/"):]
        p = _safe_rel(catalogue, suffix)
        if sha(read(p, 128 * 1024 * 1024)) != row["sha256"]:
            raise ValueError(f"catalogue object bytes changed: {PurePosixPath(suffix).name}")
        if "optimization" in row:
            if not isinstance(override_map, dict):
                raise ValueError("optimized catalogue rows require an explicit override map")
            expected_opt = override_map.get(suffix, "-Oz")
            if row["optimization"] not in ("-Oz", "-Os", "-O2") or row["optimization"] != expected_opt:
                raise ValueError("catalogue object optimization differs from the supported policy")
            rows.append({"path": rel, "sha256": row["sha256"], "optimization": row["optimization"]})
        else:
            if not legacy_rows:
                raise ValueError("legacy catalogue rows cannot discard optimization metadata")
            rows.append({"path": rel, "sha256": row["sha256"]})
    rows.sort(key=lambda row: row["path"])
    schema = 2 if row_shape == frozenset({"path", "sha256", "optimization"}) else 1
    raw = canonical({"schema": schema, "objects": rows})
    return raw


def _read_pinned_worker_source(root: Path, worker_source_path: Path) -> bytes:
    expected = root / "tools/native/trusted_continuous_worker.py"
    if worker_source_path.resolve() != expected.resolve():
        raise ValueError("worker source must be the pinned source-snapshot member")
    return read(worker_source_path)


def _verify_inspection_mounts(contract, expected_mounts, container_name: str):
    if contract.get("container_name") != "/" + container_name:
        raise ValueError("container inspection name does not match Docker's exact name")
    normalized_expected = sorted(expected_mounts, key=lambda row: row["destination"])
    if contract.get("mounts") != normalized_expected:
        raise ValueError("container inspection mounts differ from the exact fixed mounts")


def _verify_worker_bindings(invocation, worker_source: bytes, worker_provenance: bytes):
    if invocation.get("worker_sha256") != sha(worker_source):
        raise ValueError("container invocation does not bind worker source bytes")
    if invocation.get("worker_provenance_sha256") != sha(worker_provenance):
        raise ValueError("container invocation does not bind worker provenance bytes")


def _verify_app_receipts(image, artifact, verification, app: bytes, elf: bytes):
    app_sha, elf_sha = sha(app), sha(elf)
    if type(image.get("app_bytes")) is not int or type(artifact.get("app_bytes")) is not int:
        raise ValueError("image/artifact app byte count must be an integer")
    if (image.get("app_sha256"), image.get("app_bytes"), image.get("elf_sha256")) != (app_sha, len(app), elf_sha):
        raise ValueError("image receipt does not bind exact app and ELF bytes")
    if (artifact.get("app_sha256"), artifact.get("app_bytes"), artifact.get("elf_sha256")) != (app_sha, len(app), elf_sha):
        raise ValueError("artifact receipt does not bind exact app and ELF bytes")
    if verification.get("elf_sha256") != elf_sha or len(app) != artifact.get("app_bytes"):
        raise ValueError("build receipt does not bind exact ELF/app length")
    return app_sha, elf_sha


def _false_flags(obj, fields, label):
    for field in fields:
        if obj.get(field) is not False:
            raise ValueError(f"{label} must keep {field}=false")


def _verify_continuous_midi_receipts(image, verification):
    midi = checked_continuous_midi_input(verification)
    if canonical(image.get("native_midi_input")) != canonical(midi):
        raise ValueError("continuous image does not bind the enabled TRS MIDI input")


def capture_trusted_build_tuple(root: Path, catalogue: Path, output: Path, toolchain: Path, *,
                                invocation_path: Path, worker_source_path: Path,
                                worker_provenance_path: Path, wrapper_path: Path):
    root, catalogue, output, toolchain = map(Path, (root, catalogue, output, toolchain))
    invocation_path, worker_source_path, worker_provenance_path, wrapper_path = map(
        Path, (invocation_path, worker_source_path, worker_provenance_path, wrapper_path))
    if output.resolve().is_relative_to(root.resolve()):
        raise ValueError("tuple output must be outside the source checkout")
    if catalogue.is_symlink() or toolchain.is_symlink():
        raise ValueError("catalogue/toolchain root may not be a symlink")

    image_raw, image = json_obj(output / "image.json")
    invocation_raw, invocation = json_obj(invocation_path)
    worker_source_raw = _read_pinned_worker_source(root, worker_source_path)
    worker_raw = read(worker_provenance_path)
    _verify_worker_bindings(invocation, worker_source_raw, worker_raw)
    worker = json.loads(worker_raw.decode("utf-8"), object_pairs_hook=_unique)
    if not isinstance(worker, dict):
        raise ValueError("worker provenance must contain a JSON object")
    toolchain_manifest_path = invocation_path.parent / "toolchain-manifest.json"
    toolchain_manifest_raw = read(toolchain_manifest_path, 16 * 1024 * 1024)
    catalogue_manifest_path = invocation_path.parent / "catalogue-tree-manifest.json"
    catalogue_tree_raw = read(catalogue_manifest_path, 16 * 1024 * 1024)
    if catalogue_tree_raw != _toolchain_manifest(catalogue):
        raise ValueError("private catalogue snapshot differs from captured full manifest")
    if invocation.get("catalogue_snapshot_tree_sha256") != sha(catalogue_tree_raw):
        raise ValueError("invocation does not bind the full private catalogue snapshot")
    if invocation.get("catalogue_snapshot_root") != str(catalogue.resolve()):
        raise ValueError("invocation names a different private catalogue snapshot")
    if not isinstance(invocation.get("catalogue_source_root"), str):
        raise ValueError("invocation lacks the original catalogue source path")
    if invocation.get("catalogue_source_tree_sha256") != sha(catalogue_tree_raw):
        raise ValueError("original catalogue and private snapshot differ")
    if toolchain_manifest_raw != _toolchain_manifest(toolchain):
        raise ValueError("toolchain tree differs from the captured full manifest")
    toolchain_tree_sha = sha(toolchain_manifest_raw)
    if invocation.get("toolchain_tree_sha256") != toolchain_tree_sha:
        raise ValueError("invocation does not bind the full toolchain tree")
    source_commit = invocation.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise ValueError("invocation source commit is not a full immutable SHA")
    if (invocation.get("schema") != 1 or type(invocation.get("schema")) is not int
            or invocation.get("image_id") != "sha256:" + PINNED_TOOLCHAIN_IMAGE
            or invocation.get("exit_code") != 0 or type(invocation.get("exit_code")) is not int
            or invocation.get("hardware_admitted") is not False
            or invocation.get("hardware_tested") is not False
            or invocation.get("installable") is not False):
        raise ValueError("operator invocation receipt is not a successful pinned diagnostic build")
    if (worker.get("source_commit") != invocation.get("source_commit")
            or worker.get("request_sha256") != invocation.get("request_sha256")
            or worker.get("runtime_mode") != "continuous"
            or worker.get("flash_layout") != "expanded-d7000"
            or worker.get("hardware_admitted") is not False
            or worker.get("hardware_tested") is not False
            or worker.get("installable") is not False):
        raise ValueError("worker provenance differs from the fixed continuous build")
    request_raw = read(output / "selection/request.json", 65536)
    request = json.loads(request_raw.decode("utf-8"), object_pairs_hook=_unique)
    prepared_raw, prepared = json_obj(output / "selection/prepared/profile.json")
    source_profile = read(output / "selection/staged/profile.json", 4 * 1024 * 1024)
    selection_raw, selection = json_obj(output / "selection/selection.json")
    build_raw, verification = json_obj(output / "link/verification.json")
    artifact_raw, artifact = json_obj(output / "link/artifact/artifact.json")
    app = read(output / "link/artifact/app.bin", MAX_APP)
    elf = read(output / "link/lunar-app-probe.elf", 32 * 1024 * 1024)

    if type(verification.get("app_budget_bytes")) is not int or len(app) > verification["app_budget_bytes"]:
        raise ValueError("continuous candidate exceeds the linked D7000 app budget")
    runtime = verification.get("runtime_configuration")
    if runtime != {
        "runtime_mode": "continuous",
        "return_to_rom_seconds": None,
        "define": "-DLUNAR_RETURN_TO_ROM_SECONDS=0",
        "release_accepted": False,
    } or image.get("runtime_configuration") != runtime:
        raise ValueError("build did not use the exact continuous runtime policy")
    if verification.get("runtime_policy_sha256") != "fe457ad4056aeb8e6b3ec9df606ac79ab757adc142bd2db9780357fb72f1e905":
        raise ValueError("continuous runtime policy digest is not pinned")
    if verification.get("probe_return_to_rom_seconds") is not None:
        raise ValueError("continuous link unexpectedly has a bounded return timer")
    _verify_continuous_midi_receipts(image, verification)
    if (verification.get("flash_layout") != "expanded-d7000"
            or type(verification.get("app_budget_bytes")) is not int
            or image.get("target_app_storage") is None):
        raise ValueError("build is not the named expanded-D7000 profile")
    if verification.get("shapes_voices") != 8 or image.get("wavetable_profile") != WAVETABLE_PROFILE:
        raise ValueError("build does not use the exact Shapes8 memory profile")
    identity = verification.get("firmware_identity")
    if identity != {
        "application_identity": "FM-1_500",
        "explicit": True,
        "recovery_identity": "FM-1_000",
        "package_identity_verified": False,
        "updater_acceptance_verified": False,
        "hardware_identity_verified": False,
    }:
        raise ValueError("build identity is not explicit FM-1_500 with stock recovery identity")
    _false_flags(verification, ("installable", "hardware_candidate", "hardware_tested"), "build receipt")
    _false_flags(artifact, ("installable", "hardware_admitted", "hardware_tested"), "artifact receipt")
    _false_flags(image, ("installable", "hardware_admitted", "hardware_tested"), "image receipt")
    save = verification.get("project_save_service")
    if not isinstance(save, dict) or save.get("linked") is not True:
        raise ValueError("continuous image must retain the linked disarmed SAVE service")
    _false_flags(save, ("storage_admitted", "flash_io_bound", "save_service_armed",
                        "runtime_verified", "hardware_tested"), "SAVE service receipt")
    _false_flags(image, ("native_ram_verified", "native_playback_verified",
                         "full_song_default_accepted"), "image acceptance receipt")

    source_profile_sha = prepared.get("profile_sha256")
    _require_sha(source_profile_sha, "prepared profile source digest")
    if sha(source_profile) != source_profile_sha:
        raise ValueError("prepared profile does not bind its staged source profile")
    request_sha = sha(request_raw)
    if (request.get("version") != 1 or type(request.get("version")) is not int
            or request_sha != image.get("request_sha256")
            or selection.get("request_sha256") != request_sha):
        raise ValueError("image/selection receipts do not bind exact request bytes")
    _verify_selection_receipt(selection, image, request_sha)
    _false_flags(selection, ("installable", "hardware_tested", "native_link_verified", "native_ram_verified"), "selection receipt")
    if (sha(prepared_raw) != image.get("prepared_profile_sha256")
            or selection.get("prepared_profile_sha256") != sha(prepared_raw)):
        raise ValueError("image receipt does not bind exact prepared profile bytes")
    if image.get("verification_sha256") != sha(build_raw):
        raise ValueError("image receipt does not bind exact build receipt bytes")
    if image.get("artifact_receipt_sha256") != sha(artifact_raw):
        raise ValueError("image receipt does not bind exact artifact receipt bytes")
    app_sha, elf_sha = _verify_app_receipts(image, artifact, verification, app, elf)

    # Pin and prove the exact clean snapshot before executing its generator.
    # The later post-build comparison still catches any change during capture.
    source_commit, source_manifest_raw = _pinned_source_manifest(
        root, invocation.get("source_commit"),
        invocation.get("post_build_source_tree_sha256"),
    )
    source_sha = sha(source_manifest_raw)

    generated, generated_rows = _verified_generated_inputs(
        root, output, prepared, image, verification,
    )
    linked_manifest_raw = _linked_object_manifest(output, catalogue, verification)
    catalogue_raw = _catalogue_manifest(catalogue, verification)
    catalogue_sha = sha(catalogue_raw)
    _verify_catalogue_subset(catalogue_tree_raw, catalogue_raw)
    if invocation.get("post_build_source_tree_sha256") != source_sha:
        raise ValueError("post-build source snapshot differs from the captured source manifest")
    build_sha = sha(build_raw)
    artifact_sha = sha(artifact_raw)
    request_sha = sha(request_raw)
    prepared_sha = sha(prepared_raw)

    if invocation.get("source_commit") != source_commit:
        raise ValueError("container invocation is bound to a different source commit")
    if invocation.get("request_sha256") != request_sha:
        raise ValueError("container invocation is bound to different request bytes")
    if invocation.get("wrapper_sha256") != sha(read(wrapper_path)):
        raise ValueError("container invocation does not bind this host wrapper")
    contract = invocation.get("container_inspection")
    expected_mounts = [
        {"source": str(root.resolve()), "destination": "/workspace", "read_only": True},
        {"source": invocation.get("request_mount_source"), "destination": "/input/request.json", "read_only": True},
        {"source": str(toolchain.resolve()), "destination": "/opt/pi32v2", "read_only": True},
        {"source": str(catalogue.resolve()), "destination": "/catalogue", "read_only": True},
        {"source": str(invocation_path.parent.resolve()), "destination": "/output", "read_only": False},
    ]
    request_mount = invocation.get("request_mount_source")
    if (not isinstance(request_mount, str) or Path(request_mount).parent.resolve() != invocation_path.parent.parent.resolve()
            or Path(request_mount).is_symlink() or Path(request_mount).name in ("", ".", "..")):
        raise ValueError("request bind mount is outside the private output parent")
    if not isinstance(contract, dict):
        raise ValueError("container inspection does not prove successful pinned image completion")
    container_name = invocation.get("container_name")
    command = invocation.get("container_command")
    if not isinstance(container_name, str) or not re.fullmatch(r"lunar-continuous-[0-9a-f]{24}", container_name):
        raise ValueError("container name is not an opaque wrapper-generated identifier")
    _verify_inspection_mounts(contract, expected_mounts, container_name)
    if not isinstance(command, list) or not all(isinstance(item, str) for item in command):
        raise ValueError("container command is not an exact argument vector")
    if invocation.get("container_command_sha256") != sha(canonical(command)):
        raise ValueError("container command digest does not bind its argument vector")
    expected_command = [
        "create", "--name", container_name,
        "--label", "lan.project=lunar-modulator",
        "--label", "lan.session=continuous-tuple-capture",
        "--cgroup-parent=docker-batch.slice", "--network=none",
        "--cpu-quota=400000", "--cpu-period=100000", "--memory=8g",
        "--memory-swap=8g", "--pids-limit=512", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=1003:1003",
        "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=3221225472",
        "--env", "LUNAR_SOURCE_COMMIT=" + source_commit,
    ]
    request_source = invocation.get("request_mount_source")
    expected_command += [
        "--mount", "type=bind,src=" + str(root.resolve()) + ",dst=/workspace,readonly",
        "--mount", "type=bind,src=" + str(request_source) + ",dst=/input/request.json,readonly",
        "--mount", "type=bind,src=" + str(toolchain.resolve()) + ",dst=/opt/pi32v2,readonly",
        "--mount", "type=bind,src=" + str(catalogue.resolve()) + ",dst=/catalogue,readonly",
        "--mount", "type=bind,src=" + str(invocation_path.parent.resolve()) + ",dst=/output",
        "sha256:" + PINNED_TOOLCHAIN_IMAGE, "python3", "/workspace/tools/native/trusted_continuous_worker.py",
    ]
    if command != expected_command:
        raise ValueError("container command differs from fixed operator invocation")
    expected_resources = {
        "network_mode": "none", "cgroup_parent": "docker-batch.slice", "cpus": 4,
        "memory": 8589934592, "memory_swap": 8589934592, "pids_limit": 512,
        "readonly_rootfs": True, "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"], "user": "1003:1003",
        "tmpfs": {"/tmp": "rw,nosuid,nodev,exec,size=3221225472"},
        "labels": {"lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture"},
    }
    if invocation.get("resources") != expected_resources:
        raise ValueError("invocation resource policy differs from fixed limits")
    host = contract.get("host")
    if (contract.get("image") != "sha256:" + PINNED_TOOLCHAIN_IMAGE
            or contract.get("container_id") != invocation.get("container_id")
            or contract.get("config_image") != "sha256:" + PINNED_TOOLCHAIN_IMAGE
            or contract.get("command") != ["python3", "/workspace/" + "tools/native/trusted_continuous_worker.py"]
            or contract.get("user") != "1003:1003"
            or contract.get("labels") != {"project": "lunar-modulator", "session": "gplfu",
                                          "lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture"}
            or contract.get("environment_keys") != ["LUNAR_SOURCE_COMMIT", "PATH"]
            or contract.get("environment_sha256") != sha(canonical([
                "LUNAR_SOURCE_COMMIT=" + source_commit,
                "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
            ]))
            or invocation.get("post_build_source_tree_sha256") is None
            or contract.get("state") != {"status": "exited", "running": False, "exit_code": 0}
            or not isinstance(host, dict)
            or host.get("network_mode") != "none" or host.get("cgroup_parent") != "docker-batch.slice"
            or host.get("readonly_rootfs") is not True or host.get("cpu_quota") != 400000
            or host.get("cpu_period") != 100000 or host.get("nano_cpus") != 0
            or host.get("privileged") is not False or host.get("devices") != []
            or host.get("device_requests") is not None or host.get("cap_add") is not None
            or host.get("pid_mode") != "" or host.get("ipc_mode") != "private"
            or host.get("uts_mode") != "" or host.get("userns_mode") != ""
            or host.get("runtime") != "runc" or host.get("binds") is not None
            or host.get("auto_remove") is not False or host.get("init") is not None
            or host.get("memory") != 8589934592
            or host.get("memory_swap") != 8589934592 or host.get("pids_limit") != 512
            or host.get("cap_drop") != ["ALL"] or host.get("security_opt") != ["no-new-privileges"]
            or host.get("tmpfs") != {"/tmp": "rw,nosuid,nodev,exec,size=3221225472"}
            or contract.get("config_contract") != {
                "entrypoint": None, "working_dir": "", "tty": False,
                "open_stdin": False, "stdin_once": False,
                "attach_stdout": True, "attach_stderr": True,
            }
            or invocation.get("container_inspection_sha256") != sha(canonical(contract))):
        raise ValueError("container inspection differs from the fixed, completed build policy")
    expected_compiler_sha = "42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c"
    candidates = [p for p in toolchain.rglob("clang") if p.is_file() and not p.is_symlink()]
    matching = [p for p in candidates if sha(read(p, 256 * 1024 * 1024)) == expected_compiler_sha]
    if len(matching) != 1:
        raise ValueError("toolchain must contain exactly one compiler matching the pinned pi32v2 digest")
    compiler = matching[0]
    compiler_sha = expected_compiler_sha

    fields = {
        "schema": TUPLE_SCHEMA,
        "profile_id": PROFILE_ID,
        "flash_layout": "expanded-d7000",
        "app_sha256": app_sha,
        "app_bytes": len(app),
        "elf_sha256": elf_sha,
        "application_identity": "FM-1_500",
        "recovery_identity": "FM-1_000",
        "artifact_receipt_sha256": artifact_sha,
        "build_receipt_sha256": build_sha,
        "catalogue_sha256": catalogue_sha,
        "request_sha256": request_sha,
        "prepared_profile_sha256": prepared_sha,
        "source_tree_sha256": source_sha,
        "toolchain_image_sha256": PINNED_TOOLCHAIN_IMAGE,
        "toolchain_tree_sha256": toolchain_tree_sha,
        "runtime_mode": "continuous",
        "hardware_admitted": False,
        "hardware_tested": False,
        "installable": False,
    }
    provenance = dict(fields)
    provenance["schema"] = PROVENANCE_SCHEMA  # independent sidecar contract
    provenance.update({
        "source_commit": source_commit,
        "toolchain_image_id": "sha256:" + PINNED_TOOLCHAIN_IMAGE,
        "container_invocation_sha256": sha(invocation_raw),
        "worker_provenance_sha256": sha(worker_raw),
        "worker_sha256": invocation.get("worker_sha256"),
        "wrapper_sha256": invocation.get("wrapper_sha256"),
        "state_tool_sha256": invocation.get("state_tool_sha256"),
        "toolchain_root": str(toolchain.resolve()),
        "compiler_path": str(compiler.resolve()),
        "compiler_sha256": compiler_sha,
        "toolchain_tree_sha256": toolchain_tree_sha,
        "linked_object_manifest_sha256": sha(linked_manifest_raw),
        "linked_object_count": len(json.loads(linked_manifest_raw)["objects"]),
        "linked_objects": json.loads(linked_manifest_raw)["objects"],
        "catalogue_container_mount": "/catalogue",
        "catalogue_source_root": invocation.get("catalogue_source_root"),
        "catalogue_snapshot_root": str(catalogue.resolve()),
        "catalogue_tree_sha256": sha(catalogue_tree_raw),
        "catalogue_manifest_path": str((output / "catalogue-manifest.json").resolve()),
        "request_receipt_sha256": request_sha,
        "prepared_profile_receipt_sha256": prepared_sha,
        "module_and_generated_inputs": generated_rows,
        "generated_link_resources": generated_rows,
        "embedded_content": image.get("embedded_content"),
        "instance_pool_bytes": verification.get("instance_pool_bytes"),
        "shapes_voices": 8,
    })
    provenance_raw = canonical(provenance)
    provenance_sha = sha(provenance_raw)
    tuple_raw = _tuple_envelope(fields, provenance_sha, source_commit, app_sha, request_sha)

    # Capture must never overwrite; callers receive immutable sidecars.
    outputs = {
        "source-tree-manifest.json": source_manifest_raw,
        "catalogue-manifest.json": catalogue_raw,
        "build-provenance.json": provenance_raw,
        "build_tuple.json": tuple_raw,
    }
    for name in outputs:
        dest = output / name
        if dest.exists() or dest.is_symlink():
            raise ValueError(f"refusing to overwrite tuple sidecar: {name}")
    for name, raw in outputs.items():
        dest = output / name
        fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb", closefd=True) as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            dest.unlink(missing_ok=True)
            raise
    capture = {
        "schema": 1,
        "tuple_sha256": sha(tuple_raw),
        "provenance_sha256": provenance_sha,
        "catalogue_sha256": catalogue_sha,
        "source_tree_sha256": source_sha,
        "source_commit": source_commit,
        "compiler_sha256": compiler_sha,
        "toolchain_image_sha256": PINNED_TOOLCHAIN_IMAGE,
        "hardware_admitted": False,
        "hardware_tested": False,
        "installable": False,
    }
    capture_path = output / "tuple-capture.json"
    fd = os.open(capture_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb", closefd=True) as stream:
        stream.write(canonical(capture))
        stream.flush()
        os.fsync(stream.fileno())
    return capture

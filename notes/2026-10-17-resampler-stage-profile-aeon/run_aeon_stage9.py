#!/usr/bin/env python3
"""Prepare one private frozen EH+SET schema-7/schema-9 profiling configuration.

This helper performs a fresh 16-shard catalogue (four concurrent) compile followed by one bounded
application link. The optional schema-9 mode also enables IRQ profiling; controls differ by that
explicit package-level flag pair. It never contacts hardware and never creates a package.
Inputs and outputs are private, manifest-bound evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

PINNED_IMAGE = "sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495"
MAX_ENTRIES = 8192
MAX_TREE_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024
CATALOGUE_TIMEOUT_S = 1800
LINK_TIMEOUT_S = 1200
SHARDS = 16
CLAIM = Path("/home/claude/.local/share/codex-coordination/claims/lunar--resampler-stage-profile-aeon-20261017-codex")
REQUIRED_EXPERIMENT_SOURCES = (
    "sim/web/src/fm1_postmix.h", "engines/include/engine_render_profile.h",
    "engines/include/fm1_resampler.h",
    "firmware/third_party/dinghy/src/platform.c", "firmware/native/app_probe.c",
    "firmware/native/diagnostic_telemetry.h",
)


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    temporary.write_bytes(canonical(value) + b"\n")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def compiler_source_manifest(source: Path) -> dict:
    module_path = source / "tools/native/compile_catalogue.py"
    spec = importlib.util.spec_from_file_location("hot_ram_compile_catalogue", module_path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load source-bound catalogue manifest function")
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module.source_manifest(source)


def tree_manifest(root: Path) -> bytes:
    if root.is_symlink():
        raise ValueError("manifest root must not be a symlink")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("manifest root must be a real directory")
    rows = [{"path": ".", "kind": "directory", "mode": root.stat().st_mode & 0o777}]
    total = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        for name in sorted(list(dirs)):
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = path.resolve(strict=True)
                if not target.is_relative_to(root) or not target.is_dir():
                    raise ValueError("directory symlink escapes or is invalid")
                rows.append({"path": rel, "kind": "symlink-dir", "target": os.readlink(path),
                             "resolved": target.relative_to(root).as_posix(),
                             "mode": path.lstat().st_mode & 0o777})
                dirs.remove(name)
            else:
                rows.append({"path": rel, "kind": "directory", "mode": path.stat().st_mode & 0o777})
        for name in sorted(files):
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                target = path.resolve(strict=True)
                if not target.is_relative_to(root) or not target.is_file():
                    raise ValueError("file symlink escapes or is invalid")
                size, digest_path, kind = target.stat().st_size, target, "symlink-file"
                target_text = os.readlink(path)
            else:
                if not path.is_file():
                    raise ValueError("tree contains non-regular entry")
                size, digest_path, kind, target_text = path.stat().st_size, path, "file", None
            if size > MAX_FILE_BYTES:
                raise ValueError("tree file exceeds manifest bound")
            total += size
            row = {"path": rel, "kind": kind, "bytes": size,
                   "sha256": sha_file(digest_path), "mode": path.lstat().st_mode & 0o777}
            if target_text is not None:
                row["target"] = target_text
            rows.append(row)
            if len(rows) > MAX_ENTRIES or total > MAX_TREE_BYTES:
                raise ValueError("tree exceeds bounded manifest")
    rows.sort(key=lambda row: row["path"])
    return canonical({"schema": 1, "objects": rows})


def copy_tree_verified(source: Path, destination: Path) -> bytes:
    before = tree_manifest(source)
    shutil.copytree(source, destination, symlinks=True, copy_function=shutil.copy2)
    copied = tree_manifest(destination)
    if before != copied or tree_manifest(source) != before:
        raise ValueError(f"copy did not preserve a stable tree: {source}")
    return copied


def archive_source(checkout: Path, commit: str, destination: Path) -> tuple[str, bytes]:
    if checkout.is_symlink():
        raise ValueError("checkout must not be a symlink")
    checkout = checkout.resolve(strict=True)
    if not checkout.is_dir():
        raise ValueError("checkout must be a real directory")
    head = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if head != commit:
        raise ValueError("checkout HEAD differs from requested exact commit")
    subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "HEAD", "--"], check=True)
    subprocess.run(["git", "-C", str(checkout), "diff", "--cached", "--quiet"], check=True)
    status = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True).splitlines()
    if status:
        raise ValueError("source checkout must be clean, including untracked files")
    tree = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD^{tree}"], text=True).strip()
    archive = subprocess.Popen(["git", "-C", str(checkout), "archive", "--format=tar", commit],
                               stdout=subprocess.PIPE)
    assert archive.stdout is not None
    try:
        with tarfile.open(fileobj=archive.stdout, mode="r|") as tar:
            tar.extractall(destination, filter="data")
    finally:
        archive.stdout.close()
    if archive.wait() != 0:
        raise ValueError("git archive failed")
    return tree, tree_manifest(destination)


def require_real_directory(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError(f"{label} must be a real directory")
    return resolved


def require_real_file(path: Path, label: str) -> Path:
    if path.is_symlink():
        raise ValueError(f"{label} must not be a symlink")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError(f"{label} must be a real file")
    return resolved


def catalogue_args(shard: int, resampler_stage_profile: bool) -> list[str]:
    if type(shard) is not int or not 0 <= shard < SHARDS:
        raise ValueError("shard must be an integer from 0 to 15")
    return ["python3", "tools/native/compile_catalogue.py",
            "--toolchain", "/toolchain", "--cxx-headers", "/headers",
            "--out", f"/out/shard-{shard:02d}", "--shard", str(shard),
            "--opt", "z", "--lto", "--shared-resampler", "--shapes-voices", "8",
            "--indexed-tft", "--hot-dsp-os", "--hot-dsp-ram", "--engine-render-profile", "--hall-o2"] + (
            ["--resampler-stage-profile"] if resampler_stage_profile else [])


def link_args(profile_sha256: str, resampler_stage_profile: bool) -> list[str]:
    if len(profile_sha256) != 64 or any(c not in "0123456789abcdef" for c in profile_sha256):
        raise ValueError("profile SHA-256 must be lowercase hexadecimal")
    return ["python3", "tools/native/build_application_probe.py",
            "--toolchain", "/toolchain", "--catalogue", "/catalogue",
            "--build", "/out/build", "--prepared-profile", "/prepared",
            "--expected-profile-sha256", profile_sha256,
            "--firmware-identity", "FM-1_500", "--runtime-mode", "song-diagnostic",
            "--stack-watermark", "--flash-layout", "expanded-d7000",
            "--link-project-save-service", "--shapes-voices", "8", "--indexed-tft",
            "--compressed-wavetables", "--enable-trs-midi", "--diagnostic-telemetry",
            "--render-stage-profile", "--link-project-loader",
            "--link-set-loader", "--hot-dsp-os", "--hot-dsp-ram",
            "--diagnostic-clock-snapshot", "--diagnostic-engine-render-profile", "--hall-o2",
            "--startup-project-index", "0"] + (["--diagnostic-irq-profile", "--diagnostic-resampler-stage-profile"]
                                                  if resampler_stage_profile else [])


def validate_engine_render_profile_receipt(receipt) -> None:
    """Require the exact schema-7 per-engine render diagnostic opt-in."""
    expected = {
        "enabled": True, "schema": 7,
        "compile_definition": "LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1",
        "frame_bytes": 54, "packets_per_frame": 18,
        "counters": ["uptime_ms", "drums_render_ticks", "drums_render_calls",
                     "drums_render_block_ticks", "drums_render_block_calls",
                     "sixop_render_ticks", "sixop_render_calls",
                     "sixop_render_block_ticks", "sixop_render_block_calls"],
        "counter_semantics": "cumulative-uint32-device-timer-ticks",
        "hardware_tested": False,
    }
    if receipt != expected:
        raise ValueError("verification receipt lacks the exact enabled schema-7 engine-render-profile configuration")


def validate_engine_render_profile_verification(verification: dict, resampler_stage_profile: bool) -> None:
    """Pin no-autoplay and all required opt-in receipts for this diagnostic build."""
    expected_disabled_play = {
        "enabled": False, "compile_definition": None, "start_ms": None,
        "once": False, "hardware_tested": False,
    }
    if (verification.get("runtime_configuration", {}).get("runtime_mode") != "song-diagnostic"
            or verification.get("diagnostic_song_play") != expected_disabled_play
            or "diagnostic_producer_gaps" in verification):
        raise ValueError("profile build must be song-diagnostic with autoplay and producer-gap modes disabled")
    if resampler_stage_profile:
        stage = verification.get("diagnostic_resampler_stage_profile", {})
        irq = verification.get("diagnostic_irq_profile", {})
        if (stage.get("enabled") is not True or stage.get("schema") != 9
                or irq.get("enabled") is not True or irq.get("schema") != 6):
            raise ValueError("schema-9 build lacks enabled resampler and IRQ receipts")
    elif ("diagnostic_resampler_stage_profile" in verification or
          "diagnostic_irq_profile" in verification):
        raise ValueError("schema-7 control unexpectedly includes IRQ or resampler-stage profiles")
    validate_engine_render_profile_receipt(verification.get("diagnostic_engine_render_profile"))
    if (verification.get("catalogue_hall_o2") is not True
            or verification.get("catalogue_optimization_overrides") != {
                "our/src/mi_sixop.o": "-Os", "our/src/fx_hall.o": "-O2"}):
        raise ValueError("linked verification must prove Hall O2 and the exact two catalogue overrides")
    if (verification.get("hot_dsp_ram", {}).get("enabled") is not True
            or verification.get("diagnostic_telemetry", {}).get("enabled") is not True
            or verification.get("render_stage_profile", {}).get("enabled") is not True
            or verification.get("diagnostic_clock_snapshot", {}).get("enabled") is not True
            or verification.get("project_save_service", {}).get("save_service_armed") is not False
            or verification.get("hardware_tested") is not False
            or verification.get("installable") is not False):
        raise ValueError("verification receipt lacks required diagnostics or false readiness flags")

def validate_shard(shard: int, report: dict, objects: list[str], expected_objects: list[str] | None,
                   expected_manifest: dict | None, resampler_stage_profile: bool) -> tuple[list[str], dict]:
    required = {"shard": shard, "chunks": SHARDS, "gpl_mods": 1, "modules": "all",
                "closed_sdk_archives": [], "optimization": "-Oz", "lto": True,
                "optimization_overrides": {"our/src/mi_sixop.o": "-Os",
                                            "our/src/fx_hall.o": "-O2"},
                "shared_resampler": True, "indexed_tft": True, "shapes_voices": 8,
                "hot_dsp_ram": True, "engine_render_profile": True,
                "resampler_stage_profile": resampler_stage_profile,
                "device_sdk_headers": [], "firmware_linked": False,
                "hardware_tested": False}
    if any(report.get(key) != value for key, value in required.items()):
        raise ValueError(f"shard-{shard:02d} report settings mismatch")
    if not isinstance(objects, list) or not objects or any(not isinstance(x, str) for x in objects):
        raise ValueError("catalogue object list is malformed")
    if expected_objects is not None and objects != expected_objects:
        raise ValueError("catalogue object lists differ between shards")
    manifest = report.get("source_manifest")
    if not isinstance(manifest, dict) or (expected_manifest is not None and manifest != expected_manifest):
        raise ValueError("catalogue source manifest missing or inconsistent")
    results = report.get("results")
    if not isinstance(results, list):
        raise ValueError("catalogue results missing")
    indexes = set()
    for row in results:
        if not isinstance(row, dict):
            raise ValueError("catalogue result row malformed")
        index = row.get("index")
        if (type(index) is not int or index % SHARDS != shard or index in indexes
                or not 0 <= index < len(objects) or row.get("object") != objects[index]
                or row.get("exit") != 0 or row.get("optimization") != required["optimization_overrides"].get(
                    objects[index], "-Oz")):
            raise ValueError(f"catalogue result invalid at shard {shard} index {index}")
        if (not isinstance(row.get("sha256"), str) or len(row["sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in row["sha256"])):
            raise ValueError("catalogue object hash missing or malformed")
        indexes.add(index)
    expected_indexes = set(range(shard, len(objects), SHARDS))
    if indexes != expected_indexes:
        raise ValueError(f"catalogue shard {shard} is incomplete")
    return objects, manifest


def docker_image_inspect(docker: str) -> dict:
    rows = json.loads(subprocess.check_output([docker, "image", "inspect", PINNED_IMAGE]))
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("Id") != PINNED_IMAGE:
        raise ValueError("pinned Docker image identity mismatch")
    return rows[0]


def create_inspect_run(*, docker: str, name: str, labels: dict, source: Path,
                       toolchain: Path, headers: Path, catalogue: Path | None,
                       prepared: Path | None, selection: Path | None, out: Path,
                       command: list[str], cpu_quota: int, memory: str, memory_swap: str,
                       timeout_s: int, log_path: Path, evidence_path: Path) -> dict:
    mounts = [("/workspace", source), ("/toolchain", toolchain), ("/headers", headers)]
    if catalogue is not None:
        mounts.append(("/catalogue", catalogue))
    if prepared is not None:
        mounts.extend([("/prepared", prepared), ("/selection.json", selection)])
    mounts.append(("/out", out))
    args = [docker, "create", "--name", name]
    for key, value in sorted(labels.items()):
        args += ["--label", f"{key}={value}"]
    args += ["--cgroup-parent=docker-batch.slice", "--network=none",
             "--cpu-quota", str(cpu_quota), "--cpu-period", "100000",
             "--memory", memory, "--memory-swap", memory_swap, "--pids-limit", "256",
             "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
             "--user=1003:1003", "--workdir=/workspace", "--tmpfs",
             "/tmp:rw,nosuid,nodev,exec,size=1073741824"]
    for destination, host_path in mounts:
        if host_path is None:
            raise ValueError("selection mount is missing")
        readonly = destination != "/out"
        args += ["--mount", f"type=bind,src={host_path},dst={destination}" +
                 (",readonly" if readonly else "")]
    args += [PINNED_IMAGE, *command]
    cid = subprocess.check_output(args, text=True).strip()
    try:
        atomic_json(evidence_path, {"id": cid, "name": name, "phase": "created"})
        inspected = json.loads(subprocess.check_output([docker, "inspect", cid]))[0]
        host, config = inspected["HostConfig"], inspected["Config"]
        expected_mounts = {dst: str(path) for dst, path in mounts}
        actual_mounts = {row["Destination"]: row["Source"] for row in inspected.get("Mounts", [])}
        expected_labels = {"project": "lunar-modulator", "session": "gplfu", **labels}
        states = inspected.get("State", {})
        expected_mem = int(memory[:-1]) * 1024**3
        expected_swap = int(memory_swap[:-1]) * 1024**3
        checks = [
            inspected.get("Image") == PINNED_IMAGE,
            config.get("Image", PINNED_IMAGE) == PINNED_IMAGE,
            config.get("Cmd") == command,
            config.get("Labels") == expected_labels,
            config.get("Entrypoint") in (None, []),
            config.get("WorkingDir") == "/workspace",
            config.get("User") == "1003:1003",
            states.get("Status") == "created" and states.get("Running") is False,
            host.get("NetworkMode") == "none",
            host.get("CgroupParent") == "docker-batch.slice",
            host.get("CpuQuota") == cpu_quota and host.get("CpuPeriod") == 100000,
            host.get("Memory") == expected_mem and host.get("MemorySwap") == expected_swap,
            host.get("PidsLimit") == 256 and host.get("ReadonlyRootfs") is True,
            host.get("SecurityOpt") == ["no-new-privileges"],
            host.get("Tmpfs") == {"/tmp": "rw,nosuid,nodev,exec,size=1073741824"},
            host.get("Privileged") is False and host.get("Devices") == [],
            host.get("CapDrop") == ["ALL"], actual_mounts == expected_mounts,
            len(inspected.get("Mounts", [])) == len(mounts),
            all(row.get("RW") is (row["Destination"] == "/out")
                for row in inspected.get("Mounts", [])),
        ]
        inspect_record = {"id": cid, "name": name, "image": inspected.get("Image"),
                          "prestart_inspect": inspected, "prestart_policy_match": all(checks),
                          "state_before_start": states.get("Status")}
        atomic_json(evidence_path, inspect_record)
        if not all(checks):
            raise ValueError(f"container {name} inspect did not match bounded build policy")
        inspect_record = {"id": cid, "name": name, "image": inspected["Image"],
                          "prestart_inspect": inspected, "prestart_policy_match": True,
                          "command": command, "labels": labels, "cpu_quota": cpu_quota,
                          "memory_bytes": host["Memory"], "memory_swap_total_bytes": host["MemorySwap"],
                          "network": host["NetworkMode"], "cgroup_parent": host["CgroupParent"],
                          "readonly_rootfs": host["ReadonlyRootfs"], "mounts": expected_mounts}
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with log_path.open("wb") as log:
                proc = subprocess.run([docker, "start", "--attach", cid], stdout=log,
                                      stderr=subprocess.STDOUT, check=False, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = json.loads(subprocess.check_output([docker, "inspect", cid]))[0]
            atomic_json(evidence_path, {**inspect_record, "postrun_inspect": timed_out,
                                        "timed_out": True})
            raise
        final = json.loads(subprocess.check_output([docker, "inspect", cid]))[0]
        inspect_record["postrun_inspect"] = final
        inspect_record["process_returncode"] = proc.returncode
        atomic_json(evidence_path, inspect_record)
        if proc.returncode != 0 or final.get("State", {}).get("ExitCode") != 0:
            raise ValueError(f"container {name} failed; inspect {log_path} and {evidence_path}")
        inspect_record["exit_code"] = final["State"].get("ExitCode")
        return inspect_record
    finally:
        subprocess.run([docker, "rm", "-f", cid], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False, timeout=60)


def run_build(args):
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("Docker CLI unavailable")
    if sys.platform != "linux" or not (CLAIM / "owner.md").is_file():
        raise ValueError("Aeon Linux and the acquired task claim are required")
    commit = args.commit
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("--commit must be a full lowercase Git SHA")
    for pin in (args.expected_profile_sha256, args.expected_selection_sha256):
        if len(pin) != 64 or any(character not in "0123456789abcdef" for character in pin):
            raise ValueError("expected profile and selection pins must be lowercase SHA-256 hex")

    if args.output.is_symlink():
        raise ValueError("output path must not be a symlink")
    output = args.output.resolve()
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    snapshots = output / "snapshots"
    snapshots.mkdir(mode=0o700)
    source = snapshots / "source"
    source.mkdir(mode=0o700)
    source_tree, source_manifest = archive_source(args.checkout, commit, source)
    for relative in REQUIRED_EXPERIMENT_SOURCES:
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"exact source commit lacks required experiment input: {relative}")
    toolchain_source = require_real_directory(args.toolchain, "toolchain")
    headers_source = require_real_directory(args.headers, "C++ headers")
    profile_source = require_real_directory(args.prepared_profile, "prepared profile")
    selection_source = require_real_file(args.selection, "selection receipt")
    if not (profile_source / "profile.json").is_file() or (profile_source / "profile.json").is_symlink():
        raise ValueError("prepared profile lacks regular profile.json")
    if sha_file(profile_source / "profile.json") != args.expected_profile_sha256:
        raise ValueError("prepared profile hash does not match external pin")
    if sha_file(selection_source) != args.expected_selection_sha256:
        raise ValueError("selection receipt hash does not match external pin")

    toolchain = snapshots / "toolchain"
    headers = snapshots / "headers"
    prepared = snapshots / "prepared"
    selection = snapshots / "selection.json"
    toolchain_source_manifest = tree_manifest(toolchain_source)
    headers_source_manifest = tree_manifest(headers_source)
    prepared_source_manifest = tree_manifest(profile_source)
    toolchain_manifest = copy_tree_verified(toolchain_source, toolchain)
    headers_manifest = copy_tree_verified(headers_source, headers)
    prepared_manifest = copy_tree_verified(profile_source, prepared)
    shutil.copy2(selection_source, selection)
    selection.chmod(0o444)
    selection_manifest = sha_file(selection)
    if selection_manifest != args.expected_selection_sha256:
        raise ValueError("selection copy differs from external pin")
    image_inspect = docker_image_inspect(docker)
    compiler_manifest = compiler_source_manifest(source)
    input_records = {
        "schema": 1, "source_commit": commit, "source_git_tree": source_tree,
        "source_tree_manifest_sha256": sha_bytes(source_manifest),
        "compiler_source_manifest_sha256": sha_bytes(canonical(compiler_manifest)),
        "toolchain_source_tree_manifest_sha256": sha_bytes(toolchain_source_manifest),
        "toolchain_snapshot_tree_manifest_sha256": sha_bytes(toolchain_manifest),
        "headers_source_tree_manifest_sha256": sha_bytes(headers_source_manifest),
        "headers_snapshot_tree_manifest_sha256": sha_bytes(headers_manifest),
        "prepared_profile_sha256": args.expected_profile_sha256,
        "prepared_source_tree_manifest_sha256": sha_bytes(prepared_source_manifest),
        "prepared_snapshot_tree_manifest_sha256": sha_bytes(prepared_manifest),
        "selection_sha256": selection_manifest,
        "docker_image_id": PINNED_IMAGE,
        "docker_image_inspect_sha256": sha_bytes(canonical(image_inspect)),
    }
    atomic_json(output / "input-snapshots.json", input_records)
    for name, raw in (("source-tree-manifest.json", source_manifest),
                      ("toolchain-tree-manifest.json", toolchain_manifest),
                      ("headers-tree-manifest.json", headers_manifest),
                      ("prepared-tree-manifest.json", prepared_manifest)):
        target = output / name
        target.write_bytes(raw)
        target.chmod(0o600)

    # Catalogue outputs are isolated per shard. The bind-mounted parent exists,
    # while compile_catalogue creates its unique child with exist_ok=False.
    stage_parent = output / "catalogue-stage"
    stage_parent.mkdir(mode=0o777)
    os.chmod(stage_parent, 0o777)
    os.chown(stage_parent, 1003, 1003)
    for shard in range(SHARDS):
        (stage_parent / f"shard-{shard:02d}").mkdir(mode=0o777)
        shutil.rmtree(stage_parent / f"shard-{shard:02d}")
    common = dict(docker=docker, source=source, toolchain=toolchain, headers=headers,
                 catalogue=None, prepared=None, selection=None)
    run_id = uuid.uuid4().hex[:10]

    def build_shard(shard: int):
        out = stage_parent
        command = catalogue_args(shard, args.resampler_stage_profile)
        labels = {"lan.project": "lunar-modulator", "lan.task": "resampler-stage-profile-catalogue",
                  "lan.session": "resampler-stage-profile-" + run_id, "lan.shard": f"{shard:02d}"}
        result = create_inspect_run(
            **common, out=out, name=f"lunar-resampler-stage-profile-cat-{run_id}-{shard:02d}",
            labels=labels, command=command, cpu_quota=200000,
            memory="2g", memory_swap="2g", timeout_s=CATALOGUE_TIMEOUT_S,
            log_path=output / "catalogue-logs" / f"shard-{shard:02d}.log",
            evidence_path=output / "container-evidence" / f"shard-{shard:02d}.json")
        result["shard"] = shard
        return result

    shard_runs = [None] * SHARDS
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(build_shard, shard): shard for shard in range(SHARDS)}
        for future in as_completed(futures):
            shard = futures[future]
            try:
                shard_runs[shard] = future.result()
            except Exception as error:
                errors.append(f"shard {shard}: {error}")
    if errors:
        raise ValueError("catalogue compile failed: " + "; ".join(errors))

    catalogue = output / "catalogue"
    catalogue.mkdir(mode=0o777)
    os.chmod(catalogue, 0o777)
    os.chown(catalogue, 1003, 1003)
    expected_objects = None
    shard_receipts = []
    for shard in range(SHARDS):
        stage = stage_parent / f"shard-{shard:02d}"
        report = json.loads((stage / "report.json").read_text())
        objects = json.loads((stage / "objects.json").read_text())
        expected_objects, shard_manifest = validate_shard(
            shard, report, objects, expected_objects, compiler_manifest, args.resampler_stage_profile)
        if shard_manifest != compiler_manifest:
            raise ValueError("catalogue shard source manifest differs from archived compiler inputs")
        shutil.move(str(stage), str(catalogue / f"shard-{shard:02d}"))
        shard_receipts.append({"shard": shard, "report_sha256": sha_file(catalogue / f"shard-{shard:02d}/report.json"),
                              "objects_sha256": sha_file(catalogue / f"shard-{shard:02d}/objects.json"),
                              "container": shard_runs[shard]})
    if compiler_source_manifest(source) != compiler_manifest:
        raise ValueError("archived compiler source manifest changed during shard builds")
    catalogue_manifest = tree_manifest(catalogue)
    catalogue_manifest_path = output / "catalogue-tree-manifest.json"
    catalogue_manifest_path.write_bytes(catalogue_manifest)
    catalogue_manifest_path.chmod(0o600)

    build_parent = output / "writable-output"
    build_parent.mkdir(mode=0o777)
    os.chmod(build_parent, 0o777)
    os.chown(build_parent, 1003, 1003)
    command = link_args(args.expected_profile_sha256, args.resampler_stage_profile)
    labels = {"lan.project": "lunar-modulator", "lan.task": "resampler-stage-profile-eh-set-link",
              "lan.session": "resampler-stage-profile-" + run_id}
    link_container = create_inspect_run(
        docker=docker, name=f"lunar-resampler-stage-profile-link-{run_id}", labels=labels,
        source=source, toolchain=toolchain, headers=headers, catalogue=catalogue,
        prepared=prepared, selection=selection, out=build_parent, command=command,
        cpu_quota=400000, memory="4g", memory_swap="4g", timeout_s=LINK_TIMEOUT_S,
        log_path=output / "link.log",
        evidence_path=output / "container-evidence" / "link.json")

    # The builder performs the authoritative firmware/profile audits. This
    # runner adds output existence/hash binding and repeats input snapshot checks.
    if (tree_manifest(source) != source_manifest or tree_manifest(toolchain) != toolchain_manifest
            or tree_manifest(headers) != headers_manifest or tree_manifest(catalogue) != catalogue_manifest
            or tree_manifest(prepared) != prepared_manifest or sha_file(selection) != selection_manifest
            or tree_manifest(toolchain_source) != toolchain_source_manifest
            or tree_manifest(headers_source) != headers_source_manifest
            or tree_manifest(profile_source) != prepared_source_manifest
            or sha_file(selection_source) != args.expected_selection_sha256):
        raise ValueError("an input changed during frozen build")

    build = build_parent / "build"
    artifact = build / "artifact"
    required_outputs = [build / "lunar-app-probe.elf", build / "lunar-app-probe.map",
                        build / "verification.json", build / "ram-text.txt",
                        build / "ram-dsp.txt", build / "ram-call-audit.json",
                        build / "sections.txt", artifact / "app.bin",
                        artifact / "artifact.json", artifact / "disassembly.txt"]
    for path in required_outputs:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing required hot-RAM link evidence: {path.name}")
    verification = json.loads((build / "verification.json").read_text())
    validate_engine_render_profile_verification(verification, args.resampler_stage_profile)
    output_hashes = {str(path.relative_to(output)): sha_file(path) for path in required_outputs}
    receipt = {
        "schema": 1, "purpose": ("private EH+SET hot-DSP-RAM schema-9 resampler + IRQ diagnostic build; no autoplay"
                                if args.resampler_stage_profile else
                                "private EH+SET hot-DSP-RAM schema-7 engine-render diagnostic control; no autoplay"),
        "profile_flags": {"diagnostic_resampler_stage_profile": args.resampler_stage_profile,
                          "diagnostic_irq_profile": args.resampler_stage_profile,
                          "catalogue_resampler_stage_profile": args.resampler_stage_profile},
        "source_commit": commit, "source_git_tree": source_tree,
        "source_tree_manifest_sha256": sha_bytes(source_manifest),
        "toolchain_source_path": str(toolchain_source),
        "toolchain_source_tree_manifest_sha256": sha_bytes(toolchain_source_manifest),
        "toolchain_snapshot_tree_manifest_sha256": sha_bytes(toolchain_manifest),
        "headers_source_tree_manifest_sha256": sha_bytes(headers_source_manifest),
        "headers_snapshot_tree_manifest_sha256": sha_bytes(headers_manifest),
        "prepared_profile_sha256": args.expected_profile_sha256,
        "prepared_source_tree_manifest_sha256": sha_bytes(prepared_source_manifest),
        "prepared_snapshot_tree_manifest_sha256": sha_bytes(prepared_manifest),
        "selection_sha256": selection_manifest,
        "catalogue_source_manifest_sha256": sha_bytes(canonical(compiler_manifest)),
        "catalogue_snapshot_tree_manifest_sha256": sha_bytes(catalogue_manifest),
        "catalogue_shards": shard_receipts,
        "docker_image_id": PINNED_IMAGE,
        "docker_image_inspect_sha256": sha_bytes(canonical(image_inspect)),
        "catalogue_container_policy": {"count": SHARDS, "max_parallel": 4,
                                      "cpu_quota": 200000, "memory_bytes": 2 * 1024**3,
                                      "memory_swap_total_bytes": 2 * 1024**3,
                                      "network": "none", "cgroup_parent": "docker-batch.slice"},
        "link_container": link_container, "link_command": command,
        "outputs": output_hashes,
        "hardware_tested": False, "hardware_admitted": False, "installable": False,
        "storage_admitted": False, "save_service_armed": False,
        "full_ram_residency": False, "runtime_performance_proven": False,
    }
    atomic_json(output / "frozen-build-input-receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--headers", type=Path, required=True)
    parser.add_argument("--prepared-profile", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--expected-profile-sha256", required=True)
    parser.add_argument("--expected-selection-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resampler-stage-profile", action="store_true",
                        help=("enable schema-9 resampler profiling plus schema-6 IRQ instrumentation; "
                              "the control omits both flags and is not a resampler-only delta"))
    run_build(parser.parse_args(argv))


if __name__ == "__main__":
    main()

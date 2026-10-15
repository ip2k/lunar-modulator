#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the corrected Trio diagnostic from frozen, manifest-bound inputs.

This runner is separate from the target source snapshot: it mounts a clean
archive of the requested Git commit, a private copy of the full toolchain and
catalogue, and a copied prepared profile read-only. It only performs an offline
link; it does not create an installable package or contact hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile

PINNED_COMMIT = "66196f54f3295cfdec14a2924c767235bbd5cc2c"
PINNED_IMAGE = "sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc"
PREVIOUS_APP = "3de52e9bddd24c19fbabaa3cc7cec97ea78ef0a2397debfc009befb1f8b9b6bc"
PREVIOUS_ELF = "a07fbd8e966873c154bfc4f62fc1d9b608004e7d1c56640f59a762959d324e6e"
EXPECTED_PROFILE = "d4b8a9c6c4945fa8b94940cd9c826f46000d18351e000090faca7b800a79ad29"
MAX_ENTRIES = 8192
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def tree_manifest(root: Path) -> bytes:
    root = root.resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
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
                size = target.stat().st_size
                digest_path = target
                kind = "symlink-file"
                target_text = os.readlink(path)
            else:
                if not path.is_file():
                    raise ValueError("tree contains a non-regular entry")
                size = path.stat().st_size
                digest_path = path
                kind = "file"
                target_text = None
            if size > MAX_FILE_BYTES:
                raise ValueError("tree file exceeds manifest bound")
            total += size
            row = {"path": rel, "kind": kind, "bytes": size, "sha256": sha_file(digest_path),
                   "mode": path.lstat().st_mode & 0o777}
            if target_text is not None:
                row["target"] = target_text
            rows.append(row)
            if len(rows) > MAX_ENTRIES or total > MAX_TOTAL_BYTES:
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


def source_archive(checkout: Path, destination: Path) -> tuple[str, str, bytes]:
    checkout = checkout.resolve(strict=True)
    # The runner and its tests are intentionally untracked task-owned files.
    # Reject tracked edits and any other untracked files; the source snapshot
    # itself is still generated only from the pinned committed tree.
    subprocess.run(["git", "-C", str(checkout), "diff", "--quiet", "HEAD", "--"], check=True)
    subprocess.run(["git", "-C", str(checkout), "diff", "--cached", "--quiet"], check=True)
    status = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True).splitlines()
    allowed = {"?? tests/test_native_frozen_trio_diagnostic_build.py",
               "?? tools/native/run_frozen_trio_diagnostic_build.py"}
    if any(row not in allowed for row in status):
        raise ValueError("source checkout has unrelated changes before frozen build")
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    tree = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD^{tree}"], text=True).strip()
    if commit != PINNED_COMMIT or tree != "483e0fa782650c2158eae979f1830960c5f86a96":
        raise ValueError("source checkout is not the exact corrected source commit/tree")
    archive = subprocess.Popen(
        ["git", "-C", str(checkout), "archive", "--format=tar", commit],
        stdout=subprocess.PIPE)
    assert archive.stdout is not None
    try:
        with tarfile.open(fileobj=archive.stdout, mode="r|") as stream:
            stream.extractall(destination, filter="data")
    finally:
        archive.stdout.close()
    if archive.wait() != 0:
        raise ValueError("git archive failed")
    return commit, tree, tree_manifest(destination)


def inspect_image(docker: str) -> dict:
    raw = subprocess.check_output([docker, "image", "inspect", PINNED_IMAGE])
    rows = json.loads(raw)
    if not isinstance(rows, list) or len(rows) != 1 or rows[0].get("Id") != PINNED_IMAGE:
        raise ValueError("pinned Docker image identity mismatch")
    return rows[0]


def run_build(args):
    docker = shutil.which("docker")
    if not docker:
        raise ValueError("Docker CLI unavailable")
    output = args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError("output directory must be empty")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    snapshot_root = output / "snapshots"
    snapshot_root.mkdir(mode=0o700)
    source = snapshot_root / "source"
    toolchain = snapshot_root / "toolchain"
    catalogue = snapshot_root / "catalogue"
    prepared = snapshot_root / "prepared"

    commit, source_git_tree, source_manifest = source_archive(args.checkout, source)
    toolchain_source = args.toolchain.resolve(strict=True)
    catalogue_source = args.catalogue.resolve(strict=True)
    toolchain_source_manifest = tree_manifest(toolchain_source)
    catalogue_source_manifest = tree_manifest(catalogue_source)
    toolchain_manifest = copy_tree_verified(toolchain_source, toolchain)
    catalogue_manifest = copy_tree_verified(catalogue_source, catalogue)
    profile_source = args.prepared_profile.resolve(strict=True)
    if profile_source.is_symlink() or not profile_source.is_dir():
        raise ValueError("prepared profile input must be a real directory")
    profile_file = profile_source / "profile.json"
    if profile_file.is_symlink() or not profile_file.is_file():
        raise ValueError("prepared profile.json must be a regular file")
    profile_sha = sha_file(profile_file)
    if profile_sha != EXPECTED_PROFILE:
        raise ValueError("prepared profile differs from the pinned request")
    prepared_source_manifest = tree_manifest(profile_source)
    prepared_manifest = copy_tree_verified(profile_source, prepared)
    if sha_file(prepared / "profile.json") != profile_sha:
        raise ValueError("prepared profile copy differs from the pinned request")
    image = inspect_image(docker)
    build_parent = output / "writable-output"
    build_parent.mkdir(mode=0o777)
    os.chmod(build_parent, 0o777)
    os.chown(build_parent, 1001, 1001)
    build = build_parent / "build"
    if build.exists():
        raise ValueError("frozen build output must not already exist")

    names = [f"lunar-trio-frozen-{os.getpid()}"]
    name = names[0]
    args_vector = [
        docker, "create", "--name", name,
        "--label", "lan.project=lunar-modulator",
        "--label", "lan.task=trio-pulse-frozen-build",
        "--label", "lan.session=trio-pulse-frozen-build",
        "--cgroup-parent=docker-batch.slice",
        "--network=none", "--cpu-quota=400000", "--cpu-period=100000",
        "--memory=4g", "--memory-swap=4g", "--pids-limit=256",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--user=1001:1001", "--workdir=/workspace",
        "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=1073741824",
        "--mount", f"type=bind,src={source},dst=/workspace,readonly",
        "--mount", f"type=bind,src={toolchain},dst=/toolchain,readonly",
        "--mount", f"type=bind,src={catalogue},dst=/catalogue,readonly",
        "--mount", f"type=bind,src={prepared},dst=/prepared,readonly",
        "--mount", f"type=bind,src={build_parent},dst=/out",
        PINNED_IMAGE, "python3", "tools/native/build_application_probe.py",
        "--toolchain", "/toolchain", "--catalogue", "/catalogue",
        "--build", "/out/build", "--prepared-profile", "/prepared",
        "--expected-profile-sha256", EXPECTED_PROFILE,
        "--firmware-identity", "FM-1_500", "--runtime-mode", "song-diagnostic",
        "--stack-watermark", "--flash-layout", "expanded-d7000",
        "--link-project-save-service", "--shapes-voices", "8",
        "--indexed-tft", "--compressed-wavetables", "--enable-trs-midi",
        "--diagnostic-trio-pulse",
    ]
    cid = subprocess.check_output(args_vector, text=True).strip()
    try:
        inspected = json.loads(subprocess.check_output([docker, "inspect", cid]))[0]
        host = inspected["HostConfig"]
        config = inspected["Config"]
        expected_mounts = {"/workspace": str(source), "/toolchain": str(toolchain),
                           "/catalogue": str(catalogue), "/prepared": str(prepared),
                           "/out": str(build_parent)}
        actual_mounts = {row["Destination"]: row["Source"] for row in inspected["Mounts"]}
        expected_labels = {"lan.project": "lunar-modulator",
                           "lan.task": "trio-pulse-frozen-build",
                           "lan.session": "trio-pulse-frozen-build"}
        expected_cmd = args_vector[args_vector.index(PINNED_IMAGE) + 1:]
        if (inspected.get("Image") != PINNED_IMAGE or config.get("Image") != PINNED_IMAGE
                or config.get("Labels") != expected_labels or config.get("Cmd") != expected_cmd
                or config.get("Entrypoint") not in (None, [])
                or host.get("NetworkMode") != "none" or host.get("CgroupParent") != "docker-batch.slice"
                or host.get("CpuQuota") != 400000 or host.get("CpuPeriod") != 100000
                or host.get("Memory") != 4294967296 or host.get("MemorySwap") != 4294967296
                or host.get("PidsLimit") != 256 or host.get("ReadonlyRootfs") is not True
                or config.get("WorkingDir") != "/workspace"
                or host.get("Privileged") is not False or host.get("Devices") != []
                or host.get("CapDrop") != ["ALL"] or config.get("User") != "1001:1001"
                or actual_mounts != expected_mounts
                or any(row.get("RW") is not False for row in inspected["Mounts"]
                       if row["Destination"] != "/out")):
            raise ValueError("container configuration differs from the frozen offline build policy")
        with (output / "container.log").open("wb") as log:
            result = subprocess.run([docker, "start", "--attach", cid],
                                    stdout=log, stderr=subprocess.STDOUT, check=False)
        final_inspect = json.loads(subprocess.check_output([docker, "inspect", cid]))[0]
        if result.returncode != 0 or final_inspect["State"].get("ExitCode") != 0:
            raise ValueError("target build container failed; see private container.log")

        if tree_manifest(source) != source_manifest:
            raise ValueError("source snapshot changed during build")
        if tree_manifest(toolchain) != toolchain_manifest:
            raise ValueError("toolchain snapshot changed during build")
        if tree_manifest(toolchain_source) != toolchain_source_manifest:
            raise ValueError("original toolchain tree changed during build")
        if tree_manifest(catalogue) != catalogue_manifest:
            raise ValueError("catalogue snapshot changed during build")
        if tree_manifest(catalogue_source) != catalogue_source_manifest:
            raise ValueError("original catalogue tree changed during build")
        if tree_manifest(prepared) != prepared_manifest:
            raise ValueError("prepared profile snapshot changed during build")
        if tree_manifest(profile_source) != prepared_source_manifest:
            raise ValueError("original prepared profile tree changed during build")
        if sha_file(prepared / "profile.json") != profile_sha:
            raise ValueError("prepared profile digest changed during build")

        artifact = build / "artifact"
        app = artifact / "app.bin"
        elf = build / "lunar-app-probe.elf"
        verification = build / "verification.json"
        artifact_receipt = artifact / "artifact.json"
        disassembly = artifact / "disassembly.txt"
        output_hashes = {str(path.relative_to(output)): sha_file(path)
                         for path in (app, elf, verification, artifact_receipt, disassembly)}
        if (output_hashes[str(app.relative_to(output))] != PREVIOUS_APP
                or output_hashes[str(elf.relative_to(output))] != PREVIOUS_ELF):
            raise ValueError("frozen rebuild output differs from the prior corrected app/ELF")
        receipt = {
            "schema": 1,
            "source_commit": commit,
            "source_git_tree": source_git_tree,
            "source_tree_manifest_sha256": hashlib.sha256(source_manifest).hexdigest(),
            "source_snapshot_manifest_sha256": hashlib.sha256(tree_manifest(source)).hexdigest(),
            "toolchain_source_path": str(toolchain_source),
            "toolchain_source_tree_manifest_sha256": hashlib.sha256(toolchain_source_manifest).hexdigest(),
            "toolchain_snapshot_tree_manifest_sha256": hashlib.sha256(toolchain_manifest).hexdigest(),
            "catalogue_source_path": str(catalogue_source),
            "catalogue_source_tree_manifest_sha256": hashlib.sha256(catalogue_source_manifest).hexdigest(),
            "catalogue_snapshot_tree_manifest_sha256": hashlib.sha256(catalogue_manifest).hexdigest(),
            "prepared_profile_sha256": profile_sha,
            "prepared_source_tree_manifest_sha256": hashlib.sha256(prepared_source_manifest).hexdigest(),
            "prepared_snapshot_tree_manifest_sha256": hashlib.sha256(prepared_manifest).hexdigest(),
            "docker_image_id": PINNED_IMAGE,
            "docker_image_inspect_sha256": hashlib.sha256(canonical(image)).hexdigest(),
            "container_id": cid,
            "container_config": {
                "network": host["NetworkMode"], "cgroup_parent": host["CgroupParent"],
                "cpu_quota": host["CpuQuota"], "cpu_period": host["CpuPeriod"],
                "memory": host["Memory"], "memory_swap": host["MemorySwap"],
                "pids_limit": host["PidsLimit"], "readonly_rootfs": host["ReadonlyRootfs"],
                "user": config["User"], "mounts": expected_mounts,
            },
            "command": args_vector,
            "outputs": output_hashes,
            "app_sha256": output_hashes[str(app.relative_to(output))],
            "app_bytes": app.stat().st_size,
            "elf_sha256": output_hashes[str(elf.relative_to(output))],
            "verification_sha256": output_hashes[str(verification.relative_to(output))],
            "artifact_receipt_sha256": output_hashes[str(artifact_receipt.relative_to(output))],
            "disassembly_sha256": output_hashes[str(disassembly.relative_to(output))],
            "prior_app_sha256": PREVIOUS_APP,
            "prior_elf_sha256": PREVIOUS_ELF,
            "build_tuple_emitted": False,
            "image_json_emitted": False,
            "hardware_admitted": False,
            "installable": False,
            "storage_admitted": False,
            "save_service_armed": False,
        }
        for label, raw in (("source-tree-manifest.json", source_manifest),
                           ("toolchain-tree-manifest.json", toolchain_manifest),
                           ("catalogue-tree-manifest.json", catalogue_manifest),
                           ("prepared-tree-manifest.json", prepared_manifest),
                           ("frozen-build-input-receipt.json", canonical(receipt) + b"\n")):
            path = output / label
            path.write_bytes(raw)
            path.chmod(0o600)
        print(json.dumps(receipt, sort_keys=True, indent=2))
    finally:
        subprocess.run([docker, "rm", "-f", cid], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--prepared-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run_build(parser.parse_args())


if __name__ == "__main__":
    main()

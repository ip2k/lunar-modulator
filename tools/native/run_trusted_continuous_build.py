#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run and attest one private continuous Shapes8/D7000 build on pinned Hera Docker."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import time

from capture_trusted_build_tuple import (capture_trusted_build_tuple, canonical, sha,
                                                 _source_manifest, _toolchain_manifest)

ROOT = Path(__file__).resolve().parents[2]
PINNED_IMAGE_ID = "sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc"
IMAGE_SHA = PINNED_IMAGE_ID.split(":", 1)[1]
PINNED_IMAGE_ENV = ["PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"]
WORKER_REL = "tools/native/trusted_continuous_worker.py"
DOCKER_POLICY = {
    "network_mode": "none",
    "cgroup_parent": "docker-batch.slice",
    "cpus": 4,
    "memory": 8589934592,
    "memory_swap": 8589934592,
    "pids_limit": 512,
    "readonly_rootfs": True,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges"],
    "user": "1001:1001",
    "tmpfs": {"/tmp": "rw,nosuid,nodev,exec,size=3221225472"},
    "labels": {"lan.project": "lunar-modulator", "lan.session": "continuous-tuple-capture"},
}
MAX_REQUEST = 65536
MAX_INSPECT = 2 * 1024 * 1024


def _json(raw: bytes, label: str):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                raise ValueError("duplicate field in " + label)
            out[key] = value
        return out
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("invalid " + label) from error


def _safe(path: Path, *, directory: bool):
    if path.is_symlink():
        raise ValueError("symlink input refused")
    resolved = path.resolve(strict=True)
    if directory != resolved.is_dir() or (not directory and not resolved.is_file()):
        raise ValueError("invalid operator input path")
    return resolved


def _run(docker: str, args: list[str], *, timeout=30, allow_failure=False) -> bytes:
    result = subprocess.run([docker, *args], stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=timeout, check=False)
    if len(result.stdout) > MAX_INSPECT:
        raise ValueError("Docker response exceeds fixed bound")
    if result.returncode and not allow_failure:
        raise ValueError("pinned Docker operation failed: " + args[0])
    return result.stdout


def _mount(source: Path, destination: str, readonly=True):
    if "," in str(source) or "\n" in str(source):
        raise ValueError("unsupported Docker mount path")
    text = "type=bind,src=" + str(source) + ",dst=" + destination
    return text + (",readonly" if readonly else "")


def container_command(docker: str, container_name: str, source: Path, request: Path,
                      toolchain: Path, catalogue: Path, output: Path, source_commit: str):
    mounts = [
        _mount(source, "/workspace"),
        _mount(request, "/input/request.json"),
        _mount(toolchain, "/opt/pi32v2"),
        _mount(catalogue, "/catalogue"),
        _mount(output, "/output", readonly=False),
    ]
    cmd = [docker, "create", "--name", container_name,
           "--label", "lan.project=lunar-modulator",
           "--label", "lan.session=continuous-tuple-capture",
           "--cgroup-parent=docker-batch.slice", "--network=none",
           "--cpu-quota=400000", "--cpu-period=100000",
           "--memory=8g", "--memory-swap=8g", "--pids-limit=512",
           "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
           "--user=1001:1001", "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=3221225472",
           "--env", "LUNAR_SOURCE_COMMIT=" + source_commit]
    for mount in mounts:
        cmd.extend(["--mount", mount])
    cmd.extend([PINNED_IMAGE_ID, "python3", "/workspace/" + WORKER_REL])
    return cmd, mounts


def _expected_mounts(mounts):
    rows = []
    for value in mounts:
        fields = dict(part.split("=", 1) for part in value.split(",") if "=" in part)
        rows.append({"source": fields["src"], "destination": fields["dst"],
                     "read_only": "readonly" in value.split(",")})
    return sorted(rows, key=lambda row: row["destination"])


def inspected_contract(inspect: dict, expected_mounts: list[dict], source_commit: str,
                       expected_name: str | None = None, expected_id: str | None = None):
    if not isinstance(inspect, dict):
        raise ValueError("Docker inspect response must be an object")
    config = inspect.get("Config")
    host = inspect.get("HostConfig")
    state = inspect.get("State")
    if not all(isinstance(x, dict) for x in (config, host, state)):
        raise ValueError("Docker inspect response is incomplete")
    actual_mounts = []
    for row in inspect.get("Mounts", []):
        if not isinstance(row, dict):
            raise ValueError("Docker mount inspection is malformed")
        actual_mounts.append({"source": row.get("Source"), "destination": row.get("Destination"),
                              "read_only": not row.get("RW")})
    actual_mounts.sort(key=lambda row: row["destination"] or "")
    expected_command = ["python3", "/workspace/" + WORKER_REL]
    expected_env = ["LUNAR_SOURCE_COMMIT=" + source_commit] + PINNED_IMAGE_ENV
    config_env = config.get("Env")
    if (inspect.get("Image") != PINNED_IMAGE_ID or config.get("Image") != PINNED_IMAGE_ID
            or (expected_name is not None and inspect.get("Name") != "/" + expected_name)
            or (expected_id is not None and inspect.get("Id") != expected_id)
            or config.get("Cmd") != expected_command or config.get("User") != DOCKER_POLICY["user"]
            or config_env != expected_env
            or host.get("NetworkMode") != "none" or host.get("CgroupParent") != "docker-batch.slice"
            or host.get("ReadonlyRootfs") is not True or host.get("CpuQuota") != 400000
            or host.get("CpuPeriod") != 100000 or host.get("NanoCpus") != 0 or host.get("Memory") != DOCKER_POLICY["memory"]
            or host.get("MemorySwap") != DOCKER_POLICY["memory_swap"]
            or host.get("PidsLimit") != DOCKER_POLICY["pids_limit"]
            or host.get("Privileged") is not False
            or host.get("Devices") != [] or host.get("DeviceRequests") is not None
            or host.get("CapAdd") is not None
            or host.get("PidMode") != "" or host.get("IpcMode") != "private"
            or host.get("UTSMode") != "" or host.get("UsernsMode") != ""
            or host.get("Runtime") != "runc" or host.get("Binds") is not None
            or host.get("AutoRemove") is not False or host.get("Init") is not None
            or host.get("CapDrop") != ["ALL"]
            or host.get("SecurityOpt") != ["no-new-privileges"]
            or host.get("Tmpfs") != DOCKER_POLICY["tmpfs"]
            or config.get("Labels") != DOCKER_POLICY["labels"]
            or config.get("Entrypoint") is not None
            or config.get("WorkingDir") != ""
            or config.get("Tty") is not False
            or config.get("OpenStdin") is not False
            or config.get("StdinOnce") is not False
            or config.get("AttachStdout") is not True
            or config.get("AttachStderr") is not True
            or actual_mounts != expected_mounts):
        raise ValueError("created container differs from the pinned build policy")
    return {
        "image": inspect.get("Image"),
        "container_name": inspect.get("Name"),
        "container_id": inspect.get("Id"),
        "config_image": config.get("Image"),
        "command": config.get("Cmd"),
        "user": config.get("User"),
        "labels": config.get("Labels"),
        "environment_keys": sorted(item.split("=", 1)[0] for item in config_env),
        "environment_sha256": sha(canonical(config_env)),
        "host": {"network_mode": host.get("NetworkMode"),
                 "cgroup_parent": host.get("CgroupParent"),
                 "readonly_rootfs": host.get("ReadonlyRootfs"),
                 "cpu_quota": host.get("CpuQuota"), "cpu_period": host.get("CpuPeriod"),
                 "nano_cpus": host.get("NanoCpus"),
                 "memory": host.get("Memory"), "memory_swap": host.get("MemorySwap"),
                 "privileged": host.get("Privileged"), "devices": host.get("Devices"),
                 "device_requests": host.get("DeviceRequests"), "cap_add": host.get("CapAdd"),
                 "pid_mode": host.get("PidMode"), "ipc_mode": host.get("IpcMode"),
                 "uts_mode": host.get("UTSMode"), "userns_mode": host.get("UsernsMode"),
                 "runtime": host.get("Runtime"), "binds": host.get("Binds"),
                 "auto_remove": host.get("AutoRemove"), "init": host.get("Init"),
                 "pids_limit": host.get("PidsLimit"), "cap_drop": host.get("CapDrop"),
                 "security_opt": host.get("SecurityOpt"), "tmpfs": host.get("Tmpfs")},
        "mounts": actual_mounts,
        "config_contract": {"entrypoint": config.get("Entrypoint"),
                            "working_dir": config.get("WorkingDir"),
                            "tty": config.get("Tty"), "open_stdin": config.get("OpenStdin"),
                            "stdin_once": config.get("StdinOnce"),
                            "attach_stdout": config.get("AttachStdout"),
                            "attach_stderr": config.get("AttachStderr")},
        "state": {"status": state.get("Status"), "running": state.get("Running"),
                  "exit_code": state.get("ExitCode")},
    }


def require_successful_exit(contract):
    state = contract.get("state") if isinstance(contract, dict) else None
    if state != {"status": "exited", "running": False, "exit_code": 0}:
        raise ValueError("continuous build container did not exit successfully")
    return contract


def _inspect(docker: str, container_id: str):
    raw = _run(docker, ["inspect", container_id])
    decoded = _json(raw, "Docker inspect")
    if not isinstance(decoded, list) or len(decoded) != 1:
        raise ValueError("Docker inspect returned an unexpected container count")
    return decoded[0]


def _write_exclusive(path: Path, raw: bytes):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def _toolchain_snapshot_fields(source: Path, snapshot: Path,
                               source_manifest: bytes, snapshot_manifest: bytes):
    if source_manifest != snapshot_manifest:
        raise ValueError("private toolchain snapshot differs from its source tree")
    return {
        "toolchain_source_root": str(source.resolve()),
        "toolchain_snapshot_root": str(snapshot.resolve()),
        "toolchain_source_tree_sha256": sha(source_manifest),
        "toolchain_snapshot_tree_sha256": sha(snapshot_manifest),
        "toolchain_tree_sha256": sha(snapshot_manifest),
    }


def _remove_private_snapshot(path: Path, parent: Path, prefix: str):
    path = Path(path)
    parent = Path(parent).resolve(strict=True)
    if path.is_symlink() or path.parent.resolve(strict=True) != parent or not path.name.startswith(prefix):
        raise ValueError("refusing to remove an unowned private snapshot")

    def retry_readonly(function, failed_path, exc_info):
        error = exc_info[1]
        candidate = Path(failed_path)
        if not isinstance(error, PermissionError) or candidate.is_symlink():
            raise error
        chmod_target = candidate if function is os.scandir else candidate.parent
        if chmod_target.is_symlink():
            raise ValueError("snapshot cleanup encountered a symlink") from error
        owned_root = path.resolve(strict=True)
        resolved_target = chmod_target.resolve(strict=True)
        if resolved_target != owned_root and not resolved_target.is_relative_to(owned_root):
            raise ValueError("snapshot cleanup escaped its owned tree") from error
        os.chmod(chmod_target, stat.S_IRWXU, follow_symlinks=False)
        function(failed_path)

    shutil.rmtree(path, onerror=retry_readonly)


def _copy_verified_snapshot(source: Path, snapshot: Path, prefix: str):
    source_manifest = _toolchain_manifest(source)
    try:
        shutil.copytree(source, snapshot, symlinks=True, copy_function=shutil.copy2)
        snapshot_manifest = _toolchain_manifest(snapshot)
        fields = _toolchain_snapshot_fields(source, snapshot, source_manifest, snapshot_manifest)
        if _toolchain_manifest(source) != source_manifest:
            raise ValueError("source tree changed while taking private snapshot")
        return snapshot_manifest, fields
    except Exception:
        if snapshot.exists() and not snapshot.is_symlink():
            _remove_private_snapshot(snapshot, snapshot.parent, prefix)
        raise


def _catalogue_snapshot_fields(source: Path, snapshot: Path,
                               source_manifest: bytes, snapshot_manifest: bytes):
    if source_manifest != snapshot_manifest:
        raise ValueError("private catalogue snapshot differs from its source tree")
    return {
        "catalogue_source_root": str(source.resolve()),
        "catalogue_snapshot_root": str(snapshot.resolve()),
        "catalogue_source_tree_sha256": sha(source_manifest),
        "catalogue_snapshot_tree_sha256": sha(snapshot_manifest),
    }


def run_build(*, request_path: Path,
              toolchain_path: Path, catalogue_path: Path, output_path: Path,
              source_root: Path = ROOT, docker_binary="docker", timeout_seconds=1200,
              poll_seconds=1, monotonic=time.monotonic):
    """Run the single fixed build; caller controls only trusted local input paths."""
    source = _safe(Path(source_root), directory=True)
    request = _safe(Path(request_path), directory=False)
    toolchain = _safe(Path(toolchain_path), directory=True)
    catalogue = _safe(Path(catalogue_path), directory=True)
    status = subprocess.run(["git", "-C", str(source), "status", "--porcelain=v1", "--untracked-files=all"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True).stdout
    if status:
        raise ValueError("source checkout must be clean including untracked inputs")
    commit = subprocess.run(["git", "-C", str(source), "rev-parse", "HEAD"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            timeout=10, check=True).stdout.strip()
    if len(commit) != 40 or any(c not in "0123456789abcdef" for c in commit):
        raise ValueError("source checkout has no full immutable commit")
    request_raw = request.read_bytes()
    if not 0 < len(request_raw) <= MAX_REQUEST:
        raise ValueError("request exceeds fixed size bound")
    try:
        request_obj = _json(request_raw, "build request")
    except ValueError:
        raise
    if not isinstance(request_obj, dict):
        raise ValueError("build request must be a JSON object")
    output = Path(output_path).absolute()
    parent = output.parent.resolve(strict=True)
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(source):
        raise ValueError("output must be a new directory outside the source checkout")
    if not parent.is_dir() or stat.S_IMODE(parent.stat().st_mode) & 0o077:
        raise ValueError("private output parent must be an existing owner-only directory")

    image = _run(docker_binary, ["image", "inspect", "--format", "{{.Id}}", PINNED_IMAGE_ID]).decode("ascii").strip()
    image_env = _json(_run(docker_binary, ["image", "inspect", "--format", "{{json .Config.Env}}", PINNED_IMAGE_ID]),
                      "pinned image environment")
    if image != PINNED_IMAGE_ID or image_env != PINNED_IMAGE_ENV:
        raise ValueError("local image ID or immutable base environment differs from the pinned image")
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    snapshot = output.parent / ("." + output.name + "-source-" + secrets.token_hex(8))
    catalogue_snapshot = output.parent / ("." + output.name + "-catalogue-" + secrets.token_hex(8))
    toolchain_snapshot = output.parent / ("." + output.name + "-toolchain-" + secrets.token_hex(8))
    request_copy = output.parent / ("." + output.name + "-" + secrets.token_hex(8) + ".request.json")
    container_id = None
    container_name = None
    try:
        fd = os.open(request_copy, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
        with os.fdopen(fd, "wb") as request_stream:
            request_stream.write(request_raw)
            request_stream.flush()
            os.fsync(request_stream.fileno())
        catalogue_source_manifest = _toolchain_manifest(catalogue)
        shutil.copytree(catalogue, catalogue_snapshot, symlinks=True, copy_function=shutil.copy2)
        catalogue_snapshot_manifest = _toolchain_manifest(catalogue_snapshot)
        catalogue_fields = _catalogue_snapshot_fields(
            catalogue, catalogue_snapshot, catalogue_source_manifest, catalogue_snapshot_manifest)
        toolchain_snapshot_manifest, toolchain_fields = _copy_verified_snapshot(
            toolchain, toolchain_snapshot, "." + output.name + "-toolchain-")
        subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", "--no-checkout",
                        str(source), str(snapshot)], stdin=subprocess.DEVNULL,
                       stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=120, check=True)
        subprocess.run(["git", "-C", str(snapshot), "checkout", "--quiet", "--detach", commit],
                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                       stderr=subprocess.DEVNULL, timeout=120, check=True)
        snapshot_head = subprocess.run(["git", "-C", str(snapshot), "rev-parse", "HEAD"],
                                       check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
        snapshot_status = subprocess.run(["git", "-C", str(snapshot), "status", "--porcelain=v1", "--untracked-files=all"],
                                         check=True, stdout=subprocess.PIPE).stdout
        if snapshot_head != commit or snapshot_status:
            raise ValueError("detached source snapshot is not clean at the requested commit")
        toolchain_manifest_raw = _toolchain_manifest(toolchain_snapshot)
        toolchain_manifest_sha = sha(toolchain_manifest_raw)
        container_name = "lunar-continuous-" + secrets.token_hex(12)
        cmd, mount_args = container_command(docker_binary, container_name, snapshot, request_copy,
                                            toolchain_snapshot, catalogue_snapshot, output, commit)
        mounts = _expected_mounts(mount_args)
        raw_id = _run(docker_binary, cmd[len([docker_binary]):], timeout=60).decode("ascii").strip()
        if not raw_id or len(raw_id) > 128 or any(c not in "0123456789abcdef" for c in raw_id):
            raise ValueError("Docker returned an invalid container identifier")
        container_id = raw_id
        initial = _inspect(docker_binary, container_id)
        initial_contract = inspected_contract(initial, mounts, commit, container_name, container_id)
        if initial_contract["state"]["status"] != "created":
            raise ValueError("new container was not in the created state")
        _run(docker_binary, ["start", container_id], timeout=30)
        deadline = monotonic() + timeout_seconds
        final = initial
        while True:
            final = _inspect(docker_binary, container_id)
            contract = inspected_contract(final, mounts, commit, container_name, container_id)
            if not contract["state"]["running"]:
                break
            if monotonic() >= deadline:
                raise TimeoutError("continuous build exceeded the fixed time limit")
            time.sleep(poll_seconds)
        contract = require_successful_exit(inspected_contract(final, mounts, commit, container_name, container_id))

        post_commit, post_manifest = _source_manifest(snapshot)
        if post_commit != commit:
            raise ValueError("source snapshot commit changed while the build ran")
        post_toolchain_manifest = _toolchain_manifest(toolchain_snapshot)
        if sha(post_toolchain_manifest) != toolchain_manifest_sha:
            raise ValueError("private toolchain snapshot changed while the container was running")
        post_catalogue_manifest = _toolchain_manifest(catalogue_snapshot)
        if post_catalogue_manifest != catalogue_snapshot_manifest:
            raise ValueError("private catalogue snapshot changed while the container was running")
        build_output = output / "build"
        worker_path = snapshot / WORKER_REL
        worker_sha = sha(worker_path.read_bytes())
        wrapper_sha = sha((snapshot / "tools/native/run_trusted_continuous_build.py").read_bytes())
        worker_raw = (output / "worker-provenance.json").read_bytes()
        worker = _json(worker_raw, "worker provenance")
        if (worker.get("source_commit") != commit or worker.get("request_sha256") != sha(request_raw)
                or worker.get("runtime_mode") != "continuous"
                or worker.get("flash_layout") != "expanded-d7000"
                or worker.get("hardware_admitted") is not False
                or worker.get("hardware_tested") is not False
                or worker.get("installable") is not False):
            raise ValueError("worker provenance differs from the requested fixed build")
        invocation = {
            "schema": 1,
            "source_commit": commit,
            "request_sha256": sha(request_raw),
            "request_mount_source": str(request_copy.resolve()),
            "image_id": PINNED_IMAGE_ID,
            "container_id": container_id,
            "container_name": container_name,
            "container_command": cmd[1:],
            "container_inspection": contract,
            "container_inspection_sha256": sha(canonical(contract)),
            "post_build_source_tree_sha256": sha(post_manifest),
            "container_command_sha256": sha(canonical(cmd[1:])),
            "wrapper_sha256": wrapper_sha,
            "worker_sha256": worker_sha,
            "worker_provenance_sha256": sha(worker_raw),
            **toolchain_fields,
            **catalogue_fields,
            "state_tool_sha256": worker.get("state_tool_sha256"),
            "resources": DOCKER_POLICY,
            "exit_code": 0,
            "hardware_admitted": False,
            "hardware_tested": False,
            "installable": False,
        }
        _write_exclusive(output / "toolchain-manifest.json", toolchain_manifest_raw)
        _write_exclusive(output / "catalogue-tree-manifest.json", catalogue_snapshot_manifest)
        _write_exclusive(output / "container-invocation.json", canonical(invocation))
        return capture_trusted_build_tuple(snapshot, catalogue_snapshot, build_output, toolchain_snapshot,
                                           invocation_path=output / "container-invocation.json",
                                           worker_source_path=snapshot / WORKER_REL,
                                           worker_provenance_path=output / "worker-provenance.json",
                                           wrapper_path=snapshot / WORKER_REL.replace("trusted_continuous_worker.py", "run_trusted_continuous_build.py"))
    except Exception:
        # Keep the private output directory and evidence for diagnosis; never reuse it.
        raise
    finally:
        cleanup_target = container_id or container_name
        if cleanup_target:
            subprocess.run([docker_binary, "rm", "-f", cleanup_target], stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=30, check=False)
        request_copy.unlink(missing_ok=True)
        if snapshot.exists() and not snapshot.is_symlink():
            _remove_private_snapshot(snapshot, output.parent, "." + output.name + "-source-")
        if catalogue_snapshot.exists() and not catalogue_snapshot.is_symlink():
            _remove_private_snapshot(catalogue_snapshot, output.parent, "." + output.name + "-catalogue-")
        if toolchain_snapshot.exists() and not toolchain_snapshot.is_symlink():
            _remove_private_snapshot(toolchain_snapshot, output.parent, "." + output.name + "-toolchain-")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True)
    parser.add_argument("--catalogue", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture = run_build(request_path=args.request, toolchain_path=args.toolchain,
                            catalogue_path=args.catalogue, output_path=args.out)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError) as error:
        parser.error(str(error))
    print(json.dumps(capture, sort_keys=True))


if __name__ == "__main__":
    main()

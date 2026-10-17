# SPDX-License-Identifier: MIT
"""Fixed-input, private Docker adapter for diagnostic builds.

No request field is interpreted as a host path, image, command, or mount.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import select
import stat
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field

from .api import (MAX_ARTIFACT_BYTES, MAX_BODY_BYTES, MAX_ELF_BYTES, QueueFull,
                  WorkerResult, WorkerSnapshot, _unique_object, _reject_constant)
from .docker_worker import GENERATED_EVIDENCE_PATHS, generated_evidence_paths
from .provenance import (make_diagnostic_provenance, sha256 as _sha256,
                         tree_manifest)

_BUILD_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
# The service deliberately pins the locally provisioned image ID.  A Docker
# image ID is an immutable sha256 digest but is not a repository-qualified
# pull reference; treating it as one makes Docker try to pull a nonexistent
# repository name.
_IMAGE_ID = "sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495"
_MAX_PRIVATE_EVIDENCE_FILE = 128 * 1024 * 1024
_MAX_PRIVATE_EVIDENCE_TOTAL = 512 * 1024 * 1024
_CATALOGUE_MOUNT = "/input/catalogue/"
_BUILD_LINK_MOUNT = "/tmp/lunar-worker/output/build/link/"


def _canonical_relative(raw: str) -> PurePosixPath:
    parts = raw.split("/")
    if not raw or "\\" in raw or any(part in ("", ".", "..") for part in parts):
        raise ValueError("private evidence path is not canonical")
    path = PurePosixPath(raw)
    if path.is_absolute() or path.as_posix() != raw:
        raise ValueError("private evidence path is not canonical")
    return path


def _receipt_key(path: str, prefix: str, key_prefix: str) -> tuple[str, PurePosixPath]:
    if not isinstance(path, str) or not path.startswith(prefix):
        raise ValueError("private receipt path is outside fixed worker mounts")
    rel = _canonical_relative(path[len(prefix):])
    return key_prefix + rel.as_posix(), rel


def _read_private_file(path: Path, limit: int, expected_size: int | None = None) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit
                or (expected_size is not None and info.st_size != expected_size)):
            raise ValueError("private evidence file differs from its declared size or cap")
        raw = stream.read(info.st_size + 1)
        if len(raw) != info.st_size:
            raise ValueError("private evidence file changed while reading")
        return raw


def read_private_evidence(result_dir: Path, expected_request: bytes,
                          expected_image_receipt: bytes,
                          catalogue_root: Path) -> dict[str, bytes]:
    """Read a content-addressed, path-safe worker evidence tree into private memory."""
    root = result_dir / "evidence"
    manifest_path = root / "manifest.json"
    if root.is_symlink() or not root.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("worker omitted private evidence manifest")
    manifest_size = manifest_path.stat().st_size
    if not 0 < manifest_size <= 2 * 1024 * 1024:
        raise ValueError("private evidence manifest exceeds cap")
    raw_manifest = _read_private_file(manifest_path, 2 * 1024 * 1024, manifest_size)
    manifest = json.loads(raw_manifest.decode("ascii"), object_pairs_hook=_unique_object,
                          parse_constant=_reject_constant)
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError("private evidence manifest is malformed")
    if len(manifest) > 8192:
        raise ValueError("private evidence manifest has too many files")
    declared_total = 0
    checked_rows = []
    for rel, row in manifest.items():
        if not isinstance(rel, str):
            raise ValueError("private evidence manifest row is malformed")
        path = _canonical_relative(rel)
        if (not isinstance(row, dict) or set(row) != {"bytes", "sha256"}
                or type(row["bytes"]) is not int or not 0 < row["bytes"] <= _MAX_PRIVATE_EVIDENCE_FILE
                or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("private evidence manifest row is malformed")
        declared_total += row["bytes"]
        if declared_total > _MAX_PRIVATE_EVIDENCE_TOTAL:
            raise ValueError("private evidence manifest exceeds aggregate cap")
        checked_rows.append((rel, path, row))
    evidence: dict[str, bytes] = {}
    total = 0
    for rel, path, row in checked_rows:
        source = root / path
        current = root
        unsafe_parent = False
        for part in path.parts[:-1]:
            current = current / part
            if current.is_symlink() or not current.is_dir():
                unsafe_parent = True
                break
        if unsafe_parent or source.is_symlink() or not source.is_file():
            raise ValueError("private evidence file is missing or unsafe")
        size = source.stat().st_size
        if size != row["bytes"] or size > _MAX_PRIVATE_EVIDENCE_TOTAL - total:
            raise ValueError("private evidence differs from manifest declaration or exceeds aggregate cap")
        content = _read_private_file(source, _MAX_PRIVATE_EVIDENCE_FILE, row["bytes"])
        if len(content) != row["bytes"] or _sha256(content) != row["sha256"]:
            raise ValueError("private evidence bytes differ from manifest")
        total += size
        evidence[rel] = content
    if evidence.get("request.json") != expected_request:
        raise ValueError("private evidence request differs from submitted request")
    if evidence.get("image_receipt.json") != expected_image_receipt:
        raise ValueError("private image receipt differs from service result")
    required = {"request.json", "prepared_profile.json", "source_profile.json",
                "artifact_receipt.json", "build_receipt.json", "image_receipt.json",
                "catalogue_manifest.json", "linked_objects.json"}
    lower_raw = evidence.get("build_receipt.json", b"{}")
    lower = json.loads(lower_raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    generated = {"generated/" + path for path in generated_evidence_paths(lower)}
    if not required.issubset(evidence) or not generated.issubset(evidence):
        raise ValueError("private evidence omits required package inputs")
    if {path for path in evidence if path.startswith("generated/")} != generated:
        raise ValueError("private generated inputs differ from the capture contract")
    build = json.loads(evidence["build_receipt.json"].decode("utf-8"),
                       object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    image = json.loads(evidence["image_receipt.json"].decode("utf-8"),
                       object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if (not isinstance(build, dict) or not isinstance(image, dict)
            or _sha256(evidence["request.json"]) != image.get("request_sha256")
            or _sha256(evidence["prepared_profile.json"]) != image.get("prepared_profile_sha256")
            or _sha256(evidence["build_receipt.json"]) != image.get("verification_sha256")
            or _sha256(evidence["artifact_receipt.json"]) != image.get("artifact_receipt_sha256")):
        raise ValueError("private receipts do not bind request, profiles, and link evidence")
    request = json.loads(expected_request, object_pairs_hook=_unique_object,
                         parse_constant=_reject_constant)
    continuous = request.get("runtime_mode") == "continuous"
    if continuous and build.get("flash_layout") != "expanded-d7000":
        raise ValueError("private continuous lower layout differs from request")
    if build.get("flash_layout") == "expanded-d7000":
        if continuous:
            from .continuous_profile import evidence_manifest, validate_receipt, validate_image_receipt
            selected = [module for group in ("engines", "effects", "midi", "modulation")
                        for module in request[group]]
            if ((build.get("module_selection") or {}).get("selected") != selected
                    or image.get("module_selection") != build.get("module_selection")):
                raise ValueError("private continuous lower selection differs from request")
            validate_image_receipt(image, selected)
        else:
            from .native_profile import evidence_manifest, validate_receipt
        profile_raw = evidence.get("native_profile.json")
        if profile_raw is None or profile_raw != evidence_manifest(evidence["build_receipt.json"]):
            raise ValueError("private native profile binding is missing or stale")
        validate_receipt(build)
    elif "native_profile.json" in evidence:
        raise ValueError("private native profile is outside the fixed D7000 build")
    catalogue = json.loads(evidence["catalogue_manifest.json"].decode("ascii"),
                           object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    linked = json.loads(evidence["linked_objects.json"].decode("ascii"),
                        object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    if (not isinstance(build, dict) or not isinstance(catalogue, dict) or not isinstance(linked, dict)
            or set(catalogue) != {"schema", "objects"} or catalogue.get("schema") != 1
            or set(linked) != {"schema", "objects"} or linked.get("schema") != 1
            or catalogue.get("objects") != build.get("catalogue_objects")
            or linked.get("objects") != build.get("linked_objects")):
        raise ValueError("private object inventories differ from the build receipt")
    catalogue_rows = catalogue.get("objects")
    linked_rows = linked.get("objects")
    if not isinstance(catalogue_rows, list) or not catalogue_rows or not isinstance(linked_rows, list) or not linked_rows:
        raise ValueError("private object inventories are empty or malformed")
    expected_catalogue = set()
    for row in catalogue_rows:
        if (not isinstance(row, dict) or set(row) not in
                ({"path", "sha256"}, {"path", "sha256", "optimization"})
                or not isinstance(row["path"], str) or not row["path"].startswith(_CATALOGUE_MOUNT)
                or not isinstance(row["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])
                or ("optimization" in row and row["optimization"] not in ("-Oz", "-Os", "-O2"))):
            raise ValueError("private catalogue inventory row is malformed")
        key, rel_path = _receipt_key(row["path"], _CATALOGUE_MOUNT, "catalogue/")
        if key in expected_catalogue or key not in evidence:
            raise ValueError("private catalogue bytes do not match the inventory")
        content = evidence[key]
        pinned = catalogue_root.joinpath(*rel_path.parts)
        if (pinned.is_symlink() or not pinned.is_file() or _sha256(content) != row["sha256"]
                or _sha256(_read_private_file(pinned, _MAX_PRIVATE_EVIDENCE_FILE, len(content))) != row["sha256"]):
            raise ValueError("private catalogue bytes differ from the host-pinned catalogue")
        expected_catalogue.add(key)
    if {path for path in evidence if path.startswith("catalogue/")} != expected_catalogue:
        raise ValueError("private catalogue files differ from its exact inventory")
    expected_linked = set()
    for row in linked_rows:
        if (not isinstance(row, dict) or set(row) != {"path", "sha256"}
                or not isinstance(row["path"], str) or not isinstance(row["sha256"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("private linked-object row is malformed")
        path = row["path"]
        if path.startswith(_CATALOGUE_MOUNT):
            key, _ = _receipt_key(path, _CATALOGUE_MOUNT, "linked/catalogue/")
        elif path.startswith(_BUILD_LINK_MOUNT):
            key, _ = _receipt_key(path, _BUILD_LINK_MOUNT, "linked/link/")
        else:
            raise ValueError("private linked-object path is outside fixed mounts")
        if key in expected_linked or key not in evidence or _sha256(evidence[key]) != row["sha256"]:
            raise ValueError("private linked-object bytes differ from the build receipt")
        expected_linked.add(key)
    if {path for path in evidence if path.startswith("linked/")} != expected_linked:
        raise ValueError("private linked files differ from the exact object inventory")
    actual = set()
    for current, dirs, files in os.walk(root, followlinks=False):
        here = Path(current)
        if any((here / name).is_symlink() for name in dirs):
            raise ValueError("private evidence contains a symlink directory")
        for name in files:
            item = here / name
            if item.is_symlink() or not item.is_file():
                raise ValueError("private evidence contains a non-regular file")
            rel = item.relative_to(root).as_posix()
            if rel != "manifest.json":
                actual.add(rel)
    if actual != set(evidence):
        raise ValueError("private evidence files differ from manifest inventory")
    return evidence


@dataclass(frozen=True)
class DockerWorkerConfig:
    source_root: Path
    toolchain_root: Path
    runtime_root: Path
    source_commit: str
    catalogue_root: Path | None = None
    image_reference: str = _IMAGE_ID
    worker_uid: int | None = None
    worker_gid: int | None = None
    docker_binary: str = "docker"
    cpu_limit: str = "4"
    memory_limit: str = "8g"
    scratch_bytes: int = 3 * 1024 * 1024 * 1024
    timeout_seconds: int = 1500
    max_log_bytes: int = 1024 * 1024
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES
    source_tree_oid: str = field(init=False, repr=False)

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{40}", self.source_commit):
            raise ValueError("source must be pinned to a full Git commit")
        if self.image_reference != _IMAGE_ID:
            raise ValueError("worker image must match the reviewed immutable image")
        if self.catalogue_root is None:
            raise ValueError("fixed verified catalogue cache is required")
        for field in ("source_root", "toolchain_root", "runtime_root", "catalogue_root"):
            path = Path(getattr(self, field)).resolve(strict=True)
            if not path.is_dir():
                raise ValueError(field + " must be an existing directory")
            object.__setattr__(self, field, path)
        runtime_info = self.runtime_root.stat()
        for name, owner_id in (("worker_uid", runtime_info.st_uid),
                               ("worker_gid", runtime_info.st_gid)):
            value = getattr(self, name)
            if value is None:
                value = owner_id
            if type(value) is not int or not 1 <= value <= 65535:
                raise ValueError(name + " must be an unprivileged numeric ID")
            if value != owner_id:
                raise ValueError(name + " must match the private runtime directory owner")
            object.__setattr__(self, name, value)
        if runtime_info.st_mode & 0o022:
            raise ValueError("private runtime directory must not be group or world writable")
        if any("," in str(getattr(self, field)) or "\n" in str(getattr(self, field)) for field in ("source_root", "toolchain_root", "runtime_root", "catalogue_root")):
            raise ValueError("Docker mount path contains unsupported delimiter")
        head = subprocess.run(["git", "-C", str(self.source_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        tree = subprocess.run(["git", "-C", str(self.source_root), "rev-parse",
                               self.source_commit + "^{tree}"],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(self.source_root), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5, check=True).stdout
        if head != self.source_commit or dirty:
            raise ValueError("source checkout must match pinned clean commit")
        object.__setattr__(self, "source_tree_oid", tree)
        if not re.fullmatch(r"[1-8]", self.cpu_limit):
            raise ValueError("CPU cap must be 1 through 8")
        if not re.fullmatch(r"[1-9][0-9]?(?:[mMgG])", self.memory_limit):
            raise ValueError("memory cap must use a bounded m/g quantity")
        if not 1 <= self.timeout_seconds <= 1800:
            raise ValueError("worker timeout exceeds configured bound")
        if not 65536 <= self.max_log_bytes <= 4 * 1024 * 1024:
            raise ValueError("invalid log cap")
        if not 1 <= self.max_artifact_bytes <= MAX_ARTIFACT_BYTES:
            raise ValueError("artifact cap exceeds service limit")
        if not 128 * 1024 * 1024 <= self.scratch_bytes <= 4 * 1024 * 1024 * 1024:
            raise ValueError("scratch cap exceeds configured bounds")


class DockerJobAdapter:
    """One bounded local Docker worker; suitable only for private prototype use."""
    def __init__(self, config: DockerWorkerConfig, *, capacity: int = 1,
                 clock=time.monotonic):
        if type(capacity) is not int or not 1 <= capacity <= 2:
            raise ValueError("Docker worker capacity must be one or two")
        self.config = config
        self.capacity = capacity
        self.clock = clock
        self.jobs: dict[str, WorkerSnapshot] = {}
        self.created: dict[str, float] = {}
        self.job_dirs: dict[str, Path] = {}
        self.threads: dict[str, threading.Thread] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.stopping = False
        self.lock = threading.RLock()
        self.semaphore = threading.BoundedSemaphore(capacity)

    def submit(self, build_id: str, request_bytes: bytes, request_sha256: str, template) -> None:
        if not _BUILD_ID.fullmatch(build_id):
            raise ValueError("invalid opaque build ID")
        if len(request_bytes) > MAX_BODY_BYTES:
            raise ValueError("request exceeds worker input cap")
        if hashlib.sha256(request_bytes).hexdigest() != request_sha256:
            raise ValueError("request digest mismatch")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", template.image_digest):
            raise ValueError("invalid image pin")
        if self.config.image_reference != template.image_digest:
            raise ValueError("request template differs from pinned worker image")
        with self.lock:
            if self.stopping:
                raise QueueFull
        if not self.semaphore.acquire(blocking=False):
            raise QueueFull
        with self.lock:
            if self.stopping:
                self.semaphore.release()
                raise QueueFull
            if build_id in self.jobs:
                self.semaphore.release()
                raise ValueError("duplicate build ID")
            try:
                base = self.config.runtime_root / build_id
                base.mkdir(mode=0o700)
                request_dir = base / "input"
                result_dir = base / "result"
                request_dir.mkdir(mode=0o700)
                result_dir.mkdir(mode=0o700)
                request_path = request_dir / "request.json"
                request_path.write_bytes(request_bytes)
                os.chmod(request_path, 0o400)
                archive_path = request_dir / "source.tar"
                subprocess.run(["git", "-C", str(self.config.source_root), "archive", "--format=tar",
                                "--output", str(archive_path), self.config.source_commit],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=30, check=True)
                if not 0 < archive_path.stat().st_size <= 128 * 1024 * 1024:
                    raise ValueError("source archive exceeds configured cap")
                os.chmod(archive_path, 0o400)
                worker_relpath = "tools/installer_service/docker_worker.py"
                worker_bytes = subprocess.run(
                    ["git", "-C", str(self.config.source_root), "show",
                     self.config.source_commit + ":" + worker_relpath],
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    timeout=10, check=True).stdout
                if not 0 < len(worker_bytes) <= 256 * 1024:
                    raise ValueError("pinned worker entrypoint exceeds configured cap")
                worker_path = request_dir / "docker_worker.py"
                worker_path.write_bytes(worker_bytes)
                os.chmod(worker_path, 0o400)
                worker_digest = hashlib.sha256(worker_bytes).hexdigest()
                digest_path = request_dir / "docker_worker.sha256"
                digest_path.write_text(worker_digest + "\n", encoding="ascii")
                os.chmod(digest_path, 0o400)
                catalogue_manifest = tree_manifest(self.config.catalogue_root)
                toolchain_manifest = tree_manifest(self.config.toolchain_root)
                for name, raw in (("catalogue-tree-manifest.json", catalogue_manifest),
                                  ("toolchain-tree-manifest.json", toolchain_manifest)):
                    path = request_dir / name
                    path.write_bytes(raw)
                    os.chmod(path, 0o400)
                binding = {
                    "schema": 1,
                    "source_commit": self.config.source_commit,
                    "source_tree_oid": self.config.source_tree_oid,
                    "source_archive_sha256": _sha256(archive_path.read_bytes()),
                    "worker_sha256": worker_digest,
                    "worker_image_digest": template.image_digest,
                    "catalogue_manifest_sha256": _sha256(catalogue_manifest),
                    "toolchain_manifest_sha256": _sha256(toolchain_manifest),
                    "request_sha256": request_sha256,
                }
                binding_path = request_dir / "host-bindings.json"
                binding_path.write_bytes(json.dumps(binding, sort_keys=True,
                    separators=(",", ":")).encode("ascii"))
                os.chmod(binding_path, 0o400)
            except Exception:
                if "base" in locals():
                    shutil.rmtree(base, ignore_errors=True)
                self.semaphore.release()
                raise
            self.job_dirs[build_id] = base
            self.created[build_id] = self.clock()
            self.jobs[build_id] = WorkerSnapshot("queued")
            worker = threading.Thread(target=self._run, args=(build_id,), daemon=True,
                                      name="lunar-build-" + build_id[:8])
            self.threads[build_id] = worker
            worker.start()

    def _command(self, build_id: str, base: Path) -> list[str]:
        cfg = self.config
        # All mount paths are constructed from trusted configured roots and the opaque ID.
        return [
            cfg.docker_binary, "run",
            "--name", "lunar-private-" + build_id,
            "--pull=never",
            "--label", "lan.project=lunar-modulator",
            "--label", "lan.session=installer-diagnostic-worker",
            "--cgroup-parent=docker-batch.slice", "--network=none", "--cpus=" + cfg.cpu_limit,
            "--memory=" + cfg.memory_limit, "--memory-swap=" + cfg.memory_limit,
            "--pids-limit=512", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=" + str(cfg.scratch_bytes),
            "--user", f"{cfg.worker_uid}:{cfg.worker_gid}",
            "--mount", "type=bind,src=" + str(base / "input" / "source.tar") + ",dst=/input/source.tar,readonly",
            "--mount", "type=bind,src=" + str(base / "input" / "docker_worker.py") + ",dst=/input/docker_worker.py,readonly",
            "--mount", "type=bind,src=" + str(cfg.toolchain_root) + ",dst=/opt/pi32v2,readonly",
            "--mount", "type=bind,src=" + str(cfg.catalogue_root) + ",dst=/input/catalogue,readonly",
            "--mount", "type=bind,src=" + str(base / "input" / "request.json") + ",dst=/input/request.json,readonly",
            "--mount", "type=bind,src=" + str(base / "result") + ",dst=/result",
            cfg.image_reference, "python3", "/input/docker_worker.py",
        ]

    def _set(self, build_id: str, snapshot: WorkerSnapshot):
        with self.lock:
            if build_id in self.jobs:
                self.jobs[build_id] = snapshot

    def _run(self, build_id: str):
        base = self.job_dirs[build_id]
        result_dir = base / "result"
        container_name = "lunar-private-" + build_id
        self._set(build_id, WorkerSnapshot("running"))
        proc = None
        log = bytearray()
        outcome = WorkerSnapshot("failed")

        try:
            cmd = self._command(build_id, base)
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    close_fds=True)
            with self.lock:
                self.processes[build_id] = proc
                stopping = self.stopping
            if stopping:
                proc.kill()
                raise RuntimeError("service is shutting down")
            if proc.stdout is None:
                raise RuntimeError("Docker worker output pipe is unavailable")
            fd = proc.stdout.fileno()
            os.set_blocking(fd, False)
            deadline = time.monotonic() + self.config.timeout_seconds
            drain_deadline = None
            eof = False
            while True:
                returncode = proc.poll()
                now = time.monotonic()
                if returncode is None and now >= deadline:
                    raise TimeoutError("worker exceeded time limit")
                if returncode is not None and drain_deadline is None:
                    drain_deadline = now + 5.0
                if eof:
                    if returncode is not None:
                        break
                    time.sleep(0.1)
                    continue
                ready, _, _ = select.select([fd], [], [], 0.1)
                if ready:
                    try:
                        block = os.read(fd, 65536)
                    except BlockingIOError:
                        block = None
                    if block == b"":
                        eof = True
                    elif block:
                        room = self.config.max_log_bytes - len(log)
                        if len(block) > room:
                            if room > 0:
                                log.extend(block[:room])
                            raise RuntimeError("worker log exceeded configured cap")
                        log.extend(block)
                if (drain_deadline is not None and not eof
                        and time.monotonic() >= drain_deadline):
                    raise TimeoutError("worker output pipe did not close after process exit")
            if proc.returncode != 0:
                raise RuntimeError("diagnostic worker failed")
            artifact_path = result_dir / "app.bin"
            elf_path = result_dir / "elf.bin"
            receipt_path = result_dir / "image.json"
            for path in (artifact_path, elf_path, receipt_path):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("worker omitted a required regular output file")
            artifact_size = artifact_path.stat().st_size
            elf_size = elf_path.stat().st_size
            receipt_size = receipt_path.stat().st_size
            if (not 0 < artifact_size <= self.config.max_artifact_bytes
                    or not 0 < elf_size <= MAX_ELF_BYTES or not 0 < receipt_size <= 65536):
                raise ValueError("worker output exceeds configured cap")
            artifact = artifact_path.read_bytes()
            elf = elf_path.read_bytes()
            receipt = receipt_path.read_bytes()
            if (len(artifact) != artifact_size or len(elf) != elf_size
                    or len(receipt) != receipt_size):
                raise ValueError("worker output changed while being collected")
            input_dir = base / "input"
            binding_raw = (input_dir / "host-bindings.json").read_bytes()
            binding = json.loads(binding_raw, object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            expected_binding_keys = {"schema", "source_commit", "source_tree_oid",
                "source_archive_sha256", "worker_sha256", "worker_image_digest",
                "catalogue_manifest_sha256", "toolchain_manifest_sha256", "request_sha256"}
            catalogue_manifest = (input_dir / "catalogue-tree-manifest.json").read_bytes()
            toolchain_manifest = (input_dir / "toolchain-tree-manifest.json").read_bytes()
            if (not isinstance(binding, dict) or set(binding) != expected_binding_keys
                    or type(binding.get("schema")) is not int or binding["schema"] != 1
                    or binding.get("source_commit") != self.config.source_commit
                    or binding.get("source_tree_oid") != self.config.source_tree_oid
                    or binding.get("worker_image_digest") != self.config.image_reference
                    or _sha256(catalogue_manifest) != binding.get("catalogue_manifest_sha256")
                    or _sha256(toolchain_manifest) != binding.get("toolchain_manifest_sha256")
                    or tree_manifest(self.config.catalogue_root) != catalogue_manifest
                    or tree_manifest(self.config.toolchain_root) != toolchain_manifest
                    or _sha256((input_dir / "request.json").read_bytes()) != binding.get("request_sha256")
                    or _sha256((input_dir / "source.tar").read_bytes()) != binding.get("source_archive_sha256")
                    or _sha256((input_dir / "docker_worker.py").read_bytes()) != binding.get("worker_sha256")):
                raise ValueError("build provenance inputs changed during worker execution")
            try:
                receipt_object = json.loads(receipt.decode("utf-8"), object_pairs_hook=_unique_object,
                                         parse_constant=_reject_constant)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                raise ValueError("worker image receipt is malformed") from exc
            if not isinstance(receipt_object, dict):
                raise ValueError("worker image receipt must be an object")
            provenance = make_diagnostic_provenance(
                bindings={key: value for key, value in binding.items()
                          if key not in ("request_sha256", "schema")},
                request_sha256=binding["request_sha256"], artifact=artifact, elf=elf,
                receipt_raw=receipt, receipt=receipt_object)
            provenance_path = result_dir / "provenance.json"
            provenance_path.write_bytes(provenance)
            os.chmod(provenance_path, 0o600)
            private_evidence = read_private_evidence(
                result_dir, (input_dir / "request.json").read_bytes(), receipt,
                self.config.catalogue_root)
            outcome = WorkerSnapshot(
                "succeeded", WorkerResult(artifact, receipt, elf, provenance, private_evidence))
        except Exception:
            outcome = WorkerSnapshot("failed")
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    outcome = WorkerSnapshot("failed")
            if proc is not None and proc.stdout is not None:
                try:
                    proc.stdout.close()
                except (OSError, ValueError):
                    outcome = WorkerSnapshot("failed")
            try:
                removed = None
                for attempt in range(2):
                    removed = subprocess.run(
                        [self.config.docker_binary, "rm", "--force", container_name],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=10, check=False)
                    if removed.returncode == 0:
                        break
                    if attempt == 0:
                        time.sleep(0.2)
                if removed is None or removed.returncode != 0:
                    outcome = WorkerSnapshot("failed")
            except Exception:
                outcome = WorkerSnapshot("failed")
            try:
                log_path = base / "worker.log"
                log_path.write_bytes(bytes(log[:self.config.max_log_bytes]))
                os.chmod(log_path, 0o600)
            except OSError:
                outcome = WorkerSnapshot("failed")
            with self.lock:
                self.processes.pop(build_id, None)
                self.threads.pop(build_id, None)
                if build_id in self.jobs:
                    self.jobs[build_id] = outcome
            self.semaphore.release()

    def shutdown(self, timeout_seconds: float = 30.0) -> None:
        # Stop admission, kill active named containers, and boundedly drain workers.
        if not isinstance(timeout_seconds, (int, float)) or not 1 <= timeout_seconds <= 120:
            raise ValueError("shutdown timeout must be between 1 and 120 seconds")
        with self.lock:
            self.stopping = True
            active = [build_id for build_id, snapshot in self.jobs.items()
                      if snapshot.status in ("queued", "running")]
            workers = {build_id: self.threads.get(build_id) for build_id in active}
            processes = {build_id: self.processes.get(build_id) for build_id in active}
        for build_id, proc in processes.items():
            if proc is not None and proc.poll() is None:
                try:
                    proc.kill()
                except OSError:
                    pass
        for build_id in active:
            try:
                subprocess.run(
                    [self.config.docker_binary, "rm", "--force", "lunar-private-" + build_id],
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=5, check=False)
            except Exception:
                pass
        end = time.monotonic() + timeout_seconds
        for worker in workers.values():
            if worker is not None:
                worker.join(max(0.0, end - time.monotonic()))
        with self.lock:
            survivors = [build_id for build_id in active
                         if (worker := self.threads.get(build_id)) is not None and worker.is_alive()]
            survivor_procs = {build_id: self.processes.get(build_id) for build_id in survivors}
        if survivors:
            for build_id, proc in survivor_procs.items():
                if proc is not None and proc.poll() is None:
                    try:
                        proc.kill()
                    except OSError:
                        pass
                try:
                    subprocess.run(
                        [self.config.docker_binary, "rm", "--force", "lunar-private-" + build_id],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL, timeout=5, check=False)
                except Exception:
                    pass
            raise TimeoutError("installer workers did not drain before shutdown deadline")

    def get(self, build_id: str) -> WorkerSnapshot | None:
        with self.lock:
            return self.jobs.get(build_id)

    def delete(self, build_id: str) -> None:
        with self.lock:
            self.jobs.pop(build_id, None)
            self.created.pop(build_id, None)
            base = self.job_dirs.pop(build_id, None)
        if base is not None:
            shutil.rmtree(base, ignore_errors=True)

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
from .docker_worker import (GENERATED_EVIDENCE_PATHS, generated_evidence_paths,
                            SELECTED_TRIO_PROFILE, selected_external_inputs,
                            selected_compile_flags, load_selected_builder)
from .provenance import (make_diagnostic_provenance, sha256 as _sha256,
                         tree_manifest)
from .process_capture import run_bounded

_BUILD_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
_CONTAINER_ID = re.compile(rb"[0-9a-f]{64}\n?\Z")
_DOCKER_CAPTURE_CAP = 65536
_CONTAINER_SESSION = "installer-diagnostic-worker"
# The service deliberately pins the locally provisioned image ID.  A Docker
# image ID is an immutable sha256 digest but is not a repository-qualified
# pull reference; treating it as one makes Docker try to pull a nonexistent
# repository name.
_IMAGE_ID = "sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495"
_MAX_PRIVATE_EVIDENCE_FILE = 128 * 1024 * 1024
_MAX_PRIVATE_EVIDENCE_TOTAL = 512 * 1024 * 1024
_CATALOGUE_MOUNT = "/catalogue/"
_BUILD_LINK_MOUNT = "/output/build/link/"
_SELECTED_EVIDENCE_CAP = 16 * 1024 * 1024
_SELECTED_RETAINED_JOBS = 4


def _remove_owned_container(docker: str, build_id: str, base: Path) -> bool:
    """Remove only the immutable ID Docker wrote for this job, after inspection.

    A failed `docker run` may be a name collision. The generated name alone is
    never authority to remove a container, even during shutdown.
    """
    name = "lunar-private-" + build_id
    try:
        cid = _read_private_file(base / "input" / "container.id", 65,
                                 nonblocking_open=True)
        if not _CONTAINER_ID.fullmatch(cid):
            return False
        cid_text = cid.decode("ascii").strip()

        def capture(args):
            result = run_bounded([docker, *args], cwd=base, timeout_seconds=10,
                                 max_stream_bytes=_DOCKER_CAPTURE_CAP)
            if (result.returncode != 0 or result.failure_reason is not None
                    or any(result.observed[stream] > _DOCKER_CAPTURE_CAP
                           for stream in ("stdout", "stderr"))):
                return None
            return result.logs["stdout"]

        raw = capture(["container", "inspect", "--format", "{{json .}}", cid_text])
        if raw is None:
            return False
        inspected = json.loads(raw)
        if not isinstance(inspected, dict):
            return False
        config = inspected.get("Config")
        labels = config.get("Labels") if isinstance(config, dict) else None
        if (inspected.get("Id") != cid_text or inspected.get("Name") != "/" + name
                or not isinstance(labels, dict)
                or labels.get("lan.project") != "lunar-modulator"
                or labels.get("lan.session") != _CONTAINER_SESSION
                or labels.get("lan.owner") != name):
            return False
        return capture(["rm", "--force", cid_text]) is not None
    except Exception:
        # Any Docker, capture, or inspection failure leaves ownership unproven.
        return False


def _scratch_tmpfs(budget: int, uid: int, gid: int) -> list[str]:
    """Partition one configured budget across canonical paths, in Linux pages."""
    # Floor the total before partitioning: Docker rounds each tmpfs size to a
    # page, so arbitrary byte sizes must not silently exceed the combined cap.
    pages = budget // 4096
    workspace_pages = pages // 8
    output_pages = 3 * pages // 8
    tmp_pages = pages - workspace_pages - output_pages
    private = f",mode=0700,uid={uid},gid={gid}"
    return [
        "/tmp:rw,nosuid,nodev,exec,size=" + str(tmp_pages * 4096),
        "/workspace:rw,nosuid,nodev,exec,size=" + str(workspace_pages * 4096) + private,
        "/output:rw,nosuid,nodev,exec,size=" + str(output_pages * 4096) + private,
    ]


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


def _read_private_file(path: Path, limit: int, expected_size: int | None = None,
                       *, nonblocking_open: bool = False) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    if nonblocking_open:
        flags |= os.O_NONBLOCK  # A planted FIFO must not block before fstat.
    descriptor = os.open(path, flags)
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
                          catalogue_root: Path | None, *, selected: bool = False) -> dict[str, bytes]:
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
    aggregate_cap = _SELECTED_EVIDENCE_CAP if selected else _MAX_PRIVATE_EVIDENCE_TOTAL
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
        if declared_total > aggregate_cap:
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
    if selected:
        required = {"request.json", "host-bindings.json", "image_receipt.json", "anchors.json",
                    "metadata.json", "host-build.log", "build.log",
                    *("prepared/" + name for name in ("selected_project.bin", "selected_project_blob.c",
                                                      "selected_project_blob.h", "receipt.json"))}
        objects = {name for name in evidence if name.startswith("objects/")}
        if not objects or any(not name.endswith(".o") for name in objects) or set(evidence) != required | objects:
            raise ValueError("selected evidence differs from its fixed inventory")
        actual = set()
        for path in root.rglob("*"):
            if path.is_symlink() or not (path.is_file() or path.is_dir()):
                raise ValueError("selected evidence contains an unsafe entry")
            if path.is_file():
                actual.add(path.relative_to(root).as_posix())
        if actual != set(manifest) | {"manifest.json"}:
            raise ValueError("selected evidence files differ from manifest")
        return evidence
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
            validate_image_receipt(image, selected, lower_receipt=build)
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
    memory_limit: str = "6g"
    scratch_bytes: int = 3 * 1024 * 1024 * 1024
    timeout_seconds: int = 1500
    max_log_bytes: int = 1024 * 1024
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES
    # Operator-owned fixed-profile inputs. The default retains all legacy gates.
    profile_id: str | None = None
    toolchain_archive: Path | None = None
    cxx_headers: Path | None = None
    source_tree_oid: str = field(init=False, repr=False)

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{40}", self.source_commit):
            raise ValueError("source must be pinned to a full Git commit")
        if self.image_reference != _IMAGE_ID:
            raise ValueError("worker image must match the reviewed immutable image")
        selected = self.profile_id == SELECTED_TRIO_PROFILE
        if self.profile_id not in (None, SELECTED_TRIO_PROFILE):
            raise ValueError("unsupported fixed worker profile")
        if not selected and self.catalogue_root is None:
            raise ValueError("fixed verified catalogue cache is required")
        if selected and (self.toolchain_archive is None or self.cxx_headers is None):
            raise ValueError("selected worker requires original archive and libc++ headers")
        if selected:
            for name in ("toolchain_archive", "cxx_headers"):
                original = Path(getattr(self, name))
                if original.absolute() != original.resolve(strict=True):
                    raise ValueError("selected mount must be canonical")
        directories = ("source_root", "toolchain_root", "runtime_root") + (
            ("cxx_headers",) if selected else ("catalogue_root",))
        for field in directories:
            path = Path(getattr(self, field)).resolve(strict=True)
            if not path.is_dir():
                raise ValueError(field + " must be an existing directory")
            object.__setattr__(self, field, path)
        if selected:
            for name in ("toolchain_archive", "cxx_headers"):
                original = Path(getattr(self, name))
                resolved = original.resolve(strict=True)
                if original.absolute() != resolved or "," in str(resolved) or "\n" in str(resolved):
                    raise ValueError("selected mount must be canonical and delimiter-free")
                if name == "toolchain_archive" and not resolved.is_file():
                    raise ValueError("original toolchain archive must be a regular file")
                object.__setattr__(self, name, resolved)
            # Writable job storage must never be nested in, or contain, a
            # supposedly read-only operator input. Otherwise collecting/deleting
            # an owned job could mutate an input mounted into another build.
            for name in ("source_root", "toolchain_root", "cxx_headers", "toolchain_archive"):
                path = getattr(self, name)
                if path.is_relative_to(self.runtime_root) or self.runtime_root.is_relative_to(path):
                    raise ValueError("selected runtime storage overlaps a read-only input")
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
        if any("," in str(getattr(self, field)) or "\n" in str(getattr(self, field)) for field in directories):
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
        if not re.fullmatch(r"[1-4]", self.cpu_limit):
            raise ValueError("CPU cap must be 1 through 4")
        if not re.fullmatch(r"[1-9][0-9]{0,3}(?:[mMgG])", self.memory_limit):
            raise ValueError("memory cap must use a bounded m/g quantity")
        memory_bytes = int(self.memory_limit[:-1]) * (1024 ** (3 if self.memory_limit[-1].lower() == "g" else 2))
        if memory_bytes > 6 * 1024 ** 3:
            raise ValueError("memory cap exceeds 6 GiB")
        if not 1 <= self.timeout_seconds <= 1800:
            raise ValueError("worker timeout exceeds configured bound")
        if not 65536 <= self.max_log_bytes <= 4 * 1024 * 1024:
            raise ValueError("invalid log cap")
        if not 1 <= self.max_artifact_bytes <= MAX_ARTIFACT_BYTES:
            raise ValueError("artifact cap exceeds service limit")
        if (type(self.scratch_bytes) is not int
                or not 128 * 1024 * 1024 <= self.scratch_bytes <= 4 * 1024 * 1024 * 1024):
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
        self.selected_inputs: dict[str, dict] = {}
        self.selected_verified: dict[str, tuple] = {}
        self.created: dict[str, float] = {}
        self.job_dirs: dict[str, Path] = {}
        self.threads: dict[str, threading.Thread] = {}
        self.processes: dict[str, subprocess.Popen] = {}
        self.cleanup_confirmed: set[str] = set()
        self.cleanup_unconfirmed: set[str] = set()
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
        if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
            from .selected_trio_profile import validate_request
            validate_request(request_bytes)
        with self.lock:
            if self.cleanup_unconfirmed:
                raise RuntimeError("prior installer container cleanup is unconfirmed")
            if self.stopping:
                raise QueueFull
        if not self.semaphore.acquire(blocking=False):
            raise QueueFull
        with self.lock:
            if self.cleanup_unconfirmed:
                self.semaphore.release()
                raise RuntimeError("prior installer container cleanup is unconfirmed")
            if self.stopping:
                self.semaphore.release()
                raise QueueFull
            if build_id in self.jobs:
                self.semaphore.release()
                raise ValueError("duplicate build ID")
            if (getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE and
                    len(self.jobs) >= _SELECTED_RETAINED_JOBS):
                self.semaphore.release()
                raise QueueFull
            created_base = False
            try:
                base = self.config.runtime_root / build_id
                base.mkdir(mode=0o700)
                created_base = True
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
                selected = getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE
                catalogue_manifest = (tree_manifest(self.config.cxx_headers) if selected else
                                      tree_manifest(self.config.catalogue_root))
                toolchain_manifest = tree_manifest(self.config.toolchain_root)
                if selected:
                    external = selected_external_inputs(
                        self.config.source_root, self.config.toolchain_root,
                        self.config.toolchain_archive, self.config.cxx_headers)
                headers_name = "cxx-headers-manifest.json" if selected else "catalogue-tree-manifest.json"
                for name, raw in ((headers_name, catalogue_manifest),
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
                if selected:
                    binding["schema"] = 2
                    binding["profile_id"] = SELECTED_TRIO_PROFILE
                    binding["cxx_headers_manifest_sha256"] = binding.pop("catalogue_manifest_sha256")
                    binding["toolchain_archive_sha256"] = external["toolchain_binding"]["archive_sha256"]
                binding_path = request_dir / "host-bindings.json"
                binding_path.write_bytes(json.dumps(binding, sort_keys=True,
                    separators=(",", ":")).encode("ascii"))
                os.chmod(binding_path, 0o400)
                if selected:
                    self.selected_inputs[build_id] = dict(
                        external=external, binding=json.loads(binding_path.read_bytes()),
                        binding_raw=binding_path.read_bytes(), request=request_bytes,
                        toolchain_manifest=toolchain_manifest, headers_manifest=catalogue_manifest)
            except Exception:
                if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
                    self._rollback_selected_submission(build_id, base if created_base else None)
                else:
                    if created_base:
                        shutil.rmtree(base, ignore_errors=True)
                self.semaphore.release()
                raise
            self.job_dirs[build_id] = base
            self.created[build_id] = self.clock()
            self.jobs[build_id] = WorkerSnapshot("queued")
            try:
                worker = threading.Thread(target=self._run, args=(build_id,), daemon=True,
                                          name="lunar-build-" + build_id[:8])
                self.threads[build_id] = worker
                worker.start()
            except Exception:
                if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
                    self.threads.pop(build_id, None)
                    self._rollback_selected_submission(build_id, base)
                    self.semaphore.release()
                raise

    def _rollback_selected_submission(self, build_id: str, base: Path | None) -> None:
        """Retain ownership/capacity if an unstarted job cannot be removed.

        Called under the admission lock before a worker thread has started.
        No container exists in this path, so only filesystem removal is pending.
        """
        removed = base is None
        if base is not None:
            try:
                shutil.rmtree(base)
                removed = not base.exists() and not base.is_symlink()
            except OSError:
                removed = False
        if removed:
            self.jobs.pop(build_id, None)
            self.job_dirs.pop(build_id, None)
            self.created.pop(build_id, None)
            self.selected_inputs.pop(build_id, None)
            self.selected_verified.pop(build_id, None)
            self.cleanup_confirmed.discard(build_id)
        else:
            self.job_dirs[build_id] = base
            self.created[build_id] = self.clock()
            self.jobs[build_id] = WorkerSnapshot("failed")
            self.cleanup_confirmed.add(build_id)  # No container was launched.

    def _command(self, build_id: str, base: Path) -> list[str]:
        cfg = self.config
        # All mount paths are constructed from trusted configured roots and the opaque ID.
        return [
            cfg.docker_binary, "run",
            "--name", "lunar-private-" + build_id,
            "--cidfile", str(base / "input" / "container.id"),
            "--pull=never",
            "--label", "lan.project=lunar-modulator",
            "--label", "lan.session=" + _CONTAINER_SESSION,
            "--label", "lan.owner=lunar-private-" + build_id,
            "--cgroup-parent=docker-batch.slice", "--network=none", "--cpuset-cpus=4-7", "--cpus=" + cfg.cpu_limit,
            "--memory=" + cfg.memory_limit, "--memory-swap=" + cfg.memory_limit,
            "--log-driver=json-file", "--log-opt=max-size=1m", "--log-opt=max-file=1",
            "--pids-limit=512", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            *[item for mount in _scratch_tmpfs(cfg.scratch_bytes, cfg.worker_uid, cfg.worker_gid)
              for item in ("--tmpfs", mount)],
            "--user", f"{cfg.worker_uid}:{cfg.worker_gid}",
            "--mount", "type=bind,src=" + str(base / "input" / "source.tar") + ",dst=/input/source.tar,readonly",
            "--mount", "type=bind,src=" + str(base / "input" / "docker_worker.py") + ",dst=/input/docker_worker.py,readonly",
            "--mount", "type=bind,src=" + str(cfg.toolchain_root) + ",dst=/opt/pi32v2,readonly",
            *(["--mount", "type=bind,src=" + str(cfg.toolchain_archive) + ",dst=/opt/lunar-toolchain.tar,readonly",
               "--mount", "type=bind,src=" + str(cfg.cxx_headers) + ",dst=/opt/original-libcxx,readonly",
               "--mount", "type=bind,src=" + str(base / "input/host-bindings.json") +
               ",dst=/input/host-bindings.json,readonly"]
              if getattr(cfg, "profile_id", None) == SELECTED_TRIO_PROFILE else
              ["--mount", "type=bind,src=" + str(cfg.catalogue_root) + ",dst=/catalogue,readonly"]),
            "--mount", "type=bind,src=" + str(base / "input" / "request.json") + ",dst=/input/request.json,readonly",
            "--mount", "type=bind,src=" + str(base / "result") + ",dst=/result",
            cfg.image_reference, "python3", "/input/docker_worker.py",
        ]

    def _collect_selected_result(self, build_id, base, artifact, elf, receipt):
        """Bind actual worker evidence to previously acquired operator inputs."""
        from .selected_trio_profile import TrustedInputs, validate_receipt
        saved = self.selected_inputs[build_id]
        binding = saved["binding"]
        input_dir = base / "input"
        request = _read_private_file(input_dir / "request.json", MAX_BODY_BYTES)
        if (request != saved["request"] or
                _read_private_file(input_dir / "host-bindings.json", 4 * 1024 * 1024) != saved["binding_raw"]):
            raise ValueError("selected job binding changed")
        for name, key in (("source.tar", "source_archive_sha256"),
                          ("docker_worker.py", "worker_sha256")):
            if _sha256(_read_private_file(input_dir / name, 128 * 1024 * 1024)) != binding[key]:
                raise ValueError("selected pinned job input changed")
        if (tree_manifest(self.config.toolchain_root) != saved["toolchain_manifest"] or
                tree_manifest(self.config.cxx_headers) != saved["headers_manifest"] or
                selected_external_inputs(self.config.source_root, self.config.toolchain_root,
                                         self.config.toolchain_archive, self.config.cxx_headers) != saved["external"]):
            raise ValueError("selected operator inputs changed during worker execution")
        evidence = read_private_evidence(base / "result", request, receipt, None, selected=True)
        if evidence["host-bindings.json"] != saved["binding_raw"]:
            raise ValueError("worker evidence substituted host bindings")
        anchors = json.loads(evidence["anchors.json"], object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
        expected_keys = set(saved["external"]) | {"compile_flags", "compiler_version", "audit_sources", "host_tools"}
        if not isinstance(anchors, dict) or set(anchors) != expected_keys:
            raise ValueError("selected worker anchors have an unsupported shape")
        for name, expected in saved["external"].items():
            if anchors[name] != expected:
                raise ValueError("selected worker anchor differs from operator input: " + name)
        if anchors["compile_flags"] != selected_compile_flags():
            raise ValueError("selected worker changed fixed compile recipe")
        # Audit source roots are independently read from the pinned source, not
        # selected from paths or claims supplied in the worker's receipt.
        builder = load_selected_builder(self.config.source_root)
        audit_sources = tuple(builder.collect_sources([
            str(self.config.source_root / "firmware/native"),
            str(self.config.source_root / "firmware/third_party/dinghy")]))
        # collect_sources records absolute names, so compare exact source text,
        # line and relative source path across the two fixed root namespaces.
        def normalized(rows, root):
            return tuple((str(Path(name).relative_to(root)), line, text) for name, line, text in rows)
        if normalized(anchors["audit_sources"], Path("/workspace")) != normalized(audit_sources, self.config.source_root):
            raise ValueError("selected worker audit sources differ from pinned source")
        metadata = evidence["metadata.json"]
        if len(metadata) > 1048576:
            raise ValueError("selected host metadata exceeds cap")
        # These two executable hashes are acquired by the pinned worker from
        # its freshly built tools before preparing the candidate, not copied
        # from the receipt being checked. Reproducible host binaries are not
        # retained in every API record. Metadata bytes are independently held.
        host_tools = anchors["host_tools"]
        if (not isinstance(host_tools, dict) or set(host_tools) != {"renderer", "state_tool", "metadata"} or
                any(type(v) is not str or not re.fullmatch(r"[0-9a-f]{64}", v) for v in host_tools.values()) or
                host_tools["metadata"] != _sha256(metadata)):
            raise ValueError("selected worker host-tool anchors are malformed")
        trusted = TrustedInputs(
            binding["source_commit"], binding["source_tree_oid"],
            dict(saved["external"]["source_manifest"]),
            saved["external"]["toolchain_binding"],
            dict(saved["external"]["cxx_headers_manifest"]),
            dict(saved["external"]["configured_cxx_headers_manifest"]), host_tools,
            {name.removeprefix("prepared/"): raw for name, raw in evidence.items() if name.startswith("prepared/")},
            {name.removeprefix("objects/"): raw for name, raw in evidence.items() if name.startswith("objects/")},
            tuple(tuple(row) for row in anchors["audit_sources"]),
            tuple(selected_compile_flags()), anchors["compiler_version"])
        summary = validate_receipt(request, receipt, app=artifact, elf=elf, trusted=trusted)
        provenance = json.dumps(dict(schema=2, profile_id=SELECTED_TRIO_PROFILE,
            host_bindings=binding, validation=summary), sort_keys=True, separators=(",", ":")).encode()
        result = WorkerResult(artifact, receipt, elf, provenance, evidence)
        self.selected_verified[build_id] = (request, trusted, self._selected_result_fingerprint(result))
        return result

    @staticmethod
    def _selected_result_fingerprint(result):
        evidence = result.private_evidence
        if (type(result.artifact) is not bytes or not 0 < len(result.artifact) <= MAX_ARTIFACT_BYTES or
                type(result.elf) is not bytes or not 0 < len(result.elf) <= MAX_ELF_BYTES or
                type(result.receipt) is not bytes or not 0 < len(result.receipt) <= 4 * 1024 * 1024 or
                type(result.provenance) is not bytes or not 0 < len(result.provenance) <= 4 * 1024 * 1024 or
                not isinstance(evidence, dict) or not 0 < len(evidence) <= 8192 or
                any(type(k) is not str or type(v) is not bytes for k, v in evidence.items()) or
                sum(map(len, evidence.values())) > _SELECTED_EVIDENCE_CAP):
            raise ValueError("selected result exceeds bounded verification inputs")
        return (_sha256(result.artifact), _sha256(result.elf), _sha256(result.receipt),
                _sha256(result.provenance), tuple(sorted((k, _sha256(v)) for k, v in evidence.items())))

    def verify_selected_trio_result(self, build_id, request_bytes, result):
        """Pure revalidation of a completed job using private, acquired anchors.

        No process, file, mount or external-input acquisition occurs here. A
        result envelope's validation claims cannot seed its own trusted inputs.
        The API may call this in its bounded verification executor.
        """
        from .selected_trio_profile import validate_receipt
        with self.lock:
            snapshot = self.jobs.get(build_id)
            saved = self.selected_verified.get(build_id)
            if (getattr(self.config, "profile_id", None) != SELECTED_TRIO_PROFILE or
                    snapshot is None or snapshot.status != "succeeded" or saved is None or
                    build_id not in self.cleanup_confirmed or build_id in self.cleanup_unconfirmed):
                raise ValueError("no verified selected job is available")
        request, trusted, fingerprint = saved
        if request_bytes != request or self._selected_result_fingerprint(result) != fingerprint:
            raise ValueError("selected result differs from the recorded job")
        return validate_receipt(request, result.receipt, app=result.artifact, elf=result.elf, trusted=trusted)

    def _set(self, build_id: str, snapshot: WorkerSnapshot):
        with self.lock:
            if build_id in self.jobs:
                self.jobs[build_id] = snapshot

    def _cleanup_container(self, build_id: str, base: Path) -> bool:
        # Shutdown and a worker finalizer may race. Serialize their Docker
        # inspection/removal so an already removed ID is not treated as foreign.
        with self.lock:
            if build_id in self.cleanup_confirmed:
                return True
            if _remove_owned_container(self.config.docker_binary, build_id, base):
                self.cleanup_confirmed.add(build_id)
                self.cleanup_unconfirmed.discard(build_id)
                return True
            self.cleanup_unconfirmed.add(build_id)
            return False

    def _run(self, build_id: str):
        base = self.job_dirs[build_id]
        result_dir = base / "result"
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
                    or not 0 < elf_size <= MAX_ELF_BYTES or not 0 < receipt_size <= (4 * 1024 * 1024 if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE else 65536)):
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
            if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
                selected_result = self._collect_selected_result(build_id, base, artifact, elf, receipt)
                outcome = WorkerSnapshot("succeeded", selected_result)
            else:
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
                private_evidence = read_private_evidence(
                    result_dir, (input_dir / "request.json").read_bytes(), receipt,
                    self.config.catalogue_root)
                lower_receipt = None
                if ((receipt_object.get("runtime_configuration") or {}).get("runtime_mode")
                        == "continuous"):
                    lower_receipt = json.loads(
                        private_evidence["build_receipt.json"].decode("utf-8"),
                        object_pairs_hook=_unique_object, parse_constant=_reject_constant)
                provenance = make_diagnostic_provenance(
                    bindings={key: value for key, value in binding.items()
                              if key not in ("request_sha256", "schema")},
                    request_sha256=binding["request_sha256"], artifact=artifact, elf=elf,
                    receipt_raw=receipt, receipt=receipt_object, lower_receipt=lower_receipt)
                provenance_path = result_dir / "provenance.json"
                provenance_path.write_bytes(provenance)
                os.chmod(provenance_path, 0o600)
                outcome = WorkerSnapshot(
                    "succeeded", WorkerResult(artifact, receipt, elf, provenance, private_evidence))

        except Exception as error:
            if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
                # Private diagnostic only, bounded by the existing worker log cap.
                diagnostic = ("\nSelected worker refusal: " + type(error).__name__ +
                              ": " + str(error)[:2000] + "\n").encode(errors="replace")
                log.extend(diagnostic[:max(0, self.config.max_log_bytes - len(log))])
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
            if not self._cleanup_container(build_id, base):
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
        # Stop admission, kill active clients, and boundedly drain workers.
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
                base = self.job_dirs.get(build_id)
                if base is not None:
                    self._cleanup_container(build_id, base)
            raise TimeoutError("installer workers did not drain before shutdown deadline")
        if self.cleanup_unconfirmed:
            raise RuntimeError("installer container cleanup was not confirmed; job evidence retained")

    def get(self, build_id: str) -> WorkerSnapshot | None:
        with self.lock:
            return self.jobs.get(build_id)

    def delete(self, build_id: str) -> None:
        with self.lock:
            if build_id in self.cleanup_unconfirmed:
                return  # Keep both the job and its exact private evidence for recovery.
            base = self.job_dirs.get(build_id)
            if getattr(self.config, "profile_id", None) == SELECTED_TRIO_PROFILE:
                snapshot = self.jobs.get(build_id)
                if snapshot is not None and (snapshot.status in ("queued", "running") or
                                             build_id not in self.cleanup_confirmed):
                    return
                if base is not None:
                    # Keep the record/capacity on an uncertain removal. The API
                    # confirms absence through get() before forgetting admission.
                    try:
                        if base.exists() or base.is_symlink():
                            shutil.rmtree(base)
                        if base.exists() or base.is_symlink():
                            return
                    except OSError:
                        return
            self.jobs.pop(build_id, None)
            self.selected_inputs.pop(build_id, None)
            self.selected_verified.pop(build_id, None)
            self.created.pop(build_id, None)
            self.cleanup_confirmed.discard(build_id)
            base = self.job_dirs.pop(build_id, None)
        if base is not None:
            shutil.rmtree(base, ignore_errors=True)

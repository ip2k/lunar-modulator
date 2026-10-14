# SPDX-License-Identifier: MIT
"""Fixed-input, private Docker adapter for diagnostic builds.

No request field is interpreted as a host path, image, command, or mount.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

from .api import MAX_ARTIFACT_BYTES, MAX_BODY_BYTES, QueueFull, WorkerResult, WorkerSnapshot

_BUILD_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
_IMAGE = "lunar-recovery-pytest@sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d"


@dataclass(frozen=True)
class DockerWorkerConfig:
    source_root: Path
    toolchain_root: Path
    runtime_root: Path
    source_commit: str
    catalogue_root: Path | None = None
    image_reference: str = _IMAGE
    docker_binary: str = "docker"
    cpu_limit: str = "4"
    memory_limit: str = "8g"
    scratch_bytes: int = 3 * 1024 * 1024 * 1024
    timeout_seconds: int = 1500
    max_log_bytes: int = 1024 * 1024
    max_artifact_bytes: int = MAX_ARTIFACT_BYTES

    def __post_init__(self):
        if not re.fullmatch(r"[0-9a-f]{40}", self.source_commit):
            raise ValueError("source must be pinned to a full Git commit")
        if self.image_reference != _IMAGE:
            raise ValueError("worker image must match the reviewed immutable image")
        if self.catalogue_root is None:
            raise ValueError("fixed verified catalogue cache is required")
        for field in ("source_root", "toolchain_root", "runtime_root", "catalogue_root"):
            path = Path(getattr(self, field)).resolve(strict=True)
            if not path.is_dir():
                raise ValueError(field + " must be an existing directory")
            object.__setattr__(self, field, path)
        if any("," in str(getattr(self, field)) or "\n" in str(getattr(self, field)) for field in ("source_root", "toolchain_root", "runtime_root", "catalogue_root")):
            raise ValueError("Docker mount path contains unsupported delimiter")
        head = subprocess.run(["git", "-C", str(self.source_root), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=5, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(self.source_root), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, timeout=5, check=True).stdout
        if head != self.source_commit or dirty:
            raise ValueError("source checkout must match pinned clean commit")
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
        if self.config.image_reference.split("@", 1)[-1] != template.image_digest:
            raise ValueError("request template differs from pinned worker image")
        if not self.semaphore.acquire(blocking=False):
            raise QueueFull
        with self.lock:
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
            except Exception:
                if "base" in locals():
                    shutil.rmtree(base, ignore_errors=True)
                self.semaphore.release()
                raise
            self.job_dirs[build_id] = base
            self.created[build_id] = self.clock()
            self.jobs[build_id] = WorkerSnapshot("queued")
        threading.Thread(target=self._run, args=(build_id,), daemon=True,
                         name="lunar-build-" + build_id[:8]).start()

    def _command(self, build_id: str, base: Path, cidfile: Path) -> list[str]:
        cfg = self.config
        # All mount paths are constructed from trusted configured roots and the opaque ID.
        return [
            cfg.docker_binary, "run", "--rm", "--cidfile", str(cidfile),
            "--name", "lunar-private-" + build_id,
            "--label", "lan.project=lunar-modulator",
            "--label", "lan.session=installer-diagnostic-worker",
            "--cgroup-parent=docker-batch.slice", "--network=none", "--cpus=" + cfg.cpu_limit,
            "--memory=" + cfg.memory_limit, "--memory-swap=" + cfg.memory_limit,
            "--pids-limit=512", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--tmpfs", "/tmp:rw,nosuid,nodev,exec,size=" + str(cfg.scratch_bytes),
            "--user", "1001:1001",
            "--mount", "type=bind,src=" + str(base / "input" / "source.tar") + ",dst=/input/source.tar,readonly",
            "--mount", "type=bind,src=" + str(cfg.source_root / "tools/installer_service/docker_worker.py") + ",dst=/input/docker_worker.py,readonly",
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
        cidfile = base / "container.id"
        self._set(build_id, WorkerSnapshot("running"))
        proc = None
        log = bytearray()
        overflow = threading.Event()

        try:
            cmd = self._command(build_id, base, cidfile)
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    close_fds=True)
            def drain():
                assert proc.stdout is not None
                while True:
                    block = proc.stdout.read(65536)
                    if not block:
                        return
                    room = self.config.max_log_bytes - len(log)
                    if room > 0:
                        log.extend(block[:room])
                    if len(block) > room:
                        overflow.set()
                        try:
                            proc.kill()
                        except OSError:
                            pass
                        return
            reader = threading.Thread(target=drain, daemon=True)
            reader.start()
            deadline = time.monotonic() + self.config.timeout_seconds
            while proc.poll() is None:
                if overflow.is_set():
                    raise RuntimeError("worker log exceeded configured cap")
                if time.monotonic() >= deadline:
                    raise TimeoutError("worker exceeded time limit")
                time.sleep(0.2)
            reader.join(timeout=5)
            if proc.returncode != 0:
                raise RuntimeError("diagnostic worker failed")
            artifact_path = result_dir / "app.bin"
            receipt_path = result_dir / "image.json"
            for path in (artifact_path, receipt_path):
                if path.is_symlink() or not path.is_file():
                    raise ValueError("worker omitted a required regular output file")
            artifact_size = artifact_path.stat().st_size
            receipt_size = receipt_path.stat().st_size
            if not 0 < artifact_size <= self.config.max_artifact_bytes or not 0 < receipt_size <= 65536:
                raise ValueError("worker output exceeds configured cap")
            artifact = artifact_path.read_bytes()
            receipt = receipt_path.read_bytes()
            if len(artifact) != artifact_size or len(receipt) != receipt_size:
                raise ValueError("worker output changed while being collected")
            self._set(build_id, WorkerSnapshot("succeeded", WorkerResult(artifact, receipt)))
        except Exception:
            if proc is not None and proc.poll() is None:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
            if cidfile.exists():
                try:
                    cid = cidfile.read_text().strip()
                    if re.fullmatch(r"[0-9a-f]{64}", cid):
                        subprocess.run([self.config.docker_binary, "kill", cid],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=5, check=False)
                except Exception:
                    pass
            self._set(build_id, WorkerSnapshot("failed"))
        finally:
            # Keep only the already capped combined worker output inside the
            # mode-0700 private job directory for operator diagnosis. The API
            # never returns logs; normal retention cleanup removes this file.
            try:
                log_path = base / "worker.log"
                log_path.write_bytes(bytes(log[:self.config.max_log_bytes]))
                os.chmod(log_path, 0o600)
            except OSError:
                pass
            self.semaphore.release()

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

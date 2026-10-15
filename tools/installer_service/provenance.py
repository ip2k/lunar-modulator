# SPDX-License-Identifier: MIT
"""Bounded local provenance for the diagnostic installer worker.

This records build inputs and output bindings for later trusted review. It is
not a release tuple, installability decision, or hardware admission.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re

MAX_TREE_ENTRIES = 8192
MAX_TREE_BYTES = 512 * 1024 * 1024
MAX_FILE_BYTES = 256 * 1024 * 1024
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def tree_manifest(root: Path) -> bytes:
    """Return a deterministic bounded manifest, refusing escaping links."""
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("manifest root must be a directory")
    rows = [{"path": ".", "kind": "directory", "mode": root.stat().st_mode & 0o777}]
    total_bytes = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        symlink_dirs = [name for name in dirs if (here / name).is_symlink()]
        for name in symlink_dirs:
            link = here / name
            resolved = link.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_dir():
                raise ValueError("manifest symlink directory escapes root")
            rows.append({"path": link.relative_to(root).as_posix(), "kind": "symlink-dir",
                         "target": os.readlink(link),
                         "resolved": resolved.relative_to(root).as_posix(),
                         "mode": link.lstat().st_mode & 0o777})
            dirs.remove(name)
        dirs.sort()
        for name in dirs:
            path = here / name
            rows.append({"path": path.relative_to(root).as_posix(), "kind": "directory",
                         "mode": path.stat().st_mode & 0o777})
        for name in sorted(files):
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    raise ValueError("manifest symlink file escapes root")
                source = resolved
                kind = "symlink-file"
                row = {"path": rel, "kind": kind, "target": os.readlink(path),
                       "resolved": resolved.relative_to(root).as_posix(),
                       "mode": path.lstat().st_mode & 0o777}
            else:
                if not path.is_file():
                    raise ValueError("manifest contains a non-regular entry")
                source = path
                row = {"path": rel, "kind": "file", "mode": path.stat().st_mode & 0o777}
            size = source.stat().st_size
            if size > MAX_FILE_BYTES:
                raise ValueError("manifest file exceeds fixed bound")
            data = source.read_bytes()
            if len(data) != size:
                raise ValueError("manifest file changed while being read")
            total_bytes += size
            row.update({"bytes": size, "sha256": sha256(data)})
            rows.append(row)
            if len(rows) > MAX_TREE_ENTRIES or total_bytes > MAX_TREE_BYTES:
                raise ValueError("manifest tree exceeds fixed bounds")
        if len(rows) > MAX_TREE_ENTRIES:
            raise ValueError("manifest tree exceeds fixed bounds")
    rows.sort(key=lambda row: row["path"])
    return canonical({"schema": 1, "objects": rows})


def make_diagnostic_provenance(*, bindings: dict, request_sha256: str,
                               artifact: bytes, elf: bytes, receipt_raw: bytes,
                               receipt: dict) -> bytes:
    """Bind host-owned input pins to the worker's already-verified outputs."""
    expected_binding_keys = {
        "source_commit", "source_tree_oid", "source_archive_sha256",
        "worker_sha256", "worker_image_digest", "catalogue_manifest_sha256",
        "toolchain_manifest_sha256",
    }
    if not isinstance(bindings, dict) or set(bindings) != expected_binding_keys:
        raise ValueError("host provenance bindings are malformed")
    if not re.fullmatch(r"[0-9a-f]{40}", bindings["source_commit"]):
        raise ValueError("source commit binding is malformed")
    if not isinstance(bindings["source_tree_oid"], str) or not re.fullmatch(
            r"[0-9a-f]{40}", bindings["source_tree_oid"]):
        raise ValueError("source tree binding is malformed")
    for key in expected_binding_keys - {"source_commit", "source_tree_oid", "worker_image_digest"}:
        if not isinstance(bindings[key], str) or not SHA256.fullmatch(bindings[key]):
            raise ValueError("host provenance digest is malformed")
    if not isinstance(bindings["worker_image_digest"], str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", bindings["worker_image_digest"]):
        raise ValueError("worker image binding is malformed")
    if not isinstance(request_sha256, str) or not SHA256.fullmatch(request_sha256):
        raise ValueError("request digest binding is malformed")
    if not all(isinstance(value, bytes) and value for value in (artifact, elf, receipt_raw)):
        raise ValueError("worker output bytes are malformed")
    profile = {
        "flash_layout": receipt.get("flash_layout"),
        "runtime_mode": (receipt.get("runtime_configuration") or {}).get("runtime_mode"),
        "shapes_voices": receipt.get("shapes_voices"),
    }
    if (profile["flash_layout"] != "expanded-d9000"
            or profile["runtime_mode"] not in ("diagnostic", "song-diagnostic")
            or type(profile["shapes_voices"]) is not int
            or profile["shapes_voices"] != 12):
        raise ValueError("worker profile is outside the fixed diagnostic provenance profile")
    envelope = {
        "schema": 1,
        "kind": "private-diagnostic-build-provenance",
        "bindings": {**bindings, "request_sha256": request_sha256},
        "outputs": {
            "artifact_sha256": sha256(artifact), "artifact_bytes": len(artifact),
            "elf_sha256": sha256(elf), "elf_bytes": len(elf),
            "image_receipt_sha256": sha256(receipt_raw),
            "verification_sha256": receipt.get("verification_sha256"),
            "artifact_receipt_sha256": receipt.get("artifact_receipt_sha256"),
        },
        "profile": profile,
        "trusted_fwsc_packager_compatible": False,
        "compatibility_reason": "diagnostic service emits expanded-d9000/12-voice; trusted schema-2 packager requires an explicitly captured expanded-d7000 tuple",
        "installable": False,
        "hardware_admitted": False,
        "hardware_tested": False,
    }
    return canonical(envelope)

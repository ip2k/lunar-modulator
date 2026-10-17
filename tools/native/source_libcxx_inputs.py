#!/usr/bin/env python3
"""Validate tuple-bound libc++ headers and return deterministic bundle inputs.

The captured catalogue contains the exact adapted headers used by the build.
This module reverses only compile_catalogue.py's one-line __config edit. It
never treats an arbitrary compatible header directory as tuple provenance.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath


LLVM_RELEASE = "llvmorg-12.0.0"
SDK_COMMIT = "e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d"
SDK_PATH = "include_lib/c++/include"
LIBCXX_SUBTREE_COMMIT = "43eed217352338ad4de6a824fc835befd2e60b18"
LIBCXX_TREE_SHA256 = "2e92acfe3d2c9cac278fa0ba30f0e9ecf542df52056a0984af6e33bc17a2a4ce"
LIBCXX_LICENSE_SHA256 = "539dd7aed86e8a4f12cbdd0e6c50c189c7d74847e4fecc64ce2c6ee3a01da38b"
LIBCXX_LICENSE_URL = (
    "https://raw.githubusercontent.com/llvm/llvm-project/"
    "llvmorg-12.0.0/libcxx/LICENSE.TXT"
)
HEADER_COUNT = 189
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_TREE_ENTRIES = 8192
MAX_TREE_BYTES = 512 * 1024 * 1024
MAX_HEADER_FILES = 512
MAX_HEADER_FILE_BYTES = 16 * 1024 * 1024
MAX_HEADER_BYTES = 64 * 1024 * 1024
MAX_LICENSE_BYTES = 1024 * 1024
HASH = re.compile(r"^[0-9a-f]{64}$")
_PTHREAD = b"#define _LIBCPP_HAS_THREAD_API_PTHREAD\n"
_NO_THREADS = b"/* Native: no thread API. */\n"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate JSON key")
        out[key] = value
    return out


def _safe_root(path: Path) -> Path:
    """Resolve an existing directory while rejecting symlinks in its spelling."""
    lexical = path if path.is_absolute() else Path.cwd() / path
    current = Path(lexical.anchor)
    for part in lexical.parts[1:]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink path component refused: {part}")
    resolved = lexical.resolve(strict=True)
    if not resolved.is_dir():
        raise ValueError("input root must be a directory")
    return resolved


def _read_regular(path: Path, limit: int) -> tuple[bytes, int]:
    """Read one regular file without following a final-component symlink."""
    lexical = path if path.is_absolute() else Path.cwd() / path
    current = Path(lexical.anchor)
    for part in lexical.parts[1:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink parent path refused: {part}")
    flags = (os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) |
             getattr(os, "O_NONBLOCK", 0))
    fd = os.open(path, flags)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError(f"invalid or oversized regular file: {path.name}")
        chunks = []
        total = 0
        while True:
            chunk = os.read(fd, min(1024 * 1024, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > limit:
                raise ValueError(f"file exceeds byte limit: {path.name}")
        after = os.fstat(fd)
        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise ValueError(f"file changed while being read: {path.name}")
        return b"".join(chunks), stat.S_IMODE(before.st_mode)
    finally:
        os.close(fd)


def _tree(root: Path, *, allow_symlinks: bool = False):
    """Return capture_trusted_build_tuple's canonical schema-1 tree manifest.

    Catalogue snapshots may contain internal links under the capture format;
    header trees never may. All entries and bytes are bounded, and all links
    are checked to remain within the supplied root.
    """
    root = _safe_root(root)
    rows = [{"path": ".", "kind": "directory",
             "mode": root.stat().st_mode & 0o777}]
    total = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        link_dirs = [name for name in dirs if (here / name).is_symlink()]
        for name in link_dirs:
            link = here / name
            if not allow_symlinks:
                raise ValueError("header tree contains a symlink directory")
            resolved = link.resolve(strict=True)
            if not resolved.is_relative_to(root) or not resolved.is_dir():
                raise ValueError("catalogue symlink directory escapes root")
            rows.append({"path": link.relative_to(root).as_posix(),
                         "kind": "symlink-dir", "target": os.readlink(link),
                         "resolved": resolved.relative_to(root).as_posix(),
                         "mode": link.lstat().st_mode & 0o777})
            if len(rows) > MAX_TREE_ENTRIES:
                raise ValueError("tree exceeds fixed manifest entry bound")
            dirs.remove(name)
        dirs.sort()
        for name in dirs:
            path = here / name
            rows.append({"path": path.relative_to(root).as_posix(),
                         "kind": "directory", "mode": path.stat().st_mode & 0o777})
            if len(rows) > MAX_TREE_ENTRIES:
                raise ValueError("tree exceeds fixed manifest entry bound")
        for name in sorted(files):
            path = here / name
            rel = path.relative_to(root).as_posix()
            if path.is_symlink():
                if not allow_symlinks:
                    raise ValueError("header tree contains a symlink file")
                resolved = path.resolve(strict=True)
                if not resolved.is_relative_to(root) or not resolved.is_file():
                    raise ValueError("catalogue symlink file escapes root")
                data, _ = _read_regular(resolved, MAX_TREE_BYTES)
                total += len(data)
                rows.append({"path": rel, "kind": "symlink-file", "target": os.readlink(path),
                             "resolved": resolved.relative_to(root).as_posix(),
                             "bytes": len(data), "sha256": _sha(data),
                             "mode": path.lstat().st_mode & 0o777})
            else:
                data, _ = _read_regular(path, MAX_TREE_BYTES)
                mode = path.stat().st_mode & 0o777
                total += len(data)
                rows.append({"path": rel, "kind": "file", "bytes": len(data),
                             "sha256": _sha(data), "mode": mode})
            if len(rows) > MAX_TREE_ENTRIES or total > MAX_TREE_BYTES:
                raise ValueError("tree exceeds fixed manifest bounds")
    rows.sort(key=lambda row: row["path"])
    return _canonical({"schema": 1, "objects": rows}), rows


def _raw_manifest(path: Path, expected_sha: str) -> tuple[bytes, dict]:
    if not isinstance(expected_sha, str) or not HASH.fullmatch(expected_sha):
        raise ValueError("tuple-bound catalogue tree digest is malformed")
    raw, _ = _read_regular(path, MAX_MANIFEST_BYTES)
    if _sha(raw) != expected_sha:
        raise ValueError("catalogue tree manifest does not match tuple-bound digest")
    value = json.loads(raw.decode("ascii"), object_pairs_hook=_unique_pairs)
    if not isinstance(value, dict) or value.get("schema") != 1 or not isinstance(value.get("objects"), list):
        raise ValueError("catalogue tree manifest has an unsupported shape")
    if _canonical(value) != raw:
        raise ValueError("catalogue tree manifest is not canonical")
    return raw, value


def _header_rows(rows, prefix: str):
    selected = {}
    for row in rows:
        path = row.get("path")
        if not isinstance(path, str) or not path.startswith(prefix):
            continue
        rel = path[len(prefix):]
        pure = PurePosixPath(rel)
        if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
            raise ValueError("unsafe path in captured libc++ tree")
        if row.get("kind") == "directory":
            continue
        if row.get("kind") != "file" or rel in selected:
            raise ValueError("captured libc++ tree contains a non-file or duplicate")
        size, digest, mode = row.get("bytes"), row.get("sha256"), row.get("mode")
        if (not isinstance(size, int) or size < 0 or size > MAX_HEADER_FILE_BYTES or
                not isinstance(digest, str) or not HASH.fullmatch(digest) or
                not isinstance(mode, int) or mode < 0 or mode > 0o777):
            raise ValueError("invalid libc++ file row in captured manifest")
        selected[rel] = (size, digest, mode)
    return selected


def _read_header_tree(root: Path):
    root = _safe_root(root)
    rows = []
    contents = {}
    total = 0
    entries = 0
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        here = Path(current)
        entries += len(dirs) + len(files)
        if entries > MAX_TREE_ENTRIES:
            raise ValueError("tree exceeds fixed manifest entry bound")
        if any((here / name).is_symlink() for name in dirs):
            raise ValueError("pristine header tree contains a symlink directory")
        dirs.sort()
        for name in sorted(files):
            path = here / name
            if path.is_symlink():
                raise ValueError("pristine header tree contains a symlink file")
            rel = path.relative_to(root).as_posix()
            pure = PurePosixPath(rel)
            if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
                raise ValueError("unsafe path in pristine header tree")
            data, mode = _read_regular(path, MAX_HEADER_FILE_BYTES)
            total += len(data)
            if total > MAX_HEADER_BYTES or len(contents) >= MAX_HEADER_FILES:
                raise ValueError("pristine header tree exceeds fixed bounds")
            contents[rel] = data
            rows.append(f"{rel}\0{mode}\0{_sha(data)}\n".encode("utf-8"))
    if not contents:
        raise ValueError("pristine header tree is empty")
    digest = _sha(b"".join(sorted(rows)))
    return contents, digest, total


def collect_libcxx_inputs(*, catalogue_root: Path, catalogue_manifest: Path,
                          expected_catalogue_tree_sha256: str,
                          official_license: Path,
                          pristine_headers: Path):
    """Return ``(archive_entries, metadata)`` for the tuple-bound libc++ input.

    ``archive_entries`` maps safe archive-relative paths to exact bytes.
    ``pristine_headers`` is required because the compiler capture changes the
    mode of ``__config``; the helper must not guess the upstream mode.
    """
    root = _safe_root(Path(catalogue_root))
    raw, manifest = _raw_manifest(Path(catalogue_manifest), expected_catalogue_tree_sha256)
    actual, rows = _tree(root, allow_symlinks=True)
    if actual != raw:
        raise ValueError("catalogue snapshot does not match its tuple-bound tree manifest")

    shard_maps = []
    shard_bytes = []
    for number in range(16):
        prefix = f"shard-{number:02d}/cxx/"
        mapped = _header_rows(manifest["objects"], prefix)
        if not mapped:
            raise ValueError(f"missing captured libc++ input tree: shard-{number:02d}")
        if "__config" not in mapped:
            raise ValueError(f"captured libc++ tree lacks __config: shard-{number:02d}")
        shard_maps.append(mapped)
        per_shard = {}
        for rel, (size, digest, mode) in mapped.items():
            data, actual_mode = _read_regular(root / prefix / rel, MAX_HEADER_FILE_BYTES)
            if len(data) != size or _sha(data) != digest or actual_mode != mode:
                raise ValueError("captured libc++ bytes/mode differ from bound manifest")
            per_shard[rel] = (data, mode)
        shard_bytes.append(per_shard)
    first = shard_bytes[0]
    if any(mapping.keys() != first.keys() for mapping in shard_bytes[1:]):
        raise ValueError("captured libc++ shard trees have different path sets")
    for mapping in shard_bytes[1:]:
        if any(mapping[path] != first[path] for path in first):
            raise ValueError("captured libc++ shard trees differ")

    configured, configured_mode = first["__config"]
    if configured.count(_NO_THREADS) != 1 or configured.count(_PTHREAD) != 0:
        raise ValueError("captured __config does not contain exactly the known no-thread adaptation")
    original_config = configured.replace(_NO_THREADS, _PTHREAD)
    if configured_mode != 0o600:
        raise ValueError("captured adapted __config mode is not the compiler's fixed 0600 mode")
    source_bytes = {path: data for path, (data, _) in first.items()}
    source_bytes["__config"] = original_config

    source_size = sum(map(len, source_bytes.values()))
    if len(source_bytes) != HEADER_COUNT or source_size > MAX_HEADER_BYTES:
        raise ValueError("captured libc++ tree does not match the fixed file-count/size bounds")
    supplied, source_tree_sha256, supplied_size = _read_header_tree(Path(pristine_headers))
    if source_tree_sha256 != LIBCXX_TREE_SHA256 or len(supplied) != HEADER_COUNT:
        raise ValueError("pristine libc++ tree does not match the fixed upstream path/mode/hash pin")
    if supplied_size != source_size or supplied.keys() != source_bytes.keys():
        raise ValueError("pristine libc++ tree does not match captured compiler input paths/size")
    for path, data in source_bytes.items():
        if supplied[path] != data:
            raise ValueError("pristine libc++ bytes differ from tuple-bound compiler input")
    # The source __config mode is captured only by this supplied pristine tree.
    source_bytes = supplied

    license_bytes, _ = _read_regular(Path(official_license), MAX_LICENSE_BYTES)
    if _sha(license_bytes) != LIBCXX_LICENSE_SHA256:
        raise ValueError("libc++ license bytes do not match the pinned LLVM 12.0.0 notice")

    archive_entries = {
        f"external/libcxx-{LLVM_RELEASE}/include/{path}": data
        for path, data in source_bytes.items()
    }
    archive_entries[f"external/libcxx-{LLVM_RELEASE}/LICENSE.TXT"] = license_bytes
    metadata = {
        "schema": 1,
        "upstream": "llvm/llvm-project",
        "release": LLVM_RELEASE,
        "sdk_commit": SDK_COMMIT,
        "sdk_header_path": SDK_PATH,
        "libcxx_subtree_commit": LIBCXX_SUBTREE_COMMIT,
        "catalogue_tree_sha256": expected_catalogue_tree_sha256,
        "header_file_count": len(source_bytes),
        "header_bytes": sum(map(len, source_bytes.values())),
        "header_tree_sha256": source_tree_sha256,
        "pristine_tree_identity_verified": True,
        "adaptation": {
            "path": "__config",
            "captured_line": _NO_THREADS.decode("ascii").rstrip("\n"),
            "restored_line": _PTHREAD.decode("ascii").rstrip("\n"),
            "captured_mode": "0600",
        },
        "license_path": f"external/libcxx-{LLVM_RELEASE}/LICENSE.TXT",
        "license_url": LIBCXX_LICENSE_URL,
        "license_sha256": _sha(license_bytes),
        "license_bytes": len(license_bytes),
    }
    return archive_entries, metadata

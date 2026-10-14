#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Container entrypoint. Inputs/paths are constants, never request-controlled."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

SOURCE = Path("/workspace")
SOURCE_ARCHIVE = Path("/input/source.tar")
REQUEST = Path("/input/request.json")
TOOLCHAIN = Path("/opt/pi32v2")
CATALOGUE = Path("/input/catalogue")
RESULT = Path("/result")
SCRATCH = Path("/tmp/lunar-worker")
MAX_REQUEST = 65536
MAX_APP = 1048576
MAX_RECEIPT = 65536


def regular_file(path: Path, limit: int) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError("expected regular file")
    size = path.stat().st_size
    if not 0 < size <= limit:
        raise ValueError("input/output exceeds cap")
    data = path.read_bytes()
    if len(data) != size:
        raise ValueError("file changed while reading")
    return data


def main() -> int:
    request_bytes = regular_file(REQUEST, MAX_REQUEST)
    request = json.loads(request_bytes)
    if not isinstance(request, dict):
        raise ValueError("request must be object")
    archive_bytes = regular_file(SOURCE_ARCHIVE, 128 * 1024 * 1024)
    if not TOOLCHAIN.is_dir() or not (CATALOGUE / "shard-00/objects.json").is_file():
        raise ValueError("fixed worker inputs are unavailable")
    if RESULT.is_symlink() or not RESULT.is_dir() or any(RESULT.iterdir()):
        raise ValueError("result mount is not an empty service directory")

    # Extract only the server-created git archive into bounded tmpfs. Reject
    # links and path traversal even though the archive is generated locally.
    SCRATCH.mkdir(mode=0o700, parents=True, exist_ok=False)
    work = SCRATCH / "source"
    work.mkdir(mode=0o700)
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
    subprocess.run(["make", "-C", str(work / "engines"), "build/fm1-state"],
                   check=True, timeout=120)
    output = SCRATCH / "output"
    (output / "build").parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        sys.executable, str(work / "tools/native/build_demo_image.py"),
        "--request", str(REQUEST),
        "--state-tool", str(work / "engines/build/fm1-state"),
        "--toolchain", str(TOOLCHAIN),
        "--catalogue", str(CATALOGUE),
        "--out", str(output / "build"),
    ], check=True, timeout=1200)
    app = regular_file(output / "build/link/artifact/app.bin", MAX_APP)
    receipt = regular_file(output / "build/image.json", MAX_RECEIPT)
    (RESULT / "app.bin").write_bytes(app)
    (RESULT / "image.json").write_bytes(receipt)
    print(json.dumps({"app_bytes": len(app), "app_sha256": hashlib.sha256(app).hexdigest(),
                      "receipt_bytes": len(receipt)}), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("diagnostic worker failed: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1)

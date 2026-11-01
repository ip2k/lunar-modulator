#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fixed worker entrypoint for the private continuous target tuple build."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

SOURCE = Path("/workspace")
REQUEST = Path("/input/request.json")
TOOLCHAIN = Path("/opt/pi32v2")
CATALOGUE = Path("/catalogue")
OUTPUT = Path("/output")
SCRATCH = Path("/tmp/lunar-continuous")
MAX_REQUEST = 65536
MAX_STATE_TOOL = 64 * 1024 * 1024


def sha(path: Path, limit: int) -> str:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= limit:
        raise ValueError("invalid bounded input")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    expected_commit = os.environ.get("LUNAR_SOURCE_COMMIT", "")
    if len(expected_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_commit):
        raise ValueError("source commit is not pinned")
    if not SOURCE.is_dir() or not REQUEST.is_file() or not TOOLCHAIN.is_dir():
        raise ValueError("fixed build inputs are unavailable")
    if not (CATALOGUE / "shard-00/objects.json").is_file():
        raise ValueError("fixed catalogue input is unavailable")
    if OUTPUT.is_symlink() or not OUTPUT.is_dir() or any(OUTPUT.iterdir()):
        raise ValueError("output mount is not empty")
    request = REQUEST.read_bytes()
    if not 0 < len(request) <= MAX_REQUEST:
        raise ValueError("request exceeds fixed input bound")
    SCRATCH.mkdir(mode=0o700, parents=True, exist_ok=False)
    state_dir = SCRATCH / "state"
    state_tool = state_dir / "fm1-state"
    subprocess.run([
        "make", "-C", str(SOURCE / "engines"), "BUILD=" + str(state_dir),
        "FM1_GPL_MODS=1", "-j4", str(state_tool),
    ], check=True, timeout=180)
    if not 0 < state_tool.stat().st_size <= MAX_STATE_TOOL:
        raise ValueError("state tool exceeds fixed size bound")

    build_output = OUTPUT / "build"
    subprocess.run([
        sys.executable, str(SOURCE / "tools/native/build_demo_image.py"),
        "--request", str(REQUEST),
        "--state-tool", str(state_tool),
        "--toolchain", str(TOOLCHAIN),
        "--catalogue", str(CATALOGUE),
        "--out", str(build_output),
        "--runtime-mode", "continuous",
        "--wavetable-profile", "compressed-required-banks-ram-plaits-braids-shapes8-v1",
        "--firmware-identity", "FM-1_500",
        "--flash-layout", "expanded-d7000",
    ], check=True, timeout=1200)
    worker_receipt = {
        "schema": 1,
        "source_commit": expected_commit,
        "request_sha256": hashlib.sha256(request).hexdigest(),
        "state_tool_sha256": sha(state_tool, MAX_STATE_TOOL),
        "runtime_mode": "continuous",
        "flash_layout": "expanded-d7000",
        "wavetable_profile": "compressed-required-banks-ram-plaits-braids-shapes8-v1",
        "hardware_admitted": False,
        "hardware_tested": False,
        "installable": False,
    }
    receipt_path = OUTPUT / "worker-provenance.json"
    fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(json.dumps(worker_receipt, sort_keys=True, separators=(",", ":")).encode("ascii"))
        stream.flush()
        os.fsync(stream.fileno())
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("continuous build worker refused: " + type(error).__name__, file=sys.stderr, flush=True)
        raise SystemExit(1)

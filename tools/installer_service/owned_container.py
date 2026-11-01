# SPDX-License-Identifier: MIT
"""Cancel only a uniquely named, owner-labelled private Docker container."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess

from .process_capture import run_bounded

OWNED_NAME = re.compile(r"lunar-continuous-[0-9a-f]{24}\Z")
MAX_DOCKER_OUTPUT = 65536


def cancel_owned_container(name: str, *, cwd: Path, docker: str = "docker") -> bool:
    """Return confirmed absence; daemon failure never means removal succeeded.

    A matching name alone does not confer ownership. In particular a failed
    create due to a collision must preserve the pre-existing container.
    """
    if not isinstance(name, str) or not OWNED_NAME.fullmatch(name):
        raise ValueError("invalid parent-owned continuous container name")

    def capture(arguments):
        return run_bounded([docker, *arguments], cwd=cwd, timeout_seconds=10,
                           max_stream_bytes=MAX_DOCKER_OUTPUT)

    def complete(result):
        return (result.returncode == 0 and result.failure_reason is None
                and all(result.observed[stream] <= MAX_DOCKER_OUTPUT
                        for stream in ("stdout", "stderr")))

    def absent():
        # Docker documents full/substring name matching. Avoid regex anchors:
        # the full literal generated name matches itself with or without '/'.
        result = capture(["ps", "--all", "--filter", "name=" + name,
                          "--format", "{{.Names}}"])
        if not complete(result):
            return False
        names = [value.lstrip("/") for line in result.logs["stdout"].decode("utf-8").splitlines()
                 for value in line.split(",")]
        if any(not re.fullmatch(r"[A-Za-z0-9_./-]+", value) for value in names):
            return False
        return name not in names

    try:
        result = capture(["container", "inspect", "--format", "{{json .Config.Labels}}", name])
        if not complete(result):
            return absent()
        labels = json.loads(result.logs["stdout"].decode("utf-8"))
        if not isinstance(labels, dict) or labels.get("lan.owner") != name:
            return False
        result = capture(["rm", "--force", name])
        return complete(result) or absent()
    except (OSError, ValueError, subprocess.SubprocessError):
        return False

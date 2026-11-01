# SPDX-License-Identifier: MIT
"""Bounded concurrent pipe capture for private, POSIX trusted-build processes."""
from __future__ import annotations

from dataclasses import dataclass
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path


@dataclass(frozen=True)
class Capture:
    returncode: int
    logs: dict[str, bytes]
    observed: dict[str, int]
    failure_reason: str | None


def run_bounded(command: list[str], *, cwd: Path, timeout_seconds: float,
                max_stream_bytes: int, drain_seconds: float = 1.0) -> Capture:
    """Drain both streams without retaining more than the per-stream prefix cap.

    Own a new process group so a timeout, exception, or inherited pipe cannot
    strand descendants. EOF after parent exit has a separate bounded deadline.
    The caller decides whether any captured bytes may enter private diagnostics.
    """
    if (timeout_seconds <= 0 or drain_seconds <= 0
            or type(max_stream_bytes) is not int or max_stream_bytes < 0):
        raise ValueError("invalid capture bounds")
    deadline = time.monotonic() + timeout_seconds
    logs = {name: bytearray() for name in ("stdout", "stderr")}
    observed = dict.fromkeys(logs, 0)
    reason = None
    exited_at = None
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)

    killed = False

    def kill_group():
        nonlocal killed
        if killed:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        killed = True

    try:
        with selectors.DefaultSelector() as selector:
            for name in logs:
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                if reason is None and now >= deadline:
                    reason = "timeout"
                    kill_group()
                    exited_at = now
                if process.poll() is not None and exited_at is None:
                    exited_at = now
                if exited_at is not None and now - exited_at >= drain_seconds:
                    if selector.get_map() and reason is None:
                        reason = "output_drain_timeout"
                    kill_group()
                    break
                for key, _events in selector.select(timeout=0.05):
                    raw = os.read(key.fileobj.fileno(), 65536)
                    if not raw:
                        selector.unregister(key.fileobj)
                        continue
                    name = key.data
                    observed[name] += len(raw)
                    remaining = max_stream_bytes - len(logs[name])
                    if remaining > 0:
                        logs[name].extend(raw[:remaining])
        # Also clean up descendants which closed the inherited output pipes.
        kill_group()
        returncode = process.wait(timeout=drain_seconds)
        return Capture(returncode, {name: bytes(raw) for name, raw in logs.items()},
                       observed, reason)
    finally:
        kill_group()
        for stream in (process.stdout, process.stderr):
            stream.close()
        process.wait(timeout=drain_seconds)

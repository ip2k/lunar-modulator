#!/usr/bin/env python3
"""Passively record Lunar diagnostic SysEx from one exact MIDI input port.

This tool never opens a MIDI output port and never sends messages. Port names
identify a host port only; the caller supplies an expected image hash and must
bind the recording to device identity separately.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from typing import Any, Callable

if __package__:
    from .diagnostic_telemetry import (FRAME_BYTES, PROFILE_FRAME_BYTES, CLOCK_FRAME_BYTES, PLL_FRAME_BYTES,
                                      PRODUCER_GAP_FRAME_BYTES,
                                      IRQ_PROFILE_FRAME_BYTES,
                                      ENGINE_PROFILE_FRAME_BYTES,
                                      CPU_RATE_FRAME_BYTES,
                                      decode_any_frame)
else:  # Direct ``python tools/native/record_diagnostic_telemetry.py`` use.
    from diagnostic_telemetry import (FRAME_BYTES, PROFILE_FRAME_BYTES, CLOCK_FRAME_BYTES, PLL_FRAME_BYTES,
                                      PRODUCER_GAP_FRAME_BYTES,
                                      IRQ_PROFILE_FRAME_BYTES,
                                      ENGINE_PROFILE_FRAME_BYTES,
                                      CPU_RATE_FRAME_BYTES,
                                      decode_any_frame)

MAX_TIMEOUT_SECONDS = 180.0
MAX_VALID_FRAMES = 4096
MAX_EVENTS = 8192
POLL_SECONDS = 0.02
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


def _exclusive_file(path: Path):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "wb")


def _stamp(wall_time: Callable[[], float]) -> str:
    return datetime.fromtimestamp(wall_time(), timezone.utc).isoformat(timespec="milliseconds")


def record(
    port_name: str,
    expected_image_sha256: str,
    output_dir: Path,
    timeout: float = 60.0,
    *,
    mido_module: Any = None,
    monotonic: Callable[[], float] = time.monotonic,
    wall_time: Callable[[], float] = time.time,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Record all complete valid diagnostic frames until timeout.

    The output directory itself must be new. Malformed SysEx and unrelated
    input messages are retained as timestamped JSONL event summaries, but only
    validated raw diagnostic frames are appended to ``raw.syx``.
    """
    if not isinstance(port_name, str) or not port_name:
        raise ValueError("an exact non-empty MIDI input port name is required")
    if not isinstance(expected_image_sha256, str) or not SHA256_RE.fullmatch(expected_image_sha256):
        raise ValueError("expected image SHA-256 must be 64 lowercase hexadecimal characters")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)):
        raise ValueError("timeout must be a finite number in (0, 180] seconds")
    timeout = float(timeout)
    if not math.isfinite(timeout) or not 0.0 < timeout <= MAX_TIMEOUT_SECONDS:
        raise ValueError("timeout must be a finite number in (0, 180] seconds")

    if mido_module is None:
        import mido as mido_module

    names = mido_module.get_input_names()
    if names.count(port_name) != 1:
        raise ValueError("exact MIDI input port name must match one available input")

    output_dir = Path(output_dir)
    output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
    raw_path = output_dir / "raw.syx"
    events_path = output_dir / "events.jsonl"
    receipt_path = output_dir / "receipt.json"
    raw_hash = hashlib.sha256()
    valid_frames = 0
    profile_frames = 0
    clock_frames = 0
    pll_frames = 0
    producer_gap_frames = 0
    irq_profile_frames = 0
    engine_profile_frames = 0
    cpu_rate_frames = 0
    event_count = 0
    started_wall = _stamp(wall_time)
    started_mono = monotonic()

    def write_event(stream, event: dict[str, Any]) -> None:
        nonlocal event_count
        if event_count >= MAX_EVENTS:
            raise RuntimeError("input event limit exceeded")
        event_count += 1
        event["wall_time_utc"] = _stamp(wall_time)
        event["elapsed_seconds"] = max(0.0, monotonic() - started_mono)
        stream.write((json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode())

    with _exclusive_file(raw_path) as raw, _exclusive_file(events_path) as events:
        deadline = started_mono + timeout
        with mido_module.open_input(port_name) as midi_in:
            while monotonic() < deadline:
                had_messages = False
                for message in midi_in.iter_pending():
                    had_messages = True
                    if monotonic() >= deadline:
                        break
                    if message.type == "sysex":
                        try:
                            data = message.data
                            if len(data) not in (FRAME_BYTES - 2, PROFILE_FRAME_BYTES - 2,
                                                 CLOCK_FRAME_BYTES - 2, PLL_FRAME_BYTES - 2,
                                                 PRODUCER_GAP_FRAME_BYTES - 2,
                                                 IRQ_PROFILE_FRAME_BYTES - 2,
                                                 ENGINE_PROFILE_FRAME_BYTES - 2,
                                                 CPU_RATE_FRAME_BYTES - 2):
                                raise ValueError("diagnostic SysEx payload has wrong length")
                            frame = bytes((0xF0, *data, 0xF7))
                            schema, values = decode_any_frame(frame)
                        except (TypeError, ValueError, OverflowError) as exc:
                            write_event(events, {"event": "malformed_sysex", "error": str(exc)[:160]})
                            continue
                        if valid_frames >= MAX_VALID_FRAMES:
                            raise RuntimeError("valid diagnostic frame limit exceeded")
                        offset = raw.tell()
                        raw.write(frame)
                        raw_hash.update(frame)
                        valid_frames += 1
                        if schema == 2:
                            profile_frames += 1
                        if schema == 3:
                            clock_frames += 1
                        if schema == 4:
                            pll_frames += 1
                        if schema == 5:
                            producer_gap_frames += 1
                        if schema == 6:
                            irq_profile_frames += 1
                        if schema == 7:
                            engine_profile_frames += 1
                        if schema == 8:
                            cpu_rate_frames += 1
                        write_event(events, {
                            "event": {1: "diagnostic_frame", 2: "render_profile_frame",
                                      3: "clock_snapshot_frame", 4: "pll_snapshot_frame",
                                      5: "producer_gap_frame", 6: "irq_profile_frame",
                                      7: "engine_profile_frame",
                                      8: "cpu_rate_frame"}[schema],
                            "schema": schema,
                            "frame_index": valid_frames - 1,
                            "raw_offset": offset,
                            "raw_bytes": len(frame),
                            "values": values,
                        })
                    else:
                        write_event(events, {
                            "event": "unrelated_message",
                            "message_type": str(getattr(message, "type", "unknown"))[:80],
                        })
                if not had_messages:
                    sleep(min(POLL_SECONDS, max(0.0, deadline - monotonic())))
        raw.flush()
        os.fsync(raw.fileno())
        events.flush()
        os.fsync(events.fileno())

    if valid_frames == 0:
        raise RuntimeError("timeout completed without a valid diagnostic frame; no success receipt written")

    receipt = {
        "schema": 1,
        "input_port_name": port_name,
        "expected_image_sha256": expected_image_sha256,
        "started_at_utc": started_wall,
        "finished_at_utc": _stamp(wall_time),
        "timeout_seconds": timeout,
        "elapsed_seconds": max(0.0, monotonic() - started_mono),
        "termination_reason": "capture_deadline_reached",
        "midi_backend": getattr(getattr(mido_module, "backend", None), "name", None),
        "midi_backend_api": getattr(getattr(mido_module, "backend", None), "api", None),
        "valid_frame_count": valid_frames,
        "render_profile_frame_count": profile_frames,
        "clock_snapshot_frame_count": clock_frames,
        "pll_snapshot_frame_count": pll_frames,
        "producer_gap_frame_count": producer_gap_frames,
        "irq_profile_frame_count": irq_profile_frames,
        "engine_profile_frame_count": engine_profile_frames,
        "cpu_rate_frame_count": cpu_rate_frames,
        "raw_bytes": raw_path.stat().st_size,
        "raw_sha256": raw_hash.hexdigest(),
        "events_jsonl_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
        "midi_output_opened": False,
        "device_identity_verified": False,
        "hardware_acceptance": False,
    }
    with _exclusive_file(receipt_path) as stream:
        stream.write((json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="exact MIDI input port name")
    parser.add_argument("--image-sha256", required=True, help="expected candidate image SHA-256")
    parser.add_argument("--output-dir", required=True, type=Path, help="new directory for raw.syx and receipts")
    parser.add_argument("--timeout", type=float, default=60.0, help="recording window in seconds (maximum 180)")
    args = parser.parse_args()
    try:
        receipt = record(args.port, args.image_sha256, args.output_dir, args.timeout)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

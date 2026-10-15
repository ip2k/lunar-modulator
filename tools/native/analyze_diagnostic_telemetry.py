#!/usr/bin/env python3
"""Summarize recorded Lunar diagnostic frames without opening MIDI or audio devices."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
from typing import Any, Iterable

try:
    from .diagnostic_telemetry import (CLOCK_FIELDS, FIELDS, PLL_FIELDS, PROFILE_FIELDS,
                                      PROFILE_STAGES, PRODUCER_GAP_FIELDS,
                                      IRQ_PROFILE_FIELDS)
except ImportError:  # Direct ``python tools/native/analyze_diagnostic_telemetry.py`` use.
    from diagnostic_telemetry import (CLOCK_FIELDS, FIELDS, PLL_FIELDS, PROFILE_FIELDS,
                                      PROFILE_STAGES, PRODUCER_GAP_FIELDS,
                                      IRQ_PROFILE_FIELDS)

UINT32_MAX = 0xFFFFFFFF
TICKS_PER_US = 24
SAMPLE_RATE_HZ = 44118
BLOCK_FRAMES = 64
MAX_EVENT_ROWS = 8192
MAX_INPUT_BYTES = 4 * 1024 * 1024
MAX_LINE_BYTES = 16 * 1024

_CUMULATIVE_FIELDS = (
    "uptime_ms",
    "audio_underruns",
    "usb_messages",
    "uart_bytes",
    "accepted_noteons",
    "rejected_messages",
    "produced_audio_blocks",
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _uint32(value: Any, name: str, line_number: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= UINT32_MAX:
        raise ValueError(f"line {line_number}: {name} must be a uint32 integer")
    return value


def _elapsed(value: Any, line_number: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"line {line_number}: elapsed_seconds must be a finite nonnegative number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"line {line_number}: elapsed_seconds must be a finite nonnegative number") from exc
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"line {line_number}: elapsed_seconds must be a finite nonnegative number")
    return result


def analyze_jsonl(lines: Iterable[str]) -> dict[str, Any]:
    """Validate recorder JSONL and derive frame-to-frame, wrap-safe summaries.

    ``elapsed_seconds`` is the recorder's monotonic clock from capture start.
    Host arrival rates and device uptime rates are reported separately, since
    buffered reports can arrive together. Device uptime must be continuous;
    reconnects/reboots must be analyzed as separate logs.
    Counter deltas use uint32 modular arithmetic; maxima and sampled values are
    retained as observations and are never differenced as cumulative counters.
    """
    previous_elapsed: float | None = None
    previous_values: dict[str, int] | None = None
    frames: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    clock_snapshots: list[dict[str, Any]] = []
    pll_snapshots: list[dict[str, Any]] = []
    producer_gap_frames: list[dict[str, Any]] = []
    irq_profile_frames: list[dict[str, Any]] = []
    previous_profile_elapsed: float | None = None
    previous_irq_values: dict[str, int] | None = None
    event_counts: dict[str, int] = {}
    total_bytes = 0
    row_count = 0

    for line_number, line in enumerate(lines, 1):
        encoded_size = len(line.encode("utf-8"))
        total_bytes += encoded_size
        row_count += 1
        if row_count > MAX_EVENT_ROWS:
            raise ValueError(f"event log exceeds {MAX_EVENT_ROWS} rows")
        if encoded_size > MAX_LINE_BYTES:
            raise ValueError(f"line {line_number}: event row exceeds {MAX_LINE_BYTES} bytes")
        if total_bytes > MAX_INPUT_BYTES:
            raise ValueError(f"event log exceeds {MAX_INPUT_BYTES} bytes")
        if not line.strip():
            raise ValueError(f"line {line_number}: blank JSONL rows are not valid events")
        try:
            event = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise ValueError(f"line {line_number}: invalid JSON event") from exc
        if not isinstance(event, dict) or not isinstance(event.get("event"), str):
            raise ValueError(f"line {line_number}: event row must be an object with an event name")
        event_name = event["event"]
        event_counts[event_name] = event_counts.get(event_name, 0) + 1
        elapsed = _elapsed(event.get("elapsed_seconds"), line_number)
        if previous_elapsed is not None and elapsed < previous_elapsed:
            raise ValueError(f"line {line_number}: elapsed_seconds moved backwards")
        previous_elapsed = elapsed

        if event_name == "clock_snapshot_frame":
            values = event.get("values")
            if (type(event.get("schema")) is not int or event["schema"] != 3
                    or not isinstance(values, dict) or set(values) != set(CLOCK_FIELDS)):
                raise ValueError(f"line {line_number}: clock snapshot values must contain exactly schema-3 fields")
            checked = {name: _uint32(values[name], name, line_number) for name in CLOCK_FIELDS}
            clock_snapshots.append({
                "wall_time_utc": event.get("wall_time_utc"),
                "elapsed_seconds": elapsed,
                "values": checked,
                "frequency_interpreted": False,
            })
            continue

        if event_name == "pll_snapshot_frame":
            values = event.get("values")
            if (type(event.get("schema")) is not int or event["schema"] != 4
                    or not isinstance(values, dict) or set(values) != set(PLL_FIELDS)):
                raise ValueError(f"line {line_number}: PLL snapshot values must contain exactly schema-4 fields")
            checked = {name: _uint32(values[name], name, line_number) for name in PLL_FIELDS}
            pll_snapshots.append({
                "wall_time_utc": event.get("wall_time_utc"),
                "elapsed_seconds": elapsed,
                "values": checked,
                "frequency_interpreted": False,
            })
            continue

        if event_name == "producer_gap_frame":
            values = event.get("values")
            schema = event.get("schema")
            if (type(schema) is not int or schema != 5 or not isinstance(values, dict)
                    or set(values) != set(PRODUCER_GAP_FIELDS)):
                raise ValueError(f"line {line_number}: producer-gap values must contain exactly schema-5 fields")
            checked = {name: _uint32(values[name], name, line_number)
                       for name in PRODUCER_GAP_FIELDS}
            producer_gap_frames.append({
                "frame_index": event.get("frame_index"),
                "wall_time_utc": event.get("wall_time_utc"),
                "elapsed_seconds": elapsed,
                "values": checked,
                "timing_units": "raw device timer ticks; do not infer duration without calibrated timer rate",
                "queue_depth_semantics": "best-effort main-loop samples; audio IRQ may advance the read counter",
            })
            continue

        if event_name == "irq_profile_frame":
            values = event.get("values")
            schema = event.get("schema")
            if (type(schema) is not int or schema != 6 or not isinstance(values, dict)
                    or set(values) != set(IRQ_PROFILE_FIELDS)):
                raise ValueError(f"line {line_number}: IRQ profile values must contain exactly schema-6 fields")
            checked = {name: _uint32(values[name], name, line_number)
                       for name in IRQ_PROFILE_FIELDS}
            delta_fields = tuple(name for name in IRQ_PROFILE_FIELDS
                                 if not name.endswith("_max_ticks"))
            deltas = (None if previous_irq_values is None else {
                name: (checked[name] - previous_irq_values[name]) & UINT32_MAX
                for name in delta_fields
            })
            irq_profile_frames.append({
                "frame_index": event.get("frame_index"),
                "wall_time_utc": event.get("wall_time_utc"),
                "elapsed_seconds": elapsed,
                "values": checked,
                "counter_deltas": deltas,
                "timing_units": "raw device timer ticks; do not infer duration without calibrated timer rate",
                "counter_semantics": "non-maximum fields are cumulative uint32 counters since boot; modular deltas are shown; max fields are retained observations",
            })
            previous_irq_values = checked
            continue

        if event_name == "render_profile_frame":
            values = event.get("values")
            schema = event.get("schema")
            if type(schema) is not int or schema != 2 or not isinstance(values, dict) or set(values) != set(PROFILE_FIELDS):
                raise ValueError(f"line {line_number}: render profile values must contain exactly schema-2 fields")
            checked = {name: _uint32(values[name], name, line_number) for name in PROFILE_FIELDS}
            delta = None if previous_profile_elapsed is None else elapsed - previous_profile_elapsed
            stages = {}
            for stage in PROFILE_STAGES:
                ticks = checked[f"{stage}_window_ticks"]
                maximum = checked[f"{stage}_max_ticks"]
                calls = checked[f"{stage}_calls"]
                stages[stage] = {
                    "window_ticks": ticks,
                    "window_us": ticks / TICKS_PER_US,
                    "max_ticks": maximum,
                    "max_us": maximum / TICKS_PER_US,
                    "calls": calls,
                }
            profiles.append({
                "frame_index": event.get("frame_index"),
                "wall_time_utc": event.get("wall_time_utc"),
                "elapsed_seconds": elapsed,
                "elapsed_since_previous_profile_seconds": delta,
                "values": checked,
                "stages": stages,
                "counter_semantics": "uint32 counters accumulated since prior emitted schema-2 frame; wrap is possible",
            })
            previous_profile_elapsed = elapsed
            continue

        if event_name != "diagnostic_frame":
            continue

        values = event.get("values")
        if not isinstance(values, dict) or set(values) != set(FIELDS):
            raise ValueError(f"line {line_number}: diagnostic values must contain exactly the schema-1 fields")
        checked = {name: _uint32(values[name], name, line_number) for name in FIELDS}
        elapsed_delta = None if not frames else elapsed - float(frames[-1]["elapsed_seconds"])
        deltas: dict[str, int] | None = None
        rates: dict[str, float | None] | None = None
        device_seconds: float | None = None
        device_rates: dict[str, float | None] | None = None
        if previous_values is not None:
            deltas = {
                name: (checked[name] - previous_values[name]) & UINT32_MAX
                for name in _CUMULATIVE_FIELDS
            }
            rates = {
                name: (delta / elapsed_delta if elapsed_delta and elapsed_delta > 0 else None)
                for name, delta in deltas.items()
            }
            device_seconds = deltas["uptime_ms"] / 1000.0
            device_rates = {
                name: (delta / device_seconds if device_seconds > 0 else None)
                for name, delta in deltas.items()
            }

        stack_samples = checked["stack_samples"]
        stack = {}
        for field in ("user_stack_margin", "system_stack_margin"):
            margin = checked[field]
            available = stack_samples > 0 and margin != UINT32_MAX
            stack[field] = {
                "bytes": margin if available else None,
                "status": "observed_minimum_not_worst_case" if available else "unavailable",
            }

        frames.append({
            "frame_index": event.get("frame_index"),
            "wall_time_utc": event.get("wall_time_utc"),
            "elapsed_seconds": elapsed,
            "elapsed_since_previous_frame_seconds": elapsed_delta,
            "values": checked,
            "render_max_us": checked["render_ticks_max"] / TICKS_PER_US,
            "draw_max_us": checked["draw_ticks_max"] / TICKS_PER_US,
            "stack": {
                "samples": stack_samples,
                "user": stack["user_stack_margin"],
                "system": stack["system_stack_margin"],
            },
            "counter_deltas": deltas,
            "counter_rates_per_second": rates,
            "device_seconds_since_previous_frame": device_seconds,
            "counter_rates_per_device_second": device_rates,
        })
        previous_values = checked

    if not frames and not profiles and not clock_snapshots and not pll_snapshots and not producer_gap_frames and not irq_profile_frames:
        raise ValueError("event log contains no diagnostic or render_profile rows, clock snapshots, PLL snapshots, producer-gap frames, or IRQ profile frames")

    return {
        "schema": 1,
        "source": "record_diagnostic_telemetry.py events.jsonl",
        "time_basis": "elapsed_seconds from telemetry recorder monotonic clock; align explicitly with WAV and helper timestamps before correlation",
        "counter_rate_time_bases": {
            "counter_rates_per_second": "host receipt intervals; buffered delivery can distort rates",
            "counter_rates_per_device_second": "uint32 uptime_ms deltas; requires continuous device uptime and timer calibration",
        },
        "sample_rate_hz": SAMPLE_RATE_HZ,
        "audio_block_frames": BLOCK_FRAMES,
        "expected_audio_blocks_per_second": SAMPLE_RATE_HZ / BLOCK_FRAMES,
        "event_rows": row_count,
        "event_counts": event_counts,
        "diagnostic_frame_count": len(frames),
        "render_profile_frame_count": len(profiles),
        "clock_snapshot_frame_count": len(clock_snapshots),
        "pll_snapshot_frame_count": len(pll_snapshots),
        "producer_gap_frame_count": len(producer_gap_frames),
        "irq_profile_frame_count": len(irq_profile_frames),
        "frames": frames,
        "render_profiles": profiles,
        "clock_snapshots": clock_snapshots,
        "pll_snapshots": pll_snapshots,
        "producer_gap_frames": producer_gap_frames,
        "irq_profile_frames": irq_profile_frames,
        "interpretation_limits": [
            "Schema-1 counters are cumulative and sampled non-atomically; use modular deltas between frames.",
            "Missing reports create longer intervals; rates are interval averages, not reconstructed event times.",
            "Buffered reports distort host receipt rates; device rates assume no intervening reboot or timer reset.",
            "USB messages and UART bytes are ingress observations; accepted_noteons is handler dispatch, not audible acceptance.",
            "Stack margins are observed minima only; sentinel or zero samples means unavailable.",
            "No device identity, image identity, WAV alignment, or hardware/perceptual acceptance is inferred.",
            "Schema-3 clock and schema-4 PLL frames repeat startup raw samples; register fields are not decoded into CPU frequency.",
        ],
    }


def analyze_file(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    if size > MAX_INPUT_BYTES:
        raise ValueError(f"event log exceeds {MAX_INPUT_BYTES} bytes")
    with path.open("r", encoding="utf-8") as stream:
        return analyze_jsonl(stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events_jsonl", type=Path, help="events.jsonl emitted by the passive recorder")
    args = parser.parse_args(argv)
    try:
        report = analyze_file(args.events_jsonl)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(report, sys.stdout, sort_keys=True, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

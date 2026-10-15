#!/usr/bin/env python3
"""Streaming analyzer for six-channel, 48 kHz, signed 32-bit PCM KA6 WAVs.

Only channels 1 and 2 receive signal statistics; all six are required so format
mistakes fail closed. Optional JSONL timestamps are annotations, never MIDI proof.
"""
from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path
from typing import BinaryIO

RIFF_WAVE = b"WAVE"
PCM_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
EXPECTED = (6, 48000, 32, 32)
WINDOW_FRAMES = 48000
FULL_SCALE = 1 << 31


class WaveError(ValueError):
    pass


def _read_exact(stream: BinaryIO, count: int) -> bytes:
    data = stream.read(count)
    if len(data) != count:
        raise WaveError("truncated WAV")
    return data


def inspect_wave(path: str | Path) -> dict:
    """Validate the RIFF format and return data offset/length and sample metadata."""
    path = Path(path)
    file_size = path.stat().st_size
    with path.open("rb") as f:
        header = _read_exact(f, 12)
        if header[:4] != b"RIFF" or header[8:] != RIFF_WAVE:
            raise WaveError("expected little-endian RIFF/WAVE (RF64 is unsupported)")
        riff_size = struct.unpack_from("<I", header, 4)[0]
        if riff_size + 8 != file_size:
            raise WaveError("RIFF size does not exactly match file size")
        fmt = None
        data_chunk = None
        while f.tell() < file_size:
            if file_size - f.tell() < 8:
                raise WaveError("truncated chunk header")
            chunk_id, chunk_size = struct.unpack("<4sI", _read_exact(f, 8))
            chunk_start = f.tell()
            chunk_end = chunk_start + chunk_size
            padded_end = chunk_end + (chunk_size & 1)
            if padded_end > file_size:
                raise WaveError("chunk extends beyond RIFF boundary")
            if chunk_id == b"fmt ":
                if fmt is not None:
                    raise WaveError("multiple fmt chunks are unsupported")
                raw = _read_exact(f, chunk_size)
                if chunk_size < 16:
                    raise WaveError("fmt chunk is shorter than PCM base header")
                tag, channels, rate, byte_rate, align, bits = struct.unpack_from("<HHIIHH", raw)
                valid_bits = bits
                channel_mask = None
                if tag == 0xFFFE:
                    if chunk_size < 40:
                        raise WaveError("WAVE_FORMAT_EXTENSIBLE fmt chunk is incomplete")
                    cb_size, valid_bits, channel_mask = struct.unpack_from("<HHI", raw, 16)
                    if cb_size < 22 or raw[24:40] != PCM_GUID:
                        raise WaveError("extensible WAV subtype must be PCM")
                elif tag != 1:
                    raise WaveError(f"unsupported WAV format tag 0x{tag:04x}; expected PCM")
                fmt = {
                    "format_tag": tag, "channels": channels, "sample_rate": rate,
                    "byte_rate": byte_rate, "block_align": align,
                    "bits_per_sample": bits, "valid_bits_per_sample": valid_bits,
                    "channel_mask": channel_mask,
                }
            elif chunk_id == b"data":
                if data_chunk is not None:
                    raise WaveError("multiple data chunks are unsupported")
                data_chunk = {"offset": chunk_start, "bytes": chunk_size}
            f.seek(padded_end)
        if fmt is None or data_chunk is None:
            raise WaveError("WAV must contain one fmt and one data chunk")
        ch, rate, bits, valid = EXPECTED
        if (fmt["channels"], fmt["sample_rate"], fmt["bits_per_sample"],
                fmt["valid_bits_per_sample"]) != (ch, rate, bits, valid):
            raise WaveError("expected six-channel 48 kHz signed 32-bit PCM with 32 valid bits")
        expected_align = ch * (bits // 8)
        if fmt["block_align"] != expected_align or fmt["byte_rate"] != rate * expected_align:
            raise WaveError("inconsistent block alignment or byte rate")
        if data_chunk["bytes"] % expected_align:
            raise WaveError("data length is not a whole number of sample frames")
        data_chunk["frames"] = data_chunk["bytes"] // expected_align
        fmt["container"] = "WAVE_FORMAT_EXTENSIBLE PCM" if fmt["format_tag"] == 0xFFFE else "PCM"
        return {"path": str(path), "file_bytes": file_size, "format": fmt, "data": data_chunk}


def _new_accumulator() -> dict:
    return {"sum_squares": 0, "peak_abs": 0, "clipped": 0, "frames": 0}


def _finish_accumulator(a: dict) -> dict:
    frames = a["frames"]
    rms = math.sqrt(a["sum_squares"] / frames) / FULL_SCALE if frames else 0.0
    return {
        "frames": frames,
        "rms": rms,
        "peak": a["peak_abs"] / FULL_SCALE,
        "peak_abs_s32": a["peak_abs"],
        "clipped_samples": a["clipped"],
    }


def analyze(path: str | Path) -> dict:
    meta = inspect_wave(path)
    channels = {str(c): _new_accumulator() for c in (1, 2)}
    windows = []
    window = {str(c): _new_accumulator() for c in (1, 2)}
    window_start = 0
    frame_fmt = struct.Struct("<6i")
    with Path(path).open("rb") as f:
        f.seek(meta["data"]["offset"])
        remaining = meta["data"]["frames"]
        while remaining:
            count = min(remaining, 4096)
            raw = _read_exact(f, count * frame_fmt.size)
            for offset in range(0, len(raw), frame_fmt.size):
                samples = frame_fmt.unpack_from(raw, offset)
                index = meta["data"]["frames"] - remaining + offset // frame_fmt.size
                for c in (1, 2):
                    value = samples[c - 1]
                    a = channels[str(c)]
                    w = window[str(c)]
                    for acc in (a, w):
                        acc["frames"] += 1
                        acc["sum_squares"] += value * value
                        magnitude = abs(value)
                        if magnitude > acc["peak_abs"]:
                            acc["peak_abs"] = magnitude
                        if value in (-FULL_SCALE, FULL_SCALE - 1):
                            acc["clipped"] += 1
                if index + 1 - window_start >= WINDOW_FRAMES:
                    windows.append({
                        "start_seconds": window_start / meta["format"]["sample_rate"],
                        "duration_seconds": WINDOW_FRAMES / meta["format"]["sample_rate"],
                        "channels": {c: _finish_accumulator(a) for c, a in window.items()},
                    })
                    window = {str(c): _new_accumulator() for c in (1, 2)}
                    window_start = index + 1
            remaining -= count
    if window["1"]["frames"]:
        frames = window["1"]["frames"]
        windows.append({
            "start_seconds": window_start / meta["format"]["sample_rate"],
            "duration_seconds": frames / meta["format"]["sample_rate"],
            "channels": {c: _finish_accumulator(a) for c, a in window.items()},
        })
    return {
        "format": meta["format"],
        "data_frames": meta["data"]["frames"],
        "duration_seconds": meta["data"]["frames"] / meta["format"]["sample_rate"],
        "channels": {c: _finish_accumulator(a) for c, a in channels.items()},
        "windows": windows,
    }


def read_annotations(path: str | Path, duration: float) -> list[dict]:
    annotations = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"annotations line {line_no}: invalid JSON") from e
            if not isinstance(item, dict) or item.get("kind") not in ("boot", "stimulus"):
                raise ValueError(f"annotations line {line_no}: kind must be boot or stimulus")
            t = item.get("t_seconds")
            if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0:
                raise ValueError(f"annotations line {line_no}: t_seconds must be finite and nonnegative")
            label = item.get("label", "")
            if not isinstance(label, str):
                raise ValueError(f"annotations line {line_no}: label must be text")
            annotations.append({
                "kind": item["kind"], "t_seconds": float(t),
                "within_capture": t <= duration, "label": label,
                "interpretation": "timing annotation only; does not prove MIDI event receipt",
            })
    return annotations


def compare_windows(current: dict, baseline: dict) -> dict:
    if current["format"] != baseline["format"]:
        raise WaveError("baseline WAV format differs from current capture")
    result = []
    for i, (now, before) in enumerate(zip(current["windows"], baseline["windows"])):
        channels = {}
        for c in ("1", "2"):
            a, b = now["channels"][c], before["channels"][c]
            channels[c] = {
                "current_rms": a["rms"], "baseline_rms": b["rms"],
                "rms_delta": a["rms"] - b["rms"],
                "current_peak": a["peak"], "baseline_peak": b["peak"],
                "current_clipped_samples": a["clipped_samples"],
                "baseline_clipped_samples": b["clipped_samples"],
            }
        result.append({"window_index": i, "channels": channels})
    return {"matched_windows": len(result), "windows": result,
            "note": "windows are matched by capture-relative index; unmatched tails are omitted"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wav")
    parser.add_argument("--annotations", help="optional JSONL with kind=boot|stimulus and t_seconds")
    parser.add_argument("--baseline", help="optional pre-install WAV in the same required format")
    parser.add_argument("-o", "--output", help="JSON output path (default stdout)")
    args = parser.parse_args()
    try:
        result = analyze(args.wav)
        result["annotations"] = read_annotations(args.annotations, result["duration_seconds"]) if args.annotations else []
        if args.baseline:
            result["baseline"] = analyze(args.baseline)
            result["comparison"] = compare_windows(result, result["baseline"])
    except (OSError, WaveError, ValueError) as e:
        parser.error(str(e))
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

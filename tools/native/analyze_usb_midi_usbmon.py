#!/usr/bin/env python3
"""Analyze a bounded Linux usbmon 1u text capture for one USB-MIDI OUT endpoint.

This reports host-side URB submissions and callbacks. A successful callback is
not evidence that a USB device parsed or acted on a MIDI message.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Any

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_ROWS = 200_000
MAX_LINE_BYTES = 8 * 1024
MAX_DIAGNOSTICS = 256
MAX_PACKET_RECORDS = 100_000
ADDRESS_RE = re.compile(r"(?P<pipe>[BCZI][io]):(?P<bus>[0-9]+):(?P<device>[0-9]+):(?P<endpoint>[0-9]+)\Z")
DECIMAL_RE = re.compile(r"[0-9]+\Z")
TAG_RE = re.compile(r"[^\s]+\Z")


def _bounded_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [0, {maximum}]")
    return value


def _parse_payload(words: list[str], line_number: int) -> bytes:
    if not words or words[0] != "=":
        return b""
    output = bytearray()
    for word in words[1:]:
        if word in ("<", ">", "="):
            raise ValueError(f"line {line_number}: unexpected usbmon data marker")
        if len(word) < 2 or len(word) > 8 or len(word) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", word):
            raise ValueError(f"line {line_number}: malformed usbmon data word")
        output.extend(bytes.fromhex(word))
    return bytes(output)


def _packet_events(payload: bytes, line_number: int) -> tuple[list[dict[str, int | str]], list[str]]:
    packets: list[dict[str, int | str]] = []
    issues: list[str] = []
    complete = len(payload) // 4
    if len(payload) % 4:
        issues.append(f"line {line_number}: captured MIDI payload ends with a partial 4-byte USB-MIDI event")
    for index in range(complete):
        cable_cin, status, data1, data2 = payload[index * 4:index * 4 + 4]
        cin = cable_cin & 0x0F
        message_type = status & 0xF0
        if message_type == 0x80:
            if cin != 0x8:
                issues.append(f"line {line_number}: Note Off status has non-Note-Off CIN 0x{cin:x}")
                continue
            kind = "note_off"
        elif message_type == 0x90:
            if cin != 0x9:
                issues.append(f"line {line_number}: Note On status has non-Note-On CIN 0x{cin:x}")
                continue
            kind = "note_off_zero_velocity" if data2 == 0 else "note_on"
        else:
            continue
        if data1 >= 0x80 or data2 >= 0x80:
            issues.append(f"line {line_number}: note event contains non-7-bit MIDI data")
            continue
        packets.append({
            "packet_index": index,
            "cable": cable_cin >> 4,
            "cin": cin,
            "kind": kind,
            "channel": (status & 0x0F) + 1,
            "note": data1,
            "velocity": data2,
        })
    return packets, issues


def analyze_usbmon(raw: bytes | str, *, bus: int, device: int) -> dict[str, Any]:
    """Parse usbmon 1u rows for bulk OUT endpoint 1 on the exact bus/device."""
    bus = _bounded_int(bus, "bus", 9999)
    device = _bounded_int(device, "device", 9999)
    if isinstance(raw, str):
        try:
            encoded = raw.encode("ascii")
        except UnicodeEncodeError as exc:
            raise ValueError("usbmon text must be ASCII") from exc
    elif isinstance(raw, bytes):
        encoded = raw
    else:
        raise ValueError("usbmon input must be bytes or text")
    if len(encoded) > MAX_INPUT_BYTES:
        raise ValueError(f"usbmon input exceeds {MAX_INPUT_BYTES} bytes")
    try:
        text = encoded.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("usbmon text must be ASCII") from exc

    submissions: list[dict[str, Any]] = []
    pending: dict[str, dict[str, Any]] = {}
    completions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, int | str]] = []
    diagnostic_count = 0
    counts = {
        "rows": 0,
        "target_submissions": 0,
        "target_submission_errors": 0,
        "target_completions": 0,
        "successful_completions": 0,
        "zero_status_completions": 0,
        "filtered_rows": 0,
        "malformed_rows": 0,
        "unmatched_completions": 0,
        "unmatched_submission_errors": 0,
        "duplicate_outstanding_tags": 0,
        "uncompleted_submissions": 0,
    }

    def diagnose(code: str, line_number: int, message: str) -> None:
        nonlocal diagnostic_count
        diagnostic_count += 1
        if len(diagnostics) < MAX_DIAGNOSTICS:
            diagnostics.append({"code": code, "line": line_number, "message": message[:240]})

    lines = text.splitlines()
    if len(lines) > MAX_ROWS:
        raise ValueError(f"usbmon input exceeds {MAX_ROWS} rows")
    for line_number, line in enumerate(lines, 1):
        if len(line.encode("ascii")) > MAX_LINE_BYTES:
            raise ValueError(f"line {line_number}: row exceeds {MAX_LINE_BYTES} bytes")
        if not line.strip():
            continue
        counts["rows"] += 1
        fields = line.split()
        if len(fields) < 5 or not TAG_RE.fullmatch(fields[0]) or not DECIMAL_RE.fullmatch(fields[1]):
            counts["malformed_rows"] += 1
            diagnose("malformed_row", line_number, "missing or invalid common usbmon fields")
            continue
        tag, timestamp_text, event, address, status_text = fields[:5]
        if event not in ("S", "C", "E"):
            counts["malformed_rows"] += 1
            diagnose("malformed_row", line_number, f"unsupported event type {event!r}")
            continue
        match = ADDRESS_RE.fullmatch(address)
        if match is None:
            counts["malformed_rows"] += 1
            diagnose("malformed_row", line_number, "invalid usbmon address word")
            continue
        address_tuple = (match["pipe"], int(match["bus"]), int(match["device"]), int(match["endpoint"]))
        timestamp = int(timestamp_text)
        selected = address_tuple == ("Bo", bus, device, 1)
        if not selected:
            counts["filtered_rows"] += 1
            continue

        if event == "S":
            if len(fields) < 6 or not re.fullmatch(r"-?[0-9]+", status_text) or not DECIMAL_RE.fullmatch(fields[5]):
                counts["malformed_rows"] += 1
                diagnose("malformed_submission", line_number, "invalid status or requested length")
                continue
            requested = int(fields[5])
            try:
                payload = _parse_payload(fields[6:], line_number)
            except ValueError as exc:
                counts["malformed_rows"] += 1
                diagnose("malformed_payload", line_number, str(exc))
                continue
            if len(payload) > requested:
                counts["malformed_rows"] += 1
                diagnose("payload_exceeds_declared_length", line_number, "captured bytes exceed requested length")
                continue
            packets, packet_issues = _packet_events(payload, line_number)
            submission = {
                "tag": tag,
                "timestamp_us": timestamp,
                "line": line_number,
                "requested_bytes": requested,
                "captured_bytes": len(payload),
                "payload_truncated": len(payload) < requested,
                "decoded_note_events": packets,
            }
            submissions.append(submission)
            counts["target_submissions"] += 1
            for issue in packet_issues:
                diagnose("malformed_midi_packet", line_number, issue)
            if tag in pending:
                counts["duplicate_outstanding_tags"] += 1
                diagnose("duplicate_outstanding_tag", line_number, "tag submitted again before prior completion")
            else:
                pending[tag] = submission
        elif event == "C":
            if not re.fullmatch(r"-?[0-9]+", status_text) or len(fields) < 6 or not DECIMAL_RE.fullmatch(fields[5]):
                counts["malformed_rows"] += 1
                diagnose("malformed_completion", line_number, "invalid status or actual length")
                continue
            status = int(status_text)
            actual = int(fields[5])
            item = pending.pop(tag, None)
            if item is None:
                counts["unmatched_completions"] += 1
                diagnose("unmatched_completion", line_number, "no outstanding selected submission has this tag")
                completions.append({"tag": tag, "timestamp_us": timestamp, "status": status,
                                    "actual_bytes": actual, "matched_submission": False,
                                    "successful_completion": False})
                continue
            counts["target_completions"] += 1
            if status == 0:
                counts["zero_status_completions"] += 1
            succeeded = status == 0 and actual == item["requested_bytes"]
            if succeeded:
                counts["successful_completions"] += 1
            item["completion"] = {"timestamp_us": timestamp, "status": status, "actual_bytes": actual,
                                  "successful_completion": succeeded}
            completions.append({"tag": tag, "timestamp_us": timestamp, "status": status,
                                "actual_bytes": actual, "matched_submission": True,
                                "successful_completion": succeeded})
        else:  # E: usbmon submission error
            if not re.fullmatch(r"-?[0-9]+", status_text):
                counts["malformed_rows"] += 1
                diagnose("malformed_submission_error", line_number, "invalid submission-error status")
                continue
            status = int(status_text)
            item = pending.pop(tag, None)
            if item is None:
                counts["unmatched_submission_errors"] += 1
                diagnose("unmatched_submission_error", line_number, "no outstanding selected submission has this tag")
            else:
                counts["target_submission_errors"] += 1
                item["submission_error"] = {"timestamp_us": timestamp, "status": status}

    for tag, item in pending.items():
        counts["uncompleted_submissions"] += 1
        diagnose("uncompleted_submission", item["line"], f"tag {tag!r} has no completion or submission-error event")
    for item in submissions:
        item.pop("line", None)

    return {
        "schema": 1,
        "kind": "usb-midi-usbmon-analysis",
        "scope": {"bus": bus, "device": device, "endpoint": 1, "direction": "bulk-out"},
        "evidence_boundary": {
            "successful_completion_means": "host USB callback status zero and actual length equals requested length",
            "does_not_establish": "device-side USB reception, MIDI parser acceptance, note handling, or audible output",
            "payload_capture": "captured usbmon bytes may be shorter than the requested or actual transfer length",
        },
        "counts": counts,
        "submissions": submissions[:MAX_PACKET_RECORDS],
        "completions": completions[:MAX_PACKET_RECORDS],
        "diagnostics": diagnostics,
        "diagnostics_truncated": diagnostic_count > len(diagnostics),
        "records_truncated": len(submissions) > MAX_PACKET_RECORDS or len(completions) > MAX_PACKET_RECORDS,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="usbmon 1u text capture")
    parser.add_argument("--bus", type=int, required=True, help="exact decimal USB bus number")
    parser.add_argument("--device", type=int, required=True, help="exact decimal USB device address")
    args = parser.parse_args()
    try:
        size = args.capture.stat().st_size
        if size > MAX_INPUT_BYTES:
            raise ValueError(f"usbmon input exceeds {MAX_INPUT_BYTES} bytes")
        report = analyze_usbmon(args.capture.read_bytes(), bus=args.bus, device=args.device)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    json.dump(report, sys.stdout, sort_keys=True, indent=2, allow_nan=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

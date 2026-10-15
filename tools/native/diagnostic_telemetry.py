"""Decode private Lunar Trio diagnostic SysEx; this tool never opens a device."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = b"\xf0\x7dLUNAR\x01"
FIELDS = (
    "uptime_ms", "render_ticks_max", "draw_ticks_max", "audio_underruns",
    "usb_messages", "uart_bytes", "accepted_noteons", "rejected_messages",
    "master_adc", "user_stack_margin", "system_stack_margin", "stack_samples",
    "initial_engine_result", "produced_audio_blocks",
)
FRAME_BYTES = len(PREFIX) + 5 * len(FIELDS) + 1


def decode_frame(frame: bytes) -> dict[str, int]:
    """Require a complete schema-1 frame, including canonical uint32 digits."""
    if len(frame) != FRAME_BYTES or not frame.startswith(PREFIX) or frame[-1] != 0xF7:
        raise ValueError("not a complete Lunar diagnostic schema-1 frame")
    result = {}
    for index, name in enumerate(FIELDS):
        digits = frame[len(PREFIX) + index * 5:len(PREFIX) + (index + 1) * 5]
        if any(d > 127 for d in digits) or digits[4] > 15:
            raise ValueError("noncanonical diagnostic uint32")
        result[name] = sum(d << (7 * i) for i, d in enumerate(digits))
    return result


def decode_capture(data: bytes) -> list[dict[str, int]]:
    """Read concatenated SysEx frames, permitting interleaved MIDI realtime.

    Other messages, unknown schemas and truncated captures are errors rather
    than evidence of zero counters. Capture provenance belongs to the boot
    receipt; these counters alone cannot establish source identity or acceptance.
    """
    clean = bytes(b for b in data if b < 0xF8)
    if not clean or len(clean) % FRAME_BYTES:
        raise ValueError("empty or truncated diagnostic capture")
    return [decode_frame(clean[i:i + FRAME_BYTES])
            for i in range(0, len(clean), FRAME_BYTES)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="raw MIDI SysEx capture")
    args = parser.parse_args()
    print(json.dumps(decode_capture(args.capture.read_bytes()), indent=2))


if __name__ == "__main__":
    main()

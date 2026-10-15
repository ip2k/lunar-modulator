"""Decode private Lunar diagnostic SysEx; this tool never opens a device."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

PREFIX = b"\xf0\x7dLUNAR\x01"
CLOCK_PREFIX = b"\xf0\x7dLUNAR\x03"
CLOCK_FIELDS = ("snapshot_uptime_ms", "clk_con0_raw", "clk_con2_raw", "sys_div_raw")
CLOCK_FRAME_BYTES = len(CLOCK_PREFIX) + 5 * len(CLOCK_FIELDS) + 1
PLL_PREFIX = b"\xf0\x7dLUNAR\x04"
PLL_FIELDS = ("snapshot_uptime_ms", "pll_osc_selector_raw", "pll_predivider_raw", "pll_multiplier_raw")
PLL_FRAME_BYTES = len(PLL_PREFIX) + 5 * len(PLL_FIELDS) + 1
PRODUCER_GAP_PREFIX = b"\xf0\x7dLUNAR\x05"
PRODUCER_GAP_FIELDS = (
    "uptime_ms", "refill_entry_calls", "max_refill_entry_gap_ticks",
    "max_render_call_ticks", "published_blocks", "max_publish_gap_ticks",
    "min_queue_depth", "max_display_wait_ticks", "max_display_work_ticks",
    "display_calls",
)
PRODUCER_GAP_FRAME_BYTES = len(PRODUCER_GAP_PREFIX) + 5 * len(PRODUCER_GAP_FIELDS) + 1
IRQ_PROFILE_PREFIX = b"\xf0\x7dLUNAR\x06"
IRQ_PROFILE_FIELDS = (
    "uptime_ms", "busy_ticks", "alnk_count", "alnk_ticks", "alnk_max_ticks",
    "timer5_count", "timer5_ticks", "timer5_max_ticks", "input_count",
    "input_ticks", "input_max_ticks", "usb_count", "usb_ticks", "usb_max_ticks",
    "uac_count", "uac_ticks", "uac_max_ticks", "render_calls",
    "render_elapsed_ticks", "render_irq_ticks", "overflow_count", "mismatch_count",
)
IRQ_PROFILE_FRAME_BYTES = len(IRQ_PROFILE_PREFIX) + 5 * len(IRQ_PROFILE_FIELDS) + 1
ENGINE_PROFILE_PREFIX = b"\xf0\x7dLUNAR\x07"
ENGINE_PROFILE_FIELDS = (
    "uptime_ms", "drums_render_ticks", "drums_render_calls",
    "drums_render_block_ticks", "drums_render_block_calls",
    "sixop_render_ticks", "sixop_render_calls",
    "sixop_render_block_ticks", "sixop_render_block_calls",
)
ENGINE_PROFILE_FRAME_BYTES = len(ENGINE_PROFILE_PREFIX) + 5 * len(ENGINE_PROFILE_FIELDS) + 1
CPU_RATE_PREFIX = b"\xf0\x7dLUNAR\x08"
CPU_RATE_FIELDS = (
    "uptime_ms", "iterations_per_trial", "trials_per_kernel",
    "xip_elapsed_ticks", "ram_elapsed_ticks", "xip_checksum",
    "ram_checksum", "status",
)
CPU_RATE_FRAME_BYTES = len(CPU_RATE_PREFIX) + 5 * len(CPU_RATE_FIELDS) + 1
PROFILE_PREFIX = b"\xf0\x7dLUNAR\x02"
FIELDS = (
    "uptime_ms", "render_ticks_max", "draw_ticks_max", "audio_underruns",
    "usb_messages", "uart_bytes", "accepted_noteons", "rejected_messages",
    "master_adc", "user_stack_margin", "system_stack_margin", "stack_samples",
    "initial_engine_result", "produced_audio_blocks",
)
FRAME_BYTES = len(PREFIX) + 5 * len(FIELDS) + 1
PROFILE_STAGES = (
    "sequence_dispatch", "sound_0", "sound_1", "sound_2", "sound_3",
    "master_fx_0", "master_fx_1", "postmix", "display_strip",
)
PROFILE_FIELDS = ("uptime_ms",) + tuple(
    f"{stage}_{metric}" for stage in PROFILE_STAGES
    for metric in ("window_ticks", "max_ticks", "calls")
)
PROFILE_FRAME_BYTES = len(PROFILE_PREFIX) + 5 * len(PROFILE_FIELDS) + 1


def _decode_values(frame: bytes, prefix: bytes, fields: tuple[str, ...], schema: int):
    expected = len(prefix) + 5 * len(fields) + 1
    if len(frame) != expected or not frame.startswith(prefix) or frame[-1] != 0xF7:
        raise ValueError(f"not a complete Lunar diagnostic schema-{schema} frame")
    result = {}
    for index, name in enumerate(fields):
        digits = frame[len(prefix) + index * 5:len(prefix) + (index + 1) * 5]
        if any(d > 127 for d in digits) or digits[4] > 15:
            raise ValueError("noncanonical diagnostic uint32")
        result[name] = sum(d << (7 * i) for i, d in enumerate(digits))
    return result


def decode_frame(frame: bytes) -> dict[str, int]:
    """Require a complete schema-1 frame, including canonical uint32 digits."""
    return _decode_values(frame, PREFIX, FIELDS, 1)


def decode_profile_frame(frame: bytes) -> dict[str, int]:
    """Require a complete schema-2 render profile frame."""
    return _decode_values(frame, PROFILE_PREFIX, PROFILE_FIELDS, 2)


def decode_producer_gap_frame(frame: bytes) -> dict[str, int]:
    """Require a complete schema-5 main-loop refill/display observation."""
    return _decode_values(frame, PRODUCER_GAP_PREFIX, PRODUCER_GAP_FIELDS, 5)


def decode_irq_profile_frame(frame: bytes) -> dict[str, int]:
    """Require one complete schema-6 IRQ timing profile frame."""
    return _decode_values(frame, IRQ_PROFILE_PREFIX, IRQ_PROFILE_FIELDS, 6)


def decode_engine_profile_frame(frame: bytes) -> dict[str, int]:
    """Require a complete schema-7 engine outer/block timing frame."""
    return _decode_values(frame, ENGINE_PROFILE_PREFIX, ENGINE_PROFILE_FIELDS, 7)


def decode_cpu_rate_frame(frame: bytes) -> dict[str, int]:
    """Require schema-8 fixed-work XIP/SRAM raw-tick results."""
    return _decode_values(frame, CPU_RATE_PREFIX, CPU_RATE_FIELDS, 8)


def decode_any_frame(frame: bytes) -> tuple[int, dict[str, int]]:
    if frame.startswith(PREFIX):
        return 1, decode_frame(frame)
    if frame.startswith(PROFILE_PREFIX):
        return 2, decode_profile_frame(frame)
    if frame.startswith(CLOCK_PREFIX):
        return 3, _decode_values(frame, CLOCK_PREFIX, CLOCK_FIELDS, 3)
    if frame.startswith(PLL_PREFIX):
        return 4, _decode_values(frame, PLL_PREFIX, PLL_FIELDS, 4)
    if frame.startswith(PRODUCER_GAP_PREFIX):
        return 5, decode_producer_gap_frame(frame)
    if frame.startswith(IRQ_PROFILE_PREFIX):
        return 6, decode_irq_profile_frame(frame)
    if frame.startswith(ENGINE_PROFILE_PREFIX):
        return 7, decode_engine_profile_frame(frame)
    if frame.startswith(CPU_RATE_PREFIX):
        return 8, decode_cpu_rate_frame(frame)
    raise ValueError("unknown Lunar diagnostic schema")


def decode_capture(data: bytes) -> list[dict[str, int]]:
    """Read concatenated SysEx frames, permitting interleaved MIDI realtime.

    Other messages, unknown schemas and truncated captures are errors rather
    than evidence of zero counters. Capture provenance belongs to the boot
    receipt; these counters alone cannot establish source identity or acceptance.
    """
    clean = bytes(b for b in data if b < 0xF8)
    if not clean:
        raise ValueError("empty or truncated diagnostic capture")
    frames = []
    offset = 0
    while offset < len(clean):
        if clean.startswith(PREFIX, offset):
            size = FRAME_BYTES
        elif clean.startswith(PROFILE_PREFIX, offset):
            size = PROFILE_FRAME_BYTES
        elif clean.startswith(CLOCK_PREFIX, offset):
            size = CLOCK_FRAME_BYTES
        elif clean.startswith(PLL_PREFIX, offset):
            size = PLL_FRAME_BYTES
        elif clean.startswith(PRODUCER_GAP_PREFIX, offset):
            size = PRODUCER_GAP_FRAME_BYTES
        elif clean.startswith(IRQ_PROFILE_PREFIX, offset):
            size = IRQ_PROFILE_FRAME_BYTES
        elif clean.startswith(ENGINE_PROFILE_PREFIX, offset):
            size = ENGINE_PROFILE_FRAME_BYTES
        elif clean.startswith(CPU_RATE_PREFIX, offset):
            size = CPU_RATE_FRAME_BYTES
        else:
            raise ValueError("unknown or truncated diagnostic frame prefix")
        if offset + size > len(clean):
            raise ValueError("empty or truncated diagnostic capture")
        schema, values = decode_any_frame(clean[offset:offset + size])
        frames.append({"schema": schema, "values": values})
        offset += size
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="raw MIDI SysEx capture")
    args = parser.parse_args()
    print(json.dumps(decode_capture(args.capture.read_bytes()), indent=2))


if __name__ == "__main__":
    main()

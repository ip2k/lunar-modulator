from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.native import analyze_diagnostic_telemetry as analyzer
from tools.native import diagnostic_telemetry as codec
from tools.native import record_diagnostic_telemetry as recorder

ROOT = Path(__file__).resolve().parents[1]
GAP_VALUES = dict(zip(codec.PRODUCER_GAP_FIELDS, [
    1234, 80, 0xFFFFFFFF, 900, 120, 0x80000000, 2, 8000, 5000, 60,
]))


def encode_values(prefix: bytes, values: dict[str, int], fields: tuple[str, ...]) -> bytes:
    frame = bytearray(prefix)
    for name in fields:
        for digit in range(5):
            frame.append((values[name] >> (7 * digit)) & 0x7F)
    frame.append(0xF7)
    return bytes(frame)


def gap_frame(values=GAP_VALUES) -> bytes:
    return encode_values(codec.PRODUCER_GAP_PREFIX, values, codec.PRODUCER_GAP_FIELDS)


def test_native_schema5_encoder_matches_strict_python_decoder(tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a C compiler is required for the native wire encoder harness")
    source = tmp_path / "schema5.c"
    source.write_text(r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>
int main(void) {
    uint32_t values[LUNAR_PRODUCER_GAP_FIELDS] = {
        1234, 80, UINT32_MAX, 900, 120, 0x80000000u, 2, 8000, 5000, 60
    };
    assert(LUNAR_PRODUCER_GAP_BYTES == 59u);
    assert(LUNAR_PRODUCER_GAP_PACKETS == 20u);
    for (unsigned i = 0; i < LUNAR_PRODUCER_GAP_PACKETS; ++i) {
        uint32_t packet = lunar_producer_gap_packet(values, i);
        unsigned cin = packet & 15u;
        unsigned n = cin == 4u ? 3u : cin - 4u;
        assert(i + 1u == LUNAR_PRODUCER_GAP_PACKETS ? cin == 6u : cin == 4u);
        for (unsigned j = 0; j < n; ++j)
            putchar((packet >> (8u * (j + 1u))) & 255u);
    }
    assert(lunar_producer_gap_packet(values, LUNAR_PRODUCER_GAP_PACKETS) == 0u);
}
''')
    executable = tmp_path / "schema5"
    subprocess.run([
        compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
        "-I", str(ROOT / "firmware/native"), "-I", str(ROOT / "sim/web/src"),
        str(source), "-o", str(executable),
    ], check=True, capture_output=True, text=True)
    wire = subprocess.check_output([str(executable)])
    assert wire == gap_frame()
    assert codec.decode_any_frame(wire) == (5, GAP_VALUES)
    assert codec.decode_capture(wire + b"\xf8\xfe" + wire) == [
        {"schema": 5, "values": GAP_VALUES}, {"schema": 5, "values": GAP_VALUES}
    ]


@pytest.mark.parametrize("mutation", ["truncated", "terminator", "noncanonical"])
def test_schema5_wire_rejects_malformed_frame(mutation):
    frame = bytearray(gap_frame())
    if mutation == "truncated":
        frame.pop()
    elif mutation == "terminator":
        frame[-1] = 0
    else:
        frame[8 + 5 * 2 + 4] = 16
    with pytest.raises(ValueError):
        codec.decode_producer_gap_frame(bytes(frame))


def test_analyzer_preserves_schema5_raw_ticks_and_rejects_bad_event_fields():
    event = {"event": "producer_gap_frame", "schema": 5,
             "elapsed_seconds": 3.0, "values": GAP_VALUES}
    report = analyzer.analyze_jsonl([json.dumps(event)])
    assert report["producer_gap_frame_count"] == 1
    frame = report["producer_gap_frames"][0]
    assert frame["values"] == GAP_VALUES
    assert "raw device timer ticks" in frame["timing_units"]
    assert "best-effort" in frame["queue_depth_semantics"]
    malformed = dict(event, schema=4)
    with pytest.raises(ValueError, match="schema-5 fields"):
        analyzer.analyze_jsonl([json.dumps(malformed)])
    malformed = dict(event, values={**GAP_VALUES, "extra": 1})
    with pytest.raises(ValueError, match="schema-5 fields"):
        analyzer.analyze_jsonl([json.dumps(malformed)])


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        self.now += 0.01
        return self.now

    def wall_time(self):
        return 1_800_000_000 + self.now

    def sleep(self, duration):
        self.now += duration


class _Input:
    def __init__(self, messages):
        self.messages = list(messages)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_pending(self):
        messages, self.messages = self.messages, []
        return iter(messages)


class _Mido:
    backend = SimpleNamespace(name="fake", api="test")

    def __init__(self, messages):
        self.messages = messages

    def get_input_names(self):
        return ["FM-1 MIDI"]

    def open_input(self, name):
        assert name == "FM-1 MIDI"
        return _Input(self.messages)


def test_recorder_logs_schema5_as_versioned_producer_gap_frame(tmp_path):
    clock = _Clock()
    output = tmp_path / "capture"
    result = recorder.record(
        "FM-1 MIDI", "a" * 64, output, 0.05,
        mido_module=_Mido([SimpleNamespace(type="sysex", data=gap_frame()[1:-1])]),
        monotonic=clock.monotonic, wall_time=clock.wall_time, sleep=clock.sleep,
    )
    row = json.loads((output / "events.jsonl").read_text().splitlines()[0])
    assert row["event"] == "producer_gap_frame"
    assert row["schema"] == 5 and row["values"] == GAP_VALUES
    assert result["producer_gap_frame_count"] == 1
    assert result["midi_output_opened"] is False

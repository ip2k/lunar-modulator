from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.native import record_diagnostic_telemetry as recorder
from tools.native.diagnostic_telemetry import (
    FIELDS, FRAME_BYTES, PREFIX, PROFILE_FIELDS, PROFILE_FRAME_BYTES, PROFILE_PREFIX,
)


IMAGE_SHA = "a" * 64
FRAME = PREFIX + bytes(5 * 14) + b"\xf7"
assert len(FRAME) == FRAME_BYTES
PROFILE_FRAME = PROFILE_PREFIX + bytes(5 * len(PROFILE_FIELDS)) + b"\xf7"
assert len(PROFILE_FRAME) == PROFILE_FRAME_BYTES
from tools.native.diagnostic_telemetry import PLL_FIELDS, PLL_FRAME_BYTES, PLL_PREFIX
PLL_FRAME = PLL_PREFIX + bytes(5 * len(PLL_FIELDS)) + b"\xf7"
assert len(PLL_FRAME) == PLL_FRAME_BYTES
from tools.native.diagnostic_telemetry import IRQ_PROFILE_FIELDS, IRQ_PROFILE_FRAME_BYTES, IRQ_PROFILE_PREFIX
IRQ_PROFILE_FRAME = IRQ_PROFILE_PREFIX + bytes(5 * len(IRQ_PROFILE_FIELDS)) + b"\xf7"
assert len(IRQ_PROFILE_FRAME) == IRQ_PROFILE_FRAME_BYTES == 119


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def wall_time(self):
        return 1_800_000_000.0 + self.now

    def sleep(self, duration):
        self.now += duration


class FakeInput:
    def __init__(self, messages):
        self.messages = list(messages)
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def iter_pending(self):
        messages, self.messages = self.messages, []
        return iter(messages)


class FakeMido:
    def __init__(self, messages, names=("FM-1 MIDI",)):
        self.messages = messages
        self.names = list(names)
        self.opened = []

    def get_input_names(self):
        return self.names

    def open_input(self, name):
        self.opened.append(name)
        return FakeInput(self.messages)


class ContinuousInput(FakeInput):
    def __init__(self, clock):
        super().__init__([])
        self.clock = clock

    def iter_pending(self):
        while True:
            self.clock.now += 0.01
            yield SimpleNamespace(type="sysex", data=FRAME[1:-1])


class ContinuousMido(FakeMido):
    def __init__(self, clock):
        super().__init__([])
        self.clock = clock

    def open_input(self, name):
        self.opened.append(name)
        return ContinuousInput(self.clock)


class OversizedIterable:
    def __len__(self):
        return FRAME_BYTES

    def __iter__(self):
        raise AssertionError("oversized payload must be rejected before iteration")


def test_records_valid_frames_and_logs_other_input(tmp_path):
    clock = FakeClock()
    fake = FakeMido([
        SimpleNamespace(type="note_on", note=60),
        SimpleNamespace(type="sysex", data=FRAME[1:-1]),
        SimpleNamespace(type="sysex", data=FRAME[1:-2]),  # malformed/truncated
    ])
    out = tmp_path / "capture"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.06,
                              mido_module=fake, monotonic=clock.monotonic,
                              wall_time=clock.wall_time, sleep=clock.sleep)
    assert fake.opened == ["FM-1 MIDI"]
    assert (out / "raw.syx").read_bytes() == FRAME
    assert receipt["raw_sha256"] == hashlib.sha256(FRAME).hexdigest()
    assert receipt["valid_frame_count"] == 1
    assert receipt["midi_output_opened"] is False
    assert receipt["device_identity_verified"] is False
    assert receipt["elapsed_seconds"] >= receipt["timeout_seconds"]
    assert receipt["termination_reason"] == "capture_deadline_reached"
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == [
        "unrelated_message", "diagnostic_frame", "malformed_sysex"]
    assert rows[1]["values"]["uptime_ms"] == 0
    assert rows[1]["wall_time_utc"].endswith("+00:00")
    assert json.loads((out / "receipt.json").read_text()) == receipt


def test_records_mixed_schema_frames_with_bounded_versioned_events(tmp_path):
    clock = FakeClock()
    fake = FakeMido([
        SimpleNamespace(type="sysex", data=FRAME[1:-1]),
        SimpleNamespace(type="sysex", data=PROFILE_FRAME[1:-1]),
        SimpleNamespace(type="sysex", data=PLL_FRAME[1:-1]),
    ])
    out = tmp_path / "mixed"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.05,
                              mido_module=fake, monotonic=clock.monotonic,
                              wall_time=clock.wall_time, sleep=clock.sleep)
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["diagnostic_frame", "render_profile_frame", "pll_snapshot_frame"]
    assert [row["schema"] for row in rows] == [1, 2, 4]
    assert rows[0]["values"] == dict.fromkeys(FIELDS, 0)
    assert rows[1]["values"] == dict.fromkeys(PROFILE_FIELDS, 0)
    assert receipt["valid_frame_count"] == 3
    assert receipt["render_profile_frame_count"] == 1
    assert receipt["pll_snapshot_frame_count"] == 1
    assert (out / "raw.syx").read_bytes() == FRAME + PROFILE_FRAME + PLL_FRAME


def test_records_schema7_engine_profile_as_bounded_passive_frame(tmp_path):
    from tools.native.diagnostic_telemetry import (
        ENGINE_PROFILE_FIELDS, ENGINE_PROFILE_FRAME_BYTES, ENGINE_PROFILE_PREFIX,
    )
    values = dict.fromkeys(ENGINE_PROFILE_FIELDS, 0)
    values.update(uptime_ms=12000, drums_render_ticks=0xFFFFFFF0,
                  drums_render_calls=100, drums_render_block_ticks=800,
                  drums_render_block_calls=100, sixop_render_ticks=1200,
                  sixop_render_calls=100, sixop_render_block_ticks=700,
                  sixop_render_block_calls=100)
    # Use the canonical 7-bit uint32 wire encoder and ensure the recorder sees
    # one whole schema-7 SysEx, not a host-fragmented packet as a frame.
    frame = bytearray(ENGINE_PROFILE_PREFIX)
    for name in ENGINE_PROFILE_FIELDS:
        value = values[name]
        for shift in (0, 7, 14, 21, 28):
            frame.append((value >> shift) & 0x7f)
    frame.append(0xf7)
    assert len(frame) == ENGINE_PROFILE_FRAME_BYTES == 54
    clock = FakeClock()
    out = tmp_path / "engine-profile"
    receipt = recorder.record(
        "FM-1 MIDI", IMAGE_SHA, out, 0.05,
        mido_module=FakeMido([SimpleNamespace(type="sysex", data=bytes(frame[1:-1]))]),
        monotonic=clock.monotonic, wall_time=clock.wall_time, sleep=clock.sleep,
    )
    row = json.loads((out / "events.jsonl").read_text().splitlines()[0])
    assert row["event"] == "engine_profile_frame" and row["schema"] == 7
    assert row["values"] == values
    assert receipt["engine_profile_frame_count"] == 1
    assert receipt["midi_output_opened"] is False
    assert (out / "raw.syx").read_bytes() == bytes(frame)


def test_exact_port_must_exist_once_before_open(tmp_path):
    fake = FakeMido([], names=("FM-1 MIDI", "FM-1 MIDI (2)"))
    with pytest.raises(ValueError, match="exact MIDI input"):
        recorder.record("FM-1", IMAGE_SHA, tmp_path / "capture", 1,
                        mido_module=fake)
    assert fake.opened == []
    assert not (tmp_path / "capture").exists()


def test_zero_valid_frames_is_failure_without_success_receipt(tmp_path):
    clock = FakeClock()
    out = tmp_path / "empty"
    with pytest.raises(RuntimeError, match="without a valid diagnostic frame"):
        recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.04,
                        mido_module=FakeMido([SimpleNamespace(type="note_off")]),
                        monotonic=clock.monotonic, wall_time=clock.wall_time,
                        sleep=clock.sleep)
    assert not (out / "receipt.json").exists()
    assert (out / "raw.syx").read_bytes() == b""


def test_continuous_input_cannot_extend_timeout(tmp_path):
    clock = FakeClock()
    out = tmp_path / "continuous"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.05,
                              mido_module=ContinuousMido(clock),
                              monotonic=clock.monotonic, wall_time=clock.wall_time,
                              sleep=clock.sleep)
    assert 0.05 <= clock.now < 0.06
    assert receipt["valid_frame_count"] == 4
    assert receipt["raw_bytes"] == 4 * FRAME_BYTES


def test_oversized_payload_is_rejected_before_iteration(tmp_path):
    clock = FakeClock()
    fake = FakeMido([
        SimpleNamespace(type="sysex", data=OversizedIterable()),
        SimpleNamespace(type="sysex", data=FRAME[1:-1]),
    ])
    out = tmp_path / "oversized"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.04,
                              mido_module=fake, monotonic=clock.monotonic,
                              wall_time=clock.wall_time, sleep=clock.sleep)
    assert receipt["valid_frame_count"] == 1
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["malformed_sysex", "diagnostic_frame"]


@pytest.mark.parametrize("timeout", [0, -1, 180.01, float("inf"), True])
def test_timeout_is_strictly_bounded(timeout, tmp_path):
    with pytest.raises(ValueError, match="timeout"):
        recorder.record("FM-1 MIDI", IMAGE_SHA, tmp_path / "capture", timeout,
                        mido_module=FakeMido([]))


def test_output_directory_is_exclusive(tmp_path):
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(FileExistsError):
        recorder.record("FM-1 MIDI", IMAGE_SHA, out, 1,
                        mido_module=FakeMido([]))


def test_records_clock_snapshot_separately_without_opening_output(tmp_path):
    from tools.native.diagnostic_telemetry import CLOCK_PREFIX, CLOCK_FIELDS
    frame = CLOCK_PREFIX + bytes(5 * len(CLOCK_FIELDS)) + b"\xf7"
    clock = FakeClock()
    fake = FakeMido([SimpleNamespace(type="sysex", data=frame[1:-1])])
    out = tmp_path / "clock"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.05,
                              mido_module=fake, monotonic=clock.monotonic,
                              wall_time=clock.wall_time, sleep=clock.sleep)
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert rows[0]["event"] == "clock_snapshot_frame"
    assert rows[0]["schema"] == 3
    assert rows[0]["values"] == dict.fromkeys(CLOCK_FIELDS, 0)
    assert receipt["clock_snapshot_frame_count"] == 1
    assert receipt["render_profile_frame_count"] == 0
    assert receipt["valid_frame_count"] == 1
    assert receipt["midi_output_opened"] is False
    assert (out / "raw.syx").read_bytes() == frame


def test_records_schema6_irq_profile_in_mixed_capture(tmp_path):
    clock = FakeClock()
    fake = FakeMido([
        SimpleNamespace(type="sysex", data=FRAME[1:-1]),
        SimpleNamespace(type="sysex", data=IRQ_PROFILE_FRAME[1:-1]),
    ])
    out = tmp_path / "irq"
    receipt = recorder.record("FM-1 MIDI", IMAGE_SHA, out, 0.05,
                              mido_module=fake, monotonic=clock.monotonic,
                              wall_time=clock.wall_time, sleep=clock.sleep)
    rows = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [row["event"] for row in rows] == ["diagnostic_frame", "irq_profile_frame"]
    assert [row["schema"] for row in rows] == [1, 6]
    assert rows[1]["values"] == dict.fromkeys(IRQ_PROFILE_FIELDS, 0)
    assert receipt["irq_profile_frame_count"] == 1
    assert receipt["valid_frame_count"] == 2
    assert (out / "raw.syx").read_bytes() == FRAME + IRQ_PROFILE_FRAME

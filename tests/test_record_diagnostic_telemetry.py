from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.native import record_diagnostic_telemetry as recorder
from tools.native.diagnostic_telemetry import FRAME_BYTES, PREFIX


IMAGE_SHA = "a" * 64
FRAME = PREFIX + bytes(5 * 14) + b"\xf7"
assert len(FRAME) == FRAME_BYTES


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

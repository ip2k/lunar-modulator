from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from tools.native import analyze_diagnostic_telemetry as analyzer
from tools.native import diagnostic_telemetry as codec
from tools.native import record_diagnostic_telemetry as recorder


def values(**overrides):
    result = {name: 0 for name in codec.FIELDS}
    result.update({
        "user_stack_margin": 1200,
        "system_stack_margin": 800,
        "stack_samples": 2,
    })
    result.update(overrides)
    return result


def row(elapsed, data, *, event="diagnostic_frame", **extra):
    item = {
        "event": event,
        "wall_time_utc": "2026-10-15T12:00:00.000+00:00",
        "elapsed_seconds": elapsed,
    }
    if event == "diagnostic_frame":
        item["values"] = data
    elif event == "render_profile_frame":
        item["schema"] = 2
        item["values"] = data
    item.update(extra)
    return json.dumps(item, separators=(",", ":"))


def test_deltas_rates_timing_stack_and_gaps_are_explicit():
    first = values(
        uptime_ms=1000, render_ticks_max=2400, draw_ticks_max=4800,
        audio_underruns=0xFFFFFFFE, usb_messages=10, uart_bytes=20,
        accepted_noteons=4, rejected_messages=1, produced_audio_blocks=500,
    )
    second = values(
        uptime_ms=3000, render_ticks_max=3600, draw_ticks_max=7200,
        audio_underruns=1, usb_messages=16, uart_bytes=26,
        accepted_noteons=5, rejected_messages=3, produced_audio_blocks=1880,
    )
    report = analyzer.analyze_jsonl([
        row(0.0, first),
        row(0.5, {}, event="unrelated_message", message_type="note_on"),
        row(2.0, second),
    ])

    before, after = report["frames"]
    assert report["diagnostic_frame_count"] == 2
    assert report["event_counts"] == {"diagnostic_frame": 2, "unrelated_message": 1}
    assert before["render_max_us"] == 100
    assert before["draw_max_us"] == 200
    assert before["counter_deltas"] is None
    assert after["elapsed_since_previous_frame_seconds"] == 2.0
    assert after["counter_deltas"] == {
        "uptime_ms": 2000,
        "audio_underruns": 3,
        "usb_messages": 6,
        "uart_bytes": 6,
        "accepted_noteons": 1,
        "rejected_messages": 2,
        "produced_audio_blocks": 1380,
    }
    assert after["counter_rates_per_second"]["audio_underruns"] == 1.5
    assert after["counter_rates_per_second"]["accepted_noteons"] == 0.5
    assert after["stack"]["user"] == {
        "bytes": 1200,
        "status": "observed_minimum_not_worst_case",
    }
    assert after["counter_rates_per_second"]["produced_audio_blocks"] == 690
    assert report["expected_audio_blocks_per_second"] == 44118 / 64
    assert report["audio_budget"]["block_deadline_ms"] == pytest.approx(64 / 44118 * 1000)
    assert report["audio_budget"]["nominal_block_deadline_ticks"] == pytest.approx(34815.7)
    assert "not independently physically calibrated" in report["audio_budget"]["nominal_timer_basis"]
    assert "do not contain per-block costs" in report["audio_budget"]["queue_sensitivity"]
    assert after["render_max_ratio_to_nominal_block_deadline"] == pytest.approx(3600 / 34815.7)


def test_stack_sentinel_and_zero_samples_are_unavailable():
    sample = values(user_stack_margin=0xFFFFFFFF, system_stack_margin=0xFFFFFFFF,
                    stack_samples=0)
    report = analyzer.analyze_jsonl([row(0, sample)])
    stack = report["frames"][0]["stack"]
    assert stack["user"] == {"bytes": None, "status": "unavailable"}
    assert stack["system"] == {"bytes": None, "status": "unavailable"}


def test_clock_snapshot_preserves_raw_startup_values_without_frequency_inference():
    raw = dict(zip(codec.CLOCK_FIELDS, [1234, 0xFFFFFFFF, 0x80000000, 0x12345678]))
    clock = row(0.5, None, event="clock_snapshot_frame", schema=3, values=raw)
    report = analyzer.analyze_jsonl([
        row(0, values(uptime_ms=1000, produced_audio_blocks=100)), clock,
        row(1, values(uptime_ms=2000, produced_audio_blocks=350)),
    ])
    assert report["clock_snapshot_frame_count"] == 1
    assert report["clock_snapshots"][0]["values"] == raw
    assert report["clock_snapshots"][0]["frequency_interpreted"] is False
    assert report["frames"][1]["counter_rates_per_device_second"]["produced_audio_blocks"] == 250
    alone = analyzer.analyze_jsonl([clock, clock])
    assert alone["diagnostic_frame_count"] == 0
    assert alone["clock_snapshot_frame_count"] == 2


def test_pll_snapshot_preserves_raw_startup_values_without_frequency_inference():
    raw = dict(zip(codec.PLL_FIELDS, [1234, 0x10203040, 0x55667788, 0x99AABBCC]))
    snapshot = row(0.75, None, event="pll_snapshot_frame", schema=4, values=raw)
    report = analyzer.analyze_jsonl([snapshot])
    assert report["pll_snapshot_frame_count"] == 1
    assert report["pll_snapshots"][0]["values"] == raw
    assert report["pll_snapshots"][0]["frequency_interpreted"] is False
    assert report["diagnostic_frame_count"] == 0


@pytest.mark.parametrize("mutation", ["schema", "missing", "extra", "bool", "negative", "overflow"])
def test_rejects_malformed_known_pll_snapshot(mutation):
    raw = dict.fromkeys(codec.PLL_FIELDS, 0)
    schema = 4
    if mutation == "schema":
        schema = True
    elif mutation == "missing":
        raw.pop("pll_multiplier_raw")
    elif mutation == "extra":
        raw["cpu_mhz"] = 240
    else:
        raw["pll_osc_selector_raw"] = {
            "bool": True, "negative": -1, "overflow": 0x100000000}[mutation]
    with pytest.raises(ValueError, match="schema-4 fields|must be a uint32"):
        analyzer.analyze_jsonl([row(0, None, event="pll_snapshot_frame", schema=schema, values=raw)])


@pytest.mark.parametrize("mutation", ["schema", "missing", "extra", "bool", "negative", "overflow"])
def test_rejects_malformed_known_clock_snapshot(mutation):
    raw = dict.fromkeys(codec.CLOCK_FIELDS, 0)
    schema = 3
    if mutation == "schema":
        schema = True
    elif mutation == "missing":
        raw.pop("sys_div_raw")
    elif mutation == "extra":
        raw["cpu_mhz"] = 240
    else:
        raw["clk_con0_raw"] = {"bool": True, "negative": -1, "overflow": 0x100000000}[mutation]
    with pytest.raises(ValueError, match="schema-3 fields|must be a uint32"):
        analyzer.analyze_jsonl([row(0, None, event="clock_snapshot_frame", schema=schema, values=raw)])


def test_buffered_reports_keep_device_rates_separate_from_host_arrival():
    report = analyzer.analyze_jsonl([
        row(0, values(uptime_ms=10000, produced_audio_blocks=200)),
        row(0.5, values(uptime_ms=42000, produced_audio_blocks=8200)),
    ])
    first, second = report["frames"]
    assert first["counter_rates_per_device_second"] is None
    assert second["device_seconds_since_previous_frame"] == 32
    assert second["counter_rates_per_second"]["produced_audio_blocks"] == 16000
    assert second["counter_rates_per_device_second"]["produced_audio_blocks"] == 250


def test_device_uptime_wrap_and_zero_interval():
    report = analyzer.analyze_jsonl([
        row(0, values(uptime_ms=0xFFFFFF00, produced_audio_blocks=100)),
        row(1, values(uptime_ms=744, produced_audio_blocks=350)),
        row(2, values(uptime_ms=744, produced_audio_blocks=351)),
    ])
    wrapped, same = report["frames"][1:]
    assert wrapped["device_seconds_since_previous_frame"] == 1
    assert wrapped["counter_rates_per_device_second"]["produced_audio_blocks"] == 250
    assert same["counter_rates_per_device_second"]["produced_audio_blocks"] is None


def test_equal_monotonic_timestamps_have_null_rate_not_division_or_invention():
    first = values(usb_messages=5)
    second = values(usb_messages=7)
    report = analyzer.analyze_jsonl([row(1.0, first), row(1.0, second)])
    frame = report["frames"][1]
    assert frame["elapsed_since_previous_frame_seconds"] == 0
    assert frame["counter_deltas"]["usb_messages"] == 2
    assert frame["counter_rates_per_second"]["usb_messages"] is None


@pytest.mark.parametrize("bad_elapsed", [True, -0.1, float("inf"), float("nan"), "1.0", 10**1000])
def test_rejects_invalid_elapsed_timestamps(bad_elapsed):
    with pytest.raises(ValueError, match="elapsed_seconds"):
        analyzer.analyze_jsonl([row(bad_elapsed, values())])


def test_rejects_elapsed_time_regression_even_across_unrelated_events():
    with pytest.raises(ValueError, match="moved backwards"):
        analyzer.analyze_jsonl([
            row(2.0, values()),
            row(1.5, {}, event="unrelated_message"),
        ])


@pytest.mark.parametrize("bad_value", [True, -1, 0x100000000, 1.5, "7"])
def test_rejects_non_uint32_telemetry_fields(bad_value):
    sample = values(usb_messages=bad_value)
    with pytest.raises(ValueError, match="usb_messages must be a uint32"):
        analyzer.analyze_jsonl([row(0, sample)])


def test_rejects_missing_extra_duplicate_and_malformed_schema_rows():
    valid = values()
    missing = dict(valid)
    del missing["usb_messages"]
    extra = dict(valid, caller_asserted_installable=True)
    with pytest.raises(ValueError, match="exactly the schema-1 fields"):
        analyzer.analyze_jsonl([row(0, missing)])
    with pytest.raises(ValueError, match="exactly the schema-1 fields"):
        analyzer.analyze_jsonl([row(0, extra)])
    duplicate = '{"event":"unrelated_message","event":"diagnostic_frame","elapsed_seconds":0,"values":{}}'
    with pytest.raises(ValueError, match="duplicate JSON key"):
        analyzer.analyze_jsonl([duplicate])
    with pytest.raises(ValueError, match="invalid JSON"):
        analyzer.analyze_jsonl(["{broken"])
    with pytest.raises(ValueError, match="no diagnostic or render_profile"):
        analyzer.analyze_jsonl([row(0, {}, event="unrelated_message")])


def test_profile_frames_are_separate_bounded_observations_and_allow_wrap():
    first = {name: 0 for name in codec.PROFILE_FIELDS}
    second = {name: 0 for name in codec.PROFILE_FIELDS}
    first["uptime_ms"] = 1000
    first["sound_0_window_ticks"] = 0xFFFFFFF0
    first["sound_0_max_ticks"] = 2400
    first["sound_0_calls"] = 500
    second["uptime_ms"] = 2000
    second["sound_0_window_ticks"] = 24
    second["sound_0_max_ticks"] = 3600
    second["sound_0_calls"] = 10
    report = analyzer.analyze_jsonl([
        row(0, first, event="render_profile_frame"),
        row(1, values(audio_underruns=4)),
        row(2, second, event="render_profile_frame"),
    ])
    assert report["diagnostic_frame_count"] == 1
    assert report["render_profile_frame_count"] == 2
    assert report["render_profiles"][0]["stages"]["sound_0"] == {
        "window_ticks": 0xFFFFFFF0, "window_us": 0xFFFFFFF0 / 24,
        "max_ticks": 2400, "max_us": 100,
        "timer_conversion": "nominal only: source-configured 24 ticks/us; physical calibration pending",
        "calls": 500,
    }
    assert report["render_profiles"][1]["stages"]["sound_0"]["window_ticks"] == 24
    assert report["render_profiles"][1]["elapsed_since_previous_profile_seconds"] == 2


def test_profile_rejects_unknown_or_non_uint32_values():
    good = {name: 0 for name in codec.PROFILE_FIELDS}
    altered = dict(good, made_up=1)
    with pytest.raises(ValueError, match="exactly schema-2 fields"):
        analyzer.analyze_jsonl([row(0, altered, event="render_profile_frame")])
    altered = dict(good, sound_0_calls=True)
    with pytest.raises(ValueError, match="sound_0_calls must be a uint32"):
        analyzer.analyze_jsonl([row(0, altered, event="render_profile_frame")])


@pytest.mark.parametrize("schema", [2.0, True, "2"])
def test_profile_schema_must_be_an_integer(schema):
    profile = {name: 0 for name in codec.PROFILE_FIELDS}
    with pytest.raises(ValueError, match="exactly schema-2 fields"):
        analyzer.analyze_jsonl([
            row(0, profile, event="render_profile_frame", schema=schema)
        ])


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
        self.messages = messages

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


def _encode_frame(data):
    body = bytearray(codec.PREFIX)
    for name in codec.FIELDS:
        value = data[name]
        for digit in range(5):
            body.append((value >> (7 * digit)) & 0x7F)
    return bytes(body) + b"\xf7"


def test_reads_actual_recorder_events_jsonl_schema(tmp_path):
    clock = _Clock()
    first = values(uptime_ms=1000, render_ticks_max=240, usb_messages=1)
    second = values(uptime_ms=2000, render_ticks_max=480, usb_messages=3)
    fake_mido = _Mido([
        SimpleNamespace(type="sysex", data=_encode_frame(first)[1:-1]),
        SimpleNamespace(type="note_on", note=60),
        SimpleNamespace(type="sysex", data=_encode_frame(second)[1:-1]),
    ])
    output = tmp_path / "capture"
    recorder.record(
        "FM-1 MIDI", "a" * 64, output, 0.5,
        mido_module=fake_mido,
        monotonic=clock.monotonic,
        wall_time=clock.wall_time,
        sleep=clock.sleep,
    )
    report = analyzer.analyze_file(output / "events.jsonl")
    assert report["event_counts"] == {"diagnostic_frame": 2, "unrelated_message": 1}
    assert report["frames"][1]["render_max_us"] == 20
    assert report["frames"][1]["counter_deltas"]["usb_messages"] == 2
    assert report["frames"][1]["elapsed_seconds"] > report["frames"][0]["elapsed_seconds"]


def test_irq_profile_rows_validate_exact_fields_and_compute_wrap_safe_cumulative_deltas():
    from tools.native.diagnostic_telemetry import IRQ_PROFILE_FIELDS
    first = dict.fromkeys(IRQ_PROFILE_FIELDS, 0)
    first.update(uptime_ms=1000, busy_ticks=0xFFFFFFF0, alnk_count=7,
                 alnk_max_ticks=42, render_irq_ticks=24)
    second = dict.fromkeys(IRQ_PROFILE_FIELDS, 0)
    second.update(uptime_ms=2000, busy_ticks=8, alnk_count=10,
                  alnk_max_ticks=50, render_irq_ticks=96)
    rows = [
        {"event": "irq_profile_frame", "schema": 6, "frame_index": index,
         "elapsed_seconds": index, "values": values}
        for index, values in enumerate((first, second))
    ]
    report = analyzer.analyze_jsonl(json.dumps(row) for row in rows)
    assert report["irq_profile_frame_count"] == 2
    observed = report["irq_profile_frames"][1]
    assert observed["counter_deltas"]["busy_ticks"] == 24
    assert observed["counter_deltas"]["alnk_count"] == 3
    assert "alnk_max_ticks" not in observed["counter_deltas"]
    assert observed["values"]["alnk_max_ticks"] == 50
    assert "do not infer duration" in observed["timing_units"]


@pytest.mark.parametrize("mutation", ["schema", "missing", "extra", "bool"])
def test_irq_profile_rejects_wrong_schema_or_nonexact_values(mutation):
    from tools.native.diagnostic_telemetry import IRQ_PROFILE_FIELDS
    values = dict.fromkeys(IRQ_PROFILE_FIELDS, 0)
    event = {"event": "irq_profile_frame", "schema": 6,
             "elapsed_seconds": 0, "values": values}
    if mutation == "schema":
        event["schema"] = 5
    elif mutation == "missing":
        values.pop(IRQ_PROFILE_FIELDS[-1])
    elif mutation == "extra":
        values["unexpected"] = 1
    else:
        values[IRQ_PROFILE_FIELDS[0]] = True
    with pytest.raises(ValueError):
        analyzer.analyze_jsonl([json.dumps(event)])


def test_engine_profile_rows_report_wrap_safe_cumulative_outer_and_block_counters():
    from tools.native.diagnostic_telemetry import ENGINE_PROFILE_FIELDS
    first = dict.fromkeys(ENGINE_PROFILE_FIELDS, 0)
    first.update(uptime_ms=10000, drums_render_ticks=0xFFFFFFF0,
                 drums_render_calls=10, drums_render_block_ticks=900,
                 drums_render_block_calls=10, sixop_render_ticks=2000,
                 sixop_render_calls=10, sixop_render_block_ticks=1500,
                 sixop_render_block_calls=10)
    second = dict.fromkeys(ENGINE_PROFILE_FIELDS, 0)
    second.update(uptime_ms=14000, drums_render_ticks=24,
                  drums_render_calls=15, drums_render_block_ticks=1300,
                  drums_render_block_calls=15, sixop_render_ticks=3000,
                  sixop_render_calls=15, sixop_render_block_ticks=2200,
                  sixop_render_block_calls=15)
    rows = [
        {"event": "engine_profile_frame", "schema": 7, "frame_index": i,
         "elapsed_seconds": i * 4, "values": values}
        for i, values in enumerate((first, second))
    ]
    report = analyzer.analyze_jsonl(json.dumps(item) for item in rows)
    assert report["engine_profile_frame_count"] == 2
    second_frame = report["engine_profile_frames"][1]
    assert second_frame["counter_deltas"]["drums_render_ticks"] == 40
    assert second_frame["counter_deltas"]["drums_render_calls"] == 5
    assert second_frame["counter_deltas"]["drums_render_block_ticks"] == 400
    assert second_frame["counter_deltas"]["sixop_render_block_calls"] == 5
    assert "not FIR-only" in second_frame["scope"]
    assert "no calibration inferred" in second_frame["timing_units"]


@pytest.mark.parametrize("mutation", ["schema", "missing", "extra", "bool", "overflow"])
def test_engine_profile_rejects_wrong_schema_or_nonexact_values(mutation):
    from tools.native.diagnostic_telemetry import ENGINE_PROFILE_FIELDS
    values = dict.fromkeys(ENGINE_PROFILE_FIELDS, 0)
    event = {"event": "engine_profile_frame", "schema": 7,
             "elapsed_seconds": 0, "values": values}
    if mutation == "schema":
        event["schema"] = True
    elif mutation == "missing":
        values.pop(ENGINE_PROFILE_FIELDS[-1])
    elif mutation == "extra":
        values["fir_only_ticks"] = 1
    elif mutation == "bool":
        values[ENGINE_PROFILE_FIELDS[0]] = True
    else:
        values[ENGINE_PROFILE_FIELDS[0]] = 0x100000000
    with pytest.raises(ValueError, match="schema-7 fields|must be a uint32"):
        analyzer.analyze_jsonl([json.dumps(event)])


def test_cpu_rate_analysis_is_raw_tick_only_and_rejects_unknown_status_bits():
    values = dict.fromkeys(codec.CPU_RATE_FIELDS, 0)
    values.update(uptime_ms=123, iterations_per_trial=4096, trials_per_kernel=4,
                  xip_elapsed_ticks=400, ram_elapsed_ticks=420,
                  xip_checksum=17, ram_checksum=17, status=3)
    event = {"event": "cpu_rate_frame", "schema": 8, "frame_index": 0,
             "elapsed_seconds": 4.0, "values": values}
    report = analyzer.analyze_jsonl([json.dumps(event)])
    assert report["cpu_rate_frame_count"] == 1
    result = report["cpu_rate_frames"][0]
    assert result["checks"]["both_elapsed_nonzero"]
    assert result["checks"]["checksums_match"]
    assert "raw TIMER4 ticks" in result["timing_units"]
    assert any("not an instruction counter or calibrated CPU frequency" in item
               for item in report["interpretation_limits"])
    for bad_values in (dict(values, status=4), dict(values, iterations_per_trial=1)):
        bad_event = dict(event, values=bad_values)
        with pytest.raises(ValueError):
            analyzer.analyze_jsonl([json.dumps(bad_event)])

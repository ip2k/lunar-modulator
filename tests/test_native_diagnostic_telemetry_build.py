"""Builder contract for telemetry-only and legacy Trio-pulse diagnostics."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
import build_application_probe as builder  # noqa: E402


def test_telemetry_is_opt_in_and_has_no_hardware_claim():
    assert builder.diagnostic_telemetry_configuration(False) == {
        "enabled": False,
        "compile_definition": None,
        "interval_ms": None,
        "transport": None,
        "hardware_tested": False,
    }
    assert builder.diagnostic_telemetry_flags(False) == []
    enabled = builder.validate_diagnostic_telemetry(True, "song-diagnostic")
    assert enabled == {
        "enabled": True,
        "compile_definition": "LUNAR_DIAGNOSTIC_TELEMETRY=1",
        "interval_ms": 1000,
        "transport": "USB-MIDI-SysEx",
        "hardware_tested": False,
    }
    assert builder.diagnostic_telemetry_flags(True) == [
        "-DLUNAR_DIAGNOSTIC_TELEMETRY=1"]


def test_telemetry_only_supports_prepared_project_runtime_modes():
    for mode in ("diagnostic", "song-diagnostic"):
        assert builder.validate_diagnostic_telemetry(True, mode)["enabled"]
    for mode in ("continuous", "invalid"):
        try:
            builder.validate_diagnostic_telemetry(True, mode)
        except ValueError as error:
            assert "bounded diagnostic runtime" in str(error)
        else:
            raise AssertionError(f"accepted telemetry in {mode!r}")


def test_producer_gap_profile_is_explicit_schema5_song_telemetry_only():
    import pytest

    disabled = builder.diagnostic_producer_gaps_configuration(False)
    assert disabled == {
        "enabled": False, "schema": None, "compile_definition": None,
        "frame_bytes": None, "packets_per_frame": None, "transport": None,
        "hardware_tested": False,
    }
    assert builder.diagnostic_producer_gaps_flags(False) == []
    enabled = builder.validate_diagnostic_producer_gaps(
        True, "song-diagnostic", True, 0, True)
    assert enabled == {
        "enabled": True, "schema": 5,
        "compile_definition": "LUNAR_DIAGNOSTIC_PRODUCER_GAPS=1",
        "frame_bytes": 59, "packets_per_frame": 20,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    assert builder.diagnostic_producer_gaps_flags(True) == [
        "-DLUNAR_DIAGNOSTIC_PRODUCER_GAPS=1"]
    for mode, telemetry, project, play in (
        ("diagnostic", True, 0, True),
        ("song-diagnostic", False, 0, True),
        ("song-diagnostic", True, None, True),
        ("song-diagnostic", True, 0, False),
    ):
        with pytest.raises(ValueError, match="producer-gap telemetry requires"):
            builder.validate_diagnostic_producer_gaps(
                True, mode, telemetry, project, play)
    with pytest.raises(TypeError):
        builder.diagnostic_producer_gaps_configuration(1)


def test_old_pulse_option_still_enables_telemetry_but_keeps_pulse_contract():
    assert not builder.diagnostic_telemetry_enabled(False, False)
    assert builder.diagnostic_telemetry_enabled(False, True)
    assert builder.diagnostic_telemetry_enabled(True, False)
    assert builder.diagnostic_telemetry_enabled(True, True)

    # The pulse remains independently constrained to a content-free profile.
    try:
        builder.validate_trio_diagnostic_pulse(
            True, "song-diagnostic", True, 0, None, True, True)
    except ValueError as error:
        assert "cannot be combined with startup content" in str(error)
    else:
        raise AssertionError("pulse accepted a prepared-project startup")


def test_app_telemetry_gate_is_separate_from_pulse_gate():
    source = (ROOT / "firmware/native/app_probe.c").read_text()
    report_start = source.index("static void diagnostic_report(void)")
    report_gate = source.rfind("#ifdef LUNAR_DIAGNOSTIC_TELEMETRY", 0, report_start)
    assert report_gate >= 0

    loop_start = source.index("for (;;) {", source.index("static void app_main(void)"))
    loop_end = source.index("\n    }\n}", loop_start)
    loop = source[loop_start:loop_end]
    assert "#ifdef LUNAR_DIAGNOSTIC_TRIO_PULSE" in loop
    assert "lunar_trio_diagnostic_pulse_poll" in loop
    assert "#ifdef LUNAR_DIAGNOSTIC_TELEMETRY\n        diagnostic_reports();" in loop

    # Both supported startup paths publish their real API result through the
    # existing telemetry field; the failure path returns to ROM before this.
    project_result = source.index("initial_engine_result = startup_project_result;")
    trio_result = source.index("initial_engine_result = (uint32_t)fm1_app_select")
    assert project_result < trio_result


def test_producer_gap_builder_wires_opt_in_flag_and_optional_receipt():
    source = (ROOT / "tools/native/build_application_probe.py").read_text()
    assert "--diagnostic-producer-gaps" in source
    assert "validate_diagnostic_producer_gaps(" in source
    assert "diagnostic_producer_gaps_flags(args.diagnostic_producer_gaps)" in source
    assert 'if args.diagnostic_producer_gaps:' in source
    assert 'report["diagnostic_producer_gaps"] = producer_gap_receipt' in source


def test_irq_profile_is_opt_in_schema6_song_telemetry_without_autoplay():
    import pytest

    disabled = builder.diagnostic_irq_profile_configuration(False)
    assert disabled == {
        "enabled": False, "schema": None, "compile_definition": None,
        "frame_bytes": None, "packets_per_frame": None,
        "transport": None, "hardware_tested": False,
    }
    assert builder.diagnostic_irq_profile_flags(False) == []
    enabled = builder.validate_diagnostic_irq_profile(True, "song-diagnostic", True)
    assert enabled == {
        "enabled": True, "schema": 6,
        "compile_definition": "LUNAR_DIAGNOSTIC_IRQ_PROFILE=1",
        "frame_bytes": 119, "packets_per_frame": 40,
        "transport": "USB-MIDI-SysEx", "hardware_tested": False,
    }
    assert builder.diagnostic_irq_profile_flags(True) == [
        "-DLUNAR_DIAGNOSTIC_IRQ_PROFILE=1"]
    source = (ROOT / "tools/native/build_application_probe.py").read_text()
    assert "--diagnostic-irq-profile" in source
    assert "diagnostic_irq_profile_flags(args.diagnostic_irq_profile)" in source
    assert 'report["diagnostic_irq_profile"] = irq_profile_receipt' in source
    for mode, telemetry in (("diagnostic", True), ("continuous", True),
                            ("song-diagnostic", False)):
        with pytest.raises(ValueError, match="explicit telemetry and song-diagnostic"):
            builder.validate_diagnostic_irq_profile(True, mode, telemetry)
    with pytest.raises(TypeError):
        builder.diagnostic_irq_profile_configuration(1)


def test_render_profile_is_explicit_telemetry_only_and_schema2_opt_in():
    disabled = builder.render_stage_profile_configuration(False)
    assert disabled["enabled"] is False
    assert disabled["compile_definition"] is None
    assert disabled["stages"] == []
    assert builder.render_stage_profile_flags(False) == []
    assert builder.validate_render_stage_profile(
        False, "continuous", False) == disabled
    enabled = builder.validate_render_stage_profile(True, "song-diagnostic", True)
    assert enabled["enabled"] is True
    assert enabled["schema"] == 2
    assert enabled["compile_definition"] == "LUNAR_RENDER_STAGE_PROFILE=1"
    assert builder.render_stage_profile_flags(True) == ["-DLUNAR_RENDER_STAGE_PROFILE=1"]
    assert enabled["stages"] == [
        "sequence_dispatch", "sound_0", "sound_1", "sound_2", "sound_3",
        "master_fx_0", "master_fx_1", "postmix", "display_strip",
    ]
    for mode, telemetry in (("continuous", True), ("song-diagnostic", False)):
        try:
            builder.validate_render_stage_profile(True, mode, telemetry)
        except ValueError as error:
            assert "explicit telemetry" in str(error)
        else:
            raise AssertionError("render profiler escaped its explicit diagnostic gate")


def test_engine_render_profile_is_opt_in_schema7_and_has_dedicated_cadence():
    import pytest
    disabled = builder.engine_render_profile_configuration(False)
    assert disabled["enabled"] is False
    assert disabled["compile_definition"] is None
    assert builder.engine_render_profile_flags(False) == []
    enabled = builder.validate_engine_render_profile(
        True, "song-diagnostic", True, True, False, False)
    assert enabled["schema"] == 7
    assert enabled["frame_bytes"] == 54
    assert enabled["packets_per_frame"] == 18
    assert enabled["compile_definition"] == "LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1"
    assert enabled["counter_semantics"] == "cumulative-uint32-device-timer-ticks"
    assert builder.engine_render_profile_flags(True) == [
        "-DLUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE=1"]
    for args in (
        ("diagnostic", True, True, False, False),
        ("song-diagnostic", False, True, False, False),
        ("song-diagnostic", True, False, False, False),
        ("song-diagnostic", True, True, True, False),
        ("song-diagnostic", True, True, False, True),
    ):
        with pytest.raises(ValueError, match="engine render profiling requires"):
            builder.validate_engine_render_profile(True, *args)
    with pytest.raises(TypeError):
        builder.engine_render_profile_configuration(1)
    source = (ROOT / "firmware/native/app_probe.c").read_text()
    assert "case 0: diagnostic_report(); break;" in source
    assert "case 1: diagnostic_profile_report(); break;" in source
    assert "default: diagnostic_engine_profile_report(); break;" in source


def test_engine_render_hooks_compile_out_when_disabled(tmp_path):
    import subprocess
    source = tmp_path / "profile.cpp"
    source.write_text(r'''
#include "engine_render_profile.h"
void render() {
    FM1_ENGINE_PROFILE_RENDER_BEGIN();
    FM1_ENGINE_PROFILE_BLOCK_BEGIN();
    FM1_ENGINE_PROFILE_BLOCK_END();
    FM1_ENGINE_PROFILE_RENDER_END(FM1_ENGINE_PROFILE_DRUMS);
}
''')
    assembly = tmp_path / "disabled.s"
    subprocess.run(["c++", "-std=c++11", "-O2", "-S", "-I",
                    str(ROOT / "engines/include"), str(source), "-o", str(assembly)], check=True)
    generated = assembly.read_text()
    assert "lunar_engine_profile" not in generated


def test_engine_render_hooks_accumulate_wrap_safe_outer_and_block_ticks(tmp_path):
    import subprocess
    source = tmp_path / "profile.cpp"
    source.write_text(r'''
#define LUNAR_DIAGNOSTIC_ENGINE_RENDER_PROFILE 1
#include "engine_render_profile.h"
#include <cassert>
static uint32_t samples[] = {0xfffffff0u, 0xfffffffcu, 3u, 10u};
static unsigned at;
static uint32_t got_engine, got_outer, got_blocks, got_calls;
extern "C" uint32_t lunar_engine_profile_ticks(void) { return samples[at++]; }
extern "C" void lunar_engine_profile_render(uint32_t engine, uint32_t outer,
                                              uint32_t blocks, uint32_t calls) {
    got_engine = engine; got_outer = outer; got_blocks = blocks; got_calls = calls;
}
static void render() {
    FM1_ENGINE_PROFILE_RENDER_BEGIN();
    FM1_ENGINE_PROFILE_BLOCK_BEGIN();
    FM1_ENGINE_PROFILE_BLOCK_END();
    FM1_ENGINE_PROFILE_RENDER_END(FM1_ENGINE_PROFILE_DRUMS);
}
int main() {
    render();
    assert(at == 4 && got_engine == FM1_ENGINE_PROFILE_DRUMS);
    assert(got_outer == 26u && got_blocks == 7u && got_calls == 1u);
}
''')
    exe = tmp_path / "profile"
    subprocess.run(["c++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "engines/include"),
                    str(source), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


def test_render_profiler_macros_compile_out_by_default(tmp_path):
    import subprocess
    source = tmp_path / "disabled.c"
    source.write_text(r'''
#include "render_stage_profile.h"
int render(int value) {
    LUNAR_PROFILE_START(unused_start);
    value = value * 3 + 1;
    LUNAR_PROFILE_FINISH(LUNAR_PROFILE_SOUND_0, unused_start);
    return value;
}
''')
    assembly = tmp_path / "disabled.s"
    subprocess.run(["cc", "-std=c99", "-O2", "-S", "-I",
                    str(ROOT / "sim/web/src"), str(source), "-o", str(assembly)],
                   check=True)
    generated = assembly.read_text()
    assert "lunar_profile" not in generated


def test_clock_snapshot_is_explicit_bounded_and_reports_no_frequency():
    import pytest
    assert builder.validate_clock_snapshot(False, "continuous", False)["enabled"] is False
    enabled = builder.validate_clock_snapshot(True, "song-diagnostic", True)
    assert enabled["schema"] == 3
    assert enabled["supplemental_schema"] == 4
    assert enabled["supplemental_registers"] == (
        "pll_osc_selector_raw", "pll_predivider_raw", "pll_multiplier_raw")
    assert enabled["supplemental_register_addresses"] == ("0x119a0", "0x119a8", "0x119ac")
    assert enabled["supplemental_frequency_interpreted"] is False
    assert enabled["register_writes"] is False
    assert enabled["frequency_interpreted"] is False
    assert enabled["hardware_tested"] is False
    for mode, telemetry in (("continuous", True), ("diagnostic", False)):
        with pytest.raises(ValueError, match="explicit telemetry"):
            builder.validate_clock_snapshot(True, mode, telemetry)
    with pytest.raises(TypeError):
        builder.validate_clock_snapshot(1, "diagnostic", True)

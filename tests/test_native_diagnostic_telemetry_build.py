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

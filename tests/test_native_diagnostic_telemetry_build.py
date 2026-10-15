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
    assert "#ifdef LUNAR_DIAGNOSTIC_TELEMETRY\n        diagnostic_report();" in loop

    # Both supported startup paths publish their real API result through the
    # existing telemetry field; the failure path returns to ROM before this.
    project_result = source.index("initial_engine_result = startup_project_result;")
    trio_result = source.index("initial_engine_result = (uint32_t)fm1_app_select")
    assert project_result < trio_result

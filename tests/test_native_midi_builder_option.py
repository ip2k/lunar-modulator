"""The optional TRS MIDI path is source-linked only on explicit opt-in."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
import build_application_probe as builder  # noqa: E402


def test_trs_midi_is_disabled_by_default_without_changing_usb_path():
    receipt = builder.native_midi_input_configuration(False)
    assert receipt == {
        "enabled": False,
        "compile_definition": None,
        "transport": None,
        "ring_bytes": 0,
        "bytes_per_poll": 0,
        "usb_midi_preserved": True,
        "diagnostic_counters": ["usb_messages_drained", "uart_bytes_processed",
                                "accepted_note_ons", "rejected_messages"],
        "hardware_tested": False,
    }
    assert builder.native_midi_input_flags(False) == []


def test_explicit_opt_in_is_bounded_and_keeps_usb_midi():
    receipt = builder.native_midi_input_configuration(True)
    assert receipt["enabled"] is True
    assert receipt["compile_definition"] == "LUNAR_UART1_MIDI=1"
    assert receipt["transport"] == "UART1-RX/PH8"
    assert receipt["ring_bytes"] == 256
    assert receipt["bytes_per_poll"] == 32
    assert receipt["usb_midi_preserved"] is True
    assert receipt["hardware_tested"] is False
    assert builder.native_midi_input_flags(True) == ["-DLUNAR_UART1_MIDI=1"]


def test_option_rejects_truthy_non_booleans():
    for value in (None, 0, 1, "true", []):
        try:
            builder.native_midi_input_configuration(value)
        except TypeError as error:
            assert "must be a bool" in str(error)
        else:
            raise AssertionError(f"accepted non-bool {value!r}")
        try:
            builder.native_midi_input_flags(value)
        except TypeError:
            pass
        else:
            raise AssertionError(f"flag helper accepted non-bool {value!r}")


def test_trio_pulse_is_explicit_and_restricted_to_empty_trio_diagnostic():
    disabled = builder.trio_diagnostic_pulse_configuration(False)
    assert disabled["enabled"] is False
    assert disabled["compile_definition"] is None
    assert builder.trio_diagnostic_pulse_flags(False) == []
    enabled = builder.validate_trio_diagnostic_pulse(
        True, "song-diagnostic", True, None, None, True, True)
    assert enabled == {
        "enabled": True,
        "compile_definition": "LUNAR_DIAGNOSTIC_TRIO_PULSE=1",
        "note": 60,
        "velocity": 100,
        "start_ms": 3000,
        "end_ms": 5000,
        "once": True,
        "hardware_tested": False,
    }
    assert builder.trio_diagnostic_pulse_flags(True) == [
        "-DLUNAR_DIAGNOSTIC_TRIO_PULSE=1"]


def test_trio_pulse_refuses_content_or_non_diagnostic_modes():
    for arguments in (
        ("continuous", True, None, None, True, True),
        ("song-diagnostic", False, None, None, True, True),
        ("song-diagnostic", True, 0, None, True, True),
        ("song-diagnostic", True, None, 0, True, True),
        ("song-diagnostic", True, None, None, False, True),
        ("song-diagnostic", True, None, None, True, False),
    ):
        try:
            builder.validate_trio_diagnostic_pulse(True, *arguments)
        except ValueError:
            pass
        else:
            raise AssertionError(f"accepted invalid pulse configuration: {arguments}")


def test_trio_pulse_configuration_rejects_non_bool():
    for value in (None, 0, 1, "yes"):
        try:
            builder.trio_diagnostic_pulse_configuration(value)
        except TypeError:
            pass
        else:
            raise AssertionError(f"accepted non-bool {value!r}")

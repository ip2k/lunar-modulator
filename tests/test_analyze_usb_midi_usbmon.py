"""Offline tests for the bounded usbmon USB-MIDI analyzer."""
import pytest

from tools.native.analyze_usb_midi_usbmon import analyze_usbmon


def row(tag, time_us, event, *, bus=1, device=53, endpoint=1, pipe="Bo", status="-115", length=4, payload=None):
    text = f"{tag} {time_us} {event} {pipe}:{bus}:{device:03d}:{endpoint} {status} {length}"
    if payload is not None:
        text += " = " + payload
    return text


def test_note_events_are_submissions_and_host_completions_are_separate():
    trace = "\n".join((
        row("abc", 100, "S", length=12, payload="09 90 3c 64 09 90 40 00 08 80 3c 00"),
        row("abc", 180, "C", status="0", length=12, payload=None),
    ))
    result = analyze_usbmon(trace, bus=1, device=53)
    assert result["schema"] == 1
    assert result["kind"] == "usb-midi-usbmon-analysis"
    assert result["counts"]["target_submissions"] == 1
    assert result["counts"]["successful_completions"] == 1
    assert result["submissions"][0]["decoded_note_events"] == [
        {"packet_index": 0, "cable": 0, "cin": 9, "kind": "note_on", "channel": 1, "note": 60, "velocity": 100},
        {"packet_index": 1, "cable": 0, "cin": 9, "kind": "note_off_zero_velocity", "channel": 1, "note": 64, "velocity": 0},
        {"packet_index": 2, "cable": 0, "cin": 8, "kind": "note_off", "channel": 1, "note": 60, "velocity": 0},
    ]
    assert "device-side USB reception" in result["evidence_boundary"]["does_not_establish"]


def test_capped_capture_is_not_confused_with_declared_transfer_length():
    payload = " ".join(["09 90 3c 64"] * 8)  # 32 captured bytes, common usbmon cap
    result = analyze_usbmon("\n".join((
        row("cap", 1, "S", length=256, payload=payload),
        row("cap", 2, "C", status="0", length=256),
    )), bus=1, device=53)
    submission = result["submissions"][0]
    assert submission["requested_bytes"] == 256
    assert submission["captured_bytes"] == 32
    assert submission["payload_truncated"] is True
    assert len(submission["decoded_note_events"]) == 8
    assert result["counts"]["successful_completions"] == 1


def test_zero_length_transfer_is_counted_without_invented_payload():
    result = analyze_usbmon("\n".join((
        row("zero", 3, "S", length=0),
        row("zero", 4, "C", status="0", length=0),
    )), bus=1, device=53)
    assert result["submissions"][0]["captured_bytes"] == 0
    assert result["submissions"][0]["decoded_note_events"] == []
    assert result["counts"]["successful_completions"] == 1


def test_failed_and_short_completions_are_not_successful():
    result = analyze_usbmon("\n".join((
        row("bad", 10, "S", length=4, payload="09 90 3c 64"),
        row("bad", 11, "C", status="-71", length=0),
        row("short", 12, "S", length=4, payload="09 90 3c 64"),
        row("short", 13, "C", status="0", length=0),
    )), bus=1, device=53)
    assert result["counts"]["target_completions"] == 2
    assert result["counts"]["zero_status_completions"] == 1
    assert result["counts"]["successful_completions"] == 0
    assert [item["successful_completion"] for item in result["completions"]] == [False, False]


def test_usbmon_submission_error_consumes_only_its_matching_pending_tag():
    result = analyze_usbmon("\n".join((
        row("err", 10, "S", length=4, payload="09 90 3c 64"),
        "err 11 E Bo:1:053:1 -28",
    )), bus=1, device=53)
    assert result["counts"]["target_submission_errors"] == 1
    assert result["counts"]["uncompleted_submissions"] == 0
    assert result["submissions"][0]["submission_error"] == {"timestamp_us": 11, "status": -28}
    assert result["counts"]["successful_completions"] == 0


def test_unmatched_completion_and_uncompleted_submission_are_reported():
    result = analyze_usbmon("\n".join((
        row("orphan", 1, "C", status="0", length=4),
        row("pending", 2, "S", length=4, payload="09 90 3c 64"),
    )), bus=1, device=53)
    assert result["counts"]["unmatched_completions"] == 1
    assert result["counts"]["uncompleted_submissions"] == 1
    assert {item["code"] for item in result["diagnostics"]} >= {
        "unmatched_completion", "uncompleted_submission"
    }


def test_duplicate_outstanding_tag_is_anomaly_but_reuse_after_completion_is_valid():
    duplicate = analyze_usbmon("\n".join((
        row("reuse", 1, "S", payload="09 90 3c 64"),
        row("reuse", 2, "S", payload="09 90 3d 64"),
        row("reuse", 3, "C", status="0", length=4),
        row("reuse", 4, "C", status="0", length=4),
    )), bus=1, device=53)
    assert duplicate["counts"]["duplicate_outstanding_tags"] == 1
    assert duplicate["counts"]["unmatched_completions"] == 1

    reused = analyze_usbmon("\n".join((
        row("reuse", 1, "S", payload="09 90 3c 64"),
        row("reuse", 2, "C", status="0", length=4),
        row("reuse", 3, "S", payload="09 90 3d 64"),
        row("reuse", 4, "C", status="0", length=4),
    )), bus=1, device=53)
    assert reused["counts"]["duplicate_outstanding_tags"] == 0
    assert reused["counts"]["successful_completions"] == 2


def test_exact_bus_device_and_bulk_out_endpoint_one_filtering():
    result = analyze_usbmon("\n".join((
        row("want", 1, "S", payload="09 90 3c 64"),
        row("other-device", 2, "S", device=54, payload="09 90 3d 64"),
        row("other-bus", 3, "S", bus=2, payload="09 90 3e 64"),
        row("other-endpoint", 4, "S", endpoint=2, payload="09 90 3f 64"),
        row("input", 5, "S", pipe="Bi", payload="09 90 40 64"),
    )), bus=1, device=53)
    assert [item["tag"] for item in result["submissions"]] == ["want"]
    assert result["counts"]["filtered_rows"] == 4


@pytest.mark.parametrize("bad", [
    "broken",
    "tag 1 S Bo:1:053:1 -115 four = 09 90 3c 64",
    "tag 1 S Bo:1:053:1 -115 4 = 09 9x 3c 64",
    "tag 1 S Bo:1:053:1 -115 3 = 09 90 3c 64",
])
def test_malformed_rows_and_payloads_are_reported_without_silent_decode(bad):
    result = analyze_usbmon(bad, bus=1, device=53)
    assert result["counts"]["malformed_rows"] == 1
    assert result["diagnostics"]


def test_partial_usb_midi_event_and_bad_cin_are_diagnostic():
    partial = analyze_usbmon(row("p", 1, "S", length=3, payload="09 90 3c"), bus=1, device=53)
    assert partial["submissions"][0]["decoded_note_events"] == []
    assert partial["counts"]["malformed_rows"] == 0
    assert partial["diagnostics"][0]["code"] == "malformed_midi_packet"

    bad_cin = analyze_usbmon(row("c", 1, "S", payload="08 90 3c 64"), bus=1, device=53)
    assert bad_cin["submissions"][0]["decoded_note_events"] == []
    assert bad_cin["diagnostics"][0]["code"] == "malformed_midi_packet"


def test_invalid_addressing_input_type_and_capture_limits_refuse():
    with pytest.raises(ValueError, match="integer"):
        analyze_usbmon("", bus=True, device=53)
    with pytest.raises(ValueError, match="ASCII"):
        analyze_usbmon(b"\xff", bus=1, device=53)
    with pytest.raises(ValueError, match="exceeds"):
        analyze_usbmon(b" " * (16 * 1024 * 1024 + 1), bus=1, device=53)
    with pytest.raises(ValueError, match="rows"):
        analyze_usbmon("\n".join(["\n"] * 200_001), bus=1, device=53)


@pytest.mark.parametrize("payload", ["09 90 80 40", "09 90 3c ff", "08 80 ff 00"])
def test_note_data_must_be_seven_bit_even_when_usb_transfer_completes(payload):
    result = analyze_usbmon("\n".join((
        row("invalid-midi", 1, "S", payload=payload),
        row("invalid-midi", 2, "C", status="0", length=4),
    )), bus=1, device=53)
    assert result["counts"]["successful_completions"] == 1
    assert result["submissions"][0]["decoded_note_events"] == []
    assert result["diagnostics"][0]["code"] == "malformed_midi_packet"

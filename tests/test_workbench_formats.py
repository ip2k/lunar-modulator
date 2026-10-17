"""Independent DX7 vectors and refusal checks for the offline Workbench adapter."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import lunar_state
from tools.workbench import formats

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "workbench" / "formats.py"
C_STATE = ROOT / "engines" / "build" / "fm1-state"
META = ROOT / "sim" / "web" / "www" / "meta.json"


def _checksum(data):
    return (-sum(data)) & 0x7F


def _voice_vced():
    """Build a small musical VCED voice directly from documented field order."""
    out = bytearray(155)
    for op in range(6):
        at = op * 21
        out[at:at + 8] = bytes((92 - op, 84, 63, 18, 99, 78, 54, 0))
        out[at + 8:at + 16] = bytes((39, 12, 22, 1, 2, 3, 1, 4))
        out[at + 16:at + 21] = bytes((67 - op * 4, 0, 2 + op % 3, 25 + op, 7))
    out[126:134] = bytes((99, 88, 77, 44, 99, 70, 48, 18))
    out[134:145] = bytes((17, 5, 1, 38, 7, 32, 19, 1, 4, 3, 24))
    out[145:155] = b"TEST VOICE"
    return bytes(out)


def _single_syx(voice=None, channel=0):
    voice = _voice_vced() if voice is None else voice
    return bytes((0xF0, 0x43, channel, 0, 1, 27)) + voice + bytes((_checksum(voice), 0xF7))


def _bank_voice(number):
    """Write 128 VMEM bytes directly; no production packer is used."""
    out = bytearray(128)
    for op in range(6):
        at = 17 * op
        out[at:at + 11] = bytes((95 - op, 82, 67, 21, 99, 84, 60, 0, 39, 12, 22))
        out[at + 11] = (2 << 2) | 1
        out[at + 12] = (7 << 3) | 3
        out[at + 13] = (5 << 2) | 2
        out[at + 14] = 64 - op * 5
        out[at + 15] = 4 + (op % 3) * 2
        out[at + 16] = 17 + op
    out[102:110] = bytes((99, 88, 77, 44, 99, 70, 48, 18))
    out[110] = 17 + number % 15
    out[111] = 5 | (1 << 3)
    out[112:116] = bytes((38, 7, 32, 19))
    out[116] = (3 << 4) | (4 << 1) | 1
    out[117] = 24
    out[118:128] = f"V{number:03d} PATCH".ljust(10).encode("ascii")
    return bytes(out)


def _bank_syx(channel=0):
    payload = b"".join(_bank_voice(i) for i in range(32))
    return bytes((0xF0, 0x43, channel, 9, 32, 0)) + payload + bytes((_checksum(payload), 0xF7))


def _read_lunar(data):
    names = lunar_state.Names.from_file(META)
    records, report = lunar_state.read_any(data, names)
    assert not (report.skipped or report.repaired or report.unknown)
    return json.loads(lunar_state.write_json(records, names)[0])


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_single_voice_round_trips_all_vced_bytes_and_is_a_lunar_sound():
    source = _single_syx(channel=3)
    imported, report = formats.import_syx(source)
    doc = _read_lunar(imported)
    assert doc["kind"] == "sound"
    assert doc["sound"]["engine"] == "dx7"
    assert [row["slot"] for row in doc["dx7"]] == [1]
    assert report["voice_count"] == 1
    assert report["source_channel"] == 3
    assert report["losses"] == []

    exported, export_report = formats.export_syx(imported, channel=11)
    assert exported == _single_syx(_voice_vced(), channel=11)
    assert export_report["target_channel"] == 11
    assert export_report["losses"] == []


def test_32_voice_bank_round_trips_musical_voice_data_deterministically():
    source = _bank_syx(channel=6)
    imported, report = formats.import_syx(source)
    doc = _read_lunar(imported)
    assert doc["kind"] == "sound"
    assert doc["sound"]["engine"] == "dx7"
    assert [row["slot"] for row in doc["dx7"]] == list(range(1, 33))
    assert [row["name"] for row in doc["dx7"][:3]] == [
        "V000 PATCH", "V001 PATCH", "V002 PATCH"
    ]
    assert doc["dx7"][0]["ops"][0][:8] == [95, 82, 67, 21, 99, 84, 60, 0]
    assert doc["dx7"][0]["ops"][0][16] == 64
    assert doc["dx7"][0]["globals"][0] == 99
    assert report["voice_count"] == 32
    assert report["source_channel"] == 6
    assert report["losses"] == []

    expected = _bank_syx(channel=9)
    first, report1 = formats.export_syx(imported, channel=9)
    second, report2 = formats.export_syx(imported, channel=9)
    assert first == expected
    assert second == first
    assert report1 == report2
    assert report1["losses"] == []


@pytest.mark.parametrize(
    "source,code",
    [
        (_single_syx()[:-1], "SYX_SIZE"),
        (_single_syx()[:-2] + bytes([_single_syx()[-2] ^ 1]) + b"\xF7", "CHECKSUM"),
        (_single_syx()[:6] + b"\x80" + _single_syx()[7:], "SYX_FRAME"),
        (_single_syx()[:2] + b"\x10" + _single_syx()[3:], "SYX_FRAME"),
        (_single_syx() + _single_syx(), "SYX_SIZE"),
    ],
    ids=["truncated", "checksum", "over-seven-bit", "channel-range", "wrong-voice-count"],
)
def test_import_rejects_malformed_or_unsupported_sysex(source, code):
    with pytest.raises(formats.ConversionError) as caught:
        formats.import_syx(source)
    assert caught.value.code == code


def test_export_rejects_noncontiguous_slots_and_partial_bank():
    imported, _ = formats.import_syx(_bank_syx())
    doc = json.loads(imported)
    doc["dx7"][1]["slot"] = 3
    malformed_slots = json.dumps(doc, separators=(",", ":")).encode()
    with pytest.raises(formats.ConversionError) as caught:
        formats.export_syx(malformed_slots)
    assert caught.value.code in {"VOICE_SLOTS", "LUNAR_BAD"}

    partial, _ = formats.import_syx(_bank_syx())
    doc = json.loads(partial)
    doc["dx7"] = doc["dx7"][:2]
    doc["dx7"][1]["slot"] = 2
    partial_state = json.dumps(doc, separators=(",", ":")).encode()
    with pytest.raises(formats.ConversionError) as caught:
        formats.export_syx(partial_state)
    assert caught.value.code == "VOICE_COUNT"


def test_export_reports_losses_and_requires_explicit_opt_in():
    imported, _ = formats.import_syx(_single_syx())
    doc = json.loads(imported)
    doc["sound"]["level"] = 40
    changed = json.dumps(doc, separators=(",", ":")).encode()

    with pytest.raises(formats.ConversionError) as caught:
        formats.export_syx(changed)
    error = caught.value
    assert error.code == "LOSS_REQUIRES_OPT_IN"
    assert any(loss["field"] == "sound.level" for loss in error.report["losses"])

    output, report = formats.export_syx(changed, allow_loss=True)
    assert output == _single_syx()
    assert any(loss["field"] == "sound.level" for loss in report["losses"])


def test_canonical_sound_bytes_are_accepted_by_python_and_c_state_parsers(tmp_path):
    imported, _ = formats.import_syx(_single_syx())
    python_doc = _read_lunar(imported)
    assert python_doc["kind"] == "sound"
    assert C_STATE.exists(), "build the focused fm1-state parser before this acceptance check"
    parsed = subprocess.run(
        [str(C_STATE), "records", "-"],
        input=imported,
        capture_output=True,
        check=False,
    )
    assert parsed.returncode == 0, parsed.stderr.decode(errors="replace")
    assert parsed.stdout


def test_reserved_dx7bank_kind_is_not_used_for_imported_voice_data():
    imported, _ = formats.import_syx(_bank_syx())
    doc = _read_lunar(imported)
    assert doc["kind"] == "sound"
    assert doc["sound"]["engine"] == "dx7"
    assert "dx7" in doc and len(doc["dx7"]) == 32


def test_cli_validation_failure_and_path_conflicts_write_nothing(tmp_path):
    invalid = tmp_path / "invalid.syx"
    invalid.write_bytes(_single_syx()[:-1])
    output = tmp_path / "out.lunar"
    report = tmp_path / "report.json"
    result = _run_cli("import", invalid, "-o", output, "--report", report)
    assert result.returncode != 0
    assert not output.exists()
    assert not report.exists()

    source = tmp_path / "voice.syx"
    source.write_bytes(_single_syx())
    output.write_bytes(b"owner data")
    result = _run_cli("import", source, "-o", output, "--report", report)
    assert result.returncode != 0
    assert output.read_bytes() == b"owner data"
    assert not report.exists()

    same = tmp_path / "same.syx"
    same.write_bytes(_single_syx())
    result = _run_cli("import", same, "-o", same, "--report", report)
    assert result.returncode != 0
    assert same.read_bytes() == _single_syx()
    assert not report.exists()

    result = _run_cli("import", source, "-o", report, "--report", report)
    assert result.returncode != 0
    assert not report.exists()


def test_export_refuses_binary_state_that_python_writer_would_repair():
    imported, _ = formats.import_syx(_single_syx())
    names = lunar_state.Names.from_file(META)
    records, _ = lunar_state.read_json(imported, names)
    patch = next(
        row for row in records
        if row.get("rec") == "param" and row.get("uid") == 1 and row.get("index") == 32
    )
    del patch["index"]
    patch["f32"] = "42000000"
    binary = lunar_state.write_bin(records)

    parsed, read_report = lunar_state.read_any(binary, names)
    assert not read_report.skipped
    assert not read_report.repaired
    assert lunar_state.write_json(parsed, names)[1].repaired
    with pytest.raises(formats.ConversionError) as caught:
        formats.export_syx(binary)
    assert caught.value.code == "LUNAR_REPAIR"


def test_dx7bank_is_reserved_and_not_a_lunar_json_kind():
    reserved = json.dumps({"lunar": "1.0", "kind": "dx7bank"}).encode()
    names = lunar_state.Names.from_file(META)
    with pytest.raises(lunar_state.Refused):
        lunar_state.read_json(reserved, names)

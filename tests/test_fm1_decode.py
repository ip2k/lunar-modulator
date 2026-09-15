"""Synthetic instruction vectors and analysis provenance/bounds regressions.

No vendor application, function listing, or private path is a test dependency.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tools import fm1_decode as decode


@pytest.mark.parametrize("word,width", [(0, 2), (0xD625, 2), (0xE040, 4), (0xFEFF, 4), (0xFF00, 6), (0xFFFF, 6)])
def test_instruction_width(word, width):
    assert decode.instruction_size(word) == width


@pytest.mark.parametrize("raw,pc,name,target", [
    ("80ff10000000", 0x2000120, "call", 0x2000136),
    ("80ff11000000", 0x2000120, "gotoss", 0x2000136),
    ("80fff0ffffff", 0x1C01200, "call", 0x1C011F6),
    ("4183", 0x1F0, "call", 0xF8),
    ("80ea0100", 0x2000, "call", 0x2006),
    ("bfeaffff", 0x2000, "call", 0x2002),
    ("0401", 0x2000, "tbb", None),
])
def test_relative_and_indirect_control_flow(raw, pc, name, target):
    item = decode.decode_instruction(bytes.fromhex(raw), 0, pc)
    assert item["mnemonic"] == name
    assert item.get("target") == target


def test_relative_address_is_not_guessed_for_unknown_mapping():
    item = decode.decode_instruction(bytes.fromhex("80ff10000000"), 0)
    assert item["target"] is None
    assert item["displacement"] == 16


@pytest.mark.parametrize("raw,name,register,source", [
    ("5019", "or", "r0", "r5"),
    ("5919", "xor", "r1", "r5"),
    ("a319", "and", "r3", "r2"),
    ("9919", "not", "r1", "r1"),
    ("25d6", "mov", "r5", "r2"),
    ("ff17", "sxth", "r7", "r7"),
    ("8017", "uxth", "r0", "r0"),
])
def test_register_operators_include_corrected_reference_defects(raw, name, register, source):
    item = decode.decode_instruction(bytes.fromhex(raw), 0)
    assert (item["mnemonic"], item["register"], item["source_register"]) == (name, register, source)


@pytest.mark.parametrize("raw,register,value", [
    ("c1ff78563412", "r1", 0x12345678),
    ("eeff78563412", "sp", 0x12345678),
    ("47f0ff3f", "r7", 16383),
    ("4ee00080", "r14", -32768),
    ("102a", "r0", -22),
    ("1520", "r5", -32),
])
def test_constant_decoding(raw, register, value):
    item = decode.decode_instruction(bytes.fromhex(raw), 0)
    assert item["mnemonic"] == "mov"
    assert (item["register"], item["immediate"]) == (register, value)


@pytest.mark.parametrize("raw,name,register,base,offset,update", [
    ("d2ec2825", "lw", "r2", "r2", 600, None),
    ("d0ec2650", "lw", "r5", "r2", 4, "pre"),
    ("d0ec9100", "sw", "r0", "r9", 0, None),
    ("51ee1c0f", "lbu", "r0", "r1", -4, None),
    ("0521", "lw", "r5", "sp", 4, None),
    ("8560", "sw", "r5", "r0", 0, None),
])
def test_memory_field_decoding(raw, name, register, base, offset, update):
    item = decode.decode_instruction(bytes.fromhex(raw), 0)
    assert item["mnemonic"] == name
    assert item["register"] == register
    assert (item["memory"]["base"], item["memory"]["offset"], item["memory"]["update"]) == (base, offset, update)


def test_indexed_table_load_has_dynamic_offset():
    item = decode.decode_instruction(bytes.fromhex("d8ed9800"), 0)
    assert item["mnemonic"] == "lhu"
    assert item["memory"] == {"base": "r9", "offset": None, "index": "r0", "index_shift": 1,
                              "width": 2, "access": "read", "update": None}


def test_bit_instruction_is_not_misreported_as_stack_access():
    assert not decode.decode_instruction(bytes.fromhex("3022"), 0)["supported"]
    assert not decode.decode_instruction(bytes.fromhex("b827"), 0)["supported"]


def test_stack_register_range_including_low_registers():
    assert decode.decode_instruction(bytes.fromhex("7f04"), 0)["registers"] == ["rets"] + [f"r{i}" for i in range(15, 3, -1)]
    assert decode.decode_instruction(bytes.fromhex("6004"), 0)["registers"] == ["r3", "r2", "r1", "r0"]


def test_parallel_packet_is_explicit_even_for_unsupported_arithmetic():
    listing = decode.disassemble(bytes.fromhex("a0f0806c1464"), 0, 6)
    assert listing["instructions"][0]["parallel_pair"]
    assert listing["instructions"][0]["supported"] is False
    assert listing["instructions"][1]["parallel_companion"]
    assert listing["instructions"][1]["packet_file_offset"] == 0


def test_truncated_and_unsupported_instructions_preserve_all_bytes():
    blob = bytes.fromhex("00ff0102030480ff12")
    report = decode.disassemble(blob, 0, len(blob))
    assert "".join(i["bytes"] for i in report["instructions"]) == blob.hex()
    assert [i["size"] for i in report["instructions"]] == [6, 3]
    assert report["unsupported_bytes"] == len(blob)
    assert report["instructions"][-1]["expected_size"] == 6


def test_disassembly_stops_at_requested_boundary():
    blob = bytes.fromhex("c1ff785634128000")
    report = decode.disassemble(blob, 0, 5)
    assert report["instructions"][0]["size"] == 5
    assert report["instructions"][0]["supported"] is False
    assert report["unsupported_bytes"] == 5


@pytest.mark.parametrize("start,size", [(-1, 2), (8, 1), (0, 9), (0, 0), ("0", 2)])
def test_invalid_disassembly_ranges(start, size):
    with pytest.raises(decode.DecodeError):
        decode.disassemble(b"12345678", start, size)


def test_disassembly_limit_applies_to_bytes_not_image_size():
    blob = b"\0" * 100000
    with pytest.raises(decode.DecodeError):
        decode.disassemble(blob, 0, 65537)
    assert decode.disassemble(blob, 99996, 4)["size"] == 4


def test_unrecognized_image_identity_does_not_grant_runtime_addresses():
    report = decode.analyze_application(b"FM-1_015\0audio_server\0untrusted synthetic application\0")
    assert report["identities"] == ["FM-1_015"]
    assert not report["profile"]["matched"]
    assert report["functions"] == []
    assert report["calls"] == []
    assert all(i["address"] is None for i in report["strings"])
    assert report["device_io_performed"] is False
    assert json.loads(json.dumps(report))["kind"] == "fm1-executable-analysis"


def test_long_printable_runs_without_nul_are_skipped_linearly():
    # This input previously caused regex backtracking at every byte boundary.
    # No timing assertion is required: the fixture exercises the linear scan.
    report = decode.analyze_application(b"A" * 100000)
    assert report["strings"] == []
    assert not report["strings_truncated"]


def test_long_run_with_nul_is_not_reclassified_by_its_short_suffix():
    report = decode.analyze_application(b"A" * 1000 + b"\0audio_server\0")
    assert [r["text"] for r in report["strings"]] == ["audio_server"]


def test_string_count_is_explicitly_bounded():
    blob = b"sample_name\0" * (decode.MAX_STRINGS + 1)
    report = decode.analyze_application(blob)
    assert len(report["strings"]) == decode.MAX_STRINGS
    assert report["strings_truncated"]


def test_stale_analysis_cannot_claim_a_verified_instruction_boundary():
    report = decode.disassemble(b"\0\0", 0, 2, analysis={"sha256": "unrelated", "functions": [{"file_offset": 0}]})
    assert report["boundary_verified"] is False


def test_runtime_translation_excludes_unbacked_bss():
    analysis = {"regions": [{"file_offset": 12, "runtime_address": 0x1C00000, "size": 16},
                             {"file_offset": None, "runtime_address": 0x1C00010, "size": 16}]}
    assert decode.address_to_offset(0x1C00000, analysis) == 12
    assert decode.address_to_offset(0x1C0000F, analysis) == 27
    assert decode.address_to_offset(0x1C00010, analysis) is None


def test_cli_cannot_overwrite_source_application(tmp_path):
    source = tmp_path / "app.bin"
    data = b"synthetic firmware\0"
    source.write_bytes(data)
    result = subprocess.run([sys.executable, "-m", "tools.fm1_decode", str(source), "--output", str(source)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "must not overwrite" in result.stderr
    assert source.read_bytes() == data


@pytest.mark.skipif(not os.environ.get("FM1_V15_APPLICATION"), reason="optional private V15 application not configured")
def test_private_v15_map_and_core_boundaries():
    blob = Path(os.environ["FM1_V15_APPLICATION"]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() == decode.V15_SHA256
    report = decode.analyze_application(blob)
    assert report["profile"]["exact_image"]
    ram = next(r for r in report["regions"] if r["name"] == "RAM initialization image")
    assert (ram["file_offset"], ram["runtime_address"], ram["size"]) == (0x83F40, 0x1C00000, 0xA05C)
    assert report["dsp"]["algorithm_tables"][0]["address"] == 0x1C07F4C
    table_names = {t["name"] for t in report["dsp"]["mathematical_tables"]["tables"]}
    assert {"fractional_exponent", "quarter_wave_log_sine"} <= table_names
    note = next(f for f in report["functions"] if f["name"] == "dx7note_compute_block_candidate")
    listing = decode.disassemble(blob, note["file_offset"], note["size"], analysis=report)
    assert listing["boundary_verified"]
    assert listing["data_bytes"] == 10
    assert len([i for i in listing["instructions"] if i.get("is_data")]) == 2
    assert all(c["source_file_offset"] not in (0x85BB4, 0x85BB6, 0x85BB8, 0x860D6, 0x860D8) for c in report["calls"])
    assert next(f for f in report["functions"] if f["category"] == "effects")["size"] == 656
    # Edits retain only evidence whose underlying bytes are unchanged.
    altered = bytearray(blob)
    altered[0x85064] ^= 1
    changed = decode.analyze_application(bytes(altered))
    assert changed["profile"]["matched"] and not changed["profile"]["exact_image"]
    assert not any(f["name"] == "fm_operator_kernel_candidate" for f in changed["functions"])
    altered[0x2A054] ^= 1
    assert not decode.analyze_application(bytes(altered))["profile"]["matched"]

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
    listing = decode.disassemble(bytes.fromhex("c4f100001464"), 0, 6)
    assert listing["instructions"][0]["parallel_pair"]
    assert listing["instructions"][0]["supported"] is False
    assert listing["instructions"][1]["parallel_companion"]
    assert listing["instructions"][1]["packet_file_offset"] == 0


@pytest.mark.parametrize("encoded,value", [(0x0AB, 0xAB), (0x1AB, 0x00AB00AB),
    (0x2AB, 0xAB00AB00), (0x3AB, 0xABABABAB), (0x400, 0x80000000),
    (0xC80, 0x4000), (0xC7C, 0xFC00), (0xAE0, 0x70000), (0xFFF, 0x1FE)])
def test_compact_immediate_expansion(encoded, value):
    assert decode.compact_immediate(encoded) == value


@pytest.mark.parametrize("raw,name,destination,source,immediate", [
    ("a0f0806c", "reverse_sub", "r0", "r6", 16384),
    ("a0e080dc", "reverse_sub", "r0", "r13", 16384),
    ("ede07cec", "add", "r13", "r14", 0xFC00),
    ("c0f15edc", "asr", "r13", "r5", 14),
    ("c0f10df0", "lsl", "r15", "r0", 13),
    ("40e1e05a", "or", "r0", "r5", 0x70000),
])
def test_operator_arithmetic_forms(raw, name, destination, source, immediate):
    item = decode.decode_instruction(bytes.fromhex(raw), 0)
    assert (item["mnemonic"], item["register"], item["source_register"], item["immediate"]) == (name, destination, source, immediate)


def test_full_register_add_and_shift_sources():
    item = decode.decode_instruction(bytes.fromhex("b4f0005a"), 0)
    assert (item["register"], item["source_registers"]) == ("r5", ["r0", "r10"])
    item = decode.decode_instruction(bytes.fromhex("c8e10255"), 0)
    assert (item["mnemonic"], item["register"], item["source_register"], item["shift_register"]) == ("lsr", "r5", "r0", "r5")
    item = decode.decode_instruction(bytes.fromhex("d81a"), 0)
    assert (item["mnemonic"], item["register"], item["source_register"], item["shift_register"]) == ("asr", "r0", "r0", "r5")


@pytest.mark.parametrize("raw,destination,source,position,length,signed", [
    ("b5e11475", "r5", "r7", 10, 5, False),
    ("b0e11475", "r0", "r7", 10, 5, False),
    ("b5f10812", "r5", "r1", 4, 2, False),
    ("b5e18550", "r5", "r5", 1, 1, True),
])
def test_bit_field_extraction(raw, destination, source, position, length, signed):
    item = decode.decode_instruction(bytes.fromhex(raw), 0)
    assert item["mnemonic"] == ("sextra" if signed else "uextra")
    assert (item["register"], item["source_register"], item["position"], item["length"]) == (destination, source, position, length)


@pytest.mark.parametrize("raw,register,comparison,immediate,displacement", [
    ("20ff007e1400", "r7", "==", 2048, 40),
    ("00ff00740800", "r7", "==", 1024, 16),
    ("01ff0310ea01", "r1", "!=", 3, 980),
    ("83f83a81", "r3", "!=", 64, -396),
    ("01f8c73e", "r1", "==", 31, 398),
    ("71f8f9ff", "r1", "==", -1, -14),
])
def test_conditional_branch_operands_and_targets(raw, register, comparison, immediate, displacement):
    item = decode.decode_instruction(bytes.fromhex(raw), 0, 0x1C01000)
    assert item["mnemonic"] == "branch_if"
    assert item["condition"]["register"] == register
    assert item["condition"]["comparison"] == comparison
    assert item["condition"]["immediate"] == immediate
    assert item["displacement"] == displacement
    assert item["target"] == 0x1C01000 + item["size"] + displacement


def test_predicate_scope_is_explicit_and_unverified_modes_stay_unknown():
    item = decode.decode_instruction(bytes.fromhex("b9e80000"), 0)
    assert item["predicate"] == {"register": "r9", "comparison": "!=", "immediate": 0, "signed": False, "instruction_count": 1}
    item = decode.decode_instruction(bytes.fromhex("37ed0000"), 0)
    assert item["predicate"]["comparison"] == ">=" and item["predicate"]["signed"]
    assert not decode.decode_instruction(bytes.fromhex("b0e80010"), 0)["supported"]


def test_postincrement_store_preserves_old_address_then_updates_base():
    item = decode.decode_instruction(bytes.fromhex("d8ec05b0"), 0)
    assert item["register"] == "r11"
    assert item["memory"] == {"base": "r0", "offset": 0, "width": 4, "access": "write", "update": "post +4"}


def test_control_flow_loop_is_finite_and_branches_preserve_boundaries():
    graph = decode.analyze_control_flow(bytes.fromhex("4121f79f"), 0, 4)
    assert [n["file_offset"] for n in graph["nodes"]] == [0, 2]
    assert graph["edges"][-1]["target_file_offset"] == 2
    assert graph["barriers"] == []


def test_control_flow_stops_at_unknown_semantics():
    graph = decode.analyze_control_flow(bytes.fromhex("c4e100004121"), 0, 6)
    assert len(graph["nodes"]) == 1
    assert graph["edges"] == []
    assert "unsupported" in graph["barriers"][0]["reason"]


def test_control_flow_single_predicate_has_two_paths():
    graph = decode.analyze_control_flow(bytes.fromhex("b9e8000090168000"), 0, 8)
    first = [e for e in graph["edges"] if e["source_file_offset"] == 0]
    assert {e["target_file_offset"] for e in first} == {4, 6}
    assert graph["barriers"] == []


def test_control_flow_rejects_target_inside_an_instruction():
    blob = bytes.fromhex("80ff05000000c1ff78563412")
    graph = decode.analyze_control_flow(blob, 0, len(blob))
    assert len(graph["nodes"]) == 1
    assert graph["barriers"][0]["target_file_offset"] == 10


def test_control_flow_does_not_guess_predicate_scope_over_parallel_packet():
    blob = bytes.fromhex("b9e8000025d600208000")
    graph = decode.analyze_control_flow(blob, 0, len(blob))
    assert len(graph["nodes"]) == 1
    assert "predicate scope" in graph["barriers"][0]["reason"]


def test_truncated_and_unsupported_instructions_preserve_all_bytes():
    blob = bytes.fromhex("7fff0102030480ff12")
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
    effects = report["dsp"]["effects"]
    assert effects["profile"]["matched"]
    assert len(effects["effects"]) == 6
    assert sum(len(effect["callbacks"]) for effect in effects["effects"]) == 18
    note = next(f for f in report["functions"] if f["name"] == "dx7note_compute_block_candidate")
    listing = decode.disassemble(blob, note["file_offset"], note["size"], analysis=report)
    assert listing["boundary_verified"]
    assert listing["data_bytes"] == 10
    assert len([i for i in listing["instructions"] if i.get("is_data")]) == 2
    assert all(c["source_file_offset"] not in (0x85BB4, 0x85BB6, 0x85BB8, 0x860D6, 0x860D8) for c in report["calls"])
    assert next(f for f in report["functions"] if f["category"] == "effects")["size"] == 656
    kernel = next(f for f in report["functions"] if f["name"] == "fm_operator_kernel_candidate")
    assert kernel["supported_bytes"] == kernel["size"] == 544
    assert kernel["control_flow"]["barriers"] == []
    forged = {"sha256": report["sha256"], "functions": [{"file_offset": 0x85066}]}
    assert not decode.disassemble(blob, 0x85066, 2, analysis=forged)["boundary_verified"]
    # Edits retain only evidence whose underlying bytes are unchanged.
    altered = bytearray(blob)
    altered[0x85064] ^= 1
    changed = decode.analyze_application(bytes(altered))
    assert changed["profile"]["matched"] and not changed["profile"]["exact_image"]
    assert not changed["dsp"]["effects"]["profile"]["matched"]
    assert changed["dsp"]["effects"]["effects"] == []
    assert not any(f["name"] == "fm_operator_kernel_candidate" for f in changed["functions"])
    altered[0x2A054] ^= 1
    assert not decode.analyze_application(bytes(altered))["profile"]["matched"]

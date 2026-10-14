# SPDX-License-Identifier: MIT
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/native"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/jieli"))
from inspect_fwsc import crc16
from tail_migration_plan import (FLASH_BYTES, SLOT_SECTORS, TAIL_RECORD_OFFSET,
                                 analyze_first_format, sha256)


def image():
    return b"\xff" * FLASH_BYTES


def make_outer_record(word2):
    record = bytearray(80)
    record[2:4] = word2.to_bytes(2, "little")
    record[6:8] = (0x5441).to_bytes(2, "little")
    for value in range(256):
        record[4] = value
        checksum = crc16(record[2:80])
        if checksum:
            record[0:2] = checksum.to_bytes(2, "little")
            return bytes(record)
    raise AssertionError("test vector unexpectedly has no nonzero CRC")


def test_erased_pages_satisfy_record_precondition_but_withhold_sequence():
    raw = image()
    plan = analyze_first_format(raw, raw, sha256(raw), "FM-1_500", "FM-1_500")
    assert plan["map_sector_count"] == 24
    assert len(plan["record_scan_candidates"]) == 24
    assert plan["hazards"] == []
    assert plan["status"] == "record_page_precondition_satisfied_under_model"
    assert plan["erase_sequence"] == []
    assert plan["erase_sequence_withheld"] is True
    assert plan["record_windows_pre_erased"]
    assert all(not row["spl_outer_record"] and not row["cleanup_record"]
               for row in plan["record_scan_candidates"])
    assert plan["semantic_migration_verified"] is False
    assert plan["physical_rollback_verified"] is False
    assert plan["hardware_admitted"] is False
    assert plan["physical_writer_ready"] is False
    assert plan["hardware_operations"] == 0


def test_non_erased_invalid_page_refuses_record_precondition():
    raw = bytearray(image())
    sector = SLOT_SECTORS["A"][0]
    raw[sector + TAIL_RECORD_OFFSET + 100] = 0
    snapshot = bytes(raw)
    plan = analyze_first_format(snapshot, snapshot, sha256(snapshot), "FM-1_500", "FM-1_500")
    assert plan["status"] == "record_page_precondition_refused"
    assert plan["erase_sequence"] == []
    assert plan["erase_sequence_withheld"] is True
    assert plan["record_windows_pre_erased"] is False
    hazard = plan["hazards"][0]
    assert hazard["candidate_offset"] == sector + TAIL_RECORD_OFFSET
    assert hazard["page_is_erased"] is False
    assert hazard["spl_outer_record"] is False
    assert hazard["cleanup_record"] is False
    assert "opaque_tail_page_not_erased" in hazard["hazards"]


@pytest.mark.parametrize("word2,expected_spl", [(0, False), (1, True)])
def test_currently_matching_record_predicates_are_reported(word2, expected_spl):
    raw = bytearray(image())
    sector = SLOT_SECTORS["B"][0]
    record = make_outer_record(word2)
    raw[sector + TAIL_RECORD_OFFSET:sector + TAIL_RECORD_OFFSET + 80] = record
    snapshot = bytes(raw)
    plan = analyze_first_format(snapshot, snapshot, sha256(snapshot), "FM-1_092", "FM-1_092")
    hazard = next(item for item in plan["hazards"] if item["sector_offset"] == sector)
    assert hazard["cleanup_record"] is True
    assert hazard["spl_outer_record"] is expected_spl
    assert plan["erase_sequence"] == []


@pytest.mark.parametrize("case", ["missing-b", "different-pair", "wrong-hash", "short", "identity"])
def test_missing_or_mismatched_baseline_evidence_rejects(case):
    a = image()
    b = a
    digest = sha256(a)
    target = expected = "FM-1_500"
    if case == "missing-b":
        b = None
    elif case == "different-pair":
        b = b[:-1] + b"\x00"
    elif case == "wrong-hash":
        digest = "0" * 64
    elif case == "short":
        a = a[:-1]
    elif case == "identity":
        expected = "FM-1_092"
    with pytest.raises(ValueError):
        analyze_first_format(a, b, digest, target, expected)


def test_planned_map_matches_the_reviewed_two_slot_sector_extents():
    assert SLOT_SECTORS["A"] == (
        tuple(range(0xD9000, 0xE0000, 0x1000))
        + tuple(range(0xE5000, 0xE9000, 0x1000))
        + (0xEA000,)
    )
    assert SLOT_SECTORS["B"] == tuple(range(0xEB000, 0xF7000, 0x1000))
    assert len(set(SLOT_SECTORS["A"]) | set(SLOT_SECTORS["B"])) == 24
    assert all((sector % 0x1000) == 0 and sector + 0x1000 <= FLASH_BYTES
               for sectors in SLOT_SECTORS.values() for sector in sectors)

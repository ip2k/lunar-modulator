# SPDX-License-Identifier: MIT
"""Offline first-format analysis for the proposed FM-1 storage48 tail map.

This module never reads or writes a device and never returns an erase sequence.
Its record-page result depends on the stated monotonic-NOR erase model; it is
not a write authorization or physical erase proof.
"""
import hashlib
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jieli"))
from inspect_fwsc import crc16

FLASH_BYTES = 0x100000
SECTOR_BYTES = 0x1000
PAGE_BYTES = 0x100
TAIL_RECORD_OFFSET = 0xF00

SLOT_SECTORS = {
    "A": tuple(range(0xD9000, 0xE0000, SECTOR_BYTES))
       + tuple(range(0xE5000, 0xE9000, SECTOR_BYTES))
       + (0xEA000,),
    "B": tuple(range(0xEB000, 0xF7000, SECTOR_BYTES)),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def _hex_digest(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Explicit lowercase SHA-256 pin required")
    return value


def _u16(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def _record_predicates(page):
    """Evaluate retained outer SPL and cleanup predicates on page[0:80]."""
    record = page[:80]
    if len(record) != 80:
        raise ValueError("Complete 80-byte stock record window required")
    signature = _u16(record, 6) == 0x5441
    outer_crc = _u16(record, 0)
    crc_matches = outer_crc == crc16(record[2:80])
    cleanup = signature and outer_crc != 0 and crc_matches
    spl = cleanup and _u16(record, 2) != 0
    return spl, cleanup


def analyze_first_format(snapshot_a, snapshot_b, snapshot_sha256,
                         target_identity, expected_target_identity):
    """Return per-sector hazards and record-page precondition status.

    Identical, complete snapshots and explicit identity assertion are required.
    Every mapped sector's entire final 256-byte page must already be erased.
    Any non-erased page refuses the record-page precondition, even when its
    current bytes fail both record predicates: interrupted erase may change it.
    This analyzer always withholds destructive sequencing because other gates
    (migration, rollback, recovery) are not validated here.
    """
    expected = _hex_digest(snapshot_sha256)
    if not isinstance(snapshot_a, bytes) or not isinstance(snapshot_b, bytes):
        raise ValueError("Two complete immutable snapshot byte strings required")
    if len(snapshot_a) != FLASH_BYTES or len(snapshot_b) != FLASH_BYTES:
        raise ValueError("Two complete 1 MiB snapshots required")
    if snapshot_a != snapshot_b or sha256(snapshot_a) != expected:
        raise ValueError("Matching snapshots bound to explicit full-image SHA-256 required")
    if (not isinstance(target_identity, str) or not target_identity.strip()
            or not isinstance(expected_target_identity, str)
            or target_identity != expected_target_identity):
        raise ValueError("Explicit matching current-target identity assertion required")

    hazards = []
    candidates = []
    for slot, sectors in SLOT_SECTORS.items():
        for sector in sectors:
            candidate = sector + TAIL_RECORD_OFFSET
            page = snapshot_a[candidate:candidate + PAGE_BYTES]
            spl, cleanup = _record_predicates(page)
            erased = page == b"\xff" * PAGE_BYTES
            candidates.append(dict(slot=slot, sector_offset=sector,
                                   candidate_offset=candidate, page_is_erased=erased,
                                   spl_outer_record=spl, cleanup_record=cleanup))
            if not erased:
                reasons = ["opaque_tail_page_not_erased"]
                if spl:
                    reasons.append("currently_matches_spl_outer_record")
                if cleanup:
                    reasons.append("currently_matches_loader_cleanup_record")
                hazards.append(dict(slot=slot, sector_offset=sector,
                                    candidate_offset=candidate,
                                    candidate_bytes=80, reserved_page_bytes=PAGE_BYTES,
                                    page_sha256=sha256(page), page_is_erased=False,
                                    spl_outer_record=spl, cleanup_record=cleanup,
                                    hazards=reasons))
    refused = bool(hazards)
    return dict(
        schema=1,
        kind="fm1-storage48-first-format-analysis",
        caller_asserted_target_identity=target_identity,
        snapshot_sha256=expected,
        map_sector_count=sum(map(len, SLOT_SECTORS.values())),
        record_scan_candidates=candidates,
        hazards=hazards,
        status=("record_page_precondition_refused" if refused
                else "record_page_precondition_satisfied_under_model"),
        record_windows_pre_erased=not refused,
        erase_sequence=[],
        erase_sequence_withheld=True,
        erase_sequence_withheld_reason="migration, rollback, and recovery evidence are not validated by this analyzer",
        assumptions=["NOR erase changes bits only from 0 to 1",
                     "no programming is directed into each reserved final 256-byte page"],
        unresolved_preconditions=["current-target acquisition provenance is external to this analyzer",
                                  "stock VM/USR semantic export and migration equivalence",
                                  "retained stock reconstruction and tested restore route",
                                  "physical erase interruption behavior and exact-sector authorization"],
        semantic_migration_verified=False,
        physical_rollback_verified=False,
        hardware_admitted=False,
        physical_writer_ready=False,
        hardware_operations=0,
    )

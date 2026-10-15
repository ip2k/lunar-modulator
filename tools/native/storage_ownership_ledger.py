#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only, hash-bound inventory of proposed FM-1 storage48 sectors.

This reports byte accounting and overlap with the supplied recorded profile.
It does not establish logical ownership, data semantics, or erase permission.
In particular, an all-0xff sector remains ownership-unresolved.
"""
import argparse
import json
import re
from pathlib import Path

from tail_migration_plan import (FLASH_BYTES, SECTOR_BYTES, SLOT_SECTORS,
                                 _record_predicates, sha256)

OTA_START = 0xE0000
OTA_END = 0xE5000
PAGE_BYTES = 0x100
# Keep synchronized with tools/jieli/raw_flash_profile.py:
# APP_BASE=0x4000; CFG_TOOL_OFFSET=APP_BASE+692032.
PROFILE_CFG_TOOL_OFFSET = 0x4000 + 692032
PROFILE_PROTECTED_RANGES = ((0x00000, 0x04000),
                            (PROFILE_CFG_TOOL_OFFSET, FLASH_BYTES))
PROFILE_RESERVED = {
    "VM": [0xD9000, 0x10000, 0x12],
    "PRCT": [0, 0xD9000, 0x92],
    "BTIF": [0xE9000, 0x1000, 0x92],
    "USR": [0xEA000, 0x12000, 0x92],
    "key_mac": [0xFF000, 0x1000, 0x12],
}


def _digest(value, label):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"{label}: explicit lowercase SHA-256 required")
    return value


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _overlap(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def _validate_profile(profile):
    if (not isinstance(profile, dict) or type(profile.get("schema")) is not int
            or profile.get("schema") != 1):
        raise ValueError("Recorded FM-1_092 profile object required")
    internal = _digest(profile.get("profile_sha256"), "profile object")
    body = dict(profile)
    del body["profile_sha256"]
    if sha256(_canonical(body)) != internal:
        raise ValueError("Profile object's internal digest differs")
    if profile.get("status") != "recorded-fm1-092-raw-profile-verified-offline":
        raise ValueError("Only the recorded offline FM-1_092 profile is supported")
    if profile.get("coordinates") != "raw NOR byte offsets":
        raise ValueError("Profile coordinates are not raw flash offsets")
    _digest(profile.get("baseline_sha256"), "profile baseline")
    reserved = profile.get("reserved")
    if not isinstance(reserved, dict):
        raise ValueError("Profile reservation map required")
    if reserved != PROFILE_RESERVED:
        raise ValueError("Recorded reservation geometry differs")
    ranges = profile.get("protected_ranges")
    if ranges != [list(item) for item in PROFILE_PROTECTED_RANGES]:
        raise ValueError("Recorded protected-range geometry differs")
    checked = []
    for row in ranges:
        if (not isinstance(row, list) or len(row) != 2
                or any(type(x) is not int for x in row)
                or not (0 <= row[0] < row[1] <= FLASH_BYTES)):
            raise ValueError("Malformed protected range")
        checked.append(tuple(row))
    return internal, reserved, checked


def analyze(image_a, image_b, expected_image_sha256, profile_baseline_image,
            profile, expected_profile_file_sha256, profile_file_bytes):
    """Compare current paired reads with the separately pinned profile baseline."""
    expected_image = _digest(expected_image_sha256, "image")
    expected_profile_file = _digest(expected_profile_file_sha256, "profile file")
    if not isinstance(image_a, bytes) or not isinstance(image_b, bytes):
        raise ValueError("Two immutable raw-image byte strings required")
    if len(image_a) != FLASH_BYTES or len(image_b) != FLASH_BYTES:
        raise ValueError("Two complete 1 MiB images required")
    if image_a != image_b or sha256(image_a) != expected_image:
        raise ValueError("Matching images bound to the explicit image digest required")
    if (not isinstance(profile_baseline_image, bytes)
            or len(profile_baseline_image) != FLASH_BYTES):
        raise ValueError("Complete profile-baseline image bytes required")
    if not isinstance(profile_file_bytes, bytes) or sha256(profile_file_bytes) != expected_profile_file:
        raise ValueError("Profile file differs from its explicit external digest")
    try:
        decoded_profile = json.loads(profile_file_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Profile file must be valid JSON") from exc
    if _canonical(decoded_profile) != _canonical(profile):
        raise ValueError("Supplied profile object differs from hashed profile file")
    try:
        profile_sha, reserved, protected = _validate_profile(profile)
    except (KeyError, TypeError) as exc:
        raise ValueError("Malformed recorded profile") from exc
    expected_profile_baseline = profile["baseline_sha256"]
    if sha256(profile_baseline_image) != expected_profile_baseline:
        raise ValueError("Profile baseline bytes differ from the profile's pinned image")

    named_banks = {name: (item[0], item[0] + item[1])
                   for name, item in reserved.items() if name in ("VM", "BTIF", "USR")}
    sectors = []
    for slot, offsets in SLOT_SECTORS.items():
        for offset in offsets:
            end = offset + SECTOR_BYTES
            raw = image_a[offset:end]
            baseline_sector = profile_baseline_image[offset:end]
            tail = raw[-PAGE_BYTES:]
            spl_record, cleanup_record = _record_predicates(tail)
            bank_overlap = sorted(name for name, (lo, hi) in named_banks.items()
                                  if _overlap(offset, end, lo, hi))
            protected_overlap = [[lo, hi] for lo, hi in protected
                                 if _overlap(offset, end, lo, hi)]
            sectors.append({
                "slot": slot,
                "offset": offset,
                "length": SECTOR_BYTES,
                "sector_sha256": sha256(raw),
                "opaque_non_ff_bytes": sum(byte != 0xFF for byte in raw),
                "sector_is_all_ff": raw == b"\xff" * SECTOR_BYTES,
                "profile_baseline_sector_sha256": sha256(baseline_sector),
                "profile_baseline_opaque_non_ff_bytes": sum(byte != 0xFF for byte in baseline_sector),
                "profile_baseline_sector_is_all_ff": baseline_sector == b"\xff" * SECTOR_BYTES,
                "matches_profile_baseline": raw == baseline_sector,
                "differing_bytes_from_profile_baseline": sum(
                    current != original for current, original in zip(raw, baseline_sector)),
                "declared_bank_overlaps": bank_overlap,
                "ota_stage_overlap": _overlap(offset, end, OTA_START, OTA_END),
                "protected_range_overlaps": protected_overlap,
                "spl_record_candidate": spl_record,
                "cleanup_record_candidate": cleanup_record,
                "tail_page_sha256": sha256(tail),
                "tail_page_non_ff_bytes": sum(byte != 0xFF for byte in tail),
                "logical_ownership": "unresolved",
                "erase_safe": False,
            })
    return {
        "schema": 1,
        "kind": "fm1-storage48-read-only-ownership-inventory",
        "image_sha256": expected_image,
        "current_pair_sha256": expected_image,
        "profile_file_sha256": expected_profile_file,
        "profile_sha256": profile_sha,
        "profile_baseline_sha256": profile["baseline_sha256"],
        "profile_identity": "FM-1_092 recorded offline profile; geometry provenance only, not current-target identity or admission",
        "ota_stage_range": [OTA_START, OTA_END],
        "map_sector_count": len(sectors),
        "sectors": sectors,
        "opaque_non_ff_bytes_total": sum(row["opaque_non_ff_bytes"] for row in sectors),
        "profile_baseline_opaque_non_ff_bytes_total": sum(
            row["profile_baseline_opaque_non_ff_bytes"] for row in sectors),
        "profile_baseline_differing_candidate_sector_count": sum(
            not row["matches_profile_baseline"] for row in sectors),
        "profile_baseline_differing_candidate_bytes": sum(
            row["differing_bytes_from_profile_baseline"] for row in sectors),
        "ownership_verified": False,
        "semantic_migration_verified": False,
        "erase_sequence": [],
        "erase_safe": False,
        "physical_writer_ready": False,
        "hardware_admitted": False,
        "hardware_operations": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-a", type=Path, required=True)
    parser.add_argument("--image-b", type=Path, required=True)
    parser.add_argument("--expected-image-sha256", required=True)
    parser.add_argument("--profile-baseline", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--expected-profile-file-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    profile_bytes = args.profile.read_bytes()
    profile = json.loads(profile_bytes)
    result = analyze(args.image_a.read_bytes(), args.image_b.read_bytes(),
                     args.expected_image_sha256, args.profile_baseline.read_bytes(), profile,
                     args.expected_profile_file_sha256, profile_bytes)
    args.out.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")


if __name__ == "__main__":
    main()

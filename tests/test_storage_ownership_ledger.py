# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
from storage_ownership_ledger import (FLASH_BYTES, SLOT_SECTORS, analyze,
                                      sha256)


def make_profile(image):
    body = {
        "schema": 1,
        "status": "recorded-fm1-092-raw-profile-verified-offline",
        "coordinates": "raw NOR byte offsets",
        "baseline_sha256": sha256(image),
        "reserved": {
            "VM": [0xD9000, 0x10000, 0x12],
            "PRCT": [0, 0xD9000, 0x92],
            "BTIF": [0xE9000, 0x1000, 0x92],
            "USR": [0xEA000, 0x12000, 0x92],
            "key_mac": [0xFF000, 0x1000, 0x12],
        },
        # Independent literal from raw_flash_profile.py: 0x4000 + 692032.
        "protected_ranges": [[0, 0x4000], [708416, FLASH_BYTES]],
    }
    body["profile_sha256"] = sha256(json.dumps(
        body, sort_keys=True, separators=(",", ":")).encode())
    encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    return body, encoded


def run(image, profile=None, profile_bytes=None, *, profile_baseline=None,
        image_pin=None, profile_pin=None):
    if profile is None:
        profile, profile_bytes = make_profile(image)
    baseline = image if profile_baseline is None else profile_baseline
    return analyze(image, image, image_pin or sha256(image), baseline, profile,
                   profile_pin or sha256(profile_bytes), profile_bytes)


def test_ledger_accounts_each_candidate_and_never_equates_blank_with_free():
    raw = b"\xff" * FLASH_BYTES
    ledger = run(raw)
    rows = ledger["sectors"]
    assert ledger["map_sector_count"] == 24
    assert len(rows) == sum(map(len, SLOT_SECTORS.values()))
    assert ledger["opaque_non_ff_bytes_total"] == 0
    assert all(row["sector_is_all_ff"] for row in rows)
    assert all(row["logical_ownership"] == "unresolved" for row in rows)
    assert all(row["erase_safe"] is False for row in rows)
    assert ledger["erase_safe"] is False
    assert ledger["erase_sequence"] == []
    assert ledger["ownership_verified"] is False
    assert ledger["hardware_admitted"] is False


def test_ledger_counts_opaque_bytes_and_classifies_profile_bank_and_ota_overlap():
    raw = bytearray(b"\xff" * FLASH_BYTES)
    offsets = SLOT_SECTORS["A"]
    raw[offsets[0] + 7] = 0x00
    raw[offsets[0] + 9] = 0x00
    usr_offset = SLOT_SECTORS["B"][0]
    raw[usr_offset + 10] = 0x00
    snapshot = bytes(raw)
    ledger = run(snapshot)
    vm = next(row for row in ledger["sectors"] if row["offset"] == offsets[0])
    usr = next(row for row in ledger["sectors"] if row["offset"] == usr_offset)
    assert vm["opaque_non_ff_bytes"] == 2
    assert vm["declared_bank_overlaps"] == ["VM"]
    assert vm["ota_stage_overlap"] is False
    assert usr["opaque_non_ff_bytes"] == 1
    assert usr["declared_bank_overlaps"] == ["USR"]
    assert usr["ota_stage_overlap"] is False
    assert ledger["opaque_non_ff_bytes_total"] == 3


def test_current_pair_can_differ_from_pinned_stock_profile_without_relabeling_it():
    profile_baseline = b"\xff" * FLASH_BYTES
    profile, profile_bytes = make_profile(profile_baseline)
    current = bytearray(profile_baseline)
    current[0x5000] = 0x00  # application-space change, outside candidate map
    current_bytes = bytes(current)
    result = analyze(current_bytes, current_bytes, sha256(current_bytes),
                     profile_baseline, profile, sha256(profile_bytes), profile_bytes)
    assert result["profile_baseline_sha256"] == sha256(profile_baseline)
    assert result["current_pair_sha256"] == sha256(current_bytes)
    assert result["profile_identity"].startswith("FM-1_092 recorded offline profile")
    assert result["profile_baseline_differing_candidate_sector_count"] == 0
    assert all(row["matches_profile_baseline"] for row in result["sectors"])


def test_candidate_difference_is_counted_but_remains_ownership_unresolved():
    profile_baseline = b"\xff" * FLASH_BYTES
    profile, profile_bytes = make_profile(profile_baseline)
    current = bytearray(profile_baseline)
    offset = SLOT_SECTORS["A"][0]
    current[offset + 3] = 0x00
    current_bytes = bytes(current)
    result = analyze(current_bytes, current_bytes, sha256(current_bytes),
                     profile_baseline, profile, sha256(profile_bytes), profile_bytes)
    row = next(item for item in result["sectors"] if item["offset"] == offset)
    assert row["matches_profile_baseline"] is False
    assert row["differing_bytes_from_profile_baseline"] == 1
    assert row["opaque_non_ff_bytes"] == 1
    assert row["logical_ownership"] == "unresolved"
    assert row["erase_safe"] is False
    assert result["profile_baseline_differing_candidate_sector_count"] == 1
    assert result["profile_baseline_differing_candidate_bytes"] == 1


def test_profile_baseline_is_independently_hash_checked():
    profile_baseline = b"\xff" * FLASH_BYTES
    current = profile_baseline
    profile, profile_bytes = make_profile(profile_baseline)
    wrong_baseline = bytearray(profile_baseline)
    wrong_baseline[0xD9000] = 0
    with pytest.raises(ValueError, match="profile's pinned image"):
        analyze(current, current, sha256(current), bytes(wrong_baseline),
                profile, sha256(profile_bytes), profile_bytes)


@pytest.mark.parametrize("fault", ["different-pair", "wrong-image-pin", "short-image",
                                    "wrong-profile-pin", "changed-profile-file",
                                    "wrong-profile-baseline", "wrong-bank-map",
                                    "malformed-protected-range"])
def test_unpinned_or_incompatible_inputs_refuse(fault):
    image = b"\xff" * FLASH_BYTES
    profile, profile_bytes = make_profile(image)
    image_b = image
    image_pin = sha256(image)
    profile_pin = sha256(profile_bytes)
    if fault == "different-pair":
        image_b = image[:-1] + b"\x00"
    elif fault == "wrong-image-pin":
        image_pin = "0" * 64
    elif fault == "short-image":
        image = image[:-1]
        image_b = image
        image_pin = sha256(image)
    elif fault == "wrong-profile-pin":
        profile_pin = "0" * 64
    elif fault == "changed-profile-file":
        profile_bytes += b" "
    elif fault == "wrong-profile-baseline":
        profile["baseline_sha256"] = "0" * 64
        profile_bytes = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
        profile_pin = sha256(profile_bytes)
    elif fault == "wrong-bank-map":
        profile["reserved"]["VM"][0] += 0x1000
        profile["profile_sha256"] = "1" * 64
        profile_bytes = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
        profile_pin = sha256(profile_bytes)
    elif fault == "malformed-protected-range":
        profile["protected_ranges"] = [[0x4000, 0x4000]]
        body = dict(profile)
        del body["profile_sha256"]
        profile["profile_sha256"] = sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode())
        profile_bytes = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
        profile_pin = sha256(profile_bytes)
    with pytest.raises(ValueError):
        analyze(image, image_b, image_pin, image, profile, profile_pin, profile_bytes)


def test_missing_profile_fields_refuse_with_value_error():
    image = b"\xff" * FLASH_BYTES
    profile, profile_bytes = make_profile(image)
    del profile["baseline_sha256"]
    profile_bytes = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    profile["profile_sha256"] = sha256(json.dumps(
        {k: v for k, v in profile.items() if k != "profile_sha256"},
        sort_keys=True, separators=(",", ":")).encode())
    profile_bytes = json.dumps(profile, sort_keys=True, separators=(",", ":")).encode()
    with pytest.raises(ValueError):
        analyze(image, image, sha256(image), image, profile,
                sha256(profile_bytes), profile_bytes)

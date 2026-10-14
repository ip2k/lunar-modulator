#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare offline exact-evidence transactions for the device38 Event Horizon candidate.

This helper never opens a transport or performs device operations. Candidate
readiness remains false pending independent transport-manifest admission.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm1_flash_transaction import (FLASH_SIZE, SECTOR_BYTES, checked_identity,
                                   create_transaction, digest, encoded, load_transaction,
                                   save_new, sync_directory)

BASELINE_SHA = "c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903"
MANIFEST_SHA = "2bed49db98cf7268d7cab7ff3283dd8d5eade233cf45d39505099a0095e44812"
COMMANDS_SHA = "fb3f60fb4344b72e3887283ed9b046e9109ef7f3d2a83f2ed0d8cdf67d8e259f"
TARGET_SHA = "145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657"
STOCK_SHA = "96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4"
CANDIDATE_APP_SHA = "5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573"
CANDIDATE_RECEIPT_SHA = "1c53f94ba57001f30901a2f33081f26c223f1789781abaa0f5325e83880684db"
INSTALLATION_PROOF_SHA = "1798734ef5d8a0754cd17e039e7747a306e34177ebaabcdc591ad06f3a25e41c"
APP_BASE, AREA_END = 0x4000, 0xD9000


def pinned(path, expected, limit=FLASH_SIZE):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("Regular pinned evidence file required")
    with path.open("rb") as fp:
        raw = fp.read(limit + 1)
    if len(raw) > limit or digest(raw) != expected:
        raise ValueError("Evidence digest or size differs from recorded pin")
    return raw


def changed_ranges(before, after):
    if any(not isinstance(x, bytes) or len(x) != FLASH_SIZE for x in (before, after)):
        raise ValueError("Complete NOR images required")
    if before[:APP_BASE] != after[:APP_BASE] or before[AREA_END:] != after[AREA_END:]:
        raise ValueError("Protected stock bytes differ")
    ranges = []
    for address in range(APP_BASE, AREA_END, SECTOR_BYTES):
        if before[address:address + SECTOR_BYTES] == after[address:address + SECTOR_BYTES]:
            continue
        if ranges and ranges[-1][1] == address:
            ranges[-1][1] += SECTOR_BYTES
        else:
            ranges.append([address, address + SECTOR_BYTES])
    if not ranges or ranges[0][0] != APP_BASE:
        raise ValueError("Changed application directory sector required")
    return ranges


def prepare(output, receipt, target, stock_a, stock_b):
    receipt, output = Path(receipt), Path(output)
    manifest = json.loads(pinned(receipt / "manifest.json", MANIFEST_SHA, 65536))
    pinned(receipt / "commands.jsonl", COMMANDS_SHA, 8 * FLASH_SIZE)
    current_a = pinned(receipt / "dumpA.bin", BASELINE_SHA)
    current_b = pinned(receipt / "dumpB.bin", BASELINE_SHA)
    image = pinned(target, TARGET_SHA)
    stock = pinned(stock_a, STOCK_SHA)
    if current_a != current_b or pinned(stock_b, STOCK_SHA) != stock:
        raise ValueError("Two matching fresh current reads and stock references required")
    if (manifest.get("kind") != "fm1-device38-expanded-rom-fixed-loader-dual-read" or
            manifest.get("usb_binding", {}).get("devnum") != "38" or
            manifest.get("current_flash_sha256") != BASELINE_SHA or
            manifest.get("dumps") != [
                {"bytes": FLASH_SIZE, "file": "dumpA.bin", "sha256": BASELINE_SHA},
                {"bytes": FLASH_SIZE, "file": "dumpB.bin", "sha256": BASELINE_SHA}] or
            manifest.get("flash_operations") != 0 or manifest.get("reset_operations") != 0 or
            manifest.get("installation_proof_sha256") != INSTALLATION_PROOF_SHA):
        raise ValueError("Fresh exact device38 dual-read receipt binding required")
    candidate_receipt = json.loads(pinned(
        Path(target).parent / "candidate-receipt.json", CANDIDATE_RECEIPT_SHA, 65536))
    if (candidate_receipt.get("app_sha256") != CANDIDATE_APP_SHA or
            candidate_receipt.get("app_bytes") != 845036 or
            candidate_receipt.get("target_sha256") != TARGET_SHA or
            candidate_receipt.get("hardware_admitted") is not False or
            candidate_receipt.get("installable") is not False or
            candidate_receipt.get("physical_writer_ready") is not False):
        raise ValueError("Candidate content receipt does not identify the pinned profile")
    identity = checked_identity(dict(unit_id="owner-fm1-fresh-rom-device38",
        flash_size=FLASH_SIZE, sector_size=SECTOR_BYTES, page_size=256,
        jedec=0x856014, simulated=False, usb_binding=manifest["usb_binding"],
        backup_manifest_sha256=MANIFEST_SHA))
    install_ranges = changed_ranges(current_a, image)
    stock_ranges = changed_ranges(current_a, stock)
    changed_ranges(stock, image)
    if output.exists():
        raise ValueError("New private output directory required")
    create_transaction(output / "event120-candidate", current_a, current_b,
        image, identity, install_ranges, "offline device38 Event Horizon 120 candidate plan",
        commit_sector=APP_BASE)
    create_transaction(output / "stock-rollback", current_a, current_b,
        stock, identity, stock_ranges, "offline device38 stock restoration plan",
        commit_sector=APP_BASE)
    plans = {}
    for name, expected in (("event120-candidate", image), ("stock-rollback", stock)):
        loaded, journal, saved_before, saved_target = load_transaction(output / name)
        if (journal["state"] != "prepared" or saved_before != current_a or
                saved_target != expected or loaded["sector_order"][-1] != APP_BASE):
            raise ValueError("Durable prepared plan verification failed")
        plans[name] = dict(plan_sha256=digest(encoded(loaded)),
            sectors=len(loaded["sector_order"]), target_sha256=digest(expected),
            commit_sector=loaded["sector_order"][-1])
    report = dict(schema=1, kind="device38-event120-offline-transactions",
        source_manifest_sha256=MANIFEST_SHA, source_commands_sha256=COMMANDS_SHA,
        baseline_sha256=BASELINE_SHA, stock_reference_sha256=STOCK_SHA,
        target_sha256=TARGET_SHA, candidate_app_sha256=CANDIDATE_APP_SHA,
        candidate_transport_manifest_admitted=False, physical_writer_ready=False,
        hardware_admitted=False, installable=False, physical_recovery_verified=False,
        plans=plans, recovery_sequence=["candidate failure: restore current backup",
        "verify full current SHA", "stock:install prepared stock rollback plan",
        "verify full stock SHA"])
    save_new(output / "preparation.json", encoded(report))
    sync_directory(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "receipt", "target", "stock-a", "stock-b"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.receipt, args.target,
        args.stock_a, args.stock_b), sort_keys=True))


if __name__ == "__main__":
    main()

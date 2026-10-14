#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline, exact-device36 plans for the current thirteen-engine timed probe.

No transport, loader upload, reset or physical writer admission. Private image
pins identify this one campaign; changing firmware requires a new review.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm1_flash_transaction import (create_transaction, digest, encoded,
                                   load_transaction, save_new, sync_directory)
from native.controls_transactions import pinned

BASELINE_SHA = '770fd5f275110f017329dda30315343d766ff4a6c6beaa62f5a0060c629dc561'
TARGET_SHA = 'c543e538754d0ae02ee119fd1e29a9b8cb9eb21a23edf0c12fc981ddaa3bc903'
STOCK_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
MANIFEST_SHA = '3d0b78a4815de882e7b1498c65b2ae9bc619b40139be9bdab084b0214542d17e'
COMMANDS_SHA = 'b9394debd199d34231d7848062d15e22e069141d247153f4ad2dfef8c3b34059'
TRANSACTION_SHA = 'd0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908'
APP_BASE, AREA_END, FLASH_BYTES, SECTOR = 0x4000, 0xD9000, 1048576, 4096


def changed_ranges(before, after):
    """Full changed-sector union, refusing any protected byte difference."""
    if any(not isinstance(x, bytes) or len(x) != FLASH_BYTES for x in (before, after)):
        raise ValueError('Complete NOR images required')
    if before[:APP_BASE] != after[:APP_BASE] or before[AREA_END:] != after[AREA_END:]:
        raise ValueError('Protected stock bytes differ')
    ranges = []
    for address in range(APP_BASE, AREA_END, SECTOR):
        if before[address:address + SECTOR] == after[address:address + SECTOR]:
            continue
        if ranges and ranges[-1][1] == address:
            ranges[-1][1] += SECTOR
        else:
            ranges.append([address, address + SECTOR])
    if not ranges or ranges[0][0] != APP_BASE:
        raise ValueError('Changed application directory sector required')
    return ranges


def prepare(output, receipt, target, stock_a, stock_b):
    """Seal install/rollback artifacts from the fresh matching Trio backups."""
    pinned(Path(__file__).resolve().parents[1] / 'fm1_flash_transaction.py', TRANSACTION_SHA)
    receipt, output = Path(receipt), Path(output)
    manifest = json.loads(pinned(receipt / 'manifest.json', MANIFEST_SHA, 65536))
    pinned(receipt / 'commands.jsonl', COMMANDS_SHA, 8 * FLASH_BYTES)
    a = pinned(receipt / 'dumpA.bin', BASELINE_SHA)
    b = pinned(receipt / 'dumpB.bin', BASELINE_SHA)
    image = pinned(target, TARGET_SHA)
    stock = pinned(stock_a, STOCK_SHA)
    if a != b or pinned(stock_b, STOCK_SHA) != stock:
        raise ValueError('Two matching complete backups required')
    pairs = [('native', a, b, image), ('stock', a, b, stock)]
    ranges = {name: changed_ranges(before, after) for name, before, _, after in pairs}
    changed_ranges(stock, image)
    identity = dict(unit_id='owner-fm1-bench01-fresh-rom-device36',
                    flash_size=FLASH_BYTES, sector_size=SECTOR, page_size=256,
                    jedec=0x856014, simulated=False, usb_binding=manifest['usb_binding'],
                    backup_manifest_sha256=MANIFEST_SHA)
    if output.exists():
        raise ValueError('New private output directory required')
    plans = {}
    for name, before, other, after in pairs:
        plan = create_transaction(output / name, before, other, after, identity,
                                  ranges[name], 'fresh device36 expanded timed probe: ' + name,
                                  commit_sector=APP_BASE)
        loaded, journal, saved_before, saved_after = load_transaction(output / name)
        if (loaded != plan or journal['state'] != 'prepared' or
                saved_before != before or saved_after != after or
                plan['sector_order'][-1] != APP_BASE):
            raise ValueError('Durable transaction verification failed')
        plans[name] = dict(plan_sha256=digest(encoded(plan)),
                           sectors=len(plan['sector_order']),
                           baseline_sha256=digest(before), target_sha256=digest(after))
    report = dict(schema=1, kind='device36-expanded-offline-transactions', plans=plans,
                  hardware_admitted=False, physical_writer_ready=False, installable=False,
                  settings_migration_verified=False, physical_recovery_verified=False,
                  recovery_sequence=['native:restore', 'verify full Trio', 'stock:install'])
    save_new(output / 'preparation.json', encoded(report))
    sync_directory(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'receipt', 'target', 'stock-a', 'stock-b'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.receipt, args.target, args.stock_a, args.stock_b)))


if __name__ == '__main__':
    main()

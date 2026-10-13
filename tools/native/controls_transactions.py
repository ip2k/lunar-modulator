"""MIT. Offline plans for the fresh device-27 V8-to-controls bench experiment.

No transport or writer admission. Pins select the already independently
replayed private receipt and the audited native candidate, not arbitrary
caller-described firmware. Physical use still needs a current loader policy.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fm1_flash_transaction import (FLASH_SIZE, SECTOR_BYTES, checked_identity,
                                   create_transaction, digest, encoded, save_new,
                                   sync_directory)

V8_SHA = '5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d'
STOCK_SHA = '96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4'
NATIVE_SHA = '770fd5f275110f017329dda30315343d766ff4a6c6beaa62f5a0060c629dc561'
MANIFEST_SHA = '0c8f8e37b9bb12cdee0e608bec6cb5b5e473f5f243ffacb5f94ee7e25c0a5265'
COMMANDS_SHA = 'd4ecaab69eff3e1d55d335d2068d133feecc176b46c46d2d079c71291ffafed3'
APP_BASE = 0x4000
# Same reviewed raw profile boundary: cfg_tool and all following bytes.
PROTECTED_END_START = APP_BASE + 692032


def changed_ranges(before, after):
    """Derive the full sector union from current bytes, including old app tail."""
    if any(not isinstance(x, bytes) or len(x) != FLASH_SIZE for x in (before, after)):
        raise ValueError('Complete NOR images required')
    if (before[:APP_BASE] != after[:APP_BASE] or
            before[PROTECTED_END_START:] != after[PROTECTED_END_START:]):
        raise ValueError('Protected stock bytes differ')
    ranges = []
    for address in range(0, FLASH_SIZE, SECTOR_BYTES):
        if before[address:address + SECTOR_BYTES] == after[address:address + SECTOR_BYTES]:
            continue
        if address < APP_BASE or address + SECTOR_BYTES > PROTECTED_END_START:
            raise ValueError('Changed sector overlaps protected bytes')
        if ranges and ranges[-1][1] == address:
            ranges[-1][1] += SECTOR_BYTES
        else:
            ranges.append([address, address + SECTOR_BYTES])
    if not ranges:
        raise ValueError('No changed sectors')
    return ranges


def pinned(path, expected, limit=FLASH_SIZE):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular private evidence file required')
    with path.open('rb') as fp:
        raw = fp.read(limit + 1)
    if len(raw) > limit or digest(raw) != expected:
        raise ValueError('Recorded evidence pin differs')
    return raw


def prepare(output, receipt, stock_a, stock_b, native, *, simulated=False):
    """Make separate current-to-native and current-to-stock durable plans."""
    receipt = Path(receipt)
    manifest = json.loads(pinned(receipt / 'manifest.json', MANIFEST_SHA, 65536))
    pinned(receipt / 'commands.jsonl', COMMANDS_SHA, 8 * FLASH_SIZE)
    a = pinned(receipt / 'dumpA.bin', V8_SHA)
    b = pinned(receipt / 'dumpB.bin', V8_SHA)
    stock = pinned(stock_a, STOCK_SHA)
    if pinned(stock_b, STOCK_SHA) != stock or a != b:
        raise ValueError('Matching complete backups required')
    target = pinned(native, NATIVE_SHA)
    # No historical USB3 topology is promoted to a current connection.
    identity = checked_identity(dict(
        unit_id='owner-fm1-bench01-fresh-rom-device27',
        flash_size=FLASH_SIZE, sector_size=SECTOR_BYTES, page_size=256,
        jedec=0x856014, simulated=simulated,
        usb_binding=manifest['usb_binding'],
        backup_manifest_sha256=MANIFEST_SHA))
    native_ranges = changed_ranges(a, target)
    stock_ranges = changed_ranges(a, stock)
    # Explicitly verify stock/native agree in every protected byte too.
    changed_ranges(stock, target)
    output = Path(output)
    if output.exists():
        raise ValueError('New private output directory required')
    first = create_transaction(output / 'native', a, b, target, identity,
                               native_ranges, 'fresh bounded native Trio controls probe',
                               commit_sector=APP_BASE)
    second = create_transaction(output / 'stock', a, b, stock, identity,
                                stock_ranges, 'stock after verified V8 rollback',
                                commit_sector=APP_BASE)
    report = dict(schema=1, kind='native-controls-offline-transactions',
                  hardware_admitted=False, installable=False,
                  physical_recovery_verified=False, simulated=simulated,
                  native_plan_sha256=digest(encoded(first)),
                  stock_plan_sha256=digest(encoded(second)),
                  native_sectors=len(first['sector_order']),
                  stock_sectors=len(second['sector_order']),
                  recovery_sequence=['native:restore', 'verify full V8', 'stock:install'])
    save_new(output / 'preparation.json', encoded(report))
    sync_directory(output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('output', 'receipt', 'stock-a', 'stock-b', 'native'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.output, args.receipt, args.stock_a,
                             args.stock_b, args.native), sort_keys=True))


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Check a linked dev-board pipeline ELF against the two image bounds.

1. Writer bound: the flat application (the load images of .text, .data,
   .dynamic_data, .ram0_data and .cache_ram_data, contiguous from the app entry
   0x02000120) starts at flash 0x4120, and the bounded app-only writer stops at
   0x97000, so the application must be shorter than 601,824 bytes.
2. Heap: HEAP_END - HEAP_BEGIN is the SDK's HEAP_SIZE (V225: 47,212 in both the
   ELF and the boot log). Five board logs (V198, V201, V220, V224, V225) show
   43,512 B in use after the DAC opens, and V225 ran stably with 3,700 B left,
   so HEAP_SIZE - 43,512 must be at least 3,700 [inferred: a prediction until
   the board reports it].

Offline only: reads the ELF, never a device. Exit status 1 when a bound fails.
MIT licence.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_link import Elf  # noqa: E402

APP_ENTRY = 0x02000120
APP_FLASH_OFFSET = 0x4120
WRITER_END = 0x97000
APP_BYTES_LIMIT = WRITER_END - APP_FLASH_OFFSET
HEAP_IN_USE_AFTER_OPEN = 43512
HEAP_MIN_AFTER_OPEN = 3700
# Section, and the symbol holding its load address (None: the app entry).
LOAD_IMAGES = (('.text', None), ('.data', 'data_lma'), ('.dynamic_data', 'dynamic_data_lma'),
               ('.ram0_data', '_ram0_data_lma'), ('.cache_ram_data', 'cache_ram_data_lma'))


def measure(data, name='<elf>'):
    """Bounds of one linked ELF: app bytes, app_end, HEAP_SIZE, predicted heap."""
    elf = Elf(data, name)

    def symbol(n):
        value = elf.symbol_value(n)
        if value is None:
            raise ValueError(f'{name}: no {n} symbol')
        return value
    sections = {s['name']: s for s in elf.sections}
    app = 0
    parts = {}
    for section, lma_symbol in LOAD_IMAGES:
        if section not in sections:
            raise ValueError(f'{name}: no {section} section')
        lma = APP_ENTRY if lma_symbol is None else symbol(lma_symbol)
        if lma - APP_ENTRY != app:
            raise ValueError(f'{name}: {section} does not follow the previous load image')
        parts[section] = sections[section]['size']
        app += sections[section]['size']
    heap = symbol('HEAP_END') - symbol('HEAP_BEGIN')
    predicted = heap - HEAP_IN_USE_AFTER_OPEN
    return dict(app_bytes=app, app_end=hex(APP_FLASH_OFFSET + app), app_bytes_limit=APP_BYTES_LIMIT,
                app_margin=APP_BYTES_LIMIT - app, load_images=parts, heap_size=heap,
                heap_after_open_predicted=predicted, heap_margin=predicted - HEAP_MIN_AFTER_OPEN,
                writer_bound=app < APP_BYTES_LIMIT, heap_bound=predicted >= HEAP_MIN_AFTER_OPEN)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('elf', nargs='+', type=Path, help='linked sdk.elf files')
    args = ap.parse_args(argv)
    report = {str(p): measure(p.read_bytes(), str(p)) for p in args.elf}
    print(json.dumps(report, indent=2))
    return 0 if all(r['writer_bound'] and r['heap_bound'] for r in report.values()) else 1


if __name__ == '__main__':
    sys.exit(main())

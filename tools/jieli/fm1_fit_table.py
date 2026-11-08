#!/usr/bin/env python3
"""Compare linked images against V15's app slot and the FM-1's SRAM (docs/18 M2).

Takes `NAME=ELF` pairs and prints one row per image: app bytes (the sum of the
ELF's load images, which equals the flat `app.bin` when the build writes one:
597,916 B for the soak image, notes/2026-10-29-fm1-image-budget.md), the margin
in the 581,564 B slot, the SRAM margin over the minimum heap, and, against the
first image, the bytes each symbol gained or lost. Uses fm1_budget.measure, so
the limits are that tool's. Offline: reads files only. MIT licence.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_link import Elf  # noqa: E402
import fm1_budget  # noqa: E402


def symbol_sizes(elf):
    """name -> bytes of the symbols placed in an allocated section (sizes summed per name)."""
    out = {}
    for s in elf.symbols:
        if s['size'] and s['type'] in (1, 2) and s['name']:
            out[s['name']] = out.get(s['name'], 0) + s['size']
    return out


def row(name, path):
    elf = Elf(Path(path).read_bytes(), str(path))
    app = sum(s['size'] for s in elf.sections if s['name'] in fm1_budget.LOAD_IMAGES)
    rep = fm1_budget.measure(app, elf)
    return dict(name=name, app_bytes=app, slot_margin=rep['app_margin'],
                sram_static=rep['ram_static_bytes'], heap=rep['heap_bytes'],
                heap_margin=rep['heap_margin'], cache_ram_used=rep['cache_ram_used'],
                load_images=rep['load_images'], symbols=symbol_sizes(elf))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image', nargs='+', metavar='NAME=ELF')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--diff', type=int, default=0, metavar='N',
                    help='list the N largest symbol changes of each image against the first')
    args = ap.parse_args(argv)
    rows = []
    for spec in args.image:
        name, _, path = spec.partition('=')
        if not path:
            ap.error('expected NAME=ELF: ' + spec)
        rows.append(row(name, path))
    base = rows[0]
    if args.json:
        print(json.dumps([{k: v for k, v in r.items() if k != 'symbols'} for r in rows], indent=1))
        return 0
    print(f"{'image':<24}{'app.bin B':>11}{'vs base':>9}{'slot margin':>13}{'SRAM static':>12}{'heap margin':>12}{'cache RAM':>10}")
    for r in rows:
        print(f"{r['name']:<24}{r['app_bytes']:>11,}{r['app_bytes'] - base['app_bytes']:>+9,}"
              f"{r['slot_margin']:>+13,}{r['sram_static']:>12,}{r['heap_margin']:>+12,}{r['cache_ram_used']:>10,}")
    if args.diff:
        for r in rows[1:]:
            d = {n: r['symbols'].get(n, 0) - base['symbols'].get(n, 0)
                 for n in set(r['symbols']) | set(base['symbols'])}
            top = sorted((kv for kv in d.items() if kv[1]), key=lambda kv: kv[1])
            print(f"\n{r['name']} against {base['name']}: largest symbol changes")
            for n, v in (top[:args.diff] + top[-args.diff:]):
                print(f"  {v:>+9,} {n}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

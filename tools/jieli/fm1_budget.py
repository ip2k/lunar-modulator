#!/usr/bin/env python3
"""Offline size and SRAM budget gate for an FM-1 image (docs/18 milestone M2).

Reads a flat `app.bin` and, optionally, the linked ELF it came from, and checks
them against the FM-1's V15 layout:

1. App slot. V15 puts the JLFS directory at 0x4000, `app.bin` at 0x4120 and
   `cfg_tool.bin` at 0x920DC [verified: notes/2026-09-06-bench.md, docs/01 §2],
   so an app that leaves cfg, OTA loader and layout byte-identical to stock
   (CLAUDE.md conventions) must be no longer than 0x920DC - 0x4120 = 581,564 B
   [inferred: the app is not allowed to run into `cfg_tool.bin`]. `--margin`
   demands that much spare room on top.
2. SRAM. The chip has 578 KB [verified: AC79 SDK README]; the SDK map puts the
   app's SRAM at 0x01C00000 and `boot_info` at 0x01C7FD4C [verified: SDK
   `sdk_ld_sfc.c` at e30b1ee], stock's boot struct at 0x01C7FD50 [reported]. Stock
   `.bss` ends at 0x01C211FC, which leaves the 387,924 B "SRAM gap"
   (0x01C7FD50 - 0x01C211FC; docs/11 §2, engines/README.md) [inferred]. An image
   fits when its RAM sections (`.data`/`.bss` or the SDK's `.ram0_data`/`.ram0_bss`)
   plus a minimum heap end at or below `boot_info`. The default minimum heap is
   the 47,212 B the dev-board pipeline needs (tools/jieli/pipeline_bounds.py:
   43,512 B in use after the DAC opens, 3,700 B floor) [inferred]; set
   `--min-heap` for an FM-1 board layer that differs.
3. Cache RAM. Sections in the 28 KB cache-RAM window 0x01F28000-0x01F2F000
   [reported: fm1-nes `audit_boot.py`] must fit it.
4. SPL hole. The stock SPL body sits at 0x01C02000-0x01C05820 [verified:
   notes/2026-10-09-handover-layout-audit.md]. The overlap is reported. It is
   expected for a flash-installed app (stock's own `.data` covers the hole
   [verified: docs/01 §2 addresses]) and fatal only with `--spl-hole fail`, for a
   RAM-run image that must leave the SPL intact.

Exit status: 0 every check passes, 1 a check fails, 2 usage or unreadable input.
Offline: reads files only, never a device. MIT licence.
"""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from audit_link import Elf, SHT_NOBITS  # noqa: E402

SHF_ALLOC = 2
SHT_PROGBITS = 1

APP_FLASH_OFFSET = 0x4120            # [verified: V15 unpack]
CFG_TOOL_OFFSET = 0x920DC            # [verified: bench note 2026-09-06]
APP_SLOT = CFG_TOOL_OFFSET - APP_FLASH_OFFSET   # 581,564

SRAM_BASE = 0x01C00000
SDK_BOOT_INFO = 0x01C7FD4C           # [verified: SDK sdk_ld_sfc.c]
STOCK_BOOT_STRUCT = 0x01C7FD50       # [reported: AL-255, Felucca]
STOCK_BSS_END = 0x01C211FC           # [reported: AL-255]
STOCK_GAP = STOCK_BOOT_STRUCT - STOCK_BSS_END   # 387,924
MIN_HEAP = 47212                     # [inferred: pipeline_bounds.py]
CACHE_RAM = (0x01F28000, 0x01F2F000)  # [reported: fm1-nes]
SPL_HOLE = (0x01C02000, 0x01C05820)  # [verified: handover layout audit]
# Load images of the SDK flat application, in order.
LOAD_IMAGES = ('.text', '.data', '.dynamic_data', '.ram0_data', '.cache_ram_data')


def _in(addr, window):
    return window[0] <= addr < window[1]


def measure(app_size, elf=None, slot=APP_SLOT, margin=0, min_heap=MIN_HEAP, top=0,
            spl_hole_fatal=False):
    """Budget report. `app_size` is the flat app.bin length; `elf` an audit_link.Elf or None."""
    report = dict(
        app_bytes=app_size, slot_bytes=slot, margin_required=margin,
        app_margin=slot - app_size, slot_ok=slot - app_size >= margin,
        stock_gap=STOCK_GAP, checks=[])
    ok = report['slot_ok']
    report['checks'].append(dict(
        check='app_slot', ok=report['slot_ok'],
        detail=f'{app_size} B in a {slot} B slot, margin {slot - app_size} (need {margin})'))
    if elf is None:
        report['pass'] = ok
        return report

    sections = [s for s in elf.sections
                if s['flags'] & SHF_ALLOC and s['size'] and s['name'] != '.boot_info']
    load = {s['name']: s['size'] for s in elf.sections if s['name'] in LOAD_IMAGES}
    elf_app = sum(load.values())
    report['load_images'] = load
    report['elf_app_bytes'] = elf_app
    same = elf_app == app_size
    report['elf_matches_app_bin'] = same
    report['checks'].append(dict(
        check='elf_matches_app_bin', ok=same,
        detail=f'ELF load images {elf_app} B, app.bin {app_size} B'))
    ok = ok and same

    ram = [s for s in sections if SRAM_BASE <= s['addr'] < SDK_BOOT_INFO and s['type'] in
           (SHT_PROGBITS, SHT_NOBITS)]
    ram_secs = {s['name']: dict(addr=hex(s['addr']), size=s['size'],
                                kind='bss' if s['type'] == SHT_NOBITS else 'data') for s in ram}
    static_end = max((s['addr'] + s['size'] for s in ram), default=SRAM_BASE)
    static = sum(s['size'] for s in ram)
    defs = {s['name']: s['value'] for s in elf.symbols if s['name'] in ('HEAP_BEGIN', 'HEAP_END')}
    if len(defs) == 2:
        heap = defs['HEAP_END'] - defs['HEAP_BEGIN']
        heap_src = 'HEAP_END - HEAP_BEGIN'
    else:
        heap = SDK_BOOT_INFO - static_end
        heap_src = 'space between the last RAM section and boot_info'
    pool = SDK_BOOT_INFO - SRAM_BASE
    report.update(ram_sections=ram_secs, ram_static_bytes=static, ram_static_end=hex(static_end),
                  ram_available=pool, heap_bytes=heap, heap_source=heap_src, min_heap=min_heap,
                  heap_margin=heap - min_heap,
                  stock_static_bytes=STOCK_BSS_END - SRAM_BASE,
                  static_growth_over_stock=static - (STOCK_BSS_END - SRAM_BASE))
    ram_ok = static_end <= SDK_BOOT_INFO and heap >= min_heap and static + min_heap <= pool
    report['checks'].append(dict(
        check='sram_budget', ok=ram_ok,
        detail=f'static {static} B ends {hex(static_end)}, heap {heap} B ({heap_src}), '
               f'minimum {min_heap} B, boot_info at {hex(SDK_BOOT_INFO)}'))
    ok = ok and ram_ok

    cache = [s for s in sections if _in(s['addr'], CACHE_RAM)]
    cache_used = max((s['addr'] + s['size'] for s in cache), default=CACHE_RAM[0]) - CACHE_RAM[0]
    cache_ok = cache_used <= CACHE_RAM[1] - CACHE_RAM[0]
    report.update(cache_ram_used=cache_used, cache_ram_size=CACHE_RAM[1] - CACHE_RAM[0])
    report['checks'].append(dict(
        check='cache_ram', ok=cache_ok,
        detail=f'{cache_used} of {CACHE_RAM[1] - CACHE_RAM[0]} B used'))
    ok = ok and cache_ok

    overlaps = {}
    for s in ram:
        lo, hi = max(s['addr'], SPL_HOLE[0]), min(s['addr'] + s['size'], SPL_HOLE[1])
        if hi > lo:
            overlaps[s['name']] = hi - lo
    report['spl_hole_overlap'] = overlaps
    hole_ok = not (overlaps and spl_hole_fatal)
    report['checks'].append(dict(
        check='spl_hole', ok=hole_ok,
        detail=(f'{sum(overlaps.values())} B of the SPL body range overwritten by '
                f'{", ".join(overlaps)}' if overlaps else 'no RAM section overlaps the SPL body')
        + ('' if spl_hole_fatal or not overlaps else ' (expected for a flash-installed app)')))
    ok = ok and hole_ok

    if top:
        def region(addr):
            for s in sections:
                if s['addr'] <= addr < s['addr'] + s['size']:
                    return s['name']
            return None
        rows = {}
        for sym in elf.symbols:
            if sym['size'] and sym['type'] in (1, 2) and sym['name']:
                name = region(sym['value'])
                if name:
                    rows.setdefault(name, []).append((sym['size'], sym['name']))
        report['top_symbols'] = {
            name: dict(listed_bytes=sum(r[0] for r in lst),
                       symbols=[dict(name=n, size=sz) for sz, n in sorted(lst, reverse=True)[:top]])
            for name, lst in rows.items()}
    report['pass'] = ok
    return report


def render(rep):
    out = [f"app.bin {rep['app_bytes']} B of {rep['slot_bytes']} B slot: margin {rep['app_margin']:+d}"]
    if 'load_images' in rep:
        out.append('  load images: ' + ', '.join(f'{k} {v}' for k, v in rep['load_images'].items()))
    if 'ram_sections' in rep:
        out.append(f"RAM static {rep['ram_static_bytes']} B (stock {rep['stock_static_bytes']}), "
                   f"heap {rep['heap_bytes']} B, margin over minimum {rep['heap_margin']:+d} B")
        for n, s in rep['ram_sections'].items():
            out.append(f"  {n} {s['addr']} {s['size']} B {s['kind']}")
    for c in rep['checks']:
        out.append(f"{'PASS' if c['ok'] else 'FAIL'} {c['check']}: {c['detail']}")
    for name, t in rep.get('top_symbols', {}).items():
        out.append(f"largest symbols in {name} ({t['listed_bytes']} B have symbols):")
        out += [f"  {s['size']:>8} {s['name']}" for s in t['symbols']]
    out.append('PASS' if rep['pass'] else 'FAIL')
    return '\n'.join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('app_bin', type=Path, help='flat application image')
    ap.add_argument('--elf', type=Path, help='linked ELF of the same build (adds RAM and cache checks)')
    ap.add_argument('--slot', type=lambda v: int(v, 0), default=APP_SLOT,
                    help=f'app slot in bytes (default {APP_SLOT}: V15, up to cfg_tool.bin)')
    ap.add_argument('--margin', type=lambda v: int(v, 0), default=0, help='spare bytes required in the slot')
    ap.add_argument('--min-heap', type=lambda v: int(v, 0), default=MIN_HEAP, help='minimum heap in bytes')
    ap.add_argument('--spl-hole', choices=('report', 'fail'), default='report',
                    help='fail when a RAM section overlaps the stock SPL body (RAM-run images)')
    ap.add_argument('--top', type=int, default=0, metavar='N', help='list the N largest symbols per section')
    ap.add_argument('--json', action='store_true', help='print the report as JSON')
    args = ap.parse_args(argv)
    if args.margin < 0 or args.min_heap < 0 or args.slot <= 0 or args.top < 0:
        ap.error('--margin, --min-heap, --top must be non-negative and --slot positive')
    try:
        size = args.app_bin.stat().st_size
        elf = Elf(args.elf.read_bytes(), str(args.elf)) if args.elf else None
    except (OSError, ValueError) as e:
        print(f'fm1_budget: {e}', file=sys.stderr)
        return 2
    rep = measure(size, elf, args.slot, args.margin, args.min_heap, args.top,
                  args.spl_hole == 'fail')
    print(json.dumps(rep, indent=2) if args.json else render(rep))
    return 0 if rep['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())

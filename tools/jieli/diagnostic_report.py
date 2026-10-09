#!/usr/bin/env python3
"""MIT. Fail closed on the inert diagnostic's link and flat-image contract.

This checks generated artifacts only; it does not establish the stock SPL's
clock/watchdog/cache/interrupt handover contract or device execution.
"""
import json
import struct
import sys
from pathlib import Path

from audit_link import Elf, EM_PI32V2, ET_EXEC

FLASH = 0x02000120
RAM = 0x01C02000
BUDGET = 16 * 1024
SHT_PROGBITS = 1


def report(elf_bytes, app, audit):
    image = Elf(elf_bytes)
    if image.e_type != ET_EXEC or image.e_machine != EM_PI32V2:
        raise ValueError("requires a linked pi32v2 executable")
    entry, = struct.unpack_from("<I", elf_bytes, 24)
    if entry != FLASH or image.symbol_value("_start") != FLASH:
        raise ValueError("wrong diagnostic entry")
    unresolved = image.undefined_symbols()
    if unresolved:
        raise ValueError(f"unresolved providers: {sorted(unresolved)}")
    if not audit["passed"] or audit["n_pending"] or audit.get("runtime") != "sdk-free":
        raise ValueError("requires a complete passing SDK-free link audit")
    names = ("__data_begin", "__data_end", "__data_load", "__bss_begin",
             "__bss_end", "__stack_guard", "__stack_bottom", "__stack_top", "__flash_end")
    bounds = {name: image.symbol_value(name) for name in names}
    if any(value is None for value in bounds.values()):
        raise ValueError("missing diagnostic boundary symbols")
    if not (RAM <= bounds["__data_begin"] <= bounds["__data_end"] <= bounds["__bss_begin"]
            <= bounds["__bss_end"] <= bounds["__stack_guard"] < bounds["__stack_bottom"]
            < bounds["__stack_top"] <= RAM + BUDGET):
        raise ValueError("invalid or overlapping RAM ranges")
    if bounds["__stack_top"] - bounds["__stack_bottom"] != 4096 or bounds["__stack_top"] % 16:
        raise ValueError("wrong stack reservation or alignment")
    if bounds["__stack_bottom"] - bounds["__stack_guard"] != 16:
        raise ValueError("wrong stack guard reservation")
    length = bounds["__flash_end"] - FLASH
    if not 0 < length <= BUDGET or len(app) != length:
        raise ValueError("flat image does not match flash bounds")
    expected = bytearray(length)
    sections = []
    for section in image.sections:
        if not section["flags"] & 2 or not section["size"]:
            continue
        name, address, size = section["name"], section["addr"], section["size"]
        if name not in (".entry", ".text", ".data", ".bss", ".stack"):
            raise ValueError(f"unexpected allocated section: {name}")
        is_ram = name in (".data", ".bss", ".stack")
        lower = RAM if is_ram else FLASH
        if not lower <= address < address + size <= lower + BUDGET:
            raise ValueError(f"section outside its budget: {name}")
        if (section["flags"] & 1) != (1 if is_ram else 0) or (is_ram and section["flags"] & 4):
            raise ValueError(f"invalid section permissions: {name}")
        if section["type"] == SHT_PROGBITS:
            load = bounds["__data_load"] if name == ".data" else address
            offset = load - FLASH
            if not 0 <= offset <= offset + size <= length:
                raise ValueError(f"load bytes outside flash: {name}")
            expected[offset:offset + size] = elf_bytes[section["offset"]:section["offset"] + size]
        elif name not in (".bss", ".stack"):
            raise ValueError(f"missing file bytes: {name}")
        sections.append(dict(name=name, address=address, bytes=size))
    if bytes(expected) != app:
        raise ValueError("flat application differs from ELF load bytes")
    return dict(entry=entry, flash_bytes=length,
                data_bytes=bounds["__data_end"] - bounds["__data_begin"],
                bss_bytes=bounds["__bss_end"] - bounds["__bss_begin"],
                stack_bytes=4096, stack_guard_bytes=16,
                ram_reserved_bytes=bounds["__stack_top"] - RAM,
                ram_budget_bytes=BUDGET, unresolved_symbols=[], sdk_libraries=[],
                sections=sections, bounds=bounds,
                device_execution="unverified", package="not created")


if __name__ == "__main__":
    try:
        result = report(Path(sys.argv[1]).read_bytes(), Path(sys.argv[2]).read_bytes(),
                        json.loads(Path(sys.argv[3]).read_text()))
    except (ValueError, KeyError, IndexError) as exc:
        print(f"diagnostic_report: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2))

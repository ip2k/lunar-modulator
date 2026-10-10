#!/usr/bin/env python3
"""MIT. Compare an audited diagnostic ELF with pinned stock SPL RAM offline.

Only layout evidence is produced. Core, exception and TLB ownership remain
unresolved; no package, hardware operation or runtime safety approval follows.
"""
import argparse
import binascii
import hashlib
import json
import struct
import sys
from pathlib import Path

from audit_link import Elf, audit
from diagnostic_report import report, RAM
from package_guard import STOCK_SPL_SHA256, STOCK_SPL_SIZE

PROTECTED = (("boot_prefix", 0x01C7FE08, 0x01C7FE20),
             ("boot_header", 0x01C7FE20, 0x01C7FE40))
RAM_SECTIONS = {".data", ".bss", ".stack", ".ssp_stack"}


def stock_bank(spl):
    if len(spl) != STOCK_SPL_SIZE or hashlib.sha256(spl).hexdigest() != STOCK_SPL_SHA256:
        raise ValueError("unexpected stock SPL; requires exact FM-1 V15 pin")
    count, size, load, offset, crc, hcrc = struct.unpack("<HHIIHH", spl[:16])
    if (count, size, load, offset) != (1, 14368, 0x01C02000, 16):
        raise ValueError("unexpected stock SPL bank header")
    if binascii.crc_hqx(spl[:14], 0) != hcrc or binascii.crc_hqx(spl[offset:], 0) != crc:
        raise ValueError("stock SPL bank CRC mismatch")
    # The header is excluded from loaded body. Never add all file bytes to load.
    return dict(file_bytes=len(spl), header_bytes=offset, body_bytes=size,
                load_begin=load, load_end=load + size, sha256=STOCK_SPL_SHA256)


def range_end(begin, size):
    if type(begin) is not int or type(size) is not int or not (0 <= begin < begin + size <= 0x100000000):
        raise ValueError("malformed RAM range")
    return begin + size


def classify_ram(sections, bank):
    """Compare validated linked RAM sections; never infer complete ownership."""
    result = []
    for section in sections:
        name, begin, size = section["name"], section["address"], section["bytes"]
        if name not in RAM_SECTIONS or any(item["name"] == name for item in result):
            raise ValueError("unexpected or duplicate RAM section")
        end = range_end(begin, size)
        if any(begin < item["end"] and end > item["begin"] for item in result):
            raise ValueError("overlapping linked RAM sections")
        for label, protected_begin, protected_end in PROTECTED:
            if begin < protected_end and end > protected_begin:
                raise ValueError(f"RAM overlaps protected {label}")
        overlap = max(0, min(end, bank["load_end"]) - max(begin, bank["load_begin"]))
        result.append(dict(name=name, begin=begin, end=end, bytes=size,
                           loaded_spl_overlap_bytes=overlap,
                           ownership="unresolved"))
    if not result:
        raise ValueError("no linked RAM sections")
    return result


def inspect(elf_bytes, app, spl, profile="handover"):
    bank = stock_bank(spl)
    # Derive ranges from the linked ELF, never accept a caller-supplied JSON map.
    link = audit([("diagnostic.elf", Elf(elf_bytes))], [("diagnostic.bin", app)],
                 True, runtime="sdk-free")
    layout = report(elf_bytes, app, link, profile=profile)
    ram = classify_ram([s for s in layout["sections"] if s["name"] in RAM_SECTIONS], bank)
    # Include alignment gaps in the reserved budget as well as section bytes.
    classify_ram([dict(name=".stack", address=RAM, bytes=layout["ram_reserved_bytes"])], bank)
    return dict(status="layout-evidence-only", layout_verified=True,
                elf_sha256=hashlib.sha256(elf_bytes).hexdigest(),
                app_sha256=hashlib.sha256(app).hexdigest(), stock_bank=bank,
                layout=layout, ram_sections=ram,
                protected_ranges=[dict(name=n, begin=b, end=e) for n, b, e in PROTECTED],
                requires_nonreturning=any(s["loaded_spl_overlap_bytes"] for s in ram),
                private_ram_proven=False, device_execution="unverified",
                unresolved_runtime_gates=["core identity and secondary-core quiescence",
                    "exception vector routing and policy", "MMU/TLB ownership",
                    "final watchdog state", "clock/power and XIP/cache/SFC contract"],
                package_created=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--spl", required=True, help="decoded unpacked top/uboot.boot")
    parser.add_argument("--profile", choices=("inert", "handover"), default="handover")
    args = parser.parse_args()
    try:
        result = inspect(Path(args.elf).read_bytes(), Path(args.app).read_bytes(),
                         Path(args.spl).read_bytes(), args.profile)
    except (OSError, ValueError, KeyError, IndexError, struct.error) as exc:
        print(f"handover-layout: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

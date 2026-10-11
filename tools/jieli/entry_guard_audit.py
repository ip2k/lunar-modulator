#!/usr/bin/env python3
"""MIT. Exact, fail-closed audit of the instruction-only XIP entry guard.

The byte/operand contract was checked with the pinned JieLi 20250324.1
toolchain on Hera. This is intentionally a fixed program, not an ISA decoder:
any change requires independent listing/byte review and a new explicit pin.
The flat .entry export is the artifact; ELF program headers are not an
installation format. No installation or exception dispatch is authorized.
"""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from audit_link import Elf, EM_PI32V2, ET_EXEC, audit

FLASH = 0x02000120
EXPECTED_R0 = 0x01C7FE08
# offset, vendor bytes, exact vendor operation, branch target (when present).
INSTRUCTIONS = (
    (0, "6000", "cli", None),
    (2, "64e00016", "r1 = cnum", None),
    (6, "8147", "if (r1 != 0) goto 14", FLASH + 22),
    (8, "c2ff08fec701", "r2 = 29883912", None),
    (14, "82e80200", "if (r0 != r2) goto 4", FLASH + 22),
    (18, "6000", "cli", None),
    (20, "f79e", "goto -4", FLASH + 18),
    (22, "6000", "cli", None),
    (24, "f79e", "goto -4", FLASH + 22),
)
EXPECTED_APP = b"".join(bytes.fromhex(row[1]) for row in INSTRUCTIONS)
SYMBOLS = dict(_start=FLASH, lunar_entry_accepted_stop=FLASH + 18,
               lunar_entry_rejected_stop=FLASH + 22, __flash_end=FLASH + 26)
# Exact observed pinned-vendor ELF32 section table. Alignment values are the
# vendor's values, not inferred conventional defaults.
SECTION_HEADERS = (
    (0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
    (27, 1, 6, FLASH, 800, 26, 0, 0, 1, 0),
    (17, 3, 0, 0, 996, 34, 0, 0, 1, 0),
    (1, 2, 0, 0, 828, 96, 4, 2, 4, 16),
    (9, 3, 0, 0, 924, 72, 0, 0, 1, 0),
)
ROW = re.compile(r"^\s*([0-9a-fA-F]+):\s*((?:[0-9a-fA-F]{2}\s+)+)(\S.*?)\s*$")
TARGET = re.compile(r"^<[^<>:]+\s*:\s*([0-9a-fA-F]+)\s*>$")


def audit_listing(listing, app):
    """Require one vendor row per pinned instruction and complete byte coverage."""
    rows = []
    sections = []
    for line in listing.splitlines():
        if line.startswith("Disassembly of section "):
            sections.append(line)
        match = ROW.fullmatch(line)
        if match:
            address, encoded, operation = match.groups()
            rows.append((int(address, 16), bytes.fromhex(encoded), operation))
        elif re.match(r"^\s*[0-9a-fA-F]+:", line):
            raise ValueError("unparsed vendor instruction row")
    if sections != ["Disassembly of section .entry:"] or len(rows) != len(INSTRUCTIONS):
        raise ValueError("unexpected listing section or instruction count")
    covered = bytearray()
    for row, (offset, encoded, operation, target) in zip(rows, INSTRUCTIONS):
        address, blob, text = row
        if address != FLASH + offset or blob != bytes.fromhex(encoded):
            raise ValueError("unexpected instruction address or bytes")
        parts = text.split("<", 1)
        actual_operation = " ".join(parts[0].split())
        if actual_operation != operation:
            raise ValueError("unexpected vendor instruction operation")
        if target is None:
            if len(parts) != 1:
                raise ValueError("unexpected instruction annotation")
        else:
            annotation = TARGET.fullmatch("<" + parts[1]) if len(parts) == 2 else None
            if annotation is None or int(annotation[1], 16) != target:
                raise ValueError("unexpected branch target; foreign fallthrough rejected")
        covered.extend(blob)
    if bytes(covered) != app:
        raise ValueError("vendor listing differs from flat bytes")


def report(elf_bytes, app, listing, link_audit):
    if (elf_bytes[:16] != bytes.fromhex("7f454c46010101000000000000000000")
            or struct.unpack_from("<I", elf_bytes, 20)[0] != 1
            or struct.unpack_from("<I", elf_bytes, 36)[0] != 0
            or struct.unpack_from("<H", elf_bytes, 40)[0] != 52):
        raise ValueError("unexpected ELF header metadata")
    image = Elf(elf_bytes)
    if image.e_type != ET_EXEC or image.e_machine != EM_PI32V2:
        raise ValueError("requires a linked pi32v2 executable")
    if struct.unpack_from("<I", elf_bytes, 24)[0] != FLASH:
        raise ValueError("wrong entry")
    if app != EXPECTED_APP:
        raise ValueError("unexpected linked program bytes or length")
    if image.undefined_symbols() or image.relocation_symbol_names():
        raise ValueError("unresolved or relocated program")
    if (link_audit.get("passed") is not True or link_audit.get("n_pending") != 0
            or link_audit.get("n_fail") != 0
            or link_audit.get("runtime") != "sdk-free"):
        raise ValueError("requires passing complete SDK-free link audit")
    hashes = dict(elf=hashlib.sha256(elf_bytes).hexdigest(),
                  app=hashlib.sha256(app).hexdigest())
    if link_audit.get("artifact_sha256") != hashes:
        raise ValueError("link audit receipt does not match ELF/app hashes")
    # Recheck linked bytes/symbols here rather than accepting a supplied summary.
    checked = audit([("diagnostic.elf", image)], [("diagnostic.bin", app)],
                    True, [], runtime="sdk-free")
    if {key: value for key, value in link_audit.items()
            if key != "artifact_sha256"} != checked:
        raise ValueError("link audit receipt differs from current linked audit")
    for name, value in SYMBOLS.items():
        if image.symbol_value(name) != value:
            raise ValueError("wrong entry/stop/end symbol: " + name)
    seen = set()
    for symbol in image.symbols:
        if symbol["name"]:
            if symbol["name"] in seen:
                raise ValueError("duplicate linked symbol: " + symbol["name"])
            seen.add(symbol["name"])
        if symbol["name"] and symbol["name"] not in {*SYMBOLS, ".entry"}:
            raise ValueError("unexpected linked symbol: " + symbol["name"])
        if symbol["name"] == "_start" and (symbol["type"] != 2 or symbol["size"] != 26):
            raise ValueError("wrong entry function extent")
    allocated = [section for section in image.sections if section["flags"] & 2]
    if len(allocated) != 1:
        raise ValueError("unexpected allocated section; no RAM/stack permitted")
    section = allocated[0]
    if (section["name"], section["addr"], section["size"], section["flags"], section["type"]) != (
            ".entry", FLASH, 26, 6, 1):
        raise ValueError("invalid entry section layout/permissions")
    phoff = struct.unpack_from("<I", elf_bytes, 28)[0]
    phentsize, phnum = struct.unpack_from("<HH", elf_bytes, 42)
    if phoff != 52 or phentsize != 32 or phnum != 1:
        raise ValueError("unexpected ELF program header table")
    header = struct.unpack_from("<IIIIIIII", elf_bytes, phoff)
    # Exact vendor PHDRS layout; 0x320 offset excludes the header/padding from
    # the load, and is congruent with FLASH modulo the vendor 0x500 alignment.
    if section["offset"] != 0x320 or header != (1, 0x320, FLASH, FLASH, 26, 26, 5, 0x500):
        raise ValueError("unexpected ELF load mapping/permissions")
    if section["offset"] < phoff + phentsize or section["offset"] + 26 > len(elf_bytes):
        raise ValueError("ELF load mapping overlaps headers or exceeds file")
    for item in image.sections:
        if item["name"] not in ("", ".entry", ".shstrtab", ".strtab", ".symtab"):
            raise ValueError("unexpected ELF section: " + item["name"])
        if item is not section and item["flags"] & 7:
            raise ValueError("unexpected executable/writable metadata")
    shoff = struct.unpack_from("<I", elf_bytes, 32)[0]
    geometry = struct.unpack_from("<HHH", elf_bytes, 46)
    if (shoff, geometry, len(elf_bytes)) != (1032, (40, 5, 2), 1232):
        raise ValueError("unexpected ELF section table geometry")
    headers = tuple(struct.unpack_from("<IIIIIIIIII", elf_bytes, shoff + i * 40)
                    for i in range(5))
    if headers != SECTION_HEADERS:
        raise ValueError("unexpected ELF section metadata/layout")
    if image.read(FLASH, 26) != app:
        raise ValueError("flat bytes differ from ELF")
    audit_listing(listing, app)
    return dict(profile="entry-guard", passed=True, hardware_ready=False,
                entry=FLASH, flash_bytes=26, instruction_count=9,
                expected_core=0, expected_r0=EXPECTED_R0, r0_preserved=True,
                accepted_stop=FLASH + 18, rejected_stop=FLASH + 22,
                ram_reserved_bytes=0, stack_bytes=0, board_output=False,
                exception_dispatch_installed=False, package_created=False,
                device_execution="unverified", runtime="sdk-free",
                activation_gates=["ordinary-entry privilege/CLI/cnum semantics",
                                  "secondary-core ownership/quiescence",
                                  "SSP/protection/bootstrap RAM ownership",
                                  "exception dispatch and nested faults",
                                  "physical recovery and external result"],
                app_sha256=hashlib.sha256(app).hexdigest(),
                elf_sha256=hashlib.sha256(elf_bytes).hexdigest(),
                listing_sha256=hashlib.sha256(listing.encode()).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--listing", type=Path, required=True)
    parser.add_argument("--link-audit", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = report(args.elf.read_bytes(), args.app.read_bytes(),
                        args.listing.read_text(), json.loads(args.link_audit.read_text()))
    except (ValueError, KeyError, IndexError, struct.error, OSError) as exc:
        parser.exit(1, f"entry_guard_audit: {exc}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

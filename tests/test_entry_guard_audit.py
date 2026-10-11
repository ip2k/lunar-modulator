"""Exact no-stack entry audit: synthetic ELF corruption and vendor-row mutations."""
import hashlib
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/jieli"))
from entry_guard_audit import EXPECTED_APP, FLASH, INSTRUCTIONS, SYMBOLS, report as strict_report
from diagnostic_report import layout_profile
from audit_link import Elf, audit as audit_link

AUDIT = dict(passed=True, n_fail=0, n_pending=0, runtime="sdk-free")


def listing(app=EXPECTED_APP):
    rows = ["Disassembly of section .entry:", "_start:"]
    for offset, encoded, operation, target in INSTRUCTIONS:
        blob = app[offset:offset + len(bytes.fromhex(encoded))]
        annotation = f" <stop : {target:x} >" if target is not None else ""
        rows.append(f" {FLASH + offset:x}: {blob.hex(' ')}\t{operation}{annotation}")
    return "\n".join(rows) + "\n"


def fixture(app=EXPECTED_APP, *, changes=None, extra=False):
    """Own compact ELF fixture with exact entry bytes; no vendor artifact required."""
    sections = [(".entry", 1, 6, FLASH, app)]
    if extra:
        sections.append((".stack", 8, 3, 0x01C02000, b""))
    names = b"\0.symtab\0.strtab\0.shstrtab\0.entry\0"
    name_offsets = {name: names.index(name.encode())
                    for name in [".entry", ".shstrtab", ".symtab", ".strtab"]}
    if extra:
        name_offsets[".stack"] = len(names)
        names += b".stack\0"
    symbol_names = b"\0"
    symbols = bytearray(16)
    symbols += struct.pack("<IIIBBH", 0, FLASH, 0, 3, 0, 1)
    values = {name: SYMBOLS[name] for name in
              ["lunar_entry_rejected_stop", "lunar_entry_accepted_stop", "_start", "__flash_end"]}
    values.update(changes or {})
    for name, value in values.items():
        symbols += struct.pack("<IIIBBH", len(symbol_names), value,
                               26 if name == "_start" else 0,
                               0x12 if name == "_start" else 0x10, 0, 1)
        symbol_names += name.encode() + b"\0"
    body = bytearray(0x320)
    headers = bytearray(40)
    for name, kind, flags, address, blob in sections:
        headers += struct.pack("<IIIIIIIIII", name_offsets[name], kind, flags,
                               address, len(body), len(blob), 0, 0, 1, 0)
        body += blob
    body += bytes((-len(body)) % 4)
    symoff = len(body); body += symbols
    stroff = len(body); body += symbol_names
    nameoff = len(body); body += names
    for name, off, size, kind, link, info, align, entsize in (
            (".shstrtab", nameoff, len(names), 3, 0, 0, 1, 0),
            (".symtab", symoff, len(symbols), 2, len(sections) + 3, 2, 4, 16),
            (".strtab", stroff, len(symbol_names), 3, 0, 0, 1, 0)):
        headers += struct.pack("<IIIIIIIIII", name_offsets[name], kind, 0, 0,
                               off, size, link, info, align, entsize)
    body += bytes((-len(body)) % 4)
    body[:52] = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8) + struct.pack(
        "<HHIIIIIHHHHHH", 2, 0xF1, 1, FLASH, 52, len(body), 0, 52, 32, 1,
        40, len(sections) + 4, len(sections) + 1)
    body[52:84] = struct.pack("<IIIIIIII", 1, 0x320, FLASH, FLASH, len(app), len(app), 5, 0x500)
    return bytes(body + headers)


def receipt(elf, app=EXPECTED_APP):
    value = audit_link([("diagnostic.elf", Elf(elf))], [("diagnostic.bin", app)],
                       True, [], runtime="sdk-free")
    value["artifact_sha256"] = dict(elf=hashlib.sha256(elf).hexdigest(),
                                    app=hashlib.sha256(app).hexdigest())
    return value


def report(elf, app, text, summary):
    # Each structural corruption gets a fresh bound receipt so that a stale
    # hash does not obscure the independent ELF/instruction failure under test.
    value = receipt(elf, app)
    value.update(summary)
    return strict_report(elf, app, text, value)


def test_exact_program_and_closed_activation():
    result = report(fixture(), EXPECTED_APP, listing(), AUDIT)
    assert result["passed"] and result["r0_preserved"]
    assert result["instruction_count"] == 9 and result["flash_bytes"] == 26
    assert result["accepted_stop"] != result["rejected_stop"]
    assert not result["hardware_ready"] and not result["exception_dispatch_installed"]
    assert not result["board_output"] and not result["package_created"]
    assert result["stack_bytes"] == result["ram_reserved_bytes"] == 0
    assert result["device_execution"] == "unverified"


@pytest.mark.parametrize("offset", range(26))
def test_every_linked_byte_is_pinned_even_with_consistent_forged_artifacts(offset):
    app = bytearray(EXPECTED_APP)
    app[offset] ^= 1
    with pytest.raises(ValueError, match="program bytes"):
        report(fixture(app), bytes(app), listing(app), AUDIT)


@pytest.mark.parametrize("damaged", [EXPECTED_APP[:-2], EXPECTED_APP + b"\x00\x00",
    # STI, call, store, stack write and return cannot replace even the first row.
    bytes.fromhex("7000") + EXPECTED_APP[2:],
    bytes.fromhex("80ff00000000") + EXPECTED_APP[6:],
    bytes.fromhex("8060") + EXPECTED_APP[2:],
    bytes.fromhex("64e0801e") + EXPECTED_APP[4:],
    bytes.fromhex("a000") + EXPECTED_APP[2:]])
def test_dangerous_or_additional_code_rejected(damaged):
    with pytest.raises(ValueError, match="program bytes"):
        report(fixture(damaged), damaged, listing(damaged), AUDIT)


@pytest.mark.parametrize("old,new", [
    ("cli", "sti"), ("r1 = cnum", "r0 = cnum"),
    ("r2 = 29883912", "r2 = [r0]"),
    ("if (r1 != 0)", "if (r1 == 0)"),
    ("if (r0 != r2)", "if (r0 == r2)"),
    ("goto -4", "call -4"), ("goto -4", "rts"),
    ("2000136 >", "ffc00000 >"), ("2000132 >", "2000136 >"),
    ("60 00", "60 01"), ("2000120:", "200011e:"),
    ("section .entry:", "section .text:"),
])
def test_untrusted_vendor_listing_cannot_override_linked_contract(old, new):
    with pytest.raises(ValueError):
        report(fixture(), EXPECTED_APP, listing().replace(old, new, 1), AUDIT)


@pytest.mark.parametrize("damage", ["missing", "duplicate", "extra_section", "unparsed"])
def test_listing_requires_exact_order_and_full_coverage(damage):
    rows = listing().splitlines()
    if damage == "missing":
        rows.pop(4)
    elif damage == "duplicate":
        rows.insert(3, rows[2])
    elif damage == "extra_section":
        rows += ["Disassembly of section .text:"]
    else:
        rows += [" 200013a: <unknown instruction>"]
    with pytest.raises(ValueError):
        report(fixture(), EXPECTED_APP, "\n".join(rows), AUDIT)


@pytest.mark.parametrize("name", SYMBOLS)
def test_entry_stop_and_extent_symbols_are_pinned(name):
    with pytest.raises(ValueError, match="symbol"):
        report(fixture(changes={name: SYMBOLS[name] + 2}), EXPECTED_APP, listing(), AUDIT)


@pytest.mark.parametrize("field,value", [(24, FLASH + 2), (16, 1), (18, 0),
                                       ("flags", 7), ("address", FLASH + 2), ("size", 28)])
def test_elf_entry_permissions_machine_and_extent_fail_closed(field, value):
    elf = bytearray(fixture())
    shoff = struct.unpack_from("<I", elf, 32)[0]
    if isinstance(field, str):
        field = shoff + 40 + {"flags": 8, "address": 12, "size": 20}[field]
        fmt = "<I"
    else:
        fmt = "<I" if field == 24 else "<H"
    struct.pack_into(fmt, elf, field, value)
    with pytest.raises(ValueError):
        report(bytes(elf), EXPECTED_APP, listing(), AUDIT)


def test_no_extra_ram_or_foreign_symbol_and_flat_corruption():
    with pytest.raises(ValueError, match="allocated section"):
        report(fixture(extra=True), EXPECTED_APP, listing(), AUDIT)
    with pytest.raises(ValueError, match="symbol"):
        report(fixture(changes={"foreign_vendor_helper": 0xFFC00000}), EXPECTED_APP, listing(), AUDIT)
    elf = bytearray(fixture())
    elf[0x320] ^= 1
    with pytest.raises(ValueError, match="ELF"):
        report(bytes(elf), EXPECTED_APP, listing(), AUDIT)


@pytest.mark.parametrize("audit", [dict(AUDIT, passed=False), dict(AUDIT, passed=1),
                                   dict(AUDIT, n_pending=1), dict(AUDIT, n_fail=1),
                                   dict(AUDIT, runtime="sdk")])
def test_incomplete_or_foreign_link_audit_rejected(audit):
    with pytest.raises(ValueError, match="link audit"):
        report(fixture(), EXPECTED_APP, listing(), audit)


def test_entry_guard_cannot_use_existing_package_or_raw_layout_profiles():
    with pytest.raises(ValueError, match="unknown diagnostic profile"):
        layout_profile("entry-guard")


@pytest.mark.parametrize("field,value", [(28, 0), (28, 56), (42, 0), (42, 64),
                                       (44, 0), (44, 2)])
def test_program_header_table_must_be_exact(field, value):
    elf = bytearray(fixture())
    struct.pack_into("<I" if field == 28 else "<H", elf, field, value)
    with pytest.raises(ValueError, match="program header"):
        report(bytes(elf), EXPECTED_APP, listing(), AUDIT)


@pytest.mark.parametrize("field,value", [(0, 0), (4, 0), (8, 0x01c02000),
    (12, 0x01c02000), (16, 28), (20, 28), (24, 7), (28, 4)])
def test_extra_ram_header_load_writes_and_wrong_mapping_rejected(field, value):
    elf = bytearray(fixture())
    struct.pack_into("<I", elf, 52 + field, value)
    with pytest.raises(ValueError, match="load mapping"):
        report(bytes(elf), EXPECTED_APP, listing(), AUDIT)


@pytest.mark.parametrize("kind", ["elf", "app", "missing", "swapped", "summary"])
def test_link_receipt_binds_current_artifacts_and_recomputes_checks(kind):
    elf = fixture()
    bound = receipt(elf)
    if kind in ("elf", "app"):
        bound["artifact_sha256"][kind] = "0" * 64
    elif kind == "missing":
        del bound["artifact_sha256"]
    elif kind == "swapped":
        bound["artifact_sha256"] = receipt(fixture(extra=True))["artifact_sha256"]
    else:
        bound["checks"][0]["detail"] = "stale passing receipt"
    with pytest.raises(ValueError, match="link audit receipt"):
        strict_report(elf, EXPECTED_APP, listing(), bound)


@pytest.mark.parametrize("field,fmt,value", [(6, "B", 0), (7, "B", 3), (8, "B", 1),
    (20, "I", 0), (36, "I", 0xffffffff), (40, "H", 0),
    (32, "I", 1036), (46, "H", 44), (48, "H", 4), (50, "H", 4)])
def test_elf_header_and_table_geometry_are_pinned_with_fresh_receipt(field, fmt, value):
    elf = bytearray(fixture())
    bound = receipt(bytes(elf))
    struct.pack_into("<" + fmt, elf, field, value)
    bound["artifact_sha256"]["elf"] = hashlib.sha256(elf).hexdigest()
    with pytest.raises((ValueError, struct.error, IndexError)):
        strict_report(bytes(elf), EXPECTED_APP, listing(), bound)


@pytest.mark.parametrize("section,field,value", [(0, 20, 1), (1, 32, 4),
    (2, 4, 1), (2, 20, 33), (3, 28, 1), (3, 32, 1), (4, 32, 4)])
def test_fixed_metadata_section_geometry_rejects_mutations(section, field, value):
    elf = bytearray(fixture())
    struct.pack_into("<I", elf, 1032 + section * 40 + field, value)
    with pytest.raises(ValueError):
        report(bytes(elf), EXPECTED_APP, listing(), AUDIT)

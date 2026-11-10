"""The `ram` profile of tools/jieli/diagnostic_report.py (firmware/m5/app.ld),
on synthetic ELFs: no target code and no vendor binaries."""
import pathlib
import struct
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools/jieli"
sys.path.insert(0, str(TOOLS))
from diagnostic_report import report, RAM  # noqa: E402

AUDIT = dict(passed=True, n_pending=0, runtime="sdk-free")
IMAGE = b"\x60\x00\x80\x00LUNA"


def ram_fixture(boundary_changes=None, section_changes=None, entry=RAM, extra=()):
    sections = [[".image", RAM, IMAGE, 8, 1, 7],
                [".bss", RAM + 8, b"", 24, 8, 3],
                [".stack", RAM + 32, b"", 4112, 8, 3],
                [".ssp_stack", RAM + 4144, b"", 4112, 8, 3]]
    sections += [list(row) for row in extra]
    for index, column, value in section_changes or ():
        sections[index][column] = value
    bounds = dict(_start=RAM, __image_end=RAM + 8, __bss_begin=RAM + 8, __bss_end=RAM + 32,
                  __stack_guard=RAM + 32, __stack_bottom=RAM + 48, __stack_top=RAM + 4144,
                  __ssp_guard=RAM + 4144, __ssp_bottom=RAM + 4160, __ssp_top=RAM + 8256)
    bounds.update(boundary_changes or {})
    strings, names = b"\0", {}
    for name in [row[0] for row in sections] + [".shstrtab", ".strtab", ".symtab"]:
        names[name] = len(strings)
        strings += name.encode() + b"\0"
    symbols, symbol_names = bytearray(16), b"\0"
    for name, value in bounds.items():
        symbols += struct.pack("<IIIBBH", len(symbol_names), value, 0, 0x10, 0, 1)
        symbol_names += name.encode() + b"\0"
    body, headers = bytearray(52), bytearray(40)
    for name, address, blob, size, kind, flags in sections:
        headers += struct.pack("<IIIIIIIIII", names[name], kind, flags, address,
                               len(body), size, 0, 0, 4, 0)
        body += blob
    for name, blob, kind, link, entry_size in (
            (".shstrtab", strings, 3, 0, 0), (".strtab", symbol_names, 3, 0, 0),
            (".symtab", bytes(symbols), 2, len(sections) + 2, 16)):
        headers += struct.pack("<IIIIIIIIII", names[name], kind, 0, 0,
                               len(body), len(blob), link, 0, 1, entry_size)
        body += blob
    header = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8)
    header += struct.pack("<HHIIIIIHHHHHH", 2, 0xF1, 1, entry, 0, len(body), 0,
                          52, 0, 0, 40, len(sections) + 4, len(sections) + 1)
    body[:52] = header
    return bytes(body + headers)


def test_valid_ram_image():
    result = report(ram_fixture(), IMAGE, AUDIT, "ram")
    assert result["profile"] == "ram" and result["entry"] == RAM
    assert result["image_bytes"] == 8 and result["ram_reserved_bytes"] == 8256
    assert [s["name"] for s in result["sections"]] == [".image", ".bss", ".stack", ".ssp_stack"]
    assert result["device_execution"] == "unverified"


def test_empty_bss_is_allowed():
    elf = ram_fixture(dict(__bss_end=RAM + 8), [(1, 3, 0)])
    assert report(elf, IMAGE, AUDIT, "ram")["bss_bytes"] == 0


@pytest.mark.parametrize("kwargs,app,message", [
    (dict(entry=RAM + 2), IMAGE, "entry"),
    (dict(boundary_changes=dict(_start=RAM + 2)), IMAGE, "entry"),
    ({}, IMAGE[:4], "flat image"),
    ({}, IMAGE[:4] + b"XXXX", "differs"),
    (dict(boundary_changes=dict(__ssp_top=RAM + 0x4010, __ssp_bottom=RAM + 0x3010,
                                __ssp_guard=RAM + 0x3000)), IMAGE, "overlapping"),  # past the 16 KiB budget
    (dict(boundary_changes=dict(__ssp_top=RAM + 0x4010, __ssp_bottom=RAM + 0x3010,
                                __ssp_guard=RAM + 0x3000, __stack_top=RAM + 0x3000)),
     IMAGE, "overlapping"),
    (dict(boundary_changes=dict(__stack_bottom=RAM + 40)), IMAGE, "stack"),
    (dict(section_changes=[(0, 5, 3)]), IMAGE, "executable"),
    (dict(section_changes=[(0, 4, 8)]), IMAGE, "PROGBITS"),
    (dict(section_changes=[(2, 5, 7)]), IMAGE, "NOBITS"),
    (dict(section_changes=[(2, 1, RAM + 36)]), IMAGE, "boundary"),
    (dict(extra=[(".text", RAM + 0x3800, b"", 4, 8, 6)]), IMAGE, "unexpected"),
])
def test_rejects_damaged_ram_layout(kwargs, app, message):
    with pytest.raises(ValueError, match=message):
        report(ram_fixture(**kwargs), app, AUDIT, "ram")


def test_requires_complete_sdk_free_audit():
    for audit in (dict(AUDIT, passed=False), dict(AUDIT, n_pending=1), dict(AUDIT, runtime="sdk")):
        with pytest.raises(ValueError, match="audit"):
            report(ram_fixture(), IMAGE, audit, "ram")


def high_stacks(ssp_top):
    """The fixture with its stacks moved up so the reservation ends at ssp_top."""
    stack_guard = ssp_top - 2 * 4112
    bounds = dict(__bss_end=stack_guard, __stack_guard=stack_guard,
                  __stack_bottom=stack_guard + 16, __stack_top=stack_guard + 4112,
                  __ssp_guard=stack_guard + 4112, __ssp_bottom=stack_guard + 4128,
                  __ssp_top=ssp_top)
    sections = [(1, 3, stack_guard - RAM - 8), (2, 1, stack_guard), (3, 1, stack_guard + 4112)]
    return ram_fixture(bounds, sections)


def test_ram_window_profile_allows_the_whole_rom_window():
    # M6 (firmware/m6/app.ld): up to 0x01C07E00, the 24,064-byte ROM window
    elf = high_stacks(RAM + 24064)
    result = report(elf, IMAGE, AUDIT, "ram-window")
    assert result["profile"] == "ram-window" and result["ram_budget_bytes"] == 24064
    assert result["ram_reserved_bytes"] == 24064
    with pytest.raises(ValueError, match="overlapping"):
        report(elf, IMAGE, AUDIT, "ram")          # M5's 16 KiB stays the M5 bound


def test_ram_window_profile_stops_at_the_window_end():
    with pytest.raises(ValueError, match="overlapping"):
        report(high_stacks(RAM + 24064 + 16), IMAGE, AUDIT, "ram-window")

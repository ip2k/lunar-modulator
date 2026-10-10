"""Reject damaged link layouts and exports without requiring vendor binaries."""
import pathlib
import importlib.util
import struct
import sys

import pytest

TOOLS = pathlib.Path(__file__).resolve().parents[1] / "tools/jieli"
sys.path.insert(0, str(TOOLS))
from diagnostic_report import report, FLASH, RAM  # noqa: E402
from diagnostic_flat import assemble  # noqa: E402
from audit_link import Elf  # noqa: E402


def fixture(handover=False, boundary_changes=None):
    """Small synthetic ELF with the same load/RAM contract, no target code."""
    sections = [(".entry", FLASH, b"\x60\x00", 2, 1, 6),
                (".text", FLASH + 2, b"\x80\x00", 2, 1, 6),
                (".data", RAM, b"LUNA", 4, 1, 3),
                (".bss", RAM + 4, b"", 24, 8, 3),
                (".stack", RAM + 32, b"", 4112, 8, 3)]
    boundaries = dict(_start=FLASH, __data_begin=RAM, __data_end=RAM + 4,
                      __data_load=FLASH + 4, __flash_end=FLASH + 8,
                      __bss_begin=RAM + 4, __bss_end=RAM + 28,
                      __stack_guard=RAM + 32, __stack_bottom=RAM + 48,
                      __stack_top=RAM + 4144)
    if handover:
        sections.append((".ssp_stack", RAM + 4144, b"", 4112, 8, 3))
        boundaries.update(__ssp_guard=RAM + 4144, __ssp_bottom=RAM + 4160,
                          __ssp_top=RAM + 8256)
    boundaries.update(boundary_changes or {})
    strings = b"\0"
    names = {}
    for name in [row[0] for row in sections] + [".shstrtab", ".strtab", ".symtab"]:
        names[name] = len(strings)
        strings += name.encode() + b"\0"
    symbols = bytearray(16)
    symbol_names = b"\0"
    for name, value in boundaries.items():
        symbols += struct.pack("<IIIBBH", len(symbol_names), value, 0, 0x10, 0, 1)
        symbol_names += name.encode() + b"\0"
    body = bytearray(52)
    headers = bytearray(40)
    for name, address, blob, size, kind, flags in sections:
        headers += struct.pack("<IIIIIIIIII", names[name], kind, flags, address,
                               len(body), size, 0, 0, 4, 0)
        body += blob
    for name, blob, kind, link, entry_size in (
            (".shstrtab", strings, 3, 0, 0),
            (".strtab", symbol_names, 3, 0, 0),
            (".symtab", bytes(symbols), 2, len(sections) + 2, 16)):
        headers += struct.pack("<IIIIIIIIII", names[name], kind, 0, 0,
                               len(body), len(blob), link, 0, 1, entry_size)
        body += blob
    header = b"\x7fELF" + bytes([1, 1, 1, 0]) + bytes(8)
    header += struct.pack("<HHIIIIIHHHHHH", 2, 0xF1, 1, FLASH, 0, len(body), 0,
                          52, 0, 0, 40, len(sections) + 4, len(sections) + 1)
    body[:52] = header
    return bytes(body + headers), b"\x60\x00\x80\x00LUNA"


AUDIT = dict(passed=True, n_pending=0, runtime="sdk-free")


def test_valid_layout_and_vendor_fragments():
    elf, app = fixture()
    result = report(elf, app, AUDIT)
    assert result["flash_bytes"] == 8 and result["ram_reserved_bytes"] == 4144
    assert assemble(Elf(elf), dict(entry=app[:2], text=app[2:4], data=app[4:])) == app


@pytest.mark.parametrize("offset,value,message", [
    (24, FLASH + 2, "entry"),
    # Section flags and addresses in the second allocated section.
    ("text_flags", 3, "permissions"),
    ("text_addr", FLASH, "overlapping"),
    ("stack_addr", RAM + 0x4000, "budget"),
    ("stack_addr", RAM + 4, "boundary"),
    ("stack_size", 32, "boundary"),
    ("data_type", 8, "missing file"),
])
def test_rejects_mutated_link_contract(offset, value, message):
    elf, app = fixture()
    changed = bytearray(elf)
    shoff, = struct.unpack_from("<I", elf, 32)
    fields = dict(text_flags=shoff + 2 * 40 + 8, text_addr=shoff + 2 * 40 + 12,
                  stack_addr=shoff + 5 * 40 + 12, stack_size=shoff + 5 * 40 + 20,
                  data_type=shoff + 3 * 40 + 4)
    struct.pack_into("<I", changed, fields.get(offset, offset), value)
    with pytest.raises(ValueError, match=message):
        report(bytes(changed), app, AUDIT)


def test_rejects_corrupt_flat_image_and_incomplete_audit():
    elf, app = fixture()
    with pytest.raises(ValueError, match="differs"):
        report(elf, app[:-1] + b"!", AUDIT)
    with pytest.raises(ValueError, match="audit"):
        report(elf, app, dict(AUDIT, n_pending=1))
    with pytest.raises(ValueError, match="export"):
        assemble(Elf(elf), dict(entry=app[:2], text=app[2:4], data=app[4:-1]))


def test_rejects_missing_required_section():
    elf, app = fixture()
    changed = bytearray(elf)
    shoff, = struct.unpack_from("<I", elf, 32)
    # Clear SHF_ALLOC on BSS: cookie globals must not quietly disappear.
    struct.pack_into("<I", changed, shoff + 4 * 40 + 8, 0)
    with pytest.raises(ValueError, match="required"):
        report(bytes(changed), app, AUDIT)


def test_handover_layout_is_explicit_and_separate_from_default():
    elf, app = fixture(handover=True)
    result = report(elf, app, AUDIT, profile="handover")
    assert result["ram_reserved_bytes"] == 8256
    assert result["ssp_stack_bytes"] == 4096 and result["ssp_guard_bytes"] == 16
    with pytest.raises(ValueError, match="unexpected allocated"):
        report(elf, app, AUDIT)
    with pytest.raises(ValueError, match="profile"):
        report(elf, app, AUDIT, profile="unknown")
    elf, app = fixture()
    with pytest.raises(ValueError, match="boundary"):
        report(elf, app, AUDIT, profile="handover")


@pytest.mark.parametrize("field,value,message", [(12, RAM + 32, "boundary"),
                                                (20, 16, "boundary"),
                                                (8, 7, "permissions"),
                                                (4, 1, "NOBITS")])
def test_ssp_section_rejects_overlap_size_permissions_and_file_bytes(field, value, message):
    elf, app = fixture(handover=True)
    changed = bytearray(elf)
    shoff, = struct.unpack_from("<I", elf, 32)
    struct.pack_into("<I", changed, shoff + 6 * 40 + field, value)
    with pytest.raises(ValueError, match=message):
        report(bytes(changed), app, AUDIT, profile="handover")


@pytest.mark.parametrize("changes", [{"__ssp_guard": RAM + 32},
                                    {"__ssp_bottom": RAM + 4161},
                                    {"__ssp_top": RAM + 16385}])
def test_ssp_boundary_reservations_fail_closed(changes):
    elf, app = fixture(handover=True, boundary_changes=changes)
    with pytest.raises(ValueError, match="SSP reservation"):
        report(elf, app, AUDIT, profile="handover")


def test_staging_fails_closed_without_overwriting_or_partial_output(tmp_path):
    spec = importlib.util.spec_from_file_location("stage_diagnostic", TOOLS / "stage-diagnostic.py")
    staging = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(staging)
    elf, app = fixture()
    elf_path, app_path = tmp_path / "diagnostic.elf", tmp_path / "diagnostic.bin"
    elf_path.write_bytes(elf)
    app_path.write_bytes(app)
    destination = tmp_path / "output"
    with pytest.raises(ValueError, match="stock reference"):
        staging.stage(tmp_path / "missing-stock", elf_path, app_path, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob(".diagnostic-stage-*"))

    app_path.write_bytes(app[:-1] + b"!")
    with pytest.raises(ValueError, match="differs"):
        staging.stage(tmp_path / "missing-stock", elf_path, app_path, destination)
    assert not destination.exists()

    destination.mkdir()
    marker = destination / "keep"
    marker.write_bytes(b"existing result")
    with pytest.raises(ValueError, match="already exists"):
        staging.stage(tmp_path / "missing-stock", elf_path, app_path, destination)
    assert marker.read_bytes() == b"existing result"

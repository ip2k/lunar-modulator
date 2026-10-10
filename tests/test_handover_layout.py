"""Offline stock-bank and linked-RAM evidence; no device or vendor fixture required."""
import binascii
import hashlib
import os
from pathlib import Path
import struct
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools/jieli"))
import handover_layout as layout  # noqa: E402
from tests.test_diagnostic_report import fixture  # noqa: E402


def synthetic_bank():
    body = bytes(14368)
    header = struct.pack("<HHIIH", 1, len(body), 0x01C02000, 16,
                         binascii.crc_hqx(body, 0))
    return header + struct.pack("<H", binascii.crc_hqx(header, 0)) + body


def pin_for_test(monkeypatch, blob):
    # Only tests replace the module constant. The CLI has no alternate-pin switch.
    monkeypatch.setattr(layout, "STOCK_SPL_SHA256", hashlib.sha256(blob).hexdigest())


def section(begin, size, name=".stack"):
    return dict(name=name, address=begin, bytes=size)


def test_header_is_not_loaded_and_exact_end_intersection(monkeypatch):
    blob = synthetic_bank()
    pin_for_test(monkeypatch, blob)
    bank = layout.stock_bank(blob)
    assert (bank["header_bytes"], bank["body_bytes"], bank["load_end"]) == (16, 14368, 0x01C05820)
    assert bank["load_end"] != bank["load_begin"] + len(blob)
    result = layout.classify_ram([section(bank["load_end"] - 8, 24)], bank)
    assert result[0]["loaded_spl_overlap_bytes"] == 8
    assert layout.classify_ram([section(bank["load_end"], 16)], bank)[0]["loaded_spl_overlap_bytes"] == 0


@pytest.mark.parametrize("change", ["short", "extra", "modified"])
def test_production_pin_rejects_unexpected_stock(change):
    blob = synthetic_bank()
    changed = {"short": blob[:-1], "extra": blob + b"!", "modified": blob[:-1] + b"!"}[change]
    with pytest.raises(ValueError, match="exact FM-1 V15 pin"):
        layout.stock_bank(changed)
    with pytest.raises(ValueError, match="exact FM-1 V15 pin"):
        layout.stock_bank(blob)


@pytest.mark.parametrize("offset,value", [(0, 2), (2, 14384), (4, 0x01C02010), (8, 0)])
def test_bank_contract_rejects_header_mapping_errors(monkeypatch, offset, value):
    changed = bytearray(synthetic_bank())
    struct.pack_into("<H" if offset < 4 else "<I", changed, offset, value)
    pin_for_test(monkeypatch, changed)
    with pytest.raises(ValueError, match="bank header"):
        layout.stock_bank(changed)


@pytest.mark.parametrize("offset", [14, 16])
def test_header_and_body_crc_are_checked_independently(monkeypatch, offset):
    changed = bytearray(synthetic_bank())
    changed[offset] ^= 1
    pin_for_test(monkeypatch, changed)
    with pytest.raises(ValueError, match="CRC mismatch"):
        layout.stock_bank(changed)


@pytest.mark.parametrize("begin,size", [(-1, 1), (0, 0), (0, -1), (True, 4),
                                       (0, False), ("0", 4), (0xFFFFFFFF, 2)])
def test_malformed_ranges_fail_closed(begin, size):
    with pytest.raises(ValueError, match="malformed"):
        layout.range_end(begin, size)


@pytest.mark.parametrize("name,begin,end", layout.PROTECTED)
def test_protected_boot_data_overlap_and_boundary_touch(name, begin, end):
    bank = dict(load_begin=0x01C02000, load_end=0x01C05820)
    for address, size in [(begin, 1), (begin - 1, 2), (end - 1, 2)]:
        with pytest.raises(ValueError, match="protected"):
            layout.classify_ram([section(address, size)], bank)
    # The adjacent prefix/header are both protected: touch the outer edges only.
    layout.classify_ram([section(layout.PROTECTED[0][1] - 4, 4)], bank)
    layout.classify_ram([section(layout.PROTECTED[-1][2], 4)], bank)


@pytest.mark.parametrize("sections,message", [([], "no linked"),
    ([section(0, 4, ".unknown")], "unexpected"),
    ([section(0, 4), section(8, 4)], "duplicate"),
    ([section(0, 8), section(4, 4, ".bss")], "overlapping")])
def test_section_set_rejects_invalid_contract(sections, message):
    with pytest.raises(ValueError, match=message):
        layout.classify_ram(sections, dict(load_begin=0x01C02000, load_end=0x01C05820))


@pytest.mark.parametrize("handover", [False, True])
def test_actual_elf_ranges_and_nonreturning_evidence(monkeypatch, handover):
    blob = synthetic_bank()
    pin_for_test(monkeypatch, blob)
    elf, app = fixture(handover=handover)
    result = layout.inspect(elf, app, blob, "handover" if handover else "inert")
    assert result["layout_verified"] and result["requires_nonreturning"]
    assert result["layout"]["ram_reserved_bytes"] == (8256 if handover else 4144)
    assert sum(s["loaded_spl_overlap_bytes"] for s in result["ram_sections"]) == (8252 if handover else 4140)
    assert not result["private_ram_proven"] and not result["package_created"]
    assert result["device_execution"] == "unverified"
    assert all(s["ownership"] == "unresolved" for s in result["ram_sections"])
    assert len(result["unresolved_runtime_gates"]) == 5


def test_linked_bytes_and_profile_are_not_trusted(monkeypatch):
    blob = synthetic_bank()
    pin_for_test(monkeypatch, blob)
    elf, app = fixture(handover=True)
    with pytest.raises(ValueError, match="differs"):
        layout.inspect(elf, app[:-1] + b"!", blob)
    with pytest.raises(ValueError, match="unexpected allocated"):
        layout.inspect(elf, app, blob, "inert")
    with pytest.raises(ValueError, match="profile"):
        layout.inspect(elf, app, blob, "invalid")


def test_report_recomputes_link_audit(monkeypatch):
    from audit_link import EFUSE_SFR_LO
    blob = synthetic_bank()
    pin_for_test(monkeypatch, blob)
    elf, app = fixture()
    # Flat image and ELF agree, but forbidden access evidence fails the audit.
    bad = struct.pack("<I", EFUSE_SFR_LO)
    with pytest.raises(ValueError, match="passing SDK-free link audit"):
        layout.inspect(elf.replace(b"LUNA", bad), app.replace(b"LUNA", bad), blob, "inert")


def test_cli_rejects_unknown_stock_without_success_json(tmp_path, monkeypatch, capsys):
    elf, app = fixture()
    for name, blob in (("elf", elf), ("app", app), ("spl", synthetic_bank())):
        (tmp_path / name).write_bytes(blob)
    monkeypatch.setattr(sys, "argv", ["handover_layout.py", "--profile", "inert",
        "--elf", str(tmp_path / "elf"), "--app", str(tmp_path / "app"),
        "--spl", str(tmp_path / "spl")])
    assert layout.main() == 1
    output = capsys.readouterr()
    assert not output.out and "exact FM-1 V15 pin" in output.err


def test_optional_actual_stock_bank():
    path = os.environ.get("FM1_STOCK_SPL")
    if not path:
        pytest.skip("set FM1_STOCK_SPL for the locally held decoded V15 SPL")
    result = layout.stock_bank(Path(path).read_bytes())
    assert result["load_end"] == 0x01C05820
    assert result["sha256"] == "730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef"

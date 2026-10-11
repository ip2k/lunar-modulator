"""Fail-closed staging and SDK image-layout checks; no vendor/device dependency."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/jieli"))

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

BUILD = load("sdk_build", ROOT / "tools/jieli/build-sdk-diagnostic.py")
AUDIT = load("sdk_audit", ROOT / "tools/jieli/audit_sdk_diagnostic.py")

@pytest.mark.parametrize("mutation", [None, "missing", "extra", "bytes", "manifest"])
def test_stage_inventory_rejects_drift(tmp_path, monkeypatch, mutation):
    source = tmp_path / "source.c"
    source.write_text("int pinned;\n")
    marker = tmp_path / ".lunar-sdk-stage.json"
    marker.write_text(json.dumps({"schema": 1, "revision": BUILD.PIN,
        "private_build_input": True, "archives": {},
        "files": {"source.c": hashlib.sha256(source.read_bytes()).hexdigest()}}))
    monkeypatch.setattr(BUILD, "STAGE_SHA256", BUILD.sha(marker))
    if mutation == "missing":
        source.unlink()
    elif mutation == "extra":
        (tmp_path / "unexpected.c").write_text("extra")
    elif mutation == "bytes":
        source.write_text("modified")
    elif mutation == "manifest":
        marker.write_text(marker.read_text() + " ")
    if mutation is None:
        assert BUILD.verify_stage(tmp_path)["revision"] == BUILD.PIN
    else:
        with pytest.raises(ValueError):
            BUILD.verify_stage(tmp_path)

@pytest.mark.parametrize("symbol", [None, "chip_entry", "exception_irq_handler",
    "sdk_meky_check", "p33_lock", "syscfg_ops_begin", "late_initcall_begin"])
def test_actual_native_contract_rejects_instruction_or_registry_mutation(symbol):
    path = os.environ.get("LUNAR_SDK_ELF")
    if not path:
        pytest.skip("Set LUNAR_SDK_ELF to the private native candidate")
    elf = AUDIT.Elf(Path(path).read_bytes())
    if symbol is not None:
        addr = elf.symbol_value(symbol)
        section = next(s for s in elf.sections if s["addr"] <= addr < s["addr"] + s["size"])
        modified = bytearray(elf.data)
        modified[section["offset"] + addr - section["addr"]] ^= 1
        elf = AUDIT.Elf(bytes(modified))
        with pytest.raises(ValueError):
            AUDIT.instruction_contract(elf)
            AUDIT.registration_contract(elf)
    else:
        assert AUDIT.instruction_contract(elf)["runtime_result_verified"] is False
        assert AUDIT.registration_contract(elf)["persistent_cfg_writer_registered"] is False

def test_make_parser_preserves_multitoken_flags_and_rejects_missing_list():
    assert BUILD.make_list("CFLAGS := \\\n -target pi32v2 \\\n -Oz \\\n\n", "CFLAGS") == ["-target", "pi32v2", "-Oz"]
    with pytest.raises(ValueError, match="Missing"):
        BUILD.make_list("CFLAGS := -Oz\n", "CFLAGS")

def layout():
    sections = []
    values = {}
    data = bytearray()
    for i, (name, symbol) in enumerate(AUDIT.LAYOUT):
        values[symbol] = 0x02000120 + len(data)
        sections.append({"name": name, "type": 1, "addr": 0x01c00000 + i * 4,
                         "offset": len(data), "size": 4})
        data.extend(bytes([i]) * 4)
    return SimpleNamespace(sections=sections, data=bytes(data), symbol_value=values.get), values

def test_layout_reconstructs_sdk_lmas():
    elf, _ = layout()
    app, rows = AUDIT.reconstruct(elf)
    assert app == b"\x00" * 4 + b"\x01" * 4 + b"\x02" * 4 + b"\x03" * 4 + b"\x04" * 4
    assert rows[-1]["image_offset"] == 16

@pytest.mark.parametrize("mutation", ["lma", "duplicate", "nobits", "truncated"])
def test_layout_refuses_corrupt_mapping(mutation):
    elf, values = layout()
    if mutation == "lma":
        values["_ram0_data_lma"] += 4
    elif mutation == "duplicate":
        elf.sections.append(dict(elf.sections[0]))
    elif mutation == "nobits":
        elf.sections[0]["type"] = 8
    else:
        elf.data = elf.data[:-1]
    with pytest.raises(ValueError):
        AUDIT.reconstruct(elf)

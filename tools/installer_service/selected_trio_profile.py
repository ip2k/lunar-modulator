# SPDX-License-Identifier: MIT
"""Pure fixed-Trio v2 contract and offline evidence checks; no build or admission.

TrustedInputs must be captured by the future trusted operator/worker from its
pinned inputs and retained output evidence. Never construct it from a client
request or the receipt being checked. These checks prove evidence coherence,
not execution, target performance, authenticity or a distribution entitlement.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import struct
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from tools.jieli.audit_link import Elf, EM_PI32V2, ET_EXEC, SHF_ALLOC, SHT_NOBITS, audit
from .build_capabilities import SELECTED_TRIO_PROFILE
from .request_contract import MAX_REQUEST_BYTES, canonical_request, decode_json_object

SOURCE_PATH = "engines/state/examples/init-starters/trio-init.lunar"
SOURCE_SHA256 = "46541967e4fa7321f4efe1105632de3613064a2fbcf7d71490cb647247a97c1b"
PACKED_SHA256 = "dc3c50d8da761fdfe36d17e1368d99f40740652192f14649230a9f8d7e3d58d4"
ARCHIVE_SHA256 = "f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958"
APP_BUDGET = 0x8DFBC
AUDIT_LIMIT = ("Symbol closure scan is additional evidence, not audit_link admission "
               "or a complete MMIO/callgraph audit.")
MAX_RECEIPT = 4 * 1024 * 1024
MAX_ELF = 16 * 1024 * 1024
MAX_EVIDENCE = 256 * 1024 * 1024
GPL_SOURCES = dict(dinghy="d44df7db09b98ccad2f1233b8f83f5f09c04829e",
                   felucca_trio="b0dcd53a251d5f5392fea9478b48244d322eeb2a")
DENIED = dict(installable=False, package_admitted=False, release_admitted=False, hardware_admitted=False,
              hardware_tested=False, distribution_admitted=False, rom_return=False)


class SelectedTrioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: StrictInt = Field(ge=2, le=2)
    profile_id: Literal["sdk-free-selected-trio-offline-diagnostic-v1"]
    runtime_mode: Literal["offline"]
    flash_layout: Literal["stock-sized-diagnostic"]
    engines: list[StrictStr]
    effects: list[StrictStr]
    midi: list[StrictStr]
    modulation: list[StrictStr]
    project_ids: list[StrictStr]
    startup_index: StrictInt
    set_ids: list[StrictStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def fixed_selection(self):
        if (self.engines != ["trio"] or self.effects or self.midi or self.modulation
                or self.project_ids != ["init-starter-trio"] or self.startup_index != 0
                or self.set_ids):
            raise ValueError("only the fixed Trio offline selection is supported")
        return self


def validate_request(raw: bytes) -> dict:
    model = SelectedTrioRequest.model_validate(decode_json_object(raw, limit=MAX_REQUEST_BYTES))
    return model.model_dump(mode="json", exclude_defaults=True)


@dataclass(frozen=True)
class TrustedInputs:
    source_commit: str
    source_tree_oid: str
    source_manifest: Mapping[str, str]
    toolchain_binding: dict
    cxx_headers_manifest: Mapping[str, str]
    configured_cxx_headers_manifest: Mapping[str, str]
    host_tools: Mapping[str, str]  # renderer, state_tool, metadata SHA-256
    prepared_files: Mapping[str, bytes]
    objects: Mapping[str, bytes]
    audit_sources: tuple[tuple[str, int, str], ...]
    compile_flags: tuple[str, ...]
    compiler_version: str


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _same(actual, expected, field):
    if _canonical(actual) != _canonical(expected):
        raise ValueError("selected Trio evidence mismatch: " + field)


def _hashes(value, field):
    if (not isinstance(value, dict) or not value or len(value) > 10000
            or any(not isinstance(k, str) or not _relative(k)
                   or not isinstance(v, str) or not re.fullmatch(r"[0-9a-f]{64}", v)
                   for k, v in value.items())):
        raise ValueError("invalid trusted hash manifest: " + field)


def _relative(path):
    return bool(path) and "\\" not in path and all(p not in ("", ".", "..") for p in path.split("/"))


def _elf(raw):
    # Bound the existing shared reader's section/symbol loops before parsing.
    if type(raw) is not bytes or not 52 <= len(raw) <= MAX_ELF:
        raise ValueError("bounded ELF required")
    shoff = struct.unpack_from("<I", raw, 32)[0]
    stride, count, names = struct.unpack_from("<HHH", raw, 46)
    if stride != 40 or not 1 <= count <= 4096 or names >= count or shoff + count * stride > len(raw):
        raise ValueError("invalid ELF section table")
    payloads, rows, symbol_count = [], [], 0
    for index in range(count):
        row = struct.unpack_from("<10I", raw, shoff + index * stride)
        rows.append(row)
        _, kind, _, _, offset, size, link, _, _, entry = row
        if kind != SHT_NOBITS and size:
            if offset < 52 or offset + size > len(raw):
                raise ValueError("ELF section exceeds file")
            payloads.append((offset, offset + size))
        # This fully linked fixed profile has no retained relocation sections.
        if kind in (4, 9):
            raise ValueError("unexpected linked ELF relocations")
        if kind == 2 and (entry != 16 or size % 16 or size // 16 > 100000 or link >= count):
            raise ValueError("invalid ELF symbol table")
        if kind == 2:
            symbol_count += size // 16
    payloads.sort()
    if (symbol_count > 100000 or any(a[1] > b[0] for a, b in zip(payloads, payloads[1:]))
            or any(start < shoff + count * stride and shoff < end for start, end in payloads)):
        raise ValueError("overlapping or excessive ELF tables")
    def check_name(table, name_offset, maximum):
        if table[1] != 3 or name_offset >= table[5]:
            raise ValueError("invalid ELF string reference")
        start = table[4] + name_offset
        if raw.find(b"\0", start, min(table[4] + table[5], start + maximum + 1)) < 0:
            raise ValueError("unbounded ELF name")
    for row in rows:
        check_name(rows[names], row[0], 255)
        if row[1] == 2:
            for offset in range(row[4], row[4] + row[5], 16):
                check_name(rows[row[6]], struct.unpack_from("<I", raw, offset)[0], 1024)
                section = struct.unpack_from("<H", raw, offset + 14)[0]
                if section >= count and section != 0xFFF1:
                    raise ValueError("invalid linked ELF symbol section")
    try:
        result = Elf(raw, "selected-trio.elf")
    except (ValueError, IndexError, struct.error) as error:
        raise ValueError("invalid selected Trio ELF") from error
    if result.e_type != ET_EXEC or result.e_machine != EM_PI32V2 or result.undefined_symbols():
        raise ValueError("linked pi32v2 ELF required")
    starts = [s for s in result.symbols if s["name"] == "_start"]
    texts = [(i, s) for i, s in enumerate(result.sections) if s["name"] == ".text"]
    if len(starts) != 1 or len(texts) != 1:
        raise ValueError("unique executable startup required")
    start = starts[0]; index, text = texts[0]
    # The actual assembly label is STT_NOTYPE with size0, not STT_FUNC. Its
    # containing file-backed text still has to supply at least one instruction.
    if (text["type"] != 1 or text["flags"] != 6 or text["addr"] != 0x02000120
            or text["size"] < 2 or start["shndx"] != index
            or start["type"] not in (0, 2) or start["bind"] != 1
            or start["value"] != text["addr"]
            or max(start["size"], 2) > text["size"]
            or struct.unpack_from("<I", raw, 24)[0] != start["value"]):
        raise ValueError("ELF entry is not the fixed executable startup")
    forbidden = r"(?:fl_(?:erase|write|prog)\w*|ota_\w*|sdk_\w*|mkey_\w*|putchar_|_putchar|malloc|free|fm1_(?:enter_|reboot|core_reset)\w*|g_default_workspace)"
    if any(re.fullmatch(forbidden, name) for name in result.defined_symbols()):
        raise ValueError("forbidden offline diagnostic closure")
    return result


def _sizes(image, app, report):
    allocated = [s for s in image.sections if s["flags"] & SHF_ALLOC]
    sections = {s["name"]: dict(address=s["addr"], bytes=s["size"]) for s in allocated}
    if len(allocated) != 4 or set(sections) != {".text", ".data", ".bss", ".noinit"}:
        raise ValueError("unexpected allocated section")
    geometry = {".text": (1, 6), ".data": (1, 3), ".bss": (SHT_NOBITS, 3),
                ".noinit": (SHT_NOBITS, 3)}
    if any((s["type"], s["flags"]) != geometry[s["name"]] for s in allocated):
        raise ValueError("invalid allocated section geometry")
    def symbol(name):
        matches = [s for s in image.symbols if s["name"] == name and s["shndx"]]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous target symbol: " + name)
        return dict(address=matches[0]["value"], bytes=matches[0]["size"])
    text, data, bss, noinit = (sections[k] for k in (".text", ".data", ".bss", ".noinit"))
    if (text["address"] != 0x02000120 or text["bytes"] + data["bytes"] > APP_BUDGET
            or data["address"] != 0x01C08000
            or bss["address"] < data["address"] + data["bytes"]
            or bss["address"] + bss["bytes"] > 0x01C74000
            or noinit["address"] < 0x01C7C000
            or noinit["address"] + noinit["bytes"] > 0x01C7FD50
            or image.symbol_value("_data_load") != text["address"] + text["bytes"]
            or image.symbol_value("_bss_end") != bss["address"] + bss["bytes"]):
        raise ValueError("stock diagnostic layout or stack guard mismatch")
    flat = b"".join(image.data[s["offset"]:s["offset"] + s["size"]]
                    for name in (".text", ".data") for s in allocated
                    if s["name"] == name and s["type"] != SHT_NOBITS)
    if flat != app:
        raise ValueError("flat image differs from ELF load bytes")
    expected = dict(sections=sections, app=symbol("app"), arena=symbol("sound"),
                    descriptors=symbol("arenas"), user_stack_bytes=0x5F00,
                    supervisor_stack_bytes=0x1F00,
                    globals_to_stack_guard_bytes=0x01C74000 - image.symbol_value("_bss_end"),
                    flash_bytes=len(flat), reader_workspace=symbol("reader_space"),
                    selected_blob=symbol("lunar_selected_project_blob"))
    _same(report, expected, "ELF sizes")
    if expected["arena"]["bytes"] != 16384 or expected["reader_workspace"]["bytes"] != 16384:
        raise ValueError("fixed arena/reader storage mismatch")
    for name, address in dict(_guard0=0x01C74000, _ustack_lo=0x01C74100,
                              _ustack_top=0x01C7A000, _guard1=0x01C7A000,
                              _sstack_lo=0x01C7A100, _sstack_top=0x01C7C000).items():
        if image.symbol_value(name) != address:
            raise ValueError("stack/guard symbol mismatch")
    intervals = []
    for name in ("app", "arena", "descriptors", "reader_workspace"):
        s = expected[name]
        if not s["bytes"] or not bss["address"] <= s["address"] <= s["address"] + s["bytes"] <= bss["address"] + bss["bytes"]:
            raise ValueError("target storage is not contained in BSS")
        intervals.append((s["address"], s["address"] + s["bytes"]))
    intervals.sort()
    if any(left[1] > right[0] for left, right in zip(intervals, intervals[1:])):
        raise ValueError("target storage overlaps")
    blob = expected["selected_blob"]
    containing = [s for s in allocated if s["name"] in (".text", ".data")
                  and s["addr"] <= blob["address"]
                  and blob["address"] + blob["bytes"] <= s["addr"] + s["size"]]
    if len(containing) != 1 or blob["bytes"] != 597:
        raise ValueError("selected blob is not retained in one load section")
    s = containing[0]; start = s["offset"] + blob["address"] - s["addr"]
    if _sha(image.data[start:start + 597]) != PACKED_SHA256:
        raise ValueError("ELF selected blob differs from fixed packed source")
    return expected


def validate_receipt(request_raw: bytes, receipt_raw: bytes, *, app: bytes, elf: bytes,
                     trusted: TrustedInputs) -> dict:
    """Validate actual retained bytes; this never creates an install capability."""
    request = validate_request(request_raw)
    receipt = decode_json_object(receipt_raw, limit=MAX_RECEIPT)
    expected_keys = set("profile hardware_admitted release_candidate sdk_archives modules "
        "external_arenas arena_bytes cpu1 usb persistence fail_open toolchain_archive_sha256 "
        "toolchain_binding compiler_version cxx_headers_manifest configured_cxx_headers_manifest "
        "source_manifest compile_flags objects elf_sha256 app_sha256 sizes audit_link audit_limit "
        "selected_project fixed_project_startup rom_return distribution_reviewed linked_blob "
        "combined_licence gpl_sources prepared_input_manifest renderer_input state_tool_input".split())
    if set(receipt) != expected_keys:
        raise ValueError("unsupported selected Trio receipt schema")
    flag_prefix = ["-target", "pi32v2", "-mcpu=r3", "-mfprev1", "-Oz", "-ffreestanding",
                   "-fno-builtin", "-ffunction-sections", "-fdata-sections",
                   "-DFM1_APP_EXTERNAL_ARENAS=1", "-DNDEBUG", "-D_GNU_SOURCE", "-D_XOPEN_SOURCE=700",
                   "-DFM1_APP_STATE_EXTERNAL_WORKSPACE=1", "-D_LIBCPP_HAS_NO_THREADS",
                   "-D_LIBCPP_DISABLE_EXTERN_TEMPLATE"]
    flags = list(trusted.compile_flags)
    if (flags[:16] != flag_prefix or len(flags) != 20 or flags[16] != "-isystem"
            or flags[18] != "-isystem" or not all(type(f) is str and f for f in flags)
            or type(trusted.compiler_version) is not str or not trusted.compiler_version):
        raise ValueError("unsupported trusted compiler recipe")
    _same(receipt["compile_flags"], flags, "compiler flags")
    _same(receipt["compiler_version"], trusted.compiler_version, "compiler version")
    for field in ("source_commit", "source_tree_oid"):
        if not re.fullmatch(r"[0-9a-f]{40}", getattr(trusted, field)):
            raise ValueError("full trusted Git identity required")
    for field in ("source_manifest", "cxx_headers_manifest", "configured_cxx_headers_manifest"):
        expected = dict(getattr(trusted, field)); _hashes(expected, field)
        _same(receipt.get(field), expected, field)
    if trusted.source_manifest.get(SOURCE_PATH) != SOURCE_SHA256:
        raise ValueError("fixed source missing from trusted commit manifest")
    for field, expected in dict(profile=SELECTED_TRIO_PROFILE, hardware_admitted=False,
            release_candidate=False, sdk_archives=[], modules=["trio"], external_arenas=True,
            arena_bytes=16384, cpu1=False, usb=False, persistence=False, fail_open=False,
            fixed_project_startup=True, rom_return=False, distribution_reviewed=False,
            combined_licence="GPL-3.0-only", gpl_sources=GPL_SOURCES,
            toolchain_archive_sha256=ARCHIVE_SHA256, audit_limit=AUDIT_LIMIT).items():
        _same(receipt.get(field), expected, field)
    # This profile must not borrow old FM6 or timed/expanded profile fields.
    if any(k in receipt for k in ("voices", "dx7_sine", "shapes_voices", "runtime_configuration", "flash_layout")):
        raise ValueError("historical diagnostic fields are not offline Trio evidence")
    for key, value in receipt.items():
        if key in DENIED and value is not False:
            raise ValueError("receipt overstates admission")
    binding = trusted.toolchain_binding
    if (binding.get("schema") != 1 or binding.get("archive_sha256") != ARCHIVE_SHA256
            or not isinstance(binding.get("tree_manifest"), dict) or not binding["tree_manifest"]
            or binding.get("tree_sha256") != _sha(_canonical(binding["tree_manifest"]))):
        raise ValueError("invalid trusted archive/tree binding")
    _same(receipt.get("toolchain_binding"), binding, "archive/tree binding")
    files = dict(trusted.prepared_files); objects = dict(trusted.objects)
    if (set(files) != {"selected_project.bin", "selected_project_blob.c", "selected_project_blob.h", "receipt.json"}
            or not objects or len(objects) > 8192
            or any(not _relative(k) or type(v) is not bytes or not v for k, v in (*files.items(), *objects.items()))
            or sum(map(len, (*files.values(), *objects.values()))) > MAX_EVIDENCE):
        raise ValueError("invalid bounded private evidence")
    _same(receipt.get("prepared_input_manifest"), {k: _sha(v) for k, v in files.items()}, "prepared inputs")
    rows = receipt.get("objects")
    if not isinstance(rows, list) or any(not isinstance(r, dict) or set(r) != {"path", "sha256"}
            or not isinstance(r["path"], str) or not _relative(r["path"])
            or not isinstance(r["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", r["sha256"]) for r in rows):
        raise ValueError("invalid object inventory")
    if len(rows) != len(objects) or len({r["path"] for r in rows}) != len(rows):
        raise ValueError("duplicate or missing object evidence")
    _same({r["path"]: r["sha256"] for r in rows}, {k: _sha(v) for k, v in objects.items()}, "object inputs")
    preparation = decode_json_object(files["receipt.json"], limit=MAX_RECEIPT)
    _same(receipt.get("selected_project"), preparation, "preparation receipt")
    expected_prep = dict(schema=1, selection="init-starter-trio", source_path=SOURCE_PATH,
                         source_sha256=SOURCE_SHA256, packed_sha256=PACKED_SHA256,
                         packed_bytes=597, records=30, parameters=14,
                         renderer_sha256=trusted.host_tools.get("renderer"),
                         state_tool_sha256=trusted.host_tools.get("state_tool"),
                         metadata_sha256=trusted.host_tools.get("metadata"),
                         linked_hal=dict(name="Dinghy", upstream_commit=GPL_SOURCES["dinghy"],
                                         licence="GPL-3.0-only", linked_here=False),
                         distribution_reviewed=False, release_candidate=False, installable=False,
                         hardware_admitted=False, native_link_verified=False, native_ram_verified=False)
    _hashes(dict(trusted.host_tools), "host tools")
    if set(trusted.host_tools) != {"renderer", "state_tool", "metadata"}:
        raise ValueError("invalid trusted host tool keys")
    _same(preparation, expected_prep, "fixed preparation")
    if len(files["selected_project.bin"]) != 597 or _sha(files["selected_project.bin"]) != PACKED_SHA256:
        raise ValueError("prepared binary differs from fixed source")
    for key in ("renderer", "state_tool"):
        tool = receipt.get(key + "_input")
        if not isinstance(tool, dict) or set(tool) != {"path", "sha256"} or not isinstance(tool["path"], str):
            raise ValueError("invalid host tool input")
        _same(tool["sha256"], trusted.host_tools[key], key)
    if type(app) is not bytes or not 0 < len(app) <= APP_BUDGET:
        raise ValueError("bounded flat app required")
    _same(receipt.get("app_sha256"), _sha(app), "app bytes")
    _same(receipt.get("elf_sha256"), _sha(elf), "ELF bytes")
    image = _elf(elf)
    sizes = _sizes(image, app, receipt.get("sizes"))
    _same(receipt.get("linked_blob"), dict(sha256=PACKED_SHA256, bytes=597,
          address=sizes["selected_blob"]["address"]), "linked blob")
    recorded_audit = receipt.get("audit_link")
    if (not trusted.audit_sources or not isinstance(recorded_audit, dict)
            or recorded_audit.get("n_fail") != 0 or recorded_audit.get("n_pending") != 0
            or recorded_audit.get("passed") is not True
            or recorded_audit.get("runtime") != "sdk-free" or recorded_audit.get("linked") is not True
            or not isinstance(recorded_audit.get("inputs"), list) or len(recorded_audit["inputs"]) != 2):
        raise ValueError("complete original SDK-free audit required")
    actual_audit = audit([(recorded_audit["inputs"][0], image)], [("app.bin", app)], True,
                         sources=trusted.audit_sources, runtime="sdk-free")
    _same(recorded_audit, actual_audit, "original audit")
    return dict(version=2, profile_id=SELECTED_TRIO_PROFILE, runtime_mode="offline",
                flash_layout="stock-sized-diagnostic", request_sha256=_sha(canonical_request(request)),
                source_commit=trusted.source_commit, source_tree_oid=trusted.source_tree_oid,
                receipt_sha256=_sha(receipt_raw), artifact_sha256=_sha(app), elf_sha256=_sha(elf),
                artifact_bytes=len(app), app_budget_bytes=APP_BUDGET,
                remaining_bytes=APP_BUDGET - len(app), internal_dependencies=["arp"],
                **DENIED)

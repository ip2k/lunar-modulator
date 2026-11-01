#!/usr/bin/env python3
"""Strict offline FM-1_092 expanded app-container model; emits JSON only.

This profile accepts one pinned public 092 FWSC source and a supplied app image.
It relocates the FWSC entries following flash.bin and re-encodes their existing
SFC payloads at the new logical addresses. No package bytes are written.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from inspect_fwsc import (ENCRYPTED_TYPES, LOGICAL_PREFIX, PREFIX, PLAIN_TYPES,
                          STOCK_CHIP_KEY, cstring, crc16, header_decode,
                          inspect as inspect_fwsc, sfc_decode)
from inspect_stock_flash import stock_key

SOURCE_SHA256 = "ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80"
TARGET_APP_SHA256 = "5709ac03377a310eefdff563f4f08fe8a0e932ed9e0ecacef96464a59ec48573"
IDENTITY = "FM-1_092"
LEGACY_OFFSET_DELTA = 0x1B000
FLASH_ENTRY_OFFSET = 0x400
SOURCE_FLASH_BYTES = 0xAE000
INNER_APP_ORIGIN = 0x4000
APP_IMAGE_ORIGIN = 0x4120
STAGE_START = 0xD7000
# Current 092 decoded nested resource record extents, including each record header.
CFG_TOOL_BYTES = 383
CFG_RESOURCE_BYTES = 2937
OPAQUE_TAIL_BYTES = 968
MAX_APP_BYTES = STAGE_START - APP_IMAGE_ORIGIN - CFG_TOOL_BYTES - CFG_RESOURCE_BYTES - OPAQUE_TAIL_BYTES
EXPECTED_NAMES_TYPES = (
    ("flash.bin", 0), ("info.log", 2), ("USR", 50),
    ("isd_config.ini", 52), ("ota.bin", 100),
    ("script.ver", 251), ("blimit.bin", 161), ("tail.bin", 255),
)
EXPECTED_RESERVED = {
    "VM": (0xD9000, 0x10000, 0x12),
    "PRCT": (0, 0xD9000, 0x92),
    "BTIF": (0xE9000, 0x1000, 0x92),
    "USR": (0xEA000, 0x12000, 0x92),
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _logical(raw):
    if len(raw) < PREFIX:
        raise ValueError("FWSC is shorter than its 20-slot prefix")
    return bytearray(b"".join(raw[i:i + 47] for i in range(0, PREFIX, 48)) + raw[PREFIX:])


def _physical(logical, original):
    markers = [original[i * 48 + 47] for i in range(20)]
    out = bytearray()
    for i in range(20):
        out.extend(logical[i * 47:(i + 1) * 47])
        out.append(markers[i])
    out.extend(logical[940:])
    return bytes(out)


def _name(raw):
    value, sep, padding = raw.partition(b"\0")
    if not sep or any(padding):
        raise ValueError("invalid nested record name padding")
    try:
        return value.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ASCII nested record name") from exc


def _record(data, offset):
    if offset < 0 or offset + 32 > len(data):
        raise ValueError("nested record outside flash payload")
    raw = bytes(data[offset:offset + 32])
    hcrc, dcrc, address, size, flags, reserved, terminal, raw_name = struct.unpack("<HHIIBBH16s", raw)
    if crc16(raw[2:]) != hcrc:
        raise ValueError("nested JLFS header CRC mismatch")
    name_bytes, sep, tail = raw_name.partition(b"\0")
    if not sep or (not flags & 0x10 and any(x not in (0, 255) for x in tail)):
        raise ValueError("invalid nested record name padding")
    try:
        name = name_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("non-ASCII nested record name") from exc
    return {"offset": offset, "dcrc": dcrc, "address": address, "size": size,
            "flags": flags, "reserved": reserved, "terminal": terminal,
            "name": name, "raw": raw}


def _patch_record(data, offset, *, dcrc=None, address=None, size=None):
    if dcrc is not None:
        struct.pack_into("<H", data, offset + 2, dcrc)
    if address is not None:
        struct.pack_into("<I", data, offset + 4, address)
    if size is not None:
        struct.pack_into("<I", data, offset + 8, size)
    struct.pack_into("<H", data, offset, crc16(data[offset + 2:offset + 32]))


def _outer_parse(raw, *, legacy_092=False):
    """Strict UFW parse; legacy mode decodes the inherited 092 SFC-at-V15 offsets."""
    logical = _logical(raw)
    markers = [raw[i * 48 + 47] for i in range(20)]
    end = next((i for i, value in enumerate(markers) if value == 125), 20)
    if any(value != 125 for value in markers[end:]):
        raise ValueError("FWSC identity markers are not contiguous")
    identity = bytes((value - i - 1) & 255 for i, value in enumerate(markers[:end])).decode("ascii")
    if identity != IDENTITY:
        raise ValueError("only the pinned FM-1_092 identity is supported")
    header = header_decode(logical[:64])
    hcrc, listcrc, image_size, count, unknown16, unknown32, chip = struct.unpack("<HHIHHI48s", header)
    if crc16(header[2:]) != hcrc or image_size != len(logical):
        raise ValueError("FWSC header CRC or logical size mismatch")
    if cstring(chip) != "AC791N" or count != len(EXPECTED_NAMES_TYPES):
        raise ValueError("unsupported FM-1_092 FWSC header profile")
    table_end = 64 + count * 80
    table = bytes(logical[64:table_end])
    if crc16(table) != listcrc:
        raise ValueError("FWSC entry-list CRC mismatch")
    entries, occupied = [], []
    for i in range(count):
        row = header_decode(table[i * 80:(i + 1) * 80])
        kind, ordinal, checksum, unknown, offset, size, alloc, extra, raw_name = struct.unpack("<HHHHIII44s16s", row)
        name = cstring(raw_name)
        if (name, kind) != EXPECTED_NAMES_TYPES[i] or ordinal != i:
            raise ValueError("FWSC entry order/type differs from strict 092 profile")
        if alloc < size or offset < LOGICAL_PREFIX or offset + alloc > len(logical):
            raise ValueError("FWSC allocation is outside the logical container")
        if alloc:
            if any(offset < hi and lo < offset + alloc for lo, hi in occupied):
                raise ValueError("FWSC entry allocations overlap")
            occupied.append((offset, offset + alloc))
        payload = bytes(logical[offset:offset + alloc])
        if kind in ENCRYPTED_TYPES:
            decode_offset = offset - LEGACY_OFFSET_DELTA if legacy_092 else offset
            if decode_offset < 0 or decode_offset % 32:
                raise ValueError("encrypted FWSC entry has unsupported SFC offset")
            decoded = sfc_decode(payload, decode_offset)
        else:
            decoded = payload
        if crc16(decoded[:size]) != checksum:
            raise ValueError(f"FWSC payload CRC mismatch: {name}")
        entries.append({"name": name, "type": kind, "index": ordinal,
                        "checksum": checksum, "offset": offset, "size": size,
                        "alloc": alloc, "unknown": unknown, "extra": extra,
                        "encoded_allocation": payload, "decoded_allocation": decoded,
                        "header_row": row})
    return {"logical": logical, "header": header, "entries": entries,
            "identity": identity, "markers": markers,
            "unknown16": unknown16, "unknown32": unknown32}


def _flash_parse(flash, reference_dir):
    """Validate the 092 nested directory and compare protected decoded files."""
    ref = Path(reference_dir)
    for rel in ("top/uboot.boot", "top/isd_config.ini", "files/app.bin",
                "files/cfg_tool.bin", "files/cfg"):
        if not (ref / rel).is_file():
            raise ValueError(f"092 unpack reference is missing {rel}")
    if len(flash) < INNER_APP_ORIGIN or len(flash) % 32:
        raise ValueError("flash payload is truncated or not SFC-block aligned")
    raw_top_header = bytes(flash[:32])
    top_header = header_decode(raw_top_header)
    if crc16(top_header[2:]) != int.from_bytes(top_header[:2], "little"):
        raise ValueError("nested flash header CRC mismatch")
    top = [_record(header_decode(flash[o:o + 32]), 0) for o in (32, 64, 96, 128)]
    if [x["name"] for x in top] != ["uboot.boot", "isd_config.ini", "app_dir_head", "key_mac"]:
        raise ValueError("unexpected nested top directory")
    spl, config, area_top, key_mac = top
    if (spl["address"], spl["size"], spl["flags"], spl["terminal"]) != (0xA0, 14384, 0, 0):
        raise ValueError("FM-1_092 SPL record differs")
    if (config["address"], config["size"], config["flags"], config["terminal"]) != (0x38D0, 699, 2, 0):
        raise ValueError("FM-1_092 config record differs")
    if (area_top["address"], area_top["size"], area_top["flags"], area_top["dcrc"]) != (0x4000, 0xFFFFFFFF, 0x81, 0xFFFF):
        raise ValueError("FM-1_092 app-directory record differs")
    if (key_mac["address"], key_mac["size"], key_mac["flags"], key_mac["dcrc"]) != (0xFF000, 0x1000, 0x12, 0xFFFF):
        raise ValueError("FM-1_092 key descriptor differs")
    config_bytes = bytes(flash[config["address"]:config["address"] + config["size"]])
    if len(config_bytes) != config["size"] or crc16(config_bytes) != config["dcrc"]:
        raise ValueError("nested isd_config CRC/bounds mismatch")
    if config_bytes != (ref / "top/isd_config.ini").read_bytes():
        raise ValueError("decoded isd_config.ini differs from pinned 092 unpack")
    stock_key(config_bytes)
    spl_blob = bytearray(flash[spl["address"]:spl["address"] + spl["size"]])
    if len(spl_blob) != spl["size"]:
        raise ValueError("nested SPL outside flash payload")
    spl_blob[:16] = header_decode(spl_blob[:16])
    count, bank_size, bank_load, bank_offset, bank_crc, bank_hcrc = struct.unpack("<HHIIHH", spl_blob[:16])
    if crc16(spl_blob[:14]) != bank_hcrc or (count, bank_offset, bank_size, bank_load) != (1, 16, 14368, 0x01C02000):
        raise ValueError("nested stock SPL bank header differs")
    spl_blob[16:] = header_decode(spl_blob[16:])
    if crc16(spl_blob[16:]) != bank_crc or bytes(spl_blob) != (ref / "top/uboot.boot").read_bytes():
        raise ValueError("decoded SPL CRC or bytes differ from pinned 092 unpack")
    if crc16(spl_blob) != spl["dcrc"]:
        raise ValueError("outer nested SPL CRC mismatch")

    decoded = bytearray(flash)
    decoded[INNER_APP_ORIGIN:] = sfc_decode(flash[INNER_APP_ORIGIN:], 0)
    area = _record(decoded, INNER_APP_ORIGIN)
    if area["name"] != "app_area_head" or area["flags"] != 0x83 or area["address"] != 0x02000120:
        raise ValueError("unsupported 092 application area header")
    if area["size"] < 32 + 6 * 32 or INNER_APP_ORIGIN + area["size"] > len(flash):
        raise ValueError("application area exceeds flash profile")
    if crc16(decoded[INNER_APP_ORIGIN + 32:INNER_APP_ORIGIN + area["size"]]) != area["dcrc"]:
        raise ValueError("application area directory/data CRC mismatch")
    children = [_record(decoded, INNER_APP_ORIGIN + 32 + i * 32) for i in range(6)]
    if [x["name"] for x in children] != ["app.bin", "cfg_tool.bin", "VM", "PRCT", "BTIF", "USR"]:
        raise ValueError("unexpected 092 app child directory")
    if [x["terminal"] for x in children] != [0, 0, 0, 0, 0, 1]:
        raise ValueError("unexpected child directory termination")
    app, tool = children[:2]
    if app["flags"] != 0x82 or app["address"] != 0x120:
        raise ValueError("app child placement differs from 092 profile")
    expected_tool_address = app["address"] + app["size"]
    if tool["flags"] != 0x82 or tool["address"] != expected_tool_address or tool["size"] != CFG_TOOL_BYTES:
        raise ValueError("cfg-tool child placement differs from 092 profile")
    for item in children[2:]:
        expected = EXPECTED_RESERVED[item["name"]]
        if (item["address"], item["size"], item["flags"]) != expected or item["dcrc"] != 0xFFFF:
            raise ValueError("reserved FM-1 bank descriptor changed")
    app_start = INNER_APP_ORIGIN + app["address"]
    tool_start = INNER_APP_ORIGIN + tool["address"]
    app_bytes = bytes(decoded[app_start:app_start + app["size"]])
    tool_bytes = bytes(decoded[tool_start:tool_start + tool["size"]])
    if len(app_bytes) != app["size"] or crc16(app_bytes) != app["dcrc"]:
        raise ValueError("app child CRC/bounds mismatch")
    if len(tool_bytes) != tool["size"] or crc16(tool_bytes) != tool["dcrc"]:
        raise ValueError("cfg-tool child CRC/bounds mismatch")
    cfg_offset = INNER_APP_ORIGIN + area["size"]
    cfg = _record(decoded, cfg_offset)
    if cfg["name"] != "cfg" or (cfg["address"], cfg["flags"], cfg["terminal"]) != (32, 0x83, 1):
        raise ValueError("FM-1_092 cfg resource record differs")
    cfg_start = cfg_offset + cfg["address"]
    cfg_payload = bytes(decoded[cfg_start:cfg_offset + cfg["size"]])
    cfg_bytes = bytes(decoded[cfg_offset:cfg_offset + cfg["size"]])
    if cfg["size"] != 2937 or len(cfg_bytes) != 2937 or len(cfg_payload) != cfg["size"] - 32 or crc16(cfg_payload) != cfg["dcrc"]:
        raise ValueError("cfg resource CRC/bounds mismatch")
    if tool_start != app_start + len(app_bytes) or cfg_offset != tool_start + len(tool_bytes):
        raise ValueError("nested app/tool/cfg resources are not tightly bounded")
    if cfg_bytes != (ref / "files/cfg").read_bytes():
        raise ValueError("decoded cfg differs from pinned 092 unpack")
    if tool_bytes != (ref / "files/cfg_tool.bin").read_bytes():
        raise ValueError("decoded cfg_tool.bin differs from pinned 092 unpack")
    suffix_start = cfg_offset + cfg["size"]
    if suffix_start > len(decoded):
        raise ValueError("opaque suffix outside expanded flash extent")
    return {"decoded": decoded, "top_records": top, "area": area,
            "children": children, "app": app_bytes, "tool": tool_bytes,
            "cfg": cfg_bytes, "cfg_record": cfg, "cfg_offset": cfg_offset,
            "cfg_end": suffix_start, "opaque_tail": bytes(decoded[suffix_start:]),
            "protected_sha256": {"uboot.boot": _sha(bytes(spl_blob)),
                                  "isd_config.ini": _sha(config_bytes),
                                  "cfg_tool.bin": _sha(tool_bytes), "cfg": _sha(cfg_bytes),
                                  "key_mac_descriptor": _sha(key_mac["raw"])} }


def _set_entry(row, *, checksum=None, offset=None, size=None, alloc=None):
    b = bytearray(row)
    if checksum is not None:
        struct.pack_into("<H", b, 4, checksum)
    if offset is not None:
        struct.pack_into("<I", b, 8, offset)
    if size is not None:
        struct.pack_into("<I", b, 12, size)
    if alloc is not None:
        struct.pack_into("<I", b, 16, alloc)
    return bytes(b)


def _build(raw, reference_dir, app, *, target_app_sha256=TARGET_APP_SHA256):
    if _sha(raw) != SOURCE_SHA256:
        raise ValueError("source package is not the pinned public FM-1_092 fixture")
    if not app or len(app) > MAX_APP_BYTES:
        raise ValueError(f"replacement app must be 1..{MAX_APP_BYTES} bytes under the preserved-tail D7000 profile")
    if not isinstance(target_app_sha256, str) or len(target_app_sha256) != 64 or any(c not in "0123456789abcdef" for c in target_app_sha256):
        raise ValueError("replacement app digest parameter is invalid")
    if _sha(app) != target_app_sha256:
        if target_app_sha256 == TARGET_APP_SHA256:
            raise ValueError("replacement app is not the pinned Shapes8/Event-Horizon target artifact")
        raise ValueError("replacement app SHA-256 differs from the explicitly selected trusted build tuple")
    source = _outer_parse(raw, legacy_092=True)
    entries = source["entries"]
    flash_entry = entries[0]
    if (flash_entry["offset"], flash_entry["size"], flash_entry["alloc"]) != (FLASH_ENTRY_OFFSET, SOURCE_FLASH_BYTES, SOURCE_FLASH_BYTES):
        raise ValueError("source flash extent differs from strict 092 profile")
    old_flash = flash_entry["decoded_allocation"]
    old_nested = _flash_parse(old_flash, reference_dir)
    if old_nested["app"] != (Path(reference_dir) / "files/app.bin").read_bytes():
        raise ValueError("source nested app differs from unpacked public 092 package")
    if len(old_nested["opaque_tail"]) != OPAQUE_TAIL_BYTES:
        raise ValueError("092 opaque tail length differs from pinned profile")
    target_app_end = APP_IMAGE_ORIGIN + len(app)
    target_tool_end = target_app_end + CFG_TOOL_BYTES
    target_cfg_end = target_tool_end + CFG_RESOURCE_BYTES
    final_used_end = target_cfg_end + OPAQUE_TAIL_BYTES
    if final_used_end > STAGE_START:
        raise ValueError("nested resources and preserved opaque tail cross D7000 stage boundary")

    old_decoded = old_nested["decoded"]
    new_region = bytearray(b"\xff") * (STAGE_START - INNER_APP_ORIGIN)
    # Relative indexing here is from the SFC origin at 0x4000.
    # Preserve directory and pre-app gap bytes; patch only the bounded records.
    new_region[:APP_IMAGE_ORIGIN - INNER_APP_ORIGIN] = old_decoded[INNER_APP_ORIGIN:APP_IMAGE_ORIGIN]
    area_size = (APP_IMAGE_ORIGIN - INNER_APP_ORIGIN) + len(app) + CFG_TOOL_BYTES
    app_rel = APP_IMAGE_ORIGIN - INNER_APP_ORIGIN
    tool_rel = app_rel + len(app)
    new_region[app_rel:app_rel + len(app)] = app
    old_tool = old_nested["tool"]
    new_region[tool_rel:tool_rel + len(old_tool)] = old_tool
    app_record_off = 32
    tool_record_off = 64
    _patch_record(new_region, app_record_off, dcrc=crc16(app), size=len(app))
    _patch_record(new_region, tool_record_off, dcrc=crc16(old_tool), address=tool_rel, size=len(old_tool))
    _patch_record(new_region, 0, dcrc=crc16(new_region[32:area_size]), size=area_size)
    old_cfg_rel = old_nested["cfg_offset"] - INNER_APP_ORIGIN
    cfg_blob = old_decoded[INNER_APP_ORIGIN + old_cfg_rel:INNER_APP_ORIGIN + old_cfg_rel + CFG_RESOURCE_BYTES]
    if len(cfg_blob) != CFG_RESOURCE_BYTES:
        raise ValueError("source cfg block is not complete")
    cfg_rel = area_size
    new_region[cfg_rel:cfg_rel + len(cfg_blob)] = cfg_blob
    tail_rel = cfg_rel + len(cfg_blob)
    new_region[tail_rel:tail_rel + OPAQUE_TAIL_BYTES] = old_nested["opaque_tail"]
    if len(new_region) % 32:
        raise ValueError("D7000 region is not SFC block aligned")
    new_flash = bytearray(old_flash[:INNER_APP_ORIGIN])
    new_flash.extend(sfc_decode(bytes(new_region), 0))
    if len(new_flash) != STAGE_START:
        raise ValueError("expanded flash payload does not end exactly at D7000")

    logical = source["logical"]
    flash_start = flash_entry["offset"]
    flash_end = flash_start + flash_entry["alloc"]
    delta = len(new_flash) - flash_entry["alloc"]
    if delta <= 0 or delta % 32:
        raise ValueError("expanded flash relocation is not a positive aligned insertion")
    out = bytearray(logical[:flash_start] + new_flash + logical[flash_end:])
    encoded_rows = []
    moved_payloads = {}
    for item in entries:
        new_offset = item["offset"] if item["index"] == 0 else item["offset"] + delta
        if item["index"] == 0:
            decoded = bytes(new_flash)
            encoded = decoded
            row = _set_entry(item["header_row"], checksum=crc16(decoded), offset=new_offset,
                             size=len(decoded), alloc=len(decoded))
        else:
            decoded = item["decoded_allocation"]
            encoded = sfc_decode(decoded, new_offset) if item["type"] in ENCRYPTED_TYPES else decoded
            row = _set_entry(item["header_row"], offset=new_offset)
            moved_payloads[item["name"]] = (item["encoded_allocation"], encoded, decoded)
        if new_offset + len(encoded) > len(out):
            raise ValueError("relocated FWSC entry exceeds reconstructed container")
        out[new_offset:new_offset + len(encoded)] = encoded
        encoded_rows.append(header_decode(row))
    table = b"".join(encoded_rows)
    out[64:64 + len(table)] = table
    decoded_header = bytearray(source["header"])
    struct.pack_into("<I", decoded_header, 4, len(out))
    struct.pack_into("<H", decoded_header, 2, crc16(table))
    struct.pack_into("<H", decoded_header, 0, crc16(decoded_header[2:]))
    out[:64] = header_decode(decoded_header)
    modeled = _physical(out, raw)
    return modeled, source, old_nested, moved_payloads, {
        "delta": delta, "area_size": area_size, "app_end": target_app_end,
        "cfg_end": target_cfg_end, "used_end": final_used_end,
        "slack_to_stage": STAGE_START - final_used_end,
    }


def verify_modeled(raw, modeled, reference_dir, app, *, target_app_sha256=TARGET_APP_SHA256):
    """Independently re-open and validate a modeled package without rebuilding it."""
    if _sha(raw) != SOURCE_SHA256:
        raise ValueError("verification source is not the pinned public FM-1_092 package")
    if not isinstance(target_app_sha256, str) or len(target_app_sha256) != 64 or any(c not in "0123456789abcdef" for c in target_app_sha256):
        raise ValueError("replacement app digest parameter is invalid")
    if _sha(app) != target_app_sha256:
        if target_app_sha256 == TARGET_APP_SHA256:
            raise ValueError("replacement app is not the pinned Shapes8/Event-Horizon target artifact")
        raise ValueError("replacement app SHA-256 differs from the explicitly selected trusted build tuple")
    source = _outer_parse(raw, legacy_092=True)
    output = _outer_parse(modeled, legacy_092=False)
    generic = inspect_fwsc(modeled)
    if output["identity"] != IDENTITY or generic["identity"] != IDENTITY:
        raise ValueError("modeled identity changed")
    source_entries = {item["name"]: item for item in source["entries"]}
    output_entries = {item["name"]: item for item in output["entries"]}
    delta = STAGE_START - SOURCE_FLASH_BYTES
    for name, before in source_entries.items():
        after = output_entries[name]
        expected_offset = before["offset"] if name == "flash.bin" else before["offset"] + delta
        expected_extent = STAGE_START if name == "flash.bin" else before["alloc"]
        expected_size = STAGE_START if name == "flash.bin" else before["size"]
        if (after["offset"] != expected_offset or after["alloc"] != expected_extent
                or after["size"] != expected_size):
            raise ValueError(f"FWSC entry extent/relocation differs: {name}")
        if name != "flash.bin" and after["decoded_allocation"] != before["decoded_allocation"]:
            raise ValueError(f"decoded relocated FWSC content changed: {name}")
        if name != "flash.bin":
            left, right = after["header_row"], before["header_row"]
            if left[:8] != right[:8] or left[20:24] != right[20:24] or left[24:] != right[24:]:
                raise ValueError(f"non-placement FWSC metadata changed: {name}")
    old_flash_entry = source_entries["flash.bin"]
    new_flash_entry = output_entries["flash.bin"]
    if new_flash_entry["size"] != STAGE_START:
        raise ValueError("modeled flash payload does not end at D7000")
    old_nested = _flash_parse(old_flash_entry["decoded_allocation"], reference_dir)
    new_nested = _flash_parse(new_flash_entry["decoded_allocation"], reference_dir)
    if new_nested["app"] != app:
        raise ValueError("candidate app bytes do not round-trip through modeled SFC region")
    for key in ("uboot.boot", "isd_config.ini", "cfg_tool.bin", "cfg", "key_mac_descriptor"):
        if new_nested["protected_sha256"][key] != old_nested["protected_sha256"][key]:
            raise ValueError(f"decoded protected component changed: {key}")
    if new_nested["opaque_tail"][:OPAQUE_TAIL_BYTES] != old_nested["opaque_tail"]:
        raise ValueError("decoded opaque 092 tail changed")
    expected_cfg_offset = INNER_APP_ORIGIN + (APP_IMAGE_ORIGIN - INNER_APP_ORIGIN) + len(app) + CFG_TOOL_BYTES
    if new_nested["cfg_offset"] != expected_cfg_offset:
        raise ValueError("cfg resource did not follow relocated app/tool extent")
    if len(new_nested["opaque_tail"]) != STAGE_START - new_nested["cfg_end"]:
        raise ValueError("expanded padding extent differs from D7000 bound")
    changed_ciphertext = {}
    for name in ("USR", "isd_config.ini", "script.ver", "blimit.bin"):
        before, after = source_entries[name], output_entries[name]
        changed_ciphertext[name] = {
            "source_sha256": _sha(before["encoded_allocation"]),
            "modeled_sha256": _sha(after["encoded_allocation"]),
            "changed": before["encoded_allocation"] != after["encoded_allocation"],
            "decoded_sha256": _sha(after["decoded_allocation"][:after["size"]]),
        }
    bounds = {
        "delta": delta,
        "area_size": new_nested["area"]["size"],
        "app_end": APP_IMAGE_ORIGIN + len(app),
        "cfg_end": new_nested["cfg_end"],
        "used_end": new_nested["cfg_end"] + OPAQUE_TAIL_BYTES,
        "slack_to_stage": STAGE_START - (new_nested["cfg_end"] + OPAQUE_TAIL_BYTES),
    }
    return source, output, old_nested, new_nested, generic, changed_ciphertext, bounds


def model(raw, reference_dir, app):
    modeled, _, _, _, _ = _build(raw, reference_dir, app)
    source, output, before, after, generic, cipher, bounds = verify_modeled(
        raw, modeled, reference_dir, app)
    report = {
        "status": "offline-fm1-092-expanded-app-model-verified",
        "profile": "FM-1_092-only-expanded-d7000-preserve-tail",
        "identity": IDENTITY,
        "source_sha256": SOURCE_SHA256,
        "source_bytes": len(raw),
        "candidate_app_sha256": _sha(app),
        "candidate_app_bytes": len(app),
        "modeled_container_sha256": _sha(modeled),
        "modeled_container_bytes": len(modeled),
        "source_flash_bytes": SOURCE_FLASH_BYTES,
        "modeled_flash_bytes": output["entries"][0]["size"],
        "flash_inserted_bytes": bounds["delta"],
        "max_app_bytes_preserving_092_tail": MAX_APP_BYTES,
        "app_slack_to_max": MAX_APP_BYTES - len(app),
        "nested_boundaries": {key: hex(value) if key.endswith("_end") else value for key, value in bounds.items()},
        "d7000_start": hex(STAGE_START),
        "protected_decoded_sha256": after["protected_sha256"],
        "relocated_outer_payloads": cipher,
        "outer_integrity": {"header_crc_verified": generic["header_crc_verified"],
                             "entry_list_crc_verified": generic["entry_list_crc_verified"],
                             "all_payload_crcs_verified": all(e["crc_verified"] for e in generic["entries"])},
        "logical_protected_components_preserved": True,
        "address_dependent_ciphertext_reencoded": True,
        "binary_emitted": False,
        "packaging_ready": False,
        "hardware_admitted": False,
        "installable": False,
        "device_execution": "unverified",
        "pending": ["independent source/profile review", "outer FWSC metadata/trailer/version acceptance", "physical SFC/loader semantics and recovery remain unproven"],
    }
    if not all(report["outer_integrity"].values()):
        raise ValueError("modeled FWSC integrity check did not pass")
    return report

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fwsc", type=Path)
    parser.add_argument("--reference-dir", type=Path, required=True, help="private ignored FM-1_092 unpack tree")
    parser.add_argument("--app", type=Path, required=True, help="pinned public linked app payload")
    parser.add_argument("--json", type=Path, required=True, help="new report path; refuses overwrite")
    args = parser.parse_args(argv)
    try:
        result = model(args.fwsc.read_bytes(), args.reference_dir, args.app.read_bytes())
        with args.json.open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
    except (OSError, ValueError, KeyError, UnicodeError, struct.error) as exc:
        parser.exit(1, f"model_092_app_replacement: {exc}\n")
    print(f"{result['identity']}: 092 D7000 model verified; JSON only, installable=false")


if __name__ == "__main__":
    main()

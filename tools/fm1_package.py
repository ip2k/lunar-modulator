#!/usr/bin/env python3
"""Offline, bounded FM-1 FWSC inspection. No device I/O or package rebuilding.

Format research: kagaimiq/jl-misctools and Echomatter's local recovery-tool
analyzers. See docs/12-package-inspection.md for provenance and limitations.
Adapted decoding algorithms retain the MIT notice in THIRD_PARTY_NOTICES.md.
The msfa reference constants remain in check_msfa_table.py.
"""

from __future__ import annotations

import argparse
import binascii
import hashlib
import json
import re
import struct
from pathlib import Path

try:
    from .check_msfa_table import ANCHOR, MSFA_ALGORITHMS
except ImportError:
    from check_msfa_table import ANCHOR, MSFA_ALGORITHMS


MAX_INPUT_SIZE = 16 * 1024 * 1024
MAX_TABLE_HITS = 64
MAX_DIRECTORY_ENTRIES = 64
HEADER_BLOCKS = 20
RAW_BLOCK_SIZE = 48
LOGICAL_BLOCK_SIZE = 47
UFW_DATA_START = 0x400
IDENTITY_PATTERN = re.compile(rb"FM-1_[0-9]{3}(?![0-9])")


class PackageError(ValueError):
    """Input is malformed, unsupported, or fails an integrity check."""


def crc16(data: bytes) -> int:
    """JieLi CRC: polynomial 0x1021, init 0, no reflection, xorout 0."""
    return binascii.crc_hqx(data, 0)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _bounded(raw: bytes) -> None:
    if not isinstance(raw, bytes):
        raise PackageError("input must be bytes")
    if not raw or len(raw) > MAX_INPUT_SIZE:
        raise PackageError(f"input must contain 1 to {MAX_INPUT_SIZE} bytes")


def _slice(data: bytes, offset: int, size: int, label: str) -> bytes:
    if offset < 0 or size < 0 or offset > len(data) or size > len(data) - offset:
        raise PackageError(f"{label} lies outside its containing image")
    return data[offset:offset + size]


def _crc(data: bytes, expected: int, label: str) -> str:
    actual = crc16(data)
    if expected != actual:
        raise PackageError(f"{label} CRC mismatch: stored {expected:04x}, calculated {actual:04x}")
    return f"{actual:04x}"


def _name(raw: bytes, label: str) -> str:
    name = raw.split(b"\0", 1)[0].split(b"\xff", 1)[0]
    if not name or any(b < 0x20 or b > 0x7e for b in name):
        raise PackageError(f"{label} is not a printable ASCII name")
    return name.decode("ascii")


def _unscramble(raw: bytes, key: int = 0xffff) -> bytes:
    result = bytearray(len(raw))
    for index, value in enumerate(raw):
        result[index] = value ^ (key & 0xff)
        key = ((key << 1) ^ (0x1021 if key & 0x8000 else 0)) & 0xffff
    return bytes(result)


def _sfc_decode(raw: bytes, key: int, offset_bias: int = 0) -> bytes:
    # The cipher restarts every 32 bytes, relative to the app area base.
    result = bytearray()
    for offset in range(0, len(raw), 32):
        result.extend(_unscramble(raw[offset:offset + 32], (key ^ ((offset + offset_bias) >> 2)) & 0xffff))
    return bytes(result)


def _chip_key(encoded: bytes) -> int:
    if len(encoded) != 32:
        raise PackageError("chip-key record must be 32 bytes")
    threshold = sum(encoded[:16]) & 0xff
    threshold = 0xaa if threshold >= 0xe0 else 0x55 if threshold <= 0x10 else threshold
    return sum(1 << bit for bit in range(16)
               if (encoded[16 + bit] ^ encoded[15 - bit]) < threshold)


def _jlfs_header(raw: bytes, offset: int, label: str, encrypted: bool = False) -> dict:
    header = _slice(raw, offset, 32, f"{label} header")
    if encrypted:
        header = _unscramble(header)
    hcrc, dcrc, data_offset, size, flags, reserved, last, name = struct.unpack("<HHIIBBH16s", header)
    checked = _crc(header[2:], hcrc, f"{label} header")
    return {"name": _name(name, label), "header_offset": offset,
            "header_crc16": checked, "data_crc": dcrc, "offset": data_offset,
            "size": size, "flags": flags, "reserved": reserved, "last": last}


def _extract_application(flash: bytes) -> tuple[bytes, dict]:
    """Follow checked JLFS metadata; do not scan for names or assume addresses."""
    header = _unscramble(_slice(flash, 0, 32, "new-fw header"))
    flash_header_crc = _crc(header[2:], int.from_bytes(header[:2], "little"), "new-fw header")
    # VID/PID remain plaintext on disk but participate in the descrambled CRC.
    product = _name(flash[16:32], "flash product")
    if product != "AC791N_STORY":
        raise PackageError(f"unsupported flash product {product!r}")

    top = []
    for index in range(MAX_DIRECTORY_ENTRIES):
        entry = _jlfs_header(flash, 32 + index * 32, "top directory", encrypted=True)
        top.append(entry)
        if entry["last"]:
            break
    else:
        raise PackageError("top directory has no terminator within the entry limit")

    def exactly_one(entries: list[dict], name: str) -> dict:
        matches = [entry for entry in entries if entry["name"] == name]
        if len(matches) != 1:
            raise PackageError(f"expected exactly one {name!r} directory entry")
        return matches[0]

    app_head = exactly_one(top, "app_dir_head")
    config = exactly_one(top, "isd_config.ini")
    if app_head["flags"] != 0x81:
        raise PackageError("unsupported app_dir_head flags")
    top_end = 32 + len(top) * 32
    top_ranges = []
    for entry in top:
        if entry["name"] == "app_dir_head" or entry["flags"] & 0x10:
            continue
        if entry["offset"] < top_end:
            raise PackageError(f"{entry['name']} overlaps the top directory")
        _slice(flash, entry["offset"], entry["size"], f"top {entry['name']}")
        if entry["size"]:
            top_ranges.append((entry["offset"], entry["offset"] + entry["size"]))
    for previous, current in zip(sorted(top_ranges), sorted(top_ranges)[1:]):
        if current[0] < previous[1]:
            raise PackageError("top directory payloads overlap")
    if config["flags"] != 0x02:
        raise PackageError("unsupported isd_config.ini flags")
    if config["offset"] < top_end:
        raise PackageError("isd_config.ini overlaps the top directory")
    config_data = _slice(flash, config["offset"], config["size"], "isd_config.ini")
    config_crc = _crc(config_data, config["data_crc"], "isd_config.ini")
    key_record = _slice(config_data, 0, 34, "chip-key record")
    key_crc = _crc(key_record[:32], int.from_bytes(key_record[32:], "little"), "chip-key record")
    key = _chip_key(key_record[:32])
    app_base = app_head["offset"]
    if app_base < max([top_end] + [end for _, end in top_ranges]) or app_base % 32:
        raise PackageError("application area overlaps metadata or is not 32-byte aligned")
    area = _sfc_decode(_slice(flash, app_base, len(flash) - app_base, "application area"), key)
    area_head = _jlfs_header(area, 0, "application area")
    if area_head["name"] != "app_area_head" or area_head["flags"] != 0x83:
        raise PackageError("unsupported application area header")
    if area_head["size"] < 64:
        raise PackageError("application area is too short for a directory")
    area_body = _slice(area, 32, area_head["size"] - 32, "application area body")
    area_crc = _crc(area_body, area_head["data_crc"], "application area body")
    app_area = area[:area_head["size"]]

    entries = []
    for index in range(MAX_DIRECTORY_ENTRIES):
        entry = _jlfs_header(app_area, 32 + index * 32, "application directory")
        entries.append(entry)
        if entry["last"]:
            break
    else:
        raise PackageError("application directory has no terminator within the entry limit")
    directory_end = 32 + len(entries) * 32
    if len({entry["name"] for entry in entries}) != len(entries):
        raise PackageError("duplicate application directory entry name")
    occupied = []
    for entry in entries:
        if entry["flags"] & 0x10:
            # Reserved flash regions are declarations, not bytes in this file.
            continue
        if entry["flags"] != 0x82:
            raise PackageError("unsupported regular application entry flags")
        if entry["offset"] < directory_end:
            raise PackageError(f"{entry['name']} payload overlaps the application directory")
        payload = _slice(app_area, entry["offset"], entry["size"], entry["name"])
        _crc(payload, entry["data_crc"], entry["name"])
        if entry["size"]:
            occupied.append((entry["offset"], entry["offset"] + entry["size"]))
    for previous, current in zip(sorted(occupied), sorted(occupied)[1:]):
        if current[0] < previous[1]:
            raise PackageError("application payloads overlap")
    app = exactly_one(entries, "app.bin")
    if app["flags"] != 0x82 or not app["size"]:
        raise PackageError("app.bin is not a nonempty regular file")
    payload = _slice(app_area, app["offset"], app["size"], "app.bin")
    return payload, {
        "method": "JLFS directory and SFC decoding",
        "offset_basis": "file offsets within flash.bin; no runtime address inferred",
        "flash_header_crc16": flash_header_crc,
        "config_crc16": config_crc, "chip_key_crc16": key_crc,
        "chip_key": f"{key:04x}", "app_area_offset": app_base,
        "app_area_header_crc16": area_head["header_crc16"],
        "app_area_data_crc16": area_crc,
        "entry_header_offset": app_base + app["header_offset"],
        "entry_header_crc16": app["header_crc16"],
        "flash_data_offset": app_base + app["offset"],
        "relative_data_offset": app["offset"],
        "data_crc16": f"{app['data_crc']:04x}",
        "top_headers_verified": len(top),
        "application_headers_verified": len(entries),
    }


def inspect_application(raw: bytes) -> dict:
    """Analyze a supplied app image; SHA256 is provenance, not authenticity."""
    _bounded(raw)
    tables = []
    position = raw.find(ANCHOR)
    while position >= 0:
        if len(tables) == MAX_TABLE_HITS:
            raise PackageError("too many msfa anchors; analysis limit exceeded")
        table = raw[position:position + 192]
        differences = []
        matching_rows = 0
        for row_index, reference in enumerate(MSFA_ALGORITHMS):
            actual_row = table[row_index * 6:(row_index + 1) * 6]
            matching_rows += tuple(actual_row) == reference
            for op_index, expected in enumerate(reference):
                actual = actual_row[op_index] if op_index < len(actual_row) else None
                if actual != expected:
                    differences.append({"algorithm": row_index + 1, "operator": op_index + 1,
                                        "actual": actual, "expected": expected})
        known_fix = [{"algorithm": algorithm, "operator": 1, "actual": 0x41, "expected": 0xc1}
                     for algorithm in (4, 6)]
        classification = ("truncated" if len(table) != 192 else "msfa-original" if not differences
                          else "dexed-feedback-variant" if differences == known_fix else "other-variant")
        tables.append({"offset": position, "classification": classification,
                       "complete": len(table) == 192, "matching_rows": matching_rows,
                       "differences": differences})
        position = raw.find(ANCHOR, position + 1)
    return {"schema_version": 1, "kind": "fm1-application", "size": len(raw),
            "sha256": _sha256(raw),
            "embedded_identities": sorted({m.group().decode("ascii") for m in IDENTITY_PATTERN.finditer(raw)}),
            "msfa_tables": tables, "device_io_performed": False}


def _inspect_package(raw: bytes) -> tuple[dict, bytes]:
    _bounded(raw)
    if len(raw) < UFW_DATA_START + HEADER_BLOCKS:
        raise PackageError("truncated interleaved FWSC header")
    markers = bytes(raw[i * RAW_BLOCK_SIZE + LOGICAL_BLOCK_SIZE] for i in range(HEADER_BLOCKS))
    decoded = bytes((value - index - 1) & 0xff for index, value in enumerate(markers[:8]))
    if re.fullmatch(rb"FM-1_[0-9]{3}", decoded) is None or markers[8:] != b"\x7d" * 12:
        raise PackageError("unsupported or malformed interleaved FM-1 identity")
    logical = b"".join(raw[i * 48:i * 48 + 47] for i in range(20)) + raw[960:]
    header = _unscramble(logical[:64])
    hcrc, table_crc, declared_size, count, _flags, _unknown, chip_name = struct.unpack("<HHIHHI48s", header)
    checked_header = _crc(header[2:], hcrc, "UFW header")
    if declared_size != len(logical):
        raise PackageError("declared UFW size does not match the complete logical image")
    if not 1 <= count <= (UFW_DATA_START - 64) // 80:
        raise PackageError("UFW entry count exceeds the supported header region")
    checked_table = _crc(logical[64:64 + count * 80], table_crc, "UFW entry table")
    chip = _name(chip_name, "UFW chip")
    if chip != "AC791N":
        raise PackageError(f"unsupported UFW chip {chip!r}")
    entries, names, indexes, ranges = [], set(), set(), []
    for number in range(count):
        record = _unscramble(logical[64 + number * 80:144 + number * 80])
        kind, index, dcrc, _unused, offset, size, allocation, _reserved, raw_name = struct.unpack("<HHHHIII44s16s", record)
        name = _name(raw_name, "UFW entry")
        if name in names or index in indexes:
            raise PackageError("duplicate UFW entry name or index")
        names.add(name)
        indexes.add(index)
        if offset < UFW_DATA_START or allocation < size:
            raise PackageError(f"{name} has an invalid payload offset or allocation")
        _slice(logical, offset, allocation, f"{name} allocation")
        _slice(logical, offset, size, name)
        if allocation:
            ranges.append((offset, offset + allocation))
        entries.append({"name": name, "type": kind, "index": index, "offset": offset,
                        "size": size, "allocation": allocation, "crc16": f"{dcrc:04x}"})
    for previous, current in zip(sorted(ranges), sorted(ranges)[1:]):
        if current[0] < previous[1]:
            raise PackageError("UFW entry allocations overlap")
    tails = [entry for entry in entries if entry["name"] == "tail.bin" and entry["type"] == 255]
    if len(tails) != 1 or tails[0]["size"] != 64:
        raise PackageError("expected one 64-byte tail.bin key record")
    tail_entry = tails[0]
    tail = logical[tail_entry["offset"]:tail_entry["offset"] + 64]
    _crc(tail, int(tail_entry["crc16"], 16), "tail.bin")
    if tail[48:53] != b"JLUFW":
        raise PackageError("tail.bin has no JLUFW marker")
    _crc(tail[:32], int.from_bytes(tail[32:34], "little"), "tail chip-key record")
    package_key = _chip_key(tail[:32])
    flash = None
    for entry in entries:
        offset, size = entry["offset"], entry["size"]
        data = logical[offset:offset + size]
        if entry["type"] in (50, 52, 161, 251):
            if offset % 32:
                raise PackageError("SFC entry is not 32-byte aligned")
            decoded_data = _sfc_decode(data, package_key, offset)
            entry["crc_scope"] = "sfc-decoded payload"
            entry["decoded_sha256"] = _sha256(decoded_data)
        elif entry["type"] in (0, 2, 100, 255):
            decoded_data = data
            entry["crc_scope"] = "stored payload"
        else:
            raise PackageError(f"unsupported UFW entry type {entry['type']}")
        _crc(decoded_data, int(entry["crc16"], 16), entry["name"])
        entry["sha256"] = _sha256(data)
        if entry["name"] == "flash.bin":
            if entry["type"] != 0:
                raise PackageError("flash.bin has an unexpected UFW entry type")
            flash = data
    if flash is None:
        raise PackageError("package has no flash.bin entry")
    application, extraction = _extract_application(flash)
    if extraction["chip_key"] != f"{package_key:04x}":
        raise PackageError("tail and flash chip-key records disagree")
    app_report = {"status": "verified", **inspect_application(application), "extraction": extraction}
    report = {"schema_version": 1, "kind": "fm1-package", "size": len(raw),
              "logical_size": len(logical), "sha256": _sha256(raw), "chip": chip,
              "identity": {"value": decoded.decode("ascii"), "source": "interleaved header markers",
                           "authenticated": False,
                           "matches_application": decoded.decode("ascii") in app_report["embedded_identities"]
                           if app_report["embedded_identities"] else None},
              "integrity": {"header_crc16": checked_header, "entry_table_crc16": checked_table,
                            "entries_verified": len(entries), "crc_parameters": "poly=1021 init=0000 refin=false refout=false xorout=0000",
                            "authenticated": False},
              "entries": entries, "application": app_report,
              "unchecked_layers": [
                  "Nested boot payload decoding and checksums; the outer flash.bin CRC is checked.",
                  "Nested OTA compression and decompressed-image checksums; the UFW ota.bin CRC is checked.",
                  "Resource directories after app_area_head; the outer flash.bin CRC is checked.",
                  "Reserved flash regions and runtime address validity.",
                  "Identity marker bytes and unused allocation padding are outside stored CRC coverage.",
              ], "device_io_performed": False}
    return report, application


def inspect_package(raw: bytes) -> dict:
    """Return a JSON report only after all supported integrity checks pass."""
    return _inspect_package(raw)[0]


def inspect_and_extract(raw: bytes) -> tuple[dict, bytes]:
    """Return a checked package report and decoded application, in memory only."""
    return _inspect_package(raw)


def _read_bounded(path: Path) -> bytes:
    with path.open("rb") as source:
        raw = source.read(MAX_INPUT_SIZE + 1)
    _bounded(raw)
    return raw


def _output_path(path: Path) -> Path:
    # These trees are explicitly ignored by this repository. Resolve symlinks.
    target = path.resolve()
    root = Path(__file__).resolve().parents[1]
    if not any(target.is_relative_to(root / name) for name in ("scratch", "reference")):
        raise PackageError("output must be inside this repository's ignored scratch/ or reference/ tree")
    if target.exists():
        raise PackageError("output already exists; choose a new path to preserve evidence")
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("package", "app"))
    parser.add_argument("input", type=Path)
    parser.add_argument("--report", type=Path, help="also save JSON inside ignored scratch/ or reference/")
    parser.add_argument("--app-out", type=Path, help="explicitly extract app.bin inside ignored scratch/ or reference/")
    args = parser.parse_args(argv)
    try:
        if args.app_out and args.kind != "package":
            raise PackageError("--app-out requires package input")
        report_path = _output_path(args.report) if args.report else None
        app_path = _output_path(args.app_out) if args.app_out else None
        if report_path and app_path and report_path == app_path:
            raise PackageError("report and application output paths must differ")
        raw = _read_bounded(args.input)
        if args.kind == "package":
            report, application = _inspect_package(raw)
        else:
            report, application = inspect_application(raw), None
        serialized = json.dumps(report, indent=2) + "\n"
        if app_path:
            app_path.parent.mkdir(parents=True, exist_ok=True)
            with app_path.open("xb") as output:
                output.write(application)
        if report_path:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            with report_path.open("x", encoding="utf-8") as output:
                output.write(serialized)
        print(serialized, end="")
    except (OSError, PackageError) as error:
        parser.exit(2, f"inspection failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

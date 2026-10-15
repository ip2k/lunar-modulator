# SPDX-License-Identifier: MIT
"""Bounded host-only archive codec for opaque FM-1_092 VM and USR bytes.

This module only creates/decodes an in-memory archive. It does not interpret
stock settings, write flash, admit a migration, or establish a recovery path.
"""
from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib

from tools.native import storage_backup

FLASH_BYTES = storage_backup.FLASH_BYTES
FIXED_BANKS = storage_backup.FIXED_BANKS
PROFILES = storage_backup.PROFILES
inspect_reservations = storage_backup.inspect_reservations

MAGIC = b"FM1OSAR\0"
SCHEMA = 1
CAPACITY_BYTES = 20_480
WINDOW_BITS = -12
COMPRESSION_LEVEL = 6
PREFIX = struct.Struct(">8sHHI")
MAX_HEADER_BYTES = 2_048

VM_EXTENT = ("vm.bin", 0xD9000, 0x10000)
USR_EXTENT = ("usr.bin", 0xEA000, 0x12000)
BTIF_EXTENT = (0xE9000, 0x1000)
EXTENTS = (VM_EXTENT, USR_EXTENT)
RAW_BYTES = sum(row[2] for row in EXTENTS)

_HEADER_KEYS = {
    "schema", "kind", "baseline_sha256", "extents", "compression",
    "compressed_bytes", "compressed_sha256", "uncompressed_bytes",
    "uncompressed_sha256", "capacity_bytes",
}
_EXTENT_KEYS = {"name", "offset", "length", "sha256"}
_DIGEST_RE = re.compile(r"[0-9a-f]{64}\Z")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("ascii")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate archive JSON key: {key}")
        result[key] = value
    return result


def _check_profile_contract() -> None:
    if PROFILES.get("recorded-092") != (VM_EXTENT[1], VM_EXTENT[2]):
        raise ValueError("recorded-092 VM geometry differs from archive schema")
    if FIXED_BANKS.get("usr.bin") != (USR_EXTENT[1], USR_EXTENT[2]):
        raise ValueError("recorded-092 USR geometry differs from archive schema")
    if FIXED_BANKS.get("btif.bin") != BTIF_EXTENT:
        raise ValueError("recorded-092 BTIF boundary differs from archive schema")


def _encode(header: dict, compressed: bytes) -> bytes:
    header_bytes = _canonical(header)
    if len(header_bytes) > MAX_HEADER_BYTES:
        raise ValueError("archive metadata exceeds header bound")
    payload_offset = (PREFIX.size + len(header_bytes) + 3) & ~3
    padding = b"\0" * (payload_offset - PREFIX.size - len(header_bytes))
    total = payload_offset + len(compressed)
    if total > CAPACITY_BYTES:
        raise ValueError("opaque archive exceeds fixed 20 KiB capacity")
    return PREFIX.pack(MAGIC, SCHEMA, 0, len(header_bytes)) + header_bytes + padding + compressed


def pack(image_a: bytes, image_b: bytes, expected_baseline_sha256: str) -> bytes:
    """Return a complete archive only after source and size checks succeed.

    ``expected_baseline_sha256`` is an external trust anchor; it must not be
    copied from metadata supplied alongside ``image``.
    """
    _check_profile_contract()
    expected = _digest(expected_baseline_sha256, "expected baseline SHA-256")
    if (not isinstance(image_a, bytes) or not isinstance(image_b, bytes)
            or len(image_a) != FLASH_BYTES or len(image_b) != FLASH_BYTES):
        raise ValueError("two complete 1 MiB raw images required")
    if image_a != image_b:
        raise ValueError("full-flash backup pair differs")
    if _sha(image_a) != expected:
        raise ValueError("raw image differs from externally pinned baseline")

    image = image_a
    reservations = inspect_reservations(image, "recorded-092")
    pieces = []
    extent_rows = []
    for name, offset, length in EXTENTS:
        if reservations.get(name) != (offset, length):
            raise ValueError("storage backup profile and archive extents differ")
        raw = image[offset:offset + length]
        if len(raw) != length:
            raise ValueError("source image has a short opaque extent")
        pieces.append(raw)
        extent_rows.append({
            "name": name,
            "offset": offset,
            "length": length,
            "sha256": _sha(raw),
        })
    uncompressed = b"".join(pieces)
    if len(uncompressed) != RAW_BYTES:
        raise AssertionError("internal extent length mismatch")

    compressor = zlib.compressobj(COMPRESSION_LEVEL, zlib.DEFLATED, WINDOW_BITS)
    compressed = compressor.compress(uncompressed) + compressor.flush()
    if not compressed:
        raise ValueError("raw DEFLATE produced an empty stream")
    header = {
        "schema": SCHEMA,
        "kind": "fm1-recorded-092-opaque-vm-usr",
        "baseline_sha256": expected,
        "extents": extent_rows,
        "compression": "deflate-raw-wbits-12-level-6",
        "compressed_bytes": len(compressed),
        "compressed_sha256": _sha(compressed),
        "uncompressed_bytes": len(uncompressed),
        "uncompressed_sha256": _sha(uncompressed),
        "capacity_bytes": CAPACITY_BYTES,
    }
    encoded = _encode(header, compressed)
    decoded = unpack(encoded, expected, _sha(encoded))
    if decoded != {name: piece for (name, _, _), piece in zip(EXTENTS, pieces)}:
        raise ValueError("archive round-trip changed opaque extent bytes")
    return encoded


def unpack(archive: bytes, expected_baseline_sha256: str,
           expected_archive_sha256: str) -> dict[str, bytes]:
    """Decode only this bounded schema after checking an external archive pin.

    The embedded baseline digest is provenance metadata, not authentication:
    a producer can rewrite payload and all embedded hashes while retaining it.
    Callers must obtain ``expected_archive_sha256`` from a separate trusted
    boundary.
    """
    _check_profile_contract()
    expected = _digest(expected_baseline_sha256, "expected baseline SHA-256")
    archive_pin = _digest(expected_archive_sha256, "expected archive SHA-256")
    if not isinstance(archive, bytes) or len(archive) > CAPACITY_BYTES:
        raise ValueError("archive must be bytes within the fixed 20 KiB capacity")
    if _sha(archive) != archive_pin:
        raise ValueError("archive differs from externally pinned archive digest")
    if len(archive) < PREFIX.size:
        raise ValueError("truncated archive prefix")
    magic, schema, flags, header_length = PREFIX.unpack_from(archive)
    if magic != MAGIC or schema != SCHEMA or flags != 0:
        raise ValueError("unsupported archive magic, schema, or flags")
    if not 1 <= header_length <= MAX_HEADER_BYTES:
        raise ValueError("archive header length is outside its bound")
    header_end = PREFIX.size + header_length
    payload_offset = (header_end + 3) & ~3
    if payload_offset > len(archive):
        raise ValueError("truncated archive header or alignment padding")
    header_raw = archive[PREFIX.size:header_end]
    if any(archive[header_end:payload_offset]):
        raise ValueError("archive alignment padding must be zero")
    try:
        header = json.loads(header_raw.decode("ascii"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid archive metadata JSON") from exc
    if not isinstance(header, dict) or set(header) != _HEADER_KEYS or _canonical(header) != header_raw:
        raise ValueError("archive metadata schema or canonical encoding differs")

    if type(header["schema"]) is not int or header["schema"] != SCHEMA:
        raise ValueError("unsupported archive metadata schema")
    if header["kind"] != "fm1-recorded-092-opaque-vm-usr":
        raise ValueError("unsupported opaque archive kind")
    if _digest(header["baseline_sha256"], "archive baseline SHA-256") != expected:
        raise ValueError("archive is bound to a different full-image digest")
    if header["compression"] != "deflate-raw-wbits-12-level-6":
        raise ValueError("unsupported archive compression policy")
    if type(header["capacity_bytes"]) is not int or header["capacity_bytes"] != CAPACITY_BYTES:
        raise ValueError("archive capacity declaration differs")
    if type(header["uncompressed_bytes"]) is not int or header["uncompressed_bytes"] != RAW_BYTES:
        raise ValueError("archive uncompressed size differs from fixed extents")
    if type(header["compressed_bytes"]) is not int or not 1 <= header["compressed_bytes"] <= CAPACITY_BYTES:
        raise ValueError("archive compressed size is outside its bound")
    _digest(header["compressed_sha256"], "compressed payload SHA-256")
    _digest(header["uncompressed_sha256"], "uncompressed payload SHA-256")

    extent_rows = header["extents"]
    if not isinstance(extent_rows, list) or len(extent_rows) != len(EXTENTS):
        raise ValueError("archive extent inventory differs")
    for row, (name, offset, length) in zip(extent_rows, EXTENTS):
        if not isinstance(row, dict) or set(row) != _EXTENT_KEYS:
            raise ValueError("malformed archive extent row")
        if (row["name"] != name or type(row["offset"]) is not int or row["offset"] != offset
                or type(row["length"]) is not int or row["length"] != length):
            raise ValueError("archive extent identity or geometry differs")
        _digest(row["sha256"], f"{name} SHA-256")

    payload_end = payload_offset + header["compressed_bytes"]
    if payload_end != len(archive):
        raise ValueError("archive payload is truncated or has trailing bytes")
    compressed = archive[payload_offset:payload_end]
    if _sha(compressed) != header["compressed_sha256"]:
        raise ValueError("compressed payload SHA-256 differs")
    try:
        inflater = zlib.decompressobj(WINDOW_BITS)
        decoded = inflater.decompress(compressed, RAW_BYTES + 1)
    except zlib.error as exc:
        raise ValueError("invalid raw-DEFLATE payload") from exc
    if len(decoded) > RAW_BYTES or inflater.unconsumed_tail:
        raise ValueError("DEFLATE output exceeds fixed extent capacity")
    if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
        raise ValueError("DEFLATE stream is incomplete or has trailing data")
    if len(decoded) != RAW_BYTES or _sha(decoded) != header["uncompressed_sha256"]:
        raise ValueError("uncompressed archive bytes or digest differ")

    result = {}
    cursor = 0
    for row, (name, _offset, length) in zip(extent_rows, EXTENTS):
        piece = decoded[cursor:cursor + length]
        cursor += length
        if _sha(piece) != row["sha256"]:
            raise ValueError(f"{name} extent SHA-256 differs")
        result[name] = piece
    if cursor != len(decoded):
        raise AssertionError("internal decoder extent accounting mismatch")
    return result

# SPDX-License-Identifier: MIT
"""The VM/USR archive is lossless, bounded host data; it is not a writer."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import struct
import zlib

import pytest

from tools.native import opaque_stock_archive as archive
from tools.native.storage_backup import (FLASH_BYTES, PROFILES, crc16,
                                         header_decode, sfc_decode)

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_A = ROOT / "scratch/archived-092-recovery/stockA.bin"
PRIVATE_B = ROOT / "scratch/archived-092-recovery/stockB.bin"
PRIVATE_BASELINE_SHA256 = "96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4"


def _descriptor(name, address, size, flags, terminal=0):
    body = struct.pack("<HIIBBH16s", 0xFFFF, address, size, flags, 0, terminal,
                       name.encode().ljust(16, b"\0"))
    return struct.pack("<H", crc16(body)) + body


def _valid_image():
    start, size = PROFILES["recorded-092"]
    raw = bytearray(b"\xff" * FLASH_BYTES)
    head = bytearray(32)
    struct.pack_into("<H", head, 0, crc16(head[2:]))
    raw[:32] = header_decode(head)
    top = [
        _descriptor("uboot.boot", 0xA0, 14384, 0),
        _descriptor("isd_config.ini", 0x38D0, 699, 2),
        _descriptor("app_dir_head", 0x4000, 0xFFFFFFFF, 0x81),
        _descriptor("key_mac", 0xFF000, 4096, 0x12, 1),
    ]
    for index, entry in enumerate(top):
        raw[32 + index * 32:64 + index * 32] = header_decode(entry)
    children = b"".join([
        _descriptor("app_area_head", 0x02000120, 224, 0x83),
        _descriptor("app.bin", 0x120, 4, 0x82),
        _descriptor("cfg_tool.bin", 0x124, 4, 0x82),
        _descriptor("VM", start, size, 0x12),
        _descriptor("PRCT", 0, start, 0x92),
        _descriptor("BTIF", 0xE9000, 4096, 0x92),
        _descriptor("USR", 0xEA000, 0x12000, 0x92, 1),
    ])
    raw[0x4000:0x40E0] = sfc_decode(children, 0)
    pattern = bytes(range(256))
    for _name, offset, length in archive.EXTENTS:
        raw[offset:offset + length] = (pattern * ((length + 255) // 256))[:length]
    return bytes(raw)


def _pack(image, baseline_sha256):
    return archive.pack(image, image, baseline_sha256)


def _unpack(blob, baseline_sha256, archive_sha256=None):
    return archive.unpack(blob, baseline_sha256,
                          archive_sha256 or hashlib.sha256(blob).hexdigest())


def _parts(blob):
    magic, schema, flags, size = archive.PREFIX.unpack_from(blob)
    start = (archive.PREFIX.size + size + 3) & ~3
    header = json.loads(blob[archive.PREFIX.size:archive.PREFIX.size + size])
    return (magic, schema, flags), header, start, blob[start:]


def _wire(header, payload):
    encoded = archive._canonical(header)
    start = (archive.PREFIX.size + len(encoded) + 3) & ~3
    padding = b"\0" * (start - archive.PREFIX.size - len(encoded))
    return archive.PREFIX.pack(archive.MAGIC, archive.SCHEMA, 0, len(encoded)) + encoded + padding + payload


def _rebuild(blob, mutate_header=None, payload=None):
    _prefix, header, _offset, original_payload = _parts(blob)
    if mutate_header:
        mutate_header(header)
    return _wire(header, original_payload if payload is None else payload)


def test_synthetic_full_image_roundtrip_is_bounded_and_exact():
    image = _valid_image()
    baseline = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, baseline)
    decoded = _unpack(encoded, baseline)
    assert len(encoded) <= archive.CAPACITY_BYTES
    assert decoded == {
        name: image[offset:offset + length]
        for name, offset, length in archive.EXTENTS
    }
    _, header, payload_offset, _ = _parts(encoded)
    assert payload_offset % 4 == 0
    assert header["baseline_sha256"] == baseline
    assert header["capacity_bytes"] == archive.CAPACITY_BYTES
    assert header["compression"] == "deflate-raw-wbits-12-level-6"
    assert [row["name"] for row in header["extents"]] == ["vm.bin", "usr.bin"]
    assert not any(offset <= BTIF < offset + length
                   for _name, offset, length in archive.EXTENTS
                   for BTIF in (archive.BTIF_EXTENT[0],))


def test_pack_requires_external_baseline_hash_and_exact_recorded_profile():
    image = _valid_image()
    with pytest.raises(ValueError, match="externally pinned"):
        _pack(image, "0" * 64)
    malformed = bytearray(image)
    malformed[0x4000] ^= 1
    with pytest.raises(ValueError):
        _pack(bytes(malformed), hashlib.sha256(malformed).hexdigest())
    with pytest.raises(ValueError, match="1 MiB"):
        _pack(image[:-1], hashlib.sha256(image[:-1]).hexdigest())


def test_pack_requires_matching_full_flash_backup_pair():
    image = _valid_image()
    changed = bytearray(image)
    changed[0x5000] ^= 1
    with pytest.raises(ValueError, match="backup pair differs"):
        archive.pack(image, bytes(changed), hashlib.sha256(image).hexdigest())


def test_unpack_rejects_wrong_external_baseline_pin():
    image = _valid_image()
    pin = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, pin)
    with pytest.raises(ValueError, match="different full-image"):
        _unpack(encoded, "1" * 64)


def test_unpack_requires_external_archive_digest():
    image = _valid_image()
    baseline = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, baseline)
    with pytest.raises(ValueError, match="externally pinned archive"):
        archive.unpack(encoded, baseline, "0" * 64)


def test_recomputed_inner_hashes_do_not_replace_external_archive_pin():
    image = _valid_image()
    baseline = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, baseline)
    _, header, _offset, compressed = _parts(encoded)
    decoded = bytearray(zlib.decompress(compressed, -12))
    decoded[0] ^= 1
    compressor = zlib.compressobj(archive.COMPRESSION_LEVEL, zlib.DEFLATED,
                                  archive.WINDOW_BITS)
    forged_payload = compressor.compress(decoded) + compressor.flush()
    header["compressed_bytes"] = len(forged_payload)
    header["compressed_sha256"] = hashlib.sha256(forged_payload).hexdigest()
    header["uncompressed_sha256"] = hashlib.sha256(decoded).hexdigest()
    cursor = 0
    for row, (_name, _offset, length) in zip(header["extents"], archive.EXTENTS):
        row["sha256"] = hashlib.sha256(decoded[cursor:cursor + length]).hexdigest()
        cursor += length
    forged = _wire(header, forged_payload)
    with pytest.raises(ValueError, match="externally pinned archive"):
        archive.unpack(forged, baseline, hashlib.sha256(encoded).hexdigest())


@pytest.mark.parametrize("fault", [
    "payload-bit", "truncated", "trailing", "wrong-offset", "wrong-extent-hash",
    "wrong-compressed-length", "wrong-baseline", "wrong-schema", "bool-length",
])
def test_archive_mutations_refuse(fault):
    image = _valid_image()
    pin = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, pin)
    _, header, offset, payload = _parts(encoded)
    if fault == "payload-bit":
        broken = bytearray(encoded)
        broken[-1] ^= 1
        broken = bytes(broken)
    elif fault == "truncated":
        broken = encoded[:-1]
    elif fault == "trailing":
        broken = encoded + b"\0"
    elif fault == "wrong-offset":
        broken = _rebuild(encoded, lambda h: h["extents"][0].update(offset=0xD8000))
    elif fault == "wrong-extent-hash":
        broken = _rebuild(encoded, lambda h: h["extents"][1].update(sha256="0" * 64))
    elif fault == "wrong-compressed-length":
        broken = _rebuild(encoded, lambda h: h.update(compressed_bytes=len(payload) - 1))
    elif fault == "wrong-baseline":
        broken = _rebuild(encoded, lambda h: h.update(baseline_sha256="0" * 64))
    elif fault == "wrong-schema":
        broken = _rebuild(encoded, lambda h: h.update(schema=2))
    else:
        broken = _rebuild(encoded, lambda h: h.update(uncompressed_bytes=True))
    with pytest.raises(ValueError):
        _unpack(broken, pin)


def test_duplicate_json_keys_are_rejected():
    image = _valid_image()
    pin = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, pin)
    _, header, _offset, payload = _parts(encoded)
    raw = archive._canonical(header).replace(b'"kind":', b'"kind":"shadow", "kind":', 1)
    start = (archive.PREFIX.size + len(raw) + 3) & ~3
    broken = (archive.PREFIX.pack(archive.MAGIC, archive.SCHEMA, 0, len(raw)) + raw
              + b"\0" * (start - archive.PREFIX.size - len(raw)) + payload)
    with pytest.raises(ValueError, match="duplicate archive JSON key"):
        _unpack(broken, pin)


def test_trailing_deflate_data_is_rejected_even_with_updated_payload_hash():
    image = _valid_image()
    pin = hashlib.sha256(image).hexdigest()
    encoded = _pack(image, pin)
    payload = _parts(encoded)[3] + b"trailing"
    broken = _rebuild(encoded, lambda h: h.update(
        compressed_bytes=len(payload), compressed_sha256=hashlib.sha256(payload).hexdigest()),
        payload=payload)
    with pytest.raises(ValueError, match="trailing"):
        _unpack(broken, pin)


def test_decompression_output_is_bounded_to_fixed_extent_total():
    payload = zlib.compressobj(6, zlib.DEFLATED, -12)
    compressed = payload.compress(b"A" * (archive.RAW_BYTES + 1)) + payload.flush()
    header = {
        "schema": archive.SCHEMA,
        "kind": "fm1-recorded-092-opaque-vm-usr",
        "baseline_sha256": "a" * 64,
        "extents": [
            {"name": name, "offset": offset, "length": length, "sha256": "b" * 64}
            for name, offset, length in archive.EXTENTS
        ],
        "compression": "deflate-raw-wbits-12-level-6",
        "compressed_bytes": len(compressed),
        "compressed_sha256": hashlib.sha256(compressed).hexdigest(),
        "uncompressed_bytes": archive.RAW_BYTES,
        "uncompressed_sha256": "c" * 64,
        "capacity_bytes": archive.CAPACITY_BYTES,
    }
    with pytest.raises(ValueError, match="exceeds fixed extent"):
        candidate = _wire(header, compressed)
        archive.unpack(candidate, "a" * 64, hashlib.sha256(candidate).hexdigest())


def test_incompressible_opaque_extents_refuse_before_archive_return(tmp_path):
    image = bytearray(_valid_image())
    random_bytes = random.Random(20261015)
    for _name, offset, length in archive.EXTENTS:
        image[offset:offset + length] = bytes(random_bytes.getrandbits(8) for _ in range(length))
    image = bytes(image)
    pin = hashlib.sha256(image).hexdigest()
    with pytest.raises(ValueError, match="20 KiB capacity"):
        _pack(image, pin)
    assert list(tmp_path.iterdir()) == []


def test_retained_original_pair_roundtrips_without_exposing_bytes():
    if not PRIVATE_A.is_file() or not PRIVATE_B.is_file():
        pytest.skip("private retained FM-1_092 originals are unavailable")
    first, second = PRIVATE_A.read_bytes(), PRIVATE_B.read_bytes()
    assert first == second
    pin = hashlib.sha256(first).hexdigest()
    assert pin == PRIVATE_BASELINE_SHA256
    encoded = archive.pack(first, second, pin)
    decoded = _unpack(encoded, pin)
    assert len(encoded) <= archive.CAPACITY_BYTES
    assert len(first) == FLASH_BYTES
    assert decoded == {
        name: first[offset:offset + length]
        for name, offset, length in archive.EXTENTS
    }

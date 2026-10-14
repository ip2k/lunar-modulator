#!/usr/bin/env python3
"""Measure bounded RFC1951 raw-deflate candidates without retaining payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import zlib


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    source = args.payload.read_bytes()
    rows = []
    for level in (1, 6, 9):
        encoder = zlib.compressobj(level, zlib.DEFLATED, -12, 8,
                                   zlib.Z_DEFAULT_STRATEGY)
        packed = encoder.compress(source) + encoder.flush()
        if len(packed) <= 0:
            raise SystemExit(f"level {level}: compression produced no bytes")
        decoded = zlib.decompress(packed, -12)
        if decoded != source:
            raise SystemExit(f"level {level}: round-trip mismatch")
        rows.append({
            "level": level,
            "compressed_bytes": len(packed),
            "saved_bytes": len(source) - len(packed),
            "compressed_sha256": hashlib.sha256(packed).hexdigest(),
            "roundtrip_byte_identical": True,
        })
    print(json.dumps({
        "payload_bytes": len(source),
        "payload_sha256": hashlib.sha256(source).hexdigest(),
        "zlib_version": zlib.ZLIB_VERSION,
        "method": "RFC1951 raw deflate, 4 KiB window, default strategy",
        "levels": rows,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline footprint experiment; no firmware mutation or allocation admission."""
import hashlib
import json
import pathlib
import sys
import zlib


def main():
    app_path, symbols_path, sections_path, output = map(pathlib.Path, sys.argv[1:])
    app = app_path.read_bytes()
    expected = "eff6f5b2821a229f7a0255a873031c52d5f8242e4312f07e3f54fb4c951f5960"
    if hashlib.sha256(app).hexdigest() != expected:
        raise SystemExit("This experiment requires the installed all13 candidate")
    rows = []
    for line in symbols_path.read_text().splitlines():
        fields = line.split()
        if ".text" not in fields:
            continue
        index = fields.index(".text")
        address, size = int(fields[0], 16), int(fields[index + 1], 16)
        if not size:
            continue
        offset = address - 0x02000120
        if offset < 0 or offset + size > len(app):
            raise SystemExit("Symbol outside candidate application")
        rows.append(dict(name=fields[-1], address=address, bytes=size,
                         kind="code" if "F" in fields[:index] else "data"))
    assets = sorted((r for r in rows if r["kind"] == "data"),
                    key=lambda r: r["bytes"], reverse=True)[:30]
    for row in assets:
        offset = row["address"] - 0x02000120
        raw = app[offset:offset + row["bytes"]]
        compressed = zlib.compress(raw, 9)
        assert zlib.decompress(compressed) == raw
        # Independent small blocks approximate random-access index overhead.
        blocks = [raw[i:i + 256] for i in range(0, len(raw), 256)]
        block_bytes = sum(len(zlib.compress(b, 9)) for b in blocks) + 4 * (len(blocks) + 1)
        row.update(zlib_bytes=len(compressed), savings=row["bytes"] - len(compressed),
                   indexed_256_byte_blocks=block_bytes,
                   raw_sha256=hashlib.sha256(raw).hexdigest())
    report = dict(schema="lunar-native-footprint-experiment-v1", app_bytes=len(app),
                  input_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (app_path, symbols_path, sections_path)},
                  top_symbols=sorted(rows, key=lambda r: r["bytes"], reverse=True)[:30],
                  data_experiments=assets, runtime_decoder_verified=False,
                  physical_storage_admitted=False)
    output.write_text(json.dumps(report, indent=2) + "\n")
    for row in assets[:8]:
        print(row["name"], row["bytes"], row["zlib_bytes"], row["indexed_256_byte_blocks"])


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rank retained native ELF symbols by linked size; performs no build or device I/O."""
import argparse
from pathlib import Path


def symbols(path):
    rows = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if ".text" not in fields:
            continue
        section = fields.index(".text")
        if section + 1 >= len(fields):
            continue
        try:
            address, size = int(fields[0], 16), int(fields[section + 1], 16)
        except ValueError:
            continue
        if size:
            rows.append({
                "address": address,
                "bytes": size,
                "kind": "code" if "F" in fields[:section] else "data",
                "name": fields[-1],
            })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbols", type=Path, nargs="?", default=Path(
        "build/native-save-scheduler-20261014/save-scheduler-link-v1/symbols.txt"))
    parser.add_argument("--limit", type=int, default=40)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    rows = sorted(symbols(args.symbols), key=lambda row: row["bytes"], reverse=True)
    print(f"linked symbols: {len(rows)}; source: {args.symbols}")
    print(" bytes   kind address   symbol")
    for row in rows[:args.limit]:
        print(f"{row['bytes']:6}  {row['kind']:4} {row['address']:08x}  {row['name']}")


if __name__ == "__main__":
    main()

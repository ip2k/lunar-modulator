#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check exact binary32 row duplication in the generated 9W9 pot table."""
import re
import struct
from pathlib import Path


SOURCE = Path("engines/third_party/fm1-x0x/gen/x0x_drum_tables.h")


def main():
    text = SOURCE.read_text()
    match = re.search(r"x0x_pot_exp\[19\]\[128\]\s*=\s*\{(.*?)\n\};", text, re.S)
    if not match:
        raise SystemExit(f"table not found: {SOURCE}")
    row_texts = re.findall(r"\{([^{}]*)\}", match.group(1), re.S)
    rows = []
    for row_text in row_texts:
        literals = re.findall(r"(?<![A-Za-z0-9_])[-+]?(?:\d+\.?(?:\d*)?|\.\d+)(?:[eE][-+]?\d+)?f", row_text)
        if len(literals) != 128:
            raise SystemExit(f"expected 128 floats per row, found {len(literals)}")
        rows.append(b"".join(struct.pack("<f", float(value[:-1])) for value in literals))
    if len(rows) != 19:
        raise SystemExit(f"expected 19 rows, found {len(rows)}")
    distinct = len(set(rows))
    print(
        f"source={SOURCE}; rows={len(rows)}; widths={[128] * len(rows)}; "
        f"bytes={sum(map(len, rows))}; distinct_byte_rows={distinct}; "
        f"exact_dedup_saving={(len(rows) - distinct) * len(rows[0])}"
    )


if __name__ == "__main__":
    main()

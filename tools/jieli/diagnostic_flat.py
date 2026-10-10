#!/usr/bin/env python3
"""MIT. Assemble vendor objcopy's single-section exports at their load addresses."""
import sys
from pathlib import Path
from audit_link import Elf
from diagnostic_report import FLASH, BUDGET


def assemble(image, fragments):
    length = image.symbol_value("__flash_end") - FLASH
    if not 0 < length <= BUDGET:
        raise ValueError("invalid diagnostic flash bounds")
    result = bytearray(length)
    for name in ("entry", "text", "data"):
        section = next(section for section in image.sections if section["name"] == "." + name)
        blob = fragments[name]
        load = image.symbol_value("__data_load") if name == "data" else section["addr"]
        offset = load - FLASH
        if len(blob) != section["size"] or not 0 <= offset <= offset + len(blob) <= length:
            raise ValueError(f"invalid objcopy export: {name}")
        result[offset:offset + len(blob)] = blob
    return bytes(result)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    try:
        image = Elf((out / "diagnostic.elf").read_bytes())
        fragments = {name: (out / (name + ".bin")).read_bytes() for name in ("entry", "text", "data")}
        (out / "diagnostic.bin").write_bytes(assemble(image, fragments))
    except (ValueError, TypeError, StopIteration) as exc:
        print(f"diagnostic_flat: {exc}", file=sys.stderr)
        sys.exit(1)

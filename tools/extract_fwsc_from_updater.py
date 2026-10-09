#!/usr/bin/env python3
"""Carve the embedded FM-1 firmware package (.fwsc) out of an M-UPGRADE-FM1 updater.

M-VAVE's updater (M-UPGRADE-FM1.app on macOS, M-UPGRADE-FM1.exe on Windows) is
a Qt6 program that embeds the firmware as a Qt resource ``:/Resources/FM-1.fwsc``.
Qt stores each resource blob as a 4-byte big-endian length followed by the data.

Rather than hard-coding offsets per updater version (AL-255's extractor does
that for the 2026-07-06 Windows build), this tool locates the package by its
structure, which is the same in every known version:

* the package ends with a UFW trailer whose ``JLUFW`` marker sits exactly
  16 bytes before the end of the file (verified on the V13 and V14 packages);
* the flash header near the start carries the chip name ``AC791N`` at
  offset ``0x424``;
* the big-endian length word immediately precedes the package.

For every ``JLUFW`` marker we walk back over plausible package sizes looking
for a length word that lands exactly on the marker + 16, then confirm the
``AC791N`` marker. Universal (fat) Mach-O binaries contain the resource once
per architecture slice; identical copies are written once.

Usage:
    python3 tools/extract_fwsc_from_updater.py /path/to/M-UPGRADE-FM1 -o FM-1_v15.fwsc

For a macOS disk image:
    hdiutil attach ~/Downloads/M-UPGRADE-FM1*.dmg
    python3 tools/extract_fwsc_from_updater.py \
        "/Volumes/<name>/M-UPGRADE-FM1.app/Contents/MacOS/M-UPGRADE-FM1" -o FM-1_v15.fwsc

Then unpack with kagaimiq's jl-misctools:
    python3 jl-misctools/firmware/fwunpack_newfw.py FM-1_v15.fwsc

This tool never touches the device. Do not commit the extracted package.
"""

import argparse
import hashlib
import sys

TRAILER = b"JLUFW"
TRAILER_TO_END = 16          # bytes from the start of 'JLUFW' to end of file
CHIP_MARK = b"AC791N"
CHIP_MARK_OFFSET = 0x424
MIN_SIZE = 200 * 1024        # plausible .fwsc size window
MAX_SIZE = 4 * 1024 * 1024


def find_packages(blob):
    found = {}
    pos = blob.find(TRAILER)
    while pos >= 0:
        end = pos + TRAILER_TO_END
        lo = max(0, end - MAX_SIZE)
        hi = end - MIN_SIZE
        for start in range(hi, lo - 1, -1):
            if start < 4:
                break
            size = int.from_bytes(blob[start - 4:start], "big")
            if size == end - start:
                pkg = blob[start:end]
                if pkg[CHIP_MARK_OFFSET:CHIP_MARK_OFFSET + len(CHIP_MARK)] == CHIP_MARK:
                    found.setdefault(hashlib.sha256(pkg).hexdigest(), (start, pkg))
                    break
        pos = blob.find(TRAILER, pos + 1)
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("updater", help="M-UPGRADE-FM1 executable (Mach-O or PE)")
    ap.add_argument("-o", "--output", default="FM-1.fwsc",
                    help="output path (a suffix is added if several distinct packages are found)")
    args = ap.parse_args()

    blob = open(args.updater, "rb").read()
    print(f"updater: {args.updater} ({len(blob)} bytes) sha256 {hashlib.sha256(blob).hexdigest()}")
    found = find_packages(blob)
    if not found:
        print("no embedded .fwsc found (no JLUFW trailer with a matching Qt length prefix)")
        return 1
    for n, (digest, (start, pkg)) in enumerate(sorted(found.items(), key=lambda kv: kv[1][0])):
        out = args.output if len(found) == 1 else f"{args.output}.{n}"
        with open(out, "wb") as fh:
            fh.write(pkg)
        print(f"wrote {out}: {len(pkg)} bytes from offset 0x{start:X}, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

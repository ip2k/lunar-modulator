#!/usr/bin/env python3
"""Find the msfa/Dexed FM algorithm table in an M-VAVE FM-1 application image.

Google's music-synthesizer-for-android (msfa) defines the 32 DX7 algorithms as a
32x6 byte table (``FmCore::algorithms`` in ``fm_core.cc``). Each byte holds bus
flags for one operator:

    OUT_BUS_ONE 0x01  OUT_BUS_TWO 0x02  OUT_BUS_ADD 0x04
    IN_BUS_ONE  0x10  IN_BUS_TWO  0x20  FB_IN 0x40  FB_OUT 0x80

The table is constant data, so it survives compilation unchanged. Finding it in
``app.bin`` is strong evidence that the firmware embeds the msfa engine (the
core of Dexed, Synth_Dexed, MicroDexed and MiniDexed).

Usage:
    python3 tools/check_msfa_table.py path/to/app.bin

Tested against the FM-1 V13 (FM-1_009) and V14 (FM-1_014) images unpacked by
AL-255/FM-1-RE: the table is found at 0x8C46C and 0x8CBCC respectively, and all
rows match msfa except algorithms 4 and 6, where the first operator carries
0x41 instead of 0xC1 (the Dexed-family feedback fix for those algorithms).

Vendor firmware is not included in this repository; obtain ``app.bin`` by
unpacking an official ``FM-1.fwsc`` with kagaimiq's jl-misctools.
"""

import sys

# Table as in Google's msfa fm_core.cc (Apache-2.0), rows = algorithms 1..32.
MSFA_ALGORITHMS = [
    (0xC1, 0x11, 0x11, 0x14, 0x01, 0x14),  # 1
    (0x01, 0x11, 0x11, 0x14, 0xC1, 0x14),  # 2
    (0xC1, 0x11, 0x14, 0x01, 0x11, 0x14),  # 3
    (0xC1, 0x11, 0x94, 0x01, 0x11, 0x14),  # 4
    (0xC1, 0x14, 0x01, 0x14, 0x01, 0x14),  # 5
    (0xC1, 0x94, 0x01, 0x14, 0x01, 0x14),  # 6
    (0xC1, 0x11, 0x05, 0x14, 0x01, 0x14),  # 7
    (0x01, 0x11, 0xC5, 0x14, 0x01, 0x14),  # 8
    (0x01, 0x11, 0x05, 0x14, 0xC1, 0x14),  # 9
    (0x01, 0x05, 0x14, 0xC1, 0x11, 0x14),  # 10
    (0xC1, 0x05, 0x14, 0x01, 0x11, 0x14),  # 11
    (0x01, 0x05, 0x05, 0x14, 0xC1, 0x14),  # 12
    (0xC1, 0x05, 0x05, 0x14, 0x01, 0x14),  # 13
    (0xC1, 0x05, 0x11, 0x14, 0x01, 0x14),  # 14
    (0x01, 0x05, 0x11, 0x14, 0xC1, 0x14),  # 15
    (0xC1, 0x11, 0x02, 0x25, 0x05, 0x14),  # 16
    (0x01, 0x11, 0x02, 0x25, 0xC5, 0x14),  # 17
    (0x01, 0x11, 0x11, 0xC5, 0x05, 0x14),  # 18
    (0xC1, 0x14, 0x14, 0x01, 0x11, 0x14),  # 19
    (0x01, 0x05, 0x14, 0xC1, 0x14, 0x14),  # 20
    (0x01, 0x14, 0x14, 0xC1, 0x14, 0x14),  # 21
    (0xC1, 0x14, 0x14, 0x14, 0x01, 0x14),  # 22
    (0xC1, 0x14, 0x14, 0x01, 0x14, 0x04),  # 23
    (0xC1, 0x14, 0x14, 0x14, 0x04, 0x04),  # 24
    (0xC1, 0x14, 0x14, 0x04, 0x04, 0x04),  # 25
    (0xC1, 0x05, 0x14, 0x01, 0x14, 0x04),  # 26
    (0x01, 0x05, 0x14, 0xC1, 0x14, 0x04),  # 27
    (0x04, 0xC1, 0x11, 0x14, 0x01, 0x14),  # 28
    (0xC1, 0x14, 0x01, 0x14, 0x04, 0x04),  # 29
    (0x04, 0xC1, 0x11, 0x14, 0x04, 0x04),  # 30
    (0xC1, 0x14, 0x04, 0x04, 0x04, 0x04),  # 31
    (0xC4, 0x04, 0x04, 0x04, 0x04, 0x04),  # 32
]

# Rows 1-3 are identical in every known variant; use them as the anchor.
ANCHOR = bytes(b for row in MSFA_ALGORITHMS[:3] for b in row)

FLAGS = [
    (0x80, "FB_OUT"), (0x40, "FB_IN"), (0x20, "IN_BUS_TWO"), (0x10, "IN_BUS_ONE"),
    (0x04, "OUT_BUS_ADD"), (0x02, "OUT_BUS_TWO"), (0x01, "OUT_BUS_ONE"),
]


def describe(byte):
    names = [name for bit, name in FLAGS if byte & bit]
    return "|".join(names) if names else "0"


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    data = open(argv[1], "rb").read()
    hits = []
    pos = data.find(ANCHOR)
    while pos >= 0:
        hits.append(pos)
        pos = data.find(ANCHOR, pos + 1)
    if not hits:
        print("msfa algorithm table anchor (algorithms 1-3) NOT found")
        return 1
    status = 0
    for off in hits:
        table = data[off:off + 32 * 6]
        print(f"msfa algorithm table at application file offset 0x{off:X}")
        print("  Runtime address requires a verified startup memory map; see tools/fm1_decode.py.")
        diffs = 0
        for alg in range(32):
            row = tuple(table[alg * 6:(alg + 1) * 6])
            ref = MSFA_ALGORITHMS[alg]
            mark = "" if row == ref else "   <-- differs from msfa"
            if row != ref:
                diffs += 1
            print(f"  alg {alg + 1:2d}: {' '.join(f'{b:02x}' for b in row)}{mark}")
            if row != ref:
                for op, (a, b) in enumerate(zip(row, ref), start=1):
                    if a != b:
                        print(f"           op{op}: {describe(a)} (msfa: {describe(b)})")
        print(f"  {32 - diffs}/32 rows identical to msfa fm_core.cc")
        if diffs > 2:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main(sys.argv))

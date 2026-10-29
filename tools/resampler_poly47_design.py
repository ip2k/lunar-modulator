#!/usr/bin/env python3
"""Design of fm1_resampler.h's fixed 51/47 polyphase converter (FM1_RESAMPLER_POLY47).

Plaits-derived engines (Drums, Macro, Macro Heavy, Six-Op) run at Plaits'
47,872.34 Hz; the FM-1 runs at 44,118 Hz, and 44,118 x 51 / 47 = 47,872.72 Hz,
7.9 ppm from Plaits' rate (0.014 cent). At exactly 51/47 a resampler needs no
phase interpolation: output k sits at input time k x 51 / 47, whose fractional
part is one of 47 phases q / 47, and each output is one 48-tap dot product with
that phase's row of a fixed table (engines/resampler.md, "The 51/47 fast
path").

The prototype is a Kaiser-windowed sinc (beta 10, cut off at 20,800 Hz at a
44,118 Hz output: 0.4715 of the output rate), 48 input samples wide (half
width 24). Row q holds h(q / 47 + 23 - k) for k = 0 .. 47, normalised so the
row sums to exactly 1 (every phase passes DC at unity, so the phases leave no
spur at the phase pattern's rate). Row 47 - q is row q reversed, so only rows
0 .. 23 are stored: 24 x 48 floats, 4,608 bytes.

    python3 tools/resampler_poly47_design.py            # print the C table
    python3 tools/resampler_poly47_design.py --check    # compare with the header
    python3 tools/resampler_poly47_design.py --write    # rewrite the header's table

Pure Python (no numpy), so the test suite can import it. MIT licence.
"""
import argparse
import math
import pathlib
import struct
import sys

PHASES = 47            # interpolation factor: the output's positions fall on q / 47
DECIMATION = 51        # 47 outputs take 51 inputs: each output advances 51 / 47
TAPS = 48              # input samples per output
ROWS = PHASES // 2 + 1  # rows 0 .. 23 stored; row q >= 24 is row 47 - q reversed
BETA = 10.0
HOST_RATE = 44118.0
CUTOFF_HZ = 20800.0    # at a 44,118 Hz output
# The cut-off in cycles per input sample: input rate = output rate x 51 / 47.
CUTOFF = CUTOFF_HZ / HOST_RATE * PHASES / DECIMATION
HALF_WIDTH = TAPS // 2  # 24 input samples either side
# Output k reads the 48 inputs from floor(k x 51 / 47) - 23 on; its time is
# 23 + q / 47 input samples after the first of them.
CENTRE = TAPS // 2 - 1

HEADER = pathlib.Path(__file__).resolve().parents[1] / "engines" / "include" / "fm1_resampler.h"
BEGIN = "static const float fm1_resampler_poly47[FM1_RESAMPLER_POLY47_ROWS][FM1_RESAMPLER_POLY47_TAPS] = {"
END = "};"


def f32(x):
    return struct.unpack("<f", struct.pack("<f", x))[0]


def bessel_i0(x):
    s = t = 1.0
    k = 1
    while True:
        t *= (x / (2 * k)) ** 2
        s += t
        if t < 1e-21 * s:
            return s
        k += 1


def kaiser(t, half_width=HALF_WIDTH, beta=BETA):
    """The Kaiser window at t samples from the centre; 0 at and beyond the edge."""
    if abs(t) >= half_width:
        return 0.0
    r = t / half_width
    return bessel_i0(beta * math.sqrt(max(0.0, 1.0 - r * r))) / bessel_i0(beta)


def prototype(t):
    """The un-normalised prototype at t input samples: 2 fc sinc(2 fc t) x Kaiser."""
    x = 2.0 * CUTOFF * t
    s = 1.0 if x == 0 else math.sin(math.pi * x) / (math.pi * x)
    return 2.0 * CUTOFF * s * kaiser(t)


def row64(q):
    """Phase q's 48 taps in float64, for q = 0 .. 46: the prototype at
    q / 47 + 23 - k, k = 0 .. 47, scaled to sum to 1."""
    raw = [prototype(q / PHASES + CENTRE - k) for k in range(TAPS)]
    total = sum(raw)
    return [v / total for v in raw]


def table64():
    """All 47 phases in float64 (the reference the header's floats round)."""
    return [row64(q) for q in range(PHASES)]


def stored_rows():
    """The header's table: rows 0 .. 23, rounded to float32."""
    return [[f32(v) for v in row64(q)] for q in range(ROWS)]


def c_float(v):
    s = f"{v:.9g}"
    return (s if any(c in s for c in ".e") else s + ".0") + "f"


def c_table():
    lines = [BEGIN]
    for q, row in enumerate(stored_rows()):
        lines.append(f"  {{ /* q = {q} */")
        for i in range(0, TAPS, 6):
            lines.append("    " + ", ".join(c_float(v) for v in row[i:i + 6]) + ",")
        lines.append("  },")
    lines.append(END)
    return "\n".join(lines)


def header_table(text):
    a = text.index(BEGIN)
    b = text.index("\n" + END, a) + 1 + len(END)
    return a, b


def output64(x, outputs):
    """The converter in float64, from the float64 design: output k is the
    dot product of row (4 k mod 47) with the 48 inputs from
    floor(51 k / 47) - 23 (inputs before 0 are 0). The reference for the
    header's float32 arithmetic."""
    rows = table64()
    y = []
    for k in range(outputs):
        q = (DECIMATION * k) % PHASES
        b = (DECIMATION * k) // PHASES - CENTRE
        row = rows[q]
        acc = 0.0
        for j in range(TAPS):
            i = b + j
            if 0 <= i < len(x):
                acc += row[j] * x[i]
        y.append(acc)
    return y


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 unless the header holds this table")
    ap.add_argument("--write", action="store_true", help="rewrite the header's table")
    args = ap.parse_args(argv)
    table = c_table()
    if not (args.check or args.write):
        print(table)
        return 0
    text = HEADER.read_text()
    a, b = header_table(text)
    if args.check:
        same = text[a:b] == table
        print("header table matches the design" if same else "header table differs from the design")
        return 0 if same else 1
    HEADER.write_text(text[:a] + table + text[b:])
    print(f"wrote {HEADER}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

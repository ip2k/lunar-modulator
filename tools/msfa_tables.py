#!/usr/bin/env python3
"""msfa's start-up tables, made ahead of time: the FM6 engine's sine, exp2
and frequency tables as const data, written into engines/src/msfa_rom.cc.

    python3 tools/msfa_tables.py            # rewrite engines/src/msfa_rom.cc
                                            # and engines/src/msfa_sin_trunc12.h
    python3 tools/msfa_tables.py --check    # exit 1 if either file is stale

msfa (Google's music-synthesizer-for-android, Apache-2.0, vendored in
engines/third_party/msfa) fills three tables in RAM when it starts:
Sin::init (sin.cc), Exp2::init (exp2.cc) and Freqlut::init (freqlut.cc).
Each takes one libm value (cos and sin of 2 pi / 1024, 2^(1/1024)) and then
integer steps or repeated multiplication in doubles. This tool runs the same
steps, with those libm values computed correctly rounded (Decimal), so the
tables come out as msfa's own init makes them on any machine whose libm is
right in the last bit; fm1-dx7-oracle --tables-vs-msfa compares them with
msfa's init, word for word (tests/test_engines_dx7.py). The frequency table
depends on the rate; this file holds it at the FM-1's 44,118 Hz, and the
engine fills one in its instance at any other rate (engines/msfa.md,
"Tables in flash").

It also makes the sine of the build switch FM1_DX7_SINE=trunc12
(engines/Makefile; engines/msfa.md, "The trunc12 sine"): kSinTab12, 4,096
int16 points of one sine cycle, each the value at the middle of its step,
read with no interpolation, and engines/src/msfa_sin_trunc12.h, msfa's sin.h
with only Sin::lookup's tail replaced by that read. The build compiles msfa
against that header in place of the vendored one when the switch says so;
the default, FM1_DX7_SINE=msfa, is msfa's own interpolated sine.

The values are mathematical constants in msfa's fixed-point formats, not
code; the file is MIT like the rest of this repository. The trunc12 header
is derived from msfa's Apache-2.0 sin.h and keeps its licence.
"""
from __future__ import annotations

import argparse
import math
import sys
from decimal import Decimal, getcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "engines" / "src" / "msfa_rom.cc"
SIN_H = ROOT / "engines" / "third_party" / "msfa" / "sin.h"
OUT_SIN12 = ROOT / "engines" / "src" / "msfa_sin_trunc12.h"
FM1_RATE = 44118             # the FM-1's rate: the frequency table held as const data
SIN_N = 1024                 # SIN_N_SAMPLES, EXP2_N_SAMPLES, Freqlut's N_SAMPLES
SIN12_LG_N = 12              # trunc12: phase bits that index the table
SIN12_N = 1 << SIN12_LG_N    # 4,096 points
SIN12_SCALE = 1 << 15        # Q15; Sin::lookup returns it times 2^9, msfa's Q24

getcontext().prec = 60
PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494")


def dsin(x: Decimal) -> Decimal:
    term, total, k = x, x, 1
    while abs(term) > Decimal(10) ** -55:
        term = -term * x * x / ((2 * k) * (2 * k + 1))
        total += term
        k += 1
    return total


def dcos(x: Decimal) -> Decimal:
    term, total, k = Decimal(1), Decimal(1), 1
    while abs(term) > Decimal(10) ** -55:
        term = -term * x * x / ((2 * k - 1) * (2 * k))
        total += term
        k += 1
    return total


# 2^(1/1024), correctly rounded to a double: exp2(1.0 / 1024) in Exp2::init
# and pow(2, 1.0 / 1024) in Freqlut::init, which the compilers fold.
INC = float((Decimal(2).ln() / SIN_N).exp())


def sin_table() -> list[int]:
    """Sin::init with SIN_DELTA: 1,024 points of a Q24 sine in the odd
    entries, each one's step to the next in the even ones."""
    dphase = float(2 * PI / SIN_N)                    # 2 * M_PI / SIN_N_SAMPLES, a double
    c = math.floor(float(dcos(Decimal(dphase))) * (1 << 30) + 0.5)
    s = math.floor(float(dsin(Decimal(dphase))) * (1 << 30) + 0.5)
    u, v, r = 1 << 30, 0, 1 << 29
    tab = [0] * (2 * SIN_N)
    for i in range(SIN_N // 2):
        tab[2 * i + 1] = (v + 32) >> 6
        tab[2 * (i + SIN_N // 2) + 1] = -((v + 32) >> 6)
        t = (u * s + v * c + r) >> 30
        u = (u * c - v * s + r) >> 30
        v = t
    for i in range(SIN_N - 1):
        tab[2 * i] = tab[2 * i + 3] - tab[2 * i + 1]
    tab[2 * SIN_N - 2] = -tab[2 * SIN_N - 1]
    return tab


def sin12_table() -> list[int]:
    """The trunc12 sine: 4,096 int16 points of one cycle, point i the sine at
    the middle of its step, 2 pi (i + 1/2) / 4096, in Q15, rounded to the
    nearest and held to +-32,767 (the twelve points nearest each peak, whose
    values round to 32,768). Sin::lookup reads point (phase >> 12) & 4095 with no
    interpolation. Sampling the middle of each step rather than its start
    centres the phase error on zero, about 6 dB less error than a table of
    sin(2 pi i / 4096) read the same way, at no cost; the table stays odd
    (point 4095 - i is minus point i), so it adds no offset."""
    tab = []
    for i in range(SIN12_N):
        x = dsin(2 * PI * (2 * i + 1) / (2 * SIN12_N)) * SIN12_SCALE
        v = int(x.to_integral_value(rounding="ROUND_HALF_EVEN"))
        tab.append(max(-(SIN12_SCALE - 1), min(SIN12_SCALE - 1, v)))
    return tab


def exp2_table() -> list[int]:
    """Exp2::init: 2^(i / 1024) in Q30 in the odd entries, steps in the even
    ones; the last step reaches 2^31 (computed in 32 unsigned bits)."""
    y, tab = float(1 << 30), [0] * (2 * SIN_N)
    for i in range(SIN_N):
        tab[2 * i + 1] = math.floor(y + 0.5)
        y *= INC
    for i in range(SIN_N - 1):
        tab[2 * i] = tab[2 * i + 3] - tab[2 * i + 1]
    tab[2 * SIN_N - 2] = (1 << 31) - tab[2 * SIN_N - 1]
    return tab


def freq_table(rate: int) -> list[int]:
    """Freqlut::init(rate): 1,025 phase increments, an octave from
    2^44 / rate (logfreq 0, the top of msfa's 20 octaves)."""
    y, tab = float(1 << 44) / rate, []
    for _ in range(SIN_N + 1):
        tab.append(math.floor(y + 0.5))
        y *= INC
    return tab


def c_array(name: str, values: list[int], comment: str, ctype: str = "int32_t",
            per_line: int = 8) -> str:
    lines = [f"// {comment}", f"extern const {ctype} {name}[{len(values)}] = {{"]
    for i in range(0, len(values), per_line):
        lines.append("  " + ", ".join(f"{v}" for v in values[i:i + per_line]) + ",")
    lines.append("};")
    return "\n".join(lines) + "\n"


def source() -> str:
    head = f"""\
// msfa_rom.cc -- msfa's sine, exp2 and frequency tables as const data, which
// the FM-1 keeps in flash, for the FM6 engine (src/msfa_dx7.cc). Generated by
// tools/msfa_tables.py, which runs the steps of msfa's Sin::init, Exp2::init
// and Freqlut::init({FM1_RATE}) (third_party/msfa, Apache-2.0); do not edit.
// fm1-dx7-oracle --tables-vs-msfa checks them against msfa's own init, word
// for word. The values are msfa's fixed-point constants; MIT licence, like
// the rest of this repository. engines/msfa.md, "Tables in flash".

#include "msfa.h"   // the declarations these definitions must match

namespace fm1_msfa {{

"""
    body = "\n".join([
        # One sine table per build (FM1_DX7_SINE, engines/Makefile): the
        # other is left out, so the switch costs no flash or RAM.
        "#if !FM1_DX7_SINE_TRUNC12\n"
        + c_array("kSinTab", sin_table(),
                  "Sin::init (SIN_DELTA): odd entries a Q24 sine, even ones the step to the next.")
        + "#else\n"
        + c_array("kSinTab12", sin12_table(),
                  "FM1_DX7_SINE=trunc12: one cycle in 4,096 Q15 points, each its step's middle "
                  "(src/msfa_sin_trunc12.h).", "int16_t", 12)
        + "#endif  // FM1_DX7_SINE_TRUNC12\n",
        c_array("kExp2Tab", exp2_table(),
                "Exp2::init: odd entries 2^(i / 1024) in Q30, even ones the step to the next."),
        c_array("kFreqLut44118", freq_table(FM1_RATE),
                f"Freqlut::init({FM1_RATE}): phase increments over an octave, 2^44 / rate up."),
    ])
    return head + body + "\n}  // namespace fm1_msfa\n"


# The tail of msfa's sin.h from its table declaration on (upstream a99ac7a,
# third_party/msfa/UPSTREAM.md): what the trunc12 header replaces. Anything
# else in the vendored file changing stops the generator.
SIN_H_TAIL = """#ifdef SIN_DELTA
extern int32_t sintab[SIN_N_SAMPLES << 1];
#else
extern int32_t sintab[SIN_N_SAMPLES + 1];
#endif

#ifdef SIN_INLINE
inline
int32_t Sin::lookup(int32_t phase) {
  const int SHIFT = 24 - SIN_LG_N_SAMPLES;
  int lowbits = phase & ((1 << SHIFT) - 1);
#ifdef SIN_DELTA
  int phase_int = (phase >> (SHIFT - 1)) & ((SIN_N_SAMPLES - 1) << 1);
  int dy = sintab[phase_int];
  int y0 = sintab[phase_int + 1];

  return y0 + (((int64_t)dy * (int64_t)lowbits) >> SHIFT);
#else
  int phase_int = (phase >> SHIFT) & (SIN_N_SAMPLES - 1);
  int y0 = sintab[phase_int];
  int y1 = sintab[phase_int + 1];

  return y0 + (((int64_t)(y1 - y0) * (int64_t)lowbits) >> SHIFT);
#endif
}
#endif
"""

SIN12_NOTICE = """/*
 * engines/src/msfa_sin_trunc12.h -- msfa's sin.h (third_party/msfa/sin.h,
 * above) with Sin::lookup replaced, for the build switch FM1_DX7_SINE=trunc12
 * (engines/Makefile; engines/msfa.md, "The trunc12 sine"). Modified by the
 * Lunar Modulator project: generated by tools/msfa_tables.py from the
 * vendored file, whose text up to the table declaration is kept unchanged;
 * do not edit. Apache-2.0, like the file it is derived from.
 *
 * The build copies msfa's files into $(BUILD)/gen/msfa-trunc12/ with this
 * one as sin.h (mk/msfa.mk), because msfa's own .cc files include "sin.h"
 * from their directory first: every Sin::lookup, the operators' and the
 * LFO's, then reads kSinTab12 (src/msfa_rom.cc), 4,096 points of a cycle,
 * with the phase's top 12 bits and no interpolation.
 */
"""

SIN12_TAIL = """// FM1_DX7_SINE=trunc12: src/msfa.h checks that the build switch agrees.
#define FM1_MSFA_SIN_TRUNC12 1

// One sine cycle in 4,096 Q15 points, each the value at its step's middle
// (src/msfa_rom.cc, made by tools/msfa_tables.py). msfa's sintab is not
// declared: nothing reads it in this build.
extern const int16_t kSinTab12[1 << 12];

#ifdef SIN_INLINE
inline
int32_t Sin::lookup(int32_t phase) {
  // Bits 12..23 of the Q24 phase pick the point; Q15 times 2^9 is msfa's
  // Q24 (a multiply, not a shift: the point may be negative).
  return static_cast<int32_t>(kSinTab12[(phase >> (24 - 12)) & ((1 << 12) - 1)]) * 512;
}
#endif
"""


def sin12_header() -> str:
    """msfa's sin.h with its table declaration and Sin::lookup replaced."""
    vendored = SIN_H.read_text()
    if vendored.rstrip(" ").count(SIN_H_TAIL) != 1 or not vendored.rstrip(" ").endswith(SIN_H_TAIL):
        raise SystemExit(f"{SIN_H} is not the sin.h this generator knows: review the trunc12 header")
    head = vendored.rstrip(" ")[: -len(SIN_H_TAIL)]
    licence_end = head.index(" */\n") + len(" */\n")
    return head[:licence_end] + SIN12_NOTICE + head[licence_end:] + SIN12_TAIL


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if msfa_rom.cc or msfa_sin_trunc12.h is stale")
    a = ap.parse_args()
    outputs = ((OUT, source()), (OUT_SIN12, sin12_header()))
    if a.check:
        stale = [p for p, text in outputs if not p.exists() or p.read_text() != text]
        for p in stale:
            print(f"{p} is stale: run tools/msfa_tables.py", file=sys.stderr)
        return 1 if stale else 0
    for p, text in outputs:
        p.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

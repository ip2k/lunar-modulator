#!/usr/bin/env python3
"""Derived tables computed at startup on the FM-1 (size lever (a),
notes/2026-11-10-init-tables.md): writes engines/src/fm1_init_tables.cc.

    python3 tools/init_tables.py            # rewrite engines/src/fm1_init_tables.cc
    python3 tools/init_tables.py --check    # exit 1 if it is stale

Four tables the FM-1 image keeps in cache RAM are each a simple function of a
smaller part of themselves:

- kSinTab12 (engines/src/msfa_rom.cc, 4,096 int16): a quarter wave mirrored
  and negated. Seed: points 0..1023.
- kExp2Tab (msfa_rom.cc, 2,048 int32): odd entries are the values, even ones
  the step to the next value (the last to 2^31). Seed: the 1,024 values.
- fm1_resampler_kernel_pairs (prepare-renderer-devkit.py
  resampler_slope_definition, 1,536 float): each stage-1 kernel tap and its
  slope, (k[i+1] - k[i]) * 2^-16 in float32. Seed: the 769-tap kernel
  (engines/include/fm1_resampler.h).
- plaits::lut_sine (Mutable Instruments' plaits/resources.cc, 641 float): a
  sine with 512 points a cycle and a 128-point wrap. Seed: points 0..128 and
  the two literals at 256 and 512 that are not exact negations.

The generated file defines the full tables as zero-initialised, non-const
arrays in a NOLOAD cache-RAM section and the seeds as const data, and
lunar_init_tables() fills the tables with integer copies, sign flips and one
float subtraction and multiply per slope. Before writing anything this tool
checks every identity against the stored tables, so a table that is not
exactly derivable stops it. tests/test_init_tables.py compiles the file on
the host and compares every entry with the stored tables, and the dev-kit
image checks the same per-table hashes on the target
(lunar_init_tables_check, FM1_INIT_TABLES_CHECK).

The vendored definitions are not touched: the preparer
(prepare-pipeline-devkit.py --init-tables) removes them from its private
copies only. The lut_sine seed is 131 of Mutable Instruments' coefficients
(MIT, Emilie Gillet, engines/third_party/mutable); the rest is ours (MIT).
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "engines" / "src" / "fm1_init_tables.cc"
MSFA_ROM = ROOT / "engines" / "src" / "msfa_rom.cc"
RESAMPLER_H = ROOT / "engines" / "include" / "fm1_resampler.h"
RESOURCES = ROOT / "engines" / "third_party" / "mutable" / "plaits" / "resources.cc"
RENDERER_PREPARE = ROOT / "tools" / "jieli" / "prepare-renderer-devkit.py"

SIN12_N, SIN12_Q = 4096, 1024
EXP2_N = 1024
KERNEL_LEN = 769
LUT_SINE_N = 641
FNV_OFFSET, FNV_PRIME = 2166136261, 16777619
TABLES = ("kSinTab12", "kExp2Tab", "fm1_resampler_kernel_pairs", "lut_sine")


def f32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def f32_bits(x: float) -> int:
    return struct.unpack("<I", struct.pack("<f", x))[0]


def array_body(text: str, head: str) -> str:
    if text.count(head) != 1:
        raise ValueError("Expected one definition: " + head)
    return text.split(head, 1)[1].split("};", 1)[0]


def ints(body: str) -> list[int]:
    return [int(x) for x in body.replace("\n", " ").split(",") if x.strip()]


def literals(body: str) -> list[str]:
    return [x.strip() for x in body.replace("\n", " ").split(",") if x.strip()]


def stored_sin12(text: str) -> list[int]:
    v = ints(array_body(text, "extern const int16_t kSinTab12[4096] = {"))
    if len(v) != SIN12_N:
        raise ValueError("kSinTab12 is not 4,096 points")
    return v


def stored_exp2(text: str) -> list[int]:
    v = ints(array_body(text, "extern const int32_t kExp2Tab[2048] = {"))
    if len(v) != 2 * EXP2_N:
        raise ValueError("kExp2Tab is not 2,048 words")
    return v


def kernel_definition(text: str) -> str:
    m = re.findall(r"static const float fm1_resampler_kernel\[FM1_RESAMPLER_KERNEL_LEN\] = \{.*?\n\};", text, re.S)
    if len(m) != 1:
        raise ValueError("Expected one stage-1 kernel definition")
    return m[0]


def kernel_literals(text: str) -> list[str]:
    v = literals(kernel_definition(text).split(" = {", 1)[1].rsplit("};", 1)[0])
    if len(v) != KERNEL_LEN or any(not re.fullmatch(r"[-+0-9.eE]+f", x) for x in v):
        raise ValueError("Unexpected stage-1 kernel literals")
    return v


def lut_sine_literals(text: str) -> list[str]:
    v = literals(array_body(text, "const float lut_sine[] = {"))
    if len(v) != LUT_SINE_N or any(not re.fullmatch(r"-?[0-9.]+e[-+][0-9]+", x) for x in v):
        raise ValueError("Unexpected lut_sine literals")
    return v


def renderer_prepare():
    spec = importlib.util.spec_from_file_location("renderer_prepare_tables", RENDERER_PREPARE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stored_pairs(header: str) -> list[float]:
    """The pairs exactly as the stored-table build defines them (float32 values)."""
    definition = renderer_prepare().resampler_slope_definition(kernel_definition(header))
    v = literals(definition.split(" = {", 1)[1].rsplit("};", 1)[0])
    if len(v) != 2 * (KERNEL_LEN - 1):
        raise ValueError("Unexpected kernel pair count")
    return [f32(float(x.rstrip("f"))) for x in v]


def stored_lut_sine(resources: str) -> list[float]:
    return [f32(float(x)) for x in lut_sine_literals(resources)]


# The generator's derivations, written exactly as the C++ below computes them.
def derive_sin12(quarter: list[int]) -> list[int]:
    t = [0] * SIN12_N
    for k, s in enumerate(quarter):
        t[k] = t[2047 - k] = s
        t[2048 + k] = t[4095 - k] = -s
    return t


def derive_exp2(values: list[int]) -> list[int]:
    t = [0] * (2 * EXP2_N)
    for i, v in enumerate(values):
        nxt = values[i + 1] if i + 1 < EXP2_N else 1 << 31
        delta = (nxt - v) & 0xFFFFFFFF
        t[2 * i] = delta - (1 << 32) if delta >= 1 << 31 else delta
        t[2 * i + 1] = v
    return t


def derive_pairs(kernel: list[float]) -> list[float]:
    t = []
    for i in range(KERNEL_LEN - 1):
        t += [kernel[i], f32(f32(kernel[i + 1] - kernel[i]) * (1.0 / 65536.0))]
    return t


def derive_lut_sine(seed: list[float]) -> list[float]:
    s = [0.0] * LUT_SINE_N
    s[:129] = seed[:129]
    for k in range(1, 128):
        s[128 + k] = seed[128 - k]
    s[256] = seed[129]
    for k in range(1, 256):
        s[256 + k] = -s[k]
    s[512] = seed[130]
    for k in range(1, 129):
        s[512 + k] = s[k]
    return s


def fnv(words) -> int:
    h = FNV_OFFSET
    for w in words:
        h = ((h ^ (w & 0xFFFFFFFF)) * FNV_PRIME) & 0xFFFFFFFF
    return h


def hashes(sin12, exp2, pairs, lut_sine) -> list[int]:
    return [fnv(x & 0xFFFF for x in sin12), fnv(exp2), fnv(f32_bits(x) for x in pairs),
            fnv(f32_bits(x) for x in lut_sine)]


def tables(root: Path = ROOT) -> dict:
    """Parse the stored tables and seeds; refuse unless every identity holds exactly."""
    rom = (root / MSFA_ROM.relative_to(ROOT)).read_text()
    header = (root / RESAMPLER_H.relative_to(ROOT)).read_text()
    resources = (root / RESOURCES.relative_to(ROOT)).read_text()
    sin12, exp2 = stored_sin12(rom), stored_exp2(rom)
    kernel_lit = kernel_literals(header)
    kernel = [f32(float(x[:-1])) for x in kernel_lit]
    pairs = stored_pairs(header)
    sine_lit = lut_sine_literals(resources)
    lut_sine = stored_lut_sine(resources)
    quarter = sin12[:SIN12_Q]
    values = exp2[1::2]
    sine_seed_lit = sine_lit[:129] + [sine_lit[256], sine_lit[512]]
    sine_seed = [f32(float(x)) for x in sine_seed_lit]
    checks = (
        ("kSinTab12", derive_sin12(quarter), sin12, lambda x: x & 0xFFFF),
        ("kExp2Tab", derive_exp2(values), exp2, lambda x: x & 0xFFFFFFFF),
        ("fm1_resampler_kernel_pairs", derive_pairs(kernel), pairs, f32_bits),
        ("lut_sine", derive_lut_sine(sine_seed), lut_sine, f32_bits),
    )
    for name, derived, stored, bits in checks:
        bad = [i for i, (a, b) in enumerate(zip(derived, stored)) if bits(a) != bits(b)]
        if len(derived) != len(stored) or bad:
            raise ValueError(f"{name} is not exactly derivable (first mismatch at {bad[:1]})")
    # The mirrored lut_sine literals are also the same text, not only the same float.
    if (any(sine_lit[128 + k] != sine_lit[128 - k] for k in range(1, 128))
            or any(sine_lit[512 + k] != sine_lit[k] for k in range(1, 129))):
        raise ValueError("lut_sine is not exactly derivable (mirrored literals differ in text)")
    return {"sin12": sin12, "exp2": exp2, "pairs": pairs, "lut_sine": lut_sine,
            "quarter": quarter, "values": values, "kernel_literals": kernel_lit,
            "sine_seed_literals": sine_seed_lit,
            "hashes": hashes(sin12, exp2, pairs, lut_sine)}


def rows(items: list[str], per_line: int) -> str:
    return "\n".join("  " + ", ".join(items[i:i + per_line]) + ","
                     for i in range(0, len(items), per_line))


def source(t: dict | None = None) -> str:
    t = t or tables()
    expected = ", ".join(f"0x{h:08x}u" for h in t["hashes"])
    return f"""\
// fm1_init_tables.cc -- four derived tables filled at startup instead of
// stored in flash (size lever (a), notes/2026-11-10-init-tables.md).
// Generated by tools/init_tables.py from engines/src/msfa_rom.cc,
// engines/include/fm1_resampler.h and Mutable Instruments'
// plaits/resources.cc; do not edit. Built only into FM-1 and dev-kit images
// prepared with --init-tables, which drop the stored definitions from their
// private copies; tests/test_init_tables.py compiles it on the host and
// compares every entry with the stored tables.
//
// lunar_init_tables() must run once, on CPU0, before anything reads the
// tables: the preparer calls it at the end of the SDK's setup_arch(), before
// main() creates a task, starts the scheduler or CPU1, or opens audio.
//
// The kSinTab12, kExp2Tab and kernel seeds are ours (MIT). The lut_sine seed
// is 131 coefficients of plaits/resources.cc, Copyright 2016 Emilie Gillet,
// MIT (engines/third_party/mutable/plaits/resources.cc has the notice).

#include <stdint.h>
#include <string.h>

// The tables are zero-initialised storage in a NOLOAD cache-RAM section: no
// flash image. The host test builds with an empty section.
#ifndef FM1_INIT_TABLES_SECTION
#define FM1_INIT_TABLES_SECTION __attribute__((section(".lunar_cache_init")))
#endif

// Non-const, here and in the prepared declarations: a const definition with
// no initialiser would let LTO fold every read to zero.
namespace fm1_msfa {{
int16_t kSinTab12[{SIN12_N}] FM1_INIT_TABLES_SECTION;
int32_t kExp2Tab[{2 * EXP2_N}] FM1_INIT_TABLES_SECTION;
}}  // namespace fm1_msfa
namespace plaits {{
float lut_sine[{LUT_SINE_N}] FM1_INIT_TABLES_SECTION;
}}  // namespace plaits
float fm1_resampler_kernel_pairs[{2 * (KERNEL_LEN - 1)}] FM1_INIT_TABLES_SECTION;

namespace {{

// kSinTab12 points 0..1023: the first quarter wave.
const int16_t kSinQuarter[{SIN12_Q}] = {{
{rows([str(x) for x in t["quarter"]], 12)}
}};

// kExp2Tab's odd entries: 2^(i / 1024) in Q30.
const int32_t kExp2Values[{EXP2_N}] = {{
{rows([str(x) for x in t["values"]], 6)}
}};

// The stage-1 kernel, fm1_resampler.h's literals.
const float kKernel[{KERNEL_LEN}] = {{
{rows(t["kernel_literals"], 6)}
}};

// lut_sine points 0..128, then the literals at 256 and 512: double literals
// rounded to float, exactly as resources.cc writes them.
const float kSineSeed[131] = {{
{rows(t["sine_seed_literals"], 4)}
}};

}}  // namespace

extern "C" void lunar_init_tables(void) {{
  for (int k = 0; k < {SIN12_Q}; k++) {{
    const int16_t s = kSinQuarter[k];
    fm1_msfa::kSinTab12[k] = s;
    fm1_msfa::kSinTab12[2047 - k] = s;
    fm1_msfa::kSinTab12[2048 + k] = (int16_t)-s;
    fm1_msfa::kSinTab12[4095 - k] = (int16_t)-s;
  }}
  for (int i = 0; i < {EXP2_N}; i++) {{
    const uint32_t v = (uint32_t)kExp2Values[i];
    const uint32_t next = i + 1 < {EXP2_N} ? (uint32_t)kExp2Values[i + 1] : 0x80000000u;
    fm1_msfa::kExp2Tab[2 * i] = (int32_t)(next - v);
    fm1_msfa::kExp2Tab[2 * i + 1] = (int32_t)v;
  }}
  for (int i = 0; i < {KERNEL_LEN - 1}; i++) {{
    // float32 throughout, as the stored pairs were rounded (-ffp-contract=off).
    const float a = kKernel[i], b = kKernel[i + 1];
    fm1_resampler_kernel_pairs[2 * i] = a;
    fm1_resampler_kernel_pairs[2 * i + 1] = (b - a) * (1.0f / 65536.0f);
  }}
  float *s = plaits::lut_sine;
  for (int k = 0; k <= 128; k++) s[k] = kSineSeed[k];
  for (int k = 1; k < 128; k++) s[128 + k] = kSineSeed[128 - k];
  s[256] = kSineSeed[129];
  for (int k = 1; k < 256; k++) s[256 + k] = -s[k];
  s[512] = kSineSeed[130];
  for (int k = 1; k <= 128; k++) s[512 + k] = s[k];
}}

#if FM1_INIT_TABLES_CHECK
// FNV-1a over each entry as a 32-bit word (int16 zero-extended, float as its
// bits): compares bit patterns, whatever the byte order. Returns a mask of the
// tables that differ from the stored ones (0: all exact).
static uint32_t fm1_init_tables_fnv(uint32_t h, uint32_t w) {{ return (h ^ w) * {FNV_PRIME}u; }}

extern "C" uint32_t lunar_init_tables_check(uint32_t out[4]) {{
  static const uint32_t kExpected[4] = {{{expected}}};
  uint32_t h = {FNV_OFFSET}u, w, bad = 0;
  for (int i = 0; i < {SIN12_N}; i++) h = fm1_init_tables_fnv(h, (uint16_t)fm1_msfa::kSinTab12[i]);
  out[0] = h;
  h = {FNV_OFFSET}u;
  for (int i = 0; i < {2 * EXP2_N}; i++) h = fm1_init_tables_fnv(h, (uint32_t)fm1_msfa::kExp2Tab[i]);
  out[1] = h;
  h = {FNV_OFFSET}u;
  for (int i = 0; i < {2 * (KERNEL_LEN - 1)}; i++) {{
    memcpy(&w, &fm1_resampler_kernel_pairs[i], 4);
    h = fm1_init_tables_fnv(h, w);
  }}
  out[2] = h;
  h = {FNV_OFFSET}u;
  for (int i = 0; i < {LUT_SINE_N}; i++) {{
    memcpy(&w, &plaits::lut_sine[i], 4);
    h = fm1_init_tables_fnv(h, w);
  }}
  out[3] = h;
  for (int i = 0; i < 4; i++)
    if (out[i] != kExpected[i]) bad |= 1u << i;
  return bad;
}}
#endif
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if the generated file is stale")
    args = parser.parse_args()
    text = source()
    if args.check:
        if not OUT.exists() or OUT.read_text() != text:
            print(f"{OUT.relative_to(ROOT)} is stale: run tools/init_tables.py", file=sys.stderr)
            return 1
        return 0
    OUT.write_text(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

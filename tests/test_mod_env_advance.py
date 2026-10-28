"""Envelope state advancement against the original division-based algorithm."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_envelope_advance_boundary_states(tmp_path):
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("no C compiler")
    source = tmp_path / "advance.c"
    source.write_text(r'''
#include <assert.h>
#include <string.h>
#include "mp_env.c"

static void reference(fm1_mp_env_t *e, uint32_t n) {
  while (n) {
    uint64_t left, steps;
    uint32_t inc;
    if (frozen(e)) return;
    inc = e->inc[e->seg];
    left = 0x100000000ull - e->phase;
    steps = (left + inc - 1u) / inc;
    if ((uint64_t)n < steps) {
      e->phase += (uint32_t)((uint64_t)inc * n);
      return;
    }
    n -= (uint32_t)steps;
    next_segment(e);
  }
}

static uint32_t seed = 0x815732a9u;
static uint32_t random32(void) {
  seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
  return seed;
}

static void check(fm1_mp_env_t e, uint32_t n) {
  fm1_mp_env_t expected = e;
  reference(&expected, n);
  advance(&e, n);
  assert(memcmp(&e, &expected, sizeof e) == 0);
}

int main(void) {
  unsigned trial, i;
  for (trial = 0; trial < 20000; ++trial) {
    fm1_mp_env_t e;
    uint64_t boundary;
    memset(&e, 0, sizeof e);
    e.num_segments = 4;
    e.seg = random32() % 5; /* includes the finished state */
    e.phase = random32();
    e.gate = random32() & 1;
    e.sustain = (trial % 3 == 0) ? 2 : 0;
    if (trial & 1) { e.loop_start = 1; e.loop_end = 3; }
    for (i = 0; i < 4; ++i) {
      e.inc[i] = random32() | 1u;
      e.level[i + 1] = (float)i * 0.25f;
    }
    check(e, 0); check(e, 1); check(e, 32); check(e, 257);
    if (e.seg >= e.num_segments) continue;
    boundary = (0x100000000ull - e.phase + e.inc[e.seg] - 1u) / e.inc[e.seg];
    if (boundary < 1024) {
      check(e, (uint32_t)boundary - 1);
      check(e, (uint32_t)boundary);
      check(e, (uint32_t)boundary + 1);
    }
    /* A product larger than UINT32_MAX must not wrap the comparison. */
    e.loop_start = e.loop_end = e.sustain = 0;
    check(e, 0xffffffffu);
  }
  /* Exact equality and the minimum increment at both phase extremes. */
  for (i = 0; i < 2; ++i) {
    fm1_mp_env_t e;
    memset(&e, 0, sizeof e);
    e.num_segments = 1; e.inc[0] = 1;
    e.phase = i ? 0xffffffffu : 0;
    check(e, 1); check(e, 0xffffffffu);
    e.inc[0] = 0x80000000u; e.phase = 0;
    check(e, 1); check(e, 2); check(e, 3);
  }
  return 0;
}
''')
    executable = tmp_path / "advance"
    subprocess.run([
        compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
        "-I" + str(ROOT / "engines/include"),
        "-I" + str(ROOT / "engines/mod"), str(source),
        str(ROOT / "engines/mod/mp_tables.c"), "-o", str(executable),
    ], check=True, capture_output=True)
    subprocess.run([str(executable)], check=True, timeout=20)

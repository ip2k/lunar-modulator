"""A diagnostic must bound its work and report valid arithmetic across timer wrap."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_arithmetic_probe_values_bounds_and_timer_wrap(tmp_path):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("C compiler unavailable")
    harness = tmp_path / "probe.c"
    harness.write_text(r'''
#include "arithmetic_probe.h"
#include <assert.h>
#include <string.h>
static unsigned clocks, yields, rows;
static uint32_t tick = UINT32_MAX - 8u;
static uint32_t now(void) { ++clocks; tick += 17u; return tick; }
static void yield(void) { ++yields; }
static void emit(const struct lunar_arithmetic_result *r) {
    float x;
    assert(r->operation == rows++);
    assert(r->iterations == 1024 && r->batches == 8);
    assert(r->min_ticks == 17 && r->max_ticks == 17 && r->ticks == 8 * 17);
    memcpy(&x, &r->result_bits, sizeof x);
    if (r->operation == 0) assert(r->result_bits == 1025);
    if (r->operation == 1) assert(x == 2.0f);
    /* (1+1/n)^n approaches e from below, its reciprocal from above.
     * Bounds are independent of a compiler's exact intermediate rounding. */
    if (r->operation == 2) assert(x > 2.71f && x < 2.72f);
    if (r->operation == 3) assert(x > .367f && x < .369f);
}
int main(void) {
    assert(!lunar_devkit_arithmetic_probe(0, yield, emit));
    assert(!lunar_devkit_arithmetic_probe(now, 0, emit));
    assert(!lunar_devkit_arithmetic_probe(now, yield, 0));
    assert(!clocks && !yields && !rows);
    assert(lunar_devkit_arithmetic_probe(now, yield, emit));
    assert(rows == 4 && yields == 32 && clocks == 64);
}
''')
    binary = tmp_path / "probe"
    subprocess.run([cc, "-std=c99", "-O2", "-ffp-contract=off", "-Wall", "-Wextra",
                    "-Werror", "-I", str(ROOT / "firmware/devkit"), str(harness),
                    str(ROOT / "firmware/devkit/arithmetic_probe.c"), "-o", str(binary)],
                   check=True, capture_output=True)
    subprocess.run([str(binary)], check=True)

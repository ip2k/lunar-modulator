"""Full-state differential proof for offset-free CV window selection."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("sanitized", [False, True])
def test_cv_window_preserves_state(tmp_path, sanitized):
    if sys.platform != "linux":
        pytest.skip("Linux section GC isolates the internal function")
    proof = r'''
#include "CORE_PATH"
#include <stdio.h>
#include <stdlib.h>
static void baseline_feed_cv(fm1_mod_t *m, unsigned id, uint64_t at, float v) {
  unsigned off;
  const unsigned w = window_of(m, at, &off);
  m->pend_cv[w][id] = v;
  m->cv_has[w] |= UINT64_C(1) << id;
}
static uint32_t seed = 0x42783219u;
static uint32_t draw(void) {
  seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5; return seed;
}
static uint64_t draw64(void) { return ((uint64_t)draw() << 32) | draw(); }
int main(void) {
  fm1_mod_t *a = malloc(sizeof *a), *b = malloc(sizeof *b);
  if (!a || !b) return 2;
  for (unsigned trial = 0; trial < 20000; ++trial) {
    unsigned char *bytes = (unsigned char *)a;
    for (size_t j = 0; j < sizeof *a; ++j) bytes[j] = (unsigned char)draw();
    a->next_tick = trial % 3 == 0 ? UINT64_MAX - 64 : trial % 3 == 1 ? 64 : draw64();
    uint64_t at;
    switch (trial % 8) {
      case 0: at = 0; break;
      case 1: at = a->next_tick - 1; break;
      case 2: at = a->next_tick; break;
      case 3: at = a->next_tick + 1; break;
      case 4: at = a->next_tick + FM1_MOD_TICK - 1; break;
      case 5: at = a->next_tick + FM1_MOD_TICK; break;
      case 6: at = UINT64_MAX; break;
      default: at = draw64(); break;
    }
    uint32_t bits = draw(); float v; memcpy(&v, &bits, sizeof v);
    unsigned id = trial % FM1_MOD_SRC_SYSTEM;
    memcpy(b, a, sizeof *a);
    baseline_feed_cv(a, id, at, v); feed_cv(b, id, at, v);
    if (memcmp(a, b, sizeof *a)) {
      fprintf(stderr, "state mismatch trial %u\n", trial); return 1;
    }
  }
  printf("PASS 20000 full-state CV comparisons; %zu bytes/state\n", sizeof *a);
  free(a); free(b); return 0;
}
'''
    proof = proof.replace("CORE_PATH", str(ROOT / "engines/mod/mod_core.c"))
    source = tmp_path / "proof.c"
    source.write_text(proof)
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitized else []
    exe = tmp_path / "proof"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-ffp-contract=off",
                    "-ffunction-sections", "-fdata-sections", *flags,
                    "-I" + str(ROOT / "engines/include"), str(source),
                    "-Wl,--gc-sections", "-o", str(exe)], check=True, capture_output=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=120)
    assert "PASS 20000 full-state CV" in result.stdout

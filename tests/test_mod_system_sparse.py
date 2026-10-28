"""Complete-state differential test for sparse system-CV window intake."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("sanitized", [False, True])
def test_sparse_system_intake_preserves_state(tmp_path, sanitized):
    if sys.platform != "linux":
        pytest.skip("Linux section GC isolates the internal function from unused engine registry calls")
    source = (ROOT / "engines/mod/mod_core.c").read_text()
    start = source.index("static void take_system(fm1_mod_t *m) {")
    end = source.index("\n}\n", start) + 2
    current = source[start:end]
    begin_loop = current.index("  /* Visit pending CVs")
    end_loop = current.index("  m->cv_has[0] = m->cv_has[1];", begin_loop)
    old_loop = r'''  for (id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    if ((m->cv_has[0] >> id) & 1u) {
      const float v = m->pend_cv[0][id];
      if (mod_finite(v)) m->sys_cv[id] = v;
      else ++m->stats.nonfinite;
    }
    if ((m->cv_has[1] >> id) & 1u) m->pend_cv[0][id] = m->pend_cv[1][id];
  }'''
    baseline = (current[:begin_loop] + old_loop + "\n" + current[end_loop:]).replace(
        "take_system(", "baseline_take_system(", 1)
    proof = r'''
#include "CORE_PATH"
#include <stdio.h>
#include <stdlib.h>
BASELINE
typedef char system_sources_fit[FM1_MOD_SRC_SYSTEM == 64 ? 1 : -1];
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
    a->next_tick = (trial % 3 == 0) ? UINT64_MAX - 64 : 64;
    for (unsigned g = 0; g < MOD_SYS_GATES; ++g) {
      a->trig_fall[g] = (draw() & 1) ? MOD_NO_FRAME : a->next_tick - 1;
      for (unsigned w = 0; w < 2; ++w) {
        fm1_mod_gate_t *gate = &a->pend_g[w][g];
        gate->start &= 1; gate->n %= FM1_MOD_EDGES + 1;
        for (unsigned e = 0; e < FM1_MOD_EDGES; ++e) {
          gate->ev[e].frame = e * 7; gate->ev[e].high &= 1;
        }
      }
    }
    if (trial < 128) {
      a->cv_has[0] = trial < 64 ? UINT64_C(1) << trial : 0;
      a->cv_has[1] = trial >= 64 ? UINT64_C(1) << (trial - 64) : 0;
    } else if (trial % 4 == 0) a->cv_has[0] = a->cv_has[1] = 0;
    else if (trial % 4 == 1) a->cv_has[0] = a->cv_has[1] = UINT64_MAX;
    else { a->cv_has[0] = draw64(); a->cv_has[1] = draw64(); }
    memcpy(b, a, sizeof *a);
    baseline_take_system(a);
    take_system(b);
    if (memcmp(a, b, sizeof *a)) {
      fprintf(stderr, "state mismatch trial %u\n", trial); return 1;
    }
  }
  printf("PASS 20000 full-state take_system comparisons; %zu bytes/state\n", sizeof *a);
  free(a); free(b); return 0;
}
'''
    proof = proof.replace("CORE_PATH", str(ROOT / "engines/mod/mod_core.c")).replace("BASELINE", baseline)
    (tmp_path / "proof.c").write_text(proof)
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitized else []
    exe = tmp_path / "proof"
    subprocess.run([os.environ.get("CC", "cc"), "-std=c99", "-O2", "-ffp-contract=off",
                    "-ffunction-sections", "-fdata-sections", *flags,
                    "-I" + str(ROOT / "engines/include"), str(tmp_path / "proof.c"),
                    "-Wl,--gc-sections", "-o", str(exe)], check=True, capture_output=True)
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True, timeout=120)
    assert "PASS 20000 full-state" in result.stdout

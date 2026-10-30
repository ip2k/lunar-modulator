"""Compare sparse Ladder updates with the original full coefficient update."""
import shutil
import subprocess

import pytest

from tests.engine_helpers import ENGINES


def test_pitch_only_control_matches_full_update(tmp_path):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("no C++ compiler")
    source = tmp_path / "control.cc"
    source.write_text(r'''
#include <cassert>
#include <cmath>
#include <cstring>
#include "fx_filter.cc"

// The unspecialized control step is an independent reference for every
// coefficient and lifecycle field, including those deliberately left alone.
static void full_control(FilterInstance *s) {
  bool moved = false;
  for (int i = 0; i < C_COUNT; ++i) {
    if (s->value[i] != s->target[i]) {
      s->value[i] = FiltGlide(s->value[i], s->target[i], s->glide_ctrl);
      moved = true;
    }
  }
  if (!moved) return;
  s->g_done = 0;
  FiltUpdateShared(s);
  FiltUpdateCoefs(s, s->cur);
  if (s->fade) FiltUpdateCoefs(s, s->prev);
}

int main() {
  const float rates[] = {8000, 44118, 48000, 96000, 384000};
  const unsigned sizes[] = {1, 7, 8, 9, 31, 64};
  unsigned fast = 0, fallback = 0;
  for (float rate : rates) for (int type = 0; type < 6; ++type) {
    FilterInstance s;
    fm1_host_t host = {FM1_ENGINE_API_VERSION, rate, 64};
    assert(FilterCreate(&s, &host));
    FilterSet(&s, 0, float(type));
    for (unsigned step = 0; step < 1800; ++step) {
      if (step % 61 == 0) FilterSet(&s, 1, step % 122 ? 20.f : 18000.f);
      if (step == 200) FilterSet(&s, 0, 1.f);
      if (step && step % 307 == 0) FilterSet(&s, 0, float((step / 307) % 6));
      if (step % 307 == 150) FilterSet(&s, 0, 1.f);
      if (step % 173 == 0) {
        FilterSet(&s, 2, .7f); FilterSet(&s, 3, .4f);
        FilterSet(&s, 4, float(step % 7) * .5f);
        FilterSet(&s, 5, .3f);
      }
      if (step % 173 == 85) {
        FilterSet(&s, 2, 0.f); FilterSet(&s, 3, 0.f);
        FilterSet(&s, 4, 0.f); FilterSet(&s, 5, 0.f);
      }
      FilterInstance actual = s, expected = s;
      unsigned moving = 0;
      for (int i = 0; i < C_COUNT; ++i)
        if (s.value[i] != s.target[i]) moving |= 1u << i;
      if (moving == (1u << C_PITCH) && s.primed &&
          s.cur == T_LADDER && s.want == T_LADDER && !s.fade && !s.warm)
        ++fast;
      else ++fallback;
      FiltControl(&actual);
      full_control(&expected);
      assert(memcmp(&actual, &expected, sizeof(actual)) == 0);
      float lr[128];
      for (unsigned i = 0; i < 128; ++i) lr[i] = sinf(float(i + step)) * .2f;
      if (step % 71 == 0) lr[0] = NAN;
      FilterRender(&s, lr, sizes[step % 6]);
      if (step == 600) s.count = 0xfffffff8u;
    }
  }
  assert(fast > 100 && fallback > 100);
}
''')
    binary = tmp_path / "control"
    subprocess.run([compiler, "-std=c++11", "-O2", "-ffp-contract=off",
                    "-I", str(ENGINES / "include"),
                    "-I", str(ENGINES / "src"), str(source), "-o", str(binary)],
                   check=True, capture_output=True, text=True)
    subprocess.run([str(binary)], check=True, capture_output=True, text=True)

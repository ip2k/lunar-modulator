/* SPDX-License-Identifier: MIT. Directed host seam and PCM equivalence test. */
#include "diagnostic_app.h"
#include "fm1_dx7_budget.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static fm1_app_t ref FM1_APP_ALIGN16;
static unsigned char ref_sound[LUNAR_DIAGNOSTIC_ARENA_BYTES] FM1_APP_ALIGN16;
static fm1_app_arena_t ref_arenas[FM1_APP_UNITS];
int main(void) {
  int32_t pcm[128];
  fm1_dx7_budget_stats_t stats;
  int nonzero = 0;
  assert(lunar_diagnostic_init() == 0);
  assert(lunar_diagnostic_init() == -1);
  ref_arenas[0].mem = ref_sound; ref_arenas[0].bytes = sizeof ref_sound;
  assert(!fm1_app_init_arenas(&ref, LUNAR_DIAGNOSTIC_RATE, ref_arenas));
  assert(!fm1_app_select(&ref, 0, fm1_app_find("dx7")));
  assert(fm1_dx7_set_voice_limit(ref.unit[0].self, 8));
  assert(fm1_dx7_get_budget_stats(lunar_diagnostic_state()->unit[0].self, &stats));
  assert(stats.limit == 8);
  for (unsigned block = 0; block < 256; ++block) {
    if (block == 0) {
      for (int note = 60; note < 70; ++note) {
        lunar_diagnostic_note(note, 100, 1); fm1_app_note_on(&ref, note, 100);
      }
    }
    if (block == 60) { lunar_diagnostic_key(5, 1); fm1_app_key(&ref, 5, 1, 100); }
    if (block == 90) { lunar_diagnostic_knob(2, 3); fm1_app_encoder(&ref, 2, 3); }
    if (block == 120) {
      lunar_diagnostic_key(5, 0); fm1_app_key(&ref, 5, 0, 100);
      for (int note = 60; note < 70; ++note) {
        lunar_diagnostic_note(note, 0, 0); fm1_app_note_off(&ref, note);
      }
    }
    assert(!lunar_diagnostic_render(pcm, 64));
    const float *f = fm1_app_render(&ref, 64);
    for (unsigned i = 0; i < 128; ++i) {
      int32_t expected = f[i] >= 1 ? 32767 : f[i] <= -1 ? -32767 : (int32_t)(f[i]*32767.0f);
      assert(pcm[i] == expected); nonzero |= pcm[i] != 0;
    }
  }
  assert(nonzero);
  assert(lunar_diagnostic_render(pcm, 65) == -1);
  assert(lunar_diagnostic_status() == 4);
  memset(pcm, 0x55, sizeof pcm);
  lunar_diagnostic_note(80, 100, 1);
  assert(lunar_diagnostic_render(pcm, 64) == -1);
  for (unsigned i = 0; i < 128; ++i) assert(pcm[i] == 0);
  lunar_diagnostic_fault(99); assert(lunar_diagnostic_status() == 4);
  assert(lunar_diagnostic_init() == -1);
  printf("diagnostic PCM parity: 256 blocks; app=%zu arena=%u engine=%zu cap=8; sticky fault silence passed\n",
    sizeof ref, LUNAR_DIAGNOSTIC_ARENA_BYTES, ref.unit[0].ram);
  return 0;
}

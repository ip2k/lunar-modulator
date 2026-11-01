/* SPDX-License-Identifier: MIT */
#include "diagnostic_app.h"
#include "fm1_dx7_budget.h"
#include <math.h>
#include <string.h>
/* Permanent storage: neither a stack arena nor an old app-private structure.
 * Linker bounds count the app, descriptors and arena independently. */
static fm1_app_t app FM1_APP_ALIGN16;
static unsigned char sound[LUNAR_DIAGNOSTIC_ARENA_BYTES] FM1_APP_ALIGN16;
static fm1_app_arena_t arenas[FM1_APP_UNITS];
static uint32_t ready, fault;

int lunar_diagnostic_init(void) {
  int dx7;
  size_t bytes;
  if (ready || fault) return -1; /* init_arenas only accepts a fresh app */
  dx7 = fm1_app_find("dx7");
  if (dx7 < 0) { lunar_diagnostic_fault(1); return -1; }
  bytes = fm1_engines[dx7]->instance_size(&(fm1_host_t){
    FM1_ENGINE_API_VERSION, LUNAR_DIAGNOSTIC_RATE, FM1_APP_MAX_FRAMES});
  if (!bytes || bytes > sizeof sound) { lunar_diagnostic_fault(2); return -1; }
  arenas[0].mem = sound;
  arenas[0].bytes = sizeof sound;
  if (fm1_app_init_arenas(&app, LUNAR_DIAGNOSTIC_RATE, arenas) ||
      fm1_app_select(&app, 0, dx7) ||
      !fm1_dx7_set_voice_limit(app.unit[0].self, LUNAR_DIAGNOSTIC_VOICES)) {
    lunar_diagnostic_fault(3); return -1;
  }
  ready = 1;
  return 0;
}

void lunar_diagnostic_key(int key, int down) {
  if (ready && !fault) fm1_app_key(&app, key, down, 100);
}
void lunar_diagnostic_note(int note, int velocity, int down) {
  if (!ready || fault) return;
  if (down) fm1_app_note_on(&app, note, velocity);
  else fm1_app_note_off(&app, note);
}
void lunar_diagnostic_knob(int encoder, int delta) {
  /* Only parameter knobs; SELECT/ALGORITHM/PRESETS can change arrangement. */
  if (ready && !fault && encoder >= 2 && encoder <= 5)
    fm1_app_encoder(&app, encoder, delta);
}
int lunar_diagnostic_render(int32_t *pcm, uint32_t frames) {
  const float *out;
  if (!pcm || frames > FM1_APP_MAX_FRAMES) {
    lunar_diagnostic_fault(4); return -1;
  }
  if (!ready || fault) {
    memset(pcm, 0, 2u * frames * sizeof *pcm); return -1;
  }
  out = fm1_app_render(&app, frames);
  for (uint32_t i = 0; i < 2u * frames; ++i) {
    float v = out[i];
    if (!isfinite(v)) {
      lunar_diagnostic_fault(5);
      memset(pcm, 0, 2u * frames * sizeof *pcm); return -1;
    }
    /* Bounded conversion before multiplication; symmetric Q15, then the
     * platform scales to the codec's 24-bit left-justified words. */
    pcm[i] = v >= 1.0f ? 32767 : v <= -1.0f ? -32767 : (int32_t)(v * 32767.0f);
  }
  return 0;
}
void lunar_diagnostic_fault(uint32_t reason) {
  if (!fault) fault = reason ? reason : 1;
  ready = 0; /* sticky and silent; no reset, boot mailbox or flash commands */
}
uint32_t lunar_diagnostic_status(void) { return fault; }
const fm1_app_t *lunar_diagnostic_state(void) { return &app; }

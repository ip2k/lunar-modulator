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
  if (!ready || fault || encoder < FM1_ENC_KNOB1 || encoder > FM1_ENC_KNOB4) return;
  if (app.mode != FM1_MODE_HOME) { lunar_diagnostic_fault(7); return; }
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
#ifdef LUNAR_DIAGNOSTIC_OFFLINE_PROOF
/* Recreated DX7 instances start at the global default of 12 voices. The proof
 * only admits the fixed unit-0 DX7 arrangement and restores its budget before
 * rendering; other arrangements fail closed, never inherit a larger cap. */
static int owner_admit(void) {
  int dx7=fm1_app_find("dx7");
  if (!ready || fault || dx7<0 || app.unit[0].index!=dx7 || !app.unit[0].e ||
      !app.unit[0].self || !fm1_dx7_set_voice_limit(app.unit[0].self,8)) {
    lunar_diagnostic_fault(8); return -1;
  }
  return 0;
}
int lunar_diagnostic_owner_button(int button,int down) {
  if(button<0 || button>13 || (down!=0 && down!=1) || owner_admit()) return -1;
  fm1_app_button(&app,button,down); return owner_admit();
}
int lunar_diagnostic_owner_encoder(int encoder,int delta) {
  if(encoder<0 || encoder>6 || delta< -64 || delta>64 || owner_admit()) return -1;
  fm1_app_encoder(&app,encoder,delta); return owner_admit();
}
int lunar_diagnostic_owner_select(int engine) {
  if(owner_admit()) return -1;
  int result=fm1_app_select(&app,0,engine);
  if(owner_admit()) return -1;
  return result;
}
int lunar_diagnostic_owner_render(int32_t *pcm,uint32_t frames) {
  if(owner_admit()) {
    if(pcm && frames<=FM1_APP_MAX_FRAMES) memset(pcm,0,2u*frames*sizeof *pcm);
    return -1;
  }
  return lunar_diagnostic_render(pcm,frames);
}
const uint16_t *lunar_diagnostic_owner_draw(void *unused, uint32_t min_frames) {
  (void)unused;
  if (!ready || fault || !fm1_app_draw(&app, min_frames)) return NULL;
  return app.tft.px;
}
#endif

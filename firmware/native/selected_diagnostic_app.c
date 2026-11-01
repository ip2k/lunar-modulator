/* SPDX-License-Identifier: MIT
 * Fixed selected-Trio offline diagnostic. No project chooser, save or reset. */
#include "diagnostic_app.h"
#include "selected_project.h"
#include "selected_project_blob.h"
#include <math.h>
#include <string.h>

#define LUNAR_SELECTED_SOUND_BYTES 16384u
#define LUNAR_SELECTED_READER_BYTES 16384u

/* Permanent storage: the bounded reader is never placed on an IRQ stack. */
static fm1_app_t app FM1_APP_ALIGN16;
static unsigned char sound[LUNAR_SELECTED_SOUND_BYTES] FM1_APP_ALIGN16;
static fm1_app_arena_t arenas[FM1_APP_UNITS];
static unsigned char reader_space[LUNAR_SELECTED_READER_BYTES] FM1_APP_ALIGN16;
static fm1_state_report_t report;
static uint32_t ready, fault;

int lunar_diagnostic_init(void) {
  if (ready || fault) return -1;
  if (lunar_selected_project_blob_bytes != 597u ||
      fm1_state_bin_reader_size() > sizeof reader_space) {
    lunar_diagnostic_fault(1); return -1;
  }
  arenas[0].mem = sound;
  arenas[0].bytes = sizeof sound;
  if (fm1_app_init_arenas(&app, LUNAR_DIAGNOSTIC_RATE, arenas) ||
      !lunar_selected_project_load(&app, lunar_selected_project_blob,
          lunar_selected_project_blob_bytes,
          reader_space, sizeof reader_space, &report)) {
    lunar_diagnostic_fault(2); return -1;
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
    pcm[i] = v >= 1.0f ? 32767 : v <= -1.0f ? -32767 : (int32_t)(v * 32767.0f);
  }
  return 0;
}
void lunar_diagnostic_fault(uint32_t reason) {
  if (!fault) fault = reason ? reason : 1;
  ready = 0; /* Sticky silence; no reset or boot mailbox in this profile. */
}
uint32_t lunar_diagnostic_status(void) { return fault; }
const fm1_app_t *lunar_diagnostic_state(void) { return &app; }

#ifdef LUNAR_SELECTED_INTERACTIVE_PROOF
#include "selected_interactive_app.h"
int lunar_selected_interactive_apply(void *unused, const lunar_input_t *e) {
  (void)unused;
  if (!ready || fault || !e) return -1;
  if (e->kind == LUNAR_INPUT_ENCODER && e->id < 7 &&
      e->value && e->value >= -64 && e->value <= 64)
    fm1_app_encoder(&app, e->id, e->value);
  else if ((e->value == 0 || e->value == 1) &&
           e->kind == LUNAR_INPUT_KEY && e->id < 27)
    fm1_app_key(&app, e->id, e->value, 100);
  else if ((e->value == 0 || e->value == 1) &&
           e->kind == LUNAR_INPUT_BUTTON && e->id < 14)
    fm1_app_button(&app, e->id, e->value);
  else return -1;
  return 0;
}
int lunar_selected_interactive_render(void *unused, int32_t *pcm) {
  (void)unused;
  if (lunar_diagnostic_render(pcm, LUNAR_PCM_FRAMES)) return -1;
  for (unsigned i = 0; i < LUNAR_PCM_WORDS; ++i) pcm[i] *= 128;
  return 0;
}
const uint16_t *lunar_selected_interactive_draw(void *unused, uint32_t frames) {
  (void)unused;
  if (!ready || fault || !fm1_app_draw(&app, frames)) return NULL;
  return app.tft.px;
}
#endif

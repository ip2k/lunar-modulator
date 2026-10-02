/* mod_glue.c -- the modulation runtime as the bridge's control-rate hook
 * (fm1_mod_host.h). C99, no heap, no stdio. MIT licence. */
#include "fm1_mod_host.h"

#include <string.h>

static uint32_t glue_begin(void *ctx, uint32_t frames, const fm1_engine_t *engine,
                           uint32_t bpm_x100, int playing) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  if (engine && engine != g->sound) {
    fm1_mod_bind(g->mod, FM1_MOD_SOUND, engine);
    g->sound = engine;
  }
  return fm1_mod_begin(g->mod, frames, bpm_x100, playing);
}

static void glue_event(void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  switch (e->kind) {
    case FM1_SEQ_EV_NOTE_ON:
    case FM1_SEQ_EV_NOTE_OFF: {
      const uint8_t vel = e->kind == FM1_SEQ_EV_NOTE_ON ? (uint8_t)e->b : 0u;
      if (to_engine) fm1_mod_note(g->mod, frame, e->a, vel);
      if (e->track < 8u) fm1_mod_seq_note(g->mod, frame, e->track, e->a, vel);
      break;
    }
    case FM1_SEQ_EV_CLOCK: fm1_mod_seq_clock(g->mod, frame, e->tick); break;
    case FM1_SEQ_EV_START: fm1_mod_seq_run(g->mod, frame, 1); break;
    case FM1_SEQ_EV_STOP: fm1_mod_seq_run(g->mod, frame, 0); break;
    default: break;
  }
}

static float glue_lock(void *ctx, uint16_t index, float value) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  return fm1_mod_set_base(g->mod, FM1_MOD_SOUND, index, value);
}

static uint32_t glue_tick(void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w,
                          uint32_t *next) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  const fm1_mod_write_t *wr = NULL;
  const uint32_t n = fm1_mod_tick(g->mod, frame, &wr);
  uint32_t i, k = 0;
  for (i = 0; i < n; ++i) {
    const fm1_mod_write_t *x = &wr[i];
    if (x->unit == FM1_MOD_SOUND || (x->unit == FM1_MOD_HOST && x->index == FM1_MOD_HOST_PITCH)) {
      if (k < sizeof(g->w) / sizeof(g->w[0])) {
        g->w[k].index = x->index;
        g->w[k].bend = (uint8_t)(x->unit == FM1_MOD_HOST);
        g->w[k].reserved = 0;
        g->w[k].value = x->value;
        ++k;
      }
    } else {
      if (g->write) g->write(g->ctx, frame, x);
      ++g->other_writes;
    }
  }
  g->sound_writes += k;
  if (g->ticked) g->ticked(g->ctx, frame, wr, n);
  *w = g->w;
  *next = frame + FM1_MOD_TICK;
  return k;
}

void fm1_mod_glue_init(fm1_mod_glue_t *g, fm1_mod_t *m, const fm1_engine_t *sound) {
  memset(g, 0, sizeof(*g));
  g->mod = m;
  g->sound = sound;
  g->hook.ctx = g;
  g->hook.begin = glue_begin;
  g->hook.event = glue_event;
  g->hook.lock = glue_lock;
  g->hook.tick = glue_tick;
}

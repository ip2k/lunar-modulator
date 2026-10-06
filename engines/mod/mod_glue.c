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
  (void)playing;   /* Start and Stop reach the runtime as events, at their frames */
  return fm1_mod_begin(g->mod, frames, bpm_x100);
}

static void glue_event(void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  switch (e->kind) {
    case FM1_SEQ_EV_NOTE_ON:
    case FM1_SEQ_EV_NOTE_OFF: {
      const uint8_t vel = e->kind == FM1_SEQ_EV_NOTE_ON ? (uint8_t)e->b : 0u;
      /* to_engine is 1 + the slot: sound unit k's notes are slot k's. */
      if (to_engine > 0) {
        const unsigned snd = (unsigned)to_engine - 1u;
        fm1_mod_sound_note(g->mod, frame, snd < FM1_MOD_SOUNDS ? snd : 0u, e->a, vel);
      }
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

/* A lock on slot `slot` (fm1_seq_host_dispatch_slots_ticks): the slot is
 * the sound unit, slot 0 SOUND. */
static float glue_lock_slot(void *ctx, unsigned slot, uint16_t index, float value) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  if (slot >= FM1_MOD_SOUNDS) return value;
  return fm1_mod_set_base(g->mod, fm1_mod_sound_unit(slot), index, value);
}

/* Per-voice offsets (MG9) as the bridge's writes, after the k there are. */
static uint32_t voice_hook_writes(fm1_mod_glue_t *g, uint32_t n, uint32_t k) {
  uint32_t i;
  for (i = 0; i < n && k < sizeof(g->w) / sizeof(g->w[0]); ++i) {
    const fm1_mod_write_t *x = &g->vw[i];
    const int snd = fm1_mod_unit_sound(x->unit);
    if (snd < 0) continue;
    memset(&g->w[k], 0, sizeof(g->w[k]));
    g->w[k].index = x->index;
    g->w[k].slot = (uint8_t)snd;
    g->w[k].value = x->value;
    g->w[k].note = 1;
    g->w[k].key = x->key;
    ++k;
  }
  g->voice_writes += n;
  return k;
}

static uint32_t glue_tick(void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w,
                          uint32_t *next) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  const fm1_mod_write_t *wr = NULL;
  const uint32_t n = fm1_mod_tick(g->mod, frame, &wr);
  uint32_t i, k = 0, nv;
  for (i = 0; i < n; ++i) {
    const fm1_mod_write_t *x = &wr[i];
    const int snd = fm1_mod_unit_sound(x->unit);   /* a sound unit's: the bridge's slot */
    const int bend = x->unit == FM1_MOD_HOST ? fm1_mod_host_pitch_sound(x->index) : -1;
    if (snd >= 0 || bend >= 0) {
      if (k < sizeof(g->w) / sizeof(g->w[0])) {
        memset(&g->w[k], 0, sizeof(g->w[k]));
        g->w[k].index = x->index;
        g->w[k].bend = (uint8_t)(bend >= 0);
        g->w[k].slot = (uint8_t)(bend >= 0 ? bend : snd);   /* HOST PITCH bends sound unit 1 */
        g->w[k].value = x->value;
        ++k;
      }
    } else {
      if (g->write) g->write(g->ctx, frame, x);
      ++g->other_writes;
    }
  }
  g->sound_writes += k;
  nv = fm1_mod_voice_writes(g->mod, g->vw, sizeof(g->vw) / sizeof(g->vw[0]));
  if (nv && g->voiced) g->voiced(g->ctx, frame, g->vw, nv);
  if (g->ticked) g->ticked(g->ctx, frame, wr, n);
  k = voice_hook_writes(g, nv, k);
  *w = g->w;
  *next = frame + FM1_MOD_TICK;
  return k;
}

/* A note-on just reached slot `slot`'s engine: its voice's first offsets. */
static uint32_t glue_note_on(void *ctx, uint32_t frame, unsigned slot, uint8_t key,
                             const fm1_seq_hook_write_t **w) {
  fm1_mod_glue_t *g = (fm1_mod_glue_t *)ctx;
  uint32_t n;
  *w = g->w;
  if (slot >= FM1_MOD_SOUNDS) return 0;
  n = fm1_mod_voice_start(g->mod, slot, key, g->vw, sizeof(g->vw) / sizeof(g->vw[0]));
  if (n && g->voiced) g->voiced(g->ctx, frame, g->vw, n);
  return voice_hook_writes(g, n, 0);
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
  g->hook.lock_slot = glue_lock_slot;
  g->hook.note_on = glue_note_on;
}

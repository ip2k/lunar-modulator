/* fm1_app.c -- the virtual FM-1 application (fm1_app.h). C99, no heap.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_app.h"

#include <math.h>
#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "fm1_look.h"
#include "fm1_seq_view.h"

/* Compile-time checks of the sequencer's fixed sizes (docs/15 §2.6; C99 has
 * no static_assert): the event buffer is 3,072 B and the pending record one
 * 240-byte command, on 32- and 64-bit builds alike. The instance's own size
 * comes from fm1_seq_size at run time; fm1_app_seq_reset refuses limits
 * whose instance does not fit FM1_APP_SEQ_BYTES, and tests/test_sim_web.py
 * checks the budget sum. */
typedef char fm1_app_seq_events_are_3k[sizeof(fm1_seq_ev_t) * FM1_APP_SEQ_EVENTS == 3072u ? 1 : -1];
typedef char fm1_app_seq_cmd_is_240[sizeof(fm1_seq_cmd_t) == 240u ? 1 : -1];
typedef char fm1_app_seq_ui_fits[sizeof(fm1_seq_ui_t) <= FM1_APP_SEQ_UI_BYTES ? 1 : -1];

/* ---- small helpers ---------------------------------------------------------- */

static int eq_nocase(const char *a, const char *b) {
  for (;; ++a, ++b) {
    int x = (unsigned char)*a, y = (unsigned char)*b;
    if (x >= 'A' && x <= 'Z') x += 'a' - 'A';
    if (y >= 'A' && y <= 'Z') y += 'a' - 'A';
    if (x != y) return 0;
    if (!x) return 1;
  }
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

static double seconds(const fm1_app_t *a) { return (double)a->frames / a->host.sample_rate; }

static const fm1_engine_t *entry(int index) {
  if (index < 0 || (size_t)index >= fm1_engine_count) return NULL;
  return fm1_engines[index];
}

/* ---- units: sounds, inserts and the master bus ----------------------------------- */

int fm1_app_sound_unit(int sound) {
  if (sound == 0) return 0;
  return sound > 0 && sound < FM1_APP_SOUNDS ? 1 + FM1_APP_FX_SLOTS + sound - 1 : -1;
}

int fm1_app_insert_unit(int sound, int slot) {
  if (sound < 0 || sound >= FM1_APP_SOUNDS || slot < 0 || slot >= FM1_APP_INSERTS) return -1;
  return 1 + FM1_APP_FX_SLOTS + (FM1_APP_SOUNDS - 1) + FM1_APP_INSERTS * sound + slot;
}

/* The sound unit a unit id holds, or -1 for an effect. */
static int unit_sound(int unit) {
  if (unit == 0) return 0;
  if (unit > FM1_APP_FX_SLOTS && unit <= FM1_APP_FX_SLOTS + FM1_APP_SOUNDS - 1) {
    return unit - FM1_APP_FX_SLOTS;
  }
  return -1;
}

/* Units only the lab switch offers: sound units 1..3 and the inserts. */
static int unit_is_lab(int unit) { return unit > FM1_APP_FX_SLOTS; }

/* Sound unit `sound`'s unit (callers keep it in range; unit 0 otherwise). */
static fm1_app_unit_t *sound_of(fm1_app_t *a, int sound) {
  const int u = fm1_app_sound_unit(sound);
  return &a->unit[u < 0 ? 0 : u];
}

static const fm1_app_unit_t *sound_of_c(const fm1_app_t *a, int sound) {
  const int u = fm1_app_sound_unit(sound);
  return &a->unit[u < 0 ? 0 : u];
}

/* The current sound's unit: what the keys play and HOME shows. */
static fm1_app_unit_t *cur(fm1_app_t *a) { return sound_of(a, a->sound); }

/* Several sounds in use: the title names the current one ("S2 Shapes"). */
static int multi_in_use(const fm1_app_t *a) {
  if (!a->lab) return 0;
  if (a->sound != 0) return 1;
  for (int k = 1; k < FM1_APP_SOUNDS; ++k) {
    if (sound_of_c(a, k)->e) return 1;
  }
  return 0;
}

/* FX mode's slots with the lab switch on: the current sound's inserts, its
 * Mix page (every sound's level), and the master bus. */
enum { FX_IN1 = 0, FX_IN2, FX_MIX, FX_M1, FX_M2, FX_LAB_SLOTS };
static const char *const kFxTags[FX_LAB_SLOTS] = { "In1", "In2", "Mix", "M1", "M2" };

/* The unit FX mode's slot shows, or -1 for the Mix page. */
static int fx_unit_at(const fm1_app_t *a, int slot) {
  if (!a->lab) return 1 + slot;
  if (slot == FX_MIX) return -1;
  if (slot < FX_MIX) return fm1_app_insert_unit(a->sound, slot);
  return 1 + slot - FX_M1;
}

static int fx_slots(const fm1_app_t *a) { return a->lab ? FX_LAB_SLOTS : FM1_APP_FX_SLOTS; }

int fm1_app_find(const char *id) {
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (strcmp(fm1_engines[i]->id, id) == 0) return (int)i;
  }
  return -1;
}

static int page_count(const fm1_engine_t *e) {
  int pages = 1;
  for (uint16_t i = 0; e && i < e->n_params; ++i) {
    if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
  }
  return pages;
}

/* Pages of FX mode's slot: its effect's, or one for the Mix page or an
 * empty slot. */
static int fx_pages(const fm1_app_t *a, int slot) {
  const int u = fx_unit_at(a, slot);
  return u < 0 ? 1 : page_count(a->unit[u].e);
}

/* The first four parameters on `page`, in index order. */
static int page_params(const fm1_engine_t *e, int page, int out[4]) {
  int n = 0;
  for (uint16_t i = 0; e && i < e->n_params && n < 4; ++i) {
    if (e->params[i].page == page) out[n++] = i;
  }
  return n;
}

/* The engine's first list parameter: what ALGORITHM turns. */
static int model_param(const fm1_engine_t *e) {
  for (uint16_t i = 0; e && i < e->n_params; ++i) {
    if (e->params[i].type == FM1_PARAM_ENUM) return i;
  }
  return -1;
}

static int enum_index(const fm1_param_t *p, float v) {
  int n = (int)(p->max - p->min) + 1;
  int i = (int)floorf(v - p->min + 0.5f);
  return clampi(i, 0, n - 1);
}

void fm1_look_value(const fm1_param_t *p, float v, char *buf, size_t size) {
  if (p->type == FM1_PARAM_ENUM) {
    const char *name = p->enum_names ? p->enum_names[enum_index(p, v)] : NULL;
    if (name) snprintf(buf, size, "%s", name);
    else snprintf(buf, size, "%d", (int)floorf(v + 0.5f));
    return;
  }
  float range = p->max - p->min;
  int decimals = range <= 2.0f ? 2 : (range <= 20.0f ? 1 : 0);
  float tiny = decimals == 2 ? 0.005f : (decimals == 1 ? 0.05f : 0.5f);
  if (fabsf(v) < tiny) v = 0.0f;   /* no "-0.00" */
  snprintf(buf, size, "%.*f", decimals, (double)v);
}

/* Detent size for a float parameter: a hundredth of its range, or whole
 * units for wide integer ranges such as 0..100. */
static float step_of(const fm1_param_t *p) {
  if (p->type == FM1_PARAM_ENUM) return 1.0f;
  float range = p->max - p->min;
  if (range >= 10.0f && p->min == floorf(p->min) && p->max == floorf(p->max)) {
    float s = floorf(range / 100.0f + 0.5f);
    return s < 1.0f ? 1.0f : s;
  }
  return range / 100.0f;
}

static void popup(fm1_app_t *a, const char *l0, const char *l1, const char *l2, int mark) {
  const char *lines[3] = { l0, l1, l2 };
  a->popup_lines = 0;
  for (int i = 0; i < 3; ++i) {
    if (!lines[i]) break;
    snprintf(a->popup[i], sizeof a->popup[i], "%s", lines[i]);
    a->popup_lines = i + 1;
  }
  a->popup_mark = mark;
  a->popup_until = a->frames + (uint64_t)a->host.sample_rate;   /* about a second */
  a->dirty = 1;
}

/* Why fm1_app_select refused registry entry `index`, as a popup. */
static void refusal_popup(fm1_app_t *a, int index, int code) {
  char why[24], over[24];
  if (code == FM1_APP_SELECT_RAM) {       /* the meter: by how much, in KB rounded up */
    snprintf(over, sizeof over, "%uK over budget", (unsigned)((a->ram_over + 1023u) / 1024u));
    popup(a, entry(index) ? entry(index)->name : "?", "does not fit", over, -1);
    return;
  }
  if (code == -2) snprintf(why, sizeof why, "does not fit");
  else if (code == -3) snprintf(why, sizeof why, "refuses %.0f Hz", (double)a->host.sample_rate);
  else snprintf(why, sizeof why, "cannot load");
  popup(a, entry(index) ? entry(index)->name : "?", why, NULL, -1);
}

/* ---- the sequencer's panel UI (fm1_seq_ui.h) ------------------------------------- */

/* The UI's commands go in through fm1_app_seq_cmd, under the event-room rule. */
static int ui_cmd(void *ctx, const fm1_seq_cmd_t *c) { return fm1_app_seq_cmd((fm1_app_t *)ctx, c); }

static fm1_seq_ui_emit_t ui_out(fm1_app_t *a) {
  fm1_seq_ui_emit_t out;
  out.ctx = a;
  out.cmd = ui_cmd;
  return out;
}

/* After an edge the UI took: the screen and LEDs follow, and its toast, if
 * any, becomes a popup. */
static void ui_after(fm1_app_t *a) {
  switch (a->ui.toast) {
    case FM1_SEQ_TOAST_FULL_VEL_ON: popup(a, "Full velocity", "on", NULL, -1); break;
    case FM1_SEQ_TOAST_FULL_VEL_OFF: popup(a, "Full velocity", "off", NULL, -1); break;
    default: break;
  }
  a->ui.toast = FM1_SEQ_TOAST_NONE;
  a->dirty = 1;
  a->leds_changed = 1;
}

static void forget_knob_hint(fm1_app_t *a) {
  a->ui.knob = -1;
  if (a->ui.hint == FM1_SEQ_HINT_KNOB) a->ui.hint = FM1_SEQ_HINT_NONE;
}

/* The note key 0 plays now: SHIFT's pitches on a held step use it. */
static int base_note(const fm1_app_t *a) {
  return FM1_APP_FIRST_NOTE + 12 * a->octave + a->transpose;
}

/* HOME, FX and GLO leave SEQ mode; its holds go without a toggle. */
static void set_mode(fm1_app_t *a, int mode) {
  if (a->mode == FM1_MODE_SEQ && mode != FM1_MODE_SEQ) fm1_seq_ui_leave(&a->ui);
  a->mode = mode;
}

/* ---- set-up and units --------------------------------------------------------- */

void fm1_app_init(fm1_app_t *a, float sample_rate) {
  memset(a, 0, offsetof(fm1_app_t, tft));
  a->host.api_version = FM1_ENGINE_API_VERSION;
  a->host.sample_rate = sample_rate;
  a->host.max_frames = FM1_APP_MAX_FRAMES;
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    a->unit[u].index = -1;
    a->unit[u].cap = FM1_APP_FX_BYTES;
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {         /* each sound unit its own arena */
    a->unit[fm1_app_sound_unit(k)].mem = a->sound_mem[k];
    a->unit[fm1_app_sound_unit(k)].cap = FM1_APP_SOUND_BYTES;
    a->level[k] = FM1_APP_LEVEL_MAX;
    a->sink_ctx[k].a = a;
    a->sink_ctx[k].sound = k;
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      a->unit[fm1_app_insert_unit(k, j)].mem = a->fx_mem[FM1_APP_FX_SLOTS + FM1_APP_INSERTS * k + j];
    }
  }
  for (int k = 0; k < FM1_APP_FX_SLOTS; ++k) a->unit[1 + k].mem = a->fx_mem[k];
  fm1_mix_limiter_init(&a->limiter, sample_rate);
  a->master = 1.0f;
  a->gain = 1.0f;
  a->popup_mark = -1;
  a->mode = FM1_MODE_HOME;
  a->dirty = 1;
  a->leds_changed = 1;
  a->tft.record = 0;
  fm1_seq_ui_init(&a->ui, sample_rate);
  fm1_app_seq_reset(a, FM1_APP_SEQ_TRACKS);
}

static void release(fm1_app_unit_t *u) {
  if (u->e && u->self) u->e->destroy(u->self);
  u->e = NULL;
  u->self = NULL;
  u->index = -1;
  u->bytes = 0;
}

/* Create registry entry `index` (already checked, `bytes` its instance
 * size) in an empty unit, with its defaults. 0 if the engine refused this
 * host. */
static int load(fm1_app_t *a, fm1_app_unit_t *u, int index, size_t bytes) {
  const fm1_engine_t *e = fm1_engines[index];
  memset(u->mem, 0, bytes);
  u->self = e->create(u->mem, &a->host);
  if (!u->self) return 0;
  u->e = e;
  u->index = index;
  u->bytes = bytes;
  for (uint16_t i = 0; i < e->n_params; ++i) u->value[i] = e->params[i].def;
  return 1;
}

/* A sound unit's notes go (a change of its engine, the lab switch off):
 * the keys' and MIDI IN's, then the sequencer's, as fm1_app_all_notes_off
 * releases sound 0's. */
static void release_sound(fm1_app_t *a, int sound);

/* The FX mode slot's unit just changed: its page is clamped (an empty slot
 * has one). */
static void fx_unit_changed(fm1_app_t *a, int unit) {
  if (fx_unit_at(a, a->fx_slot) == unit) a->fx_page = clampi(a->fx_page, 0, fx_pages(a, a->fx_slot) - 1);
}

int fm1_app_select(fm1_app_t *a, int unit, int index) {
  if (unit < 0 || unit >= FM1_APP_UNITS) return FM1_APP_SELECT_BAD;
  if (unit_is_lab(unit) && !a->lab) return FM1_APP_SELECT_BAD;
  fm1_app_unit_t *u = &a->unit[unit];
  const fm1_engine_t *e = entry(index);
  const int snd = unit_sound(unit);
  fm1_kind_t want = snd >= 0 ? FM1_KIND_SOUND : FM1_KIND_AUDIO_FX;
  if (index == -1 && unit > 0) {
    if (snd >= 0) release_sound(a, snd);
    release(u);
    if (snd < 0 && fx_unit_at(a, a->fx_slot) == unit) a->fx_page = 0;   /* an empty slot has one page */
    if (snd == a->sound) {
      a->page = 0;
      forget_knob_hint(a);
    }
    a->dirty = 1;
    return 0;
  }
  if (!e || e->magic != FM1_ENGINE_MAGIC || e->api_version != FM1_ENGINE_API_VERSION ||
      e->kind != want || e->n_params > FM1_APP_MAX_PARAMS) {
    return FM1_APP_SELECT_BAD;
  }
  size_t bytes = e->instance_size(&a->host);
  if (bytes > u->cap) return FM1_APP_SELECT_ARENA;
  if (a->lab) {
    /* The RAM meter: refuse what would take the chain past the FM-1's
     * budget, unless it does not grow (a chain already past it, from
     * before the switch, can still shrink). */
    const size_t now = fm1_app_ram(a), with = fm1_app_ram_with(a, unit, index);
    if (with > FM1_APP_RAM_BUDGET && with > now) {
      a->ram_over = with - FM1_APP_RAM_BUDGET;
      return FM1_APP_SELECT_RAM;
    }
  }
  int prev = u->index;
  size_t prev_bytes = u->bytes;
  float prev_value[FM1_APP_MAX_PARAMS];
  memcpy(prev_value, u->value, sizeof prev_value);
  if (snd >= 0) {
    /* The public page releases every note, as it always has; with several
     * sounds only this one's go. */
    if (a->lab) release_sound(a, snd);
    else fm1_app_all_notes_off(a);
  }
  release(u);
  if (!load(a, u, index, bytes)) {
    /* The engine refused this host (the Plaits-based ones refuse rates
     * above 47,872 Hz): put the previous engine back with its values,
     * rather than leave the unit silent. */
    if (prev >= 0 && load(a, u, prev, prev_bytes)) {
      for (uint16_t i = 0; i < u->e->n_params; ++i) {
        u->value[i] = prev_value[i];
        u->e->set_param(u->self, i, prev_value[i]);
      }
    }
    a->dirty = 1;
    return -3;
  }
  if (snd == a->sound) {
    a->page = clampi(a->page, 0, page_count(e) - 1);
    forget_knob_hint(a);                 /* the Track view's hint named the last sound's knob */
  } else if (snd < 0) {
    fx_unit_changed(a, unit);
  }
  a->dirty = 1;
  return 0;
}

int fm1_app_default_chain(fm1_app_t *a) {
  int macro = fm1_app_find("macro");
  int r = fm1_app_select(a, 0, macro);
  if (r != 0) {
    /* Not at this rate: the first sound that loads, and say why. */
    for (size_t i = 0; i < fm1_engine_count && !a->unit[0].e; ++i) {
      if (fm1_engines[i]->kind == FM1_KIND_SOUND) fm1_app_select(a, 0, (int)i);
    }
    refusal_popup(a, macro, r);
  }
  int f = fm1_app_select(a, 1, fm1_app_find("plate"));
  fm1_app_seq_default_route(a);
  if (a->lab) fm1_app_seq_demo(a);
  return r != 0 ? r : f;
}

void fm1_app_set_lab(fm1_app_t *a, int on) {
  const int was = a->lab;
  a->lab = on != 0;
  if (a->lab && !was) {
    /* FX mode's master slot keeps its place among the lab's five. */
    a->fx_slot = FX_M1 + clampi(a->fx_slot, 0, FM1_APP_FX_SLOTS - 1);
    a->fx_grab = 0;
  }
  if (!a->lab && was) {
    /* Multi-sound goes: every sound unit but the first and every insert,
     * their notes first; sound 0 is the sound again, at full level. */
    for (int k = 1; k < FM1_APP_SOUNDS; ++k) {
      if (sound_of(a, k)->e) release_sound(a, k);
      release(sound_of(a, k));
    }
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      for (int j = 0; j < FM1_APP_INSERTS; ++j) release(&a->unit[fm1_app_insert_unit(k, j)]);
    }
    a->sound = 0;
    a->page = clampi(a->page, 0, page_count(a->unit[0].e) - 1);
    a->fx_slot = a->fx_slot >= FX_M1 ? a->fx_slot - FX_M1 : 0;
    a->fx_page = clampi(a->fx_page, 0, page_count(a->unit[1 + a->fx_slot].e) - 1);
    a->fx_grab = 0;
  }
  if (!a->lab) {
    /* Nothing of the sequencer stays on the panel: no hold, no SHIFT, no
     * full velocity. */
    if (a->mode == FM1_MODE_SEQ) a->mode = FM1_MODE_HOME;
    fm1_seq_ui_leave(&a->ui);
    a->ui.shift = 0;
    a->ui.full_vel = 0;
  }
  a->dirty = 1;
  a->leds_changed = 1;
}

/* The demo pattern (O4): one bar in C minor at the default 120 BPM, a
 * bass note on each half bar and an answering figure above it, three notes
 * held for two steps; no locks (those come with S8). Track 0 plays the
 * sound by the default route. */
const char fm1_app_demo_pattern[] =
    "tog 0 0 48 110;tog 0 2 60 80;tog 0 3 55 90;tog 0 4 63 95;tog 0 6 62 80;"
    "tog 0 7 60 70;tog 0 8 46 110;tog 0 10 58 80;tog 0 11 53 90;tog 0 12 62 95;"
    "tog 0 13 60 80;tog 0 14 55 85;tog 0 15 58 75;"
    "slen 0 0 0 -1 48;slen 0 4 4 -1 48;slen 0 8 8 -1 48";

int fm1_app_seq_demo(fm1_app_t *a) {
  const size_t len = sizeof fm1_app_demo_pattern - 1u;
  return a->seq && fm1_app_seq_line(a, fm1_app_demo_pattern, len) == len;
}

int fm1_app_param_index(const fm1_app_t *a, int unit, const char *name) {
  if (unit < 0 || unit >= FM1_APP_UNITS || !a->unit[unit].e) return -1;
  const fm1_engine_t *e = a->unit[unit].e;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (eq_nocase(e->params[i].name, name)) return i;
  }
  return -1;
}

void fm1_app_set_param(fm1_app_t *a, int unit, int index, float value) {
  if (unit < 0 || unit >= FM1_APP_UNITS) return;
  fm1_app_unit_t *u = &a->unit[unit];
  if (!u->e || index < 0 || index >= u->e->n_params) return;
  u->value[index] = fm1_param_clamp(&u->e->params[index], value);
  u->e->set_param(u->self, (uint16_t)index, value);   /* the engine clamps too */
  a->dirty = 1;
}

float fm1_app_get_param(const fm1_app_t *a, int unit, int index) {
  if (unit < 0 || unit >= FM1_APP_UNITS) return 0.0f;
  const fm1_app_unit_t *u = &a->unit[unit];
  if (!u->e || index < 0 || index >= u->e->n_params) return 0.0f;
  return u->value[index];
}

/* The RAM figure with unit `unit` holding `bytes` (`loaded` or empty), or
 * the chain as it is for unit -1. */
static size_t ram_of(const fm1_app_t *a, int unit, size_t bytes, int loaded) {
  size_t total = 0;
  int sounds = 0;
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const int on = u == unit ? loaded : a->unit[u].e != NULL;
    total += u == unit ? (loaded ? bytes : 0u) : a->unit[u].bytes;
    if (on && unit_sound(u) >= 0) ++sounds;
  }
  if (a->seq) {
    total += fm1_seq_size(&a->seq_lim) + sizeof a->seq_ev;
    if (a->lab) total += sizeof a->seq_pend + FM1_APP_SEQ_UI_BYTES;
  }
  if (a->lab && sounds > 1) total += (size_t)(sounds - 1) * FM1_APP_MIX_BLOCK_BYTES;
  return total;
}

size_t fm1_app_ram(const fm1_app_t *a) { return ram_of(a, -1, 0, 0); }

size_t fm1_app_ram_with(const fm1_app_t *a, int unit, int index) {
  const fm1_engine_t *e = entry(index);
  if (unit < 0 || unit >= FM1_APP_UNITS) return fm1_app_ram(a);
  return ram_of(a, unit, e ? e->instance_size(&a->host) : 0u, e != NULL);
}

/* ---- sound units (multi-sound) ---------------------------------------------------- */

int fm1_app_unit_count(const fm1_app_t *a) { return a->lab ? FM1_APP_SOUNDS : 1; }

const fm1_engine_t *fm1_app_unit_engine(const fm1_app_t *a, int sound) {
  return sound >= 0 && sound < FM1_APP_SOUNDS ? sound_of_c(a, sound)->e : NULL;
}

int fm1_app_unit_current(const fm1_app_t *a) { return a->sound; }

int fm1_app_unit_set_current(fm1_app_t *a, int sound) {
  if (sound < 0 || sound >= fm1_app_unit_count(a)) return -1;
  if (sound != a->sound) {
    a->sound = sound;
    a->page = clampi(a->page, 0, page_count(cur(a)->e) - 1);
    forget_knob_hint(a);                 /* the hint named the last sound's knob */
    if (a->lab && a->fx_slot < FX_MIX) a->fx_page = clampi(a->fx_page, 0, fx_pages(a, a->fx_slot) - 1);
    a->fx_grab = 0;
    a->dirty = 1;
  }
  return 0;
}

int fm1_app_unit_select(fm1_app_t *a, int sound, int index) {
  const int u = fm1_app_sound_unit(sound);
  return u < 0 ? FM1_APP_SELECT_BAD : fm1_app_select(a, u, index);
}

int fm1_app_unit_insert(fm1_app_t *a, int sound, int slot, int index) {
  const int u = fm1_app_insert_unit(sound, slot);
  return u < 0 ? FM1_APP_SELECT_BAD : fm1_app_select(a, u, index);
}

float fm1_app_unit_level(const fm1_app_t *a, int sound) {
  return sound >= 0 && sound < FM1_APP_SOUNDS ? a->level[sound] : 0.0f;
}

void fm1_app_unit_set_level(fm1_app_t *a, int sound, float percent) {
  if (sound < 0 || sound >= FM1_APP_SOUNDS || !(percent == percent)) return;
  a->level[sound] = percent < 0.0f ? 0.0f : (percent > FM1_APP_LEVEL_MAX ? FM1_APP_LEVEL_MAX : percent);
  a->dirty = 1;
}

int fm1_app_unit_route(fm1_app_t *a, int track, int sound) {
  if (!a->lab || sound < 0 || sound >= FM1_APP_SOUNDS) return 0;
  return fm1_app_seq_route(a, track, FM1_SEQ_ROUTE_ENGINE, sound);
}

int fm1_app_unit_of_track(const fm1_app_t *a, int track) {
  fm1_seq_track_info_t ti;
  if (!a->seq || track < 0 || track > 255 || !fm1_seq_get_track(a->seq, (uint8_t)track, &ti) ||
      ti.route_kind != FM1_SEQ_ROUTE_ENGINE) {
    return -1;
  }
  if (!a->lab) return 0;                 /* one sound: every engine route plays it */
  return ti.route_index < FM1_APP_SOUNDS ? ti.route_index : -1;
}

/* ---- notes -------------------------------------------------------------------- */

/* A note on sound unit `sound`, counted there so it can be released. */
static void play_on(fm1_app_t *a, int sound, int note, int velocity) {
  fm1_app_unit_t *s = sound_of(a, sound);
  if (s->e && s->e->note_on) s->e->note_on(s->self, (uint8_t)note, (uint8_t)velocity);
  if (a->note_count[sound][note] < 255) ++a->note_count[sound][note];
}

static void play_off(fm1_app_t *a, int sound, int note) {
  fm1_app_unit_t *s = sound_of(a, sound);
  if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)note);
  if (a->note_count[sound][note]) --a->note_count[sound][note];
}

void fm1_app_unit_note_on(fm1_app_t *a, int sound, int note, int velocity) {
  if (sound < 0 || sound >= fm1_app_unit_count(a) || note < 0 || note > 127) return;
  play_on(a, sound, note, clampi(velocity, 1, 127));
}

void fm1_app_unit_note_off(fm1_app_t *a, int sound, int note) {
  if (sound < 0 || sound >= fm1_app_unit_count(a) || note < 0 || note > 127) return;
  play_off(a, sound, note);
}

void fm1_app_note_on(fm1_app_t *a, int note, int velocity) {
  if (note < 0 || note > 127) return;
  velocity = clampi(velocity, 1, 127);
  play_on(a, a->sound, note, velocity);
  if (a->lab && a->seq) {           /* the chord a step tap writes, or a held step's pitch */
    const fm1_seq_ui_emit_t out = ui_out(a);
    fm1_seq_ui_note(&a->ui, note, velocity, a->mode, &out);
    ui_after(a);
  }
}

void fm1_app_note_off(fm1_app_t *a, int note) {
  if (note < 0 || note > 127) return;
  int sound = a->sound;
  /* The current sound's note of that pitch, else the first sound holding
   * one: a note started before the current sound changed. */
  for (int k = 0; k < FM1_APP_SOUNDS && !a->note_count[sound][note]; ++k) {
    if (a->note_count[k][note]) sound = k;
  }
  play_off(a, sound, note);
  if (a->lab && a->seq) fm1_seq_ui_note(&a->ui, note, 0, a->mode, NULL);
}

void fm1_app_pitch_bend(fm1_app_t *a, float semitones) {
  if (!(semitones == semitones)) return;
  if (semitones > 48.0f) semitones = 48.0f;
  if (semitones < -48.0f) semitones = -48.0f;
  fm1_app_unit_t *s = cur(a);
  if (s->e && s->e->pitch_bend) s->e->pitch_bend(s->self, semitones);
}

/* The sequencer's notes on a sound unit, released (a reset, an import, a
 * change of sound). The core still holds their gates; their note-offs, when
 * they come, find nothing to release. */
static void seq_release_sound(fm1_app_t *a, int sound) {
  fm1_app_unit_t *s = sound_of(a, sound);
  for (int n = 0; n < 128; ++n) {
    while (a->seq_note_count[sound][n]) {
      if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)n);
      --a->seq_note_count[sound][n];
    }
  }
}

static void seq_release(fm1_app_t *a) {
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) seq_release_sound(a, k);
}

/* The keys' and MIDI IN's notes on a sound unit. */
static void notes_release_sound(fm1_app_t *a, int sound) {
  fm1_app_unit_t *s = sound_of(a, sound);
  for (int n = 0; n < 128; ++n) {
    while (a->note_count[sound][n]) {
      if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)n);
      --a->note_count[sound][n];
    }
  }
}

static void release_sound(fm1_app_t *a, int sound) {
  notes_release_sound(a, sound);
  seq_release_sound(a, sound);
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    if (a->key_sound[k] == sound) a->key_down[k] = 0;
  }
  if (sound == a->sound) fm1_seq_ui_notes_off(&a->ui);
}

void fm1_app_all_notes_off(fm1_app_t *a) {
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) notes_release_sound(a, k);
  seq_release(a);
  for (int k = 0; k < FM1_APP_KEYS; ++k) a->key_down[k] = 0;
  fm1_seq_ui_notes_off(&a->ui);
}

/* ---- the panel ---------------------------------------------------------------- */

static const char *const kButtonNames[FM1_APP_BUTTONS] = {
  "OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO",
  "HOME", "SAVE", "ARP", "SEQ", "PLAY/STOP", "REC",
};

void fm1_app_key(fm1_app_t *a, int key, int down, int velocity) {
  if (key < 0 || key >= FM1_APP_KEYS) return;
  if (down) {
    if (a->key_down[key]) return;
    if (a->lab && a->seq) {
      /* In SEQ mode the white keys are steps and the black keys roles
       * (owner decision O1): the UI takes them, and they play nothing. */
      const fm1_seq_ui_emit_t out = ui_out(a);
      if (fm1_seq_ui_key(&a->ui, a->seq, key, 1, velocity, a->frames, a->mode, base_note(a),
                         &out)) {
        ui_after(a);
        return;
      }
      if (a->ui.full_vel) velocity = 127;    /* SHIFT + 10: full velocity */
    }
    int note = base_note(a) + key;
    if (note < 0 || note > 127) return;
    a->key_down[key] = 1;
    a->key_note[key] = (uint8_t)note;
    a->key_vel[key] = (uint8_t)clampi(velocity, 1, 127);
    a->key_sound[key] = (uint8_t)a->sound;          /* its release goes there too */
    fm1_app_note_on(a, note, velocity);
  } else if (a->key_down[key]) {
    a->key_down[key] = 0;
    play_off(a, a->key_sound[key], a->key_note[key]);
    if (a->lab && a->seq) fm1_seq_ui_note(&a->ui, a->key_note[key], 0, a->mode, NULL);
  } else if (fm1_seq_ui_has_key(&a->ui, key)) {   /* a step's release, in any mode */
    const fm1_seq_ui_emit_t out = ui_out(a);
    fm1_seq_ui_key(&a->ui, a->seq, key, 0, 0, a->frames, a->mode, base_note(a), &out);
    ui_after(a);
  }
}

static void show_signed(fm1_app_t *a, const char *what, int v) {
  char buf[24];
  snprintf(buf, sizeof buf, "%s %+d", what, v);
  if (v == 0) snprintf(buf, sizeof buf, "%s 0", what);
  popup(a, buf, NULL, NULL, -1);
}

static void stub_popup(fm1_app_t *a, int button) {
  popup(a, kButtonNames[button], "not in the", "simulator yet", -1);
}

void fm1_app_button(fm1_app_t *a, int button, int down) {
  if (button < 0 || button >= FM1_APP_BUTTONS) return;
  int was = a->button_down[button];
  a->button_down[button] = (uint8_t)(down != 0);
  if (a->lab && a->seq && (down != 0) != (was != 0)) {
    /* Every edge goes to the sequencer's UI first; what it sends goes in
     * as typed commands, under the event-room rule (a second command while
     * one is held is refused and counted in seq_busy). An edge it takes
     * (SEL as SHIFT, OCT on held steps) goes no further. An OCT press it
     * took transposed the held steps, so the app does not count it as
     * held either: ALGORITHM keeps turning the model rather than the
     * keys' transpose, and the other OCT moves the octave rather than
     * resetting it. SEL stays held, as SHIFT needs its release. */
    const fm1_seq_ui_emit_t out = ui_out(a);
    const int took = fm1_seq_ui_button(&a->ui, a->seq, button, down != 0, a->frames, a->mode,
                                       &out);
    ui_after(a);
    if (took) {
      if (down && button != FM1_BTN_SEL) a->button_down[button] = 0;
      return;
    }
  }
  if (!down || was) return;
  switch (button) {
    case FM1_BTN_OCT_DOWN:
    case FM1_BTN_OCT_UP: {
      int other = button == FM1_BTN_OCT_DOWN ? FM1_BTN_OCT_UP : FM1_BTN_OCT_DOWN;
      if (a->button_down[other]) {          /* both: reset octave and transpose */
        a->octave = 0;
        a->transpose = 0;
        popup(a, "Octave 0", "Transpose 0", NULL, -1);
      } else {
        a->octave = clampi(a->octave + (button == FM1_BTN_OCT_UP ? 1 : -1), -3, 3);
        show_signed(a, "Octave", a->octave);
      }
      break;
    }
    case FM1_BTN_FX:
      set_mode(a, a->mode == FM1_MODE_FX ? FM1_MODE_HOME : FM1_MODE_FX);
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    case FM1_BTN_SEL:
      if (a->mode == FM1_MODE_FX) {
        a->fx_grab = a->lab && a->fx_slot == FX_MIX ? 0 : !a->fx_grab;   /* Mix moves nowhere */
        a->dirty = 1;
      } else {
        popup(a, "SEL", "works in FX mode", NULL, -1);
      }
      break;
    case FM1_BTN_GLO:
      set_mode(a, a->mode == FM1_MODE_GLOBAL ? FM1_MODE_HOME : FM1_MODE_GLOBAL);
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    case FM1_BTN_HOME:
      set_mode(a, FM1_MODE_HOME);
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    case FM1_BTN_SEQ:                    /* the Track view, from any mode */
      if (!a->lab || !a->seq) {
        stub_popup(a, button);
        break;
      }
      a->mode = FM1_MODE_SEQ;
      a->fx_grab = 0;
      fm1_seq_ui_enter(&a->ui);
      fm1_seq_ui_sync(&a->ui, a->seq, a->seq_gen, a->frames);
      a->dirty = 1;
      break;
    case FM1_BTN_PLAY:                   /* the UI sent `play` or `stop` above */
      if (!a->lab || !a->seq) stub_popup(a, button);
      break;
    default:
      stub_popup(a, button);
      break;
  }
}

static void turn_param(fm1_app_t *a, int unit, int index, int delta) {
  const fm1_param_t *p = &a->unit[unit].e->params[index];
  float v = a->unit[unit].value[index] + (float)delta * step_of(p);
  if (p->type == FM1_PARAM_ENUM) v = floorf(v + 0.5f);
  fm1_app_set_param(a, unit, index, fm1_param_clamp(p, v));
}

/* The next sound (dir +1/-1) in registry order, wrapping. */
static int next_sound(int from, int dir) {
  int n = (int)fm1_engine_count;
  for (int k = 1; k <= n; ++k) {
    int i = ((from + dir * k) % n + n) % n;
    if (fm1_engines[i]->kind == FM1_KIND_SOUND) return i;
  }
  return from;
}

/* The next choice of `kind` for a unit that may be empty: -1 (empty), then
 * every entry of that kind. */
static int next_entry(int from, int dir, fm1_kind_t kind) {
  int n = (int)fm1_engine_count;
  for (int k = 1; k <= n + 1; ++k) {
    int i = ((from + 1 + dir * k) % (n + 1) + (n + 1)) % (n + 1) - 1;
    if (i == -1 || fm1_engines[i]->kind == kind) return i;
  }
  return from;
}

/* The next effect choice for a slot: -1 (empty), then every effect. */
static int next_fx(int from, int dir) { return next_entry(from, dir, FM1_KIND_AUDIO_FX); }

/* Sound units 1..3 can be empty: their PRESETS list starts with Empty, as
 * an effect slot's ALGORITHM list does. */
static int sound_empty_ok(const fm1_app_t *a) { return a->sound != 0; }

static int next_preset(const fm1_app_t *a, int from, int dir) {
  return sound_empty_ok(a) ? next_entry(from, dir, FM1_KIND_SOUND) : next_sound(from, dir);
}

static const char *entry_name(int index) { return index < 0 ? "Empty" : fm1_engines[index]->name; }

static void preset_popup(fm1_app_t *a) {
  int cur_index = cur(a)->index;
  if (cur_index < 0 && !sound_empty_ok(a)) return;
  popup(a, entry_name(next_preset(a, cur_index, -1)), entry_name(cur_index),
        entry_name(next_preset(a, cur_index, +1)), 1);
}

/* SHIFT + PRESETS: the current sound, 1 to 4, and what it holds. */
static void sound_popup(fm1_app_t *a) {
  char line[24];
  snprintf(line, sizeof line, "Sound %d of %d", a->sound + 1, FM1_APP_SOUNDS);
  if (cur(a)->e) popup(a, line, cur(a)->e->name, NULL, -1);
  else popup(a, line, "Empty:", "turn PRESETS", -1);
}

/* FX mode walks (slot, page) pairs: slot 1's pages, then slot 2's (with
 * the lab switch: In1, In2, Mix, M1, M2). */
static void fx_step(fm1_app_t *a, int delta) {
  while (delta) {
    int dir = delta > 0 ? 1 : -1;
    int pages = fx_pages(a, a->fx_slot);
    int page = a->fx_page + dir;
    if (page >= 0 && page < pages) {
      a->fx_page = page;
    } else if (a->fx_slot + dir >= 0 && a->fx_slot + dir < fx_slots(a)) {
      a->fx_slot += dir;
      a->fx_page = dir > 0 ? 0 : fx_pages(a, a->fx_slot) - 1;
    }
    delta -= dir;
  }
}

/* SEL then SELECT in FX mode: the slot swaps with its neighbour in its own
 * group (the two master slots, or with the lab switch the two inserts),
 * arenas and all. */
static void fx_swap(fm1_app_t *a, int delta) {
  int lo = 0, hi = FM1_APP_FX_SLOTS - 1;
  if (a->lab) {
    if (a->fx_slot == FX_MIX) return;
    lo = a->fx_slot < FX_MIX ? FX_IN1 : FX_M1;
    hi = a->fx_slot < FX_MIX ? FX_IN2 : FX_M2;
  }
  const int to = clampi(a->fx_slot + (delta > 0 ? 1 : -1), lo, hi);
  if (to != a->fx_slot) {
    const int ua = fx_unit_at(a, a->fx_slot), ub = fx_unit_at(a, to);
    fm1_app_unit_t t = a->unit[ub];
    a->unit[ub] = a->unit[ua];
    a->unit[ua] = t;
    a->fx_slot = to;
    a->fx_page = 0;
  }
}

/* ALGORITHM in FX mode with the lab switch: the slot's effect, stepping
 * over a choice the RAM meter (or anything else) refuses, as PRESETS does,
 * so every effect past it stays reachable; the popup names the first one
 * refused and why. */
static void fx_choose_lab(fm1_app_t *a, int unit, int delta) {
  const int dir = delta > 0 ? 1 : -1;
  int to = a->unit[unit].index, refused = -1, code = 0, r = -1;
  for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_fx(to, dir);
  for (int tries = 0; tries <= (int)fm1_engine_count; ++tries) {
    r = fm1_app_select(a, unit, to);
    if (r == 0) break;
    if (refused < 0) refused = to, code = r;
    to = next_fx(to, dir);
    if (to == a->unit[unit].index) break;
  }
  a->fx_page = 0;
  if (refused >= 0) refusal_popup(a, refused, code);
  else if (to < 0) popup(a, "Empty slot", NULL, NULL, -1);
  else popup(a, fm1_engines[to]->name, NULL, NULL, -1);
}

void fm1_app_encoder(fm1_app_t *a, int encoder, int delta) {
  if (encoder < 0 || encoder >= FM1_ENC_COUNT || delta == 0) return;
  delta = clampi(delta, -64, 64);
  if (a->lab && a->seq) {               /* with steps held: the Step pages */
    const fm1_seq_ui_emit_t out = ui_out(a);
    const int took = fm1_seq_ui_encoder(&a->ui, a->seq, encoder, delta, a->frames, a->mode, &out);
    if (took) {
      ui_after(a);
      return;
    }
  }
  const int snd_unit = fm1_app_sound_unit(a->sound);   /* the current sound */
  switch (encoder) {
    case FM1_ENC_SELECT:
      if (a->mode == FM1_MODE_HOME || a->mode == FM1_MODE_SEQ) {
        a->page = clampi(a->page + delta, 0, page_count(cur(a)->e) - 1);
        forget_knob_hint(a);             /* the hint named the last page's knob */
      } else if (a->mode == FM1_MODE_FX && a->fx_grab) {
        fx_swap(a, delta);
      } else if (a->mode == FM1_MODE_FX) {
        fx_step(a, delta);
      }
      a->dirty = 1;
      break;
    case FM1_ENC_PRESETS: {
      if (a->lab && a->ui.shift) {       /* SHIFT + PRESETS: the current sound (§3.16) */
        a->ui.shift_clean = 0;
        fm1_app_unit_set_current(a, clampi(a->sound + delta, 0, FM1_APP_SOUNDS - 1));
        sound_popup(a);
        break;
      }
      const int empty_ok = sound_empty_ok(a);
      int cur_index = cur(a)->index < 0 && !empty_ok ? 0 : cur(a)->index;
      int dir = delta > 0 ? 1 : -1;
      int to = cur_index, refused = -1, code = 0;
      for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_preset(a, to, dir);
      /* A sound this host cannot run (or, with the lab switch, one that
       * would not fit the RAM) is stepped over, so every other one stays
       * reachable; the popup names the first one skipped. */
      for (int tries = 0; tries < (int)fm1_engine_count + empty_ok && to != cur(a)->index; ++tries) {
        int r = fm1_app_select(a, snd_unit, to);
        if (r == 0) break;
        if (refused < 0) refused = to, code = r;
        to = next_preset(a, to, dir);
      }
      if (refused >= 0) refusal_popup(a, refused, code);
      else preset_popup(a);
      break;
    }
    case FM1_ENC_ALGORITHM:
      if (a->button_down[FM1_BTN_OCT_DOWN] || a->button_down[FM1_BTN_OCT_UP]) {
        a->transpose = clampi(a->transpose + delta, -12, 12);
        show_signed(a, "Transpose", a->transpose);
      } else if (a->mode == FM1_MODE_FX && a->lab) {
        const int unit = fx_unit_at(a, a->fx_slot);
        if (unit >= 0) fx_choose_lab(a, unit, delta);   /* the Mix page has no effect */
      } else if (a->mode == FM1_MODE_FX) {
        int slot = 1 + a->fx_slot;
        int to = a->unit[slot].index;
        for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_fx(to, delta > 0 ? 1 : -1);
        int r = fm1_app_select(a, slot, to);
        a->fx_page = 0;
        if (r != 0) refusal_popup(a, to, r);
        else if (to < 0) popup(a, "Empty slot", NULL, NULL, -1);
        else popup(a, fm1_engines[to]->name, NULL, NULL, -1);
      } else if (cur(a)->e) {
        int m = model_param(cur(a)->e);
        if (m >= 0) {
          char buf[24];
          turn_param(a, snd_unit, m, delta);
          fm1_look_value(&cur(a)->e->params[m], cur(a)->value[m], buf, sizeof buf);
          popup(a, cur(a)->e->params[m].name, buf, NULL, -1);
        }
      }
      break;
    default: {
      int knob = encoder - FM1_ENC_KNOB1;
      int unit = a->mode == FM1_MODE_FX ? fx_unit_at(a, a->fx_slot) : snd_unit;
      int page = a->mode == FM1_MODE_FX ? a->fx_page : a->page;
      int idx[4];
      if (a->mode == FM1_MODE_GLOBAL) break;
      if (a->mode == FM1_MODE_FX && unit < 0) {   /* the Mix page: KNOBn is sound n's level */
        fm1_app_unit_set_level(a, knob, a->level[knob] + (float)delta);
        break;
      }
      if (unit < 0 || !a->unit[unit].e) break;
      if (knob < page_params(a->unit[unit].e, page, idx)) {
        turn_param(a, unit, idx[knob], delta);
        if (a->mode == FM1_MODE_SEQ) {   /* its name and value on the hint line */
          fm1_seq_ui_knob(&a->ui, knob, a->frames + (uint64_t)(2.0f * a->host.sample_rate));
        }
      }
      break;
    }
  }
}

void fm1_app_master(fm1_app_t *a, float position, int show) {
  if (!(position == position)) return;
  if (position < 0.0f) position = 0.0f;
  if (position > 1.0f) position = 1.0f;
  a->master = position;
  a->gain = position * position;
  if (show) {
    char buf[24];
    snprintf(buf, sizeof buf, "Volume %d", (int)floorf(position * 100.0f + 0.5f));
    popup(a, buf, NULL, NULL, -1);
  }
}

/* ---- LEDs ---------------------------------------------------------------------- */

/* The stock octave LED: off at 0, slow blink at 1, fast at 2, solid at 3. */
static int octave_led(const fm1_app_t *a, int magnitude) {
  double t = seconds(a);
  if (magnitude <= 0) return 0;
  if (magnitude >= 3) return 1;
  double period = magnitude == 1 ? 1.0 : 0.25;
  return fmod(t, period) < period * 0.5;
}

static void update_leds(fm1_app_t *a) {
  uint8_t led[FM1_APP_LEDS];
  int base = FM1_APP_FIRST_NOTE + 12 * a->octave + a->transpose;
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    int note = base + k, sounding = 0;
    for (int s = 0; note >= 0 && note < 128 && s < FM1_APP_SOUNDS; ++s) sounding |= a->note_count[s][note];
    led[k] = (uint8_t)(a->key_down[k] || sounding);
  }
  for (int b = 0; b < FM1_APP_BUTTONS; ++b) led[FM1_APP_KEYS + b] = a->button_down[b];
  led[FM1_APP_KEYS + FM1_BTN_OCT_DOWN] = (uint8_t)octave_led(a, -a->octave);
  led[FM1_APP_KEYS + FM1_BTN_OCT_UP] = (uint8_t)octave_led(a, a->octave);
  led[FM1_APP_KEYS + FM1_BTN_FX] = a->mode == FM1_MODE_FX;
  led[FM1_APP_KEYS + FM1_BTN_SEL] = (uint8_t)((a->mode == FM1_MODE_FX && a->fx_grab) ||
                                               (a->lab && a->ui.shift));
  led[FM1_APP_KEYS + FM1_BTN_GLO] = a->mode == FM1_MODE_GLOBAL;
  if (a->lab) {
    /* SEQ in SEQ mode, PLAY while the transport runs; in SEQ mode the
     * white keys show the bar's steps, the playhead inverted, and the two
     * bar keys their role (sequencer notes light no key outside it: owner
     * decision O6). */
    led[FM1_APP_KEYS + FM1_BTN_SEQ] = a->mode == FM1_MODE_SEQ;
    led[FM1_APP_KEYS + FM1_BTN_PLAY] = a->ui.playing != 0;
    if (a->mode == FM1_MODE_SEQ) {
      const uint32_t keys = fm1_seq_ui_key_leds(&a->ui, a->frames);
      for (int k = 0; k < FM1_APP_KEYS; ++k) led[k] = (uint8_t)(a->key_down[k] || ((keys >> k) & 1u));
    }
  }
  if (memcmp(led, a->led, sizeof led) != 0) {
    memcpy(a->led, led, sizeof led);
    a->leds_changed = 1;
  }
}

/* ---- audio --------------------------------------------------------------------- */

static void seq_flush(fm1_app_t *a);

/* The bridge's sink: one sound unit (its ctx says which), called exactly
 * as fm1-render's sink calls its engine (no velocity clamp: the core's
 * velocities are 1..127 already). The app counts the notes, to release
 * them, and mirrors each lock for the screen without touching value[], the
 * knob's own value. */
static void sink_render(void *ctx, float *lr, uint32_t n) {
  const fm1_app_sink_ctx_t *c = (const fm1_app_sink_ctx_t *)ctx;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  u->e->render(u->self, lr, n);
}

static void sink_note_on(void *ctx, uint8_t note, uint8_t velocity) {
  const fm1_app_sink_ctx_t *c = (const fm1_app_sink_ctx_t *)ctx;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  uint8_t *count = c->a->seq_note_count[c->sound];
  u->e->note_on(u->self, note, velocity);
  if (note < 128 && count[note] < 255) ++count[note];
}

static void sink_note_off(void *ctx, uint8_t note) {
  const fm1_app_sink_ctx_t *c = (const fm1_app_sink_ctx_t *)ctx;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  uint8_t *count = c->a->seq_note_count[c->sound];
  u->e->note_off(u->self, note);
  if (note < 128 && count[note]) --count[note];
}

static void sink_set_param(void *ctx, uint16_t index, float value) {
  const fm1_app_sink_ctx_t *c = (const fm1_app_sink_ctx_t *)ctx;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  u->e->set_param(u->self, index, value);
  if (index < FM1_APP_MAX_PARAMS) {
    c->a->lock_shown[c->sound][index] = value;
    c->a->lock_mask[c->sound] |= 1u << index;
  }
}

/* With the lab switch: every sound unit renders its own block, split at its
 * own tracks' events (fm1_seq_host_dispatch_slots), runs its inserts, is
 * scaled by its level (skipped at 100 %) and summed into `out` in unit
 * order, the first one copied. fm1-render --slots does the same, float for
 * float; with sound 0 alone, no insert and level 100 it is the plain path's
 * output to the bit. */
static void render_sounds(fm1_app_t *a, uint32_t n, float *out) {
  fm1_seq_sink_t sink[FM1_APP_SOUNDS];
  fm1_seq_slot_t slot[FM1_APP_SOUNDS];
  int first = 1;
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    const fm1_app_unit_t *u = sound_of(a, k);
    sink[k].ctx = &a->sink_ctx[k];
    sink[k].engine = u->e;
    sink[k].render = sink_render;
    sink[k].note_on = sink_note_on;
    sink[k].note_off = sink_note_off;
    sink[k].set_param = sink_set_param;
    slot[k].sink = u->e ? &sink[k] : NULL;
    slot[k].block = a->mix[k];
  }
  if (a->seq) {
    seq_flush(a);
    a->seq_last_n = fm1_seq_host_advance(&a->seq_host, n);
    fm1_seq_host_dispatch_slots(&a->seq_host, n, slot, FM1_APP_SOUNDS);
  } else {
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      if (slot[k].sink) sound_of(a, k)->e->render(sound_of(a, k)->self, a->mix[k], n);
    }
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    float *b = a->mix[k];
    if (!slot[k].sink) continue;
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      const fm1_app_unit_t *f = &a->unit[fm1_app_insert_unit(k, j)];
      if (f->e) f->e->render(f->self, b, n);
    }
    if (a->level[k] != FM1_APP_LEVEL_MAX) {
      const float g = a->level[k] / 100.0f;
      for (uint32_t i = 0; i < 2 * n; ++i) b[i] *= g;
    }
    if (first) memcpy(out, b, 2u * n * sizeof *out);
    else for (uint32_t i = 0; i < 2 * n; ++i) out[i] += b[i];
    first = 0;
  }
  if (first) {
    for (uint32_t i = 0; i < 2 * n; ++i) out[i] = 0.0f;
  }
}

const float *fm1_app_render(fm1_app_t *a, uint32_t frames) {
  uint32_t n = frames > FM1_APP_MAX_FRAMES ? FM1_APP_MAX_FRAMES : frames;
  float *out = a->out;
  const fm1_app_unit_t *s = &a->unit[0];
  if (a->lab) {
    render_sounds(a, n, out);              /* several sound units, their inserts and levels */
  } else if (a->seq) {
    /* docs/15 §2.4, steps 2-6: what was held, the block's own events, then
     * the sound split at each one it takes. */
    seq_flush(a);
    a->seq_last_n = fm1_seq_host_advance(&a->seq_host, n);
    if (s->e) {
      const fm1_seq_sink_t sink = { &a->sink_ctx[0], s->e, sink_render, sink_note_on, sink_note_off,
                                    sink_set_param };
      fm1_seq_host_dispatch(&a->seq_host, n, out, &sink);
    } else {
      fm1_seq_host_dispatch(&a->seq_host, n, out, NULL);
      for (uint32_t i = 0; i < 2 * n; ++i) out[i] = 0.0f;
    }
  } else if (s->e) {
    s->e->render(s->self, out, n);
  } else {
    for (uint32_t i = 0; i < 2 * n; ++i) out[i] = 0.0f;
  }
  for (int u = 1; u <= FM1_APP_FX_SLOTS; ++u) {   /* the master bus, after the mix */
    if (a->unit[u].e) a->unit[u].e->render(a->unit[u].self, out, n);
  }
  fm1_mix_limiter_process(&a->limiter, out, n);
  for (uint32_t i = 0; i < n; ++i) {
    float m = 0.5f * (out[2 * i] + out[2 * i + 1]);
    a->scope[a->scope_pos] = m;
    a->scope_pos = (a->scope_pos + 1) % FM1_APP_SCOPE;
    float p = fabsf(out[2 * i]) > fabsf(out[2 * i + 1]) ? fabsf(out[2 * i]) : fabsf(out[2 * i + 1]);
    if (p > a->peak) a->peak = p;
  }
  if (a->gain != 1.0f) {
    for (uint32_t i = 0; i < 2 * n; ++i) out[i] *= a->gain;
  }
  a->frames += n;
  if (a->popup_lines && a->frames >= a->popup_until) {
    a->popup_lines = 0;
    a->dirty = 1;
  }
  if (a->lab && a->seq) {
    if (fm1_seq_ui_sync(&a->ui, a->seq, a->seq_gen, a->frames) && a->mode == FM1_MODE_SEQ) {
      a->dirty = 1;
    }
  }
  update_leds(a);
  return out;
}

/* ---- the sequencer ------------------------------------------------------------- */

/* Room an op needs (the event-room rule, fm1_seq_host.h): the most one
 * command can cause, and the block's own minimum after it. 201 events at 8
 * tracks, of 256. */
static uint32_t seq_need(const fm1_app_t *a) {
  return fm1_seq_cmd_max_events(&a->seq_lim) + fm1_seq_min_events(&a->seq_lim);
}

static int seq_fits(const fm1_app_t *a) {
  return fm1_seq_host_room(&a->seq_host) >= seq_need(a);
}

static void seq_apply(fm1_app_t *a, const fm1_seq_cmd_t *c) {
  ++a->seq_gen;
  fm1_seq_host_cmd(&a->seq_host, c);
  if (a->on_cmd) a->on_cmd(a->on_cmd_ctx, a->frames, c);
}

/* A held command goes in as soon as it fits: first thing at the next
 * block, since every input and every render calls this first. */
static void seq_flush(fm1_app_t *a) {
  if (a->seq_pending && seq_fits(a)) {
    a->seq_pending = 0;
    seq_apply(a, &a->seq_pend);
  }
}

static int is_blank(char c) { return c == ' ' || c == '\t'; }

size_t fm1_app_seq_line(fm1_app_t *a, const char *ops, size_t len) {
  if (!a->seq) return 0;
  ++a->seq_gen;
  seq_flush(a);
  if (a->seq_pending) return 0;
  if (fm1_seq_realtime_status(ops, len) || (len && ops[0] == '#')) {
    /* Realtime input is one op. A batch tag suppresses a resent batch, which
     * only the core can tell, so a tagged line goes in whole, given room for
     * every op in it (or an empty buffer, if that is more than it has). */
    uint32_t k = 1, need;
    for (size_t i = 0; i < len; ++i) k += ops[i] == ';';
    need = k * fm1_seq_cmd_max_events(&a->seq_lim) + fm1_seq_min_events(&a->seq_lim);
    if (need > a->seq_host.cap) need = a->seq_host.cap;
    if (fm1_seq_host_room(&a->seq_host) < need) return 0;
    fm1_seq_host_line(&a->seq_host, ops, len);
    return len;
  }
  /* Op by op, as fm1_seq_apply_text splits and trims them; with no tag and
   * no compat mode its loop is exactly parse and apply per op. */
  for (size_t i = 0; i <= len; ++i) {
    size_t start = i, b;
    while (i < len && ops[i] != ';') ++i;
    b = i;
    while (start < b && is_blank(ops[start])) ++start;
    while (b > start && is_blank(ops[b - 1])) --b;
    if (b > start) {
      fm1_seq_cmd_t c;
      if (!seq_fits(a)) return start;
      fm1_seq_parse(ops + start, b - start, &c);
      fm1_seq_host_cmd(&a->seq_host, &c);
    }
  }
  return len;
}

int fm1_app_seq_cmd(fm1_app_t *a, const fm1_seq_cmd_t *c) {
  if (!a->seq) return FM1_APP_SEQ_REFUSED;
  seq_flush(a);
  if (a->seq_pending) {
    ++a->seq_busy;
    return FM1_APP_SEQ_BUSY;
  }
  if (seq_fits(a)) {
    seq_apply(a, c);
    return FM1_APP_SEQ_APPLIED;
  }
  a->seq_pend = *c;
  a->seq_pending = 1;
  ++a->seq_held;
  return FM1_APP_SEQ_HELD;
}

void fm1_app_seq_note_in(fm1_app_t *a, int track, int pitch, int velocity) {
  if (!a->seq || track < 0 || track > 255 || pitch < 0 || pitch > 127) return;
  ++a->seq_gen;
  seq_flush(a);
  fm1_seq_host_note_in(&a->seq_host, (uint8_t)track, (uint8_t)pitch,
                       (uint8_t)clampi(velocity, 0, 127));
}

/* Before a reset or an import: the instance's gates are about to go, so
 * its notes on the engine are released now, and nothing queued for it
 * (a held command, events for the next block) is played. */
static void seq_drop(fm1_app_t *a) {
  ++a->seq_gen;
  seq_release(a);
  memset(a->lock_mask, 0, sizeof a->lock_mask);
  a->seq_pending = 0;
  a->seq_host.n = 0;
  a->seq_last_n = 0;
}

int fm1_app_seq_reset(fm1_app_t *a, int tracks) {
  fm1_seq_limits_t lim;
  fm1_seq_stats_t st;
  if (tracks < 1 || tracks > FM1_APP_SEQ_TRACKS) return -1;
  if (a->seq) {
    seq_drop(a);
    fm1_seq_get_stats(a->seq, &st);
    a->seq_dropped_before += st.dropped_events;
  }
  fm1_seq_limits_default(&lim, (uint8_t)tracks);
  ++a->seq_gen;
  a->seq_lim = lim;
  a->seq = fm1_seq_size(&lim) <= sizeof a->seq_mem
               ? fm1_seq_create(a->seq_mem, &lim, (uint32_t)lrintf(a->host.sample_rate))
               : NULL;
  if (a->seq_host.seq) {   /* the same buffer; the counters run on */
    a->seq_host.seq = a->seq;
  } else {
    fm1_seq_host_init(&a->seq_host, a->seq, a->seq_ev, FM1_APP_SEQ_EVENTS);
  }
  return a->seq ? 0 : -1;
}

int fm1_app_seq_import(fm1_app_t *a, const char *txt, size_t len) {
  if (!a->seq) return 0;
  seq_drop(a);
  return fm1_seq_host_import(&a->seq_host, txt, len);   /* resolves the lanes' uids once */
}

int fm1_app_seq_route(fm1_app_t *a, int track, int kind, int index) {
  if (!a->seq || track < 0 || track > 255 || kind < 0 || kind > 255 || index < 0 || index > 255) {
    return 0;
  }
  ++a->seq_gen;
  return fm1_seq_set_route(a->seq, (uint8_t)track, (uint8_t)kind, (uint8_t)index);
}

int fm1_app_seq_default_route(fm1_app_t *a) {
  return a->seq ? fm1_seq_default_route(a->seq, a->unit[0].e != NULL) : 0;
}

const fm1_seq_t *fm1_app_seq(const fm1_app_t *a) { return a->seq; }

const fm1_seq_ev_t *fm1_app_seq_events(const fm1_app_t *a, uint32_t *n) {
  if (n) *n = a->seq_last_n;
  return a->seq_ev;
}

uint64_t fm1_app_seq_dropped(const fm1_app_t *a) {
  fm1_seq_stats_t st;
  if (!a->seq) return a->seq_dropped_before;
  fm1_seq_get_stats(a->seq, &st);
  return a->seq_dropped_before + st.dropped_events;
}

/* ---- the screen ---------------------------------------------------------------- */

void fm1_look_bar(fm1_tft_t *t, int x, int y, int w, int h, const fm1_param_t *p, float v,
                  uint16_t fill) {
  fm1_tft_graphic(t, x, y, w, h);
  fm1_tft_paint(t, x, y, w, h, C_BAR_BG);
  if (p->type == FM1_PARAM_ENUM) {
    int n = (int)(p->max - p->min) + 1;
    int i = enum_index(p, v);
    int seg = w / n < 3 ? 3 : w / n;
    int sx = x + (i * (w - seg)) / (n > 1 ? n - 1 : 1);
    fm1_tft_paint(t, sx, y, seg, h, fill);
    return;
  }
  float range = p->max - p->min;
  float f = range > 0.0f ? (v - p->min) / range : 0.0f;
  f = f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
  int pos = x + (int)floorf(f * (float)w + 0.5f);
  if (p->min < 0.0f && p->max > 0.0f) {          /* bipolar: from the zero point */
    int zero = x + (int)floorf((-p->min / range) * (float)w + 0.5f);
    int a0 = pos < zero ? pos : zero, a1 = pos < zero ? zero : pos;
    fm1_tft_paint(t, a0, y, a1 - a0 > 0 ? a1 - a0 : 1, h, fill);
    fm1_tft_paint(t, zero, y, 1, h, C_TEXT);
  } else {
    fm1_tft_paint(t, x, y, pos - x, h, fill);
  }
}

static void draw_params(fm1_app_t *a, int unit, int page, int y0) {
  const fm1_app_unit_t *u = &a->unit[unit];
  int idx[4];
  int n = page_params(u->e, page, idx);
  for (int s = 0; s < n; ++s) {
    const fm1_param_t *p = &u->e->params[idx[s]];
    char value[24];
    int y = y0 + s * ROW_PITCH;
    fm1_look_value(p, u->value[idx[s]], value, sizeof value);
    fm1_look_row(&a->tft, y, p->name, value, C_TEXT);
    fm1_look_bar(&a->tft, MARGIN, y + BAR_DY, FM1_TFT_W - 2 * MARGIN, BAR_H, p, u->value[idx[s]],
                 C_ACCENT);
  }
}

static void draw_meter(fm1_app_t *a) {
  const int x = 206, y = 6, w = 28, h = 12;
  fm1_tft_graphic(&a->tft, x, y, w, h);
  fm1_tft_paint(&a->tft, x, y, w, h, C_BAR_BG);
  float m = a->meter > 1.0f ? 1.0f : a->meter;
  /* -48 dB .. 0 dB across the width */
  float db = m > 0.0f ? 20.0f * log10f(m) : -100.0f;
  int fill = (int)floorf((db + 48.0f) / 48.0f * (float)w + 0.5f);
  fill = clampi(fill, 0, w);
  fm1_tft_paint(&a->tft, x, y, fill, h, m >= 0.97f ? C_WARN : C_METER);
}

/* The RAM meter (lab), where the RAM figure is otherwise: a bar of the
 * chain's RAM against FM1_APP_RAM_BUDGET and the percentage, rounded up,
 * in the warning colour past 100 %. The bar sits where "100%" would start,
 * so it never moves. */
static void draw_ram_meter(fm1_app_t *a) {
  const size_t used = fm1_app_ram(a);
  const unsigned pct = (unsigned)((used * 100u + FM1_APP_RAM_BUDGET - 1u) / FM1_APP_RAM_BUDGET);
  const int over = used > FM1_APP_RAM_BUDGET;
  const int bw = 36, bh = 8, by = BOTTOM_Y + 8;
  const int bx = RIGHT - fm1_tft_text_width("100%", 4, SCALE) - FM1_APP_LAYOUT_GAP - bw;
  char txt[8];
  int fill;
  snprintf(txt, sizeof txt, "%u%%", pct > 999u ? 999u : pct);
  fill = (int)((used > FM1_APP_RAM_BUDGET ? FM1_APP_RAM_BUDGET : used) * (size_t)bw / FM1_APP_RAM_BUDGET);
  fm1_tft_graphic(&a->tft, bx, by, bw, bh);
  fm1_tft_paint(&a->tft, bx, by, bw, bh, C_BAR_BG);
  fm1_tft_paint(&a->tft, bx, by, fill, bh, over ? C_WARN : C_METER);
  fm1_tft_text(&a->tft, RIGHT - fm1_tft_text_width(txt, 4, SCALE), BOTTOM_Y + 3, txt, 4, SCALE,
               over ? C_WARN : C_DIM);
}

static void draw_bottom(fm1_app_t *a, const char *left) {
  char ram[16];
  size_t bytes = fm1_app_ram(a);
  fm1_tft_fill(&a->tft, 0, BOTTOM_Y, FM1_TFT_W, FM1_TFT_H - BOTTOM_Y, C_BOTTOM_BG);
  fm1_tft_text(&a->tft, MARGIN, BOTTOM_Y + 3, left, 12, SCALE, C_TEXT);
  if (a->lab) {
    draw_ram_meter(a);
    return;
  }
  snprintf(ram, sizeof ram, "%uK", (unsigned)((bytes + 1023) / 1024));
  int w = fm1_tft_text_width(ram, 6, SCALE);
  fm1_tft_text(&a->tft, RIGHT - w, BOTTOM_Y + 3, ram, 6, SCALE,
               bytes > FM1_APP_RAM_BUDGET ? C_WARN : C_DIM);
}

static void draw_scope(fm1_app_t *a) {
  const int x = MARGIN, y = 192, w = FM1_TFT_W - 2 * MARGIN, h = 20;
  float s[FM1_APP_SCOPE];
  for (int i = 0; i < FM1_APP_SCOPE; ++i) s[i] = a->scope[(a->scope_pos + i) % FM1_APP_SCOPE];
  int start = FM1_APP_SCOPE - w;
  for (int i = 1; i + w <= FM1_APP_SCOPE; ++i) {   /* first rising zero crossing */
    if (s[i - 1] < 0.0f && s[i] >= 0.0f) { start = i; break; }
  }
  /* The trace fills the strip: scaled to the window's peak, but never by
   * more than x16, so quiet noise stays a flat line. */
  float peak = 1.0f / 16.0f;
  for (int i = 0; i < w; ++i) {
    float m = fabsf(s[start + i]);
    if (m > peak) peak = m;
  }
  fm1_tft_graphic(&a->tft, x, y, w, h);
  fm1_tft_paint(&a->tft, x, y, w, h, C_SCOPE_BG);
  int prev = -1;
  for (int i = 0; i < w; ++i) {
    float v = s[start + i] / peak;
    v = v > 1.0f ? 1.0f : (v < -1.0f ? -1.0f : v);
    int py = y + h / 2 - (int)floorf(v * (float)(h / 2 - 1) + 0.5f);
    py = clampi(py, y, y + h - 1);
    int a0 = prev < 0 ? py : (prev < py ? prev : py), a1 = prev < 0 ? py : (prev < py ? py : prev);
    fm1_tft_paint(&a->tft, x + i, a0, 1, a1 - a0 + 1, C_SCOPE);
    prev = py;
  }
}

/* Popups take the whole centre area, between the top and bottom bars, as
 * stock's do ("overlaying the current mode"), so nothing peeks out. */
static void draw_popup(fm1_app_t *a) {
  const int pitch = POPUP_PITCH;   /* the highlight keeps 5 px from the next line */
  const int top = TITLE_H, bottom = BOTTOM_Y;
  fm1_tft_fill(&a->tft, 0, top, FM1_TFT_W, bottom - top, C_POPUP_BG);
  fm1_tft_paint(&a->tft, 0, top, FM1_TFT_W, 2, C_ACCENT);
  fm1_tft_paint(&a->tft, 0, bottom - 2, FM1_TFT_W, 2, C_ACCENT);
  int y0 = (top + bottom) / 2 - (a->popup_lines * pitch - (pitch - 18)) / 2;
  for (int i = 0; i < a->popup_lines; ++i) {
    int ly = y0 + i * pitch;
    int w = fm1_tft_text_width(a->popup[i], POPUP_CHARS, SCALE);
    if (i == a->popup_mark) fm1_tft_paint(&a->tft, 12, ly - 3, FM1_TFT_W - 24, 24, C_ACCENT);
    fm1_tft_text(&a->tft, 120 - w / 2, ly, a->popup[i], POPUP_CHARS, SCALE,
                 i == a->popup_mark ? C_BG : C_TEXT);
  }
}

void fm1_look_row(fm1_tft_t *t, int y, const char *label, const char *value, uint16_t color) {
  int label_chars = (int)strlen(label) < LABEL_CHARS ? (int)strlen(label) : LABEL_CHARS;
  int value_chars = LINE_CHARS - 1 - label_chars;
  fm1_tft_text(t, MARGIN, y, label, label_chars, SCALE, C_DIM);
  int w = fm1_tft_text_width(value, value_chars, SCALE);
  fm1_tft_text(t, RIGHT - w, y, value, value_chars, SCALE, color);
}

static void draw_line(fm1_app_t *a, int y, const char *label, const char *value) {
  fm1_look_row(&a->tft, y, label, value, C_TEXT);
}

/* An empty slot's (or sound's) two hint lines at y0. */
static void draw_empty(fm1_app_t *a, int y0, const char *what, const char *turn) {
  fm1_tft_text(&a->tft, MARGIN, y0 + 4, what, LINE_CHARS, SCALE, C_DIM);
  fm1_tft_text(&a->tft, MARGIN, y0 + 4 + LINE_PITCH, turn, LINE_CHARS, SCALE, C_DIM);
}

/* FX mode with the lab switch (§3.16): the chain on the first line (the
 * current sound, its inserts, Mix, the master slots; the selected one in
 * the accent colour, an empty one dim), the selected slot and its effect on
 * the second, then its page, or the Mix page's four levels. */
static void draw_fx_lab(fm1_app_t *a, char *bottom, size_t size) {
  static const fm1_param_t kLevel = { "Level", FM1_PARAM_FLOAT, 0.0f, FM1_APP_LEVEL_MAX,
                                      FM1_APP_LEVEL_MAX, NULL, 0, 0, 0, 0, "" };
  fm1_tft_t *t = &a->tft;
  char buf[48];
  int x = MARGIN;
  const int y0 = CONTENT_Y + 2 * LINE_PITCH;
  const int unit = fx_unit_at(a, a->fx_slot);
  snprintf(buf, sizeof buf, "S%d", a->sound + 1);
  x += fm1_tft_text(t, x, CONTENT_Y, buf, 2, SCALE, C_MODEL) + FM1_TFT_ADVANCE(SCALE);
  for (int k = 0; k < FX_LAB_SLOTS; ++k) {
    const int u = fx_unit_at(a, k);
    const uint16_t c = k == a->fx_slot ? C_ACCENT : (u < 0 || a->unit[u].e ? C_TEXT : C_DIM);
    x += fm1_tft_text(t, x, CONTENT_Y, kFxTags[k], 3, SCALE, c) + FM1_TFT_ADVANCE(SCALE);
  }
  snprintf(buf, sizeof buf, "%s %s %s", a->fx_grab ? "*" : ">", kFxTags[a->fx_slot],
           unit < 0 ? "levels" : (a->unit[unit].e ? a->unit[unit].e->name : "--"));
  fm1_tft_text(t, MARGIN, CONTENT_Y + LINE_PITCH, buf, LINE_CHARS, SCALE, C_ACCENT);
  if (unit < 0) {
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      const fm1_app_unit_t *u = sound_of(a, k);
      char label[8];
      const int y = y0 + k * ROW_PITCH;
      snprintf(label, sizeof label, "S%d", k + 1);
      snprintf(buf, sizeof buf, "%s %d%%", u->e ? u->e->name : "Empty",
               (int)floorf(a->level[k] + 0.5f));
      fm1_look_row(t, y, label, buf, u->e ? C_TEXT : C_DIM);
      fm1_look_bar(t, MARGIN, y + BAR_DY, FM1_TFT_W - 2 * MARGIN, BAR_H, &kLevel, a->level[k],
                   u->e ? C_ACCENT : C_DIM);
    }
    snprintf(bottom, size, "1/1 Mix");
  } else {
    if (a->unit[unit].e) draw_params(a, unit, a->fx_page, y0);
    else draw_empty(a, y0, "Empty slot:", "turn ALGORITHM");
    if (a->fx_slot < FX_MIX) {
      snprintf(bottom, size, "%d/%d S%d %s", a->fx_page + 1, page_count(a->unit[unit].e),
               a->sound + 1, kFxTags[a->fx_slot]);
    } else {
      snprintf(bottom, size, "%d/%d %s", a->fx_page + 1, page_count(a->unit[unit].e),
               kFxTags[a->fx_slot]);
    }
  }
}

static void draw(fm1_app_t *a) {
  fm1_tft_t *t = &a->tft;
  const fm1_app_unit_t *s = cur(a);
  const int su = fm1_app_sound_unit(a->sound);
  char buf[48];
  fm1_tft_begin(t, C_BG);

  fm1_tft_fill(t, 0, 0, FM1_TFT_W, TITLE_H, C_TITLE_BG);
  if (multi_in_use(a)) {                 /* "S2 Shapes": which of the sounds is current */
    snprintf(buf, sizeof buf, "S%d %s", a->sound + 1, s->e ? s->e->name : "(empty)");
    fm1_tft_text(t, MARGIN, 3, buf, NAME_CHARS, SCALE, C_TEXT);
  } else {
    fm1_tft_text(t, MARGIN, 3, s->e ? s->e->name : "(no sound)", NAME_CHARS, SCALE, C_TEXT);
  }
  draw_meter(a);

  if (a->mode == FM1_MODE_HOME) {
    int m = model_param(s->e);
    if (m >= 0) {
      fm1_look_value(&s->e->params[m], s->value[m], buf, sizeof buf);
      fm1_tft_text(t, MARGIN, CONTENT_Y, buf, LINE_CHARS, SCALE, C_MODEL);
    }
    if (s->e) draw_params(a, su, a->page, CONTENT_Y + LINE_PITCH);
    else if (a->lab) draw_empty(a, CONTENT_Y, "Empty sound:", "turn PRESETS");
    draw_scope(a);
    snprintf(buf, sizeof buf, "%d/%d Sound", a->page + 1, page_count(s->e));
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_FX && a->lab) {
    draw_fx_lab(a, buf, sizeof buf);
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_FX) {
    for (int k = 0; k < FM1_APP_FX_SLOTS; ++k) {
      const fm1_app_unit_t *f = &a->unit[1 + k];
      int sel = k == a->fx_slot;
      snprintf(buf, sizeof buf, "%s %d %s", sel ? (a->fx_grab ? "*" : ">") : " ", k + 1,
               f->e ? f->e->name : "--");
      fm1_tft_text(t, MARGIN, CONTENT_Y + LINE_PITCH * k, buf, LINE_CHARS, SCALE,
                   sel ? C_ACCENT : C_DIM);
    }
    const fm1_app_unit_t *f = &a->unit[1 + a->fx_slot];
    const int y0 = CONTENT_Y + LINE_PITCH * FM1_APP_FX_SLOTS;
    if (f->e) {
      draw_params(a, 1 + a->fx_slot, a->fx_page, y0);
    } else {
      draw_empty(a, y0, "Empty slot:", "turn ALGORITHM");
    }
    snprintf(buf, sizeof buf, "%d/%d FX%d", a->fx_page + 1, page_count(f->e), a->fx_slot + 1);
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_SEQ) {
    fm1_seq_view_sound_t snd;
    snd.e = s->e;
    snd.value = s->value;
    snd.page = a->page;
    snd.pages = page_count(s->e);
    snd.n = page_params(s->e, a->page, snd.idx);
    snd.model = model_param(s->e);
    fm1_seq_view_draw(t, &a->ui, &snd);
    fm1_seq_view_bottom(&a->ui, &snd, buf, sizeof buf);
    draw_bottom(a, buf);
  } else {
    /* Eight lines at a 23 px pitch (the sound's name is in the title bar). */
    const int pitch = 23;
    char v[32];
    int y = CONTENT_Y;
    snprintf(v, sizeof v, "%.0f Hz", (double)a->host.sample_rate);
    draw_line(a, y, "Rate", v); y += pitch;
    snprintf(v, sizeof v, "%u", (unsigned)a->host.max_frames);
    draw_line(a, y, "Block", v); y += pitch;
    snprintf(v, sizeof v, "%uK/%uK", (unsigned)((fm1_app_ram(a) + 1023) / 1024),
             (unsigned)((FM1_APP_RAM_BUDGET + 512) / 1024));
    draw_line(a, y, "RAM", v); y += pitch;
    snprintf(v, sizeof v, "%u", s->e ? (unsigned)s->e->max_voices : 0u);
    draw_line(a, y, "Voices", v); y += pitch;
    draw_line(a, y, "FX1", a->unit[1].e ? a->unit[1].e->id : "--"); y += pitch;
    draw_line(a, y, "FX2", a->unit[2].e ? a->unit[2].e->id : "--"); y += pitch;
    snprintf(v, sizeof v, "%+d", a->octave);
    draw_line(a, y, "Octave", a->octave ? v : "0"); y += pitch;
    snprintf(v, sizeof v, "%+d", a->transpose);
    draw_line(a, y, "Transpose", a->transpose ? v : "0");
    draw_bottom(a, "1/1 Globe");
  }
  if (a->popup_lines) draw_popup(a);
}

int fm1_app_draw(fm1_app_t *a, uint32_t min_frames) {
  int live = a->peak > 0.0f || a->meter > 0.0f;
  if (!a->dirty && !(live && a->frames - a->last_draw >= min_frames)) return 0;
  a->meter = a->peak > a->meter * 0.6f ? a->peak : a->meter * 0.6f;
  if (a->meter < 1e-4f) a->meter = 0.0f;
  a->peak = 0.0f;
  draw(a);
  a->dirty = 0;
  a->last_draw = a->frames;
  return 1;
}

void fm1_app_draw_checked(fm1_app_t *a) {
  a->tft.record = 1;
  draw(a);
  a->tft.record = 0;
}

/* ---- catalogue ------------------------------------------------------------------- */

typedef struct { char *p; size_t left; int full; } sink_t;

#if defined(__GNUC__) || defined(__clang__)
static void put(sink_t *k, const char *fmt, ...) __attribute__((format(printf, 2, 3)));
#endif

static void put(sink_t *k, const char *fmt, ...) {
  va_list ap;
  if (k->full) return;
  va_start(ap, fmt);
  int n = vsnprintf(k->p, k->left, fmt, ap);
  va_end(ap);
  if (n < 0 || (size_t)n >= k->left) {
    k->full = 1;
    return;
  }
  k->p += n;
  k->left -= (size_t)n;
}

static void put_str(sink_t *k, const char *s) {
  put(k, "\"");
  for (; s && *s; ++s) {
    unsigned char c = (unsigned char)*s;
    if (c == '"' || c == '\\') put(k, "\\%c", c);
    else if (c < 0x20) put(k, "\\u%04x", c);
    else put(k, "%c", c);
  }
  put(k, "\"");
}

const char *fm1_app_catalog_json(void) {
  static char buf[32768];
  static int built = 0, ok = 0;
  if (built) return ok ? buf : NULL;
  sink_t k = { buf, sizeof buf, 0 };
  put(&k, "[");
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    put(&k, "%s{\"index\":%u,\"id\":", i ? "," : "", (unsigned)i);
    put_str(&k, e->id);
    put(&k, ",\"name\":");
    put_str(&k, e->name);
    put(&k, ",\"credits\":");
    put_str(&k, e->credits);
    put(&k, ",\"kind\":\"%s\",\"max_voices\":%u,\"params\":[",
        e->kind == FM1_KIND_SOUND ? "sound" : e->kind == FM1_KIND_AUDIO_FX ? "audio_fx" : "midi_fx",
        (unsigned)e->max_voices);
    for (uint16_t p = 0; p < e->n_params; ++p) {
      const fm1_param_t *q = &e->params[p];
      put(&k, "%s{\"name\":", p ? "," : "");
      put_str(&k, q->name);
      put(&k, ",\"type\":\"%s\",\"min\":%g,\"max\":%g,\"def\":%g,\"page\":%u",
          q->type == FM1_PARAM_ENUM ? "enum" : "float", (double)q->min, (double)q->max,
          (double)q->def, (unsigned)q->page);
      if (q->type == FM1_PARAM_ENUM && q->enum_names) {
        int n = (int)(q->max - q->min) + 1;
        put(&k, ",\"names\":[");
        for (int j = 0; j < n; ++j) {
          if (j) put(&k, ",");
          put_str(&k, q->enum_names[j]);
        }
        put(&k, "]");
      }
      put(&k, "}");
    }
    put(&k, "]}");
  }
  put(&k, "]");
  built = 1;
  ok = !k.full;
  return ok ? buf : NULL;
}

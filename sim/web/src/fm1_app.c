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

#include "fm1_fx_host.h"
#include "fm1_look.h"
#include "fm1_mod_view.h"
#include "fm1_seq_view.h"
#include "mod_script.h"

/* Compile-time checks of the sequencer's fixed sizes (docs/15 §2.6; C99 has
 * no static_assert): the event buffer is 3,264 B, the pending record one
 * 240-byte command and the click voice 20 B, on 32- and 64-bit builds
 * alike. The instance's own size comes from fm1_seq_size at run time;
 * fm1_app_seq_reset refuses limits whose instance does not fit
 * FM1_APP_SEQ_BYTES, and tests/test_sim_web.py checks the budget sum. */
typedef char fm1_app_seq_events_are_3k[sizeof(fm1_seq_ev_t) * FM1_APP_SEQ_EVENTS == 3264u ? 1 : -1];
typedef char fm1_app_seq_click_is_20[sizeof(fm1_seq_click_t) == 20u ? 1 : -1];
typedef char fm1_app_seq_ui_sounds[FM1_SEQ_UI_SOUNDS == FM1_APP_SOUNDS ? 1 : -1];
typedef char fm1_app_seq_cmd_is_240[sizeof(fm1_seq_cmd_t) == 240u ? 1 : -1];
typedef char fm1_app_seq_ui_fits[sizeof(fm1_seq_ui_t) <= FM1_APP_SEQ_UI_BYTES ? 1 : -1];
/* Every app unit is one of the runtime's sinks (fm1_mod.h's codes): the
 * sound units, their inserts and the master slots. */
typedef char fm1_app_mod_units[FM1_MOD_SOUNDS == FM1_APP_SOUNDS && FM1_MOD_INSERTS == FM1_APP_INSERTS &&
                               FM1_MOD_SINKS == FM1_APP_UNITS + 1 && FM1_APP_FX_SLOTS == 2 ? 1 : -1];

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
  if (a->sound != 0) return 1;
  for (int k = 1; k < FM1_APP_SOUNDS; ++k) {
    if (sound_of_c(a, k)->e) return 1;
  }
  return 0;
}

/* FX mode's slots: the current sound's inserts, its Mix page (every
 * sound's level), and the master bus. */
enum { FX_IN1 = 0, FX_IN2, FX_MIX, FX_M1, FX_M2, FX_SLOT_COUNT };
static const char *const kFxTags[FX_SLOT_COUNT] = { "In1", "In2", "Mix", "M1", "M2" };

/* The unit FX mode's slot shows, or -1 for the Mix page. */
static int fx_unit_at(const fm1_app_t *a, int slot) {
  if (slot == FX_MIX) return -1;
  if (slot < FX_MIX) return fm1_app_insert_unit(a->sound, slot);
  return 1 + slot - FX_M1;
}

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
  /* A wide range's small fraction keeps one decimal: the Gate's 0.5 ms
   * Attack would otherwise read "0". */
  if (decimals == 0 && fabsf(v) < 10.0f && fabsf(v - floorf(v + 0.5f)) >= 0.05f) decimals = 1;
  if (fm1_param_is_log(p)) {
    /* LOG (engine API v3): a detent is a ratio, so the digits follow the
     * value, three significant ones or more down to 1 (1.07 ms, 21.4 Hz,
     * 2143 Hz). */
    decimals = v < 10.0f ? 2 : (v < 100.0f ? 1 : 0);
  }
  float tiny = decimals == 2 ? 0.005f : (decimals == 1 ? 0.05f : 0.5f);
  if (fabsf(v) < tiny) v = 0.0f;   /* no "-0.00" */
  snprintf(buf, size, "%.*f", decimals, (double)v);
}

/* Detent size for a linear float parameter: a hundredth of its range, or
 * whole units for wide integer ranges such as 0..100. A LOG one steps in
 * step_value. */
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
  a->popup_title[0] = '\0';
  a->popup_first = a->popup_total = 0;
  a->popup_dim = 0;
  a->popup_until = a->frames + (uint64_t)a->host.sample_rate;   /* about a second */
  a->dirty = 1;
}

/* Entry k of a list popup's list, into buf; 1 to draw it dim. */
typedef int (*list_entry_fn)(const fm1_app_t *a, const void *ctx, int k, char *buf, size_t size);

/* A list popup, for as long as a message's: `title`, entry `sel` of
 * `total` chosen, and the window of entries around it that the screen
 * shows (fm1_list_first), each named by `name`. */
static void list_popup(fm1_app_t *a, const char *title, int total, int sel, list_entry_fn name,
                       const void *ctx) {
  const int first = fm1_list_first(total, sel, FM1_LIST_ROWS);
  a->popup_lines = 0;
  a->popup_dim = 0;
  for (int r = 0; r < FM1_LIST_ROWS && first + r < total; ++r) {
    if (name(a, ctx, first + r, a->popup[r], sizeof a->popup[r])) a->popup_dim |= 1u << r;
    a->popup_lines = r + 1;
  }
  snprintf(a->popup_title, sizeof a->popup_title, "%s", title);
  a->popup_first = first;
  a->popup_total = total;
  a->popup_mark = sel - first;
  a->popup_until = a->frames + (uint64_t)a->host.sample_rate;
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

/* The lock sound (docs/15 S8): the sound unit the focused track routes to,
 * whose parameters its lanes lock, and whether it is the current sound.
 * Returns its index, or -1 (a MIDI route, an empty sound, no sequencer),
 * with snd's engine NULL. */
static int lock_sound(fm1_app_t *a, fm1_seq_ui_sound_t *snd) {
  const int k = a->seq ? fm1_app_unit_of_track(a, a->ui.track) : -1;
  const fm1_app_unit_t *u = k >= 0 ? sound_of(a, k) : NULL;
  snd->e = u ? u->e : NULL;
  snd->value = u ? u->value : NULL;
  snd->current = k == a->sound;
  return u && u->e ? k : -1;
}

/* A parameter name of the lock sound for a toast. */
static const char *lock_param_name(fm1_app_t *a, int param) {
  fm1_seq_ui_sound_t snd;
  return lock_sound(a, &snd) >= 0 && param < snd.e->n_params ? snd.e->params[param].name : "?";
}

/* The UI made a lane on a parameter of the lock sound: the knob goes onto
 * the 7-bit grid, to the value the lane's base gives (fm1_seq_lock_value of
 * fm1_seq_value7), so a stop's D6 revert sends the engine exactly value[]. */
static void ui_snap(fm1_app_t *a) {
  fm1_seq_ui_sound_t snd;
  const int param = a->ui.snap;
  const int k = lock_sound(a, &snd);
  a->ui.snap = -1;
  if (k >= 0 && param >= 0 && param < snd.e->n_params) {
    const fm1_param_t *p = &snd.e->params[param];
    const float v = fm1_seq_lock_value(p, fm1_seq_value7(p, snd.value[param]));
    if (v != snd.value[param]) fm1_app_set_param(a, fm1_app_sound_unit(k), param, v);
  }
}

/* The UI's toast, if any, as a popup. */
static void ui_toast(fm1_app_t *a) {
  switch (a->ui.toast) {
    case FM1_SEQ_TOAST_FULL_VEL_ON: popup(a, "Full velocity", "on", NULL, -1); break;
    case FM1_SEQ_TOAST_FULL_VEL_OFF: popup(a, "Full velocity", "off", NULL, -1); break;
    case FM1_SEQ_TOAST_CAPTURED: popup(a, "Captured", NULL, NULL, -1); break;
    case FM1_SEQ_TOAST_NOTHING: popup(a, "Nothing to capture", NULL, NULL, -1); break;
    case FM1_SEQ_TOAST_TRACK:
    case FM1_SEQ_TOAST_TRACK_EMPTIED: {
      char line[24];
      snprintf(line, sizeof line, "Track %u", (unsigned)a->ui.toast_arg + 1u);
      popup(a, line, a->ui.toast == FM1_SEQ_TOAST_TRACK_EMPTIED ? "Capture emptied" : NULL, NULL, -1);
      break;
    }
    case FM1_SEQ_TOAST_METRO_ON: popup(a, "Metronome", "on", NULL, -1); break;
    case FM1_SEQ_TOAST_METRO_OFF: popup(a, "Metronome", "off", NULL, -1); break;
    case FM1_SEQ_TOAST_QUANT: {
      char line[24];
      snprintf(line, sizeof line, "%u%%", (unsigned)a->ui.toast_arg);
      popup(a, "Clip quantize", line, NULL, -1);
      break;
    }
    case FM1_SEQ_TOAST_LANES_FULL: popup(a, "8 lanes used", NULL, NULL, -1); break;
    case FM1_SEQ_TOAST_NOLOCK:
      popup(a, lock_param_name(a, a->ui.toast_arg), "cannot be locked", NULL, -1);
      break;
    case FM1_SEQ_TOAST_LOCK_CLEARED:
      popup(a, lock_param_name(a, a->ui.toast_arg), "lock cleared", NULL, -1);
      break;
    case FM1_SEQ_TOAST_LANE_CLEARED:
      popup(a, lock_param_name(a, a->ui.toast_arg), "lane cleared", NULL, -1);
      break;
    case FM1_SEQ_TOAST_LOCKS_CLEARED: popup(a, "Locks cleared", NULL, NULL, -1); break;
    default: break;
  }
  a->ui.toast = FM1_SEQ_TOAST_NONE;
}

/* The focused track's sound becomes the current one when the UI focused a
 * track or routed it to a sound (S6): the keys then play, and HOME edits,
 * what the track plays. SHIFT + PRESETS still chooses any sound after. */
static void ui_follow(fm1_app_t *a) {
  if (!a->ui.follow) return;
  a->ui.follow = 0;
  if (a->ui.route_kind == FM1_SEQ_ROUTE_ENGINE && a->ui.route_index < FM1_APP_SOUNDS) {
    fm1_app_unit_set_current(a, a->ui.route_index);
  }
}

/* After an edge the UI took: the screen and LEDs follow, and its toast, if
 * any, becomes a popup. */
static void ui_after(fm1_app_t *a) {
  if (a->ui.snap >= 0) ui_snap(a);
  ui_follow(a);
  ui_toast(a);
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

/* The note a key plays. A pad kit (an engine that says so, pad_count in
 * fm1_engine.h: Sophie and Drums, 16 pads on MIDI notes 36-51, the General
 * MIDI drum keys) sits below the keys' range at any useful octave (53-79
 * at octave 0), so with a kit as the current sound the 16 white keys play
 * its pads 1-16 whatever the octave, and the black keys, and white keys
 * past its last pad, play nothing (-1). MIDI IN keeps the drum map. */
static int key_note(const fm1_app_t *a, int key) {
  /* White keys from F: F G A B C D E. */
  static const int8_t white_of[12] = {0, -1, 1, -1, 2, -1, 3, 4, -1, 5, -1, 6};
  const fm1_engine_t *e = sound_of_c(a, a->sound)->e;
  if (e && e->pad_count) {
    const int w = white_of[key % 12];
    return w < 0 ? -1 : fm1_engine_pad_note(e, 7 * (key / 12) + w);
  }
  return base_note(a) + key;
}

/* HOME, FX and GLO leave SEQ mode; its holds go without a toggle. */
static void set_mode(fm1_app_t *a, int mode) {
  if (a->mode == FM1_MODE_SEQ && mode != FM1_MODE_SEQ) fm1_seq_ui_leave(&a->ui);
  a->mode = mode;
}

/* ---- set-up and units --------------------------------------------------------- */

/* Everything fm1_app_init sets up but modulation, which needs the sinks
 * and the runtime's code below. */
static void app_init(fm1_app_t *a, float sample_rate) {
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
  a->fx_slot = FX_M1;                  /* FX mode opens on the master bus */
  fm1_seq_ui_init(&a->ui, sample_rate);
  fm1_seq_click_init(&a->click, (uint32_t)lrintf(sample_rate));
  fm1_mod_ui_init(&a->mui);
  fm1_app_seq_reset(a, FM1_APP_SEQ_TRACKS);
}

static void mod_start(fm1_app_t *a, uint32_t seed, int deflt);

void fm1_app_init(fm1_app_t *a, float sample_rate) {
  app_init(a, sample_rate);
  mod_start(a, FM1_APP_MOD_SEED, 1);   /* modulation from the default rack (docs/16 MG3) */
}

/* ---- modulation: the runtime on the bridge (docs/16 MG3) ------------------------ */

int fm1_app_mod_unit(int unit) {
  if (unit >= 0 && unit <= FM1_APP_FX_SLOTS) return unit;          /* sound 0, M1, M2 */
  if (unit_sound(unit) > 0) return (int)fm1_mod_sound_unit((unsigned)unit_sound(unit));
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      if (fm1_app_insert_unit(k, j) == unit) return (int)fm1_mod_insert_unit((unsigned)k, (unsigned)j);
    }
  }
  return -1;
}

/* The app unit a sink's code names (the inverse of fm1_app_mod_unit), or
 * -1 (HOST, a module, nothing). */
static int app_unit_of(unsigned code) {
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (fm1_app_mod_unit(u) == (int)fm1_mod_unit_canonical(code)) return u;
  }
  return -1;
}

/* Every sink's engine, by sink index (fm1_mod_sink_unit's order). */
static void mod_units(const fm1_app_t *a, const fm1_engine_t **units) {
  for (unsigned i = 0; i < FM1_MOD_SINKS; ++i) {
    const int u = app_unit_of(fm1_mod_sink_unit(i));
    units[i] = u >= 0 ? a->unit[u].e : NULL;
  }
}

/* Each edit to the harness's log, with the frame of the block it leads. */
static void mod_emit(void *ctx, const char *line) {
  fm1_app_t *a = (fm1_app_t *)ctx;
  if (a->on_mod) a->on_mod(a->on_mod_ctx, a->frames, line);
}

static void mod_env(fm1_app_t *a, fm1_mod_ui_env_t *env) {
  env->m = a->mod;
  env->rate = a->host.sample_rate;
  env->sound = (uint8_t)a->sound;
  mod_units(a, env->unit);
  env->emit = a->on_mod ? mod_emit : NULL;
  env->ctx = a;
}

/* The glue's writes to the effects and AMP, rendered after the sounds. */
static void mod_write(void *ctx, uint32_t frame, const fm1_mod_write_t *w) {
  fm1_app_t *a = (fm1_app_t *)ctx;
  if (a->mod_nwr < FM1_APP_MOD_WRITES) {
    a->mod_wr[a->mod_nwr].frame = frame;
    a->mod_wr[a->mod_nwr].w = *w;
    ++a->mod_nwr;
  }
}

/* Binds a unit's engine (or none) as the runtime's sink for it, its knobs'
 * values as bases: what the engine holds. */
static void mod_bind(fm1_app_t *a, int unit) {
  const fm1_app_unit_t *u = &a->unit[unit];
  const int code = fm1_app_mod_unit(unit);
  if (!a->mod || code < 0) return;
  fm1_mod_bind(a->mod, (unsigned)code, u->e);
  for (uint16_t i = 0; u->e && i < u->e->n_params; ++i) {
    fm1_mod_set_base(a->mod, (unsigned)code, i, u->value[i]);
  }
  if (code == FM1_MOD_SOUND) a->mod_glue.sound = u->e;
}

/* The runtime goes; every parameter it moved goes back to its base, so a
 * runtime that follows (or none) starts from what the knobs say. */
static void mod_release(fm1_app_t *a) {
  if (!a->mod) return;
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    const fm1_app_unit_t *x = &a->unit[u];
    const int code = fm1_app_mod_unit(u);
    for (uint16_t i = 0; code >= 0 && x->e && i < x->e->n_params && i < FM1_MOD_UNIT_PARAMS; ++i) {
      if (fm1_mod_sent(a->mod, (unsigned)code, i) != x->value[i]) x->e->set_param(x->self, i, x->value[i]);
    }
  }
  if (a->unit[0].e && a->unit[0].e->pitch_bend &&
      fm1_mod_sent(a->mod, FM1_MOD_HOST, FM1_MOD_HOST_PITCH) != a->bend) {
    a->unit[0].e->pitch_bend(a->unit[0].self, a->bend);
  }
  fm1_mod_destroy(a->mod);
  a->mod = NULL;
}

/* A new runtime with `seed`, bound to the chain; with `deflt`, the default
 * rack and its cables (fm1_app_init's). */
static void mod_start(fm1_app_t *a, uint32_t seed, int deflt) {
  mod_release(a);                      /* a script's reset after the default runtime ran */
  if (fm1_mod_size() > sizeof a->mod_mem) return;
  a->mod = fm1_mod_create(a->mod_mem, &a->host, seed);
  if (!a->mod) return;
  a->mod_seed = seed;
  fm1_mod_glue_init(&a->mod_glue, a->mod, a->unit[0].e);
  a->mod_glue.ctx = a;
  a->mod_glue.write = mod_write;
  for (int u = 0; u < FM1_APP_UNITS; ++u) mod_bind(a, u);
  fm1_mod_set_base(a->mod, FM1_MOD_HOST, FM1_MOD_HOST_PITCH, a->bend);
  fm1_mod_ramp_init(&a->mod_amp, 1.0f);
  a->mod_amp_used = 0;
  a->mod_nwr = 0;
  fm1_mod_ui_init(&a->mui);
  if (deflt) {
    fm1_mod_ui_env_t env;
    mod_env(a, &env);
    env.emit = NULL;                    /* a log starts from the dump */
    fm1_mod_ui_default(&env, &a->mui);
  }
  a->dirty = 1;
  a->leds_changed = 1;
}

static int is_mod_mode(int mode) {
  return mode == FM1_MODE_RACK || mode == FM1_MODE_MATRIX || mode == FM1_MODE_CHAIN;
}

void fm1_app_mod_reset(fm1_app_t *a, uint32_t seed) { mod_start(a, seed, 0); }

int fm1_app_mod_line(fm1_app_t *a, const char *line, char *err, size_t cap) {
  const fm1_engine_t *units[FM1_MOD_SINKS];
  uint32_t seed;
  if (!a->mod) {
    if (err && cap) snprintf(err, cap, "no modulation runtime");
    return 0;
  }
  mod_units(a, units);
  if (!fm1_mod_script_apply(a->mod, line, units, err, cap)) return 0;
  if (!fm1_mod_script_seed(line, &seed)) {     /* a seed only counts at creation */
    while (*line == ' ' || *line == '\t') ++line;
    if (*line && *line != '#') mod_emit(a, line);
  }
  a->dirty = 1;
  return 1;
}

int fm1_app_mod_dump(fm1_app_t *a, void (*emit)(void *ctx, const char *line), void *ctx) {
  fm1_mod_ui_env_t env;
  if (!a->mod) return 0;
  mod_env(a, &env);
  env.emit = emit;
  env.ctx = ctx;
  return fm1_mod_ui_dump(&env, a->mod_seed) && !a->mui.unloggable;
}

const fm1_mod_t *fm1_app_mod(const fm1_app_t *a) { return a->mod; }

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

/* A sound unit's notes go (a change of its engine): the keys' and MIDI
 * IN's, then the sequencer's, as fm1_app_all_notes_off releases every
 * sound's. */
static void release_sound(fm1_app_t *a, int sound);

/* The FX mode slot's unit just changed: its page is clamped (an empty slot
 * has one). */
static void fx_unit_changed(fm1_app_t *a, int unit) {
  if (fx_unit_at(a, a->fx_slot) == unit) a->fx_page = clampi(a->fx_page, 0, fx_pages(a, a->fx_slot) - 1);
}

int fm1_app_select(fm1_app_t *a, int unit, int index) {
  if (unit < 0 || unit >= FM1_APP_UNITS) return FM1_APP_SELECT_BAD;
  fm1_app_unit_t *u = &a->unit[unit];
  const fm1_engine_t *e = entry(index);
  const int snd = unit_sound(unit);
  fm1_kind_t want = snd >= 0 ? FM1_KIND_SOUND : FM1_KIND_AUDIO_FX;
  if (index == -1 && unit > 0) {
    if (snd >= 0) release_sound(a, snd);
    release(u);
    mod_bind(a, unit);
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
  {
    /* The RAM meter: refuse what would take the chain past the FM-1's
     * budget, unless it does not grow (a chain already past it, after a
     * larger sequencer, can still shrink). The popup says so whoever asked
     * (the page's menus, fm1_app_unit_*); PRESETS and ALGORITHM, which
     * step past a refusal, put up their own after it. */
    const size_t now = fm1_app_ram(a), with = fm1_app_ram_with(a, unit, index);
    if (with > FM1_APP_RAM_BUDGET && with > now) {
      a->ram_over = with - FM1_APP_RAM_BUDGET;
      refusal_popup(a, index, FM1_APP_SELECT_RAM);
      return FM1_APP_SELECT_RAM;
    }
  }
  int prev = u->index;
  size_t prev_bytes = u->bytes;
  float prev_value[FM1_APP_MAX_PARAMS];
  memcpy(prev_value, u->value, sizeof prev_value);
  if (snd >= 0) release_sound(a, snd);   /* this sound's notes; the others play on */
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
    mod_bind(a, unit);
    a->dirty = 1;
    return -3;
  }
  mod_bind(a, unit);                      /* the runtime's sink follows the unit */
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
  fm1_app_seq_start_routes(a);
  fm1_app_seq_demo(a);
  return r != 0 ? r : f;
}

int fm1_app_seq_start_routes(fm1_app_t *a) {
  int n = 0;
  fm1_seq_info_t info;
  if (!a->seq) return 0;
  fm1_seq_get_info(a->seq, &info);
  for (int t = 1; t < info.tracks; ++t) {
    fm1_seq_track_info_t ti;
    if (!fm1_seq_get_track(a->seq, (uint8_t)t, &ti) || ti.route_kind != FM1_SEQ_ROUTE_MIDI ||
        ti.route_index != t % 16 + 1) {
      continue;                          /* routed already: left as it is */
    }
    n += fm1_app_seq_route(a, t, FM1_SEQ_ROUTE_ENGINE, 0);
  }
  return n;
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
  /* With modulation, the knob moves the base (rule M1) and the engine gets
   * the base plus what the cables add now. */
  if (a->mod && fm1_app_mod_unit(unit) >= 0) {
    value = fm1_mod_set_base(a->mod, (unsigned)fm1_app_mod_unit(unit), (unsigned)index, value);
  }
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
    total += fm1_seq_size(&a->seq_lim) + sizeof a->seq_ev + sizeof a->seq_pend +
             FM1_APP_SEQ_UI_BYTES + sizeof a->click;
  }
  if (sounds > 1) total += (size_t)(sounds - 1) * FM1_APP_MIX_BLOCK_BYTES;
  if (a->mod) total += fm1_mod_size();
  return total;
}

size_t fm1_app_ram(const fm1_app_t *a) { return ram_of(a, -1, 0, 0); }

size_t fm1_app_ram_with(const fm1_app_t *a, int unit, int index) {
  const fm1_engine_t *e = entry(index);
  if (unit < 0 || unit >= FM1_APP_UNITS) return fm1_app_ram(a);
  return ram_of(a, unit, e ? e->instance_size(&a->host) : 0u, e != NULL);
}

/* ---- sound units (multi-sound) ---------------------------------------------------- */

const fm1_engine_t *fm1_app_unit_engine(const fm1_app_t *a, int sound) {
  return sound >= 0 && sound < FM1_APP_SOUNDS ? sound_of_c(a, sound)->e : NULL;
}

int fm1_app_unit_current(const fm1_app_t *a) { return a->sound; }

int fm1_app_unit_set_current(fm1_app_t *a, int sound) {
  if (sound < 0 || sound >= FM1_APP_SOUNDS) return -1;
  if (sound != a->sound) {
    a->sound = sound;
    a->page = clampi(a->page, 0, page_count(cur(a)->e) - 1);
    forget_knob_hint(a);                 /* the hint named the last sound's knob */
    if (a->fx_slot < FX_MIX) a->fx_page = clampi(a->fx_page, 0, fx_pages(a, a->fx_slot) - 1);
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

/* A typed `route t 1 sound`, as the panel's commands go in (the event-room
 * rule, and the harness's --log-cmds), so a gesture that routes a track
 * replays through fm1-render. */
int fm1_app_unit_route(fm1_app_t *a, int track, int sound) {
  fm1_seq_cmd_t c;
  int64_t arg[3];
  if (!a->seq || track < 0 || track > 255 || sound < 0 || sound >= FM1_APP_SOUNDS) {
    return FM1_APP_SEQ_REFUSED;
  }
  arg[0] = track;
  arg[1] = FM1_SEQ_ROUTE_ENGINE;
  arg[2] = sound;
  fm1_seq_cmd_make(&c, FM1_SEQ_V_ROUTE, 3u, arg);
  return fm1_app_seq_cmd(a, &c);
}

int fm1_app_unit_of_track(const fm1_app_t *a, int track) {
  fm1_seq_track_info_t ti;
  if (!a->seq || track < 0 || track > 255 || !fm1_seq_get_track(a->seq, (uint8_t)track, &ti) ||
      ti.route_kind != FM1_SEQ_ROUTE_ENGINE) {
    return -1;
  }
  return ti.route_index < FM1_APP_SOUNDS ? ti.route_index : -1;
}

/* ---- notes -------------------------------------------------------------------- */

/* A note on sound unit `sound`, counted there so it can be released. */
/* With modulation, a note on a sound unit with an engine feeds the
 * runtime's note sources (VEL, KEY, TRIG...), as fm1-render feeds a --note
 * or --sound-note on a loaded unit. */
static void play_on(fm1_app_t *a, int sound, int note, int velocity) {
  fm1_app_unit_t *s = sound_of(a, sound);
  if (s->e && s->e->note_on) s->e->note_on(s->self, (uint8_t)note, (uint8_t)velocity);
  if (a->mod && s->e) fm1_mod_live_note(a->mod, (uint8_t)note, (uint8_t)velocity);
  if (a->note_count[sound][note] < 255) ++a->note_count[sound][note];
}

static void play_off(fm1_app_t *a, int sound, int note) {
  fm1_app_unit_t *s = sound_of(a, sound);
  if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)note);
  if (a->mod && s->e) fm1_mod_live_note(a->mod, (uint8_t)note, 0);
  if (a->note_count[sound][note]) --a->note_count[sound][note];
}

void fm1_app_unit_note_on(fm1_app_t *a, int sound, int note, int velocity) {
  if (sound < 0 || sound >= FM1_APP_SOUNDS || note < 0 || note > 127) return;
  play_on(a, sound, note, clampi(velocity, 1, 127));
}

void fm1_app_unit_note_off(fm1_app_t *a, int sound, int note) {
  if (sound < 0 || sound >= FM1_APP_SOUNDS || note < 0 || note > 127) return;
  play_off(a, sound, note);
}

/* A note played that no step took is live input to the focused track
 * (docs/15 §3.2, S5): recording and Capture hear it. Its release goes to
 * the same track, once per note given. */
static void feed_on(fm1_app_t *a, int note, int velocity) {
  if (a->seq_fed[note] == 255) return;
  ++a->seq_fed[note];
  a->seq_fed_track[note] = a->ui.track;
  fm1_app_seq_note_in(a, a->ui.track, note, velocity);
}

static void feed_off(fm1_app_t *a, int note) {
  if (!a->seq_fed[note]) return;
  --a->seq_fed[note];
  fm1_app_seq_note_in(a, a->seq_fed_track[note], note, 0);
}

/* A note's release seen by the sequencer's UI (step record's head may move
 * on) and by live input, after the sound let it go. */
static void ui_note_off(fm1_app_t *a, int note) {
  if (a->seq) {
    const fm1_seq_ui_emit_t out = ui_out(a);
    fm1_seq_ui_note(&a->ui, note, 0, a->mode, &out);
    ui_after(a);
  }
  feed_off(a, note);
}

void fm1_app_note_on(fm1_app_t *a, int note, int velocity) {
  if (note < 0 || note > 127) return;
  velocity = clampi(velocity, 1, 127);
  play_on(a, a->sound, note, velocity);
  if (a->seq) {                     /* the chord a step tap writes, a held step's pitch, */
    const fm1_seq_ui_emit_t out = ui_out(a);   /* step record's, or live input */
    const int edit = fm1_seq_ui_note(&a->ui, note, velocity, a->mode, &out);
    ui_after(a);
    if (!edit) feed_on(a, note, velocity);
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
  ui_note_off(a, note);
}

void fm1_app_pitch_bend(fm1_app_t *a, float semitones) {
  if (!(semitones == semitones)) return;
  if (semitones > 48.0f) semitones = 48.0f;
  if (semitones < -48.0f) semitones = -48.0f;
  fm1_app_unit_t *s = cur(a);
  if (a->sound == 0) {
    /* With modulation sound 0's bend is HOST PITCH's base (fm1_mod_host.h),
     * as fm1-render's --bend is. */
    a->bend = semitones;
    if (a->mod) semitones = fm1_mod_set_base(a->mod, FM1_MOD_HOST, FM1_MOD_HOST_PITCH, semitones);
  }
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
      if (a->mod && s->e) fm1_mod_live_note(a->mod, (uint8_t)n, 0);   /* no event will say it */
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
      if (a->mod && s->e) fm1_mod_live_note(a->mod, (uint8_t)n, 0);
      --a->note_count[sound][n];
    }
  }
}

static void release_sound(fm1_app_t *a, int sound) {
  notes_release_sound(a, sound);
  seq_release_sound(a, sound);
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    if (a->key_sound[k] == sound) a->key_down[k] = a->key_sound_only[k] = 0;
  }
  for (int n = 0; n < 128; ++n) {   /* live input let go too (S5: a change of sound */
    while (a->seq_fed[n]) feed_off(a, n);   /* releases every note given) */
  }
  if (sound == a->sound) fm1_seq_ui_notes_off(&a->ui);
}

void fm1_app_all_notes_off(fm1_app_t *a) {
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) notes_release_sound(a, k);
  seq_release(a);
  for (int k = 0; k < FM1_APP_KEYS; ++k) a->key_down[k] = a->key_sound_only[k] = 0;
  for (int n = 0; n < 128; ++n) {   /* live input let go too: no note left open */
    while (a->seq_fed[n]) feed_off(a, n);
  }
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
    int sound_only = 0;
    if (a->key_down[key]) return;
    if (a->seq) {
      /* In SEQ mode the white keys are steps and the black keys roles
       * (owner decision O1): the UI takes them, and they play nothing,
       * except in step record, where a white key enters its pitch and
       * sounds it (only on the sound: it is no live input). */
      const fm1_seq_ui_emit_t out = ui_out(a);
      const int took = fm1_seq_ui_key(&a->ui, a->seq, key, 1, velocity, a->frames, a->mode,
                                       key_note(a, key), &out);
      if (took) {
        ui_after(a);
        if (took != FM1_SEQ_UI_KEY_SOUND) return;
        sound_only = 1;
      }
      if (a->ui.full_vel) velocity = 127;    /* SHIFT + 10: full velocity */
    }
    int note = key_note(a, key);
    if (note < 0 || note > 127) return;
    a->key_down[key] = 1;
    a->key_note[key] = (uint8_t)note;
    a->key_vel[key] = (uint8_t)clampi(velocity, 1, 127);
    a->key_sound[key] = (uint8_t)a->sound;          /* its release goes there too */
    a->key_sound_only[key] = (uint8_t)sound_only;
    if (sound_only) play_on(a, a->sound, note, a->key_vel[key]);
    else fm1_app_note_on(a, note, velocity);
    return;
  }
  if (a->key_down[key]) {
    a->key_down[key] = 0;
    play_off(a, a->key_sound[key], a->key_note[key]);
    if (!a->key_sound_only[key]) ui_note_off(a, a->key_note[key]);
    a->key_sound_only[key] = 0;
  }
  if (fm1_seq_ui_has_key(&a->ui, key)) {   /* a step's or step record's release, in any mode */
    const fm1_seq_ui_emit_t out = ui_out(a);
    fm1_seq_ui_key(&a->ui, a->seq, key, 0, 0, a->frames, a->mode, key_note(a, key), &out);
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

/* ---- modulation on the panel (fm1_mod_ui.h) ------------------------------------ */

static int say_entry(const fm1_app_t *a, const void *ctx, int k, char *buf, size_t size) {
  const fm1_mod_ui_say_t *s = (const fm1_mod_ui_say_t *)ctx;
  const int r = k - s->first;            /* the same window: fm1_list_first both times */
  (void)a;
  snprintf(buf, size, "%s", r >= 0 && r < s->n ? s->line[r] : "");
  return r >= 0 && r < s->n && ((s->dim >> r) & 1u);
}

static void say(fm1_app_t *a, const fm1_mod_ui_say_t *s) {
  if (s->n > 0 && s->total > 0) {        /* a picker's list: the window it chose */
    list_popup(a, s->title, s->total, s->first + s->mark, say_entry, s);
  } else if (s->n > 0) {
    popup(a, s->line[0], s->n > 1 ? s->line[1] : NULL, s->n > 2 ? s->line[2] : NULL, s->mark);
  }
}

/* Units ua and ub swapped places (SEL and SELECT in FX mode): their cables
 * go with them (not replayable: fm1-render's effects do not move). */
static void mod_swap_units(fm1_app_t *a, int ua, int ub) {
  const int ca = fm1_app_mod_unit(ua), cb = fm1_app_mod_unit(ub);
  if (!a->mod || ca < 0 || cb < 0) return;
  for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    fm1_mod_get_slot(a->mod, i, &s);
    if (s.dst_unit == ca || s.dst_unit == cb) {
      s.dst_unit = (uint8_t)(s.dst_unit == ca ? cb : ca);
      fm1_mod_set_slot(a->mod, i, &s);
    }
  }
  mod_bind(a, ua);
  mod_bind(a, ub);
  a->mui.unloggable = 1;
}

/* A waiting picker's choice, now; its popup goes with it. */
static void mod_commit(fm1_app_t *a) {
  fm1_mod_ui_env_t env;
  if (!a->mod || !a->mui.picker) return;
  mod_env(a, &env);
  fm1_mod_ui_commit(&env, &a->mui);
  a->popup_lines = 0;
  a->dirty = 1;
}

static int kind_of_button(int button) {
  return fm1_mod_kind_find(button == FM1_BTN_LFO ? "lfo" : "env");
}

/* ENV and LFO: a tap opens RACK at that kind; held, the knobs make cables
 * (mod_gesture). EDIT: MATRIX, or back to HOME. SEL: CHAIN from MATRIX and
 * back; in RACK it grabs the module (docs/16 §5.2: SEL keeps its FX-style
 * role on these pages; everywhere else but FX mode it is SHIFT, and the
 * sequencer's UI never sees its press here). 1 when the edge was
 * modulation's. */
static int mod_button(fm1_app_t *a, int button, int down) {
  fm1_mod_ui_t *u = &a->mui;
  if (down) mod_commit(a);                /* any press settles a waiting picker */
  if (down && u->held != FM1_MOD_UI_NONE && button != u->held) {
    u->held_used = 1;                     /* a held ENV or LFO with another press is no tap */
  }
  switch (button) {
    case FM1_BTN_ENV:
    case FM1_BTN_LFO:
      if (down) {
        u->held = (uint8_t)button;
        u->held_used = 0;
      } else if (u->held == button) {
        const int other = button == FM1_BTN_ENV ? FM1_BTN_LFO : FM1_BTN_ENV;
        if (!u->held_used) {              /* a tap */
          if (!fm1_mod_ui_open_rack(u, a->mod, kind_of_button(button), a->mode == FM1_MODE_RACK)) {
            popup(a, button == FM1_BTN_LFO ? "No LFO" : "No envelope", "in the rack", NULL, -1);
          }
          set_mode(a, FM1_MODE_RACK);
          a->fx_grab = 0;
          a->dirty = 1;
        }
        /* The other one, still held, had a press during its hold: no tap. */
        u->held = a->button_down[other] ? (uint8_t)other : (uint8_t)FM1_MOD_UI_NONE;
        u->held_used = u->held != FM1_MOD_UI_NONE;
      }
      return 1;
    case FM1_BTN_EDIT:
      if (down) {
        set_mode(a, a->mode == FM1_MODE_MATRIX || a->mode == FM1_MODE_CHAIN ? FM1_MODE_HOME
                                                                            : FM1_MODE_MATRIX);
        a->fx_grab = 0;
        u->grab = 0;
        a->dirty = 1;
      }
      return 1;
    case FM1_BTN_SEL:
      if (!down) return 0;
      if (a->mode == FM1_MODE_MATRIX || a->mode == FM1_MODE_CHAIN) {
        a->mode = a->mode == FM1_MODE_MATRIX ? FM1_MODE_CHAIN : FM1_MODE_MATRIX;
      } else if (a->mode == FM1_MODE_RACK) {
        u->grab = fm1_mod_kind_at(a->mod, u->pos) >= 0 ? !u->grab : 0;
      } else {
        return 0;
      }
      a->dirty = 1;
      return 1;
    case FM1_BTN_HOME:
    case FM1_BTN_FX:
    case FM1_BTN_GLO:
    case FM1_BTN_SEQ:
      if (down) u->grab = 0;              /* leaving RACK lets go */
      return 0;
    default:
      return 0;
  }
}

/* Hold ENV or LFO and turn KNOB1-4 on HOME, FX or RACK: a cable from the
 * selected Envelope or LFO to that knob's parameter (docs/16's quick
 * assign), its amount following the turn. On HOME the parameter is the
 * current sound's; in FX mode, the slot's effect's. */
static void mod_gesture(fm1_app_t *a, const fm1_mod_ui_env_t *env, int knob, int delta,
                        fm1_mod_ui_say_t *out) {
  fm1_mod_ui_t *u = &a->mui;
  const int src = fm1_mod_ui_selected(u, a->mod, kind_of_button(u->held));
  int idx[4], n;
  fm1_mod_dest_t d;
  memset(&d, 0, sizeof d);
  if (a->mode == FM1_MODE_RACK) {
    const int k = fm1_mod_kind_at(a->mod, u->pos);
    n = fm1_mod_ui_rack_params(a->mod, u->pos, u->page, idx);
    if (k < 0 || knob >= n) return;
    d.unit = (uint8_t)(FM1_MOD_MODULE + u->pos);
    d.dst = fm1_mod_kinds[k]->params[idx[knob]].uid;
  } else {
    const int unit = a->mode == FM1_MODE_FX ? fx_unit_at(a, a->fx_slot) : fm1_app_sound_unit(a->sound);
    const int code = unit >= 0 ? fm1_app_mod_unit(unit) : -1;
    const fm1_engine_t *e = unit >= 0 ? a->unit[unit].e : NULL;
    n = page_params(e, a->mode == FM1_MODE_FX ? a->fx_page : a->page, idx);
    if (!e || code < 0 || knob >= n || idx[knob] >= (int)FM1_MOD_UNIT_PARAMS) return;
    d.unit = (uint8_t)code;
    d.dst = e->params[idx[knob]].uid;
  }
  d.index = (int16_t)idx[knob];
  if (src < 0) {
    out->n = 2;
    out->mark = -1;
    snprintf(out->line[0], sizeof out->line[0], "%s", u->held == FM1_BTN_LFO ? "No LFO" : "No envelope");
    snprintf(out->line[1], sizeof out->line[1], "in the rack");
    return;
  }
  fm1_mod_ui_route(env, u, (unsigned)src, &d, delta, out);
}

/* The modulation pages' encoders, and the gesture. 1 when the turn was
 * modulation's; PRESETS (with SHIFT, the current sound) and OCT +
 * ALGORITHM stay what they are everywhere. */
static int mod_encoder(fm1_app_t *a, int encoder, int delta) {
  fm1_mod_ui_t *u = &a->mui;
  fm1_mod_ui_env_t env;
  fm1_mod_ui_say_t out;
  const int knob = encoder >= FM1_ENC_KNOB1 ? encoder - FM1_ENC_KNOB1 : -1;
  const int oct = a->button_down[FM1_BTN_OCT_DOWN] || a->button_down[FM1_BTN_OCT_UP];
  const int algo = encoder == FM1_ENC_ALGORITHM && !oct;
  out.n = 0;
  out.mark = -1;
  out.total = 0;                         /* a message, unless a picker says a list */
  mod_env(a, &env);
  /* A waiting picker goes on with its own control; anything else settles it. */
  if (u->picker &&
      !((u->picker == FM1_MOD_PICK_KIND && a->mode == FM1_MODE_RACK && algo) ||
        (u->picker == FM1_MOD_PICK_DEST && a->mode == FM1_MODE_MATRIX &&
         (algo || (knob == 1 && u->mpage == 0))))) {
    mod_commit(a);
  }
  /* Any turn while ENV or LFO is held makes the hold no tap, so letting go
   * does not open RACK (a knob in SEQ mode or MATRIX, SELECT, PRESETS). */
  if (u->held != FM1_MOD_UI_NONE) u->held_used = 1;
  if (knob >= 0 && u->held != FM1_MOD_UI_NONE &&
      (a->mode == FM1_MODE_HOME || a->mode == FM1_MODE_FX || a->mode == FM1_MODE_RACK)) {
    mod_gesture(a, &env, knob, delta, &out);
  } else if (a->mode == FM1_MODE_RACK) {
    if (encoder == FM1_ENC_SELECT) fm1_mod_ui_rack_select(&env, u, delta);
    else if (algo) fm1_mod_ui_rack_algorithm(&env, u, delta, &out);
    else if (knob >= 0) fm1_mod_ui_rack_knob(&env, u, knob, delta);
    else return 0;
  } else if (a->mode == FM1_MODE_MATRIX) {
    if (encoder == FM1_ENC_SELECT) fm1_mod_ui_matrix_select(u, delta);
    else if (algo) fm1_mod_ui_matrix_algorithm(&env, u, delta, &out);
    else if (knob >= 0) {
      fm1_mod_ui_matrix_knob(&env, u, knob, delta,
                             a->frames + (uint64_t)(2.0f * a->host.sample_rate), &out);
    } else {
      return 0;
    }
  } else if (a->mode == FM1_MODE_CHAIN) {
    if (encoder == FM1_ENC_SELECT) fm1_mod_ui_chain_select(&env, u, delta);
    else if (!(knob >= 0 || algo)) return 0;     /* nothing to turn here */
  } else {
    return 0;
  }
  say(a, &out);
  a->dirty = 1;
  return 1;
}

void fm1_app_button(fm1_app_t *a, int button, int down) {
  if (button < 0 || button >= FM1_APP_BUTTONS) return;
  int was = a->button_down[button];
  a->button_down[button] = (uint8_t)(down != 0);
  const int mod_sel = button == FM1_BTN_SEL && down && a->mod && is_mod_mode(a->mode);
  if (a->seq && (down != 0) != (was != 0) && !mod_sel) {
    /* Every edge goes to the sequencer's UI first (but SEL pressed on a
     * modulation page, which keeps its FX-style role there: mod_button); what it sends goes in
     * as typed commands, under the event-room rule (a second command while
     * one is held is refused and counted in seq_busy). An edge it takes
     * (SEL as SHIFT, OCT on held steps) goes no further. An OCT press it
     * took transposed the held steps, so the app does not count it as
     * held either: ALGORITHM keeps turning the model rather than the
     * keys' transpose, and the other OCT moves the octave rather than
     * resetting it. SEL and REC stay held, as SHIFT and step record need
     * their releases. */
    const fm1_seq_ui_emit_t out = ui_out(a);
    const int took = fm1_seq_ui_button(&a->ui, a->seq, button, down != 0, a->frames, a->mode,
                                       &out);
    ui_after(a);
    if (took) {
      if (down && button != FM1_BTN_SEL && button != FM1_BTN_REC) a->button_down[button] = 0;
      return;
    }
  }
  if (button == FM1_BTN_SEQ && !down && was && a->ui.seq_gestured &&
      a->seq_from_mode != FM1_MODE_SEQ && a->mode == FM1_MODE_SEQ) {
    /* SEQ held to focus a track from another mode: back there (S6). */
    a->ui.seq_gestured = 0;
    set_mode(a, a->seq_from_mode);
    a->dirty = 1;
    a->leds_changed = 1;
    return;
  }
  if (a->mod && (down != 0) != (was != 0) && mod_button(a, button, down != 0)) return;
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
    case FM1_BTN_SEL:                    /* elsewhere SHIFT, the sequencer's UI's */
      if (a->mode == FM1_MODE_FX) {
        a->fx_grab = a->fx_slot == FX_MIX ? 0 : !a->fx_grab;   /* Mix moves nowhere */
        a->dirty = 1;
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
      if (!a->seq) {
        stub_popup(a, button);
        break;
      }
      a->seq_from_mode = a->mode;
      a->mode = FM1_MODE_SEQ;
      a->fx_grab = 0;
      fm1_seq_ui_enter(&a->ui);
      fm1_seq_ui_sync(&a->ui, a->seq, a->seq_gen, a->frames);
      a->dirty = 1;
      break;
    case FM1_BTN_PLAY:                   /* the UI sent `play` or `stop` above */
      if (!a->seq) stub_popup(a, button);
      break;
    default:
      stub_popup(a, button);
      break;
  }
}

/* `delta` detents from v: step_of's step, a whole entry for a list, and for
 * a LOG parameter (engine API v3) a hundredth of its octaves, so the knob
 * moves by ratios (1.2 semitones a detent on a 20 Hz..18 kHz cutoff) and
 * reaches min and max exactly. */
static float step_value(const fm1_param_t *p, float v, int delta) {
  if (fm1_param_is_log(p)) {
    /* One rounding per statement, so no build fuses a multiply-add here and
     * the browser's module steps to the same bits as fm1-sim-render. */
    const float d = (float)delta * 0.01f;
    float u = fm1_param_pos(p, v);
    u = u + d;
    return fm1_param_at(p, u);
  }
  v = v + (float)delta * step_of(p);
  if (p->type == FM1_PARAM_ENUM) v = floorf(v + 0.5f);
  return fm1_param_clamp(p, v);
}

static void turn_param(fm1_app_t *a, int unit, int index, int delta) {
  const fm1_param_t *p = &a->unit[unit].e->params[index];
  fm1_app_set_param(a, unit, index, step_value(p, a->unit[unit].value[index], delta));
}

/* The lanes on parameter `index` of sound unit `sound`: every lane, of every
 * track that plays the sound, whose label names it. With
 * `sync`, each takes the knob's 7-bit value as its base, quietly (`abaseq`,
 * Movy's base sync, sent at once rather than at a knob's release), so no
 * stale base snaps the parameter back at the next note (R8) and a stop's D6
 * revert sends the engine exactly value[]; the knob is put on the grid
 * first if a script left it off. Returns how many there are. */
static int sound_lanes(fm1_app_t *a, int sound, int index, int sync) {
  fm1_seq_info_t info;
  fm1_app_unit_t *u = sound_of(a, sound);
  const fm1_param_t *p;
  unsigned v7;
  int n = 0;
  if (!a->seq || !u->e || index < 0 || index >= u->e->n_params) return 0;
  p = &u->e->params[index];
  v7 = fm1_seq_value7(p, u->value[index]);
  fm1_seq_get_info(a->seq, &info);
  for (int t = 0; t < info.tracks; ++t) {
    fm1_seq_track_info_t ti;
    if (fm1_app_unit_of_track(a, t) != sound || !fm1_seq_get_track(a->seq, (uint8_t)t, &ti)) continue;
    for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) {
      const char *label = fm1_seq_lane_label(a->seq, (uint8_t)t, (uint8_t)lane);
      if (!((ti.lanes_assigned >> lane) & 1u) || !label[0] || fm1_seq_lane_param(u->e, label) != index) {
        continue;
      }
      if (sync && !n) {
        const float on_grid = fm1_seq_lock_value(p, v7);
        if (on_grid != u->value[index]) fm1_app_set_param(a, fm1_app_sound_unit(sound), index, on_grid);
      }
      ++n;
      if (sync && ti.base[lane] != v7) {
        fm1_seq_cmd_t c;
        const int64_t arg[3] = { t, lane, v7 };
        fm1_seq_cmd_make(&c, FM1_SEQ_V_ABASEQ, 3u, arg);
        fm1_app_seq_cmd(a, &c);
      }
    }
  }
  return n;
}

/* A knob detent (or ALGORITHM's) on sound unit `sound`'s parameter. A
 * parameter with a lane turns on its 7-bit grid, one step a
 * detent (owner decision O14: v/127 of the range, or one list entry), so the
 * engine plays the value the lanes' bases give, and the bases follow. */
static void turn_sound(fm1_app_t *a, int sound, int index, int delta) {
  const int unit = fm1_app_sound_unit(sound);
  const fm1_param_t *p = &a->unit[unit].e->params[index];
  if (p->type == FM1_PARAM_FLOAT && sound_lanes(a, sound, index, 0)) {
    const unsigned v = fm1_seq_value7_step(p, fm1_seq_value7(p, a->unit[unit].value[index]), delta);
    fm1_app_set_param(a, unit, index, fm1_seq_lock_value(p, v));
  } else {
    turn_param(a, unit, index, delta);
  }
  sound_lanes(a, sound, index, 1);
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

/* ALGORITHM's list: entry k of an ENUM parameter, by name. */
static int enum_entry(const fm1_app_t *a, const void *ctx, int k, char *buf, size_t size) {
  const fm1_param_t *p = (const fm1_param_t *)ctx;
  (void)a;
  fm1_look_value(p, p->min + (float)k, buf, size);
  return 0;
}

/* The list PRESETS (`kind` sound) or ALGORITHM in FX mode (an effect)
 * turns through, in the order next_preset and next_fx step: Empty first
 * when the unit may be empty, then every registry entry of that kind. */
typedef struct kind_list {
  fm1_kind_t kind;
  int empty_ok;
  const char *empty;                     /* Empty's name in the list */
} kind_list_t;

static int kind_list_count(const kind_list_t *l) {
  int n = l->empty_ok;
  for (size_t i = 0; i < fm1_engine_count; ++i) n += fm1_engines[i]->kind == l->kind;
  return n;
}

/* The list's entry k: a registry index, or -1 for Empty. */
static int kind_list_at(const kind_list_t *l, int k) {
  if (l->empty_ok && k-- == 0) return -1;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind == l->kind && k-- == 0) return (int)i;
  }
  return -1;
}

/* Where registry entry `index` (-1: Empty) is in the list. */
static int kind_list_pos(const kind_list_t *l, int index) {
  const int n = kind_list_count(l);
  for (int k = 0; k < n; ++k) {
    if (kind_list_at(l, k) == index) return k;
  }
  return 0;
}

static int kind_list_entry(const fm1_app_t *a, const void *ctx, int k, char *buf, size_t size) {
  const kind_list_t *l = (const kind_list_t *)ctx;
  const int index = kind_list_at(l, k);
  (void)a;
  snprintf(buf, size, "%s", index < 0 ? l->empty : entry_name(index));
  return index < 0;                      /* Empty, dim */
}

/* PRESETS: the engines, the current sound's highlighted. */
static void preset_popup(fm1_app_t *a) {
  const kind_list_t l = { FM1_KIND_SOUND, sound_empty_ok(a), "Empty" };
  if (cur(a)->index < 0 && !l.empty_ok) return;
  list_popup(a, "Engine", kind_list_count(&l), kind_list_pos(&l, cur(a)->index), kind_list_entry,
             &l);
}

static int sound_entry(const fm1_app_t *a, const void *ctx, int k, char *buf, size_t size) {
  const fm1_engine_t *e = sound_of_c(a, k)->e;
  (void)ctx;
  snprintf(buf, size, "S%d %s", k + 1, e ? e->name : "Empty");
  return e == NULL;
}

/* SHIFT + PRESETS: the four sounds and what each holds, the current one
 * highlighted. */
static void sound_popup(fm1_app_t *a) {
  list_popup(a, "Sound", FM1_APP_SOUNDS, a->sound, sound_entry, NULL);
}

/* FX mode walks (slot, page) pairs: In1's pages, then In2's, Mix, M1's and
 * M2's. */
static void fx_step(fm1_app_t *a, int delta) {
  while (delta) {
    int dir = delta > 0 ? 1 : -1;
    int pages = fx_pages(a, a->fx_slot);
    int page = a->fx_page + dir;
    if (page >= 0 && page < pages) {
      a->fx_page = page;
    } else if (a->fx_slot + dir >= 0 && a->fx_slot + dir < FX_SLOT_COUNT) {
      a->fx_slot += dir;
      a->fx_page = dir > 0 ? 0 : fx_pages(a, a->fx_slot) - 1;
    }
    delta -= dir;
  }
}

/* SEL then SELECT in FX mode: the slot swaps with its neighbour in its own
 * group (the two inserts, or the two master slots), arenas and all. */
static void fx_swap(fm1_app_t *a, int delta) {
  if (a->fx_slot == FX_MIX) return;
  const int lo = a->fx_slot < FX_MIX ? FX_IN1 : FX_M1;
  const int hi = a->fx_slot < FX_MIX ? FX_IN2 : FX_M2;
  const int to = clampi(a->fx_slot + (delta > 0 ? 1 : -1), lo, hi);
  if (to != a->fx_slot) {
    const int ua = fx_unit_at(a, a->fx_slot), ub = fx_unit_at(a, to);
    fm1_app_unit_t t = a->unit[ub];
    a->unit[ub] = a->unit[ua];
    a->unit[ua] = t;
    a->fx_slot = to;
    a->fx_page = 0;
    mod_swap_units(a, ua, ub);
  }
}

/* ALGORITHM in FX mode: the slot's effect, stepping over a choice the RAM
 * meter (or anything else) refuses, as PRESETS does, so every effect past
 * it stays reachable; the popup names the first one refused and why. */
static void fx_choose(fm1_app_t *a, int unit, int delta) {
  const int dir = delta > 0 ? 1 : -1;
  int to = a->unit[unit].index, refused = -1, code = 0, r = -1;
  size_t over = 0;
  for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_fx(to, dir);
  for (int tries = 0; tries <= (int)fm1_engine_count; ++tries) {
    r = fm1_app_select(a, unit, to);
    if (r == 0) break;
    if (refused < 0) refused = to, code = r, over = a->ram_over;
    to = next_fx(to, dir);
    if (to == a->unit[unit].index) break;
  }
  a->fx_page = 0;
  a->ram_over = over;                    /* the popup's figure is the first refusal's */
  if (refused >= 0) {
    refusal_popup(a, refused, code);
  } else {                               /* the effects, the slot's highlighted */
    const kind_list_t l = { FM1_KIND_AUDIO_FX, 1, "Empty slot" };
    char title[24];
    snprintf(title, sizeof title, "%s effect", kFxTags[a->fx_slot]);
    list_popup(a, title, kind_list_count(&l), kind_list_pos(&l, a->unit[unit].index),
               kind_list_entry, &l);
  }
}

void fm1_app_encoder(fm1_app_t *a, int encoder, int delta) {
  if (encoder < 0 || encoder >= FM1_ENC_COUNT || delta == 0) return;
  delta = clampi(delta, -64, 64);
  if (a->mod && mod_encoder(a, encoder, delta)) return;
  if (a->seq) {                         /* with steps held: the Step and lock pages */
    const fm1_seq_ui_emit_t out = ui_out(a);
    fm1_seq_ui_sound_t snd;
    int took;
    lock_sound(a, &snd);
    took = fm1_seq_ui_encoder(&a->ui, a->seq, encoder, delta, a->frames, a->mode, &snd, &out);
    if (took) {
      ui_after(a);
      return;
    }
  }
  const int snd_unit = fm1_app_sound_unit(a->sound);   /* the current sound */
  switch (encoder) {
    case FM1_ENC_SELECT:
      if (a->mode == FM1_MODE_SEQ && a->page + delta >= page_count(cur(a)->e)) {
        /* Past the sound's last page: the Set page (S6, O21), then Clip
         * and Track (fm1_seq_ui.h). */
        a->page = page_count(cur(a)->e) - 1;
        fm1_seq_ui_open(&a->ui, FM1_SEQ_VIEW_SET);
        forget_knob_hint(a);
      } else if (a->mode == FM1_MODE_HOME || a->mode == FM1_MODE_SEQ) {
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
      if (a->ui.shift) {                 /* SHIFT + PRESETS: the current sound (§3.16) */
        a->ui.shift_clean = 0;
        fm1_app_unit_set_current(a, clampi(a->sound + delta, 0, FM1_APP_SOUNDS - 1));
        sound_popup(a);
        break;
      }
      const int empty_ok = sound_empty_ok(a);
      int cur_index = cur(a)->index < 0 && !empty_ok ? 0 : cur(a)->index;
      int dir = delta > 0 ? 1 : -1;
      int to = cur_index, refused = -1, code = 0;
      size_t over = 0;
      for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_preset(a, to, dir);
      /* A sound this host cannot run (or one that would not fit the
       * RAM) is stepped over, so every other one stays
       * reachable; the popup names the first one skipped, and by how much
       * it would pass the budget (a later refusal's figure is another
       * sound's). */
      for (int tries = 0; tries < (int)fm1_engine_count + empty_ok && to != cur(a)->index; ++tries) {
        int r = fm1_app_select(a, snd_unit, to);
        if (r == 0) break;
        if (refused < 0) refused = to, code = r, over = a->ram_over;
        to = next_preset(a, to, dir);
      }
      a->ram_over = over;
      if (refused >= 0) refusal_popup(a, refused, code);
      else preset_popup(a);
      break;
    }
    case FM1_ENC_ALGORITHM:
      if (a->button_down[FM1_BTN_OCT_DOWN] || a->button_down[FM1_BTN_OCT_UP]) {
        a->transpose = clampi(a->transpose + delta, -12, 12);
        show_signed(a, "Transpose", a->transpose);
      } else if (a->mode == FM1_MODE_FX) {
        const int unit = fx_unit_at(a, a->fx_slot);
        if (unit >= 0) fx_choose(a, unit, delta);   /* the Mix page has no effect */
      } else if (cur(a)->e) {
        int m = model_param(cur(a)->e);
        if (m >= 0) {                    /* its list, the entry it is on highlighted */
          const fm1_param_t *p = &cur(a)->e->params[m];
          turn_sound(a, a->sound, m, delta);   /* its lanes' bases follow (S8) */
          list_popup(a, p->name, (int)(p->max - p->min) + 1, enum_index(p, cur(a)->value[m]),
                     enum_entry, p);
        }
      }
      break;
    default: {
      int knob = encoder - FM1_ENC_KNOB1;
      int unit = a->mode == FM1_MODE_FX ? fx_unit_at(a, a->fx_slot) : snd_unit;
      int page = a->mode == FM1_MODE_FX ? a->fx_page : a->page;
      int sound = a->mode == FM1_MODE_FX ? -1 : a->sound;   /* the sound unit turned, if any */
      int several = 0;
      int idx[4];
      fm1_seq_ui_sound_t snd;
      if (a->mode == FM1_MODE_GLOBAL) break;
      if (a->mode == FM1_MODE_FX && unit < 0) {   /* the Mix page: KNOBn is sound n's level */
        fm1_app_unit_set_level(a, knob, a->level[knob] + (float)delta);
        break;
      }
      if (a->seq && a->mode == FM1_MODE_SEQ && a->ui.held_n > 1 &&
          a->ui.view == FM1_SEQ_VIEW_STEP && a->ui.step_page >= FM1_SEQ_UI_STEP_PAGES) {
        /* Several steps held on a lock page (S8): the lock sound's page
         * edits the sound, with no lock. */
        sound = lock_sound(a, &snd);
        if (sound < 0) break;
        unit = fm1_app_sound_unit(sound);
        page = a->ui.step_page - FM1_SEQ_UI_STEP_PAGES;
        several = 1;
      }
      if (unit < 0 || !a->unit[unit].e) break;
      if (knob < page_params(a->unit[unit].e, page, idx)) {
        if (a->seq && sound >= 0 && !several) {
          /* CLEAR + knob, or a live take of the focused track (S8). */
          const fm1_seq_ui_emit_t out = ui_out(a);
          lock_sound(a, &snd);
          if (fm1_seq_ui_sound_knob(&a->ui, a->seq, &snd, idx[knob], delta, a->frames, &out)) {
            ui_after(a);
            if (a->mode == FM1_MODE_SEQ) {
              fm1_seq_ui_knob(&a->ui, knob, a->frames + (uint64_t)(2.0f * a->host.sample_rate));
            }
            break;
          }
        }
        if (sound >= 0) turn_sound(a, sound, idx[knob], delta);
        else turn_param(a, unit, idx[knob], delta);
        if (a->mode == FM1_MODE_SEQ && !several) {   /* its name and value on the hint line */
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
  for (int k = 0; k < FM1_APP_KEYS; ++k) {
    /* A key lights while the note it plays sounds: with a pad kit as the
     * sound, its pad's (a black key's -1: none). */
    int note = key_note(a, k), sounding = 0;
    for (int s = 0; note >= 0 && note < 128 && s < FM1_APP_SOUNDS; ++s) sounding |= a->note_count[s][note];
    led[k] = (uint8_t)(a->key_down[k] || sounding);
  }
  for (int b = 0; b < FM1_APP_BUTTONS; ++b) led[FM1_APP_KEYS + b] = a->button_down[b];
  led[FM1_APP_KEYS + FM1_BTN_OCT_DOWN] = (uint8_t)octave_led(a, -a->octave);
  led[FM1_APP_KEYS + FM1_BTN_OCT_UP] = (uint8_t)octave_led(a, a->octave);
  led[FM1_APP_KEYS + FM1_BTN_FX] = a->mode == FM1_MODE_FX;
  led[FM1_APP_KEYS + FM1_BTN_SEL] = (uint8_t)((a->mode == FM1_MODE_FX && a->fx_grab) || a->ui.shift);
  led[FM1_APP_KEYS + FM1_BTN_GLO] = a->mode == FM1_MODE_GLOBAL;
  /* SEQ in SEQ mode, PLAY while the transport runs; in SEQ mode the white
   * keys show the bar's steps, the playhead inverted, and the two bar keys
   * their role (sequencer notes light no key outside it: owner decision
   * O6). */
  led[FM1_APP_KEYS + FM1_BTN_SEQ] = a->mode == FM1_MODE_SEQ;
  led[FM1_APP_KEYS + FM1_BTN_PLAY] = a->ui.playing != 0;
  led[FM1_APP_KEYS + FM1_BTN_REC] =
      (uint8_t)fm1_seq_ui_rec_led(&a->ui, a->frames, a->button_down[FM1_BTN_REC]);
  if (a->mode == FM1_MODE_SEQ) {
    const uint32_t keys = fm1_seq_ui_key_leds(&a->ui, a->frames);
    for (int k = 0; k < FM1_APP_KEYS; ++k) led[k] = (uint8_t)(a->key_down[k] || ((keys >> k) & 1u));
  }
  if (a->mod) {
    /* LFO or ENV while RACK shows one of theirs, EDIT in MATRIX and CHAIN,
     * SEL in CHAIN and while RACK has a module grabbed. */
    const int k = a->mode == FM1_MODE_RACK ? fm1_mod_kind_at(a->mod, a->mui.pos) : -1;
    led[FM1_APP_KEYS + FM1_BTN_LFO] |= (uint8_t)(k >= 0 && k == kind_of_button(FM1_BTN_LFO));
    led[FM1_APP_KEYS + FM1_BTN_ENV] |= (uint8_t)(k >= 0 && k == kind_of_button(FM1_BTN_ENV));
    led[FM1_APP_KEYS + FM1_BTN_EDIT] |= (uint8_t)(a->mode == FM1_MODE_MATRIX || a->mode == FM1_MODE_CHAIN);
    led[FM1_APP_KEYS + FM1_BTN_SEL] |=
        (uint8_t)(a->mode == FM1_MODE_CHAIN || (a->mode == FM1_MODE_RACK && a->mui.grab));
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

/* HOST PITCH's writes (modulation): the sound unit's bend. */
static void sink_bend(void *ctx, float semitones) {
  const fm1_app_sink_ctx_t *c = (const fm1_app_sink_ctx_t *)ctx;
  const fm1_app_unit_t *u = sound_of(c->a, c->sound);
  if (u->e->pitch_bend) u->e->pitch_bend(u->self, semitones);
}

/* An effect over the block, split at its own writes from the ticks, as
 * fm1-render's RenderFx does; each piece through fm1_fx_render, which
 * gives an effect with engine API v3's extension the sequencer's tempo,
 * beats, Start and Stop (fm1_fx_host.h; no key yet). */
static void render_fx(fm1_app_t *a, int unit, float *out, uint32_t n) {
  const fm1_app_unit_t *u = &a->unit[unit];
  const int code = fm1_app_mod_unit(unit);
  fm1_fx_block_t b;
  uint32_t cur = 0;
  b.clock = a->seq ? &a->seq_host.clock : NULL;
  b.ev = a->seq ? a->seq_ev : NULL;
  b.n_ev = a->seq ? a->seq_last_n : 0u;
  b.frames = n;
  b.bpm = 120.0f;                       /* without a sequencer: its default */
  for (uint32_t k = 0; code >= 0 && k < a->mod_nwr; ++k) {
    const uint32_t f = a->mod_wr[k].frame;
    const fm1_mod_write_t *w = &a->mod_wr[k].w;
    if (w->unit != code) continue;
    if (f > cur) {
      fm1_fx_render(u->e, u->self, out, cur, f, &b);
      cur = f;
    }
    if (w->index < u->e->n_params) u->e->set_param(u->self, w->index, w->value);
  }
  if (cur < n) fm1_fx_render(u->e, u->self, out, cur, n, &b);
}

/* HOST AMP's gain before the click and the limiter, ramped over each tick
 * on absolute frames (fm1-render's order). */
static void apply_amp(fm1_app_t *a, float *out, uint32_t n) {
  const uint64_t pos = a->frames;
  uint32_t cur = 0;
  for (uint32_t k = 0; k < a->mod_nwr; ++k) {
    const fm1_mod_write_t *w = &a->mod_wr[k].w;
    const uint32_t f = a->mod_wr[k].frame;
    if (w->unit != FM1_MOD_HOST || w->index != FM1_MOD_HOST_AMP) continue;
    if (a->mod_amp_used && f > cur) fm1_mod_ramp_apply(&a->mod_amp, pos + cur, out + 2u * cur, f - cur);
    fm1_mod_ramp_set(&a->mod_amp, pos + f, w->value);
    a->mod_amp_used = 1;
    cur = f;
  }
  if (a->mod_amp_used && cur < n) fm1_mod_ramp_apply(&a->mod_amp, pos + cur, out + 2u * cur, n - cur);
}

/* Every sound unit renders its own block, split at its own tracks' events
 * (fm1_seq_host_dispatch_slots), runs its inserts, is scaled by its level
 * (skipped at 100 %) and summed into `out` in unit order, the first one
 * copied. fm1-render --slots does the same, float for float; with sound 0
 * alone, no insert and level 100 it is fm1-render's one sound to the bit. */
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
    sink[k].pitch_bend = sink_bend;
    slot[k].sink = u->e ? &sink[k] : NULL;
    slot[k].block = a->mix[k];
  }
  if (a->seq) {
    /* With modulation the runtime's ticks run inside the block at their
     * own frames, each sound unit split where a tick writes to it. */
    seq_flush(a);
    a->seq_last_n = fm1_seq_host_advance(&a->seq_host, n);
    fm1_seq_host_dispatch_slots_ticks(&a->seq_host, n, slot, FM1_APP_SOUNDS,
                                      a->mod ? &a->mod_glue.hook : NULL);
  } else {
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      if (slot[k].sink) sound_of(a, k)->e->render(sound_of(a, k)->self, a->mix[k], n);
    }
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    float *b = a->mix[k];
    if (!slot[k].sink) continue;
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      const int iu = fm1_app_insert_unit(k, j);
      if (a->unit[iu].e) render_fx(a, iu, b, n);
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
  a->mod_nwr = 0;
  /* docs/15 §2.4, steps 2-6: what was held, the block's own events, then
   * every sound unit split at each one it takes, its inserts and its level;
   * the runtime's ticks run inside the block at their own frames
   * (fm1_mod_host.h). */
  render_sounds(a, n, out);
  for (int u = 1; u <= FM1_APP_FX_SLOTS; ++u) {   /* the master bus, after the mix */
    if (a->unit[u].e) render_fx(a, u, out, n);
  }
  if (a->mod) apply_amp(a, out, n);
  /* The metronome's click (O11), from the block's events, as fm1-render
   * adds it: after the effects, before the limiter. */
  if (a->seq) fm1_seq_click_mix(&a->click, a->seq, a->seq_ev, a->seq_last_n, n, out);
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
    mod_commit(a);                       /* a picker commits a second after its last turn */
    a->popup_lines = 0;
    a->dirty = 1;
  }
  if (a->mod && n >= FM1_MOD_TICK) {
    /* A block of a tick or more ran the plan the last edits asked for, so
     * reading it now builds nothing (a build here could change what a knob
     * sends before the next tick, which fm1-render would not). */
    fm1_mod_get_plan(a->mod, &a->mui.plan);
  }
  if (a->seq) {
    fm1_seq_ui_sound_t snd;
    const uint8_t page_was = a->ui.step_page;
    const int changed = fm1_seq_ui_sync(&a->ui, a->seq, a->seq_gen, a->frames);
    lock_sound(a, &snd);
    fm1_seq_ui_lock_pages(&a->ui, fm1_seq_ui_pages(snd.e));   /* the lock pages there are now */
    if (a->ui.step_page != page_was && a->mode == FM1_MODE_SEQ) a->dirty = 1;
    if (((changed & FM1_SEQ_UI_SYNC_SEQ) && a->mode == FM1_MODE_SEQ) ||
        (changed & FM1_SEQ_UI_SYNC_OVERLAY)) {
      a->dirty = 1;
    }
    if (a->ui.toast || a->ui.follow) ui_after(a);   /* what a Capture did */
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
  velocity = clampi(velocity, 0, 127);
  fm1_seq_host_note_in(&a->seq_host, (uint8_t)track, (uint8_t)pitch, (uint8_t)velocity);
  if (a->on_note_in) a->on_note_in(a->on_cmd_ctx, a->frames, track, pitch, velocity);
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
  fm1_look_fill(t, x, y, w, h, p, v, fill);
}

void fm1_look_fill(fm1_tft_t *t, int x, int y, int w, int h, const fm1_param_t *p, float v,
                   uint16_t fill) {
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
  if (fm1_param_is_log(p)) f = fm1_param_pos(p, v);   /* its knob's position (API v3) */
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
  const int code = fm1_app_mod_unit(unit);
  for (int s = 0; s < n; ++s) {
    const fm1_param_t *p = &u->e->params[idx[s]];
    int y = y0 + s * ROW_PITCH;
    float depth = 0.0f;
    /* With modulation, a parameter cables reach gets docs/16 §5.5's marks. */
    const int routes = a->mod && code >= 0 && idx[s] < (int)FM1_MOD_UNIT_PARAMS
                           ? fm1_mod_ui_routes(a->mod, (unsigned)code, p->uid, 0, &depth)
                           : 0;
    fm1_mod_view_row(&a->tft, y, p, u->value[idx[s]], NULL, routes, depth,
                     routes ? fm1_mod_sent(a->mod, (unsigned)code, (unsigned)idx[s]) : 0.0f);
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

/* The RAM meter, on the bottom bar's right: a bar of the chain's RAM
 * against FM1_APP_RAM_BUDGET and the percentage, rounded up, in the
 * warning colour past 100 %. The bar sits where "100%" would start, so it
 * never moves. */
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
  fm1_tft_fill(&a->tft, 0, BOTTOM_Y, FM1_TFT_W, FM1_TFT_H - BOTTOM_Y, C_BOTTOM_BG);
  fm1_tft_text(&a->tft, MARGIN, BOTTOM_Y + 3, left, 12, SCALE, C_TEXT);
  draw_ram_meter(a);
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
static void draw_popup_lines(fm1_app_t *a, const char (*text)[24], int lines, int mark) {
  const int pitch = POPUP_PITCH;   /* the highlight keeps 5 px from the next line */
  const int top = TITLE_H, bottom = BOTTOM_Y;
  fm1_tft_fill(&a->tft, 0, top, FM1_TFT_W, bottom - top, C_POPUP_BG);
  fm1_tft_paint(&a->tft, 0, top, FM1_TFT_W, 2, C_ACCENT);
  fm1_tft_paint(&a->tft, 0, bottom - 2, FM1_TFT_W, 2, C_ACCENT);
  int y0 = (top + bottom) / 2 - (lines * pitch - (pitch - 18)) / 2;
  for (int i = 0; i < lines; ++i) {
    int ly = y0 + i * pitch;
    int w = fm1_tft_text_width(text[i], POPUP_CHARS, SCALE);
    if (i == mark) fm1_tft_paint(&a->tft, 12, ly - 3, FM1_TFT_W - 24, 24, C_ACCENT);
    fm1_tft_text(&a->tft, 120 - w / 2, ly, text[i], POPUP_CHARS, SCALE,
                 i == mark ? C_BG : C_TEXT);
  }
}

/* A triangle LIST_MARK_W wide and LIST_MARK_H tall, centred, pointing up
 * (the list goes on above) or down (below), logged as one graphic. */
static void draw_list_mark(fm1_app_t *a, int y, int up) {
  const int cx = FM1_TFT_W / 2;
  fm1_tft_graphic(&a->tft, cx - LIST_MARK_W / 2, y, LIST_MARK_W, LIST_MARK_H);
  for (int r = 0; r < LIST_MARK_H; ++r) {
    const int half = r * (LIST_MARK_W / 2) / (LIST_MARK_H - 1);
    fm1_tft_paint(&a->tft, cx - half, up ? y + r : y + LIST_MARK_H - 1 - r, 2 * half + 1, 1,
                  C_ACCENT);
  }
}

/* A list popup over the centre area, as a message's: the list's title in
 * gold and the chosen entry's place ("12/96") dim on the first line, then
 * the window's entries from the left, the chosen one on the accent, an
 * Empty entry dim; a triangle between the title and the entries when the
 * list goes on above them, and one under them when it goes on below. */
static void draw_list(fm1_app_t *a, const char *title, const char (*text)[24], int lines,
                      int mark, int first, int total, uint32_t dim) {
  const int top = TITLE_H, bottom = BOTTOM_Y;
  char place[16];
  fm1_tft_fill(&a->tft, 0, top, FM1_TFT_W, bottom - top, C_POPUP_BG);
  fm1_tft_paint(&a->tft, 0, top, FM1_TFT_W, 2, C_ACCENT);
  fm1_tft_paint(&a->tft, 0, bottom - 2, FM1_TFT_W, 2, C_ACCENT);
  snprintf(place, sizeof place, "%d/%d", first + mark + 1, total);
  {
    const int pw = fm1_tft_text_width(place, 8, SCALE);
    const int px = FM1_TFT_W - LIST_X - pw;
    /* The title takes what is left before the place and the gap; a longer
     * one is cut, and the layout check counts the cut. */
    const int room = (px - FM1_APP_LAYOUT_GAP - LIST_X + SCALE) / FM1_TFT_ADVANCE(SCALE);
    fm1_tft_text(&a->tft, LIST_X, LIST_TITLE_Y, title, room, SCALE, C_MODEL);
    fm1_tft_text(&a->tft, px, LIST_TITLE_Y, place, 8, SCALE, C_DIM);
  }
  if (first > 0) draw_list_mark(a, LIST_MORE_Y, 1);
  for (int i = 0; i < lines; ++i) {
    const int ly = LIST_Y + i * LIST_PITCH;
    uint16_t color = (dim >> i) & 1u ? C_DIM : C_TEXT;
    if (i == mark) {
      fm1_tft_paint(&a->tft, MARGIN, ly - 3, RIGHT - MARGIN, LIST_PITCH - 1, C_ACCENT);
      color = C_BG;
    }
    fm1_tft_text(&a->tft, LIST_X, ly, text[i], POPUP_CHARS, SCALE, color);
  }
  if (first + lines < total) {
    draw_list_mark(a, LIST_Y + (lines - 1) * LIST_PITCH + 18 + FM1_APP_LAYOUT_GAP, 0);
  }
}

static void draw_popup(fm1_app_t *a) {
  if (a->popup_total > 0) {
    draw_list(a, a->popup_title, (const char (*)[24])a->popup, a->popup_lines, a->popup_mark,
              a->popup_first, a->popup_total, a->popup_dim);
  } else {
    draw_popup_lines(a, (const char (*)[24])a->popup, a->popup_lines, a->popup_mark);
  }
}

/* A tempo as "120 BPM", or "117.50 BPM" (the core's are 20.00 to 300.00). */
static void bpm_text(char *buf, size_t size, unsigned bpm_x100) {
  const unsigned v = bpm_x100 % 1000000u;
  if (v % 100u) snprintf(buf, size, "%u.%02u BPM", v / 100u, v % 100u);
  else snprintf(buf, size, "%u BPM", v / 100u);
}

/* Capture's overlay after a stopped Capture (O7), over every mode until a
 * press closes it, as Movy's: the tempo picker, one candidate a line with
 * the one taken highlighted (SELECT or KNOB1 takes another), or the tempo
 * the take was fitted to (the set's, or the external clock's). */
static void draw_capture(fm1_app_t *a) {
  const fm1_seq_ui_t *u = &a->ui;
  char text[3][24];
  char bpm[16];
  int lines = 0;
  if (u->capture_mode == FM1_SEQ_UI_CAPTURE_PICK && u->capture_n) {   /* a list, as PRESETS' */
    for (int k = 0; k < u->capture_n && k < 3; ++k) {
      bpm_text(text[lines++], sizeof text[0], u->capture_cands[k] * 100u);
    }
    const int mark = u->capture_sel < lines ? u->capture_sel : 0;
    draw_list(a, "Tempo", (const char (*)[24])text, lines, mark, 0, lines, 0);
    return;
  }
  bpm_text(bpm, sizeof bpm, u->bpm_x100);
  snprintf(text[lines++], sizeof text[0], "Captured");
  snprintf(text[lines++], sizeof text[0], "at %s", bpm);
  draw_popup_lines(a, (const char (*)[24])text, lines, -1);
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

/* FX mode (docs/15 §3.16): the chain on the first line (the current sound,
 * its inserts, Mix, the master slots; the selected one in the accent
 * colour, an empty one dim), the selected slot and its effect on the
 * second, then its page, or the Mix page's four levels. */
static void draw_fx(fm1_app_t *a, char *bottom, size_t size) {
  static const fm1_param_t kLevel = { "Level", FM1_PARAM_FLOAT, 0.0f, FM1_APP_LEVEL_MAX,
                                      FM1_APP_LEVEL_MAX, NULL, 0, 0, 0, 0, "" };
  fm1_tft_t *t = &a->tft;
  char buf[48];
  int x = MARGIN;
  const int y0 = CONTENT_Y + 2 * LINE_PITCH;
  const int unit = fx_unit_at(a, a->fx_slot);
  snprintf(buf, sizeof buf, "S%d", a->sound + 1);
  x += fm1_tft_text(t, x, CONTENT_Y, buf, 2, SCALE, C_MODEL) + FM1_TFT_ADVANCE(SCALE);
  for (int k = 0; k < FX_SLOT_COUNT; ++k) {
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
  const int mod_page = a->mod && is_mod_mode(a->mode);
  fm1_mod_ui_env_t env;
  char buf[48];
  fm1_tft_begin(t, C_BG);

  fm1_tft_fill(t, 0, 0, FM1_TFT_W, TITLE_H, C_TITLE_BG);
  if (mod_page) {                        /* the module, MATRIX or CHAIN */
    mod_env(a, &env);
    fm1_mod_view_title(&env, &a->mui, a->mode, buf, sizeof buf);
    fm1_tft_text(t, MARGIN, 3, buf, NAME_CHARS, SCALE, C_TEXT);
  } else if (multi_in_use(a)) {          /* "S2 Shapes": which of the sounds is current */
    snprintf(buf, sizeof buf, "S%d %s", a->sound + 1, s->e ? s->e->name : "(empty)");
    fm1_tft_text(t, MARGIN, 3, buf, NAME_CHARS, SCALE, C_TEXT);
  } else {
    fm1_tft_text(t, MARGIN, 3, s->e ? s->e->name : "(no sound)", NAME_CHARS, SCALE, C_TEXT);
  }
  draw_meter(a);

  if (mod_page) {
    if (a->mode == FM1_MODE_RACK) fm1_mod_view_rack(t, &env, &a->mui);
    else if (a->mode == FM1_MODE_MATRIX) fm1_mod_view_matrix(t, &env, &a->mui, a->frames);
    else fm1_mod_view_chain(t, &env, &a->mui);
    fm1_mod_view_bottom(&env, &a->mui, a->mode, buf, sizeof buf);
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_HOME) {
    int m = model_param(s->e);
    if (m >= 0) {
      fm1_look_value(&s->e->params[m], s->value[m], buf, sizeof buf);
      fm1_tft_text(t, MARGIN, CONTENT_Y, buf, LINE_CHARS, SCALE, C_MODEL);
    }
    if (s->e) draw_params(a, su, a->page, CONTENT_Y + LINE_PITCH);
    else draw_empty(a, CONTENT_Y, "Empty sound:", "turn PRESETS");
    draw_scope(a);
    snprintf(buf, sizeof buf, "%d/%d Sound", a->page + 1, page_count(s->e));
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_FX) {
    draw_fx(a, buf, sizeof buf);
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_SEQ) {
    fm1_seq_view_sound_t snd;
    snd.e = s->e;
    snd.value = s->value;
    snd.page = a->page;
    snd.pages = page_count(s->e);
    snd.n = page_params(s->e, a->page, snd.idx);
    snd.model = model_param(s->e);
    snd.seq = a->seq;
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      snd.unit_name[k] = sound_of(a, k)->e ? sound_of(a, k)->e->name : NULL;
    }
    {                                    /* the lock pages' sound: the focused track's (S8) */
      fm1_seq_ui_sound_t ls;
      snd.lock_sound = lock_sound(a, &ls);
      snd.lock_e = ls.e;
      snd.lock_value = ls.value;
      snd.lock_current = ls.current;
    }
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
  else if (a->ui.capture_mode) draw_capture(a);
}

int fm1_app_draw(fm1_app_t *a, uint32_t min_frames) {
  /* With modulation the rack's cells, the live ticks and MATRIX's hint line
   * move without input: redraw like the scope. */
  int live = a->peak > 0.0f || a->meter > 0.0f || a->mod != NULL;
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

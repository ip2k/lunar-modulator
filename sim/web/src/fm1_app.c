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

/* ---- colours (RGB565) ---------------------------------------------------- */

#define C_BG FM1_RGB565(0, 0, 0)
#define C_TEXT FM1_RGB565(240, 240, 240)
#define C_DIM FM1_RGB565(150, 150, 160)
#define C_ACCENT FM1_RGB565(255, 184, 48)
#define C_BAR_BG FM1_RGB565(48, 48, 56)
#define C_TITLE_BG FM1_RGB565(52, 40, 96)
#define C_BOTTOM_BG FM1_RGB565(28, 28, 36)
#define C_WARN FM1_RGB565(255, 80, 64)
#define C_SCOPE_BG FM1_RGB565(56, 56, 56)
#define C_SCOPE FM1_RGB565(255, 220, 0)
#define C_POPUP_BG FM1_RGB565(20, 20, 28)
#define C_METER FM1_RGB565(96, 220, 120)

/* Screen geometry: 2x text is 12 px a character and 18 px tall, so a line
 * holds 19 characters between the 6 px margins. */
#define SCALE 2
#define MARGIN 6
#define LINE_CHARS 19
#define RIGHT (FM1_TFT_W - MARGIN)
#define TITLE_H 24
#define BOTTOM_Y 216
#define ROW_PITCH 36
#define BAR_DY 21
#define BAR_H 7
#define LABEL_CHARS 10
#define NAME_CHARS 16
#define POPUP_CHARS 18

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

static void format_value(const fm1_param_t *p, float v, char *buf, size_t size) {
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

/* ---- set-up and units --------------------------------------------------------- */

void fm1_app_init(fm1_app_t *a, float sample_rate) {
  memset(a, 0, offsetof(fm1_app_t, tft));
  a->host.api_version = FM1_ENGINE_API_VERSION;
  a->host.sample_rate = sample_rate;
  a->host.max_frames = FM1_APP_MAX_FRAMES;
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    a->unit[u].index = -1;
    a->unit[u].mem = u == 0 ? a->sound_mem : a->fx_mem[u - 1];
    a->unit[u].cap = u == 0 ? FM1_APP_SOUND_BYTES : FM1_APP_FX_BYTES;
  }
  fm1_mix_limiter_init(&a->limiter, sample_rate);
  a->master = 1.0f;
  a->gain = 1.0f;
  a->popup_mark = -1;
  a->mode = FM1_MODE_HOME;
  a->dirty = 1;
  a->leds_changed = 1;
  a->tft.record = 0;
}

static void release(fm1_app_unit_t *u) {
  if (u->e && u->self) u->e->destroy(u->self);
  u->e = NULL;
  u->self = NULL;
  u->index = -1;
  u->bytes = 0;
}

int fm1_app_select(fm1_app_t *a, int unit, int index) {
  if (unit < 0 || unit >= FM1_APP_UNITS) return -1;
  fm1_app_unit_t *u = &a->unit[unit];
  const fm1_engine_t *e = entry(index);
  fm1_kind_t want = unit == 0 ? FM1_KIND_SOUND : FM1_KIND_AUDIO_FX;
  if (index == -1 && unit > 0) {
    release(u);
    a->dirty = 1;
    return 0;
  }
  if (!e || e->magic != FM1_ENGINE_MAGIC || e->api_version != FM1_ENGINE_API_VERSION ||
      e->kind != want || e->n_params > FM1_APP_MAX_PARAMS) {
    return -1;
  }
  size_t bytes = e->instance_size(&a->host);
  if (bytes > u->cap) return -2;
  if (unit == 0) fm1_app_all_notes_off(a);
  release(u);
  memset(u->mem, 0, bytes);
  u->self = e->create(u->mem, &a->host);
  if (!u->self) return -3;
  u->e = e;
  u->index = index;
  u->bytes = bytes;
  for (uint16_t i = 0; i < e->n_params; ++i) u->value[i] = e->params[i].def;
  if (unit == 0) a->page = clampi(a->page, 0, page_count(e) - 1);
  else if (a->fx_slot == unit - 1) a->fx_page = clampi(a->fx_page, 0, page_count(e) - 1);
  a->dirty = 1;
  return 0;
}

void fm1_app_default_chain(fm1_app_t *a) {
  fm1_app_select(a, 0, fm1_app_find("macro"));
  fm1_app_select(a, 1, fm1_app_find("plate"));
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

size_t fm1_app_ram(const fm1_app_t *a) {
  size_t total = 0;
  for (int u = 0; u < FM1_APP_UNITS; ++u) total += a->unit[u].bytes;
  return total;
}

/* ---- notes -------------------------------------------------------------------- */

void fm1_app_note_on(fm1_app_t *a, int note, int velocity) {
  if (note < 0 || note > 127) return;
  velocity = clampi(velocity, 1, 127);
  fm1_app_unit_t *s = &a->unit[0];
  if (s->e && s->e->note_on) s->e->note_on(s->self, (uint8_t)note, (uint8_t)velocity);
  if (a->note_count[note] < 255) ++a->note_count[note];
}

void fm1_app_note_off(fm1_app_t *a, int note) {
  if (note < 0 || note > 127) return;
  fm1_app_unit_t *s = &a->unit[0];
  if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)note);
  if (a->note_count[note]) --a->note_count[note];
}

void fm1_app_pitch_bend(fm1_app_t *a, float semitones) {
  if (!(semitones == semitones)) return;
  if (semitones > 48.0f) semitones = 48.0f;
  if (semitones < -48.0f) semitones = -48.0f;
  fm1_app_unit_t *s = &a->unit[0];
  if (s->e && s->e->pitch_bend) s->e->pitch_bend(s->self, semitones);
}

void fm1_app_all_notes_off(fm1_app_t *a) {
  fm1_app_unit_t *s = &a->unit[0];
  for (int n = 0; n < 128; ++n) {
    while (a->note_count[n]) {
      if (s->e && s->e->note_off) s->e->note_off(s->self, (uint8_t)n);
      --a->note_count[n];
    }
  }
  for (int k = 0; k < FM1_APP_KEYS; ++k) a->key_down[k] = 0;
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
    int note = FM1_APP_FIRST_NOTE + key + 12 * a->octave + a->transpose;
    if (note < 0 || note > 127) return;
    a->key_down[key] = 1;
    a->key_note[key] = (uint8_t)note;
    fm1_app_note_on(a, note, velocity);
  } else if (a->key_down[key]) {
    a->key_down[key] = 0;
    fm1_app_note_off(a, a->key_note[key]);
  }
}

static void show_signed(fm1_app_t *a, const char *what, int v) {
  char buf[24];
  snprintf(buf, sizeof buf, "%s %+d", what, v);
  if (v == 0) snprintf(buf, sizeof buf, "%s 0", what);
  popup(a, buf, NULL, NULL, -1);
}

void fm1_app_button(fm1_app_t *a, int button, int down) {
  if (button < 0 || button >= FM1_APP_BUTTONS) return;
  int was = a->button_down[button];
  a->button_down[button] = (uint8_t)(down != 0);
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
      a->mode = a->mode == FM1_MODE_FX ? FM1_MODE_HOME : FM1_MODE_FX;
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    case FM1_BTN_SEL:
      if (a->mode == FM1_MODE_FX) {
        a->fx_grab = !a->fx_grab;
        a->dirty = 1;
      } else {
        popup(a, "SEL", "works in FX mode", NULL, -1);
      }
      break;
    case FM1_BTN_GLO:
      a->mode = a->mode == FM1_MODE_GLOBAL ? FM1_MODE_HOME : FM1_MODE_GLOBAL;
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    case FM1_BTN_HOME:
      a->mode = FM1_MODE_HOME;
      a->fx_grab = 0;
      a->dirty = 1;
      break;
    default:
      popup(a, kButtonNames[button], "not in the", "simulator yet", -1);
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

/* The next effect choice for a slot: -1 (empty), then every effect. */
static int next_fx(int from, int dir) {
  int n = (int)fm1_engine_count;
  for (int k = 1; k <= n + 1; ++k) {
    int i = ((from + 1 + dir * k) % (n + 1) + (n + 1)) % (n + 1) - 1;
    if (i == -1 || fm1_engines[i]->kind == FM1_KIND_AUDIO_FX) return i;
  }
  return from;
}

static void preset_popup(fm1_app_t *a) {
  int cur = a->unit[0].index;
  if (cur < 0) return;
  popup(a, fm1_engines[next_sound(cur, -1)]->name, fm1_engines[cur]->name,
        fm1_engines[next_sound(cur, +1)]->name, 1);
}

/* FX mode walks (slot, page) pairs: slot 1's pages, then slot 2's. */
static void fx_step(fm1_app_t *a, int delta) {
  while (delta) {
    int dir = delta > 0 ? 1 : -1;
    int pages = page_count(a->unit[1 + a->fx_slot].e);
    int page = a->fx_page + dir;
    if (page >= 0 && page < pages) {
      a->fx_page = page;
    } else if (a->fx_slot + dir >= 0 && a->fx_slot + dir < FM1_APP_FX_SLOTS) {
      a->fx_slot += dir;
      a->fx_page = dir > 0 ? 0 : page_count(a->unit[1 + a->fx_slot].e) - 1;
    }
    delta -= dir;
  }
}

void fm1_app_encoder(fm1_app_t *a, int encoder, int delta) {
  if (encoder < 0 || encoder >= FM1_ENC_COUNT || delta == 0) return;
  delta = clampi(delta, -64, 64);
  switch (encoder) {
    case FM1_ENC_SELECT:
      if (a->mode == FM1_MODE_HOME) {
        a->page = clampi(a->page + delta, 0, page_count(a->unit[0].e) - 1);
      } else if (a->mode == FM1_MODE_FX && a->fx_grab) {
        int to = clampi(a->fx_slot + (delta > 0 ? 1 : -1), 0, FM1_APP_FX_SLOTS - 1);
        if (to != a->fx_slot) {                 /* swap the units, arenas and all */
          fm1_app_unit_t t = a->unit[1 + to];
          a->unit[1 + to] = a->unit[1 + a->fx_slot];
          a->unit[1 + a->fx_slot] = t;
          a->fx_slot = to;
          a->fx_page = 0;
        }
      } else if (a->mode == FM1_MODE_FX) {
        fx_step(a, delta);
      }
      a->dirty = 1;
      break;
    case FM1_ENC_PRESETS: {
      int cur = a->unit[0].index < 0 ? 0 : a->unit[0].index;
      int to = cur;
      for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_sound(to, delta > 0 ? 1 : -1);
      if (to != a->unit[0].index && fm1_app_select(a, 0, to) != 0) {
        popup(a, fm1_engines[to]->name, "does not fit", NULL, -1);
        break;
      }
      preset_popup(a);
      break;
    }
    case FM1_ENC_ALGORITHM:
      if (a->button_down[FM1_BTN_OCT_DOWN] || a->button_down[FM1_BTN_OCT_UP]) {
        a->transpose = clampi(a->transpose + delta, -12, 12);
        show_signed(a, "Transpose", a->transpose);
      } else if (a->mode == FM1_MODE_FX) {
        int slot = 1 + a->fx_slot;
        int to = a->unit[slot].index;
        for (int k = 0; k < (delta > 0 ? delta : -delta); ++k) to = next_fx(to, delta > 0 ? 1 : -1);
        int r = fm1_app_select(a, slot, to);
        a->fx_page = 0;
        if (r != 0) popup(a, fm1_engines[to]->name, "does not fit", NULL, -1);
        else if (to < 0) popup(a, "Empty slot", NULL, NULL, -1);
        else popup(a, fm1_engines[to]->name, NULL, NULL, -1);
      } else if (a->unit[0].e) {
        int m = model_param(a->unit[0].e);
        if (m >= 0) {
          char buf[24];
          turn_param(a, 0, m, delta);
          format_value(&a->unit[0].e->params[m], a->unit[0].value[m], buf, sizeof buf);
          popup(a, a->unit[0].e->params[m].name, buf, NULL, -1);
        }
      }
      break;
    default: {
      int knob = encoder - FM1_ENC_KNOB1;
      int unit = a->mode == FM1_MODE_FX ? 1 + a->fx_slot : 0;
      int page = a->mode == FM1_MODE_FX ? a->fx_page : a->page;
      int idx[4];
      if (a->mode == FM1_MODE_GLOBAL || !a->unit[unit].e) break;
      if (knob < page_params(a->unit[unit].e, page, idx)) turn_param(a, unit, idx[knob], delta);
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
    int note = base + k;
    led[k] = (uint8_t)(a->key_down[k] || (note >= 0 && note < 128 && a->note_count[note]));
  }
  for (int b = 0; b < FM1_APP_BUTTONS; ++b) led[FM1_APP_KEYS + b] = a->button_down[b];
  led[FM1_APP_KEYS + FM1_BTN_OCT_DOWN] = (uint8_t)octave_led(a, -a->octave);
  led[FM1_APP_KEYS + FM1_BTN_OCT_UP] = (uint8_t)octave_led(a, a->octave);
  led[FM1_APP_KEYS + FM1_BTN_FX] = a->mode == FM1_MODE_FX;
  led[FM1_APP_KEYS + FM1_BTN_SEL] = (uint8_t)(a->mode == FM1_MODE_FX && a->fx_grab);
  led[FM1_APP_KEYS + FM1_BTN_GLO] = a->mode == FM1_MODE_GLOBAL;
  if (memcmp(led, a->led, sizeof led) != 0) {
    memcpy(a->led, led, sizeof led);
    a->leds_changed = 1;
  }
}

/* ---- audio --------------------------------------------------------------------- */

const float *fm1_app_render(fm1_app_t *a, uint32_t frames) {
  uint32_t n = frames > FM1_APP_MAX_FRAMES ? FM1_APP_MAX_FRAMES : frames;
  float *out = a->out;
  if (a->unit[0].e) {
    a->unit[0].e->render(a->unit[0].self, out, n);
  } else {
    for (uint32_t i = 0; i < 2 * n; ++i) out[i] = 0.0f;
  }
  for (int u = 1; u < FM1_APP_UNITS; ++u) {
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
  update_leds(a);
  return out;
}

/* ---- the screen ---------------------------------------------------------------- */

static void draw_bar(fm1_tft_t *t, int y, const fm1_param_t *p, float v) {
  const int x = MARGIN, w = FM1_TFT_W - 2 * MARGIN;
  fm1_tft_graphic(t, x, y, w, BAR_H);
  fm1_tft_paint(t, x, y, w, BAR_H, C_BAR_BG);
  if (p->type == FM1_PARAM_ENUM) {
    int n = (int)(p->max - p->min) + 1;
    int i = enum_index(p, v);
    int seg = w / n < 3 ? 3 : w / n;
    int sx = x + (i * (w - seg)) / (n > 1 ? n - 1 : 1);
    fm1_tft_paint(t, sx, y, seg, BAR_H, C_ACCENT);
    return;
  }
  float range = p->max - p->min;
  float f = range > 0.0f ? (v - p->min) / range : 0.0f;
  f = f < 0.0f ? 0.0f : (f > 1.0f ? 1.0f : f);
  int pos = x + (int)floorf(f * (float)w + 0.5f);
  if (p->min < 0.0f && p->max > 0.0f) {          /* bipolar: from the zero point */
    int zero = x + (int)floorf((-p->min / range) * (float)w + 0.5f);
    int a0 = pos < zero ? pos : zero, a1 = pos < zero ? zero : pos;
    fm1_tft_paint(t, a0, y, a1 - a0 > 0 ? a1 - a0 : 1, BAR_H, C_ACCENT);
    fm1_tft_paint(t, zero, y, 1, BAR_H, C_TEXT);
  } else {
    fm1_tft_paint(t, x, y, pos - x, BAR_H, C_ACCENT);
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
    int label_chars = (int)strlen(p->name) < LABEL_CHARS ? (int)strlen(p->name) : LABEL_CHARS;
    int value_chars = LINE_CHARS - 1 - label_chars;
    format_value(p, u->value[idx[s]], value, sizeof value);
    fm1_tft_text(&a->tft, MARGIN, y, p->name, label_chars, SCALE, C_DIM);
    int vw = fm1_tft_text_width(value, value_chars, SCALE);
    fm1_tft_text(&a->tft, RIGHT - vw, y, value, value_chars, SCALE, C_TEXT);
    draw_bar(&a->tft, y + BAR_DY, p, u->value[idx[s]]);
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

static void draw_bottom(fm1_app_t *a, const char *left) {
  char ram[16];
  size_t bytes = fm1_app_ram(a);
  fm1_tft_fill(&a->tft, 0, BOTTOM_Y, FM1_TFT_W, FM1_TFT_H - BOTTOM_Y, C_BOTTOM_BG);
  fm1_tft_text(&a->tft, MARGIN, BOTTOM_Y + 3, left, 12, SCALE, C_TEXT);
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
  fm1_tft_graphic(&a->tft, x, y, w, h);
  fm1_tft_paint(&a->tft, x, y, w, h, C_SCOPE_BG);
  int prev = -1;
  for (int i = 0; i < w; ++i) {
    float v = s[start + i];
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
  const int pitch = 24;
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

static void draw_line(fm1_app_t *a, int y, const char *label, const char *value) {
  int label_chars = (int)strlen(label) < LABEL_CHARS ? (int)strlen(label) : LABEL_CHARS;
  int value_chars = LINE_CHARS - 1 - label_chars;
  fm1_tft_text(&a->tft, MARGIN, y, label, label_chars, SCALE, C_DIM);
  int w = fm1_tft_text_width(value, value_chars, SCALE);
  fm1_tft_text(&a->tft, RIGHT - w, y, value, value_chars, SCALE, C_TEXT);
}

static void draw(fm1_app_t *a) {
  fm1_tft_t *t = &a->tft;
  const fm1_app_unit_t *s = &a->unit[0];
  char buf[48];
  fm1_tft_begin(t, C_BG);

  fm1_tft_fill(t, 0, 0, FM1_TFT_W, TITLE_H, C_TITLE_BG);
  fm1_tft_text(t, MARGIN, 3, s->e ? s->e->name : "(no sound)", NAME_CHARS, SCALE, C_TEXT);
  draw_meter(a);

  if (a->mode == FM1_MODE_HOME) {
    int m = model_param(s->e);
    if (m >= 0) {
      format_value(&s->e->params[m], s->value[m], buf, sizeof buf);
      fm1_tft_text(t, MARGIN, 27, buf, LINE_CHARS, SCALE, C_ACCENT);
    }
    if (s->e) draw_params(a, 0, a->page, 50);
    draw_scope(a);
    snprintf(buf, sizeof buf, "%d/%d Sound", a->page + 1, page_count(s->e));
    draw_bottom(a, buf);
  } else if (a->mode == FM1_MODE_FX) {
    for (int k = 0; k < FM1_APP_FX_SLOTS; ++k) {
      const fm1_app_unit_t *f = &a->unit[1 + k];
      int sel = k == a->fx_slot;
      snprintf(buf, sizeof buf, "%s %d %s", sel ? (a->fx_grab ? "*" : ">") : " ", k + 1,
               f->e ? f->e->name : "--");
      fm1_tft_text(t, MARGIN, 27 + 20 * k, buf, LINE_CHARS, SCALE, sel ? C_ACCENT : C_DIM);
    }
    const fm1_app_unit_t *f = &a->unit[1 + a->fx_slot];
    if (f->e) {
      draw_params(a, 1 + a->fx_slot, a->fx_page, 70);
    } else {
      fm1_tft_text(t, MARGIN, 76, "Empty slot:", LINE_CHARS, SCALE, C_DIM);
      fm1_tft_text(t, MARGIN, 98, "turn ALGORITHM", LINE_CHARS, SCALE, C_DIM);
    }
    snprintf(buf, sizeof buf, "%d/%d FX%d", a->fx_page + 1, page_count(f->e), a->fx_slot + 1);
    draw_bottom(a, buf);
  } else {
    char v[32];
    int y = 28;
    snprintf(v, sizeof v, "%.0f Hz", (double)a->host.sample_rate);
    draw_line(a, y, "Rate", v); y += 20;
    snprintf(v, sizeof v, "%u", (unsigned)a->host.max_frames);
    draw_line(a, y, "Block", v); y += 20;
    snprintf(v, sizeof v, "%uK/%uK", (unsigned)((fm1_app_ram(a) + 1023) / 1024),
             (unsigned)((FM1_APP_RAM_BUDGET + 512) / 1024));
    draw_line(a, y, "RAM", v); y += 20;
    snprintf(v, sizeof v, "%u", s->e ? (unsigned)s->e->max_voices : 0u);
    draw_line(a, y, "Voices", v); y += 20;
    draw_line(a, y, "Sound", s->e ? s->e->id : "--"); y += 20;
    draw_line(a, y, "FX1", a->unit[1].e ? a->unit[1].e->id : "--"); y += 20;
    draw_line(a, y, "FX2", a->unit[2].e ? a->unit[2].e->id : "--"); y += 20;
    snprintf(v, sizeof v, "%+d", a->octave);
    draw_line(a, y, "Octave", a->octave ? v : "0"); y += 20;
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

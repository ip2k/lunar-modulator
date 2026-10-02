/* fm1_sim_render.c -- native harness for the virtual FM-1 (sim/web/src).
 *
 * Drives fm1_app_t the way the browser does and writes what it produces:
 *
 *   fm1-sim-render --engine macro --param Model=4 --note 0:57:100:1 \
 *                  --fx plate --seconds 2 --out a.wav
 *       the same note script as engines/build/fm1-render, rendered through
 *       the app (events at 64-frame block boundaries, offs before ons,
 *       controls first). With MASTER at full gain the WAV must equal
 *       fm1-render's byte for byte (tests/test_sim_web.py).
 *   --key T:KEY:VEL:DUR, --button T:NAME[:DUR], --turn T:ENCODER:DELTA,
 *   --master POSITION
 *       panel input at time T (KEY 0..26 is F3..G5 at octave 0; NAME as
 *       printed, e.g. OCT+, FX, PLAY/STOP; ENCODER SELECT, PRESETS,
 *       ALGORITHM, KNOB1..KNOB4)
 *   --select T:UNIT:ID  load engine ID (or - to empty an effect slot) into
 *                       unit 0..2 at time T, as the page's dropdowns do
 *   --screen FILE.ppm   the screen after the render, as a PPM image
 *   --screens DIR       draw every page of every engine and effect at its
 *                       defaults, minima, maxima and list values, plus the
 *                       global page and every popup, check each for layout
 *                       faults (fm1_tft_check_layout with FM1_APP_LAYOUT_GAP,
 *                       and truncated text), and write the representative
 *                       ones to DIR as PPM
 *   --list              the catalogue JSON
 *
 * Prints one line of JSON. Test code: C99 with stdio. MIT licence.
 */
#include "fm1_app.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_EVENTS 512

typedef enum { EV_NOTE, EV_BEND, EV_PARAM, EV_KEY, EV_BUTTON, EV_TURN, EV_SELECT } ev_kind_t;

typedef struct {
  double time;
  ev_kind_t kind;
  int on;              /* note/key/button: 1 down, 0 up */
  int a, b;            /* note/key and velocity; encoder/button id and delta */
  float value;
  char name[32];
  int done;
} event_t;

static fm1_app_t g_app;
static event_t g_ev[MAX_EVENTS];
static int g_nev;

static void usage(void) {
  fprintf(stderr,
          "usage: fm1-sim-render --list | --screens DIR |\n"
          "       [--engine ID [--param NAME=V]...] [--fx ID [--fx-param NAME=V]...]...\n"
          "       [--note T:KEY:VEL:DUR] [--bend T:ST] [--param-at T:NAME=V]\n"
          "       [--key T:KEY:VEL:DUR] [--button T:NAME[:DUR]] [--turn T:ENC:DELTA]\n"
          "       [--select T:UNIT:ID|-]\n"
          "       [--master P] [--seconds S] [--rate HZ] [--out F.wav] [--screen F.ppm]\n");
}

static event_t *add_event(double t, ev_kind_t kind) {
  if (g_nev >= MAX_EVENTS) {
    fprintf(stderr, "too many events\n");
    exit(2);
  }
  event_t *e = &g_ev[g_nev++];
  memset(e, 0, sizeof *e);
  e->time = t;
  e->kind = kind;
  return e;
}

static const char *const kButtons[FM1_APP_BUTTONS] = {
  "OCT-", "OCT+", "FX", "SEL", "ENV", "LFO", "EDIT", "GLO",
  "HOME", "SAVE", "ARP", "SEQ", "PLAY/STOP", "REC",
};
static const char *const kEncoders[FM1_ENC_COUNT] = {
  "SELECT", "PRESETS", "ALGORITHM", "KNOB1", "KNOB2", "KNOB3", "KNOB4",
};

static int lookup(const char *const *names, int n, const char *s) {
  for (int i = 0; i < n; ++i) {
    if (strcmp(names[i], s) == 0) return i;
  }
  return -1;
}

static int split_param(const char *arg, char *name, size_t size, float *value) {
  const char *eq = strchr(arg, '=');
  if (!eq || (size_t)(eq - arg) >= size) return 0;
  memcpy(name, arg, (size_t)(eq - arg));
  name[eq - arg] = 0;
  *value = (float)atof(eq + 1);
  return 1;
}

static int write_wav(const char *path, const float *lr, uint32_t frames, uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return 0;
  uint32_t data = frames * 4;
  uint8_t h[44] = { 'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ',
                    16, 0, 0, 0, 1, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 4, 0, 16, 0,
                    'd', 'a', 't', 'a', 0, 0, 0, 0 };
  uint32_t v[4] = { 36 + data, rate, rate * 4, data };
  int at[4] = { 4, 24, 28, 40 };
  for (int k = 0; k < 4; ++k) {
    for (int b = 0; b < 4; ++b) h[at[k] + b] = (uint8_t)(v[k] >> (8 * b));
  }
  fwrite(h, 1, sizeof h, f);
  for (uint32_t i = 0; i < 2 * frames; ++i) {
    float x = lr[i];
    if (!(x == x)) x = 0.0f;
    if (x > 1.0f) x = 1.0f;
    if (x < -1.0f) x = -1.0f;
    int16_t s = (int16_t)lrintf(x * 32767.0f);   /* as engines/host/render.cc */
    uint8_t b[2] = { (uint8_t)((uint16_t)s), (uint8_t)((uint16_t)s >> 8) };
    fwrite(b, 1, 2, f);
  }
  return fclose(f) == 0;
}

static int write_ppm(const char *path, const fm1_tft_t *t) {
  FILE *f = fopen(path, "wb");
  if (!f) return 0;
  fprintf(f, "P6\n%d %d\n255\n", FM1_TFT_W, FM1_TFT_H);
  for (int i = 0; i < FM1_TFT_W * FM1_TFT_H; ++i) {
    uint16_t p = t->px[i];
    uint8_t rgb[3] = { (uint8_t)(((p >> 11) & 0x1F) * 255 / 31),
                       (uint8_t)(((p >> 5) & 0x3F) * 255 / 63), (uint8_t)((p & 0x1F) * 255 / 31) };
    fwrite(rgb, 1, 3, f);
  }
  return fclose(f) == 0;
}

/* ---- --screens: every page, value extreme and popup, checked ---------------- */

static int g_screens, g_faults;

static void check_screen(const char *name, const char *dir, int save) {
  int report[8];
  fm1_app_draw_checked(&g_app);
  int n = fm1_tft_check_layout(&g_app.tft, FM1_APP_LAYOUT_GAP, report, 4);
  ++g_screens;
  if (n) {
    if (g_faults < 20) {
      for (int k = 0; k < n && k < 4; ++k) {
        int i = report[2 * k], j = report[2 * k + 1];
        if (i == -2) {
          fprintf(stderr, "layout fault in %s: text cut short\n", name);
          continue;
        }
        const fm1_tft_box_t *a = i >= 0 ? &g_app.tft.boxes[i] : NULL;
        const fm1_tft_box_t *b = j >= 0 ? &g_app.tft.boxes[j] : NULL;
        fprintf(stderr, "layout fault in %s: box %d (%d,%d %dx%d) vs box %d (%d,%d %dx%d)\n", name,
                i, a ? a->x : 0, a ? a->y : 0, a ? a->w : 0, a ? a->h : 0, j, b ? b->x : 0,
                b ? b->y : 0, b ? b->w : 0, b ? b->h : 0);
      }
    }
    g_faults += n;
  }
  if (save && dir) {
    char path[512];
    snprintf(path, sizeof path, "%s/%s.ppm", dir, name);
    for (char *c = path + strlen(dir) + 1; *c; ++c) {
      if (*c == '/' || *c == ' ') *c = '_';
    }
    if (!write_ppm(path, &g_app.tft)) fprintf(stderr, "cannot write %s\n", path);
  }
}

static void sweep_unit(int unit, const char *dir) {
  const fm1_engine_t *e = g_app.unit[unit].e;
  char name[128];
  int pages = 1;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
  }
  for (int page = 0; page < pages; ++page) {
    if (unit == 0) g_app.page = page;
    else g_app.fx_page = page;
    snprintf(name, sizeof name, "%s-%s-p%d", unit == 0 ? "home" : "fx", e->id, page + 1);
    check_screen(name, dir, 1);
    for (int pass = 0; pass < 2; ++pass) {               /* every value at its extremes */
      for (uint16_t i = 0; i < e->n_params; ++i) {
        const fm1_param_t *p = &e->params[i];
        fm1_app_set_param(&g_app, unit, i, pass ? p->max : p->min);
      }
      snprintf(name, sizeof name, "%s-%s-p%d-%s", unit == 0 ? "home" : "fx", e->id, page + 1,
               pass ? "max" : "min");
      check_screen(name, dir, 0);
    }
    for (uint16_t i = 0; i < e->n_params; ++i) {          /* every list entry */
      const fm1_param_t *p = &e->params[i];
      if (p->type != FM1_PARAM_ENUM || p->page != page) continue;
      for (int v = (int)p->min; v <= (int)p->max; ++v) {
        fm1_app_set_param(&g_app, unit, i, (float)v);
        snprintf(name, sizeof name, "%s-%s-p%d-%s-%d", unit == 0 ? "home" : "fx", e->id,
                 page + 1, p->name, v);
        check_screen(name, dir, 0);
      }
    }
    for (uint16_t i = 0; i < e->n_params; ++i) fm1_app_set_param(&g_app, unit, i, e->params[i].def);
  }
}

static int run_screens(const char *dir, float rate) {
  fm1_app_init(&g_app, rate);
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_SOUND) continue;
    if (fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    g_app.mode = FM1_MODE_HOME;
    fm1_app_note_on(&g_app, 57, 100);
    for (int k = 0; k < 40; ++k) fm1_app_render(&g_app, 64);  /* a live scope and meter */
    fm1_app_draw(&g_app, 0);
    sweep_unit(0, dir);
    fm1_app_all_notes_off(&g_app);
  }
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  g_app.mode = FM1_MODE_FX;
  for (int slot = 0; slot < FM1_APP_FX_SLOTS; ++slot) {
    g_app.fx_slot = slot;
    g_app.fx_page = 0;
    fm1_app_select(&g_app, 1 + slot, -1);
    check_screen(slot ? "fx-empty-slot2" : "fx-empty-slot1", dir, 1);
    for (size_t i = 0; i < fm1_engine_count; ++i) {
      if (fm1_engines[i]->kind != FM1_KIND_AUDIO_FX) continue;
      if (fm1_app_select(&g_app, 1 + slot, (int)i) != 0) continue;
      g_app.fx_grab = slot;                       /* both markers get drawn */
      sweep_unit(1 + slot, slot == 0 ? dir : NULL);
    }
  }
  g_app.mode = FM1_MODE_GLOBAL;
  g_app.octave = -3;
  g_app.transpose = -12;
  check_screen("global", dir, 1);
  g_app.octave = 0;
  g_app.transpose = 0;

  /* Popups, over HOME. */
  g_app.mode = FM1_MODE_HOME;
  fm1_app_encoder(&g_app, FM1_ENC_PRESETS, 1);
  check_screen("popup-presets", dir, 1);
  fm1_app_select(&g_app, 0, fm1_app_find("sixop"));
  fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, 1);
  check_screen("popup-algorithm", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_OCT_UP, 1);
  check_screen("popup-octave", dir, 0);
  fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -5);
  check_screen("popup-transpose", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_OCT_DOWN, 1);
  check_screen("popup-reset", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_OCT_UP, 0);
  fm1_app_button(&g_app, FM1_BTN_OCT_DOWN, 0);
  fm1_app_master(&g_app, 0.8f, 1);
  check_screen("popup-volume", dir, 0);
  for (int b = FM1_BTN_ENV; b < FM1_APP_BUTTONS; ++b) {
    if (b == FM1_BTN_GLO || b == FM1_BTN_HOME) continue;
    char name[64];
    fm1_app_button(&g_app, b, 1);
    fm1_app_button(&g_app, b, 0);
    snprintf(name, sizeof name, "popup-button-%d", b);
    check_screen(name, dir, b == FM1_BTN_PLAY);
  }
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);              /* SEL outside FX mode */
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);
  check_screen("popup-sel", dir, 0);
  fm1_app_button(&g_app, FM1_BTN_FX, 1);               /* FX: slot 2 to empty */
  fm1_app_button(&g_app, FM1_BTN_FX, 0);
  g_app.fx_slot = 1;
  g_app.fx_page = 0;
  fm1_app_select(&g_app, 2, fm1_app_find("diffuse"));
  fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -64);
  while (g_app.unit[2].e) fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -1);
  check_screen("popup-empty-slot", dir, 1);
  fm1_app_select(&g_app, 2, fm1_app_find("sw-psxverb"));   /* emptied on its 2nd page */
  fm1_app_encoder(&g_app, FM1_ENC_SELECT, 1);
  fm1_app_select(&g_app, 2, -1);
  check_screen("fx-emptied-on-page-2", dir, 0);
  if (g_app.fx_page != 0) {
    fprintf(stderr, "emptied slot left on page %d\n", g_app.fx_page + 1);
    ++g_faults;
  }
  g_app.mode = FM1_MODE_HOME;
  g_app.popup_lines = 0;
  /* Refusals: an arena too small, and a host rate the Plaits-based engines
   * refuse (last, at its own rate: the Schwung shim keeps its first rate). */
  g_app.unit[0].cap = 1024;
  fm1_app_encoder(&g_app, FM1_ENC_PRESETS, 1);
  g_app.unit[0].cap = FM1_APP_SOUND_BYTES;
  check_screen("popup-does-not-fit", dir, 1);
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (g_app.unit[u].e) g_app.unit[u].e->destroy(g_app.unit[u].self);
  }
  fm1_app_init(&g_app, 96000.0f);
  if (fm1_app_default_chain(&g_app) != -3 || !g_app.unit[0].e) {
    fprintf(stderr, "at 96000 Hz the default chain should fall back from Macro\n");
    ++g_faults;
  }
  check_screen("popup-refuses-rate", dir, 1);
  printf("{\"screens\":%d,\"faults\":%d}\n", g_screens, g_faults);
  return g_faults ? 1 : 0;
}

/* ---- the render ---------------------------------------------------------------- */

static int find_param(int unit, const char *name) {
  int i = fm1_app_param_index(&g_app, unit, name);
  if (i < 0) fprintf(stderr, "unknown parameter for unit %d: %s\n", unit, name);
  return i;
}

int main(int argc, char **argv) {
  const char *engine = NULL, *out_path = NULL, *screen_path = NULL;
  const char *fx_id[FM1_APP_FX_SLOTS] = { NULL, NULL };
  char fx_pname[FM1_APP_FX_SLOTS][16][32];
  float fx_pval[FM1_APP_FX_SLOTS][16];
  int fx_np[FM1_APP_FX_SLOTS] = { 0, 0 }, n_fx = 0;
  char pname[16][32];
  float pval[16];
  int np = 0;
  double secs = 2.0;
  float rate = 44118.0f, master = 1.0f;

  for (int i = 1; i < argc; ++i) {
    const char *a = argv[i];
    if (strcmp(a, "--list") == 0) {
      const char *j = fm1_app_catalog_json();
      if (!j) return 1;
      puts(j);
      return 0;
    }
    if (i + 1 >= argc) { usage(); return 2; }
    const char *v = argv[++i];
    if (strcmp(a, "--screens") == 0) return run_screens(v, rate);
    else if (strcmp(a, "--engine") == 0) engine = v;
    else if (strcmp(a, "--out") == 0) out_path = v;
    else if (strcmp(a, "--screen") == 0) screen_path = v;
    else if (strcmp(a, "--seconds") == 0) secs = atof(v);
    else if (strcmp(a, "--rate") == 0) rate = (float)atof(v);
    else if (strcmp(a, "--master") == 0) master = (float)atof(v);
    else if (strcmp(a, "--param") == 0) {
      if (np >= 16 || !split_param(v, pname[np], sizeof pname[np], &pval[np])) { usage(); return 2; }
      ++np;
    } else if (strcmp(a, "--fx") == 0) {
      if (n_fx >= FM1_APP_FX_SLOTS) { fprintf(stderr, "at most %d effects\n", FM1_APP_FX_SLOTS); return 2; }
      fx_id[n_fx++] = v;
    } else if (strcmp(a, "--fx-param") == 0) {
      int s = n_fx - 1;
      if (s < 0 || fx_np[s] >= 16 ||
          !split_param(v, fx_pname[s][fx_np[s]], sizeof fx_pname[s][0], &fx_pval[s][fx_np[s]])) {
        usage();
        return 2;
      }
      ++fx_np[s];
    } else if (strcmp(a, "--note") == 0 || strcmp(a, "--key") == 0) {
      double t, dur;
      int key, vel;
      if (sscanf(v, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) { usage(); return 2; }
      ev_kind_t k = a[2] == 'n' ? EV_NOTE : EV_KEY;
      event_t *on = add_event(t, k);
      on->on = 1, on->a = key, on->b = vel;
      event_t *off = add_event(t + dur, k);
      off->on = 0, off->a = key;
    } else if (strcmp(a, "--bend") == 0) {
      double t;
      float st;
      if (sscanf(v, "%lf:%f", &t, &st) != 2) { usage(); return 2; }
      add_event(t, EV_BEND)->value = st;
    } else if (strcmp(a, "--param-at") == 0) {
      const char *colon = strchr(v, ':');
      event_t *e;
      if (!colon) { usage(); return 2; }
      e = add_event(atof(v), EV_PARAM);
      if (!split_param(colon + 1, e->name, sizeof e->name, &e->value)) { usage(); return 2; }
    } else if (strcmp(a, "--button") == 0) {
      char name[32];
      double t, dur = 0.0;
      const char *c1 = strchr(v, ':');
      if (!c1) { usage(); return 2; }
      t = atof(v);
      snprintf(name, sizeof name, "%s", c1 + 1);
      char *c2 = strchr(name, ':');
      if (c2) { dur = atof(c2 + 1); *c2 = 0; }
      int b = lookup(kButtons, FM1_APP_BUTTONS, name);
      if (b < 0) { fprintf(stderr, "unknown button %s\n", name); return 2; }
      event_t *dn = add_event(t, EV_BUTTON);
      dn->on = 1, dn->a = b;
      event_t *up = add_event(t + dur, EV_BUTTON);
      up->on = 0, up->a = b;
    } else if (strcmp(a, "--select") == 0) {
      double t;
      int unit, n = 0;
      if (sscanf(v, "%lf:%d:%n", &t, &unit, &n) != 2 || !n) { usage(); return 2; }
      event_t *e = add_event(t, EV_SELECT);
      e->a = unit;
      snprintf(e->name, sizeof e->name, "%s", v + n);
    } else if (strcmp(a, "--turn") == 0) {
      char name[32];
      const char *c1 = strchr(v, ':');
      if (!c1) { usage(); return 2; }
      snprintf(name, sizeof name, "%s", c1 + 1);
      char *c2 = strchr(name, ':');
      if (!c2) { usage(); return 2; }
      *c2 = 0;
      int enc = lookup(kEncoders, FM1_ENC_COUNT, name);
      if (enc < 0) { fprintf(stderr, "unknown encoder %s\n", name); return 2; }
      event_t *e = add_event(atof(v), EV_TURN);
      e->a = enc, e->b = atoi(c2 + 1);
    } else { usage(); return 2; }
  }

  fm1_app_init(&g_app, rate);
  if (engine) {
    int r = fm1_app_select(&g_app, 0, fm1_app_find(engine));
    if (r) { fprintf(stderr, "cannot load %s (%d)\n", engine, r); return 1; }
    for (int p = 0; p < np; ++p) {
      int idx = find_param(0, pname[p]);
      if (idx < 0) return 1;
      fm1_app_set_param(&g_app, 0, idx, pval[p]);
    }
  }
  for (int s = 0; s < n_fx; ++s) {
    int r = fm1_app_select(&g_app, 1 + s, fm1_app_find(fx_id[s]));
    if (r) { fprintf(stderr, "cannot load %s (%d)\n", fx_id[s], r); return 1; }
    for (int p = 0; p < fx_np[s]; ++p) {
      int idx = find_param(1 + s, fx_pname[s][p]);
      if (idx < 0) return 1;
      fm1_app_set_param(&g_app, 1 + s, idx, fx_pval[s][p]);
    }
  }
  fm1_app_master(&g_app, master, 0);
  for (int k = 0; k < g_nev; ++k) {
    if (g_ev[k].kind == EV_PARAM && find_param(0, g_ev[k].name) < 0) return 1;
    if (g_ev[k].kind == EV_SELECT && strcmp(g_ev[k].name, "-") != 0 &&
        fm1_app_find(g_ev[k].name) < 0) {
      fprintf(stderr, "unknown engine %s\n", g_ev[k].name);
      return 1;
    }
  }

  uint32_t total = (uint32_t)(secs * rate);
  float *out = calloc((size_t)total * 2 + 2, sizeof(float));
  if (!out) return 1;
  double sum2 = 0.0;
  float peak = 0.0f;
  for (uint32_t pos = 0; pos < total; pos += FM1_APP_MAX_FRAMES) {
    double now = pos / (double)rate;
    uint32_t n = total - pos < FM1_APP_MAX_FRAMES ? total - pos : FM1_APP_MAX_FRAMES;
    for (int k = 0; k < g_nev; ++k) {                  /* controls first, in order */
      event_t *e = &g_ev[k];
      if (e->done || e->time > now) continue;
      if (e->kind == EV_BEND) fm1_app_pitch_bend(&g_app, e->value);
      else if (e->kind == EV_PARAM) fm1_app_set_param(&g_app, 0, find_param(0, e->name), e->value);
      else if (e->kind == EV_TURN) fm1_app_encoder(&g_app, e->a, e->b);
      else if (e->kind == EV_BUTTON) fm1_app_button(&g_app, e->a, e->on);
      else if (e->kind == EV_SELECT) {
        int idx = strcmp(e->name, "-") == 0 ? -1 : fm1_app_find(e->name);
        int r = fm1_app_select(&g_app, e->a, idx);
        if (r) fprintf(stderr, "select %s into unit %d: %d\n", e->name, e->a, r);
      } else continue;
      e->done = 1;
    }
    for (int pass = 0; pass < 2; ++pass) {             /* offs before ons */
      for (int k = 0; k < g_nev; ++k) {
        event_t *e = &g_ev[k];
        if (e->done || e->time > now || e->on != pass) continue;
        if (e->kind == EV_NOTE) {
          if (e->on) fm1_app_note_on(&g_app, e->a, e->b);
          else fm1_app_note_off(&g_app, e->a);
        } else if (e->kind == EV_KEY) {
          fm1_app_key(&g_app, e->a, e->on, e->b);
        } else {
          continue;
        }
        e->done = 1;
      }
    }
    const float *b = fm1_app_render(&g_app, n);
    memcpy(&out[(size_t)pos * 2], b, (size_t)n * 2 * sizeof(float));
    for (uint32_t i = 0; i < 2 * n; ++i) {
      float x = b[i];
      if (fabsf(x) > peak) peak = fabsf(x);
      sum2 += (double)x * x;
    }
  }
  if (out_path && !write_wav(out_path, out, total, (uint32_t)lrintf(rate))) {
    fprintf(stderr, "cannot write %s\n", out_path);
    return 1;
  }
  if (screen_path) {
    fm1_app_draw(&g_app, 0);
    if (!write_ppm(screen_path, &g_app.tft)) return 1;
  }
  int sounding = 0;
  for (int n = 0; n < 128; ++n) sounding += g_app.note_count[n];
  printf("{\"engine\":\"%s\",\"rate\":%g,\"frames\":%u,\"peak\":%.6f,\"rms\":%.6f,"
         "\"ram\":%u,\"mode\":%d,\"octave\":%d,\"transpose\":%d,\"sounding\":%d,"
         "\"fx\":[\"%s\",\"%s\"],\"fx_slot\":%d,\"fx_page\":%d,\"leds\":\"",
         g_app.unit[0].e ? g_app.unit[0].e->id : "", (double)rate, total, (double)peak,
         total ? sqrt(sum2 / (2.0 * total)) : 0.0, (unsigned)fm1_app_ram(&g_app), g_app.mode,
         g_app.octave, g_app.transpose, sounding, g_app.unit[1].e ? g_app.unit[1].e->id : "",
         g_app.unit[2].e ? g_app.unit[2].e->id : "", g_app.fx_slot, g_app.fx_page);
  for (int i = 0; i < FM1_APP_LEDS; ++i) putchar(g_app.led[i] ? '1' : '0');
  printf("\",\"popup\":[");
  for (int i = 0; i < g_app.popup_lines; ++i) {
    printf(i ? ",\"%s\"" : "\"%s\"", g_app.popup[i]);   /* popups hold plain names */
  }
  printf("]");
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    printf(",\"values%d\":[", u);
    const fm1_engine_t *e = g_app.unit[u].e;
    for (uint16_t p = 0; e && p < e->n_params; ++p) printf(p ? ",%g" : "%g", (double)g_app.unit[u].value[p]);
    printf("]");
  }
  printf("}\n");
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (g_app.unit[u].e) g_app.unit[u].e->destroy(g_app.unit[u].self);
  }
  free(out);
  return 0;
}

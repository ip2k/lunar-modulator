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
 *   --sizes             the sequencer's memory figures and sizeof(fm1_app_t)
 *   --lab               the lab switch on (fm1_app_set_lab): SEQ mode and
 *                       PLAY/STOP drive the sequencer (docs/15 S3)
 *   --start             the browser's start chain (fm1_app_default_chain)
 *                       in place of --engine: Macro, Plate, the default
 *                       route and, with --lab, the demo pattern
 *   --panel FILE        panel input from a file: one --key, --button or
 *                       --turn flag and its value per line ('#' comments)
 *   --format-check      every verb through fm1_seq_cmd_format and back
 *                       through fm1_seq_parse; prints JSON, exit 1 on a
 *                       difference
 *   --mod FILE          modulation as fm1-render --mod FILE plays it
 *                       (engines/host/mod_script.h): a new runtime with the
 *                       file's seed, its untimed lines after the chain is
 *                       set up, `@FRAME` lines at the first block starting
 *                       there (fm1_app_mod_reset, fm1_app_mod_line)
 *   --mod-format-check  random slots, bases and racks written as script
 *                       lines (fm1_mod_ui.h) and read back by mod_script.c
 *                       into a second runtime: the same records; JSON, exit
 *                       1 on a difference
 *
 * The sequencer, with fm1-render's meaning for its flags (engines/host/
 * render.cc): --cmd FILE plays a timed verb script, --seq FILE.movy1 loads a
 * set first (alone, it plays from the start), --tracks N (1..8; else the
 * script's header), --route T:engine|T:midi:CH, --events N (the bridge's
 * room, at most the app's 256) and --log-events FILE.jsonl. Rate and the run
 * length come from the script as fm1-render takes them at --frames 64: the
 * app's blocks are always 64 frames. Script lines apply at the first block
 * starting at or after their frame, after the panel and notes, through
 * fm1_app_seq_line; a line the event-room rule cuts short is finished at
 * the next block. With no --route the default-route rule applies, as in
 * fm1-render. --log-cmds FILE writes the lines as they were applied, and
 * every typed command (the panel's, --seq-ui's) as fm1_seq_cmd_format
 * writes it, at the block it led, as a verb script (header `#! rate
 * block=64 tracks end`, then `@<block start> <ops>`), and next to it a
 * sidecar, FILE less `.verbs` plus `.args`: the run's --engine, --param,
 * --fx, --fx-param, --note, --bend, --param-at, --seq and --route
 * arguments, one per line, then a --param-at for every sound parameter the
 * panel changed, at mid-block (docs/15 §6.3). With modulation running (the
 * lab switch, or --mod) it also writes FILE less `.verbs` plus `.mod`: the
 * runtime's whole state before the first block (fm1_app_mod_dump) and every
 * edit after it, the panel's and --mod's timed lines, as `@<block start>
 * <line>`; the sidecar then ends with `--mod` and that file (docs/16 MG3).
 * So
 *   fm1-render --cmd FILE.verbs $(arguments in FILE.args)
 * renders the same samples ("two-step parity"), unless the summary says
 * "replayable":0: the panel or --select changed the sound or an effect, a
 * key was played (key notes are logged from docs/15 S5), MASTER was not at
 * full gain, --seq-reset or --seq-import ran, or a modulation edit had no
 * script line (the effects swapped places, a per-voice cable).
 *
 * Test hooks: --seq-reset T:N and --seq-import T:FILE recreate the instance or import a set at time T, as a
 * UI would (then the default route, unless --route was given); --seq-ui
 * T:OP sends one op as a typed command at time T, as the panel will
 * (fm1_app_seq_cmd), and sends it again after each render while the app
 * answers BUSY.
 *
 * Prints one line of JSON. Test code: C99 with stdio. MIT licence.
 */
#include "fm1_app.h"
#include "mod_script.h"
#include "seq_script.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_EVENTS 512
#define MAX_ROUTES 64

typedef enum {
  EV_NOTE, EV_BEND, EV_PARAM, EV_KEY, EV_BUTTON, EV_TURN, EV_SELECT, EV_SEQ_RESET, EV_SEQ_IMPORT,
  EV_SEQ_UI
} ev_kind_t;

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
static int g_lab;                    /* --lab */
static int g_start;                  /* --start */
static int g_replayable = 1;         /* fm1-render can replay --log-cmds */

static void usage(void) {
  fprintf(stderr,
          "usage: fm1-sim-render --list | --screens DIR |\n"
          "       [--engine ID [--param NAME=V]...] [--fx ID [--fx-param NAME=V]...]...\n"
          "       [--note T:KEY:VEL:DUR] [--bend T:ST] [--param-at T:NAME=V]\n"
          "       [--key T:KEY:VEL:DUR] [--button T:NAME[:DUR]] [--turn T:ENC:DELTA]\n"
          "       [--select T:UNIT:ID|-]\n"
          "       [--master P] [--seconds S] [--rate HZ] [--out F.wav] [--screen F.ppm]\n"
          "       [--cmd FILE] [--seq FILE.movy1] [--tracks N] [--route T:engine|T:midi:CH]...\n"
          "       [--events N] [--log-events FILE.jsonl] [--log-cmds FILE.verbs]\n"
          "       [--seq-reset T:N] [--seq-import T:FILE.movy1] [--seq-ui T:OP]\n"
          "       [--lab] [--panel FILE] [--start] [--mod FILE]\n"
          "       | --sizes | --format-check | --mod-format-check\n");
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

/* --key T:KEY:VEL:DUR, --button T:NAME[:DUR] or --turn T:ENCODER:DELTA, from
 * the command line or a --panel line: 1, 0 for a malformed value, -1 for an
 * unknown name (reported). */
static int add_panel(const char *flag, const char *v) {
  if (strcmp(flag, "--key") == 0) {
    double t, dur;
    int key, vel;
    if (sscanf(v, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) return 0;
    event_t *on = add_event(t, EV_KEY);
    on->on = 1, on->a = key, on->b = vel;
    event_t *off = add_event(t + dur, EV_KEY);
    off->on = 0, off->a = key;
    return 1;
  }
  if (strcmp(flag, "--button") == 0) {
    char name[32];
    double t, dur = 0.0;
    const char *c1 = strchr(v, ':');
    if (!c1) return 0;
    t = atof(v);
    snprintf(name, sizeof name, "%s", c1 + 1);
    char *c2 = strchr(name, ':');
    if (c2) { dur = atof(c2 + 1); *c2 = 0; }
    int b = lookup(kButtons, FM1_APP_BUTTONS, name);
    if (b < 0) { fprintf(stderr, "unknown button %s\n", name); return -1; }
    event_t *dn = add_event(t, EV_BUTTON);
    dn->on = 1, dn->a = b;
    event_t *up = add_event(t + dur, EV_BUTTON);
    up->on = 0, up->a = b;
    return 1;
  }
  if (strcmp(flag, "--turn") == 0) {
    char name[32];
    const char *c1 = strchr(v, ':');
    if (!c1) return 0;
    snprintf(name, sizeof name, "%s", c1 + 1);
    char *c2 = strchr(name, ':');
    if (!c2) return 0;
    *c2 = 0;
    int enc = lookup(kEncoders, FM1_ENC_COUNT, name);
    if (enc < 0) { fprintf(stderr, "unknown encoder %s\n", name); return -1; }
    event_t *e = add_event(atof(v), EV_TURN);
    e->a = enc, e->b = atoi(c2 + 1);
    return 1;
  }
  return 0;
}

/* --panel FILE: one --key, --button or --turn and its value per line. */
static int read_panel(const char *path) {
  size_t len = 0;
  char *txt = fm1_read_file(path, &len);
  int ok = 1, lineno = 0;
  if (!txt) {
    fprintf(stderr, "cannot read %s\n", path);
    return 0;
  }
  for (char *p = txt, *eol; ok && p && *p; p = eol) {
    char *q, *v;
    ++lineno;
    eol = strchr(p, '\n');
    if (eol) *eol++ = '\0';
    q = p + strlen(p);
    while (q > p && (q[-1] == '\r' || q[-1] == ' ' || q[-1] == '\t')) *--q = '\0';
    while (*p == ' ' || *p == '\t') ++p;
    if (!*p || *p == '#') continue;
    for (v = p; *v && *v != ' ' && *v != '\t'; ++v) {}
    if (*v) *v++ = '\0';
    while (*v == ' ' || *v == '\t') ++v;
    if (strcmp(p, "--key") != 0 && strcmp(p, "--button") != 0 && strcmp(p, "--turn") != 0) {
      fprintf(stderr, "%s:%d: want --key, --button or --turn\n", path, lineno);
      ok = 0;
    } else if (add_panel(p, v) <= 0) {
      fprintf(stderr, "%s:%d: bad %s %s\n", path, lineno, p, v);
      ok = 0;
    }
  }
  free(txt);
  return ok;
}

/* ---- --log-cmds: the sidecar of arguments fm1-render needs to replay ------ */

#define MAX_SIDE 1024
static const char *g_side_flag[MAX_SIDE];
static char *g_side_value[MAX_SIDE];
static int g_nside;

static void side(const char *flag, const char *value) {
  size_t n = strlen(value) + 1;
  char *copy = malloc(n);
  if (!copy || g_nside >= MAX_SIDE) {
    fprintf(stderr, "too many replay arguments\n");
    exit(2);
  }
  memcpy(copy, value, n);
  g_side_flag[g_nside] = flag;
  g_side_value[g_nside++] = copy;
}

/* The units before a panel event, to see what it changed. */
typedef struct {
  int index[FM1_APP_UNITS];
  float value[FM1_APP_UNITS][FM1_APP_MAX_PARAMS];
} units_t;

static void units_now(units_t *u) {
  for (int k = 0; k < FM1_APP_UNITS; ++k) {
    u->index[k] = g_app.unit[k].index;
    memcpy(u->value[k], g_app.unit[k].value, sizeof u->value[k]);
  }
}

/* After a panel event in the block at `pos`: a sound parameter it changed
 * replays as --param-at at mid-block, where fm1-render applies it at the
 * same block start (docs/15 §6.3); a new sound or effect, or an effect's
 * parameter, cannot be replayed. */
static void panel_changed(const units_t *b, uint32_t pos, float rate) {
  const fm1_engine_t *e = g_app.unit[0].e;
  for (int k = 0; k < FM1_APP_UNITS; ++k) {
    if (g_app.unit[k].index != b->index[k]) g_replayable = 0;
    if (k && memcmp(g_app.unit[k].value, b->value[k], sizeof b->value[k]) != 0) g_replayable = 0;
  }
  if (!g_replayable || !e) return;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (g_app.unit[0].value[i] != b->value[0][i]) {
      char buf[96];
      snprintf(buf, sizeof buf, "%.9f:%s=%.9g", pos ? (pos - 32.0) / rate : 0.0,
               e->params[i].name, (double)g_app.unit[0].value[i]);
      side("--param-at", buf);
    }
  }
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

/* ---- --screens, lab on: SEQ mode's Track view (docs/15 §4, S3) --------- */

static void press(int button) {
  fm1_app_button(&g_app, button, 1);
  fm1_app_button(&g_app, button, 0);
}

static void seq_line(const char *ops) {
  if (fm1_app_seq_line(&g_app, ops, strlen(ops)) != strlen(ops)) {
    fprintf(stderr, "screens: \"%s\" did not go in\n", ops);
    ++g_faults;
  }
}

static void expect(int ok, const char *what) {
  if (!ok) {
    fprintf(stderr, "screens: %s\n", what);
    ++g_faults;
  }
}

/* Render until the focused clip's playhead reaches `step` (at most ~10 s). */
static void play_to(int step) {
  for (int k = 0; k < 8000 && !(g_app.ui.clip_playing && g_app.ui.step == step); ++k) {
    fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  }
  expect(g_app.ui.clip_playing && g_app.ui.step == step, "the playhead never reached its step");
}

static void destroy_units(void) {
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (g_app.unit[u].e) g_app.unit[u].e->destroy(g_app.unit[u].self);
    g_app.unit[u].e = NULL;
  }
}

static void seq_screens(const char *dir, float rate) {
  char name[128];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_set_lab(&g_app, 1);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_seq_default_route(&g_app);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  press(FM1_BTN_PLAY);                                 /* from HOME: no popup, no keys */
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  expect(g_app.popup_lines == 0 && g_app.mode == FM1_MODE_HOME, "PLAY/STOP in HOME");
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_PLAY] == 1, "the PLAY LED is off while playing");
  press(FM1_BTN_PLAY);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_PLAY] == 0, "the PLAY LED is on after a stop");
  press(FM1_BTN_SEQ);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  expect(g_app.mode == FM1_MODE_SEQ && g_app.popup_lines == 0, "SEQ does not open SEQ mode");
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_SEQ] == 1, "the SEQ LED is off in SEQ mode");
  check_screen("seq-empty", dir, 1);
  fm1_app_seq_demo(&g_app);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-demo", dir, 1);
  press(FM1_BTN_PLAY);
  play_to(0);
  check_screen("seq-demo-step1", dir, 1);
  play_to(15);
  check_screen("seq-demo-step16", dir, 1);
  seq_line("bpm 2000");
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-20-playing", dir, 0);
  seq_line("bpm 30000");
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-300-playing", dir, 1);
  press(FM1_BTN_PLAY);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-300-stopped", dir, 0);
  seq_line("bpm 2000");
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-20-stopped", dir, 0);
  seq_line("bpm 12000");
  /* A four-bar clip: a note toggled on every step, which clears the demo's
   * own in bar 1 and fills bars 2 to 4; the playhead in the fourth. */
  seq_line("clen 0 64");
  for (int k = 0; k < 64; k += 8) {
    char ops[512];
    int n = 0;
    for (int j = k; j < k + 8; ++j) {
      n += snprintf(ops + n, sizeof ops - (size_t)n, "%stog 0 %d %d 90", j > k ? ";" : "", j,
                    48 + j % 24);
    }
    seq_line(ops);
  }
  press(FM1_BTN_PLAY);
  play_to(50);
  check_screen("seq-four-bars-playing", dir, 1);
  /* A loop inside the clip (bar-aligned, then 6 steps long): the rest
   * outlined, its notes dim. */
  seq_line("loop 0 20 8;clen 0 6");
  play_to(18);
  check_screen("seq-loop-window", dir, 1);
  expect(fm1_seq_ui_key_leds(&g_app.ui) == 0, "bar 1 lies outside the loop: no key lit");
  press(FM1_BTN_PLAY);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  /* Track 8, which has no clip; and popups over the Track view. */
  g_app.ui.track = 7;
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-track8-no-clip", dir, 1);
  g_app.ui.track = 0;
  fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, 1);
  check_screen("seq-popup-algorithm", dir, 1);
  g_app.popup_lines = 0;
  press(FM1_BTN_REC);                                  /* still a stub with lab on */
  expect(g_app.popup_lines == 3, "REC does not say it is not in the simulator yet");
  check_screen("seq-popup-rec", dir, 0);
  g_app.popup_lines = 0;
  /* The hint line and the knob strip: every sound, page and knob, each
   * value at its extremes and every list entry; then the model line. */
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    int pages = 1;
    if (e->kind != FM1_KIND_SOUND || fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    g_app.popup_lines = 0;
    for (uint16_t q = 0; q < e->n_params; ++q) {
      if (e->params[q].page + 1 > pages) pages = e->params[q].page + 1;
    }
    for (int page = 0; page < pages; ++page) {
      int idx[4], n = 0;
      g_app.page = page;
      for (uint16_t q = 0; q < e->n_params && n < 4; ++q) {
        if (e->params[q].page == page) idx[n++] = q;
      }
      for (int k = 0; k < n; ++k) {
        const fm1_param_t *p = &e->params[idx[k]];
        fm1_seq_ui_knob(&g_app.ui, k, UINT64_MAX);
        for (int pass = 0; pass < 2; ++pass) {
          fm1_app_set_param(&g_app, 0, idx[k], pass ? p->max : p->min);
          snprintf(name, sizeof name, "seq-hint-%s-p%d-k%d-%s", e->id, page + 1, k + 1,
                   pass ? "max" : "min");
          check_screen(name, dir, page == 0 && k == 1 && pass);
        }
        for (int v = (int)p->min; p->type == FM1_PARAM_ENUM && v <= (int)p->max; ++v) {
          fm1_app_set_param(&g_app, 0, idx[k], (float)v);
          snprintf(name, sizeof name, "seq-hint-%s-p%d-k%d-%d", e->id, page + 1, k + 1, v);
          check_screen(name, dir, 0);
        }
        fm1_app_set_param(&g_app, 0, idx[k], p->def);
      }
      g_app.ui.knob = -1;
      snprintf(name, sizeof name, "seq-%s-p%d", e->id, page + 1);
      check_screen(name, dir, page == 0);
    }
    g_app.page = 0;
    for (uint16_t q = 0; q < e->n_params; ++q) {          /* the model line */
      const fm1_param_t *p = &e->params[q];
      if (p->type != FM1_PARAM_ENUM) continue;
      for (int v = (int)p->min; v <= (int)p->max; ++v) {
        fm1_app_set_param(&g_app, 0, q, (float)v);
        snprintf(name, sizeof name, "seq-model-%s-%d", e->id, v);
        check_screen(name, dir, 0);
      }
      fm1_app_set_param(&g_app, 0, q, p->def);
      break;
    }
  }
  /* HOME, FX and GLO leave SEQ mode; the lab switch off leaves it too. */
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  press(FM1_BTN_HOME);
  expect(g_app.mode == FM1_MODE_HOME, "HOME does not leave SEQ mode");
  press(FM1_BTN_SEQ);
  press(FM1_BTN_FX);
  expect(g_app.mode == FM1_MODE_FX, "FX does not leave SEQ mode");
  press(FM1_BTN_SEQ);
  press(FM1_BTN_GLO);
  expect(g_app.mode == FM1_MODE_GLOBAL, "GLO does not leave SEQ mode");
  press(FM1_BTN_SEQ);
  press(FM1_BTN_SEQ);
  expect(g_app.mode == FM1_MODE_SEQ, "SEQ inside SEQ mode leaves it");
  fm1_app_set_lab(&g_app, 0);
  expect(g_app.mode == FM1_MODE_HOME, "the lab switch off leaves SEQ mode");
  press(FM1_BTN_SEQ);
  expect(g_app.mode == FM1_MODE_HOME && g_app.popup_lines == 3, "SEQ with the lab switch off");
  destroy_units();
}

/* ---- --screens, lab on: the modulation pages (docs/16 §5, stage MG3) ---- */

static void mod_line(const char *line) {
  char err[256];
  if (!fm1_app_mod_line(&g_app, line, err, sizeof err)) {
    fprintf(stderr, "screens: \"%s\": %s\n", line, err);
    ++g_faults;
  }
}

static void blocks(int n) {
  for (int k = 0; k < n; ++k) fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
}

static void turn(int encoder, int delta) { fm1_app_encoder(&g_app, encoder, delta); }

/* A screen with no popup over it, then that popup timed out. */
static void settle(void) {
  while (g_app.popup_lines) blocks(16);
}

/* Every page of the module at position 6 (index 5) at its parameters'
 * extremes and list entries, routed and not. */
static void mod_sweep_module(const char *dir, const char *id) {
  char name[128], line[128];
  const int k = fm1_mod_kind_find(id);
  const fm1_mod_kind_t *kd = fm1_mod_kinds[k];
  snprintf(line, sizeof line, "mod 6 %s", id);
  mod_line(line);
  g_app.mui.pos = 5;
  for (int routed = 0; routed < 2; ++routed) {
    if (routed) {                      /* a cable into every parameter, both signs */
      int slot = 10;
      for (unsigned i = 0; i < kd->n_params && slot <= 32; ++i, ++slot) {
        snprintf(line, sizeof line, "slot %d lfo1 > mod6:%s amt=%d", slot, kd->params[i].abbr,
                 i % 2 ? -100 : 35);
        mod_line(line);
      }
      blocks(2);
    }
    for (int page = 0; page < fm1_mod_ui_rack_pages(g_app.mod, 5); ++page) {
      g_app.mui.page = (uint8_t)page;
      snprintf(name, sizeof name, "rack-%s-p%d%s", id, page + 1, routed ? "-routed" : "");
      check_screen(name, dir, 1);
      for (int pass = 0; pass < 2; ++pass) {
        for (unsigned i = 0; i < kd->n_params; ++i) {
          fm1_mod_set_param(g_app.mod, 5, i, pass ? kd->params[i].max : kd->params[i].min);
        }
        blocks(1);
        snprintf(name, sizeof name, "rack-%s-p%d-%s%s", id, page + 1, pass ? "max" : "min",
                 routed ? "-routed" : "");
        check_screen(name, dir, 0);
      }
      for (unsigned i = 0; i < kd->n_params; ++i) {
        const fm1_param_t *p = &kd->params[i];
        if (p->type != FM1_PARAM_ENUM || p->page != page) continue;
        for (int v = (int)p->min; v <= (int)p->max; ++v) {
          fm1_mod_set_param(g_app.mod, 5, i, (float)v);
          snprintf(name, sizeof name, "rack-%s-p%d-%s-%d%s", id, page + 1, p->name, v,
                   routed ? "-routed" : "");
          check_screen(name, dir, 0);
        }
      }
      for (unsigned i = 0; i < kd->n_params; ++i) fm1_mod_set_param(g_app.mod, 5, i, kd->params[i].def);
    }
  }
  for (int slot = 10; slot <= 32; ++slot) {
    snprintf(line, sizeof line, "slot %d clear", slot);
    mod_line(line);
  }
  mod_line("mod 6 none");
}

static void mod_screens(const char *dir, float rate) {
  char name[128], line[160];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_set_lab(&g_app, 1);
  expect(g_app.mod != NULL, "the lab switch starts no modulation runtime");
  if (!g_app.mod) return;
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  fm1_app_select(&g_app, 2, fm1_app_find("echo"));
  fm1_app_seq_default_route(&g_app);
  fm1_app_note_on(&g_app, 57, 100);
  blocks(40);
  /* LFO: RACK at LFO1, then LFO2; ENV at ENV1; the LEDs. */
  press(FM1_BTN_LFO);
  expect(g_app.mode == FM1_MODE_RACK && g_app.mui.pos == 0, "LFO does not open RACK at LFO1");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_LFO] == 1, "the LFO LED is off on LFO1's page");
  check_screen("rack-lfo1", dir, 1);
  press(FM1_BTN_LFO);
  expect(g_app.mui.pos == 1, "LFO again does not step to LFO2");
  press(FM1_BTN_ENV);
  expect(g_app.mode == FM1_MODE_RACK && g_app.mui.pos == 2, "ENV does not open RACK at ENV1");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_ENV] == 1 && g_app.led[FM1_APP_KEYS + FM1_BTN_LFO] == 0,
         "ENV1's page lights ENV alone");
  check_screen("rack-env1", dir, 1);
  /* SELECT walks every position and page, there and back. */
  g_app.mui.pos = 0;
  g_app.mui.page = 0;
  for (int k = 0; k < 16; ++k) {
    snprintf(name, sizeof name, "rack-walk-%02d", k);
    check_screen(name, dir, k == 8 || k == 10);
    turn(FM1_ENC_SELECT, 1);
  }
  expect(g_app.mui.pos == 7, "SELECT does not reach the last position");
  turn(FM1_ENC_SELECT, -64);
  expect(g_app.mui.pos == 0 && g_app.mui.page == 0, "SELECT does not come back to the first");
  /* The kind picker on an empty position, and its commit after a second. */
  g_app.mui.pos = 6;
  for (int k = 0; k < (int)fm1_mod_kind_count + 1; ++k) {
    turn(FM1_ENC_ALGORITHM, 1);
    snprintf(name, sizeof name, "rack-picker-%d", k);
    check_screen(name, dir, k == 0);
  }
  turn(FM1_ENC_ALGORITHM, 1);              /* round to the first kind again */
  settle();
  expect(fm1_mod_kind_at(g_app.mod, 6) == 0, "the kind picker did not commit its choice");
  check_screen("rack-new-module", dir, 1);
  turn(FM1_ENC_ALGORITHM, -1);             /* back to Empty */
  settle();
  expect(fm1_mod_kind_at(g_app.mod, 6) < 0, "the kind picker did not empty the position");
  /* Grab: SEL, then SELECT moves the module. */
  g_app.mui.pos = 4;
  press(FM1_BTN_SEL);
  expect(g_app.mui.grab == 1, "SEL does not grab in RACK");
  blocks(1);
  check_screen("rack-grab", dir, 1);
  turn(FM1_ENC_SELECT, 1);
  expect(g_app.mui.pos == 5 && fm1_mod_kind_at(g_app.mod, 5) == fm1_mod_kind_find("chance"),
         "SELECT does not move a grabbed module");
  turn(FM1_ENC_SELECT, -1);
  press(FM1_BTN_SEL);
  /* Every kind's every page. */
  for (size_t k = 0; k < fm1_mod_kind_count; ++k) mod_sweep_module(dir, fm1_mod_kinds[k]->id);
  /* The gesture's popups: a cable made, a parameter that takes none, a full
   * matrix and no LFO in the rack; then the routed marks on HOME and FX. */
  g_app.mode = FM1_MODE_HOME;
  g_app.page = 0;
  fm1_app_button(&g_app, FM1_BTN_LFO, 1);
  turn(FM1_ENC_KNOB2, 12);
  check_screen("gesture-made", dir, 1);
  turn(FM1_ENC_KNOB1, 1);
  check_screen("gesture-no-cable", dir, 0);
  fm1_app_button(&g_app, FM1_BTN_LFO, 0);
  expect(g_app.mode == FM1_MODE_HOME, "a held LFO that turned a knob opened RACK");
  settle();
  /* Every sound's every page with a cable on each knob. */
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    int pages = 1;
    if (e->kind != FM1_KIND_SOUND || fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    settle();
    for (uint16_t q = 0; q < e->n_params; ++q) {
      if (e->params[q].page + 1 > pages) pages = e->params[q].page + 1;
    }
    for (int slot = 3; slot <= 32; ++slot) {
      snprintf(line, sizeof line, "slot %d clear", slot);
      mod_line(line);
    }
    for (uint16_t q = 0, slot = 3; q < e->n_params && slot <= 32; ++q) {
      if (!fm1_param_modulatable(&e->params[q])) continue;
      snprintf(line, sizeof line, "slot %u %s > snd:%s amt=%d", (unsigned)slot++, q % 2 ? "env3" : "lfo1",
               e->params[q].abbr, q % 3 ? 60 : -100);
      mod_line(line);
    }
    blocks(3);
    for (int page = 0; page < pages; ++page) {
      g_app.page = page;
      for (int pass = 0; pass < 3; ++pass) {
        for (uint16_t q = 0; pass < 2 && q < e->n_params; ++q) {
          fm1_app_set_param(&g_app, 0, q, pass ? e->params[q].max : e->params[q].min);
        }
        blocks(1);
        snprintf(name, sizeof name, "home-routed-%s-p%d-%s", e->id, page + 1,
                 pass == 2 ? "def" : pass ? "max" : "min");
        check_screen(name, dir, page == 0 && pass == 2);
        for (uint16_t q = 0; pass < 2 && q < e->n_params; ++q) {
          fm1_app_set_param(&g_app, 0, q, e->params[q].def);
        }
      }
    }
  }
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  settle();
  /* FX: every effect in slot 1 with a cable on each parameter. */
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 0;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    int pages = 1;
    if (e->kind != FM1_KIND_AUDIO_FX || fm1_app_select(&g_app, 1, (int)i) != 0) continue;
    for (uint16_t q = 0; q < e->n_params; ++q) {
      if (e->params[q].page + 1 > pages) pages = e->params[q].page + 1;
    }
    for (int slot = 3; slot <= 32; ++slot) {
      snprintf(line, sizeof line, "slot %d clear", slot);
      mod_line(line);
    }
    for (uint16_t q = 0, slot = 3; q < e->n_params && slot <= 32; ++q) {
      if (!fm1_param_modulatable(&e->params[q])) continue;
      snprintf(line, sizeof line, "slot %u chance5 > fx1:%s amt=%d", (unsigned)slot++, e->params[q].abbr,
               q % 2 ? 100 : -45);
      mod_line(line);
    }
    blocks(3);
    for (int page = 0; page < pages; ++page) {
      g_app.fx_page = page;
      snprintf(name, sizeof name, "fx-routed-%s-p%d", e->id, page + 1);
      check_screen(name, dir, page == 0);
    }
    g_app.fx_page = 0;
  }
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  for (int slot = 3; slot <= 32; ++slot) {
    snprintf(line, sizeof line, "slot %d clear", slot);
    mod_line(line);
  }
  /* MATRIX: EDIT; the default two cables, then 0, 1, 7 and 32 slots; both
   * pages; a refused, an off, a delayed and a per-voice row; every field's
   * hint; the destination picker. */
  g_app.mode = FM1_MODE_HOME;
  press(FM1_BTN_EDIT);
  expect(g_app.mode == FM1_MODE_MATRIX, "EDIT does not open MATRIX");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_EDIT] == 1, "the EDIT LED is off in MATRIX");
  turn(FM1_ENC_SELECT, -64);
  check_screen("matrix-default", dir, 1);
  mod_line("slot 1 clear");
  mod_line("slot 2 clear");
  blocks(1);
  check_screen("matrix-empty", dir, 1);
  mod_line("slot 1 lfo1 > snd:Timbre amt=40");
  blocks(1);
  check_screen("matrix-one", dir, 0);
  {
    static const char *const kSeven[] = {
      "slot 2 lfo2.wrap > env3:gate amt=100",
      "slot 3 env3.eoc > chance5:trig amt=75",
      "slot 4 chance5.smth > lfo2.rate amt=-100 ofs=-100",
      "slot 5 lfo1 > snd:Model amt=50",              /* NOLOCK: refused */
      "slot 6 seq8 > fx2:PingPg amt=-100 off",
      "slot 7 lfo2 > lfo1.rate amt=12",              /* with slot 8: a loop */
      "slot 8 lfo1 > lfo2.phase amt=100 via=chance5.held pol=inv curve=square",
    };
    for (size_t k = 0; k < sizeof kSeven / sizeof kSeven[0]; ++k) mod_line(kSeven[k]);
  }
  blocks(2);
  expect(g_app.mui.plan.refused != 0 && g_app.mui.plan.delayed != 0,
         "MATRIX's sweep has no refused or no delayed row");
  check_screen("matrix-seven", dir, 1);
  g_app.mui.mpage = 1;
  check_screen("matrix-seven-b", dir, 1);
  g_app.mui.mpage = 0;
  for (int f = 0; f < 8; ++f) {                         /* each field's hint */
    g_app.mui.mpage = (uint8_t)(f / 4);
    g_app.mui.field = (int8_t)f;
    g_app.mui.field_until = UINT64_MAX;
    for (int sl = 0; sl < 8; sl += 7) {
      g_app.mui.slot = (uint8_t)sl;
      snprintf(name, sizeof name, "matrix-hint-%d-slot%d", f, sl + 1);
      check_screen(name, dir, 0);
    }
  }
  g_app.mui.field = -1;
  g_app.mui.mpage = 0;
  g_app.mui.slot = 0;
  {                                                     /* a per-voice row */
    fm1_mod_slot_t v;
    fm1_mod_get_slot(g_app.mod, 0, &v);
    v.flags |= FM1_MOD_SLOT_VOICE;
    fm1_mod_set_slot(g_app.mod, 0, &v);
    check_screen("matrix-voice", dir, 0);
    v.flags &= (uint8_t)~FM1_MOD_SLOT_VOICE;
    fm1_mod_set_slot(g_app.mod, 0, &v);
  }
  /* 32 slots, the widest names: module outputs past the first, effect
   * parameters, gate inputs. */
  for (int slot = 9; slot <= 32; ++slot) {
    static const char *const kSrc[] = { "lfo1.wrap", "env4.act", "chance5.step", "clock", "start", "sqv8" };
    static const char *const kDst[] = { "fx2:PingPg", "env4:gate", "chance5:trig", "lfo2:reset",
                                        "snd:EnvMor", "host:pitch", "host:amp", "env3.sus" };
    snprintf(line, sizeof line, "slot %d %s > %s amt=%d ofs=%d pol=bi curve=log", slot,
             kSrc[slot % 6], kDst[slot % 8], slot % 2 ? -100 : 100, -100);
    mod_line(line);
  }
  blocks(2);
  for (int sl = 0; sl < 32; sl += 5) {
    turn(FM1_ENC_SELECT, sl - g_app.mui.slot);
    for (int pg = 0; pg < 2; ++pg) {
      g_app.mui.mpage = (uint8_t)pg;
      snprintf(name, sizeof name, "matrix-full-slot%d-%c", sl + 1, pg ? 'b' : 'a');
      check_screen(name, dir, sl == 30);
    }
  }
  g_app.mui.mpage = 0;
  turn(FM1_ENC_SELECT, 31);
  expect(g_app.mui.slot == 31 && g_app.mui.top == 25, "SELECT does not scroll to slot 32");
  check_screen("matrix-last", dir, 1);
  turn(FM1_ENC_SELECT, -64);
  /* The destination picker: open, at both ends, a group jump. */
  turn(FM1_ENC_KNOB2, 1);
  check_screen("matrix-picker", dir, 1);
  turn(FM1_ENC_KNOB2, -999);
  check_screen("matrix-picker-first", dir, 0);
  turn(FM1_ENC_ALGORITHM, 3);
  check_screen("matrix-picker-group", dir, 1);
  turn(FM1_ENC_KNOB2, 999);
  check_screen("matrix-picker-last", dir, 0);
  settle();
  /* CHAIN: SEL on the loop's cable and on a chain through three modules. */
  turn(FM1_ENC_SELECT, 2 - g_app.mui.slot);             /* slot 3: ENV1 EOC into CHN1 */
  press(FM1_BTN_SEL);
  expect(g_app.mode == FM1_MODE_CHAIN, "SEL does not open CHAIN from MATRIX");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_SEL] == 1, "the SEL LED is off in CHAIN");
  check_screen("chain-slot3", dir, 1);
  for (int k = 0; k < 32; ++k) {
    snprintf(name, sizeof name, "chain-%02d", g_app.mui.slot + 1);
    check_screen(name, dir, g_app.mui.slot == 6);
    turn(FM1_ENC_SELECT, 1);
  }
  g_app.mui.slot = 20;
  mod_line("slot 21 clear");
  check_screen("chain-empty", dir, 1);
  press(FM1_BTN_SEL);
  expect(g_app.mode == FM1_MODE_MATRIX, "SEL in CHAIN does not go back to MATRIX");
  /* Popups over the pages. */
  turn(FM1_ENC_PRESETS, 1);
  check_screen("matrix-popup", dir, 0);
  settle();
  /* HOME, FX and GLO leave the pages; the switch off brings the stubs back. */
  press(FM1_BTN_HOME);
  expect(g_app.mode == FM1_MODE_HOME, "HOME does not leave MATRIX");
  press(FM1_BTN_LFO);
  press(FM1_BTN_GLO);
  expect(g_app.mode == FM1_MODE_GLOBAL, "GLO does not leave RACK");
  press(FM1_BTN_EDIT);
  fm1_app_set_lab(&g_app, 0);
  expect(g_app.mode == FM1_MODE_HOME && !g_app.mod, "the switch off keeps modulation");
  for (int b = FM1_BTN_ENV; b <= FM1_BTN_EDIT; ++b) {
    g_app.popup_lines = 0;
    press(b);
    expect(g_app.mode == FM1_MODE_HOME && g_app.popup_lines == 3,
           "ENV, LFO or EDIT with the switch off is not the stub");
  }
  destroy_units();
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
  seq_screens(dir, rate);
  mod_screens(dir, rate);
  printf("{\"screens\":%d,\"faults\":%d}\n", g_screens, g_faults);
  return g_faults ? 1 : 0;
}

/* ---- the sequencer's sizes ------------------------------------------------------ */

static int print_sizes(void) {
  fm1_seq_limits_t lim8, lim4;
  fm1_seq_limits_default(&lim8, 8);
  fm1_seq_limits_default(&lim4, 4);
  printf("{\"app_bytes\":%zu,\"mod_bytes\":%zu,\"mod_arena\":%u,\"mod_ui_bytes\":%zu,"
         "\"mod_writes_bytes\":%zu,"
         "\"seq_arena\":%u,\"seq_tracks\":%d,\"seq_bytes_8\":%zu,"
         "\"seq_bytes_4\":%zu,\"seq_event_bytes\":%zu,\"seq_pending_bytes\":%zu,"
         "\"seq_ui_bytes\":%u,\"seq_ui_size\":%zu,\"seq_budget\":%u,\"seq_need\":%u,"
         "\"seq_events\":%u}\n",
         sizeof(fm1_app_t), fm1_mod_size(), FM1_APP_MOD_BYTES, sizeof(fm1_mod_ui_t),
         sizeof g_app.mod_wr, FM1_APP_SEQ_BYTES, FM1_APP_SEQ_TRACKS, fm1_seq_size(&lim8),
         fm1_seq_size(&lim4), sizeof g_app.seq_ev, sizeof g_app.seq_pend, FM1_APP_SEQ_UI_BYTES,
         sizeof(fm1_seq_ui_t),
         FM1_APP_SEQ_BUDGET,
         (unsigned)(fm1_seq_cmd_max_events(&lim8) + fm1_seq_min_events(&lim8)),
         FM1_APP_SEQ_EVENTS);
  return 0;
}

/* --log-cmds: a script line as applied, less trailing separators. */
static void log_cmd(FILE *f, uint32_t pos, const char *t, size_t k) {
  while (k && (t[k - 1] == ' ' || t[k - 1] == '\t' || t[k - 1] == ';')) --k;
  if (f && k) fprintf(f, "@%u %.*s\n", (unsigned)pos, (int)k, t);
}

/* --seq-ui: typed commands as a UI sends them; the frames they went in at. */
#define MAX_UI 64
static fm1_seq_cmd_t g_ui[MAX_UI];
static int g_ui_n, g_ui_next;
static uint64_t g_ui_frames[MAX_UI];
static int g_ui_applied;

/* Every typed command applied (the panel's and --seq-ui's), as text. */
#define MAX_UI_LOG 4096
static uint64_t g_ui_log_frame[MAX_UI_LOG];
static char *g_ui_log_text[MAX_UI_LOG];
static int g_ui_log_n;
static FILE *g_log_cmds;

static void on_cmd(void *ctx, uint64_t frame, const fm1_seq_cmd_t *c) {
  char text[1024];
  (void)ctx;
  if (g_ui_applied < MAX_UI) g_ui_frames[g_ui_applied] = frame;
  ++g_ui_applied;
  fm1_seq_cmd_format(c, text, sizeof text);
  if (g_log_cmds) fprintf(g_log_cmds, "@%llu %s\n", (unsigned long long)frame, text);
  if (g_ui_log_n < MAX_UI_LOG) {
    size_t n = strlen(text) + 1;
    char *copy = malloc(n);
    if (copy) {
      memcpy(copy, text, n);
      g_ui_log_frame[g_ui_log_n] = frame;
      g_ui_log_text[g_ui_log_n++] = copy;
    }
  }
}

static void json_string(const char *t) {
  putchar('"');
  for (; *t; ++t) {
    if (*t == '"' || *t == '\\') putchar('\\');
    putchar((unsigned char)*t < 0x20 ? '?' : *t);
  }
  putchar('"');
}

/* --format-check: every verb, written by fm1_seq_cmd_format and read back
 * by fm1_seq_parse, is the record it was: parsed from text in several
 * shapes, and made as the panel makes them (fm1_seq_cmd_make). */
static int g_fmt_records, g_fmt_failures;

static void format_round_trip(const fm1_seq_cmd_t *c) {
  char text[1024];
  fm1_seq_cmd_t back;
  ++g_fmt_records;
  fm1_seq_cmd_format(c, text, sizeof text);
  fm1_seq_parse(text, strlen(text), &back);
  if (memcmp(c, &back, sizeof back) != 0) {
    if (g_fmt_failures < 10) fprintf(stderr, "format round trip: verb %u: %s\n", c->verb, text);
    ++g_fmt_failures;
  }
}

static int format_check(void) {
  static const char *const tails[] = {
    "", " 0", " 1 -2", " 3 4 60 100", " 0 1 synth:Timbre", " 0 1 +5 -007", " x 2 _ 4",
    " 7 0 0 -1 380", " 0 1 a:b:Volume 9", " -9223372036854775808 9223372036854775807 12",
    " 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28",
  };
  int64_t args[FM1_SEQ_CMD_ARGS];
  int named = 0;
  for (unsigned i = 0; i < FM1_SEQ_CMD_ARGS; ++i) args[i] = (int64_t)i * 37 - 100;
  args[3] = INT64_MIN;
  args[4] = INT64_MAX;
  for (unsigned v = 0; v < FM1_SEQ_V_COUNT; ++v) {
    const char *name = fm1_seq_verb_name(v);
    char op[256];
    fm1_seq_cmd_t c;
    if (!name) {
      fprintf(stderr, "verb %u has no name\n", v);
      ++g_fmt_failures;
      continue;
    }
    if (v) {
      fm1_seq_parse(name, strlen(name), &c);
      if (c.verb != v) {
        fprintf(stderr, "\"%s\" parses as verb %u, not %u\n", name, c.verb, v);
        ++g_fmt_failures;
      }
      ++named;
    }
    for (size_t k = 0; k < sizeof tails / sizeof tails[0]; ++k) {
      snprintf(op, sizeof op, "%s%s", v ? name : "nosuchverb", tails[k]);
      fm1_seq_parse(op, strlen(op), &c);
      format_round_trip(&c);
    }
    for (unsigned argc = 0; argc <= FM1_SEQ_CMD_ARGS; ++argc) {
      fm1_seq_cmd_make(&c, (uint16_t)v, argc, args);
      format_round_trip(&c);
    }
  }
  printf("{\"verbs\":%d,\"records\":%d,\"failures\":%d}\n", named, g_fmt_records,
         g_fmt_failures);
  return g_fmt_failures ? 1 : 0;
}

typedef struct { int track, engine, channel; } route_t;

static int apply_routes(const route_t *r, int n, int tracks) {
  for (int k = 0; k < n; ++k) {
    if (r[k].track < 0 || r[k].track >= tracks ||
        !fm1_app_seq_route(&g_app, r[k].track, r[k].engine ? FM1_SEQ_ROUTE_ENGINE : FM1_SEQ_ROUTE_MIDI,
                           r[k].engine ? 0 : r[k].channel)) {
      fprintf(stderr, "bad --route for track %d\n", r[k].track);
      return 0;
    }
  }
  if (!n) fm1_app_seq_default_route(&g_app);
  return 1;
}

static int import_file(const char *path) {
  size_t len = 0;
  char *txt = fm1_read_file(path, &len);
  int ok = txt && fm1_app_seq_import(&g_app, txt, len);
  free(txt);
  if (!ok) fprintf(stderr, "%s: not a movy1 set\n", path);
  return ok;
}

/* ---- modulation: --mod, the .mod log and --mod-format-check (docs/16 MG3) ---- */

typedef struct {
  uint64_t frame;
  int order;
  char text[1024];
} mod_line_t;

static mod_line_t *g_mod;
static int g_mod_n, g_mod_next;
static uint32_t g_mod_seed;
static FILE *g_log_mod;

static int mod_line_cmp(const void *x, const void *y) {
  const mod_line_t *a = (const mod_line_t *)x, *b = (const mod_line_t *)y;
  if (a->frame != b->frame) return a->frame < b->frame ? -1 : 1;
  return a->order - b->order;                    /* stable, as fm1-render sorts */
}

/* --mod FILE, read as fm1-render reads it: leading blanks, an optional
 * @FRAME, the seed from a line at frame 0, lines sorted by frame. */
static int load_mod(const char *path) {
  FILE *f = fopen(path, "r");
  char buf[1024];
  if (!f) {
    fprintf(stderr, "cannot read %s\n", path);
    return 0;
  }
  while (fgets(buf, sizeof buf, f)) {
    const char *t = buf;
    uint64_t frame = 0;
    mod_line_t *l;
    size_t n;
    while (*t == ' ' || *t == '\t') ++t;
    if (*t == '@') {
      char *end = NULL;
      frame = strtoull(t + 1, &end, 10);
      if (end == t + 1) {
        fprintf(stderr, "%s: bad @FRAME: %s", path, buf);
        fclose(f);
        return 0;
      }
      t = end;
    }
    g_mod = realloc(g_mod, (size_t)(g_mod_n + 1) * sizeof *g_mod);
    if (!g_mod) return 0;
    l = &g_mod[g_mod_n];
    l->frame = frame;
    l->order = g_mod_n++;
    snprintf(l->text, sizeof l->text, "%s", t);
    n = strlen(l->text);
    while (n && (l->text[n - 1] == '\n' || l->text[n - 1] == '\r')) l->text[--n] = '\0';
    if (frame == 0) fm1_mod_script_seed(l->text, &g_mod_seed);
  }
  fclose(f);
  if (g_mod_n) qsort(g_mod, (size_t)g_mod_n, sizeof *g_mod, mod_line_cmp);
  return 1;
}

/* The --mod lines due by `upto`, as fm1-render applies them. */
static int apply_mod(uint64_t upto) {
  while (g_mod_next < g_mod_n && g_mod[g_mod_next].frame <= upto) {
    char err[256];
    if (!fm1_app_mod_line(&g_app, g_mod[g_mod_next].text, err, sizeof err)) {
      fprintf(stderr, "--mod: %s\n", err);
      return 0;
    }
    ++g_mod_next;
  }
  return 1;
}

static void log_mod_edit(void *ctx, uint64_t frame, const char *line) {
  (void)ctx;
  if (g_log_mod) fprintf(g_log_mod, "@%llu %s\n", (unsigned long long)frame, line);
}

static void log_mod_dump(void *ctx, const char *line) {
  (void)ctx;
  if (g_log_mod) fprintf(g_log_mod, "%s\n", line);
}

/* --mod-format-check: script lines written by fm1_mod_ui.c and read by
 * mod_script.c rebuild the same runtime state. */
static uint32_t g_rng = 1u;
static uint32_t rnd(uint32_t n) {
  g_rng = g_rng * 1664525u + 1013904223u;
  return n ? (g_rng >> 8) % n : 0;
}

static fm1_mod_t *g_mod2;            /* the replay's runtime */
static int g_fmt_lines, g_fmt_bad;

static void replay_line(void *ctx, const char *line) {
  const fm1_engine_t *units[FM1_APP_UNITS];
  char err[256];
  (void)ctx;
  for (int u = 0; u < FM1_APP_UNITS; ++u) units[u] = g_app.unit[u].e;
  ++g_fmt_lines;
  if (!fm1_mod_script_line(g_mod2, line, units, err, sizeof err)) {
    if (g_fmt_bad < 10) fprintf(stderr, "mod format: \"%s\": %s\n", line, err);
    ++g_fmt_bad;
  }
}

static int has_dst(const fm1_mod_slot_t *s) {
  return (s->flags & FM1_MOD_SLOT_GATE_DST) || s->dst != 0;
}

/* The runtime states the script can say are the same: kinds, bases, and
 * every slot with a destination (one without is the same as a cleared one
 * to the runtime: off, and never planned). */
static int same_mod_state(const fm1_mod_t *a, const fm1_mod_t *b, const char *what) {
  for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const int k = fm1_mod_kind_at(a, pos);
    if (k != fm1_mod_kind_at(b, pos)) {
      fprintf(stderr, "mod format (%s): position %u holds %d, not %d\n", what, pos + 1, k,
              fm1_mod_kind_at(b, pos));
      return 0;
    }
    for (unsigned i = 0; k >= 0 && i < fm1_mod_kinds[k]->n_params; ++i) {
      const float x = fm1_mod_param_base(a, pos, i), y = fm1_mod_param_base(b, pos, i);
      if (memcmp(&x, &y, sizeof x) != 0) {
        fprintf(stderr, "mod format (%s): base %u.%u %.9g vs %.9g\n", what, pos + 1, i, (double)x,
                (double)y);
        return 0;
      }
    }
  }
  for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t x, y;
    fm1_mod_get_slot(a, i, &x);
    fm1_mod_get_slot(b, i, &y);
    if (!has_dst(&x)) {
      memset(&x, 0, sizeof x);
      x.via = FM1_MOD_NONE;
    }
    if (memcmp(&x, &y, sizeof x) != 0) {
      fprintf(stderr, "mod format (%s): slot %u differs (src %u/%u dst %u:%u/%u:%u amt %d/%d "
              "ofs %d/%d via %u/%u flags %02x/%02x)\n", what, i + 1, x.src, y.src, x.dst_unit, x.dst,
              y.dst_unit, y.dst, x.amount, y.amount, x.offset, y.offset, x.via, y.via, x.flags, y.flags);
      return 0;
    }
  }
  return 1;
}

static void random_slot(const fm1_mod_ui_env_t *env, fm1_mod_slot_t *s) {
  uint8_t src[FM1_MOD_UI_MAX_SOURCES];
  fm1_mod_dest_t dst[FM1_MOD_UI_MAX_DESTS];
  const int ns = fm1_mod_ui_sources(env->m, src, FM1_MOD_UI_MAX_SOURCES);
  const int nd = fm1_mod_ui_dests(env, dst, FM1_MOD_UI_MAX_DESTS);
  const fm1_mod_dest_t *d = &dst[rnd((uint32_t)nd)];
  memset(s, 0, sizeof *s);
  s->src = src[rnd((uint32_t)ns)];
  s->via = rnd(3) ? (uint8_t)FM1_MOD_NONE : src[rnd((uint32_t)ns)];
  s->dst_unit = d->unit;
  s->dst = d->dst;
  s->amount = (int16_t)((int)rnd(32769) - 16384);
  s->offset = (int16_t)(rnd(4) ? (int)rnd(32769) - 16384 : 0);
  s->flags = (uint8_t)((rnd(4) ? FM1_MOD_SLOT_ON : 0) | (d->gate ? FM1_MOD_SLOT_GATE_DST : 0) |
                       (rnd(4) << FM1_MOD_SLOT_POL_SHIFT) |
                       (rnd(FM1_MOD_CURVE_COUNT) << FM1_MOD_SLOT_CURVE_SHIFT));
}

static int mod_format_check(void) {
  static unsigned char mem2[FM1_APP_MOD_BYTES] FM1_APP_ALIGN16;
  const char *units[FM1_APP_UNITS] = { "macro", "plate", "echo" };
  fm1_mod_ui_env_t env;
  int rounds = 0, failures = 0;
  fm1_app_init(&g_app, 44118.0f);
  fm1_app_set_lab(&g_app, 1);
  for (int u = 0; u < FM1_APP_UNITS; ++u) fm1_app_select(&g_app, u, fm1_app_find(units[u]));
  memset(&env, 0, sizeof env);
  env.m = g_app.mod;
  for (int u = 0; u < FM1_APP_UNITS; ++u) env.unit[u] = g_app.unit[u].e;
  for (int round = 0; round < 300; ++round) {
    fm1_mod_ui_t ui;
    const uint32_t seed = rnd(1000000);
    ++rounds;
    /* A random runtime written whole (the dump), and read back. */
    fm1_app_mod_reset(&g_app, seed);
    env.m = g_app.mod;
    for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      const int k = (int)rnd((uint32_t)fm1_mod_kind_count + 2u) - 1;
      fm1_mod_set_kind(g_app.mod, pos, k < (int)fm1_mod_kind_count ? k : -1);
      for (unsigned i = 0; k >= 0 && k < (int)fm1_mod_kind_count && i < fm1_mod_kinds[k]->n_params; ++i) {
        const fm1_param_t *p = &fm1_mod_kinds[k]->params[i];
        if (rnd(2)) continue;
        fm1_mod_set_param(g_app.mod, pos, i,
                          p->type == FM1_PARAM_ENUM ? p->min + (float)rnd((uint32_t)(p->max - p->min) + 1u)
                                                    : p->min + (p->max - p->min) * (float)rnd(100001) / 100000.0f);
      }
    }
    for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_slot_t s;
      if (rnd(4) == 0) continue;
      random_slot(&env, &s);
      fm1_mod_set_slot(g_app.mod, i, &s);
    }
    g_mod2 = fm1_mod_create(mem2, &g_app.host, seed);
    if (!fm1_app_mod_dump(&g_app, replay_line, NULL)) {
      fprintf(stderr, "mod format: round %d: the dump has a slot no line can say\n", round);
      ++failures;
      continue;
    }
    if (!same_mod_state(g_app.mod, g_mod2, "dump")) {
      ++failures;
      continue;
    }
    /* Edits as the panel makes them, each line applied to the replay at
     * once: slots, kinds (with their switch-off and restore), bases, moves. */
    fm1_mod_ui_init(&ui);
    env.emit = replay_line;
    for (int e = 0; e < 40; ++e) {
      const uint32_t what = rnd(10);
      const unsigned pos = rnd(FM1_MOD_POSITIONS);
      if (what < 5) {
        fm1_mod_slot_t s;
        if (rnd(5) == 0) {
          memset(&s, 0, sizeof s);
          s.via = FM1_MOD_NONE;
        } else {
          random_slot(&env, &s);
        }
        fm1_mod_ui_set_slot(&env, &ui, rnd(FM1_MOD_SLOTS), &s);
      } else if (what < 7) {
        fm1_mod_ui_set_kind(&env, &ui, pos, (int)rnd((uint32_t)fm1_mod_kind_count + 1u) - 1);
      } else if (what < 9) {
        const int k = fm1_mod_kind_at(g_app.mod, pos);
        if (k >= 0) {
          const unsigned i = rnd(fm1_mod_kinds[k]->n_params);
          const fm1_param_t *p = &fm1_mod_kinds[k]->params[i];
          fm1_mod_ui_set_param(&env, &ui, pos, i, p->min - 0.5f + (p->max - p->min + 1.0f) * (float)rnd(1001) / 1000.0f);
        }
      } else {
        fm1_mod_ui_move(&env, &ui, pos, rnd(FM1_MOD_POSITIONS));
      }
    }
    env.emit = NULL;
    if (ui.unloggable) fprintf(stderr, "mod format: round %d: an edit had no line\n", round);
    if (ui.unloggable || !same_mod_state(g_app.mod, g_mod2, "edits")) ++failures;
  }
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (g_app.unit[u].e) g_app.unit[u].e->destroy(g_app.unit[u].self);
  }
  printf("{\"rounds\":%d,\"lines\":%d,\"refused_lines\":%d,\"failures\":%d}\n", rounds, g_fmt_lines,
         g_fmt_bad, failures);
  return failures || g_fmt_bad ? 1 : 0;
}

/* The summary's "mod": the rack, every slot that is not empty (its record
 * and its MATRIX row), the pages' state and the runtime's counters. */
static void print_mod(void) {
  fm1_mod_ui_env_t env;
  fm1_mod_stats_t st;
  fm1_mod_plan_info_t plan;
  const fm1_mod_ui_t *u = &g_app.mui;
  int first = 1;
  memset(&env, 0, sizeof env);
  env.m = g_app.mod;
  for (int k = 0; k < FM1_APP_UNITS; ++k) env.unit[k] = g_app.unit[k].e;
  fm1_mod_get_stats(g_app.mod, &st);
  fm1_mod_get_plan(g_app.mod, &plan);
  printf(",\"mod\":{\"rack\":[");
  for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const int k = fm1_mod_kind_at(g_app.mod, pos);
    printf("%s\"%s\"", pos ? "," : "", k >= 0 ? fm1_mod_kinds[k]->id : "");
  }
  printf("],\"slots\":[");
  for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    char row[FM1_MOD_UI_ROW_CHARS + 1];
    if (fm1_mod_ui_empty(u, g_app.mod, i)) continue;
    fm1_mod_get_slot(g_app.mod, i, &s);
    fm1_mod_ui_row(&env, u, i, 0, row);
    printf("%s{\"slot\":%u,\"src\":%u,\"via\":%u,\"unit\":%u,\"dst\":%u,\"amount\":%d,"
           "\"offset\":%d,\"flags\":%u,\"row\":", first ? "" : ",", i + 1, s.src, s.via, s.dst_unit,
           s.dst, s.amount, s.offset, s.flags);
    json_string(row);
    printf("}");
    first = 0;
  }
  printf("],\"bases\":[");
  for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    const int k = fm1_mod_kind_at(g_app.mod, pos);
    printf("%s[", pos ? "," : "");
    for (unsigned i = 0; k >= 0 && i < fm1_mod_kinds[k]->n_params; ++i) {
      printf(i ? ",%.9g" : "%.9g", (double)fm1_mod_param_base(g_app.mod, pos, i));
    }
    printf("]");
  }
  printf("],\"pos\":%u,\"page\":%u,\"slot\":%u,\"mpage\":%u,\"picker\":%u,\"held\":%d,"
         "\"sel_lfo\":%d,\"sel_env\":%d,\"grab\":%u,\"active\":%u,\"refused\":%u,"
         "\"delayed\":%u,\"ticks\":%llu,\"writes\":%llu,\"unloggable\":%u,\"sent0\":[",
         u->pos + 1, u->page + 1, u->slot + 1, u->mpage, u->picker,
         u->held == FM1_MOD_UI_NONE ? -1 : u->held, u->sel_lfo == FM1_MOD_UI_NONE ? -1 : u->sel_lfo + 1,
         u->sel_env == FM1_MOD_UI_NONE ? -1 : u->sel_env + 1, u->grab, plan.active, plan.refused,
         plan.delayed, (unsigned long long)st.ticks, (unsigned long long)st.writes, u->unloggable);
  for (uint16_t i = 0; g_app.unit[0].e && i < g_app.unit[0].e->n_params && i < FM1_MOD_UNIT_PARAMS; ++i) {
    printf(i ? ",%.9g" : "%.9g", (double)fm1_mod_sent(g_app.mod, 0, i));
  }
  {                                    /* CHAIN's lines through the selected slot */
    char lines[FM1_MOD_UI_CHAIN_LINES][FM1_MOD_UI_ROW_CHARS + 1];
    int hl = -1;
    const int n = fm1_mod_ui_chain(&env, u, u->slot, lines, &hl);
    printf("],\"chain_hl\":%d,\"chain\":[", hl);
    for (int k = 0; k < n; ++k) {
      if (k) printf(",");
      json_string(lines[k]);
    }
  }
  printf("]}");
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
  const char *cmd_path = NULL, *seq_path = NULL, *log_path = NULL, *log_cmds_path = NULL;
  const char *mod_path = NULL;
  char log_mod_path[1024] = "";
  int tracks = -1, seconds_given = 0, rate_given = 0, n_routes = 0;
  long events_cap = -1;
  route_t routes[MAX_ROUTES];

  for (int i = 1; i < argc; ++i) {
    const char *a = argv[i];
    if (strcmp(a, "--list") == 0) {
      const char *j = fm1_app_catalog_json();
      if (!j) return 1;
      puts(j);
      return 0;
    }
    if (strcmp(a, "--sizes") == 0) return print_sizes();
    if (strcmp(a, "--format-check") == 0) return format_check();
    if (strcmp(a, "--mod-format-check") == 0) return mod_format_check();
    if (strcmp(a, "--lab") == 0) { g_lab = 1; continue; }
    if (strcmp(a, "--start") == 0) { g_start = 1; continue; }
    if (i + 1 >= argc) { usage(); return 2; }
    const char *v = argv[++i];
    /* What fm1-render needs to replay a --log-cmds file (its sidecar). */
    if (strcmp(a, "--engine") == 0 || strcmp(a, "--param") == 0 || strcmp(a, "--fx") == 0 ||
        strcmp(a, "--fx-param") == 0 || strcmp(a, "--note") == 0 || strcmp(a, "--bend") == 0 ||
        strcmp(a, "--param-at") == 0 || strcmp(a, "--seq") == 0 || strcmp(a, "--route") == 0) {
      side(a, v);
    }
    if (strcmp(a, "--screens") == 0) return run_screens(v, rate);
    else if (strcmp(a, "--panel") == 0) { if (!read_panel(v)) return 2; }
    else if (strcmp(a, "--engine") == 0) engine = v;
    else if (strcmp(a, "--out") == 0) out_path = v;
    else if (strcmp(a, "--screen") == 0) screen_path = v;
    else if (strcmp(a, "--seconds") == 0) { secs = atof(v); seconds_given = 1; }
    else if (strcmp(a, "--rate") == 0) { rate = (float)atof(v); rate_given = 1; }
    else if (strcmp(a, "--cmd") == 0) cmd_path = v;
    else if (strcmp(a, "--seq") == 0) seq_path = v;
    else if (strcmp(a, "--log-events") == 0) log_path = v;
    else if (strcmp(a, "--log-cmds") == 0) log_cmds_path = v;
    else if (strcmp(a, "--mod") == 0) mod_path = v;
    else if (strcmp(a, "--tracks") == 0) tracks = atoi(v);
    else if (strcmp(a, "--events") == 0) {      /* decimal, as fm1-render reads it */
      char *end = NULL;
      events_cap = strtol(v, &end, 10);
      if (end == v || *end || events_cap < 1 || events_cap > (long)FM1_APP_SEQ_EVENTS) {
        fprintf(stderr, "--events wants 1..%u\n", FM1_APP_SEQ_EVENTS);
        return 2;
      }
    } else if (strcmp(a, "--route") == 0) {
      char kind[16] = { 0 };
      int t = 0, ch = 0;
      const int got = sscanf(v, "%d:%15[a-z]:%d", &t, kind, &ch);
      if (n_routes >= MAX_ROUTES) { usage(); return 2; }
      if (got >= 2 && strcmp(kind, "engine") == 0) {
        routes[n_routes++] = (route_t){ t, 1, 0 };
      } else if (got == 3 && strcmp(kind, "midi") == 0 && ch >= 1 && ch <= 16) {
        routes[n_routes++] = (route_t){ t, 0, ch };
      } else {
        fprintf(stderr, "--route wants T:engine or T:midi:CH\n");
        return 2;
      }
    } else if (strcmp(a, "--seq-ui") == 0) {
      const char *colon = strchr(v, ':');
      if (!colon) { usage(); return 2; }
      add_event(atof(v), EV_SEQ_UI)->a = i;
    } else if (strcmp(a, "--seq-reset") == 0 || strcmp(a, "--seq-import") == 0) {
      const char *colon = strchr(v, ':');
      if (!colon) { usage(); return 2; }
      event_t *e = add_event(atof(v), a[6] == 'r' ? EV_SEQ_RESET : EV_SEQ_IMPORT);
      e->a = a[6] == 'r' ? atoi(colon + 1) : i;   /* the file: argv[i] after the colon */
    }
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
    } else if (strcmp(a, "--note") == 0) {
      double t, dur;
      int key, vel;
      if (sscanf(v, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) { usage(); return 2; }
      event_t *on = add_event(t, EV_NOTE);
      on->on = 1, on->a = key, on->b = vel;
      event_t *off = add_event(t + dur, EV_NOTE);
      off->on = 0, off->a = key;
    } else if (strcmp(a, "--key") == 0 || strcmp(a, "--button") == 0 || strcmp(a, "--turn") == 0) {
      const int r = add_panel(a, v);
      if (r == 0) usage();
      if (r <= 0) return 2;
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
    } else if (strcmp(a, "--select") == 0) {
      double t;
      int unit, n = 0;
      if (sscanf(v, "%lf:%d:%n", &t, &unit, &n) != 2 || !n) { usage(); return 2; }
      event_t *e = add_event(t, EV_SELECT);
      e->a = unit;
      snprintf(e->name, sizeof e->name, "%s", v + n);
    } else { usage(); return 2; }
  }

  const int use_seq = cmd_path || seq_path;
  if (g_start && (use_seq || engine || n_fx)) {
    fprintf(stderr, "--start is the whole chain: no --engine, --fx, --cmd or --seq with it\n");
    return 2;
  }
  fm1_script_t script;
  uint64_t seq_end = 0;              /* the script's run length, in frames */
  memset(&script, 0, sizeof script);
  if (use_seq) {
    char err[256];
    if (cmd_path && !fm1_script_load(cmd_path, &script, err, sizeof err)) {
      fprintf(stderr, "%s\n", err);
      return 1;
    }
    if (!cmd_path) { script.rate = 44118; script.block = 128; script.tracks = 8; }
    if (!rate_given) rate = (float)script.rate;
    if (tracks < 0) tracks = script.tracks;
    if (!seconds_given && (script.has_end || script.n)) {   /* fm1-render at --frames 64 */
      uint64_t end = script.end;
      if (!script.has_end) {
        const uint64_t last = script.cmds[script.n - 1].frame;
        end = ((last + FM1_APP_MAX_FRAMES - 1u) / FM1_APP_MAX_FRAMES + 1u) * FM1_APP_MAX_FRAMES;
      }
      secs = (double)end / rate;
      seq_end = end;
    }
    if (tracks < 1 || tracks > FM1_APP_SEQ_TRACKS) {
      fprintf(stderr, "the app's sequencer has 1..%d tracks\n", FM1_APP_SEQ_TRACKS);
      return 2;
    }
  } else if (n_routes || log_path || log_cmds_path || tracks >= 0 || events_cap > 0) {
    fprintf(stderr, "--route, --log-events, --log-cmds, --tracks and --events need --cmd or --seq\n");
    return 2;
  }
  for (int k = 0; k < g_nev; ++k) {
    if ((g_ev[k].kind == EV_SEQ_RESET || g_ev[k].kind == EV_SEQ_IMPORT ||
         g_ev[k].kind == EV_SEQ_UI) && !use_seq) {
      fprintf(stderr, "--seq-reset, --seq-import and --seq-ui need --cmd or --seq\n");
      return 2;
    }
  }

  fm1_app_init(&g_app, rate);
  if (g_lab) fm1_app_set_lab(&g_app, 1);
  if (master != 1.0f) g_replayable = 0;      /* fm1-render has no MASTER */
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
  FILE *log = NULL;
  if (use_seq) {
    /* As fm1-render: the instance at the script's track count, the set,
     * the routes given or else the default route. */
    if (fm1_app_seq_reset(&g_app, tracks) != 0) return 1;
    if (seq_path && !import_file(seq_path)) return 1;
    if (!apply_routes(routes, n_routes, tracks)) return 2;
    if (events_cap > 0) g_app.seq_host.cap = (uint32_t)events_cap;
    g_app.on_cmd = on_cmd;
    if (log_path && !(log = fopen(log_path, "w"))) {
      fprintf(stderr, "cannot write %s\n", log_path);
      return 1;
    }
    if (log_cmds_path && !(g_log_cmds = fopen(log_cmds_path, "w"))) {
      fprintf(stderr, "cannot write %s\n", log_cmds_path);
      return 1;
    }
  } else if (g_start) {
    fm1_app_default_chain(&g_app);
  } else if (g_lab) {
    fm1_app_seq_default_route(&g_app);   /* as the browser's start chain */
  }
  /* --mod: a new runtime with the file's seed and its untimed lines, after
   * the chain, as fm1-render builds its own; then the log of everything
   * that follows. */
  if (mod_path) {
    if (!load_mod(mod_path)) return 2;
    fm1_app_mod_reset(&g_app, g_mod_seed);
    if (!apply_mod(0)) return 2;
  }
  if (g_log_cmds && g_app.mod) {
    size_t n = strlen(log_cmds_path);
    if (n > 6 && strcmp(log_cmds_path + n - 6, ".verbs") == 0) n -= 6;
    snprintf(log_mod_path, sizeof log_mod_path, "%.*s.mod", (int)n, log_cmds_path);
    if (!(g_log_mod = fopen(log_mod_path, "w"))) {
      fprintf(stderr, "cannot write %s\n", log_mod_path);
      return 1;
    }
    fprintf(g_log_mod, "# The virtual FM-1's modulation (fm1-sim-render --log-cmds): its state at\n"
                       "# the start, then every edit at the block it led (fm1-render --mod).\n");
    if (!fm1_app_mod_dump(&g_app, log_mod_dump, NULL)) g_replayable = 0;
    g_app.on_mod = log_mod_edit;
  }
  for (int k = 0; k < g_nev; ++k) {
    if (g_ev[k].kind == EV_PARAM && find_param(0, g_ev[k].name) < 0) return 1;
    if (g_ev[k].kind == EV_SELECT && strcmp(g_ev[k].name, "-") != 0 &&
        fm1_app_find(g_ev[k].name) < 0) {
      fprintf(stderr, "unknown engine %s\n", g_ev[k].name);
      return 1;
    }
  }

  uint32_t total = seq_end ? (uint32_t)seq_end : (uint32_t)(secs * rate);
  float *out = calloc((size_t)total * 2 + 2, sizeof(float));
  if (!out) return 1;
  double sum2 = 0.0;
  float peak = 0.0f;
  size_t next_cmd = 0;
  const char *rest = NULL;           /* a line the event-room rule cut short */
  int implicit_play = use_seq && !cmd_path;   /* --seq alone plays the set */
  uint64_t seq_events = 0;
  if (g_log_cmds) {
    fprintf(g_log_cmds, "#! rate=%ld block=%u tracks=%d end=%u\n", lrintf(rate),
            FM1_APP_MAX_FRAMES, tracks, (unsigned)total);
  }
  for (uint32_t pos = 0; pos < total; pos += FM1_APP_MAX_FRAMES) {
    double now = pos / (double)rate;
    uint32_t n = total - pos < FM1_APP_MAX_FRAMES ? total - pos : FM1_APP_MAX_FRAMES;
    for (int k = 0; k < g_nev; ++k) {                  /* controls first, in order */
      event_t *e = &g_ev[k];
      if (e->done || e->time > now) continue;
      if (e->kind == EV_BEND) fm1_app_pitch_bend(&g_app, e->value);
      else if (e->kind == EV_PARAM) fm1_app_set_param(&g_app, 0, find_param(0, e->name), e->value);
      else if (e->kind == EV_TURN || e->kind == EV_BUTTON) {
        units_t before;
        units_now(&before);
        if (e->kind == EV_TURN) fm1_app_encoder(&g_app, e->a, e->b);
        else fm1_app_button(&g_app, e->a, e->on);
        panel_changed(&before, pos, rate);
      } else if (e->kind == EV_SELECT) {
        int idx = strcmp(e->name, "-") == 0 ? -1 : fm1_app_find(e->name);
        int r = fm1_app_select(&g_app, e->a, idx);
        if (r) fprintf(stderr, "select %s into unit %d: %d\n", e->name, e->a, r);
        g_replayable = 0;
      } else if (e->kind == EV_SEQ_RESET || e->kind == EV_SEQ_IMPORT) {
        g_replayable = 0;
        if (e->kind == EV_SEQ_RESET && fm1_app_seq_reset(&g_app, e->a) != 0) {
          fprintf(stderr, "bad --seq-reset track count %d\n", e->a);
          return 2;
        }
        if (e->kind == EV_SEQ_IMPORT && !import_file(strchr(argv[e->a], ':') + 1)) return 1;
        rest = NULL;                   /* what was queued went with the instance */
        if (!n_routes) fm1_app_seq_default_route(&g_app);
      } else if (e->kind == EV_SEQ_UI) {
        const char *op = strchr(argv[e->a], ':') + 1;
        if (g_ui_n >= MAX_UI) { usage(); return 2; }
        fm1_seq_parse(op, strlen(op), &g_ui[g_ui_n++]);
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
          g_replayable = 0;                    /* key notes are logged from S5 */
        } else {
          continue;
        }
        e->done = 1;
      }
    }
    while (g_ui_next < g_ui_n) {       /* typed commands, in order, until one is BUSY */
      if (fm1_app_seq_cmd(&g_app, &g_ui[g_ui_next]) == FM1_APP_SEQ_BUSY) break;
      ++g_ui_next;
    }
    if (use_seq) {                     /* lines due now, after the panel and notes */
      for (;;) {
        const char *t;
        if (implicit_play) {
          t = "play";
          implicit_play = 0;
        } else if (rest) {
          t = rest;
        } else if (next_cmd < script.n && script.cmds[next_cmd].frame <= pos) {
          if (script.cmds[next_cmd].snap) { ++next_cmd; continue; }   /* fm1-seq's */
          t = script.cmds[next_cmd++].ops;
        } else {
          break;
        }
        const size_t len = strlen(t);
        const size_t k = fm1_app_seq_line(&g_app, t, len);
        log_cmd(g_log_cmds, pos, t, k);
        rest = k < len ? t + k : NULL;
        if (rest) break;
      }
    }
    if (mod_path && !apply_mod(pos)) return 2;     /* as fm1-render, before the block */
    const float *b = fm1_app_render(&g_app, n);
    if (use_seq) {
      uint32_t n_ev = 0;
      const fm1_seq_ev_t *ev = fm1_app_seq_events(&g_app, &n_ev);
      for (uint32_t k = 0; log && k < n_ev; ++k) {
        fm1_script_log_event(log, pos / FM1_APP_MAX_FRAMES, pos, &ev[k]);
      }
      seq_events += n_ev;
    }
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
  if (g_app.mui.unloggable) g_replayable = 0;    /* a modulation edit no line can say */
  printf(",\"lab\":%d,\"replayable\":%d", g_lab, g_replayable);
  if (g_app.mod) print_mod();
  if (g_lab) {
    printf(",\"seq_view\":{\"track\":%u,\"step\":%u,\"clip_playing\":%u,\"playing\":%u,"
           "\"knob\":%d,\"key_leds\":%u}",
           (unsigned)g_app.ui.track, (unsigned)g_app.ui.step, (unsigned)g_app.ui.clip_playing,
           (unsigned)g_app.ui.playing, (int)g_app.ui.knob, (unsigned)fm1_seq_ui_key_leds(&g_app.ui));
  }
  if (use_seq) {
    fm1_seq_stats_t st;
    int seq_sounding = 0;
    size_t left = (rest ? 1u : 0u);
    for (size_t k = next_cmd; k < script.n; ++k) left += !script.cmds[k].snap;
    for (int n = 0; n < 128; ++n) seq_sounding += g_app.seq_note_count[n];
    fm1_seq_get_stats(g_app.seq, &st);
    printf(",\"seq_bytes\":%zu,\"seq_events\":%llu,\"seq_notes_to_engine\":%llu,"
           "\"seq_locks_to_engine\":%llu,\"seq_refused\":%lu,\"seq_dropped\":%llu,"
           "\"seq_max_block_events\":%lu,\"seq_splits\":%llu,\"seq_held\":%llu,"
           "\"seq_busy\":%llu,\"seq_lines_left\":%zu,\"seq_sounding\":%d,"
           "\"seq_ui_left\":%d,\"seq_ui_frames\":[",
           fm1_seq_size(&g_app.seq_lim), (unsigned long long)seq_events,
           (unsigned long long)g_app.seq_host.notes_to_engine,
           (unsigned long long)g_app.seq_host.locks_to_engine, (unsigned long)st.refused,
           (unsigned long long)fm1_app_seq_dropped(&g_app), (unsigned long)g_app.seq_host.max_n,
           (unsigned long long)g_app.seq_host.splits, (unsigned long long)g_app.seq_held,
           (unsigned long long)g_app.seq_busy, left, seq_sounding, g_ui_n - g_ui_next);
    for (int k = 0; k < g_ui_applied && k < MAX_UI; ++k) {
      printf(k ? ",%llu" : "%llu", (unsigned long long)g_ui_frames[k]);
    }
    printf("],\"seq_ui_cmds\":[");
    for (int k = 0; k < g_ui_log_n; ++k) {
      printf(k ? ",[%llu," : "[%llu,", (unsigned long long)g_ui_log_frame[k]);
      json_string(g_ui_log_text[k]);
      printf("]");
      free(g_ui_log_text[k]);
    }
    printf("]");
    if (log) fclose(log);
    if (g_log_cmds) fclose(g_log_cmds);
    if (g_log_mod) fclose(g_log_mod);
    fm1_script_free(&script);
    if (log_cmds_path) {               /* the sidecar: FILE.verbs -> FILE.args */
      char path[1024];
      size_t n = strlen(log_cmds_path);
      FILE *f;
      if (n > 6 && strcmp(log_cmds_path + n - 6, ".verbs") == 0) n -= 6;
      snprintf(path, sizeof path, "%.*s.args", (int)n, log_cmds_path);
      if (!(f = fopen(path, "w"))) {
        fprintf(stderr, "cannot write %s\n", path);
        return 1;
      }
      for (int k = 0; k < g_nside; ++k) fprintf(f, "%s\n%s\n", g_side_flag[k], g_side_value[k]);
      if (log_mod_path[0]) fprintf(f, "--mod\n%s\n", log_mod_path);
      fclose(f);
    }
  }
  for (int k = 0; k < g_nside; ++k) free(g_side_value[k]);
  printf("}\n");
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    if (g_app.unit[u].e) g_app.unit[u].e->destroy(g_app.unit[u].self);
  }
  free(out);
  return 0;
}

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
 *   --sysex FILE        DX7 voices from a .syx file into FM6's user bank
 *                       (fm1_app_dx7_load), after --engine is loaded and
 *                       before its --param values, as fm1-render --sysex
 *                       loads them; several in order
 *   --sysex-play FILE   the same, then as the page does after a load: the
 *                       current sound plays the first voice loaded
 *                       (fm1_app_dx7_play; becomes FM6 if it is not). The
 *                       summary gets "dx7": each file's result and the 32
 *                       user slots' names as the Patch list shows them
 *   --screen FILE.ppm   the screen after the render, as a PPM image
 *   --screens DIR       draw every page of every engine and effect at its
 *                       defaults, minima, maxima and list values, plus the
 *                       global page and every popup, check each for layout
 *                       faults (fm1_tft_check_layout with FM1_APP_LAYOUT_GAP,
 *                       and truncated text), and write the representative
 *                       ones to DIR as PPM
 *   --list              the catalogue JSON
 *   --sizes             the sequencer's memory figures and sizeof(fm1_app_t)
 *   --start             the browser's start chain (fm1_app_default_chain)
 *                       in place of --engine: Macro, Plate, the default
 *                       route, every other track on Sound 1 and the demo
 *                       pattern
 *   --panel FILE        panel input from a file: one --key, --button,
 *                       --turn or --note (MIDI IN) flag and its value per
 *                       line ('#' comments)
 *   --format-check      every verb through fm1_seq_cmd_format and back
 *                       through fm1_seq_parse; prints JSON, exit 1 on a
 *                       difference
 *   --lock-check        every parameter of every engine on the lock UI's
 *                       7-bit grid (docs/15 S8): value7 against lock_value,
 *                       a knob step, the lane label; JSON, exit 1 on a fault
 *   --mod FILE          modulation as fm1-render --mod FILE plays it
 *                       (engines/host/mod_script.h): a new runtime with the
 *                       file's seed, its untimed lines after the chain is
 *                       set up, `@FRAME` lines at the first block starting
 *                       there (fm1_app_mod_reset, fm1_app_mod_line)
 *   --mod-format-check  random slots, bases and racks written as script
 *                       lines (fm1_mod_ui.h) and read back by mod_script.c
 *                       into a second runtime: the same records; JSON, exit
 *                       1 on a difference
 *   --font-check        the three text faces (fm1_tft.h): metrics, every
 *                       character as drawn, logged boxes, widths, the 4 px
 *                       rule between faces, multi-colour runs; JSON, exit 1
 *                       on a fault
 *   --font-sheet FILE.ppm  both Spleen faces on one screen, checked; JSON
 *
 * The sequencer, with fm1-render's meaning for its flags (engines/host/
 * render.cc): --cmd FILE plays a timed verb script, --seq FILE.movy1 loads a
 * set first (alone, it plays from the start), --tracks N (1..8; else the
 * script's header), --route T:engine|T:midi:CH, --events N (the bridge's
 * room, at most the app's 272) and --log-events FILE.jsonl. Rate and the run
 * length come from the script as fm1-render takes them at --frames 64: the
 * app's blocks are always 64 frames. Script lines apply at the first block
 * starting at or after their frame, after the panel and notes, through
 * fm1_app_seq_line; a line the event-room rule cuts short is finished at
 * the next block. With no --route the default-route rule applies, as in
 * fm1-render. --log-cmds FILE writes the lines as they were applied, every
 * typed command (the panel's, --seq-ui's) as fm1_seq_cmd_format writes it,
 * and every live note the app gave the sequencer (a note no step took,
 * from a key outside SEQ mode or MIDI IN: docs/15 S5) as the
 * `non` or `nof` op fm1-render applies the same way, each at the block it
 * led, as a verb script (header `#! rate
 * block=64 tracks end`, then `@<block start> <ops>`), and next to it a
 * sidecar, FILE less `.verbs` plus `.args`: the run's --engine, --param,
 * --fx, --fx-param, --note, --bend, --param-at, --fx-param-at, --seq and
 * --route arguments, one per line, after `--slots` (the app routes tracks
 * to its sound units by route index), then a --param-at for every sound
 * parameter the panel changed, at mid-block (docs/15 §6.3). With
 * modulation running (always, unless its runtime did not fit) it also
 * writes FILE less `.verbs` plus `.mod`: the
 * runtime's whole state before the first block (fm1_app_mod_dump) and every
 * edit after it, the panel's and --mod's timed lines, as `@<block start>
 * <line>`; the sidecar then ends with `--mod` and that file (docs/16 MG3).
 * So
 *   fm1-render --cmd FILE.verbs $(arguments in FILE.args)
 * renders the same samples ("two-step parity"), unless the summary says
 * "replayable":0: the panel or --select changed the sound or an effect,
 * MASTER was not at full gain, --seq-reset or --seq-import ran, a
 * modulation edit had no script line (the effects swapped places, a
 * per-voice cable), or notes in one block went to the sound in an order
 * fm1-render cannot replay. A
 * key that played the sound (outside SEQ mode) is in the sidecar as a
 * --note at mid-block times, written at its press, so keys keep their
 * order; a MIDI IN note played after a key's in the same block would not,
 * and makes the run not replayable. In SEQ mode the keys play nothing, and
 * what they did is in the script.
 *
 * Multi-sound (docs/15 §3.16), as fm1-render takes it: --sound K:ID loads
 * sound unit K (1..3), --sound-param K:NAME=V, --insert K:ID (the next
 * insert slot of unit K, 0..3) and --insert-param K:NAME=V, --level K:PCT,
 * and the timed --sound-note K:T:KEY:VEL:DUR, --sound-param-at K:T:NAME=V
 * and --level-at K:T:PCT; --slots is accepted and implied (the sidecar
 * always says it, since the app routes tracks by slot). Keys and MIDI IN
 * play the current sound: a note on a sound unit
 * other than 0 goes into the sidecar as --sound-note, a knob turn on its
 * page as --sound-param-at, a level on the Mix page as --level-at; a change
 * of an insert or of the sound units, a bend on another sound, or a note-off
 * that would release another unit's note of the same pitch makes the run
 * not replayable. --unit-route T:TRACK:SOUND calls fm1_app_unit_route at
 * time T (stage S6's API), whose typed `route` goes into the --log-cmds
 * file as the panel's commands do; if the app is busy it is sent again
 * after each render until it goes in.
 *
 * The arpeggiator, and the other MIDI effects (engine API v3), as fm1-render
 * takes them: --mfx K:ID switches sound unit K's MIDI-FX slot on from the
 * start with effect ID in it (the arp, or another, which then takes the
 * slot: fm1_app_mfx_select; K:ID:off leaves it bypassed, as the app
 * starts), --mfx-param K:NAME=V sets one of its parameters, and the timed
 * --mfx-param-at K:T:NAME=V and --mfx-on-at K:T:0|1 change one or switch it
 * (J, the chain's slot, is 1: the app has its MIDI effect there only).
 * --log-mfx FILE.jsonl writes what the effects sent their sounds, as
 * fm1-render's does. With --log-cmds every change of a slot (the flags',
 * ARP's tap and hold, the ARP pages' knobs and presets) goes into the
 * sidecar, at the block it led: --mfx K:ID:off at the sound's first, then
 * --mfx-on-at and --mfx-param-at at mid-block, where fm1-render applies
 * them before the block's notes, as the app took them. An effect put in a
 * slot after that cannot be replayed (fm1-render has no such flag).
 *
 * Test hooks: --seq-reset T:N and --seq-import T:FILE recreate the instance or import a set at time T, as a
 * UI would (then the default route, unless --route was given); --seq-ui
 * T:OP sends one op as a typed command at time T, as the panel will
 * (fm1_app_seq_cmd), and sends it again after each render while the app
 * answers BUSY.
 *
 * The project key (owner, 2026-10-06): the summary's "key" is the app's
 * (the set's, fm1_app_project_key) and "glo_page" the global page shown;
 * with a sequencer script "seq_key" says it again beside fm1-render's own
 * "seq_key", which a replay of the panel's typed `key` commands must match.
 *
 * Prints one line of JSON. Test code: C99 with stdio. MIT licence.
 */
#include "fm1_app.h"
#include "fm1_look.h"
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
  EV_SEQ_UI, EV_LEVEL, EV_UNIT_ROUTE, EV_MFX_ON, EV_MFX_PARAM
} ev_kind_t;

typedef struct {
  double time;
  ev_kind_t kind;
  int on;              /* note/key/button: 1 down, 0 up */
  int a, b;            /* note/key and velocity; encoder/button id and delta */
  float value;
  char name[32];
  int side;            /* note: its --note in the replay's sidecar, index + 1; 0 none */
  int done;
  int sound;           /* note, param, level: its sound unit; -1 a note on the current one */
  int played;          /* a note-off of the current sound's: where its note-on went */
} event_t;

static fm1_app_t g_app;
static event_t g_ev[MAX_EVENTS];
static int g_nev;
static int g_start;                  /* --start */
static int g_replayable = 1;         /* fm1-render can replay --log-cmds */

static void usage(void) {
  fprintf(stderr,
          "usage: fm1-sim-render --list | --screens DIR |\n"
          "       [--engine ID [--param NAME=V]...] [--fx ID [--fx-param NAME=V]...]...\n"
          "       [--note T:KEY:VEL:DUR] [--bend T:ST] [--param-at T:NAME=V]\n"
          "       [--fx-param-at T:K:NAME=V]\n"
          "       [--key T:KEY:VEL:DUR] [--button T:NAME[:DUR]] [--turn T:ENC:DELTA]\n"
          "       [--select T:UNIT:ID|-] [--sysex FILE.syx]... [--sysex-play FILE.syx]\n"
          "       [--master P] [--seconds S] [--rate HZ] [--out F.wav] [--screen F.ppm]\n"
          "       [--cmd FILE] [--seq FILE.movy1] [--tracks N] [--route T:engine|T:midi:CH]...\n"
          "       [--events N] [--log-events FILE.jsonl] [--log-cmds FILE.verbs]\n"
          "       [--seq-reset T:N] [--seq-import T:FILE.movy1] [--seq-ui T:OP]\n"
          "       [--panel FILE] [--start] [--mod FILE]\n"
          "       [--sound K:ID [--sound-param K:NAME=V]...] [--insert K:ID\n"
          "       [--insert-param K:NAME=V]...] [--level K:PCT] [--slots]\n"
          "       [--sound-note K:T:KEY:VEL:DUR] [--sound-param-at K:T:NAME=V] [--level-at K:T:PCT]\n"
          "       [--unit-route T:TRACK:SOUND]\n"
          "       [--mfx K:arp[:off] [--mfx-param K:NAME=V]...] [--mfx-param-at K:T:NAME=V]\n"
          "       [--mfx-on-at K:T:0|1] [--log-mfx FILE.jsonl]\n"
          "       | --sizes | --format-check | --lock-check | --mod-format-check\n"
          "       | --font-check | --font-sheet FILE.ppm\n");
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
  e->sound = kind == EV_NOTE ? -1 : 0;
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

/* --key T:KEY:VEL:DUR, --button T:NAME[:DUR], --turn T:ENCODER:DELTA or, in
 * a --panel file, --note T:KEY:VEL:DUR (a note at MIDI IN, which the replay
 * gets in the sidecar): 1, 0 for a malformed value, -1 for an unknown name
 * (reported). */
static int add_panel(const char *flag, const char *v) {
  if (strcmp(flag, "--key") == 0 || strcmp(flag, "--note") == 0) {
    const ev_kind_t kind = flag[2] == 'k' ? EV_KEY : EV_NOTE;
    double t, dur;
    int key, vel;
    if (sscanf(v, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) return 0;
    event_t *on = add_event(t, kind);
    on->on = 1, on->a = key, on->b = vel;
    event_t *off = add_event(t + dur, kind);
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

static void side(const char *flag, const char *value);
static void side_note_pair(void);

/* --panel FILE: one --key, --button, --turn or --note and its value per line. */
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
    if (strcmp(p, "--key") != 0 && strcmp(p, "--button") != 0 && strcmp(p, "--turn") != 0 &&
        strcmp(p, "--note") != 0) {
      fprintf(stderr, "%s:%d: want --key, --button, --turn or --note\n", path, lineno);
      ok = 0;
    } else if (add_panel(p, v) <= 0) {
      fprintf(stderr, "%s:%d: bad %s %s\n", path, lineno, p, v);
      ok = 0;
    } else if (strcmp(p, "--note") == 0) {
      side("--note", v);                   /* the replay plays it as MIDI IN did */
      side_note_pair();
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

/* The --note just added to the sidecar replays the last two events, a
 * note's on and off. */
static void side_note_pair(void) { g_ev[g_nev - 2].side = g_ev[g_nev - 1].side = g_nside; }

/* A key that played the sound: its --note goes into the sidecar at its press,
 * so the replay starts notes in the app's order, and gets its length at the
 * release. */
static int g_key_side[FM1_APP_KEYS];          /* sidecar index + 1, 0: none */
static double g_key_t0[FM1_APP_KEYS];

static void key_note_text(int key, double dur) {
  char buf[96];
  const int k = g_key_side[key] - 1;
  const int snd = g_app.key_sound[key];
  if (snd) {                                /* a key on another sound unit */
    g_side_flag[k] = "--sound-note";
    snprintf(buf, sizeof buf, "%d:%.9f:%u:%u:%.9f", snd, g_key_t0[key], (unsigned)g_app.key_note[key],
             (unsigned)g_app.key_vel[key], dur);
  } else {
    snprintf(buf, sizeof buf, "%.9f:%u:%u:%.9f", g_key_t0[key], (unsigned)g_app.key_note[key],
             (unsigned)g_app.key_vel[key], dur);
  }
  free(g_side_value[k]);
  g_side_value[k] = malloc(strlen(buf) + 1);
  if (!g_side_value[k]) exit(2);
  memcpy(g_side_value[k], buf, strlen(buf) + 1);
}

/* After a key edge at block `pos`: a note it started or ended. Times sit at
 * mid-block (docs/15 §6.3), where fm1-render applies them at this block. */
static void key_logged(int key, int was_down, uint32_t pos, float rate) {
  const double t = pos ? (pos - 32.0) / rate : 0.0;
  if (!was_down && g_app.key_down[key]) {
    side("--note", "0:0:0:0");
    g_key_side[key] = g_nside;
    g_key_t0[key] = t;
    key_note_text(key, 3600.0);            /* still held at the end: never released */
  } else if (was_down && !g_app.key_down[key] && g_key_side[key]) {
    key_note_text(key, t - g_key_t0[key]);
    g_key_side[key] = 0;
  }
}

/* The units before a panel event, to see what it changed. */
typedef struct {
  int index[FM1_APP_UNITS];
  float value[FM1_APP_UNITS][FM1_APP_MAX_PARAMS];
  float level[FM1_APP_SOUNDS];
} units_t;

static void units_now(units_t *u) {
  for (int k = 0; k < FM1_APP_UNITS; ++k) {
    u->index[k] = g_app.unit[k].index;
    memcpy(u->value[k], g_app.unit[k].value, sizeof u->value[k]);
  }
  memcpy(u->level, g_app.level, sizeof u->level);
}

/* After a panel event in the block at `pos`: a sound parameter it changed
 * replays as --param-at at mid-block (--sound-param-at for another sound
 * unit), where fm1-render applies it at the same block start (docs/15
 * §6.3), and a level on the Mix page as --level-at; a new sound or effect,
 * or an effect's parameter, cannot be replayed. */
static void panel_changed(const units_t *b, uint32_t pos, float rate) {
  const double t = pos ? (pos - 32.0) / rate : 0.0;
  int sound_unit[FM1_APP_UNITS];
  for (int k = 0; k < FM1_APP_UNITS; ++k) sound_unit[k] = -1;
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) sound_unit[fm1_app_sound_unit(k)] = k;
  for (int k = 0; k < FM1_APP_UNITS; ++k) {
    if (g_app.unit[k].index != b->index[k]) g_replayable = 0;
    if (sound_unit[k] < 0 && memcmp(g_app.unit[k].value, b->value[k], sizeof b->value[k]) != 0) {
      g_replayable = 0;
    }
  }
  if (!g_replayable) return;
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    const int u = fm1_app_sound_unit(k);
    const fm1_engine_t *e = g_app.unit[u].e;
    char buf[128];
    if (g_app.level[k] != b->level[k]) {
      snprintf(buf, sizeof buf, "%d:%.9f:%.9g", k, t, (double)g_app.level[k]);
      side("--level-at", buf);
    }
    for (uint16_t i = 0; e && i < e->n_params; ++i) {
      if (g_app.unit[u].value[i] == b->value[u][i]) continue;
      if (k) {
        snprintf(buf, sizeof buf, "%d:%.9f:%s=%.9g", k, t, e->params[i].name,
                 (double)g_app.unit[u].value[i]);
        side("--sound-param-at", buf);
      } else {
        snprintf(buf, sizeof buf, "%.9f:%s=%.9g", t, e->params[i].name, (double)g_app.unit[u].value[i]);
        side("--param-at", buf);
      }
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
static long g_face_boxes[FM1_TFT_FONTS];   /* visible text boxes by face, every screen */

/* A logged box's kind for a fault report: a graphic, or text in its face. */
static const char *box_kind(const fm1_tft_box_t *b) {
  static const char *const kText[FM1_TFT_FONTS] = { "MAIN text", "MID text", "SMALL text" };
  if (!b) return "-";
  if (b->kind == FM1_BOX_GRAPHIC) return "graphic";
  return b->font < FM1_TFT_FONTS ? kText[b->font] : "text";
}

static void check_screen(const char *name, const char *dir, int save) {
  int report[8];
  fm1_app_draw_checked(&g_app);
  int n = fm1_tft_check_layout(&g_app.tft, FM1_APP_LAYOUT_GAP, report, 4);
  ++g_screens;
  /* Every text box is in one of the three faces, at that face's height:
   * nothing smaller than SMALL (Spleen 6 x 12) reaches the screen. */
  for (int i = 0; i < g_app.tft.n_boxes; ++i) {
    const fm1_tft_box_t *b = &g_app.tft.boxes[i];
    if (b->hidden || b->kind != FM1_BOX_TEXT) continue;
    if (b->font >= FM1_TFT_FONTS || b->h != fm1_tft_metrics((fm1_tft_font_t)b->font)->height) {
      fprintf(stderr, "layout fault in %s: text box %d in face %d, %d px tall\n", name, i, b->font, b->h);
      ++g_faults;
      continue;
    }
    ++g_face_boxes[b->font];
  }
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
        fprintf(stderr, "layout fault in %s: box %d (%s %d,%d %dx%d) vs box %d (%s %d,%d %dx%d)\n",
                name, i, box_kind(a), a ? a->x : 0, a ? a->y : 0, a ? a->w : 0, a ? a->h : 0, j,
                box_kind(b), b ? b->x : 0, b ? b->y : 0, b ? b->w : 0, b ? b->h : 0);
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

/* ---- --screens: FM6's user bank (the page's "Load DX7 patches") ------- */

static void expect(int ok, const char *what);

/* A single-voice dump (VCED, 163 bytes) of a plain voice: the first
 * operator alone at ratio `coarse`, named `name` (padded to 10). */
static size_t dx7_vced(uint8_t *m, const char *name, int coarse) {
  uint8_t *d = m + 6;
  unsigned sum = 0;
  size_t n = strlen(name);
  m[0] = 0xF0; m[1] = 0x43; m[2] = 0x00; m[3] = 0x00; m[4] = 0x01; m[5] = 0x1B;
  memset(d, 0, FM1_DX7_VCED_BYTES);
  for (int op = 0; op < 6; ++op) {          /* stored sixth first */
    uint8_t *o = d + 21 * op;
    for (int i = 0; i < 4; ++i) {
      o[i] = 99;
      o[4 + i] = i == 3 ? 0 : 99;
    }
    o[8] = 39;                              /* break point C3 */
    o[16] = op == 5 ? 99 : 0;               /* output level: the first operator only */
    o[18] = (uint8_t)coarse;
    o[20] = 7;                              /* detune: none */
  }
  for (int i = 0; i < 4; ++i) { d[126 + i] = 99; d[130 + i] = 50; }   /* pitch EG: flat */
  d[136] = 1; d[137] = 35; d[141] = 1; d[143] = 3; d[144] = 24;       /* LFO, transpose */
  for (size_t i = 0; i < FM1_DX7_NAME_BYTES; ++i) d[145 + i] = (uint8_t)(i < n ? name[i] : ' ');
  for (unsigned i = 0; i < FM1_DX7_VCED_BYTES; ++i) sum += d[i];
  m[6 + FM1_DX7_VCED_BYTES] = (uint8_t)((0x80u - (sum & 0x7Fu)) & 0x7Fu);
  m[7 + FM1_DX7_VCED_BYTES] = 0xF7;
  return FM1_DX7_VCED_BYTES + 8u;
}

/* Every user slot loaded with a 10-character name (the longest a voice
 * has) and shown: HOME's model line and Patch row at each, the ALGORITHM
 * popup, SEQ mode's hint line; the load popups for one voice, 32, two runs
 * that wrap past User 32, and both refusals. */
static void dx7_screens(const char *dir) {
  static uint8_t file[32 * (FM1_DX7_VCED_BYTES + 8u)];
  char name[64], voice[16];
  size_t len = 0;
  int n;
  fm1_app_select(&g_app, 0, fm1_app_find("dx7"));
  g_app.mode = FM1_MODE_HOME;
  g_app.page = 0;
  g_app.dx7.next = 0;
  for (int k = 0; k < 32; ++k) {
    snprintf(voice, sizeof voice, "WIDE NAM%02d", k + 1);
    len += dx7_vced(file + len, voice, 1 + k % 4);
  }
  n = fm1_app_dx7_load(&g_app, file, len, NULL);
  expect(n == 32 && g_app.dx7.next == 0, "32 single voices did not fill User 1-32");
  check_screen("dx7-popup-loaded-32", dir, 1);
  g_app.popup_lines = 0;
  for (int k = 0; k < 32; ++k) {
    expect(strcmp(fm1_app_dx7_name(&g_app, (unsigned)k), "") != 0 &&
           strlen(fm1_app_dx7_name(&g_app, (unsigned)k)) == 10, "a user slot's name");
    fm1_app_set_param(&g_app, 0, g_app.dx7.patch, (float)(FM1_APP_DX7_PATCHES - 32 + k));
    snprintf(name, sizeof name, "dx7-home-user-%d", k + 1);
    check_screen(name, dir, k == 31);
  }
  fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -1);          /* the popup names it */
  check_screen("dx7-popup-algorithm-user", dir, 1);
  expect(g_app.popup_total == FM1_APP_DX7_PATCHES && g_app.popup_mark >= 0 &&
         strcmp(g_app.popup[g_app.popup_mark], fm1_app_dx7_name(&g_app, 30)) == 0,
         "ALGORITHM's popup names User 31");
  g_app.popup_lines = 0;
  fm1_app_button(&g_app, FM1_BTN_SEQ, 1);                  /* SEQ mode's hint line */
  fm1_app_button(&g_app, FM1_BTN_SEQ, 0);
  check_screen("dx7-seq-user", dir, 0);
  fm1_app_button(&g_app, FM1_BTN_HOME, 1);
  fm1_app_button(&g_app, FM1_BTN_HOME, 0);
  len = dx7_vced(file, "ONE VOICE", 2);
  n = fm1_app_dx7_load(&g_app, file, len, NULL);
  expect(n == 1 && g_app.dx7.next == 1, "a single voice did not go to User 1");
  check_screen("dx7-popup-loaded-1", dir, 1);
  g_app.dx7.next = 30;                                     /* four from User 31: they wrap */
  len = 0;
  for (int k = 0; k < 4; ++k) len += dx7_vced(file + len, "WRAPPED", 3);
  n = fm1_app_dx7_load(&g_app, file, len, NULL);
  expect(n == 4 && g_app.dx7.next == 2, "four voices from User 31 did not wrap");
  check_screen("dx7-popup-loaded-wrap", dir, 1);
  g_app.dx7.next = 31;                                     /* two from User 32: "User 32, 1" */
  len = 0;
  for (int k = 0; k < 2; ++k) len += dx7_vced(file + len, "WRAPPED", 3);
  n = fm1_app_dx7_load(&g_app, file, len, NULL);
  expect(n == 2 && g_app.dx7.next == 1 && strcmp(g_app.popup[1], "User 32, 1") == 0,
         "two voices from User 32 did not wrap to User 1");
  check_screen("dx7-popup-loaded-wrap-32", dir, 1);
  memset(file, 0x41, 300);                                 /* no SysEx at all */
  n = fm1_app_dx7_load(&g_app, file, 300, NULL);
  expect(n == FM1_APP_DX7_NONE, "a file of text loaded voices");
  check_screen("dx7-popup-none", dir, 1);
  n = fm1_app_dx7_load(&g_app, file, FM1_APP_DX7_FILE_MAX + 1u, NULL);
  expect(n == FM1_APP_DX7_TOO_BIG, "a file past the limit was read");
  check_screen("dx7-popup-too-big", dir, 1);
  g_app.popup_lines = 0;
}

/* ---- --screens: SEQ mode's Track view (docs/15 §4, S3) ----------------- */

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

/* The rows the open list's window holds: its face's (fm1_panel.h); a
 * modulation picker's window, which fm1_mod_ui fills, is sized for the face
 * the app draws it in (FM1_LIST_FACE_KIND, FM1_LIST_FACE_DEST). */
static int window_rows(void) {
  return fm1_list_rows(g_app.popup_face);
}

/* A knob's list is in the face audit D9 gives it: MAIN when the whole list
 * fits it (FM1_LIST_ROWS entries or fewer, every one within MAIN's line),
 * else MID. */
static void expect_knob_list_face(int total, const char *what) {
  int want = total <= FM1_LIST_ROWS && g_app.popup_lines == total ? FM1_LIST_MAIN : FM1_LIST_MID;
  for (int i = 0; want == FM1_LIST_MAIN && i < g_app.popup_lines; ++i) {
    if ((int)strlen(g_app.popup[i]) > fm1_list_chars(FM1_LIST_MAIN)) want = FM1_LIST_MID;
  }
  expect(g_app.popup_face == want, what);
}

/* The open popup is a list `title` (NULL: any) with entry `sel` of `total`
 * chosen, in the window fm1_list_first gives for the rows its face holds
 * (window_rows): the choice on the third row where it can be, the window
 * never past either end. */
static void expect_window(const char *what, const char *title, int total, int sel) {
  const int face_rows = window_rows();
  const int first = fm1_list_first(total, sel, face_rows);
  const int rows = total - first < face_rows ? total - first : face_rows;
  if (g_app.popup_total != total || g_app.popup_first != first || g_app.popup_lines != rows ||
      g_app.popup_mark != sel - first || (title && strcmp(g_app.popup_title, title) != 0)) {
    fprintf(stderr,
            "screens: %s: list \"%s\" %d of %d from %d, %d lines (want \"%s\" %d of %d from %d, "
            "%d lines)\n", what, g_app.popup_title, g_app.popup_first + g_app.popup_mark,
            g_app.popup_total, g_app.popup_first, g_app.popup_lines, title ? title : "*", sel,
            total, first, rows);
    ++g_faults;
  }
}

/* Saved as NAME-top, -middle and -end: the list's first, a middle and its
 * last entry. */
static void check_list_screen(const char *name, const char *dir, int k, int total, int save) {
  char path[128];
  const char *at = k == 0 ? "top" : (k == total / 2 ? "middle" : (k == total - 1 ? "end" : NULL));
  if (at) snprintf(path, sizeof path, "%s-%s", name, at);
  else snprintf(path, sizeof path, "%s-%d", name, k);
  check_screen(path, dir, save && at != NULL);
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

/* ---- --screens: the ARP pages --------------------------------------------- */

/* Renders until ARP's hold has latched (FM1_APP_ARP_HOLD_S and a block). */
static void hold_arp(float rate) {
  fm1_app_button(&g_app, FM1_BTN_ARP, 1);
  for (int k = 0; k < (int)(FM1_APP_ARP_HOLD_S * rate / 64.0f) + 2; ++k) fm1_app_render(&g_app, 64);
}

static void arp_screens(const char *dir, float rate) {
  char name[128];
  const fm1_engine_t *e = fm1_app_arp_engine();
  int pages = 1;
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  expect(e && !fm1_app_arp_on(&g_app, 0), "the arp is on before ARP");
  if (!e) return;
  press(FM1_BTN_ARP);                         /* a tap: on, and the pages */
  expect(g_app.mode == FM1_MODE_ARP && fm1_app_arp_on(&g_app, 0), "an ARP tap does not open its pages");
  check_screen("popup-arp-on", dir, 1);
  g_app.popup_lines = 0;
  fm1_app_note_on(&g_app, 57, 100);
  for (int k = 0; k < 60; ++k) fm1_app_render(&g_app, 64);   /* a live scope */
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
  }
  for (int page = 0; page < pages; ++page) {   /* every page, at its extremes and every entry */
    for (int k = 0; k < page; ++k) fm1_app_encoder(&g_app, FM1_ENC_SELECT, 1);
    expect(g_app.arp_page == page, "SELECT does not step the ARP pages");
    snprintf(name, sizeof name, "arp-p%d", page + 1);
    check_screen(name, dir, 1);
    for (int pass = 0; pass < 2; ++pass) {
      for (uint16_t i = 0; i < e->n_params; ++i) {
        fm1_app_arp_set_param(&g_app, 0, i, pass ? e->params[i].max : e->params[i].min);
      }
      snprintf(name, sizeof name, "arp-p%d-%s", page + 1, pass ? "max" : "min");
      check_screen(name, dir, 0);
    }
    for (uint16_t i = 0; i < e->n_params; ++i) {
      const fm1_param_t *q = &e->params[i];
      if (q->type != FM1_PARAM_ENUM || q->page != page) continue;
      for (int v = (int)q->min; v <= (int)q->max; ++v) {
        fm1_app_arp_set_param(&g_app, 0, i, (float)v);
        snprintf(name, sizeof name, "arp-p%d-%s-%d", page + 1, q->name, v);
        check_screen(name, dir, 0);
      }
    }
    for (uint16_t i = 0; i < e->n_params; ++i) fm1_app_arp_set_param(&g_app, 0, i, e->params[i].def);
    {                                     /* the page's knobs on its lists (audit D1) */
      int idx[4], n = 0;
      for (uint16_t i = 0; i < e->n_params && n < 4; ++i) {
        if (e->params[i].page == page) idx[n++] = i;
      }
      for (int k = 0; k < n; ++k) {
        const fm1_param_t *q = &e->params[idx[k]];
        const int total = (int)(q->max - q->min) + 1;
        if (q->type != FM1_PARAM_ENUM) continue;
        fm1_app_arp_set_param(&g_app, 0, idx[k], q->min);
        g_app.popup_lines = 0;
        fm1_app_encoder(&g_app, FM1_ENC_KNOB1 + k, 1);
        snprintf(name, sizeof name, "knob-list-arp-%s", q->name);
        if (total < 5) {
          expect(g_app.popup_lines == 0, "a short ARP list parameter's knob opened a popup");
        } else {
          expect_knob_list_face(total, "an ARP knob's list is not in its face");
          expect_window(name, q->name, total, 1);
          check_screen(name, dir, strcmp(q->name, "Mode") == 0 || strcmp(q->name, "Oct Mode") == 0);
          fm1_app_encoder(&g_app, FM1_ENC_KNOB1 + k, total);
          expect_window(name, q->name, total, total - 1);
          snprintf(name, sizeof name, "knob-list-arp-%s-end", q->name);
          check_screen(name, dir, 0);
        }
        fm1_app_arp_set_param(&g_app, 0, idx[k], q->def);
        g_app.popup_lines = 0;
      }
    }
    fm1_app_encoder(&g_app, FM1_ENC_SELECT, -64);
  }
  expect(fm1_app_arp_preset_of(&g_app, 0) == 0, "the arp's defaults are not stock's Up");
  for (int k = 1; k < fm1_app_arp_preset_count(); ++k) {   /* ALGORITHM: the stock presets, */
    fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, 1);         /* then the other MIDI effects */
    expect(fm1_app_arp_preset_of(&g_app, 0) == k, "ALGORITHM does not step the arp presets");
    expect_window("ALGORITHM on the ARP pages", "Arp preset", fm1_app_arp_preset_count(), k);
    snprintf(name, sizeof name, "popup-arp-preset-%d", k);
    check_screen(name, dir, k == 2);
  }
  for (int k = fm1_app_arp_preset_count() - 1; k > 0; --k) {   /* and back to the arp's Up */
    fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -1);
  }
  expect(fm1_app_mfx_engine(&g_app, 0) == e && fm1_app_arp_preset_of(&g_app, 0) == 0,
         "ALGORITHM does not bring the arp back");
  g_app.popup_lines = 0;
  check_screen("arp-preset-shown", dir, 1);
  hold_arp(rate);                             /* a hold: Latch */
  expect(fm1_app_arp_get_param(&g_app, 0, fm1_app_arp_param_index("Latch")) == 1.0f,
         "holding ARP does not latch");
  check_screen("popup-latch-on", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_ARP, 0);
  expect(fm1_app_arp_on(&g_app, 0), "a hold's release switched the arp off");
  g_app.popup_lines = 0;
  check_screen("arp-latched", dir, 1);
  fm1_app_note_off(&g_app, 57);
  press(FM1_BTN_HOME);
  fm1_app_render(&g_app, 64);
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);     /* SHIFT + ARP: the pages, no switch */
  press(FM1_BTN_ARP);
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);
  expect(g_app.mode == FM1_MODE_ARP && fm1_app_arp_on(&g_app, 0), "SHIFT + ARP switched the arp");
  press(FM1_BTN_ARP);                         /* a tap there: off, the pages close */
  expect(g_app.mode == FM1_MODE_HOME && !fm1_app_arp_on(&g_app, 0), "an ARP tap does not switch off");
  check_screen("popup-arp-off", dir, 1);
  g_app.popup_lines = 0;
  fm1_app_unit_select(&g_app, 1, fm1_app_find("shapes"));    /* another sound's, by name */
  fm1_app_unit_set_current(&g_app, 1);
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);
  press(FM1_BTN_ARP);
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);
  check_screen("arp-sound-2-off", dir, 1);
  fm1_app_all_notes_off(&g_app);
}

/* Every other MIDI effect in the MIDI-FX slot (Acid Gen while the GPL
 * switch is on): chosen with ALGORITHM on the ARP pages, then every page at
 * its defaults, extremes and list entries, its on and off popups and Latch,
 * and the arp back. */
static void mfx_screens(const char *dir, float rate) {
  char name[160];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  for (size_t f = 0; f < fm1_midi_fx_count; ++f) {
    const fm1_engine_t *e = &fm1_midi_fxs[f]->engine;
    int pages = 1, preset = -1;
    if (e == fm1_app_arp_engine()) continue;
    for (int k = 0; k < fm1_app_arp_preset_count(); ++k) {
      const char *n = fm1_app_arp_preset_name(k);
      if (n && strcmp(n, e->name) == 0) preset = k;
    }
    expect(preset >= 0, "a MIDI effect is not on ALGORITHM's list");
    press(FM1_BTN_ARP);                       /* the arp on, its pages */
    for (int k = 0; k < preset; ++k) fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, 1);
    expect(fm1_app_mfx_engine(&g_app, 0) == e && fm1_app_arp_on(&g_app, 0),
           "ALGORITHM does not put the effect in the slot, on");
    expect_window("ALGORITHM on the ARP pages", "Arp preset", fm1_app_arp_preset_count(), preset);
    snprintf(name, sizeof name, "popup-mfx-%s", e->id);
    check_screen(name, dir, 1);
    g_app.popup_lines = 0;
    fm1_app_note_on(&g_app, 45, 100);
    for (int k = 0; k < 60; ++k) fm1_app_render(&g_app, 64);
    for (uint16_t i = 0; i < e->n_params; ++i) {
      if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
    }
    for (int page = 0; page < pages; ++page) {
      for (int k = 0; k < page; ++k) fm1_app_encoder(&g_app, FM1_ENC_SELECT, 1);
      expect(g_app.arp_page == page, "SELECT does not step the MIDI effect's pages");
      snprintf(name, sizeof name, "mfx-%s-p%d", e->id, page + 1);
      check_screen(name, dir, 1);
      for (int pass = 0; pass < 2; ++pass) {
        for (uint16_t i = 0; i < e->n_params; ++i) {
          fm1_app_arp_set_param(&g_app, 0, i, pass ? e->params[i].max : e->params[i].min);
        }
        for (int k = 0; k < 30; ++k) fm1_app_render(&g_app, 64);
        snprintf(name, sizeof name, "mfx-%s-p%d-%s", e->id, page + 1, pass ? "max" : "min");
        check_screen(name, dir, 0);
      }
      for (uint16_t i = 0; i < e->n_params; ++i) {
        const fm1_param_t *q = &e->params[i];
        if (q->type != FM1_PARAM_ENUM || q->page != page) continue;
        for (int v = (int)q->min; v <= (int)q->max; ++v) {
          fm1_app_arp_set_param(&g_app, 0, i, (float)v);
          snprintf(name, sizeof name, "mfx-%s-p%d-%s-%d", e->id, page + 1, q->name, v);
          check_screen(name, dir, 0);
        }
      }
      for (uint16_t i = 0; i < e->n_params; ++i) fm1_app_arp_set_param(&g_app, 0, i, e->params[i].def);
      fm1_app_encoder(&g_app, FM1_ENC_SELECT, -64);
    }
    hold_arp(rate);                           /* a hold: its Latch */
    fm1_app_button(&g_app, FM1_BTN_ARP, 0);
    snprintf(name, sizeof name, "popup-mfx-%s-latch", e->id);
    check_screen(name, dir, 0);
    g_app.popup_lines = 0;
    fm1_app_note_off(&g_app, 45);
    press(FM1_BTN_ARP);                       /* off: the pages close */
    expect(!fm1_app_arp_on(&g_app, 0), "an ARP tap does not switch the effect off");
    snprintf(name, sizeof name, "popup-mfx-%s-off", e->id);
    check_screen(name, dir, 0);
    g_app.popup_lines = 0;
    fm1_app_button(&g_app, FM1_BTN_SEL, 1);   /* SHIFT + ARP: its pages, off */
    press(FM1_BTN_ARP);
    fm1_app_button(&g_app, FM1_BTN_SEL, 0);
    snprintf(name, sizeof name, "mfx-%s-off", e->id);
    check_screen(name, dir, 0);
    fm1_app_encoder(&g_app, FM1_ENC_ALGORITHM, -64);   /* back to the arp */
    expect(fm1_app_mfx_engine(&g_app, 0) == fm1_app_arp_engine(), "ALGORITHM does not bring the arp back");
    g_app.popup_lines = 0;
    press(FM1_BTN_HOME);
    fm1_app_all_notes_off(&g_app);
  }
}

static void seq_screens(const char *dir, float rate) {
  char name[128];
  destroy_units();
  fm1_app_init(&g_app, rate);
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
  /* A tempo with decimals ("300.00" at its widest) keeps the tracks' room. */
  seq_line("bpm 29999");
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-299.99", dir, 1);
  seq_line("bpm 12050");
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  check_screen("seq-bpm-120.5", dir, 1);
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
  /* The bar on the keys follows the loop into bar 2, the loop's first: the
   * back key is dark, the forward one lit (bar 3 is the empty bar after the
   * loop, Movy's way to grow it). */
  {
    const uint32_t keys = fm1_seq_ui_key_leds(&g_app.ui, g_app.frames);
    expect(g_app.ui.bar == 1, "the bar on the keys did not follow the loop");
    expect(!((keys >> FM1_SEQ_UI_KEY_BAR_BACK) & 1u) && ((keys >> FM1_SEQ_UI_KEY_BAR_ON) & 1u),
           "the bar keys' LEDs");
  }
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
  press(FM1_BTN_REC);                                  /* S5: a tap, stopped: a count-in */
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  expect(g_app.popup_lines == 0 && g_app.ui.counting_in && g_app.ui.playing,
         "REC did not start a count-in");
  check_screen("seq-count-in-loop-window", dir, 0);
  press(FM1_BTN_REC);                                  /* again, playing: off at once */
  press(FM1_BTN_PLAY);
  fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
  expect(!g_app.ui.counting_in && !g_app.ui.playing && !g_app.ui.recording,
         "REC and PLAY/STOP did not end the count-in");
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
  /* HOME, FX and GLO leave SEQ mode. */
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
  destroy_units();
}

/* ---- --screens: step entry (docs/15 §4, S4) --------------------------- */

static void blocks(int n) {
  for (int k = 0; k < n; ++k) fm1_app_render(&g_app, FM1_APP_MAX_FRAMES);
}

static void key_edge(int key, int down) {
  fm1_app_key(&g_app, key, down, 100);
  blocks(1);
}

static void turn(int encoder, int delta) {
  fm1_app_encoder(&g_app, encoder, delta);
  blocks(1);
}

static void step_check(const char *name, const char *dir, int save) {
  g_app.popup_lines = 0;
  check_screen(name, dir, save);
}

/* The Step pages and the Track view's S4 marks, each value at its extremes:
 * a 16-bar clip, so LEN reaches 16 bars and the bar keys bar 16. */
static void seq_step_screens(const char *dir, float rate) {
  char name[128];
  const int hold = (int)((uint32_t)g_app.ui.hold_frames / FM1_APP_MAX_FRAMES + 2u);
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  press(FM1_BTN_SEQ);
  blocks(1);
  /* Step entry from nothing: a tap enters note 60 at 100 (O5); the bar keys
   * page nothing without a clip. */
  key_edge(fm1_white_key(0), 1);
  key_edge(fm1_white_key(0), 0);
  expect(g_app.ui.notes == 1u && g_app.ui.length == 16, "a tap did not enter step 1");
  key_edge(1, 1);
  key_edge(1, 0);
  expect(g_app.ui.bar == 0, "F#3 paged back from bar 1");
  seq_line("clen 0 256;tog 0 3 48 90;tog 0 6 60 100 64 90;slen 0 6 6 64 48;"
           "eprob 0 3 3 -1 50;econd 0 9 9 -1 2 3;einv 0 12 12 -1 1;tog 0 12 55 80;"
           "eprob 0 70 70 60 20");
  blocks(1);
  step_check("seq-step-marks", dir, 1);
  /* SHIFT: its legend, and full velocity on (a popup) and off. */
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);
  blocks(1);
  check_screen("seq-shift-legend", dir, 1);
  key_edge(fm1_white_key(FM1_SEQ_UI_FULL_VEL_KEY), 1);
  expect(g_app.ui.full_vel == 1 && g_app.popup_lines == 2, "SHIFT + 10 did not turn full velocity on");
  check_screen("seq-popup-full-velocity", dir, 1);
  key_edge(fm1_white_key(FM1_SEQ_UI_FULL_VEL_KEY), 0);
  step_check("seq-shift-legend-full-velocity", dir, 0);
  key_edge(fm1_white_key(FM1_SEQ_UI_FULL_VEL_KEY), 1);
  key_edge(fm1_white_key(FM1_SEQ_UI_FULL_VEL_KEY), 0);
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);
  blocks(1);
  expect(g_app.ui.full_vel == 0 && !g_app.ui.shift, "SHIFT + 10 again did not turn it off");
  /* The bar keys: through all 16 bars and back; the hint names the bar. */
  for (int b = 1; b < 16; ++b) {
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
    snprintf(name, sizeof name, "seq-bar-%d", b + 1);
    step_check(name, dir, b == 4 || b == 15);
  }
  expect(g_app.ui.bar == 15 && g_app.ui.grid_first == 192, "A#3 did not reach bar 16");
  for (int b = 15; b > 0; --b) {
    key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 0);
  }
  expect(g_app.ui.bar == 0, "F#3 did not come back to bar 1");
  seq_line("clen 0 16");
  blocks(1);
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
  step_check("seq-bar-2-empty", dir, 1);
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 1);
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 0);
  seq_line("clen 0 256");
  blocks(1);
  /* Step 7 held (its chord: 60 and 64, two lengths) past the threshold:
   * Step page 1, then every field at its extremes. */
  key_edge(fm1_white_key(6), 1);
  blocks(hold);
  expect(g_app.ui.view == FM1_SEQ_VIEW_STEP, "a hold did not open the Step page");
  step_check("seq-step-p1-mixed", dir, 1);
  turn(FM1_ENC_KNOB1, -64);
  turn(FM1_ENC_KNOB2, -64);
  turn(FM1_ENC_KNOB3, -64);
  turn(FM1_ENC_KNOB4, -64);
  expect(g_app.ui.hold.vel == 1 && g_app.ui.hold.gate == 12 && g_app.ui.hold.prob == 10,
         "the Step page's minima");
  step_check("seq-step-p1-min", dir, 1);
  turn(FM1_ENC_KNOB1, 64);
  turn(FM1_ENC_KNOB2, 64);
  turn(FM1_ENC_KNOB3, 64);
  turn(FM1_ENC_KNOB4, 64);
  /* 16 bars asked; the core holds the note to the clip's end, 250 steps on. */
  expect(g_app.ui.hold.vel == 127 && g_app.ui.hold.gate == 250 * 24 && g_app.ui.hold.prob == 100 &&
         g_app.ui.hold.cond_a == 8 && g_app.ui.hold.cond_b == 8, "the Step page's maxima");
  step_check("seq-step-p1-max", dir, 1);
  for (int i = 0; i < FM1_SEQ_UI_LENGTHS; ++i) {       /* every length, prob and condition */
    seq_line("slen 0 6 6 -1 1");
    blocks(1);
    turn(FM1_ENC_KNOB2, i - fm1_seq_ui_length_index(g_app.ui.hold.gate));
    snprintf(name, sizeof name, "seq-step-len-%d", i);
    step_check(name, dir, 0);
  }
  for (int i = 0; i < FM1_SEQ_UI_PROBS; ++i) {
    turn(FM1_ENC_KNOB3, fm1_seq_ui_prob_index(g_app.ui.hold.prob) - i);
    snprintf(name, sizeof name, "seq-step-prob-%d", i);
    step_check(name, dir, 0);
  }
  for (int i = 0; i < FM1_SEQ_UI_CONDS; ++i) {
    turn(FM1_ENC_KNOB4, i - fm1_seq_ui_cond_index(g_app.ui.hold.cond_a, g_app.ui.hold.cond_b));
    snprintf(name, sizeof name, "seq-step-cond-%d", i);
    step_check(name, dir, 0);
  }
  /* Step page 2: INV off and on, the nudge at both ends, a chord of 12
   * from note 1 (the longest name, "C#-1 +11"). */
  turn(FM1_ENC_SELECT, 1);
  step_check("seq-step-p2", dir, 1);
  turn(FM1_ENC_KNOB1, 1);
  expect(g_app.ui.hold.inv == 1, "INV did not turn on");
  seq_line("enudge 0 6 6 -1 -99");
  blocks(1);
  step_check("seq-step-p2-nudge-min", dir, 0);
  seq_line("enudge 0 6 6 -1 99");
  blocks(1);
  step_check("seq-step-p2-nudge-max", dir, 1);
  key_edge(fm1_white_key(6), 0);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACK && g_app.ui.held_n == 0, "the hold did not end");
  seq_line("tog 0 10 1 100 2 100 3 100 4 100 5 100 6 100 7 100 8 100 9 100 10 100 11 100 12 100");
  blocks(1);
  key_edge(fm1_white_key(10), 1);
  blocks(hold);
  step_check("seq-step-p2-chord", dir, 0);
  /* SHIFT during the hold: the legend on the first line and the strip. */
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);
  blocks(1);
  step_check("seq-step-shift", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);              /* a SHIFT tap: the step is cleared */
  blocks(1);
  expect(g_app.ui.hold.notes == 0, "a SHIFT tap did not clear the held step");
  turn(FM1_ENC_SELECT, -1);
  step_check("seq-step-p1-empty", dir, 1);
  key_edge(fm1_white_key(10), 0);
  /* Every white key held in bar 16, the last first: "Step 256 +15". */
  for (int b = 0; b < 15; ++b) {
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
  }
  for (int n = 15; n >= 0; --n) key_edge(fm1_white_key(n), 1);
  turn(FM1_ENC_KNOB1, 1);
  expect(g_app.ui.held_n == 16 && g_app.ui.hold.step == 255, "sixteen held steps");
  step_check("seq-step-sixteen-held", dir, 1);
  for (int n = 15; n >= 0; --n) key_edge(fm1_white_key(n), 0);
  /* Playing and recording on the track: REC on the status line, and the
   * playhead in the step strip under a hold. */
  for (int b = 0; b < 15; ++b) {
    key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 0);
  }
  seq_line("clen 0 16;play;rec 0");
  blocks(400);
  expect(g_app.ui.recording && g_app.ui.rec_track == 0, "not recording on track 1");
  step_check("seq-recording", dir, 1);
  key_edge(fm1_white_key(3), 1);
  blocks(hold);
  step_check("seq-step-playing", dir, 0);
  key_edge(fm1_white_key(3), 0);
  seq_line("stop");
  blocks(1);
  destroy_units();
}

/* ---- --screens: record and Capture (docs/15 §4, S5) ------------------- */

static void button_edge(int button, int down) {
  fm1_app_button(&g_app, button, down);
  blocks(1);
}

/* A note at MIDI IN, `len` blocks long, then `gap` blocks of silence. */
static void midi_note(int pitch, int len, int gap) {
  fm1_app_note_on(&g_app, pitch, 100);
  blocks(len);
  fm1_app_note_off(&g_app, pitch);
  blocks(gap);
}

/* Quarter notes at MIDI IN, stopped, at `bpm`: something for a stopped
 * Capture to read a tempo from. */
static void play_quarters(int n, double bpm, float rate) {
  const int beat = (int)(60.0 / bpm * rate / FM1_APP_MAX_FRAMES + 0.5);
  for (int k = 0; k < n; ++k) midi_note(60 + (k % 4) * 3, beat / 2, beat - beat / 2);
}

static void shift_rec(void) {
  button_edge(FM1_BTN_SEL, 1);
  button_edge(FM1_BTN_REC, 1);
  button_edge(FM1_BTN_REC, 0);
  button_edge(FM1_BTN_SEL, 0);
}

static void seq_rec_screens(const char *dir, float rate) {
  char name[128];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  press(FM1_BTN_SEQ);
  blocks(1);
  /* REC tapped, stopped: a bar's count-in (gold REC), then the take. */
  seq_line("tog 0 0 60 100");
  blocks(1);
  button_edge(FM1_BTN_REC, 1);
  button_edge(FM1_BTN_REC, 0);
  expect(g_app.ui.counting_in && g_app.ui.rec_track == 0, "a REC tap did not count in");
  step_check("seq-count-in", dir, 1);
  blocks(1400);                                        /* a bar at 120 BPM: 2 s */
  expect(g_app.ui.recording && !g_app.ui.counting_in, "the count-in did not become a take");
  step_check("seq-recording-take", dir, 0);
  button_edge(FM1_BTN_REC, 1);                         /* playing: off at once */
  button_edge(FM1_BTN_REC, 0);
  button_edge(FM1_BTN_PLAY, 1);
  button_edge(FM1_BTN_PLAY, 0);
  expect(!g_app.ui.recording && !g_app.ui.playing, "REC and PLAY/STOP did not stop the take");

  /* Step record on an empty clip: it grows to what is played. */
  fm1_app_seq_reset(&g_app, FM1_APP_SEQ_TRACKS);
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  button_edge(FM1_BTN_REC, 1);
  expect(g_app.ui.srec && g_app.ui.srec_grow && g_app.ui.srec_head == 0, "REC held: no step record");
  step_check("seq-step-rec-empty", dir, 1);
  key_edge(fm1_white_key(0), 1);                       /* a chord of two on step 1, */
  key_edge(fm1_white_key(2), 1);
  step_check("seq-step-rec-chord", dir, 0);
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);                  /* tied into step 2 */
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
  expect(g_app.ui.srec_tie == 1 && g_app.ui.srec_head == 1, "A#3 with keys down did not tie");
  step_check("seq-step-rec-tie", dir, 1);
  key_edge(fm1_white_key(0), 0);
  key_edge(fm1_white_key(2), 0);
  expect(g_app.ui.srec_head == 2 && g_app.ui.length == 2, "the head did not move on");
  key_edge(fm1_white_key(4), 1);
  key_edge(fm1_white_key(4), 0);
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);                  /* a rest */
  key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 1);                /* and back */
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 0);
  expect(g_app.ui.srec_head == 3 && g_app.ui.length == 4, "a rest and a step back");
  button_edge(FM1_BTN_SEL, 1);
  step_check("seq-step-rec-shift", dir, 1);
  key_edge(fm1_white_key(0), 1);                       /* SHIFT + key 1: the head there */
  key_edge(fm1_white_key(0), 0);
  button_edge(FM1_BTN_SEL, 0);
  expect(g_app.ui.srec_head == 0 && g_app.ui.notes == 0x4u, "SHIFT + key 1 did not move the head");
  button_edge(FM1_BTN_REC, 0);
  expect(!g_app.ui.srec && !g_app.ui.counting_in && !g_app.ui.playing,
         "letting go of REC after step record recorded");
  step_check("seq-step-rec-done", dir, 0);

  /* A 16-bar clip: the head wraps at its end. Every bar's head, then a
   * chord on the last step tied as far as it goes. */
  seq_line("clen 0 256;tog 0 255 60 100");
  blocks(1);
  button_edge(FM1_BTN_REC, 1);
  expect(g_app.ui.srec && !g_app.ui.srec_grow, "step record on a clip should wrap");
  for (int k = 1; k < 256; ++k) {
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
    if (k % 16 == 15) {
      snprintf(name, sizeof name, "seq-step-rec-head-%d", k + 1);
      step_check(name, dir, k == 255);
    }
  }
  expect(g_app.ui.srec_head == 255 && g_app.ui.bar == 15, "the head did not reach step 256");
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 1);
  key_edge(FM1_SEQ_UI_KEY_BAR_BACK, 0);
  for (int n = 0; n < 12; ++n) key_edge(fm1_white_key(n), 1);
  for (int k = 0; k < 4; ++k) {
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 1);
    key_edge(FM1_SEQ_UI_KEY_BAR_ON, 0);
  }
  expect(g_app.ui.srec_tie == 1 && g_app.ui.srec_chord_n == 12, "a tie stops at step 256");
  step_check("seq-step-rec-tie-to-the-end", dir, 1);
  for (int n = 0; n < 12; ++n) key_edge(fm1_white_key(n), 0);
  expect(g_app.ui.srec_head == 0, "the head did not wrap");
  button_edge(FM1_BTN_REC, 0);

  /* Capture: nothing buffered; then played over a playing clip; then
   * stopped, into an empty clip (the picker) and over notes (fitted). */
  fm1_app_seq_reset(&g_app, FM1_APP_SEQ_TRACKS);
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  shift_rec();
  expect(g_app.popup_lines == 1, "SHIFT + REC with nothing buffered");
  check_screen("seq-capture-nothing", dir, 1);
  g_app.popup_lines = 0;
  seq_line("tog 0 0 48 100;play");
  blocks(1);
  play_quarters(4, 120.0, rate);
  expect(g_app.ui.capture_pending == 4, "the notes played were not buffered");
  shift_rec();
  expect(g_app.popup_lines == 1 && g_app.ui.notes != 0x1u, "a Capture while playing");
  check_screen("seq-capture-captured", dir, 1);
  g_app.popup_lines = 0;
  seq_line("stop");
  fm1_app_seq_reset(&g_app, FM1_APP_SEQ_TRACKS);
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  play_quarters(8, 100.0, rate);
  shift_rec();
  expect(g_app.ui.capture_mode == FM1_SEQ_UI_CAPTURE_PICK && g_app.ui.capture_n >= 2 &&
         g_app.ui.playing, "a stopped Capture into an empty clip did not open the picker");
  step_check("seq-capture-picker", dir, 1);
  {
    const unsigned sel = g_app.ui.capture_sel;
    turn(FM1_ENC_SELECT, sel ? -1 : 1);
    expect(g_app.ui.capture_sel != sel &&
           g_app.ui.bpm_x100 == g_app.ui.capture_cands[g_app.ui.capture_sel] * 100u,
           "SELECT did not take another tempo");
  }
  button_edge(FM1_BTN_HOME, 1);                        /* any press: closed, nothing else */
  button_edge(FM1_BTN_HOME, 0);
  expect(g_app.ui.capture_mode == 0 && g_app.mode == FM1_MODE_SEQ, "HOME should only close it");
  seq_line("stop;bpm 11750");
  blocks(1);
  play_quarters(8, 100.0, rate);
  shift_rec();
  expect(g_app.ui.capture_mode == FM1_SEQ_UI_CAPTURE_FITTED, "a stopped Capture over notes");
  step_check("seq-capture-fitted", dir, 1);
  key_edge(fm1_white_key(3), 1);                       /* a key closes it too, and plays nothing */
  key_edge(fm1_white_key(3), 0);
  expect(g_app.ui.capture_mode == 0 && g_app.ui.held_n == 0, "a key did not close it");
  seq_line("stop");
  blocks(1);
  /* Every overlay at its extremes, drawn from the UI's mirror: the picker
   * with one, two and three candidates from 20 to 300 BPM, each taken, and
   * the fitted tempo at its narrowest and widest. */
  {
    static const uint16_t cands[3] = { 20, 150, 300 };
    for (int n = 1; n <= 3; ++n) {
      for (int sel = 0; sel < n; ++sel) {
        g_app.ui.capture_mode = FM1_SEQ_UI_CAPTURE_PICK;
        g_app.ui.capture_n = (uint8_t)n;
        g_app.ui.capture_sel = (uint8_t)sel;
        for (int k = 0; k < 3; ++k) g_app.ui.capture_cands[k] = cands[(k + 3 - n) % 3];
        snprintf(name, sizeof name, "seq-capture-picker-%d-of-%d", sel + 1, n);
        step_check(name, dir, n == 3 && sel == 1);
      }
    }
    static const unsigned bpm[4] = { 2000, 11750, 29999, 30000 };
    for (int k = 0; k < 4; ++k) {
      g_app.ui.capture_mode = FM1_SEQ_UI_CAPTURE_FITTED;
      g_app.ui.bpm_x100 = bpm[k];
      snprintf(name, sizeof name, "seq-capture-fitted-%u", bpm[k]);
      step_check(name, dir, 0);
    }
    g_app.ui.capture_mode = FM1_SEQ_UI_CAPTURE_PICK;   /* over HOME too */
    g_app.ui.capture_n = 3;
    g_app.mode = FM1_MODE_HOME;
    step_check("home-capture-picker", dir, 1);
    g_app.mode = FM1_MODE_SEQ;
    g_app.ui.capture_mode = 0;
  }
  destroy_units();
}

/* ---- --screens: tracks, mute and the pages (docs/15 §4, S6) ----------- */

/* SEQ held, white key n, SEQ let go: focus track n + 1. */
static void seq_focus(int n) {
  button_edge(FM1_BTN_SEQ, 1);
  key_edge(fm1_white_key(n), 1);
  key_edge(fm1_white_key(n), 0);
  button_edge(FM1_BTN_SEQ, 0);
}

/* SHIFT + white key n (0-based): Movy's shortcut n + 1. */
static void shift_key(int n) {
  button_edge(FM1_BTN_SEL, 1);
  key_edge(fm1_white_key(n), 1);
  key_edge(fm1_white_key(n), 0);
  button_edge(FM1_BTN_SEL, 0);
}

static void seq_track_screens(const char *dir, float rate) {
  char name[128];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  button_edge(FM1_BTN_SEQ, 1);
  button_edge(FM1_BTN_SEQ, 0);
  expect(g_app.mode == FM1_MODE_SEQ && g_app.ui.tracks == 8, "SEQ mode with 8 tracks");
  for (int t = 0; t < 8; ++t) {                      /* a bar on every track */
    char ops[96];
    snprintf(ops, sizeof ops, "tog %d %d %d 100;tog %d %d %d 100", t, t, 60 + t, t, 8 + t, 67 + t);
    seq_line(ops);
  }
  blocks(1);
  check_screen("seq-tracks-eight", dir, 1);
  /* SEQ + white keys 1-8 focus every track; the toast names it. */
  for (int n = 0; n < 8; ++n) {
    seq_focus(n);
    expect(g_app.ui.track == (unsigned)(n ? n : 0) && g_app.mode == FM1_MODE_SEQ,
           "SEQ + a white key did not focus its track");
    if (n == 7) {
      expect(g_app.popup_lines == 1 && strcmp(g_app.popup[0], "Track 8") == 0, "no toast for track 8");
      check_screen("seq-toast-track-8", dir, 1);
    }
    snprintf(name, sizeof name, "seq-track-%d", n + 1);
    step_check(name, dir, n == 7);
  }
  seq_focus(0);
  /* From HOME: SEQ + key 3 focuses track 3 and goes back to HOME; a note
   * played there, then SEQ + key 2: Capture emptied, and the toast says so. */
  button_edge(FM1_BTN_HOME, 1);
  button_edge(FM1_BTN_HOME, 0);
  seq_focus(2);
  expect(g_app.ui.track == 2 && g_app.mode == FM1_MODE_HOME, "SEQ + key from HOME did not go back");
  midi_note(64, 4, 4);
  expect(g_app.ui.capture_pending == 1, "the note was not buffered on track 3");
  seq_focus(1);
  expect(g_app.popup_lines == 2 && strcmp(g_app.popup[1], "Capture emptied") == 0,
         "focusing did not say Capture was emptied");
  check_screen("home-toast-capture-emptied", dir, 1);
  g_app.popup_lines = 0;
  button_edge(FM1_BTN_SEQ, 1);
  check_screen("seq-seq-held", dir, 1);
  button_edge(FM1_BTN_SEQ, 0);
  /* C#5 and D#5: the previous and the next track. */
  key_edge(FM1_SEQ_UI_KEY_TRACK_NEXT, 1);
  key_edge(FM1_SEQ_UI_KEY_TRACK_NEXT, 0);
  expect(g_app.ui.track == 2, "D#5 did not focus the next track");
  key_edge(FM1_SEQ_UI_KEY_TRACK_PREV, 1);
  key_edge(FM1_SEQ_UI_KEY_TRACK_PREV, 0);
  key_edge(FM1_SEQ_UI_KEY_TRACK_PREV, 1);
  key_edge(FM1_SEQ_UI_KEY_TRACK_PREV, 0);
  expect(g_app.ui.track == 0, "C#5 did not focus the previous track");
  g_app.popup_lines = 0;
  /* MUTE: a tap mutes track 1; held, the mute map, then every track muted. */
  key_edge(FM1_SEQ_UI_KEY_MUTE, 1);
  key_edge(FM1_SEQ_UI_KEY_MUTE, 0);
  expect(g_app.ui.muted == 1u, "a MUTE tap did not mute track 1");
  step_check("seq-track-1-muted", dir, 1);
  key_edge(FM1_SEQ_UI_KEY_MUTE, 1);
  step_check("seq-mute-map", dir, 1);
  for (int n = 1; n < 8; ++n) {
    key_edge(fm1_white_key(n), 1);
    key_edge(fm1_white_key(n), 0);
  }
  key_edge(FM1_SEQ_UI_KEY_MUTE, 0);
  expect(g_app.ui.muted == 0xFFu, "the mute map did not mute every track");
  step_check("seq-all-muted", dir, 0);
  key_edge(FM1_SEQ_UI_KEY_MUTE, 1);
  for (int n = 0; n < 8; ++n) {
    key_edge(fm1_white_key(n), 1);
    key_edge(fm1_white_key(n), 0);
  }
  key_edge(FM1_SEQ_UI_KEY_MUTE, 0);
  expect(g_app.ui.muted == 0u, "the mute map did not unmute every track");
  /* The strip in the sounds' colours (audit L3): tracks on sounds 1-4 in
   * turn, two muted, track 3 focused, then muted too; the routes after. */
  {
    fm1_seq_track_info_t was[8];
    char ops[160];
    int at = 0;
    for (int t = 0; t < 8; ++t) {
      memset(&was[t], 0, sizeof was[t]);
      fm1_seq_get_track(g_app.seq, (unsigned)t, &was[t]);
      at += snprintf(ops + at, sizeof ops - (size_t)at, "%sroute %d 1 %d", t ? ";" : "", t, t % 4);
    }
    seq_line(ops);
    seq_line("mute 1 1;mute 4 1");
    blocks(1);
    seq_focus(2);
    step_check("seq-tracks-sounds", dir, 1);
    seq_line("mute 2 1");
    blocks(1);
    step_check("seq-tracks-sounds-focused-muted", dir, 1);
    at = 0;
    for (int t = 0; t < 8; ++t) {
      at += snprintf(ops + at, sizeof ops - (size_t)at, "%sroute %d %u %u;mute %d 0", t ? ";" : "", t,
                     (unsigned)was[t].route_kind, (unsigned)was[t].route_index, t);
    }
    seq_line(ops);
    blocks(1);
    seq_focus(0);
    g_app.popup_lines = 0;
    expect(g_app.ui.muted == 0u && g_app.ui.track == 0, "the strip's routes did not go back");
  }
  /* SHIFT's legend, its states at both ends. */
  button_edge(FM1_BTN_SEL, 1);
  step_check("seq-shift-legend-s6", dir, 1);
  button_edge(FM1_BTN_SEL, 0);
  shift_key(5);                                      /* metronome on, */
  expect(g_app.ui.metro == 1 && g_app.popup_lines == 2, "SHIFT + 6 did not turn the metronome on");
  check_screen("seq-toast-metro-on", dir, 1);
  shift_key(9);                                      /* full velocity on, */
  shift_key(15);                                     /* quantize 0 -> 100 (the default is 0) */
  expect(g_app.ui.clip_quant == 100 && g_app.popup_lines == 2, "SHIFT + 16 did not cycle quantize");
  check_screen("seq-toast-quant", dir, 1);
  button_edge(FM1_BTN_SEL, 1);
  step_check("seq-shift-legend-on", dir, 0);
  button_edge(FM1_BTN_SEL, 0);
  shift_key(5);
  shift_key(9);
  shift_key(15);
  expect(g_app.ui.metro == 0 && g_app.ui.clip_quant == 0, "SHIFT + 6 and + 16 did not go back");
  g_app.popup_lines = 0;
  /* SELECT past the sound's last page: Set, Clip, Track 1/2 and 2/2, and back. */
  turn(FM1_ENC_SELECT, 10);
  expect(g_app.ui.view == FM1_SEQ_VIEW_SET, "SELECT past the sound's pages is not the Set page");
  turn(FM1_ENC_SELECT, 1);
  expect(g_app.ui.view == FM1_SEQ_VIEW_CLIP, "SELECT does not reach the Clip page");
  turn(FM1_ENC_SELECT, 1);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACKPG && g_app.ui.track_page == 0, "no Track page 1");
  turn(FM1_ENC_SELECT, 5);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACKPG && g_app.ui.track_page == 1, "no Track page 2");
  turn(FM1_ENC_SELECT, -4);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACK, "SELECT back does not reach the Track view");
  /* The Set page at its extremes. */
  shift_key(4);
  expect(g_app.ui.view == FM1_SEQ_VIEW_SET, "SHIFT + 5 does not open the Set page");
  step_check("seq-set", dir, 1);
  {
    static const char *const sets[] = { "bpm 2000;swing 50;dq 0;metro 0", "bpm 30000;swing 80;dq 100;metro 1",
                                         "bpm 11750;swing 66;dq 70;metro 0", "bpm 29999;swing 51;dq 10;metro 1" };
    for (int k = 0; k < 4; ++k) {
      seq_line(sets[k]);
      blocks(1);
      snprintf(name, sizeof name, "seq-set-%d", k + 1);
      step_check(name, dir, k == 1);
    }
  }
  seq_line("bpm 12000;swing 50;dq 0;metro 0");
  blocks(1);
  turn(FM1_ENC_KNOB1, 3);                            /* 123 BPM; with SHIFT 123.20 */
  button_edge(FM1_BTN_SEL, 1);
  turn(FM1_ENC_KNOB1, 2);
  button_edge(FM1_BTN_SEL, 0);
  turn(FM1_ENC_KNOB2, 7);
  turn(FM1_ENC_KNOB3, 7);
  turn(FM1_ENC_KNOB4, 1);
  expect(g_app.ui.bpm_x100 == 12320 && g_app.ui.swing == 57 && g_app.ui.dq == 70 && g_app.ui.metro == 1,
         "the Set page's knobs");
  step_check("seq-set-turned", dir, 0);
  /* The Clip page: every speed, the length at its ends, transpose, quantize. */
  shift_key(2);
  expect(g_app.ui.view == FM1_SEQ_VIEW_CLIP, "SHIFT + 3 does not open the Clip page");
  for (int i = 0; i < FM1_SEQ_UI_SPEEDS; ++i) {
    char ops[48];
    snprintf(ops, sizeof ops, "cscl 0 %u %u", (unsigned)fm1_seq_ui_speeds[i][0],
             (unsigned)fm1_seq_ui_speeds[i][1]);
    seq_line(ops);
    blocks(1);
    snprintf(name, sizeof name, "seq-clip-speed-%u-%u", (unsigned)fm1_seq_ui_speeds[i][0],
             (unsigned)fm1_seq_ui_speeds[i][1]);
    step_check(name, dir, i == 0);
  }
  {
    static const char *const clips[] = { "clen 0 1;ctr 0 -36;cq 0 0", "clen 0 256;ctr 0 36;cq 0 100",
                                         "clen 0 16;ctr 0 0;cq 0 70" };
    for (int k = 0; k < 3; ++k) {
      seq_line(clips[k]);
      blocks(1);
      snprintf(name, sizeof name, "seq-clip-%d", k + 1);
      step_check(name, dir, k == 1);
    }
  }
  seq_line("cscl 0 1 1");
  blocks(1);
  turn(FM1_ENC_KNOB1, -3);                           /* 1X -> 1/4X, then to 2X */
  expect(g_app.ui.clip_num == 1 && g_app.ui.clip_den == 4, "SPEED down");
  turn(FM1_ENC_KNOB1, 5);
  turn(FM1_ENC_KNOB2, -8);
  turn(FM1_ENC_KNOB3, 5);
  turn(FM1_ENC_KNOB4, -2);
  expect(g_app.ui.clip_num == 2 && g_app.ui.clip_den == 1 && g_app.ui.length == 8 && g_app.ui.clip_tr == 5 &&
             g_app.ui.clip_quant == 50, "the Clip page's knobs");
  step_check("seq-clip-turned", dir, 0);
  seq_focus(1);                                      /* a track with no clip in its slot */
  seq_line("clipsel 1 3");
  blocks(1);
  g_app.popup_lines = 0;
  shift_key(2);
  expect(g_app.ui.length == 0, "slot 4 of track 2 has a clip");
  step_check("seq-clip-none", dir, 1);
  seq_focus(0);
  /* The Track page: a route to each sound unit, loaded or empty, past
   * them, to MIDI channels 1-16, muted or not. */
  fm1_app_unit_select(&g_app, 1, fm1_app_find("macro-heavy"));
  fm1_app_unit_select(&g_app, 3, fm1_app_find("sixop"));
  shift_key(1);                                      /* on the page it was left on (O21) */
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACKPG && g_app.ui.track_page == 1, "SHIFT + 2: no Track page");
  turn(FM1_ENC_SELECT, -1);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACKPG && g_app.ui.track_page == 0, "SELECT back: no Track page 1");
  for (int k = 0; k < 5; ++k) {
    char ops[32];
    snprintf(ops, sizeof ops, "route 0 1 %d", k);
    seq_line(ops);
    blocks(1);
    g_app.popup_lines = 0;
    snprintf(name, sizeof name, "seq-trackpg-sound-%d", k + 1);
    step_check(name, dir, k == 1);
  }
  for (int ch = 1; ch <= 16; ++ch) {
    char ops[32];
    snprintf(ops, sizeof ops, "route 0 0 %d;mute 0 %d", ch, ch & 1);
    seq_line(ops);
    blocks(1);
    snprintf(name, sizeof name, "seq-trackpg-midi-%d", ch);
    step_check(name, dir, ch == 16);
  }
  seq_line("route 0 1 0;mute 0 0");
  blocks(1);
  turn(FM1_ENC_KNOB2, 1);                            /* Sound 2: the current sound follows */
  expect(g_app.ui.route_index == 1 && fm1_app_unit_of_track(&g_app, 0) == 1 && g_app.sound == 1,
         "KNOB2 on the Track page did not route track 1 to Sound 2");
  turn(FM1_ENC_KNOB1, 1);
  expect(g_app.ui.route_kind == FM1_SEQ_ROUTE_MIDI && g_app.ui.route_index == 1, "KNOB1: MIDI out");
  turn(FM1_ENC_KNOB2, 20);
  turn(FM1_ENC_KNOB3, 1);
  expect(g_app.ui.route_index == 16 && (g_app.ui.muted & 1u), "KNOB2 and KNOB3 on the Track page");
  step_check("seq-trackpg-turned", dir, 0);
  turn(FM1_ENC_KNOB1, -1);
  turn(FM1_ENC_KNOB3, -1);
  expect(g_app.ui.route_kind == FM1_SEQ_ROUTE_ENGINE && g_app.ui.route_index == 0 && !(g_app.ui.muted & 1u),
         "back to Sound 1, unmuted");
  /* Track page 2: every track's lanes, from none to all eight with the
   * longest labels, bases 0 to 127. */
  turn(FM1_ENC_SELECT, 1);
  expect(g_app.ui.track_page == 1, "SELECT on Track page 1 is not page 2");
  step_check("seq-lanes-none", dir, 1);
  for (int t = 0; t < 8; ++t) {
    for (int lane = 0; lane <= t; ++lane) {
      char ops[160];
      snprintf(ops, sizeof ops, "alabel %d %d %s;abase %d %d %d", t, lane,
               lane % 3 == 0 ? "synth:Brightness" : lane % 3 == 1 ? "synth:ABCDEFGHIJKLMNOPQRS" : "x:Y",
               t, lane, (lane * 127) / 7);
      seq_line(ops);
    }
    blocks(1);
    seq_focus(t);
    g_app.popup_lines = 0;
    shift_key(1);
    if (g_app.ui.track_page != 1) turn(FM1_ENC_SELECT, 1);
    snprintf(name, sizeof name, "seq-lanes-track-%d", t + 1);
    step_check(name, dir, t == 7);
  }
  /* SEQ goes back to the Track view; a step key closes a page too. */
  button_edge(FM1_BTN_SEQ, 1);
  button_edge(FM1_BTN_SEQ, 0);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACK, "SEQ does not close the Track page");
  shift_key(2);
  key_edge(fm1_white_key(3), 1);
  key_edge(fm1_white_key(3), 0);
  expect(g_app.ui.view == FM1_SEQ_VIEW_TRACK, "a step key does not close the Clip page");
  destroy_units();
}

/* ---- --screens: parameter locks (docs/15 §4, S8) ---------------------- */

/* Up to 8 lanes on track 1 for the lockable parameters of unit 0's engine,
 * in index order, each locked at `v` on step `step` (v < 0: no lock). */
static int lanes_on_every_param(int step, int v) {
  const fm1_engine_t *e = g_app.unit[0].e;
  int lane = 0;
  seq_line("aclr 0 0;aclr 0 1;aclr 0 2;aclr 0 3;aclr 0 4;aclr 0 5;aclr 0 6;aclr 0 7");
  for (uint16_t q = 0; e && q < e->n_params && lane < (int)FM1_SEQ_LANES; ++q) {
    char label[FM1_SEQ_LABEL_MAX], ops[160];
    if (!fm1_param_lockable(&e->params[q])) continue;
    fm1_seq_lane_label_for(&e->params[q], label, sizeof label);
    if (v >= 0) snprintf(ops, sizeof ops, "alabel 0 %d %s;abaseq 0 %d %d;aset 0 %d %d %d 1", lane, label,
                         lane, 127 - v, lane, step, v);
    else snprintf(ops, sizeof ops, "alabel 0 %d %s;abaseq 0 %d 64", lane, label, lane);
    seq_line(ops);
    ++lane;
  }
  blocks(1);
  return lane;
}

static void seq_lock_screens(const char *dir, float rate) {
  char name[128];
  const int hold = (int)((uint32_t)g_app.ui.hold_frames / FM1_APP_MAX_FRAMES + 2u);
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  press(FM1_BTN_SEQ);
  blocks(1);
  seq_line("clen 0 64;tog 0 0 60 100;tog 0 5 62 100;tog 0 21 64 100;tog 0 63 67 100");
  blocks(1);
  /* A step held, SELECT past Step 2/2: the first lock page, no lanes yet. */
  key_edge(fm1_white_key(0), 1);
  blocks(hold);
  turn(FM1_ENC_SELECT, 1);
  turn(FM1_ENC_SELECT, 1);
  expect(g_app.ui.step_page == FM1_SEQ_UI_STEP_PAGES && g_app.ui.lock_pages == 4,
         "SELECT past Step 2/2 is not Macro's first lock page");   /* 4: Glide's */
  step_check("seq-lock-no-lanes", dir, 1);
  turn(FM1_ENC_KNOB1, 1);                            /* Model: NOLOCK */
  expect(g_app.popup_lines == 2 && strcmp(g_app.popup[1], "cannot be locked") == 0,
         "Model did not say it cannot be locked");
  check_screen("seq-lock-toast-nolock", dir, 1);
  g_app.popup_lines = 0;
  turn(FM1_ENC_KNOB3, 5);                            /* Timbre: a lane, a lock */
  expect(g_app.ui.lanes == 1u && g_app.ui.hold.lock_mask == 1u && g_app.ui.hold.lock[0] == 69,
         "KNOB3 did not lock Timbre at 64 + 5");
  step_check("seq-lock-one-lane", dir, 1);
  button_edge(FM1_BTN_SEL, 1);                       /* SHIFT: a knob clears its lock */
  step_check("seq-lock-shift", dir, 1);
  turn(FM1_ENC_KNOB3, 1);
  expect(g_app.ui.hold.lock_mask == 0 && g_app.popup_lines == 2, "SHIFT + KNOB3 did not clear the lock");
  check_screen("seq-lock-toast-lock-cleared", dir, 1);
  button_edge(FM1_BTN_SEL, 0);
  g_app.popup_lines = 0;
  turn(FM1_ENC_KNOB3, -1);                           /* the lane again (the last lock freed it), */
  seq_line("aset 0 0 9 30 1");                       /* and a lock elsewhere, so it outlives */
  blocks(1);
  key_edge(FM1_SEQ_UI_KEY_CLEAR, 1);                 /* step + CLEAR: aclrstep */
  expect(g_app.ui.hold.lock_mask == 0 && g_app.popup_lines == 1, "step + CLEAR did not clear its locks");
  check_screen("seq-lock-toast-locks-cleared", dir, 1);
  expect(g_app.ui.clear_held && g_app.ui.view == FM1_SEQ_VIEW_STEP &&
             g_app.ui.step_page >= FM1_SEQ_UI_STEP_PAGES,
         "step + CLEAR left the lock page");
  step_check("seq-lock-clear-held-page", dir, 1);    /* the first line: a knob clears its lane */
  key_edge(fm1_white_key(0), 0);                     /* the step let go, CLEAR still held: */
  step_check("seq-lock-clear-held", dir, 1);         /* the hint says a knob clears its lane */
  key_edge(fm1_white_key(0), 1);
  blocks(hold);
  turn(FM1_ENC_KNOB3, 1);                            /* CLEAR + knob: aclr */
  expect(g_app.ui.lanes == 0 && g_app.popup_lines == 2, "CLEAR + KNOB3 did not clear the lane");
  check_screen("seq-lock-toast-lane-cleared", dir, 1);
  key_edge(FM1_SEQ_UI_KEY_CLEAR, 0);
  key_edge(fm1_white_key(0), 0);
  g_app.popup_lines = 0;
  /* Every sound engine's lock pages: 8 lanes (as many as it has lockable
   * parameters), locked at 0 and at 127 over the other end's base, and laned
   * with no lock on the step; a ninth lane's toast. */
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    int lanes;
    if (fm1_engines[i]->kind != FM1_KIND_SOUND || fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    blocks(1);
    for (int pass = 0; pass < 3; ++pass) {
      lanes = lanes_on_every_param(5, pass == 0 ? 0 : pass == 1 ? 127 : -1);
      key_edge(fm1_white_key(5), 1);
      blocks(hold);
      for (int k = 0; k < 8 && g_app.ui.step_page < FM1_SEQ_UI_STEP_PAGES; ++k) turn(FM1_ENC_SELECT, 1);
      while (g_app.ui.step_page > FM1_SEQ_UI_STEP_PAGES) turn(FM1_ENC_SELECT, -1);
      for (int page = 0; page < g_app.ui.lock_pages; ++page) {
        snprintf(name, sizeof name, "seq-lock-%s-p%d-%s", fm1_engines[i]->id, page + 1,
                 pass == 0 ? "min" : pass == 1 ? "max" : "base");
        step_check(name, dir, page == 0 && pass == 1);
        if (page + 1 < g_app.ui.lock_pages) turn(FM1_ENC_SELECT, 1);
      }
      if (pass == 1 && lanes == (int)FM1_SEQ_LANES) {
        /* A ninth lane: the first lockable parameter past the eighth. */
        const fm1_engine_t *e = g_app.unit[0].e;
        int seen = 0, target = -1;
        for (uint16_t q = 0; q < e->n_params && target < 0; ++q) {
          if (fm1_param_lockable(&e->params[q]) && seen++ == (int)FM1_SEQ_LANES) target = q;
        }
        if (target >= 0) {
          int idx[4], n;
          while (g_app.ui.step_page > FM1_SEQ_UI_STEP_PAGES) turn(FM1_ENC_SELECT, -1);
          while (g_app.ui.step_page - FM1_SEQ_UI_STEP_PAGES < e->params[target].page) {
            turn(FM1_ENC_SELECT, 1);
          }
          n = fm1_seq_ui_page_params(e, e->params[target].page, idx);
          for (int k = 0; k < n; ++k) {
            if (idx[k] == target) turn(FM1_ENC_KNOB1 + k, 1);
          }
          expect(g_app.popup_lines == 1 && strcmp(g_app.popup[0], "8 lanes used") == 0,
                 "a ninth lane did not say 8 lanes used");
          snprintf(name, sizeof name, "seq-lock-%s-toast-lanes-full", e->id);
          check_screen(name, dir, i == 0);
          g_app.popup_lines = 0;
        }
      }
      key_edge(fm1_white_key(5), 0);
    }
  }
  /* The Track view: a lock on every step of the grid's four bars. */
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  seq_line("alabel 0 0 synth:Env_Timbre;asetr 0 0 0 63 90 1");
  blocks(1);
  expect(g_app.ui.locks == ~(uint64_t)0, "not every step has a lock");
  step_check("seq-locks-every-step", dir, 1);
  /* Several steps held on a lock page (two without notes, so the second is
   * no length gesture): the sound, no lock. */
  key_edge(fm1_white_key(1), 1);
  key_edge(fm1_white_key(2), 1);
  turn(FM1_ENC_KNOB2, 1);
  expect(g_app.ui.view == FM1_SEQ_VIEW_STEP && g_app.ui.step_page >= FM1_SEQ_UI_STEP_PAGES &&
             g_app.ui.held_n == 2 && g_app.ui.lanes == 1u,
         "two steps held left the lock pages, or locked");
  step_check("seq-lock-several", dir, 1);
  key_edge(fm1_white_key(2), 0);
  key_edge(fm1_white_key(1), 0);
  /* Track page 2: a label's '_' is the space it stands for. */
  shift_key(1);
  if (g_app.ui.track_page != 1) turn(FM1_ENC_SELECT, 1);
  step_check("seq-lanes-spaced", dir, 1);
  button_edge(FM1_BTN_SEQ, 1);
  button_edge(FM1_BTN_SEQ, 0);
  /* A live take: recording, KNOB2 (Harmonics) turned; the hint follows it. */
  seq_line("aclr 0 0;play;rec 0");
  blocks(30);
  expect(g_app.ui.recording && g_app.ui.clip_playing, "not recording on track 1");
  {
    const unsigned from = fm1_seq_value7(&g_app.unit[0].e->params[1], g_app.unit[0].value[1]);
    turn(FM1_ENC_KNOB2, 9);
    expect(g_app.ui.take_param == 1 && g_app.ui.take_v == from + 9u,
           "KNOB2 did not take Harmonics 9 steps on");
  }
  step_check("seq-take-hint", dir, 1);
  seq_line("stop");
  blocks(1);
  /* The lock pages of another sound than the current one: "S2". */
  fm1_app_unit_select(&g_app, 1, fm1_app_find("shapes"));
  seq_line("route 0 1 1");
  blocks(1);
  expect(fm1_app_unit_of_track(&g_app, 0) == 1 && g_app.sound == 0, "track 1 on Sound 2, Sound 1 current");
  key_edge(fm1_white_key(2), 1);
  blocks(hold);
  while (g_app.ui.step_page < FM1_SEQ_UI_STEP_PAGES) turn(FM1_ENC_SELECT, 1);
  turn(FM1_ENC_KNOB2, 3);
  expect(fm1_seq_ui_lane_of(g_app.seq, 0, fm1_app_unit_engine(&g_app, 1), 1) >= 0,
         "the lock did not go to Sound 2's Timbre");
  step_check("seq-lock-other-sound", dir, 1);
  key_edge(fm1_white_key(2), 0);
  destroy_units();
}

/* ---- --screens: multi-sound (docs/15 §3.16) --------------------------- */

/* Every page of a unit shown in FX mode at FX slot `slot` (In1 0 .. M2 4),
 * at its defaults, extremes and list entries (as sweep_unit does for HOME). */
static void sweep_fx(int unit, int slot, const char *tag, const char *dir, int save) {
  const fm1_engine_t *e = g_app.unit[unit].e;
  char name[160];
  int pages = 1;
  g_app.fx_slot = slot;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (e->params[i].page + 1 > pages) pages = e->params[i].page + 1;
  }
  for (int page = 0; page < pages; ++page) {
    g_app.fx_page = page;
    snprintf(name, sizeof name, "fx-%s-%s-p%d", tag, e->id, page + 1);
    check_screen(name, dir, save && page == 0);
    for (int pass = 0; pass < 2; ++pass) {
      for (uint16_t i = 0; i < e->n_params; ++i) {
        fm1_app_set_param(&g_app, unit, i, pass ? e->params[i].max : e->params[i].min);
      }
      snprintf(name, sizeof name, "fx-%s-%s-p%d-%s", tag, e->id, page + 1, pass ? "max" : "min");
      check_screen(name, dir, 0);
    }
    for (uint16_t i = 0; i < e->n_params; ++i) {
      const fm1_param_t *q = &e->params[i];
      if (q->type != FM1_PARAM_ENUM || q->page != page) continue;
      for (int v = (int)q->min; v <= (int)q->max; ++v) {
        fm1_app_set_param(&g_app, unit, i, (float)v);
        snprintf(name, sizeof name, "fx-%s-%s-p%d-%s-%d", tag, e->id, page + 1, q->name, v);
        check_screen(name, dir, 0);
      }
    }
    for (uint16_t i = 0; i < e->n_params; ++i) fm1_app_set_param(&g_app, unit, i, e->params[i].def);
  }
  g_app.fx_page = 0;
}

static void turn_now(int encoder, int delta) { fm1_app_encoder(&g_app, encoder, delta); }

/* SHIFT (SEL outside FX mode) held around one PRESETS turn: the current sound. */
static void shift_presets(int delta) {
  fm1_app_button(&g_app, FM1_BTN_SEL, 1);
  turn_now(FM1_ENC_PRESETS, delta);
  fm1_app_button(&g_app, FM1_BTN_SEL, 0);
}

static void multi_screens(const char *dir, float rate) {
  char name[160];
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  fm1_app_seq_default_route(&g_app);
  blocks(1);
  /* One sound: the title names it alone, the RAM meter in the bottom bar,
   * and FX mode's five slots, opening on M1. */
  check_screen("multi-home-one-sound", dir, 1);
  press(FM1_BTN_FX);
  expect(g_app.mode == FM1_MODE_FX && g_app.fx_slot == 3, "FX mode does not open on M1 (Plate)");
  check_screen("multi-fx-m1-plate", dir, 1);
  turn_now(FM1_ENC_SELECT, -64);
  expect(g_app.fx_slot == 0 && g_app.fx_page == 0, "SELECT does not walk back to In1");
  check_screen("multi-fx-in1-empty", dir, 1);
  turn_now(FM1_ENC_SELECT, 2);
  expect(g_app.fx_slot == 2, "SELECT does not reach the Mix page");
  check_screen("multi-fx-mix-one-sound", dir, 1);
  press(FM1_BTN_SEL);                                    /* Mix: nothing to grab */
  expect(!g_app.fx_grab, "SEL grabbed the Mix page");
  turn_now(FM1_ENC_KNOB1, -64);                          /* a percent a detent */
  expect(g_app.level[0] == 36.0f, "KNOB1 on Mix does not turn Sound 1's level a percent a detent");
  turn_now(FM1_ENC_KNOB1, -64);
  expect(g_app.level[0] == 0.0f, "KNOB1 on Mix does not take Sound 1's level to 0");
  check_screen("multi-fx-mix-level-0", dir, 0);
  turn_now(FM1_ENC_KNOB1, 64);
  turn_now(FM1_ENC_KNOB1, 64);
  expect(g_app.level[0] == 100.0f, "KNOB1 on Mix does not bring the level back to 100");
  turn_now(FM1_ENC_ALGORITHM, 1);                         /* the Mix page has no effect */
  expect(g_app.popup_lines == 0, "ALGORITHM on the Mix page");
  /* Every effect in an insert, every page at its extremes (In1); the
   * master slots had theirs in run_screens. */
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_AUDIO_FX) continue;
    if (fm1_app_unit_insert(&g_app, 0, 0, (int)i) == 0) {
      g_app.popup_lines = 0;
      sweep_fx(fm1_app_insert_unit(0, 0), 0, "in1", dir, fm1_engines[i] == fm1_engine_find("ensemble"));
    }
  }
  fm1_app_unit_insert(&g_app, 0, 0, fm1_app_find("ensemble"));
  fm1_app_unit_insert(&g_app, 0, 1, fm1_app_find("diffuse"));
  fm1_app_select(&g_app, 2, -1);
  /* SEL then SELECT swaps the two inserts; the grab marker. */
  g_app.fx_slot = 0;
  g_app.fx_page = 0;
  press(FM1_BTN_SEL);
  expect(g_app.fx_grab == 1, "SEL does not grab In1");
  check_screen("multi-fx-in1-grabbed", dir, 1);
  turn_now(FM1_ENC_SELECT, 1);
  expect(g_app.fx_slot == 1 && g_app.unit[fm1_app_insert_unit(0, 1)].e == fm1_engine_find("ensemble") &&
             g_app.unit[fm1_app_insert_unit(0, 0)].e == fm1_engine_find("diffuse"),
         "SEL + SELECT does not swap the inserts");
  turn_now(FM1_ENC_SELECT, 1);                            /* the group ends at In2 */
  expect(g_app.fx_slot == 1, "a grabbed insert left its group");
  press(FM1_BTN_SEL);
  press(FM1_BTN_HOME);
  /* SHIFT + PRESETS: Sound 2, empty; PRESETS walks Empty and the sounds. */
  shift_presets(1);
  expect(g_app.sound == 1, "SHIFT + PRESETS does not choose Sound 2");
  expect_window("SHIFT + PRESETS", "Current sound", FM1_APP_SOUNDS, 1);
  check_screen("multi-popup-sound-2-empty", dir, 1);
  g_app.popup_lines = 0;
  check_screen("multi-home-empty-sound", dir, 1);
  expect(!g_app.ui.shift, "SHIFT stuck after SHIFT + PRESETS");
  turn_now(FM1_ENC_PRESETS, 1);
  expect(g_app.unit[fm1_app_sound_unit(1)].e != NULL, "PRESETS does not load Sound 2");
  check_screen("multi-popup-presets-sound-2", dir, 1);
  turn_now(FM1_ENC_PRESETS, -1);
  expect(g_app.unit[fm1_app_sound_unit(1)].e == NULL, "PRESETS does not reach Empty on Sound 2");
  check_screen("multi-popup-presets-empty", dir, 0);
  /* Every sound as Sound 2: HOME's title "S2 <name>", the Mix page's row.
   * Diffuse goes first, so Shapes fits beside the modulation runtime the
   * RAM meter counts (docs/16 MG3). */
  fm1_app_unit_insert(&g_app, 0, 0, -1);
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_SOUND) continue;
    if (fm1_app_unit_select(&g_app, 1, (int)i) != 0) continue;
    g_app.popup_lines = 0;
    g_app.mode = FM1_MODE_HOME;
    snprintf(name, sizeof name, "multi-home-s2-%s", fm1_engines[i]->id);
    check_screen(name, dir, fm1_engines[i] == fm1_engine_find("shapes"));
    g_app.mode = FM1_MODE_FX;
    g_app.fx_slot = 2;
    snprintf(name, sizeof name, "multi-mix-s2-%s", fm1_engines[i]->id);
    check_screen(name, dir, 0);
    g_app.mode = FM1_MODE_SEQ;
    snprintf(name, sizeof name, "multi-seq-s2-%s", fm1_engines[i]->id);
    check_screen(name, dir, 0);
  }
  /* Four sounds: Sound 3 Six-Op, Sound 4 Test Sine; their levels at both
   * ends; Sound 3 empty again. */
  fm1_app_unit_select(&g_app, 1, fm1_app_find("sw-sophie"));
  expect(fm1_app_unit_select(&g_app, 2, fm1_app_find("sixop")) == 0, "Six-Op as Sound 3");
  expect(fm1_app_unit_select(&g_app, 3, fm1_app_find("test-sine")) == 0, "Test Sine as Sound 4");
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 2;
  g_app.popup_lines = 0;
  check_screen("multi-fx-mix-four", dir, 1);
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) fm1_app_unit_set_level(&g_app, k, (float)(k * 33));
  check_screen("multi-fx-mix-four-levels", dir, 0);
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) fm1_app_unit_set_level(&g_app, k, 100.0f);
  fm1_app_unit_select(&g_app, 2, -1);
  check_screen("multi-fx-mix-sound-3-empty", dir, 0);
  /* The current sound's inserts follow it: Sound 2's, then Sound 1's. */
  g_app.fx_slot = 0;
  check_screen("multi-fx-s2-in1-empty", dir, 0);
  /* The RAM meter refuses: Shapes on Sound 1 with Shapes already on Sound 2
   * passes the budget; the popup says by how much. */
  fm1_app_unit_set_current(&g_app, 0);
  fm1_app_unit_select(&g_app, 1, fm1_app_find("shapes"));
  g_app.mode = FM1_MODE_HOME;
  {
    const size_t before = fm1_app_ram(&g_app);
    const int r = fm1_app_unit_select(&g_app, 0, fm1_app_find("shapes"));
    expect(r == FM1_APP_SELECT_RAM && fm1_app_ram(&g_app) == before, "the meter let Shapes twice in");
    /* Refused from the page's menu or the API, the popup says so too. */
    expect(g_app.popup_lines == 3 && strcmp(g_app.popup[0], "Shapes") == 0 &&
               strcmp(g_app.popup[1], "does not fit") == 0 && strstr(g_app.popup[2], "K over budget"),
           "no popup for a refusal from the menu");
    g_app.popup_lines = 0;
  }
  expect(g_app.unit[0].e != NULL, "Sound 1 emptied by a refusal");
  turn_now(FM1_ENC_PRESETS, 1);                           /* Macro -> Shapes is stepped over */
  expect(g_app.unit[0].e && g_app.unit[0].e != fm1_engine_find("shapes"), "PRESETS loaded what does not fit");
  expect(g_app.popup_lines == 3, "no refusal popup from PRESETS");
  check_screen("multi-popup-ram-refused", dir, 1);
  g_app.popup_lines = 0;
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  /* ALGORITHM in FX mode steps over an effect that does not fit (PSX Verb). */
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 3;
  fm1_app_select(&g_app, 1, fm1_app_find("diffuse"));
  fm1_app_unit_insert(&g_app, 1, 0, fm1_app_find("plate"));
  {
    const int psx = fm1_app_find("sw-psxverb");
    int prev = psx - 1;                                   /* the effect before it in the list */
    while (prev >= 0 && fm1_engines[prev]->kind != FM1_KIND_AUDIO_FX) --prev;
    expect(psx >= 0 && prev >= 0 && fm1_app_ram_with(&g_app, 1, psx) > FM1_APP_RAM_BUDGET,
           "PSX Verb fits beside Shapes and Plate");
    fm1_app_select(&g_app, 1, prev);
    turn_now(FM1_ENC_ALGORITHM, 1);
    expect(g_app.unit[1].index != psx && g_app.unit[1].index != prev && g_app.popup_lines == 3,
           "ALGORITHM did not step over PSX Verb");
    check_screen("multi-popup-fx-ram-refused", dir, 1);
    g_app.popup_lines = 0;
  }
  /* The meter's states: a quarter, nearly full, and past the budget. */
  g_app.mode = FM1_MODE_HOME;
  for (int k = 1; k < FM1_APP_SOUNDS; ++k) fm1_app_unit_select(&g_app, k, -1);
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    for (int j = 0; j < FM1_APP_INSERTS; ++j) fm1_app_unit_insert(&g_app, k, j, -1);
  }
  check_screen("multi-meter-low", dir, 0);
  fm1_app_unit_select(&g_app, 1, fm1_app_find("shapes"));
  fm1_app_unit_insert(&g_app, 1, 0, fm1_app_find("plate"));
  check_screen("multi-meter-high", dir, 1);
  g_app.mode = FM1_MODE_GLOBAL;
  check_screen("multi-global", dir, 1);
  /* Past the budget: every unit filled with the largest engine or effect
   * that fits beside a one-track sequencer, then the sequencer at eight
   * tracks again (fm1_app_seq_reset asks no meter). Such a chain may shrink
   * but not grow. */
  destroy_units();
  fm1_app_init(&g_app, rate);
  fm1_app_seq_reset(&g_app, 1);
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    int is_sound = 0, best = -1;
    size_t most = 0;
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) is_sound |= fm1_app_sound_unit(k) == u;
    for (size_t i = 0; i < fm1_engine_count; ++i) {
      const size_t with = fm1_app_ram_with(&g_app, u, (int)i);
      if ((fm1_engines[i]->kind == FM1_KIND_SOUND) != is_sound || with > FM1_APP_RAM_BUDGET) continue;
      if (best < 0 || with > most) best = (int)i, most = with;
    }
    if (best >= 0) expect(fm1_app_select(&g_app, u, best) == 0, "a unit that fits did not load");
  }
  fm1_app_seq_reset(&g_app, FM1_APP_SEQ_TRACKS);
  fm1_app_seq_default_route(&g_app);
  expect(fm1_app_ram(&g_app) > FM1_APP_RAM_BUDGET, "the full chain fits the budget at eight tracks");
  check_screen("multi-meter-over", dir, 1);
  {
    const int big = g_app.unit[1].index;
    expect(fm1_app_select(&g_app, 1, fm1_app_find("test-gain")) == 0, "a chain past the budget cannot shrink");
    expect(fm1_app_select(&g_app, 1, big) == FM1_APP_SELECT_RAM, "a chain past the budget grew");
  }
  destroy_units();
}

/* ---- --screens: list popups (PRESETS, ALGORITHM, the pickers) ---------- */

/* Every list a turn opens, end to end: ALGORITHM through each sound
 * engine's first list parameter (Six-Op FM's 96 patches the longest),
 * PRESETS through the engines, and ALGORITHM in FX mode through the
 * effects, each entry's window checked and drawn. */
static void list_screens(const char *dir) {
  char name[128];
  g_app.mode = FM1_MODE_HOME;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    int m = -1;
    if (e->kind != FM1_KIND_SOUND || fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    for (uint16_t k = 0; k < e->n_params && m < 0; ++k) {
      if (e->params[k].type == FM1_PARAM_ENUM) m = k;
    }
    if (m < 0) continue;
    {
      const fm1_param_t *p = &e->params[m];
      const int n = (int)(p->max - p->min) + 1;
      fm1_app_set_param(&g_app, 0, (uint16_t)m, p->min + 1.0f);
      turn_now(FM1_ENC_ALGORITHM, -1);                 /* the top */
      for (int k = 0; k < n; ++k) {
        if (k) turn_now(FM1_ENC_ALGORITHM, 1);
        snprintf(name, sizeof name, "list-%s", e->id);
        expect_window(name, p->name, n, k);
        check_list_screen(name, dir, k, n, strcmp(e->id, "sixop") == 0);
      }
      turn_now(FM1_ENC_ALGORITHM, 1);                  /* past the end: it stays there */
      expect_window("ALGORITHM past the end", p->name, n, n - 1);
    }
  }
  /* PRESETS: Sound 1's engines (no Empty), from the first to the last. */
  {
    int first = -1, n = 0, k = 0;
    for (size_t i = 0; i < fm1_engine_count; ++i) {
      if (fm1_engines[i]->kind != FM1_KIND_SOUND) continue;
      if (first < 0) first = (int)i;
      ++n;
    }
    fm1_app_select(&g_app, 0, first);
    for (k = 0; k < n; ++k) {
      turn_now(FM1_ENC_PRESETS, 1);
      if (!k) turn_now(FM1_ENC_PRESETS, -1);           /* open it on the first */
      expect_window("PRESETS", "Engine", n, k);
      check_list_screen("list-presets", dir, k, n, 0);
    }
  }
  /* ALGORITHM in FX mode, on M1 with a small sound: Empty, then every
   * effect. */
  fm1_app_select(&g_app, 0, fm1_app_find("test-sine"));
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 3;
  g_app.fx_page = 0;
  fm1_app_select(&g_app, 1, -1);
  {
    int n = 1;
    for (size_t i = 0; i < fm1_engine_count; ++i) n += fm1_engines[i]->kind == FM1_KIND_AUDIO_FX;
    for (int k = 0; k < n; ++k) {
      turn_now(FM1_ENC_ALGORITHM, 1);
      if (!k) turn_now(FM1_ENC_ALGORITHM, -1);         /* open it on Empty */
      expect_window("ALGORITHM in FX mode", "Master 1 effect", n, k);
      check_list_screen("list-fx", dir, k, n, 1);
    }
  }
  fm1_app_select(&g_app, 1, -1);
  g_app.mode = FM1_MODE_HOME;
  g_app.popup_lines = 0;
}

/* ---- --screens: the audit's proposals in the app (2026-10-06) ---------- */

/* KNOB1-4 over every list parameter of unit `unit`'s pages (HOME's sound,
 * or an effect in FX mode): a list of LIST_PARAM_MIN entries or more opens
 * its list (in MID, or whole in MAIN when it fits) with the knob's value
 * chosen, from the top and at the end (audit D1); a shorter one changes in
 * place, with no popup. */
static void knob_lists(int unit, const char *tag, const char *dir) {
  const fm1_engine_t *e = g_app.unit[unit].e;
  char name[128];
  for (int page = 0; e && page < 8; ++page) {
    int idx[4], n = 0;
    for (uint16_t i = 0; i < e->n_params && n < 4; ++i) {
      if (e->params[i].page == page) idx[n++] = i;
    }
    if (!n) break;
    if (unit == 0) g_app.page = page;
    else g_app.fx_page = page;
    for (int k = 0; k < n; ++k) {
      const fm1_param_t *p = &e->params[idx[k]];
      const int total = (int)(p->max - p->min) + 1;
      if (p->type != FM1_PARAM_ENUM) continue;
      fm1_app_set_param(&g_app, unit, idx[k], p->min);
      g_app.popup_lines = 0;
      turn_now(FM1_ENC_KNOB1 + k, 1);
      snprintf(name, sizeof name, "knob-list-%s-%s-%s", tag, e->id, p->name);
      if (total < 5) {
        expect(g_app.popup_lines == 0, "a short list parameter's knob opened a popup");
        continue;
      }
      expect_knob_list_face(total, "a knob's list is not in its face");
      expect_window(name, p->name, total, 1);
      check_screen(name, dir, strcmp(e->id, "shapes") == 0 || strcmp(e->id, "filter") == 0 ||
                           strcmp(e->id, "drums") == 0);
      for (int r = total; r > 0; r -= 64) turn_now(FM1_ENC_KNOB1 + k, r > 64 ? 64 : r);   /* a turn's most */
      expect_window(name, p->name, total, total - 1);
      snprintf(name, sizeof name, "knob-list-%s-%s-%s-end", tag, e->id, p->name);
      check_screen(name, dir, 0);
      fm1_app_set_param(&g_app, unit, idx[k], p->def);
      g_app.popup_lines = 0;
    }
  }
  if (unit == 0) g_app.page = 0;
  else g_app.fx_page = 0;
}

/* The audit's proposals the app draws: the knobs' lists (D1) on every
 * sound and effect; banners (L1) over HOME, FX with four rows (the row the
 * band would cut goes whole), GLO and MATRIX, and a refusal, which keeps
 * the full popup in C_REFUSE (Q2); FX mode's chip on each slot, held and
 * not, with sounds of every colour (Q5, L3). */
static void app_ui_screens(const char *dir) {
  char line[FM1_LIST_ENTRY];
  g_app.mode = FM1_MODE_HOME;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_SOUND || fm1_app_select(&g_app, 0, (int)i) != 0) continue;
    knob_lists(0, "home", dir);
  }
  fm1_app_select(&g_app, 0, fm1_app_find("test-sine"));
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 3;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_AUDIO_FX || fm1_app_select(&g_app, 1, (int)i) != 0) continue;
    knob_lists(1, "fx", dir);
  }
  /* Banners. */
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  g_app.mode = FM1_MODE_HOME;
  fm1_app_master(&g_app, 0.5f, 1);
  expect(fm1_app_banner(&g_app, line, sizeof line) == 1 + FM1_TFT_MAIN && strcmp(line, "Volume 50") == 0,
         "MASTER's popup is no banner");
  check_screen("banner-home-volume", dir, 1);
  fm1_app_master(&g_app, 1.0f, 0);
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 3;
  g_app.fx_page = 0;
  press(FM1_BTN_OCT_UP);
  expect(fm1_app_banner(&g_app, line, sizeof line) == 1 + FM1_TFT_MAIN && strcmp(line, "Octave +1") == 0,
         "OCT+'s popup is no banner");
  check_screen("banner-fx-four-rows", dir, 1);
  g_app.mode = FM1_MODE_GLOBAL;
  check_screen("banner-global", dir, 1);
  press(FM1_BTN_OCT_DOWN);
  g_app.mode = FM1_MODE_MATRIX;
  fm1_app_master(&g_app, 0.25f, 1);
  check_screen("banner-matrix", dir, 1);
  fm1_app_master(&g_app, 1.0f, 0);
  g_app.mode = FM1_MODE_HOME;
  press(FM1_BTN_SAVE);
  expect(!fm1_app_banner(&g_app, line, sizeof line) && g_app.popup_tone == FM1_APP_TONE_REFUSE,
         "SAVE's stub is no refusal");
  g_app.popup_lines = 0;
  fm1_app_button(&g_app, FM1_BTN_OCT_UP, 1);
  fm1_app_button(&g_app, FM1_BTN_OCT_DOWN, 1);
  expect(fm1_app_banner(&g_app, line, sizeof line) == 1 + FM1_TFT_MID &&
             strcmp(line, "Octave 0, Transpose 0") == 0,
         "\"Octave 0, Transpose 0\" is no MID banner");
  check_screen("banner-home-mid", dir, 1);
  fm1_app_button(&g_app, FM1_BTN_OCT_UP, 0);
  fm1_app_button(&g_app, FM1_BTN_OCT_DOWN, 0);
  g_app.popup_lines = 0;
  /* FX mode's strip: the chip on each slot, held on the inserts and the
   * master slots, Sound 3 current with a filled insert. */
  fm1_app_unit_select(&g_app, 2, fm1_app_find("shapes"));
  fm1_app_unit_set_current(&g_app, 2);
  fm1_app_unit_insert(&g_app, 2, 0, fm1_app_find("drive"));
  g_app.mode = FM1_MODE_FX;
  for (int slot = 0; slot < 5; ++slot) {
    char name[64];
    g_app.fx_slot = slot;
    g_app.fx_page = 0;
    for (int grab = 0; grab < 2; ++grab) {
      g_app.fx_grab = grab && slot != 2;
      snprintf(name, sizeof name, "fx-chip-%d%s", slot, g_app.fx_grab ? "-held" : "");
      check_screen(name, dir, slot == 0 || (slot == 3 && grab));
    }
  }
  g_app.fx_grab = 0;
  fm1_app_unit_insert(&g_app, 2, 0, -1);
  fm1_app_unit_set_current(&g_app, 0);
  fm1_app_unit_select(&g_app, 2, -1);
  fm1_app_select(&g_app, 1, -1);
  g_app.mode = FM1_MODE_HOME;
  g_app.popup_lines = 0;
}

/* ---- --screens: the modulation pages (docs/16 §5, stage MG3) ---------- */

static void mod_line(const char *line) {
  char err[256];
  if (!fm1_app_mod_line(&g_app, line, err, sizeof err)) {
    fprintf(stderr, "screens: \"%s\": %s\n", line, err);
    ++g_faults;
  }
}

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

/* The pages' environment, as the app builds it for them. */
/* The app's value text (fm1_look.h), for the summary's RACK values. */
void fm1_look_value(const fm1_param_t *p, float v, char *buf, size_t size);

/* Every sink's engine by sink index (fm1_mod_sink_unit's order), as the
 * app gives the pages and the script reader. */
static void harness_units(const fm1_engine_t **units) {
  for (unsigned i = 0; i < FM1_MOD_SINKS; ++i) {
    units[i] = NULL;
    for (int u = 0; u < FM1_APP_UNITS; ++u) {
      if (fm1_app_mod_unit(u) == (int)fm1_mod_sink_unit(i)) units[i] = g_app.unit[u].e;
    }
  }
}

static void harness_mod_env(fm1_mod_ui_env_t *env) {
  memset(env, 0, sizeof *env);
  env->m = g_app.mod;
  env->rate = g_app.host.sample_rate;
  env->sound = (uint8_t)g_app.sound;
  harness_units(env->unit);
}

/* Every short form in a destination list distinct and at most
 * FM1_MOD_UI_DST_CHARS long; `what` names the list for a fault. */
static void unique_dests(const fm1_mod_ui_env_t *env, const char *what) {
  static fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
  static char names[FM1_MOD_UI_MAX_DESTS][16], rows[FM1_MOD_UI_MAX_DESTS][32];
  const int n = fm1_mod_ui_dests(env, list, FM1_MOD_UI_MAX_DESTS);
  for (int i = 0; i < n; ++i) {
    fm1_mod_ui_dest_name(env, &list[i], 0, names[i], sizeof names[i]);
    if (strlen(names[i]) > FM1_MOD_UI_DST_CHARS || strchr(names[i], '?')) {
      fprintf(stderr, "screens: %s: a short name %s\n", what, names[i]);
      ++g_faults;
    }
    /* ...and the names a MATRIX row gives them (audit L2), as full as fit. */
    fm1_mod_ui_dest_fit(env, &list[i], FM1_MOD_UI_ROW_DST, rows[i], sizeof rows[i]);
    if (strlen(rows[i]) > FM1_MOD_UI_ROW_DST || strchr(rows[i], '?')) {
      fprintf(stderr, "screens: %s: a row's name %s\n", what, rows[i]);
      ++g_faults;
    }
    for (int j = 0; j < i; ++j) {
      if (strcmp(names[i], names[j]) == 0) {
        fprintf(stderr, "screens: %s: two destinations are both %s\n", what, names[i]);
        ++g_faults;
      }
      if (strcmp(rows[i], rows[j]) == 0) {
        fprintf(stderr, "screens: %s: two rows' destinations are both %s\n", what, rows[i]);
        ++g_faults;
      }
    }
  }
}

/* Every engine's parameters in every unit they can fill: each sound engine
 * as all four sound units, beside effects as every insert and master slot
 * (the names need only the engines, not instances). */
static void engine_names(void) {
  fm1_mod_ui_env_t env;
  size_t fx = 0;
  harness_mod_env(&env);
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (fm1_engines[i]->kind != FM1_KIND_SOUND) continue;
    for (unsigned si = 0; si < FM1_MOD_SINKS; ++si) {
      const unsigned code = fm1_mod_sink_unit(si);
      if (code == FM1_MOD_HOST) continue;
      if (fm1_mod_unit_sound(code) >= 0) {
        env.unit[si] = fm1_engines[i];
        continue;
      }
      do fx = (fx + 1) % fm1_engine_count; while (fm1_engines[fx]->kind != FM1_KIND_AUDIO_FX);
      env.unit[si] = fm1_engines[fx];
    }
    unique_dests(&env, fm1_engines[i]->id);
  }
}

/* MATRIX's names never collide (docs/16 MG3): racks holding every kind,
 * each destination's short form (FM1_MOD_UI_DST_CHARS at most) and each
 * source's (6 at most) distinct from every other in the lists, every
 * engine's in every unit too, and MATRIX with a cable into every kind's
 * parameters and gate inputs, both pages. */
static void mod_names(const char *dir) {
  static fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
  uint8_t srcs[FM1_MOD_UI_MAX_SOURCES];
  char name[128], line[64], other[16];
  fm1_mod_ui_env_t env;
  for (unsigned base = 0; base < fm1_mod_kind_count; base += FM1_MOD_POSITIONS) {
    for (unsigned pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      snprintf(line, sizeof line, "mod %u %s", pos + 1u,
               fm1_mod_kinds[(base + pos) % fm1_mod_kind_count]->id);
      mod_line(line);
    }
    harness_mod_env(&env);
    unique_dests(&env, "a rack of every kind");
    engine_names();
    const int n = fm1_mod_ui_dests(&env, list, FM1_MOD_UI_MAX_DESTS);
    const int ns = fm1_mod_ui_sources(g_app.mod, srcs, FM1_MOD_UI_MAX_SOURCES);
    for (int i = 0; i < ns; ++i) {
      fm1_mod_ui_source(g_app.mod, srcs[i], 0, name, sizeof name);
      expect(strlen(name) <= 6, "a source's short name is too long");
      for (int j = 0; j < i; ++j) {
        fm1_mod_ui_source(g_app.mod, srcs[j], 0, other, sizeof other);
        if (strcmp(name, other) == 0) {
          fprintf(stderr, "screens: two sources are both %s\n", name);
          ++g_faults;
        }
      }
    }
    /* Cables into the modules' destinations, from module outputs, then
     * MATRIX over them. */
    {
      int k = 0;
      for (int i = 0; i < n && k < (int)FM1_MOD_SLOTS; ++i) {
        fm1_mod_slot_t sl;
        if (list[i].unit < FM1_MOD_MODULE || list[i].unit >= FM1_MOD_MODULE + FM1_MOD_POSITIONS) continue;
        memset(&sl, 0, sizeof sl);
        sl.src = srcs[(ns - 1 - k) % ns];
        sl.via = FM1_MOD_NONE;
        sl.dst_unit = list[i].unit;
        sl.dst = list[i].dst;
        sl.flags = (uint8_t)(FM1_MOD_SLOT_ON | (list[i].gate ? FM1_MOD_SLOT_GATE_DST : 0));
        sl.amount = fm1_mod_q14((float)((k % 3) - 1) * (k % 2 ? 1.0f : 0.37f));
        fm1_mod_set_slot(g_app.mod, (unsigned)k++, &sl);
      }
    }
    blocks(2);
    g_app.mode = FM1_MODE_MATRIX;
    for (int top = 0; top < (int)FM1_MOD_SLOTS; top += FM1_MOD_UI_ROWS) {
      g_app.mui.slot = (uint8_t)top;
      g_app.mui.top = (uint8_t)(top > (int)FM1_MOD_SLOTS - FM1_MOD_UI_ROWS ? (int)FM1_MOD_SLOTS - FM1_MOD_UI_ROWS : top);
      for (int pg = 0; pg < 2; ++pg) {
        g_app.mui.mpage = (uint8_t)pg;
        snprintf(name, sizeof name, "matrix-kinds-%u-slot%d-%c", base / FM1_MOD_POSITIONS + 1u, top + 1,
                 pg ? 'b' : 'a');
        check_screen(name, dir, top == 0 && pg == 0);
      }
    }
    for (unsigned i = 0; i < FM1_MOD_SLOTS; ++i) {
      snprintf(line, sizeof line, "slot %u clear", i + 1u);
      mod_line(line);
    }
  }
  g_app.mui.mpage = 0;
  g_app.mui.slot = g_app.mui.top = 0;
}

/* Several sound units (docs/16 MG3): Sounds 2-4 and an insert on each,
 * a cable into every parameter of every unit, MATRIX over them, the target
 * picker at each group, CHAIN into an insert, and the marks on Sound 2's
 * HOME page, its insert's page and the master's. */
static void mod_multi_screens(const char *dir) {
  static const char *const kSounds[FM1_APP_SOUNDS] = { "", "sixop", "sw-sophie", "test-sine" };
  static const char *const kInserts[FM1_APP_SOUNDS] = { "drive", "ensemble", "fold", "crush" };
  static fm1_mod_dest_t list[FM1_MOD_UI_MAX_DESTS];
  char name[96], line[64];
  fm1_mod_ui_env_t env;
  uint8_t srcs[FM1_MOD_UI_MAX_SOURCES];
  int n, ns, slot = 2;
  for (int k = 1; k < FM1_APP_SOUNDS; ++k) {
    expect(fm1_app_unit_select(&g_app, k, fm1_app_find(kSounds[k])) == 0, "a sound unit did not load");
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    expect(fm1_app_unit_insert(&g_app, k, 0, fm1_app_find(kInserts[k])) == 0, "an insert did not load");
  }
  for (int i = 3; i <= 32; ++i) {
    snprintf(line, sizeof line, "slot %d clear", i);
    mod_line(line);
  }
  harness_mod_env(&env);
  n = fm1_mod_ui_dests(&env, list, FM1_MOD_UI_MAX_DESTS);
  ns = fm1_mod_ui_sources(g_app.mod, srcs, FM1_MOD_UI_MAX_SOURCES);
  /* One cable into each unit's first two parameters, from module outputs. */
  for (int i = 0; i < n && slot < (int)FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t sl;
    if (list[i].unit >= FM1_MOD_MODULE && list[i].unit < FM1_MOD_MODULE + FM1_MOD_POSITIONS) continue;
    if (i > 1 && list[i - 2].unit == list[i].unit) continue;
    memset(&sl, 0, sizeof sl);
    sl.src = srcs[ns - 1 - slot % 8];
    sl.via = FM1_MOD_NONE;
    sl.dst_unit = list[i].unit;
    sl.dst = list[i].dst;
    sl.flags = FM1_MOD_SLOT_ON;
    sl.amount = fm1_mod_q14(slot % 2 ? -0.7f : 0.45f);
    fm1_mod_set_slot(g_app.mod, (unsigned)slot++, &sl);
  }
  blocks(3);
  g_app.mode = FM1_MODE_MATRIX;
  for (int top = 0; top < slot; top += FM1_MOD_UI_ROWS) {
    g_app.mui.slot = (uint8_t)top;
    g_app.mui.top = (uint8_t)(top > (int)FM1_MOD_SLOTS - FM1_MOD_UI_ROWS ? (int)FM1_MOD_SLOTS - FM1_MOD_UI_ROWS : top);
    for (int pg = 0; pg < 2; ++pg) {
      g_app.mui.mpage = (uint8_t)pg;
      snprintf(name, sizeof name, "matrix-units-slot%d-%c", top + 1, pg ? 'b' : 'a');
      check_screen(name, dir, pg == 0 && top <= 7);
    }
  }
  g_app.mui.mpage = 0;
  /* The target picker on an empty slot opens at the current sound; then
   * ALGORITHM jumps group by group. */
  expect(fm1_app_unit_set_current(&g_app, 1) == 0, "Sound 2 is not current");
  if (slot < (int)FM1_MOD_SLOTS) {
    turn_now(FM1_ENC_SELECT, slot - g_app.mui.slot);
    turn_now(FM1_ENC_KNOB2, 1);
    expect(g_app.mui.picker == FM1_MOD_PICK_DEST, "KNOB2 opens no picker");
    harness_mod_env(&env);
    n = fm1_mod_ui_dests(&env, list, FM1_MOD_UI_MAX_DESTS);
    expect(g_app.mui.pick >= 0 && g_app.mui.pick < n && list[g_app.mui.pick].unit == fm1_mod_sound_unit(1),
           "the picker does not open at the current sound");
    check_screen("matrix-picker-sound2", dir, 1);
    for (int g = 0; g < 16; ++g) {
      turn_now(FM1_ENC_ALGORITHM, 1);
      snprintf(name, sizeof name, "matrix-picker-unit-%02d", g);
      check_screen(name, dir, 0);
    }
    g_app.popup_lines = 0;
    g_app.mui.picker = FM1_MOD_PICK_NONE;
  }
  /* CHAIN through a cable into an insert. */
  for (int i = 2; i < slot; ++i) {
    fm1_mod_slot_t sl;
    fm1_mod_get_slot(g_app.mod, (unsigned)i, &sl);
    if (sl.dst_unit < FM1_MOD_INSERT) continue;
    g_app.mui.slot = (uint8_t)i;
    g_app.mode = FM1_MODE_CHAIN;
    check_screen("chain-insert", dir, 1);
    break;
  }
  /* The marks on Sound 2's HOME page, its insert's and the master's pages. */
  g_app.mode = FM1_MODE_HOME;
  g_app.page = 0;
  blocks(2);
  check_screen("home-routed-sound2", dir, 1);
  g_app.mode = FM1_MODE_FX;
  for (int fs = 0; fs < 5; ++fs) {
    g_app.fx_slot = fs;
    g_app.fx_page = 0;
    snprintf(name, sizeof name, "fx-routed-sound2-slot%d", fs + 1);
    check_screen(name, dir, fs == 0);
  }
  g_app.fx_slot = 3;
  g_app.mode = FM1_MODE_HOME;
  fm1_app_unit_set_current(&g_app, 0);
  for (int i = 3; i <= 32; ++i) {
    snprintf(line, sizeof line, "slot %d clear", i);
    mod_line(line);
  }
  for (int k = FM1_APP_SOUNDS - 1; k >= 0; --k) {
    fm1_app_unit_insert(&g_app, k, 0, -1);
    if (k) fm1_app_unit_select(&g_app, k, -1);
  }
}

/* Per voice (docs/16 MG9) and the MG3 follow-ups: an Envelope per voice
 * into Timbre, VEL per voice into its attack, RAND per voice into the
 * pitch, a chord held; RACK's line saying vN; MATRIX's `v` rows and a
 * refused one (`!`: per voice into an effect), the state's hints; one
 * sound's note sources and the per-sound and current-sound pitches; and a
 * cable an engine change switched off, shown under the name it had, then
 * re-aimed when an engine with that name comes back. */
static void mod_voice_screens(const char *dir) {
  static const char *const kLines[] = {
    "slot 1 env3 > snd:Timbre amt=60 voice",
    "slot 2 vel > env3:attack amt=-40 voice",
    "slot 3 rand > host:pitch amt=2 voice",
    "slot 4 env4 > fx1:Mix amt=50 voice",               /* poly into mono: refused */
    "slot 5 s2rtrg > env4:gate amt=100",
    "slot 6 lfo1 > host:pitchc amt=10",
    "slot 7 s1note > lfo2.rate amt=30",
    "slot 8 s4vel > host:pitch4 amt=-25",
    "slot 9 lfo2 > snd:Model amt=40 voice",             /* engine-wide: refused */
  };
  char name[96], line[64];
  for (int i = 1; i <= 32; ++i) {
    snprintf(line, sizeof line, "slot %d clear", i);
    mod_line(line);
  }
  for (size_t k = 0; k < sizeof kLines / sizeof kLines[0]; ++k) mod_line(kLines[k]);
  fm1_app_note_on(&g_app, 48, 100);
  fm1_app_note_on(&g_app, 55, 90);
  fm1_app_note_on(&g_app, 64, 70);
  blocks(24);
  expect((g_app.mui.plan.poly >> 2) & 1u, "ENV3 does not run per voice");
  expect(fm1_mod_voice_count(g_app.mod) >= 3, "a chord of three starts no three voices");
  expect(((g_app.mui.plan.refused >> 3) & 1u) && ((g_app.mui.plan.refused >> 8) & 1u),
         "per voice into an effect or an engine-wide parameter is not refused");
  g_app.mode = FM1_MODE_RACK;
  g_app.mui.pos = 2;
  g_app.mui.page = 0;
  check_screen("rack-voices", dir, 1);
  g_app.mui.page = 1;
  check_screen("rack-voices-p2", dir, 0);
  g_app.mui.page = 0;
  /* RACK's line past MID's 28 characters ("ENV3  2 out  1 in  1 late  3
   * voices"): in SMALL, the one place the sweep draws that face. */
  mod_line("slot 10 env3 > lfo1.rate amt=10");
  mod_line("slot 11 lfo1 > env3:decay amt=10");        /* a loop: one of the two is late */
  blocks(2);
  expect((g_app.mui.plan.delayed >> 9 | g_app.mui.plan.delayed >> 10) & 1u,
         "the loop through ENV3 and LFO1 has no cable a tick late");
  check_screen("rack-voices-small", dir, 1);
  mod_line("slot 10 clear");
  mod_line("slot 11 clear");
  blocks(2);
  g_app.mode = FM1_MODE_MATRIX;
  g_app.mui.slot = g_app.mui.top = 0;
  for (int pg = 0; pg < 2; ++pg) {
    g_app.mui.mpage = (uint8_t)pg;
    snprintf(name, sizeof name, "matrix-voices-%c", pg ? 'b' : 'a');
    check_screen(name, dir, 1);
  }
  g_app.mui.mpage = 1;
  g_app.mui.field = FM1_MOD_F_ON;
  g_app.mui.field_until = UINT64_MAX;
  for (int sl = 0; sl < 9; ++sl) {                      /* every state's hint */
    g_app.mui.slot = (uint8_t)sl;
    snprintf(name, sizeof name, "matrix-voices-hint-slot%d", sl + 1);
    check_screen(name, dir, sl == 0 || sl == 3);
  }
  g_app.mui.field = -1;
  /* KNOB4 on page B: on, per voice, back to on and off. */
  g_app.mui.slot = 4;
  turn_now(FM1_ENC_KNOB4, 1);
  {
    fm1_mod_slot_t v;
    fm1_mod_get_slot(g_app.mod, 4, &v);
    expect((v.flags & (FM1_MOD_SLOT_ON | FM1_MOD_SLOT_VOICE)) == (FM1_MOD_SLOT_ON | FM1_MOD_SLOT_VOICE),
           "KNOB4 does not make a cable per voice");
    turn_now(FM1_ENC_KNOB4, -1);
    fm1_mod_get_slot(g_app.mod, 4, &v);
    expect((v.flags & (FM1_MOD_SLOT_ON | FM1_MOD_SLOT_VOICE)) == FM1_MOD_SLOT_ON,
           "KNOB4 does not make a per-voice cable global again");
  }
  g_app.mui.mpage = 0;
  fm1_app_all_notes_off(&g_app);
  blocks(4);
  /* An engine without Timbre: the cable goes off under its old name; one
   * with it (Shapes) takes it back on. */
  expect(fm1_app_select(&g_app, 0, fm1_app_find("sixop")) == 0, "Six-Op did not load");
  blocks(2);
  g_app.mui.slot = 0;
  check_screen("matrix-aimed", dir, 1);
  g_app.mui.mpage = 1;
  g_app.mui.field = FM1_MOD_F_ON;
  check_screen("matrix-aimed-hint", dir, 0);
  g_app.mui.field = -1;
  g_app.mui.mpage = 0;
  g_app.mode = FM1_MODE_CHAIN;
  check_screen("chain-aimed", dir, 0);
  g_app.mode = FM1_MODE_MATRIX;
  expect(fm1_app_select(&g_app, 0, fm1_app_find("macro-heavy")) == 0, "Macro Heavy did not load");
  {
    fm1_mod_slot_t v;
    fm1_mod_get_slot(g_app.mod, 0, &v);
    expect((v.flags & FM1_MOD_SLOT_ON) && !g_app.mui.aim[0],
           "Macro Heavy's Timbre did not take the cable back");
  }
  blocks(2);
  check_screen("matrix-reaimed", dir, 0);
  expect(fm1_app_select(&g_app, 0, fm1_app_find("macro")) == 0, "Macro did not load");
  for (int i = 1; i <= 32; ++i) {
    snprintf(line, sizeof line, "slot %d clear", i);
    mod_line(line);
  }
  mod_line("slot 1 rtrg > env3:gate amt=100");          /* the default cables again */
  mod_line("slot 2 rtrg > env4:gate amt=100");
  blocks(2);
  g_app.mui.slot = g_app.mui.top = 0;
}

static void mod_screens(const char *dir, float rate) {
  char name[128], line[160];
  destroy_units();
  fm1_app_init(&g_app, rate);
  expect(g_app.mod != NULL, "fm1_app_init starts no modulation runtime");
  if (!g_app.mod) return;
  fm1_app_select(&g_app, 0, fm1_app_find("macro"));
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  fm1_app_select(&g_app, 2, fm1_app_find("echo"));
  fm1_app_seq_default_route(&g_app);
  fm1_app_note_on(&g_app, 57, 100);
  blocks(40);
  /* LFO: RACK at LFO1, then LFO2; ENV at ENV3; the LEDs. */
  press(FM1_BTN_LFO);
  expect(g_app.mode == FM1_MODE_RACK && g_app.mui.pos == 0, "LFO does not open RACK at LFO1");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_LFO] == 1, "the LFO LED is off on LFO1's page");
  check_screen("rack-lfo1", dir, 1);
  press(FM1_BTN_LFO);
  expect(g_app.mui.pos == 1, "LFO again does not step to LFO2");
  press(FM1_BTN_ENV);
  expect(g_app.mode == FM1_MODE_RACK && g_app.mui.pos == 2, "ENV does not open RACK at ENV3");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_ENV] == 1 && g_app.led[FM1_APP_KEYS + FM1_BTN_LFO] == 0,
         "ENV3's page lights ENV alone");
  check_screen("rack-env1", dir, 1);
  /* SELECT walks every position and page, there and back. */
  g_app.mui.pos = 0;
  g_app.mui.page = 0;
  for (int k = 0; k < 16; ++k) {
    snprintf(name, sizeof name, "rack-walk-%02d", k);
    check_screen(name, dir, k == 8 || k == 10);
    turn_now(FM1_ENC_SELECT, 1);
  }
  expect(g_app.mui.pos == 7, "SELECT does not reach the last position");
  turn_now(FM1_ENC_SELECT, -64);
  expect(g_app.mui.pos == 0 && g_app.mui.page == 0, "SELECT does not come back to the first");
  /* The kind picker on an empty position, and its commit after a second. */
  g_app.mui.pos = 6;
  const int kinds = (int)fm1_mod_kind_count + 1;       /* Empty, then every kind */
  for (int k = 0; k < kinds; ++k) {
    turn_now(FM1_ENC_ALGORITHM, 1);
    snprintf(name, sizeof name, "rack-picker-%d", k);
    expect_window(name, "Mod7 kind", kinds, (k + 1) % kinds);       /* round to Empty at the end */
    check_screen(name, dir, k == 0 || k == kinds / 2 - 1 || k == kinds - 2);
  }
  turn_now(FM1_ENC_ALGORITHM, 1);              /* round to the first kind again */
  settle();
  expect(fm1_mod_kind_at(g_app.mod, 6) == 0, "the kind picker did not commit its choice");
  check_screen("rack-new-module", dir, 1);
  turn_now(FM1_ENC_ALGORITHM, -1);             /* back to Empty */
  settle();
  expect(fm1_mod_kind_at(g_app.mod, 6) < 0, "the kind picker did not empty the position");
  /* Grab: SEL, then SELECT moves the module. */
  g_app.mui.pos = 4;
  press(FM1_BTN_SEL);
  expect(g_app.mui.grab == 1, "SEL does not grab in RACK");
  blocks(1);
  check_screen("rack-grab", dir, 1);
  turn_now(FM1_ENC_SELECT, 1);
  expect(g_app.mui.pos == 5 && fm1_mod_kind_at(g_app.mod, 5) == fm1_mod_kind_find("chance"),
         "SELECT does not move a grabbed module");
  turn_now(FM1_ENC_SELECT, -1);
  press(FM1_BTN_SEL);
  /* Every kind's every page. */
  for (size_t k = 0; k < fm1_mod_kind_count; ++k) mod_sweep_module(dir, fm1_mod_kinds[k]->id);
  /* The gesture's popups: a cable made, a parameter that takes none, a full
   * matrix and no LFO in the rack; then the routed marks on HOME and FX. */
  g_app.mode = FM1_MODE_HOME;
  g_app.page = 0;
  fm1_app_button(&g_app, FM1_BTN_LFO, 1);
  turn_now(FM1_ENC_KNOB2, 12);
  check_screen("gesture-made", dir, 1);
  turn_now(FM1_ENC_KNOB1, 1);
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
  /* FX: every effect in M1 with a cable on each parameter (FX mode's slot
   * 3 shows M1). */
  g_app.mode = FM1_MODE_FX;
  g_app.fx_slot = 3;
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
  turn_now(FM1_ENC_SELECT, -64);
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
    turn_now(FM1_ENC_SELECT, sl - g_app.mui.slot);
    for (int pg = 0; pg < 2; ++pg) {
      g_app.mui.mpage = (uint8_t)pg;
      snprintf(name, sizeof name, "matrix-full-slot%d-%c", sl + 1, pg ? 'b' : 'a');
      check_screen(name, dir, sl == 30);
    }
  }
  g_app.mui.mpage = 0;
  turn_now(FM1_ENC_SELECT, 31);
  expect(g_app.mui.slot == 31 && g_app.mui.top == FM1_MOD_SLOTS - FM1_MOD_UI_ROWS, "SELECT does not scroll to slot 32");
  check_screen("matrix-last", dir, 1);
  turn_now(FM1_ENC_SELECT, -64);
  /* The destination picker: open, at both ends, a group jump, and every
   * destination in turn, each one's window checked. */
  turn_now(FM1_ENC_KNOB2, 1);
  check_screen("matrix-picker", dir, 1);
  turn_now(FM1_ENC_KNOB2, -999);
  {
    static fm1_mod_dest_t dl[FM1_MOD_UI_MAX_DESTS];
    fm1_mod_ui_env_t denv;
    int nd;
    harness_mod_env(&denv);
    nd = fm1_mod_ui_dests(&denv, dl, FM1_MOD_UI_MAX_DESTS);
    expect_window("the destination picker's first", "Destination", nd, 0);
    check_screen("matrix-picker-first", dir, 1);
    turn_now(FM1_ENC_ALGORITHM, 3);
    check_screen("matrix-picker-group", dir, 1);
    turn_now(FM1_ENC_KNOB2, 999);
    expect_window("the destination picker's last", "Destination", nd, nd - 1);
    check_screen("matrix-picker-last", dir, 1);
    turn_now(FM1_ENC_KNOB2, -999);
    for (int k = 0; k < nd; ++k) {
      if (k) turn_now(FM1_ENC_KNOB2, 1);
      expect_window("the destination picker", "Destination", nd, k);
      check_list_screen("matrix-picker-walk", dir, k, nd, 0);
    }
  }
  settle();
  /* CHAIN: SEL on the loop's cable and on a chain through three modules. */
  turn_now(FM1_ENC_SELECT, 2 - g_app.mui.slot);             /* slot 3: ENV3 EOC into CHN5 */
  press(FM1_BTN_SEL);
  expect(g_app.mode == FM1_MODE_CHAIN, "SEL does not open CHAIN from MATRIX");
  blocks(1);
  expect(g_app.led[FM1_APP_KEYS + FM1_BTN_SEL] == 1, "the SEL LED is off in CHAIN");
  check_screen("chain-slot3", dir, 1);
  for (int k = 0; k < 32; ++k) {
    snprintf(name, sizeof name, "chain-%02d", g_app.mui.slot + 1);
    check_screen(name, dir, g_app.mui.slot == 6);
    turn_now(FM1_ENC_SELECT, 1);
  }
  g_app.mui.slot = 20;
  mod_line("slot 21 clear");
  check_screen("chain-empty", dir, 1);
  press(FM1_BTN_SEL);
  expect(g_app.mode == FM1_MODE_MATRIX, "SEL in CHAIN does not go back to MATRIX");
  /* Popups over the pages. */
  turn_now(FM1_ENC_PRESETS, 1);
  check_screen("matrix-popup", dir, 0);
  settle();
  mod_voice_screens(dir);
  mod_multi_screens(dir);
  mod_names(dir);
  g_app.mode = FM1_MODE_MATRIX;
  /* HOME, FX and GLO leave the pages. */
  press(FM1_BTN_HOME);
  expect(g_app.mode == FM1_MODE_HOME, "HOME does not leave MATRIX");
  press(FM1_BTN_LFO);
  press(FM1_BTN_GLO);
  expect(g_app.mode == FM1_MODE_GLOBAL, "GLO does not leave RACK");
  press(FM1_BTN_EDIT);
  press(FM1_BTN_FX);
  expect(g_app.mode == FM1_MODE_FX, "FX does not leave MATRIX");
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
  for (int slot = 0; slot < FM1_APP_FX_SLOTS; ++slot) {   /* the master bus, M1 and M2 */
    g_app.fx_slot = 3 + slot;
    g_app.fx_page = 0;
    fm1_app_select(&g_app, 1 + slot, -1);
    check_screen(slot ? "fx-empty-m2" : "fx-empty-m1", dir, 1);
    for (size_t i = 0; i < fm1_engine_count; ++i) {
      if (fm1_engines[i]->kind != FM1_KIND_AUDIO_FX) continue;
      if (fm1_app_select(&g_app, 1 + slot, (int)i) != 0) continue;
      g_app.fx_grab = slot;                       /* both markers get drawn */
      sweep_fx(1 + slot, 3 + slot, slot ? "m2" : "m1", dir, slot == 0);
    }
    fm1_app_select(&g_app, 1 + slot, -1);         /* room for the rest of the sweep */
  }
  g_app.fx_grab = 0;
  g_app.mode = FM1_MODE_GLOBAL;
  g_app.octave = -3;
  g_app.transpose = -12;
  check_screen("global", dir, 1);
  g_app.octave = 0;
  g_app.transpose = 0;
  /* The Key page: SELECT turns to it; every root and every scale, the
   * longest name with the longest root (F# Mixolydian), KNOB1 and KNOB2. */
  fm1_app_encoder(&g_app, FM1_ENC_SELECT, 1);
  expect(g_app.glo_page == 1, "SELECT does not turn the global page to Key");
  check_screen("global-key", dir, 1);
  for (int root = 0; root < 12; ++root) {
    for (int place = 0; place < FM1_KEY_SCALES; ++place) {
      char name[64];
      int scale;
      expect(fm1_app_set_project_key(&g_app, root, fm1_app_key_scale_at(place)) == 0, "the key was refused");
      expect(fm1_app_project_key(&g_app, &scale) == root && scale == fm1_app_key_scale_at(place),
             "the key did not change");
      snprintf(name, sizeof name, "global-key-%d-%d", root, place);
      check_screen(name, dir, root == 6 && fm1_app_key_scale_at(place) == FM1_KEY_MIXOLYDIAN);
    }
  }
  fm1_app_set_project_key(&g_app, 0, FM1_KEY_MAJOR);
  fm1_app_encoder(&g_app, FM1_ENC_SELECT, -1);
  fm1_app_encoder(&g_app, FM1_ENC_KNOB1, 2);          /* a knob on Globe: D, and the Key page */
  expect(g_app.glo_page == 1 && fm1_app_project_key(&g_app, NULL) == 2, "KNOB1 on the global page");
  /* ...with the root's list open on D, as a list parameter's knob opens
   * its list on HOME (audit D1) */
  expect(g_app.popup_lines > 0 && g_app.popup_total == 12 && g_app.popup_mark >= 0 &&
         strcmp(g_app.popup[g_app.popup_mark], "D") == 0, "KNOB1 does not open the root's list on D");
  check_screen("global-key-list-root", dir, 1);
  fm1_app_encoder(&g_app, FM1_ENC_KNOB2, 1);          /* Minor, the second */
  fm1_app_encoder(&g_app, FM1_ENC_KNOB2, 1);          /* Dorian, the third */
  {
    int scale;
    expect(fm1_app_project_key(&g_app, &scale) == 2 && scale == FM1_KEY_DORIAN, "KNOB2 on the Key page");
  }
  expect(g_app.popup_lines > 0 && g_app.popup_total == FM1_KEY_SCALES && g_app.popup_mark >= 0 &&
         strcmp(g_app.popup[g_app.popup_mark], "Dorian") == 0, "KNOB2 does not open the scale's list on Dorian");
  check_screen("global-key-list-scale", dir, 1);
  fm1_app_encoder(&g_app, FM1_ENC_KNOB2, 64);         /* clamped at Chromatic */
  fm1_app_encoder(&g_app, FM1_ENC_KNOB1, -64);        /* ...and at C */
  {
    int scale;
    expect(fm1_app_project_key(&g_app, &scale) == 0 && scale == FM1_KEY_CHROMATIC, "the key's knobs clamp");
  }
  fm1_app_set_project_key(&g_app, 0, FM1_KEY_MAJOR);
  g_app.popup_lines = 0;
  g_app.glo_page = 0;

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
  list_screens(dir);
  fm1_app_select(&g_app, 0, fm1_app_find("sixop"));
  for (int b = FM1_BTN_SAVE; b <= FM1_BTN_SAVE; ++b) {   /* the buttons still to come */
    char name[64];
    fm1_app_button(&g_app, b, 1);
    fm1_app_button(&g_app, b, 0);
    snprintf(name, sizeof name, "popup-button-%d", b);
    expect(g_app.mode == FM1_MODE_HOME && g_app.popup_lines == 3, "SAVE is not the stub");
    check_screen(name, dir, 1);
  }
  fm1_app_button(&g_app, FM1_BTN_FX, 1);               /* FX: M2 to empty */
  fm1_app_button(&g_app, FM1_BTN_FX, 0);
  g_app.fx_slot = 4;
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
  app_ui_screens(dir);
  dx7_screens(dir);
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
  arp_screens(dir, rate);
  mfx_screens(dir, rate);
  seq_screens(dir, rate);
  seq_step_screens(dir, rate);
  seq_rec_screens(dir, rate);
  seq_track_screens(dir, rate);
  multi_screens(dir, rate);
  seq_lock_screens(dir, rate);
  mod_screens(dir, rate);
  printf("{\"screens\":%d,\"faults\":%d,\"text_boxes\":{\"MAIN\":%ld,\"MID\":%ld,\"SMALL\":%ld}}\n",
         g_screens, g_faults, g_face_boxes[FM1_TFT_MAIN], g_face_boxes[FM1_TFT_MID],
         g_face_boxes[FM1_TFT_SMALL]);
  return g_faults ? 1 : 0;
}

/* ---- the sequencer's sizes ------------------------------------------------------ */

static int print_sizes(void) {
  fm1_seq_limits_t lim8, lim4;
  fm1_seq_limits_default(&lim8, 8);
  fm1_seq_limits_default(&lim4, 4);
  printf("{\"app_bytes\":%zu,\"sounds\":%d,\"inserts\":%d,\"master_slots\":%d,"
         "\"units\":%d,\"sound_arena\":%u,\"fx_arena\":%u,\"arena_bytes\":%zu,"
         "\"ram_budget\":%u,\"mix_block_bytes\":%u,",
         sizeof(fm1_app_t), FM1_APP_SOUNDS, FM1_APP_INSERTS, FM1_APP_FX_SLOTS, FM1_APP_UNITS,
         FM1_APP_SOUND_BYTES, FM1_APP_FX_BYTES, sizeof g_app.sound_mem + sizeof g_app.fx_mem,
         FM1_APP_RAM_BUDGET, FM1_APP_MIX_BLOCK_BYTES);
  printf("\"mod_bytes\":%zu,\"mod_arena\":%u,\"mod_ui_bytes\":%zu,\"mod_writes_bytes\":%zu,",
         fm1_mod_size(), FM1_APP_MOD_BYTES, sizeof(fm1_mod_ui_t), sizeof g_app.mod_wr);
  {
    const fm1_engine_t *ae = fm1_app_arp_engine();
    const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, FM1_APP_MAX_FRAMES };
    printf("\"mfx_stage_bytes\":%zu,\"mfx_arena\":%u,\"arp_bytes\":%zu,\"mfx_slots\":%u,",
           sizeof(fm1_mfx_t), FM1_APP_MFX_BYTES, ae ? ae->instance_size(&host) : (size_t)0,
           FM1_MFX_SLOTS);
  }
  printf("\"seq_arena\":%u,\"seq_tracks\":%d,\"seq_bytes_8\":%zu,"
         "\"seq_bytes_4\":%zu,\"seq_event_bytes\":%zu,\"seq_pending_bytes\":%zu,"
         "\"seq_ui_bytes\":%u,\"seq_ui_size\":%zu,\"seq_budget\":%u,\"seq_need\":%u,"
         "\"seq_events\":%u,\"seq_click_bytes\":%zu}\n",
         FM1_APP_SEQ_BYTES, FM1_APP_SEQ_TRACKS, fm1_seq_size(&lim8),
         fm1_seq_size(&lim4), sizeof g_app.seq_ev, sizeof g_app.seq_pend, FM1_APP_SEQ_UI_BYTES,
         sizeof(fm1_seq_ui_t),
         FM1_APP_SEQ_BUDGET,
         (unsigned)(fm1_seq_cmd_max_events(&lim8) + fm1_seq_min_events(&lim8)),
         FM1_APP_SEQ_EVENTS, sizeof g_app.click);
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

/* A live note the app gave the sequencer (the keys outside SEQ mode, MIDI
 * IN): logged as the `non` or `nof` op fm1-render applies the same way, at
 * frame 0 of the block it leads, and listed with the panel's commands. */
static void on_note_in(void *ctx, uint64_t frame, int track, int pitch, int velocity) {
  char text[64];
  (void)ctx;
  if (velocity) snprintf(text, sizeof text, "non %d %d %d", track, pitch, velocity);
  else snprintf(text, sizeof text, "nof %d %d", track, pitch);
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

/* --lock-check (docs/15 S8): on every parameter of every registered engine
 * and effect, the 7-bit grid the lock UI turns on. FLOAT: fm1_seq_value7
 * inverts fm1_seq_lock_value at every v in 0..127. ENUM: every entry's
 * fm1_seq_value7 locks back to it, and every v's is its bin's lowest. A
 * knob step from every v moves one v or one entry. The label the UI gives a
 * lane for the parameter resolves to it, and fits a label. */
static int g_lock_checks, g_lock_failures;

static void lock_expect(int ok, const fm1_engine_t *e, const fm1_param_t *p, unsigned v,
                        const char *what) {
  ++g_lock_checks;
  if (ok) return;
  if (g_lock_failures++ < 20) fprintf(stderr, "%s %s v=%u: %s\n", e->id, p->name, v, what);
}

static int lock_check(void) {
  unsigned params = 0;
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    for (uint16_t q = 0; q < e->n_params; ++q) {
      const fm1_param_t *p = &e->params[q];
      char label[FM1_SEQ_LABEL_MAX];
      ++params;
      for (unsigned v = 0; v <= FM1_SEQ_VAL_MAX; ++v) {
        const float x = fm1_seq_lock_value(p, v);
        const unsigned w = fm1_seq_value7(p, x);
        const unsigned up = fm1_seq_value7_step(p, v, 1), down = fm1_seq_value7_step(p, v, -1);
        if (p->type == FM1_PARAM_FLOAT) {
          lock_expect(w == v, e, p, v, "value7(lock_value(v)) != v");
          lock_expect(up == (v < FM1_SEQ_VAL_MAX ? v + 1u : v) && down == (v ? v - 1u : 0u), e, p, v,
                      "a knob step is not one 7-bit value");
        } else {
          lock_expect(w <= v && fm1_seq_lock_value(p, w) == x &&
                          (w == 0 || fm1_seq_lock_value(p, w - 1u) != x),
                      e, p, v, "value7 is not the bin's lowest");
          lock_expect(fm1_seq_lock_value(p, up) == (x < p->max ? x + 1.0f : p->max) &&
                          fm1_seq_lock_value(p, down) == (x > p->min ? x - 1.0f : p->min),
                      e, p, v, "a knob step is not one entry");
        }
      }
      if (p->type == FM1_PARAM_ENUM) {
        for (float x = p->min; x <= p->max; x += 1.0f) {
          lock_expect(fm1_seq_lock_value(p, fm1_seq_value7(p, x)) == x, e, p, (unsigned)x,
                      "an entry no lock reaches");
        }
      }
      lock_expect(fm1_seq_lane_label_for(p, label, sizeof label) + 1u < sizeof label &&
                      fm1_seq_lane_param(e, label) == (int)q && !strchr(label, ' '),
                  e, p, 0, "its lane label does not name it");
    }
  }
  printf("{\"engines\":%u,\"params\":%u,\"checks\":%d,\"failures\":%d}\n",
         (unsigned)fm1_engine_count, params, g_lock_checks, g_lock_failures);
  return g_lock_failures ? 1 : 0;
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
  const fm1_engine_t *units[FM1_MOD_SINKS];
  char err[256];
  (void)ctx;
  harness_units(units);
  ++g_fmt_lines;
  if (!fm1_mod_script_apply(g_mod2, line, units, err, sizeof err)) {
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
  if (fm1_mod_current(a) != fm1_mod_current(b)) {
    fprintf(stderr, "mod format (%s): the current sound is %u, not %u\n", what, fm1_mod_current(b) + 1,
            fm1_mod_current(a) + 1);
    return 0;
  }
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
                       (rnd(FM1_MOD_CURVE_COUNT) << FM1_MOD_SLOT_CURVE_SHIFT) |
                       (rnd(3) ? 0 : FM1_MOD_SLOT_VOICE));   /* per voice (MG9) */
}

static int mod_format_check(void) {
  static unsigned char mem2[FM1_APP_MOD_BYTES] FM1_APP_ALIGN16;
  /* Every unit loaded (multi-sound), so every kind of
   * destination is drawn: four sounds, each with two inserts, and the
   * master slots, inside the RAM meter's budget. */
  static const char *const kSounds[FM1_APP_SOUNDS] = { "macro", "sixop", "test-sine", "sw-sophie" };
  static const char *const kInserts[FM1_APP_SOUNDS][FM1_APP_INSERTS] = {
    { "crush", "drive" }, { "fold", "ensemble" }, { "test-gain", "comp" }, { "filter", "crush" } };
  fm1_mod_ui_env_t env;
  int rounds = 0, failures = 0;
  fm1_app_init(&g_app, 44118.0f);
  fm1_app_select(&g_app, 1, fm1_app_find("plate"));
  fm1_app_select(&g_app, 2, fm1_app_find("echo"));
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    if (fm1_app_unit_select(&g_app, k, fm1_app_find(kSounds[k])) != 0) {
      fprintf(stderr, "mod format: cannot load %s\n", kSounds[k]);
      return 1;
    }
    for (int j = 0; j < FM1_APP_INSERTS; ++j) {
      if (fm1_app_unit_insert(&g_app, k, j, fm1_app_find(kInserts[k][j])) != 0) {
        fprintf(stderr, "mod format: cannot load %s\n", kInserts[k][j]);
        return 1;
      }
    }
  }
  harness_mod_env(&env);
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
    fm1_mod_set_current(g_app.mod, rnd(FM1_APP_SOUNDS));   /* a `current K` line when not 1 */
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
      } else if (what < 9 && rnd(8) == 0) {             /* the current sound, as the app logs it */
        char line[16];
        const unsigned k = rnd(FM1_APP_SOUNDS);
        fm1_mod_set_current(g_app.mod, k);
        snprintf(line, sizeof line, "current %u", k + 1u);
        replay_line(NULL, line);
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
  harness_mod_env(&env);
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
    fm1_mod_ui_row(&env, u, i, 0, row, NULL);
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
  printf("],\"values\":[");             /* RACK's page as it shows the values */
  {
    int idx[4];
    const int k = fm1_mod_kind_at(g_app.mod, u->pos);
    const int n = fm1_mod_ui_rack_params(g_app.mod, u->pos, u->page, idx);
    for (int r = 0; k >= 0 && r < n; ++r) {
      const float v = fm1_mod_param_base(g_app.mod, u->pos, (unsigned)idx[r]);
      char text[24];
      if (!fm1_mod_ui_value(&env, u->pos, (unsigned)idx[r], v, text, sizeof text)) {
        fm1_look_value(&fm1_mod_kinds[k]->params[idx[r]], v, text, sizeof text);
      }
      printf(r ? "," : "");
      json_string(text);
    }
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
    const int n = fm1_mod_ui_chain(&env, u, u->slot, lines, NULL, &hl);
    printf("],\"chain_hl\":%d,\"chain\":[", hl);
    for (int k = 0; k < n; ++k) {
      if (k) printf(",");
      json_string(lines[k]);
    }
  }
  printf("]}");
}

/* ---- --font-check and --font-sheet: the three faces (fm1_tft.h, audit D7) ------ */

static const char *const kFontNames[FM1_TFT_FONTS] = { "MAIN", "MID", "SMALL" };
static fm1_tft_t g_ft;                            /* a frame of its own, not the app's */

/* Two runs, `a` and then `b` beside it (axis 0) or under it (axis 1), `gap`
 * px apart; b < 0 is a 10 x 10 graphic. The faults the layout check finds. */
static int font_gap_faults(int a, int b, int axis, int gap) {
  fm1_tft_begin(&g_ft, 0);
  g_ft.record = 1;
  const int x = 20, y = 40;
  const int w = fm1_tft_font_text(&g_ft, x, y, "Hg", 8, (fm1_tft_font_t)a, 0xFFFF);
  const int h = fm1_tft_metrics((fm1_tft_font_t)a)->height;
  const int bx = axis ? x : x + w + gap, by = axis ? y + h + gap : y;
  if (b < 0) fm1_tft_graphic(&g_ft, bx, by, 10, 10);
  else fm1_tft_font_text(&g_ft, bx, by, "Hg", 8, (fm1_tft_font_t)b, 0xFFFF);
  g_ft.record = 0;
  return fm1_tft_check_layout(&g_ft, FM1_APP_LAYOUT_GAP, NULL, 0);
}

/* Prints, per face, its metrics, its characters as drawn (each glyph's box,
 * '#' painted) and what went wrong: a single character's logged box not at
 * its place and size, a pixel painted outside the box, a run whose logged
 * width is not fm1_tft_font_width's or FM1_TFT_RUN_W's, a fit count that
 * disagrees with the widths, a cut run not counted, a span drawn in the
 * wrong colour or logged as more than one box. Then the 4 px rule between
 * every pair of faces, and a face and a graphic, side by side and one
 * above the other, at 3 and 4 px. tests/test_sim_fonts.py compares the
 * glyphs with the BDF files and font5x9.txt. */
static int font_check(void) {
  const char *sample = "The quick brown fox jumps over 13 lazy dogs!";
  const int line_chars[FM1_TFT_FONTS] = { LINE_CHARS, MID_LINE_CHARS, SMALL_LINE_CHARS };
  const int pitch[FM1_TFT_FONTS] = { LINE_PITCH, MID_LINE_PITCH, SMALL_LINE_PITCH };
  int errors = 0;
  printf("{\"fonts\":[");
  for (int f = 0; f < FM1_TFT_FONTS; ++f) {
    const fm1_tft_font_t font = (fm1_tft_font_t)f;
    const fm1_tft_metrics_t *m = fm1_tft_metrics(font);
    int box_errors = 0, outside = 0, width_errors = 0, fit_errors = 0;
    printf("%s{\"name\":\"%s\",\"advance\":%d,\"height\":%d,\"ink_w\":%d,\"cap_h\":%d,"
           "\"baseline\":%d,\"line_chars\":%d,\"line_pitch\":%d,\"glyphs\":[",
           f ? "," : "", kFontNames[f], m->advance, m->height, m->ink_w, m->cap_h, m->baseline,
           line_chars[f], pitch[f]);
    for (int c = 0x20; c <= 0x7E; ++c) {
      const char s[2] = { (char)c, 0 };
      const int x0 = 8, y0 = 8;
      fm1_tft_begin(&g_ft, 0);
      g_ft.record = 1;
      fm1_tft_font_text(&g_ft, x0, y0, s, 1, font, 0xFFFF);
      g_ft.record = 0;
      const fm1_tft_box_t *b = &g_ft.boxes[0];
      if (g_ft.n_boxes != 1 || b->x != x0 || b->y != y0 || b->w != m->ink_w ||
          b->h != m->height || b->kind != FM1_BOX_TEXT || b->font != f) {
        ++box_errors;
      }
      for (int y = 0; y < FM1_TFT_H; ++y) {
        for (int x = 0; x < FM1_TFT_W; ++x) {
          const int in = x >= x0 && x < x0 + m->ink_w && y >= y0 && y < y0 + m->height;
          if (!in && g_ft.px[y * FM1_TFT_W + x]) ++outside;
        }
      }
      printf("%s[", c > 0x20 ? "," : "");
      for (int y = 0; y < m->height; ++y) {
        putchar(y ? ',' : ' ');
        putchar('"');
        for (int x = 0; x < m->ink_w; ++x) putchar(g_ft.px[(y0 + y) * FM1_TFT_W + x0 + x] ? '#' : '.');
        putchar('"');
      }
      printf("]");
    }
    for (int n = 0; n <= (int)strlen(sample); ++n) {      /* run widths and fit counts */
      fm1_tft_begin(&g_ft, 0);
      g_ft.record = 1;
      const int w = fm1_tft_font_text(&g_ft, 0, 0, sample, n, font, 0xFFFF);
      g_ft.record = 0;
      const int want = FM1_TFT_RUN_W(m->advance, m->ink_w, n);
      if (w != want || fm1_tft_font_width(sample, n, font) != want ||
          (n && (g_ft.n_boxes != 1 || g_ft.boxes[0].w != want)) || (!n && g_ft.n_boxes)) {
        ++width_errors;
      }
      if (n && (fm1_tft_font_fit(want, font) != n || fm1_tft_font_fit(want - 1, font) != n - 1)) {
        ++fit_errors;
      }
    }
    if (fm1_tft_font_fit(FM1_TFT_W - 2 * 6, font) != line_chars[f]) ++fit_errors;
    errors += box_errors + outside + width_errors + fit_errors;
    printf("],\"box_errors\":%d,\"outside\":%d,\"width_errors\":%d,\"fit_errors\":%d}", box_errors,
           outside, width_errors, fit_errors);
  }
  printf("],\"gaps\":[");
  int first = 1;
  for (int a = 0; a < FM1_TFT_FONTS; ++a) {
    for (int b = -1; b < FM1_TFT_FONTS; ++b) {
      for (int axis = 0; axis < 2; ++axis) {
        for (int gap = 3; gap <= 4; ++gap) {
          const int faults = font_gap_faults(a, b, axis, gap);
          errors += faults != (gap < FM1_APP_LAYOUT_GAP);
          printf("%s{\"a\":\"%s\",\"b\":\"%s\",\"axis\":\"%c\",\"gap\":%d,\"faults\":%d}",
                 first ? "" : ",", kFontNames[a], b < 0 ? "graphic" : kFontNames[b],
                 axis ? 'y' : 'x', gap, faults);
          first = 0;
        }
      }
    }
  }
  printf("],\"runs\":[");
  for (int f = 0; f < FM1_TFT_FONTS; ++f) {
    const fm1_tft_font_t font = (fm1_tft_font_t)f;
    const fm1_tft_metrics_t *m = fm1_tft_metrics(font);
    /* A run cut short by max_chars is a fault; one that fits is not. */
    fm1_tft_begin(&g_ft, 0);
    g_ft.record = 1;
    fm1_tft_font_text(&g_ft, 6, 30, "S1 Timbre", 4, font, 0xFFFF);
    g_ft.record = 0;
    const int cut = fm1_tft_check_layout(&g_ft, FM1_APP_LAYOUT_GAP, NULL, 0);
    /* A box past the right edge by one pixel is off screen; at the edge it
     * is not. */
    int edge[2];
    for (int k = 0; k < 2; ++k) {
      fm1_tft_begin(&g_ft, 0);
      g_ft.record = 1;
      fm1_tft_font_text(&g_ft, FM1_TFT_W - FM1_TFT_RUN_W(m->advance, m->ink_w, 3) + k, 30, "Hgy",
                        3, font, 0xFFFF);
      g_ft.record = 0;
      edge[k] = fm1_tft_check_layout(&g_ft, FM1_APP_LAYOUT_GAP, NULL, 0);
    }
    /* MATRIX's row as one multi-colour run (audit L2), and a NULL span. */
    const fm1_tft_span_t spans[4] = {
      { "LFO1", RP_FOAM }, { ">", RP_SUBTLE }, { NULL, RP_LOVE }, { "S1 Timbre +100", RP_TEXT },
    };
    const uint16_t colour_of[19] = {
      RP_FOAM, RP_FOAM, RP_FOAM, RP_FOAM, RP_SUBTLE, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT,
      RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT, RP_TEXT,
    };
    const int x0 = 2, y0 = 40;
    fm1_tft_begin(&g_ft, RP_BASE);
    g_ft.record = 1;
    const int w = fm1_tft_span_text(&g_ft, x0, y0, spans, 4, 40, font);
    g_ft.record = 0;
    const int span_boxes = g_ft.n_boxes, span_faults = fm1_tft_check_layout(&g_ft, 4, NULL, 0);
    int colour_errors = 0, painted = 0;
    for (int i = 0; i < 19; ++i) {
      int any = 0;
      for (int y = y0; y < y0 + m->height; ++y) {
        for (int x = x0 + i * m->advance; x < x0 + (i + 1) * m->advance && x < FM1_TFT_W; ++x) {
          const uint16_t p = g_ft.px[y * FM1_TFT_W + x];
          if (p == RP_BASE) continue;
          any = 1;
          if (p != colour_of[i]) ++colour_errors;
        }
      }
      painted += any;
    }
    /* The same spans cut at 6 characters: one truncated run, 6 wide. */
    fm1_tft_begin(&g_ft, RP_BASE);
    g_ft.record = 1;
    const int w6 = fm1_tft_span_text(&g_ft, x0, y0, spans, 4, 6, font);
    g_ft.record = 0;
    const int cut6 = g_ft.truncated;
    /* With leads (MATRIX's mark, the track strip's numbers): 4 px before
     * the '>' and 4 before the destination; none before the first span or
     * the NULL one, whatever their leads say, and none before a span that
     * max_chars leaves out. Still one box, as wide as the leads make it. */
    const uint8_t lead[4] = { 7, 4, 9, 4 };
    fm1_tft_begin(&g_ft, RP_BASE);
    g_ft.record = 1;
    const int wl = fm1_tft_span_text_lead(&g_ft, x0, y0, spans, lead, 4, 40, font);
    g_ft.record = 0;
    const int lead_boxes = g_ft.n_boxes, lead_box_w = g_ft.n_boxes ? g_ft.boxes[0].w : 0;
    int lead_colour_errors = 0, lead_painted = 0;
    for (int i = 0; i < 19; ++i) {
      const int cx = x0 + i * m->advance + (i >= 4 ? 4 : 0) + (i >= 5 ? 4 : 0);
      int any = 0;
      for (int y = y0; y < y0 + m->height; ++y) {
        for (int x = cx; x < cx + m->advance && x < FM1_TFT_W; ++x) {
          const uint16_t p = g_ft.px[y * FM1_TFT_W + x];
          if (p == RP_BASE) continue;
          any = 1;
          if (p != colour_of[i]) ++lead_colour_errors;
        }
      }
      lead_painted += any;
    }
    const int lead_w4 = fm1_tft_span_width_lead(spans, lead, 4, 4, font);
    const int lead_w6 = fm1_tft_span_width_lead(spans, lead, 4, 6, font);
    /* MAIN in a face is fm1_tft_text at x2, pixel for pixel and box for box. */
    int main_same = 1;
    if (font == FM1_TFT_MAIN) {
      static fm1_tft_t ref;
      fm1_tft_begin(&ref, RP_BASE);
      fm1_tft_begin(&g_ft, RP_BASE);
      ref.record = g_ft.record = 1;
      fm1_tft_text(&ref, 7, 33, sample, 12, 2, RP_TEXT);
      fm1_tft_font_text(&g_ft, 7, 33, sample, 12, FM1_TFT_MAIN, RP_TEXT);
      ref.record = g_ft.record = 0;
      main_same = memcmp(ref.px, g_ft.px, sizeof ref.px) == 0 && ref.n_boxes == 1 &&
                  g_ft.n_boxes == 1 && ref.truncated == 1 && g_ft.truncated == 1 &&
                  memcmp(&ref.boxes[0], &g_ft.boxes[0], sizeof ref.boxes[0]) == 0;
    }
    const int want = FM1_TFT_RUN_W(m->advance, m->ink_w, 19);
    errors += cut != 1 || edge[0] != 0 || edge[1] != 1 || span_boxes != 1 || span_faults != 0 ||
              w != want || colour_errors || painted != 17 || cut6 != 1 ||
              w6 != FM1_TFT_RUN_W(m->advance, m->ink_w, 6) || !main_same ||
              fm1_tft_span_width(spans, 4, 40, font) != want;
    errors += wl != want + 8 || lead_boxes != 1 || lead_box_w != wl || lead_colour_errors ||
              lead_painted != 17 || fm1_tft_span_width_lead(spans, lead, 4, 40, font) != wl ||
              lead_w4 != FM1_TFT_RUN_W(m->advance, m->ink_w, 4) ||
              lead_w6 != FM1_TFT_RUN_W(m->advance, m->ink_w, 6) + 8;
    printf("%s{\"font\":\"%s\",\"cut_faults\":%d,\"edge_faults\":[%d,%d],\"span_boxes\":%d,"
           "\"span_faults\":%d,\"span_w\":%d,\"span_want_w\":%d,\"colour_errors\":%d,"
           "\"painted\":%d,\"cut6\":%d,\"w6\":%d,\"main_same\":%d,\"lead_w\":%d,"
           "\"lead_boxes\":%d,\"lead_box_w\":%d,\"lead_colour_errors\":%d,\"lead_painted\":%d,"
           "\"lead_w4\":%d,\"lead_w6\":%d}",
           f ? "," : "", kFontNames[f], cut, edge[0], edge[1], span_boxes, span_faults, w, want,
           colour_errors, painted, cut6, w6, main_same, wl, lead_boxes, lead_box_w,
           lead_colour_errors, lead_painted, lead_w4, lead_w6);
  }
  printf("],\"errors\":%d}\n", errors);
  return errors ? 1 : 0;
}

/* --font-sheet FILE.ppm: both Spleen faces' characters and a few names in
 * MID and SMALL, under MAIN headings, as one screen that passes the layout
 * check; prints its faults and boxes. A sheet to look at, not a page. */
static int font_sheet(const char *path) {
  static const struct { int font; const char *s; uint16_t color; } rows[] = {
    { FM1_TFT_MAIN, "MID: Spleen 8x16", RP_IRIS },
    { FM1_TFT_MID, "ABCDEFGHIJKLMNOPQRSTUVWXYZ", RP_TEXT },
    { FM1_TFT_MID, "abcdefghijklmnopqrstuvwxyz", RP_TEXT },
    { FM1_TFT_MID, "0123456789 !\"#$%&'()*+,-./:;", RP_TEXT },
    { FM1_TFT_MID, "<=>?@[\\]^_`{|}~  S1 Timbre", RP_TEXT },
    { FM1_TFT_MAIN, "SMALL: Spleen 6x12", RP_IRIS },
    { FM1_TFT_SMALL, "ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789", RP_TEXT },
    { FM1_TFT_SMALL, "abcdefghijklmnopqrstuvwxyz", RP_TEXT },
    { FM1_TFT_SMALL, "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~", RP_TEXT },
  };
  fm1_tft_begin(&g_ft, RP_BASE);
  g_ft.record = 1;
  int y = 4;
  for (size_t i = 0; i < sizeof rows / sizeof rows[0]; ++i) {
    const fm1_tft_font_t font = (fm1_tft_font_t)rows[i].font;
    fm1_tft_font_text(&g_ft, MARGIN, y, rows[i].s, 40, font, rows[i].color);
    y += fm1_tft_metrics(font)->height + FM1_APP_LAYOUT_GAP;
  }
  const fm1_tft_span_t matrix[3] = {
    { "LFO1", RP_FOAM }, { " > ", RP_SUBTLE }, { "S1 Timbre  +100", RP_TEXT },
  };
  fm1_tft_span_text(&g_ft, MARGIN, y, matrix, 3, MID_LINE_CHARS, FM1_TFT_MID);
  y += MID_LINE_PITCH;
  const fm1_tft_span_t matrix2[3] = {
    { "ENV2", RP_FOAM }, { " ~ ", RP_SUBTLE }, { "M2 Ping-Pong Delay Feedback -35", RP_TEXT },
  };
  fm1_tft_span_text(&g_ft, MARGIN, y, matrix2, 3, SMALL_LINE_CHARS, FM1_TFT_SMALL);
  y += SMALL_LINE_PITCH;
  /* A MAIN name and a MID place on one baseline. */
  fm1_tft_font_text(&g_ft, MARGIN, y, "Six-Op FM", 20, FM1_TFT_MAIN, RP_TEXT);
  const char *place = "34/96";
  fm1_tft_font_text(&g_ft, RIGHT - fm1_tft_font_width(place, 8, FM1_TFT_MID),
                    y + FM1_TFT_MAIN_BASELINE - FM1_TFT_MID_BASELINE, place, 8, FM1_TFT_MID,
                    RP_SUBTLE);
  g_ft.record = 0;
  const int faults = fm1_tft_check_layout(&g_ft, FM1_APP_LAYOUT_GAP, NULL, 0);
  printf("{\"faults\":%d,\"boxes\":%d,\"bottom\":%d}\n", faults, g_ft.n_boxes, y + FM1_TFT_MAIN_H);
  if (!write_ppm(path, &g_ft)) {
    fprintf(stderr, "cannot write %s\n", path);
    return 2;
  }
  return faults ? 1 : 0;
}

/* ---- the render ---------------------------------------------------------------- */

/* Multi-sound set-up from the command line (--sound, --insert, their
 * parameters and --level), applied after the sound and the master effects,
 * in fm1-render's order. */
typedef struct {
  char id[32];
  int np;
  char pname[16][32];
  float pval[16];
} unit_spec_t;
static unit_spec_t g_more[FM1_APP_SOUNDS];                 /* [0] unused: --engine */
static unit_spec_t g_ins[FM1_APP_SOUNDS][FM1_APP_INSERTS];
static int g_nins[FM1_APP_SOUNDS];
static float g_level[FM1_APP_SOUNDS];
static int g_level_set[FM1_APP_SOUNDS];
static int g_multi;                                         /* any multi-sound flag */

/* "K:REST" with K a sound unit 0..3: K, and REST in *rest; -1 if malformed. */
static int sound_arg(const char *v, const char **rest) {
  char *end = NULL;
  const long k = strtol(v, &end, 10);
  if (end == v || *end != ':' || k < 0 || k >= FM1_APP_SOUNDS) return -1;
  *rest = end + 1;
  return (int)k;
}

static int add_unit_param(unit_spec_t *u, const char *arg) {
  if (u->np >= 16 || !split_param(arg, u->pname[u->np], sizeof u->pname[0], &u->pval[u->np])) return 0;
  ++u->np;
  return 1;
}

/* --sound, --sound-param, --insert, --insert-param, --level, --sound-note,
 * --sound-param-at and --level-at: 1, or 0 for a malformed value. */
static int add_multi(const char *flag, const char *v) {
  const char *rest = NULL;
  const int k = sound_arg(v, &rest);
  g_multi = 1;
  if (k < 0) return 0;
  if (strcmp(flag, "--sound") == 0) {
    if (k == 0) return 0;                               /* unit 0 is --engine */
    snprintf(g_more[k].id, sizeof g_more[k].id, "%s", rest);
    return 1;
  }
  if (strcmp(flag, "--sound-param") == 0) return add_unit_param(&g_more[k], rest);
  if (strcmp(flag, "--insert") == 0) {
    if (g_nins[k] >= FM1_APP_INSERTS) return 0;
    snprintf(g_ins[k][g_nins[k]++].id, sizeof g_ins[k][0].id, "%s", rest);
    return 1;
  }
  if (strcmp(flag, "--insert-param") == 0) return g_nins[k] && add_unit_param(&g_ins[k][g_nins[k] - 1], rest);
  if (strcmp(flag, "--level") == 0) {           /* 0..100, as fm1-render takes it */
    g_level[k] = (float)atof(rest);
    g_level_set[k] = 1;
    return g_level[k] >= 0.0f && g_level[k] <= 100.0f;
  }
  if (strcmp(flag, "--sound-note") == 0) {
    double t, dur;
    int key, vel;
    if (sscanf(rest, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) return 0;
    event_t *on = add_event(t, EV_NOTE);
    on->on = 1, on->a = key, on->b = vel, on->sound = k;
    event_t *off = add_event(t + dur, EV_NOTE);
    off->on = 0, off->a = key, off->sound = k;
    return 1;
  }
  {                                                     /* --sound-param-at, --level-at: K:T:... */
    const char *colon = strchr(rest, ':');
    event_t *e;
    if (!colon) return 0;
    e = add_event(atof(rest), strcmp(flag, "--level-at") == 0 ? EV_LEVEL : EV_PARAM);
    e->sound = k;
    if (e->kind == EV_LEVEL) {
      e->value = (float)atof(colon + 1);
      return e->value >= 0.0f && e->value <= 100.0f;
    }
    return split_param(colon + 1, e->name, sizeof e->name, &e->value);
  }
}

static int is_multi_flag(const char *a) {
  return strcmp(a, "--sound") == 0 || strcmp(a, "--sound-param") == 0 || strcmp(a, "--insert") == 0 ||
         strcmp(a, "--insert-param") == 0 || strcmp(a, "--level") == 0 ||
         strcmp(a, "--sound-note") == 0 || strcmp(a, "--sound-param-at") == 0 ||
         strcmp(a, "--level-at") == 0;
}

/* Loads the multi-sound set-up: 0, or 1 after saying what failed. */
static int load_multi(void) {
  for (int k = 1; k < FM1_APP_SOUNDS; ++k) {
    const int u = fm1_app_sound_unit(k);
    if (!g_more[k].id[0]) {
      if (g_more[k].np) { fprintf(stderr, "--sound-param for sound unit %d without --sound\n", k); return 1; }
      continue;
    }
    const int r = fm1_app_select(&g_app, u, fm1_app_find(g_more[k].id));
    if (r) { fprintf(stderr, "cannot load %s into sound unit %d (%d)\n", g_more[k].id, k, r); return 1; }
    for (int q = 0; q < g_more[k].np; ++q) {
      const int idx = fm1_app_param_index(&g_app, u, g_more[k].pname[q]);
      if (idx < 0) { fprintf(stderr, "unknown parameter for %s: %s\n", g_more[k].id, g_more[k].pname[q]); return 1; }
      fm1_app_set_param(&g_app, u, idx, g_more[k].pval[q]);
    }
  }
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    for (int j = 0; j < g_nins[k]; ++j) {
      const int u = fm1_app_insert_unit(k, j);
      const int r = fm1_app_select(&g_app, u, fm1_app_find(g_ins[k][j].id));
      if (r) { fprintf(stderr, "cannot load %s as insert %d of sound unit %d (%d)\n", g_ins[k][j].id, j, k, r); return 1; }
      for (int q = 0; q < g_ins[k][j].np; ++q) {
        const int idx = fm1_app_param_index(&g_app, u, g_ins[k][j].pname[q]);
        if (idx < 0) { fprintf(stderr, "unknown parameter for %s: %s\n", g_ins[k][j].id, g_ins[k][j].pname[q]); return 1; }
        fm1_app_set_param(&g_app, u, idx, g_ins[k][j].pval[q]);
      }
    }
    if (g_level_set[k]) fm1_app_unit_set_level(&g_app, k, g_level[k]);
  }
  return 0;
}

/* The unit an EV_PARAM turns: a master effect (--fx-param-at, `a` 1 or 2),
 * else the sound unit `sound` (--param-at is Sound 1, --sound-param-at K). */
static int param_unit(const event_t *e) {
  return e->a > 0 ? e->a : fm1_app_sound_unit(e->sound);
}

static int find_param(int unit, const char *name) {
  int i = fm1_app_param_index(&g_app, unit, name);
  if (i < 0) fprintf(stderr, "unknown parameter for unit %d: %s\n", unit, name);
  return i;
}

/* A run stopped in the middle (a refused --unit-route, --seq-reset or
 * --seq-import): what it holds goes, so the sanitizers' leak check (CI's
 * ASan job, on Linux) sees only the refusal. Returns `code`. */
static int abandon_run(int code, float *out, fm1_script_t *script) {
  for (int k = 0; k < g_ui_log_n; ++k) free(g_ui_log_text[k]);
  for (int k = 0; k < g_nside; ++k) free(g_side_value[k]);
  g_ui_log_n = g_nside = 0;
  fm1_script_free(script);
  destroy_units();
  free(out);
  return code;
}

/* ---- the arpeggiator: flags, the sidecar and the log ---------------------------- */

static float g_rate = 44118.0f;
static int g_mfx_sided[FM1_APP_SOUNDS];   /* the sidecar has the sound's --mfx */
static int g_mfx_log_side;                /* log arp changes into the sidecar */

/* Every change of an arp (fm1_app_t.on_mfx), into the sidecar at the block
 * it led, as --mfx-on-at or --mfx-param-at at mid-block. */
static void on_mfx(void *ctx, uint64_t frame, int sound, int param, float value) {
  const fm1_engine_t *e = fm1_app_mfx_engine(&g_app, sound);
  const double t = frame ? ((double)frame - 32.0) / g_rate : 0.0;
  char buf[160];
  (void)ctx;
  if (!g_mfx_log_side || sound < 0 || sound >= FM1_APP_SOUNDS || !e) return;
  if (param == -2 && g_mfx_sided[sound]) {   /* another effect, once the sidecar named one */
    g_replayable = 0;
    return;
  }
  if (!g_mfx_sided[sound]) {
    snprintf(buf, sizeof buf, "%d:%s:off", sound, e->id);
    side("--mfx", buf);
    g_mfx_sided[sound] = 1;
  }
  if (param == -2) return;
  if (param < 0) {
    snprintf(buf, sizeof buf, "%d:%.9f:%d", sound, t, value != 0.0f);
    side("--mfx-on-at", buf);
  } else if (param < e->n_params) {
    snprintf(buf, sizeof buf, "%d:%.9f:%s=%.9g", sound, t, e->params[param].name, (double)value);
    side("--mfx-param-at", buf);
  }
}

/* --mfx and --mfx-param, before the first block. */
#define MAX_MFX_PARAMS 64
static int g_mfx_on[FM1_APP_SOUNDS];      /* 0 none, 1 on, 2 off (K:ID:off) */
static char g_mfx_id[FM1_APP_SOUNDS][32];  /* the effect each --mfx named */
static int g_mfx_np;
static int g_mfx_psound[MAX_MFX_PARAMS];
static char g_mfx_pname[MAX_MFX_PARAMS][32];
static float g_mfx_pval[MAX_MFX_PARAMS];

/* K:... of an --mfx flag: the sound unit, `rest` past its colon (and past
 * a ".1" slot); -1 when malformed or another slot. */
static int mfx_unit(const char *v, const char **rest) {
  char *end = NULL;
  const long k = strtol(v, &end, 10);
  if (end == v || k < 0 || k >= FM1_APP_SOUNDS) return -1;
  if (*end == '.') {
    char *e2 = NULL;
    if (strtol(end + 1, &e2, 10) != 1 || e2 == end + 1) return -1;   /* the app's arp is slot 1 */
    end = e2;
  }
  if (*end != ':') return -1;
  *rest = end + 1;
  return (int)k;
}

static int add_mfx(const char *flag, const char *v) {
  const char *rest = NULL;
  const int k = mfx_unit(v, &rest);
  if (k < 0) return 0;
  if (strcmp(flag, "--mfx") == 0) {
    const char *colon = strchr(rest, ':');
    const size_t n = colon ? (size_t)(colon - rest) : strlen(rest);
    if (!n || n >= sizeof g_mfx_id[0] || (colon && strcmp(colon, ":off") != 0)) return 0;
    memcpy(g_mfx_id[k], rest, n);
    g_mfx_id[k][n] = 0;
    if (!fm1_midi_fx_find(g_mfx_id[k])) return 0;
    g_mfx_on[k] = colon ? 2 : 1;
    return 1;
  }
  if (strcmp(flag, "--mfx-param") == 0) {
    if (g_mfx_np >= MAX_MFX_PARAMS || !g_mfx_on[k]) return 0;
    g_mfx_psound[g_mfx_np] = k;
    if (!split_param(rest, g_mfx_pname[g_mfx_np], sizeof g_mfx_pname[0], &g_mfx_pval[g_mfx_np])) return 0;
    ++g_mfx_np;
    return 1;
  }
  {                                         /* --mfx-param-at, --mfx-on-at: K:T:... */
    const char *c2 = strchr(rest, ':');
    event_t *e;
    if (!c2) return 0;
    e = add_event(atof(rest), strcmp(flag, "--mfx-on-at") == 0 ? EV_MFX_ON : EV_MFX_PARAM);
    e->sound = k;
    if (e->kind == EV_MFX_ON) {
      e->value = atof(c2 + 1) != 0.0 ? 1.0f : 0.0f;
      return 1;
    }
    return split_param(c2 + 1, e->name, sizeof e->name, &e->value);   /* checked by load_mfx */
  }
}

/* The flags' effects: put in their slots, switched on, then their
 * parameters; the timed ones checked against them. 0, or 1 after saying
 * what failed. */
static int load_mfx(void) {
  for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
    if (!g_mfx_on[k]) continue;
    if (fm1_app_mfx_select(&g_app, k, g_mfx_id[k]) != 0) {
      fprintf(stderr, "cannot put %s in sound %d's MIDI-FX slot\n", g_mfx_id[k], k);
      return 1;
    }
    if (g_mfx_on[k] == 1) fm1_app_arp_set_on(&g_app, k, 1);
  }
  for (int q = 0; q < g_mfx_np; ++q) {
    const int idx = fm1_app_mfx_param_index(&g_app, g_mfx_psound[q], g_mfx_pname[q]);
    if (idx < 0) { fprintf(stderr, "unknown parameter for %s: %s\n", g_mfx_id[g_mfx_psound[q]], g_mfx_pname[q]); return 1; }
    fm1_app_arp_set_param(&g_app, g_mfx_psound[q], idx, g_mfx_pval[q]);
  }
  for (int k = 0; k < g_nev; ++k) {
    if (g_ev[k].kind == EV_MFX_PARAM && fm1_app_mfx_param_index(&g_app, g_ev[k].sound, g_ev[k].name) < 0) {
      fprintf(stderr, "unknown parameter for sound %d's MIDI effect: %s\n", g_ev[k].sound, g_ev[k].name);
      return 1;
    }
  }
  return 0;
}

/* --log-mfx: what each arp sent its sound in the block at `pos`, by frame
 * and then sound, as fm1-render writes it. */
static void log_mfx(FILE *f, uint32_t pos) {
  uint32_t m[FM1_MFX_CHAINS], j[FM1_MFX_CHAINS];
  const fm1_midi_ev_t *o[FM1_MFX_CHAINS];
  if (!f) return;
  for (unsigned c = 0; c < FM1_MFX_CHAINS; ++c) {
    o[c] = fm1_mfx_output(&g_app.mfx, c, &m[c]);
    j[c] = 0;
  }
  for (;;) {
    int best = -1;
    for (unsigned c = 0; c < FM1_MFX_CHAINS; ++c) {
      if (j[c] < m[c] && (best < 0 || o[c][j[c]].frame < o[best][j[best]].frame)) best = (int)c;
    }
    if (best < 0) break;
    {
      const fm1_midi_ev_t *e = &o[best][j[best]++];
      if (e->kind == FM1_MIDI_EV_NOTE_ON && e->b) {
        fprintf(f, "{\"t\":%llu,\"u\":%d,\"k\":\"on\",\"key\":%u,\"vel\":%u}\n",
                (unsigned long long)pos + e->frame, best, e->a, e->b);
      } else {
        fprintf(f, "{\"t\":%llu,\"u\":%d,\"k\":\"off\",\"key\":%u}\n",
                (unsigned long long)pos + e->frame, best, e->a);
      }
    }
  }
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
  const char *mod_path = NULL, *log_mfx_path = NULL;
  FILE *log_mfx_file = NULL;
  char log_mod_path[1024] = "";
  int tracks = -1, seconds_given = 0, rate_given = 0, n_routes = 0;
  long events_cap = -1;
  route_t routes[MAX_ROUTES];
  int side_note_pair_later = 0;
  const char *sysex_path[8];
  int sysex_play[8], n_sysex = 0;

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
    if (strcmp(a, "--lock-check") == 0) return lock_check();
    if (strcmp(a, "--mod-format-check") == 0) return mod_format_check();
    if (strcmp(a, "--font-check") == 0) return font_check();
    if (strcmp(a, "--slots") == 0) continue;                 /* implied: the app routes by slot */
    if (strcmp(a, "--start") == 0) { g_start = 1; continue; }
    if (i + 1 >= argc) { usage(); return 2; }
    const char *v = argv[++i];
    /* What fm1-render needs to replay a --log-cmds file (its sidecar). */
    if (strcmp(a, "--engine") == 0 || strcmp(a, "--param") == 0 || strcmp(a, "--fx") == 0 ||
        strcmp(a, "--fx-param") == 0 || strcmp(a, "--note") == 0 || strcmp(a, "--bend") == 0 ||
        strcmp(a, "--param-at") == 0 || strcmp(a, "--fx-param-at") == 0 ||
        strcmp(a, "--seq") == 0 || strcmp(a, "--route") == 0 || strcmp(a, "--sysex") == 0 ||
        is_multi_flag(a)) {
      side(a, v);
      if (strcmp(a, "--sound-note") == 0) side_note_pair_later = 1;
    }
    if (strcmp(a, "--screens") == 0) return run_screens(v, rate);
    if (strcmp(a, "--font-sheet") == 0) return font_sheet(v);
    else if (is_multi_flag(a)) {
      if (!add_multi(a, v)) { fprintf(stderr, "bad %s %s\n", a, v); return 2; }
      if (side_note_pair_later) side_note_pair();          /* the --sound-note just added */
      side_note_pair_later = 0;
    }
    else if (strcmp(a, "--panel") == 0) { if (!read_panel(v)) return 2; }
    else if (strcmp(a, "--mfx") == 0 || strcmp(a, "--mfx-param") == 0 ||
             strcmp(a, "--mfx-param-at") == 0 || strcmp(a, "--mfx-on-at") == 0) {
      if (!add_mfx(a, v)) { fprintf(stderr, "bad %s %s\n", a, v); return 2; }
    }
    else if (strcmp(a, "--log-mfx") == 0) log_mfx_path = v;
    else if (strcmp(a, "--sysex") == 0 || strcmp(a, "--sysex-play") == 0) {
      if (n_sysex >= 8) { usage(); return 2; }
      sysex_play[n_sysex] = strcmp(a, "--sysex-play") == 0;
      sysex_path[n_sysex++] = v;
      if (strcmp(a, "--sysex-play") == 0) g_replayable = 0;   /* fm1-render has no such step */
    }
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
    } else if (strcmp(a, "--unit-route") == 0) {
      double t;
      int track, sound;
      if (sscanf(v, "%lf:%d:%d", &t, &track, &sound) != 3) { usage(); return 2; }
      event_t *e = add_event(t, EV_UNIT_ROUTE);
      e->a = track;
      e->b = sound;
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
      side_note_pair();                    /* copied into the sidecar above */
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
    } else if (strcmp(a, "--fx-param-at") == 0) {
      /* T:K:NAME=V, K the effect's place in the chain (1 = the first --fx), as fm1-render */
      const char *c1 = strchr(v, ':');
      const char *c2 = c1 ? strchr(c1 + 1, ':') : NULL;
      char *end = NULL;
      long unit = c1 ? strtol(c1 + 1, &end, 10) : 0;
      event_t *e;
      if (!c2 || end != c2 || unit < 1 || unit > FM1_APP_FX_SLOTS) {
        fprintf(stderr, "--fx-param-at wants T:K:NAME=V, K from 1 to %d\n", FM1_APP_FX_SLOTS);
        return 2;
      }
      e = add_event(atof(v), EV_PARAM);
      e->a = (int)unit;
      if (!split_param(c2 + 1, e->name, sizeof e->name, &e->value)) { usage(); return 2; }
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
  /* Before anything is loaded, so a refusal leaves nothing allocated. */
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
    if (!cmd_path) { script.rate = 44118; script.tracks = 8; }
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
         g_ev[k].kind == EV_SEQ_UI || g_ev[k].kind == EV_UNIT_ROUTE) && !use_seq) {
      fprintf(stderr, "--seq-reset, --seq-import, --seq-ui and --unit-route need --cmd or --seq\n");
      return 2;
    }
  }

  fm1_app_init(&g_app, rate);
  if (master != 1.0f) g_replayable = 0;      /* fm1-render has no MASTER */
  if (engine) {
    int r = fm1_app_select(&g_app, 0, fm1_app_find(engine));
    if (r) { fprintf(stderr, "cannot load %s (%d)\n", engine, r); return 1; }
  }
  /* --sysex: after the sound is loaded, before its parameters (fm1-render
   * --sysex's order). */
  int sysex_n[8], sysex_played[8];
  fm1_dx7_sysex_result_t sysex_r[8];
  for (int k = 0; k < n_sysex; ++k) {
    static uint8_t file[FM1_APP_DX7_FILE_MAX + 1];
    FILE *f = fopen(sysex_path[k], "rb");
    size_t len;
    if (!f) { fprintf(stderr, "--sysex: cannot open %s\n", sysex_path[k]); return 1; }
    len = fread(file, 1, sizeof file, f);   /* one byte past the limit: refused */
    fclose(f);
    sysex_n[k] = fm1_app_dx7_load(&g_app, file, len, &sysex_r[k]);
    sysex_played[k] = sysex_play[k] && sysex_n[k] > 0 ? fm1_app_dx7_play(&g_app, sysex_r[k].first_slot) : 1;
  }
  if (engine) {
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
  if (load_multi()) return 1;               /* after the sound and the master bus, as fm1-render */
  g_rate = rate;
  g_app.on_mfx = on_mfx;                    /* the arps' changes, for the sidecar */
  g_mfx_log_side = log_cmds_path != NULL;
  if (load_mfx()) return 1;
  if (log_mfx_path && !(log_mfx_file = fopen(log_mfx_path, "w"))) {
    fprintf(stderr, "cannot write %s\n", log_mfx_path);
    return 1;
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
    g_app.on_note_in = on_note_in;
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
  } else {
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
    if (g_ev[k].kind == EV_PARAM && find_param(param_unit(&g_ev[k]), g_ev[k].name) < 0) {
      return 1;
    }
    /* A note or a level on an empty sound unit is taken (it plays
     * nothing, as fm1-render plays it); a parameter needs the engine. */
    if (g_ev[k].kind == EV_PARAM && g_ev[k].sound > 0 && !fm1_app_unit_engine(&g_app, g_ev[k].sound)) {
      fprintf(stderr, "--sound-param-at for sound unit %d, which has no --sound\n", g_ev[k].sound);
      return 2;
    }
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
      if (e->kind == EV_BEND) {
        if (g_app.sound != 0) g_replayable = 0;       /* fm1-render bends sound 0 */
        fm1_app_pitch_bend(&g_app, e->value);
      } else if (e->kind == EV_PARAM) {
        const int u = param_unit(e);
        fm1_app_set_param(&g_app, u, find_param(u, e->name), e->value);
      } else if (e->kind == EV_LEVEL) {
        fm1_app_unit_set_level(&g_app, e->sound, e->value);
      } else if (e->kind == EV_MFX_ON) {
        fm1_app_arp_set_on(&g_app, e->sound, e->value != 0.0f);
      } else if (e->kind == EV_MFX_PARAM) {
        fm1_app_arp_set_param(&g_app, e->sound, fm1_app_mfx_param_index(&g_app, e->sound, e->name),
                              e->value);
      }
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
          return abandon_run(2, out, &script);
        }
        if (e->kind == EV_SEQ_IMPORT && !import_file(strchr(argv[e->a], ':') + 1)) {
          return abandon_run(1, out, &script);
        }
        rest = NULL;                   /* what was queued went with the instance */
        if (!n_routes) fm1_app_seq_default_route(&g_app);
      } else if (e->kind == EV_SEQ_UI) {
        const char *op = strchr(argv[e->a], ':') + 1;
        if (g_ui_n >= MAX_UI) { usage(); return abandon_run(2, out, &script); }
        fm1_seq_parse(op, strlen(op), &g_ui[g_ui_n++]);
      } else if (e->kind == EV_UNIT_ROUTE) {
        const int r = fm1_app_unit_route(&g_app, e->a, e->b);
        if (r == FM1_APP_SEQ_BUSY) continue;            /* again after the next render */
        if (r == FM1_APP_SEQ_REFUSED) {
          fprintf(stderr, "--unit-route %d:%d refused\n", e->a, e->b);
          return abandon_run(2, out, &script);
        }
      } else continue;
      e->done = 1;
    }
    for (int pass = 0; pass < 2; ++pass) {             /* offs before ons */
      /* fm1-render plays a block's due note-offs, then its note-ons, each in
       * the order of its --note arguments. A note the app plays here out of
       * that order (a MIDI IN note after a key's in the same block, whose
       * --note was added when the key was pressed) cannot be replayed. */
      int last_side = 0;
      for (int k = 0; k < g_nev; ++k) {
        event_t *e = &g_ev[k];
        int ix = 0;
        if (e->done || e->time > now || e->on != pass) continue;
        if (e->kind == EV_NOTE && e->sound >= 0) {     /* --sound-note: that unit */
          if (e->on) fm1_app_unit_note_on(&g_app, e->sound, e->a, e->b);
          else fm1_app_unit_note_off(&g_app, e->sound, e->a);
          ix = e->side;
        } else if (e->kind == EV_NOTE) {               /* MIDI IN: the current sound */
          const int pitch = e->a < 0 ? 0 : (e->a > 127 ? 127 : e->a);
          if (e->on) {
            /* Replayed on the unit it plays now; a pitch another unit holds
             * would make its note-off ambiguous. */
            for (int u = 0; u < FM1_APP_SOUNDS; ++u) {
              if (u != g_app.sound && g_app.note_count[u][pitch]) g_replayable = 0;
            }
            if (e->side && g_app.sound && strcmp(g_side_flag[e->side - 1], "--note") == 0) {
              char buf[160];
              snprintf(buf, sizeof buf, "%d:%s", g_app.sound, g_side_value[e->side - 1]);
              free(g_side_value[e->side - 1]);
              g_side_value[e->side - 1] = malloc(strlen(buf) + 1);
              if (!g_side_value[e->side - 1]) exit(2);
              memcpy(g_side_value[e->side - 1], buf, strlen(buf) + 1);
              g_side_flag[e->side - 1] = "--sound-note";
            }
            for (int j = k + 1; j < g_nev; ++j) {      /* its off: where this on went */
              if (g_ev[j].kind == EV_NOTE && !g_ev[j].on && g_ev[j].side == e->side &&
                  g_ev[j].a == e->a && !g_ev[j].done) {
                g_ev[j].played = g_app.sound;
                break;
              }
            }
            fm1_app_note_on(&g_app, e->a, e->b);
          } else {
            int to = g_app.sound;                      /* fm1_app_note_off's choice */
            for (int u = 0; u < FM1_APP_SOUNDS && !g_app.note_count[to][pitch]; ++u) {
              if (g_app.note_count[u][pitch]) to = u;
            }
            if (to != e->played) g_replayable = 0;
            fm1_app_note_off(&g_app, e->a);
          }
          ix = e->side;
        } else if (e->kind == EV_KEY) {
          const int was_down = g_app.key_down[e->a], was_side = g_key_side[e->a];
          fm1_app_key(&g_app, e->a, e->on, e->b);
          key_logged(e->a, was_down, pos, rate);
          if (!was_down && g_app.key_down[e->a]) ix = g_key_side[e->a];
          else if (was_down && !g_app.key_down[e->a]) ix = was_side;
        } else {
          continue;
        }
        if (ix) {
          if (ix < last_side) g_replayable = 0;
          last_side = ix;
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
    log_mfx(log_mfx_file, pos);
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
  if (log_mfx_file) fclose(log_mfx_file);
  if (out_path && !write_wav(out_path, out, total, (uint32_t)lrintf(rate))) {
    fprintf(stderr, "cannot write %s\n", out_path);
    return 1;
  }
  if (screen_path) {
    fm1_app_draw(&g_app, 0);
    if (!write_ppm(screen_path, &g_app.tft)) return 1;
  }
  int sounding = 0, key_scale = 0;
  for (int u = 0; u < FM1_APP_SOUNDS; ++u) {
    for (int n = 0; n < 128; ++n) sounding += g_app.note_count[u][n];
  }
  fm1_app_project_key(&g_app, &key_scale);   /* the project key, the set's (or the stage's) */
  printf("{\"engine\":\"%s\",\"rate\":%g,\"frames\":%u,\"peak\":%.6f,\"rms\":%.6f,"
         "\"ram\":%u,\"mode\":%d,\"octave\":%d,\"transpose\":%d,\"sounding\":%d,"
         "\"fx\":[\"%s\",\"%s\"],\"fx_slot\":%d,\"fx_page\":%d,\"glo_page\":%d,"
         "\"key\":[%d,%d],\"leds\":\"",
         g_app.unit[0].e ? g_app.unit[0].e->id : "", (double)rate, total, (double)peak,
         total ? sqrt(sum2 / (2.0 * total)) : 0.0, (unsigned)fm1_app_ram(&g_app), g_app.mode,
         g_app.octave, g_app.transpose, sounding, g_app.unit[1].e ? g_app.unit[1].e->id : "",
         g_app.unit[2].e ? g_app.unit[2].e->id : "", g_app.fx_slot, g_app.fx_page, g_app.glo_page,
         fm1_app_project_key(&g_app, NULL), key_scale);
  for (int i = 0; i < FM1_APP_LEDS; ++i) putchar(g_app.led[i] ? '1' : '0');
  printf("\",\"popup\":[");
  for (int i = 0; i < g_app.popup_lines; ++i) {
    printf(i ? ",\"%s\"" : "\"%s\"", g_app.popup[i]);   /* popups hold plain names */
  }
  printf("]");
  if (g_app.popup_lines && g_app.popup_total > 0) {   /* a list's window: popup[0] is entry first */
    static const char *const kFace[] = { "MAIN", "MID", "SMALL" };
    printf(",\"popup_list\":{\"title\":\"%s\",\"first\":%d,\"total\":%d,\"mark\":%d}",
           g_app.popup_title, g_app.popup_first, g_app.popup_total, g_app.popup_mark);
    /* Its face and the most entries that face shows (fm1_panel.h). */
    printf(",\"popup_face\":\"%s\",\"popup_rows\":%d",
           g_app.popup_face >= 0 && g_app.popup_face < 3 ? kFace[g_app.popup_face] : "?",
           fm1_list_rows(g_app.popup_face));
    /* Each entry's sound + 1 when its "S<n>" is drawn in that sound's colour. */
    printf(",\"popup_tags\":[");
    for (int i = 0; i < g_app.popup_lines; ++i) {
      printf(i ? ",%u" : "%u", (unsigned)((g_app.popup_tag >> (4 * i)) & 15u));
    }
    printf("]");
  } else {
    char banner[FM1_LIST_ENTRY];
    printf(",\"popup_list\":null");
    if (g_app.popup_lines) {               /* a message: a refusal, a banner or a popup */
      printf(",\"popup_tone\":\"%s\"", g_app.popup_tone == FM1_APP_TONE_SAY ? "say" : "refuse");
      const int face = fm1_app_banner(&g_app, banner, sizeof banner);
      if (face) {
        printf(",\"popup_banner\":\"%s\",\"popup_banner_face\":\"%s\"", banner,
               face == 1 + FM1_TFT_MID ? "MID" : "MAIN");
      }
    }
  }
  for (int u = 0; u < FM1_APP_UNITS; ++u) {
    printf(",\"values%d\":[", u);
    const fm1_engine_t *e = g_app.unit[u].e;
    for (uint16_t p = 0; e && p < e->n_params; ++p) printf(p ? ",%g" : "%g", (double)g_app.unit[u].value[p]);
    printf("]");
  }
  {                                  /* the MIDI-FX slots: their effects, on, their parameters, the page */
    printf(",\"arp\":{\"effect\":[");
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      const fm1_engine_t *me = fm1_app_mfx_engine(&g_app, k);
      printf(k ? ",\"%s\"" : "\"%s\"", me ? me->id : "");
    }
    printf("],\"on\":[");
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) printf(k ? ",%d" : "%d", fm1_app_arp_on(&g_app, k));
    printf("],\"page\":%d,\"preset\":%d,\"values\":[", g_app.arp_page,
           fm1_app_arp_preset_of(&g_app, g_app.sound));
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      const fm1_engine_t *ae = fm1_app_mfx_engine(&g_app, k);
      printf(k ? ",[" : "[");
      for (uint16_t i = 0; ae && i < ae->n_params; ++i) printf(i ? ",%g" : "%g", (double)g_app.arp_value[k][i]);
      printf("]");
    }
    printf("],\"notes_in\":%llu,\"notes_out\":%llu,\"ticks\":%llu,\"direct\":%llu,\"dropped\":%llu}",
           (unsigned long long)g_app.mfx.stats.notes_in, (unsigned long long)g_app.mfx.stats.notes_out,
           (unsigned long long)g_app.mfx.stats.ticks, (unsigned long long)g_app.mfx.stats.direct,
           (unsigned long long)g_app.mfx.stats.dropped);
  }
  if (g_app.mui.unloggable) g_replayable = 0;    /* a modulation edit no line can say */
  printf(",\"replayable\":%d", g_replayable);
  if (n_sysex) {
    printf(",\"dx7\":{\"files\":[");
    for (int k = 0; k < n_sysex; ++k) {
      const fm1_dx7_sysex_result_t *r = &sysex_r[k];
      printf("%s{\"result\":%d,\"played\":%d,\"voices\":%u,\"first_slot\":%u,\"messages\":%u,"
             "\"bad_checksums\":%u,\"skipped\":%u,\"foreign\":%u,\"truncated\":%u,"
             "\"wrong_size\":%u,\"raw\":%u,\"outside\":%u}", k ? "," : "", sysex_n[k], sysex_played[k],
             r->voices, r->first_slot, r->messages, r->bad_checksums, r->skipped, r->foreign,
             r->truncated, r->wrong_size, r->raw, (unsigned)r->outside);
    }
    printf("],\"names\":[");
    for (unsigned k = 0; k < FM1_DX7_USER_SLOTS; ++k) {
      if (k) putchar(',');
      json_string(fm1_app_dx7_name(&g_app, k));
    }
    printf("],\"next\":%u}", g_app.dx7.next);
  }
  if (g_app.mod) print_mod();
  {                                  /* multi-sound: the units, the current one, levels, inserts */
    printf(",\"current\":%d,\"sounds\":[", fm1_app_unit_current(&g_app));
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      const fm1_engine_t *e = fm1_app_unit_engine(&g_app, k);
      printf(k ? ",\"%s\"" : "\"%s\"", e ? e->id : "");
    }
    printf("],\"levels\":[");
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) printf(k ? ",%g" : "%g", (double)fm1_app_unit_level(&g_app, k));
    printf("],\"inserts\":[");
    for (int k = 0; k < FM1_APP_SOUNDS; ++k) {
      printf(k ? ",[" : "[");
      for (int j = 0; j < FM1_APP_INSERTS; ++j) {
        const fm1_engine_t *e = g_app.unit[fm1_app_insert_unit(k, j)].e;
        printf(j ? ",\"%s\"" : "\"%s\"", e ? e->id : "");
      }
      printf("]");
    }
    printf("],\"ram_budget\":%u,\"fx_unit_slot\":%d", FM1_APP_RAM_BUDGET, g_app.fx_slot);
  }
  {
    /* key_leds: bit n for white key n; role_leds: bit per black key, in
     * key order (F#3 first). */
    const uint32_t keys = fm1_seq_ui_key_leds(&g_app.ui, g_app.frames);
    unsigned white = 0, black = 0, nb = 0;
    for (int k = 0, n = 0; k < FM1_APP_KEYS; ++k) {
      if (fm1_white_key(n) == k) white |= ((keys >> k) & 1u) << n++;
      else black |= ((keys >> k) & 1u) << nb++;
    }
    printf(",\"seq_view\":{\"track\":%u,\"step\":%u,\"clip_playing\":%u,\"playing\":%u,"
           "\"knob\":%d,\"key_leds\":%u,\"role_leds\":%u,\"view\":%u,\"step_page\":%u,"
           "\"bar\":%u,\"held\":%u,\"shift\":%u,\"full_vel\":%u,\"hint\":%u,"
           "\"length\":%u,\"loop_start\":%u}",
           (unsigned)g_app.ui.track, (unsigned)g_app.ui.step, (unsigned)g_app.ui.clip_playing,
           (unsigned)g_app.ui.playing, (int)g_app.ui.knob, white, black, (unsigned)g_app.ui.view,
           (unsigned)g_app.ui.step_page, (unsigned)g_app.ui.bar, (unsigned)g_app.ui.held_n,
           (unsigned)g_app.ui.shift, (unsigned)g_app.ui.full_vel, (unsigned)g_app.ui.hint,
           (unsigned)g_app.ui.length, (unsigned)g_app.ui.loop_start);
    /* Tracks, mute and the pages (S6), as the UI mirrors them. */
    printf(",\"tracks\":{\"tracks\":%u,\"muted\":%u,\"track_page\":%u,\"swing\":%u,\"dq\":%u,"
           "\"metro\":%u,\"speed\":[%u,%u],\"clip_quant\":%u,\"clip_tr\":%d,\"route\":[%u,%u]}",
           (unsigned)g_app.ui.tracks, (unsigned)g_app.ui.muted, (unsigned)g_app.ui.track_page,
           (unsigned)g_app.ui.swing, (unsigned)g_app.ui.dq, (unsigned)g_app.ui.metro,
           (unsigned)g_app.ui.clip_num, (unsigned)g_app.ui.clip_den, (unsigned)g_app.ui.clip_quant,
           (int)g_app.ui.clip_tr, (unsigned)g_app.ui.route_kind, (unsigned)g_app.ui.route_index);
    /* Record and Capture (S5): the transport's record state, step record's
     * head, and Capture as the UI mirrors it. */
    printf(",\"rec\":{\"recording\":%u,\"counting_in\":%u,\"rec_track\":%u,\"srec\":%u,"
           "\"head\":%u,\"grow\":%u,\"capture_pending\":%u,\"capture_mode\":%u,"
           "\"capture_n\":%u,\"capture_sel\":%u,\"capture_cands\":[%u,%u,%u],\"bpm_x100\":%u}",
           (unsigned)g_app.ui.recording, (unsigned)g_app.ui.counting_in,
           (unsigned)g_app.ui.rec_track, (unsigned)g_app.ui.srec, (unsigned)g_app.ui.srec_head,
           (unsigned)g_app.ui.srec_grow, (unsigned)g_app.ui.capture_pending,
           (unsigned)g_app.ui.capture_mode, (unsigned)g_app.ui.capture_n,
           (unsigned)g_app.ui.capture_sel, (unsigned)g_app.ui.capture_cands[0],
           (unsigned)g_app.ui.capture_cands[1], (unsigned)g_app.ui.capture_cands[2],
           (unsigned)g_app.ui.bpm_x100);
    if (g_app.ui.held_n && g_app.ui.hold_valid) {   /* what the Step pages show */
      const fm1_seq_ui_hold_t *h = &g_app.ui.hold;
      printf(",\"hold\":{\"step\":%u,\"notes\":%u,\"tick\":%u,\"gate\":%u,\"vel\":%u,"
             "\"pitch\":%u,\"gate_mixed\":%u,\"prob\":%u,\"cond\":[%u,%u],\"inv\":%u}",
             (unsigned)h->step, (unsigned)h->notes, (unsigned)h->tick, (unsigned)h->gate,
             (unsigned)h->vel, (unsigned)h->pitch, (unsigned)h->gate_mixed, (unsigned)h->prob,
             (unsigned)h->cond_a, (unsigned)h->cond_b, (unsigned)h->inv);
      /* Locks (S8): the held step's, lane by lane (-1 none). */
      printf(",\"hold_locks\":[");
      for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) {
        printf(lane ? ",%d" : "%d", (h->lock_mask >> lane) & 1u ? (int)h->lock[lane] : -1);
      }
      printf("]");
    }
    {
      /* Locks (S8): the focused track's lanes (label, 7-bit base), the grid's
       * lock bits, the live take, and for sound unit 0 what the engine last
       * heard through a lock beside the knob's value, both %.9g, so equal
       * text is equal bits ("knob sync"). */
      fm1_seq_track_info_t tr;
      memset(&tr, 0, sizeof tr);
      fm1_seq_get_track(g_app.seq, g_app.ui.track, &tr);
      printf(",\"locks\":{\"lanes\":[");
      for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) {
        printf(lane ? "," : "");
        json_string(fm1_seq_lane_label(g_app.seq, g_app.ui.track, (uint8_t)lane));
      }
      printf("],\"bases\":[");
      for (unsigned lane = 0; lane < FM1_SEQ_LANES; ++lane) printf(lane ? ",%u" : "%u", (unsigned)tr.base[lane]);
      printf("],\"assigned\":%u,\"grid\":%llu,\"take\":%d,\"take_v\":%u,\"clear\":%u,"
             "\"lock_pages\":%u,\"shown_mask\":%u,\"shown\":[",
             (unsigned)tr.lanes_assigned, (unsigned long long)g_app.ui.locks, (int)g_app.ui.take_param,
             (unsigned)g_app.ui.take_v, (unsigned)g_app.ui.clear_held, (unsigned)g_app.ui.lock_pages,
             (unsigned)g_app.lock_mask[0]);
      {
        const fm1_engine_t *e = g_app.unit[0].e;
        for (uint16_t q = 0; e && q < e->n_params; ++q) {
          printf(q ? ",\"%.9g\"" : "\"%.9g\"", (double)g_app.lock_shown[0][q]);
        }
        printf("],\"value\":[");
        for (uint16_t q = 0; e && q < e->n_params; ++q) {
          printf(q ? ",\"%.9g\"" : "\"%.9g\"", (double)g_app.unit[0].value[q]);
        }
      }
      printf("]}");
    }
  }
  if (use_seq) {
    fm1_seq_stats_t st;
    int seq_sounding = 0;
    size_t left = (rest ? 1u : 0u);
    for (size_t k = next_cmd; k < script.n; ++k) left += !script.cmds[k].snap;
    for (int u = 0; u < FM1_APP_SOUNDS; ++u) {
      for (int n = 0; n < 128; ++n) seq_sounding += g_app.seq_note_count[u][n];
    }
    fm1_seq_get_stats(g_app.seq, &st);
    printf(",\"seq_bytes\":%zu,\"seq_events\":%llu,\"seq_notes_to_engine\":%llu,"
           "\"seq_locks_to_engine\":%llu,\"seq_refused\":%lu,\"seq_dropped\":%llu,"
           "\"seq_max_block_events\":%lu,\"seq_splits\":%llu,\"seq_held\":%llu,"
           "\"seq_busy\":%llu,\"seq_lines_left\":%zu,\"seq_sounding\":%d,"
           "\"seq_clicks\":%lu,\"seq_ui_left\":%d,\"seq_ui_frames\":[",
           fm1_seq_size(&g_app.seq_lim), (unsigned long long)seq_events,
           (unsigned long long)g_app.seq_host.notes_to_engine,
           (unsigned long long)g_app.seq_host.locks_to_engine, (unsigned long)st.refused,
           (unsigned long long)fm1_app_seq_dropped(&g_app), (unsigned long)g_app.seq_host.max_n,
           (unsigned long long)g_app.seq_host.splits, (unsigned long long)g_app.seq_held,
           (unsigned long long)g_app.seq_busy, left, seq_sounding, (unsigned long)g_app.click.clicks,
           g_ui_n - g_ui_next);
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
    {
      int scale;
      const int root = fm1_app_project_key(&g_app, &scale);   /* the set's key, as fm1-render's */
      printf(",\"seq_key\":[%d,%d]", root, scale);
    }
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
      fprintf(f, "--slots\n");             /* the app routes tracks to its sound units by slot */
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

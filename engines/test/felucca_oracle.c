/* felucca_oracle.c -- fm1-felucca-oracle: Drawbar, Trio and Phase Bend
 * (src/felucca_shim.cc) against Felucca's own voice code.
 *
 * The oracle is Felucca's voice.c, unmodified (third_party/felucca/src),
 * driving the same engine files on one part as Felucca's firmware does:
 * its trk_note_on, trk_note_off and track_render, with its envelope, its
 * modulation and its POLY voice allocation. What voice.c needs from files
 * not vendored (the modulation matrix, the DRUM engine, the generator its
 * LFO draws from, the engine table) is stubbed below, inert as on a part
 * with no matrix route, no drum and no LFO depth. The engine under test is
 * the same engine through our API (fm1_engine_find), with its parameters
 * in their units: the test (tests/test_engine_felucca.py) gives both sides
 * the same sound, Felucca's in its integers (--fel) and ours in units
 * computed from Felucca's own curves (--param), so the parameter maps are
 * checked too.
 *
 *   fm1-felucca-oracle ENGINE [--rate HZ] [--blocks N] [--host-block F]
 *       [--fel E0=..,E7=..,ATK=..,DEC=..,SUS=..,REL=..,FLT=..]
 *       [--param NAME=VALUE]... [--on B:KEY:VEL]... [--off B:KEY]...
 *
 * Events land at the start of 32-sample block B on both sides. Our engine
 * renders in host calls of F frames (default 32). Prints one JSON line:
 * whether the outputs are identical, the first frame and the largest
 * difference where not, the peak, and frames that are not silent; exit 0
 * when identical, 1 when not, 2 on a usage error.
 *
 * It also counts our samples that are not finite or are subnormal, and
 * gives our peak. Felucca's samples are its integers times the shim's output gain at
 * Volume 0.7 (felucca_shim.cc kPartGain), computed by the same expression,
 * so identical means bit for bit.
 *
 * A desktop test tool, built only while the GPL switch is on
 * (mk/felucca.mk): it includes GPL-3.0-only code. MIT licence (this file's
 * own text).
 */
#include "fm1_gpl_mods.h"

#if !FM1_GPL_MODS
#error "felucca_oracle.c includes GPL code: it is built only with FM1_GPL_MODS=1"
#endif

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_engine.h"

/* ---- Felucca: its files, as tests/hostsim.c includes them ------------------- */
#include "felucca_tables.h"
#define section(x) unused
#define bootguard fel_oracle_bootguard
#include "core.h"
#undef bootguard
#undef section
#include "dsp.c"
#include "eng_wheel.c"
#include "eng_trio.c"
#include "eng_phase.c"

/* What voice.c reaches outside the vendored files, inert. */
static uint32_t rng(void) {                     /* libc.c's xorshift, seeded as at boot */
  static uint32_t s = 0x2545F491u;
  s ^= s << 13;
  s ^= s >> 17;
  s ^= s << 5;
  return s;
}
static const engine_t ENG_DRUM = { .name = "DRUM" };
static voice_t *drum_reuse(track_t *t, uint32_t note) { (void)t; (void)note; return 0; }
static struct { uint8_t on; } mod;              /* no matrix route: mod.c is never called */
static void mod_note(track_t *t, uint32_t note, uint32_t vel) { (void)t; (void)note; (void)vel; }
static void mod_voice(track_t *t, voice_t *v, vmod_t *m, int32_t fine) {
  (void)t; (void)v; (void)m; (void)fine;
}
static const engine_t *const ENGINES[NENGINES] = {
  [0 ... NENGINES - 1] = &ENG_TRIO,             /* the parts not played: any engine */
  [2] = &ENG_PHASE, [6] = &ENG_TRIO, [7] = &ENG_WHEEL,
};
static inline uint32_t eng_idx(uint32_t e) { return e < NENGINES ? e : 0u; }

#include "voice.c"

/* ---- The run ------------------------------------------------------------------ */
#define MAX_EVENTS 512
#define MAX_PARAMS 32
typedef struct { uint32_t block; int on; uint8_t key, vel; } event_t;

static void usage(void) {
  fprintf(stderr, "usage: fm1-felucca-oracle drawbar|trio|phase-bend [--rate HZ] [--blocks N]\n"
                  "         [--host-block F] [--fel K=V,...] [--param NAME=VALUE]...\n"
                  "         [--on B:KEY:VEL]... [--off B:KEY]...\n");
}

static int fel_key(const char *k) {
  if (k[0] == 'E' && k[1] >= '0' && k[1] <= '7' && !k[2]) return P_E0 + (k[1] - '0');
  if (!strcmp(k, "ATK")) return P_ATK;
  if (!strcmp(k, "DEC")) return P_DEC;
  if (!strcmp(k, "SUS")) return P_SUS;
  if (!strcmp(k, "REL")) return P_REL;
  if (!strcmp(k, "FLT")) return P_ED_FLT;
  return -1;
}

int main(int argc, char **argv) {
  const fm1_engine_t *e;
  int fel_engine;
  float rate = 44100.0f;
  uint32_t blocks = 200, host_block = 32;
  event_t ev[MAX_EVENTS];
  int n_ev = 0;
  const char *params[MAX_PARAMS];
  int n_params = 0;
  track_t *t = &trk[0];
  int i;
  if (argc < 2) { usage(); return 2; }
  e = fm1_engine_find(argv[1]);
  if (!e) { usage(); return 2; }
  fel_engine = !strcmp(argv[1], "drawbar") ? 7 : !strcmp(argv[1], "trio") ? 6
             : !strcmp(argv[1], "phase-bend") ? 2 : -1;
  if (fel_engine < 0) { usage(); return 2; }

  /* Felucca's part: its defaults where voice.c reads them (params.c TP),
   * then --fel. */
  memset(trk, 0, sizeof trk);
  t->p[P_ATK] = 10; t->p[P_DEC] = 70; t->p[P_SUS] = 90; t->p[P_REL] = 60;
  t->p[P_LRATE] = 60; t->p[P_DETUNE] = 40; t->p[P_LEVEL] = 104;
  for (i = 0; i < NPART; ++i) t[i].engine = t[i].eng_req = (uint8_t)(i ? 6 : fel_engine);
  {
    const engine_t *eng = ENGINES[fel_engine];
    for (i = 0; i < 8; ++i) t->p[P_E0 + i] = eng->edit[i].def;
  }

  for (i = 2; i < argc; ++i) {
    const char *a = argv[i];
    const char *v = i + 1 < argc ? argv[i + 1] : NULL;
    if (!v) { usage(); return 2; }
    if (!strcmp(a, "--rate")) rate = (float)atof(v);
    else if (!strcmp(a, "--blocks")) blocks = (uint32_t)atoi(v);
    else if (!strcmp(a, "--host-block")) host_block = (uint32_t)atoi(v);
    else if (!strcmp(a, "--param")) { if (n_params < MAX_PARAMS) params[n_params++] = v; }
    else if (!strcmp(a, "--fel")) {
      char buf[256], *tok, *save = NULL;
      snprintf(buf, sizeof buf, "%s", v);
      for (tok = strtok_r(buf, ",", &save); tok; tok = strtok_r(NULL, ",", &save)) {
        char *eq = strchr(tok, '=');
        int k;
        if (!eq) { usage(); return 2; }
        *eq = 0;
        k = fel_key(tok);
        if (k < 0) { usage(); return 2; }
        t->p[k] = (int16_t)atoi(eq + 1);
      }
    } else if (!strcmp(a, "--on") || !strcmp(a, "--off")) {
      unsigned b = 0, key = 0, vel = 0;
      const int on = !strcmp(a, "--on");
      if (n_ev >= MAX_EVENTS) { usage(); return 2; }
      if ((on && sscanf(v, "%u:%u:%u", &b, &key, &vel) != 3) || (!on && sscanf(v, "%u:%u", &b, &key) != 2)) {
        usage();
        return 2;
      }
      ev[n_ev].block = b;
      ev[n_ev].on = on;
      ev[n_ev].key = (uint8_t)key;
      ev[n_ev].vel = (uint8_t)vel;
      ++n_ev;
    } else {
      usage();
      return 2;
    }
    ++i;
  }

  /* Our engine. */
  {
    const fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, host_block > 64 ? host_block : 64 };
    const size_t size = e->instance_size(&host);
    void *mem = NULL, *self;
    float *ours = (float *)calloc((size_t)blocks * 32u * 2u, sizeof(float));
    const float gain = 2584.0f / 4096.0f / 32768.0f / 4.0f;   /* felucca_shim.cc kPartGain */
    uint32_t b, f, frames = blocks * 32u, first = 0, diffs = 0, loud = 0, subnormal = 0, nonfinite = 0;
    double max_diff = 0.0, peak = 0.0, ours_peak = 0.0;
    if (posix_memalign(&mem, 16, size) || !ours) return 2;
    memset(mem, 0xA5, size);
    self = e->create(mem, &host);
    if (!self) { fprintf(stderr, "%s refused %g Hz\n", e->id, (double)rate); return 2; }
    for (i = 0; i < n_params; ++i) {
      char name[64];
      const char *eq = strchr(params[i], '=');
      uint16_t k;
      int found = 0;
      if (!eq || (size_t)(eq - params[i]) >= sizeof name) { usage(); return 2; }
      memcpy(name, params[i], (size_t)(eq - params[i]));
      name[eq - params[i]] = 0;
      for (k = 0; k < e->n_params; ++k) {
        if (!strcmp(e->params[k].name, name)) {
          e->set_param(self, k, (float)atof(eq + 1));
          found = 1;
        }
      }
      if (!found) { fprintf(stderr, "no parameter %s\n", name); return 2; }
    }
    /* Ours, in host calls of host_block frames, events at their block's
     * first frame. */
    for (f = 0; f < frames;) {
      uint32_t n = host_block;
      int k;
      if (f % 32u == 0) {
        for (k = 0; k < n_ev; ++k) {
          if (ev[k].block != f / 32u) continue;
          if (ev[k].on) e->note_on(self, ev[k].key, ev[k].vel);
          else e->note_off(self, ev[k].key);
        }
      }
      if (n > 32u - f % 32u) n = 32u - f % 32u;   /* events sit at block starts */
      if (n > frames - f) n = frames - f;
      e->render(self, ours + 2u * f, n);
      f += n;
    }
    e->destroy(self);
    free(mem);
    for (f = 0; f < 2u * frames; ++f) {   /* ours: finite, no subnormal, its peak */
      const float y = ours[f];
      if (!(y == y) || y > 3.4e38f || y < -3.4e38f) ++nonfinite;
      else if (y != 0.0f && fabsf(y) < 1.17549435e-38f) ++subnormal;
      else if (fabs((double)y) > ours_peak) ours_peak = fabs((double)y);
    }
    /* Felucca's, block by block. */
    for (b = 0; b < blocks; ++b) {
      int32_t out[CTL];
      int k;
      for (k = 0; k < n_ev; ++k) {
        if (ev[k].block != b) continue;
        if (ev[k].on) trk_note_on(t, ev[k].key, ev[k].vel);
        else trk_note_off(t, ev[k].key);
      }
      track_render(t, out, CTL);
      for (k = 0; k < CTL; ++k) {
        const float want = (float)out[k] * gain;
        const uint32_t at = b * 32u + (uint32_t)k;
        const float got = ours[2u * at];
        const double d = fabs((double)got - (double)want);
        if (got != want || ours[2u * at + 1] != want) {
          if (!diffs) first = at;
          ++diffs;
        }
        if (d > max_diff) max_diff = d;
        if (fabs((double)want) > peak) peak = fabs((double)want);
        if (out[k]) ++loud;
      }
    }
    free(ours);
    printf("{\"engine\":\"%s\",\"frames\":%u,\"identical\":%s,\"diffs\":%u,\"first\":%u,"
           "\"max_diff\":%.9g,\"peak\":%.9g,\"loud\":%u,\"instance\":%zu,"
           "\"ours_peak\":%.9g,\"ours_subnormal\":%u,\"ours_nonfinite\":%u}\n",
           e->id, frames, diffs ? "false" : "true", diffs, first, max_diff, peak, loud, size,
           ours_peak, subnormal, nonfinite);
    return diffs ? 1 : 0;
  }
}

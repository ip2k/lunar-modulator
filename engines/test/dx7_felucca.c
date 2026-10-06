/* dx7_felucca.c -- Felucca's fm6_core.c (third_party/felucca-fm6, an
 * integer C port of Dexed's msfa by Leo Kuroshita, Hugelton Instruments,
 * Apache-2.0) set up and driven as the FM6 engine's desktop oracle
 * (engines/test/dx7_oracle.cc, tests/test_engines_dx7.py). Not part of any
 * engine or firmware build.
 *
 * fm6_core.c expects tables its firmware generates at build time (with a
 * GPL-3.0 tool we do not use). They are computed here instead, at the
 * oracle's rate, from the definitions its comments and the msfa sources
 * give: the Q30 exp2 mantissa, the Q15 sine, msfa's fine-frequency table,
 * the rate units of msfa's LFO and pitch envelope for Felucca's 32-sample
 * blocks, and the AMS curve's constants. Two are chosen to match Google's
 * msfa, which FM6 runs, rather than Dexed's, so that a comparison shows
 * differences in how the engine is put together rather than in two tables
 * both keep from msfa's lineage: the detune step is msfa's constant 12,606
 * per step at every key (Dexed scales it by key), and the LFO's speeds come
 * from msfa's formula (Dexed has a table of measured rates).
 *
 * The note is driven as a keyboard would: key-on at frame 0 (the LFO reset
 * to the voice's settings and keyed), key-off at `gate`, one Felucca block
 * (32 samples) at a time, nothing else (no bend, no macros).
 *
 * C99, MIT licence (this file).
 */
#include <math.h>
#include <stdint.h>
#include <string.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

#define CTL 32

static int16_t SINE[1025];
static uint32_t FM6_EXP2[1025];
static uint32_t FM6_LFO_DELTA[100];
static uint16_t FM6_DETUNE[128];
static int32_t FM6_FINE[100];
static uint32_t fm6_freq_r;
static int32_t fm6_lfo_unit, fm6_penv_unit, fm6_ams_c0, fm6_ams_k;
#define FM6_FREQ_R fm6_freq_r
#define FM6_LFO_UNIT fm6_lfo_unit
#define FM6_PENV_UNIT fm6_penv_unit
#define FM6_AMS_C0 fm6_ams_c0
#define FM6_AMS_K fm6_ams_k

#include "fm6_core.c"

void felucca_init(double rate) {
  int i;
  for (i = 0; i < 1025; ++i) {
    SINE[i] = (int16_t)lround(32767.0 * sin(2.0 * M_PI * i / 1024.0));
    FM6_EXP2[i] = (uint32_t)llround((double)(1u << 30) * (pow(2.0, i / 1024.0) - 1.0));
  }
  fm6_lfo_unit = (int32_t)(CTL * 25190424.0 / rate + 0.5);
  fm6_penv_unit = (int32_t)(CTL * 16777216.0 / (21.3 * rate) + 0.5);
  fm6_freq_r = (uint32_t)llround(pow(2.0, 40.0) / rate);
  fm6_ams_c0 = (int32_t)llround(12.2 * log2(exp(1.0)) * 16777216.0);
  fm6_ams_k = (int32_t)llround(0.07 / 262144.0 * log2(exp(1.0)) * 16777216.0 * 1024.0);
  for (i = 0; i < 100; ++i) {
    int sr = i == 0 ? 1 : (165 * i) >> 6;               /* msfa Lfo::reset */
    sr *= sr < 160 ? 11 : (11 + ((sr - 160) >> 4));
    FM6_LFO_DELTA[i] = (uint32_t)fm6_lfo_unit * (uint32_t)sr;
    FM6_FINE[i] = (int32_t)floor(24204406.323123 * log(1 + 0.01 * i) + 0.5);
  }
  for (i = 0; i < 128; ++i) FM6_DETUNE[i] = 12606;      /* msfa osc_freq */
}

/* One note of voice p (155 VCED bytes) at key `key` (the voice's transpose
 * applied, as FM6 applies it), velocity vel, released at frame `gate`, for
 * `total` frames, into out as fm6_core's Q24 samples. */
void felucca_render(const uint8_t *p155, int key, int vel, int gate, int total, int32_t *out) {
  uint8_t p[FP_SIZE + 1];
  fm6_note_t n;
  fm6_lfo_t lfo;
  int32_t buf[FM6_N];
  static const int32_t dt[6] = { 0, 0, 0, 0, 0, 0 };
  int note, f = 0, k;
  memcpy(p, p155, FP_SIZE);
  p[FP_SIZE] = 0;
  note = key + p[FP_TRNSP] - 24;
  note = note < 0 ? 0 : (note > 127 ? 127 : note);
  memset(&n, 0, sizeof(n));
  memset(&lfo, 0, sizeof(lfo));
  fm6_lfo_reset(&lfo, p);
  fm6_lfo_key(&lfo);
  fm6_note_init(&n, p, note, vel, 1);
  while (f < total) {
    int32_t lv, ld;
    if (f >= gate && n.down) fm6_note_key(&n, p, 0);
    lv = fm6_lfo_sample(&lfo);
    ld = fm6_lfo_delay(&lfo);
    if (!fm6_note_compute(&n, p, buf, lv, ld, fm6_note_logfreq(note * 16, 0), p[FP_ALG],
                          p[FP_FB], dt, 0)) {
      memset(buf, 0, sizeof(buf));
    }
    for (k = 0; k < FM6_N && f < total; ++k, ++f) out[f] = buf[k];
  }
}

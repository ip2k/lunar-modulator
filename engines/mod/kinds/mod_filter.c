/* kinds/mod_filter.c -- the Filter module kind (docs/16 §3.6; the owner's
 * request of 2026-10-02): a resonant filter for control signals, whose
 * outputs are matrix sources.
 *
 * IN (a bare signal input) runs through a two-pole state-variable filter,
 * one sample per tick (1,378.7 Hz at the FM-1's rate), with low-pass,
 * band-pass and high-pass outputs at once:
 *   Cutoff  0..1 on a log scale, 0.05 Hz to 409.6 Hz (2^(13 x Cutoff) x
 *           0.05 Hz; 0.5 is 4.5 Hz), held below 0.3 x the tick rate so it
 *           stays clear of the tick's Nyquist (689 Hz). A cable moves it by
 *           octaves; a cutoff in Hz would be linear under the matrix's
 *           amount x range.
 *   Res     0..1: damping k = 2 (1 - Res)^2, from a Q of 0.5 (no overshoot)
 *           to an undamped resonator at 1 that rings for ever: a sine LFO
 *           at Cutoff once something excites it.
 *   Blend   OUT crossfades LP (0) to BP (0.5) to HP (1).
 *   Level   scales every output (-1..1).
 *   Strike  each rising edge at the PING gate input adds Strike to the
 *           band-pass state: the filter rings at its cutoff with an
 *           amplitude near Strike on every output, decaying as Res sets.
 *           With Res high, a note trigger into PING makes a resonant
 *           wobble.
 * LP has unity gain at DC, HP at the top, and LP and BP peak at about
 * 1 / k at the cutoff, so a resonant filter clips a full-scale input there
 * (outputs are limited to -1..1); lower Level or the input's amount. The
 * state is limited to +-8, so an undamped filter driven at its cutoff
 * saturates instead of growing without bound.
 *
 * How it differs from Slew: Slew limits the rate of change (or lags with
 * one pole); it never overshoots and has no notion of frequency. Filter is
 * frequency-selective: LP smooths with a 12 dB/octave slope and can
 * overshoot and ring, BP and HP take out the slow part (centre a drifting
 * signal, keep only its movement), and a ping makes it an oscillator.
 *
 * The design is the trapezoidal (topology-preserving) state-variable filter
 * as Andrew Simper (Cytomic) published it, written here: its cutoff is
 * exact (g = tan(pi fc / rate), from Taylor polynomials, no libm), it is
 * stable for every cutoff below Nyquist and every damping above 0, also
 * while either moves, and at k = 0 its poles sit exactly on the unit
 * circle. A PING lands at the tick it falls in (0.725 ms resolution). Our
 * own code, MIT. */
#include "kinds_int.h"

enum { P_CUTOFF, P_RES, P_BLEND, P_LEVEL, P_STRIKE, P_IN, P_COUNT };
enum { O_OUT, O_LP, O_BP, O_HP };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Cutoff", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Cut" },
  { "Res", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.3f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Res" },
  { "Blend", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.0f, NULL, 0, 3, MOD, FM1_UNIT_NONE, "Blend" },
  { "Level", FM1_PARAM_FLOAT, -1.0f, 1.0f, 1.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Level" },
  { "Strike", FM1_PARAM_FLOAT, 0.0f, 1.0f, 1.0f, NULL, 1, 5, MOD, FM1_UNIT_NONE, "Strike" },
  { "In", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 6, FM1_PARAM_INPUT, FM1_UNIT_NONE, "In" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Ping", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };
static const fm1_port_t kOuts[] = { { "Out", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "LP", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "BP", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                    { "HP", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 } };

#define STATE_MAX 8.0f
#define PI 3.14159265f

typedef struct filter {
  float ic1, ic2;              /* the two integrators' states */
  float a1, a2, a3, k;         /* coefficients for the current cutoff and damping */
  float tick_hz;               /* samples per second: the tick rate */
  uint32_t key[2];             /* Cutoff and Res as bits, when the coefficients were made */
  uint8_t configured, reserved[3];
} filter_t;

static size_t filter_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(filter_t);
}

static void *filter_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  filter_t *s = (filter_t *)mem;
  (void)seed;
  s->ic1 = s->ic2 = 0.0f;
  s->a1 = 1.0f;
  s->a2 = s->a3 = 0.0f;
  s->k = 2.0f;
  s->tick_hz = 1.0f / kind_tick_s(kind_rate(host));
  s->key[0] = s->key[1] = 0;
  s->configured = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

/* tan x for 0 <= x < 1 from the Taylor series of sin and cos to x^11 and
 * x^12 (error under 1e-10 before rounding at x = 0.95). */
static float tan_small(float x) {
  const float x2 = x * x;
  const float s = x * (1.0f - x2 * (1.0f / 6.0f) *
                       (1.0f - x2 * (1.0f / 20.0f) *
                        (1.0f - x2 * (1.0f / 42.0f) *
                         (1.0f - x2 * (1.0f / 72.0f) * (1.0f - x2 * (1.0f / 110.0f))))));
  const float c = 1.0f - x2 * 0.5f *
                  (1.0f - x2 * (1.0f / 12.0f) *
                   (1.0f - x2 * (1.0f / 30.0f) *
                    (1.0f - x2 * (1.0f / 56.0f) *
                     (1.0f - x2 * (1.0f / 90.0f) * (1.0f - x2 * (1.0f / 132.0f))))));
  return s / c;
}

static void configure(filter_t *s, const float *p) {
  const uint32_t kc = mod_bits(p[P_CUTOFF]), kr = mod_bits(p[P_RES]);
  float fc, g, r;
  if (s->configured && kc == s->key[0] && kr == s->key[1]) return;
  fc = 0.05f * fm1_mod_exp2(13.0f * p[P_CUTOFF]);
  if (fc > 0.3f * s->tick_hz) fc = 0.3f * s->tick_hz;
  g = tan_small(PI * fc / s->tick_hz);
  r = 1.0f - p[P_RES];
  s->k = 2.0f * r * r;
  s->a1 = 1.0f / (1.0f + g * (g + s->k));
  s->a2 = g * s->a1;
  s->a3 = g * s->a2;
  s->key[0] = kc;
  s->key[1] = kr;
  s->configured = 1;
}

static float limit(float x) {
  return mod_clampf(x, -STATE_MAX, STATE_MAX, 0.0f);
}

static void filter_process(void *self, const fm1_mod_io_t *io) {
  filter_t *s = (filter_t *)self;
  const float *p = io->p;
  const fm1_mod_gate_t *ping = &io->gate[0];
  const float v0 = p[P_IN], b = p[P_BLEND], level = p[P_LEVEL];
  float v1, v2, v3, lp, bp, hp, out;
  unsigned e;
  configure(s, p);
  for (e = 0; e < ping->n; ++e) {
    if (ping->ev[e].high) s->ic1 = limit(s->ic1 + p[P_STRIKE]);
  }
  v3 = v0 - s->ic2;
  v1 = s->a1 * s->ic1 + s->a2 * v3;
  v2 = s->ic2 + s->a2 * s->ic1 + s->a3 * v3;
  s->ic1 = limit(2.0f * v1 - s->ic1);
  s->ic2 = limit(2.0f * v2 - s->ic2);
  lp = v2;
  bp = v1;
  hp = v0 - s->k * v1 - v2;
  out = b <= 0.5f ? lp + (bp - lp) * (2.0f * b) : bp + (hp - bp) * (2.0f * b - 1.0f);
  io->out[O_OUT] = level * out;
  io->out[O_LP] = level * lp;
  io->out[O_BP] = level * bp;
  io->out[O_HP] = level * hp;
}

static void filter_reset(void *self, uint32_t why) {
  filter_t *s = (filter_t *)self;
  if (why == FM1_MOD_RESET_PRESET) s->ic1 = s->ic2 = 0.0f;
}

const fm1_mod_kind_t fm1_mod_kind_filter = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "filter", 0x464C5420u /* "FLT " */, "Filter", "FLT",
  "Our own: the trapezoidal state-variable filter after Andrew Simper's (Cytomic) published "
  "derivation, at the control rate.",
  kParams, P_COUNT, 1, 4, kGates, kOuts, 0, 0,
  filter_size, filter_create, NULL, filter_reset, filter_process, NULL, NULL, NULL
};

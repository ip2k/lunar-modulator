/* kinds/mod_slew.c -- the Slew module kind (docs/16 §3.6): a slew limiter
 * with six outputs.
 *
 * OUT follows IN no faster than Up (rising) and Down (falling) allow. Type
 * Linear moves at a fixed rate: a full 0 -> 1 change takes the knob's time,
 * Peaks' knob-to-time curve, 0.5 ms to 8 s. Type Expo is a one-pole lag
 * with that time constant (63 % of a step), landing exactly on the target.
 * Spread fans OUT2-OUT6 out from OUT: output j (0 for OUT) takes the time
 * x (1 + Spread x j) for Spread above 0, and / (1 - Spread x j) below, so
 * at +1 OUT6 is six times slower and at -1 six times faster (the idea of
 * Just Friends' INTONE). While THRU is high every output follows IN at
 * once.
 *
 * IN changes once a tick, so the limiter steps once a tick, the tick's 32
 * samples at a time: the linear step and the lag's factor are exact for 32
 * samples, and the state is integer (Q4.28, as fm1_mp's slew), so the
 * result is the same everywhere.
 *
 * Our own code, MIT. After the disting mk4's B-2 (closed; idea only),
 * Phazerville's Slew applet (MIT) and Just Friends' STRATA and INTONE
 * (Mannequins; ideas only); no code taken. */
#include "kinds_int.h"

#include "mp_int.h"

enum { P_UP, P_DOWN, P_TYPE, P_SPREAD, P_IN, P_COUNT };
enum { N_OUT = 6 };
enum { T_LINEAR, T_EXPO };

static const char *const kTypes[] = { "Linear", "Expo" };

#define MOD FM1_PARAM_MOD
static const fm1_param_t kParams[P_COUNT] = {
  { "Up", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.3f, NULL, 0, 1, MOD, FM1_UNIT_NONE, "Up" },
  { "Down", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.3f, NULL, 0, 2, MOD, FM1_UNIT_NONE, "Down" },
  { "Type", FM1_PARAM_ENUM, 0.0f, 1.0f, 0.0f, kTypes, 0, 3, 0, FM1_UNIT_NONE, "Type" },
  { "Spread", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 0, 4, MOD, FM1_UNIT_NONE, "Spread" },
  { "In", FM1_PARAM_FLOAT, -1.0f, 1.0f, 0.0f, NULL, 1, 5, FM1_PARAM_INPUT, FM1_UNIT_NONE, "In" },
};
#undef MOD

static const fm1_port_t kGates[] = { { "Thru", FM1_PORT_GATE, FM1_UNIT_NONE, MOD_NONE, 0 } };
static const fm1_port_t kOuts[N_OUT] = { { "Out", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                         { "Out2", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                         { "Out3", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                         { "Out4", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                         { "Out5", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 },
                                         { "Out6", FM1_PORT_CV_BI, FM1_UNIT_NONE, MOD_NONE, 0 } };

#define Q 268435456.0f                 /* 2^28 */
#define QMAX 2147483520.0f             /* just under 2^31 */
#define INSTANT 0x100000000ull

typedef struct slew {
  int32_t y[N_OUT];                    /* Q4.28 */
  uint64_t up[N_OUT], down[N_OUT];     /* per tick: a step (linear) or a factor in Q32 (expo) */
  uint32_t key[4];                     /* Up, Down, Spread, Type as bits: when to recompute */
  float tick_s;
  uint8_t configured, reserved[3];
} slew_t;

static size_t slew_size(const fm1_host_t *host) {
  (void)host;
  return sizeof(slew_t);
}

static void *slew_create(void *mem, const fm1_host_t *host, uint32_t seed) {
  slew_t *s = (slew_t *)mem;
  unsigned i;
  (void)seed;
  for (i = 0; i < N_OUT; ++i) {
    s->y[i] = 0;
    s->up[i] = s->down[i] = INSTANT;
  }
  for (i = 0; i < 4u; ++i) s->key[i] = 0;
  s->tick_s = kind_tick_s(kind_rate(host));
  s->configured = 0;
  s->reserved[0] = s->reserved[1] = s->reserved[2] = 0;
  return s;
}

/* Per tick: a full-scale step of tick/time (linear), or 1 - e^(-tick/time)
 * (expo); INSTANT when the time is under a tick. */
static uint64_t coeff(float seconds, float tick_s, int expo) {
  float ticks, k;
  if (!(seconds > tick_s)) return INSTANT;
  ticks = seconds / tick_s;
  if (!expo) {
    k = Q / ticks;
    return k < 1.0f ? 1u : (uint64_t)k;
  }
  /* e^(-1/ticks) = 2^(-log2(e) / ticks) */
  k = (1.0f - fm1_mod_exp2(-1.44269504f / ticks)) * 4294967296.0f;
  return k < 1.0f ? 1u : k >= 4294967296.0f ? INSTANT : (uint64_t)k;
}

static void configure(slew_t *s, const float *p) {
  const uint32_t key[4] = { mod_bits(p[P_UP]), mod_bits(p[P_DOWN]), mod_bits(p[P_SPREAD]),
                            (uint32_t)p[P_TYPE] };
  const int expo = (unsigned)p[P_TYPE] == T_EXPO;
  const float up = fm1_mp_env_time_from_knob(p[P_UP]), down = fm1_mp_env_time_from_knob(p[P_DOWN]);
  unsigned j;
  if (s->configured && key[0] == s->key[0] && key[1] == s->key[1] && key[2] == s->key[2] &&
      key[3] == s->key[3]) {
    return;
  }
  for (j = 0; j < N_OUT; ++j) {
    const float spread = p[P_SPREAD] * (float)j;
    const float m = spread >= 0.0f ? 1.0f + spread : 1.0f / (1.0f - spread);
    s->up[j] = coeff(up * m, s->tick_s, expo);
    s->down[j] = coeff(down * m, s->tick_s, expo);
  }
  for (j = 0; j < 4u; ++j) s->key[j] = key[j];
  s->configured = 1;
}

static int32_t step(int32_t y, int32_t target, uint64_t c, int expo) {
  const int64_t diff = (int64_t)target - (int64_t)y;
  const uint64_t d = (uint64_t)(diff < 0 ? -diff : diff);
  uint64_t by;
  if (d == 0) return y;
  if (c >= INSTANT) return target;
  by = expo ? (d * c) >> 32 : c;
  if (by == 0 || by >= d) return target;   /* the lag lands exactly */
  return (int32_t)(diff > 0 ? (int64_t)y + (int64_t)by : (int64_t)y - (int64_t)by);
}

static void slew_process(void *self, const fm1_mod_io_t *io) {
  slew_t *s = (slew_t *)self;
  const fm1_mod_gate_t *thru = &io->gate[0];
  const int32_t target = (int32_t)mod_clampf(io->p[P_IN] * Q, -QMAX, QMAX, 0.0f);
  const int expo = (unsigned)io->p[P_TYPE] == T_EXPO;
  int bypass = fm1_mod_gate_end(thru);
  unsigned j, e;
  for (e = 0; e < thru->n; ++e) bypass |= thru->ev[e].high;
  configure(s, io->p);
  for (j = 0; j < N_OUT; ++j) {
    s->y[j] = bypass ? target : step(s->y[j], target, target > s->y[j] ? s->up[j] : s->down[j], expo);
    io->out[j] = (float)s->y[j] * (1.0f / Q);
  }
}

static void slew_reset(void *self, uint32_t why) {
  slew_t *s = (slew_t *)self;
  unsigned j;
  if (why == FM1_MOD_RESET_PRESET) {
    for (j = 0; j < N_OUT; ++j) s->y[j] = 0;
  }
}

const fm1_mod_kind_t fm1_mod_kind_slew = {
  FM1_MOD_MAGIC, FM1_MOD_API_VERSION, "slew", 0x534C5720u /* "SLW " */, "Slew", "SLW",
  "Our own. After the disting mk4's slew (Expert Sleepers; idea only), Phazerville's Slew "
  "(MIT) and Just Friends' STRATA (Mannequins; idea only); no code taken.",
  kParams, P_COUNT, 1, N_OUT, kGates, kOuts, 0, 0,
  slew_size, slew_create, NULL, slew_reset, slew_process, NULL, NULL, NULL
};

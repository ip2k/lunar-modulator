/* mod_kinds_test.c -- fm1-mod-kinds-test: the modulation kinds of docs/16
 * stage MG2 through the runtime (fm1_mod.h), one behaviour at a time:
 *
 *   Calc's ops, Mix's sums, Slew's times, Compare's crossings and frames,
 *   Logic's tables and flip-flops, Coin's odds and latch, Divide's
 *   divisions, Euclid, multiplication, swing, delay and reset, Quantize's
 *   scales, hysteresis and clock, Register's loops, Function's segments,
 *   retriggers, hold, slew and sync, Bounce's hits, Burst's counts, accel and
 *   clock, and the Filter: its frequency response against the analytic one
 *   of the trapezoidal state-variable filter, DC gains, ringing frequency
 *   and decay against its poles, and stability under random modulation;
 *
 *   every kind from memory filled with 0x00, 0xA5 and 0xFF giving the same
 *   ticks bit for bit, and fuzzed with random and extreme parameters and
 *   gates without a non-finite output.
 *
 * Inputs: an INPUT or MOD parameter's base set before a tick, or system
 * gates (KEY, TRIG, the sequencer's CLOCK and START) fed at frames. With
 * 32-frame blocks every block runs one tick at its frame 0, so an event fed
 * after it at frame f reaches the next tick at offset f.
 *
 * Prints one JSON line of counts; exits 1 after reporting failed checks.
 * Desktop test code (libm allowed here). MIT licence. */
#include "mod_int.h"
#include "mod_mi.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failed;
static unsigned checks;

#define CHECK(c)                                                          \
  do {                                                                    \
    ++checks;                                                             \
    if (!(c)) {                                                           \
      if (failed < 20) fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #c); \
      ++failed;                                                           \
    }                                                                     \
  } while (0)

#define G FM1_MOD_TICK
#define RATE 44118.0f
#define TICK_HZ (44118.0 / 32.0)
#define MEM_BYTES (1u << 16)
#define PI_D 3.14159265358979323846

static const fm1_host_t kHost = { FM1_ENGINE_API_VERSION, RATE, 64 };

static unsigned char *mem_block(int which) {
  static unsigned char raw[3][MEM_BYTES + 16];
  return raw[which] + (16u - ((uintptr_t)raw[which] & 15u)) % 16u;
}

static fm1_mod_t *make(int which, int fill, uint32_t seed) {
  unsigned char *mem = mem_block(which);
  fm1_mod_t *m;
  memset(mem, fill, fm1_mod_size());
  m = fm1_mod_create(mem, &kHost, seed);
  CHECK(m != NULL);
  return m;
}

static int kind(const char *id) {
  const int k = fm1_mod_kind_find(id);
  CHECK(k >= 0);
  return k;
}

/* A module at pos with parameters set by name. */
static void put(fm1_mod_t *m, unsigned pos, const char *id) {
  CHECK(fm1_mod_set_kind(m, pos, kind(id)) >= 0);
}

static int param_index(fm1_mod_t *m, unsigned pos, const char *name) {
  const fm1_mod_kind_t *kd = fm1_mod_kinds[fm1_mod_kind_at(m, pos)];
  unsigned i;
  for (i = 0; i < kd->n_params; ++i) {
    if (!strcmp(kd->params[i].name, name)) return (int)i;
  }
  fprintf(stderr, "no parameter %s on %s\n", name, kd->id);
  failed++;
  return 0;
}

static void set(fm1_mod_t *m, unsigned pos, const char *name, float v) {
  fm1_mod_set_param(m, pos, (unsigned)param_index(m, pos, name), v);
}

static uint16_t uid_of(fm1_mod_t *m, unsigned pos, const char *name) {
  return fm1_mod_kinds[fm1_mod_kind_at(m, pos)]->params[param_index(m, pos, name)].uid;
}

static unsigned out_of(unsigned pos, unsigned port) { return FM1_MOD_SRC_MODULE + 8u * pos + port; }

/* A cable from src into a parameter (by name) or, with gate >= 0, a gate input. */
static void cable(fm1_mod_t *m, unsigned slot, unsigned src, unsigned pos, const char *param,
                  int gate, float amount) {
  fm1_mod_slot_t s;
  memset(&s, 0, sizeof(s));
  s.src = (uint8_t)src;
  s.via = FM1_MOD_NONE;
  s.dst_unit = (uint8_t)(FM1_MOD_MODULE + pos);
  s.flags = FM1_MOD_SLOT_ON;
  if (gate >= 0) {
    s.flags |= FM1_MOD_SLOT_GATE_DST;
    s.dst = (uint16_t)gate;
  } else {
    s.dst = uid_of(m, pos, param);
  }
  s.amount = fm1_mod_q14(amount);
  fm1_mod_set_slot(m, slot, &s);
}

/* One 32-frame block, running its tick (when there is one) at frame 0. */
static void step(fm1_mod_t *m) {
  if (fm1_mod_begin(m, G, 0) == 0) fm1_mod_tick(m, 0, NULL);
}

static void steps(fm1_mod_t *m, unsigned n) {
  while (n--) step(m);
}

static float out(fm1_mod_t *m, unsigned pos, unsigned port) { return fm1_mod_out(m, pos, port); }

static const fm1_mod_gate_t *gout(fm1_mod_t *m, unsigned pos, unsigned port) {
  return fm1_mod_gate_out(m, pos, port);
}

/* The frame of the first rising edge of an output in the last tick, or -1. */
static int rise_at(fm1_mod_t *m, unsigned pos, unsigned port) {
  const fm1_mod_gate_t *g = gout(m, pos, port);
  unsigned e;
  for (e = 0; e < g->n; ++e) {
    if (g->ev[e].high) return g->ev[e].frame;
  }
  return -1;
}

static int fall_at(fm1_mod_t *m, unsigned pos, unsigned port) {
  const fm1_mod_gate_t *g = gout(m, pos, port);
  unsigned e;
  for (e = 0; e < g->n; ++e) {
    if (!g->ev[e].high) return g->ev[e].frame;
  }
  return -1;
}

static int rises(fm1_mod_t *m, unsigned pos, unsigned port) {
  const fm1_mod_gate_t *g = gout(m, pos, port);
  unsigned e;
  int n = 0;
  for (e = 0; e < g->n; ++e) n += g->ev[e].high;
  return n;
}

static uint32_t bits(float x) { return mod_bits(x); }

/* ---- Calc and Mix ------------------------------------------------------------- */

static void calc(void) {
  static const float kv[] = { -1.0f, -0.5f, -0.1f, 0.0f, 0.3f, 1.0f };
  fm1_mod_t *m = make(0, 0, 1);
  unsigned op, i, j;
  put(m, 0, "calc");
  step(m);                                         /* the first block has no tick */
  for (op = 0; op < 10; ++op) {
    for (i = 0; i < 6; ++i) {
      for (j = 0; j < 6; ++j) {
        const float a = kv[i], b = kv[j];
        float want;
        set(m, 0, "Op", (float)op);
        set(m, 0, "A", a);
        set(m, 0, "B", b);
        set(m, 0, "Amount", 0.75f);
        set(m, 0, "Offset", 0.125f);
        set(m, 0, "Fade", 0.25f);
        step(m);
        switch (op) {
          case 0: want = a + b; break;
          case 1: want = a - b; break;
          case 2: want = a * b; break;
          case 3: want = a < b ? a : b; break;
          case 4: want = a > b ? a : b; break;
          case 5: want = (a + b) * 0.5f; break;
          case 6: want = a < 0.0f ? -a : a; break;
          case 7: want = a > 0.0f ? a : 0.0f; break;
          case 8: want = -a; break;
          default: want = a + (b - a) * 0.25f; break;
        }
        want = 0.75f * want + 0.125f;
        want = want > 1.0f ? 1.0f : want < -1.0f ? -1.0f : want;
        CHECK(bits(out(m, 0, 0)) == bits(want) && bits(out(m, 0, 1)) == bits(-want));
      }
    }
  }
  /* Log, Root, Square through the matrix's tables, within their accuracy. */
  set(m, 0, "Amount", 1.0f);
  set(m, 0, "Offset", 0.0f);
  for (i = 0; i <= 40; ++i) {
    const float a = -1.0f + 0.05f * (float)i, s = a < 0.0f ? -1.0f : 1.0f, x = fabsf(a);
    set(m, 0, "A", a);
    set(m, 0, "Op", 10.0f);
    step(m);
    CHECK(fabsf(out(m, 0, 0) - s * (float)(log1p((exp(4.0) - 1.0) * x) / 4.0)) < 0.02f);
    set(m, 0, "Op", 11.0f);
    step(m);
    CHECK(fabsf(out(m, 0, 0) - s * sqrtf(x)) < 0.03f);
    set(m, 0, "Op", 12.0f);
    step(m);
    CHECK(fabsf(out(m, 0, 0) - s * x * x) < 0.002f);
  }
  /* Slope: a ramp of 0.001 a tick is 0.001 x 1,378.7 / 10 per 0.1 s. */
  set(m, 0, "Op", 13.0f);
  for (i = 0; i < 50; ++i) {
    set(m, 0, "A", -0.5f + 0.001f * (float)i);
    step(m);
  }
  CHECK(fabsf(out(m, 0, 0) - 0.001f * (float)(TICK_HZ / 10.0)) < 1e-3f);
  /* Snap: whole semitones of the offset. */
  set(m, 0, "Op", 0.0f);
  set(m, 0, "A", 0.0f);
  set(m, 0, "B", 0.0f);
  set(m, 0, "Offset", 0.105f);
  set(m, 0, "Snap", 1.0f);
  step(m);
  CHECK(bits(out(m, 0, 0)) == bits(6.0f * (1.0f / 60.0f)));
  fm1_mod_destroy(m);
}

static void mix(void) {
  fm1_mod_t *m = make(0, 0, 1);
  put(m, 0, "mix");
  set(m, 0, "Gain2", 2.0f);
  set(m, 0, "Offset", -0.25f);
  cable(m, 0, FM1_MOD_SRC_VEL, 0, "In1", -1, 0.5f);
  cable(m, 1, FM1_MOD_SRC_VEL, 0, "In2", -1, 0.25f);
  fm1_mod_live_note(m, 60, 127);
  steps(m, 3);
  /* VEL 1: In1 0.5, In2 0.25 x gain 2: sum 1.0, two cables: avg 0.5. */
  CHECK(out(m, 0, 0) == 0.75f && out(m, 0, 1) == 0.25f && out(m, 0, 2) == -0.75f);
  fm1_mod_destroy(m);
}

/* ---- Slew ------------------------------------------------------------------------ */

static unsigned ticks_to(fm1_mod_t *m, unsigned port, float target, unsigned limit) {
  unsigned n = 0;
  while (n < limit && out(m, 0, port) != target) {
    step(m);
    ++n;
  }
  return n;
}

static void slew(void) {
  const float tick_s = (float)(1.0 / TICK_HZ);
  fm1_mod_t *m = make(0, 0, 1);
  unsigned n, j;
  float t;
  put(m, 0, "slew");
  set(m, 0, "Up", 0.6f);
  set(m, 0, "Down", 0.2f);
  step(m);
  /* Linear: a full move in the knob's time. */
  t = fm1_mp_env_time_from_knob(0.6f);
  set(m, 0, "In", 1.0f);
  n = ticks_to(m, 0, 1.0f, 100000);
  CHECK(fabsf((float)n - t / tick_s) <= 1.0f);
  set(m, 0, "In", 0.0f);
  n = ticks_to(m, 0, 0.0f, 100000);
  CHECK(fabsf((float)n - fm1_mp_env_time_from_knob(0.2f) / tick_s) <= 1.0f);
  /* Spread: OUT6 takes six times as long at +1, a sixth at -1. */
  set(m, 0, "Spread", 1.0f);
  set(m, 0, "In", 1.0f);
  n = ticks_to(m, 5, 1.0f, 100000);
  CHECK(fabsf((float)n - 6.0f * t / tick_s) <= 1.0f);
  set(m, 0, "In", 0.0f);
  steps(m, 20000);
  set(m, 0, "Spread", -1.0f);
  set(m, 0, "In", 1.0f);
  n = ticks_to(m, 5, 1.0f, 100000);
  CHECK(fabsf((float)n - t / 6.0f / tick_s) <= 1.0f);
  /* Expo: 1 - 1/e after the time constant, landing exactly. */
  set(m, 0, "Spread", 0.0f);
  set(m, 0, "In", 0.0f);
  steps(m, 20000);
  set(m, 0, "Type", 1.0f);
  set(m, 0, "In", 1.0f);
  n = (unsigned)(t / tick_s + 0.5f);
  steps(m, n);
  CHECK(fabsf(out(m, 0, 0) - (float)(1.0 - exp(-(double)n * tick_s / t))) < 2e-3f);
  CHECK(ticks_to(m, 0, 1.0f, 100000) < 100000);
  /* THRU: every output jumps while it is high. */
  set(m, 0, "In", -1.0f);
  cable(m, 0, FM1_MOD_SRC_KEY, 0, NULL, 0, 1.0f);
  fm1_mod_live_note(m, 60, 100);
  steps(m, 2);
  for (j = 0; j < 6; ++j) CHECK(out(m, 0, j) == -1.0f);
  fm1_mod_destroy(m);
}

/* ---- Compare -------------------------------------------------------------------- */

static void compare(void) {
  fm1_mod_t *m = make(0, 0, 1);
  fm1_mod_t *sweep = make(1, 0, 2);
  float a = -1.0f, prev;
  unsigned k, seen = 0;
  put(m, 0, "compare");
  set(m, 0, "Hyst", 0.0f);
  set(m, 0, "Thresh", 0.3f);
  set(m, 0, "A", a);
  steps(m, 2);                                     /* the first block has no tick */
  CHECK(out(m, 0, 0) == 0.0f && out(m, 0, 1) == 1.0f && out(m, 0, 6) == 1.0f);   /* NOT, BELOW */
  /* Crossing ABOVE -> MID -> BELOW in one tick must preserve MID's pulse. */
  put(sweep, 0, "compare");
  set(sweep, 0, "Hyst", 0.0f);
  set(sweep, 0, "Width", 0.25f);
  set(sweep, 0, "A", 0.5f);
  steps(sweep, 2);
  CHECK(out(sweep, 0, 4) == 1.0f && out(sweep, 0, 5) == 0.0f && out(sweep, 0, 6) == 0.0f);
  set(sweep, 0, "A", -0.5f);
  step(sweep);
  CHECK(gout(sweep, 0, 5)->n == 2);
  CHECK(gout(sweep, 0, 5)->ev[0].high == 1 && gout(sweep, 0, 5)->ev[0].frame == 8);
  CHECK(gout(sweep, 0, 5)->ev[1].high == 0 && gout(sweep, 0, 5)->ev[1].frame == 24);
  CHECK(out(sweep, 0, 5) == 0.0f && out(sweep, 0, 6) == 1.0f);
  set(sweep, 0, "A", 0.5f);
  step(sweep);
  CHECK(gout(sweep, 0, 5)->n == 2);
  CHECK(gout(sweep, 0, 5)->ev[0].high == 1 && gout(sweep, 0, 5)->ev[0].frame == 8);
  CHECK(gout(sweep, 0, 5)->ev[1].high == 0 && gout(sweep, 0, 5)->ev[1].frame == 24);
  CHECK(out(sweep, 0, 5) == 0.0f && out(sweep, 0, 4) == 1.0f);
  fm1_mod_destroy(sweep);
  /* A ramp up crosses 0.3 inside a tick: the edge is at the frame where
   * the straight line crosses it. */
  for (k = 0; k < 200; ++k) {
    prev = a;
    a = a + 0.0123f;
    set(m, 0, "A", a);
    step(m);
    if (prev - 0.3f <= 0.0f && a - 0.3f > 0.0f) {
      const float frac = (0.3f - (prev - 0.0f)) / (a - prev);
      const int want = (int)(frac * 32.0f);
      CHECK(rise_at(m, 0, 0) == (want > 31 ? 31 : want));
      CHECK(fall_at(m, 0, 1) == rise_at(m, 0, 0) && rise_at(m, 0, 2) == rise_at(m, 0, 0));
      ++seen;
    }
  }
  CHECK(seen == 1 && out(m, 0, 0) == 1.0f && out(m, 0, 4) == 1.0f);   /* GATE, ABOVE */
  /* Hysteresis: falls only below Thresh - Hyst / 2. */
  set(m, 0, "Hyst", 0.2f);
  for (k = 0; k < 300; ++k) {
    a = a - 0.01f;
    set(m, 0, "A", a);
    step(m);
    if (rises(m, 0, 3)) {
      CHECK(a - 0.3f < -0.1f && a - 0.3f > -0.12f);
      ++seen;
    }
  }
  CHECK(seen == 2);
  /* Window: high while |A - B - Thresh| < Width. */
  set(m, 0, "Mode", 1.0f);
  set(m, 0, "Hyst", 0.0f);
  set(m, 0, "Thresh", 0.0f);
  set(m, 0, "Width", 0.25f);
  for (k = 0; k <= 200; ++k) {
    a = -1.0f + 0.01f * (float)k;
    set(m, 0, "A", a);
    step(m);
    if (k > 2) {
      /* (at exactly Width it holds: a Schmitt trigger with no band) */
      if (fabsf(fabsf(a) - 0.25f) > 1e-6f) CHECK(out(m, 0, 0) == (fabsf(a) < 0.25f ? 1.0f : 0.0f));
      CHECK(out(m, 0, 5) == (fabsf(a) <= 0.25f ? 1.0f : 0.0f) || fabsf(fabsf(a) - 0.25f) < 1e-5f);
    }
  }
  /* Trend: high while A rises faster than Thresh (per 0.1 s). */
  set(m, 0, "Mode", 2.0f);
  set(m, 0, "Thresh", 0.05f);
  set(m, 0, "Hyst", 0.0f);
  for (k = 0; k < 100; ++k) {
    a = (k < 50 ? 0.001f : -0.001f) * (float)k;
    set(m, 0, "A", a);
    step(m);
    if (k > 2 && k < 50) CHECK(out(m, 0, 0) == 1.0f);   /* 0.1379 per 0.1 s > 0.05 */
    if (k > 52) CHECK(out(m, 0, 0) == 0.0f);
  }
  fm1_mod_destroy(m);
}

/* ---- Logic ---------------------------------------------------------------------- */

/* Gate A from KEY (note 60 on and off at frames), B from SEQ1. */
static void logic_case(unsigned op, const int *a_frames, const int *b_frames, const int *want) {
  fm1_mod_t *m = make(0, 0, 1);
  unsigned i, e, got = 0;
  int edges[16];
  put(m, 0, "logic");
  set(m, 0, "Op", (float)op);
  cable(m, 0, FM1_MOD_SRC_KEY, 0, NULL, 0, 1.0f);
  cable(m, 1, FM1_MOD_SRC_SEQ_GATE, 0, NULL, 1, 1.0f);
  steps(m, 2);
  /* Events in the next tick; each array alternates on/off, -1 ends. */
  for (i = 0; a_frames[i] >= 0; ++i) fm1_mod_note(m, (uint32_t)a_frames[i], 60, i & 1u ? 0 : 100);
  for (i = 0; b_frames[i] >= 0; ++i) fm1_mod_seq_note(m, (uint32_t)b_frames[i], 0, 60, i & 1u ? 0 : 100);
  /* fm1_mod_note's frames are within the current block; feed in order. */
  step(m);
  {
    const fm1_mod_gate_t *g = gout(m, 0, 0);
    for (e = 0; e < g->n; ++e) edges[got++] = (int)g->ev[e].frame * 2 + g->ev[e].high;
  }
  for (i = 0; want[i] >= 0; ++i) CHECK(i < got && edges[i] == want[i]);
  CHECK(got == i);
  {
    const fm1_mod_gate_t *n = gout(m, 0, 1);
    CHECK(n->n == got);
  }
  fm1_mod_destroy(m);
}

static void logic(void) {
  /* A high 2-20, B high 10-26. As frame x 2 + level. */
  static const int a[] = { 2, 20, -1 }, b[] = { 10, 26, -1 };
  static const int k_and[] = { 10 * 2 + 1, 20 * 2, -1 }, k_or[] = { 2 * 2 + 1, 26 * 2, -1 };
  static const int k_xor[] = { 2 * 2 + 1, 10 * 2, 20 * 2 + 1, 26 * 2, -1 };
  static const int k_sr[] = { 2 * 2 + 1, 10 * 2, -1 };          /* A sets, B resets */
  static const int k_d[] = { 10 * 2 + 1, -1 };                  /* B clocks A's level (high) */
  static const int k_tog[] = { 2 * 2 + 1, 10 * 2, -1 };         /* A flips, B resets */
  logic_case(0, a, b, k_and);
  logic_case(1, a, b, k_or);
  logic_case(2, a, b, k_xor);
  logic_case(6, a, b, k_sr);
  logic_case(7, a, b, k_d);
  logic_case(8, a, b, k_tog);
  {
    /* NAND, NOR, XNOR are the inverses: NOR starts high (both low) and
     * falls at 2, rises at 26. */
    static const int k_nor[] = { 2 * 2, 26 * 2 + 1, -1 };
    logic_case(4, a, b, k_nor);
  }
}

/* ---- Coin ------------------------------------------------------------------------ */

static void coin(void) {
  unsigned trial;
  for (trial = 0; trial < 5; ++trial) {
    static const float prob[5] = { 0.0f, 1.0f, 0.25f, 0.0f, 1.0f };
    const unsigned toggle = trial >= 3;
    fm1_mod_t *m = make(0, 0, 3);
    unsigned k, a = 0, b = 0, alternations = 0, last = 2;
    put(m, 0, "coin");
    set(m, 0, "Prob", prob[trial]);
    set(m, 0, "Mode", (float)toggle);
    for (k = 0; k < 4000; ++k) {
      step(m);
      fm1_mod_note(m, 7, 60, 100);   /* TRIG at frame 7 of the next tick */
      step(m);
      if (rises(m, 0, 0)) {
        CHECK(rise_at(m, 0, 0) == 7);
        ++a;
        alternations += last == 1;
        last = 0;
      }
      if (rises(m, 0, 1)) {
        CHECK(rise_at(m, 0, 1) == 7);
        ++b;
        alternations += last == 0;
        last = 1;
      }
      steps(m, 2);
      CHECK(out(m, 0, 0) == 0.0f && out(m, 0, 1) == 0.0f);   /* Latch off: they fall */
    }
    CHECK(a + b == 4000);
    if (trial == 0) CHECK(b == 0);
    if (trial == 1) CHECK(a == 0);
    if (trial == 2) CHECK(b > 880 && b < 1120);
    if (trial == 3) CHECK(b == 0);                           /* never switches from A */
    if (trial == 4) CHECK(alternations == 3999);             /* always switches */
    fm1_mod_destroy(m);
  }
  {
    /* Latch: the chosen side stays high, the other falls at the toss. */
    fm1_mod_t *m = make(0, 0, 9);
    unsigned k, high = 0;
    put(m, 0, "coin");
    set(m, 0, "Latch", 1.0f);
    for (k = 0; k < 200; ++k) {
      step(m);
      fm1_mod_note(m, 5, 60, 100);
      steps(m, 3);
      CHECK(out(m, 0, 0) + out(m, 0, 1) == 1.0f);
      high += out(m, 0, 1) == 1.0f;
    }
    CHECK(high > 60 && high < 140);
    fm1_mod_destroy(m);
  }
}

/* ---- Divide ---------------------------------------------------------------------- */

/* Clocks every `period` frames at frame offset 3 (the sequencer's CLOCK);
 * returns the absolute frames of OUT1 and OUT2 rises in `got`. */
static unsigned divide_run(fm1_mod_t *m, unsigned period, unsigned clocks, int start_at,
                           uint64_t *got1, uint64_t *got2, unsigned cap) {
  uint64_t t = 0, next = 3;
  unsigned n1 = 0, n2 = 0, c = 0;
  while (c < clocks || t < next + 50000u) {
    step(m);
    t += G;
    {
      unsigned port;
      for (port = 0; port < 2u; ++port) {
        const fm1_mod_gate_t *g = gout(m, 0, port);
        unsigned e;
        for (e = 0; e < g->n; ++e) {
          if (!g->ev[e].high) continue;
          if (port == 0 && n1 < cap) got1[n1++] = t - 2u * G + g->ev[e].frame;
          if (port == 1 && n2 < cap) got2[n2++] = t - 2u * G + g->ev[e].frame;
        }
      }
    }
    /* The block now running covers [t - G, t); its events reach the next tick. */
    if (c < clocks && next >= t - G && next < t) {
      if (start_at >= 0 && (int)c == start_at) fm1_mod_seq_run(m, (uint32_t)(next - (t - G)), 1);
      fm1_mod_seq_clock(m, (uint32_t)(next - (t - G)), 24u * c);
      next += period;
      ++c;
    }
    if (t > 4000000u) break;
  }
  return n1 | (n2 << 16);
}

static void divide(void) {
  static uint64_t g1[256], g2[256];
  fm1_mod_t *m;
  unsigned r, i;
  const uint64_t base = 3;        /* the first clock: frame 3 of the first block */
  /* Div 3 rotated 1 on OUT1; Euclid 3 of 8 on OUT2 (x..x..x.). */
  m = make(0, 0, 1);
  put(m, 0, "divide");
  set(m, 0, "Value1", 3.0f);
  set(m, 0, "Rot1", 1.0f);
  r = divide_run(m, 1000, 16, -1, g1, g2, 256);
  CHECK((r & 0xFFFFu) == 5);                       /* steps 2, 5, 8, 11, 14 */
  for (i = 0; i < 5; ++i) CHECK(g1[i] == base + 1000u * (2u + 3u * i));
  CHECK((r >> 16) == 6);                           /* steps 0, 3, 6, 8, 11, 14 */
  {
    static const unsigned want[6] = { 0, 3, 6, 8, 11, 14 };
    for (i = 0; i < 6; ++i) CHECK(g2[i] == base + 1000u * want[i]);
  }
  fm1_mod_destroy(m);
  /* Mult 4 on a 1,000-frame clock: after the second clock, 4 per period. */
  m = make(0, 0, 1);
  put(m, 0, "divide");
  set(m, 0, "Mode1", 1.0f);
  set(m, 0, "Value1", 4.0f);
  set(m, 0, "Mode2", 3.0f);                        /* Prob 1: every step */
  set(m, 0, "Fill2", 1.0f);
  r = divide_run(m, 1000, 6, -1, g1, g2, 256);
  CHECK((r & 0xFFFFu) == 1 + 4 * 5 && (r >> 16) == 6);
  for (i = 1; i < 21; ++i) CHECK(g1[i] == base + 1000u + 250u * (i - 1u));
  fm1_mod_destroy(m);
  /* Mult 16 on a 2,000-frame clock: all sixteen per period, though only 8
   * triggers wait at once (the run is queued as room frees). */
  m = make(0, 0, 1);
  put(m, 0, "divide");
  set(m, 0, "Mode1", 1.0f);
  set(m, 0, "Value1", 16.0f);
  set(m, 0, "Mode2", 3.0f);
  set(m, 0, "Fill2", 0.0f);                        /* Prob 0: none */
  r = divide_run(m, 2000, 4, -1, g1, g2, 256);
  CHECK((r & 0xFFFFu) == 1 + 16 * 3 && (r >> 16) == 0);
  for (i = 1; i < 49; ++i) {
    CHECK(g1[i] == base + 2000u * (1u + (i - 1u) / 16u) + 125u * ((i - 1u) % 16u));
  }
  fm1_mod_destroy(m);
  /* Swing 1 and a 10 ms delay, Div 1: odd triggers half a step late. */
  m = make(0, 0, 1);
  put(m, 0, "divide");
  set(m, 0, "Value1", 1.0f);
  set(m, 0, "Swing", 1.0f);
  set(m, 0, "Delay", 10.0f);
  set(m, 0, "Mode2", 3.0f);
  set(m, 0, "Fill2", 0.0f);                        /* Prob 0: none */
  r = divide_run(m, 1000, 8, -1, g1, g2, 256);
  CHECK((r & 0xFFFFu) == 8 && (r >> 16) == 0);
  {
    const uint64_t delay = (uint64_t)(10.0f * 0.001f * RATE);
    for (i = 0; i < 8; ++i) {
      /* The first clock knows no period yet: its swing is 0 (only odd ones swing). */
      CHECK(g1[i] == base + 1000u * i + delay + (i & 1u ? 500u : 0u));
    }
  }
  fm1_mod_destroy(m);
  /* RESET (START) makes the next clock step 0: Div 4 restarts. */
  m = make(0, 0, 1);
  put(m, 0, "divide");
  set(m, 0, "Value1", 4.0f);
  r = divide_run(m, 1000, 12, 6, g1, g2, 256);
  CHECK((r & 0xFFFFu) == 4);                       /* steps 0, 4, then reset at 6: 6, 10 */
  CHECK(g1[0] == base && g1[1] == base + 4000u && g1[2] == base + 6000u && g1[3] == base + 10000u);
  fm1_mod_destroy(m);
}

/* ---- Quantize ---------------------------------------------------------------------- */

static int in_major(int semis) {
  static const int major[12] = { 1, 0, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1 };
  return major[((semis % 12) + 12) % 12];
}

static void quantize(void) {
  fm1_mod_t *m = make(0, 0, 1);
  unsigned k, changes = 0, notes = 0;
  float last = 0.0f;
  put(m, 0, "quantize");                           /* Ionian on C, Range 5 */
  step(m);                                         /* the first block has no tick */
  for (k = 0; k <= 2000; ++k) {
    const float in = -0.5f + (float)k * 0.0005f;   /* -30 to +30 semitones */
    set(m, 0, "In", in);
    step(m);
    {
      const float o = out(m, 0, 0) * 60.0f;
      const int n = (int)lroundf(o);
      CHECK(fabsf(o - (float)n) < 1e-4f && in_major(n));
      CHECK(k == 0 || o >= last);                  /* rising input, rising notes */
      CHECK(fabsf(o - in * 60.0f) <= 1.5f);         /* the nearest, with hysteresis */
      if (k && o != last) {
        CHECK(rise_at(m, 0, 1) == 0);
        ++changes;
      } else if (k) {
        CHECK(rises(m, 0, 1) == 0);
      }
      notes += k == 0 || o != last;
      last = o;
    }
  }
  CHECK(notes >= 34 && changes == notes - 1u);     /* -30..30 in a major scale */
  /* Root D, Trans +7: C# is in D major, then a fifth up. */
  set(m, 0, "Root", 2.0f);
  set(m, 0, "Trans", 7.0f);
  set(m, 0, "In", 1.0f / 60.0f);
  steps(m, 2);
  CHECK(fabsf(out(m, 0, 0) * 60.0f - 8.0f) < 1e-4f);
  /* Clocked: IN is taken only at CLOCK's rise, CHANGED at its frame. */
  set(m, 0, "Root", 0.0f);
  set(m, 0, "Trans", 0.0f);
  cable(m, 0, FM1_MOD_SRC_KEY, 0, NULL, 0, 1.0f);
  set(m, 0, "In", 0.2f);
  steps(m, 3);
  CHECK(fabsf(out(m, 0, 0) * 60.0f - 1.0f) < 1e-4f && rises(m, 0, 1) == 0);   /* held */
  fm1_mod_note(m, 11, 60, 100);
  step(m);
  CHECK(fabsf(out(m, 0, 0) * 60.0f - 12.0f) < 1e-4f && rise_at(m, 0, 1) == 11);
  fm1_mod_destroy(m);
}

/* ---- Register ---------------------------------------------------------------------- */

static void reg_run(fm1_mod_t *m, unsigned clocks, float *cv, int write_at) {
  unsigned c;
  for (c = 0; c < clocks; ++c) {
    step(m);
    if ((int)c == write_at) fm1_mod_note(m, 2, 61, 100);   /* WRITE from KEY */
    fm1_mod_seq_clock(m, 4, 0);
    step(m);
    cv[c] = out(m, 0, 0);
    if ((int)c == write_at) fm1_mod_note(m, 2, 61, 0);
    steps(m, 2);
  }
}

static void register_(void) {
  static float a[200], b[200];
  fm1_mod_t *m;
  unsigned c, differ = 0;
  /* Change +1 locks a loop of Length; -1 a loop of twice it. */
  m = make(0, 0, 5);
  put(m, 0, "register");
  set(m, 0, "Change", 1.0f);
  set(m, 0, "Length", 7.0f);
  reg_run(m, 100, a, -1);
  for (c = 20; c + 7 < 100; ++c) CHECK(a[c] == a[c + 7]);
  fm1_mod_destroy(m);
  m = make(0, 0, 5);
  put(m, 0, "register");
  set(m, 0, "Change", -1.0f);
  set(m, 0, "Length", 7.0f);
  reg_run(m, 100, b, -1);
  for (c = 20; c + 14 < 100; ++c) CHECK(b[c] == b[c + 14]);
  for (c = 20; c < 40; ++c) differ += b[c] != b[c + 7];
  CHECK(differ > 10);
  fm1_mod_destroy(m);
  /* WRITE flips the next bit back: the loop changes from there on. */
  m = make(0, 0, 5);
  put(m, 0, "register");
  set(m, 0, "Change", 1.0f);
  set(m, 0, "Length", 7.0f);
  cable(m, 0, FM1_MOD_SRC_KEY, 0, NULL, 1, 1.0f);
  reg_run(m, 100, b, 50);
  for (c = 0; c < 50; ++c) CHECK(a[c] == b[c]);
  differ = 0;
  for (c = 50; c < 100; ++c) differ += a[c] != b[c];
  CHECK(differ > 5);
  fm1_mod_destroy(m);
}

/* Pattern data (fm1_mod_get_data / fm1_mod_set_data, notes/2026-10-06-
 * state-files.md ST12): a loop locked and edited by hand, saved and given
 * to a Register of another seed, plays on exactly where it was; bad data
 * is refused and changes nothing; only kinds with data take any. */
static void register_data(void) {
  static float a[200], b[200], c2[200];
  uint8_t data[FM1_MOD_DATA_MAX], again[FM1_MOD_DATA_MAX], bad[8];
  uint8_t version = 0;
  uint16_t n;
  unsigned c, k;
  fm1_mod_t *m = make(0, 0, 5), *r = make(1, 0xA5, 77), *q;
  put(m, 0, "register");
  set(m, 0, "Change", 1.0f);
  set(m, 0, "Length", 9.0f);
  reg_run(m, 60, a, 30);                       /* locked, and edited at clock 30 */
  n = fm1_mod_get_data(m, 0, data, (uint16_t)sizeof(data), &version);
  CHECK(n == 5 && version == 1 && data[4] == 9);
  put(r, 0, "register");
  set(r, 0, "Change", 1.0f);
  set(r, 0, "Length", 9.0f);
  CHECK(fm1_mod_set_data(r, 0, data, n, version) == 1);
  CHECK(fm1_mod_get_data(r, 0, again, (uint16_t)sizeof(again), &version) == 5);
  CHECK(memcmp(data, again, 5) == 0);
  reg_run(m, 80, a, -1);                       /* both run on: the same loop */
  reg_run(r, 80, b, -1);
  for (c = 0; c < 80; ++c) CHECK(a[c] == b[c]);
  /* Without the data, the other seed's loop. */
  q = make(2, 0, 77);
  put(q, 0, "register");
  set(q, 0, "Change", 1.0f);
  set(q, 0, "Length", 9.0f);
  reg_run(q, 80, c2, -1);
  for (c = 0, k = 0; c < 80; ++c) k += a[c] != c2[c];
  CHECK(k > 10);
  /* Refused, and nothing changes: another version, another size, a
   * length out of 1-32; a short buffer reads nothing. */
  memcpy(bad, data, 5);
  CHECK(fm1_mod_set_data(r, 0, bad, 5, 2) == 0);
  CHECK(fm1_mod_set_data(r, 0, bad, 4, 1) == 0);
  bad[4] = 0;
  CHECK(fm1_mod_set_data(r, 0, bad, 5, 1) == 0);
  bad[4] = 33;
  CHECK(fm1_mod_set_data(r, 0, bad, 5, 1) == 0);
  CHECK(fm1_mod_get_data(r, 0, again, 4, &version) == 0);
  CHECK(fm1_mod_get_data(r, 0, again, 5, &version) == 5);
  CHECK(fm1_mod_get_data(m, 0, data, 5, &version) == 5 && memcmp(data, again, 5) == 0);
  /* An empty position, and a kind without data. */
  CHECK(fm1_mod_get_data(r, 3, again, 5, &version) == 0);
  CHECK(fm1_mod_set_data(r, 3, data, 5, 1) == 0);
  put(r, 1, "lfo");
  CHECK(fm1_mod_get_data(r, 1, again, 5, &version) == 0);
  CHECK(fm1_mod_set_data(r, 1, data, 5, 1) == 0);
  /* The rules every kind keeps: data has both hooks, a version, a size
   * within the cap and one instance; no data, no hooks. */
  for (k = 0; k < fm1_mod_kind_count; ++k) {
    const fm1_mod_kind_t *kd = fm1_mod_kinds[k];
    if (kd->data_bytes) {
      CHECK(kd->get_data && kd->set_data && kd->data_version >= 1);
      CHECK(kd->data_bytes <= FM1_MOD_DATA_MAX && !(kd->flags & FM1_MOD_KIND_POLY_OK));
    } else {
      CHECK(!kd->get_data && !kd->set_data && kd->data_version == 0);
    }
  }
  fm1_mod_destroy(m);
  fm1_mod_destroy(r);
  fm1_mod_destroy(q);
}

/* ---- Function ---------------------------------------------------------------------- */

/* Absolute frame of the next rise on `port` of module 0 within `limit`
 * ticks, stepping; -1 if none. `now` is the absolute frame after the last
 * block. */
static int64_t next_rise(fm1_mod_t *m, unsigned port, uint64_t *now, unsigned limit) {
  while (limit--) {
    int f;
    step(m);
    *now += G;
    f = rise_at(m, 0, port);
    if (f >= 0) return (int64_t)(*now - 2u * G + (unsigned)f);
  }
  return -1;
}

static void function(void) {
  const float rise_s = fm1_mp_env_time_from_knob(0.4f), fall_s = fm1_mp_env_time_from_knob(0.5f);
  const float tol = 2.0f + rise_s * RATE * 2e-3f;
  fm1_mod_t *m = make(0, 0, 1);
  uint64_t now = 0;
  int64_t t, eor, eoc, c1, c2;
  float v1, v2;
  unsigned k;
  put(m, 0, "function");
  set(m, 0, "Rise", 0.4f);
  set(m, 0, "Fall", 0.5f);
  steps(m, 2);
  now = 2u * G;
  /* AD: a TRIG at frame 9 of the next tick; EOR one rise later, EOC a fall
   * after that. */
  fm1_mod_note(m, 9, 60, 100);
  fm1_mod_note(m, 9, 60, 0);
  t = (int64_t)(now - G) + 9;
  eor = next_rise(m, 4, &now, 100000);
  eoc = next_rise(m, 5, &now, 100000);
  CHECK(fabsf((float)(eor - t) - rise_s * RATE) <= tol);
  CHECK(fabsf((float)(eoc - eor) - fall_s * RATE) <= tol);
  CHECK(out(m, 0, 0) == 0.0f);
  /* Retrig 0: a trigger during the cycle is ignored. */
  set(m, 0, "Retrig", 0.0f);
  step(m);
  now += G;
  fm1_mod_note(m, 0, 60, 100);
  fm1_mod_note(m, 0, 60, 0);
  t = (int64_t)(now - G);
  steps(m, 20);
  now += 20u * G;
  fm1_mod_note(m, 0, 60, 100);                     /* mid-rise: ignored */
  fm1_mod_note(m, 0, 60, 0);
  eor = next_rise(m, 4, &now, 100000);
  CHECK(fabsf((float)(eor - t) - rise_s * RATE) <= tol);
  next_rise(m, 5, &now, 100000);
  /* Retrig 1: it restarts the rise from where it is, so EOR moves. */
  set(m, 0, "Retrig", 1.0f);
  step(m);
  now += G;
  fm1_mod_note(m, 0, 60, 100);
  fm1_mod_note(m, 0, 60, 0);
  steps(m, 200);
  now += 200u * G;
  fm1_mod_note(m, 0, 60, 100);
  fm1_mod_note(m, 0, 60, 0);
  t = (int64_t)(now - G);
  eor = next_rise(m, 4, &now, 100000);
  CHECK(fabsf((float)(eor - t) - rise_s * RATE) <= tol);
  next_rise(m, 5, &now, 100000);
  /* Cycle: a steady period of rise + fall. */
  set(m, 0, "Mode", 2.0f);
  c1 = next_rise(m, 5, &now, 100000);
  c2 = next_rise(m, 5, &now, 100000);
  CHECK(fabsf((float)(c2 - c1) - (rise_s + fall_s) * RATE) <= 2.0f * tol);
  /* HOLD freezes it. */
  cable(m, 0, FM1_MOD_SRC_KEY, 0, NULL, 3, 1.0f);
  fm1_mod_live_note(m, 60, 100);
  step(m);
  v1 = out(m, 0, 0);
  steps(m, 300);
  v2 = out(m, 0, 0);
  CHECK(v1 == v2);
  fm1_mod_live_note(m, 60, 0);
  steps(m, 3);
  CHECK(out(m, 0, 0) != v2);
  fm1_mod_destroy(m);

  /* AR: rises on the key, holds at Level, falls on release. */
  m = make(0, 0, 1);
  put(m, 0, "function");
  set(m, 0, "Mode", 1.0f);
  set(m, 0, "Rise", 0.2f);
  set(m, 0, "Level", 0.8f);
  fm1_mod_live_note(m, 60, 100);
  steps(m, 3000);
  CHECK(out(m, 0, 0) == 0.8f && out(m, 0, 2) == 0.0f && out(m, 0, 3) == 0.0f);
  fm1_mod_live_note(m, 60, 0);
  steps(m, 2);
  CHECK(out(m, 0, 3) == 1.0f && out(m, 0, 0) < 0.8f);
  steps(m, 30000);
  CHECK(out(m, 0, 0) == 0.0f);
  /* Held at the top, a switch to AD lets it fall. */
  fm1_mod_live_note(m, 60, 100);
  steps(m, 3000);
  CHECK(out(m, 0, 0) == 0.8f);
  set(m, 0, "Mode", 0.0f);
  steps(m, 2);
  CHECK(out(m, 0, 3) == 1.0f && out(m, 0, 0) < 0.8f);
  fm1_mod_destroy(m);

  /* Slew: OUT glides to Floor + IN, a full move in Rise; half a move in
   * half. Shape -1 is ahead of the straight line at the midpoint, +1
   * behind. */
  for (k = 0; k < 3; ++k) {
    const float shape = (float)k - 1.0f;
    unsigned n;
    v1 = 0.0f;
    m = make(0, 0, 1);
    put(m, 0, "function");
    set(m, 0, "Mode", 3.0f);
    set(m, 0, "Rise", 0.5f);
    set(m, 0, "Shape", shape);
    set(m, 0, "In", 0.5f);
    n = 0;
    while (out(m, 0, 0) != 0.5f && n < 100000) {
      step(m);
      ++n;
      if (n == (unsigned)(0.25f * fm1_mp_env_time_from_knob(0.5f) * RATE / G)) v1 = out(m, 0, 0);
    }
    /* n counts the first block (no tick) and the tick the glide ends in. */
    CHECK(fabsf((float)(n - 1u) * G - 0.5f * fm1_mp_env_time_from_knob(0.5f) * RATE) <= tol + G);
    if (k == 0) CHECK(v1 > 0.3f);
    if (k == 1) CHECK(fabsf(v1 - 0.25f) < 0.01f);
    if (k == 2) CHECK(v1 < 0.2f);
    fm1_mod_destroy(m);
  }

  /* Slew to a target that wobbles a little every tick (a vibrato on a
   * step to 0.5): every shape rises without falling back until it is
   * there, and is there by twice the glide's time. A slow start (+1)
   * keeps its place on its curve as the target moves; were it to restart
   * at the curve's flat start each tick, it would stay near 0. */
  for (k = 0; k < 3; ++k) {
    const float shape = (float)k - 1.0f;
    const unsigned glide = (unsigned)(0.5f * fm1_mp_env_time_from_knob(0.5f) * RATE / G);
    unsigned n, rising = 1, arrived = 0;
    float last = 0.0f;
    m = make(0, 0, 1);
    put(m, 0, "function");
    set(m, 0, "Mode", 3.0f);
    set(m, 0, "Rise", 0.5f);
    set(m, 0, "Shape", shape);
    step(m);
    for (n = 1; n <= 2u * glide; ++n) {
      set(m, 0, "In", n & 1u ? 0.502f : 0.498f);
      step(m);
      if (!arrived && out(m, 0, 0) < last) rising = 0;
      last = out(m, 0, 0);
      if (!arrived && last >= 0.497f) arrived = n;
    }
    CHECK(rising && arrived && last >= 0.497f && last <= 0.503f);
    fm1_mod_destroy(m);
  }

  /* Sync 1/4 at 120 BPM: one cycle per beat, 22,059 frames, Start
   * restarting it. */
  m = make(0, 0, 1);
  put(m, 0, "function");
  set(m, 0, "Mode", 2.0f);
  set(m, 0, "Sync", 5.0f);
  now = 0;
  fm1_mod_begin(m, G, 12000);
  fm1_mod_seq_run(m, 5, 1);
  now = G;
  c1 = next_rise(m, 2, &now, 100000);              /* UP rises at Start */
  c1 = next_rise(m, 5, &now, 100000);
  c2 = next_rise(m, 5, &now, 100000);
  CHECK(llabs((long long)(c2 - c1) - 22059) <= 2);
  fm1_mod_destroy(m);
}

/* ---- Bounce ---------------------------------------------------------------------------- */

static void bounce(void) {
  unsigned k;
  for (k = 0; k < 2; ++k) {
    const float gravity = (float)k;
    fm1_mod_t *m = make(0, 0, 1);
    uint64_t now = 0;
    int64_t hit;
    int g;
    double fall;
    unsigned n, hits = 0;
    put(m, 0, "bounce");
    set(m, 0, "Gravity", gravity);
    set(m, 0, "Bounce", 0.5f);
    steps(m, 2);
    now = 2u * G;
    fm1_mod_note(m, 0, 60, 100);
    fm1_mod_note(m, 0, 60, 0);
    hit = next_rise(m, 1, &now, 200000);
    /* A fall from 2^30 under Peaks' gravity g (position units per sample^2). */
    g = mod_mi_lut_gravity[k ? 0 : MOD_MI_LUT_SIZE - 1];
    fall = sqrt(2.0 * 1073725440.0 / g) / 48000.0;
    CHECK(fabs((double)(hit - (int64_t)G) / RATE - fall) < 2e-3 + fall * 0.01);
    if (k == 0) CHECK(fall > 0.9 && fall < 1.0);
    else CHECK(fall > 0.004 && fall < 0.006);
    /* It comes to rest without a stream of hits. */
    for (n = 0; n < 20000; ++n) {
      step(m);
      hits += (unsigned)rises(m, 0, 1);
    }
    CHECK(hits < 60 && hits > 3);
    for (n = 0; n < 2000; ++n) {
      step(m);
      /* Heavy, it comes to rest. Light, Peaks' integer rebound adds a little
       * energy at low speed and the ball bounces for ever, a few percent
       * high: HIT keeps going, as the original would. */
      if (k == 1) CHECK(rises(m, 0, 1) == 0);
    }
    fm1_mod_destroy(m);
  }
}

/* ---- Burst ------------------------------------------------------------------------------- */

static void burst(void) {
  unsigned count;
  for (count = 1; count <= 8; ++count) {
    fm1_mod_t *m = make(0, 0, 1);
    unsigned n, outs = 0, gates = 0, dones = 0;
    put(m, 0, "burst");
    set(m, 0, "Count", (float)count);
    set(m, 0, "Spacing", 0.2f);
    set(m, 0, "Length", 0.1f);
    step(m);
    fm1_mod_note(m, 3, 60, 100);
    fm1_mod_note(m, 3, 60, 0);
    for (n = 0; n < 20000; ++n) {
      step(m);
      outs += (unsigned)rises(m, 0, 0);
      gates += (unsigned)rises(m, 0, 1);
      dones += (unsigned)rises(m, 0, 2);
    }
    CHECK(outs == count && gates == 1 && dones == 1);
    fm1_mod_destroy(m);
  }
  {
    /* Accel 1: each gap shorter than the one before. Clocked: the gaps
     * share the clock's period. */
    unsigned mode;
    for (mode = 0; mode < 2; ++mode) {
      fm1_mod_t *m = make(0, 0, 1);
      uint64_t now = 0, at[8];
      unsigned n = 0, i;
      put(m, 0, "burst");
      set(m, 0, "Count", 8.0f);
      set(m, 0, "Spacing", 0.4f);
      set(m, 0, "Length", 0.0f);
      if (mode == 0) {
        set(m, 0, "Accel", 1.0f);
      } else {
        cable(m, 0, FM1_MOD_SRC_CLOCK, 0, NULL, 1, 1.0f);
        for (i = 0; i < 3; ++i) {                   /* clocks 12,000 frames apart */
          step(m);
          now += G;
          fm1_mod_seq_clock(m, 0, 0);
          steps(m, 374);
          now += 374u * G;
        }
      }
      step(m);
      now += G;
      fm1_mod_note(m, 0, 60, 100);
      fm1_mod_note(m, 0, 60, 0);
      while (n < 8) {
        int f;
        step(m);
        now += G;
        f = rise_at(m, 0, 0);
        if (f >= 0) at[n++] = now - 2u * G + (unsigned)f;
        if (now > 2000000u) break;
      }
      CHECK(n == 8);
      for (i = 2; i < n; ++i) {
        const int64_t gap = (int64_t)(at[i] - at[i - 1]), before = (int64_t)(at[i - 1] - at[i - 2]);
        if (mode == 0) CHECK(gap < before);
        /* 12,000 frames between the clocks (375 blocks), / 8 per gap, to
         * a 12 kHz call (3.7 frames). */
        else CHECK(llabs((long long)gap - 12000 / 8) <= 8);
      }
      fm1_mod_destroy(m);
    }
  }
}

/* ---- Filter -------------------------------------------------------------------------- */

static double cutoff_hz(float knob) { return 0.05 * pow(2.0, 13.0 * knob); }

/* |H| of the trapezoidal SVF at frequency f: the analog prototype at the
 * prewarped frequency. */
static void analytic(double fc, double k, double f, double *lp, double *bp, double *hp) {
  const double g = tan(PI_D * fc / TICK_HZ), w = tan(PI_D * f / TICK_HZ) / g;
  const double re = 1.0 - w * w, im = k * w, d = sqrt(re * re + im * im);
  *lp = 1.0 / d;
  *bp = w / d;
  *hp = w * w / d;
}

static void filter(unsigned *responses) {
  static const float knobs[3] = { 0.3325f, 0.588f, 0.8435f };    /* about 1, 10 and 100 Hz */
  static const float res[3] = { 0.0f, 0.1591f, 0.3f };
  static const double ratios[5] = { 0.25, 0.5, 1.0, 2.0, 4.0 };
  unsigned a, b, c;
  for (a = 0; a < 3; ++a) {
    for (b = 0; b < 3; ++b) {
      for (c = 0; c < 5; ++c) {
        const double fc = cutoff_hz(knobs[a]), f = fc * ratios[c];
        const double r = 1.0 - res[b], k = 2.0 * r * r, w = 2.0 * PI_D * f / TICK_HZ;
        const unsigned settle = (unsigned)(30.0 * TICK_HZ / (k * PI_D * fc)) + 2000u;
        const unsigned n = (unsigned)(TICK_HZ / f * 10.0) + 1000u;
        double lp, bp, hp, ss = 0, sc = 0, cc = 0, ys[3] = { 0, 0, 0 }, yc[3] = { 0, 0, 0 };
        unsigned i, j;
        fm1_mod_t *m = make(0, 0, 1);
        put(m, 0, "filter");
        set(m, 0, "Cutoff", knobs[a]);
        set(m, 0, "Res", res[b]);
        step(m);
        for (i = 0; i < settle + n; ++i) {
          const double s = sin(w * (double)i), co = cos(w * (double)i);
          set(m, 0, "In", (float)(0.4 * s));
          step(m);
          if (i >= settle) {
            ss += s * s;
            sc += s * co;
            cc += co * co;
            for (j = 0; j < 3; ++j) {
              const double y = out(m, 0, 1 + j);
              ys[j] += y * s;
              yc[j] += y * co;
            }
          }
        }
        analytic(fc, k, f, &lp, &bp, &hp);
        {
          /* The least-squares fit of a sin + b cos: exact for any span. */
          const double det = ss * cc - sc * sc, want[3] = { lp, bp, hp };
          for (j = 0; j < 3; ++j) {
            const double fa = (ys[j] * cc - yc[j] * sc) / det, fb = (yc[j] * ss - ys[j] * sc) / det;
            const double got = hypot(fa, fb) / 0.4;
            if (fabs(got - want[j]) > 0.01 * want[j] + 2e-3) {
              fprintf(stderr, "filter fc %.3f k %.3f f %.3f out %u: got %.5f want %.5f\n", fc, k, f,
                      j, got, want[j]);
            }
            CHECK(fabs(got - want[j]) <= 0.01 * want[j] + 2e-3);
            if (b == 1 && c == 2 && j == 0) CHECK(fabs(got - sqrt(0.5)) < 0.01);   /* -3 dB */
            ++*responses;
          }
        }
        fm1_mod_destroy(m);
      }
    }
  }
  {
    /* DC: LP passes it, HP and BP take it out. */
    fm1_mod_t *m = make(0, 0, 1);
    put(m, 0, "filter");
    set(m, 0, "Cutoff", 0.6f);
    set(m, 0, "In", 0.5f);
    steps(m, 20000);
    CHECK(fabsf(out(m, 0, 1) - 0.5f) < 1e-4f && fabsf(out(m, 0, 2)) < 1e-4f &&
          fabsf(out(m, 0, 3)) < 1e-4f);
    fm1_mod_destroy(m);
  }
  {
    /* Ringing. Res 1 (k = 0): a strike rings at exactly the cutoff (the
     * poles at 2 atan(g)) and does not decay. Res 0.9 (k = 0.02): the
     * envelope decays by the poles' radius per tick. */
    unsigned trial;
    for (trial = 0; trial < 2; ++trial) {
      const float knob = 0.5f, resv = trial ? 0.9f : 1.0f;
      const double fc = cutoff_hz(knob), r = 1.0 - resv, k = 2.0 * r * r;
      const double g = tan(PI_D * fc / TICK_HZ);
      const double radius = sqrt((1.0 - k * g + g * g) / (1.0 + k * g + g * g));
      fm1_mod_t *m = make(0, 0, 1);
      unsigned i, crossings = 0, first = 0, last = 0, at_early = 0, at_late = 0;
      float prev = 0.0f, peak_early = 0.0f, peak_late = 0.0f;
      const unsigned span = 20000;
      put(m, 0, "filter");
      set(m, 0, "Cutoff", knob);
      set(m, 0, "Res", resv);
      cable(m, 0, FM1_MOD_SRC_TRIG, 0, NULL, 0, 1.0f);
      step(m);
      fm1_mod_note(m, 0, 60, 100);
      step(m);
      for (i = 0; i < span; ++i) {
        const float y = out(m, 0, 2);
        if (i && prev <= 0.0f && y > 0.0f) {   /* the strike itself is no crossing */
          if (!crossings) first = i;
          last = i;
          ++crossings;
        }
        if (i < 1000 && fabsf(y) > peak_early) {
          peak_early = fabsf(y);
          at_early = i;
        }
        if (i >= span - 1000 && fabsf(y) > peak_late) {
          peak_late = fabsf(y);
          at_late = i;
        }
        prev = y;
        step(m);
      }
      {
        const double measured = (double)(crossings - 1) * TICK_HZ / (double)(last - first);
        CHECK(fabs(measured / fc - 1.0) < 2e-3);
      }
      CHECK(peak_early > 0.95f && peak_early < 1.05f);
      if (trial == 0) {
        CHECK(fabsf(peak_late / peak_early - 1.0f) < 1e-3f);
      } else {
        const double want = pow(radius, (double)(at_late - at_early));
        CHECK(fabs(peak_late / peak_early / want - 1.0) < 0.01);
      }
      fm1_mod_destroy(m);
    }
  }
  {
    /* Stable under random modulation of everything, driven or struck. */
    fm1_mod_t *m = make(0, 0, 1);
    fm1_mod_stats_t st;
    unsigned i;
    srand(7);
    put(m, 0, "filter");
    cable(m, 0, FM1_MOD_SRC_TRIG, 0, NULL, 0, 1.0f);
    for (i = 0; i < 200000; ++i) {
      set(m, 0, "Cutoff", (float)rand() / (float)RAND_MAX);
      set(m, 0, "Res", i % 5000 < 2500 ? 1.0f : (float)rand() / (float)RAND_MAX);
      set(m, 0, "In", (float)rand() / (float)RAND_MAX * 2.0f - 1.0f);
      if (i % 97 == 0) fm1_mod_live_note(m, 60, 100);
      step(m);
      CHECK(fabsf(m->out[m->cur][0][1]) <= 1.0f);
    }
    fm1_mod_get_stats(m, &st);
    CHECK(st.nonfinite == 0);
    fm1_mod_destroy(m);
  }
}

/* ---- every kind: any fill, extreme and random parameters ---------------------------- */

/* A scenario for kind k at position 0 with an LFO at 1: the LFO into every
 * MOD and INPUT parameter, KEY, TRIG and CLOCK into the gate inputs, notes
 * and sequencer clocks fed at frames, and, with `fuzz`, random or extreme
 * bases each tick. Records every output's bits and gate edges. */
static unsigned scenario(fm1_mod_t *m, int k, unsigned ticks, int fuzz, uint32_t *rec, unsigned cap) {
  const fm1_mod_kind_t *kd = fm1_mod_kinds[k];
  unsigned i, n = 0, slot = 0;
  uint32_t r = 99;
  fm1_mod_set_kind(m, 0, k);
  fm1_mod_set_kind(m, 1, fm1_mod_kind_find("lfo"));
  fm1_mod_set_param(m, 1, 0, 0.7f);
  for (i = 0; i < kd->n_params && slot < 24u; ++i) {
    if (!(kd->params[i].flags & (FM1_PARAM_MOD | FM1_PARAM_INPUT))) continue;
    {
      fm1_mod_slot_t s;
      memset(&s, 0, sizeof(s));
      s.src = (uint8_t)out_of(1, 0);
      s.via = FM1_MOD_NONE;
      s.dst_unit = FM1_MOD_MODULE;
      s.dst = kd->params[i].uid;
      s.flags = FM1_MOD_SLOT_ON;
      s.amount = fm1_mod_q14(0.3f);
      fm1_mod_set_slot(m, slot++, &s);
    }
  }
  for (i = 0; i < kd->n_gate_in; ++i) {
    static const uint8_t src[3] = { FM1_MOD_SRC_TRIG, FM1_MOD_SRC_KEY, FM1_MOD_SRC_CLOCK };
    fm1_mod_slot_t s;
    memset(&s, 0, sizeof(s));
    s.src = src[i % 3u];
    s.via = FM1_MOD_NONE;
    s.dst_unit = FM1_MOD_MODULE;
    s.dst = (uint16_t)i;
    s.flags = FM1_MOD_SLOT_ON | FM1_MOD_SLOT_GATE_DST;
    s.amount = fm1_mod_q14(1.0f);
    fm1_mod_set_slot(m, 24u + i, &s);
  }
  for (i = 0; i < ticks; ++i) {
    unsigned p;
    if (fuzz) {
      for (p = 0; p < kd->n_params; ++p) {
        static const float extreme[6] = { 1e30f, -1e30f, INFINITY, -INFINITY, NAN, 0.0f };
        const fm1_param_t *q = &kd->params[p];
        float v;
        r = r * 1664525u + 1013904223u;
        if (fuzz == 2) v = extreme[(r >> 8) % 6u];
        else v = q->min + (q->max - q->min) * (float)(r >> 8) * (1.0f / 16777216.0f);
        if ((r >> 4) % 7u == 0) fm1_mod_set_param(m, 0, p, v);
      }
    }
    step(m);
    if (i % 13u == 5u) fm1_mod_note(m, (i * 7u) % 32u, (uint8_t)(48u + i % 24u), 100);
    if (i % 13u == 9u) fm1_mod_note(m, (i * 5u) % 32u, (uint8_t)(48u + (i - 4u) % 24u), 0);
    if (i % 31u == 3u) fm1_mod_seq_clock(m, (i * 3u) % 32u, 24u * i);
    for (p = 0; p < kd->n_out; ++p) {
      const fm1_mod_gate_t *g = gout(m, 0, p);
      unsigned e;
      CHECK(mod_finite(out(m, 0, p)));
      if (n < cap) rec[n++] = bits(out(m, 0, p));
      for (e = 0; e < g->n && n < cap; ++e) rec[n++] = (uint32_t)(g->ev[e].frame << 8 | g->ev[e].high);
    }
  }
  return n;
}

static void every_kind(unsigned *fills, unsigned *fuzzed) {
  static uint32_t rec[3][40000];
  size_t k;
  for (k = 0; k < fm1_mod_kind_count; ++k) {
    unsigned n[3], f, fuzz;
    for (f = 0; f < 3; ++f) {
      static const int fill[3] = { 0x00, 0xA5, 0xFF };
      fm1_mod_t *m = make((int)f, fill[f], 11);
      n[f] = scenario(m, (int)k, 3000, 1, rec[f], 40000);
      fm1_mod_destroy(m);
    }
    CHECK(n[0] == n[1] && n[1] == n[2] && n[0] > 3000);
    CHECK(!memcmp(rec[0], rec[1], n[0] * sizeof(uint32_t)) &&
          !memcmp(rec[1], rec[2], n[0] * sizeof(uint32_t)));
    if (n[0] != n[1] || memcmp(rec[0], rec[1], n[0] * sizeof(uint32_t))) {
      fprintf(stderr, "fills differ for %s\n", fm1_mod_kinds[k]->id);
    }
    ++*fills;
    for (fuzz = 1; fuzz <= 2; ++fuzz) {
      fm1_mod_t *m = make(0, 0, (uint32_t)fuzz);
      fm1_mod_stats_t st;
      scenario(m, (int)k, 5000, (int)fuzz, rec[0], 40000);
      fm1_mod_get_stats(m, &st);
      CHECK(st.nonfinite == 0);
      if (st.nonfinite) fprintf(stderr, "%s: %u non-finite\n", fm1_mod_kinds[k]->id, st.nonfinite);
      fm1_mod_destroy(m);
      ++*fuzzed;
    }
    {
      const size_t bytes = fm1_mod_kinds[k]->instance_size(&kHost);
      CHECK(bytes <= (strcmp(fm1_mod_kinds[k]->id, "burst") ? 256u : 320u));
    }
  }
}

int main(void) {
  unsigned responses = 0, fills = 0, fuzzed = 0;
  calc();
  mix();
  slew();
  compare();
  logic();
  coin();
  divide();
  quantize();
  register_();
  register_data();
  function();
  bounce();
  burst();
  filter(&responses);
  every_kind(&fills, &fuzzed);
  printf("{\"checks\":%u,\"filter_responses\":%u,\"kinds_filled\":%u,\"kinds_fuzzed\":%u,"
         "\"failed\":%d}\n",
         checks, responses, fills, fuzzed, failed);
  return failed != 0;
}

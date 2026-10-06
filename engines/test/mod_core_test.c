/* mod_core_test.c -- fm1-mod-core-test: the modulation runtime (fm1_mod.h)
 * on its own, as docs/16 §2.7 asks:
 *
 *   - the planner: rebuilding is idempotent; any permutation of an
 *     equivalent slot table runs the same modules in the same order and
 *     delays the same cables; every cable that is not delayed runs after
 *     its source, and every delayed one is inside a loop and runs up the
 *     rack (fuzzed over random racks and tables);
 *   - a chain A -> B -> C -> D entered backwards in the rack arrives in the
 *     same tick as a direct cable; a self-cable and a two-module loop read
 *     exactly one tick late;
 *   - construction from memory filled with 0x00, 0xA5 and 0xFF gives the
 *     same ticks, bit for bit;
 *   - NaN and infinity in sources, bases, amounts and offsets never reach a
 *     write;
 *   - rules M1-M4 at the core: a zero amount writes nothing, NOLOCK and an
 *     ENUM without MOD are refused, an ENUM with MOD is rounded, a base set
 *     while routed returns base + offset, and an unrouted parameter goes
 *     back to its base;
 *   - gate cables: probability per rising edge from the slot's own seeded
 *     generator, the falling edge with it; edges keep their frame;
 *   - gate inputs never jump: an amount edit keeps a cable's state, a cable
 *     patched or pulled is an edge at frame 0, a reset envelope's ACT falls
 *     as an edge; a zero amount over a base set out of range writes nothing;
 *   - fm1_mod_size(), printed for tests/test_engines_mod_runtime.py to pin at 32 and 64
 *     bits.
 *
 * White-box where a public input cannot reach (a NaN source): it includes
 * the runtime's internal header. Prints one JSON line of counts; exits 1
 * after reporting the first failed check. Desktop test code. MIT licence. */
#include "mod_int.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static int failed;

#define CHECK(c)                                                          \
  do {                                                                    \
    if (!(c)) {                                                           \
      fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #c); \
      failed = 1;                                                         \
    }                                                                     \
  } while (0)

#define CONT FM1_PARAM_CONTINUOUS
static const char *const kPatches[] = { "a", "b", "c", "d", "e", "f", "g", "h" };
static const fm1_param_t kParams[] = {
  { "Model", FM1_PARAM_ENUM, 0.0f, 7.0f, 0.0f, kPatches, 0, 1, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Model" },
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 3, CONT, FM1_UNIT_NONE, "Timbre" },
  { "Tune", FM1_PARAM_FLOAT, -24.0f, 24.0f, 0.0f, NULL, 0, 5, CONT, FM1_UNIT_SEMI, "Tune" },
  { "Patch", FM1_PARAM_ENUM, 0.0f, 7.0f, 2.0f, kPatches, 0, 7, FM1_PARAM_LATCH | FM1_PARAM_MOD,
    FM1_UNIT_NONE, "Patch" },
  { "Lpg", FM1_PARAM_ENUM, 0.0f, 2.0f, 0.0f, kPatches, 1, 11, 0, FM1_UNIT_NONE, "Lpg" },
};
#undef CONT
static const fm1_engine_t kEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake", "Fake", "", kParams,
  (uint16_t)(sizeof(kParams) / sizeof(kParams[0])), 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, NULL, 0, NULL, 0, 0, NULL
};
enum { I_MODEL, I_TIMBRE, I_TUNE, I_PATCH, I_LPG };

/* An engine with per-note offsets (MG9): Timbre takes one, Drive is
 * engine-wide. The runtime only reads the table and the entry's presence. */
static void poly_note(void *self, uint8_t key, uint16_t index, float offset) {
  (void)self;
  (void)key;
  (void)index;
  (void)offset;
}
static const fm1_param_t kPolyParams[] = {
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 3, FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY,
    FM1_UNIT_NONE, "Timbre" },
  { "Drive", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Drive" },
};
static const fm1_engine_t kPolyEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake-poly", "Fake Poly", "", kPolyParams,
  (uint16_t)(sizeof(kPolyParams) / sizeof(kPolyParams[0])), 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, poly_note, 0, NULL, 0, 0, NULL
};

#define G FM1_MOD_TICK
#define MEM_BYTES (1u << 16)

static fm1_host_t kHost = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
static int K_LFO, K_ENV, K_CHN;

/* 16-aligned scratch for runtimes. */
static unsigned char *mem_block(int which) {
  static unsigned char raw[4][MEM_BYTES + 16];
  return raw[which] + (16u - ((uintptr_t)raw[which] & 15u)) % 16u;
}

static fm1_mod_t *make(int which, int fill, uint32_t seed) {
  unsigned char *mem = mem_block(which);
  fm1_mod_t *m;
  memset(mem, fill, fm1_mod_size());
  m = fm1_mod_create(mem, &kHost, seed);
  CHECK(m != NULL);
  fm1_mod_bind(m, FM1_MOD_SOUND, &kEngine);
  return m;
}

static fm1_mod_slot_t cable(unsigned src, unsigned unit, unsigned dst, float amount) {
  fm1_mod_slot_t s;
  memset(&s, 0, sizeof(s));
  s.src = (uint8_t)src;
  s.via = FM1_MOD_NONE;
  s.dst_unit = (uint8_t)unit;
  s.dst = (uint16_t)dst;
  s.flags = FM1_MOD_SLOT_ON;
  s.amount = fm1_mod_q14(amount);
  return s;
}

static unsigned out_of(unsigned pos, unsigned port) { return FM1_MOD_SRC_MODULE + 8u * pos + port; }

/* One block with its ticks; collects every write into w (up to cap). */
static uint32_t block(fm1_mod_t *m, uint32_t frames, fm1_mod_write_t *w, uint32_t cap) {
  uint32_t tf = fm1_mod_begin(m, frames, 0), n = 0;
  while (tf < frames) {
    const fm1_mod_write_t *x;
    const uint32_t k = fm1_mod_tick(m, tf, &x);
    uint32_t i;
    for (i = 0; i < k && n < cap; ++i) w[n++] = x[i];
    tf += G;
  }
  return n;
}

static uint32_t bits_of(float x) { return mod_bits(x); }

/* ---- the planner ---------------------------------------------------------- */

static uint32_t rnd_state = 12345u;
static uint32_t rnd(void) {
  rnd_state ^= rnd_state << 13;
  rnd_state ^= rnd_state >> 17;
  rnd_state ^= rnd_state << 5;
  return rnd_state;
}

/* A random cable: mostly module to module, some from system sources, some
 * to sinks and gates; some off, some invalid. */
static fm1_mod_slot_t random_slot(const fm1_mod_t *m) {
  fm1_mod_slot_t s;
  const unsigned a = rnd() % FM1_MOD_POSITIONS, b = rnd() % FM1_MOD_POSITIONS;
  const int kb = fm1_mod_kind_at(m, b);
  memset(&s, 0, sizeof(s));
  s.flags = (rnd() % 10u) ? FM1_MOD_SLOT_ON : 0u;
  s.src = (uint8_t)((rnd() % 8u) ? out_of(a, rnd() % 3u) : FM1_MOD_SRC_KEY);
  s.via = (uint8_t)((rnd() % 6u) ? FM1_MOD_NONE : out_of(rnd() % FM1_MOD_POSITIONS, 0));
  s.amount = (int16_t)((int)(rnd() % 32769u) - 16384);
  if (rnd() % 5u == 0) {
    s.dst_unit = FM1_MOD_SOUND;
    s.dst = 3;
  } else {
    s.dst_unit = (uint8_t)(FM1_MOD_MODULE + b);
    if (kb >= 0 && rnd() % 4u == 0) {
      s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
      s.dst = 0;
    } else {
      s.dst = (uint16_t)(1u + rnd() % 8u);
    }
  }
  if (rnd() % 3u == 0) s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_VOICE);   /* MG9 */
  return s;
}

static void random_rack(fm1_mod_t *m) {
  unsigned p;
  const int kinds[3] = { K_LFO, K_ENV, K_CHN };
  for (p = 0; p < FM1_MOD_POSITIONS; ++p) {
    fm1_mod_set_kind(m, p, rnd() % 6u ? kinds[rnd() % 3u] : -1);
  }
}

static int same_plan(const fm1_mod_plan_info_t *a, const fm1_mod_plan_info_t *b) {
  return a->n_order == b->n_order && !memcmp(a->order, b->order, sizeof(a->order)) &&
         !memcmp(a->comp, b->comp, sizeof(a->comp));
}

/* Every module once; order respects every cable that is not delayed;
 * delayed cables are inside one component and run up the rack. */
static int plan_valid(const fm1_mod_t *m, const fm1_mod_plan_info_t *p) {
  unsigned at[FM1_MOD_POSITIONS], comp[FM1_MOD_POSITIONS], i, pos, seen = 0;
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) at[pos] = comp[pos] = 99;
  for (i = 0; i < p->n_order; ++i) {
    if (at[p->order[i]] != 99) return 0;
    at[p->order[i]] = i;
    comp[p->order[i]] = p->comp[i];
    ++seen;
  }
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if ((fm1_mod_kind_at(m, pos) >= 0) != (at[pos] != 99)) return 0;
  }
  for (i = 0; i < FM1_MOD_SLOTS; ++i) {
    fm1_mod_slot_t s;
    unsigned b, k;
    fm1_mod_get_slot(m, i, &s);
    if (!((p->active >> i) & 1u) || s.dst_unit < FM1_MOD_MODULE) continue;
    b = s.dst_unit - FM1_MOD_MODULE;
    for (k = 0; k < 2u; ++k) {
      const unsigned src = k ? s.via : s.src;
      unsigned a;
      if (src == FM1_MOD_NONE || src < FM1_MOD_SRC_MODULE) continue;
      a = (src - FM1_MOD_SRC_MODULE) / 8u;
      if (comp[a] == comp[b] && a >= b) {
        if (!((p->delayed >> i) & 1u)) return 0;   /* must be delayed */
      } else if (at[a] >= at[b]) {
        return 0;                                  /* must run first */
      }
    }
  }
  return seen == p->n_order;
}

static void planner_fuzz(unsigned *n_plans, unsigned *n_loops) {
  unsigned trial, n_voice = 0;
  for (trial = 0; trial < 3000; ++trial) {
    fm1_mod_t *m = make(0, 0, trial);
    fm1_mod_t *q = make(1, 0, trial);
    fm1_mod_plan_info_t a, b, c;
    fm1_mod_slot_t table[FM1_MOD_SLOTS], s;
    unsigned perm[FM1_MOD_SLOTS], i, n = 1u + rnd() % FM1_MOD_SLOTS, pos;
    uint32_t want_delayed = 0, got_delayed = 0;
    if (trial & 1u) {                   /* per-note offsets: VOICE cables into the sound live */
      fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
      fm1_mod_bind(q, FM1_MOD_SOUND, &kPolyEngine);
    }
    random_rack(m);
    for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) fm1_mod_set_kind(q, pos, fm1_mod_kind_at(m, pos));
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      memset(&table[i], 0, sizeof(table[i]));
      table[i].via = FM1_MOD_NONE;
      if (i < n) table[i] = random_slot(m);
      fm1_mod_set_slot(m, i, &table[i]);
      perm[i] = i;
    }
    fm1_mod_get_plan(m, &a);
    CHECK(plan_valid(m, &a));
    /* Idempotent: the same tables plan the same. */
    m->dirty = 1;
    fm1_mod_get_plan(m, &c);
    CHECK(same_plan(&a, &c) && a.active == c.active && a.delayed == c.delayed &&
          a.refused == c.refused);
    /* Permuted: the same cables in other slots. */
    for (i = FM1_MOD_SLOTS - 1u; i > 0; --i) {
      const unsigned j = rnd() % (i + 1u), t = perm[i];
      perm[i] = perm[j];
      perm[j] = t;
    }
    for (i = 0; i < FM1_MOD_SLOTS; ++i) fm1_mod_set_slot(q, perm[i], &table[i]);
    fm1_mod_get_plan(q, &b);
    CHECK(same_plan(&a, &b));
    CHECK(plan_valid(q, &b));
    CHECK(a.poly == b.poly && a.voice_cap == b.voice_cap && a.n_vdest == b.n_vdest);
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      if ((a.delayed >> i) & 1u) want_delayed |= 1u << perm[i];
      if ((a.active >> i) & 1u) CHECK((b.active >> perm[i]) & 1u);
      CHECK(((a.voice >> i) & 1u) == ((b.voice >> perm[i]) & 1u));
    }
    if (a.voice) ++n_voice;
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_get_slot(q, i, &s);
      if ((b.delayed >> i) & 1u) got_delayed |= 1u << i;
    }
    CHECK(want_delayed == got_delayed);
    if (a.delayed) ++*n_loops;
    ++*n_plans;
    fm1_mod_destroy(m);
    fm1_mod_destroy(q);
  }
  CHECK(n_voice > 300);                 /* plans with live VOICE cables were among them */
}

/* ---- chains and loops -------------------------------------------------------- */

/* D <- C <- B <- A with A, an LFO, at the bottom of the rack: the planner
 * runs A, B, C, D, and Timbre moves in the very tick a direct cable moves
 * it. Chance in T&H with TRIG unpatched passes IN straight through. */
static void chain(unsigned *ticks) {
  fm1_mod_t *c = make(0, 0, 7), *d = make(1, 0, 7);
  fm1_mod_plan_info_t p;
  fm1_mod_slot_t s;
  fm1_mod_write_t wc[64], wd[64];
  unsigned pos, b;
  for (pos = 0; pos < 3u; ++pos) {
    fm1_mod_set_kind(c, pos, K_CHN);
    fm1_mod_set_param(c, pos, 0, 1.0f);   /* T&H */
  }
  fm1_mod_set_kind(c, 3, K_LFO);
  fm1_mod_set_param(c, 3, 0, 0.8f);
  fm1_mod_set_kind(d, 3, K_LFO);
  fm1_mod_set_param(d, 3, 0, 0.8f);
  s = cable(out_of(3, 0), FM1_MOD_MODULE + 2u, 6, 1.0f);   /* A -> B.In */
  fm1_mod_set_slot(c, 0, &s);
  s = cable(out_of(2, 0), FM1_MOD_MODULE + 1u, 6, 1.0f);   /* B -> C.In */
  fm1_mod_set_slot(c, 1, &s);
  s = cable(out_of(1, 0), FM1_MOD_MODULE + 0u, 6, 1.0f);   /* C -> D.In */
  fm1_mod_set_slot(c, 2, &s);
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 3, 0.5f);         /* D -> Timbre */
  fm1_mod_set_slot(c, 3, &s);
  s = cable(out_of(3, 0), FM1_MOD_SOUND, 3, 0.5f);         /* A -> Timbre, directly */
  fm1_mod_set_slot(d, 3, &s);
  fm1_mod_get_plan(c, &p);
  CHECK(p.n_order == 4 && p.order[0] == 3 && p.order[1] == 2 && p.order[2] == 1 && p.order[3] == 0);
  CHECK(p.delayed == 0 && p.active == 0xFu);
  for (b = 0; b < 200; ++b) {
    const uint32_t nc = block(c, 64, wc, 64), nd = block(d, 64, wd, 64);
    unsigned i;
    CHECK(nc == nd && nc == (b ? 2u : 1u));   /* the first tick is at frame 32 */
    for (i = 0; i < nc && i < nd; ++i) {
      CHECK(wc[i].index == I_TIMBRE && bits_of(wc[i].value) == bits_of(wd[i].value));
      ++*ticks;
    }
  }
  fm1_mod_destroy(c);
  fm1_mod_destroy(d);
}

/* A self-cable reads the previous tick: Chance (T&H, unpatched) with its
 * HELD into its own IN plus an offset climbs by the offset every tick. And
 * a two-module loop: the cable running up the rack is the delayed one. */
static void feedback(unsigned *ticks) {
  fm1_mod_t *m = make(0, 0, 3);
  fm1_mod_plan_info_t p;
  fm1_mod_slot_t s;
  fm1_mod_write_t w[8];
  float want = 0.0f;
  const float ofs = (float)fm1_mod_q14(0.1f) / 16384.0f;
  unsigned k;
  fm1_mod_set_kind(m, 0, K_CHN);
  fm1_mod_set_param(m, 0, 0, 1.0f);
  s = cable(out_of(0, 0), FM1_MOD_MODULE + 0u, 6, 1.0f);
  s.offset = fm1_mod_q14(0.1f);
  fm1_mod_set_slot(m, 0, &s);
  fm1_mod_get_plan(m, &p);
  CHECK(p.delayed == 1u);
  block(m, G, w, 8);                    /* frames 0-31: the first tick is at 32 */
  for (k = 1; k <= 12; ++k) {
    block(m, G, w, 8);
    want = want + ofs;
    if (want > 1.0f) want = 1.0f;
    CHECK(bits_of(fm1_mod_out(m, 0, 0)) == bits_of(want));
    ++*ticks;
  }
  fm1_mod_destroy(m);

  m = make(0, 0, 3);
  fm1_mod_set_kind(m, 0, K_LFO);
  fm1_mod_set_kind(m, 1, K_CHN);
  s = cable(out_of(0, 0), FM1_MOD_MODULE + 1u, 6, 1.0f);   /* LFO1 -> CHN2.In: runs down */
  fm1_mod_set_slot(m, 0, &s);
  s = cable(out_of(1, 0), FM1_MOD_MODULE + 0u, 1, 0.2f);   /* CHN2 -> LFO1.Rate: runs up */
  fm1_mod_set_slot(m, 1, &s);
  fm1_mod_get_plan(m, &p);
  CHECK(p.delayed == 2u && p.n_order == 2 && p.order[0] == 0 && p.comp[0] == p.comp[1]);
  /* Moving CHN to the top of the rack moves the delay to the other cable. */
  fm1_mod_move(m, 1, 0);
  fm1_mod_get_plan(m, &p);
  CHECK(p.delayed == 1u && p.order[0] == 0 && fm1_mod_kind_at(m, 0) == K_CHN);
  fm1_mod_destroy(m);
}

/* ---- fills, NaN, M1-M4 --------------------------------------------------------- */

static void scenario(fm1_mod_t *m) {
  fm1_mod_slot_t s;
  fm1_mod_default_rack(m);
  fm1_mod_set_param(m, 4, 0, 2.0f);   /* Chance: Smooth */
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 3, 0.3f);
  fm1_mod_set_slot(m, 0, &s);
  s = cable(out_of(2, 0), FM1_MOD_SOUND, 5, 0.5f);
  fm1_mod_set_slot(m, 1, &s);
  s = cable(out_of(4, 1), FM1_MOD_MODULE + 1u, 1, 0.4f);
  fm1_mod_set_slot(m, 2, &s);
  s = cable(out_of(1, 1), FM1_MOD_MODULE + 3u, 0, 0.5f);   /* LFO2.WRAP -> ENV4.GATE, 50 % */
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
  fm1_mod_set_slot(m, 3, &s);
  s = cable(out_of(3, 0), FM1_MOD_HOST, FM1_MOD_HOST_AMP_UID, 0.25f);
  fm1_mod_set_slot(m, 4, &s);
  s = cable(FM1_MOD_SRC_RAND, FM1_MOD_MODULE + 0u, 3, 0.5f);
  s.via = FM1_MOD_SRC_VEL;
  fm1_mod_set_slot(m, 5, &s);
}

static void any_fill(unsigned *ticks) {
  static fm1_mod_write_t w[3][4096];
  uint32_t n[3];
  int f;
  const int fills[3] = { 0x00, 0xA5, 0xFF };
  for (f = 0; f < 3; ++f) {
    fm1_mod_t *m = make(f, fills[f], 99);
    uint32_t b, k = 0;
    scenario(m);
    for (b = 0; b < 400; ++b) {
      if (b % 50 == 3) fm1_mod_live_note(m, (uint8_t)(48 + b % 24), (uint8_t)(40 + b % 80));
      if (b % 50 == 30) fm1_mod_live_note(m, (uint8_t)(48 + (b - 27) % 24), 0);
      k += block(m, 64, w[f] + k, 4096 - k);
    }
    n[f] = k;
    fm1_mod_destroy(m);
  }
  CHECK(n[0] > 100 && n[0] == n[1] && n[1] == n[2]);
  CHECK(!memcmp(w[0], w[1], n[0] * sizeof(w[0][0])) && !memcmp(w[1], w[2], n[0] * sizeof(w[0][0])));
  *ticks += n[0];
}

/* ---- voices (MG9) ---------------------------------------------------------------- */

/* One block with its ticks, every tick's writes and per-voice offsets into w. */
static uint32_t block_v(fm1_mod_t *m, uint32_t frames, fm1_mod_write_t *w, uint32_t cap) {
  uint32_t tf = fm1_mod_begin(m, frames, 0), n = 0;
  while (tf < frames) {
    const fm1_mod_write_t *x;
    const uint32_t k = fm1_mod_tick(m, tf, &x);
    uint32_t i;
    for (i = 0; i < k && n < cap; ++i) w[n++] = x[i];
    n += fm1_mod_voice_writes(m, w + n, cap - n);
    tf += G;
  }
  return n;
}

static fm1_mod_slot_t voice_cable(unsigned src, unsigned unit, unsigned dst, float amount) {
  fm1_mod_slot_t s = cable(src, unit, dst, amount);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_VOICE);
  return s;
}

/* ENV3 per voice into Timbre, RAND per voice into the note's pitch, VEL per
 * voice into ENV3's attack, and one refused into an engine-wide parameter;
 * notes on two keys at a time, one re-struck while held, from any fill of
 * memory: the same writes, per key, every time. */
static void voice_scenario(fm1_mod_t *m, fm1_mod_write_t *w, uint32_t cap, uint32_t *n) {
  fm1_mod_slot_t s;
  uint32_t b;
  fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
  fm1_mod_default_rack(m);
  fm1_mod_set_param(m, 2, 0, 0.3f);
  fm1_mod_set_param(m, 2, 3, 0.05f);                        /* a short release: voices end */
  s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 3, 0.6f);
  fm1_mod_set_slot(m, 0, &s);
  s = voice_cable(FM1_MOD_SRC_RAND, FM1_MOD_HOST, FM1_MOD_HOST_PITCH_UID, 0.1f);
  fm1_mod_set_slot(m, 1, &s);
  s = voice_cable(FM1_MOD_SRC_VEL, FM1_MOD_MODULE + 2u, 1, -0.3f);
  fm1_mod_set_slot(m, 2, &s);
  s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 4, 0.5f);       /* Drive: mono, refused */
  fm1_mod_set_slot(m, 3, &s);
  *n = 0;
  for (b = 0; b < 400; ++b) {
    const uint32_t frames = 64;
    if (b % 40 == 3) fm1_mod_live_note(m, (uint8_t)(48 + b % 12), (uint8_t)(40 + b % 80));
    if (b % 40 == 9) fm1_mod_live_note(m, (uint8_t)(60 + b % 12), 100);
    if (b % 40 == 15) fm1_mod_live_note(m, (uint8_t)(48 + (b - 12) % 12), 90);   /* re-struck */
    if (b % 40 == 30) {
      fm1_mod_live_note(m, (uint8_t)(48 + (b - 27) % 12), 0);
      fm1_mod_live_note(m, (uint8_t)(60 + (b - 21) % 12), 0);
    }
    *n += block_v(m, frames, w + *n, cap - *n);
  }
}

static void voices(unsigned *checked) {
  static fm1_mod_write_t w[3][16384];
  uint32_t n[3];
  const int fills[3] = { 0x00, 0x5A, 0xFF };
  fm1_mod_plan_info_t p;
  fm1_mod_stats_t st;
  unsigned keyed = 0, i;
  int f;
  for (f = 0; f < 3; ++f) {
    fm1_mod_t *m = make(f, fills[f], 21);
    voice_scenario(m, w[f], 16384, &n[f]);
    fm1_mod_get_plan(m, &p);
    fm1_mod_get_stats(m, &st);
    CHECK(p.refused == 8u && p.voice == 7u && p.poly == 4u && p.voice_cap == FM1_MOD_VOICES);
    CHECK(st.voice_starts > 10 && st.voice_ends > 5 && st.nonfinite == 0);
    fm1_mod_destroy(m);
  }
  CHECK(n[0] > 1000 && n[0] == n[1] && n[1] == n[2]);
  CHECK(!memcmp(w[0], w[1], n[0] * sizeof(w[0][0])) && !memcmp(w[1], w[2], n[0] * sizeof(w[0][0])));
  for (i = 0; i < n[0]; ++i) {
    const fm1_mod_write_t *x = &w[0][i];
    if (x->key == FM1_MOD_NONE) continue;
    ++keyed;
    CHECK(x->unit == FM1_MOD_SOUND && (x->index == I_TIMBRE - 1u || x->index == FM1_PARAM_NOTE_PITCH));
    CHECK(mod_finite(x->value) && x->value > -9.7f && x->value < 9.7f);   /* 0.1 x 96 semitones */
  }
  CHECK(keyed == n[0]);                                      /* no global write at all */
  *checked += keyed;

  /* Eight Chances, each read per voice: the arena holds a few voices, and
   * notes past them steal the oldest. */
  {
    fm1_mod_t *m = make(0, 0, 5);
    fm1_mod_write_t x[64];
    unsigned pos, k;
    fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
    for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      fm1_mod_slot_t s = voice_cable(out_of(pos, 0), FM1_MOD_SOUND, 3, 0.05f);
      fm1_mod_set_kind(m, pos, K_CHN);
      fm1_mod_set_slot(m, pos, &s);
    }
    fm1_mod_get_plan(m, &p);
    CHECK(p.poly == 0xFFu && p.voice_cap >= 1u && p.voice_cap < FM1_MOD_VOICES && p.voice_bytes > 0);
    CHECK((uint32_t)p.voice_cap * p.voice_bytes <= FM1_MOD_ARENA);
    for (k = 0; k < (unsigned)p.voice_cap + 2u; ++k) {
      fm1_mod_live_note(m, (uint8_t)(40 + k), 100);
      block_v(m, 64, x, 64);
    }
    fm1_mod_get_stats(m, &st);
    CHECK(st.voice_starts == (uint32_t)p.voice_cap + 2u && st.voice_steals == 2u);
    CHECK(fm1_mod_voice_count(m) == p.voice_cap);
    fm1_mod_destroy(m);
  }

  /* An amount edit rebuilds the plan but keeps every voice's instance: its
   * envelope runs on; a kind changed elsewhere makes them again. */
  {
    fm1_mod_t *m = make(0, 0, 9);
    fm1_mod_write_t x[256];
    fm1_mod_slot_t s;
    float before, after;
    unsigned b;
    fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
    fm1_mod_default_rack(m);
    fm1_mod_set_param(m, 2, 0, 0.6f);                         /* a slow attack */
    s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 3, 0.5f);
    fm1_mod_set_slot(m, 0, &s);
    fm1_mod_live_note(m, 60, 100);
    for (b = 0; b < 20; ++b) block_v(m, 64, x, 256);
    before = fm1_mod_voice_out(m, 0, 2, 0);
    s.amount = fm1_mod_q14(0.7f);
    fm1_mod_set_slot(m, 0, &s);
    block_v(m, 64, x, 256);
    after = fm1_mod_voice_out(m, 0, 2, 0);
    CHECK(before > 0.05f && after > before);                 /* still climbing, not restarted */
    fm1_mod_set_kind(m, 6, K_LFO);
    block_v(m, 64, x, 256);
    CHECK(fm1_mod_voice_out(m, 0, 2, 0) < before);           /* made again */
    fm1_mod_destroy(m);
  }
}

/* ---- voices, hostile (the MG9 review) --------------------------------------------- */

/* A note event at an absolute frame on a sound unit (velocity 0: off). */
typedef struct hev {
  uint32_t frame;
  uint8_t sound, key, vel, reserved;
} hev_t;
/* A write with the absolute frame it went out at. */
typedef struct fwr {
  uint32_t frame;
  fm1_mod_write_t w;
} fwr_t;

static void push_w(fwr_t *out, uint32_t *n, uint32_t cap, uint32_t frame, const fm1_mod_write_t *w,
                   uint32_t k) {
  uint32_t i;
  for (i = 0; i < k && *n < cap; ++i) {
    out[*n].frame = frame;
    out[*n].w = w[i];
    ++*n;
  }
}

/* The bridge's order (fm1_seq_host.h, docs/16 M6) at any block size: at
 * one frame note-offs before the tick, the tick and its per-voice offsets,
 * then note-ons, each followed by fm1_mod_voice_start. edit(m, frame) runs
 * before the block that starts at `frame` (edits come at frames every block
 * size starts a block at). */
static uint32_t bridge_run(fm1_mod_t *m, uint32_t bs, uint32_t total, const hev_t *ev, unsigned nev,
                           void (*edit)(fm1_mod_t *, uint32_t), fwr_t *out, uint32_t cap) {
  uint32_t blk, n = 0;
  unsigned e = 0;
  for (blk = 0; blk < total; blk += bs) {
    uint32_t tf;
    if (edit) edit(m, blk);
    tf = fm1_mod_begin(m, bs, 0);
    for (;;) {
      const int has = e < nev && ev[e].frame < blk + bs;
      const uint32_t f = has ? ev[e].frame - blk : bs;
      while (tf < bs && (tf < f || (has && tf == f && ev[e].vel))) {
        const fm1_mod_write_t *x;
        fm1_mod_write_t vw[FM1_MOD_VOICES * FM1_MOD_VDESTS];
        const uint32_t k = fm1_mod_tick(m, tf, &x);
        push_w(out, &n, cap, blk + tf, x, k);
        push_w(out, &n, cap, blk + tf, vw, fm1_mod_voice_writes(m, vw, FM1_MOD_VOICES * FM1_MOD_VDESTS));
        tf += G;
      }
      if (!has) break;
      fm1_mod_sound_note(m, f, ev[e].sound, ev[e].key, ev[e].vel);
      if (ev[e].vel) {
        fm1_mod_write_t vw[FM1_MOD_VDESTS + 1u];
        push_w(out, &n, cap, blk + f, vw,
               fm1_mod_voice_start(m, ev[e].sound, ev[e].key, vw, FM1_MOD_VDESTS + 1u));
      }
      ++e;
    }
  }
  return n;
}

#define HB 448u                         /* a block start at blocks of 1, 7 and 64 */

static fm1_mod_slot_t gate_voice_cable(unsigned src, unsigned pos, unsigned gate, float amount) {
  fm1_mod_slot_t s = cable(src, FM1_MOD_MODULE + pos, gate, amount);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST | FM1_MOD_SLOT_VOICE);
  return s;
}

/* Edits while notes sound: an amount, the current sound, a kind changed
 * elsewhere, a per-voice cable removed, three more modules per voice (the
 * arena holds fewer voices), a move, and a sound unit whose engine takes
 * no per-note offsets. */
static void hostile_edit(fm1_mod_t *m, uint32_t at) {
  fm1_mod_slot_t s;
  unsigned pos;
  switch (at / HB) {
    case 15:
      if (at % HB) break;
      fm1_mod_get_slot(m, 0, &s);
      s.amount = fm1_mod_q14(0.8f);
      fm1_mod_set_slot(m, 0, &s);
      break;
    case 30:
      if (!(at % HB)) fm1_mod_set_current(m, 1);
      break;
    case 45:
      if (!(at % HB)) fm1_mod_set_kind(m, 6, K_LFO);
      break;
    case 60:
      if (at % HB) break;
      memset(&s, 0, sizeof(s));
      s.via = FM1_MOD_NONE;
      fm1_mod_set_slot(m, 1, &s);
      break;
    case 75:
      if (at % HB) break;
      for (pos = 5; pos < 8; ++pos) {
        fm1_mod_set_kind(m, pos, K_CHN);
        s = voice_cable(out_of(pos, 0), FM1_MOD_SOUND, 3, 0.02f);
        fm1_mod_set_slot(m, 20 + pos, &s);
      }
      break;
    case 90:
      if (!(at % HB)) fm1_mod_move(m, 2, 6);
      break;
    case 100:
      if (!(at % HB)) fm1_mod_bind(m, fm1_mod_sound_unit(1), &kEngine);
      break;
    default: break;
  }
}

static uint32_t lcg(uint32_t *s) {
  *s = *s * 1664525u + 1013904223u;
  return *s >> 8;
}

/* Notes on three sound units, more at once than there are voices (steals,
 * one sound's voices taken by another's notes), re-struck keys, notes at
 * tick frames and an off and an on of one key at one frame; ordered by
 * frame, ties in the order made. */
static unsigned hostile_notes(hev_t *ev, unsigned cap, uint32_t total) {
  unsigned n = 0, i, j;
  uint32_t r = 77u;
  while (n + 2u <= cap) {
    const uint32_t len = 64u + lcg(&r) % 9000u;
    uint32_t on = lcg(&r) % (total - 64u);
    hev_t a;
    if (lcg(&r) % 4u == 0) on -= on % G;                     /* at a tick's frame */
    a.frame = on;
    a.sound = (uint8_t)(lcg(&r) % 3u);
    a.key = (uint8_t)(40u + lcg(&r) % 24u);
    a.vel = (uint8_t)(1u + lcg(&r) % 127u);
    a.reserved = 0;
    ev[n++] = a;
    a.frame = on + len < total ? on + len : total - 1u;
    a.vel = 0;
    ev[n++] = a;
  }
  /* The same key off and on at one frame, twice. */
  ev[n - 4].frame = ev[n - 2].frame = 20u * HB + 5u * G;
  ev[n - 4].sound = ev[n - 2].sound = 0;
  ev[n - 4].key = ev[n - 2].key = 50;
  ev[n - 4].vel = 0;
  ev[n - 2].vel = 99;
  for (i = 1; i < n; ++i) {                                  /* stable: insertion */
    const hev_t x = ev[i];
    for (j = i; j > 0 && ev[j - 1].frame > x.frame; --j) ev[j] = ev[j - 1];
    ev[j] = x;
  }
  return n;
}

static void hostile_setup(fm1_mod_t *m) {
  fm1_mod_slot_t s;
  unsigned k;
  for (k = 0; k < 3u; ++k) fm1_mod_bind(m, fm1_mod_sound_unit(k), &kPolyEngine);
  fm1_mod_default_rack(m);
  fm1_mod_set_param(m, 2, 3, 0.05f);                          /* a short release */
  s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 3, 0.6f);
  fm1_mod_set_slot(m, 0, &s);
  s = voice_cable(FM1_MOD_SRC_RAND, FM1_MOD_HOST, FM1_MOD_HOST_PITCH_UID, 0.1f);
  fm1_mod_set_slot(m, 1, &s);
  s = voice_cable(FM1_MOD_SRC_VEL, FM1_MOD_MODULE + 2u, 1, -0.3f);
  fm1_mod_set_slot(m, 2, &s);
  s = voice_cable(out_of(0, 0), fm1_mod_sound_unit(1), 3, 0.4f);
  fm1_mod_set_slot(m, 3, &s);
  s = voice_cable(out_of(4, 0), FM1_MOD_HOST, FM1_MOD_HOST_PITCH_CUR_UID, 0.05f);
  fm1_mod_set_slot(m, 4, &s);
  s = cable(out_of(1, 0), FM1_MOD_HOST, FM1_MOD_HOST_PITCH2_UID, 0.3f);
  fm1_mod_set_slot(m, 5, &s);
  s = gate_voice_cable(FM1_MOD_SRC_TRIG, 0, 0, 0.7f);       /* a probability per note */
  fm1_mod_set_slot(m, 6, &s);
  s = voice_cable(FM1_MOD_SRC_S_VEL + 0u, FM1_MOD_SOUND, 3, 0.2f);
  fm1_mod_set_slot(m, 7, &s);
  s = voice_cable(FM1_MOD_SRC_S_KEY + 1u, fm1_mod_sound_unit(1), 3, 0.1f);
  fm1_mod_set_slot(m, 8, &s);
}

static void voices_hostile(unsigned *checked) {
  enum { NEV = 420, CAP = 200000 };
  static hev_t ev[NEV];
  static fwr_t w[4][CAP];
  const uint32_t total = 110u * HB;
  const uint32_t bs[4] = { 64, 1, 7, 64 };
  const int fills[4] = { 0x00, 0xA5, 0xFF, 0x5A };
  uint32_t n[4], i;
  unsigned nev, r;
  fm1_mod_stats_t st;
  nev = hostile_notes(ev, NEV, total);
  for (r = 0; r < 4u; ++r) {
    fm1_mod_t *m = make(r % 2u, fills[r], 31);
    hostile_setup(m);
    n[r] = bridge_run(m, bs[r], total, ev, nev, hostile_edit, w[r], CAP);
    fm1_mod_get_stats(m, &st);
    CHECK(n[r] < CAP && st.voice_steals > 5 && st.voice_starts > 100 && st.nonfinite == 0);
    CHECK(fm1_mod_voice_count(m) <= FM1_MOD_VOICES);
    fm1_mod_destroy(m);
  }
  /* The same writes at the same frames whatever the block and the memory. */
  for (r = 1; r < 4u; ++r) {
    CHECK(n[r] == n[0]);
    CHECK(n[r] == n[0] && !memcmp(w[r], w[0], n[0] * sizeof(w[0][0])));
  }
  for (i = 0; i < n[0]; ++i) {
    const fm1_mod_write_t *x = &w[0][i].w;
    if (x->key == FM1_MOD_NONE) continue;
    CHECK(x->key < 128u && fm1_mod_unit_sound(x->unit) >= 0 && fm1_mod_unit_sound(x->unit) < 3);
    CHECK(x->index == 0u || x->index == FM1_PARAM_NOTE_PITCH);   /* Timbre or the pitch: nothing mono */
    CHECK(mod_finite(x->value));
    ++*checked;
  }
}

/* The arena holds fewer voices than are sounding (a rack edit while twelve
 * notes are held): the voices past it stop, and every offset their notes
 * hold goes back to 0, so no note keeps a value nothing moves any more. */
static void voices_shrink(unsigned *checked) {
  fm1_mod_t *m = make(0, 0, 3);
  fm1_mod_write_t x[512];
  fm1_mod_plan_info_t p;
  fm1_mod_slot_t s;
  float last[128];
  int dropped[128];
  unsigned k, b, pos, ndrop = 0;
  uint32_t i, nx;
  fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
  fm1_mod_default_rack(m);
  s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 3, 0.6f);
  fm1_mod_set_slot(m, 0, &s);
  for (k = 0; k < 128u; ++k) last[k] = 0.0f, dropped[k] = 0;
  for (k = 0; k < FM1_MOD_VOICES; ++k) {
    fm1_mod_live_note(m, (uint8_t)(60 + k), 100);
    nx = fm1_mod_voice_start(m, 0, (uint8_t)(60 + k), x, 16);
    nx += block_v(m, 64, x + nx, 512 - nx);
    for (i = 0; i < nx; ++i) if (x[i].key < 128u) last[x[i].key] = x[i].value;
  }
  for (b = 0; b < 30; ++b) {
    nx = block_v(m, 64, x, 512);
    for (i = 0; i < nx; ++i) if (x[i].key < 128u) last[x[i].key] = x[i].value;
  }
  CHECK(fm1_mod_voice_count(m) == FM1_MOD_VOICES);
  for (k = 0; k < FM1_MOD_VOICES; ++k) CHECK(last[60 + k] > 0.1f);
  /* Every other position per voice too: fewer voices fit. */
  for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
    if (pos != 2u) {
      if (pos >= 5u) fm1_mod_set_kind(m, pos, K_CHN);
      s = voice_cable(out_of(pos, 0), FM1_MOD_SOUND, 3, 0.01f);
      fm1_mod_set_slot(m, 10 + pos, &s);
    }
  }
  fm1_mod_get_plan(m, &p);
  CHECK(p.voice_cap >= 1u && p.voice_cap < FM1_MOD_VOICES);
  for (b = 0; b < 4; ++b) {
    nx = block_v(m, 64, x, 512);
    for (i = 0; i < nx; ++i) {
      if (x[i].key >= 128u) continue;
      last[x[i].key] = x[i].value;
    }
  }
  CHECK(fm1_mod_voice_count(m) == p.voice_cap);
  for (k = 0; k < FM1_MOD_VOICES; ++k) {
    fm1_mod_voice_info_t vi;
    unsigned v, kept = 0;
    for (v = 0; v < FM1_MOD_VOICES; ++v) kept |= fm1_mod_voice(m, v, &vi) && vi.key == 60 + k;
    if (!kept) dropped[60 + k] = 1, ++ndrop;
  }
  CHECK(ndrop == FM1_MOD_VOICES - p.voice_cap);
  for (k = 0; k < 128u; ++k) {
    if (!dropped[k]) continue;
    CHECK(last[k] == 0.0f);                                  /* back to 0, not held where it was */
    ++*checked;
  }
  fm1_mod_destroy(m);
}

/* One sound's note sources in a voice of that sound are its note's own:
 * S1VEL per voice gives each note of a chord on sound unit 1 its own
 * velocity, as VEL does; another sound's (S2VEL) is that sound's last note. */
static void voices_sound_sources(unsigned *checked) {
  fm1_mod_t *m = make(0, 0, 4);
  fm1_mod_write_t x[256];
  fm1_mod_slot_t s;
  float got[128];
  const uint8_t vel[3] = { 30, 80, 125 };
  unsigned k, b;
  uint32_t i, nx;
  fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
  fm1_mod_bind(m, fm1_mod_sound_unit(1), &kPolyEngine);
  fm1_mod_default_rack(m);
  s = voice_cable(FM1_MOD_SRC_S_VEL + 0u, FM1_MOD_SOUND, 3, 1.0f);
  fm1_mod_set_slot(m, 0, &s);
  s = voice_cable(FM1_MOD_SRC_S_VEL + 0u, fm1_mod_sound_unit(1), 3, 1.0f);
  fm1_mod_set_slot(m, 1, &s);
  for (k = 0; k < 128u; ++k) got[k] = -1.0f;
  for (k = 0; k < 3u; ++k) {
    fm1_mod_live_note(m, (uint8_t)(60 + k), vel[k]);
    nx = fm1_mod_voice_start(m, 0, (uint8_t)(60 + k), x, 16);
    for (i = 0; i < nx; ++i) if (x[i].unit == FM1_MOD_SOUND) got[x[i].key] = x[i].value;
    nx = block_v(m, 64, x, 256);
    for (i = 0; i < nx; ++i) if (x[i].unit == FM1_MOD_SOUND && x[i].key < 128u) got[x[i].key] = x[i].value;
  }
  fm1_mod_live_sound_note(m, 1, 40, 50);                     /* sound unit 2: S1VEL is sound 1's last */
  nx = fm1_mod_voice_start(m, 1, 40, x, 16);
  for (b = 0; b < 4; ++b) nx += block_v(m, 64, x + nx, 256 - nx);
  for (i = 0; i < nx; ++i) {
    if (x[i].key == 40 && x[i].unit == fm1_mod_sound_unit(1)) got[40] = x[i].value;
    else if (x[i].unit == FM1_MOD_SOUND && x[i].key < 128u) got[x[i].key] = x[i].value;
  }
  for (k = 0; k < 3u; ++k) {
    CHECK(fabsf(got[60 + k] - (float)vel[k] / 127.0f) < 1e-6f);
    ++*checked;
  }
  CHECK(fabsf(got[40] - 125.0f / 127.0f) < 1e-6f);
  fm1_mod_destroy(m);
}

/* PITCH_CUR per voice follows the current sound: its voices' pitches go
 * back to 0 when another sound becomes current, and that sound's notes
 * take it from then on. */
static void voices_current(unsigned *checked) {
  fm1_mod_t *m = make(0, 0, 6);
  fm1_mod_write_t x[256];
  fm1_mod_slot_t s;
  float p60 = 0.0f, p64 = 0.0f;
  int saw64 = 0;
  unsigned b;
  uint32_t i, nx = 0;
  fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
  fm1_mod_bind(m, fm1_mod_sound_unit(1), &kPolyEngine);
  fm1_mod_default_rack(m);
  s = voice_cable(FM1_MOD_SRC_RAND, FM1_MOD_HOST, FM1_MOD_HOST_PITCH_CUR_UID, 0.2f);
  fm1_mod_set_slot(m, 0, &s);
  fm1_mod_live_sound_note(m, 0, 60, 100);
  nx = fm1_mod_voice_start(m, 0, 60, x, 16);
  for (b = 0; b < 4; ++b) nx += block_v(m, 64, x + nx, 256 - nx);
  for (i = 0; i < nx; ++i) if (x[i].key == 60 && x[i].index == FM1_PARAM_NOTE_PITCH) p60 = x[i].value;
  CHECK(p60 != 0.0f);
  fm1_mod_set_current(m, 1);
  fm1_mod_live_sound_note(m, 1, 64, 100);
  nx = fm1_mod_voice_start(m, 1, 64, x, 16);
  for (b = 0; b < 4; ++b) nx += block_v(m, 64, x + nx, 256 - nx);
  for (i = 0; i < nx; ++i) {
    if (x[i].index != FM1_PARAM_NOTE_PITCH) continue;
    if (x[i].key == 60) {
      CHECK(x[i].unit == FM1_MOD_SOUND);
      p60 = x[i].value;
    }
    if (x[i].key == 64) {
      CHECK(x[i].unit == fm1_mod_sound_unit(1));
      p64 = x[i].value;
      saw64 = 1;
    }
  }
  CHECK(p60 == 0.0f && saw64 && p64 != 0.0f);
  *checked += 2;
  fm1_mod_destroy(m);
}

/* A per-voice gate cable rewired starts low in every voice, as a global
 * one does (fm1_mod_set_slot): a voice's envelope it held open closes. Its
 * source is KEY, then ENV4's ACT per voice. */
static void voices_gate_rewire(unsigned *checked) {
  fm1_mod_write_t x[256];
  fm1_mod_slot_t s;
  unsigned b, v, round;
  for (round = 0; round < 2u; ++round) {
    fm1_mod_t *m = make(0, 0, 8);
    float held = 0.0f, after = 1.0f;
    fm1_mod_voice_info_t vi;
    fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
    fm1_mod_default_rack(m);
    fm1_mod_set_param(m, 2, 3, 0.0f);                       /* the shortest release */
    s = gate_voice_cable(round == 0 ? FM1_MOD_SRC_KEY : out_of(3, 2), 2, 0, 1.0f);
    fm1_mod_set_slot(m, 0, &s);
    s = voice_cable(out_of(2, 0), FM1_MOD_SOUND, 3, 1.0f);
    fm1_mod_set_slot(m, 1, &s);
    s = voice_cable(out_of(3, 0), FM1_MOD_SOUND, 3, 0.01f);  /* ENV4 per voice too */
    fm1_mod_set_slot(m, 2, &s);
    fm1_mod_live_note(m, 60, 100);
    for (b = 0; b < 40; ++b) block_v(m, 64, x, 256);
    for (v = 0; v < FM1_MOD_VOICES; ++v) {
      if (fm1_mod_voice(m, v, &vi) && vi.key == 60) held = fm1_mod_voice_out(m, v, 2, 0);
    }
    CHECK(held > 0.3f);
    s = gate_voice_cable(FM1_MOD_SRC_S_KEY + 1u, 2, 0, 1.0f);   /* a source that stays low */
    fm1_mod_set_slot(m, 0, &s);
    for (b = 0; b < 40; ++b) block_v(m, 64, x, 256);
    for (v = 0; v < FM1_MOD_VOICES; ++v) {
      if (fm1_mod_voice(m, v, &vi) && vi.key == 60) after = fm1_mod_voice_out(m, v, 2, 0);
    }
    CHECK(after < 0.01f);                                   /* released: the cable fell */
    ++*checked;
    fm1_mod_destroy(m);
  }
}

static void nan_survived(unsigned *checked) {
  fm1_mod_t *m = make(0, 0, 5);
  fm1_mod_slot_t s;
  fm1_mod_write_t w[64];
  fm1_mod_stats_t st;
  unsigned b, i;
  const float bad[4] = { NAN, INFINITY, -INFINITY, 1e30f };
  scenario(m);
  CHECK(fm1_mod_q14(NAN) == 0 && fm1_mod_q14(INFINITY) == 16384 && fm1_mod_q14(-INFINITY) == -16384);
  s = cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 3, 1.0f);
  s.amount = 32767;                                     /* beyond 1.0: clamped */
  s.offset = -32768;
  fm1_mod_set_slot(m, 6, &s);
  s = cable(out_of(0, 0), FM1_MOD_MODULE + 0u, 1, 0.5f);   /* a self-cable: reads the old buffer */
  fm1_mod_set_slot(m, 7, &s);
  s = cable(FM1_MOD_SRC_NOTE, FM1_MOD_SOUND, 5, 1.0f);
  fm1_mod_set_slot(m, 8, &s);
  for (b = 0; b < 40; ++b) {
    const float x = bad[b % 4u];
    uint32_t n;
    m->pend_cv[0][FM1_MOD_SRC_VEL] = x;                 /* a source gone bad */
    m->cv_has[0] |= 1ull << FM1_MOD_SRC_VEL;
    m->sys_cv[FM1_MOD_SRC_NOTE] = x;
    m->out[m->cur][0][0] = x;                           /* a module output gone bad */
    fm1_mod_set_param(m, 1, 0, x);                      /* a base */
    fm1_mod_set_base(m, FM1_MOD_SOUND, I_TUNE, x);
    fm1_mod_set_base(m, FM1_MOD_HOST, FM1_MOD_HOST_PITCH, x);
    n = block(m, 64, w, 64);
    for (i = 0; i < n; ++i) {
      CHECK(mod_finite(w[i].value));
      ++*checked;
    }
    for (i = 0; i < FM1_MOD_POSITIONS * 3u; ++i) {
      CHECK(mod_finite(fm1_mod_out(m, i / 3u, i % 3u)));
      CHECK(mod_finite(fm1_mod_param(m, i / 3u, i % 3u)));
    }
  }
  fm1_mod_get_stats(m, &st);
  CHECK(st.nonfinite > 0);
  fm1_mod_destroy(m);
}

static void rules(void) {
  fm1_mod_t *m = make(0, 0, 1);
  fm1_mod_slot_t s;
  fm1_mod_write_t w[64];
  fm1_mod_plan_info_t p;
  uint32_t n, b;
  float v;
  fm1_mod_set_kind(m, 0, K_LFO);
  fm1_mod_set_param(m, 0, 1, 4.0f);        /* square: +-1 */
  fm1_mod_set_param(m, 0, 0, 0.9f);
  /* M1: a zero amount is no write at all. */
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 3, 0.0f);
  fm1_mod_set_slot(m, 0, &s);
  for (b = 0, n = 0; b < 50; ++b) n += block(m, 64, w, 64);
  CHECK(n == 0);
  /* M4: NOLOCK refused; an ENUM without MOD refused; an unknown uid refused. */
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 1, 1.0f);
  fm1_mod_set_slot(m, 1, &s);
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 11, 1.0f);
  fm1_mod_set_slot(m, 2, &s);
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 99, 1.0f);
  fm1_mod_set_slot(m, 3, &s);
  s = cable(out_of(0, 0), FM1_MOD_MODULE + 0u, 4, 1.0f);   /* LFO's Mode: an ENUM without MOD */
  fm1_mod_set_slot(m, 4, &s);
  fm1_mod_get_plan(m, &p);
  CHECK(p.refused == 0x1Eu && p.active == 1u);
  for (b = 0, n = 0; b < 20; ++b) {
    uint32_t i;
    const uint32_t k = block(m, 64, w, 64);
    for (i = 0; i < k; ++i) CHECK(w[i].index != I_MODEL && w[i].index != I_LPG);
    n += k;
  }
  CHECK(n == 0);
  /* An ENUM with MOD is rounded. */
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 7, 0.1f);    /* +-0.7 of 7 steps from 2 */
  fm1_mod_set_slot(m, 5, &s);
  for (b = 0, n = 0; b < 100; ++b) {
    uint32_t i;
    const uint32_t k = block(m, 64, w, 64);
    for (i = 0; i < k; ++i) {
      CHECK(w[i].index == I_PATCH && (w[i].value == 1.0f || w[i].value == 3.0f ||
                                       w[i].value == 2.0f));
    }
    n += k;
  }
  CHECK(n > 0);
  /* M1: a base set while routed moves the base; the value sent is base +
   * the last offset, and the next tick swings round the new base. */
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 3, 0.25f);
  fm1_mod_set_slot(m, 0, &s);
  block(m, 64, w, 64);
  v = fm1_mod_set_base(m, FM1_MOD_SOUND, I_TIMBRE, 0.6f);
  CHECK(fm1_mod_base(m, FM1_MOD_SOUND, I_TIMBRE) == 0.6f);
  {
    volatile float base = 0.6f, swing = 0.25f;
    const float hi = base + swing, lo = base - swing;
    CHECK(v == hi || v == lo);
    for (b = 0; b < 30; ++b) {
      uint32_t i;
      const uint32_t k = block(m, 64, w, 64);
      for (i = 0; i < k; ++i) {
        if (w[i].index == I_TIMBRE) CHECK(w[i].value == hi || w[i].value == lo);
      }
    }
  }
  /* Unrouted: back to the base at the next tick. */
  s.flags = 0;
  fm1_mod_set_slot(m, 0, &s);
  n = block(m, 64, w, 64);
  CHECK(n >= 1 && w[0].index == I_TIMBRE && w[0].value == 0.6f);
  CHECK(fm1_mod_set_base(m, FM1_MOD_SOUND, I_TIMBRE, 0.3f) == 0.3f);   /* passes unchanged */
  /* SEMI into SEMI adds exact semitones: NOTE at 100 % on Tune. */
  s = cable(FM1_MOD_SRC_NOTE, FM1_MOD_SOUND, 5, 1.0f);
  fm1_mod_set_slot(m, 6, &s);
  fm1_mod_live_note(m, 67, 100);
  n = block(m, 64, w, 64);
  {
    uint32_t i, found = 0;
    for (i = 0; i < n; ++i) {
      if (w[i].index == I_TUNE) {
        CHECK(w[i].value == 7.0f);
        found = 1;
      }
    }
    CHECK(found);
  }
  fm1_mod_destroy(m);
}

/* A gate cable passes each rising edge with probability = amount, from its
 * own seeded generator, falls with it, and keeps the edge's frame; at 100 %
 * every edge passes and at 0 none. */
static void gates(unsigned *edges) {
  unsigned trial;
  for (trial = 0; trial < 3; ++trial) {
    const float amount = trial == 0 ? 1.0f : trial == 1 ? 0.5f : 0.0f;
    fm1_mod_t *m = make(0, 0, 11);
    fm1_mod_slot_t s;
    fm1_mod_write_t w[8];
    unsigned b, rises = 0, active = 0;
    fm1_mod_set_kind(m, 0, K_ENV);
    fm1_mod_set_param(m, 0, 0, 0.0f);   /* 0.5 ms attack, 0.5 ms decay: done */
    fm1_mod_set_param(m, 0, 1, 0.0f);   /* long before the next trigger */
    fm1_mod_set_param(m, 0, 6, 1.0f);   /* Trigger mode */
    s = cable(FM1_MOD_SRC_TRIG, FM1_MOD_MODULE + 0u, 0, amount);
    s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
    fm1_mod_set_slot(m, 0, &s);
    for (b = 0; b < 2000; ++b) {
      const fm1_mod_gate_t *g;
      if (b % 4u == 0) {
        fm1_mod_live_note(m, 60, 100);   /* at the block's start */
        fm1_mod_live_note(m, 60, 0);
      }
      block(m, G, w, 8);
      g = fm1_mod_gate_out(m, 0, 2);   /* ACTIVE */
      if (g->n && g->ev[0].high) {
        ++rises;
        CHECK(g->ev[0].frame == 0);
      }
      active += (unsigned)fm1_mod_gate_end(g);
      ++*edges;
    }
    if (amount >= 1.0f) CHECK(rises == 500);
    else if (amount <= 0.0f) CHECK(rises == 0 && active == 0);
    else CHECK(rises > 200 && rises < 300);
    fm1_mod_destroy(m);
  }
}

/* A note at frame f of a block reaches the next tick as an edge at its
 * offset from the previous tick: KEY into an envelope's ACTIVE output. */
static void edge_frames(void) {
  fm1_mod_t *m = make(0, 0, 2);
  fm1_mod_write_t w[8];
  const fm1_mod_gate_t *g;
  uint32_t tf;
  fm1_mod_set_kind(m, 0, K_ENV);       /* GATE normalled to KEY */
  block(m, 64, w, 8);                  /* frames 0-63; ticks at 32 and 64 */
  tf = fm1_mod_begin(m, 64, 0);     /* frames 64-127: tick at 0 (frame 64), then 32 */
  CHECK(tf == 0);
  fm1_mod_note(m, 0, 60, 100);         /* at frame 64 itself: after the tick at 64 */
  fm1_mod_tick(m, 0, NULL);
  g = fm1_mod_gate_out(m, 0, 2);
  CHECK(g->n == 0 && fm1_mod_gate_end(g) == 0);
  fm1_mod_tick(m, 32, NULL);           /* covers 64-95: the note at offset 0 */
  g = fm1_mod_gate_out(m, 0, 2);
  CHECK(g->n == 1 && g->ev[0].frame == 0 && g->ev[0].high == 1);
  tf = fm1_mod_begin(m, 64, 0);     /* frames 128-191 */
  fm1_mod_note(m, 13, 60, 0);          /* frame 141 */
  fm1_mod_tick(m, 0, NULL);            /* covers 96-127: nothing yet */
  fm1_mod_tick(m, 32, NULL);           /* covers 128-159: KEY falls at 13 */
  CHECK(fm1_mod_system_value(m, FM1_MOD_SRC_KEY) == 0.0f);
  CHECK(m->sys_gate[0].n == 1 && m->sys_gate[0].ev[0].frame == 13);
  fm1_mod_destroy(m);
}

/* Gate inputs never strand a gate. An amount edit keeps a gate cable's
 * state, so a key released after it still releases the envelope; a cable
 * patched into a normalled input, or pulled from it, is an edge at the
 * tick's first frame; a reset envelope's ACT falls as an edge. */
static uint32_t act_end(const fm1_mod_t *m, unsigned pos) {
  return (uint32_t)fm1_mod_gate_end(fm1_mod_gate_out(m, pos, 2));
}

static void gate_continuity(unsigned *checks) {
  fm1_mod_t *m = make(0, 0, 4);
  fm1_mod_slot_t s;
  fm1_mod_write_t w[8];
  const fm1_mod_gate_t *g;
  unsigned b;
  fm1_mod_set_kind(m, 0, K_ENV);           /* Gate mode, GATE normalled to KEY */
  fm1_mod_set_param(m, 0, 0, 0.0f);        /* 0.5 ms attack and decay */
  fm1_mod_set_param(m, 0, 1, 0.0f);
  fm1_mod_set_param(m, 0, 3, 0.0f);        /* 0.5 ms release */
  s = cable(FM1_MOD_SRC_KEY, FM1_MOD_MODULE + 0u, 0, 1.0f);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
  fm1_mod_set_slot(m, 0, &s);
  fm1_mod_live_note(m, 60, 100);
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 1 && m->srt[0].level == 1);
  /* Turning the cable's amount while the key is held keeps it high and its
   * stream where it was. */
  {
    const fm1_mp_rng_t before = m->srt[0].rng;
    s.amount = fm1_mod_q14(0.9f);
    fm1_mod_set_slot(m, 0, &s);
    CHECK(m->srt[0].level == 1 && m->srt[0].rng.s == before.s);
  }
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 1);
  fm1_mod_live_note(m, 60, 0);             /* the release passes the cable */
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 0);
  ++*checks;

  /* New ends make a new cable: SEQ1 (low) into GATE while the key is held
   * is a fall at the next tick's first frame, and the envelope releases. */
  fm1_mod_live_note(m, 62, 100);
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 1 && m->gin_level[0] == 1);
  s = cable(FM1_MOD_SRC_SEQ_GATE, FM1_MOD_MODULE + 0u, 0, 1.0f);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
  fm1_mod_set_slot(m, 0, &s);
  CHECK(m->srt[0].level == 0);
  block(m, 64, w, 8);
  CHECK(m->gin_level[0] == 0);
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 0);
  ++*checks;

  /* Pulling the cable gives GATE back to KEY, still held: a rise at frame
   * 0, and the envelope opens again. */
  s.flags = (uint8_t)(s.flags & ~FM1_MOD_SLOT_ON);
  fm1_mod_set_slot(m, 0, &s);
  block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 1 && m->gin_level[0] == 1);
  ++*checks;

  /* A reset (a preset load) while ACT is high: ACT falls at frame 0. */
  fm1_mod_reset(m, FM1_MOD_RESET_PRESET);
  block(m, 32, w, 8);
  g = fm1_mod_gate_out(m, 0, 2);
  CHECK(g->start == 1 && g->n == 1 && g->ev[0].frame == 0 && g->ev[0].high == 0);
  ++*checks;
  fm1_mod_destroy(m);

  /* Rule M1 at a zero amount: an unrouted base set out of range, or NaN,
   * is held clamped as the engine holds it, so a zero-amount route writes
   * nothing. */
  m = make(0, 0, 4);
  fm1_mod_set_kind(m, 0, K_LFO);
  CHECK(fm1_mod_set_base(m, FM1_MOD_SOUND, I_TIMBRE, 1.5f) == 1.5f);   /* passed on as sent */
  CHECK(fm1_mod_sent(m, FM1_MOD_SOUND, I_TIMBRE) == 1.0f);
  CHECK(fm1_mod_set_base(m, FM1_MOD_HOST, FM1_MOD_HOST_PITCH, 60.0f) == 60.0f);
  {
    const float r = fm1_mod_set_base(m, FM1_MOD_SOUND, I_TUNE, NAN);
    CHECK(r != r && fm1_mod_sent(m, FM1_MOD_SOUND, I_TUNE) == 0.0f);   /* NaN: the default */
  }
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 3, 0.0f);
  fm1_mod_set_slot(m, 0, &s);
  s = cable(out_of(0, 0), FM1_MOD_SOUND, 5, 0.0f);
  fm1_mod_set_slot(m, 1, &s);
  s = cable(out_of(0, 0), FM1_MOD_HOST, FM1_MOD_HOST_PITCH_UID, 0.0f);
  fm1_mod_set_slot(m, 2, &s);
  for (b = 0; b < 20; ++b) CHECK(block(m, 64, w, 8) == 0);
  ++*checks;
  fm1_mod_destroy(m);

  /* Replacing a module restarts its outputs low, so a gate cable it drove
   * goes low too: the module it reached releases even though the new
   * instance never rises (its own GATE now comes from SEQ1, silent). */
  m = make(0, 0, 5);
  fm1_mod_set_kind(m, 0, K_ENV);
  fm1_mod_set_kind(m, 1, K_ENV);
  for (b = 0; b < 2u; ++b) {
    fm1_mod_set_param(m, b, 0, 0.0f);
    fm1_mod_set_param(m, b, 1, 0.0f);
    fm1_mod_set_param(m, b, 3, 0.0f);
  }
  s = cable(out_of(0, 2), FM1_MOD_MODULE + 1u, 0, 1.0f);   /* ENV1 ACT -> ENV2 GATE */
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
  fm1_mod_set_slot(m, 0, &s);
  fm1_mod_live_note(m, 60, 100);
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 1) == 1 && m->srt[0].level == 1);
  fm1_mod_set_kind(m, 0, K_ENV);
  s = cable(FM1_MOD_SRC_SEQ_GATE, FM1_MOD_MODULE + 0u, 0, 1.0f);
  s.flags = (uint8_t)(s.flags | FM1_MOD_SLOT_GATE_DST);
  fm1_mod_set_slot(m, 1, &s);
  CHECK(m->srt[0].level == 0);
  for (b = 0; b < 4; ++b) block(m, 64, w, 8);
  CHECK(act_end(m, 0) == 0 && act_end(m, 1) == 0 && m->gin_level[1] == 0);
  ++*checks;
  fm1_mod_destroy(m);
}

int main(void) {
  unsigned plans = 0, loops = 0, chain_ticks = 0, fb_ticks = 0, fill_writes = 0, nan_checked = 0;
  unsigned gate_ticks = 0, continuity = 0, voice_writes = 0;
  K_LFO = fm1_mod_kind_find("lfo");
  K_ENV = fm1_mod_kind_find("ENV");
  K_CHN = fm1_mod_kind_find("chance");
  CHECK(K_LFO >= 0 && K_ENV >= 0 && K_CHN >= 0 && fm1_mod_kind_find("CHN") == K_CHN);
  CHECK(fm1_mod_size() <= MEM_BYTES && (fm1_mod_size() & 15u) == 0);
  CHECK(fm1_mod_create(mem_block(0) + 8, &kHost, 0) == NULL);   /* misaligned */
  planner_fuzz(&plans, &loops);
  chain(&chain_ticks);
  feedback(&fb_ticks);
  any_fill(&fill_writes);
  nan_survived(&nan_checked);
  rules();
  gates(&gate_ticks);
  edge_frames();
  gate_continuity(&continuity);
  voices(&voice_writes);
  voices_hostile(&voice_writes);
  voices_shrink(&voice_writes);
  voices_sound_sources(&voice_writes);
  voices_current(&voice_writes);
  voices_gate_rewire(&voice_writes);
  printf("{\"size\":%zu,\"plans\":%u,\"plans_with_loops\":%u,\"chain_ticks\":%u,"
         "\"feedback_ticks\":%u,\"fill_writes\":%u,\"nan_writes\":%u,\"gate_ticks\":%u,"
         "\"continuity\":%u,\"voice_writes\":%u,"
         "\"failed\":%d}\n",
         fm1_mod_size(), plans, loops, chain_ticks, fb_ticks, fill_writes, nan_checked,
         gate_ticks, continuity, voice_writes, failed);
  return failed;
}

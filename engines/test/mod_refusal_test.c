/* mod_refusal_test.c -- fm1-mod-refusal-test: why the planner refuses a slot
 * (fm1_mod_slot_refusal, fm1_mod.h; the codes and words of fm1_refusal.h,
 * stage ED0 of notes/2026-10-06-web-editor.md):
 *
 *   - each reason, from a slot built to have it: NO_SOURCE (an empty rack
 *     position, a port its kind lacks, a VIA that names nothing), NO_DEST,
 *     NOLOCK, ENUM_NO_MOD, NO_MOD, VOICE_TO_MONO, VOICE_TO_EFFECT,
 *     UNIT_RESERVED and VOICE_FULL; and 0 for a slot that runs or is off;
 *   - over random racks, engines and slot tables, a slot has a reason
 *     exactly when the plan refuses it, and the reason is a cable's;
 *   - asking changes nothing: the plan and every slot are the same after.
 *
 * VOICE_ROOM (the modules' per-voice copies do not fit one voice) is
 * unreachable with today's kinds, whose copies are a few hundred bytes of
 * the 8 KB arena; the fuzz would count it if a kind ever made it so.
 *
 * Prints one JSON line of counts; exits 1 after reporting the first failed
 * check. Desktop test code. MIT licence, like the rest of this repository. */
#include "mod_int.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "fm1_refusal.h"

static int failed;

#define CHECK(c)                                                          \
  do {                                                                    \
    if (!(c)) {                                                           \
      fprintf(stderr, "%s:%d: check failed: %s\n", __FILE__, __LINE__, #c); \
      failed = 1;                                                         \
    }                                                                     \
  } while (0)

#define CONT FM1_PARAM_CONTINUOUS
static const char *const kNames[] = { "a", "b", "c", "d", "e", "f", "g", "h" };
/* A sound with one parameter of every kind a cable may meet. */
static const fm1_param_t kParams[] = {
  { "Model", FM1_PARAM_ENUM, 0.0f, 7.0f, 0.0f, kNames, 0, 1, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Model" },
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 3, CONT, FM1_UNIT_NONE, "Timbre" },
  { "Dry", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 4, 0, FM1_UNIT_NONE, "Dry" },
  { "Patch", FM1_PARAM_ENUM, 0.0f, 7.0f, 2.0f, kNames, 1, 7, FM1_PARAM_MOD, FM1_UNIT_NONE, "Patch" },
  { "Lpg", FM1_PARAM_ENUM, 0.0f, 2.0f, 0.0f, kNames, 1, 11, 0, FM1_UNIT_NONE, "Lpg" },
};
static const fm1_engine_t kEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake", "Fake", "", kParams,
  (uint16_t)(sizeof(kParams) / sizeof(kParams[0])), 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, NULL, 0, NULL, 0, 0, NULL
};

/* A sound with per-note offsets on three parameters (MG9). */
static void poly_note(void *self, uint8_t key, uint16_t index, float offset) {
  (void)self;
  (void)key;
  (void)index;
  (void)offset;
}
static const fm1_param_t kPolyParams[] = {
  { "Timbre", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 3, CONT | FM1_PARAM_POLY, FM1_UNIT_NONE, "Timbre" },
  { "Color", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 5, CONT | FM1_PARAM_POLY, FM1_UNIT_NONE, "Color" },
  { "Morph", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 6, CONT | FM1_PARAM_POLY, FM1_UNIT_NONE, "Morph" },
  { "Drive", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 4, CONT, FM1_UNIT_NONE, "Drive" },
};
static const fm1_engine_t kPolyEngine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND, "fake-poly", "Fake Poly", "", kPolyParams,
  (uint16_t)(sizeof(kPolyParams) / sizeof(kPolyParams[0])), 8, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, poly_note, 0, NULL, 0, 0, NULL
};

/* An effect with one parameter that takes cables. */
static const fm1_param_t kFxParams[] = {
  { "Mix", FM1_PARAM_FLOAT, 0.0f, 1.0f, 0.5f, NULL, 0, 1, CONT, FM1_UNIT_NONE, "Mix" },
};
static const fm1_engine_t kFx = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX, "fake-fx", "Fake FX", "", kFxParams,
  (uint16_t)(sizeof(kFxParams) / sizeof(kFxParams[0])), 0, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
  NULL, NULL, 0, NULL, 0, 0, NULL
};
#undef CONT

#define MEM_BYTES (1u << 16)
static fm1_host_t kHost = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };

static unsigned char *mem_block(void) {
  static unsigned char raw[MEM_BYTES + 16];
  return raw + (16u - ((uintptr_t)raw & 15u)) % 16u;
}

static fm1_mod_t *make(uint32_t seed) {
  unsigned char *mem = mem_block();
  fm1_mod_t *m;
  memset(mem, 0, fm1_mod_size());
  m = fm1_mod_create(mem, &kHost, seed);
  CHECK(m != NULL);
  return m;
}

static fm1_mod_slot_t cable(unsigned src, unsigned unit, unsigned dst, unsigned flags) {
  fm1_mod_slot_t s;
  memset(&s, 0, sizeof(s));
  s.src = (uint8_t)src;
  s.via = FM1_MOD_NONE;
  s.dst_unit = (uint8_t)unit;
  s.dst = (uint16_t)dst;
  s.flags = (uint8_t)(FM1_MOD_SLOT_ON | flags);
  s.amount = fm1_mod_q14(0.5f);
  return s;
}

static unsigned out_of(unsigned pos, unsigned port) { return FM1_MOD_SRC_MODULE + 8u * pos + port; }

static unsigned asked;

/* Slot 0 set to s alone: its reason. */
static unsigned reason(fm1_mod_t *m, fm1_mod_slot_t s) {
  fm1_mod_slot_t off;
  unsigned i;
  ++asked;
  memset(&off, 0, sizeof(off));
  off.via = FM1_MOD_NONE;
  for (i = 0; i < FM1_MOD_SLOTS; ++i) fm1_mod_set_slot(m, i, &off);
  fm1_mod_set_slot(m, 0, &s);
  return fm1_mod_slot_refusal(m, 0);
}

static int is_cable_code(unsigned c) {
  return c >= FM1_REFUSE_NO_SOURCE && c <= FM1_REFUSE_VOICE_ROOM && fm1_refusal_find(c) != NULL;
}

static void each_reason(unsigned *cases) {
  const int k_lfo = fm1_mod_kind_find("lfo"), k_env = fm1_mod_kind_find("env");
  fm1_mod_t *m = make(1);
  fm1_mod_slot_t s;
  unsigned i;
  CHECK(k_lfo >= 0 && k_env >= 0);
  fm1_mod_bind(m, FM1_MOD_SOUND, &kEngine);
  fm1_mod_bind(m, FM1_MOD_FX1, &kFx);
  fm1_mod_bind(m, fm1_mod_insert_unit(0, 0), &kFx);
  fm1_mod_set_kind(m, 0, k_lfo);
  fm1_mod_set_kind(m, 1, k_env);

  /* Running, and off. */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 3, 0)) == 0);
  CHECK(reason(m, cable(out_of(0, 0), FM1_MOD_FX1, 1, 0)) == 0);
  s = cable(out_of(5, 0), FM1_MOD_SOUND, 3, 0);
  s.flags = 0;
  CHECK(reason(m, s) == 0);
  /* Sources. */
  CHECK(reason(m, cable(out_of(5, 0), FM1_MOD_SOUND, 3, 0)) == FM1_REFUSE_NO_SOURCE);   /* empty */
  CHECK(reason(m, cable(out_of(0, 7), FM1_MOD_SOUND, 3, 0)) == FM1_REFUSE_NO_SOURCE);   /* no port */
  s = cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 3, 0);
  s.via = (uint8_t)out_of(6, 0);
  CHECK(reason(m, s) == FM1_REFUSE_NO_SOURCE);
  /* Destinations. */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 99, 0)) == FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 0, 0)) == FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_MODULE + 6u, 1, 0)) == FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_TRIG, FM1_MOD_SOUND, 3, FM1_MOD_SLOT_GATE_DST)) == FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_TRIG, FM1_MOD_MODULE + 1u, 7, FM1_MOD_SLOT_GATE_DST)) ==
        FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_TRIG, FM1_MOD_MODULE + 1u, 0, FM1_MOD_SLOT_GATE_DST)) == 0);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_HOST, 77, 0)) == FM1_REFUSE_NO_DEST);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND_UNIT + 2u, 3, 0)) == FM1_REFUSE_NO_DEST);  /* unbound */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 1, 0)) == FM1_REFUSE_NOLOCK);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 11, 0)) == FM1_REFUSE_ENUM_NO_MOD);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 7, 0)) == 0);                 /* ENUM with MOD */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 4, 0)) == FM1_REFUSE_NO_MOD);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, 5u, 1, 0)) == FM1_REFUSE_UNIT_RESERVED);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, 42u, 1, 0)) == FM1_REFUSE_UNIT_RESERVED);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, 200u, 1, 0)) == FM1_REFUSE_UNIT_RESERVED);
  /* Per voice. */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_SOUND, 3, FM1_MOD_SLOT_VOICE)) ==
        FM1_REFUSE_VOICE_TO_MONO);                       /* an engine with no per-note offsets */
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_HOST, FM1_MOD_HOST_AMP_UID, FM1_MOD_SLOT_VOICE)) ==
        FM1_REFUSE_VOICE_TO_MONO);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_FX1, 1, FM1_MOD_SLOT_VOICE)) == FM1_REFUSE_VOICE_TO_EFFECT);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, fm1_mod_insert_unit(0, 0), 1, FM1_MOD_SLOT_VOICE)) ==
        FM1_REFUSE_VOICE_TO_EFFECT);
  CHECK(reason(m, cable(FM1_MOD_SRC_VEL, FM1_MOD_MODULE + 0u, fm1_mod_kinds[k_lfo]->params[0].uid,
                        FM1_MOD_SLOT_VOICE)) == FM1_REFUSE_VOICE_TO_MONO);   /* the LFO runs once */
  *cases += asked;
  fm1_mod_destroy(m);

  /* VOICE_FULL: nine per-voice destinations, of which eight fit. */
  m = make(2);
  fm1_mod_bind(m, FM1_MOD_SOUND, &kPolyEngine);
  fm1_mod_bind(m, FM1_MOD_SOUND_UNIT + 1u, &kPolyEngine);
  fm1_mod_bind(m, FM1_MOD_SOUND_UNIT + 2u, &kPolyEngine);
  {
    static const unsigned kUids[3] = { 3, 5, 6 };
    const unsigned units[3] = { FM1_MOD_SOUND, FM1_MOD_SOUND_UNIT + 1u, FM1_MOD_SOUND_UNIT + 2u };
    unsigned n = 0, u, k;
    for (u = 0; u < 3; ++u) {
      for (k = 0; k < 3; ++k) {
        s = cable(FM1_MOD_SRC_VEL, units[u], kUids[k], FM1_MOD_SLOT_VOICE);
        fm1_mod_set_slot(m, n++, &s);
      }
    }
    /* A second cable into a destination that fits is live too. */
    s = cable(FM1_MOD_SRC_RAND, FM1_MOD_SOUND, 3, FM1_MOD_SLOT_VOICE);
    fm1_mod_set_slot(m, n++, &s);
    for (i = 0; i < n; ++i) {
      CHECK(fm1_mod_slot_refusal(m, i) == (i == 8 ? (unsigned)FM1_REFUSE_VOICE_FULL : 0u));
    }
    *cases += n;
  }
  fm1_mod_destroy(m);
}

/* Random racks and slot tables: a reason exactly when the plan refuses. */
static uint32_t rng_state = 12345u;
static uint32_t rnd(void) {
  rng_state = rng_state * 1664525u + 1013904223u;
  return rng_state >> 8;
}

static void fuzz(unsigned rounds, unsigned *slots, unsigned counts[64]) {
  static const unsigned kUnits[] = { 0, 1, 2, 3, 5, 8, 9, 10, 13, 15, 16, 17, 18, 19, 20, 21, 24,
                                     27, 28, 36, 40, 41, 42, 200 };
  static const unsigned kDst[] = { 0, 1, 2, 3, 4, 5, 6, 7, 11, 99 };
  unsigned r, i;
  for (r = 0; r < rounds; ++r) {
    fm1_mod_t *m = make(r);
    fm1_mod_plan_info_t before, after;
    fm1_mod_slot_t table[FM1_MOD_SLOTS], again;
    unsigned pos;
    fm1_mod_bind(m, FM1_MOD_SOUND, rnd() & 1u ? &kPolyEngine : &kEngine);
    if (rnd() & 1u) fm1_mod_bind(m, FM1_MOD_SOUND_UNIT + 1u, &kPolyEngine);
    fm1_mod_bind(m, FM1_MOD_FX1, &kFx);
    if (rnd() & 1u) fm1_mod_bind(m, fm1_mod_insert_unit(1, 0), &kFx);
    for (pos = 0; pos < FM1_MOD_POSITIONS; ++pos) {
      const unsigned pick = rnd() % (unsigned)(fm1_mod_kind_count + 2u);
      if (pick < fm1_mod_kind_count) fm1_mod_set_kind(m, pos, (int)pick);
    }
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_slot_t s;
      const unsigned which = rnd() % 3u;
      memset(&s, 0, sizeof(s));
      s.src = (uint8_t)(which == 0 ? rnd() % 64u : out_of(rnd() % 8u, rnd() % 8u));
      s.via = (uint8_t)(rnd() % 4u ? FM1_MOD_NONE : (rnd() & 1u ? rnd() % 64u : out_of(rnd() % 8u, rnd() % 8u)));
      s.dst_unit = (uint8_t)kUnits[rnd() % (sizeof(kUnits) / sizeof(kUnits[0]))];
      s.dst = (uint16_t)kDst[rnd() % (sizeof(kDst) / sizeof(kDst[0]))];
      s.flags = (uint8_t)((rnd() % 5u ? FM1_MOD_SLOT_ON : 0u) | (rnd() % 3u ? 0u : FM1_MOD_SLOT_VOICE) |
                          (rnd() % 6u ? 0u : FM1_MOD_SLOT_GATE_DST));
      s.amount = fm1_mod_q14(0.25f);
      fm1_mod_set_slot(m, i, &s);
      fm1_mod_get_slot(m, i, &table[i]);
    }
    fm1_mod_get_plan(m, &before);
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      const unsigned why = fm1_mod_slot_refusal(m, i);
      const int refused = (int)((before.refused >> i) & 1u);
      CHECK(refused == (why != 0));
      CHECK(!why || is_cable_code(why));
      if (why) ++counts[why & 63u];
      ++*slots;
    }
    /* The loop each late slot closes (ED1): its ends' component, and the
     * positions in it, numbered as the plan's comp; nothing for the rest. */
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      uint8_t in = 0xAAu, comp_of[FM1_MOD_POSITIONS];
      const unsigned loop = fm1_mod_slot_loop(m, i, &in);
      unsigned k;
      memset(comp_of, 0xFF, sizeof(comp_of));
      for (k = 0; k < before.n_order; ++k) comp_of[before.order[k]] = before.comp[k];
      if (!((before.delayed >> i) & 1u)) {
        CHECK(loop == 0xFFu && in == 0);
        continue;
      }
      ++counts[0];
      CHECK(table[i].dst_unit >= FM1_MOD_MODULE && loop != 0xFFu);
      CHECK((in >> (table[i].dst_unit - FM1_MOD_MODULE)) & 1u);
      for (k = 0; k < FM1_MOD_POSITIONS; ++k) {
        CHECK(((in >> k) & 1u) == (comp_of[k] == loop));
      }
    }
    fm1_mod_get_plan(m, &after);
    CHECK(memcmp(&before, &after, sizeof(before)) == 0);
    for (i = 0; i < FM1_MOD_SLOTS; ++i) {
      fm1_mod_get_slot(m, i, &again);
      CHECK(memcmp(&again, &table[i], sizeof(again)) == 0);
    }
    fm1_mod_destroy(m);
    if (failed) return;
  }
}

/* A move keeps a source that names nothing as it is (ED1's fuzz found
 * fm1_mod_move reading past its permutation for one). */
static void move_keeps_nothing(void) {
  fm1_mod_t *m = make(7);
  fm1_mod_slot_t s, back;
  memset(&s, 0, sizeof(s));
  s.src = 200;
  s.via = 130;
  s.dst_unit = FM1_MOD_MODULE + 1u;
  s.flags = FM1_MOD_SLOT_ON;
  fm1_mod_set_kind(m, 0, 0);
  fm1_mod_set_kind(m, 1, 0);
  fm1_mod_set_slot(m, 0, &s);
  CHECK(fm1_mod_move(m, 0, 7) == 1);
  fm1_mod_get_slot(m, 0, &back);
  CHECK(back.src == 200 && back.via == 130 && back.dst_unit == FM1_MOD_MODULE + 0u);
  CHECK(fm1_mod_slot_refusal(m, 0) == FM1_REFUSE_NO_SOURCE);
  fm1_mod_destroy(m);
}

int main(int argc, char **argv) {
  unsigned cases = 0, slots = 0, counts[64], i, first = 1;
  const unsigned rounds = argc > 1 ? (unsigned)atoi(argv[1]) : 2000u;
  memset(counts, 0, sizeof(counts));
  each_reason(&cases);
  move_keeps_nothing();
  fuzz(rounds, &slots, counts);
  printf("{\"cases\":%u,\"fuzz_slots\":%u,\"reasons\":{", cases, slots);
  for (i = 1; i < 64; ++i) {
    const fm1_refusal_t *r = counts[i] ? fm1_refusal_find(i) : NULL;
    if (!r) continue;
    printf("%s\"%s\":%u", first ? "" : ",", r->name, counts[i]);
    first = 0;
  }
  printf("},\"late_loops\":%u,\"failed\":%d}\n", counts[0], failed);
  return failed;
}

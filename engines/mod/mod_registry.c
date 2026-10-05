/* mod_registry.c -- the modulation runtime's static tables: the module kinds,
 * the system sources and the host unit's parameters (fm1_mod.h). Adding a
 * kind is one line here plus its file under kinds/ (docs/16 §7). MIT
 * licence. */
#include "mod_int.h"

extern const fm1_mod_kind_t fm1_mod_kind_lfo;
extern const fm1_mod_kind_t fm1_mod_kind_env;
extern const fm1_mod_kind_t fm1_mod_kind_chance;
extern const fm1_mod_kind_t fm1_mod_kind_function;
extern const fm1_mod_kind_t fm1_mod_kind_bounce;
extern const fm1_mod_kind_t fm1_mod_kind_register;
extern const fm1_mod_kind_t fm1_mod_kind_coin;
extern const fm1_mod_kind_t fm1_mod_kind_divide;
extern const fm1_mod_kind_t fm1_mod_kind_burst;
extern const fm1_mod_kind_t fm1_mod_kind_slew;
extern const fm1_mod_kind_t fm1_mod_kind_quantize;
extern const fm1_mod_kind_t fm1_mod_kind_compare;
extern const fm1_mod_kind_t fm1_mod_kind_logic;
extern const fm1_mod_kind_t fm1_mod_kind_calc;
extern const fm1_mod_kind_t fm1_mod_kind_mix;
extern const fm1_mod_kind_t fm1_mod_kind_filter;

/* Registry order is not saved anywhere (presets store each kind's guid),
 * so new kinds may go anywhere; keep the first wave first. */
const fm1_mod_kind_t *const fm1_mod_kinds[] = {
  &fm1_mod_kind_lfo,
  &fm1_mod_kind_env,
  &fm1_mod_kind_chance,
  /* MG2 (docs/16 §8): the glue kinds, in the catalogue's order, and Filter. */
  &fm1_mod_kind_function,
  &fm1_mod_kind_bounce,
  &fm1_mod_kind_register,
  &fm1_mod_kind_coin,
  &fm1_mod_kind_divide,
  &fm1_mod_kind_burst,
  &fm1_mod_kind_slew,
  &fm1_mod_kind_quantize,
  &fm1_mod_kind_compare,
  &fm1_mod_kind_logic,
  &fm1_mod_kind_calc,
  &fm1_mod_kind_mix,
  &fm1_mod_kind_filter,
};
const size_t fm1_mod_kind_count = sizeof(fm1_mod_kinds) / sizeof(fm1_mod_kinds[0]);

static char lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

static int same(const char *a, const char *b) {
  for (; *a && *b; ++a, ++b) {
    if (lower(*a) != lower(*b)) return 0;
  }
  return *a == *b;
}

int fm1_mod_kind_find(const char *name) {
  size_t i;
  if (!name) return -1;
  for (i = 0; i < fm1_mod_kind_count; ++i) {
    if (same(fm1_mod_kinds[i]->id, name) || same(fm1_mod_kinds[i]->abbr, name)) return (int)i;
  }
  return -1;
}

/* The host unit: PITCH in semitones (its base is the MIDI bend, +-48 as
 * pitch_bend allows) and AMP, a gain of 0..2 (+6 dB) with base 1. */
const fm1_param_t fm1_mod_host_params[FM1_MOD_HOST_PARAMS] = {
  { "Pitch", FM1_PARAM_FLOAT, -48.0f, 48.0f, 0.0f, NULL, 0, FM1_MOD_HOST_PITCH_UID,
    FM1_PARAM_CONTINUOUS, FM1_UNIT_SEMI, "Pitch" },
  { "Amp", FM1_PARAM_FLOAT, 0.0f, 2.0f, 1.0f, NULL, 0, FM1_MOD_HOST_AMP_UID,
    FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Amp" },
};

#define CV_UNI(n) { n, FM1_PORT_CV_UNI, FM1_UNIT_NONE }
#define GATE(n) { n, FM1_PORT_GATE, FM1_UNIT_NONE }

static const fm1_mod_source_info_t kSources[FM1_MOD_SRC_SYSTEM] = {
  [FM1_MOD_SRC_VEL] = CV_UNI("VEL"),
  [FM1_MOD_SRC_NOTE] = { "NOTE", FM1_PORT_CV_BI, FM1_UNIT_SEMI },
  [FM1_MOD_SRC_RAND] = { "RAND", FM1_PORT_CV_BI, FM1_UNIT_NONE },
  [FM1_MOD_SRC_KEY] = GATE("KEY"),
  [FM1_MOD_SRC_TRIG] = GATE("TRIG"),
  [FM1_MOD_SRC_CLOCK] = GATE("CLOCK"),
  [FM1_MOD_SRC_BEAT] = GATE("BEAT"),
  [FM1_MOD_SRC_BAR] = GATE("BAR"),
  [FM1_MOD_SRC_RUN] = GATE("RUN"),
  [FM1_MOD_SRC_START] = GATE("START"),
  [FM1_MOD_SRC_SEQ_GATE + 0] = GATE("SEQ1"),
  [FM1_MOD_SRC_SEQ_GATE + 1] = GATE("SEQ2"),
  [FM1_MOD_SRC_SEQ_GATE + 2] = GATE("SEQ3"),
  [FM1_MOD_SRC_SEQ_GATE + 3] = GATE("SEQ4"),
  [FM1_MOD_SRC_SEQ_GATE + 4] = GATE("SEQ5"),
  [FM1_MOD_SRC_SEQ_GATE + 5] = GATE("SEQ6"),
  [FM1_MOD_SRC_SEQ_GATE + 6] = GATE("SEQ7"),
  [FM1_MOD_SRC_SEQ_GATE + 7] = GATE("SEQ8"),
  [FM1_MOD_SRC_SEQ_VEL + 0] = CV_UNI("SQV1"),
  [FM1_MOD_SRC_SEQ_VEL + 1] = CV_UNI("SQV2"),
  [FM1_MOD_SRC_SEQ_VEL + 2] = CV_UNI("SQV3"),
  [FM1_MOD_SRC_SEQ_VEL + 3] = CV_UNI("SQV4"),
  [FM1_MOD_SRC_SEQ_VEL + 4] = CV_UNI("SQV5"),
  [FM1_MOD_SRC_SEQ_VEL + 5] = CV_UNI("SQV6"),
  [FM1_MOD_SRC_SEQ_VEL + 6] = CV_UNI("SQV7"),
  [FM1_MOD_SRC_SEQ_VEL + 7] = CV_UNI("SQV8"),
};

const fm1_mod_source_info_t *fm1_mod_system_source(unsigned id) {
  return id < FM1_MOD_SRC_SYSTEM && kSources[id].name ? &kSources[id] : NULL;
}

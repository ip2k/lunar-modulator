// registry.cc -- the static engine registry (docs/11 §5.2, tier 0).
// Engines are compiled in; adding one is a line here and a line in the Makefile.
// MIT licence.

#include "fm1_engine.h"

#include <cstring>

extern "C" {
extern const fm1_engine_t fm1_engine_macro;
extern const fm1_engine_t fm1_engine_shapes;
extern const fm1_engine_t fm1_engine_macro_heavy;
extern const fm1_engine_t fm1_engine_sixop;
extern const fm1_engine_t fm1_engine_sw_sophie;
extern const fm1_engine_t fm1_engine_test_sine;
extern const fm1_engine_t fm1_engine_plate;
extern const fm1_engine_t fm1_engine_ensemble;
extern const fm1_engine_t fm1_engine_diffuse;
extern const fm1_engine_t fm1_engine_sw_psxverb;
extern const fm1_engine_t fm1_engine_crush;
extern const fm1_engine_t fm1_engine_fold;
extern const fm1_engine_t fm1_engine_drive;
extern const fm1_engine_t fm1_engine_echo;
extern const fm1_engine_t fm1_engine_filter;
extern const fm1_engine_t fm1_engine_comb;
extern const fm1_engine_t fm1_engine_comp;
extern const fm1_engine_t fm1_engine_limit;
extern const fm1_engine_t fm1_engine_djfilter;
extern const fm1_engine_t fm1_engine_tilt;
extern const fm1_engine_t fm1_engine_sat;
extern const fm1_engine_t fm1_engine_isolator;
extern const fm1_engine_t fm1_engine_eq;
extern const fm1_engine_t fm1_engine_test_gain;
extern const fm1_engine_t fm1_engine_test_ext;

const fm1_engine_t *const fm1_engines[] = {
  // sound engines
  &fm1_engine_macro,
  &fm1_engine_shapes,
  &fm1_engine_macro_heavy,
  &fm1_engine_sixop,
  &fm1_engine_sw_sophie,
  &fm1_engine_test_sine,
  // audio effects
  &fm1_engine_plate,
  &fm1_engine_ensemble,
  &fm1_engine_diffuse,
  &fm1_engine_sw_psxverb,
  &fm1_engine_crush,
  &fm1_engine_fold,
  &fm1_engine_drive,
  &fm1_engine_echo,
  &fm1_engine_filter,
  &fm1_engine_comb,
  &fm1_engine_comp,
  &fm1_engine_limit,
  &fm1_engine_djfilter,
  &fm1_engine_tilt,
  &fm1_engine_sat,
  &fm1_engine_isolator,
  &fm1_engine_eq,
  &fm1_engine_test_gain,
  &fm1_engine_test_ext,
};
const size_t fm1_engine_count = sizeof(fm1_engines) / sizeof(fm1_engines[0]);

const fm1_engine_t *fm1_engine_find(const char *id) {
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (strcmp(fm1_engines[i]->id, id) == 0) return fm1_engines[i];
  }
  return NULL;
}
}

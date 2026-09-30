// registry.cc -- the static engine registry (docs/11 §5.2, tier 0).
// Engines are compiled in; adding one is a line here and a line in the Makefile.
// MIT licence.

#include "fm1_engine.h"

#include <cstring>

extern "C" {
extern const fm1_engine_t fm1_engine_macro;
extern const fm1_engine_t fm1_engine_shapes;
extern const fm1_engine_t fm1_engine_test_sine;
extern const fm1_engine_t fm1_engine_test_gain;

const fm1_engine_t *const fm1_engines[] = {
  &fm1_engine_macro,
  &fm1_engine_shapes,
  &fm1_engine_test_sine,
  &fm1_engine_test_gain,
};
const size_t fm1_engine_count = sizeof(fm1_engines) / sizeof(fm1_engines[0]);

const fm1_engine_t *fm1_engine_find(const char *id) {
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    if (strcmp(fm1_engines[i]->id, id) == 0) return fm1_engines[i];
  }
  return NULL;
}
}

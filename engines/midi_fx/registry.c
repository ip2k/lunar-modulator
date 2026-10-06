/* registry.c -- the MIDI effects' static registry (engine API v3,
 * FM1_KIND_MIDI_FX; fm1_engine.h). Its own list, beside the engines' in
 * src/registry.cc, so the sound and effect lists stay as they are. Adding a
 * MIDI effect is a line here and its sources in mk/midi_fx.mk.
 * MIT licence, like the rest of this repository.
 */
#include "fm1_engine.h"

#include <string.h>

extern const fm1_midi_fx_t fm1_midi_fx_arp;

const fm1_midi_fx_t *const fm1_midi_fxs[] = {
  &fm1_midi_fx_arp,
};
const size_t fm1_midi_fx_count = sizeof(fm1_midi_fxs) / sizeof(fm1_midi_fxs[0]);

const fm1_midi_fx_t *fm1_midi_fx_find(const char *id) {
  size_t i;
  for (i = 0; id && i < fm1_midi_fx_count; ++i) {
    if (strcmp(fm1_midi_fxs[i]->engine.id, id) == 0) return fm1_midi_fxs[i];
  }
  return NULL;
}

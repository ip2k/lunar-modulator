/* state_registry.c -- fm1_state_names_default: the registries linked into
 * this program (engines/src/registry.cc, engines/midi_fx/registry.c,
 * engines/mod/mod_registry.c). Kept apart from the reader and the writers
 * so a fuzz target or a test can link them without every engine. MIT
 * licence. */
#include "fm1_state.h"

#include <string.h>

void fm1_state_names_default(fm1_state_names_t *nm) {
  memset(nm, 0, sizeof(*nm));
  nm->engines = fm1_engines;
  nm->n_engines = fm1_engine_count;
  nm->mfx = fm1_midi_fxs;
  nm->n_mfx = fm1_midi_fx_count;
  nm->kinds = fm1_mod_kinds;
  nm->n_kinds = fm1_mod_kind_count;
  nm->host = fm1_mod_host_params;
  nm->n_host = FM1_MOD_HOST_PARAMS;
  nm->source = fm1_mod_system_source;
#ifdef FM1_GPL_MODS
  nm->gpl = FM1_GPL_MODS ? 1 : 0;
#endif
}

/* fm1_known.c -- written by tools/gen_known.py from engines/known-ids.json
 * and engines/aliases.json; do not edit (fm1_known.h). MIT licence. */
#include "fm1_known.h"

#include <string.h>

const fm1_known_id_t fm1_known_ids[] = {
  { "comet", "sound", "gpl", NULL },
  { "crater", "sound", "gpl", NULL },
  { "acid-bass", "sound", "gpl", NULL },
  { "acid-gen", "midi_fx", "gpl", NULL },
  { "drawbar", "sound", "gpl", NULL },
  { "trio", "sound", "gpl", NULL },
  { "chop", "sound", "planned", NULL },
  { "phase-bend", "sound", "gpl", NULL },
  { NULL, NULL, NULL, NULL }
};
const size_t fm1_known_id_count = 8u;

const fm1_alias_t fm1_aliases[] = {
  { 0, NULL, 0u, 0, NULL }
};
const size_t fm1_alias_count = 0u;

const fm1_known_id_t *fm1_known_id_find(const char *id) {
  size_t i;
  for (i = 0; id && i < fm1_known_id_count; ++i) {
    if (strcmp(fm1_known_ids[i].id, id) == 0) return &fm1_known_ids[i];
  }
  return NULL;
}

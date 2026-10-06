/* fm1_known.h -- names a file may use that this build cannot load or no
 * longer spells that way (notes/2026-10-06-state-files.md §9, ST4):
 *
 *   - known ids: engines, effects, MIDI effects and modulation kinds a
 *     build may lack, with the reason a load gives ("in the GPL build
 *     only", "not built yet", "retired in 0.5"), so a refusal can say
 *     why, and an editor can tell an unknown id from a known absent one;
 *   - aliases: the names a parameter or a list entry had before a rename,
 *     so a file written with the old name still loads. A rename adds one
 *     and never removes one.
 *
 * Written from engines/known-ids.json and engines/aliases.json into
 * engines/state/fm1_known.c by tools/gen_known.py. The metadata export
 * (fm1_meta.h) carries both; stage E3's name tables read them.
 *
 * Plain C99, constant data. MIT licence, like the rest of this repository.
 */
#ifndef FM1_KNOWN_H_
#define FM1_KNOWN_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_known_id {
  const char *id;               /* "acid-bass" */
  const char *what;             /* "sound", "audio_fx", "midi_fx" or "mod" */
  const char *reason;           /* "gpl", "planned", "retired", or "list" (fm1_left_out) */
  const char *since;            /* a retired id: the version that retired it; else NULL */
} fm1_known_id_t;

extern const fm1_known_id_t fm1_known_ids[];   /* fm1_known_id_count rows, then a NULL row */
extern const size_t fm1_known_id_count;
/* The row for id, or NULL. */
const fm1_known_id_t *fm1_known_id_find(const char *id);

/* The modules this build's module list leaves out (FM1_MODULES,
 * engines/modules/catalogue.mk; src/registry.cc), reason "list": ids the
 * build could have had. fm1_left_out_count rows, then a NULL row. */
extern const fm1_known_id_t fm1_left_out[];
extern const size_t fm1_left_out_count;
extern const char *const fm1_modules_name;     /* the list's name: "all", "default", ... */
/* Why this build lacks id: its fm1_left_out row, else its fm1_known_ids row,
 * else NULL. */
const fm1_known_id_t *fm1_absent_find(const char *id);

enum { FM1_ALIAS_ENGINE = 1, FM1_ALIAS_MOD = 2 };
#define FM1_ALIAS_RETIRED (-2)

typedef struct fm1_alias {
  uint8_t owner;                /* FM1_ALIAS_ENGINE (an engine, effect or MIDI
                                   effect) or FM1_ALIAS_MOD (a modulation kind) */
  const char *id;               /* its id */
  uint16_t uid;                 /* the parameter's uid */
  int16_t entry;                /* -1: `name` is the parameter's old name;
                                   FM1_ALIAS_RETIRED (-2): a removed parameter's
                                   last name, `uid` its retired uid, which no
                                   table has (a file that names it reads by
                                   uid, as #UID); else the index of the list
                                   entry it is an old name of */
  const char *name;             /* the old name */
} fm1_alias_t;

extern const fm1_alias_t fm1_aliases[];        /* fm1_alias_count rows, then a NULL row */
extern const size_t fm1_alias_count;

#ifdef __cplusplus
}
#endif

#endif /* FM1_KNOWN_H_ */

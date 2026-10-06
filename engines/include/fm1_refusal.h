/* fm1_refusal.h -- why something was refused, as one set of codes with the
 * short words a person reads (notes/2026-10-06-web-editor.md §5, §6, stage
 * ED0):
 *
 *   - 1-9 are the state loader's, the same numbers as FM1_STATE_* in
 *     engines/state/fm1_state.h (NOT_LUNAR ... STOPPED);
 *   - 10 is a unit's own arena, too small for what was chosen;
 *   - 32 and on are a cable's, the matrix planner's reasons for a slot that
 *     is on but does not run (fm1_mod_slot_refusal in fm1_mod.h).
 *
 * A code never changes its number or its name; a new one takes a new
 * number. The words are what the FM-1's screen, the page and the editor
 * say, and a memory figure in them is a percentage of the FM-1's budget,
 * never bytes (owner, 2026-10-06). The metadata export (fm1_meta.h) carries
 * the table, so an editor shows C's words and never writes its own.
 *
 * Plain C99, constant data. MIT licence, like the rest of this repository.
 */
#ifndef FM1_REFUSAL_H_
#define FM1_REFUSAL_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
  FM1_REFUSE_OK = 0,
  /* The loader's (FM1_STATE_*, the same numbers). */
  FM1_REFUSE_NOT_LUNAR = 1,
  FM1_REFUSE_TOO_NEW = 2,
  FM1_REFUSE_UNKNOWN = 3,
  FM1_REFUSE_RATE = 4,          /* also choosing an engine that refuses the rate */
  FM1_REFUSE_RAM = 5,           /* also choosing an engine, an effect or the arp */
  FM1_REFUSE_NO_ROOM = 6,       /* also a rack or a matrix that is full */
  FM1_REFUSE_TOO_BIG = 7,
  FM1_REFUSE_BAD = 8,
  FM1_REFUSE_STOPPED = 9,
  /* A unit's. */
  FM1_REFUSE_ARENA = 10,        /* larger than the unit's own arena */
  /* A cable's: the planner's reasons for one slot (fm1_mod_slot_refusal). */
  FM1_REFUSE_NO_SOURCE = 32,    /* its source or VIA names nothing: an empty
                                   rack position, a port its kind lacks */
  FM1_REFUSE_NO_DEST = 33,      /* its destination names nothing */
  FM1_REFUSE_NOLOCK = 34,       /* the parameter rebuilds the voices */
  FM1_REFUSE_ENUM_NO_MOD = 35,  /* a list parameter without MOD */
  FM1_REFUSE_NO_MOD = 36,       /* a parameter that takes no modulation */
  FM1_REFUSE_VOICE_TO_MONO = 37,  /* per voice into one value for every voice */
  FM1_REFUSE_VOICE_TO_EFFECT = 38,  /* per voice into an effect or a master slot */
  FM1_REFUSE_UNIT_RESERVED = 39,  /* a unit kept for later */
  FM1_REFUSE_VOICE_FULL = 40,   /* more per-voice destinations than FM1_MOD_VDESTS */
  FM1_REFUSE_VOICE_ROOM = 41    /* the modules' per-voice copies do not fit one voice */
};

typedef struct fm1_refusal {
  uint8_t code;                 /* FM1_REFUSE_* */
  const char *name;             /* "RAM": stable, as the code */
  const char *of;               /* what refuses it, comma-separated: "load", "unit",
                                   "rack", "cable" */
  const char *words;            /* the headline: "Does not fit" */
  const char *detail;           /* the line under it, with {fills}: "needs {pct}% of
                                   RAM"; NULL when the words say it all */
} fm1_refusal_t;

/* Every code but OK, in number order. */
extern const fm1_refusal_t fm1_refusals[];
extern const size_t fm1_refusal_count;

/* code's row, or NULL. */
const fm1_refusal_t *fm1_refusal_find(unsigned code);

/* The words a known-but-absent id's reason gives (fm1_known.h's `reason`):
 * "gpl" "in the GPL build only", "planned" "not built yet", "retired"
 * "retired in {since}"; NULL for another reason. */
const char *fm1_refusal_known_words(const char *reason);

#ifdef __cplusplus
}
#endif

#endif /* FM1_REFUSAL_H_ */

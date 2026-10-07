/* fm1_app_state.h -- the virtual FM-1's whole state in and out of the state
 * core's records (stage A1; notes/2026-10-06-state-files.md §10, §12):
 * a collector that walks fm1_app_t and feeds the canonical JSON writer
 * (and, through it, the binary container), and an applier with two passes.
 *
 *   Save   project (every sound with every parameter, a pad kit's every pad
 *          through engine API v4's get_param, its level, inserts and MIDI
 *          effect; the master slots; FM6's loaded user voices; the rack and
 *          the matrix with their pattern data, flags and seed; the set, its
 *          song, scenes and key included; the session and the view), a sound
 *          (with the FM6 voice it plays and the modulation that touches only
 *          it), an effects chain (the master, or a sound's inserts), the mod
 *          rack, a clip, the set, or the device settings.
 *   Check  pass 1: the file is read whole and nothing changes. It says
 *          whether the load would be refused, and why (§10.3): NOT_LUNAR,
 *          TOO_NEW, UNKNOWN (unless "load without"), RATE, RAM (always:
 *          every instance at 44,118 Hz, ST6), NO_ROOM (unless "load
 *          without"), TOO_BIG, BAD; and the RAM figure as a percent of the
 *          FM-1's budget, the only figure the owner wants shown.
 *   Load   pass 1, then pass 2, which applies in §10.1's order and cannot
 *          fail once pass 1 passed, so a refused load changes nothing. A
 *          project replaces everything from fm1_app_init (the settings, the
 *          MASTER position and the host's callbacks are kept); every other
 *          kind merges into its target and remaps (§10.2).
 *
 * Rules this layer settles (the note's §22 and §21 left them to A1):
 *   - The project key has one home: the set's `key` line. A save writes
 *     `session.key` from it, so a mission check reads the key without
 *     parsing set lines; a load never applies `session.key`.
 *   - Unrouted tracks. A project's or a clip's set is loaded as it is:
 *     a track with no `rt` line stays on the MIDI channel the core gives it,
 *     because the file is the app's whole state and a save writes every
 *     route back. A `.movy1` set from elsewhere gets the app's start rule
 *     on top, the default-route rule (track 1 plays Sound 1 when no track is
 *     routed), as a new sequencer does.
 *   - One MIDI effect a sound (the panel's MIDI-FX slot); a file's effects
 *     in slots 2-4 are left out and counted as skipped.
 *
 * Sources are fm1_state.h's read callbacks, so RAM, a page's buffer and
 * flash look the same. The writer's memory (fm1_state_json_writer_size,
 * about 477 KB) and the buffers below are static: one save or load at a
 * time, on the thread that owns the app.
 *
 * C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_APP_STATE_H_
#define FM1_APP_STATE_H_

#include "fm1_app.h"
#include "fm1_state.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Load flags. */
#define FM1_APP_LOAD_WITHOUT 0x01u   /* "Load without ...": an engine or kind this build
                                        lacks leaves its unit empty (Sound 1 takes the
                                        default engine), modulation that does not fit and
                                        FM6 voices with no free slot are left out */
#define FM1_APP_LOAD_REPLACE 0x02u   /* a clip into a slot that holds one (the page asked) */
#define FM1_APP_LOAD_QUIET 0x04u     /* no banner on the device screen */

typedef struct fm1_app_load_opts {
  unsigned kind;      /* the kind the caller expects (FM1_STATE_*), or 0 for the file's */
  int into;           /* a sound file's sound unit (0-3); an effects file's: -1 the master,
                         0-3 that sound's inserts; a clip's track (0-7) */
  int slot;           /* a clip's slot (0-7) */
  unsigned flags;     /* FM1_APP_LOAD_* */
} fm1_app_load_opts_t;

typedef struct fm1_app_state_report {
  fm1_state_report_t r;      /* the codec's: code, kind, where, why, the name a refusal names */
  uint32_t ram;              /* the RAM figure after the load, at 44,118 Hz */
  uint32_t budget;           /* FM1_APP_RAM_BUDGET */
  uint16_t percent;          /* ram of budget, rounded up */
  uint8_t sounds, effects, mfx_on, modules, cables, voices;
  uint16_t tracks, clips, song;
  uint16_t left_out;         /* units, modules, cables and voices left out ("load without") */
  uint8_t set;               /* the load carried a set */
  uint8_t pad_;
  char message[160];         /* the page's line ("Needs 112% of the FM-1's RAM.") */
  char screen[2][28];        /* the device screen's banner lines */
} fm1_app_state_report_t;

void fm1_app_load_opts_init(fm1_app_load_opts_t *o);

/* Pass 1 only: 1 when the load would go ahead, 0 when it would be refused
 * (rep says why). The app is not changed, not even its screen. */
int fm1_app_state_check(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                        const fm1_app_load_opts_t *o, fm1_app_state_report_t *rep);
/* Pass 1, then pass 2: 1 when loaded, 0 when refused (nothing changed). The
 * screen shows the L1 banner ("LOADED", the name, "RAM 69%") or the
 * refusal, unless FM1_APP_LOAD_QUIET. */
int fm1_app_state_load(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                       const fm1_app_load_opts_t *o, fm1_app_state_report_t *rep);

/* Saves `kind` (FM1_STATE_PROJECT, _SOUND with arg the sound unit 0-3,
 * _FX with arg -1 for the master or 0-3 for that sound's inserts, _MODS,
 * _CLIP with arg track * 8 + slot, _SETTINGS, or _SET for the set's movy1
 * text) as canonical JSON, or with `binary` as the binary container (a
 * set: a SET container; the text itself with binary 0); binary 2 is the
 * container with no chunk deflated, the page's autosave: cheaper on the
 * audio thread, and loaded as any other (owner, 2026-10-06); binary 3 is
 * that container without where the panel is (the project's view and
 * its current sound), the one form the state hash
 * reads (fm1_edit_state_hash, the shadow Worker's `hash`). Out through put,
 * in pieces. 1, or 0 with rep's code (BAD for a kind or target with nothing
 * to save). */
int fm1_app_state_save(fm1_app_t *a, unsigned kind, int arg, int binary, fm1_put_t put, void *ctx,
                       fm1_state_report_t *rep);

/* JSON (canonical or not, any kind) to the binary container, through the
 * records, with no app: what a page's shadow Worker does so the audio
 * thread is handed binary and never parses JSON (stage ED13). 1, or 0 with
 * rep's code. */
int fm1_app_state_pack(fm1_src_read_t rd, void *rctx, fm1_put_t put, void *ctx, fm1_state_report_t *rep);

/* A source over a buffer (ctx: an fm1_app_state_mem_t). */
typedef struct fm1_app_state_mem {
  const uint8_t *b;
  uint32_t n;
} fm1_app_state_mem_t;
uint32_t fm1_app_state_mem_read(void *ctx, uint32_t off, uint8_t *buf, uint32_t n);

/* The scale ids the files use (FM1_KEY_* order), or NULL; and back (-1). */
const char *fm1_app_scale_id(int scale);
int fm1_app_scale_of(const char *id);

#ifdef __cplusplus
}
#endif

#endif /* FM1_APP_STATE_H_ */

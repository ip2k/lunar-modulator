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
 * flash look the same. Scratch is explicitly caller-owned below, or supplied
 * by the legacy host wrappers: one synchronous operation at a time, on the
 * thread that owns the app. The full codecs still need large workspaces;
 * external ownership alone does not make persistence fit native RAM.
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

/* Native builds may remove the legacy host default arena. Set consistently
 * for the state implementation; the old save/pack/check/load wrappers then
 * refuse before callbacks/output or app mutation. MIDI-map-only updates need
 * no large workspace. This does not expose persistence in the native UI. */
#ifndef FM1_APP_STATE_EXTERNAL_WORKSPACE
#define FM1_APP_STATE_EXTERNAL_WORKSPACE 0
#endif
#if FM1_APP_STATE_EXTERNAL_WORKSPACE != 0 && FM1_APP_STATE_EXTERNAL_WORKSPACE != 1
#error FM1_APP_STATE_EXTERNAL_WORKSPACE_must_be_0_or_1
#endif

typedef struct fm1_app_state_workspace {
  void *memory;
  size_t bytes;
} fm1_app_state_workspace_t;

enum {
  FM1_APP_STATE_WORK_SAVE = 1,
  FM1_APP_STATE_WORK_PACK = 2,
  FM1_APP_STATE_WORK_LOAD = 3,      /* both check and load */
  FM1_APP_STATE_WORK_PROJECT = 4    /* bounded offline PROJECT stage */
};
size_t fm1_app_state_workspace_size(unsigned operation);

/* Atomic mapping-only update; minimal project envelope with browser.midiMap. */
int fm1_app_midi_map_set(fm1_app_t *a, const uint8_t *bytes, size_t len, fm1_state_report_t *rep);

/* Load flags. */
#define FM1_APP_LOAD_WITHOUT 0x01u   /* "Load without ...": an engine or kind this build
                                        lacks leaves its unit empty (Sound 1 takes the
                                        default engine), modulation that does not fit and
                                        FM6 voices with no free slot are left out */
#define FM1_APP_LOAD_REPLACE 0x02u   /* a clip into a slot that holds one (the page asked) */
#define FM1_APP_LOAD_QUIET 0x04u     /* no banner on the device screen */
#define FM1_APP_LOAD_KEEP_TRANSPORT 0x08u   /* a project load that goes on playing: a running
                                        transport is carried over the load (fm1_seq.h,
                                        fm1_seq_transport_take and _put); the editor's A/B,
                                        its undo and its picks ask for it. Stopped stays stopped */
#define FM1_APP_LOAD_RESTORE_SOUND 0x10u /* same-project sound A/B: original rack/cable identities,
                                        not an external import. Unchanged modules keep their phase;
                                        a changed module shared with another destination is refused. */

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

/* Explicit workspace forms preserve the codecs, caps and atomicity above.
 * Supply at least workspace_size(operation) bytes at a 16-byte-aligned address.
 * Storage is borrowed exclusively until return, including every synchronous
 * rd/put callback. The put bytes are valid only during that callback; copy them
 * before return. No callback may retain workspace pointers, reenter a state
 * operation, or access live workspace except its supplied put bytes. Custom
 * rd/put contexts and their backing input/output allocations MUST NOT overlap
 * workspace; their opaque allocation extents cannot be inferred. Known
 * fm1_app_state_mem_read input overlap is checked, as are app/edit/engine arenas,
 * opts/report and the workspace descriptor. Invalid/busy storage refuses
 * before callbacks, output or app mutation. If report itself overlaps scratch,
 * it is left untouched. Calls from multiple threads require external exclusion.
 * Input must remain stable across all check/load passes, as with host wrappers.
 */
int fm1_app_state_save_with_workspace(fm1_app_t *a, unsigned kind, int arg, int binary,
                                      fm1_put_t put, void *ctx,
                                      const fm1_app_state_workspace_t *w, fm1_state_report_t *rep);
int fm1_app_state_pack_with_workspace(fm1_src_read_t rd, void *rctx, fm1_put_t put, void *ctx,
                                      const fm1_app_state_workspace_t *w, fm1_state_report_t *rep);
int fm1_app_state_check_with_workspace(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                                       const fm1_app_load_opts_t *o,
                                       const fm1_app_state_workspace_t *w, fm1_app_state_report_t *rep);
int fm1_app_state_load_with_workspace(fm1_app_t *a, fm1_src_read_t rd, void *rctx, uint32_t total,
                                      const fm1_app_load_opts_t *o,
                                      const fm1_app_state_workspace_t *w, fm1_app_state_report_t *rep);

/* Offline PROJECT-only staging, modes2/3 with current simulator metadata.
 * No production storage/UI binding. One synchronous call holds the same busy
 * guard through preflight, begin, replay, mandatory identity+semantic readback
 * and commit. Caller exclusively owns all app/registry/getter/sequence/storage
 * state throughout; no concurrent audio/control/ISR mutation is allowed.
 * This is structural file validation, not app-load/rate/RAM admission.
 *
 * begin returns1 only after opening an uncommitted stage; on0 it cleans itself.
 * write returns exactly n, read up to n (0 means no progress). Before commit,
 * failure invokes abort once. commit closes its handle and returns one of the
 * result codes below; INDETERMINATE requires rescan, never automatic retry or
 * abort. A physically completed commit can return INDETERMINATE.
 *
 * All callbacks are synchronous and may not reenter state operations, mutate
 * source/workspace/ops, retain pointers or alias workspace with their context
 * or backing allocations. Known pointers/objects are checked; opaque backing
 * extents remain caller responsibility. Source hashes are not locks/security.
 * Workspace uses workspace_size(WORK_PROJECT),16-aligned, disjoint from app,
 * engine/sequence/modulation arenas, descriptors/parameters, ops/context/report.
 * Report is also disjoint from those known live objects and the workspace
 * descriptor; an aliased report is left untouched on refusal. The full operation
 * is stopped-audio/offline only; no target pause/deadline is implied.
 *
 * Conditional pi32v2 component budget (see the native-project-replay note):
 * caller supplies the entire 65,536-byte arena; all persistent provider/reader/
 * manifest and phase scratch live there. Existing app, engine, modulation,
 * sequencer and editor allocations are borrowed, not included in that arena;
 * they remain separately charged baseline full-application RAM obligations.
 * With the measured -Oz profile and external workspace/engine arenas enabled,
 * the <=98,304-byte incremental budget additionally reserves 11,976 bytes for
 * the entire state TU, 36 other linked global/alignment bytes, 8,192 stack,
 * 8,192 safety and at most 4,096 bytes of additional backend/context RAM.
 * The stack reservation assumes <=4,480 in-library bytes, <=1,024 bytes for
 * each external getter/backend callback's COMPLETE callee stack, <=512 bytes
 * for the caller chain/locals, and <=1,024 combined same-stack IRQ/exception
 * bytes including nesting. No recursion/reentry into this operation is allowed.
 * Backend buffers/caches and ops/report storage outside the arena and caller
 * stack count against the 4,096 bytes; candidate file bytes cannot be retained
 * in RAM outside that allowance. No hidden heap or lazy allocation is covered.
 * These are caller admission requirements, not enforced limits or proof that
 * arbitrary callbacks/interrupts satisfy them. Different flags/modules/callers
 * need a fresh map and stack audit. This component result is not full-product
 * RAM fit or production storage/UI/hardware admission.
 */
enum { FM1_APP_STATE_REFUSED = 0, FM1_APP_STATE_COMMITTED = 1,
       FM1_APP_STATE_INDETERMINATE = 2 };
typedef struct fm1_app_state_stage {
  int (*begin)(void *ctx, uint32_t total);
  fm1_state_write_at_t write;
  fm1_src_read_t read;
  int (*commit)(void *ctx);
  void (*abort)(void *ctx);
} fm1_app_state_stage_t;
int fm1_app_state_project_stage(fm1_app_t *app, unsigned binary,
    const fm1_app_state_stage_t *stage, void *ctx,
    const fm1_app_state_workspace_t *workspace, fm1_state_report_t *report);
/* Queried total small provider/emitter/JSON-reader storage, excluding codec,
 * manifest and callback-owned storage. Target closure still requires a map. */
size_t fm1_app_state_project_aux_size(void);

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

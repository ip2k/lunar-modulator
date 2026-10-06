/* fm1_seq_host.h -- the sequencer's per-block host contract: one code path
 * from text or typed commands to split engine renders, shared by every host
 * of the fm1_seq core (fm1-render today; the virtual FM-1 and the firmware's
 * audio task next). engines/seq.md, "Host contract", has the block order.
 *
 * A host owns an event buffer and a sound engine. Per block of `frames`:
 *
 *   1. its own controls and live notes, straight to the engine;
 *   2. commands due now: fm1_seq_host_line (text) or fm1_seq_host_cmd
 *      (typed), each appending its events (a stop's note-offs...) at frame 0;
 *   3. live input: fm1_seq_host_note_in, fm1_seq_host_realtime;
 *   4. fm1_seq_host_advance(h, frames): the block's own events, after those;
 *   5. (a test harness logs ev[0..n) here);
 *   6. fm1_seq_host_dispatch(h, frames, block, &sink): renders the sound
 *      engine in pieces split at the frame of each event it receives, and
 *      empties the buffer (fm1_seq_host_dispatch_ticks also runs a
 *      control-rate hook, the modulation tick, at its own frames);
 *   7. effects, which are the host's own; the metronome's click
 *      (fm1_seq_click_mix, from the block's events); then the host's limiter
 *      and output.
 *
 * Lock targets (engine API v2). A lane's label (`synth:Timbre`) resolves to
 * the uid of the parameter it names when the lane is labelled (an `alabel`
 * through fm1_seq_host_line or fm1_seq_host_cmd), when a set is imported
 * (fm1_seq_host_import), and when the sound engine changes (dispatch sees a
 * new sink->engine, or fm1_seq_host_bind). Locks then go to that uid. A lock
 * on a NOLOCK parameter is refused and counted (locks_refused), and like a
 * lock on a lane that names nothing, it neither reaches the engine nor
 * splits the block. Labels stay text, so `movy1` sets keep `synth:<Name>`.
 * A stored uid is used only while its parameter has the name the label
 * gives, so a host that labels lanes or imports on the core directly, past
 * the bridge, still locks the right parameter: such a lane resolves afresh
 * at each lock until fm1_seq_host_bind stores it again.
 *
 * Rerouting. A `route` that moves a track elsewhere closes the track's
 * gates at once (the core's note-offs, among the block's inputs), and
 * dispatch sends a note-off from the block's inputs to where the track's
 * notes went at the last dispatch, not to its new route: every gate it
 * closes was opened in an earlier block, so its note sounds there. A note is
 * then never left hanging on a sound the track no longer plays (docs/15 S6,
 * found in its review). Everything else follows the route the track has at
 * dispatch. A host that reroutes past the bridge (fm1_seq_set_route) closes
 * no gate, so it does so only while nothing sounds (set-up, an import).
 *
 * MIDI effects (engine API v3, fm1_mfx_host.h). With h->mfx set, every
 * dispatch runs the chains first: the notes they take leave the block
 * (a hook still sees them, as notes that reach no engine), and their output
 * joins it, merged by frame (at one frame: the buffer's events but
 * note-ons, the chains' note-offs, the buffer's note-ons, the chains'
 * note-ons; chains in order), each to the slot of its chain (a single sink
 * takes chain 0's). With no chain active the calls are exactly those
 * without.
 *
 * Event room. Commands, live input and advance share one buffer per block,
 * and advance needs fm1_seq_min_events(lim) of it to keep every note-off,
 * Start and Stop (fm1_seq.h). So a host applies a command only while
 * fm1_seq_host_room(h) >= fm1_seq_cmd_max_events(lim) +
 * fm1_seq_min_events(lim), and holds it for the next block otherwise. The
 * bound is per op: a text line may hold several.
 *
 * C99, no heap, no stdio: the same object links into the desktop tools, the
 * WebAssembly module and firmware. MIT licence, like the rest of this
 * repository.
 */
#ifndef FM1_SEQ_HOST_H_
#define FM1_SEQ_HOST_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_seq.h"

#ifdef __cplusplus
extern "C" {
#endif

struct fm1_mfx;                 /* fm1_mfx_host.h */

/* Where a block's engine-routed events go: one sound engine instance. The
 * calls mirror fm1_engine_t's, with the host's context in place of `self`. */
typedef struct fm1_seq_sink {
  void *ctx;
  const fm1_engine_t *engine;   /* lane labels name parameters of this engine */
  void (*render)(void *ctx, float *out_lr, uint32_t frames);
  void (*note_on)(void *ctx, uint8_t note, uint8_t velocity);
  void (*note_off)(void *ctx, uint8_t note);
  void (*set_param)(void *ctx, uint16_t index, float value);
  void (*pitch_bend)(void *ctx, float semitones);   /* may be NULL; only a
                                   control-rate hook's writes use it */
} fm1_seq_sink_t;

/* A control-rate hook (the modulation runtime's tick, docs/16 MG1;
 * fm1_mod_host.h builds one). fm1_seq_host_dispatch_ticks runs it inside
 * the block at its own frames:
 *   begin   once, first: the block's length, the sink's engine (NULL with no
 *           sink) and the sequencer's tempo and transport (0 without one);
 *           returns the frame of the block's first tick (>= frames: none);
 *   event   every event of the buffer, in order, whatever its kind, track or
 *           route; to_engine says whether the sink receives it;
 *   lock    a lock (or a D6 revert) is about to set the sink engine's
 *           parameter `index` to `value`: the hook moves its base there and
 *           returns what to send (rule M1);
 *   tick    the tick at `frame`: its writes for the sink in *w (valid until
 *           the next call), how many as the result, and the next tick's
 *           frame in *next.
 * At one frame the order is docs/16's M6: note-offs and locks, the tick and
 * its writes, then note-ons. A tick with writes splits the render there; one
 * without splits nothing, so with nothing routed every render is what plain
 * dispatch gives. */
typedef struct fm1_seq_hook_write {
  uint16_t index;               /* the sink engine's parameter (not for a bend) */
  uint8_t bend;                 /* 1: pitch_bend(value) instead */
  uint8_t slot;                 /* the slot it is for (dispatch_slots_ticks);
                                   dispatch_ticks's one sink takes slot 0's */
  float value;
} fm1_seq_hook_write_t;

typedef struct fm1_seq_hook {
  void *ctx;
  uint32_t (*begin)(void *ctx, uint32_t frames, const fm1_engine_t *engine, uint32_t bpm_x100,
                    int playing);
  void (*event)(void *ctx, uint32_t frame, const fm1_seq_ev_t *e, int to_engine);
  float (*lock)(void *ctx, uint16_t index, float value);
  uint32_t (*tick)(void *ctx, uint32_t frame, const fm1_seq_hook_write_t **w, uint32_t *next);
  /* dispatch_slots_ticks only: lock, for the engine of slot `slot`. NULL:
   * slot 0's locks go to lock and the other slots' are sent as they are. */
  float (*lock_slot)(void *ctx, unsigned slot, uint16_t index, float value);
} fm1_seq_hook_t;

/* The most slots dispatch_slots_ticks serves (the rest are ignored). */
#define FM1_SEQ_HOST_HOOK_SLOTS 16u

typedef struct fm1_seq_host {
  fm1_seq_t *seq;
  fm1_seq_ev_t *ev;             /* the host's event buffer, cap entries */
  uint32_t cap;
  uint32_t n;                   /* events waiting for this block's dispatch */
  uint32_t max_n;               /* the most any block has held (after advance) */
  uint64_t notes_to_engine;     /* note-ons the sink received */
  uint64_t locks_to_engine;     /* locks the sink received as set_param */
  uint64_t locks_refused;       /* locks on a NOLOCK parameter, never sent */
  uint64_t splits;              /* render calls that start inside a block */
  const fm1_engine_t *engine;   /* what lane_uid is resolved against; NULL
                                   until the first bind or dispatch */
  uint16_t lane_uid[FM1_SEQ_MAX_TRACKS][FM1_SEQ_LANES];  /* each lane's target
                                   uid, 0 when its label names nothing */
  uint32_t cmd_n;               /* the events the block's inputs left before
                                   its advance (steps 2-3) */
  uint8_t dest[FM1_SEQ_MAX_TRACKS];  /* where each track's notes went at the
                                   last dispatch: its engine slot, 0x80 | its
                                   MIDI channel, FM1_SEQ_HOST_NO_DEST before
                                   the first (Rerouting, below) */
  fm1_seq_clock_t clock;        /* the core's clock as the last advance began:
                                   where that block's beats fall, for the
                                   effects (engine API v3, fm1_fx_host.h); all
                                   0 before the first advance or without a
                                   sequencer */
  struct fm1_mfx *mfx;          /* the MIDI effects in front of the sounds
                                   (fm1_mfx_host.h), or NULL: init sets it
                                   NULL, a host that has them sets it after */
} fm1_seq_host_t;

#define FM1_SEQ_HOST_NO_DEST 0xFFu

/* Binds a host to an instance and a buffer; every counter starts at 0, and
 * no engine is bound yet. */
void fm1_seq_host_init(fm1_seq_host_t *h, fm1_seq_t *seq, fm1_seq_ev_t *ev, uint32_t cap);

/* Makes e the engine lane labels resolve against and resolves every lane.
 * Dispatch calls it when its sink's engine differs from the bound one. */
void fm1_seq_host_bind(fm1_seq_host_t *h, const fm1_engine_t *e);

/* fm1_seq_import_movy1 through the bridge: replaces the set, then resolves
 * every lane against the bound engine. Returns the import's result. */
int fm1_seq_host_import(fm1_seq_host_t *h, const char *txt, size_t len);

/* The uid a lane's locks go to: 0 when the lane is unlabelled or its label
 * names no parameter of the bound engine. Always the label's own parameter,
 * even for a label set past the bridge (above). A NOLOCK parameter's uid is
 * returned, so a UI can say why its locks are refused. */
uint16_t fm1_seq_host_lane_uid(const fm1_seq_host_t *h, uint8_t track, uint8_t lane);

/* "rt XX" (XX one of F8 FA FB FC, either case; spaces or tabs around it) in
 * ops[0..len): the MIDI realtime status byte, else 0. */
unsigned fm1_seq_realtime_status(const char *ops, size_t len);

/* One script or UI line: realtime input ("rt FA", fm1_seq_realtime_in at
 * frame 0) or Movy ops (fm1_seq_apply_text). Returns the events written. */
uint32_t fm1_seq_apply_line(fm1_seq_t *s, const char *ops, size_t len, fm1_seq_ev_t *out,
                            uint32_t cap);

/* Inputs before advance. Each appends its events at ev[n..] (frame 0 of the
 * coming block) and returns how many. A line or command that labels a lane
 * (`alabel`) resolves the label to a uid as it is applied. */
uint32_t fm1_seq_host_line(fm1_seq_host_t *h, const char *ops, size_t len);
uint32_t fm1_seq_host_cmd(fm1_seq_host_t *h, const fm1_seq_cmd_t *c);
uint32_t fm1_seq_host_realtime(fm1_seq_host_t *h, uint8_t status);
/* Live input for recording and Capture, at frame 0; velocity 0 is a
 * note-off. It causes no events itself. */
void fm1_seq_host_note_in(fm1_seq_host_t *h, uint8_t track, uint8_t pitch, uint8_t vel);

/* Free entries in the buffer. */
uint32_t fm1_seq_host_room(const fm1_seq_host_t *h);

/* Where event k of the buffer goes (Rerouting, below): its track's engine
 * slot, 0x80 | its MIDI channel, or FM1_SEQ_HOST_NO_DEST. */
uint8_t fm1_seq_host_dest(const fm1_seq_host_t *h, uint32_t k);

/* The most events one command can cause: every gate's note-off, a base
 * revert per lane of every track (D6), and a Start or Stop. 129 at 8 tracks
 * and 64 gates. */
uint32_t fm1_seq_cmd_max_events(const fm1_seq_limits_t *lim);

/* Runs the block (fm1_seq_advance) into the room left after the inputs,
 * keeping the clock as it began in h->clock. Returns n, every event the
 * block holds, for a log. */
uint32_t fm1_seq_host_advance(fm1_seq_host_t *h, uint32_t frames);

/* Plays the block's events into `sink` and empties the buffer. Only
 * note-ons, note-offs and locks of tracks routed to the engine reach it;
 * clicks, clock, Start, Stop and MIDI-routed tracks are the host's to send
 * elsewhere (or log). A lock goes to the parameter whose uid its lane
 * resolved to (binding sink->engine first if it is not the bound one); a
 * lock on a lane that names no parameter of sink->engine is skipped, one on
 * a NOLOCK parameter is refused and counted, and neither splits the block.
 * The engine renders
 * `block` (frames stereo frames) in pieces split at each event's frame
 * (clamped to the block), and receives the events in emission order: at one
 * frame, note-offs, locks, note-ons. A NULL sink only empties the buffer. */
void fm1_seq_host_dispatch(fm1_seq_host_t *h, uint32_t frames, float *block,
                           const fm1_seq_sink_t *sink);

/* Dispatch with a control-rate hook (above), which runs even with a NULL
 * sink (its writes then go nowhere). A NULL hook is plain dispatch. A host
 * with no sequencer may run it on a bridge initialised with seq NULL and no
 * buffer: no events, only the hook's ticks and the split renders. The hook
 * serves one sink, which takes the writes for slot 0; several sound units
 * take theirs through fm1_seq_host_dispatch_slots_ticks below. */
void fm1_seq_host_dispatch_ticks(fm1_seq_host_t *h, uint32_t frames, float *block,
                                 const fm1_seq_sink_t *sink, const fm1_seq_hook_t *hook);

/* Several sound units (the virtual FM-1's multi-sound, docs/15 §3.16):
 * one engine slot per sound unit, and a track routed to the engine plays the
 * slot its route index names (`route t 1 k`: slot k). fm1_seq_host_dispatch
 * above is the one-unit case, which ignores the index. */
typedef struct fm1_seq_slot {
  const fm1_seq_sink_t *sink;   /* NULL: an empty slot; its tracks' events reach nothing */
  float *block;                 /* where the slot's sound renders, frames stereo frames */
} fm1_seq_slot_t;

/* Plays the block's events into slots[0..n): each slot's sink renders its
 * own block in pieces split at the frames of its own tracks' events only,
 * and receives those events in emission order, exactly as dispatch does for
 * one sink. Slots are played in index order, all of slot 0's calls first. A
 * lock goes to the parameter its lane names on that slot's engine (the
 * stored uid while it still names that parameter there, else resolved
 * afresh); slot 0's engine is the bound one, as dispatch binds its sink's.
 * Events of a track routed past slot n - 1 or to an empty slot are dropped
 * and split nothing. The counters add up over the slots. Empties the
 * buffer. */
void fm1_seq_host_dispatch_slots(fm1_seq_host_t *h, uint32_t frames, const fm1_seq_slot_t *slots,
                                 unsigned n);

/* dispatch_slots with a control-rate hook (docs/16 MG3: modulation over
 * several sound units). One pass over the block: the hook's begin gets
 * slot 0's engine, its event every event (to_engine: some slot's sink
 * receives it), and its ticks run at their frames as in dispatch_ticks;
 * each write goes to the slot it names (fm1_seq_hook_write_t.slot), whose
 * render is split there, and a lock on slot s goes through lock_slot. Each
 * slot's sink gets its calls in exactly the order dispatch_ticks would give
 * it alone, so its output is the same; the calls of different slots
 * interleave. At most FM1_SEQ_HOST_HOOK_SLOTS slots. A NULL hook is
 * dispatch_slots, slot after slot. */
void fm1_seq_host_dispatch_slots_ticks(fm1_seq_host_t *h, uint32_t frames,
                                       const fm1_seq_slot_t *slots, unsigned n,
                                       const fm1_seq_hook_t *hook);

/* The metronome's click (owner decision O11, 2026-10-02; docs/15 S6), so
 * that every host sounds the core's CLICK events the same way. A voice of
 * integers only: no libm and no rounding of its own, so each build and
 * each host adds the same bits. A CLICK event starts a click at its own
 * frame, while the metronome is on (`metro 1`; the count-in's clicks too,
 * and only then): a triangle tone of rate / 2000 half-periods (about 1 kHz;
 * rate / 3200, about 1.7 kHz and louder, on a downbeat) under a quadratic
 * decay of rate / 50 frames (20 ms), added to both channels of the block
 * after the host's effects and before its limiter. A new click restarts
 * the voice; a click outlives the block it starts in and `metro 0`. */
typedef struct fm1_seq_click {
  uint32_t len;                 /* a click's length in frames, rate / 50 */
  uint16_t half[2];             /* its tone's half-period in frames: plain, downbeat */
  uint32_t pos;                 /* frames into the click sounding; len when none */
  uint8_t accent;               /* the click sounding is a downbeat's */
  uint8_t reserved[3];
  uint32_t clicks;              /* clicks started, for logs and tests */
} fm1_seq_click_t;

/* A silent voice for `rate` frames a second. */
void fm1_seq_click_init(fm1_seq_click_t *c, uint32_t rate);

/* Adds the clicks of one block to lr (frames stereo frames, interleaved):
 * ev[0..n) are the block's events as fm1_seq_host_advance left them (the
 * buffer keeps them after dispatch), s the instance whose metronome gates
 * them. A NULL s sounds no new click. */
void fm1_seq_click_mix(fm1_seq_click_t *c, const fm1_seq_t *s, const fm1_seq_ev_t *ev, uint32_t n,
                       uint32_t frames, float *lr);

/* The parameter a lane label names: the part after the last ':' ("synth:
 * Timbre" names Timbre), compared without ASCII case, with '_' standing for
 * a space ("synth:Env_Pitch" names Env Pitch: a label is one token of a
 * script or a set, docs/15 S8). -1 if none. */
int fm1_seq_lane_param(const fm1_engine_t *e, const char *label);

/* The label a lock UI gives a lane for parameter p: "synth:" and p's name,
 * each space written as '_', so fm1_seq_lane_param reads it back as p. At
 * most size - 1 bytes and a NUL (FM1_SEQ_LABEL_MAX holds every name of 12
 * characters or fewer); returns the length written. */
size_t fm1_seq_lane_label_for(const fm1_param_t *p, char *buf, size_t size);

/* The uid of that parameter (fm1_engine.h, API v2), or 0 if none. */
uint16_t fm1_seq_lane_uid(const fm1_engine_t *e, const char *label);

/* A 7-bit lock value on p's range: linear for FLOAT (v / FM1_SEQ_VAL_MAX of
 * the way from min to max), on the LOG law for a LOG parameter (position
 * v / FM1_SEQ_VAL_MAX, fm1_engine.h: min x (max / min)^(v / 127), exactly
 * min and max at the ends), Movy's planned bins floor(v * n / 128) for an
 * ENUM of n values. */
float fm1_seq_lock_value(const fm1_param_t *p, unsigned v);

/* The inverse of fm1_seq_lock_value (docs/15 S8): the 7-bit value of x on
 * p's range. FLOAT: (x - min) / (max - min) of 127 (LOG: its position,
 * fm1_param_pos), rounded half up, so
 * fm1_seq_value7(p, fm1_seq_lock_value(p, v)) == v for every v in 0..127.
 * ENUM: the lowest v whose bin is x's entry (rounded to the nearest), so
 * fm1_seq_lock_value(p, fm1_seq_value7(p, e)) == e for every entry e of a
 * list of at most 128 (every one registered: Six-Op's 96 patches are the
 * most). Out of range clamps; NaN reads as the default. No libm. */
unsigned fm1_seq_value7(const fm1_param_t *p, float x);

/* A knob detent on a lane's parameter (owner decision O14): `delta` steps on
 * p's 7-bit grid from v, clamped, as the value a lock or a base takes. One
 * step is 1/127 of the range for FLOAT (of its octaves for LOG), and one
 * entry, the bins' grid, for ENUM. */
unsigned fm1_seq_value7_step(const fm1_param_t *p, unsigned v, int delta);

/* Routing default. The core starts every track on USB-MIDI channel
 * t mod 16 + 1, and an import puts every route back there before it reads
 * the set's own `rt` lines. 1 while every track is still there. */
int fm1_seq_routes_default(const fm1_seq_t *s);

/* The default-route rule (engines/seq.md, Host contract): when no track is
 * routed (fm1_seq_routes_default) and the host has a sound engine, track 0
 * plays it. A host applies it after create, reset or an import, unless it
 * routes tracks itself (fm1-render's --route). fm1-render and the virtual
 * FM-1 both use it. Returns 1 when it routed track 0. */
int fm1_seq_default_route(fm1_seq_t *s, int have_engine);

#ifdef __cplusplus
}
#endif

#endif /* FM1_SEQ_HOST_H_ */

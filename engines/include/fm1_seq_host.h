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
 *      empties the buffer;
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

/* Where a block's engine-routed events go: one sound engine instance. The
 * calls mirror fm1_engine_t's, with the host's context in place of `self`. */
typedef struct fm1_seq_sink {
  void *ctx;
  const fm1_engine_t *engine;   /* lane labels name parameters of this engine */
  void (*render)(void *ctx, float *out_lr, uint32_t frames);
  void (*note_on)(void *ctx, uint8_t note, uint8_t velocity);
  void (*note_off)(void *ctx, uint8_t note);
  void (*set_param)(void *ctx, uint16_t index, float value);
} fm1_seq_sink_t;

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
} fm1_seq_host_t;

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

/* The most events one command can cause: every gate's note-off, a base
 * revert per lane of every track (D6), and a Start or Stop. 129 at 8 tracks
 * and 64 gates. */
uint32_t fm1_seq_cmd_max_events(const fm1_seq_limits_t *lim);

/* Runs the block (fm1_seq_advance) into the room left after the inputs.
 * Returns n, every event the block holds, for a log. */
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
 * Timbre" names Timbre), compared without ASCII case. -1 if none. */
int fm1_seq_lane_param(const fm1_engine_t *e, const char *label);

/* The uid of that parameter (fm1_engine.h, API v2), or 0 if none. */
uint16_t fm1_seq_lane_uid(const fm1_engine_t *e, const char *label);

/* A 7-bit lock value on p's range: linear for FLOAT (v / FM1_SEQ_VAL_MAX of
 * the way from min to max), Movy's planned bins floor(v * n / 128) for an
 * ENUM of n values. */
float fm1_seq_lock_value(const fm1_param_t *p, unsigned v);

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

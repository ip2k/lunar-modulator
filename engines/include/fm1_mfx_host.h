/* fm1_mfx_host.h -- MIDI effects (engine API v3, FM1_KIND_MIDI_FX) on the
 * sequencer's host bridge (fm1_seq_host.h): a chain of up to FM1_MFX_SLOTS
 * effects in front of each sound unit, one code path that fm1-render and
 * the virtual FM-1 share, so an arpeggio is the same in both, at any block
 * size (DEVELOPERS.md, "MIDI effects"; docs/13 M2).
 *
 * Where the notes go. A chain is active while one of its effects is on.
 * Then every note headed for its sound goes through it:
 *   - live notes (the keys, MIDI IN, fm1-render's --note): the host offers
 *     each to fm1_mfx_live_note before it plays it, and plays it itself
 *     only when the chain did not take it; a taken note waits for the next
 *     block, at its first frame, as a note the host plays between blocks
 *     sounds there;
 *   - the sequencer's notes for the sound: the bridge's dispatch takes them
 *     out of the block (they still reach a control-rate hook, as notes that
 *     reach no engine) and feeds them to the chain at their frames.
 * The chain's output reaches the sound at its own frames, merged into the
 * block's events as the sequencer's notes are (a sound's render splits
 * there; a hook sees them as notes on the sound, track FM1_MFX_TRACK + the
 * chain). A note-off follows its note-on: it goes into the chain when the
 * chain took the note-on, else straight to the sound, so a chain switched on
 * or off while notes sound leaves none hanging.
 *
 * The recording rule (owner, 2026-10-05): the sequencer records what was
 * played. A host gives its live input to the sequencer as before, and the
 * chain only shapes what the sound hears, so a recorded part plays through
 * the chain again on playback.
 *
 * Time. Each block's clock ticks (96 to the quarter note) come from the
 * sequencer's integer clock as the block began (fm1_seq_host_t.clock): its
 * running sum crosses its threshold at the frame where it services a tick
 * while it plays, and keeps running at the set tempo while it is stopped,
 * so a chain free-runs on the same grid. A clock off that grid (following
 * an external MIDI clock, or Movy's compat mode) puts the block's ticks at
 * its first frame. A bridge without a sequencer runs the stage's own sum at
 * fm1_mfx_set_tempo's tempo. The sequencer's Start reaches every effect as
 * RESET, its Stop as FLUSH, each at its frame. So the ticks, and with them
 * every effect's output, are the same at any block size.
 *
 * Bypass and removal flush at once: the effect gets FLUSH and PANIC between
 * blocks, and the note-offs that come out (through the effects after it)
 * go to the host's fm1_mfx_sink_t, which plays them as live note-offs. A
 * host does the same with fm1_mfx_flush before it changes or empties the
 * sound, and on a panic.
 *
 * Memory: fixed, in the struct; the effects' instances are the host's. No
 * heap, no stdio, no libm. MIT licence, like the rest of this repository.
 */
#ifndef FM1_MFX_HOST_H_
#define FM1_MFX_HOST_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_seq_host.h"

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_MFX_CHAINS 4u      /* sound units with a chain (the virtual FM-1's four) */
#define FM1_MFX_SLOTS 4u       /* effects in a chain (owner, 2026-10-05) */
#define FM1_MFX_LIVE 64u       /* live notes a chain queues for one block */
#define FM1_MFX_IN 256u        /* events one effect takes in one block */
#define FM1_MFX_OUT FM1_MIDI_FX_OUT_MIN   /* room for one effect's output in one block */
#define FM1_MFX_TICKS 64u      /* ticks one block holds: at most one a frame */
#define FM1_MFX_TRACK 0xE0u    /* a chain's output in the block, as an fm1_seq_ev_t:
                                  track FM1_MFX_TRACK + the chain */
#define FM1_MFX_TAKEN 0x80u    /* fm1_seq_ev_t.kind, during dispatch only: a note
                                  of the sequencer's that a chain took */

typedef struct fm1_mfx_slot {
  const fm1_midi_fx_t *fx;     /* NULL: an empty slot */
  void *self;                  /* its instance, the host's memory */
  uint8_t on;                  /* 0: bypassed, events pass it unchanged */
  uint8_t reserved[3];
} fm1_mfx_slot_t;

typedef struct fm1_mfx_chain {
  fm1_mfx_slot_t slot[FM1_MFX_SLOTS];
  fm1_midi_ev_t live[FM1_MFX_LIVE];   /* live notes for the next block, at frame 0 */
  uint32_t n_live;
  uint8_t held_live[128];      /* live notes the chain took that still owe it a
                                  note-off, by key */
  uint8_t held_seq[128];       /* ...and the sequencer's: kept apart, so a note-off
                                  goes where its own note-on went even when a
                                  key and a track share a pitch */
  uint8_t owed[16];            /* note-offs it took with no room left: the next
                                  block's first events */
  fm1_midi_ev_t out[FM1_MFX_OUT];     /* the last block's output, ascending */
  uint32_t n_out;
} fm1_mfx_chain_t;

typedef struct fm1_mfx_stats {
  uint64_t blocks;             /* blocks with an active chain */
  uint64_t ticks;              /* ticks given to the effects */
  uint64_t notes_in;           /* note events the chains took */
  uint64_t notes_out;          /* note events the chains sent to the sounds */
  uint64_t direct;             /* note-ons an active chain had no room for: they
                                  went straight to the sound, as did their offs */
  uint64_t deferred_offs;      /* note-offs held for the next block (no room) */
  uint64_t dropped;            /* chain outputs past FM1_MFX_OUT (never a note-off
                                  of an effect that keeps the contract) */
} fm1_mfx_stats_t;

typedef struct fm1_mfx {
  fm1_mfx_chain_t chain[FM1_MFX_CHAINS];
  uint32_t rate;               /* frames a second: the clock without a sequencer */
  uint32_t bpm_x100;           /* that clock's tempo */
  uint64_t accum;              /* its running sum, below rate x 6000 */
  uint8_t key_root, key_scale; /* the project key (fm1_midi_fx_ctx_t) */
  uint8_t running;             /* the transport as the last block began */
  uint8_t reserved;
  uint16_t ticks[FM1_MFX_TICKS];   /* the last block's tick frames */
  uint32_t n_ticks;
  fm1_midi_ev_t a[FM1_MFX_IN], b[FM1_MFX_IN];   /* one effect's input and output */
  fm1_mfx_stats_t stats;
} fm1_mfx_t;

/* Where a flush's note-offs go: the sound of chain `chain`, as a live
 * note-off (the host's own notes go there the same way). */
typedef struct fm1_mfx_sink {
  void *ctx;
  void (*note_off)(void *ctx, unsigned chain, uint8_t key);
} fm1_mfx_sink_t;

/* Every chain empty, the clock at 120 BPM for `rate` frames a second, the
 * project key C major. A host then sets h->mfx = m on its bridge. */
void fm1_mfx_init(fm1_mfx_t *m, uint32_t rate);

/* Puts effect fx, whose instance the host created in `self`, in slot s of
 * chain c, on (`on` 1) or bypassed (0). What the slot held first gets PANIC
 * (its note-offs to `sink`, which may be NULL only when nothing sounds).
 * fx NULL empties the slot. 1, or 0 for a slot out of range or an fx that
 * is no MIDI effect (nothing changes). */
int fm1_mfx_set(fm1_mfx_t *m, unsigned c, unsigned s, const fm1_midi_fx_t *fx, void *self, int on,
                const fm1_mfx_sink_t *sink);

/* Bypass (0) or on (1). Bypassing flushes as fm1_mfx_set does; a chain
 * left with no effect on forgets every note it took. 1, or 0 out of range
 * or for an empty slot. */
int fm1_mfx_set_on(fm1_mfx_t *m, unsigned c, unsigned s, int on, const fm1_mfx_sink_t *sink);

int fm1_mfx_is_on(const fm1_mfx_t *m, unsigned c, unsigned s);
const fm1_mfx_slot_t *fm1_mfx_slot(const fm1_mfx_t *m, unsigned c, unsigned s);

/* Whether chain c has an effect on: then the notes for its sound go through it. */
int fm1_mfx_active(const fm1_mfx_t *m, unsigned c);

/* A live note for chain c's sound (velocity 0 is a note-off). 1 when the
 * chain took it (it reaches the chain at the next block's first frame); 0
 * when the host plays it itself. */
int fm1_mfx_live_note(fm1_mfx_t *m, unsigned c, uint8_t key, uint8_t velocity);

/* FLUSH (panic 0) or PANIC (1) every effect of chain c that is on, now,
 * between blocks: the note-offs that come out go to `sink`. PANIC also
 * drops the chain's queued live notes and the notes it took. */
void fm1_mfx_flush(fm1_mfx_t *m, unsigned c, int panic, const fm1_mfx_sink_t *sink);

/* The clock's tempo without a sequencer (20.00..300.00 BPM, clamped). */
void fm1_mfx_set_tempo(fm1_mfx_t *m, uint32_t bpm_x100);

/* The project key: root 0..11 (C..B), scale FM1_KEY_*. */
void fm1_mfx_set_key(fm1_mfx_t *m, unsigned root, unsigned scale);

/* The bridge's side (seq_host.c's dispatch calls it once a block, before
 * any render; `single` when it serves one sink, which takes chain 0): the
 * block's ticks, its notes for each active chain, every effect's process(),
 * and each chain's output in m->chain[c].out. Marks the sequencer's notes
 * it took with FM1_MFX_TAKEN in h->ev (dispatch clears the marks). */
void fm1_mfx_block(fm1_mfx_t *m, fm1_seq_host_t *h, uint32_t frames, int single);

/* Chain c's output from the last block (valid until the next), for a log. */
const fm1_midi_ev_t *fm1_mfx_output(const fm1_mfx_t *m, unsigned c, uint32_t *n);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MFX_HOST_H_ */

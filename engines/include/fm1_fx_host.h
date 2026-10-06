/* fm1_fx_host.h -- engine API v3's effect extension on the host side
 * (fm1_engine.h, fm1_fx_ext_t): one code path that fm1-render and the
 * virtual FM-1 share, so an effect hears the same tempo, beats and
 * transport events from both, at any block size.
 *
 * A host renders each effect over the block in pieces of its own (split at
 * the modulation's writes); for each piece it calls fm1_fx_render, which
 * calls a v2 effect's render once, exactly as before, and an effect with
 * render_ext in pieces split further where it asked (FM1_FX_WANT_TEMPO:
 * at the first frame of each beat; FM1_FX_WANT_TRANSPORT: at the
 * sequencer's Start and Stop), with the extension filled for each piece.
 *
 * Beats come from the sequencer's own integer clock as the block began
 * (fm1_seq_host_t.clock, fm1_seq_clock_t): beat k starts at the frame
 * where the sequencer services master tick 96 k, and beat and phase at a
 * frame are exact rationals of its integers, so a piece starting at a
 * given frame gets the same bits whatever the block size. A clock whose
 * ticks are not on that grid (following an external MIDI clock, Movy's
 * compat mode) gives the position at the block's start and no beat splits.
 *
 * The key is NULL in this stage: the side-chain stage gives the block a
 * key source (notes/2026-10-02-delay-reverb-eq-gates-options.md §7.3).
 *
 * C99, no heap, no stdio, no libm. MIT licence, like the rest of this
 * repository.
 */
#ifndef FM1_FX_HOST_H_
#define FM1_FX_HOST_H_

#include <stdint.h>

#include "fm1_engine.h"
#include "fm1_seq.h"

#ifdef __cplusplus
extern "C" {
#endif

/* What an effect hears about one block, the same for every effect in it. */
typedef struct fm1_fx_block {
  const fm1_seq_clock_t *clock; /* the sequencer's clock as the block began
                                   (fm1_seq_host_t.clock), or NULL for none */
  const fm1_seq_ev_t *ev;       /* the block's events, for Start and Stop; NULL
                                   with n_ev 0 for none */
  uint32_t n_ev;
  uint32_t frames;              /* the block's length */
  float bpm;                    /* the tempo with no clock (a host's own) */
} fm1_fx_block_t;

/* The extension for a piece that starts at `frame` of the block: tempo,
 * position and running; no key, no events. */
void fm1_fx_block_ext(const fm1_fx_block_t *b, uint32_t frame, fm1_fx_ext_t *ext);

/* The first frame in [from, to) at which a beat starts (the sequencer
 * services a master tick that is a multiple of 96 there), or `to` if none
 * does, or the clock is stopped or off the grid. */
uint32_t fm1_fx_block_next_beat(const fm1_fx_block_t *b, uint32_t from, uint32_t to);

/* Renders frames [from, to) of a block through effect e (lr is the block's
 * first frame, interleaved stereo; from < to <= b->frames): render for an
 * engine without render_ext, called once, bit for bit as a v2 host does;
 * else render_ext in pieces split at the beats and transport events the
 * effect asked for, each piece's events at its first frame. Returns the
 * number of calls made. A NULL b is a block with no clock, no events and
 * 120 BPM. */
uint32_t fm1_fx_render(const fm1_engine_t *e, void *self, float *lr, uint32_t from, uint32_t to,
                       const fm1_fx_block_t *b);

#ifdef __cplusplus
}
#endif

#endif /* FM1_FX_HOST_H_ */

/* fm1_mod_host.h -- the modulation runtime (fm1_mod.h) on the sequencer's
 * host bridge (fm1_seq_host.h): one glue struct that makes a runtime a
 * control-rate hook for fm1_seq_host_dispatch_ticks.
 *
 * Per block a host does what fm1_seq_host.h says, with these changes:
 *   - live notes on the sound also go to fm1_mod_live_note (before
 *     dispatch, at the block's start);
 *   - a knob or --param-at on a sound, effect or host parameter goes
 *     through fm1_mod_set_base, and the host sends what it returns; so does
 *     the MIDI bend, as the base of HOST PITCH;
 *   - dispatch is fm1_seq_host_dispatch_ticks(h, n, block, sink, &glue.hook),
 *     which feeds the runtime every event at its frame (notes on the sound
 *     for VEL, NOTE, KEY and TRIG; every track's notes for SEQ1-8; the
 *     clock, Start and Stop), runs each tick at its frame, and splits the
 *     sound's render only where a tick writes to it (set_param, or
 *     pitch_bend for HOST PITCH);
 *   - writes to the effects and to HOST AMP go to glue.write, with their
 *     frame in the block; the host renders each effect split at its own
 *     writes and applies AMP (fm1_mod_ramp_t) before the limiter.
 * With no slot on, nothing is written and nothing is split, so the audio
 * is byte for byte what plain dispatch gives.
 *
 * The glue lives in host memory and may hold pointers; the runtime's own
 * state never does. C99, no heap, no stdio. MIT licence. */
#ifndef FM1_MOD_HOST_H_
#define FM1_MOD_HOST_H_

#include "fm1_mod.h"
#include "fm1_seq_host.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_mod_glue {
  fm1_mod_t *mod;
  const fm1_engine_t *sound;    /* what FM1_MOD_SOUND is bound to; a sink with
                                   another engine rebinds it at begin */
  void *ctx;                    /* for the two callbacks */
  /* An effect or AMP write at `frame` of the block; may be NULL. */
  void (*write)(void *ctx, uint32_t frame, const fm1_mod_write_t *w);
  /* After each tick, at its frame (a log); may be NULL. */
  void (*ticked)(void *ctx, uint32_t frame, const fm1_mod_write_t *w, uint32_t n);
  fm1_seq_hook_t hook;          /* pass &glue.hook to dispatch_ticks */
  fm1_seq_hook_write_t w[FM1_MOD_UNIT_PARAMS + 1u];   /* a tick's sound writes */
  uint64_t sound_writes, other_writes;
} fm1_mod_glue_t;

/* Fills g for runtime m, whose FM1_MOD_SOUND is bound to `sound` (NULL for
 * none). The callbacks start NULL; set them after. */
void fm1_mod_glue_init(fm1_mod_glue_t *g, fm1_mod_t *m, const fm1_engine_t *sound);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_HOST_H_ */

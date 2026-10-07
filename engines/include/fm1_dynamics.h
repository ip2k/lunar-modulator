/* fm1_dynamics.h -- what the Limiter (src/fx_limit.cc, engine id "limit")
 * and Squash (src/fx_squash.cc, engine id "squash") expose beyond the engine
 * API: the gain each is applying now, for the editor's gain-reduction
 * read-outs (notes/2026-10-06-web-editor.md §12, stage ED5a), as
 * fm1_comp_reduction_db does for Comp. Read-only taps on state each effect
 * already keeps: they change no audio, no state and no instance size.
 *
 * Plain C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_DYNAMICS_H_
#define FM1_DYNAMICS_H_

#ifdef __cplusplus
extern "C" {
#endif

/* The gain the Limiter's envelope is applying, 1 for none and under 1 when
 * it cuts: the lower of its two channels, from the envelope that is
 * running (instant attack, one-pole release; Lookahead 0's has its own).
 * Finite, in (0, 1]. 1 before the first render; NULL reads 1. `instance` is
 * the handle fm1_engine_limit.create returned. Read it on the audio task,
 * between renders. */
float fm1_limit_gain(const void *instance);

/* The gain Squash's sounding Type applied to the last frame, the lower of
 * its two channels, before Output and Mix. Above 1 where the Type lifts
 * (Mu's makeup, Split's lift); a read-out shows the cut only. 1 before the
 * first render; NULL reads 1. `instance` is the handle fm1_engine_squash
 * .create returned. Read it on the audio task, between renders. */
float fm1_squash_gain(const void *instance);

#ifdef __cplusplus
}
#endif

#endif /* FM1_DYNAMICS_H_ */

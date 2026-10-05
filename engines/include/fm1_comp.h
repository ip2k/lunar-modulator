/* fm1_comp.h -- what the Comp effect (src/fx_comp.cc, engine id "comp")
 * exposes beyond the engine API: its gain reduction, for a later modulation
 * source to read (docs/16 §3.7, the Duck kind's REDUCTION output, and
 * engines/README.md, "Comp"). Not part of fm1_engine_t: the engine API is
 * unchanged.
 *
 * Plain C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_COMP_H_
#define FM1_COMP_H_

#ifdef __cplusplus
extern "C" {
#endif

/* The gain reduction Comp applied to the last frame it rendered, in dB:
 * 0 or more, finite, already smoothed by Attack and Release (so it can be
 * read once per block or per modulation tick without aliasing). Makeup is
 * not included. 0 before the first render. `instance` is the handle
 * fm1_engine_comp.create returned (a host checks the engine is "comp"
 * first); NULL reads 0. Read it on the audio task, between renders. */
float fm1_comp_reduction_db(const void *instance);

#ifdef __cplusplus
}
#endif

#endif /* FM1_COMP_H_ */

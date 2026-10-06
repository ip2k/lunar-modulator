/* fm1_state_mod.h -- a file's modulation records and the runtime
 * (state_mod.c). MIT licence. */
#ifndef FM1_STATE_MOD_H_
#define FM1_STATE_MOD_H_

#include "fm1_mod.h"
#include "fm1_state.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_state_mod {
  fm1_mod_t *m;
  const fm1_state_names_t *nm;
  const fm1_engine_t *units[FM1_MOD_SINKS];   /* the engines bound at each sink */
  fm1_state_report_t *rep;
  uint32_t seed;
  uint8_t has_seed;
  uint8_t pad_[3];
} fm1_state_mod_t;

/* units[i]: the engine bound at sink i (fm1_mod_sink_unit's order), for
 * cables kept by name. The runtime is built (with the file's seed, which a
 * first pass learns: fm1_state_mod_sink gathers it) and its units bound
 * before the records are applied. */
void fm1_state_mod_init(fm1_state_mod_t *a, fm1_mod_t *m, const fm1_state_names_t *nm,
                        const fm1_engine_t *const units[FM1_MOD_SINKS], fm1_state_report_t *rep);
/* A record sink: MODULE, a module's PARAM and CABLE records reach the
 * runtime (kinds and parameters by uid; a destination kept by name is
 * resolved against its unit); SEED is kept in a->seed; the rest is
 * ignored. What cannot be applied is skipped and counted. */
int fm1_state_mod_sink(void *ctx, const fm1_rec_t *r);

/* The runtime as records: MOD, SEED (with_seed), each module with every
 * parameter's base by uid, and every slot that has a destination. */
int fm1_state_mod_collect(const fm1_mod_t *m, uint32_t seed, int with_seed, fm1_rec_sink_t sink, void *ctx);

#ifdef __cplusplus
}
#endif

#endif /* FM1_STATE_MOD_H_ */

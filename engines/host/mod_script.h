/* mod_script.h -- fm1-render's text format for the modulation runtime
 * (fm1_mod.h): one line sets up the rack, a module's parameters or a slot.
 *
 *   seed N                         the runtime's seed (read before it is built)
 *   rack default                   LFO, LFO, Envelope, Envelope, Chance at 1-5
 *   mod P KIND [NAME=VALUE]...     KIND (lfo, env, chance, or none) at position
 *                                  P (1-8), with parameter bases
 *   set P NAME=VALUE...            parameter bases of the module at P
 *   slot S SRC > DST [amt=PCT] [ofs=PCT] [via=SRC] [pol=auto|uni|bi|inv]
 *                    [curve=lin|square|cube|root|cbrt|exp|log|s] [off]
 *   slot S on | off | clear        switch a slot, or empty it
 *   move A B                       move the module at A to B (1-8)
 *   reset                          reset every module (as a preset load)
 *
 * SRC is a system source (vel, note, rand, key, trig, clock, beat, bar, run,
 * start, rtrg, seq1-seq8, sqv1-sqv8) or a module output: the kind's id or
 * abbreviation, or "mod", with its position, and optionally a port by name
 * or number (lfo1, lfo1.wrap, env3.2, mod5.held). DST is snd:NAME,
 * fx1:NAME, fx2:NAME, host:pitch, host:amp, or a module's parameter or gate
 * input (lfo2.rate, env3:gate). Names are compared without ASCII case;
 * parameters also go by abbreviation, and ENUM values by name. amt and ofs
 * are percent, -100..100, stored in Q1.14. A '#' starts a comment.
 *
 * Desktop host code (stdio, strtod). MIT licence. */
#ifndef FM1_MOD_SCRIPT_H_
#define FM1_MOD_SCRIPT_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_mod.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Applies one line. units[0..2] are the engines bound to SOUND, FX1 and FX2
 * (NULL for none), for snd:/fx1:/fx2: names. Returns 1, or 0 with a
 * message in err. A `seed` line is accepted and does nothing here. */
int fm1_mod_script_line(fm1_mod_t *m, const char *line, const fm1_engine_t *const units[3],
                        char *err, size_t errcap);

/* The seed a `seed N` line gives, if this is one. */
int fm1_mod_script_seed(const char *line, uint32_t *seed);

/* A source's name as the format writes it (vel, seq3, lfo1.wrap); for logs. */
void fm1_mod_script_source_name(const fm1_mod_t *m, unsigned src, char *buf, size_t cap);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_SCRIPT_H_ */

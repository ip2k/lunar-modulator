/* mod_script.h -- fm1-render's text format for the modulation runtime
 * (fm1_mod.h): one line sets up the rack, a module's parameters or a slot.
 *
 *   seed N                         the runtime's seed (read before it is built)
 *   rack default                   LFO, LFO, Envelope, Envelope, Chance at 1-5
 *   mod P KIND [NAME=VALUE]...     KIND (lfo, env, chance, or none) at position
 *                                  P (1-8), with parameter bases
 *   set P NAME=VALUE...            parameter bases of the module at P
 *   slot S SRC > DST [amt=PCT] [ofs=PCT] [via=SRC] [pol=auto|uni|bi|inv]
 *                    [curve=lin|square|cube|root|cbrt|exp|log|s] [voice]
 *                    [lock=UID] [off]
 *   data P VERSION HEX             pattern data for the module at P (its
 *                                  kind's set_data): layout VERSION, the
 *                                  bytes in hex
 *   slot S on | off | clear        switch a slot, or empty it
 *   move A B                       move the module at A to B (1-8)
 *   reset                          reset every module (as a preset load)
 *   current K                      the current sound unit (1-4): host:pitchc's
 *
 * `voice` makes a slot per voice (docs/16 MG9). `lock=UID` gives the slot
 * the base uid of its own AMT and OFS for sequencer locks (MG6; 0-4095, 0
 * for none), and a `data` line a module's pattern data (Register's locked
 * loop), so the format says everything a saved file can (notes/
 * 2026-10-06-state-files.md §5.4). SRC is a system source (vel,
 * note, rand, key, trig, clock, beat, bar, run, start, rtrg, seq1-seq8,
 * sqv1-sqv8, and one sound unit's s1note-s4note, s1vel, s1key, s1trig,
 * s1rtrg...) or a module output: the kind's id or
 * abbreviation, or "mod", with its position, and optionally a port by name
 * or number (lfo1, lfo1.wrap, env3.2, mod5.held). DST is snd:NAME (sound
 * unit 1, also snd1:NAME), snd2:NAME to snd4:NAME (the other sound units),
 * sndK.fxJ:NAME (sound unit K's insert J, 1 or 2; snd.fxJ is sound unit
 * 1's), fx1:NAME and fx2:NAME (the master slots), host:pitch (sound unit
 * 1's), host:pitch2 to host:pitch4, host:pitchc (the current sound's),
 * host:amp, or
 * a module's parameter or gate input (lfo2.rate, env3:gate): a ':' when
 * there is one, else the first '.', ends the unit. Names are compared without ASCII case;
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

/* Applies one line. units[i] is the engine bound to sink i
 * (fm1_mod_sink_unit's order; NULL for none, HOST's ignored), for the
 * destinations' names. Returns 1, or 0 with a message in err. A `seed`
 * line is accepted and does nothing here. */
int fm1_mod_script_apply(fm1_mod_t *m, const char *line,
                         const fm1_engine_t *const units[FM1_MOD_SINKS], char *err, size_t errcap);

/* A sink's name as DST writes it before the ':' (snd, snd2, snd1.fx2,
 * fx1, host), by code; NULL for a code that names none. */
const char *fm1_mod_script_unit_name(unsigned unit);

/* The seed a `seed N` line gives, if this is one. */
int fm1_mod_script_seed(const char *line, uint32_t *seed);

/* The `data` line for the module at pos (0-7), "data P VERSION HEX", into
 * buf: its length, or 0 when the module has no pattern data or the line
 * does not fit cap (NUL included). */
size_t fm1_mod_script_data_line(const fm1_mod_t *m, unsigned pos, char *buf, size_t cap);

/* A source's name as the format writes it (vel, seq3, lfo1.wrap); for logs. */
void fm1_mod_script_source_name(const fm1_mod_t *m, unsigned src, char *buf, size_t cap);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_SCRIPT_H_ */

/* felucca_bridge.h -- the C side of the Felucca shim (src/felucca_shim.cc):
 * the narrow interface through which our engine API reaches three of
 * Felucca's engines, WHEEL, TRIO and PHASE (Leo Kuroshita / Hügelton
 * Instruments, GPL-3.0-only; vendored unmodified in third_party/felucca/,
 * UPSTREAM.md).
 *
 * Felucca is one compilation unit of static functions and tables, and its
 * engines are C (designated initialisers), so they are compiled into one C
 * object, src/felucca_bridge.c, which includes them and exports what is
 * declared here. Everything else, the parameters, the voices and their
 * glide, the per-note offsets, the ramps and the output, is the shim's.
 *
 * A "world" is one instance's Felucca state: a Felucca part (track_t, with
 * its eight voices and their engine state) and, for WHEEL, the per-part
 * and per-voice state eng_wheel.c keeps in arrays of its own, which the
 * bridge lends to those arrays for the length of each call and takes back
 * after it, so every instance is self-contained (engines/README.md, "The
 * Felucca engines").
 *
 * Built only while the GPL switch is on (FM1_GPL_MODS, engines/Makefile;
 * mk/felucca.mk). MIT licence (this file).
 */
#ifndef FELUCCA_BRIDGE_H_
#define FELUCCA_BRIDGE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The engines, by Felucca's names. */
enum { FEL_WHEEL = 0, FEL_TRIO = 1, FEL_PHASE = 2, FEL_ENGINES = 3 };

#define FEL_VOICES 8        /* core.h NVOICE: a part's voices */
#define FEL_CTL 32          /* felucca_tables.h CTL: the control block, in samples */
#define FEL_RATE 44100      /* felucca_tables.h FS: the rate its tables are for */
#define FEL_EDIT 8          /* an engine's EDIT parameters, P_E0..P_E7 */

/* What one voice plays for one control block. The shim fills it from its
 * parameters (in Felucca's integer units), the voice's pitch and glide, and
 * its envelope times; the bridge runs Felucca's envelope law on adsr and
 * builds the engine's modulation (vmod_t) from the rest. */
typedef struct fel_vin {
  int16_t e[FEL_EDIT];      /* this voice's P_E0..P_E7 */
  int32_t pitch16;          /* 1/16 semitone, 0..2047 (MIDI 0..127.94) */
  int32_t fine;             /* the rest, in 1/4096 of the increment (vmod_t.fine) */
  int32_t pitch_cur;        /* the key and the glide only, 1/16 semitone (voice_t.pitch_cur) */
  int32_t cutoff;           /* added to vmod_t.cutoff (0..127 << 8 scale) */
  int32_t shape;            /* vmod_t.shape: 64 << 8 is the centre */
  int32_t fenv;             /* envelope to cutoff, -64..63 (core.h P_ED_FLT) */
  uint8_t adsr[4];          /* attack, decay, sustain, release: 0..127 (core.h P_ATK..P_REL) */
  int32_t *out;             /* where the voice adds its FEL_CTL samples */
} fel_vin_t;

/* Bytes of an instance's world for `engine`, and its preparation in `w`
 * (any contents before; 8-byte aligned or better). */
size_t fel_world_size(int engine);
void fel_world_init(void *w, int engine);

/* A voice starts (or, if it sounds, starts again: its attack from the level
 * it is at, its phases kept, as Felucca's voice_start does) on `note`, with
 * the engine's note_on. e: the values its note_on may read. */
void fel_voice_start(void *w, int engine, int voice, uint8_t note, uint8_t velocity,
                     uint32_t age, int32_t pitch_cur, const int16_t e[FEL_EDIT]);
/* The key goes up: the voice releases (gate 0, the release stage). */
void fel_voice_release(void *w, int voice);
/* Legato: the voice takes another key, nothing restarts. */
void fel_voice_retune(void *w, int voice, uint8_t note);
/* Whether the voice still sounds (its release has not ended). */
int fel_voice_active(const void *w, int voice);

/* One control block of the part: the engine's per-part work (WHEEL's bars
 * and rotor) with part_e, then every sounding voice: its envelope tick,
 * then the engine's render into in[v].out. */
void fel_block(void *w, int engine, const int16_t part_e[FEL_EDIT], const fel_vin_t in[FEL_VOICES]);

/* Felucca's table entries, for the shim's parameter maps and the tests:
 * TIME_MS_X10[i] (a time knob's value i, in 0.1 ms), CUTOFF_HZ[i]. */
uint32_t fel_time_ms_x10(int i);
uint32_t fel_cutoff_hz(int i);

/* The engine's factory sounds (its preset_t table), for the tests and the
 * manual: name, EDIT values, envelope, ENV -> FILTER and the MONO flag.
 * Returns 0 past the last. */
typedef struct fel_preset {
  const char *name;
  int8_t e[FEL_EDIT];
  uint8_t env[4];
  int8_t fenv;
  uint8_t mono;
} fel_preset_t;
int fel_preset(int engine, int index, fel_preset_t *out);

/* sizeof the structs the world holds, for the size probes. */
size_t fel_sizeof_track(void);

#ifdef __cplusplus
}
#endif

#endif /* FELUCCA_BRIDGE_H_ */

/* upstream_engine_bridge.h -- the C side of the Felucca shim (src/upstream_engine_shim.cc):
 * the narrow interface through which our engine API reaches three of
 * Felucca's engines, WHEEL, TRIO and PHASE (Leo Kuroshita / Hügelton
 * Instruments, GPL-3.0-only; vendored unmodified in third_party/upstream-engines/,
 * UPSTREAM.md).
 *
 * Felucca is one compilation unit of static functions and tables, and its
 * engines are C (designated initialisers), so they are compiled into one C
 * object, src/upstream_engine_bridge.c, which includes them and exports what is
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
 * mk/upstream_engines.mk). MIT licence (this file).
 */
#ifndef UPSTREAM_ENGINE_BRIDGE_H_
#define UPSTREAM_ENGINE_BRIDGE_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The engines, by Felucca's names. */
enum { UPSTREAM_ENGINE_WHEEL = 0, UPSTREAM_ENGINE_TRIO = 1, UPSTREAM_ENGINE_PHASE = 2, UPSTREAM_ENGINE_COUNT = 3 };

#define UPSTREAM_ENGINE_VOICES 8        /* core.h NVOICE: a part's voices */
#define UPSTREAM_ENGINE_CONTROL_SAMPLES 32          /* upstream_engine_tables.h CTL: the control block, in samples */
#define UPSTREAM_ENGINE_TABLE_RATE 44100      /* upstream_engine_tables.h FS: the rate its tables are for */
#define UPSTREAM_ENGINE_EDIT_COUNT 8          /* an engine's EDIT parameters, P_E0..P_E7 */

/* What one voice plays for one control block. The shim fills it from its
 * parameters (in Felucca's integer units), the voice's pitch and glide, and
 * its envelope times; the bridge runs Felucca's envelope law on adsr and
 * builds the engine's modulation (vmod_t) from the rest. */
typedef struct upstream_engine_vin {
  int16_t e[UPSTREAM_ENGINE_EDIT_COUNT];      /* this voice's P_E0..P_E7 */
  int32_t pitch16;          /* 1/16 semitone, 0..2047 (MIDI 0..127.94) */
  int32_t fine;             /* the rest, in 1/4096 of the increment (vmod_t.fine) */
  int32_t pitch_cur;        /* the key and the glide only, 1/16 semitone (voice_t.pitch_cur) */
  int32_t cutoff;           /* added to vmod_t.cutoff (0..127 << 8 scale) */
  int32_t shape;            /* vmod_t.shape: 64 << 8 is the centre */
  int32_t fenv;             /* envelope to cutoff, -64..63 (core.h P_ED_FLT) */
  uint8_t adsr[4];          /* attack, decay, sustain, release: 0..127 (core.h P_ATK..P_REL) */
  int32_t *out;             /* where the voice adds its UPSTREAM_ENGINE_CONTROL_SAMPLES samples */
} upstream_engine_voice_input_t;

/* Bytes of an instance's world for `engine`, and its preparation in `w`
 * (any contents before; 8-byte aligned or better). */
size_t upstream_engine_world_size(int engine);
void upstream_engine_world_init(void *w, int engine);

/* A voice starts (or, if it sounds, starts again: its attack from the level
 * it is at, its phases kept, as Felucca's voice_start does) on `note`, with
 * the engine's note_on. e: the values its note_on may read. */
void upstream_engine_voice_start(void *w, int engine, int voice, uint8_t note, uint8_t velocity,
                     uint32_t age, int32_t pitch_cur, const int16_t e[UPSTREAM_ENGINE_EDIT_COUNT]);
/* The key goes up: the voice releases (gate 0, the release stage). */
void upstream_engine_voice_release(void *w, int voice);
/* Legato: the voice takes another key, nothing restarts. */
void upstream_engine_voice_retune(void *w, int voice, uint8_t note);
/* Whether the voice still sounds (its release has not ended). */
int upstream_engine_voice_active(const void *w, int voice);

/* One control block of the part: the engine's per-part work (WHEEL's bars
 * and rotor) with part_e, then every sounding voice: its envelope tick,
 * then the engine's render into in[v].out. */
void upstream_engine_block(void *w, int engine, const int16_t part_e[UPSTREAM_ENGINE_EDIT_COUNT], const upstream_engine_voice_input_t in[UPSTREAM_ENGINE_VOICES]);

/* Felucca's table entries, for the shim's parameter maps and the tests:
 * TIME_MS_X10[i] (a time knob's value i, in 0.1 ms), CUTOFF_HZ[i]. */
uint32_t upstream_engine_time_ms_x10(int i);
uint32_t upstream_engine_cutoff_hz(int i);

/* The engine's factory sounds (its preset_t table), for the tests and the
 * manual: name, EDIT values, envelope, ENV -> FILTER and the MONO flag.
 * Returns 0 past the last. */
typedef struct upstream_engine_preset {
  const char *name;
  int8_t e[UPSTREAM_ENGINE_EDIT_COUNT];
  uint8_t env[4];
  int8_t fenv;
  uint8_t mono;
} upstream_engine_preset_t;
int upstream_engine_preset(int engine, int index, upstream_engine_preset_t *out);

/* sizeof the structs the world holds, for the size probes. */
size_t upstream_engine_sizeof_track(void);

#ifdef __cplusplus
}
#endif

#endif /* UPSTREAM_ENGINE_BRIDGE_H_ */

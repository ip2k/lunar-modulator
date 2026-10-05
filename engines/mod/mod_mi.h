/* mod_mi.h -- C ports of the Mutable Instruments code three modulation kinds
 * run (docs/16 MG2): Peaks' bouncing ball, pulse shaper and pulse randomizer
 * (Emilie Gillet, 2013, MIT) for Bounce and Burst, and Braids' quantizer
 * (2015, MIT) for Quantize. Not API.
 *
 * Each port does upstream's arithmetic, operation for operation, in the
 * same integer types, so a call returns what upstream's returns:
 * fm1-mod-mi-ref (test/mod_mi_ref.cc) runs the vendored originals beside
 * these over random parameters and inputs and compares every output.
 * What differs is only how they are held: plain structs the kinds embed, a
 * per-instance random state in place of stmlib::Random's global (seeded
 * from the preset), and Braids' 128-entry codebook computed per entry
 * instead of stored. The two additions to Peaks' pulse shaper (ACCEL and a
 * clocked spacing) are off at 0 and leave it byte-identical.
 *
 * Rates. Peaks runs at 48 kHz [reported: docs/16 §2.6; peaks.cc's TIM1
 * handler says "DAC refresh at 48kHz"] and hands its processors blocks of
 * 4 samples [verified: io_buffer.h kBlockSize]. The ball steps per sample
 * (48,000 Hz); the pulse processors count calls, one per block (12,000
 * Hz), so the kinds run them at those native rates through an integer
 * accumulator (kinds_int.h).
 *
 * C99, no heap, no stdio, no libm; -ffp-contract=off. The ports carry
 * upstream's MIT notice (mod_mi.c); the rest of this repository is MIT
 * too. */
#ifndef MOD_MI_H_
#define MOD_MI_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MOD_MI_LUT_SIZE 257
#define MOD_MI_PULSES 32               /* Peaks' kPulseBufferSize, kTriggerPulseBufferSize */
#define MOD_MI_SCALES 49
#define MOD_MI_BALL_RATE 48000u        /* the ball: one step per sample */
#define MOD_MI_PULSE_RATE 12000u       /* the pulse processors: one call per 4 samples */
#define MOD_MI_PULSE_HIGH 20480        /* the processors' high output (Peaks' int16) */

/* Peaks' tables and Braids' scales (mod_mi_tables.c, written by
 * gen_mi_tables.py from the vendored originals). */
extern const uint16_t mod_mi_lut_delay_times[MOD_MI_LUT_SIZE];
extern const uint16_t mod_mi_lut_gravity[MOD_MI_LUT_SIZE];
typedef struct mod_mi_scale {
  int16_t span;
  uint8_t num_notes;
  uint8_t reserved;
  int16_t notes[16];
} mod_mi_scale_t;
extern const mod_mi_scale_t mod_mi_scales[MOD_MI_SCALES];

/* stmlib's Interpolate88 (utils/dsp.h). */
uint16_t mod_mi_interpolate88(const uint16_t *table, uint16_t index);

/* ---- Peaks' BouncingBall (peaks/modulations/bouncing_ball.h) -------------- */
typedef struct mod_mi_bounce {
  int32_t gravity, bounce_loss, initial_amplitude, initial_velocity;
  int32_t velocity, position;
} mod_mi_bounce_t;

/* Init(), plus velocity and position 0 (upstream leaves them to the
 * static object's zero fill). */
void mod_mi_bounce_init(mod_mi_bounce_t *b);
/* Configure() in CONTROL_MODE_FULL: gravity, bounce loss, initial
 * amplitude, initial velocity (+32,768) as Peaks' 16-bit knob values. */
void mod_mi_bounce_configure(mod_mi_bounce_t *b, const uint16_t p[4]);
/* One sample of Process(): `rising` is GATE_FLAG_RISING. Returns the output
 * (0..32,767); *floor is 1 when the ball hit the floor on this sample. */
int16_t mod_mi_bounce_sample(mod_mi_bounce_t *b, int rising, int *floor);

/* ---- Peaks' PulseShaper (peaks/pulse_processor/pulse_shaper.*) ------------ */
typedef struct mod_mi_pulse {
  uint16_t initial_delay_counter, duration_counter, delay_counter, repetition_counter;
} mod_mi_pulse_t;

typedef struct mod_mi_shaper {
  uint16_t initial_delay, duration, delay, num_repetitions;
  uint16_t previous_num_pulses, retrig_counter;
  /* Ours, both off at 0. accel: each repeat's gap is the last one's times
   * 2^(-accel / 2), accel in 1/16,384 (Q1.14, -1..1). clocked: when not 0,
   * the gap is `clocked` calls whatever `delay` says (a clock's period
   * shared by the repeats). */
  int16_t accel;
  uint16_t clocked;
  mod_mi_pulse_t pulse[MOD_MI_PULSES];
} mod_mi_shaper_t;

void mod_mi_shaper_init(mod_mi_shaper_t *s);
/* Configure() in CONTROL_MODE_FULL: initial delay, duration, delay and
 * repetitions as Peaks' 16-bit knob values. */
void mod_mi_shaper_configure(mod_mi_shaper_t *s, const uint16_t p[4]);
/* One call of Process() over a block; new_pulse: a rising edge in it.
 * Returns MOD_MI_PULSE_HIGH or 0. */
int16_t mod_mi_shaper_call(mod_mi_shaper_t *s, int new_pulse);
int mod_mi_shaper_active(const mod_mi_shaper_t *s);   /* a pulse is running */

/* ---- Peaks' PulseRandomizer (peaks/pulse_processor/pulse_randomizer.*) ---- */
typedef struct mod_mi_randomizer {
  uint16_t repetition_probability, acceptance_probability, delay_average, delay_randomness;
  uint16_t num_pulses, retrig_counter;
  uint32_t rng;                         /* stmlib::Random's state, this instance's own */
  uint16_t delay_counter[MOD_MI_PULSES];
} mod_mi_randomizer_t;

void mod_mi_randomizer_init(mod_mi_randomizer_t *r, uint32_t rng);
void mod_mi_randomizer_configure(mod_mi_randomizer_t *r, const uint16_t p[4]);
int16_t mod_mi_randomizer_call(mod_mi_randomizer_t *r, int new_pulse);
int mod_mi_randomizer_active(const mod_mi_randomizer_t *r);

/* ---- Braids' Quantizer (braids/quantizer.*) ---------------------------------
 * Pitches in 1/128 semitone. The codebook entry i (0..127) of a scale is
 * computed when needed: it is what Configure() would store there. */
typedef struct mod_mi_quantizer {
  int32_t codeword, previous_boundary, next_boundary;
  uint8_t scale, enabled, reserved[2];
} mod_mi_quantizer_t;

void mod_mi_quantizer_init(mod_mi_quantizer_t *q);           /* Init(): no scale */
/* Configure(scales[scale]), and the held cell dropped (Braids keeps it, so
 * a held pitch can stay out of the new scale until the input moves). */
void mod_mi_quantizer_configure(mod_mi_quantizer_t *q, unsigned scale);
int32_t mod_mi_quantizer_entry(const mod_mi_quantizer_t *q, int i);
int32_t mod_mi_quantizer_process(mod_mi_quantizer_t *q, int32_t pitch, int32_t root);

#ifdef __cplusplus
}
#endif

#endif /* MOD_MI_H_ */

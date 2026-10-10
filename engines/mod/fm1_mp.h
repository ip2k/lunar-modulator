/* fm1_mp.h -- modulation primitives: small, heap-free C99 building blocks for
 * the modulation runtime that docs/16 is designing. Nothing here is wired
 * into an engine or the simulator yet, and nothing here is the module API:
 * a module wraps these.
 *
 *   fm1_mp_rng_t     the per-instance PRNG (xorshift64*, as fm1_seq's R7)
 *   fm1_mp_lfo_t     phase-accumulator LFO: 8 shapes, rate ratio, retrigger,
 *                    one-shot and half-cycle, wrap-exact random shapes
 *   fm1_mp_env_t     multistage envelope after Mutable Instruments' Peaks:
 *                    delayed ADSR, AD, loops, linear/expo/quartic/log/smooth curves
 *   fm1_mp_slew_t    slew limiter, separate rise and fall, linear or expo
 *   fm1_mp_sah_t     sample-and-hold and track-and-hold
 *   fm1_mp_turing_t  Turing-machine shift register (length, flip chance)
 *   fm1_mp_clkdiv_t  clock divider and multiplier on integer ticks
 *
 * Conventions (engines/mod/README.md has the detail):
 * - The caller owns every struct. `init` sets every field, so the memory's
 *   prior contents never matter. No function allocates, prints or calls libm.
 * - Values are float. LFO output is bipolar, -1..1. Envelope levels are
 *   clamped to -1..1. Turing output is unipolar, 0..1.
 * - Time runs in samples. `process(n)` advances n samples and returns the
 *   value after the last one; `render(out, n)` writes the value after each
 *   sample, so render's out[n-1] equals what process(n) returns; `value()`
 *   reads the current value (the last one output) without advancing.
 * - Block-size independence: LFO, envelope, slew and S&H give bit-identical
 *   results however a span of samples is split into calls, provided the
 *   inputs and events fall on the same samples. The LFO and envelope advance
 *   integer phases, so their process(n) costs O(1) per call (O(segments or
 *   wraps crossed)); the slew loops per sample.
 * - NaN or infinite arguments never reach the output: every setter maps them
 *   to a documented safe value and every input ignores them.
 * - Build with -ffp-contract=off (docs/14, the ladder profile), as mk/mod.mk
 *   does, so float results match on every rung.
 */
#ifndef FM1_MP_H
#define FM1_MP_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define FM1_MP_DEFAULT_RATE 44118.0f /* the FM-1's sample rate */

/* ---- PRNG ------------------------------------------------------------------
 * xorshift64* (Vigna), the algorithm fm1_seq uses for its rolls (R7). Each
 * primitive that draws owns one, so two sources never share a sequence and
 * stmlib::Random's global is never touched. Any seed is valid, 0 included. */
typedef struct {
  uint64_t s;
} fm1_mp_rng_t;

void fm1_mp_rng_seed(fm1_mp_rng_t *r, uint32_t seed);
uint32_t fm1_mp_rng_next(fm1_mp_rng_t *r);   /* the high 32 bits of the product */
float fm1_mp_rng_bipolar(fm1_mp_rng_t *r);   /* -1 <= x < 1, in steps of 2^-23 */

/* ---- LFO -------------------------------------------------------------------
 * A uint32 phase accumulator, one cycle per 2^32. Phase 0 is the start of a
 * cycle: sine and triangle start at 0 rising, saws at their low (up) or high
 * (down) end, square high.
 *
 * Random shapes change only when the accumulator wraps (the 64-bit sum of
 * phase and increments carries out), however many samples a call covers.
 * Each wrap draws exactly once, so a block that crosses one or several wraps
 * makes the same draws as per-sample processing. This fixes Schwung's
 * `lfo_common.h` S&H, which re-rolls only when phase < 0.05 and so misses
 * wraps once a call advances more than 0.05 of a cycle. The random state is
 * kept for every shape, so switching to a random shape never shows an unset
 * value. */
typedef enum {
  FM1_MP_LFO_SINE = 0,
  FM1_MP_LFO_TRIANGLE,
  FM1_MP_LFO_SAW_UP,
  FM1_MP_LFO_SAW_DOWN,
  FM1_MP_LFO_SQUARE,        /* +1 for the first pulse-width fraction of the cycle */
  FM1_MP_LFO_SMOOTH_RANDOM, /* glides from the previous draw to this cycle's draw */
  FM1_MP_LFO_SAMPLE_HOLD,   /* stepped random: one new draw per cycle */
  FM1_MP_LFO_RANDOM_WALK,   /* bounded walk, a step of up to `walk` per cycle, glided */
  FM1_MP_LFO_SHAPE_COUNT
} fm1_mp_lfo_shape_t;

typedef enum {
  FM1_MP_LFO_FREE = 0, /* runs forever */
  FM1_MP_LFO_ONE_SHOT, /* one cycle from the start phase, then holds */
  FM1_MP_LFO_HALF,     /* half a cycle from the start phase, then holds */
  FM1_MP_LFO_MODE_COUNT
} fm1_mp_lfo_mode_t;

typedef struct {
  uint32_t phase;     /* position in the cycle */
  uint32_t inc;       /* phase increment per sample */
  uint32_t inc_frac;  /* and its fraction, in 2^-32 of a phase step */
  uint32_t frac;      /* the phase's fraction, accumulated */
  uint32_t start;     /* phase after a reset */
  uint64_t pw;        /* square threshold, 0..2^32 */
  uint64_t run;       /* one-shot: distance covered since the reset */
  float sample_rate;
  float hz;           /* the rate after clamping */
  float walk;         /* random walk's largest step, 0..1 */
  float prev, next;   /* smooth random runs prev -> next; S&H holds next */
  float walk_prev, walk_next;
  fm1_mp_rng_t rng;
  uint32_t wraps;     /* cycles started since init, reset included (diagnostic) */
  uint8_t shape, mode, done, owed;
} fm1_mp_lfo_t;

/* sample_rate: Hz; NaN, or outside 1,000..384,000, means FM1_MP_DEFAULT_RATE.
 * Starts as a 1 Hz free sine at phase 0, pulse width 0.5, walk 0.25. */
void fm1_mp_lfo_init(fm1_mp_lfo_t *l, float sample_rate, uint32_t seed);
/* Restart the random sequence from `seed` (a preset's seed restores it). */
void fm1_mp_lfo_seed(fm1_mp_lfo_t *l, uint32_t seed);
void fm1_mp_lfo_set_shape(fm1_mp_lfo_t *l, int shape);  /* out of range: sine */
void fm1_mp_lfo_set_mode(fm1_mp_lfo_t *l, int mode);    /* out of range: free */
/* The rate as a ratio: hz = base_hz * ratio, clamped to 0..sample_rate/2
 * (NaN gives 0, a stopped LFO). The increment is kept to 2^-64 of a cycle
 * per sample (32.32 fixed point, computed in double here and nowhere else)
 * and rounded up, so a period of a whole number of samples wraps on its last
 * sample and a synced LFO drifts by under a sample in years. Free-running: base_hz is the rate and ratio
 * a multiplier (1, or Elektron-style MULT). Tempo-synced: base_hz = bpm / 60
 * and ratio = cycles per beat (0.25 = one cycle per 4/4 bar, 4 = sixteenths). */
void fm1_mp_lfo_set_rate(fm1_mp_lfo_t *l, float base_hz, float ratio);
void fm1_mp_lfo_set_pulse_width(fm1_mp_lfo_t *l, float pw); /* 0..1; NaN: 0.5 */
void fm1_mp_lfo_set_walk(fm1_mp_lfo_t *l, float walk);      /* 0..1; NaN: 0.25 */
void fm1_mp_lfo_set_start_phase(fm1_mp_lfo_t *l, float turns); /* 0..1; NaN: 0 */
/* Retrigger: phase to the start phase, a new cycle (random shapes draw), and
 * a one-shot run starts again. */
void fm1_mp_lfo_reset(fm1_mp_lfo_t *l);
/* Move the phase to `phase` by the shorter way round, for locking a free
 * accumulator to an external phase (fm1_mp_clkdiv_phase, a tick count). A
 * forward move across the wrap counts as a wrap. A backward move across it
 * draws nothing and cancels the next forward wrap's draw, so jitter around the
 * wrap point never draws twice for one cycle. One-shot state is unchanged. */
void fm1_mp_lfo_sync(fm1_mp_lfo_t *l, uint32_t phase);
float fm1_mp_lfo_process(fm1_mp_lfo_t *l, uint32_t n);
void fm1_mp_lfo_render(fm1_mp_lfo_t *l, float *out, uint32_t n);
float fm1_mp_lfo_value(const fm1_mp_lfo_t *l);

/* ---- Multistage envelope ---------------------------------------------------
 * After Peaks' MultistageEnvelope (Emilie Gillet, MIT;
 * peaks/modulations/multistage_envelope.{h,cc}): up to 8 segments, each with
 * an end level, a time and a curve; a sustain point; a loop; a uint32 phase
 * per segment, whose overflow moves to the next segment. Rewritten in C with
 * float levels and times in seconds; the differences from Peaks are listed in
 * engines/mod/README.md. */
#define FM1_MP_ENV_MAX_SEGMENTS 8

typedef enum {
  FM1_MP_CURVE_LINEAR = 0,
  FM1_MP_CURVE_EXPO,    /* Peaks' ENV_SHAPE_EXPONENTIAL, (1-e^-4t)/(1-e^-4): fast, then settling */
  FM1_MP_CURVE_QUARTIC, /* Peaks' ENV_SHAPE_QUARTIC, t^3.32: slow, then fast */
  FM1_MP_CURVE_LOG,     /* log(1 + 9t) / log(10) */
  FM1_MP_CURVE_SMOOTH,  /* smoothstep: 3t^2 - 2t^3 */
  FM1_MP_CURVE_COUNT
} fm1_mp_curve_t;

typedef enum {
  FM1_MP_ENV_LOOP_OFF = 0,
  FM1_MP_ENV_LOOP_AD,  /* 0 -> 1 -> 0 repeats while the gate is high */
  FM1_MP_ENV_LOOP_ADR, /* 0 -> 1 -> S -> 0 repeats while the gate is high */
  FM1_MP_ENV_LOOP_COUNT
} fm1_mp_env_loop_t;

typedef struct {
  float level[FM1_MP_ENV_MAX_SEGMENTS + 1]; /* level[i] starts segment i */
  uint32_t inc[FM1_MP_ENV_MAX_SEGMENTS];
  uint8_t curve[FM1_MP_ENV_MAX_SEGMENTS];
  float sample_rate;
  float start;        /* the current segment's start value */
  uint32_t phase;
  uint8_t num_segments, sustain, loop_start, loop_end;
  uint8_t seg, gate, hard_reset, delay_stage; /* 0 absent, 1 timed, 2 zero delay */
} fm1_mp_env_t;

/* Idle at 0, configured as ADSR 2 ms / 250 ms / 0.5 / 500 ms, expo, no loop. */
void fm1_mp_env_init(fm1_mp_env_t *e, float sample_rate);
/* ADSR: 0 -> 1 in a, 1 -> s in d, held at s while the gate is high, then to 0
 * in r from wherever the gate fell. The loop modes repeat while the gate is
 * high and release on gate off. Times in seconds, 0..3600 (NaN: 0); s 0..1
 * (NaN: 0). A segment lasts at least 2 samples. */
void fm1_mp_env_set_adsr(fm1_mp_env_t *e, float a, float d, float s, float r,
                         int curve, int loop);
/* AD: 0 -> 1 -> 0, the gate's fall ignored; loop != 0 repeats it until the
 * next trigger restarts it. */
void fm1_mp_env_set_ad(fm1_mp_env_t *e, float a, float d, int curve, int loop);
/* Custom shapes: `segments` 1..8; `sustain` 1..segments-1, or 0 for none
 * (holds at the start of segment `sustain` while the gate is high; the gate's
 * fall jumps there); a loop jumps from the end of segment loop_end-1 back to
 * loop_start, active when loop_start < loop_end <= segments. Anything else
 * disables that feature. */
void fm1_mp_env_configure(fm1_mp_env_t *e, int segments, int sustain,
                          int loop_start, int loop_end);
void fm1_mp_env_set_segment(fm1_mp_env_t *e, int i, float end_level,
                            float seconds, int curve);
void fm1_mp_env_set_start_level(fm1_mp_env_t *e, float level);
/* Retrigger from the current value (Peaks' default), or from level 0 of the
 * shape with hard reset on. */
void fm1_mp_env_set_hard_reset(fm1_mp_env_t *e, int on);
/* A rising gate starts segment 0 (segment 1 when a reserved delay is zero); a falling one jumps to the sustain point's
 * segment (the release). Repeating the same level does nothing. */
void fm1_mp_env_gate(fm1_mp_env_t *e, int high);
/* Start the first timed segment now (bypassing zero delay), even if gated. */
void fm1_mp_env_trigger(fm1_mp_env_t *e);
float fm1_mp_env_process(fm1_mp_env_t *e, uint32_t n);
void fm1_mp_env_render(fm1_mp_env_t *e, float *out, uint32_t n);
float fm1_mp_env_value(const fm1_mp_env_t *e);
/* Shared by the DSP and time-domain display; phase spans [0, 2^32). */
float fm1_mp_env_curve_at(uint8_t curve, uint32_t phase);
/* Delay is in seconds; 0 bypasses it with no extra samples. Trigger selects AD. */
void fm1_mp_env_set_delayed(fm1_mp_env_t *e, float delay, float a, float d,
                            float s, float r, int curve, int loop, int trigger);
int fm1_mp_env_done(const fm1_mp_env_t *e);
/* Peaks' knob-to-time curve, 0..1 -> 0.5 ms..8 s (lookup_tables.py 55-68):
 * time = (0.0005^g + k (8^g - 0.0005^g))^(1/g), g = 0.175, from a 257-point
 * table. NaN: 0. */
float fm1_mp_env_time_from_knob(float k);

/* ---- Slew limiter ------------------------------------------------------------
 * LINEAR moves at most 1/(time * rate) per sample: `rise` and `fall` are the
 * seconds a full 0 -> 1 or 1 -> 0 change takes. EXPO is a one-pole lag whose
 * time constant (63 % of a step) is `rise` going up and `fall` going down; it
 * moves at least one LSB per sample, so it lands exactly on the target. A
 * time of 0 (or under one sample) passes the input through. The state is
 * integer, Q4.28: values are quantised to 2^-28 and limited to -8..8.
 * Non-finite inputs are ignored (the target stays). */
typedef enum {
  FM1_MP_SLEW_LINEAR = 0,
  FM1_MP_SLEW_EXPO,
  FM1_MP_SLEW_MODE_COUNT
} fm1_mp_slew_mode_t;

typedef struct {
  int32_t y, target;   /* Q4.28 */
  uint64_t up, down;   /* per-sample step in Q4.28 (linear) or coefficient in Q32 (expo) */
  float rise_s, fall_s;
  float sample_rate;
  uint8_t mode, pad_[3];
} fm1_mp_slew_t;

void fm1_mp_slew_init(fm1_mp_slew_t *s, float sample_rate); /* linear, instant, at 0 */
void fm1_mp_slew_set_mode(fm1_mp_slew_t *s, int mode);      /* out of range: linear */
void fm1_mp_slew_set_times(fm1_mp_slew_t *s, float rise_s, float fall_s); /* NaN: 0 */
void fm1_mp_slew_reset(fm1_mp_slew_t *s, float value);     /* jump there; NaN: 0 */
/* Hold `in` for n samples. */
float fm1_mp_slew_process(fm1_mp_slew_t *s, float in, uint32_t n);
/* One input per sample; in == NULL holds the current target. */
void fm1_mp_slew_render(fm1_mp_slew_t *s, const float *in, float *out, uint32_t n);
float fm1_mp_slew_value(const fm1_mp_slew_t *s);

/* ---- Sample-and-hold, track-and-hold -----------------------------------------
 * SAMPLE takes the input on a rising gate; TRACK follows the input while the
 * gate is high and holds while it is low. A non-finite input is never taken.
 * The input and gate are levels, so a call covering n samples is one step
 * whatever n is: no n argument. */
typedef enum {
  FM1_MP_SAH_SAMPLE = 0,
  FM1_MP_SAH_TRACK,
  FM1_MP_SAH_MODE_COUNT
} fm1_mp_sah_mode_t;

typedef struct {
  float held;
  uint8_t mode, gate, pad_[2];
} fm1_mp_sah_t;

void fm1_mp_sah_init(fm1_mp_sah_t *h);                 /* sample mode, holding 0 */
void fm1_mp_sah_set_mode(fm1_mp_sah_t *h, int mode);   /* out of range: sample */
float fm1_mp_sah_process(fm1_mp_sah_t *h, float in, int gate);
float fm1_mp_sah_value(const fm1_mp_sah_t *h);

/* ---- Turing-machine register ---------------------------------------------------
 * After Tom Whitwell's Turing Machine (Music Thing Modular). On each clock the
 * bit shifted in `length` clocks ago comes back in at bit 0, inverted with
 * probability `flip`. flip 0 locks a loop of `length` steps; flip 1 gives a
 * loop of 2 x length with the second half inverted; 0.5 is fresh random. The
 * output is the register's low 8 bits as 0..1 (the module's 8-bit DAC). One
 * draw per clock whatever `flip` is, so turning it never shifts the random
 * stream. */
typedef struct {
  uint32_t reg;
  uint64_t flip_threshold; /* flip when a draw < threshold; 2^32 means always */
  fm1_mp_rng_t rng;
  uint8_t length, pad_[3];
} fm1_mp_turing_t;

/* Length 16, flip 0, the register filled from the seed. */
void fm1_mp_turing_init(fm1_mp_turing_t *t, uint32_t seed);
void fm1_mp_turing_set_length(fm1_mp_turing_t *t, int length); /* clamped to 1..32 */
void fm1_mp_turing_set_flip(fm1_mp_turing_t *t, float p);      /* 0..1; NaN: 0 */
float fm1_mp_turing_clock(fm1_mp_turing_t *t);                 /* one step; the new value */
float fm1_mp_turing_value(const fm1_mp_turing_t *t);
int fm1_mp_turing_gate(const fm1_mp_turing_t *t);              /* bit 0 */
uint32_t fm1_mp_turing_bits(const fm1_mp_turing_t *t);

/* ---- Clock divider and multiplier on ticks -------------------------------------
 * `mul` output pulses per `div` periods of `ref` input ticks (ref 96 = one
 * beat at fm1_seq's 96 PPQN). Pulse k falls on input tick ceil(k * ref * div
 * / mul), counting the first tick after a reset as tick 0, so pulses are
 * spread as evenly as whole ticks allow and never drift: ref 96, mul 3, div 1
 * fires on ticks 0, 32, 64, 96...; mul 5 on 0, 20, 39, 58, 77, 96. All
 * integer. */
typedef struct {
  uint32_t period;  /* ref * div */
  uint32_t mul;
  uint32_t acc;     /* (ticks since reset * mul) mod period */
  uint8_t started, pad_[3];
} fm1_mp_clkdiv_t;

/* ref 1..65535, mul 1..256, div 1..256 (clamped). */
void fm1_mp_clkdiv_init(fm1_mp_clkdiv_t *c, uint32_t ref, uint32_t mul, uint32_t div);
void fm1_mp_clkdiv_reset(fm1_mp_clkdiv_t *c);       /* the next tick is tick 0 */
uint32_t fm1_mp_clkdiv_tick(fm1_mp_clkdiv_t *c);    /* pulses on this tick (0, 1, or more if mul > ref*div) */
uint32_t fm1_mp_clkdiv_advance(fm1_mp_clkdiv_t *c, uint32_t ticks); /* pulses over `ticks` ticks */
/* The position in the current output period as a uint32 phase: feed it to
 * fm1_mp_lfo_sync for a drift-free synced LFO. 0 before the first tick. */
uint32_t fm1_mp_clkdiv_phase(const fm1_mp_clkdiv_t *c);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MP_H */

/* kinds/kinds_int.h -- helpers the modulation kinds share (docs/16 MG2):
 * absolute time, level gate outputs that may change on the tick's own end,
 * merged gate events, knob conversions, and the accumulator that runs
 * vendored code at its own rate. Not API. MIT licence. */
#ifndef FM1_MOD_KINDS_INT_H_
#define FM1_MOD_KINDS_INT_H_

#include "mod_int.h"

/* The absolute frame where this tick's window starts, t(k-1). */
static inline uint64_t kind_t0(const fm1_mod_io_t *io) {
  return (io->tick ? io->tick - 1u : 0u) * FM1_MOD_TICK;
}

/* The host's rate as whole Hz (the runtime clamps it to 1,000..384,000). */
static inline uint32_t kind_rate(const fm1_host_t *host) {
  const float r = host ? host->sample_rate : 44118.0f;
  return r >= 1000.0f && r <= 384000.0f ? (uint32_t)(r + 0.5f) : 44118u;
}

/* ---- a level gate output ----------------------------------------------------
 * Like mod_trig_t for triggers: edges at their frame; one that falls on the
 * tick's own end (frame >= FM1_MOD_TICK, the boundary after the tick's last
 * sample) waits for the next tick's frame 0. */
typedef struct kind_gate {
  uint8_t level;               /* as the runtime holds it, deferred change excluded */
  uint8_t defer;               /* a level for the next tick's frame 0, or MOD_NONE */
  uint8_t reserved[2];
} kind_gate_t;

static inline void kind_gate_init(kind_gate_t *g) {
  g->level = 0;
  g->defer = MOD_NONE;
  g->reserved[0] = g->reserved[1] = 0;
}

static inline void kind_gate_begin(kind_gate_t *g, fm1_mod_gate_t *out) {
  mod_gate_clear(out, g->level);
  if (g->defer != MOD_NONE) {
    mod_gate_edge(out, 0, g->defer, NULL);
    g->level = g->defer;
    g->defer = MOD_NONE;
  }
}

static inline void kind_gate_set(kind_gate_t *g, fm1_mod_gate_t *out, unsigned frame,
                                 unsigned level) {
  level = level != 0;
  if (frame >= FM1_MOD_TICK) {
    g->defer = level != g->level ? (uint8_t)level : (uint8_t)MOD_NONE;
    return;
  }
  if (level == g->level) return;
  mod_gate_edge(out, frame, level, NULL);
  g->level = (uint8_t)level;
}

/* The level that a set at `frame` would leave, deferred change included. */
static inline unsigned kind_gate_now(const kind_gate_t *g) {
  return g->defer != MOD_NONE ? g->defer : g->level;
}

/* ---- events of several gate inputs, merged in frame order ------------------- */
typedef struct kind_event {
  uint8_t frame, input, high, reserved;
} kind_event_t;

/* Collects the edges of gate inputs [0, n) of io (ties by input index, then
 * by order) into ev; returns how many (<= n x FM1_MOD_EDGES). */
static inline unsigned kind_events(const fm1_mod_io_t *io, unsigned n, kind_event_t *ev) {
  unsigned count = 0, g, e, a, b;
  for (g = 0; g < n; ++g) {
    for (e = 0; e < io->gate[g].n; ++e) {
      ev[count].frame = io->gate[g].ev[e].frame;
      ev[count].input = (uint8_t)g;
      ev[count].high = io->gate[g].ev[e].high;
      ev[count].reserved = (uint8_t)e;
      ++count;
    }
  }
  for (a = 1; a < count; ++a) {   /* insertion sort: small and stable */
    for (b = a; b > 0; --b) {
      const unsigned x = ((unsigned)ev[b - 1].frame << 16) | ((unsigned)ev[b - 1].input << 8) |
                         ev[b - 1].reserved;
      const unsigned y = ((unsigned)ev[b].frame << 16) | ((unsigned)ev[b].input << 8) | ev[b].reserved;
      kind_event_t t;
      if (x <= y) break;
      t = ev[b];
      ev[b] = ev[b - 1];
      ev[b - 1] = t;
    }
  }
  return count;
}

/* ---- knobs -------------------------------------------------------------------- */

/* A 0..1 knob as Peaks' 16-bit pot value. */
static inline uint16_t kind_u16(float k) {
  k = mod_clampf(k, 0.0f, 1.0f, 0.0f);
  return (uint16_t)(k * 65535.0f + 0.5f);
}

/* A FLOAT parameter that holds a whole number, rounded and clamped. */
static inline int kind_int(float x, int lo, int hi) {
  const float r = mod_round(mod_clampf(x, (float)lo, (float)hi, (float)lo));
  return (int)r;
}

/* ---- running code at its own rate -------------------------------------------
 * docs/16 §2.6 (b): tick k runs the native samples [n(t(k-1)), n(t(k))),
 * n(F) = floor(F x rate / fs), exact in 64-bit integers. An input edge at
 * absolute frame F lands on native sample n(F); an output change made by
 * native sample a lands at the host frame of the boundary after it,
 * ceil((a + 1) x fs / rate). */
static inline uint64_t kind_native(uint64_t frame, uint32_t rate, uint32_t fs) {
  return frame * rate / fs;
}

/* The frame offset from t0 of the boundary after native sample a; may be
 * FM1_MOD_TICK or more (the next tick). */
static inline unsigned kind_after_native(uint64_t a, uint32_t rate, uint32_t fs, uint64_t t0) {
  const uint64_t f = ((a + 1u) * fs + rate - 1u) / rate;
  return f <= t0 ? 0u : (f - t0 > 255u ? 255u : (unsigned)(f - t0));
}

/* Seconds per tick at the host rate fs. */
static inline float kind_tick_s(uint32_t fs) {
  return (float)FM1_MOD_TICK / (float)fs;
}

#endif /* FM1_MOD_KINDS_INT_H_ */

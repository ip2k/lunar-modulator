/* fm1_gate.h -- what the Gate effect (src/fx_gate.cc, engine id "gate")
 * exposes beyond the engine API: the hooks a later stage builds on
 * (engines/README.md, "Gate"; notes/2026-10-02-delay-reverb-eq-gates-
 * options.md §7.3-§7.4).
 *
 *   - fm1_gate_render_key: render with a key (side-chain) signal other than
 *     the effect's own input. It has the signature the note's planned
 *     fm1_fx_ext_t.render_key has, so that struct can point at it as it is.
 *     No host calls it yet: today every host keys the Gate from itself.
 *   - fm1_gate_state: the gate's state after the last frame, for the
 *     modulation sources the note plans (the OPEN, ENV and KEY outputs) and
 *     for the panel (the look-ahead's latency).
 *
 * Neither is part of fm1_engine_t: the engine API is unchanged. A host
 * checks that the unit's engine is "gate" before calling either, passes the
 * handle fm1_engine_gate.create returned, and calls them on the audio task,
 * between renders (render_key is a render).
 *
 * Plain C99. MIT licence, like the rest of this repository.
 */
#ifndef FM1_GATE_H_
#define FM1_GATE_H_

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_gate_state {
  float gain;         /* the gain the last frame got, 0..1, after Mode and
                         Range: 1 is the input untouched, 0 is silence
                         (Range at -90 dB) */
  float env;          /* the envelope, 0 (closed: Range) .. 1 (open), in
                         either Mode, linear in dB: rises over Attack, falls
                         over Decay. The gain in Gate mode is
                         10^(-(1 - env) x Range dB / 20) */
  float key;          /* the level the detector read, linear, 0..1 (clamped):
                         the key after its filters and Link, peak-held */
  uint32_t open;      /* 1 from a trigger until Hold has run out (the attack,
                         the open gate, the hold), 0 while it decays and
                         while closed: a gate signal */
  uint32_t key_high;  /* the key's trigger state: 1 above Threshold until it
                         falls below Threshold - Return */
  uint32_t latency;   /* frames the audio is delayed by (Lookahead); during
                         a Lookahead crossfade, the new delay */
} fm1_gate_state_t;

/* The state after the last frame rendered. Before the first render: a
 * closed gate (gain the default Range's, env 0, key 0, open 0). NULL
 * instance or out: nothing is written. */
void fm1_gate_state(const void *instance, fm1_gate_state_t *out);

/* Render `frames` frames of io_lr in place, as render does, but detect from
 * key_lr: stereo interleaved, read-only, `frames` frames, never aliasing
 * io_lr, and never kept after the call (the instance holds no pointer, so
 * it is the same size on 32- and 64-bit builds). The key is guarded like
 * the input (NaN reads as 0, beyond +/-16 is clamped). key_lr NULL keys
 * from io_lr itself: render_key(self, io, NULL, n) is render(self, io, n),
 * bit for bit. Listen hears the key given here. */
void fm1_gate_render_key(void *instance, float *io_lr, const float *key_lr, uint32_t frames);

#ifdef __cplusplus
}
#endif

#endif /* FM1_GATE_H_ */

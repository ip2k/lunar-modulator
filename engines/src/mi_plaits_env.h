// mi_plaits_env.h -- what Macro and Macro Heavy share of Plaits' internal
// decay envelope and low-pass gate modes, from Voice::Render
// (plaits/dsp/voice.cc and voice.h, code by Emilie Gillet, MIT; vendored
// unmodified in third_party/mutable).
//
// On the module, with TRIG patched, a decay envelope starts at every trigger
// and reaches FREQ, TIMBRE and MORPH through the three attenuverters; Decay
// sets its length. The wrappers expose the attenuverters as Env Pitch, Env
// Timbre and Env Morph (page 3), at 0 by default, where the envelope reaches
// nothing and the output is what it was before they existed, byte for byte.
//
// The LPG mode picks how the low-pass gate is driven, after the module's
// three ways of patching it:
// - Gate: LEVEL patched. The gate follows the key, at the note's velocity,
//   and closes at key-up (the default, and the only mode before 2026-10-02).
// - Ping: TRIG alone. Each note-on pings the gate, which opens at a rate set
//   by the note's pitch and closes over Decay whether the key is held or not.
//   Plaits has no velocity on this path; here the voice is scaled by the
//   velocity's accent, which is 1 at velocity 127.
// - Off: the gate is bypassed, as Plaits bypasses it for its self-enveloped
//   models; the key gates a plain gain instead, released at key-up with the
//   gate's own release curve (Macro Heavy's note-off release), and scaled by
//   the velocity's accent as in Ping.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments.

#ifndef FM1_MI_PLAITS_ENV_H_
#define FM1_MI_PLAITS_ENV_H_

#include <algorithm>
#include <cmath>

namespace fm1 {
namespace plaits_env {

enum LpgMode { LPG_GATE, LPG_PING, LPG_OFF, LPG_MODE_COUNT };

const char *const kLpgModeNames[LPG_MODE_COUNT] = { "Gate", "Ping", "Off" };

// The LPG parameter's value as a mode (the host's float, rounded as Model is).
inline LpgMode ToLpgMode(float value) {
  return static_cast<LpgMode>(static_cast<int>(value + 0.5f));
}

// An attenuverter knob (-1..1) as the amount Voice::ApplyModulations applies:
// a dead band around the centre, then a square law to 0.9975 at either end.
// The same operations in the same order, so the result is upstream's float.
inline float AttenuverterAmount(float knob) {
  float amount = knob;
  amount *= std::max(fabsf(amount) - 0.05f, 0.05f);
  amount *= 1.05f;
  return amount;
}

// Voice::ApplyModulations with the internal envelope as the source, as on the
// module with TRIG patched and the CV input unpatched. `amount` comes from
// AttenuverterAmount; at 0 the value is `base`, unchanged, before the clamp.
inline float Modulate(float base, float amount, float envelope, float lo, float hi) {
  float value = base;
  value += amount * envelope;
  return value < lo ? lo : (value > hi ? hi : value);
}

// Velocity (0..1) as Plaits compresses LEVEL into an accent: 1 at 127.
inline float Accent(float velocity) {
  float accent = 1.3f * velocity / (0.3f + velocity);
  return accent > 1.0f ? 1.0f : accent;
}

}  // namespace plaits_env
}  // namespace fm1

#endif  // FM1_MI_PLAITS_ENV_H_

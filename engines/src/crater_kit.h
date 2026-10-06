// crater_kit.h -- what "Crater Kit" (src/crater_kit.cc) shares with its
// oracle (test/crater_oracle.cc): its grid, the rates it takes, its pads, the
// velocity law, its output scale, and the vendored kit inside an instance.
// Built only while the GPL switch is on (FM1_GPL_MODS).
// MIT licence (this file).

#ifndef FM1_CRATER_KIT_H_
#define FM1_CRATER_KIT_H_

#include <stdint.h>

extern "C" {
#include "dsp/drum808.h"
}

namespace fm1 {
namespace crater {

// The engine renders fm1-x0x's 808 in chunks of this many samples, counted
// from create; hits and parameter changes land on the next chunk, and SMOOTH
// ramps step once a chunk.
const uint32_t kChunk = 16;

// The host rates it takes. fm1-x0x's 808 is built for 44,100 Hz (its
// constants are computed for it), so the engine runs it at the host's rate
// only near that: the FM-1's 44,118 Hz is 0.7 cents sharp and 0.04 % short,
// less than fm1-x0x's own device, measured at about 44,145 Hz. Other hosts
// are refused, as the Plaits engines refuse rates above theirs.
const float kMinRate = 44000.0f;
const float kMaxRate = 44200.0f;

// The pads: notes 36-51, each one of the 808's sixteen sounds. A pad plays
// its sound on the machine's track with the track's switch set: a conga is
// its tom's channel switched to conga (so a tom and its conga never sound
// together, as on the machine), the claves share the rim shot's track and
// the maracas the clap's, each with a voice of its own.
const int kNumPads = 16;
const int kFirstNote = 36;
struct Pad {
  uint8_t sound;      // D8S_*
  uint8_t track;      // D8_*
  uint8_t sw;         // the track's switch: 1 conga, claves, maracas
};
const Pad kPads[kNumPads] = {
  { D8S_BD, D8_BD, 0 },   // 36 kick
  { D8S_RS, D8_RS, 0 },   // 37 rim shot
  { D8S_SD, D8_SD, 0 },   // 38 snare
  { D8S_CP, D8_CP, 0 },   // 39 clap
  { D8S_CL, D8_RS, 1 },   // 40 claves
  { D8S_LT, D8_LT, 0 },   // 41 low tom
  { D8S_CH, D8_CH, 0 },   // 42 closed hi-hat
  { D8S_LC, D8_LT, 1 },   // 43 low conga
  { D8S_MA, D8_CP, 1 },   // 44 maracas
  { D8S_MT, D8_MT, 0 },   // 45 mid tom
  { D8S_OH, D8_OH, 0 },   // 46 open hi-hat
  { D8S_MC, D8_MT, 1 },   // 47 mid conga
  { D8S_HT, D8_HT, 0 },   // 48 high tom
  { D8S_CY, D8_CY, 0 },   // 49 cymbal
  { D8S_HC, D8_HT, 1 },   // 50 high conga
  { D8S_CB, D8_CB, 0 },   // 51 cowbell
};

// MIDI velocity to fm1-x0x's trigger velocity (0..1, 1 the accent): 88 is
// the 808's normal hit (D8_VEL_NORMAL) and 127 its accent, as fm1-x0x's MIDI
// input maps them (its sequencer plays those two); below 88 a hit is quieter
// in proportion, as there; from 88 to 127 the trigger rises evenly, where
// fm1-x0x jumps to the accent at 127.
inline float VelocityOf(uint8_t v) {
  if (v >= 127) return 1.0f;
  if (v <= 88) return static_cast<float>(v) * (D8_VEL_NORMAL / 88.0f);
  return D8_VEL_NORMAL + static_cast<float>(v - 88) * ((1.0f - D8_VEL_NORMAL) / 39.0f);
}

// The kit's output scale at Volume 0.7: fm1-x0x's dry bus times this
// (crater_kit.cc says how it was set).
extern const float kOutScale;

}  // namespace crater
}  // namespace fm1

// The vendored kit inside an instance of the engine, for the oracle to copy
// and drive beside it.
extern "C" const drum808_t *fm1_crater_unit(const void *self);

#endif  // FM1_CRATER_KIT_H_

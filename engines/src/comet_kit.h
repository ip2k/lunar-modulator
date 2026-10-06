// comet_kit.h -- what "Comet Kit" (src/comet_kit.cc) shares with its oracle
// (test/comet_oracle.cc): its grid, the rates it takes, its pads and the
// vendored unit inside an instance. Built only while the GPL switch is on
// (FM1_GPL_MODS). MIT licence (this file).

#ifndef FM1_COMET_KIT_H_
#define FM1_COMET_KIT_H_

#include <stdint.h>

extern "C" {
#include "dsp/drum909.h"
}

namespace fm1 {
namespace comet_kit {

// The engine renders fm1-x0x's 909 kit in chunks of this many samples,
// counted from create; a hit or a parameter lands on the next chunk, and the
// SMOOTH ramps step once a chunk.
const uint32_t kChunk = 16;

// The host rates it takes (it runs at the host's own).
const float kMinRate = 40000.0f;
const float kMaxRate = 96000.0f;

// Sixteen pads on General MIDI's drum keys 36-51, as Drums and Sophie.
const int kNumPads = 16;
const int kFirstNote = 36;

// The 909 voice (drum909.h: DR_BD .. DR_RD) each pad strikes. Eleven
// voices on sixteen pads: a second snare, tom and closed hat on the keys
// General MIDI gives them, each a voicing of its own on the same voice.
const uint8_t kPadVoice[kNumPads] = {
  DR_BD,  // 36 Kick
  DR_RS,  // 37 Rim
  DR_SD,  // 38 Snare
  DR_CP,  // 39 Clap
  DR_SD,  // 40 Snare 2
  DR_LT,  // 41 Low Tom
  DR_CH,  // 42 Closed HH
  DR_LT,  // 43 Floor Tom (the low tom tuned up)
  DR_CH,  // 44 Pedal HH (the closed hat, longer)
  DR_MT,  // 45 Mid Tom
  DR_OH,  // 46 Open HH
  DR_MT,  // 47 Low-Mid (the mid tom tuned up)
  DR_HT,  // 48 High-Mid (the high tom tuned down)
  DR_CR,  // 49 Crash
  DR_HT,  // 50 High Tom
  DR_RD,  // 51 Ride
};

// The kit's output at Volume 0.7: the vendored kit's dry bus times this.
// The default kick struck at full velocity then peaks near -7.6 dBFS, as
// Drums' does near -8, and a groove of kick, snare, hats and a crash at
// full velocity stays under full scale (engines/README.md, "Comet Kit").
const float kOutGain = 0.2f;

// The per-pad knobs, in parameter order (src/comet_kit.cc, P_TUNE..P_DRIVE).
enum Slot { S_TUNE, S_DECAY, S_LEVEL, S_TONE, S_SNAP, S_SWEEP, S_DRIVE, S_COUNT };

}  // namespace comet_kit
}  // namespace fm1

// The vendored unit inside an instance of the engine, for the oracle to copy
// and drive beside it.
extern "C" const drum909_t *fm1_comet_kit_unit(const void *self);

#endif  // FM1_COMET_KIT_H_

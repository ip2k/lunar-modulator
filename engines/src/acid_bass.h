// acid_bass.h -- what "Acid Bass" (src/acid_bass.cc) shares with its oracle
// (test/acid_oracle.cc): its grid, the rates it takes, and the vendored unit
// inside an instance. Built only while the GPL switch is on (FM1_GPL_MODS).
// MIT licence (this file).

#ifndef FM1_ACID_BASS_H_
#define FM1_ACID_BASS_H_

#include <stdint.h>

extern "C" {
#include "dsp/bass303.h"
}

namespace fm1 {
namespace acid_bass {

// The engine renders fm1-x0x's bass in chunks of this many samples, counted
// from create; events land on the next chunk, and SMOOTH ramps step once a
// chunk.
const uint32_t kChunk = 16;

// The host rates it takes (it runs at the host's own).
const float kMinRate = 40000.0f;
const float kMaxRate = 96000.0f;

}  // namespace acid_bass
}  // namespace fm1

// The vendored unit inside an instance of the engine, for the oracle to copy
// and drive beside it.
extern "C" const bass303_t *fm1_acid_bass_unit(const void *self);

#endif  // FM1_ACID_BASS_H_

// note_offsets.h -- a voice's per-note offsets (engine API v2,
// set_param_note in include/fm1_engine.h; engines/README.md, "Per-note
// offsets"), shared by Macro, Macro Heavy, Six-Op FM and Shapes.
//
// A voice keeps one float for each of its engine's POLY parameters and one
// for its pitch, and a bit for each of them that is not 0. A voice with no
// bit set (no call since its note-on, or every offset back at 0) plays the
// engine-wide values, computed as they always were, so an engine renders
// byte for byte what it did before per-note offsets existed until a host
// sends one. No heap: the offsets live in the voice, inside the instance.
//
// MIT licence (this file).

#ifndef FM1_NOTE_OFFSETS_H_
#define FM1_NOTE_OFFSETS_H_

#include "fm1_engine.h"

#include <stdint.h>

namespace fm1 {

// Offsets for the parameters at indices kFirst .. kFirst + kCount - 1, which
// must hold every POLY parameter of the engine (the four engines' are
// contiguous), and for the note's pitch (FM1_PARAM_NOTE_PITCH).
template <int kFirst, int kCount>
struct NoteOffsets {
  static_assert(kFirst >= 0 && kCount >= 1 && kCount <= 31,
                "a bit for each offset and one for the pitch");

  float offset[kCount];  // in each parameter's units; 0 where the bit is clear
  float pitch;           // semitones
  uint32_t set;          // bit i: offset[i] != 0; bit kCount: pitch != 0

  // A voice's note-on, a steal, or a voice built anew: no offsets.
  void Clear() {
    for (int i = 0; i < kCount; ++i) offset[i] = 0.0f;
    pitch = 0.0f;
    set = 0;
  }

  bool any() const { return set != 0; }
  bool has(int index) const {
    return index >= kFirst && index < kFirst + kCount && ((set >> (index - kFirst)) & 1u);
  }
  bool has_pitch() const { return ((set >> kCount) & 1u) != 0; }

  // The offset set_param_note asked for, as a voice keeps it
  // (fm1_param_note_offset), or false when the index is neither the pitch
  // nor a POLY parameter of this table: the call is then ignored.
  static bool Normalise(const fm1_param_t *params, uint16_t index, float *offset) {
    if (index == FM1_PARAM_NOTE_PITCH) {
      *offset = fm1_param_note_offset(NULL, *offset);
      return true;
    }
    if (index < kFirst || index >= kFirst + kCount || !fm1_param_poly(&params[index])) {
      return false;
    }
    *offset = fm1_param_note_offset(&params[index], *offset);
    return true;
  }

  // Store an offset Normalise accepted. 0 (or -0) clears its bit, so the
  // voice is back on the engine-wide value exactly.
  void Set(uint16_t index, float value) {
    const int bit = index == FM1_PARAM_NOTE_PITCH ? kCount : index - kFirst;
    float *slot = bit == kCount ? &pitch : &offset[bit];
    if (value != 0.0f) {
      *slot = value;
      set |= 1u << bit;
    } else {
      *slot = 0.0f;
      set &= ~(1u << bit);
    }
  }

  // What this voice plays for parameter `index`: `base` itself without an
  // offset, else base + offset clamped as set_param clamps.
  float Value(const fm1_param_t *params, int index, float base) const {
    if (!has(index)) return base;
    return fm1_param_note_value(&params[index], base, offset[index - kFirst]);
  }
};

}  // namespace fm1

#endif  // FM1_NOTE_OFFSETS_H_

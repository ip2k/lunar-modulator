// glide.h -- glide (a per-note pitch slew) and the voice modes Poly, Mono
// and Legato, shared by Macro, Macro Heavy, Six-Op FM, FM6 and Shapes
// (engines/README.md, "Glide and voice modes"; the owner's decision of
// 2026-10-05: glide lives in the engines).
//
// Two parameters, appended to each engine's table:
//   - Glide, a time in ms on the LOG law (1 .. 5,000 ms). At its minimum,
//     1 ms, it is Off: no glide starts, and the engine renders what it
//     rendered before glide existed, byte for byte. Above it, a new note
//     played while another is held (fingered, or legato, portamento) starts
//     at the pitch the held note sounds and moves to its own in a straight
//     line in semitones, reaching it after the Glide time whatever the
//     interval (constant time). A note played with no key held starts on its
//     own pitch. SMOOTH and MOD: the time is read every control block, so a
//     glide under way follows a change.
//   - Voice Mode, Poly, Mono or Legato. Poly: every note takes a voice, as
//     before. Mono: one voice; a key pressed while another is held moves the
//     voice to it and restarts its envelopes; letting go of the newest key
//     while older ones are held moves the voice back to the newest of them,
//     without restarting. Legato: as Mono, but a key pressed while another
//     is held restarts nothing either. LATCH and MOD: read at note-on and
//     note-off; a change never cuts a sounding voice.
//
// The glide is a pitch offset in semitones that each voice adds to its
// note after the key and the bend, beside its per-note pitch offset
// (FM1_PARAM_NOTE_PITCH, note_offsets.h): the same pitch path. It moves
// once per control block, at the engine's own native samples, so the
// output does not depend on the host's block size; the first block of a
// glide plays the pitch it starts from. Arithmetic: subtractions, one
// division a block and one product a voice, never a multiply-add in one
// expression, and no libm, so every build computes the same bits.
//
// "The held note" is the newest voice whose key is down and which has a
// pitch to glide from: one that has rendered a block since its note-on, or
// that is itself gliding. Notes struck in the same control block (a chord)
// therefore never glide from each other.
//
// MIT licence (this file).

#ifndef FM1_GLIDE_H_
#define FM1_GLIDE_H_

#include "fm1_engine.h"

#include <stdint.h>

namespace fm1 {
namespace glide {

// The Glide parameter: ms, on the LOG law. Its minimum is Off.
const float kOffMs = 1.0f;
const float kMaxMs = 5000.0f;

// The Voice Mode list.
enum Mode { MODE_POLY, MODE_MONO, MODE_LEGATO, MODE_COUNT };
static const char *const kModeNames[MODE_COUNT] = { "Poly", "Mono", "Legato" };

// Their flags: Glide is a continuous time (SMOOTH, MOD, LOG), engine-wide
// (a glide is the move between two notes, not a property of one, so it is
// not POLY); Voice Mode is read at note events and cuts nothing.
const uint16_t kGlideFlags = FM1_PARAM_CONTINUOUS_LOG;
const uint16_t kModeFlags = FM1_PARAM_LATCH | FM1_PARAM_MOD;

inline Mode ToMode(float value) {
  const int m = static_cast<int>(value + 0.5f);
  return m <= 0 ? MODE_POLY : (m >= MODE_COUNT ? MODE_LEGATO : static_cast<Mode>(m));
}

// Whether a Glide time starts glides (above Off).
inline bool On(float ms) { return ms > kOffMs; }

// A control block of `block` samples at `rate` Hz, in ms.
inline float BlockMs(float rate, uint32_t block) {
  const float samples_ms = static_cast<float>(block) * 1000.0f;
  return samples_ms / rate;
}

// The share of a glide one control block covers at `ms` (clamped by
// set_param to kOffMs .. kMaxMs, so finite and positive).
inline float Increment(float block_ms, float ms) { return block_ms / ms; }

// A voice's glide.
struct Slew {
  float span;      // semitones: the pitch the glide started from, less the key
  float left;      // the share of span still to go: 1 at the start, then down to 0
  float offset;    // semitones the voice adds to its note at its next block
  uint8_t active;  // 1 while gliding (offset != 0 or more blocks to go)
  uint8_t fresh;   // 1 from a note-on to the voice's first block after it

  void Clear() {
    span = left = offset = 0.0f;
    active = fresh = 0;
  }

  // A note-on in this voice: no glide yet, and no pitch heard yet.
  void Begin() {
    Clear();
    fresh = 1;
  }

  // Glide from `from` semitones above the voice's key (below if negative)
  // to the key; 0 ends any glide. The next block plays from + key.
  void Start(float from) {
    span = offset = from;
    left = from != 0.0f ? 1.0f : 0.0f;
    active = from != 0.0f ? 1 : 0;
  }

  // Whether the voice has a pitch a new note can glide from.
  bool HasPitch() const { return !fresh || active; }

  // After a block has read `offset`: the next block's, `inc` further on.
  void Next(float inc) {
    fresh = 0;
    if (!active) return;
    left -= inc;
    if (!(left > 0.0f)) {
      left = offset = 0.0f;
      active = 0;
      return;
    }
    offset = span * left;
  }
};

// The keys held, oldest first, for Mono and Legato's return to a held key.
// Kept in every mode, so a change of mode finds the keys as they are. At
// most kMaxHeld; a key past that drops the oldest.
struct Held {
  static const int kMaxHeld = 16;
  uint8_t key[kMaxHeld];
  uint8_t n;

  void Clear() {
    for (int i = 0; i < kMaxHeld; ++i) key[i] = 0;
    n = 0;
  }

  void Remove(uint8_t k) {
    int w = 0;
    for (int r = 0; r < n && r < kMaxHeld; ++r) {
      if (key[r] != k) key[w++] = key[r];
    }
    n = static_cast<uint8_t>(w);
  }

  void Push(uint8_t k) {
    Remove(k);
    if (n >= kMaxHeld) {
      for (int i = 1; i < kMaxHeld; ++i) key[i - 1] = key[i];
      n = kMaxHeld - 1;
    }
    key[n++] = k;
  }

  // The newest key still held, if any.
  bool Top(uint8_t *k) const {
    if (!n || n > kMaxHeld) return false;
    *k = key[n - 1];
    return true;
  }
};

// The voice a Mono or Legato note goes to: the newest active one (by its
// note-on order, `age`), or NULL when none sounds.
template <class V>
V *Newest(V *voice, int n) {
  V *best = NULL;
  for (int i = 0; i < n; ++i) {
    if (voice[i].active && (!best || voice[i].age > best->age)) best = &voice[i];
  }
  return best;
}

// The held note a Poly note glides from: the newest voice whose key is down
// and which has a pitch (Slew::HasPitch), or NULL.
template <class V>
const V *Source(const V *voice, int n) {
  const V *best = NULL;
  for (int i = 0; i < n; ++i) {
    const V &v = voice[i];
    if (v.active && v.gate && v.glide.HasPitch() && (!best || v.age > best->age)) best = &v;
  }
  return best;
}

// The pitch a voice sounds at its next block, in keys (no bend, no
// per-note offset): what a new note glides from.
template <class V>
float Pitch(const V &v) {
  float from = static_cast<float>(v.key);
  from += v.glide.offset;
  return from;
}

// What a note-on does under the voice modes, decided before any voice
// changes. mono: the voice a Mono or Legato note takes (NULL in Poly, or
// when none sounds). legato: Legato with a held note to move from, so the
// voice changes key without restarting. glides: the note glides, from
// `from` keys.
template <class V>
struct Plan {
  V *mono;
  bool legato;
  bool glides;
  float from;
};

template <class V>
Plan<V> PlanNoteOn(V *voice, int n, Mode mode, float glide_ms) {
  Plan<V> p;
  p.mono = mode == MODE_POLY ? NULL : Newest(voice, n);
  const V *src;
  if (mode == MODE_POLY) {
    src = Source(static_cast<const V *>(voice), n);
  } else {
    src = p.mono && p.mono->gate && p.mono->glide.HasPitch() ? p.mono : NULL;
  }
  p.legato = mode == MODE_LEGATO && src != NULL;
  p.glides = src != NULL && On(glide_ms);
  p.from = p.glides ? Pitch(*src) : 0.0f;
  return p;
}

// Starts a voice's glide for a note on `key` under plan p (none when p
// does not glide).
template <class V>
void StartFor(V *v, const Plan<V> &p, uint8_t key) {
  if (!p.glides) {
    v->glide.Start(0.0f);
    return;
  }
  float span = p.from;
  span -= static_cast<float>(key);
  v->glide.Start(span);
}

}  // namespace glide
}  // namespace fm1

#endif  // FM1_GLIDE_H_

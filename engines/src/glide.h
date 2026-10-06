// glide.h -- glide (a per-note pitch slew) and the voice modes Poly, Mono
// and Legato, shared by Macro, Macro Heavy, Six-Op FM, FM6 and Shapes
// (engines/README.md, "Glide and voice modes"; the owner's decisions of
// 2026-10-05, glide lives in the engines, and 2026-10-06, its modes).
//
// Four parameters, appended to each engine's table, on a page of their own:
//   - Glide, a time in ms on the LOG law (1 .. 5,000 ms, default 100): how
//     long a glide takes (Time Mode Time), or how long it takes per octave
//     (Time Mode Rate). SMOOTH and MOD: the time is read every control
//     block, so a glide under way follows a change.
//   - Voice Mode, Poly, Mono or Legato. Poly: every note takes a voice, as
//     before. Mono: one voice; a key pressed while another is held moves the
//     voice to it and restarts its envelopes; letting go of the newest key
//     while older ones are held moves the voice back to the newest of them,
//     without restarting. Legato: as Mono, but a key pressed while another
//     is held restarts nothing either. LATCH and MOD: read at note-on and
//     note-off; a change never cuts a sounding voice.
//   - Glide Mode, Off, Legato or Always. Off (the default): nothing glides,
//     and a control block does no glide arithmetic at all, so the engine
//     renders what it rendered before glide existed, byte for byte. Legato
//     (fingered portamento): a note played while another key is held starts
//     at the pitch the held note sounds; a note played with no key held
//     starts on its own pitch. Always (full-time portamento, as the stock
//     FM-1 offers): every note starts at the pitch of the last note played,
//     held or not, sounding or not. LATCH and MOD: read at note-on and
//     note-off; a glide under way finishes whatever it is switched to.
//   - Time Mode, Time or Rate. Time: a glide takes the Glide time whatever
//     the interval (constant time). Rate: Glide is the time per octave, so a
//     wider interval takes longer (constant rate). LATCH and MOD: read when
//     a glide starts, which keeps its law to the end.
// The return to a held key in Mono and Legato glides under Legato and Always
// alike.
//
// Saving (engine API v4, the state core, had not landed when Glide Mode and
// Time Mode came, 2026-10-06): all four are engine-wide, one value each, in
// each engine's value_[] and, for Glide (SMOOTH), its ramp's target,
// smooth_[P_GLIDE].target. v4's get_param must report that target for
// Glide (not the ramped value_[P_GLIDE]) and value_[] for the three
// switches; none is per voice or per pad, so none needs a focus flag.
//
// The glide is a pitch offset in semitones that each voice adds to its
// note after the key and the bend, beside its per-note pitch offset
// (FM1_PARAM_NOTE_PITCH, note_offsets.h): the same pitch path. It moves
// once per control block, at the engine's own native samples, so the
// output does not depend on the host's block size; the first block of a
// glide plays the pitch it starts from. Time: each block takes block_ms /
// Glide off the share still to go, and the offset is the start's interval
// times that share. Rate: each block moves the offset 12 x block_ms /
// Glide semitones toward 0. Arithmetic: subtractions, one division in a
// block where some voice glides and one product a gliding voice, never a
// multiply-add in one expression, and no libm, so every build computes the
// same bits.
//
// "The held note" (Legato) is the newest voice whose key is down and which
// has a pitch to glide from: one that has rendered a block since its
// note-on, or that is itself gliding. "The last note" (Always) is the newest
// voice that has played a note and has a pitch, whether it still sounds or
// not. Notes struck in the same control block (a chord) therefore never
// glide from each other.
//
// MIT licence (this file).

#ifndef FM1_GLIDE_H_
#define FM1_GLIDE_H_

#include "fm1_engine.h"

#include <stdint.h>

namespace fm1 {
namespace glide {

// The Glide parameter: ms, on the LOG law.
const float kMinMs = 1.0f;
const float kMaxMs = 5000.0f;
const float kDefaultMs = 100.0f;

// Semitones in the octave a Rate glide's time is given for.
const float kSemitonesPerOctave = 12.0f;

// The Voice Mode list.
enum Mode { MODE_POLY, MODE_MONO, MODE_LEGATO, MODE_COUNT };
static const char *const kModeNames[MODE_COUNT] = { "Poly", "Mono", "Legato" };

// The Glide Mode list.
enum GlideMode { GLIDE_OFF, GLIDE_LEGATO, GLIDE_ALWAYS, GLIDE_MODE_COUNT };
static const char *const kGlideModeNames[GLIDE_MODE_COUNT] = { "Off", "Legato", "Always" };

// The Time Mode list.
enum TimeMode { TIME_TIME, TIME_RATE, TIME_MODE_COUNT };
static const char *const kTimeModeNames[TIME_MODE_COUNT] = { "Time", "Rate" };

// Their flags: Glide is a continuous time (SMOOTH, MOD, LOG), engine-wide
// (a glide is the move between two notes, not a property of one, so it is
// not POLY); the three switches are read at note events and cut nothing.
const uint16_t kGlideFlags = FM1_PARAM_CONTINUOUS_LOG;
const uint16_t kModeFlags = FM1_PARAM_LATCH | FM1_PARAM_MOD;

// A switch's value as its entry: rounded, clamped to 0 .. count - 1.
inline int ToEntry(float value, int count) {
  const int m = static_cast<int>(value + 0.5f);
  return m <= 0 ? 0 : (m >= count ? count - 1 : m);
}

inline Mode ToMode(float value) { return static_cast<Mode>(ToEntry(value, MODE_COUNT)); }

// What the four parameters say at a note event.
struct Config {
  Mode voice;
  GlideMode glide;
  uint8_t rate;     // 1: Time Mode Rate
};

inline Config Read(float voice_mode, float glide_mode, float time_mode) {
  Config c;
  c.voice = ToMode(voice_mode);
  c.glide = static_cast<GlideMode>(ToEntry(glide_mode, GLIDE_MODE_COUNT));
  c.rate = ToEntry(time_mode, TIME_MODE_COUNT) == TIME_RATE ? 1 : 0;
  return c;
}

// A control block of `block` samples at `rate` Hz, in ms.
inline float BlockMs(float rate, uint32_t block) {
  const float samples_ms = static_cast<float>(block) * 1000.0f;
  return samples_ms / rate;
}

// The share of a glide one control block covers at `ms` (clamped by
// set_param to kMinMs .. kMaxMs, so finite and positive).
inline float Increment(float block_ms, float ms) { return block_ms / ms; }

// One control block's step: the Increment, computed the first time a
// gliding voice asks for it, so a block in which nothing glides (Glide Mode
// Off, or no glide under way) does no division.
class Step {
 public:
  Step() : block_ms_(0.0f), ms_(1.0f), inc_(-1.0f) {}
  Step(float block_ms, float ms) : block_ms_(block_ms), ms_(ms), inc_(-1.0f) {}
  float Get() {
    if (inc_ < 0.0f) inc_ = Increment(block_ms_, ms_);
    return inc_;
  }

 private:
  float block_ms_, ms_, inc_;
};

// A voice's glide.
struct Slew {
  float span;      // semitones: the pitch the glide started from, less the key
  float left;      // Time: the share of span still to go, 1 at the start, then down to 0
  float offset;    // semitones the voice adds to its note at its next block
  uint8_t active;  // 1 while gliding (offset != 0 or more blocks to go)
  uint8_t fresh;   // 1 from a note-on to the voice's first block after it
  uint8_t rate;    // 1: this glide moves at a constant rate (Time Mode Rate)
  uint8_t played;  // 1 once a note has been struck in this voice since Clear

  void Clear() {
    span = left = offset = 0.0f;
    active = fresh = rate = played = 0;
  }

  // A note-on in this voice: no glide yet, and no pitch heard yet.
  void Begin() {
    Clear();
    fresh = 1;
    played = 1;
  }

  // Glide from `from` semitones above the voice's key (below if negative)
  // to the key, at a constant rate when `constant_rate`; 0 ends any glide.
  // The next block plays from + key.
  void Start(float from, uint8_t constant_rate) {
    span = offset = from;
    left = from != 0.0f ? 1.0f : 0.0f;
    active = from != 0.0f ? 1 : 0;
    rate = active ? constant_rate : 0;
  }

  // Whether the voice has a pitch a new note can glide from.
  bool HasPitch() const { return !fresh || active; }

  // After a block has read `offset`: the next block's, one step further on.
  void Next(Step &step) {
    fresh = 0;
    if (!active) return;
    const float inc = step.Get();
    if (rate) {
      // Rate: Glide ms an octave, so 12 x inc semitones a block toward 0.
      const float d = inc * kSemitonesPerOctave;
      if (span > 0.0f) {
        offset -= d;
        if (offset > 0.0f) return;
      } else {
        offset += d;
        if (offset < 0.0f) return;
      }
      left = offset = 0.0f;
      active = 0;
      rate = 0;
      return;
    }
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

// The held note a Poly note glides from under Legato: the newest voice
// whose key is down and which has a pitch (Slew::HasPitch), or NULL.
template <class V>
const V *Source(const V *voice, int n) {
  const V *best = NULL;
  for (int i = 0; i < n; ++i) {
    const V &v = voice[i];
    if (v.active && v.gate && v.glide.HasPitch() && (!best || v.age > best->age)) best = &v;
  }
  return best;
}

// The last note, which every note glides from under Always: the newest
// voice that has played a note and has a pitch, sounding or not (an ended
// voice keeps its key, its age and where its glide was), or NULL before the
// first note.
template <class V>
const V *Last(const V *voice, int n) {
  const V *best = NULL;
  for (int i = 0; i < n; ++i) {
    const V &v = voice[i];
    if (v.glide.played && v.glide.HasPitch() && (!best || v.age > best->age)) best = &v;
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

// What a note-on does under the voice and glide modes, decided before any
// voice changes. mono: the voice a Mono or Legato note takes (NULL in Poly,
// or when none sounds). legato: Legato with a held note to move from, so the
// voice changes key without restarting. glides: the note glides, from
// `from` keys, at a constant rate when `rate`.
template <class V>
struct Plan {
  V *mono;
  bool legato;
  bool glides;
  uint8_t rate;
  float from;
};

template <class V>
Plan<V> PlanNoteOn(V *voice, int n, const Config &c) {
  Plan<V> p;
  p.mono = c.voice == MODE_POLY ? NULL : Newest(voice, n);
  const V *held;
  if (c.voice == MODE_POLY) {
    held = Source(static_cast<const V *>(voice), n);
  } else {
    held = p.mono && p.mono->gate && p.mono->glide.HasPitch() ? p.mono : NULL;
  }
  p.legato = c.voice == MODE_LEGATO && held != NULL;
  const V *src = NULL;
  if (c.glide == GLIDE_LEGATO) src = held;
  if (c.glide == GLIDE_ALWAYS) src = Last(static_cast<const V *>(voice), n);
  p.glides = src != NULL;
  p.rate = c.rate;
  p.from = p.glides ? Pitch(*src) : 0.0f;
  return p;
}

// What a note-off of `key` does in Mono and Legato: when the newest voice
// plays that key with its gate up and other keys are held (`held`, with
// `key` already removed), it moves back to the newest of them, *to,
// without restarting, gliding from where it is unless Glide Mode is Off.
// p.mono is that voice, or NULL when nothing moves. Nor does it move when
// another held voice already sounds *to (keys held in Poly, then a switch
// to Mono): it releases instead, so no key ever sounds twice.
template <class V>
Plan<V> PlanNoteOff(V *voice, int n, const Held &held, uint8_t key, const Config &c,
                    uint8_t *to) {
  Plan<V> p;
  p.mono = Newest(voice, n);
  if (!p.mono || !p.mono->gate || p.mono->key != key || !held.Top(to)) p.mono = NULL;
  for (int i = 0; p.mono && i < n; ++i) {
    const V &v = voice[i];
    if (&v != p.mono && v.active && v.gate && v.key == *to) p.mono = NULL;
  }
  p.legato = p.mono != NULL;
  p.glides = p.mono != NULL && c.glide != GLIDE_OFF && p.mono->glide.HasPitch();
  p.rate = c.rate;
  p.from = p.glides ? Pitch(*p.mono) : 0.0f;
  return p;
}

// Starts a voice's glide for a note on `key` under plan p (none when p
// does not glide).
template <class V>
void StartFor(V *v, const Plan<V> &p, uint8_t key) {
  if (!p.glides) {
    v->glide.Start(0.0f, 0);
    return;
  }
  float span = p.from;
  span -= static_cast<float>(key);
  v->glide.Start(span, p.rate);
}

}  // namespace glide
}  // namespace fm1

#endif  // FM1_GLIDE_H_

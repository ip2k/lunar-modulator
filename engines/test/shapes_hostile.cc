// shapes_hostile.cc -- fm1-shapes-hostile: a reviewer's hostile checks of
// Shapes at Braids' edges (src/mi_shapes.cc; engines/README.md, "Shapes:
// where Braids is held"), beyond tests/test_engines_shapes_edges.py, whose
// sweep sets Timbre and Color only at 0, 1/2 and 1 and the pitch in whole
// semitones:
//
//   - schedule: a random script on every shape, anything the engine API
//     allows: notes on any key, Timbre, Color, Attack, Release and Volume
//     anywhere (NaN and infinities included), bends and pitch offsets
//     anywhere in +/-48 (offsets also +/-inf and NaN), per-note Timbre and
//     Color offsets to +/-inf and NaN, and Shape switched while notes sound,
//     favouring the shapes with edges. Rendered in blocks of 64, 1, 7 and
//     random 1-64 frames and from memory filled with 0xFF and 0xA5:
//     every render the same bits, finite and sounding. Under CI's sanitizer
//     build no report, which is the check that matters: it reaches Timbre,
//     Color and pitch values between the ends;
//   - above: on every shape, a script whose every voice sits at MIDI 127.99
//     or above (keys 81-127 under bends of 47-48, pitch offsets 0-48),
//     Timbre and Color turning, renders the bits of the same script with
//     each note held at exactly MIDI 127.9921875 (Braids' 16,383);
//   - comb: Comb with every voice at Braids pitch 0 (keys 0-47 under bends
//     of -48 to -47, pitch offsets -48 to 0) and Timbre turning anywhere in
//     0-0.375, per-note Timbre offsets down to -inf, renders the bits of
//     Timbre held at 12,288, where the comb's own pitch is MIDI -16;
//   - wave_line: Wave Line on any key, bend and pitch offset with Timbre
//     turning anywhere in 0.9845-1, per-note offsets up to +inf, renders the
//     bits of Timbre held at 32,255.
//
// Prints one JSON object; tests/test_engines_shapes_hostile.py reads it. A
// desktop tool: it allocates and prints. MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vector>

#include "stmlib/utils/random.h"

extern "C" const fm1_engine_t fm1_engine_shapes;

namespace {

const fm1_engine_t *const E = &fm1_engine_shapes;
enum { P_SHAPE, P_TIMBRE, P_COLOR, P_ATTACK, P_RELEASE, P_VOLUME };
const int kNumShapes = 47;
const int kComb = 15, kWaveLine = 39;
// Exactly MIDI 127.9921875, Braids' pitch 16,383 (x 128).
const float kTop = 16383.0f / 128.0f;
// The 0..1 knobs the wrapper turns into Timbre 12,288 and 32,255 (value x
// 32,767 in float, truncated).
const float kComb12288 = 12288.5f / 32767.0f;
const float kWave32255 = 32255.5f / 32767.0f;

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Unit() { return (Next() >> 8) * (1.0f / 16777216.0f); }   // [0, 1)
  float In(float a, float b) { return a + (b - a) * Unit(); }
};

enum Kind { ON, OFF, PARAM, BEND, NOTE };
struct Event { uint32_t frame; Kind kind; uint8_t key; uint16_t index; float value; };
struct Script { int shape; uint32_t frames; std::vector<Event> events; };

uint32_t Hash(const std::vector<float> &v) {         // FNV-1a over the bits
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < v.size(); ++i) {
    uint32_t b;
    memcpy(&b, &v[i], sizeof b);
    for (int k = 0; k < 4; ++k) { h ^= (b >> (8 * k)) & 0xFFu; h *= 16777619u; }
  }
  return h;
}

// pattern: 64 for 64-frame blocks, k > 0 for k-frame blocks, -1 for random
// 1-64. A block never runs past the next event's frame. Braids draws from
// stmlib's one process-wide generator, so each render starts it where a
// fresh process does (0x21, stmlib/utils/random.cc), as fm1-render runs.
std::vector<float> Render(const Script &s, int pattern, int fill, uint32_t seed) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  const size_t n = E->instance_size(&host);
  std::vector<unsigned char> raw(n + 16);
  unsigned char *mem = &raw[0] + ((16 - (reinterpret_cast<uintptr_t>(&raw[0]) & 15)) & 15);
  memset(mem, fill, n);
  stmlib::Random::Seed(0x21);
  void *self = E->create(mem, &host);
  if (!self) { fprintf(stderr, "shapes refused 44,118 Hz\n"); exit(2); }
  E->set_param(self, P_SHAPE, static_cast<float>(s.shape));
  std::vector<float> out(2 * s.frames);
  Lcg rng = { seed };
  size_t c = 0;
  for (uint32_t f = 0; f < s.frames;) {
    while (c < s.events.size() && s.events[c].frame == f) {
      const Event &x = s.events[c++];
      switch (x.kind) {
        case ON: E->note_on(self, x.key, static_cast<uint8_t>(x.value)); break;
        case OFF: E->note_off(self, x.key); break;
        case PARAM: E->set_param(self, x.index, x.value); break;
        case BEND: E->pitch_bend(self, x.value); break;
        case NOTE: E->set_param_note(self, x.key, x.index, x.value); break;
      }
    }
    uint32_t len = pattern > 0 ? static_cast<uint32_t>(pattern) : 1u + rng.Next() % 64u;
    if (len > s.frames - f) len = s.frames - f;
    if (c < s.events.size() && s.events[c].frame < f + len) len = s.events[c].frame - f;
    E->render(self, &out[2 * f], len);
    f += len;
  }
  E->destroy(self);
  return out;
}

float Wild(Lcg *rng, float value) {
  switch (rng->Next() % 16) {
    case 0: return NAN;
    case 1: return INFINITY;
    case 2: return -INFINITY;
    case 3: return rng->Next() & 1 ? 0.0f : 1.0f;
    default: return value;
  }
}

// Steps of 0..900 frames; a note on or off, a parameter, a bend or a
// per-note offset at each. Release is kept short so voices end and are
// stolen. Kinds other than "schedule" constrain what they draw.
enum Mode { SCHEDULE, ABOVE, COMB, WAVE_LINE };

Script Make(Mode mode, int shape, uint32_t seed, int steps) {
  Script s;
  s.shape = shape;
  Lcg rng = { seed * 2654435761u + static_cast<uint32_t>(shape) * 40503u + mode };
  static const int kEdgeShapes[] = { kComb, kWaveLine, 31, 17, 18, 19, 20, 7, 8 };
  uint8_t lo = 0, hi = 127;
  float bend_lo = -48.0f, bend_hi = 48.0f, off_lo = -48.0f, off_hi = 48.0f;
  float timbre_lo = 0.0f, timbre_hi = 1.0f;
  if (mode == ABOVE) { lo = 81; bend_lo = 47.0f; off_lo = 0.0f; }
  if (mode == COMB) { hi = 47; bend_hi = -47.0f; off_hi = 0.0f; timbre_hi = 0.375f; }
  if (mode == WAVE_LINE) timbre_lo = 0.9845f;
  uint32_t t = 0;
  s.events.push_back(Event{ 0, BEND, 0, 0, rng.In(bend_lo, bend_hi) });
  s.events.push_back(Event{ 0, PARAM, 0, P_RELEASE, rng.In(0.0f, 0.3f) });
  s.events.push_back(Event{ 0, PARAM, 0, P_TIMBRE, rng.In(timbre_lo, timbre_hi) });
  for (int i = 0; i < steps; ++i) {
    t += rng.Next() % 900u;
    Event x = { t, ON, static_cast<uint8_t>(lo + rng.Next() % (hi - lo + 1u)), 0, 0.0f };
    const uint32_t r = rng.Next() % 100u;
    if (r < 25) {
      x.kind = ON;
      x.value = static_cast<float>(1u + rng.Next() % 127u);
    } else if (r < 38) {
      x.kind = OFF;
    } else if (r < 62) {
      x.kind = PARAM;
      x.index = static_cast<uint16_t>(P_TIMBRE + rng.Next() % 5u);
      x.value = x.index == P_TIMBRE ? rng.In(timbre_lo, timbre_hi) : rng.Unit();
      if (x.index == P_RELEASE || x.index == P_ATTACK) x.value *= 0.3f;
      if (mode == SCHEDULE) x.value = Wild(&rng, x.value);
    } else if (r < 72) {
      x.kind = BEND;
      x.value = rng.Next() % 4u ? rng.In(bend_lo, bend_hi) : (rng.Next() & 1 ? bend_lo : bend_hi);
    } else if (r < 94) {
      x.kind = NOTE;
      const uint32_t which = rng.Next() % 3u;
      if (which == 0) {
        x.index = FM1_PARAM_NOTE_PITCH;
        x.value = rng.Next() % 4u ? rng.In(off_lo, off_hi) : (rng.Next() & 1 ? off_lo : off_hi);
        if (mode == SCHEDULE) x.value = rng.Next() % 8u ? x.value : Wild(&rng, x.value);
      } else {
        x.index = static_cast<uint16_t>(which);           // Timbre or Color
        x.value = rng.In(-1.0f, 1.0f);
        if (which == P_TIMBRE && mode == COMB) x.value = rng.Next() & 1 ? -INFINITY : rng.In(-1.0f, 0.0f);
        if (which == P_TIMBRE && mode == WAVE_LINE) x.value = rng.Next() & 1 ? INFINITY : rng.In(0.0f, 1.0f);
        if (mode == SCHEDULE) x.value = Wild(&rng, x.value);
      }
    } else if (mode == SCHEDULE) {
      x.kind = PARAM;
      x.index = P_SHAPE;
      x.value = static_cast<float>(rng.Next() & 1 ? kEdgeShapes[rng.Next() % 9u]
                                                  : static_cast<int>(rng.Next() % kNumShapes));
    } else {
      x.kind = OFF;
    }
    s.events.push_back(x);
  }
  s.frames = t + 6000;
  return s;
}

// What the clamps say the constrained scripts play: above, every note at
// exactly MIDI 127.9921875 (bend 0 and each note's offset to it, set with
// the note); comb and wave_line, Timbre held at the clamp, no Timbre offsets.
Script Held(const Script &a, Mode mode) {
  Script b = a;
  b.events.clear();
  for (size_t i = 0; i < a.events.size(); ++i) {
    Event x = a.events[i];
    if (mode == ABOVE) {
      if (x.kind == BEND) x.value = 0.0f;
      if (x.kind == NOTE && x.index == FM1_PARAM_NOTE_PITCH) continue;
      b.events.push_back(x);
      if (x.kind == ON) {
        b.events.push_back(Event{ x.frame, NOTE, x.key, FM1_PARAM_NOTE_PITCH, kTop - x.key });
      }
      continue;
    }
    if (x.kind == NOTE && x.index == P_TIMBRE) continue;
    if (x.kind == PARAM && x.index == P_TIMBRE) x.value = mode == COMB ? kComb12288 : kWave32255;
    b.events.push_back(x);
  }
  return b;
}

void Stats(const std::vector<float> &v, bool *finite, float *peak) {
  *finite = true;
  *peak = 0.0f;
  for (size_t i = 0; i < v.size(); ++i) {
    if (!isfinite(v[i])) *finite = false;
    else if (fabsf(v[i]) > *peak) *peak = fabsf(v[i]);
  }
}

void Schedule() {
  const int patterns[] = { 1, 7, -1 };
  const int fills[] = { 0xFF, 0xA5 };
  printf("\"schedule\":[");
  for (int shape = 0; shape < kNumShapes; ++shape) {
    const Script s = Make(SCHEDULE, shape, 1, 120);
    const std::vector<float> ref = Render(s, 64, 0, 1);
    bool finite;
    float peak;
    Stats(ref, &finite, &peak);
    const uint32_t h = Hash(ref);
    int same = 0, tried = 0;
    for (int p : patterns) { ++tried; same += Hash(Render(s, p, 0, 7u + p)) == h; }
    for (int fill : fills) { ++tried; same += Hash(Render(s, -1, fill, 99u + fill)) == h; }
    printf("%s{\"shape\":%d,\"events\":%u,\"finite\":%s,\"peak\":%.6g,\"same\":%d,\"tried\":%d}",
           shape ? "," : "", shape, static_cast<unsigned>(s.events.size()),
           finite ? "true" : "false", peak, same, tried);
  }
  printf("]");
}

void Equal(const char *name, Mode mode, int first, int last) {
  printf("\"%s\":[", name);
  for (int shape = first; shape <= last; ++shape) {
    for (uint32_t seed = 1; seed <= (first == last ? 6u : 1u); ++seed) {
      const Script a = Make(mode, shape, seed, 100);
      const std::vector<float> got = Render(a, -1, 0xA5, seed);
      const std::vector<float> want = Render(Held(a, mode), 64, 0, 1);
      bool finite;
      float peak;
      Stats(got, &finite, &peak);
      printf("%s{\"shape\":%d,\"seed\":%u,\"events\":%u,\"finite\":%s,\"peak\":%.6g,"
             "\"same\":%s}", shape == first && seed == 1 ? "" : ",", shape, seed,
             static_cast<unsigned>(a.events.size()), finite ? "true" : "false", peak,
             got.size() == want.size() &&
             memcmp(&got[0], &want[0], got.size() * sizeof(float)) == 0 ? "true" : "false");
    }
  }
  printf("]");
}

}  // namespace

int main() {
  printf("{");
  Schedule(); printf(",");
  Equal("above", ABOVE, 0, kNumShapes - 1); printf(",");
  Equal("comb", COMB, kComb, kComb); printf(",");
  Equal("wave_line", WAVE_LINE, kWaveLine, kWaveLine);
  printf("}\n");
  return 0;
}

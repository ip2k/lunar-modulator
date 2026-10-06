// fx_limit.cc -- "Limiter": a look-ahead brickwall limiter (FM1_KIND_AUDIO_FX),
// written for this repository, MIT licence. Notes in engines/README.md
// ("Limiter"). Mode ROUND's stage (RoundStep) is ported from Airwindows
// ClipOnly2: Copyright (c) 2018 Chris Johnson (Airwindows' LICENSE); its file
// says "Copyright (c) 2016 airwindows, Airwindows uses the MIT license"
// (the licence: engines/third_party/airwindows/LICENSE; the commit and what
// was taken: its UPSTREAM.md).
//
// Per frame, both channels:
//
//   guard -> x Drive = u -> lookahead line (the input, Drive and Ceiling)
//         |
//         +-> detector |u| (Link) -> required gain -> envelope (instant
//             attack, Release) -> quantise -> hold (minimum over D + 1
//             frames) -> two box filters (D frames together) = gain a
//
//   line, D frames later: u x a -> output stage (Mode) -> Mix with the
//   delayed dry input
//
// The gain path is Geraint Luff's design ("Designing a straightforward
// limiter", Signalsmith Audio, 2022): a moving minimum of the required gain,
// then moving averages whose lengths add up to the minimum's window, ahead of
// a delay of the same length. Every gain the averages see at frame n is a
// minimum over a window that contains frame n - D, so their mean is never
// above the gain frame n - D needed: the audio, delayed by D, is multiplied
// by a gain that has already come down to what its peak requires, along a
// smooth ramp, and the output never exceeds the ceiling. No code is taken
// from the article or from Signalsmith's library; the arithmetic below is our
// own, in integers where it can be:
//
//   - The envelope's gain, capped at exactly what this frame needs, is
//     quantised (rounded down) to 22 fractional bits; the minimum and both
//     sums are exact integer arithmetic. The first box has a power-of-two length, so its
//     mean is a shift (rounding down again); the second box's sum is
//     converted to float once. The sums cannot drift, and a run of unity
//     gains gives a gain of exactly 1.0f, so the limiter is bit-transparent
//     whenever it is not reducing.
//   - Float rounding in that last conversion could leave a product an ulp
//     over the ceiling; a final clamp to +/-Ceiling makes the bound exact.
//
// Release is a one-pole recovery of the envelope's gain reduction (1 - gain)
// towards what the signal needs; a louder peak takes over at once. Working
// in the reduction keeps full float resolution near unity gain: the recovery
// never stalls an ulp short of 1. (Deep in limiting, 1 - reduction loses
// relative precision instead; the cap above takes care of that.)
//
// Lookahead 0: no delay, so no ramp. An instant attack would flatten the
// leading edge of every louder peak at the ceiling, a hard clip. Instead the
// envelope attacks over 1 ms and aims 1 dB under the ceiling, and a soft clip
// from there (-1 dB) towards the ceiling catches what the attack lets
// through: the soft-clip safety. Below -1 dB the signal is untouched.
//
// Mode SOFT CLIP: the envelope lets peaks reach four times the ceiling
// (+12 dB) and a soft clip with its knee 6 dB under the ceiling rounds them
// off; the output stays under the ceiling (at most -0.56 dB under it). The
// line stores the Mode (its 5 ms glide) with each frame, so a frame leaves
// through the stage its gain was computed for; and the envelope aims at
// four times the ceiling only once the glide has reached SOFT CLIP, since
// the blend of the two stages part-way would pass the ceiling with a gain
// made for +12 dB. A Mode change in either direction therefore never needs
// the final clamp.
//
// Mode ROUND (2026-10-05): a gentle final rounding clip after Airwindows
// ClipOnly2 (Chris Johnson, MIT; its loop is ported below, in single
// precision, scaled to the ceiling). The envelope lets peaks reach 3 dB
// over the ceiling; the stage leaves every frame within +/-c as it came
// (bit for bit) and replaces each over by c hardness + (the frame before)
// softness, hardness 0.7390851 (the root of x = cos x) and softness its
// complement, so an over lands between the frame before it and the ceiling;
// the last frame of an over is then put right once the next frame is known,
// towards it when it is lower, else further towards c. ClipOnly2 gives each
// frame out one sample late for that; here the stage reads the frame after
// from the line (its input times the frame's gain), so ROUND adds no delay
// and the Lookahead is the latency in every Mode. Where the gain moves from
// one frame to the next, that look ahead uses this frame's gain; with the
// gain still, the output is ClipOnly2's to float rounding [verified:
// fm1-limit-test "round", within 7e-8 of its recurrence in double]. At
// Lookahead 0 there is no next frame: each over is rounded on the way in
// and passed on at once. Above 4c, ClipOnly2's input clamp (4 at full
// scale) holds what the replaced value can see. The line keeps ROUND's share
// beside SOFT CLIP's, and its aim, as SOFT CLIP's, changes only once the
// glide has reached it. At its other Modes the stage computes what it did
// before ROUND, bit for bit; ClipOnly2's own spacing at rates above 88.2 kHz
// (looking 2-16 samples ahead) is not taken: ROUND looks one frame ahead at
// any rate.
//
// Lookahead changes: the line's read crossfades from the old delay to the
// new over 5 ms, and each tap keeps a gain path of its own while they fade,
// so neither ever steps. The old tap goes on with its boxes, untouched; the
// new tap gets a second set of boxes, its own length, that starts at the
// held gain (as on create) and is faded in from nothing, so its start is
// smooth however far the old gain had ramped. Both sets average the one
// hold, which spans the longer delay plus one frame while they fade, so
// every value either set averages is a minimum over a window holding its
// tap's frame (the argument above, for each tap). A longer lookahead replays
// frames the old hold has forgotten: the hold takes them from the line
// (their need computed again from the stored input, Drive, Ceiling and Mode,
// one divide per loud frame, once). When the crossfade ends the new set is
// the only one, and a shorter hold just forgets sooner, which its boxes
// smooth. Lookahead 0 has its own envelope (below), run only while a tap
// with no delay is heard: a fade to 0 starts it from the lookahead
// envelope's reduction, and a fade from 0 restarts the hold from the line,
// so either way the path faded in has been running since the fade began. A
// change asked for during a crossfade waits for its end.
//
// The soft clip from a knee K to the ceiling c is the rational curve
//   y = c - (c - K)^2 / (|v| - K + (c - K))   for |v| > K,
// with slope 1 at the knee, approaching c and never reaching it.
//
// Mix below 1 blends the delayed dry input back in (parallel limiting), which
// gives up the ceiling by design. The host's bus limiter (fm1_mix_limiter.h)
// stays after every effect chain; with Ceiling at or under -0.18 dB (0.98)
// and nothing louder after this effect, it has nothing to do.
//
// Memory: the line holds Drive, Ceiling and Mode (SOFT CLIP's and ROUND's
// shares) with each frame, so a turned knob takes effect at the same moment
// for the detector and for the delayed audio: the ceiling holds while
// Ceiling glides. Instance memory grows with the host rate (5 ms of frames,
// at most 510): 11,952 bytes at 44,118 Hz, 29,008 at the cap (102 kHz and
// above); the instance holds no pointers, so a 32-bit build's is the same.
// Above 102 kHz the longest lookahead is 510 frames, shorter than 5 ms.
//
// Contracts (fm1_engine.h): no heap, every byte set in create, NaN-safe
// parameters (fm1_param_clamp) and input (NaN reads as 0, beyond +/-16 is
// clamped, as mi_fx.cc), finite output, silence in gives exact silence out.
// Continuous parameters glide (5 ms one-pole) sample by sample, so any block
// size gives the same output; values set before the first render apply at
// once. A Lookahead change crossfades from the old delay to the new over
// 5 ms; Mode glides its output stage over 5 ms (both above). Determinism: no
// libm. 2^x and the one-pole coefficients are polynomials written here, and
// no multiply-add is fused (below), so the browser's build computes what the
// native one does.

#include "fm1_engine.h"

#include <stdint.h>
#include <string.h>

// No fused multiply-adds in this file: the browser's WebAssembly cannot fuse,
// so a native build that did would round differently (Apple clang on arm64
// fuses by default). GCC ignores the pragma: build for a GCC target with FMA
// with -ffp-contract=off (the x86 builds here have none to use).
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

namespace fm1 {
namespace limit {

enum { P_CEILING, P_DRIVE, P_RELEASE, P_LOOKAHEAD, P_MODE, P_LINK, P_MIX, P_COUNT };

const char *const kModeNames[] = { "Brickwall", "Soft Clip", "Round" };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter can be locked and modulated: the floats glide,
// Lookahead crossfades its delay with a gain path per tap, and Mode (rounded
// when modulated) glides its stage frame by frame; none of them steps.
// Ceiling and Drive are in dB (FM1_UNIT_DB, API v3). Release moves on the
// LOG law (fm1_engine.h); Lookahead, whose range starts at 0, stays linear.
const fm1_param_t kParams[P_COUNT] = {
  { "Ceiling",   FM1_PARAM_FLOAT, -24, 0,    -1.0f,  NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Ceil" },
  { "Drive",     FM1_PARAM_FLOAT, -12, 24,   0.0f,   NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_DB, "Drive" },
  { "Release",   FM1_PARAM_FLOAT, 1,   1000, 100.0f, NULL, 0, 3, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Rel" },
  { "Lookahead", FM1_PARAM_FLOAT, 0,   5,    2.0f,   NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Look" },
  { "Mode",      FM1_PARAM_ENUM,  0,   2,    0.0f,   kModeNames, 1, 5, FM1_PARAM_MOD, FM1_UNIT_NONE, "Mode" },
  { "Link",      FM1_PARAM_FLOAT, 0,   1,    1.0f,   NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Link" },
  { "Mix",       FM1_PARAM_FLOAT, 0,   1,    1.0f,   NULL, 1, 7, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
};

const float kMinRate = 8000.0f;
const float kMaxRate = 384000.0f;
const float kMaxLookaheadS = 0.005f;      // the knob's top
const uint32_t kMaxLookaheadFrames = 510; // the memory cap
const float kGlideS = 0.005f;             // parameter glide time constant
const float kFadeS = 0.005f;              // Lookahead crossfade length
const float kZeroAttackS = 0.001f;        // the attack at Lookahead 0
const float kSafetyKnee = 0.891250938f;   // -1 dB: Lookahead 0's soft clip
const float kSoftKnee = 0.5f;             // -6.02 dB: Mode SOFT CLIP's knee
const float kSoftHeadroom = 4.0f;         // +12.04 dB into SOFT CLIP's curve
const float kRoundHeadroom = 1.41253754f; // +3 dB of overs for ROUND to round
const float kRoundHard = 0.7390851332f;   // ClipOnly2's hardness: x = cos(x)
const float kRoundSoft = 0.2609148668f;   // its softness, 1 - hardness
const float kRoundClamp = 4.0f;           // ClipOnly2 clamps its input at +/-4
const float kInputLimit = 16.0f;          // the input guard, as mi_fx.cc
const float kReductionFloor = 2.38418579e-7f;   // 2^-22: under the gain path's step
const uint32_t kUnityQ = 1u << 22;        // gain 1 in the integer gain path
const float kUnityQf = 4194304.0f;
const float kLog2Of10Over20 = 0.166096404744368f;   // dB to log2 of gain

// --------------------------------------------------------------------------
// Arithmetic without libm

inline float Abs(float x) { return x < 0.0f ? -x : x; }

// 2^x: x = i + f with f in [0, 1); 2^f by its Taylor series to degree 8
// (truncation under 1.1e-7, relative), 2^i by building the float's exponent.
// Exactly 1 at x = 0. x is clamped to [-126, 127]; NaN reads as -126.
inline float Exp2(float x) {
  if (!(x > -126.0f)) x = -126.0f;
  if (x > 127.0f) x = 127.0f;
  int32_t i = static_cast<int32_t>(x);
  if (static_cast<float>(i) > x) --i;            // floor, for negative x
  const float f = x - static_cast<float>(i);
  const float p = 1.0f + f * (6.93147181e-01f + f * (2.40226507e-01f + f * (5.55041087e-02f +
                  f * (9.61812911e-03f + f * (1.33335581e-03f + f * (1.54035304e-04f +
                  f * (1.52527338e-05f + f * 1.32154868e-06f)))))));
  const uint32_t bits = static_cast<uint32_t>(i + 127) << 23;
  float scale;
  memcpy(&scale, &bits, sizeof scale);
  return p * scale;
}

inline float DbToGain(float db) { return Exp2(db * kLog2Of10Over20); }

// The coefficient of a one-pole with a time constant of n samples,
// 1 - e^(-1/n), for n >= 8: -expm1(-1/n) by its Taylor series to degree 6
// (truncation under 1e-10 at n = 8), with no cancellation for long times.
inline float OnePole(float n) {
  if (!(n >= 8.0f)) n = 8.0f;
  const float y = -1.0f / n;
  return -(y * (1.0f + y * (0.5f + y * (1.66666667e-01f + y * (4.16666667e-02f +
           y * (8.33333333e-03f + y * 1.38888889e-03f))))));
}

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;   // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                         // NaN
}

inline float Clamp(float v, float c) { return v > c ? c : (v < -c ? -c : v); }

// The soft clip: v unchanged up to the knee k * c, then the rational curve
// towards c.
inline float Knee(float v, float c, float k) {
  const float a = Abs(v);
  const float kc = k * c;
  if (a <= kc) return v;
  const float w = c - kc;
  const float y = c - w * w / (a - kc + w);
  return v < 0.0f ? -y : y;
}

// --------------------------------------------------------------------------
// The instance

struct Glide {
  float value, target;
  void Step(float k) {
    const float e = target - value;
    if (e == 0.0f) return;
    if (Abs(e) <= 1e-4f * (1.0f + Abs(target))) value = target;   // land exactly
    else value += k * e;
  }
};

// One channel's pair of box filters in one set.
struct Box {
  uint32_t sum1, pos1;       // box 1: the sum of its values, the next slot
  uint32_t sum2, pos2;       // box 2
};

// ROUND's stage for one tap and channel (ClipOnly2's state): the value
// pending for the frame the stage gives out next, whether that frame was
// over (above +c or below -c), and whether the state has been fed since
// ROUND last left the tap (0: start it from the frame at hand).
struct RoundState {
  float last;
  uint8_t pos, neg, warm, pad;
};

struct Channel {
  float red;                 // the envelope's gain reduction, 1 - gain
  float red0;                // Lookahead 0's envelope (1 ms attack, -1 dB)
  uint32_t dq_head, dq_count;  // the hold's deque: a ring of dq_cap entries
  Box box[2];                // two sets: the new tap's and, while they fade, the old's
};

// The geometry of one set of boxes.
struct BoxSet {
  uint32_t d, b1, b1_shift, b2;   // (b1 - 1) + (b2 - 1) = d
  uint32_t full2;                 // box 2's sum at unity gain
  float inv2;                     // 1 / full2
};

// The arrays after the struct, by byte offset (no pointers, so the instance
// is the same on 32- and 64-bit builds):
//   x    float[2n]       the guarded input, left and right, per frame
//   ctl  float[4n]       Drive and Ceiling (linear), and Mode as SOFT CLIP's
//                        and ROUND's shares (0..1 each), per frame
//   dqv  uint32[2][cap]  the hold's deque values (cap = n + 1)
//   b1   uint32[2 sets][2][b1cap], b2 uint32[2 sets][2][b2cap]   the box filters
//   dqt  uint16[2][cap]  the deque entries' frame stamps
struct Instance {
  float rate;
  uint32_t dmax;             // longest lookahead in frames
  uint32_t n;                // line length, dmax + 1 frames
  uint32_t dq_cap, b1cap, b2cap;
  uint32_t off_x, off_ctl, off_dqv, off_b1, off_b2, off_dqt;
  uint32_t bytes;

  float param[P_COUNT];
  float k_glide, k_attack0, k_release, fade_step;
  uint32_t fade_len;
  Glide drive, ceiling, link, mix, soft, round;

  uint32_t d, d_target, d_old;   // lookahead in frames: in use, asked for, fading out
  uint32_t fade_pos;             // 0, or frames into the crossfade from d_old
  uint32_t h;                    // the hold's window, frames
  uint32_t cur;                  // the set of boxes for d; the other is d_old's while fading
  BoxSet set[2];
  uint32_t write;                // the line slot of the current frame
  uint32_t now;                  // frame counter
  int primed;                    // 0 until the first render
  Channel ch[2];
  RoundState rnd[2][2];          // ROUND's stage, per set of boxes (tap) and channel
};

inline uint32_t Round16(uint32_t b) { return (b + 15u) & ~15u; }

struct Layout {
  uint32_t dmax, n, dq_cap, b1cap, b2cap;
  uint32_t off_x, off_ctl, off_dqv, off_b1, off_b2, off_dqt, bytes;
};

// Sizes for a host rate; a rate the effect refuses gets the smallest layout.
Layout MakeLayout(float rate) {
  if (!(rate >= kMinRate && rate <= kMaxRate)) rate = kMinRate;
  const float frames = rate * kMaxLookaheadS;
  uint32_t d = static_cast<uint32_t>(frames);
  if (static_cast<float>(d) < frames) ++d;
  if (d > kMaxLookaheadFrames) d = kMaxLookaheadFrames;
  Layout l;
  l.dmax = d;
  l.n = d + 1;
  l.dq_cap = d + 2;          // the window's d + 1 entries and a refill's one
  l.b1cap = 1;               // the longest boxes any lookahead up to d uses
  l.b2cap = 1;
  for (uint32_t k = 0; k <= d; ++k) {
    uint32_t b1 = 1;
    while (2u * b1 <= k / 2u + 1u) b1 *= 2u;
    if (b1 > l.b1cap) l.b1cap = b1;
    if (k + 2u - b1 > l.b2cap) l.b2cap = k + 2u - b1;
  }
  uint32_t off = Round16(static_cast<uint32_t>(sizeof(Instance)));
  l.off_x = off;   off += 8u * l.n;
  l.off_ctl = off; off += 16u * l.n;
  l.off_dqv = off; off += 8u * l.dq_cap;
  l.off_b1 = off;  off += 16u * l.b1cap;
  l.off_b2 = off;  off += 16u * l.b2cap;
  l.off_dqt = off; off += 4u * l.dq_cap;
  l.bytes = Round16(off);
  return l;
}

struct Arrays {
  float *x, *ctl;
  uint32_t *dqv, *b1, *b2;
  uint16_t *dqt;
};

Arrays ArraysOf(Instance *s) {
  unsigned char *base = reinterpret_cast<unsigned char *>(s);
  Arrays a;
  a.x = reinterpret_cast<float *>(base + s->off_x);
  a.ctl = reinterpret_cast<float *>(base + s->off_ctl);
  a.dqv = reinterpret_cast<uint32_t *>(base + s->off_dqv);
  a.b1 = reinterpret_cast<uint32_t *>(base + s->off_b1);
  a.b2 = reinterpret_cast<uint32_t *>(base + s->off_b2);
  a.dqt = reinterpret_cast<uint16_t *>(base + s->off_dqt);
  return a;
}

// The boxes for D frames: box 1 the largest power of two not above D / 2 + 1,
// box 2 the rest, so that (b1 - 1) + (b2 - 1) = D. With a lookahead of d
// they span d and the hold d + 1 frames.
void SetBoxes(Instance *s, uint32_t set, uint32_t d) {
  BoxSet &g = s->set[set];
  g.d = d;
  uint32_t b1 = 1, shift = 0;
  while (2u * b1 <= d / 2u + 1u) { b1 *= 2u; ++shift; }
  g.b1 = b1;
  g.b1_shift = shift;
  g.b2 = d + 2u - b1;
  g.full2 = g.b2 << 22;
  g.inv2 = 1.0f / static_cast<float>(g.full2);
}

inline uint32_t Held(const Instance *s, const Arrays &a, uint32_t c) {
  const Channel &k = s->ch[c];
  return k.dq_count ? a.dqv[c * s->dq_cap + k.dq_head] : kUnityQ;
}

inline uint32_t *Ring1(const Instance *s, const Arrays &a, uint32_t set, uint32_t c) {
  return a.b1 + (2u * set + c) * s->b1cap;
}

inline uint32_t *Ring2(const Instance *s, const Arrays &a, uint32_t set, uint32_t c) {
  return a.b2 + (2u * set + c) * s->b2cap;
}

// Restart a set of boxes at each channel's held gain (the lowest in the
// hold's window), so they start from a gain no higher than any frame in it
// needs.
void FillBoxes(Instance *s, const Arrays &a, uint32_t set) {
  const BoxSet &g = s->set[set];
  for (uint32_t c = 0; c < 2; ++c) {
    Box &k = s->ch[c].box[set];
    const uint32_t held = Held(s, a, c);
    uint32_t *r1 = Ring1(s, a, set, c);
    uint32_t *r2 = Ring2(s, a, set, c);
    for (uint32_t i = 0; i < g.b1; ++i) r1[i] = held;
    for (uint32_t i = 0; i < g.b2; ++i) r2[i] = held;
    k.sum1 = g.b1 * held;
    k.sum2 = g.b2 * held;
    k.pos1 = k.pos2 = 0;
  }
}

// The lookahead d in force at once, with no crossfade (create, and settings
// made before the first render): the hold as one entry and the boxes at each
// channel's held gain; with no history (create) that is unity.
void SetLookahead(Instance *s, const Arrays &a, uint32_t d) {
  s->d = d;
  s->h = d + 1;
  s->cur = 0;
  for (uint32_t c = 0; c < 2; ++c) {
    Channel &k = s->ch[c];
    const uint32_t held = Held(s, a, c);
    a.dqv[c * s->dq_cap] = held;
    a.dqt[c * s->dq_cap] = static_cast<uint16_t>(s->now);
    k.dq_head = 0;
    k.dq_count = 1;
  }
  SetBoxes(s, 0, d);
  FillBoxes(s, a, 0);
}

void Apply(Instance *s, int index) {
  const float v = s->param[index];
  switch (index) {
    case P_CEILING: s->ceiling.target = DbToGain(v); break;
    case P_DRIVE: s->drive.target = DbToGain(v); break;
    case P_RELEASE: s->k_release = OnePole(v * 0.001f * s->rate); break;
    case P_LOOKAHEAD: {
      uint32_t d = static_cast<uint32_t>(v * 0.001f * s->rate + 0.5f);
      if (d > s->dmax) d = s->dmax;
      s->d_target = d;
      break;
    }
    case P_MODE: {
      const int mode = static_cast<int>(v + 0.5f);   // v is clamped to 0..2
      s->soft.target = mode == 1 ? 1.0f : 0.0f;
      s->round.target = mode == 2 ? 1.0f : 0.0f;
      break;
    }
    case P_LINK: s->link.target = v; break;
    case P_MIX: s->mix.target = v; break;
    default: break;
  }
}

// One step of an envelope's reduction (1 - gain) towards need: an attack
// (instant, or one-pole with k_attack) and the one-pole release.
inline float Envelope(const Instance *s, float red, float need, int instant) {
  if (need > red) {
    red = instant ? need : red + s->k_attack0 * (need - red);   // attack
  } else if (need < red) {
    const float next = red + s->k_release * (need - red);       // release
    red = next == red ? need : next;   // the step fell under float resolution
    if (red < kReductionFloor) red = 0.0f;
  }
  return red;
}

// Lookahead 0's path for one channel: its envelope, aiming at what this
// frame needs (g0, the ceiling 1 dB down), attacks over 1 ms; its gain,
// quantised as the boxes' is, goes straight to the stage.
inline float ZeroGain(Instance *s, uint32_t c, float g0) {
  Channel &k = s->ch[c];
  k.red0 = Envelope(s, k.red0, 1.0f - g0, 0);
  const uint32_t q = static_cast<uint32_t>((1.0f - k.red0) * kUnityQf);   // rounds down
  return q == kUnityQ ? 1.0f : static_cast<float>(q) * (1.0f / kUnityQf);
}

// One frame of one channel's lookahead envelope and hold: the gain this frame
// needs in, the hold's minimum out.
inline uint32_t HoldStep(Instance *s, const Arrays &a, uint32_t c, float g) {
  Channel &k = s->ch[c];
  k.red = Envelope(s, k.red, 1.0f - g, 1);
  // 1 - red can sit an ulp of 1 above g, which is much of g when g is small:
  // the gain never exceeds what this frame needs.
  float gain = 1.0f - k.red;
  if (gain > g) gain = g;
  const uint32_t q = static_cast<uint32_t>(gain * kUnityQf);   // rounds down

  // The hold: a deque of increasing values, oldest first; its front is the
  // window's minimum. Expiring before pushing keeps it within h + 1 entries
  // (h frames and a refill's one), which dq_cap holds.
  const uint32_t cap = s->dq_cap;
  uint32_t *dqv = a.dqv + c * cap;
  uint16_t *dqt = a.dqt + c * cap;
  const uint16_t stamp = static_cast<uint16_t>(s->now);
  while (k.dq_count && static_cast<uint16_t>(stamp - dqt[k.dq_head]) >= s->h) {
    if (++k.dq_head == cap) k.dq_head = 0;
    --k.dq_count;
  }
  while (k.dq_count) {
    uint32_t back = k.dq_head + k.dq_count - 1u;
    if (back >= cap) back -= cap;
    if (dqv[back] < q) break;
    --k.dq_count;
  }
  uint32_t slot = k.dq_head + k.dq_count;
  if (slot >= cap) slot -= cap;
  dqv[slot] = q;
  dqt[slot] = stamp;
  ++k.dq_count;
  return dqv[k.dq_head];
}

// One frame of one channel's boxes in one set: the hold's minimum in, the
// gain for the frame leaving that set's tap out. Exact integer sums; box 1's
// mean is a shift.
inline float BoxStep(Instance *s, const Arrays &a, uint32_t set, uint32_t c, uint32_t held) {
  const BoxSet &g = s->set[set];
  Box &k = s->ch[c].box[set];
  uint32_t *r1 = Ring1(s, a, set, c);
  k.sum1 += held - r1[k.pos1];
  r1[k.pos1] = held;
  k.pos1 = (k.pos1 + 1u) & (g.b1 - 1u);
  const uint32_t mean1 = k.sum1 >> g.b1_shift;
  uint32_t *r2 = Ring2(s, a, set, c);
  k.sum2 += mean1 - r2[k.pos2];
  r2[k.pos2] = mean1;
  if (++k.pos2 == g.b2) k.pos2 = 0;
  if (k.sum2 == g.full2) return 1.0f;
  const float out = static_cast<float>(k.sum2) * g.inv2;
  return out > 1.0f ? 1.0f : out;
}

// The envelope's aim: the ceiling, Lookahead 0's 1 dB under it, four times
// it once Mode has reached SOFT CLIP, or 3 dB over it once Mode has reached
// ROUND (above).
inline float Aim(float c, float soft, float round, int zero) {
  if (soft == 1.0f) return kSoftHeadroom * c;
  if (round == 1.0f) return kRoundHeadroom * c;
  return zero ? kSafetyKnee * c : c;
}

// The lowest gain any of the line's last `span` frames (now - span .. now - 1)
// needs, per channel, quantised as HoldStep quantises it: recomputed from the
// stored input, Drive, Ceiling and Mode, with the current Link.
void LineNeeds(const Instance *s, const Arrays &a, uint32_t span, uint32_t q[2]) {
  const float link = s->link.value;
  float best[2] = { 1.0f, 1.0f };
  uint32_t slot = s->write;
  for (uint32_t j = 0; j < span; ++j) {
    slot = slot == 0 ? s->n - 1u : slot - 1u;
    const float dd = a.ctl[4 * slot];
    const float e = Aim(a.ctl[4 * slot + 1], a.ctl[4 * slot + 2], a.ctl[4 * slot + 3], 0);
    const float al = Abs(dd * a.x[2 * slot]), ar = Abs(dd * a.x[2 * slot + 1]);
    const float ll = link * ar, lrr = link * al;
    const float p[2] = { al > ll ? al : ll, ar > lrr ? ar : lrr };
    for (uint32_t c = 0; c < 2; ++c) {
      if (p[c] > e) {
        const float g = e / p[c];
        if (g < best[c]) best[c] = g;
      }
    }
  }
  q[0] = static_cast<uint32_t>(best[0] * kUnityQf);
  q[1] = static_cast<uint32_t>(best[1] * kUnityQf);
}

// Add a gain to the hold as if the last frame (now - 1) had needed it.
void PushHold(Instance *s, const Arrays &a, uint32_t c, uint32_t q) {
  Channel &k = s->ch[c];
  const uint32_t cap = s->dq_cap;
  uint32_t *dqv = a.dqv + c * cap;
  uint16_t *dqt = a.dqt + c * cap;
  while (k.dq_count) {
    uint32_t back = k.dq_head + k.dq_count - 1u;
    if (back >= cap) back -= cap;
    if (dqv[back] < q) break;
    --k.dq_count;
  }
  uint32_t slot = k.dq_head + k.dq_count;
  if (slot >= cap) slot -= cap;
  dqv[slot] = q;
  dqt[slot] = static_cast<uint16_t>(s->now - 1u);
  ++k.dq_count;
}

// A Lookahead change starts: the read crossfades from d_old to d. The old
// tap keeps its boxes; the new one gets the other set, d long, started at the
// held gain after the hold has grown to suit both taps (above).
void StartChange(Instance *s, const Arrays &a) {
  const uint32_t d_old = s->d, d = s->d_target;
  s->d_old = d_old;
  s->d = d;
  s->fade_pos = 1;
  for (uint32_t c = 0; c < 2; ++c) {
    Channel &k = s->ch[c];
    if (d == 0) k.red0 = k.red;          // Lookahead 0's envelope starts here
    if (d_old == 0) {                    // the hold and its envelope were idle
      k.dq_count = 0;
      k.red = k.red0;
    }
  }
  if (d > d_old) {
    s->h = d + 1;                       // the hold spans both taps' frames
    uint32_t q[2];
    LineNeeds(s, a, d, q);
    PushHold(s, a, 0, q[0]);
    PushHold(s, a, 1, q[1]);
  }
  s->cur ^= 1u;
  SetBoxes(s, s->cur, d);
  FillBoxes(s, a, s->cur);
  s->rnd[s->cur][0].warm = s->rnd[s->cur][1].warm = 0;   // ROUND's stage starts afresh
}

// The crossfade is over: the old tap's boxes are free, and the hold shrinks
// to d + 1 (it forgets sooner; the boxes smooth what it lets go of).
void EndChange(Instance *s) { s->h = s->d + 1; }

#ifdef FM1_LIMIT_PROBE
// Test builds only (fm1-limit-test, engines/mk/limit.mk): the largest |v| / c
// the final clamp has met in BRICKWALL with a lookahead, and the largest
// |stage output| / c in either Mode (and while Mode glides) with a lookahead,
// where only rounding should reach either.
extern "C" float fm1_limit_probe_worst;
float fm1_limit_probe_worst = 0.0f;
extern "C" float fm1_limit_probe_stage;
float fm1_limit_probe_stage = 0.0f;
#endif

// ROUND's stage, ClipOnly2's step at the ceiling c: q is the value of the
// frame after the one it gives out. The frame q follows is put right if it
// was over: towards q when q is under it, else further towards the ceiling;
// q, if over, is replaced by c hardness + (the frame before) softness. So an
// over never passes c, and a frame under +/-c that does not follow an over
// passes as it came.
inline float RoundStep(RoundState &st, float q, float c) {
  const float ch = c * kRoundHard, cs = c * kRoundSoft, lim = kRoundClamp * c;
  if (q > lim) q = lim;
  if (q < -lim) q = -lim;
  if (st.pos) st.last = q < st.last ? ch + q * kRoundSoft : cs + st.last * kRoundHard;
  st.pos = 0;
  if (q > c) {
    st.pos = 1;
    q = ch + st.last * kRoundSoft;
  }
  if (st.neg) st.last = q > st.last ? -ch + q * kRoundSoft : -cs + st.last * kRoundHard;
  st.neg = 0;
  if (q < -c) {
    st.neg = 1;
    q = -ch + st.last * kRoundSoft;
  }
  const float out = st.last;
  st.last = q;
  return out;
}

// ROUND for one tap and channel: v is the frame given out now; with a
// lookahead, peek is the next frame (its input times this frame's gain) and
// the step runs one frame ahead, so ROUND adds no delay; at Lookahead 0
// there is no next frame, and v itself is the step's input and its result
// the output: overs are still rounded on the way in, not on the way out.
inline float RoundOut(RoundState &st, float v, float peek, int has_peek, float c) {
  if (!st.warm) {
    st.last = Clamp(v, c);
    st.pos = st.neg = 0;
    st.warm = 1;
  }
  if (has_peek) return RoundStep(st, peek, c);
  RoundStep(st, v, c);
  return st.last;
}

// The output stage: BRICKWALL clamps (with Lookahead 0, soft-clips from
// -1 dB), SOFT CLIP soft-clips from -6 dB, ROUND rounds the overs off
// (ClipOnly2); a blend of them while Mode glides. With ROUND out of it the
// arithmetic is the stage's from before ROUND, bit for bit.
inline float Stage(RoundState &st, float v, float peek, int has_peek, float c, float soft,
                   float round, int zero) {
  float y = zero ? Knee(v, c, kSafetyKnee) : v;
#ifdef FM1_LIMIT_PROBE
  if (!zero && soft == 0.0f && round == 0.0f && Abs(v) / c > fm1_limit_probe_worst) {
    fm1_limit_probe_worst = Abs(v) / c;
  }
#endif
  if (round == 0.0f) {
    st.warm = 0;
    if (soft != 0.0f) {
      const float ys = Knee(v, c, kSoftKnee);
      y = soft == 1.0f ? ys : (1.0f - soft) * y + soft * ys;
    }
  } else {
    const float yr = RoundOut(st, v, peek, has_peek, c);
    if (round == 1.0f) {
      y = yr;
    } else {
      float wb = 1.0f - soft - round;
      if (wb < 0.0f) wb = 0.0f;
      y = wb * y + round * yr;
      if (soft != 0.0f) y = y + soft * Knee(v, c, kSoftKnee);
    }
  }
#ifdef FM1_LIMIT_PROBE
  if (!zero && Abs(y) / c > fm1_limit_probe_stage) fm1_limit_probe_stage = Abs(y) / c;
#endif
  return Clamp(y, c);
}

// One tap's path to the output: the driven frame from slot r times its gain,
// through the stage for its Mode and Ceiling (zero: Lookahead 0's); ROUND's
// state is the tap's set's, and its next frame is slot r + 1 (with a
// lookahead).
inline float TapOut(Instance *s, const Arrays &a, uint32_t set, uint32_t r, uint32_t c,
                    float gain, int zero) {
  const float *k = a.ctl + 4 * r;
  float peek = 0.0f;
  if (!zero && k[3] != 0.0f) {
    const uint32_t r1 = r + 1u == s->n ? 0u : r + 1u;
    peek = a.ctl[4 * r1] * a.x[2 * r1 + c] * gain;
  }
  return Stage(s->rnd[set][c], k[0] * a.x[2 * r + c] * gain, peek, !zero, k[1], k[2], k[3], zero);
}

void Render(Instance *s, float *lr, uint32_t frames) {
  const Arrays a = ArraysOf(s);
  if (!s->primed) {
    // Settings made before the first block apply from its first sample.
    s->drive.value = s->drive.target;
    s->ceiling.value = s->ceiling.target;
    s->link.value = s->link.target;
    s->mix.value = s->mix.target;
    s->soft.value = s->soft.target;
    s->round.value = s->round.target;
    if (s->d_target != s->d) SetLookahead(s, a, s->d_target);
    s->primed = 1;
  }
  const uint32_t n = s->n;
  for (uint32_t f = 0; f < frames; ++f) {
    if (s->fade_pos == 0 && s->d_target != s->d) StartChange(s, a);
    const float kg = s->k_glide;
    s->drive.Step(kg);
    s->ceiling.Step(kg);
    s->link.Step(kg);
    s->mix.Step(kg);
    s->soft.Step(kg);
    s->round.Step(kg);
    const float drive = s->drive.value, c = s->ceiling.value;
    const float link = s->link.value, mix = s->mix.value, soft = s->soft.value;
    const float round = s->round.value;

    // Into the line.
    const float xl = Guard(lr[2 * f]), xr = Guard(lr[2 * f + 1]);
    const uint32_t w = s->write;
    a.x[2 * w] = xl;
    a.x[2 * w + 1] = xr;
    a.ctl[4 * w] = drive;
    a.ctl[4 * w + 1] = c;
    a.ctl[4 * w + 2] = soft;
    a.ctl[4 * w + 3] = round;

    // The detector, and the envelopes: the lookahead one into the hold, and
    // Lookahead 0's, each only while a tap that needs it is heard.
    const float al = Abs(drive * xl), ar = Abs(drive * xr);
    const float ll = link * ar, lrr = link * al;
    const float pl = al > ll ? al : ll, pr = ar > lrr ? ar : lrr;
    const int zero = s->d == 0, zero_old = s->fade_pos != 0 && s->d_old == 0;
    uint32_t hl = kUnityQ, hr = kUnityQ;
    float zl = 1.0f, zr = 1.0f;
    if (!zero || (s->fade_pos != 0 && !zero_old)) {
      const float e = Aim(c, soft, round, 0);
      hl = HoldStep(s, a, 0, pl > e ? e / pl : 1.0f);
      hr = HoldStep(s, a, 1, pr > e ? e / pr : 1.0f);
    }
    if (zero || zero_old) {
      const float e0 = Aim(c, soft, round, 1);
      zl = ZeroGain(s, 0, pl > e0 ? e0 / pl : 1.0f);
      zr = ZeroGain(s, 1, pr > e0 ? e0 / pr : 1.0f);
    }

    // Out of the line, d frames later: the new tap, and while they fade the
    // old one, each with its own gain and stage.
    const uint32_t cur = s->cur;
    const float gl = zero ? zl : BoxStep(s, a, cur, 0, hl);
    const float gr = zero ? zr : BoxStep(s, a, cur, 1, hr);
    uint32_t r = w >= s->d ? w - s->d : w + n - s->d;
    float dl = a.x[2 * r], dr = a.x[2 * r + 1];
    float yl = TapOut(s, a, cur, r, 0, gl, zero), yr = TapOut(s, a, cur, r, 1, gr, zero);
    int ended = 0;
    if (s->fade_pos) {
      const float ol = zero_old ? zl : BoxStep(s, a, cur ^ 1u, 0, hl);
      const float orr = zero_old ? zr : BoxStep(s, a, cur ^ 1u, 1, hr);
      const uint32_t ro = w >= s->d_old ? w - s->d_old : w + n - s->d_old;
      const float t = static_cast<float>(s->fade_pos) * s->fade_step, u = 1.0f - t;
      yl = u * TapOut(s, a, cur ^ 1u, ro, 0, ol, zero_old) + t * yl;
      yr = u * TapOut(s, a, cur ^ 1u, ro, 1, orr, zero_old) + t * yr;
      dl = u * a.x[2 * ro] + t * dl;
      dr = u * a.x[2 * ro + 1] + t * dr;
      if (++s->fade_pos >= s->fade_len) {
        s->fade_pos = 0;
        ended = 1;
      }
    }
    lr[2 * f] = (1.0f - mix) * dl + mix * yl;
    lr[2 * f + 1] = (1.0f - mix) * dr + mix * yr;

    s->write = w + 1u == n ? 0u : w + 1u;
    ++s->now;
    if (ended) EndChange(s);
  }
}

// --------------------------------------------------------------------------
// The engine API

size_t InstanceSize(const fm1_host_t *host) { return MakeLayout(host->sample_rate).bytes; }

void *Create(void *mem, const fm1_host_t *host) {
  const float rate = host->sample_rate;
  if (!(rate >= kMinRate && rate <= kMaxRate)) return NULL;   // NaN fails too
  const Layout l = MakeLayout(rate);
  memset(mem, 0, l.bytes);
  Instance *s = static_cast<Instance *>(mem);
  s->rate = rate;
  s->dmax = l.dmax;
  s->n = l.n;
  s->dq_cap = l.dq_cap;
  s->b1cap = l.b1cap;
  s->b2cap = l.b2cap;
  s->off_x = l.off_x;
  s->off_ctl = l.off_ctl;
  s->off_dqv = l.off_dqv;
  s->off_b1 = l.off_b1;
  s->off_b2 = l.off_b2;
  s->off_dqt = l.off_dqt;
  s->bytes = l.bytes;
  s->k_glide = OnePole(kGlideS * rate);
  s->k_attack0 = OnePole(kZeroAttackS * rate);
  uint32_t fade = static_cast<uint32_t>(kFadeS * rate + 0.5f);
  if (fade < 2) fade = 2;
  s->fade_len = fade;
  s->fade_step = 1.0f / static_cast<float>(fade);
  for (int i = 0; i < P_COUNT; ++i) {
    s->param[i] = kParams[i].def;
    Apply(s, i);
  }
  s->drive.value = s->drive.target;
  s->ceiling.value = s->ceiling.target;
  s->link.value = s->link.target;
  s->mix.value = s->mix.target;
  s->soft.value = s->soft.target;
  s->round.value = s->round.target;
  SetLookahead(s, ArraysOf(s), s->d_target);
  return s;
}

void Destroy(void *) {}

void Set(void *p, uint16_t index, float v) {
  Instance *s = static_cast<Instance *>(p);
  if (index >= P_COUNT) return;
  s->param[index] = fm1_param_clamp(&kParams[index], v);
  Apply(s, index);
}

void RenderEntry(void *p, float *lr, uint32_t frames) {
  Render(static_cast<Instance *>(p), lr, frames);
}

}  // namespace limit
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_limit = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "limit", "Limiter",
  "This repository (MIT): a look-ahead limiter after Geraint Luff's "
  "\"Designing a straightforward limiter\" (Signalsmith Audio, 2022), no code taken; "
  "Mode Round ports Airwindows ClipOnly2 (Chris Johnson, MIT)",
  fm1::limit::kParams, fm1::limit::P_COUNT, 0,
  fm1::limit::InstanceSize, fm1::limit::Create, fm1::limit::Destroy,
  NULL, NULL, NULL,
  fm1::limit::Set, fm1::limit::RenderEntry,
  NULL,                     // no notes, so no per-note offsets
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

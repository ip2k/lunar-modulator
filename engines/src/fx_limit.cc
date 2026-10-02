// fx_limit.cc -- "Limiter": a look-ahead brickwall limiter (FM1_KIND_AUDIO_FX),
// written for this repository, MIT licence. Notes in engines/README.md
// ("Limiter").
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
// off; the output stays under the ceiling (at most -0.56 dB under it).
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
// Memory: the line holds Drive and Ceiling with each frame, so a turned knob
// takes effect at the same moment for the detector and for the delayed
// audio: the ceiling holds while Ceiling glides. Instance memory grows with
// the host rate (5 ms of frames, at most 510): 8,272 bytes at 44,118 Hz,
// 19,696 at the cap (102 kHz and above); the instance holds no pointers, so
// a 32-bit build's is the same. Above 102 kHz the longest lookahead is 510
// frames, shorter than 5 ms.
//
// Contracts (fm1_engine.h): no heap, every byte set in create, NaN-safe
// parameters (fm1_param_clamp) and input (NaN reads as 0, beyond +/-16 is
// clamped, as mi_fx.cc), finite output, silence in gives exact silence out.
// Continuous parameters glide (5 ms one-pole) sample by sample, so any block
// size gives the same output; values set before the first render apply at
// once. A Lookahead change crossfades from the old delay to the new over
// 5 ms; Mode crossfades its output stage over 5 ms. Determinism: no libm.
// 2^x and the one-pole coefficients are polynomials written here, so the
// browser's build computes what the native one does.

#include "fm1_engine.h"

#include <stdint.h>
#include <string.h>

namespace fm1 {
namespace limit {

enum { P_CEILING, P_DRIVE, P_RELEASE, P_LOOKAHEAD, P_MODE, P_LINK, P_MIX, P_COUNT };

const char *const kModeNames[] = { "Brickwall", "Soft Clip" };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Lookahead changes the latency and Mode the gain computer, so
// neither is locked or modulated (NOLOCK); the rest are read every frame.
// Ceiling and Drive are in dB, which has no unit code yet.
const fm1_param_t kParams[P_COUNT] = {
  { "Ceiling",   FM1_PARAM_FLOAT, -24, 0,    -1.0f,  NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Ceil" },
  { "Drive",     FM1_PARAM_FLOAT, -12, 24,   0.0f,   NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Drive" },
  { "Release",   FM1_PARAM_FLOAT, 1,   1000, 100.0f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_MS, "Rel" },
  { "Lookahead", FM1_PARAM_FLOAT, 0,   5,    2.0f,   NULL, 0, 4, FM1_PARAM_NOLOCK, FM1_UNIT_MS, "Look" },
  { "Mode",      FM1_PARAM_ENUM,  0,   1,    0.0f,   kModeNames, 1, 5, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Mode" },
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

struct Channel {
  float red;                 // the envelope's gain reduction, 1 - gain
  uint32_t dq_head, dq_count;  // the hold's deque: a ring of dq_cap entries
  uint32_t sum1, pos1;       // box 1: the sum of its values, the next slot
  uint32_t sum2, pos2;       // box 2
};

// The arrays after the struct, by byte offset (no pointers, so the instance
// is the same on 32- and 64-bit builds):
//   x    float[2n]       the guarded input, left and right, per frame
//   ctl  float[2n]       Drive and Ceiling (linear) per frame
//   dqv  uint32[2][cap]  the hold's deque values (cap = n + 1)
//   b1   uint32[2][b1cap], b2 uint32[2][b2cap]   the box filters
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
  Glide drive, ceiling, link, mix, soft;

  uint32_t d, d_target, d_old;   // lookahead in frames: in use, asked for, fading out
  uint32_t fade_pos;             // 0, or frames into the crossfade from d_old
  uint32_t h, b1, b1_shift, b2;  // the hold's window and the boxes' lengths
  uint32_t full2;                // box 2's sum at unity gain
  float inv2;                    // 1 / full2
  uint32_t write;                // the line slot of the current frame
  uint32_t now;                  // frame counter
  int primed;                    // 0 until the first render
  Channel ch[2];
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
  l.off_ctl = off; off += 8u * l.n;
  l.off_dqv = off; off += 8u * l.dq_cap;
  l.off_b1 = off;  off += 8u * l.b1cap;
  l.off_b2 = off;  off += 8u * l.b2cap;
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

// The windows for a lookahead of d frames: the hold spans d + 1 frames, box 1
// the largest power of two not above d / 2 + 1, box 2 the rest, so that
// (b1 - 1) + (b2 - 1) = d.
void SetWindows(Instance *s, uint32_t d) {
  s->d = d;
  s->h = d + 1;
  uint32_t b1 = 1, shift = 0;
  while (2u * b1 <= d / 2u + 1u) { b1 *= 2u; ++shift; }
  s->b1 = b1;
  s->b1_shift = shift;
  s->b2 = d + 2u - b1;
  s->full2 = s->b2 << 22;
  s->inv2 = 1.0f / static_cast<float>(s->full2);
}

// Restart the hold and the boxes at each channel's current held gain (the
// lowest in the old window), so a new lookahead starts from a gain no higher
// than the one in use. With no history (create) that is unity.
void Refill(Instance *s, const Arrays &a) {
  for (uint32_t c = 0; c < 2; ++c) {
    Channel &k = s->ch[c];
    uint32_t *dqv = a.dqv + c * s->dq_cap;
    uint16_t *dqt = a.dqt + c * s->dq_cap;
    const uint32_t held = k.dq_count ? dqv[k.dq_head] : kUnityQ;
    dqv[0] = held;
    dqt[0] = static_cast<uint16_t>(s->now);
    k.dq_head = 0;
    k.dq_count = 1;
    uint32_t *r1 = a.b1 + c * s->b1cap;
    uint32_t *r2 = a.b2 + c * s->b2cap;
    for (uint32_t i = 0; i < s->b1; ++i) r1[i] = held;
    for (uint32_t i = 0; i < s->b2; ++i) r2[i] = held;
    k.sum1 = s->b1 * held;
    k.sum2 = s->b2 * held;
    k.pos1 = k.pos2 = 0;
  }
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
    case P_MODE: s->soft.target = v >= 0.5f ? 1.0f : 0.0f; break;
    case P_LINK: s->link.target = v; break;
    case P_MIX: s->mix.target = v; break;
    default: break;
  }
}

// One frame of one channel's gain path: the gain this frame needs in, the
// gain for the frame leaving the line out.
inline float GainStep(Instance *s, const Arrays &a, uint32_t c, float g, int zero) {
  Channel &k = s->ch[c];
  const float need = 1.0f - g;
  float red = k.red;
  if (need > red) {
    red = zero ? red + s->k_attack0 * (need - red) : need;   // attack
  } else if (need < red) {
    const float next = red + s->k_release * (need - red);   // release
    red = next == red ? need : next;   // the step fell under float resolution
    if (red < kReductionFloor) red = 0.0f;
  }
  k.red = red;
  // 1 - red can sit an ulp of 1 above g, which is much of g when g is small;
  // with a lookahead the gain never exceeds what this frame needs.
  float gain = 1.0f - red;
  if (!zero && gain > g) gain = g;
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
  const uint32_t held = dqv[k.dq_head];

  // The boxes, in exact integer sums; box 1's mean is a shift.
  uint32_t *r1 = a.b1 + c * s->b1cap;
  k.sum1 += held - r1[k.pos1];
  r1[k.pos1] = held;
  k.pos1 = (k.pos1 + 1u) & (s->b1 - 1u);
  const uint32_t mean1 = k.sum1 >> s->b1_shift;
  uint32_t *r2 = a.b2 + c * s->b2cap;
  k.sum2 += mean1 - r2[k.pos2];
  r2[k.pos2] = mean1;
  if (++k.pos2 == s->b2) k.pos2 = 0;
  if (k.sum2 == s->full2) return 1.0f;
  const float out = static_cast<float>(k.sum2) * s->inv2;
  return out > 1.0f ? 1.0f : out;
}

#ifdef FM1_LIMIT_PROBE
// Test builds only (fm1-limit-test, engines/mk/limit.mk): the largest |v| / c
// the final clamp has met in BRICKWALL with a lookahead, where only rounding
// should reach it.
extern "C" float fm1_limit_probe_worst;
float fm1_limit_probe_worst = 0.0f;
#endif

// The output stage: BRICKWALL clamps (with Lookahead 0, soft-clips from
// -1 dB), SOFT CLIP soft-clips from -6 dB; between the two while Mode glides.
inline float Stage(float v, float c, float soft, int zero) {
  float y = zero ? Knee(v, c, kSafetyKnee) : v;
#ifdef FM1_LIMIT_PROBE
  if (!zero && soft == 0.0f && Abs(v) / c > fm1_limit_probe_worst) fm1_limit_probe_worst = Abs(v) / c;
#endif
  if (soft != 0.0f) {
    const float ys = Knee(v, c, kSoftKnee);
    y = soft == 1.0f ? ys : (1.0f - soft) * y + soft * ys;
  }
  return Clamp(y, c);
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
    if (s->d_target != s->d) {
      SetWindows(s, s->d_target);
      Refill(s, a);
    }
    s->primed = 1;
  }
  const uint32_t n = s->n;
  for (uint32_t f = 0; f < frames; ++f) {
    if (s->fade_pos == 0 && s->d_target != s->d) {
      s->d_old = s->d;
      SetWindows(s, s->d_target);
      Refill(s, a);
      s->fade_pos = 1;
    }
    const float kg = s->k_glide;
    s->drive.Step(kg);
    s->ceiling.Step(kg);
    s->link.Step(kg);
    s->mix.Step(kg);
    s->soft.Step(kg);
    const float drive = s->drive.value, c = s->ceiling.value;
    const float link = s->link.value, mix = s->mix.value, soft = s->soft.value;
    const int zero = s->d == 0;

    // Into the line.
    const float xl = Guard(lr[2 * f]), xr = Guard(lr[2 * f + 1]);
    const uint32_t w = s->write;
    a.x[2 * w] = xl;
    a.x[2 * w + 1] = xr;
    a.ctl[2 * w] = drive;
    a.ctl[2 * w + 1] = c;

    // The detector and the gain path.
    const float al = Abs(drive * xl), ar = Abs(drive * xr);
    const float ll = link * ar, lrr = link * al;
    const float pl = al > ll ? al : ll, pr = ar > lrr ? ar : lrr;
    const float eb = zero ? kSafetyKnee * c : c;
    const float e = (1.0f - soft) * eb + soft * (kSoftHeadroom * c);
    const float gl = GainStep(s, a, 0, pl > e ? e / pl : 1.0f, zero);
    const float gr = GainStep(s, a, 1, pr > e ? e / pr : 1.0f, zero);

    // Out of the line, d frames later.
    uint32_t r = w >= s->d ? w - s->d : w + n - s->d;
    float dl = a.x[2 * r], dr = a.x[2 * r + 1];
    const float dd = a.ctl[2 * r];
    float cd = a.ctl[2 * r + 1];
    float ul = dd * dl, ur = dd * dr;
    if (s->fade_pos) {
      r = w >= s->d_old ? w - s->d_old : w + n - s->d_old;
      const float ol = a.x[2 * r], orr = a.x[2 * r + 1];
      const float od = a.ctl[2 * r], oc = a.ctl[2 * r + 1];
      const float t = static_cast<float>(s->fade_pos) * s->fade_step, u = 1.0f - t;
      ul = u * (od * ol) + t * ul;
      ur = u * (od * orr) + t * ur;
      dl = u * ol + t * dl;
      dr = u * orr + t * dr;
      cd = u * oc + t * cd;
      if (++s->fade_pos >= s->fade_len) s->fade_pos = 0;
    }
    const float yl = Stage(ul * gl, cd, soft, zero);
    const float yr = Stage(ur * gr, cd, soft, zero);
    lr[2 * f] = (1.0f - mix) * dl + mix * yl;
    lr[2 * f + 1] = (1.0f - mix) * dr + mix * yr;

    s->write = w + 1u == n ? 0u : w + 1u;
    ++s->now;
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
  SetWindows(s, s->d_target);
  Refill(s, ArraysOf(s));
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
  "\"Designing a straightforward limiter\" (Signalsmith Audio, 2022), no code taken",
  fm1::limit::kParams, fm1::limit::P_COUNT, 0,
  fm1::limit::InstanceSize, fm1::limit::Create, fm1::limit::Destroy,
  NULL, NULL, NULL,
  fm1::limit::Set, fm1::limit::RenderEntry,
};

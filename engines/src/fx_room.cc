// fx_room.cc -- "Room": the reverb of Mutable Instruments Clouds, with the
// stereo diffuser Clouds runs before it (FM1_KIND_AUDIO_FX). Both classes
// are Emilie Gillet's MIT code, vendored unmodified in
// third_party/mutable/clouds (UPSTREAM.md); this file is the wrapper. Notes
// in engines/README.md ("Room"); research in
// notes/2026-10-02-delay-reverb-eq-gates-options.md §3.2.
//
//   in -> guard -> Blur (clouds::Diffuser: four all-passes per side,
//         crossfaded in by Blur) -> clouds::Reverb (L+R in, stereo out, at
//         its full wet) -> Width -> Mix against the guarded input -> out
//
// The reverb is the Griesinger/Dattorro loop that Rings' (our Plate) also
// uses, smaller: 16,384 words of 12-bit delay memory (32 KB) against
// Plate's 32,768 16-bit words, longest delay 4,782 samples against 6,312.
// Clouds feeds it the output of its diffuser in the same order
// (clouds/dsp/granular_processor.cc); here the diffuser sits in the wet path
// only, so Mix 0 passes the input through bit for bit.
//
//   Mix        0..1, a crossfade from the input to the wet, out = dry +
//              Mix (wet - dry), Plate's law. Default 0.3.
//   Decay      0..1, the loop gain per pass, 0.98 Decay^2: from none
//              (the all-passes' own ring, about 0.9 s to -60 dB) to Clouds'
//              longest (0.98, tails of 15 s and more). Clouds itself starts
//              at 0.35, already a 1.5 s tail; the square spends the lower
//              half of the knob on room-sized decays. Default 0.5 (0.245).
//   Damping    0..1, the in-loop one-pole low-pass coefficient 0.97 -
//              0.67 Damping: Clouds' brightest (0.97) to darker than its
//              darkest (0.6 at Damping 0.552). Default 0.4.
//   Diffusion  0..1, the all-pass coefficient 0.5 + 0.25 Diffusion, as
//              Plate's; Clouds fixes 0.7, Diffusion 0.8, the default.
//   Blur       0..1 (page 2), the diffuser's amount: how much of the input
//              is smeared by Clouds' all-passes before it enters the room.
//              Default 0.5.
//   Width      0..1 (page 2), the wet's stereo width: 1 is upstream's two
//              outputs exactly, 0 their mean on both sides. Default 1.
//
// Rate. Clouds ran at 32,000 Hz, and the classes keep every delay and LFO in
// samples, so at 44,118 Hz the room is 0.725 times the size (the longest
// loop delay is 108 ms rather than 149 ms) and the LFOs run 1.38 times as
// fast (0.69 and 0.41 Hz). As in mi_fx.cc, the wrapper keeps what it owns
// in seconds: the loop gain becomes g^(32,000 / host) and the damping
// coefficient 1 - (1 - k)^(32,000 / host), so a tail decays as many dB per
// second, and the damping cuts at the same frequency, as on the module. The
// powers come from fx_room_math.h, not libm, and at 32,000 Hz they return
// the coefficient itself.
//
// Determinism. No libm anywhere in the file; floating-point contraction is
// off for it under clang (the pragma below), the vendored code included, so
// a native build that could fuse multiply-adds (Apple clang on arm64)
// computes the bits WebAssembly computes. That matters more here than in
// most effects: the loop stores 12-bit words, and a sample one ulp away
// sooner or later flips a truncation, after which the tail differs by whole
// LSBs.
//
// Glide. Every parameter glides (one pole, 5 ms) on the coefficient it
// sets, and snaps to its target within 1e-4; values set before the first
// render apply from its first sample. Mix and Width, which the wrapper
// applies, step every frame. The classes' four coefficients step every
// kGrid (8) frames, on a grid counted from create: while they glide the
// classes run up to the next grid point at a time, and once settled the
// rest of the block in one call, which computes the same samples. A
// coefficient inside the loop moving in 8-frame steps of at most 3.6 % of
// its distance should be inaudible; running the classes a frame at a time
// while gliding took 2.5 us per block rather than 1.8 (desktop). Either way
// the output does not depend on the host's block size.
//
// Guard and silence. Every input sample passes the input guard of
// mi_fx.cc (NaN reads as 0, anything beyond +/-16 is clamped, dry path
// included), so nothing non-finite reaches the loop, and the vendored
// float-to-int32 store stays far inside its range (it would overflow past
// about 500,000). The loop's 12-bit store truncates towards zero, so with
// silent input the delay memory decays to exact zeros. The class's two
// damping states are private and are not flushed; for some Damping settings
// one can stop on the smallest subnormal, where it stays without reaching
// the delay memory. The wrapper flushes the wet below 1e-20, so the output
// itself decays to exact zeros.
//
// The diffuser's memory is floats, and its all-passes do not decay to zero
// on their own: with silent input an all-pass holding the smallest subnormal
// writes back 0.625 of it, which rounds to the same subnormal, so every one
// of its 2,048 cells ends up holding a subnormal for good, and each sample
// then does subnormal arithmetic (slow on x86 without flush-to-zero, unknown
// on pi32v2). The memory is the wrapper's, so the wrapper sweeps it: every
// kSweep frames, counted from create, the next kSweep cells below 1e-20 are
// set to 0, between two runs of the classes, so the whole memory is swept
// every 46 ms at 44,118 Hz and the result does not depend on the host's
// blocks. A cell that small is 10^-16 of a 12-bit step of the room, so the
// sound is unchanged until the tail is long gone.
//
// Memory: 41,200 bytes on a 64-bit desktop, 41,184 on 32-bit, of which
// 32,768 are reverb words and 8,192 diffuser floats. Cost on an Apple M1 Max:
// 1.6 us per 64-frame block, 1.8 us while a coefficient glides (Plate: 0.9).
//
// Written in a C-like subset of C++11 (one struct, no heap, no exceptions);
// the vendored classes are C++. MIT licence. Not affiliated with or endorsed
// by Mutable Instruments; the effect's name is our own (docs/11 §7).

// No fused multiply-adds in this file, the vendored headers included: the
// browser's WebAssembly cannot fuse, so a native build that did would round
// differently. GCC ignores the pragma; its -std=c++11 default is already
// -ffp-contract=off.
#if defined(__clang__)
#pragma STDC FP_CONTRACT OFF
#endif

#include "fm1_engine.h"

#include <new>

#include "clouds/dsp/frame.h"
#include "clouds/dsp/fx/diffuser.h"
#include "clouds/dsp/fx/reverb.h"

#include "fx_room_math.h"

namespace fm1 {
namespace room {

enum { P_MIX, P_DECAY, P_DAMPING, P_DIFFUSION, P_BLUR, P_WIDTH, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter glides: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 0.3f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
  { "Decay",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Decay" },
  { "Damping",   FM1_PARAM_FLOAT, 0, 1, 0.4f, NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Damp" },
  { "Diffusion", FM1_PARAM_FLOAT, 0, 1, 0.8f, NULL, 0, 4, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Diffus" },
  { "Blur",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Blur" },
  { "Width",     FM1_PARAM_FLOAT, 0, 1, 1.0f, NULL, 1, 6, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Width" },
};

// The gliding values, each the coefficient a parameter sets. The first two
// are the wrapper's own and glide every frame; the rest are the classes' and
// glide on a grid of kGrid frames.
enum { S_MIX, S_NARROW, S_TIME, S_LP, S_DIFFUSION, S_BLUR, S_COUNT };
const int kFirstClassValue = S_TIME;

const float kCloudsRate = 32000.0f;           // clouds.cc: codec.Init(master, 32000)
const float kInputGain = 0.2f;                // granular_processor.cc, as Plate's
const float kTimeMax = 0.98f;                 // Clouds' longest (0.35 + 0.63)
const float kLpBright = 0.97f, kLpSpan = 0.67f;
const float kDiffusionBase = 0.5f, kDiffusionSpan = 0.25f;
const float kGlideSeconds = 0.005f;
const uint32_t kGrid = 8;                     // frames per class glide step
const float kSnap = 1e-4f;                    // relative distance that snaps
const float kInputLimit = 16.0f;              // the input guard, as mi_fx.cc
const float kFlush = 1e-20f;                  // the wet below this is zero
const float kLog2e = 1.44269504f;
const uint32_t kChunk = 32;                   // frames handled at a time
const uint32_t kSweep = 64;                   // frames between sweeps, and cells per sweep

// clouds::Reverb is FxEngine<16384, FORMAT_12_BIT>: 16,384 uint16_t words.
// clouds::Diffuser is FxEngine<2048, FORMAT_32_BIT>: 2,048 floats.
const size_t kReverbWords = 16384;
const size_t kDiffuserWords = 2048;

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;  // NaN fails both
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;                                        // NaN
}

inline float Flush(float x) { return (x > -kFlush && x < kFlush) ? 0.0f : x; }

// A loop gain per pass that gives the same decay per second at the host
// rate as g gives at Clouds' rate.
inline float RateLoopGain(float g, float native_over_host) {
  return RoomPow(g, native_over_host);
}

// A one-pole coefficient (y += k (x - y)) with the same cutoff in Hz.
inline float RateOnePole(float k, float native_over_host) {
  if (native_over_host == 1.0f) return k;
  const float q = 1.0f - k;
  return 1.0f - RoomPow(q, native_over_host);
}

// One glide step for values [from, to): each moves by k of its distance to
// its target and lands on it exactly once within kSnap. Returns whether any
// is still moving.
inline bool Glide(float *value, const float *target, int from, int to, float k) {
  bool moving = false;
  for (int s = from; s < to; ++s) {
    const float t = target[s];
    const float v = value[s];
    if (v == t) continue;
    const float e = t - v;
    const float a = e < 0.0f ? -e : e;
    const float at = t < 0.0f ? -t : t;
    const float near = kSnap * (1.0f + at);
    if (a <= near) {
      value[s] = t;
    } else {
      const float d = k * e;
      value[s] = v + d;
      moving = true;
    }
  }
  return moving;
}

inline size_t Round16(size_t n) { return (n + 15u) & ~static_cast<size_t>(15u); }

// No constructor of our own: `new (mem) Instance()` value-initialises, which
// zeroes the whole object first, the delay memory and the reverb's two
// damping states (set only by Process) included.
struct Instance {
  clouds::Reverb reverb;
  clouds::Diffuser diffuser;
  float param[P_COUNT];                       // knob values, clamped
  float target[S_COUNT];
  float value[S_COUNT];
  float native_over_host;
  float glide_frame, glide_grid;              // one-pole coefficients
  uint32_t grid_phase;                        // frames rendered, mod kGrid
  uint32_t sweep_phase;                       // frames rendered, mod kSweep
  uint32_t sweep_cell;                        // the diffuser cell the next sweep starts at
  bool running;                               // set by the first render
  bool gliding_mix, gliding_class;            // values off their targets
  alignas(16) uint16_t reverb_memory[kReverbWords];
  alignas(16) float diffuser_memory[kDiffuserWords];

  void Init(float sample_rate) {
    native_over_host = kCloudsRate / sample_rate;
    const float per_sample = kGlideSeconds * sample_rate;
    glide_frame = 1.0f - RoomExp2(-kLog2e / per_sample);
    const float per_grid = static_cast<float>(kGrid) * kLog2e;
    glide_grid = 1.0f - RoomExp2(-per_grid / per_sample);
    reverb.Init(reverb_memory);               // clears the delay memory
    diffuser.Init(diffuser_memory);           // clears it too
    reverb.set_amount(1.0f);                  // wet only; Mix is ours
    reverb.set_input_gain(kInputGain);
    for (int i = 0; i < P_COUNT; ++i) {
      param[i] = kParams[i].def;
      Target(i);
    }
    for (int s = 0; s < S_COUNT; ++s) value[s] = target[s];
    grid_phase = 0;
    sweep_phase = 0;
    sweep_cell = 0;
    gliding_mix = gliding_class = false;
    Apply();
  }

  // The coefficient a knob asks for.
  void Target(int index) {
    const float v = param[index];
    switch (index) {
      case P_MIX: target[S_MIX] = v; break;
      case P_DECAY: {
        const float square = v * v;
        target[S_TIME] = RateLoopGain(kTimeMax * square, native_over_host);
        break;
      }
      case P_DAMPING: {
        const float span = kLpSpan * v;
        target[S_LP] = RateOnePole(kLpBright - span, native_over_host);
        break;
      }
      case P_DIFFUSION: {
        const float span = kDiffusionSpan * v;
        target[S_DIFFUSION] = kDiffusionBase + span;
        break;
      }
      case P_BLUR: target[S_BLUR] = v; break;
      case P_WIDTH: target[S_NARROW] = 1.0f - v; break;   // 0 at Width 1
      default: break;
    }
  }

  void Apply() {
    reverb.set_time(value[S_TIME]);
    reverb.set_lp(value[S_LP]);
    reverb.set_diffusion(value[S_DIFFUSION]);
    diffuser.set_amount(value[S_BLUR]);
  }

  // Before the first render a value follows its target at once, so
  // parameters set at load apply from sample 0; after it, it glides.
  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    param[index] = fm1_param_clamp(&kParams[index], v);
    Target(index);
    if (!running) {
      for (int s = 0; s < S_COUNT; ++s) value[s] = target[s];
      Apply();
    } else if (index == P_MIX || index == P_WIDTH) {
      gliding_mix = true;
    } else {
      gliding_class = true;
    }
  }

  // The next kSweep cells of the diffuser's memory: a value below the
  // flush threshold (a subnormal, once the tail has gone) becomes 0.
  void Sweep() {
    for (uint32_t k = 0; k < kSweep; ++k) {
      const float x = diffuser_memory[sweep_cell];
      if (x > -kFlush && x < kFlush) diffuser_memory[sweep_cell] = 0.0f;
      sweep_cell = (sweep_cell + 1) & (kDiffuserWords - 1);
    }
  }

  void Render(float *lr, uint32_t frames) {
    running = true;
    clouds::FloatFrame wet[kChunk];
    float dry[2 * kChunk];
    while (frames) {
      const uint32_t n = frames < kChunk ? frames : kChunk;
      for (uint32_t i = 0; i < n; ++i) {
        dry[2 * i] = Guard(lr[2 * i]);
        dry[2 * i + 1] = Guard(lr[2 * i + 1]);
        wet[i].l = dry[2 * i];
        wet[i].r = dry[2 * i + 1];
      }
      // The classes: in one call once settled; while their values glide, in
      // runs that end on the grid, a step at the start of each grid cell.
      // Runs also end every kSweep frames, where the diffuser's memory is
      // swept. Both grids count frames since create, so the runs fall on
      // the same frames whatever the host's blocks.
      for (uint32_t i = 0; i < n;) {
        if (sweep_phase == 0) Sweep();
        uint32_t m = n - i;
        if (m > kSweep - sweep_phase) m = kSweep - sweep_phase;
        if (gliding_class) {
          if (grid_phase == 0) {
            gliding_class = Glide(value, target, kFirstClassValue, S_COUNT, glide_grid);
            Apply();
          }
          const uint32_t left = kGrid - grid_phase;
          if (m > left) m = left;
        }
        diffuser.Process(&wet[i], m);
        reverb.Process(&wet[i], m);
        grid_phase = (grid_phase + m) % kGrid;
        sweep_phase = (sweep_phase + m) % kSweep;
        i += m;
      }
      // Width and Mix, gliding every frame.
      for (uint32_t i = 0; i < n; ++i) {
        if (gliding_mix) gliding_mix = Glide(value, target, S_MIX, kFirstClassValue, glide_frame);
        const float mix = value[S_MIX];
        const float narrow = value[S_NARROW];
        float ol = Flush(wet[i].l);           // upstream's outputs at Width 1
        float orr = Flush(wet[i].r);
        if (narrow != 0.0f) {
          const float sum = ol + orr;
          const float mid = 0.5f * sum;
          if (narrow == 1.0f) {               // Width 0: mono, exactly
            ol = orr = mid;
          } else {
            const float nl = narrow * (mid - ol);
            const float nr = narrow * (mid - orr);
            ol = ol + nl;
            orr = orr + nr;
          }
        }
        const float dl = dry[2 * i], dr = dry[2 * i + 1];
        const float xl = mix * (ol - dl);
        const float xr = mix * (orr - dr);
        lr[2 * i] = dl + xl;                  // exactly dl at Mix 0
        lr[2 * i + 1] = dr + xr;
      }
      lr += 2 * n;
      frames -= n;
    }
  }
};

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }

void *Create(void *mem, const fm1_host_t *host) {
  const float rate = host->sample_rate;
  if (!(rate >= 8000.0f && rate <= 384000.0f)) return NULL;   // NaN fails too
  Instance *self = new (mem) Instance();
  self->Init(rate);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace room
}  // namespace fm1

#ifdef FM1_ROOM_PROBE
// Test builds only (fm1-room-test, engines/mk/room.mk): how many of the
// diffuser's cells hold a nonzero value below the flush threshold, so the
// test can see the sweep keep subnormals out of a silent instance.
extern "C" uint32_t fm1_room_probe_tiny(const void *instance);
uint32_t fm1_room_probe_tiny(const void *instance) {
  const fm1::room::Instance *self = static_cast<const fm1::room::Instance *>(instance);
  uint32_t n = 0;
  for (size_t i = 0; i < fm1::room::kDiffuserWords; ++i) {
    const float x = self->diffuser_memory[i];
    if (x != 0.0f && x > -fm1::room::kFlush && x < fm1::room::kFlush) ++n;
  }
  return n;
}
#endif

extern "C" const fm1_engine_t fm1_engine_room = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "room", "Room",
  "Reverb and diffuser from Mutable Instruments Clouds by Emilie Gillet "
  "(MIT); Width and the rate rule from this repository (MIT)",
  fm1::room::kParams, fm1::room::P_COUNT, 0,
  fm1::room::InstanceSize, fm1::room::Create, fm1::room::Destroy,
  NULL, NULL, NULL,
  fm1::room::Set, fm1::room::Render,
};

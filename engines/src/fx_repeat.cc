// fx_repeat.cc -- "Repeat": beat-synchronised stutter and slice hold.
// Original MIT implementation; see notes/2026-10-09-repeat-effect.md.

#include "fm1_engine.h"

#include <cmath>
#include <new>

namespace fm1 {
namespace repeat {

enum { P_HOLD, P_SLICE, P_MIX, P_COUNT };
enum { HOLD_OFF, HOLD_ON };
enum { SLICE_8, SLICE_16, SLICE_32 };

const char *const kHoldNames[] = { "Off", "On", NULL };
const char *const kSliceNames[] = { "1/8 max", "1/16 max", "1/32 max", NULL };
const fm1_param_t kParams[P_COUNT] = {
  { "Hold",      FM1_PARAM_ENUM, 0, 1, HOLD_OFF, kHoldNames, 0, 1,
    FM1_PARAM_MOD, FM1_UNIT_NONE, "Hold" },
  { "Max slice", FM1_PARAM_ENUM, 0, 2, SLICE_16, kSliceNames, 0, 2,
    FM1_PARAM_MOD, FM1_UNIT_NONE, "Slice" },
  { "Mix",       FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3,
    FM1_PARAM_MOD | FM1_PARAM_SMOOTH, FM1_UNIT_NONE, "Mix" },
};

static const uint32_t kCapacity = 16384u;
static const uint32_t kMask = kCapacity - 1u;
static const uint32_t kMinNoteDenominator = 256u;
static const float kMinRate = 8000.0f;
static const float kMaxRate = 192000.0f;
static const float kMinBpm = 20.0f;
static const float kMaxBpm = 300.0f;
static const float kRampSeconds = 0.005f;
static const float kInputLimit = 16.0f;

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;
}

inline float ValidBpm(float bpm, float fallback) {
  if (!(bpm >= kMinBpm && bpm <= kMaxBpm)) return fallback;
  return bpm;
}

// One integer beat subdivision, rounded to the nearest sample. If the
// requested window is too long, only exact octave divisions are considered.
// At 20 BPM and 192 kHz, 1/256 note is 9,000 frames and fits this ring.
uint32_t SliceFrames(float rate, float bpm, uint32_t requested_denominator,
                     uint32_t *effective_denominator) {
  uint32_t denominator = requested_denominator;
  double frames = static_cast<double>(rate) * 240.0 /
                  (static_cast<double>(bpm) * denominator);
  while (frames > kCapacity && denominator < kMinNoteDenominator) {
    denominator *= 2u;
    frames *= 0.5;
  }
  if (effective_denominator) *effective_denominator = denominator;
  if (!(frames >= 1.0)) return 1u;
  uint32_t result = static_cast<uint32_t>(frames + 0.5);
  if (result > kCapacity) result = kCapacity;
  if (result < 1u) result = 1u;
  return result;
}

inline int16_t Pack(float x) {
  if (x > 1.0f) x = 1.0f;
  else if (x < -1.0f) x = -1.0f;
  return static_cast<int16_t>(x * 32767.0f);
}

struct Instance {
  float rate;
  float bpm;
  float pending_bpm;
  float mix;
  float mix_target;
  float mix_step;
  float wet;
  float wet_target;
  float wet_step;
  uint32_t mix_left;
  uint32_t wet_left;
  uint32_t ramp_frames;
  uint32_t ring_write;
  uint32_t ring_valid;
  uint32_t loop_frames;
  uint32_t loop_denominator;
  uint32_t play_pos;
  uint32_t old_loop_frames;
  uint32_t old_play_pos;
  uint32_t fade_left;
  uint32_t fade_frames;
  uint32_t requested_denominator;
  uint8_t hold;
  uint8_t running;
  uint8_t held;
  uint8_t armed;
  uint8_t arm_on_beat;
  uint8_t latch_when_full;
  uint8_t release_pending;
  uint8_t clear_after_release;
  uint8_t rearm_after_clear;
  uint8_t have_bpm;
  uint8_t rendered;
  alignas(16) int16_t ring[2u * kCapacity];

  void Init(const fm1_host_t *host) {
    rate = host->sample_rate;
    bpm = 120.0f;
    pending_bpm = bpm;
    mix = mix_target = kParams[P_MIX].def;
    mix_step = 0.0f;
    wet = wet_step = 0.0f;
    wet_target = 0.0f;
    ramp_frames = static_cast<uint32_t>(rate * kRampSeconds + 0.5f);
    if (ramp_frames < 1u) ramp_frames = 1u;
    requested_denominator = 16u;
  }

  void SetMix(float value) {
    const float target = fm1_param_clamp(&kParams[P_MIX], value);
    if (!rendered) {
      // Hosts normally apply saved parameters before the first audio block.
      // Start there, rather than fading from the factory default on load.
      mix_target = target;
      mix = target;
      mix_left = 0;
      mix_step = 0.0f;
      return;
    }
    if (target == mix_target) return;
    mix_target = target;
    mix_left = ramp_frames;
    mix_step = (mix_target - mix) / static_cast<float>(mix_left);
  }

  void SetWet(float target) {
    if (target < 0.0f) target = 0.0f;
    if (target > 1.0f) target = 1.0f;
    wet_target = target;
    if (wet == target) {
      wet_left = 0;
      wet_step = 0.0f;
      return;
    }
    wet_left = ramp_frames;
    wet_step = (target - wet) / static_cast<float>(wet_left);
  }

  void ClearHistory() {
    ring_write = 0;
    ring_valid = 0;
    loop_frames = 0;
    loop_denominator = 0;
    play_pos = 0;
    old_loop_frames = 0;
    old_play_pos = 0;
    fade_left = 0;
    fade_frames = 0;
    armed = 0;
    arm_on_beat = 0;
    latch_when_full = 0;
    held = 0;
  }

  void FinishRelease() {
    release_pending = 0;
    if (clear_after_release) ClearHistory();
    else held = 0;
    const bool rearm = rearm_after_clear && hold == HOLD_ON;
    clear_after_release = 0;
    rearm_after_clear = 0;
    if (rearm) Arm();
  }

  void BeginRelease(bool clear, bool rearm) {
    release_pending = 1;
    clear_after_release = clear ? 1u : 0u;
    rearm_after_clear = rearm ? 1u : 0u;
    SetWet(0.0f);
    if (wet == 0.0f) FinishRelease();
  }

  void Arm() {
    armed = 1;
    arm_on_beat = running ? 1u : 0u;
    latch_when_full = running ? 0u : 1u;
  }

  uint32_t RequestedDenominator() const {
    return requested_denominator;
  }

  void StartSlice(uint32_t frames, uint32_t denominator) {
    loop_frames = frames;
    loop_denominator = denominator;
    play_pos = 0;
    old_loop_frames = 0;
    fade_left = 0;
    fade_frames = 0;
    held = 1;
    armed = 0;
    arm_on_beat = 0;
    latch_when_full = 0;
    release_pending = 0;
    SetWet(1.0f);
  }

  void Latch() {
    if (ring_valid < kCapacity || release_pending) return;
    uint32_t denominator = 0;
    const uint32_t frames = SliceFrames(rate, bpm, RequestedDenominator(), &denominator);
    StartSlice(frames, denominator);
  }

  void ChangeHeldWindow() {
    if (!held || ring_valid < kCapacity) return;
    uint32_t denominator = 0;
    const uint32_t frames = SliceFrames(rate, bpm, RequestedDenominator(), &denominator);
    if (frames == loop_frames) {
      loop_denominator = denominator;
      return;
    }
    old_loop_frames = loop_frames;
    old_play_pos = play_pos;
    loop_frames = frames;
    loop_denominator = denominator;
    play_pos = 0;
    fade_frames = ramp_frames;
    fade_left = fade_frames;
  }

  void SetParam(uint16_t index, float value) {
    if (index >= P_COUNT) return;
    if (index == P_HOLD) {
      const float clamped = fm1_param_clamp(&kParams[index], value);
      hold = static_cast<uint8_t>(clamped >= 0.5f ? HOLD_ON : HOLD_OFF);
      if (hold == HOLD_OFF) {
        armed = arm_on_beat = latch_when_full = 0;
        BeginRelease(false, false);
      } else if (release_pending) {
        // A quick re-hold waits for the release to reach dry, then requires
        // a complete fresh capture so the released frozen segment cannot be
        // latched again at the next beat.
        clear_after_release = 1;
        rearm_after_clear = 1;
      } else if (!held) {
        Arm();
      }
      return;
    }
    if (index == P_SLICE) {
      const float clamped = fm1_param_clamp(&kParams[index], value);
      const uint32_t choice = static_cast<uint32_t>(clamped + 0.5f);
      requested_denominator = choice == SLICE_8 ? 8u : choice == SLICE_32 ? 32u : 16u;
      return;
    }
    if (index == P_MIX) SetMix(value);
  }

  int16_t Read(uint32_t pos, uint32_t length, uint32_t side) const {
    // ring_write is the next write position and, once full, the oldest
    // retained frame. A held slice ends at the frozen write head, so begin
    // at its own start rather than replaying from the oldest ring frame.
    const uint32_t start = (ring_write - length) & kMask;
    return ring[2u * ((start + pos) & kMask) + side];
  }

  float ReadLoop(uint32_t pos, uint32_t length, uint32_t side) const {
    if (!length) return 0.0f;
    const uint32_t p = pos % length;
    uint32_t fade = ramp_frames;
    if (fade > length / 4u) fade = length / 4u;
    const int16_t a = Read(p, length, side);
    if (!fade || p < length - fade) return static_cast<float>(a) * (1.0f / 32767.0f);
    const uint32_t offset = p - (length - fade);
    // Meet the loop's first sample exactly on its last frame. Blending into
    // a moving head position and then wrapping to head[0] leaves a seam jump
    // on discontinuous material; anchoring the fade preserves the loop's
    // exact sample count and gives the next frame the same value.
    const float t = static_cast<float>(offset + 1u) / static_cast<float>(fade);
    const int16_t b = Read(0u, length, side);
    return ((1.0f - t) * a + t * b) * (1.0f / 32767.0f);
  }

  void StepRamps() {
    if (mix_left) {
      if (mix_left == 1u) mix = mix_target;
      else mix += mix_step;
      --mix_left;
    }
    if (wet_left) {
      if (wet_left == 1u) wet = wet_target;
      else wet += wet_step;
      --wet_left;
      if (!wet_left && wet == 0.0f && release_pending) FinishRelease();
    }
  }

  void Render(const fm1_fx_ext_t *ext, float *lr, uint32_t frames) {
    const bool host_running = ext && ext->running;
    if (ext) {
      if (ext->bpm >= kMinBpm && ext->bpm <= kMaxBpm) {
        if (!have_bpm) bpm = pending_bpm = ext->bpm;
        pending_bpm = ext->bpm;
        have_bpm = 1;
      }
      // A Hold value can be restored before the first render call, when the
      // transport state is not yet known. Reconcile that provisional arm with
      // the host's state before processing any explicit same-frame events.
      if (host_running != (running != 0) &&
          !(ext->events & (FM1_FX_EV_STOP | FM1_FX_EV_START))) {
        running = host_running ? 1u : 0u;
        if (armed) {
          arm_on_beat = running;
          latch_when_full = running ? 0u : 1u;
        }
      }
      // The host event order at one frame is STOP, START, then BEAT.
      if (ext->events & FM1_FX_EV_STOP) {
        running = 0;
        armed = arm_on_beat = latch_when_full = 0;
        BeginRelease(true, false);
      }
      if (ext->events & FM1_FX_EV_START) {
        running = 1;
        BeginRelease(true, hold == HOLD_ON);
      }
      if (ext->events & FM1_FX_EV_RESET) {
        BeginRelease(true, false);
      }
      if (ext->events & FM1_FX_EV_BEAT) {
        bpm = ValidBpm(pending_bpm, bpm);
        if (held) ChangeHeldWindow();
        if (armed && arm_on_beat && !release_pending) Latch();
      }
      running = host_running;
    } else {
      running = 0;
    }
    rendered = 1;

    for (uint32_t i = 0; i < frames; ++i, lr += 2) {
      const float original_l = lr[0], original_r = lr[1];
      const float in_l = Guard(original_l), in_r = Guard(original_r);
      if (!held && !release_pending) {
        ring[2u * ring_write] = Pack(in_l);
        ring[2u * ring_write + 1u] = Pack(in_r);
        ring_write = (ring_write + 1u) & kMask;
        if (ring_valid < kCapacity) ++ring_valid;
        if (armed && latch_when_full && ring_valid == kCapacity) Latch();
      }

      float wet_l = 0.0f, wet_r = 0.0f;
      if (held && loop_frames) {
        wet_l = ReadLoop(play_pos, loop_frames, 0);
        wet_r = ReadLoop(play_pos, loop_frames, 1);
        if (fade_left && old_loop_frames) {
          const float t = 1.0f - static_cast<float>(fade_left) / static_cast<float>(fade_frames);
          const float old_l = ReadLoop(old_play_pos, old_loop_frames, 0);
          const float old_r = ReadLoop(old_play_pos, old_loop_frames, 1);
          wet_l = (1.0f - t) * old_l + t * wet_l;
          wet_r = (1.0f - t) * old_r + t * wet_r;
          old_play_pos = (old_play_pos + 1u) % old_loop_frames;
          --fade_left;
          if (!fade_left) old_loop_frames = 0;
        }
        play_pos = (play_pos + 1u) % loop_frames;
      }

      StepRamps();
      if (mix == 0.0f && mix_left == 0u) {
        // Exact dry: preserve all input bits, including signed zero.
        lr[0] = original_l;
        lr[1] = original_r;
      } else {
        const float wet_gain = mix * wet;
        const float dry_gain = 1.0f - wet_gain;
        lr[0] = dry_gain * in_l + wet_gain * wet_l;
        lr[1] = dry_gain * in_r + wet_gain * wet_r;
      }
    }
  }
};

inline size_t Round16(size_t n) { return (n + 15u) & ~static_cast<size_t>(15u); }

size_t InstanceSize(const fm1_host_t *) { return Round16(sizeof(Instance)); }

void *Create(void *mem, const fm1_host_t *host) {
  if (!host || !(host->sample_rate >= kMinRate && host->sample_rate <= kMaxRate)) return NULL;
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->SetParam(i, v); }
void Render(void *s, float *lr, uint32_t n) {
  static_cast<Instance *>(s)->Render(NULL, lr, n);
}
void RenderExt(void *s, float *lr, uint32_t n, const fm1_fx_ext_t *ext) {
  static_cast<Instance *>(s)->Render(ext, lr, n);
}

}  // namespace repeat
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_repeat = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "repeat", "Repeat",
  "Original MIT implementation; beat-synchronised stutter informed by project performance-FX research",
  fm1::repeat::kParams, fm1::repeat::P_COUNT, 0,
  fm1::repeat::InstanceSize, fm1::repeat::Create, fm1::repeat::Destroy,
  NULL, NULL, NULL,
  fm1::repeat::Set, fm1::repeat::Render,
  NULL,
  FM1_FX_WANT_TEMPO | FM1_FX_WANT_TRANSPORT, fm1::repeat::RenderExt,
  0, 0,
  NULL,
};

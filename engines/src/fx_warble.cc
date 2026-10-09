// fx_warble.cc -- compact, original wow/flutter tape modulation (MIT).
// CHOMPI's Warble is a conceptual reference only; this implementation is
// written independently and uses no CHOMPI/DaisySP code.

#include "fm1_engine.h"

#include <cmath>
#include <new>

namespace fm1 {
namespace warble {

enum { P_WOW, P_FLUTTER, P_MIX, P_COUNT };

const fm1_param_t kParams[P_COUNT] = {
  { "Wow",     FM1_PARAM_FLOAT, 0, 1, 0.35f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Wow" },
  { "Flutter", FM1_PARAM_FLOAT, 0, 1, 0.25f, NULL, 0, 2, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Flut" },
  { "Mix",     FM1_PARAM_FLOAT, 0, 1, 0.5f,  NULL, 0, 3, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Mix" },
};

const uint32_t kCells = 4096;
const uint32_t kMask = kCells - 1;
const float kWordScale = 16384.0f;
const float kInputLimit = 16.0f;
const float kWowHz = 0.35f;
const float kFlutterHz = 6.5f;
const float kWowDepthSeconds = 0.003f;
const float kFlutterDepthSeconds = 0.00045f;
const float kBaseDelaySeconds = 0.012f;

inline float Guard(float x) {
  if (x > -kInputLimit && x < kInputLimit) return x;
  if (x >= kInputLimit) return kInputLimit;
  if (x <= -kInputLimit) return -kInputLimit;
  return 0.0f;
}

inline float ClipStore(float x) {
  if (x > 1.9999f) x = 1.9999f;
  else if (x < -1.9999f) x = -1.9999f;
  return x;
}

inline int16_t Store(float x) {
  return static_cast<int16_t>(ClipStore(x) * kWordScale);
}

// Fast parabolic sine, with a small cubic correction. Phase is [0,1).
inline float Sine(float phase) {
  const float x = 2.0f * phase - 1.0f;
  const float p = -4.0f * x * (1.0f - fabsf(x));
  return p * (0.225f * (fabsf(p) - 1.0f) + 1.0f);
}

inline float Step(float current, float target, float k) {
  const float d = target - current;
  return fabsf(d) < 1e-6f ? target : current + k * d;
}

struct Instance {
  float rate, wow_k, mix_k, mix, wow, flutter;
  float wow_target, flutter_target, mix_target;
  float wow_phase, flutter_phase, wow_inc, flutter_inc;
  uint32_t write;
  bool started;
  float value[P_COUNT];
  alignas(16) int16_t cells[2 * kCells];

  void Init(const fm1_host_t *host) {
    rate = host->sample_rate;
    wow_k = 1.0f - expf(-1.0f / (0.02f * rate));
    mix_k = 1.0f - expf(-1.0f / (0.005f * rate));
    wow_inc = kWowHz / rate;
    flutter_inc = kFlutterHz / rate;
    wow_phase = flutter_phase = 0.0f;
    write = 0;
    started = false;
    for (int i = 0; i < P_COUNT; ++i) value[i] = kParams[i].def;
    wow = wow_target = value[P_WOW];
    flutter = flutter_target = value[P_FLUTTER];
    mix = mix_target = value[P_MIX];
  }

  void Set(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    value[index] = fm1_param_clamp(&kParams[index], v);
    float *now = index == P_WOW ? &wow : index == P_FLUTTER ? &flutter : &mix;
    float *target = index == P_WOW ? &wow_target : index == P_FLUTTER ? &flutter_target : &mix_target;
    *target = value[index];
    if (!started) *now = *target;
  }

  void Render(float *lr, uint32_t frames) {
    started = true;
    const float max_delay = 0.01545f * rate;
    for (uint32_t i = 0; i < frames; ++i, lr += 2) {
      const float raw_l = lr[0], raw_r = lr[1];
      const float in_l = Guard(raw_l), in_r = Guard(raw_r);
      wow = Step(wow, wow_target, wow_k);
      flutter = Step(flutter, flutter_target, wow_k);
      mix = Step(mix, mix_target, mix_k);
      wow_phase += wow_inc;
      flutter_phase += flutter_inc;
      if (wow_phase >= 1.0f) wow_phase -= 1.0f;
      if (flutter_phase >= 1.0f) flutter_phase -= 1.0f;

      // Shared stereo delay head preserves image; separate phases/state live
      // in this instance, so identical creates/renders are reproducible.
      float delay = (kBaseDelaySeconds + wow * kWowDepthSeconds * Sine(wow_phase) +
                     flutter * kFlutterDepthSeconds * Sine(flutter_phase)) * rate;
      if (delay < 2.0f) delay = 2.0f;
      if (delay > max_delay) delay = max_delay;
      cells[2 * write] = Store(in_l);
      cells[2 * write + 1] = Store(in_r);
      float rp = static_cast<float>(write) - delay;
      if (rp < 0.0f) rp += static_cast<float>(kCells);
      const uint32_t c0 = static_cast<uint32_t>(rp) & kMask;
      const uint32_t c1 = (c0 + 1) & kMask;
      const float frac = rp - floorf(rp);
      const float a = 1.0f / kWordScale;
      const float wet_l = ((1.0f - frac) * cells[2 * c0] + frac * cells[2 * c1]) * a;
      const float wet_r = ((1.0f - frac) * cells[2 * c0 + 1] + frac * cells[2 * c1 + 1]) * a;
      write = (write + 1) & kMask;

      // Exact dry bypass; still write guarded input so enabling Mix brings up
      // a current history instead of a stale or frozen buffer.
      if (mix == 0.0f) { lr[0] = raw_l; lr[1] = raw_r; }
      else {
        const float dry = 1.0f - mix;
        lr[0] = dry * in_l + mix * wet_l;
        lr[1] = dry * in_r + mix * wet_r;
      }
    }
  }
};

size_t InstanceSize(const fm1_host_t *) { return (sizeof(Instance) + 15u) & ~static_cast<size_t>(15u); }
void *Create(void *mem, const fm1_host_t *host) {
  if (!(host->sample_rate >= 8000.0f && host->sample_rate <= 192000.0f)) return NULL;
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *s) { static_cast<Instance *>(s)->~Instance(); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->Set(i, v); }
void Render(void *s, float *lr, uint32_t n) { static_cast<Instance *>(s)->Render(lr, n); }

}  // namespace warble
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_warble = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "warble", "Warble",
  "Written here (MIT); conceptual inspiration: CHOMPI Warble",
  fm1::warble::kParams, fm1::warble::P_COUNT, 0,
  fm1::warble::InstanceSize, fm1::warble::Create, fm1::warble::Destroy,
  NULL, NULL, NULL,
  fm1::warble::Set, fm1::warble::Render,
  NULL, 0, NULL, 0, 0, NULL,
};

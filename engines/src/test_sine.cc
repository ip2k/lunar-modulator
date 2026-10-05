// test_sine.cc -- "Test Sine": a minimal polyphonic sine engine with a linear
// attack/release. It exists to test the host, the API and the analysis in
// tests/test_engines.py independently of any third-party DSP. MIT licence.
//
// Volume is SMOOTH: a change while a voice sounds ramps sample by sample over
// 2.5 ms (fm1_smooth.h), the host's samples being this engine's own.

#include "fm1_engine.h"
#include "fm1_smooth.h"

#include <cmath>
#include <new>

namespace fm1 {
namespace test_sine {

enum Param { P_VOLUME, P_COUNT };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. Every parameter is read each block: SMOOTH and MOD.
const fm1_param_t kParams[P_COUNT] = {
  { "Volume", FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Vol" },
};

const int kNumVoices = 12;
const double kTwoPi = 6.283185307179586;  // M_PI is not guaranteed in strict C++11

struct Voice {
  double phase;
  float env;
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
};

class Instance {
 public:
  void Init(const fm1_host_t *host) {
    rate_ = host->sample_rate;
    bend_ = 0.0f;
    volume_ = kParams[P_VOLUME].def;
    fm1_smooth_init(&smooth_, &volume_, 1);
    smooth_steps_ = fm1_smooth_steps(rate_, 1);
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].active = voice_[i].gate = false;
      voice_[i].env = 0.0f;
      voice_[i].phase = 0.0;
    }
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active || v.key == key) {
        if (!v.active) { v.phase = 0.0; v.env = 0.0f; }
        v.key = key;
        v.velocity = velocity / 127.0f;
        v.gate = v.active = true;
        return;
      }
    }
  }

  void NoteOff(uint8_t key) {
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].gate && voice_[i].key == key) voice_[i].gate = false;
    }
  }

  void PitchBend(float semitones) { bend_ = semitones; }

  // A ramp while a voice sounds; at once while none does.
  void SetParam(uint16_t index, float value) {
    if (index == P_VOLUME) {
      fm1_smooth_set(&smooth_, &volume_, fm1_param_clamp(&kParams[P_VOLUME], value),
                     Sounding() ? smooth_steps_ : 0);
    }
  }

  void Render(float *out_lr, uint32_t frames) {
    const float step = 1.0f / (0.005f * rate_);   // 5 ms linear ramps
    for (uint32_t n = 0; n < frames; ++n) {
      fm1_smooth_tick(&smooth_, &volume_, 1);
      float s = 0.0f;
      for (int i = 0; i < kNumVoices; ++i) {
        Voice &v = voice_[i];
        if (!v.active) continue;
        double f = 440.0 * pow(2.0, (v.key + bend_ - 69.0) / 12.0);
        v.phase += f / rate_;
        if (v.phase >= 1.0) v.phase -= 1.0;
        float target = v.gate ? v.velocity : 0.0f;
        if (v.env < target) { v.env += step; if (v.env > target) v.env = target; }
        if (v.env > target) { v.env -= step; if (v.env < target) v.env = target; }
        s += static_cast<float>(sin(kTwoPi * v.phase)) * v.env;
        if (!v.gate && v.env <= 0.0f) v.active = false;
      }
      out_lr[2 * n] = out_lr[2 * n + 1] = s * volume_ * 0.25f;
    }
  }

 private:
  bool Sounding() const {
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active) return true;
    }
    return false;
  }

  Voice voice_[kNumVoices];
  float rate_;
  float bend_;
  float volume_;
  fm1_smooth_t smooth_;       // Volume's ramp
  uint32_t smooth_steps_;     // samples in a ramp
};

size_t InstanceSize(const fm1_host_t *) { return sizeof(Instance); }
void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  self->Init(host);
  return self;
}
void Destroy(void *self) { static_cast<Instance *>(self)->~Instance(); }
void NoteOn(void *s, uint8_t k, uint8_t v) { static_cast<Instance *>(s)->NoteOn(k, v); }
void NoteOff(void *s, uint8_t k) { static_cast<Instance *>(s)->NoteOff(k); }
void Bend(void *s, float st) { static_cast<Instance *>(s)->PitchBend(st); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->SetParam(i, v); }
void Render(void *s, float *out, uint32_t n) { static_cast<Instance *>(s)->Render(out, n); }

}  // namespace test_sine
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_test_sine = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "test-sine", "Test Sine", "This repository (MIT)",
  fm1::test_sine::kParams, fm1::test_sine::P_COUNT, fm1::test_sine::kNumVoices,
  fm1::test_sine::InstanceSize, fm1::test_sine::Create, fm1::test_sine::Destroy,
  fm1::test_sine::NoteOn, fm1::test_sine::NoteOff, fm1::test_sine::Bend,
  fm1::test_sine::Set, fm1::test_sine::Render,
  NULL,   // no per-note offsets: the host tests' engine without them
  0, 0,                     // not a pad kit
};

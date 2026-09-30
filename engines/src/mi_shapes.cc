// mi_shapes.cc -- "Shapes": a polyphonic engine built from the Mutable
// Instruments Braids macro-oscillator (code by Emilie Gillet, MIT; vendored in
// third_party/mutable).
//
// Braids is fixed point and was written for 96 kHz; each voice here is one
// braids::MacroOscillator rendered at the host's rate with the pitch corrected
// by 12*log2(96000 / rate) semitones (the approach of the Schwung and CTAG
// ports). Braids has no amplitude envelope of its own on this path, so each
// voice gets a simple attack/release envelope; Strike() on note-on excites the
// physical and percussive models.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"

#include <cmath>
#include <cstring>
#include <new>

#include "braids/macro_oscillator.h"

namespace fm1 {
namespace shapes {

using namespace braids;

const int kNumShapes = MACRO_OSC_SHAPE_LAST_ACCESSIBLE_FROM_META + 1;

const char *const kShapeNames[kNumShapes] = {
  "CSaw", "Morph", "Saw/Sqr", "Sine/Tri", "Buzz", "Sqr Sub", "Saw Sub",
  "Sqr Sync", "Saw Sync", "3x Saw", "3x Sqr", "3x Tri", "3x Sine", "3x Ring",
  "Swarm", "Comb", "Toy", "LP Flt", "Peak Flt", "BP Flt", "HP Flt", "Vosim",
  "Vowel", "Vowel FOF", "Harmonic", "FM", "FB FM", "Chaos FM", "Pluck",
  "Bowed", "Blown", "Flute", "Bell", "Drum", "Kick", "Cymbal", "Snare",
  "Wavetbl", "Wave Map", "Wave Line", "Wave x4", "Filt Noise", "Twin Peak",
  "Clk Noise", "Granular", "Particle", "Digital",
};

enum Param { P_SHAPE, P_TIMBRE, P_COLOR, P_ATTACK, P_RELEASE, P_VOLUME, P_COUNT };

const fm1_param_t kParams[P_COUNT] = {
  { "Shape",   FM1_PARAM_ENUM,  0, kNumShapes - 1, 0, kShapeNames, 0 },
  { "Timbre",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Color",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Attack",  FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 0 },
  { "Release", FM1_PARAM_FLOAT, 0, 1, 0.3f, NULL, 1 },
  { "Volume",  FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1 },
};

const int kNumVoices = 12;
const size_t kChunk = 24;        // Braids' internal buffers are 24 samples
const float kNativeRate = 96000.0f;

struct Voice {
  MacroOscillator osc;
  int16_t pcm[kChunk];
  float env;
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
  uint32_t age;
};

// Envelope time for a 0..1 knob: 1 ms .. 4 s, exponential.
inline float KnobSeconds(float knob) { return 0.001f * powf(4000.0f, knob); }

class Instance {
 public:
  void Init(const fm1_host_t *host) {
    rate_ = host->sample_rate;
    pitch_offset_ = 12.0f * log2f(kNativeRate / rate_);
    bend_ = 0.0f;
    clock_ = 0;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    memset(sync_, 0, sizeof(sync_));
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].osc.Init();
      voice_[i].env = 0.0f;
      voice_[i].gate = voice_[i].active = false;
      voice_[i].age = 0;
    }
    ApplyShape();
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    Voice *v = Allocate(key);
    v->key = key;
    v->velocity = velocity / 127.0f;
    v->gate = true;
    v->age = ++clock_;
    if (!v->active) v->env = 0.0f;
    v->active = true;
    v->osc.Strike();
  }

  void NoteOff(uint8_t key) {
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].gate && voice_[i].key == key) voice_[i].gate = false;
    }
  }

  void PitchBend(float semitones) { bend_ = semitones; }

  void SetParam(uint16_t index, float value) {
    if (index >= P_COUNT) return;
    value = fm1_param_clamp(&kParams[index], value);
    value_[index] = value;
    if (index == P_SHAPE) ApplyShape();
  }

  void Render(float *out_lr, uint32_t frames) {
    // Per-sample envelope coefficients (one-pole towards the target).
    const float attack = 1.0f - expf(-1.0f / (KnobSeconds(value_[P_ATTACK]) * rate_));
    const float release = 1.0f - expf(-1.0f / (KnobSeconds(value_[P_RELEASE]) * rate_));
    const float gain = value_[P_VOLUME] * 0.25f / 32768.0f;
    const int16_t timbre = static_cast<int16_t>(value_[P_TIMBRE] * 32767.0f);
    const int16_t color = static_cast<int16_t>(value_[P_COLOR] * 32767.0f);

    while (frames) {
      size_t n = frames < kChunk ? frames : kChunk;
      float mix[kChunk] = { 0 };
      for (int i = 0; i < kNumVoices; ++i) {
        Voice &v = voice_[i];
        if (!v.active) continue;
        float note = v.key + bend_ + pitch_offset_;
        int32_t pitch = static_cast<int32_t>(note * 128.0f);
        if (pitch < 0) pitch = 0;
        if (pitch > 32767) pitch = 32767;
        v.osc.set_pitch(static_cast<int16_t>(pitch));
        v.osc.set_parameters(timbre, color);
        v.osc.Render(sync_, v.pcm, n);
        const float target = v.gate ? v.velocity : 0.0f;
        const float k = v.gate ? attack : release;
        for (size_t s = 0; s < n; ++s) {
          v.env += (target - v.env) * k;
          mix[s] += v.pcm[s] * v.env * gain;
        }
        if (!v.gate && v.env < 1e-4f) v.active = false;
      }
      for (size_t s = 0; s < n; ++s) {
        out_lr[2 * s] = out_lr[2 * s + 1] = mix[s];
      }
      out_lr += 2 * n;
      frames -= n;
    }
  }

 private:
  void ApplyShape() {
    int s = static_cast<int>(value_[P_SHAPE] + 0.5f);
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].osc.set_shape(static_cast<MacroOscillatorShape>(s));
    }
  }

  Voice *Allocate(uint8_t key) {
    Voice *best = NULL;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) return &voice_[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {
      if (!voice_[i].active) return &voice_[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {
      Voice *v = &voice_[i];
      if (!best || (!v->gate && best->gate) ||
          (v->gate == best->gate && v->age < best->age)) {
        best = v;
      }
    }
    return best;
  }

  Voice voice_[kNumVoices];
  uint8_t sync_[kChunk];
  float value_[P_COUNT];
  float rate_;
  float pitch_offset_;
  float bend_;
  uint32_t clock_;
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

}  // namespace shapes
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_shapes = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "shapes", "Shapes",
  "Macro-oscillator from Mutable Instruments Braids by Emilie Gillet (MIT)",
  fm1::shapes::kParams, fm1::shapes::P_COUNT, fm1::shapes::kNumVoices,
  fm1::shapes::InstanceSize, fm1::shapes::Create, fm1::shapes::Destroy,
  fm1::shapes::NoteOn, fm1::shapes::NoteOff, fm1::shapes::Bend,
  fm1::shapes::Set, fm1::shapes::Render,
};

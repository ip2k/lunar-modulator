// mi_macro.cc -- "Macro": a polyphonic engine built from Mutable Instruments
// Plaits engines (code by Emilie Gillet, MIT; vendored in third_party/mutable).
//
// Plaits is a one-voice module whose Voice class embeds all 24 engines. This
// wrapper keeps one engine object per voice instead, with Plaits' own decay
// envelope, low-pass-gate envelope and post-processor, driven by note on/off
// the way Plaits behaves with its TRIG and LEVEL inputs patched. Only the light
// engines are offered for now (docs/11 §4): each needs at most a few hundred
// bytes of arena per voice.
//
// Rate: the engines are written for 47,872.34 Hz (Plaits' real I2S rate,
// kCorrectedSampleRate), and their time constants and TIMBRE-derived rates
// are counted in samples and blocks at that rate. They run at that rate here
// whatever the host's, in Plaits' own 12-sample blocks, with no pitch
// correction; the summed mono mix goes through one resampler
// (include/fm1_resampler.h, engines/resampler.md) to the host's rate, as
// Shapes does with Braids' 96 kHz. At a 47,872.34 Hz host the resampler
// passes the mix through bit for bit. Hosts above 47,872.34 Hz or below a
// quarter of it are refused. (Until 2026-10-01 the engines ran at the host's
// rate with the pitch raised by 12*log2(47872.34 / rate) semitones, so at
// 44,118 Hz their envelopes ran 8.5 % long; engines/reference-plaits.md.)
//
// The resampler pulls the mix from a 12-sample buffer as each output sample
// needs it, rendering the next block when the buffer runs out, so the output
// does not depend on the host's block size. Note events land on the next
// block rendered at 47,872.34 Hz (0.25 ms).
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_resampler.h"

#include <cstring>
#include <new>

#include "stmlib/utils/buffer_allocator.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/envelope.h"
#include "plaits/dsp/voice.h"  // ChannelPostProcessor and the engine classes

namespace fm1 {
namespace macro {

using namespace plaits;

enum Model {
  MODEL_VA_VCF,
  MODEL_PHASE_DIST,
  MODEL_WAVE_TERRAIN,
  MODEL_CHIPTUNE,
  MODEL_VIRTUAL_ANALOG,
  MODEL_WAVESHAPING,
  MODEL_FM2,
  MODEL_WAVETABLE,
  MODEL_COUNT
};

const char *const kModelNames[MODEL_COUNT] = {
  "VA+Filter", "PhaseDist", "Terrain", "Chip",
  "VA Pair", "Shaper", "2-op FM", "Wavetable",
};

// Output gains as registered by Plaits' Voice::Init for the same engines.
const float kOutGain[MODEL_COUNT] = {
  1.0f, 0.7f, 0.7f, 0.5f, 0.8f, 0.7f, 0.6f, 0.6f,
};

enum Param {
  P_MODEL, P_HARMONICS, P_TIMBRE, P_MORPH,
  P_DECAY, P_COLOUR, P_VOLUME,
  P_COUNT
};

const fm1_param_t kParams[P_COUNT] = {
  { "Model",     FM1_PARAM_ENUM,  0, MODEL_COUNT - 1, 0, kModelNames, 0 },
  { "Harmonics", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Timbre",    FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Morph",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Decay",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1 },
  { "Colour",    FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1 },
  { "Volume",    FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1 },
};

const int kNumVoices = 12;

constexpr size_t cmax(size_t a, size_t b) { return a > b ? a : b; }

// Per-voice arena. The light engines ask for at most 96 floats, but upstream
// WavetableEngine::Init allocates 64 wave pointers while LoadUserData writes
// 4 banks x 64 = 256 of them. On the module every engine shares one 16 KB
// arena from offset 0, so the overrun lands in unused space; with one tight
// arena per voice it corrupts memory. Size the arena for the 256 pointers
// (1 KB on 32-bit pi32v2, 2 KB on a 64-bit desktop).
const size_t kArenaBytes = cmax(1024, 4 * 64 * sizeof(const int16_t *));
const size_t kEngineBytes = cmax(
    cmax(cmax(sizeof(VirtualAnalogVCFEngine), sizeof(PhaseDistortionEngine)),
         cmax(sizeof(WaveTerrainEngine), sizeof(ChiptuneEngine))),
    cmax(cmax(sizeof(VirtualAnalogEngine), sizeof(WaveshapingEngine)),
         cmax(sizeof(FMEngine), sizeof(WavetableEngine))));

struct Voice {
  alignas(16) unsigned char engine_mem[kEngineBytes];
  alignas(16) char arena[kArenaBytes];
  Engine *engine;
  LPGEnvelope lpg;
  DecayEnvelope decay;
  ChannelPostProcessor post;
  float out[kBlockSize];
  float aux[kBlockSize];
  int16_t pcm[kBlockSize];
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
  bool rising;
  uint32_t age;
};

class Instance {
 public:
  // False when the resampler refuses the host's rate (above 47,872.34 Hz or
  // below a quarter of it).
  bool Init(const fm1_host_t *host) {
    const bool ok =
        fm1_resampler_init(&resampler_, kCorrectedSampleRate, host->sample_rate) != 0;
    bend_ = 0.0f;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    model_ = MODEL_VA_VCF;
    clock_ = 0;
    memset(mix_, 0, sizeof(mix_));
    pending_ = 0;
    BuildEngines();
    return ok;
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    Voice *v = Allocate(key);
    v->key = key;
    v->velocity = velocity / 127.0f;
    v->gate = true;
    v->rising = true;
    v->age = ++clock_;
    if (!v->active) {
      v->engine->Reset();
      v->lpg.Init();
      v->decay.Init();
      v->post.Init();
      v->active = true;
    }
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
    if (index == P_MODEL) {
      int m = static_cast<int>(value + 0.5f);
      if (m != model_) {
        model_ = static_cast<Model>(m);
        BuildEngines();
      }
    }
  }

  // Each output sample pulls the 47,872.34 Hz mix the resampler needs for it,
  // rendering a new 12-sample block whenever the last one is used up.
  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      uint32_t need = fm1_resampler_needed(&resampler_);
      while (need) {
        if (!pending_) {
          RenderBlock();
          pending_ = kBlockSize;
        }
        const uint32_t took = fm1_resampler_push(
            &resampler_, &mix_[kBlockSize - pending_],
            need < pending_ ? need : static_cast<uint32_t>(pending_));
        pending_ -= took;
        need -= took;
      }
      out_lr[2 * f] = out_lr[2 * f + 1] = fm1_resampler_pop(&resampler_);
    }
  }

 private:
  void BuildEngines() {
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      switch (model_) {
        case MODEL_VA_VCF: v.engine = new (v.engine_mem) VirtualAnalogVCFEngine(); break;
        case MODEL_PHASE_DIST: v.engine = new (v.engine_mem) PhaseDistortionEngine(); break;
        case MODEL_WAVE_TERRAIN: v.engine = new (v.engine_mem) WaveTerrainEngine(); break;
        case MODEL_CHIPTUNE: v.engine = new (v.engine_mem) ChiptuneEngine(); break;
        case MODEL_VIRTUAL_ANALOG: v.engine = new (v.engine_mem) VirtualAnalogEngine(); break;
        case MODEL_WAVESHAPING: v.engine = new (v.engine_mem) WaveshapingEngine(); break;
        case MODEL_FM2: v.engine = new (v.engine_mem) FMEngine(); break;
        default: v.engine = new (v.engine_mem) WavetableEngine(); break;
      }
      stmlib::BufferAllocator allocator(v.arena, kArenaBytes);
      v.engine->Init(&allocator);
      v.engine->LoadUserData(NULL);
      v.engine->Reset();
      if (model_ == MODEL_CHIPTUNE) {
        static_cast<ChiptuneEngine *>(v.engine)->set_envelope_shape(
            ChiptuneEngine::NO_ENVELOPE);
      }
      v.lpg.Init();
      v.decay.Init();
      v.post.Init();
      v.gate = v.active = v.rising = false;
      v.age = 0;
    }
  }

  Voice *Allocate(uint8_t key) {
    Voice *best = NULL;
    for (int i = 0; i < kNumVoices; ++i) {   // same key: retrigger in place
      if (voice_[i].active && voice_[i].key == key) return &voice_[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {   // a free voice
      if (!voice_[i].active) return &voice_[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {   // else the oldest released, else the oldest
      Voice *v = &voice_[i];
      if (!best || (!v->gate && best->gate) ||
          (v->gate == best->gate && v->age < best->age)) {
        best = v;
      }
    }
    return best;
  }

  void RenderBlock() {
    float mix[kBlockSize] = { 0 };
    const float decay = value_[P_DECAY];
    const float hf = value_[P_COLOUR];
    const float short_decay = (200.0f * kBlockSize) / kSampleRate *
        stmlib::SemitonesToRatio(-96.0f * decay);
    const float decay_tail = (20.0f * kBlockSize) / kSampleRate *
        stmlib::SemitonesToRatio(-72.0f * decay + 12.0f * hf) - short_decay;
    const float voice_gain = value_[P_VOLUME] * 0.25f / 32768.0f;

    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;

      EngineParameters p;
      p.trigger = (v.rising ? TRIGGER_RISING_EDGE : TRIGGER_LOW) |
                  (v.gate ? TRIGGER_HIGH : TRIGGER_LOW);
      if (v.rising) v.decay.Trigger();
      v.rising = false;
      v.decay.Process(short_decay * 2.0f);

      p.note = v.key + bend_;
      p.harmonics = value_[P_HARMONICS];
      p.timbre = value_[P_TIMBRE];
      p.morph = value_[P_MORPH];
      float level = v.gate ? v.velocity : 0.0f;
      float compressed = 1.3f * level / (0.3f + level);
      if (compressed > 1.0f) compressed = 1.0f;
      p.accent = compressed;

      bool already_enveloped = v.engine->post_processing_settings.already_enveloped;
      v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);

      v.lpg.ProcessLP(compressed, short_decay, decay_tail, hf);
      v.post.Process(kOutGain[model_], false, v.lpg.gain(), v.lpg.frequency(),
                     v.lpg.hf_bleed(), v.out, v.pcm, kBlockSize, 1);
      for (size_t n = 0; n < kBlockSize; ++n) mix[n] += v.pcm[n] * voice_gain;

      if (!v.gate && v.lpg.gain() < 1e-4f) v.active = false;
    }
    memcpy(mix_, mix, sizeof(mix_));
  }

  Voice voice_[kNumVoices];
  float value_[P_COUNT];
  Model model_;
  float bend_;
  uint32_t clock_;
  float mix_[kBlockSize];          // the current block at 47,872.34 Hz
  size_t pending_;                 // samples of mix_ not yet resampled
  fm1_resampler_t resampler_;      // 47,872.34 Hz mix -> host rate, one per instance
};

size_t InstanceSize(const fm1_host_t *) { return sizeof(Instance); }

void *Create(void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  if (!self->Init(host)) {
    self->~Instance();
    return NULL;
  }
  return self;
}

void Destroy(void *self) { static_cast<Instance *>(self)->~Instance(); }
void NoteOn(void *s, uint8_t k, uint8_t v) { static_cast<Instance *>(s)->NoteOn(k, v); }
void NoteOff(void *s, uint8_t k) { static_cast<Instance *>(s)->NoteOff(k); }
void Bend(void *s, float st) { static_cast<Instance *>(s)->PitchBend(st); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->SetParam(i, v); }
void Render(void *s, float *out, uint32_t n) { static_cast<Instance *>(s)->Render(out, n); }

}  // namespace macro
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_macro = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "macro", "Macro",
  "Engines from Mutable Instruments Plaits by Emilie Gillet (MIT)",
  fm1::macro::kParams, fm1::macro::P_COUNT, fm1::macro::kNumVoices,
  fm1::macro::InstanceSize, fm1::macro::Create, fm1::macro::Destroy,
  fm1::macro::NoteOn, fm1::macro::NoteOff, fm1::macro::Bend,
  fm1::macro::Set, fm1::macro::Render,
};

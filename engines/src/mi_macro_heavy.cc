// mi_macro_heavy.cc -- "Macro Heavy": a polyphonic engine built from the heavy
// Mutable Instruments Plaits engines (code by Emilie Gillet, MIT; vendored in
// third_party/mutable), the companion of Macro (mi_macro.cc).
//
// Thirteen models: string machine, chords, speech, formant (grain), additive,
// swarm, filtered noise, particle, string, modal, bass drum, snare drum and
// hi-hat. Each voice keeps one engine object and its own 16 KB arena, the
// size of Plaits' whole shared arena, because the particle engine alone asks
// for all of it (engines/plaits-heavy.md has the table).
//
// What this wrapper takes from Plaits' Voice (plaits/dsp/voice.cc):
// - the output and aux gains each engine is registered with, including the
//   negative ones that put the post-processor's limiter in circuit;
// - the already_enveloped flag: string, modal and the three drums shape their
//   own amplitude, and speech says so per block (words are enveloped, vowels
//   are not). For those the low-pass gate is bypassed, as Voice does;
// - the speech special cases: prosody amount and word speed (Voice takes them
//   from the FM and MORPH attenuverters when TRIG is patched; here prosody is
//   0, which keeps words on the played pitch, and speed is a parameter).
// What it adds: a release after note-off for the self-enveloped models, with
// the same curve and the same Decay/Colour controls as the low-pass gate, so
// a keyboard's note-off is honoured; Plaits has no note-off to honour.
//
// Rate and blocks as in Macro: the engines run at the host's rate with the
// pitch corrected by 12*log2(47872.34 / rate) semitones, in Plaits' own
// 12-sample blocks.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"

#include <cmath>
#include <cstring>
#include <new>

#include "stmlib/utils/buffer_allocator.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/envelope.h"
#include "plaits/dsp/voice.h"  // ChannelPostProcessor and the engine classes

namespace fm1 {
namespace macro_heavy {

using namespace plaits;

enum Model {
  MODEL_STRING_MACHINE,
  MODEL_CHORDS,
  MODEL_SPEECH,
  MODEL_FORMANT,
  MODEL_ADDITIVE,
  MODEL_SWARM,
  MODEL_NOISE,
  MODEL_PARTICLE,
  MODEL_STRING,
  MODEL_MODAL,
  MODEL_BASS_DRUM,
  MODEL_SNARE_DRUM,
  MODEL_HI_HAT,
  MODEL_COUNT
};

const char *const kModelNames[MODEL_COUNT] = {
  "Str Machine", "Chords", "Speech", "Formant", "Additive", "Swarm",
  "Filt Noise", "Particle", "String", "Modal", "Bass Drum", "Snare", "Hi-Hat",
};

// Post-processing as registered by Plaits' Voice::Init for the same engines.
// A negative gain means "run the limiter at this pre-gain".
struct ModelInfo {
  bool already_enveloped;
  float out_gain;
  float aux_gain;
};

const ModelInfo kModelInfo[MODEL_COUNT] = {
  { false, 0.8f, 0.8f },    // string machine
  { false, 0.8f, 0.8f },    // chords
  { false, -0.7f, 0.8f },   // speech (words report already_enveloped per block)
  { false, 0.7f, 0.6f },    // grain / formant
  { false, 0.8f, 0.8f },    // additive
  { false, -3.0f, 1.0f },   // swarm
  { false, -1.0f, -1.0f },  // noise
  { false, -2.0f, 1.0f },   // particle
  { true, -1.0f, 0.8f },    // string
  { true, -1.0f, 0.8f },    // modal
  { true, 0.8f, 0.8f },     // bass drum
  { true, 0.8f, 0.8f },     // snare drum
  { true, 0.8f, 0.8f },     // hi-hat
};

enum Param {
  P_MODEL, P_HARMONICS, P_TIMBRE, P_MORPH,
  P_DECAY, P_COLOUR, P_VOLUME, P_WORD_SPEED,
  P_COUNT
};

const fm1_param_t kParams[P_COUNT] = {
  { "Model",      FM1_PARAM_ENUM,  0, MODEL_COUNT - 1, 0, kModelNames, 0 },
  { "Harmonics",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Timbre",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Morph",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Decay",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1 },
  { "Colour",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1 },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1 },
  { "Word Speed", FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 1 },
};

// Four voices. RAM sets the cap first: every voice carries a 16 KB arena (the
// particle engine's diffuser; string and speech need nearly as much), so four
// voices take ~67 KB of the ~387 KB the stock layout leaves free (docs/11 §2).
// CPU is the unknown [inferred until stage B measures pi32v2]: Plaits runs ONE
// voice of these engines on a 72 MHz Cortex-M4F built to use most of that
// chip, and the FM-1 has ~5,440 cycles per output sample at 240 MHz for
// everything. On the desktop four voices cost about half of Macro's twelve
// (plaits-heavy.md), so the cap can rise if the chip allows.
const int kNumVoices = 4;

constexpr size_t cmax(size_t a, size_t b) { return a > b ? a : b; }

// Arena bytes each engine's Init() asks for, mirroring the upstream
// Allocate<>() calls one for one (plaits-heavy.md lists them). Create() checks
// that exactly this much was handed out, so a failed allocation or an upstream
// change disables the model instead of letting it write through NULL.
const size_t kChordBankBytes = sizeof(float) * kChordNumChords * kChordNumNotes +
                               sizeof(int) * kChordNumChords +
                               sizeof(float) * kChordNumNotes;
constexpr size_t kArenaNeed[MODEL_COUNT] = {
  // StringMachineEngine: chord bank, then the ensemble's 1024-sample line.
  kChordBankBytes + sizeof(Ensemble::E::T) * 1024,
  // ChordEngine: chord bank.
  kChordBankBytes,
  // SpeechEngine: LPC word bank (frames, word boundaries), two temp buffers.
  sizeof(LPCSpeechSynth::Frame) * kLPCSpeechSynthMaxFrames +
      sizeof(int) * kLPCSpeechSynthMaxWords + 2 * sizeof(float) * kMaxBlockSize,
  // GrainEngine: nothing.
  0,
  // AdditiveEngine: harmonic amplitudes.
  sizeof(float) * kNumHarmonics,
  // SwarmEngine: its eight grain voices.
  sizeof(SwarmVoice) * kNumSwarmVoices,
  // NoiseEngine: one temp buffer.
  sizeof(float) * kMaxBlockSize,
  // ParticleEngine: the diffuser's 8192 x 16-bit line, the whole arena.
  sizeof(uint16_t) * 8192,
  // StringEngine: temp buffer, three strings (delay line + stretch line), and
  // the 16-sample f0 delay.
  sizeof(float) * kMaxBlockSize +
      kNumStrings * (sizeof(float) * kDelayLineSize +
                     sizeof(float) * (kDelayLineSize / 4)) +
      sizeof(float) * 16,
  // ModalEngine: one temp buffer.
  sizeof(float) * kMaxBlockSize,
  // BassDrumEngine, SnareDrumEngine: nothing.
  0,
  0,
  // HiHatEngine: two temp buffers.
  sizeof(float) * kMaxBlockSize * 2,
};

const size_t kArenaBytes = cmax(
    cmax(cmax(cmax(kArenaNeed[0], kArenaNeed[1]), cmax(kArenaNeed[2], kArenaNeed[3])),
         cmax(cmax(kArenaNeed[4], kArenaNeed[5]), cmax(kArenaNeed[6], kArenaNeed[7]))),
    cmax(cmax(cmax(kArenaNeed[8], kArenaNeed[9]), cmax(kArenaNeed[10], kArenaNeed[11])),
         kArenaNeed[12]));
static_assert(MODEL_COUNT == 13, "kArenaBytes covers 13 models");
static_assert(kArenaBytes == 16384, "the particle engine sets the arena: Plaits' 16 KB");

const size_t kEngineBytes = cmax(
    cmax(cmax(cmax(sizeof(StringMachineEngine), sizeof(ChordEngine)),
              cmax(sizeof(SpeechEngine), sizeof(GrainEngine))),
         cmax(cmax(sizeof(AdditiveEngine), sizeof(SwarmEngine)),
              cmax(sizeof(NoiseEngine), sizeof(ParticleEngine)))),
    cmax(cmax(cmax(sizeof(StringEngine), sizeof(ModalEngine)),
              cmax(sizeof(BassDrumEngine), sizeof(SnareDrumEngine))),
         sizeof(HiHatEngine)));

// A self-enveloped voice is freed after this much output below the silence
// threshold: 50 ms once the key is up, 1 s while it is still held (a drum hit
// on a held key should not keep its voice busy).
const float kSilentAfterRelease = 0.05f;
const float kSilentWhileHeld = 1.0f;
const int kSilencePcm = 3;  // |pcm| <= 3 LSB, about -80 dBFS (Plaits adds +1)

struct Voice {
  alignas(16) unsigned char engine_mem[kEngineBytes];
  alignas(16) char arena[kArenaBytes];
  Engine *engine;           // NULL: the model failed its arena check, silent
  LPGEnvelope lpg;
  ChannelPostProcessor post_out;
  ChannelPostProcessor post_aux;
  float out[kBlockSize];
  float aux[kBlockSize];
  int16_t pcm_out[kBlockSize];
  int16_t pcm_aux[kBlockSize];
  float release;            // note-off fade for self-enveloped models
  uint32_t silent_blocks;
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
  bool rising;
  uint32_t age;
};

class Instance {
 public:
  void Init(const fm1_host_t *host) {
    rate_offset_ = 12.0f * log2f(kCorrectedSampleRate / host->sample_rate);
    const float blocks_per_second = host->sample_rate / kBlockSize;
    silent_after_release_ = static_cast<uint32_t>(kSilentAfterRelease * blocks_per_second);
    silent_while_held_ = static_cast<uint32_t>(kSilentWhileHeld * blocks_per_second);
    bend_ = 0.0f;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    model_ = MODEL_STRING_MACHINE;
    clock_ = 0;
    pending_ = 0;
    BuildEngines();
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    Voice *v = Allocate(key);
    v->key = key;
    v->velocity = velocity / 127.0f;
    v->gate = true;
    v->rising = true;
    v->age = ++clock_;
    v->silent_blocks = 0;
    if (!v->active) {
      v->release = 1.0f;
      // Speech's Reset() only discards its parsed word bank, which Render()
      // would then parse again inside the audio block; skip it.
      if (v->engine && model_ != MODEL_SPEECH) v->engine->Reset();
      v->lpg.Init();
      v->post_out.Init();
      v->post_aux.Init();
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
    const fm1_param_t &p = kParams[index];
    if (!(value >= p.min)) value = p.min;  // also catches NaN
    if (value > p.max) value = p.max;
    value_[index] = value;
    if (index == P_MODEL) {
      int m = static_cast<int>(value + 0.5f);
      if (m != model_) {
        model_ = static_cast<Model>(m);
        BuildEngines();
      }
    }
  }

  void Render(float *out_lr, uint32_t frames) {
    while (frames) {
      if (!pending_) {
        RenderBlock();
        pending_ = kBlockSize;
      }
      size_t take = frames < pending_ ? frames : pending_;
      const float *src = &block_[2 * (kBlockSize - pending_)];
      memcpy(out_lr, src, take * 2 * sizeof(float));
      out_lr += 2 * take;
      frames -= take;
      pending_ -= take;
    }
  }

 private:
  Engine *Construct(Voice &v) {
    switch (model_) {
      case MODEL_STRING_MACHINE: return new (v.engine_mem) StringMachineEngine();
      case MODEL_CHORDS: return new (v.engine_mem) ChordEngine();
      case MODEL_SPEECH: return new (v.engine_mem) SpeechEngine();
      case MODEL_FORMANT: return new (v.engine_mem) GrainEngine();
      case MODEL_ADDITIVE: return new (v.engine_mem) AdditiveEngine();
      case MODEL_SWARM: return new (v.engine_mem) SwarmEngine();
      case MODEL_NOISE: return new (v.engine_mem) NoiseEngine();
      case MODEL_PARTICLE: return new (v.engine_mem) ParticleEngine();
      case MODEL_STRING: return new (v.engine_mem) StringEngine();
      case MODEL_MODAL: return new (v.engine_mem) ModalEngine();
      case MODEL_BASS_DRUM: return new (v.engine_mem) BassDrumEngine();
      case MODEL_SNARE_DRUM: return new (v.engine_mem) SnareDrumEngine();
      default: return new (v.engine_mem) HiHatEngine();
    }
  }

  void BuildEngines() {
    const ModelInfo &info = kModelInfo[model_];
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      // A clean arena, so no engine reads what the previous model left there.
      memset(v.arena, 0, kArenaBytes);
      Engine *e = Construct(v);
      e->post_processing_settings.already_enveloped = info.already_enveloped;
      e->post_processing_settings.out_gain = info.out_gain;
      e->post_processing_settings.aux_gain = info.aux_gain;
      stmlib::BufferAllocator allocator(v.arena, kArenaBytes);
      e->Init(&allocator);
      // Every Allocate<>() succeeded iff exactly the expected bytes went out.
      v.engine = (kArenaBytes - allocator.free() == kArenaNeed[model_]) ? e : NULL;
      if (v.engine) {
        v.engine->LoadUserData(NULL);
        v.engine->Reset();
      }
      v.lpg.Init();
      v.post_out.Init();
      v.post_aux.Init();
      v.release = 1.0f;
      v.silent_blocks = 0;
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
    float mix_l[kBlockSize] = { 0 };
    float mix_r[kBlockSize] = { 0 };
    const ModelInfo &info = kModelInfo[model_];
    const bool stereo = model_ == MODEL_STRING_MACHINE;  // OUT/AUX are its L/R
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
      if (!v.engine) { v.active = false; continue; }

      EngineParameters p;
      p.trigger = (v.rising ? TRIGGER_RISING_EDGE : TRIGGER_LOW) |
                  (v.gate ? TRIGGER_HIGH : TRIGGER_LOW);
      v.rising = false;
      float note = v.key + bend_ + rate_offset_;
      CONSTRAIN(note, -119.0f, 120.0f);  // Voice's range for the note
      p.note = note;
      p.harmonics = value_[P_HARMONICS];
      p.timbre = value_[P_TIMBRE];
      p.morph = value_[P_MORPH];
      // Accent is the note's velocity for its whole life (drums, strings and
      // speech read it at the trigger or as the word's gain); the low-pass
      // gate's level drops to zero at note-off, as LEVEL does on the module.
      float accent = 1.3f * v.velocity / (0.3f + v.velocity);
      if (accent > 1.0f) accent = 1.0f;
      p.accent = accent;

      if (model_ == MODEL_SPEECH) {
        SpeechEngine *speech = static_cast<SpeechEngine *>(v.engine);
        speech->set_prosody_amount(0.0f);
        speech->set_speed(value_[P_WORD_SPEED]);
      }

      bool already_enveloped = info.already_enveloped;
      v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);

      float gain_from = 1.0f, gain_to = 1.0f;
      if (already_enveloped) {
        v.lpg.Init();   // as Voice does while the gate is bypassed
        gain_from = v.release;
        if (v.gate) {
          v.release = 1.0f;  // a retrigger mid-release ramps back over one block
        } else {
          // The low-pass gate's own release curve, on a plain gain.
          const float r2 = v.release * v.release;
          v.release -= v.release * (short_decay + (1.0f - r2 * r2) * decay_tail);
        }
        gain_to = v.release;
      } else {
        v.lpg.ProcessLP(v.gate ? accent : 0.0f, short_decay, decay_tail, hf);
      }
      v.post_out.Process(info.out_gain, already_enveloped, v.lpg.gain(),
                         v.lpg.frequency(), v.lpg.hf_bleed(), v.out, v.pcm_out,
                         kBlockSize, 1);
      if (stereo) {
        v.post_aux.Process(info.aux_gain, already_enveloped, v.lpg.gain(),
                           v.lpg.frequency(), v.lpg.hf_bleed(), v.aux, v.pcm_aux,
                           kBlockSize, 1);
      }

      const float step = (gain_to - gain_from) / kBlockSize;
      bool silent = true;
      for (size_t n = 0; n < kBlockSize; ++n) {
        const float g = voice_gain * (gain_from + step * (n + 1));
        const int16_t l = v.pcm_out[n];
        const int16_t r = stereo ? v.pcm_aux[n] : l;
        mix_l[n] += l * g;
        mix_r[n] += r * g;
        if (l > kSilencePcm || l < -kSilencePcm || r > kSilencePcm || r < -kSilencePcm) {
          silent = false;
        }
      }

      if (already_enveloped) {
        v.silent_blocks = silent ? v.silent_blocks + 1 : 0;
        const uint32_t hold = v.gate ? silent_while_held_ : silent_after_release_;
        if ((!v.gate && v.release < 1e-4f) || v.silent_blocks > hold) {
          v.active = false;
          v.gate = false;
        }
      } else {
        v.silent_blocks = 0;
        if (!v.gate && v.lpg.gain() < 1e-4f) v.active = false;
      }
    }
    for (size_t n = 0; n < kBlockSize; ++n) {
      block_[2 * n] = mix_l[n];
      block_[2 * n + 1] = mix_r[n];
    }
  }

  Voice voice_[kNumVoices];
  float value_[P_COUNT];
  Model model_;
  float rate_offset_;
  float bend_;
  uint32_t silent_after_release_;
  uint32_t silent_while_held_;
  uint32_t clock_;
  float block_[2 * kBlockSize];
  size_t pending_;
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

}  // namespace macro_heavy
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_macro_heavy = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "macro-heavy", "Macro Heavy",
  "Heavy engines from Mutable Instruments Plaits by Emilie Gillet (MIT)",
  fm1::macro_heavy::kParams, fm1::macro_heavy::P_COUNT, fm1::macro_heavy::kNumVoices,
  fm1::macro_heavy::InstanceSize, fm1::macro_heavy::Create, fm1::macro_heavy::Destroy,
  fm1::macro_heavy::NoteOn, fm1::macro_heavy::NoteOff, fm1::macro_heavy::Bend,
  fm1::macro_heavy::Set, fm1::macro_heavy::Render,
};

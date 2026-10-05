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
// Page 3 holds the module's three attenuverters as Env Pitch, Env Timbre and
// Env Morph: how far the decay envelope, restarted by every note-on, moves
// the note, TIMBRE and MORPH, as Voice::Render applies it with TRIG patched.
// On Chip, Env Timbre sets the chiptune engine's own envelope instead, as on
// the module. Its LPG parameter drives the low-pass gate as LEVEL does (Gate,
// the default), as TRIG alone does (Ping), or bypasses it (Off);
// mi_plaits_env.h has the details. At their defaults the output is what it
// was before they existed, byte for byte.
//
// Per-note offsets (set_param_note, engine API v2; note_offsets.h): every
// FLOAT parameter is POLY. A voice with an offset computes its controls from
// its own values with the code that computes the engine's (Controls), and
// adds its pitch offset to the note after the bend; a voice without one
// plays the engine's controls, so a render without offsets is byte for byte
// what it was before they existed.
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
// SMOOTH parameters (every FLOAT here) ramp while a voice sounds: each
// 12-sample block moves them a tenth of the way, so a change takes 2.5 ms at
// 47,872.34 Hz (fm1_smooth.h). While no voice sounds a change applies at once.
// A voice with a per-note offset computes its controls from the ramped
// values plus its offsets, so its offsets ride on the ramp; an offset itself
// applies at the next block, unramped.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_resampler.h"
#include "fm1_smooth.h"
#include "mi_plaits_env.h"
#include "note_offsets.h"

#include <cstring>
#include <new>

#include "stmlib/utils/buffer_allocator.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/envelope.h"
#include "plaits/dsp/voice.h"  // ChannelPostProcessor and the engine classes

namespace fm1 {
namespace macro {

using namespace plaits;
using namespace plaits_env;

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

// New parameters go at the end, so existing indices keep their meaning.
enum Param {
  P_MODEL, P_HARMONICS, P_TIMBRE, P_MORPH,
  P_DECAY, P_COLOUR, P_VOLUME,
  P_ENV_PITCH, P_ENV_TIMBRE, P_ENV_MORPH, P_LPG,
  P_COUNT
};

// Uids (API v2) are fixed: never renumber one, and give a new parameter the
// next free uid. Macro Heavy shares them for the parameters both have, so a
// lock survives a swap between the two. Model rebuilds every voice (NOLOCK);
// LPG is read every block and a change leaves the notes sounding, so it is
// lockable, but not a modulation target (a note held under Off ends when
// switched to Ping). Every FLOAT is POLY: each voice computes all of them
// for itself once it has an offset (Controls below).
const uint8_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Model",     FM1_PARAM_ENUM,  0, MODEL_COUNT - 1, 0, kModelNames, 0,
    1, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Model" },
  { "Harmonics", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPoly, FM1_UNIT_NONE, "Harm" },
  { "Timbre",    FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPoly, FM1_UNIT_NONE, "Timbre" },
  { "Morph",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 4, kPoly, FM1_UNIT_NONE, "Morph" },
  { "Decay",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, kPoly, FM1_UNIT_NONE, "Decay" },
  { "Colour",    FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 6, kPoly, FM1_UNIT_NONE, "Colour" },
  { "Volume",    FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 7, kPoly, FM1_UNIT_NONE, "Vol" },
  { "Env Pitch",  FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // FM attenuverter
    8, kPoly, FM1_UNIT_NONE, "EnvPit" },
  { "Env Timbre", FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // TIMBRE attenuverter
    9, kPoly, FM1_UNIT_NONE, "EnvTim" },
  { "Env Morph",  FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // MORPH attenuverter
    10, kPoly, FM1_UNIT_NONE, "EnvMor" },
  { "LPG",        FM1_PARAM_ENUM, 0, LPG_MODE_COUNT - 1, LPG_GATE, kLpgModeNames, 2,
    11, 0, FM1_UNIT_NONE, "LPG" },
};

const int kNumVoices = 12;

// A voice's per-note offsets: Harmonics .. Env Morph, and its pitch.
typedef NoteOffsets<P_HARMONICS, P_LPG - P_HARMONICS> Offsets;

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
  float release;            // LPG Off: the key's gain, released at key-up
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
  bool rising;
  uint32_t age;
  Offsets note;             // per-note offsets (set_param_note)
};

// What RenderBlock computes from the parameters, engine-wide, or for one
// voice from its own values when it has offsets: the same function, so a
// voice whose values equal the engine's gets the same numbers bit for bit.
struct Controls {
  float harmonics, timbre, morph;
  float short_decay, decay_tail, hf;   // the decay envelope's and the LPG's times
  float voice_gain;
  bool chip_envelope;                  // Chip: Env Timbre sets its own envelope
  float chip_shape;                    // ...to this
  float env_pitch, env_timbre, env_morph;   // attenuverter amounts
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
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(kCorrectedSampleRate, kBlockSize);
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
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
    if (!v->active) {
      v->release = 1.0f;
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
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
    if (index == P_MODEL) {
      int m = static_cast<int>(value + 0.5f);
      if (m != model_) {
        model_ = static_cast<Model>(m);
        BuildEngines();
      }
    }
  }

  // The voice sounding `key` (one at most: a key retriggers in its own
  // voice), gated or releasing, takes the offset.
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
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
  // A SMOOTH parameter ramps while a voice sounds; anything else, at once.
  uint32_t Steps(uint16_t index) const {
    if (!(kParams[index].flags & FM1_PARAM_SMOOTH)) return 0;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active) return smooth_steps_;
    }
    return 0;
  }

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
      v.release = 1.0f;
      v.gate = v.active = v.rising = false;
      v.age = 0;
      v.note.Clear();
    }
  }

  Controls MakeControls(const float *value) const {
    Controls c;
    c.harmonics = value[P_HARMONICS];
    c.timbre = value[P_TIMBRE];
    c.morph = value[P_MORPH];
    const float decay = value[P_DECAY];
    c.hf = value[P_COLOUR];
    c.short_decay = (200.0f * kBlockSize) / kSampleRate *
        stmlib::SemitonesToRatio(-96.0f * decay);
    c.decay_tail = (20.0f * kBlockSize) / kSampleRate *
        stmlib::SemitonesToRatio(-72.0f * decay + 12.0f * c.hf) - c.short_decay;
    c.voice_gain = value[P_VOLUME] * 0.25f / 32768.0f;
    // The attenuverters, as Voice::Render applies them with TRIG patched. On
    // Chip, TIMBRE's sets the engine's own envelope instead (engine index 7
    // there); at 0 the engine keeps NO_ENVELOPE, as before this page existed.
    c.chip_envelope = model_ == MODEL_CHIPTUNE && value[P_ENV_TIMBRE] != 0.0f;
    c.chip_shape = value[P_ENV_TIMBRE];
    c.env_pitch = AttenuverterAmount(value[P_ENV_PITCH]);
    c.env_timbre = c.chip_envelope ? 0.0f : AttenuverterAmount(value[P_ENV_TIMBRE]);
    c.env_morph = AttenuverterAmount(value[P_ENV_MORPH]);
    return c;
  }

  // A voice's controls: the engine's, unless it has an offset.
  Controls VoiceControls(const Voice &v, const Controls &shared) const {
    if (!v.note.any()) return shared;
    float value[P_COUNT];
    for (int i = 0; i < P_COUNT; ++i) value[i] = v.note.Value(kParams, i, value_[i]);
    return MakeControls(value);
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
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this block's step of any ramp
    float mix[kBlockSize] = { 0 };
    const Controls shared = MakeControls(value_);
    const LpgMode lpg_mode = ToLpgMode(value_[P_LPG]);

    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;
      const Controls c = VoiceControls(v, shared);
      const float short_decay = c.short_decay;
      const float decay_tail = c.decay_tail;
      const float hf = c.hf;
      const float voice_gain = c.voice_gain;

      EngineParameters p;
      p.trigger = (v.rising ? TRIGGER_RISING_EDGE : TRIGGER_LOW) |
                  (v.gate ? TRIGGER_HIGH : TRIGGER_LOW);
      const bool triggered = v.rising;
      if (triggered) {
        v.decay.Trigger();
        if (lpg_mode == LPG_PING) v.lpg.Trigger();   // LEVEL unpatched: TRIG pings
      }
      v.rising = false;
      v.decay.Process(short_decay * 2.0f);
      const float envelope = v.decay.value();

      // No clamp on the note, as before: NoteToFrequency clamps its own.
      float note = v.key + bend_;
      if (v.note.has_pitch()) note += v.note.pitch;
      p.note = note + c.env_pitch * (envelope * envelope * 48.0f);
      p.harmonics = c.harmonics;
      p.timbre = Modulate(c.timbre, c.env_timbre, envelope, 0.0f, 1.0f);
      p.morph = Modulate(c.morph, c.env_morph, envelope, 0.0f, 1.0f);
      float level = v.gate ? v.velocity : 0.0f;
      float compressed = 1.3f * level / (0.3f + level);
      if (compressed > 1.0f) compressed = 1.0f;
      p.accent = compressed;
      if (model_ == MODEL_CHIPTUNE) {
        static_cast<ChiptuneEngine *>(v.engine)->set_envelope_shape(
            c.chip_envelope ? c.chip_shape
                            : static_cast<float>(ChiptuneEngine::NO_ENVELOPE));
      }

      bool already_enveloped = v.engine->post_processing_settings.already_enveloped;
      v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);

      if (lpg_mode == LPG_GATE) {
        v.lpg.ProcessLP(compressed, short_decay, decay_tail, hf);
        v.post.Process(kOutGain[model_], false, v.lpg.gain(), v.lpg.frequency(),
                       v.lpg.hf_bleed(), v.out, v.pcm, kBlockSize, 1);
        for (size_t n = 0; n < kBlockSize; ++n) mix[n] += v.pcm[n] * voice_gain;
        if (!v.gate && v.lpg.gain() < 1e-4f) v.active = false;
        continue;
      }

      // Ping and Off: the velocity's accent scales the voice, since LEVEL no
      // longer carries it (1 at velocity 127, so Ping is Plaits' there).
      const float gain = voice_gain * Accent(v.velocity);
      float gain_from = 1.0f, gain_to = 1.0f;
      bool done;
      if (lpg_mode == LPG_PING) {
        // Pinged: rising until it peaks, then closing over Decay, held or
        // not. The voice ends once the gate is closing and nearly shut; on the
        // trigger's block the gain before it says nothing, so not then.
        const float before = v.lpg.gain();
        const float attack = NoteToFrequency(p.note) * float(kBlockSize) * 2.0f;
        v.lpg.ProcessPing(attack, short_decay, decay_tail, hf);
        done = !triggered && v.lpg.gain() < 1e-4f && v.lpg.gain() <= before;
      } else {
        // Off: bypassed, as Voice does for self-enveloped engines; the key
        // gates a gain with the gate's release curve (Macro Heavy's release).
        v.lpg.Init();
        gain_from = v.release;
        if (v.gate) {
          v.release = 1.0f;  // a retrigger mid-release ramps back over one block
        } else {
          const float r2 = v.release * v.release;
          v.release -= v.release * (short_decay + (1.0f - r2 * r2) * decay_tail);
        }
        gain_to = v.release;
        done = !v.gate && v.release < 1e-4f;
      }
      v.post.Process(kOutGain[model_], lpg_mode == LPG_OFF, v.lpg.gain(),
                     v.lpg.frequency(), v.lpg.hf_bleed(), v.out, v.pcm, kBlockSize, 1);
      const float step = (gain_to - gain_from) / kBlockSize;
      for (size_t n = 0; n < kBlockSize; ++n) {
        mix[n] += v.pcm[n] * (gain * (gain_from + step * (n + 1)));
      }
      if (done) {
        v.active = false;
        v.gate = false;
      }
    }
    memcpy(mix_, mix, sizeof(mix_));
  }

  Voice voice_[kNumVoices];
  float value_[P_COUNT];           // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;          // 12-sample blocks in a ramp
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
void SetNote(void *s, uint8_t k, uint16_t i, float o) {
  static_cast<Instance *>(s)->SetParamNote(k, i, o);
}

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
  fm1::macro::SetNote,
  0, 0,                     // not a pad kit
};

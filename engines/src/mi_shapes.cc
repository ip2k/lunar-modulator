// mi_shapes.cc -- "Shapes": a polyphonic engine built from the Mutable
// Instruments Braids macro-oscillator (code by Emilie Gillet, MIT; vendored in
// third_party/mutable).
//
// Braids is fixed point and was written for 96 kHz, and its time constants
// are counted in samples and blocks at that rate. Each voice here is one
// braids::MacroOscillator rendered at 96 kHz whatever the host's rate, and the
// summed mono mix goes through one resampler (include/fm1_resampler.h,
// engines/resampler.md) to the host's rate. At 44,118 Hz this keeps Braids'
// timing (its struck shapes used to ring 1.6-2.8 times as long when it ran at
// the host's rate with only its pitch corrected), at the cost of rendering
// 96,000 / 44,118 = 2.18 times as many samples; at a 96 kHz host the
// resampler passes the mix through bit for bit. Hosts below 24 kHz or above
// 96 kHz are refused. Braids has no amplitude envelope of its own on this
// path, so each voice gets a simple attack/release envelope, also run at
// 96 kHz; Strike() on note-on excites the physical and percussive models.
//
// The oscillators always render exactly 24 samples at a time, Braids' own
// block (braids.cc kBlockSize), whatever the host block size; the resampler
// pulls the mix from a 24-sample buffer as each output sample needs it, as
// the Macro wrapper buffers Plaits' 12-sample blocks. Several shapes advance
// once per block rather than per sample, so 64-frame host blocks rendered as
// 24 + 24 + 16 made the struck models decay 9-16 % faster than upstream and
// moved the analog, comb, vowel, wave-line and granular shapes off upstream's
// output (engines/reference-braids-fx.md). Note events land at the next
// 24-sample boundary at 96 kHz (0.25 ms).
//
// Per-note offsets (set_param_note, engine API v2; note_offsets.h): Timbre,
// Color, Attack, Release and Volume are POLY, since every voice already sets
// its oscillator's parameters and runs its own envelope, and a pitch offset
// joins the note after the bend. Shape stays engine-wide. A voice without an
// offset plays the engine's values, byte for byte as before.
//
// SMOOTH parameters (every FLOAT here) ramp while a voice sounds: each
// 24-sample chunk moves them a tenth of the way, so a change takes 2.5 ms at
// 96 kHz (fm1_smooth.h). While no voice sounds a change applies at once. A
// voice with an offset plays the ramped value plus its offset, so its
// offset rides on the ramp.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_resampler.h"
#include "fm1_smooth.h"
#include "note_offsets.h"

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

// Uids (API v2) are fixed: never renumber one. Shape sets every voice's
// oscillator at once (NOLOCK). The FLOATs are POLY: each voice's oscillator
// takes its own Timbre and Color, and its envelope and gain are its own.
const uint8_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Shape",   FM1_PARAM_ENUM,  0, kNumShapes - 1, 0, kShapeNames, 0,
    1, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Shape" },
  { "Timbre",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPoly, FM1_UNIT_NONE, "Timbre" },
  { "Color",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPoly, FM1_UNIT_NONE, "Color" },
  { "Attack",  FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 0, 4, kPoly, FM1_UNIT_NONE, "Atk" },
  { "Release", FM1_PARAM_FLOAT, 0, 1, 0.3f, NULL, 1, 5, kPoly, FM1_UNIT_NONE, "Rel" },
  { "Volume",  FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 6, kPoly, FM1_UNIT_NONE, "Vol" },
};

// A voice's per-note offsets: Timbre .. Volume, and its pitch.
typedef NoteOffsets<P_TIMBRE, P_COUNT - P_TIMBRE> Offsets;

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
  Offsets note;   // per-note offsets (set_param_note)
};

// Envelope time for a 0..1 knob: 1 ms .. 4 s, exponential.
inline float KnobSeconds(float knob) { return 0.001f * powf(4000.0f, knob); }

// What RenderChunk computes from the parameters, engine-wide, or for one
// voice from its own values when it has offsets: the same functions, so a
// voice whose values equal the engine's gets the same numbers bit for bit.
struct Controls {
  float attack, release;   // per-sample envelope coefficients at 96 kHz
  float gain;
  int16_t timbre, color;
};

// A per-sample envelope coefficient (one-pole towards the target) for an
// Attack or Release knob, at Braids' rate like everything else in the chunk.
// A powf and an expf: a voice computes its own only for an offset there.
inline float EnvelopeCoefficient(float knob) {
  return 1.0f - expf(-1.0f / (KnobSeconds(knob) * kNativeRate));
}

// The cheap controls: the gain and the oscillator's two parameters.
inline void SetLevels(const float *value, Controls *c) {
  c->gain = value[P_VOLUME] * 0.25f / 32768.0f;
  c->timbre = static_cast<int16_t>(value[P_TIMBRE] * 32767.0f);
  c->color = static_cast<int16_t>(value[P_COLOR] * 32767.0f);
}

inline Controls MakeControls(const float *value) {
  Controls c;
  c.attack = EnvelopeCoefficient(value[P_ATTACK]);
  c.release = EnvelopeCoefficient(value[P_RELEASE]);
  SetLevels(value, &c);
  return c;
}

class Instance {
 public:
  // False when the resampler refuses the host's rate (below 24 kHz or above
  // 96 kHz).
  bool Init(const fm1_host_t *host) {
    const bool ok = fm1_resampler_init(&resampler_, kNativeRate, host->sample_rate) != 0;
    bend_ = 0.0f;
    clock_ = 0;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(kNativeRate, kChunk);
    memset(sync_, 0, sizeof(sync_));
    memset(mix_, 0, sizeof(mix_));
    pending_ = 0;
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].osc.Init();
      voice_[i].env = 0.0f;
      voice_[i].gate = voice_[i].active = false;
      voice_[i].age = 0;
      voice_[i].note.Clear();
    }
    ApplyShape();
    return ok;
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
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
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
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
    if (index == P_SHAPE) ApplyShape();
  }

  // The voice sounding `key` (one at most: a key retriggers in its own
  // voice), held or releasing, takes the offset.
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  // Each output sample pulls the 96 kHz mix the resampler needs for it,
  // rendering a new 24-sample chunk whenever the last one is used up, so the
  // oscillators never see another block size and the output does not depend
  // on the host's.
  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      uint32_t need = fm1_resampler_needed(&resampler_);
      while (need) {
        if (!pending_) {
          RenderChunk();
          pending_ = kChunk;
        }
        const uint32_t took = fm1_resampler_push(
            &resampler_, &mix_[kChunk - pending_],
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

  // A voice's controls: the engine's, unless it has an offset. Then the
  // levels come from its own values, and an envelope coefficient too where
  // that parameter has an offset; elsewhere the engine's is the same number,
  // so a Timbre or pitch offset costs no powf or expf.
  Controls VoiceControls(const Voice &v, const Controls &shared) const {
    if (!v.note.any()) return shared;
    float value[P_COUNT];
    for (int i = 0; i < P_COUNT; ++i) value[i] = v.note.Value(kParams, i, value_[i]);
    Controls c = shared;
    if (v.note.has(P_ATTACK)) c.attack = EnvelopeCoefficient(value[P_ATTACK]);
    if (v.note.has(P_RELEASE)) c.release = EnvelopeCoefficient(value[P_RELEASE]);
    SetLevels(value, &c);
    return c;
  }

  void RenderChunk() {
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this chunk's step of any ramp
    const Controls shared = MakeControls(value_);

    // Mixed on the stack, then stored: accumulating straight into mix_ lets
    // the compiler assume it aliases v.env: 26-55 % more time on the desktop.
    float mix[kChunk] = { 0 };
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;
      const Controls c = VoiceControls(v, shared);
      float note = v.key + bend_;
      if (v.note.has_pitch()) note += v.note.pitch;
      int32_t pitch = static_cast<int32_t>(note * 128.0f);
      if (pitch < 0) pitch = 0;
      if (pitch > 32767) pitch = 32767;
      v.osc.set_pitch(static_cast<int16_t>(pitch));
      v.osc.set_parameters(c.timbre, c.color);
      v.osc.Render(sync_, v.pcm, kChunk);
      const float target = v.gate ? v.velocity : 0.0f;
      const float k = v.gate ? c.attack : c.release;
      const float gain = c.gain;
      for (size_t s = 0; s < kChunk; ++s) {
        v.env += (target - v.env) * k;
        mix[s] += v.pcm[s] * v.env * gain;
      }
      if (!v.gate && v.env < 1e-4f) v.active = false;
    }
    memcpy(mix_, mix, sizeof(mix_));
  }

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
  float mix_[kChunk];              // the current chunk at 96 kHz
  size_t pending_;                 // samples of mix_ not yet resampled
  fm1_resampler_t resampler_;      // 96 kHz mix -> host rate
  float value_[P_COUNT];           // what the chunks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;          // 24-sample chunks in a ramp
  float bend_;
  uint32_t clock_;
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
  fm1::shapes::SetNote,
  0, 0,                     // not a pad kit
};

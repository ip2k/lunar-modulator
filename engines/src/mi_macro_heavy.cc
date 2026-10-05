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
//   Env Pitch, 0 by default, which keeps words on the played pitch, and speed
//   is a parameter of its own);
// - the decay envelope and the three attenuverters it reaches FREQ, TIMBRE
//   and MORPH through (Env Pitch, Env Timbre, Env Morph on page 3, with
//   Voice's scaling for speech), and the LPG mode (Gate, Ping, Off), as in
//   Macro (mi_plaits_env.h). At their defaults the output is what it was
//   before they existed, byte for byte.
// What it adds: a release after note-off for the self-enveloped models, with
// the same curve and the same Decay/Colour controls as the low-pass gate, so
// a keyboard's note-off is honoured; Plaits has no note-off to honour. (With
// the LPG on Ping they ring out as on the module; on Off the same release
// gates the other models.)
// What it changes: speech runs SpeechVoiceEngine (below), Plaits' SpeechEngine
// with one LPC word bank shared by all voices, so a Harmonics move into
// another word bank parses the bank once, not once per voice.
//
// Per-note offsets (set_param_note, engine API v2; note_offsets.h): every
// FLOAT parameter is POLY, as in Macro, and a voice without an offset plays
// the engine's controls, byte for byte as before. On Speech, Harmonics stays
// engine-wide: it picks the word bank all voices share, so its per-note
// offset is ignored there.
//
// Rate and blocks as in Macro: the engines run at Plaits' own 47,872.34 Hz
// whatever the host's rate, in Plaits' 12-sample blocks, with no pitch
// correction, and the mix goes through fm1_resampler.h to the host's rate.
// One resampler per output channel: the string machine's AUX is the right
// channel, so it has a second one. Every other model is mono: both channels'
// mixes are then the same floats (RenderBlock), and the second resampler runs
// on after the string machine, ringing out its AUX, only until it holds
// exactly the first one's state (about 80 output samples at 44,118 Hz: the
// filter's memory); from then on the right channel is the left one's
// output, which is what the second resampler would give, bit for bit. On a
// change into the string machine it takes a copy of the first one's state
// unless it is still running. So the output is what two resamplers running
// all along would give, at the cost of a second one only in the string
// machine and for a few blocks after it. Hosts above 47,872.34 Hz or below a
// quarter of it are refused. Note events land on the next 12-sample block at
// 47,872.34 Hz.
//
// SMOOTH parameters ramp while a voice sounds, as in Macro: a tenth of the
// way per 12-sample block, 2.5 ms in all (fm1_smooth.h). Under Speech the
// word bank follows Harmonics' new value at once (one parse), while the
// voices' Harmonics ramps.
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

#include "stmlib/dsp/hysteresis_quantizer.h"
#include "stmlib/utils/buffer_allocator.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/envelope.h"
#include "plaits/dsp/speech/lpc_speech_synth_words.h"
#include "plaits/dsp/voice.h"  // ChannelPostProcessor and the engine classes

namespace fm1 {
namespace macro_heavy {

using namespace plaits;
using namespace plaits_env;

// The LPC word bank every speech voice reads. Instance::UpdateWordBank picks
// the bank from Harmonics once per 12-sample block and parses it (up to
// 4.8 KB of bitstream into 926 frames) once per bank change, before any voice
// renders. Plaits' SpeechEngine keeps its own bank and quantizer, so four of
// them parsed the same data four times inside one audio block.
struct SpeechShared {
  LPCSpeechSynthWordBank bank;           // storage: voice 0's arena
  stmlib::HysteresisQuantizer2 quantizer;
  int word_bank;                         // -1: phonemes, no bank
};

// Plaits' SpeechEngine (plaits/dsp/engine/speech_engine.cc, Copyright 2016
// Emilie Gillet, MIT; the full notice is in that file), adapted to read the
// shared bank. Render() is upstream's, line for line, except that the word
// bank comes from SpeechShared instead of a per-engine quantizer. Reset() is
// empty: upstream's only discards the bank, which BuildEngines owns here.
class SpeechVoiceEngine : public Engine {
 public:
  SpeechVoiceEngine(SpeechShared *shared, bool owns_bank)
      : shared_(shared), owns_bank_(owns_bank) { }

  virtual void Init(stmlib::BufferAllocator *allocator) {
    sam_speech_synth_.Init();
    naive_speech_synth_.Init();
    if (owns_bank_) {
      shared_->bank.Init(word_banks_, LPC_SPEECH_SYNTH_NUM_WORD_BANKS, allocator);
    }
    lpc_speech_synth_controller_.Init(&shared_->bank);
    temp_buffer_[0] = allocator->Allocate<float>(kMaxBlockSize);
    temp_buffer_[1] = allocator->Allocate<float>(kMaxBlockSize);
    prosody_amount_ = 0.0f;
    speed_ = 0.0f;
  }

  virtual void Reset() { }
  virtual void LoadUserData(const uint8_t *) { }

  // A new bank was loaded: leave the word being played, as upstream's
  // controller does when its own Load() succeeds (it resets the playback
  // position; Init also restarts the LPC synth, from silence).
  void RestartPlayback() { lpc_speech_synth_controller_.Init(&shared_->bank); }

  void set_prosody_amount(float prosody_amount) { prosody_amount_ = prosody_amount; }
  void set_speed(float speed) { speed_ = speed; }

  virtual void Render(const EngineParameters &parameters, float *out, float *aux,
                      size_t size, bool *already_enveloped) {
    const float f0 = NoteToFrequency(parameters.note);
    const float group = parameters.harmonics * 6.0f;

    // Interpolates between the 3 models: naive, SAM, LPC.
    if (group <= 2.0f) {
      *already_enveloped = false;
      float blend = group;
      if (group <= 1.0f) {
        naive_speech_synth_.Render(parameters.trigger == TRIGGER_RISING_EDGE, f0,
                                   parameters.morph, parameters.timbre,
                                   temp_buffer_[0], aux, out, size);
      } else {
        lpc_speech_synth_controller_.Render(
            parameters.trigger & TRIGGER_UNPATCHED,
            parameters.trigger & TRIGGER_RISING_EDGE, -1, f0, 0.0f, 0.0f,
            parameters.morph, parameters.timbre, 1.0f, aux, out, size);
        blend = 2.0f - blend;
      }
      sam_speech_synth_.Render(parameters.trigger == TRIGGER_RISING_EDGE, f0,
                               parameters.morph, parameters.timbre,
                               temp_buffer_[0], temp_buffer_[1], size);
      blend *= blend * (3.0f - 2.0f * blend);
      blend *= blend * (3.0f - 2.0f * blend);
      for (size_t i = 0; i < size; ++i) {
        aux[i] += (temp_buffer_[0][i] - aux[i]) * blend;
        out[i] += (temp_buffer_[1][i] - out[i]) * blend;
      }
    } else {
      // The bank is already loaded (UpdateWordBank), so the controller's own
      // Load() finds it current and parses nothing.
      const int word_bank = shared_->word_bank;
      const bool replay_prosody = word_bank >= 0 &&
          !(parameters.trigger & TRIGGER_UNPATCHED);
      *already_enveloped = replay_prosody;
      lpc_speech_synth_controller_.Render(
          parameters.trigger & TRIGGER_UNPATCHED,
          parameters.trigger & TRIGGER_RISING_EDGE, word_bank, f0,
          prosody_amount_, speed_, parameters.morph, parameters.timbre,
          replay_prosody ? parameters.accent : 1.0f, aux, out, size);
    }
  }

 private:
  SpeechShared *shared_;
  bool owns_bank_;
  NaiveSpeechSynth naive_speech_synth_;
  SAMSpeechSynth sam_speech_synth_;
  LPCSpeechSynthController lpc_speech_synth_controller_;
  float *temp_buffer_[2];
  float prosody_amount_;
  float speed_;
};

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

// New parameters go at the end, so existing indices keep their meaning.
enum Param {
  P_MODEL, P_HARMONICS, P_TIMBRE, P_MORPH,
  P_DECAY, P_COLOUR, P_VOLUME, P_WORD_SPEED,
  P_ENV_PITCH, P_ENV_TIMBRE, P_ENV_MORPH, P_LPG,
  P_COUNT
};

// Uids (API v2) are fixed: never renumber one. The parameters Macro also has
// keep Macro's uids, so a lock survives a swap between the two; Word Speed,
// Macro Heavy's own, takes 12, the first uid Macro does not use. Flags as
// Macro's: Model rebuilds every voice (NOLOCK), LPG is lockable but not a
// modulation target. Every FLOAT is POLY, as in Macro; on Speech a
// Harmonics offset is ignored, since Harmonics picks the word bank all
// voices share (SetParamNote).
const uint8_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Model",      FM1_PARAM_ENUM,  0, MODEL_COUNT - 1, 0, kModelNames, 0,
    1, FM1_PARAM_NOLOCK, FM1_UNIT_NONE, "Model" },
  { "Harmonics",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPoly, FM1_UNIT_NONE, "Harm" },
  { "Timbre",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPoly, FM1_UNIT_NONE, "Timbre" },
  { "Morph",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 4, kPoly, FM1_UNIT_NONE, "Morph" },
  { "Decay",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, kPoly, FM1_UNIT_NONE, "Decay" },
  { "Colour",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 6, kPoly, FM1_UNIT_NONE, "Colour" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 7, kPoly, FM1_UNIT_NONE, "Vol" },
  { "Word Speed", FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 1,
    12, kPoly, FM1_UNIT_NONE, "WrdSpd" },
  { "Env Pitch",  FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // FM attenuverter
    8, kPoly, FM1_UNIT_NONE, "EnvPit" },
  { "Env Timbre", FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // TIMBRE attenuverter
    9, kPoly, FM1_UNIT_NONE, "EnvTim" },
  { "Env Morph",  FM1_PARAM_FLOAT, -1, 1, 0.0f, NULL, 2,   // MORPH attenuverter
    10, kPoly, FM1_UNIT_NONE, "EnvMor" },
  { "LPG",        FM1_PARAM_ENUM, 0, LPG_MODE_COUNT - 1, LPG_GATE, kLpgModeNames, 2,
    11, 0, FM1_UNIT_NONE, "LPG" },
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

// A voice's per-note offsets: Harmonics .. Env Morph, and its pitch.
typedef NoteOffsets<P_HARMONICS, P_LPG - P_HARMONICS> Offsets;

constexpr size_t cmax(size_t a, size_t b) { return a > b ? a : b; }

// Arena bytes each engine's Init() asks for, mirroring the upstream
// Allocate<>() calls one for one (plaits-heavy.md lists them). Create() checks
// that exactly this much was handed out, so a failed allocation or an upstream
// change disables the model instead of letting it write through NULL.
const size_t kChordBankBytes = sizeof(float) * kChordNumChords * kChordNumNotes +
                               sizeof(int) * kChordNumChords +
                               sizeof(float) * kChordNumNotes;
const size_t kSpeechTempBytes = 2 * sizeof(float) * kMaxBlockSize;
constexpr size_t kArenaNeed[MODEL_COUNT] = {
  // StringMachineEngine: chord bank, then the ensemble's 1024-sample line.
  kChordBankBytes + sizeof(Ensemble::E::T) * 1024,
  // ChordEngine: chord bank.
  kChordBankBytes,
  // SpeechVoiceEngine, voice 0: the shared LPC word bank (frames, word
  // boundaries), then two temp buffers. Voices 1-3 take the temp buffers only
  // (ArenaNeed below).
  sizeof(LPCSpeechSynth::Frame) * kLPCSpeechSynthMaxFrames +
      sizeof(int) * kLPCSpeechSynthMaxWords + kSpeechTempBytes,
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

size_t ArenaNeed(int model, int voice) {
  return model == MODEL_SPEECH && voice > 0 ? kSpeechTempBytes : kArenaNeed[model];
}

const size_t kEngineBytes = cmax(
    cmax(cmax(cmax(sizeof(StringMachineEngine), sizeof(ChordEngine)),
              cmax(sizeof(SpeechVoiceEngine), sizeof(GrainEngine))),
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
  DecayEnvelope decay;      // Voice's internal envelope, for the attenuverters
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
  Offsets note;             // per-note offsets (set_param_note)
};

// What RenderBlock computes from the parameters, engine-wide, or for one
// voice from its own values when it has offsets: the same function, so a
// voice whose values equal the engine's gets the same numbers bit for bit.
struct Controls {
  float harmonics, timbre, morph;
  float short_decay, decay_tail, hf;   // the decay envelope's and the LPG's times
  float voice_gain;
  float env_pitch, env_timbre, env_morph;   // attenuverter amounts
  float prosody, word_speed;           // Speech
};

class Instance {
 public:
  // False when the resamplers refuse the host's rate (above 47,872.34 Hz or
  // below a quarter of it).
  bool Init(const fm1_host_t *host) {
    const bool ok_l =
        fm1_resampler_init(&resampler_l_, kCorrectedSampleRate, host->sample_rate) != 0;
    const bool ok_r =
        fm1_resampler_init(&resampler_r_, kCorrectedSampleRate, host->sample_rate) != 0;
    const float blocks_per_second = kCorrectedSampleRate / kBlockSize;
    silent_after_release_ = static_cast<uint32_t>(kSilentAfterRelease * blocks_per_second);
    silent_while_held_ = static_cast<uint32_t>(kSilentWhileHeld * blocks_per_second);
    bend_ = 0.0f;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(kCorrectedSampleRate, kBlockSize);
    model_ = MODEL_STRING_MACHINE;   // stereo: both resamplers run from here
    right_running_ = true;
    clock_ = 0;
    memset(mix_l_, 0, sizeof(mix_l_));
    memset(mix_r_, 0, sizeof(mix_r_));
    pending_ = 0;
    BuildEngines();
    return ok_l && ok_r;
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
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
    if (!v->active) {
      v->release = 1.0f;
      if (v->engine) v->engine->Reset();   // speech: nothing, the bank is shared
      v->lpg.Init();
      v->decay.Init();
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
    value = fm1_param_clamp(&kParams[index], value);   // NaN: the default
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
    if (index == P_MODEL) {
      int m = static_cast<int>(value + 0.5f);
      if (m != model_) {
        // Into the string machine: the right channel's resampler resumes from
        // the left one's state, which is its own once it has stopped (the
        // file's header has why).
        if (m == MODEL_STRING_MACHINE && !right_running_) {
          resampler_r_ = resampler_l_;
          right_running_ = true;
        }
        model_ = static_cast<Model>(m);
        BuildEngines();
      }
    }
  }

  // The voice sounding `key` (one at most: a key retriggers in its own
  // voice), gated or releasing, takes the offset. On Speech a Harmonics
  // offset is kept but not played (VoiceControls).
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  // Each output sample pulls the 47,872.34 Hz mix the resamplers need for it,
  // rendering a new 12-sample block whenever the last one is used up. While
  // the right channel's resampler runs, it takes the same samples' worth as
  // the left one, so they stay in step.
  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      uint32_t need = fm1_resampler_needed(&resampler_l_);
      while (need) {
        if (!pending_) {
          // Outside the string machine the two mixes are equal, so once the
          // two resamplers' states are, they would give the same outputs
          // from here on: the right one can stop.
          if (right_running_ && model_ != MODEL_STRING_MACHINE &&
              SameState(resampler_l_, resampler_r_)) {
            right_running_ = false;
          }
          RenderBlock();
          pending_ = kBlockSize;
        }
        const size_t at = kBlockSize - pending_;
        const uint32_t took = fm1_resampler_push(
            &resampler_l_, &mix_l_[at],
            need < pending_ ? need : static_cast<uint32_t>(pending_));
        if (right_running_) fm1_resampler_push(&resampler_r_, &mix_r_[at], took);
        pending_ -= took;
        need -= took;
      }
      const float l = fm1_resampler_pop(&resampler_l_);
      out_lr[2 * f] = l;
      out_lr[2 * f + 1] = right_running_ ? fm1_resampler_pop(&resampler_r_) : l;
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

  // Two resamplers in step (the same pushes and pops since one was copied
  // from the other) holding the same samples, bit for bit.
  static bool SameState(const fm1_resampler_t &a, const fm1_resampler_t &b) {
    return a.rel == b.rel && a.held == b.held && a.in_w == b.in_w && a.mid_w == b.mid_w &&
           memcmp(a.in, b.in, sizeof(a.in)) == 0 && memcmp(a.mid, b.mid, sizeof(a.mid)) == 0;
  }

  Engine *Construct(Voice &v, bool first) {
    switch (model_) {
      case MODEL_STRING_MACHINE: return new (v.engine_mem) StringMachineEngine();
      case MODEL_CHORDS: return new (v.engine_mem) ChordEngine();
      case MODEL_SPEECH: return new (v.engine_mem) SpeechVoiceEngine(&speech_, first);
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
    speech_.quantizer.Init(LPC_SPEECH_SYNTH_NUM_WORD_BANKS + 1, 0.1f, false);
    speech_.word_bank = -1;
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      // A clean arena, so no engine reads what the previous model left there.
      memset(v.arena, 0, kArenaBytes);
      // Voice 0 goes first: for speech it allocates the shared word bank.
      Engine *e = Construct(v, i == 0);
      e->post_processing_settings.already_enveloped = info.already_enveloped;
      e->post_processing_settings.out_gain = info.out_gain;
      e->post_processing_settings.aux_gain = info.aux_gain;
      stmlib::BufferAllocator allocator(v.arena, kArenaBytes);
      e->Init(&allocator);
      // Every Allocate<>() succeeded iff exactly the expected bytes went out.
      // Speech voices all read voice 0's bank, so they stand or fall with it.
      const bool ok = kArenaBytes - allocator.free() == ArenaNeed(model_, i) &&
          (model_ != MODEL_SPEECH || i == 0 || voice_[0].engine);
      v.engine = ok ? e : NULL;
      if (v.engine) {
        v.engine->LoadUserData(NULL);
        v.engine->Reset();
      }
      v.lpg.Init();
      v.decay.Init();
      v.post_out.Init();
      v.post_aux.Init();
      v.release = 1.0f;
      v.silent_blocks = 0;
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
    // The attenuverters, as Voice::Render applies them with TRIG patched.
    c.env_pitch = AttenuverterAmount(value[P_ENV_PITCH]);
    c.env_timbre = AttenuverterAmount(value[P_ENV_TIMBRE]);
    c.env_morph = AttenuverterAmount(value[P_ENV_MORPH]);
    c.prosody = value[P_ENV_PITCH];   // Voice: the FM attenuverter
    c.word_speed = value[P_WORD_SPEED];
    return c;
  }

  // A voice's controls: the engine's, unless it has an offset. On Speech,
  // Harmonics stays the engine's: it picks the word bank every voice reads
  // (UpdateWordBank), and the envelope's reach (env_amplitude) with it.
  Controls VoiceControls(const Voice &v, const Controls &shared) const {
    if (!v.note.any()) return shared;
    float value[P_COUNT];
    for (int i = 0; i < P_COUNT; ++i) value[i] = v.note.Value(kParams, i, value_[i]);
    if (model_ == MODEL_SPEECH) value[P_HARMONICS] = value_[P_HARMONICS];
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

  // Speech: the word bank for this block, as SpeechEngine::Render picks it
  // (the same quantizer, run only while Harmonics is in the LPC range), but
  // once for all voices, sounding or not. So a Harmonics move into another
  // bank costs one parse in the next block, and a note-on never parses. It
  // reads where Harmonics is going, not its SMOOTH ramp (fm1_smooth.h): a
  // ramp across several banks parses only the last, so the bank changes at
  // most once per set_param, as before the ramps.
  void UpdateWordBank() {
    if (!voice_[0].engine) return;   // no bank storage
    const float group = smooth_[P_HARMONICS].target * 6.0f;
    if (group <= 2.0f) return;
    speech_.word_bank = speech_.quantizer.Process((group - 2.0f) * 0.275f) - 1;
    if (speech_.word_bank >= 0 && speech_.bank.Load(speech_.word_bank)) {
      for (int i = 0; i < kNumVoices; ++i) {
        if (voice_[i].engine) {
          static_cast<SpeechVoiceEngine *>(voice_[i].engine)->RestartPlayback();
        }
      }
    }
  }

  void RenderBlock() {
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this block's step of any ramp
    float mix_l[kBlockSize] = { 0 };
    float mix_r[kBlockSize] = { 0 };
    const ModelInfo &info = kModelInfo[model_];
    const bool stereo = model_ == MODEL_STRING_MACHINE;  // OUT/AUX are its L/R
    const Controls shared = MakeControls(value_);
    if (model_ == MODEL_SPEECH) UpdateWordBank();
    const LpgMode lpg_mode = ToLpgMode(value_[P_LPG]);

    // For speech (engine index 15 in Voice) the envelope's reach on the note
    // and MORPH fades out as HARMONICS moves into the word banks.
    float env_amplitude = 1.0f;
    if (model_ == MODEL_SPEECH) {
      env_amplitude = 2.0f - value_[P_HARMONICS] * 6.0f;
      CONSTRAIN(env_amplitude, 0.0f, 1.0f);
    }

    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;
      if (!v.engine) { v.active = false; continue; }
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
      float note = v.key + bend_;
      if (v.note.has_pitch()) note += v.note.pitch;
      note += c.env_pitch * (env_amplitude * envelope * envelope * 48.0f);
      CONSTRAIN(note, -119.0f, 120.0f);  // Voice's range for the note
      p.note = note;
      p.harmonics = c.harmonics;
      p.timbre = Modulate(c.timbre, c.env_timbre, envelope, 0.0f, 1.0f);
      p.morph = Modulate(c.morph, c.env_morph, env_amplitude * envelope, 0.0f, 1.0f);
      // Accent is the note's velocity for its whole life (drums, strings and
      // speech read it at the trigger or as the word's gain); the low-pass
      // gate's level drops to zero at note-off, as LEVEL does on the module.
      float accent = 1.3f * v.velocity / (0.3f + v.velocity);
      if (accent > 1.0f) accent = 1.0f;
      p.accent = accent;

      if (model_ == MODEL_SPEECH) {
        SpeechVoiceEngine *speech = static_cast<SpeechVoiceEngine *>(v.engine);
        speech->set_prosody_amount(c.prosody);
        speech->set_speed(c.word_speed);
      }

      bool already_enveloped = info.already_enveloped;
      v.engine->Render(p, v.out, v.aux, kBlockSize, &already_enveloped);

      // The gate is bypassed for the self-enveloped models, as Voice does,
      // and for every model with the LPG Off. Bypassed, a plain gain takes the
      // key's note-off (with the LPG on Ping, the self-enveloped models ring
      // out instead, as on the module).
      const bool bypass = already_enveloped || lpg_mode == LPG_OFF;
      float gain_from = 1.0f, gain_to = 1.0f;
      bool ping_shut = false;
      if (bypass) {
        v.lpg.Init();   // as Voice does while the gate is bypassed
        gain_from = v.release;
        if (v.gate || (already_enveloped && lpg_mode == LPG_PING)) {
          v.release = 1.0f;  // a retrigger mid-release ramps back over one block
        } else {
          // The low-pass gate's own release curve, on a plain gain.
          const float r2 = v.release * v.release;
          v.release -= v.release * (short_decay + (1.0f - r2 * r2) * decay_tail);
        }
        gain_to = v.release;
      } else if (lpg_mode == LPG_PING) {
        // Pinged, as in Macro: shut once closing and below 1e-4, never on the
        // trigger's own block.
        const float before = v.lpg.gain();
        const float attack = NoteToFrequency(p.note) * float(kBlockSize) * 2.0f;
        v.lpg.ProcessPing(attack, short_decay, decay_tail, hf);
        ping_shut = !triggered && v.lpg.gain() < 1e-4f && v.lpg.gain() <= before;
      } else {
        v.lpg.ProcessLP(v.gate ? accent : 0.0f, short_decay, decay_tail, hf);
      }
      v.post_out.Process(info.out_gain, bypass, v.lpg.gain(),
                         v.lpg.frequency(), v.lpg.hf_bleed(), v.out, v.pcm_out,
                         kBlockSize, 1);
      if (stereo) {
        v.post_aux.Process(info.aux_gain, bypass, v.lpg.gain(),
                           v.lpg.frequency(), v.lpg.hf_bleed(), v.aux, v.pcm_aux,
                           kBlockSize, 1);
      }

      // On Ping and Off the velocity's accent scales the models the gate
      // would have shaped (1 at velocity 127); the self-enveloped ones have it
      // as their accent already.
      const float level = (lpg_mode != LPG_GATE && !already_enveloped) ? accent : 1.0f;
      const float vg = voice_gain * level;
      const float step = (gain_to - gain_from) / kBlockSize;
      bool silent = true;
      for (size_t n = 0; n < kBlockSize; ++n) {
        const float g = vg * (gain_from + step * (n + 1));
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
      } else if (lpg_mode == LPG_OFF) {
        v.silent_blocks = 0;
        if (!v.gate && v.release < 1e-4f) v.active = false;
      } else if (lpg_mode == LPG_PING) {
        v.silent_blocks = 0;
        if (ping_shut) {
          v.active = false;
          v.gate = false;
        }
      } else {
        v.silent_blocks = 0;
        if (!v.gate && v.lpg.gain() < 1e-4f) v.active = false;
      }
    }
    memcpy(mix_l_, mix_l, sizeof(mix_l_));
    memcpy(mix_r_, mix_r, sizeof(mix_r_));
  }

  Voice voice_[kNumVoices];
  SpeechShared speech_;
  float value_[P_COUNT];           // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;          // 12-sample blocks in a ramp
  Model model_;
  bool right_running_;             // resampler_r_ is fed, and gives the right channel
  float bend_;
  uint32_t silent_after_release_;  // in 12-sample blocks at 47,872.34 Hz
  uint32_t silent_while_held_;
  uint32_t clock_;
  float mix_l_[kBlockSize];        // the current block at 47,872.34 Hz, OUT
  float mix_r_[kBlockSize];        // AUX in the string machine, else = mix_l_
  size_t pending_;                 // samples of the block not yet resampled
  fm1_resampler_t resampler_l_;    // 47,872.34 Hz -> host rate, per channel,
  fm1_resampler_t resampler_r_;    // one pair per instance (not per voice)
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
  fm1::macro_heavy::SetNote,
};

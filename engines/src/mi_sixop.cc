// mi_sixop.cc -- "Six-Op FM": a polyphonic six-operator FM engine built from
// Mutable Instruments Plaits' six-op engine (code by Emilie Gillet, MIT;
// vendored in third_party/mutable), playing the three DX7 banks Plaits ships
// in its resources (fm_patches_table).
//
// Plaits' SixOpEngine is a mono engine with two FMVoices of its own
// (kNumSixOpVoices = 2): each trigger moves to the other one so the previous
// note can ring out, and it renders them staggered, one voice for two blocks
// per call. Here the outer voice allocator does that job instead: each FM-1
// voice is one Plaits FMVoice (fm::Voice<6> plus its LFO) with its own
// unpacked patch, all sharing one fm::Algorithms<6> table. That costs one FM
// voice of CPU per sounding note instead of two, and ~0.8 KB of RAM per voice
// instead of a whole SixOpEngine (~11 KB with its arena) per voice.
//
// What is kept from SixOpEngine::Render (triggered mode, TRIG patched):
// TIMBRE is brightness (modulator levels), MORPH is the envelope control
// (attack/decay and release time scaling), the level's compressed accent is
// the velocity, the output is SoftClip(x * 0.25) with Plaits' out gain 1.0 and
// no low-pass gate (the engine is registered already_enveloped), and the LFO:
// the most recently triggered voice's LFO runs, voices on the same patch
// follow it, voices still sounding another patch run their own.
// What differs:
// - HARMONICS' patch scan (a hysteresis quantizer over 32 patches of one
//   bank) becomes one "Patch" list of all 96 patches, named "<bank> <name>"
//   from the patch data, because the FM-1 picks from lists with an encoder.
//   23 stored names that are trademarks or a person's name are shown under
//   names of our own unless built with -DFM1_SIXOP_ORIGINAL_NAMES (below).
// - The patch's own transpose (DX7 "C3" = 24) is applied, which Plaits
//   ignores; on a keyboard the patches then sound in their intended octave.
// - Two discarded one-sample renders with the gate low precede every
//   note-on, so a stolen or retriggered voice restarts its envelopes
//   (fm::Voice only sees a note-on on a gate edge) and a new patch's setup
//   happens then, not as a silent first block.
// - Per-note offsets (set_param_note, engine API v2; note_offsets.h):
//   Brightness, Envelope and Volume are POLY, since each voice already
//   passes the first two to its fm::Voice and the third is its gain, and a
//   pitch offset joins the note after the bend. Patch stays a note-on choice
//   (LATCH). A voice without an offset plays the engine's values, byte for
//   byte as before.
//
// Rate: FMVoice runs at Plaits' 47,872.34 Hz whatever the host's rate, as
// upstream's SixOpEngine::Init sets it up, in this wrapper's 16-sample blocks
// (envelopes and LFO step once per block), and the mono mix goes through
// fm1_resampler.h to the host's rate, as in Macro. At a 47,872.34 Hz host the
// resampler passes the mix through bit for bit. Hosts above 47,872.34 Hz or
// below a quarter of it are refused. Note events land on the next 16-sample
// block at 47,872.34 Hz. (Until 2026-10-01 FMVoice ran at the host's rate.
// Its pitch and DX7 times were right there too, since FMVoice takes the rate
// in Init; running at upstream's rate makes its samples upstream's, as for
// Macro and Macro Heavy, so all three compare with upstream the same way.)
//
// Brightness, Envelope and Volume are SMOOTH: while a voice sounds a change
// ramps over eight 16-sample blocks, 2.67 ms (fm1_smooth.h: 2.5 ms rounded up
// to whole blocks). While none does it applies at once. A voice with an
// offset plays the ramped value plus its offset, so its offset rides on the
// ramp.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments; engine names here are our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_resampler.h"
#include "fm1_smooth.h"
#include "note_offsets.h"

#include <algorithm>
#include <cstring>
#include <new>

#include "stmlib/dsp/dsp.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/engine2/six_op_engine.h"
#include "plaits/resources.h"

namespace fm1 {
namespace sixop {

using namespace plaits;

const int kNumBanks = 3;
const int kPatchesPerBank = 32;
const int kNumPatches = kNumBanks * kPatchesPerBank;

// The Patch list: "<bank> <name>" for each of the 96 patches.
//
// A name is the one stored in syx_bank_0..2 (plaits/resources.cc, bytes
// 118..127 of each packed patch, trailing spaces trimmed), except where that
// name is a third-party trademark, a product or company name or a person's
// name. Those 23 are shown under a descriptive name of our own, the second
// argument of RENAMED: the browser simulator is to be published, and a
// public page counts as distribution. A build with
// -DFM1_SIXOP_ORIGINAL_NAMES shows the stored names instead, for personal
// builds. Only the names differ; the patch data, and so the sound, is the
// same either way. The tests re-read resources.cc and check the stored
// names against it, and keep the mapping in step with plaits-heavy.md ("The
// patch data"), which says why each one was renamed. The data's origin is
// unstated (plaits-heavy.md, open issues).
#ifdef FM1_SIXOP_ORIGINAL_NAMES
#define RENAMED(stored, shown) stored
#else
#define RENAMED(stored, shown) shown
#endif

const char *const kPatchNames[kNumPatches] = {
  // Bank 1
  /*  0 */ "1 SOLID BASS", RENAMED("1 Mooger Low", "1 Fat Low"),
           "1 LeaderTape", RENAMED("1 MORHOL TB1", "1 ACID BASS"),
  /*  4 */ "1 BASS    3", RENAMED("1 BILL BASS", "1 PLUCK BASS"), "1 BASS    1", "1 ELEC BASS",
  /*  8 */ "1 S.BAS 27.7", "1 RESONANCES", "1 SYN-BASS 2", "1 PRC SYNTH1",
  /* 12 */ RENAMED("1 CROMA 2", "1 PRISM 2"), "1 ANALOG  4", "1 ANALOG A", "1 ANALOG  6",
  /* 16 */ RENAMED("1 CS 80", "1 POLY 80"), "1 INSERT 1",
           "1 SPIRAL", RENAMED("1 DX-TROTT", "1 FM-TROTT"),
  /* 20 */ "1 GASHAUS", "1 RING DING", "1 PAPAGAYO", "1 WINEGLASS",
  /* 24 */ RENAMED("1 AMYTAL", "1 SEDATIVE"), RENAMED("1 FAIRLIGHT", "1 SAMPLER 1"),
           RENAMED("1 *PPG*Vol.1", "1 *Wavetbl 1"), RENAMED("1 *PPG*Vol.2", "1 *Wavetbl 2"),
  /* 28 */ RENAMED("1 *Fairl. 3", "1 *Sampler 3"), "1 *Vocoder 2", "1 *Sequence", "1 Bounce 4",
  // Bank 2
  /* 32 */ "2 E.PIANO 1", RENAMED("2 FENDER 1", "2 TINE EP 1"),
           RENAMED("2 WINTRHODES", "2 WINTER EP"), "2 RS-EP C",
  /* 36 */ RENAMED("2 *Mark III", "2 *Tines III"), "2 CLAV-E.PNO",
           RENAMED("2 SYN-CLAV", "2 SYNTH CLAV"), RENAMED("2 CLAVINET", "2 FUNK CLAV"),
  /* 40 */ "2 PIANO   5", "2 GRD PIANO1", RENAMED("2 STEINWAY", "2 BIG GRAND"), "2 GUIT ACOUS",
  /* 44 */ "2 SITAR", "2 KOTO", "2 HARPSICH 1", "2 CLAV    3",
  /* 48 */ "2 XYLOPHONE", "2 MARIMBA", "2 VIBE    1", "2 GLOKENSPL",
  /* 52 */ "2 BELL C", "2 BELLS", "2 TUB BELLS", "2 GONG    2",
  /* 56 */ "2 KETTLE 6", "2 MID DRM 3", "2 ORI DRUM 1", "2 WOOD 6",
  /* 60 */ "2 LATN DRM 4", "2 CIMBAL", RENAMED("2 SYNDM 25.8", "2 SYNTH DRUM"), "2 B.DRM-SNAR",
  // Bank 3
  /* 64 */ "3 CLICK 124", RENAMED("3 *Hammond 1", "3 *Drawbar 1"), "3 E.ORGAN 3", "3 60-S ORGAN",
  /* 68 */ "3 OPTIC 28", "3 PIPES   1", "3 PIPES   3", "3 PIPES   2",
  /* 72 */ RENAMED("3 JX-33-P", "3 POLY PAD"), "3 SOUNDTRACK",
           "3 ICE PAD  2", RENAMED("3 M1 PADS", "3 LUSH PADS"),
  /* 76 */ RENAMED("3 CARLOS   2", "3 BAROQUE 2"), "3 SOFT TOUCH", "3 *Planets", "3 CIRRUS",
  /* 80 */ "3 ENTRIX", "3 MAL POLY", "3 Textures 6", "3 Etherial5a",
  /* 84 */ "3 'Airy'", "3 BORON A", RENAMED("3 VANGELIS 1", "3 CINEMA 1"), "3 STRINGS C",
  /* 88 */ "3 STRINGS 3", "3 STRINGS 2", "3 STRINGS 7", "3 FULL STRIN",
  /* 92 */ "3 SYN-ORCH", "3 BRASS   1", "3 BRASS 6 BC", "3 BR TRUMPET",
};

#undef RENAMED

enum Param { P_PATCH, P_BRIGHTNESS, P_ENVELOPE, P_VOLUME, P_COUNT };

// Brightness 0.5 plays the modulator levels as programmed. Envelope has no
// neutral point in Plaits: attack/decay rates scale by 2^((0.5 - e) * 8) and
// release rates by 2^(-|e - 0.3| * 8), so the default 0.5 plays attacks and
// decays as programmed with releases about three times longer.

// Uids (API v2) are fixed: never renumber one. Patch is read per voice at
// note-on (LATCH), so a lock or a route picks the patch of the notes that
// start after it and leaves sounding ones alone. The three FLOATs are POLY:
// fm::Voice takes brightness and the envelope control in its parameters,
// which each voice already has, and the volume is a voice's gain.
const uint8_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Patch",      FM1_PARAM_ENUM,  0, kNumPatches - 1, 32, kPatchNames, 0,  // E.PIANO 1
    1, FM1_PARAM_LATCH | FM1_PARAM_MOD, FM1_UNIT_NONE, "Patch" },
  { "Brightness", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0,  // Plaits' TIMBRE
    2, kPoly, FM1_UNIT_NONE, "Bright" },
  { "Envelope",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0,  // Plaits' MORPH
    3, kPoly, FM1_UNIT_NONE, "Env" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 4, kPoly, FM1_UNIT_NONE, "Vol" },
};

// A voice's per-note offsets: Brightness, Envelope and Volume, and its pitch.
typedef NoteOffsets<P_BRIGHTNESS, P_COUNT - P_BRIGHTNESS> Offsets;

// Eight voices. The FM-1's stock msfa plays 12 six-op voices plus effects on
// one pi32v2 core, in fixed point with its hot loops in RAM; Plaits' float
// operators should be of the same order per voice [inferred], and eight
// leaves room for the effect chain. RAM is no constraint (~0.8 KB a voice).
// On the desktop eight voices cost half of Macro's twelve; stage B measures
// the chip, and twelve is a one-line change if it allows.
const int kNumVoices = 8;
const size_t kBlock = 16;         // envelope/LFO update interval, at 47,872.34 Hz
const size_t kPatchBytes = fm::Patch::SYX_SIZE;

// A voice is freed once its key is up and its output has stayed below the
// silence threshold for 50 ms. Held voices are never freed, even when silent
// (sustain level zero): a DX7 attack can be slow enough to stay under the
// threshold for seconds.
const float kSilentAfterRelease = 0.05f;
const float kSilence = 1e-4f;     // -80 dBFS of the voice's own full scale

struct Voice {
  FMVoice fm;
  fm::Patch patch;                // this voice's unpacked copy
  int patch_index;                // what `patch` holds, -1 = nothing yet
  uint32_t silent_blocks;
  float note_offset;              // the patch's transpose, semitones
  uint8_t key;
  float velocity;
  bool gate;
  bool active;
  uint32_t age;
  Offsets note;                   // per-note offsets (set_param_note)
};

class Instance {
 public:
  // False when the resampler refuses the host's rate (above 47,872.34 Hz or
  // below a quarter of it).
  bool Init(const fm1_host_t *host) {
    const bool ok =
        fm1_resampler_init(&resampler_, kCorrectedSampleRate, host->sample_rate) != 0;
    algorithms_.Init();
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      v.fm.Init(&algorithms_, kCorrectedSampleRate);
      v.patch_index = -1;
      v.silent_blocks = 0;
      v.note_offset = 0.0f;
      v.gate = v.active = false;
      v.age = 0;
      v.note.Clear();
    }
    const float blocks_per_second = kCorrectedSampleRate / kBlock;
    silent_after_release_ = static_cast<uint32_t>(kSilentAfterRelease * blocks_per_second);
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(kCorrectedSampleRate, kBlock);
    bend_ = 0.0f;
    lead_ = -1;
    clock_ = 0;
    memset(mix_, 0, sizeof(mix_));
    pending_ = 0;
    return ok;
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    Voice *v = Allocate(key);
    const int index = static_cast<int>(value_[P_PATCH] + 0.5f);
    if (v->patch_index != index) {
      v->fm.UnloadPatch();        // LoadPatch() ignores a pointer it already has
      const int bank = index / kPatchesPerBank;
      const int slot = index % kPatchesPerBank;
      v->patch.Unpack(fm_patches_table[bank] + slot * kPatchBytes);
      v->patch_index = index;
      v->note_offset = static_cast<float>(v->patch.transpose) - 24.0f;
    }
    v->fm.LoadPatch(&v->patch);
    v->fm.mutable_lfo()->Reset();
    v->key = key;
    v->velocity = velocity / 127.0f;
    v->age = ++clock_;
    v->silent_blocks = 0;
    v->active = true;
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
    lead_ = static_cast<int>(v - voice_);

    // Two one-sample renders with the gate low, output discarded. The first
    // runs a newly loaded patch's Setup() (which returns without rendering),
    // so Setup() does not swallow the note's first block; with no new patch
    // it is one sample of release. The second drops fm::Voice's gate, so the
    // next block is a clean note-on edge even when this voice was stolen or
    // retriggered while still held. One sample, not zero: RenderOperators
    // divides by the length (operator.h), and a zero-length render divides
    // by zero, which only a port can do (Plaits never renders 0 samples).
    fm::Voice<6>::Parameters *p = v->fm.mutable_parameters();
    p->gate = false;
    p->sustain = false;
    for (int k = 0; k < 2; ++k) {
      std::fill(&scratch_[0], &scratch_[3], 0.0f);   // a 1-sample render's buffers
      v->fm.Render(scratch_, 1);
    }
    v->gate = true;
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
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
  }

  // The voice sounding `key` (one at most: a key retriggers in its own
  // voice), held or releasing, takes the offset. A pitch offset there at the
  // note's first block is the note fm::Voice samples for its keyboard and
  // rate scaling, as a played note's would be.
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  // Each output sample pulls the 47,872.34 Hz mix the resampler needs for it,
  // rendering a new 16-sample block whenever the last one is used up.
  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      uint32_t need = fm1_resampler_needed(&resampler_);
      while (need) {
        if (!pending_) {
          RenderBlock();
          pending_ = kBlock;
        }
        const uint32_t took = fm1_resampler_push(
            &resampler_, &mix_[kBlock - pending_],
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
    float mix[kBlock] = { 0 };
    const float gain = value_[P_VOLUME] * 0.25f;
    Voice *lead = lead_ >= 0 ? &voice_[lead_] : NULL;
    if (lead) lead->fm.mutable_lfo()->Step(static_cast<float>(kBlock));

    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;

      // Velocity as Plaits derives its accent from LEVEL. fm::NormalizeVelocity
      // reads lut_cube_root[16 * velocity + 1], one past the table at exactly
      // 1.0, so stay just below it.
      float accent = 1.3f * v.velocity / (0.3f + v.velocity);
      if (accent > 0.9999f) accent = 0.9999f;

      fm::Voice<6>::Parameters *p = v.fm.mutable_parameters();
      p->sustain = false;
      p->gate = v.gate;
      float note = v.key + v.note_offset + bend_;
      if (v.note.has_pitch()) note += v.note.pitch;
      p->note = note;
      p->velocity = accent;
      p->brightness = v.note.Value(kParams, P_BRIGHTNESS, value_[P_BRIGHTNESS]);
      p->envelope_control = v.note.Value(kParams, P_ENVELOPE, value_[P_ENVELOPE]);
      const float voice_gain = v.note.has(P_VOLUME)
          ? v.note.Value(kParams, P_VOLUME, value_[P_VOLUME]) * 0.25f : gain;
      if (lead && &v != lead && v.patch_index != lead->patch_index) {
        v.fm.mutable_lfo()->Step(static_cast<float>(kBlock));
        v.fm.set_modulations(v.fm.lfo());
      } else if (lead) {
        v.fm.set_modulations(lead->fm.lfo());
      }

      // fm::Voice mixes its carriers into the first kBlock samples and uses
      // the next 2 * kBlock as operator scratch.
      std::fill(&scratch_[0], &scratch_[kBlock], 0.0f);
      v.fm.Render(scratch_, kBlock);

      bool silent = true;
      for (size_t n = 0; n < kBlock; ++n) {
        const float s = stmlib::SoftClip(scratch_[n] * 0.25f);
        if (s > kSilence || s < -kSilence) silent = false;
        mix[n] += s * voice_gain;
      }
      v.silent_blocks = (silent && !v.gate) ? v.silent_blocks + 1 : 0;
      if (v.silent_blocks > silent_after_release_) v.active = false;
    }
    memcpy(mix_, mix, sizeof(mix_));
  }

  fm::Algorithms<6> algorithms_;  // shared, read-only after Init
  Voice voice_[kNumVoices];
  float scratch_[3 * kBlock];
  float value_[P_COUNT];          // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;         // 16-sample blocks in a ramp
  float bend_;
  int lead_;                      // most recently triggered voice, drives the LFO
  uint32_t silent_after_release_; // in 16-sample blocks at 47,872.34 Hz
  uint32_t clock_;
  float mix_[kBlock];             // the current block at 47,872.34 Hz
  size_t pending_;                // samples of mix_ not yet resampled
  fm1_resampler_t resampler_;     // 47,872.34 Hz mix -> host rate, one per instance
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

}  // namespace sixop
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_sixop = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "sixop", "Six-Op FM",
  "Six-operator FM engine from Mutable Instruments Plaits by Emilie Gillet "
  "(MIT); DX7 patch banks as distributed with Plaits",
  fm1::sixop::kParams, fm1::sixop::P_COUNT, fm1::sixop::kNumVoices,
  fm1::sixop::InstanceSize, fm1::sixop::Create, fm1::sixop::Destroy,
  fm1::sixop::NoteOn, fm1::sixop::NoteOff, fm1::sixop::Bend,
  fm1::sixop::Set, fm1::sixop::Render,
  fm1::sixop::SetNote,
};

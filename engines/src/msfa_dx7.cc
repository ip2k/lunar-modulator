// msfa_dx7.cc -- "FM6" (engine id "dx7"): a polyphonic six-operator FM
// engine that plays DX7 voice data on msfa, the FM core of Google's
// music-synthesizer-for-android (Raph Levien for Google, Apache-2.0; vendored
// byte-identical in third_party/msfa) and the core the stock FM-1 runs
// (docs/02 §5). engines/msfa.md has the whole story; in short:
//
// - msfa does the synthesis: its envelope generators (Env), pitch envelope
//   (PitchEnv), LFO (Lfo), the 32 algorithms with feedback (FmCore and
//   FmOpKernel, integer kernels), its sine, exponential and frequency tables
//   (Sin, Exp2, Freqlut) and its note set-up (dx7note.cc: keyboard level and
//   rate scaling, velocity, operator pitch). Its Dx7Note class is not used:
//   this file puts a voice together from the same parts, as Dx7Note::init
//   and ::compute do, and adds what msfa leaves out (below).
// - Voice data: 155-parameter DX7 voices, from a built-in bank of our own
//   (dx7_bank.h, made by tools/dx7_bank.py) or from SysEx dumps loaded into
//   32 user slots (fm1_dx7.h, dx7_voice.cc). The patch's transpose is
//   applied (msfa's synth ignores it).
// - Added to msfa, our own code:
//   * amplitude modulation from the LFO (AMD, and each operator's AMS),
//     which msfa's Dx7Note does not do: an attenuation in the envelope's
//     log domain, as Yamaha's FM chips apply it [inferred], up to 96 dB at
//     AMS 3 and AMD 99, AMS 1 and 2 at 0.259 and 0.427 of that (Dexed's
//     sensitivity ratios, via Felucca's fm6_core.c [reported]);
//   * the multi-operator feedback loops of algorithms 4 and 6 (the fourth,
//     or fifth, operator's output fed back to the sixth), which msfa's table
//     marks but its FmCore does not run ("todo: more than one op in a
//     feedback loop"): with feedback on, those two or three operators run
//     sample by sample here, the rest through FmCore;
//   * four macros over the patch (Brightness, Env Time, Feedback, Volume),
//     per-note offsets and pitch, the SMOOTH ramps, voice allocation and
//     release;
//   * glide and the voice modes (glide.h): the glide joins the bend in the
//     voice's pitch, once per 64-sample block; a Legato move keeps the
//     envelopes and the LFO running and moves the operators that follow the
//     key, to the bit where a note-on on the new key would put them, with
//     the first note's keyboard level and rate scaling.
//
// Rate: msfa runs at the host's rate, in its own 64-sample blocks (the
// envelopes and the LFO step once per block), rendered as the host's calls
// need them, so the output does not depend on the host's block size; note
// and parameter events land on the next 64-sample block. Freqlut, Lfo and
// PitchEnv scale their tables to the rate. msfa's Env counts blocks (its
// rates are set for 44.1 kHz), so the envelope clock here is scaled by
// 44,118 / rate: exactly one envelope step per block at the FM-1's 44,118 Hz,
// as msfa itself runs, and the same times at any other rate. msfa's sine and
// exp2 tables are const data (flash on the FM-1: src/msfa_prelude.h), and so
// is its frequency table at 44,118 Hz; at any other rate the instance holds
// its own (4,100 bytes more, counted in its size). The rate units of Lfo and
// PitchEnv are globals, set by the first create; a later create at another
// rate is refused (as the Schwung shim refuses one).
//
// The engine is Google's msfa and its name is Felucca's: FM6 is the FM
// engine of hugelton's Felucca, whose Apache-2.0 fm6_core.c is this
// engine's test oracle (third_party/felucca-fm6). Both borrowed, with
// thanks (the owner kept the name, 2026-10-06: "since we're borrowing it").
//
// MIT licence (this file). Not affiliated with or endorsed by Yamaha.

#include "fm1_engine.h"
#include "fm1_dx7.h"
#include "fm1_smooth.h"
#include "glide.h"
#include "note_offsets.h"

#include <new>

#include "dx7_bank.h"
#include "dx7_loop.h"
#include "dx7_voice.h"
#include "msfa.h"   // last: msfa's headers define macros

namespace fm1 {
namespace dx7 {

using fm1_msfa::Env;
using fm1_msfa::Exp2;
using fm1_msfa::FmCore;
using fm1_msfa::FmOpParams;
using fm1_msfa::Freqlut;
using fm1_msfa::Lfo;
using fm1_msfa::PitchEnv;
using fm1_msfa::Sin;

const int kNumVoices = 12;
const int kN = fm1_msfa::kN;            // 64 samples per msfa block
const int kLgN = fm1_msfa::kLgN;
const int kNumPatches = kBankSize + static_cast<int>(FM1_DX7_USER_SLOTS);

enum Param {
  P_PATCH, P_BRIGHTNESS, P_ENV_TIME, P_FEEDBACK, P_VOLUME,
  P_GLIDE, P_VOICE_MODE, P_GLIDE_MODE, P_TIME_MODE,
  P_COUNT
};

// Uids (API v2) are fixed: never renumber one. Patch is read per voice at
// note-on (LATCH), as Six-Op FM's. The four macros are read every block and
// each voice can take its own offset (POLY): Brightness and Feedback where
// the voice computes its operators, Env Time in the voice's own envelope
// clock, Volume in its gain.
const uint16_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Patch",      FM1_PARAM_ENUM,  0, kNumPatches - 1, 0, kPatchNames, 0,
    1, FM1_PARAM_LATCH | FM1_PARAM_MOD, FM1_UNIT_NONE, "Patch" },
  { "Brightness", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPoly, FM1_UNIT_NONE, "Bright" },
  { "Env Time",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPoly, FM1_UNIT_NONE, "EnvT" },
  { "Feedback",   FM1_PARAM_FLOAT, -7, 7, 0, NULL, 0, 4, kPoly, FM1_UNIT_NONE, "FB" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 5, kPoly, FM1_UNIT_NONE, "Vol" },
  // Glide and the voice modes (glide.h), on a page of their own, the last.
  { "Glide",      FM1_PARAM_FLOAT, glide::kMinMs, glide::kMaxMs, glide::kDefaultMs, NULL, 2,
    6, glide::kGlideFlags, FM1_UNIT_MS, "Glide" },
  { "Voice Mode", FM1_PARAM_ENUM, 0, glide::MODE_COUNT - 1, glide::MODE_POLY,
    glide::kModeNames, 2, 7, glide::kModeFlags, FM1_UNIT_NONE, "VMode" },
  { "Glide Mode", FM1_PARAM_ENUM, 0, glide::GLIDE_MODE_COUNT - 1, glide::GLIDE_OFF,
    glide::kGlideModeNames, 2, 8, glide::kModeFlags, FM1_UNIT_NONE, "GMode" },
  { "Time Mode",  FM1_PARAM_ENUM, 0, glide::TIME_MODE_COUNT - 1, glide::TIME_TIME,
    glide::kTimeModeNames, 2, 9, glide::kModeFlags, FM1_UNIT_NONE, "TMode" },
};

typedef NoteOffsets<P_BRIGHTNESS, P_GLIDE - P_BRIGHTNESS> Offsets;

// Bit k: operator k (msfa's order, the sixth first) writes the output in
// algorithm a, as msfa's FmCore algorithm table routes it (an output bus of
// 0). tests/test_engines_dx7.py checks this against the vendored table.
const uint8_t kCarriers[32] = {
  0x28, 0x28, 0x24, 0x24, 0x2A, 0x2A, 0x28, 0x28, 0x28, 0x24, 0x24, 0x28, 0x28, 0x28, 0x28, 0x20,
  0x20, 0x20, 0x26, 0x34, 0x36, 0x2E, 0x36, 0x3E, 0x3E, 0x34, 0x34, 0x29, 0x3A, 0x39, 0x3E, 0x3F,
};

// dx7note.cc's pitch modulation sensitivity table (file-local there).
const uint8_t kPitchModSens[8] = { 0, 10, 20, 33, 55, 92, 153, 255 };

// Amplitude modulation: the attenuation, in msfa's envelope units (2^24 =
// one doubling, 6.02 dB), at full depth (AMD 99, the LFO at the end of its
// swing) for AMS 0..3: 16 doublings (96 dB) at 3, and Dexed's ratios
// 4342338 / 2^24 and 7171437 / 2^24 of it at 1 and 2.
const int64_t kAmsDepth[4] = { 0, 4342338LL * 16, 7171437LL * 16, 16777216LL * 16 };

// An envelope level is kept within 0 .. 17 doublings above msfa's floor
// before Exp2::lookup.
const int32_t kLevelMax = 17 << 24;

// Brightness 0..1 moves the output level of every operator that is not a
// carrier by -24 .. +24 dB (four doublings), 0.5 playing the patch as it is.
const float kBrightnessQ24 = 2.0f * 4.0f * 16777216.0f;
// Env Time 0..1: the envelopes run 8 times faster at 0 and 8 times slower
// at 1 (2^(6 * (0.5 - t))); at 0.5, as programmed.
const float kEnvTimeQ24 = 6.0f * 16777216.0f;
// A semitone in msfa's log-frequency units (2^24 = an octave).
const float kSemitoneQ24 = 16777216.0f / 12.0f;

// A voice is freed once its key is up and, for 50 ms, every carrier's
// envelope has been under msfa's threshold with a release that ends there
// too (Quiet below). The envelope, not the output: a tremolo trough mutes
// the output while the release still has its course to run.
const float kSilentAfterRelease = 0.05f;

// The output: a voice's carriers sum to about 2^25 per carrier at full
// level; each voice is scaled by its Volume in Q16 and shifted by 18 into
// the mix, and the mix by 2^-23 / 4, so one carrier at full level and
// velocity is 0.25 at Volume 1 (0.175 at the default 0.7), which puts a
// typical voice of two or three carriers near the other engines' level.
const int kVoiceShift = 18;
const float kOutScale = 0.25f / 8388608.0f;

struct Voice {
  Env env[6];
  PitchEnv pitchenv;
  FmOpParams params[6];
  int32_t basepitch[6];       // msfa's osc_freq: log2 frequency, Q24
  int32_t key_pitch;          // the note's log2 frequency in basepitch, Q24
  int32_t level[6];           // the last envelope level of each operator
  int32_t pitch_level;        // and of the pitch envelope
  int32_t fb_buf[2];
  uint32_t env_clock;         // envelope steps owed, Q24 (the Env Time clock)
  uint32_t pitch_clock;
  int32_t gain_q16;           // the voice's gain at the end of its last block
  int32_t pmd;                // LFO pitch depth, (LPMD * 165) >> 6
  int32_t amd;                // LFO amplitude depth, (LAMD * 165) >> 6
  uint8_t pms;                // kPitchModSens[LPMS]
  uint8_t algorithm;          // 0..31
  uint8_t feedback;           // the patch's 0..7
  uint8_t ams[6];
  uint8_t ratio_ops;          // bit op: operator op follows the key (ratio mode)
  uint8_t transpose;          // the voice data's transpose (24 = none)
  bool tail;                  // a carrier's release ends above silence (L4)
  uint32_t silent_blocks;
  uint32_t age;
  uint8_t key;
  bool gate;
  bool active;
  Offsets note;
  glide::Slew glide;          // its glide (glide.h)
};

// The rate units of Lfo and PitchEnv are globals, shared by every instance:
// set by the first create, at its rate. 0 = not yet. (msfa's tables are
// const data, or the instance's own frequency table: Instance::Lut.)
uint32_t g_rate_hz = 0;

// The host's rate in whole hertz, as msfa's init takes it; 0 for a rate no
// instance accepts (NaN, negative or past 4 GHz), which SharedInit refuses.
uint32_t RateHz(float rate) {
  return rate >= 0.0f && rate < 4.0e9f ? static_cast<uint32_t>(rate + 0.5f) : 0u;
}

// Whether an instance at this rate keeps its own frequency table: at any
// rate but the one msfa_rom.cc's table is for.
bool OwnLut(const fm1_host_t *host) { return RateHz(host->sample_rate) != fm1_msfa::kFreqLutRateHz; }

// The lowest rate msfa's frequency table holds: Freqlut::init fills int32_t
// entries up to 2^45 / rate (an octave's top), which passes 2^31 - 1 at
// 16,384 Hz and below, and the pitches in an octave's last few percent
// come out wrong [verified: tests/test_engines_dx7.py].
const uint32_t kMinRateHz = 16385;

bool SharedInit(float rate) {
  if (!(rate >= kMinRateHz - 0.5f && rate <= 384000.0f)) return false;   // NaN fails too
  const uint32_t hz = RateHz(rate);
  if (g_rate_hz) return g_rate_hz == hz;
  Lfo::init(hz);
  PitchEnv::init(hz);
  g_rate_hz = hz;
  return true;
}

// float -> int32 for the Q24 conversions: one multiply and a truncation
// (nothing to fuse into a multiply-add), clamped.
int32_t ToQ24(float x, float scale) {
  const float y = x * scale;
  if (!(y > -2.0e9f)) return y == y ? -2000000000 : 0;
  if (y > 2.0e9f) return 2000000000;
  return static_cast<int32_t>(y);
}

int32_t Clamp32(int64_t x, int32_t lo, int32_t hi) {
  return x < lo ? lo : (x > hi ? hi : static_cast<int32_t>(x));
}

class Instance {
 public:
  // Called right after the instance is value-initialised (zeroed) in
  // Create, so every member starts at zero; Init sets the rest.
  void Init(const fm1_host_t *host) {
    const uint32_t hz = RateHz(host->sample_rate);
    own_lut_ = OwnLut(host);
    if (own_lut_) fm1_msfa::FillFreqLut(*Lut(), hz);
    env_rate_q24_ = static_cast<uint32_t>((static_cast<uint64_t>(44118u) << 24) / hz);
    silent_after_release_ =
        static_cast<uint32_t>(kSilentAfterRelease * static_cast<float>(hz) / kN) + 1u;
    for (int k = 0; k < kBankSize; ++k) {
      FromPacked(kBank[k], unpacked_voice_);
      Pitches(unpacked_voice_, pitch_[k]);
    }
    for (unsigned s = 0; s < FM1_DX7_USER_SLOTS; ++s) {
      for (int i = 0; i < kVoiceBytes; ++i) user_[s][i] = kInitVoice[i];
      Pitches(kInitVoice, pitch_[kBankSize + s]);
    }
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].active = voice_[i].gate = false;
      voice_[i].note.Clear();
      voice_[i].glide.Clear();
    }
    held_.Clear();
    glide_block_ms_ = glide::BlockMs(host->sample_rate, kN);
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(host->sample_rate, kN);
    lfo_patch_ = -1;
    unpacked_ = -1;
    bend_q24_ = 0;
    clock_ = 0;
    pending_ = 0;
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0) { NoteOff(key); return; }
    if (key > 127) key = 127;
    if (velocity > 127) velocity = 127;
    held_.Push(key);
    const glide::Plan<Voice> plan = glide::PlanNoteOn(voice_, kNumVoices, GlideConfig());
    if (plan.legato) {         // Legato over a held note: a new key, nothing restarts
      Retune(plan.mono, key);
      glide::StartFor(plan.mono, plan, key);
      return;
    }
    int index = static_cast<int>(value_[P_PATCH] + 0.5f);
    if (index < 0) index = 0;
    if (index >= kNumPatches) index = kNumPatches - 1;
    const uint8_t *p = Patch(index);
    Voice *v = plan.mono ? plan.mono : Allocate(key);
    // The patch's LFO, as msfa's synth sets it on a program change; then a
    // key-on restarts its delay (and its phase, with LFO key sync).
    if (lfo_patch_ != index) {
      lfo_.reset(reinterpret_cast<const char *>(p) + V_LFS);
      lfo_patch_ = index;
    }
    lfo_.keydown();
    Start(v, p, pitch_[index], key, velocity);
    v->glide.Begin();
    glide::StartFor(v, plan, key);
  }

  void NoteOff(uint8_t key) {
    if (key > 127) key = 127;  // as NoteOn clamps it, or the voice and held_ keep it
    held_.Remove(key);
    if (glide::ToMode(value_[P_VOICE_MODE]) != glide::MODE_POLY) ReturnToHeld(key);
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.gate || v.key != key) continue;
      v.gate = false;
      for (int op = 0; op < 6; ++op) v.env[op].keydown(false);
      v.pitchenv.keydown(false);
    }
  }

  void PitchBend(float semitones) { bend_q24_ = ToQ24(semitones, kSemitoneQ24); }

  void SetParam(uint16_t index, float value) {
    if (index >= P_COUNT) return;
    value = fm1_param_clamp(&kParams[index], value);
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
  }

  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  void Render(float *out_lr, uint32_t frames) {
    for (uint32_t f = 0; f < frames; ++f) {
      if (!pending_) {
        RenderBlock();
        pending_ = kN;
      }
      const float s = out_[kN - pending_];
      --pending_;
      out_lr[2 * f] = out_lr[2 * f + 1] = s;
    }
  }

  int LoadSysex(const uint8_t *data, size_t len, unsigned slot, fm1_dx7_sysex_result_t *res) {
    const int n = ParseSysex(data, len, slot, &Instance::Store, this, res);
    if (n > 0) {
      // A user slot's voice may have changed under the LFO's settings or
      // the unpacked cache; take them again at the next note.
      lfo_patch_ = -1;
      unpacked_ = -1;
    }
    return n;
  }

  void UserName(unsigned slot, char out[FM1_DX7_NAME_BYTES + 1]) const {
    if (slot >= FM1_DX7_USER_SLOTS) { out[0] = '\0'; return; }
    Name(user_[slot], out);
  }

  int GetUserVoice(unsigned slot, uint8_t vced[FM1_DX7_VCED_BYTES]) const {
    if (slot >= FM1_DX7_USER_SLOTS || !vced) return 0;
    for (unsigned i = 0; i < FM1_DX7_VCED_BYTES; ++i) vced[i] = user_[slot][i];
    return 1;
  }

  int SetUserVoice(unsigned slot, const uint8_t vced[FM1_DX7_VCED_BYTES]) {
    if (slot >= FM1_DX7_USER_SLOTS || !vced) return 0;
    uint8_t v[kVoiceBytes];
    FromVced(vced, v);
    Store(this, slot, v);
    lfo_patch_ = -1;   // as LoadSysex: the LFO and the unpacked cache again
    unpacked_ = -1;
    return 1;
  }

 private:
  static void Store(void *ctx, unsigned slot, const uint8_t v[kVoiceBytes]) {
    Instance *self = static_cast<Instance *>(ctx);
    for (int i = 0; i < kVoiceBytes; ++i) self->user_[slot][i] = v[i];
    Pitches(v, self->pitch_[kBankSize + slot]);
  }

  // Each operator's pitch less the key's (msfa's osc_freq at key 0, less
  // the key's own log frequency in ratio mode), so a note-on only adds the
  // key's: osc_freq is that sum in integers, so the result is osc_freq's to
  // the bit. Computed when the instance is made and when a slot is loaded,
  // since osc_freq takes a log in doubles (software on pi32v2) per operator.
  static void Pitches(const uint8_t *v, int32_t out[6]) {
    for (int op = 0; op < 6; ++op) {
      const uint8_t *o = v + op * kOpBytes;
      int32_t f = fm1_msfa::osc_freq(0, o[OP_MODE], o[OP_FC], o[OP_FF], o[OP_DET]);
      if (!o[OP_MODE]) f -= fm1_msfa::midinote_to_logfreq(0);
      out[op] = f;
    }
  }

  // The voice data of Patch value `index`: a built-in voice, unpacked into
  // a cache on first use, or a user slot.
  const uint8_t *Patch(int index) {
    if (index >= kBankSize) return user_[index - kBankSize];
    if (unpacked_ != index) {
      FromPacked(kBank[index], unpacked_voice_);
      unpacked_ = index;
    }
    return unpacked_voice_;
  }

  // What Voice Mode, Glide Mode and Time Mode say now (glide.h).
  glide::Config GlideConfig() const {
    return glide::Read(value_[P_VOICE_MODE], value_[P_GLIDE_MODE], value_[P_TIME_MODE]);
  }

  // Mono and Legato: letting go of the key the voice plays while older keys
  // are held moves it back to the newest of them, gliding, never restarting.
  void ReturnToHeld(uint8_t key) {
    uint8_t top = 0;
    const glide::Plan<Voice> plan =
        glide::PlanNoteOff(voice_, kNumVoices, held_, key, GlideConfig(), &top);
    if (!plan.mono) return;
    Retune(plan.mono, top);
    glide::StartFor(plan.mono, plan, top);
  }

  // A voice takes another key without restarting: its envelopes and the
  // LFO go on, and the operators that follow the key move to the new one,
  // to the bit what Start gives them (osc_freq is that sum in integers).
  // Keyboard level and rate scaling stay those of the note that started
  // the envelopes. A new note for its per-note offsets; the same velocity.
  static void Retune(Voice *v, uint8_t key) {
    int note = static_cast<int>(key) + static_cast<int>(v->transpose) - 24;
    note = note < 0 ? 0 : (note > 127 ? 127 : note);
    const int32_t key_pitch = fm1_msfa::midinote_to_logfreq(note);
    const int32_t delta = key_pitch - v->key_pitch;
    for (int op = 0; op < 6; ++op) {
      if ((v->ratio_ops >> op) & 1) v->basepitch[op] += delta;
    }
    v->key_pitch = key_pitch;
    v->key = key;
    v->note.Clear();
  }

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

  // A note-on, as msfa's Dx7Note::init sets one up, from voice data p and
  // its operators' pitches (Pitches). A voice that was silent starts from
  // phase 0 with its feedback cleared; a retriggered or stolen one keeps its
  // phases and its last gains, so its first block glides from where it was.
  void Start(Voice *v, const uint8_t *p, const int32_t *pitch, uint8_t key, uint8_t velocity) {
    using fm1_msfa::ScaleLevel;
    using fm1_msfa::ScaleRate;
    using fm1_msfa::ScaleVelocity;
    const bool fresh = !v->active;
    const uint8_t carriers = kCarriers[p[V_ALG] & 31];
    bool tail = false;
    uint8_t ratio_ops = 0;
    int note = static_cast<int>(key) + static_cast<int>(p[V_TRNSP]) - 24;
    note = note < 0 ? 0 : (note > 127 ? 127 : note);
    const int32_t key_pitch = fm1_msfa::midinote_to_logfreq(note);
    for (int op = 0; op < 6; ++op) {
      const uint8_t *o = p + op * kOpBytes;
      int rates[4], levels[4];
      for (int i = 0; i < 4; ++i) {
        rates[i] = o[OP_R1 + i];
        levels[i] = o[OP_L1 + i];
      }
      int outlevel = Env::scaleoutlevel(o[OP_OL]);
      outlevel += ScaleLevel(note, o[OP_BP], o[OP_LD], o[OP_RD], o[OP_LC], o[OP_RC]);
      outlevel = outlevel > 127 ? 127 : outlevel;
      outlevel <<= 5;
      outlevel += ScaleVelocity(velocity, o[OP_KVS]);
      outlevel = outlevel < 0 ? 0 : outlevel;
      v->env[op].init(rates, levels, outlevel, ScaleRate(note, o[OP_RS]));
      if ((carriers >> op) & 1) {
        // Where this carrier's release ends: Env::advance's target for
        // stage 3 (env.cc), from L4 and the output level.
        int release = ((Env::scaleoutlevel(levels[3]) >> 1) << 6) + outlevel - 4256;
        release = release < 16 ? 16 : release;
        if (!Silent(release << 16)) tail = true;
      }
      v->basepitch[op] = o[OP_MODE] ? pitch[op] : pitch[op] + key_pitch;   // osc_freq's
      if (!o[OP_MODE]) ratio_ops = static_cast<uint8_t>(ratio_ops | (1u << op));
      v->ams[op] = o[OP_AMS];
      v->level[op] = 0;
      if (fresh) {
        v->params[op].phase = 0;
        v->params[op].gain[0] = v->params[op].gain[1] = 0;
      }
    }
    int prates[4], plevels[4];
    for (int i = 0; i < 4; ++i) {
      prates[i] = p[V_PR1 + i];
      plevels[i] = p[V_PL1 + i];
    }
    v->pitchenv.set(prates, plevels);
    v->pitch_level = 0;
    v->key_pitch = key_pitch;
    v->ratio_ops = ratio_ops;
    v->transpose = p[V_TRNSP];
    v->algorithm = p[V_ALG];
    v->feedback = p[V_FB];
    v->pmd = (p[V_LPMD] * 165) >> 6;
    v->amd = (p[V_LAMD] * 165) >> 6;
    v->pms = kPitchModSens[p[V_LPMS] & 7];
    if (fresh) {
      v->fb_buf[0] = v->fb_buf[1] = 0;
      v->gain_q16 = -1;              // no ramp into the first block
    }
    // The clocks start a hair short of a step, so the note's first block
    // takes one whatever Env Time is, as msfa's does (the attack begins
    // and the pitch envelope stands at its start level from the note's
    // first sample); at one step a block that is the same clock as from 0.
    v->env_clock = v->pitch_clock = 0xFFFFFFu;
    v->tail = tail;
    v->silent_blocks = 0;
    v->key = key;
    v->age = ++clock_;
    v->gate = true;
    v->active = true;
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
  }

  // Whether an envelope level (msfa's, Q24 doublings) plays an operator
  // under FmCore's threshold.
  static bool Silent(int32_t level) {
    return Exp2::lookup(level - (14 << 24)) < kLevelThresh;
  }

  // A released voice that can only stay silent: every carrier's envelope,
  // before the tremolo (which only takes level away) and where its release
  // ends, under the threshold. (Brightness moves the modulators only.)
  static bool Quiet(const Voice &v) {
    if (v.tail) return false;
    const uint8_t carriers = kCarriers[v.algorithm & 31];
    for (int op = 0; op < 6; ++op) {
      if (((carriers >> op) & 1) && !Silent(v.level[op])) return false;
    }
    return true;
  }

  // Envelope steps this block on a Q24 clock running at `speed`.
  static uint32_t Tick(uint32_t *clock, uint32_t speed) {
    const uint32_t c = *clock + speed;
    *clock = c & 0xFFFFFFu;
    return c >> 24;
  }

  // The frequency table this instance reads: the const one at 44,118 Hz,
  // else its own, which lives right after it in the host's memory
  // (InstanceSize). Every instance has the same rate (SharedInit), so their
  // tables are the same; Freqlut::lookup's pointer is set to this one
  // before each block all the same, since an instance can be destroyed (on
  // the control task) while others play.
  int32_t (*Lut())[fm1_msfa::kFreqLutSize] {
    if (!own_lut_) {
      return const_cast<int32_t (*)[fm1_msfa::kFreqLutSize]>(&fm1_msfa::kFreqLut44118);
    }
    return reinterpret_cast<int32_t (*)[fm1_msfa::kFreqLutSize]>(
        reinterpret_cast<unsigned char *>(this) + sizeof(Instance));
  }

  void RenderBlock() {
    fm1_msfa::fm1_freqlut = Lut();               // what Freqlut::lookup reads
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this block's step of any ramp
    glide_step_ = glide::Step(glide_block_ms_, value_[P_GLIDE]);
    const int32_t lfo_val = lfo_.getsample();
    const int32_t lfo_delay = lfo_.getdelay();
    int32_t mix[kN];
    for (int i = 0; i < kN; ++i) mix[i] = 0;
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;
      RenderVoice(&v, lfo_val, lfo_delay);
      bool silent = true;
      for (int k = 0; k < kN; ++k) {
        if (vbuf_[k]) { silent = false; break; }
      }
      const float vol = v.note.Value(kParams, P_VOLUME, value_[P_VOLUME]);
      const int32_t g1 = static_cast<int32_t>(vol * 65536.0f);   // 0..65536
      const int32_t g0 = v.gain_q16 < 0 ? g1 : v.gain_q16;
      v.gain_q16 = g1;
      if (!silent) {
        const int32_t dg = g1 - g0;
        for (int k = 0; k < kN; ++k) {
          const int32_t g = g0 + ((dg * (k + 1)) >> kLgN);
          mix[k] += static_cast<int32_t>((static_cast<int64_t>(vbuf_[k]) * g) >> kVoiceShift);
        }
      }
      v.silent_blocks = (!v.gate && Quiet(v)) ? v.silent_blocks + 1 : 0;
      if (v.silent_blocks > silent_after_release_) {
        v.active = false;
        v.note.Clear();
      }
    }
    for (int k = 0; k < kN; ++k) out_[k] = static_cast<float>(mix[k]) * kOutScale;
  }

  // One msfa block of voice v into vbuf_, as Dx7Note::compute, plus the
  // amplitude modulation, the macros and the loops of algorithms 4 and 6.
  void RenderVoice(Voice *v, int32_t lfo_val, int32_t lfo_delay) {
    const float bright = v->note.Value(kParams, P_BRIGHTNESS, value_[P_BRIGHTNESS]);
    const float env_time = v->note.Value(kParams, P_ENV_TIME, value_[P_ENV_TIME]);
    const float fb_offset = v->note.Value(kParams, P_FEEDBACK, value_[P_FEEDBACK]);

    // The envelope clocks: Env Time as a speed, 2^(6 (0.5 - t)) in Q24;
    // the operators' also scaled to the rate (msfa's Env counts blocks),
    // the pitch envelope's not (PitchEnv scales to the rate itself).
    const uint32_t speed = static_cast<uint32_t>(Exp2::lookup(ToQ24(0.5f - env_time, kEnvTimeQ24)));
    const uint32_t env_speed =
        static_cast<uint32_t>((static_cast<uint64_t>(speed) * env_rate_q24_) >> 24);
    uint32_t env_steps = Tick(&v->env_clock, env_speed);
    uint32_t pitch_steps = Tick(&v->pitch_clock, speed);
    if (env_steps > 64) env_steps = 64;
    if (pitch_steps > 64) pitch_steps = 64;
    for (uint32_t s = 0; s < pitch_steps; ++s) v->pitch_level = v->pitchenv.getsample();

    // Pitch: the pitch envelope, the LFO (as Dx7Note::compute), the bend
    // and the note's own offset.
    int32_t pitchmod = v->pitch_level;
    const uint32_t pmd = static_cast<uint32_t>(v->pmd) * static_cast<uint32_t>(lfo_delay);   // Q32
    const int32_t senslfo = v->pms * (lfo_val - (1 << 23));
    pitchmod += static_cast<int32_t>((static_cast<int64_t>(pmd) * senslfo) >> 39);
    pitchmod += bend_q24_;
    if (v->note.has_pitch()) pitchmod += ToQ24(v->note.pitch, kSemitoneQ24);
    if (v->glide.active) pitchmod += ToQ24(v->glide.offset, kSemitoneQ24);
    v->glide.Next(glide_step_);

    // Amplitude modulation depth now, Q24 (0..1): AMD after the LFO's
    // delay, times how far the LFO is from its top.
    const int64_t amod = ((static_cast<int64_t>(v->amd) * lfo_delay) >> 8) *
                         ((1 << 24) - lfo_val) >> 24;
    const int32_t bright_q24 = ToQ24(bright - 0.5f, kBrightnessQ24);
    const uint8_t carriers = kCarriers[v->algorithm & 31];

    for (int op = 0; op < 6; ++op) {
      for (uint32_t s = 0; s < env_steps; ++s) v->level[op] = v->env[op].getsample();
      int64_t level = v->level[op];
      if (v->ams[op]) level -= (amod * kAmsDepth[v->ams[op] & 3]) >> 24;
      if (!((carriers >> op) & 1)) level += bright_q24;
      const int32_t lv = Clamp32(level, 0, kLevelMax);
      FmOpParams &q = v->params[op];
      q.gain[0] = q.gain[1];
      q.gain[1] = Exp2::lookup(lv - (14 << 24));
      q.freq = Freqlut::lookup(Clamp32(static_cast<int64_t>(v->basepitch[op]) + pitchmod, 0,
                                       (20 << 24) - 1));
    }

    int fb = v->feedback + Round(fb_offset);
    fb = fb < 0 ? 0 : (fb > 7 ? 7 : fb);
    const int fb_shift = fb ? 8 - fb : 16;
    for (int k = 0; k < kN; ++k) vbuf_[k] = 0;
    const int alg = v->algorithm & 31;
    if (fb && (alg == 3 || alg == 5)) {
      RenderWithLoop(&core_, v->params, alg, alg == 3 ? 3 : 2, fb_shift, v->fb_buf, vbuf_);
    } else {
      core_.compute(vbuf_, v->params, alg, v->fb_buf, fb_shift);
    }
  }

  // Nearest integer of a value within -7..7, without libm.
  static int Round(float x) {
    return x >= 0.0f ? static_cast<int>(x + 0.5f) : -static_cast<int>(0.5f - x);
  }

  FmCore core_;                   // msfa's algorithm runner (its buses are scratch)
  Lfo lfo_;                       // one LFO, as on the keyboards
  Voice voice_[kNumVoices];
  uint8_t user_[FM1_DX7_USER_SLOTS][kVoiceBytes];
  uint8_t unpacked_voice_[kVoiceBytes];   // the built-in voice last unpacked
  int32_t pitch_[kNumPatches][6];  // each slot's operator pitches less the key's (Pitches)
  int unpacked_;                  // its Patch value, -1 none
  int lfo_patch_;                 // the Patch value the LFO is set for, -1 none
  float value_[P_COUNT];          // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;         // 64-sample blocks in a ramp
  int32_t bend_q24_;
  uint32_t env_rate_q24_;         // 44,118 / rate, Q24
  uint32_t silent_after_release_; // in blocks
  uint32_t clock_;
  glide::Held held_;              // keys down, for Mono and Legato
  float glide_block_ms_;          // a 64-sample block at the host's rate, in ms
  glide::Step glide_step_;        // this block's glide step (glide.h)
  int32_t vbuf_[kN];              // one voice's block
  float out_[kN];                 // the current block
  uint32_t pending_;              // samples of out_ not yet delivered
  bool own_lut_;                  // a frequency table of its own follows (Lut)
};

// At a rate other than 44,118 Hz the instance's frequency table follows it
// (Instance::Lut); sizeof(Instance) is a multiple of its alignment, which is
// at least an int32_t's.
size_t InstanceSize(const fm1_host_t *host) {
  return sizeof(Instance) + (OwnLut(host) ? sizeof(int32_t) * fm1_msfa::kFreqLutSize : 0u);
}

void *Create(void *mem, const fm1_host_t *host) {
  if (!SharedInit(host->sample_rate)) return NULL;
  // Value-initialised: Instance has no user-provided constructor, so this
  // zeroes every member (msfa's Lfo keeps a random state and a phase that
  // nothing else sets) before Init.
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
void SetNote(void *s, uint8_t k, uint16_t i, float o) {
  static_cast<Instance *>(s)->SetParamNote(k, i, o);
}

}  // namespace dx7
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_dx7 = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "dx7", "FM6",
  "Six-operator FM on msfa, the FM core of Google's music-synthesizer-for-"
  "android (Google, Apache-2.0); named after Felucca's FM6 engine (hugelton), "
  "both borrowed with thanks; reads DX7 voice data (a Yamaha trademark; not "
  "affiliated); built-in voices our own",
  fm1::dx7::kParams, fm1::dx7::P_COUNT, fm1::dx7::kNumVoices,
  fm1::dx7::InstanceSize, fm1::dx7::Create, fm1::dx7::Destroy,
  fm1::dx7::NoteOn, fm1::dx7::NoteOff, fm1::dx7::Bend,
  fm1::dx7::Set, fm1::dx7::Render,
  fm1::dx7::SetNote,
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
  NULL,                     // API v4: no get_param, the host keeps its values
};

extern "C" int fm1_dx7_load_sysex(void *self, const uint8_t *data, size_t len, unsigned slot,
                                  fm1_dx7_sysex_result_t *res) {
  return static_cast<fm1::dx7::Instance *>(self)->LoadSysex(data, len, slot, res);
}

extern "C" void fm1_dx7_user_name(const void *self, unsigned slot,
                                  char out[FM1_DX7_NAME_BYTES + 1]) {
  static_cast<const fm1::dx7::Instance *>(self)->UserName(slot, out);
}

extern "C" int fm1_dx7_get_user_voice(const void *self, unsigned slot,
                                      uint8_t vced[FM1_DX7_VCED_BYTES]) {
  return static_cast<const fm1::dx7::Instance *>(self)->GetUserVoice(slot, vced);
}

extern "C" int fm1_dx7_set_user_voice(void *self, unsigned slot,
                                      const uint8_t vced[FM1_DX7_VCED_BYTES]) {
  return static_cast<fm1::dx7::Instance *>(self)->SetUserVoice(slot, vced);
}

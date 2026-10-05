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
//     release.
//
// Rate: msfa runs at the host's rate, in its own 64-sample blocks (the
// envelopes and the LFO step once per block), rendered as the host's calls
// need them, so the output does not depend on the host's block size; note
// and parameter events land on the next 64-sample block. Freqlut, Lfo and
// PitchEnv scale their tables to the rate. msfa's Env counts blocks (its
// rates are set for 44.1 kHz), so the envelope clock here is scaled by
// 44,118 / rate: exactly one envelope step per block at the FM-1's 44,118 Hz,
// as msfa itself runs, and the same times at any other rate. msfa's tables
// are shared by every instance and filled by the first create; a later
// create at another rate is refused (as the Schwung shim refuses one).
//
// MIT licence (this file). Not affiliated with or endorsed by Yamaha; the
// engine's name is our own (docs/11 §7).

#include "fm1_engine.h"
#include "fm1_dx7.h"
#include "fm1_smooth.h"
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

enum Param { P_PATCH, P_BRIGHTNESS, P_ENV_TIME, P_FEEDBACK, P_VOLUME, P_COUNT };

// Uids (API v2) are fixed: never renumber one. Patch is read per voice at
// note-on (LATCH), as Six-Op FM's. The four macros are read every block and
// each voice can take its own offset (POLY): Brightness and Feedback where
// the voice computes its operators, Env Time in the voice's own envelope
// clock, Volume in its gain.
const uint8_t kPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const fm1_param_t kParams[P_COUNT] = {
  { "Patch",      FM1_PARAM_ENUM,  0, kNumPatches - 1, 0, kPatchNames, 0,
    1, FM1_PARAM_LATCH | FM1_PARAM_MOD, FM1_UNIT_NONE, "Patch" },
  { "Brightness", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPoly, FM1_UNIT_NONE, "Bright" },
  { "Env Time",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPoly, FM1_UNIT_NONE, "EnvT" },
  { "Feedback",   FM1_PARAM_FLOAT, -7, 7, 0, NULL, 0, 4, kPoly, FM1_UNIT_NONE, "FB" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 1, 5, kPoly, FM1_UNIT_NONE, "Vol" },
};

typedef NoteOffsets<P_BRIGHTNESS, P_COUNT - P_BRIGHTNESS> Offsets;

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

// A voice is freed once its key is up and its output has been exactly
// silent (every carrier below msfa's threshold) for 50 ms.
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
  uint32_t silent_blocks;
  uint32_t age;
  uint8_t key;
  bool gate;
  bool active;
  Offsets note;
};

// msfa's tables (Sin, Exp2, Freqlut) and the rate units of Lfo and PitchEnv
// are globals, shared by every instance: filled by the first create, at its
// rate. 0 = not yet.
uint32_t g_rate_hz = 0;

bool SharedInit(float rate) {
  if (!(rate >= 8000.0f && rate <= 384000.0f)) return false;
  const uint32_t hz = static_cast<uint32_t>(rate + 0.5f);
  if (g_rate_hz) return g_rate_hz == hz;
  Sin::init();
  Exp2::init();
  Freqlut::init(hz);
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
    const uint32_t hz = static_cast<uint32_t>(host->sample_rate + 0.5f);
    env_rate_q24_ = static_cast<uint32_t>((static_cast<uint64_t>(44118u) << 24) / hz);
    silent_after_release_ =
        static_cast<uint32_t>(kSilentAfterRelease * static_cast<float>(hz) / kN) + 1u;
    for (unsigned s = 0; s < FM1_DX7_USER_SLOTS; ++s) {
      for (int i = 0; i < kVoiceBytes; ++i) user_[s][i] = kInitVoice[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {
      voice_[i].active = voice_[i].gate = false;
      voice_[i].note.Clear();
    }
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
    int index = static_cast<int>(value_[P_PATCH] + 0.5f);
    if (index < 0) index = 0;
    if (index >= kNumPatches) index = kNumPatches - 1;
    const uint8_t *p = Patch(index);
    Voice *v = Allocate(key);
    // The patch's LFO, as msfa's synth sets it on a program change; then a
    // key-on restarts its delay (and its phase, with LFO key sync).
    if (lfo_patch_ != index) {
      lfo_.reset(reinterpret_cast<const char *>(p) + V_LFS);
      lfo_patch_ = index;
    }
    lfo_.keydown();
    Start(v, p, key, velocity);
  }

  void NoteOff(uint8_t key) {
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

 private:
  static void Store(void *ctx, unsigned slot, const uint8_t v[kVoiceBytes]) {
    Instance *self = static_cast<Instance *>(ctx);
    for (int i = 0; i < kVoiceBytes; ++i) self->user_[slot][i] = v[i];
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

  // A note-on, as msfa's Dx7Note::init sets one up, from voice data p. A
  // voice that was silent starts from phase 0 with its feedback cleared; a
  // retriggered or stolen one keeps its phases and its last gains, so its
  // first block glides from where it was.
  void Start(Voice *v, const uint8_t *p, uint8_t key, uint8_t velocity) {
    using fm1_msfa::ScaleLevel;
    using fm1_msfa::ScaleRate;
    using fm1_msfa::ScaleVelocity;
    using fm1_msfa::osc_freq;
    const bool fresh = !v->active;
    int note = static_cast<int>(key) + static_cast<int>(p[V_TRNSP]) - 24;
    note = note < 0 ? 0 : (note > 127 ? 127 : note);
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
      v->basepitch[op] = osc_freq(note, o[OP_MODE], o[OP_FC], o[OP_FF], o[OP_DET]);
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
    v->algorithm = p[V_ALG];
    v->feedback = p[V_FB];
    v->pmd = (p[V_LPMD] * 165) >> 6;
    v->amd = (p[V_LAMD] * 165) >> 6;
    v->pms = kPitchModSens[p[V_LPMS] & 7];
    if (fresh) {
      v->fb_buf[0] = v->fb_buf[1] = 0;
      v->gain_q16 = -1;              // no ramp into the first block
    }
    v->env_clock = v->pitch_clock = 0;
    v->silent_blocks = 0;
    v->key = key;
    v->age = ++clock_;
    v->gate = true;
    v->active = true;
    v->note.Clear();   // a new note, a retrigger or a steal starts at no offset
  }

  // Envelope steps this block on a Q24 clock running at `speed`.
  static uint32_t Tick(uint32_t *clock, uint32_t speed) {
    const uint32_t c = *clock + speed;
    *clock = c & 0xFFFFFFu;
    return c >> 24;
  }

  void RenderBlock() {
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this block's step of any ramp
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
      v.silent_blocks = (silent && !v.gate) ? v.silent_blocks + 1 : 0;
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
  int unpacked_;                  // its Patch value, -1 none
  int lfo_patch_;                 // the Patch value the LFO is set for, -1 none
  float value_[P_COUNT];          // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;         // 64-sample blocks in a ramp
  int32_t bend_q24_;
  uint32_t env_rate_q24_;         // 44,118 / rate, Q24
  uint32_t silent_after_release_; // in blocks
  uint32_t clock_;
  int32_t vbuf_[kN];              // one voice's block
  float out_[kN];                 // the current block
  uint32_t pending_;              // samples of out_ not yet delivered
};

size_t InstanceSize(const fm1_host_t *) { return sizeof(Instance); }

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
  "android (Google, Apache-2.0); reads DX7 voice data (a Yamaha trademark; "
  "not affiliated); built-in voices our own",
  fm1::dx7::kParams, fm1::dx7::P_COUNT, fm1::dx7::kNumVoices,
  fm1::dx7::InstanceSize, fm1::dx7::Create, fm1::dx7::Destroy,
  fm1::dx7::NoteOn, fm1::dx7::NoteOff, fm1::dx7::Bend,
  fm1::dx7::Set, fm1::dx7::Render,
  fm1::dx7::SetNote,
};

extern "C" int fm1_dx7_load_sysex(void *self, const uint8_t *data, size_t len, unsigned slot,
                                  fm1_dx7_sysex_result_t *res) {
  return static_cast<fm1::dx7::Instance *>(self)->LoadSysex(data, len, slot, res);
}

extern "C" void fm1_dx7_user_name(const void *self, unsigned slot,
                                  char out[FM1_DX7_NAME_BYTES + 1]) {
  static_cast<const fm1::dx7::Instance *>(self)->UserName(slot, out);
}

// crater_kit.cc -- "Crater Kit", a 16-pad kit after the TR-808: the 808 kit
// of fm1-x0x (Charles Vestal, GPL-3.0-only), vendored with small local
// changes in third_party/fm1-x0x/ (UPSTREAM.md), behind engine API v3. It
// links GPL code, so it is built only while the GPL switch is on
// (FM1_GPL_MODS, engines/Makefile; mk/x0x-crater.mk) and listed GPL in the
// licence table (src/registry.cc).
//
// What fm1-x0x's 808 is (third_party/fm1-x0x/dsp/drum808.h has the detail):
// a C99, float, libm-free port, statement for statement, of 8W8 by
// athousanddetails (GPL-3.0): sixteen sounds on eleven tracks with the
// machine's own switches, fifteen of them circuit models built from the
// TR-808's service notes and the published analyses of Werner, Abel and
// Smith (the kick's bridged-T in an op-amp loop, so Decay is loop gain; the
// snare's two shells and noise; the toms and congas; the clap's bursts; one
// bank of six Schmitt squares shared by the cowbell, the hats and the
// cymbal; the cymbal's three paths), and the rim shot a transcription of
// sc808 by Yoshinosuke Horiuchi and Sam Aaron (MIT). Every instance is
// self-contained.
//
// What this file adds, and how it plays (engines/README.md, "Crater Kit"):
//   - Pads. Notes 36-51 play the sixteen sounds (crater_kit.h's table;
//     pad_first_note and pad_count, so a host can lay them on its keys);
//     other notes and every note-off are ignored: a hit rings out, as on
//     the machine. A conga plays its tom's channel switched to conga, so a
//     tom and its conga never sound together; the claves and the maracas
//     have voices of their own beside the rim shot and the clap. A closed
//     hat cuts the open one (Choke), and a sound struck again is struck
//     again in its own circuit, as on the machine.
//   - Velocity: 88 is the 808's normal hit and 127 its accent, as fm1-x0x
//     plays MIDI (crater_kit.h, VelocityOf); Accent is 8W8's velocity depth.
//   - The rate: fm1-x0x's 808 is built for 44,100 Hz, and the engine runs it
//     unchanged at a host rate near it, 44,000-44,200 Hz (the FM-1's 44,118
//     is 0.7 cents sharp); other hosts are refused (crater_kit.h).
//   - A grid of 16 samples. The vendored kit's output depends on where its
//     render calls split (it works in 32-sample pieces of each call, its
//     tails end and its metal bank stops at their ends), so it renders whole
//     16-sample chunks, counted from create, and the host's frames are handed
//     out of the last chunk. A hit, a bend or a parameter lands on the next
//     chunk (0.36 ms at 44,118 Hz), so the output is the same at any host
//     block size and any split of a block.
//   - Parameters. Pad chooses which pad the pad's knobs edit, as on Drums
//     and Sophie; each of the sixteen keeps its own Tune, Decay, Level,
//     Tone, Snap, Drive and Dist. Accent, Choke and Volume are the kit's.
//     Each pad knob reaches 8W8's own pot for that sound, a float between
//     its integers (drum808_set_value, a local change), and every knob but
//     Tune, Drive and Dist is relative to the sound as 8W8 voices it: the
//     middle, 0.5, is 8W8's default pot for that sound, the left end its pot
//     0 and the right its pot 127, linear on either side. Tune is in
//     semitones on every pad, 12 either way about 8W8's default (whose own
//     range is 2 semitones either way on the toms and congas and 12
//     elsewhere; the law runs on past the toms' ends here, a local change).
//     Drive is 8W8's 0..10 as 0..1, clean at 0. Tone and Snap reach the
//     sounds that have such a pot: Tone the kick's and the snare's tone,
//     Snap the kick's attack, the snare's snappy and the maracas' attack; on
//     the other pads they do nothing.
//   - Flags. 8W8 reads a sound's pots when it is struck, but for its Level
//     and Drive, which it reads all along: so Tune, Decay, Tone, Snap,
//     Accent and Choke are LATCH (and MOD); Level, Drive and Volume SMOOTH
//     and MOD, ramped in 16-sample steps while the kit sounds (a pad's ramp
//     goes on when Pad moves on). Dist would click mid-hit, so a change
//     waits for that pad's next hit (LATCH and MOD: a route is rounded), or
//     applies at once while the kit is silent. Pad is the edit focus,
//     lockable without MOD, as Drums'. No per-note offsets.
//   - Pitch bend moves the hits struck while it is held: 8W8 tunes a sound
//     when it is struck. Tune and the bend together reach 12 semitones
//     either way, where the rim shot's filters and pulse stay in range.
//   - Volume outside the vendored kit: its own kit level stays at 8W8's
//     default, and Volume scales its output by (Volume / 0.7)^2 times
//     kOutScale, so the default is the dry bus at kOutScale and 1 is 6.2 dB
//     louder.
//
// No allocation and no libm: the vendored kit has its own maths
// (fastmath.h), so every build computes the same bits.
//
// MIT licence (this file); the program it is linked into is GPL-3.0 while
// the vendored kit is in it.

#include "fm1_engine.h"
#include "fm1_gpl_mods.h"   // FM1_GPL_MODS, generated by engines/Makefile
#include "fm1_smooth.h"

#if !FM1_GPL_MODS
#error "crater_kit.cc links GPL code: it is built only with FM1_GPL_MODS=1 (engines/mk/x0x-crater.mk)"
#endif

extern "C" {
#include "dsp/drum808.h"
}

#include <new>

#include "crater_kit.h"

namespace fm1 {
namespace crater {

// The output scale at Volume 0.7, set so the snare and the hats sit within
// 1 dB of Drums' (by RMS, struck at velocity 100), with 8W8's own balance
// between the sounds kept: its kick is then about 8 dB under Drums' long Deep
// kick, which Level can raise by 6. The loudest sound by peak, the cowbell
// accented, peaks near 0.75 of full scale; a groove of kick, snare and hats
// near 0.45 [measured: fm1-render and fm1-crater-oracle --pads, 2026-10-06;
// tests/test_engine_crater_kit.py].
const float kOutScale = 0.7f;

enum Param {
  P_PAD, P_TUNE, P_DECAY, P_LEVEL,        // page 1: the pad
  P_TONE, P_SNAP, P_DRIVE, P_DIST,        // page 2: its sound
  P_ACCENT, P_CHOKE, P_VOLUME,            // page 3: the kit
  P_COUNT
};

// The per-pad parameters, P_TUNE .. P_DIST, kept for each pad.
const int kPadParams = P_DIST - P_TUNE + 1;
inline int PadIndex(int param) { return param - P_TUNE; }

const char *const kPadNames[kNumPads] = {
  "1 Kick", "2 Rim Shot", "3 Snare", "4 Clap", "5 Claves", "6 Low Tom", "7 Closed HH",
  "8 Low Conga", "9 Maracas", "10 Mid Tom", "11 Open HH", "12 Mid Conga", "13 High Tom",
  "14 Cymbal", "15 Hi Conga", "16 Cowbell",
};
// 8W8's seven distortion characters (its README): its diode rounding, an
// asymmetric soft clip, a parallel saturation, a fuzz, a biased cubic, a
// wavefolder, and bits and rate falling together.
const char *const kDistNames[7] = { "Diode", "Clip", "Sat", "Fuzz", "Cubic", "Fold", "Crush" };
// 8W8's kit Choke: off, a closed hat cuts the open one, or each cuts the other.
const char *const kChokeNames[3] = { "Off", "Closed>Open", "Both" };

const uint16_t kCont = FM1_PARAM_CONTINUOUS;
const uint16_t kLatch = FM1_PARAM_LATCH | FM1_PARAM_MOD;
// API v4: Pad is the focus; each pad keeps its own Tune .. Dist (PER_FOCUS),
// which get_param reads from any pad, so a saved kit holds all sixteen
// (notes/2026-10-06-state-files.md ST7).
const uint16_t kPadCont = kCont | FM1_PARAM_PER_FOCUS;
const uint16_t kPadLatch = kLatch | FM1_PARAM_PER_FOCUS;

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid.
const fm1_param_t kParams[P_COUNT] = {
  { "Pad",    FM1_PARAM_ENUM,  0, kNumPads - 1, 0, kPadNames, 0, 1, FM1_PARAM_FOCUS, FM1_UNIT_NONE, "Pad" },
  { "Tune",   FM1_PARAM_FLOAT, -12, 12, 0, NULL, 0, 2, kPadLatch, FM1_UNIT_SEMI, "Tune" },
  { "Decay",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPadLatch, FM1_UNIT_NONE, "Decay" },
  { "Level",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 4, kPadCont, FM1_UNIT_NONE, "Level" },
  { "Tone",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, kPadLatch, FM1_UNIT_NONE, "Tone" },
  { "Snap",   FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 6, kPadLatch, FM1_UNIT_NONE, "Snap" },
  { "Drive",  FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 1, 7, kPadCont, FM1_UNIT_NONE, "Drive" },
  { "Dist",   FM1_PARAM_ENUM,  0, 6, 0, kDistNames, 1, 8, kPadLatch, FM1_UNIT_NONE, "Dist" },
  { "Accent", FM1_PARAM_FLOAT, 0, 100, 100, NULL, 2, 9, kLatch, FM1_UNIT_PCT, "Accent" },
  { "Choke",  FM1_PARAM_ENUM,  0, 2, 1, kChokeNames, 2, 10, kLatch, FM1_UNIT_NONE, "Choke" },
  { "Volume", FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 2, 11, kCont, FM1_UNIT_NONE, "Vol" },
};

const float kVolumeRef = 0.7f;        // Volume at which the output is the dry bus x kOutScale

inline bool IsTomOrConga(int s) {
  return s == D8S_LT || s == D8S_MT || s == D8S_HT || s == D8S_LC || s == D8S_MC || s == D8S_HC;
}

// The pot (0..127) for a relative knob u (0..1) about 8W8's default pot d:
// d at 0.5, 0 at 0 and 127 at 1, linear on either side.
inline float About(float d, float u) {
  return u < 0.5f ? d * (2.0f * u) : d + (127.0f - d) * (2.0f * u - 1.0f);
}

// Which of 8W8's pots Tone and Snap reach on a sound, or -1.
inline int ToneSlot(int s) { return s == D8S_BD ? D8P_X1 : (s == D8S_SD ? D8P_X2 : -1); }
inline int SnapSlot(int s) {
  return s == D8S_BD ? D8P_X2 : ((s == D8S_SD || s == D8S_MA) ? D8P_X1 : -1);
}

// The ramped per-pad parameters.
enum { R_LEVEL, R_DRIVE, kRamps };

struct Instance {
  drum808_t unit;                     // fm1-x0x's 808, first
  float value[kNumPads][kPadParams];  // set_param's values, per pad
  float def_pot[kNumPads][D8P_NUM];   // 8W8's default pots, read from the unit at create
  float cur[kNumPads][kRamps];        // Level and Drive as the unit plays them (ramped)
  fm1_smooth_t ramp[kNumPads][kRamps];
  float applied[kNumPads][kRamps];    // the pots the unit was last given for them
  float applied_tune[kNumPads];       // the Tune pot it was last given
  float applied_dist[kNumPads];       // the Dist it plays
  float accent, choke;                // the kit's LATCH values
  float volume, vol_cur;              // Volume, set and ramped
  fm1_smooth_t vol_ramp;
  float bend;                         // semitones
  float rate;
  float buf[kChunk];
  float rev[kChunk], dly[kChunk];     // the unit's send buses, unused (its sends stay at 0)
  uint32_t pos;                       // next sample of buf to hand out; kChunk: empty
  uint32_t steps;                     // ramp length in chunks
  int focus;                          // the pad Pad edits
  uint8_t pad[12];

  bool Init(const fm1_host_t *host) {
    const float r = host ? host->sample_rate : 0.0f;
    if (!(r >= kMinRate && r <= kMaxRate)) return false;
    rate = r;
    drum808_init(&unit);
    for (int p = 0; p < kNumPads; ++p) {
      const int s = kPads[p].sound;
      for (int k = 0; k < D8P_NUM; ++k) def_pot[p][k] = unit.potx[s][k];
      for (int k = 0; k < kPadParams; ++k) value[p][k] = kParams[P_TUNE + k].def;
      for (int k = 0; k < kRamps; ++k) {
        cur[p][k] = value[p][PadIndex(k == R_LEVEL ? P_LEVEL : P_DRIVE)];
        applied[p][k] = -1.0f;        // below every pot: the first Apply sets it
      }
      fm1_smooth_init(ramp[p], cur[p], kRamps);
      applied_tune[p] = unit.potx[s][D8P_TUNE];
      applied_dist[p] = unit.potx[s][D8P_DIST];
      ApplyRamped(p);
    }
    accent = kParams[P_ACCENT].def;
    choke = kParams[P_CHOKE].def;
    volume = vol_cur = kParams[P_VOLUME].def;
    fm1_smooth_init(&vol_ramp, &vol_cur, 1);
    ApplyKit();
    bend = 0.0f;
    for (uint32_t k = 0; k < kChunk; ++k) buf[k] = rev[k] = dly[k] = 0.0f;
    pos = kChunk;
    steps = fm1_smooth_steps(rate, kChunk);
    focus = 0;
    for (int k = 0; k < 12; ++k) pad[k] = 0;
    return true;
  }

  bool Silent() const { return !drum808_active(&unit); }

  float Value(int p, int param) const { return value[p][PadIndex(param)]; }

  // The pot a relative knob gives on pad p's sound, slot `slot`.
  float Pot(int p, int slot, float u) const { return About(def_pot[p][slot], u); }

  // Level and Drive: the unit reads them all along, so they follow the ramps.
  void ApplyRamped(int p) {
    const int s = kPads[p].sound;
    const float level = Pot(p, D8P_LEVEL, cur[p][R_LEVEL]);
    const float drive = cur[p][R_DRIVE] * 127.0f;
    if (level != applied[p][R_LEVEL]) {
      applied[p][R_LEVEL] = level;
      drum808_set_value(&unit, s, D8P_LEVEL, level);
    }
    if (drive != applied[p][R_DRIVE]) {
      applied[p][R_DRIVE] = drive;
      drum808_set_value(&unit, s, D8P_DRIVE, drive);
    }
  }

  // Tune, with the bend: semitones about 8W8's default pot, on its own law
  // (12 semitones a half-turn of the pot, 2 on the toms and congas), the two
  // together at most 12 either way (drum808_set_value's range).
  void ApplyTune(int p) {
    const int s = kPads[p].sound;
    float semis = Value(p, P_TUNE) + bend;
    semis = semis < -12.0f ? -12.0f : (semis > 12.0f ? 12.0f : semis);
    const float per = IsTomOrConga(s) ? 127.0f / 4.0f : 127.0f / 24.0f;
    const float x = semis == 0.0f ? def_pot[p][D8P_TUNE] : def_pot[p][D8P_TUNE] + semis * per;
    if (x == applied_tune[p]) return;
    applied_tune[p] = x;
    drum808_set_value(&unit, s, D8P_TUNE, x);
  }

  // Decay, Tone and Snap: read when the sound is struck.
  void ApplyStruck(int p) {
    const int s = kPads[p].sound;
    const int tone = ToneSlot(s), snap = SnapSlot(s);
    drum808_set_value(&unit, s, D8P_DECAY, Pot(p, D8P_DECAY, Value(p, P_DECAY)));
    if (tone >= 0) drum808_set_value(&unit, s, tone, Pot(p, tone, Value(p, P_TONE)));
    if (snap >= 0) drum808_set_value(&unit, s, snap, Pot(p, snap, Value(p, P_SNAP)));
  }

  void ApplyDist(int p) {
    const float d = Value(p, P_DIST);
    if (d == applied_dist[p]) return;
    applied_dist[p] = d;
    drum808_set_value(&unit, kPads[p].sound, D8P_DIST, d);
  }

  // Accent and Choke: 8W8's kit pots (velocity depth, the hats' choke).
  void ApplyKit() {
    drum808_set(&unit, D8_KIT, 1, static_cast<int>(accent * 1.27f + 0.5f));
    drum808_set(&unit, D8_KIT, 2, static_cast<int>(choke));
  }

  void Chunk() {
    for (int p = 0; p < kNumPads; ++p) {
      if (!fm1_smooth_moving(ramp[p], kRamps)) continue;
      fm1_smooth_tick(ramp[p], cur[p], kRamps);
      ApplyRamped(p);
    }
    if (fm1_smooth_moving(&vol_ramp, 1)) fm1_smooth_tick(&vol_ramp, &vol_cur, 1);
    for (uint32_t k = 0; k < kChunk; ++k) buf[k] = 0.0f;
    if (!Silent()) {                  // a silent kit renders nothing: skip it, exactly
      for (uint32_t k = 0; k < kChunk; ++k) rev[k] = dly[k] = 0.0f;
      drum808_render(&unit, buf, rev, dly, static_cast<int>(kChunk));
      const float r = vol_cur / kVolumeRef;
      const float gain = r * r * kOutScale;
      for (uint32_t k = 0; k < kChunk; ++k) buf[k] = buf[k] * gain;
    }
    pos = 0;
  }

  void Render(float *out, uint32_t frames) {
    uint32_t done = 0;
    while (done < frames) {
      if (pos == kChunk) Chunk();
      uint32_t n = kChunk - pos;
      if (n > frames - done) n = frames - done;
      for (uint32_t k = 0; k < n; ++k) {
        const float v = buf[pos + k];
        out[2 * (done + k)] = v;
        out[2 * (done + k) + 1] = v;
      }
      pos += n;
      done += n;
    }
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (key < kFirstNote || key >= kFirstNote + kNumPads || velocity == 0) return;
    const int p = key - kFirstNote;
    ApplyTune(p);                     // the bend in force when it is struck
    ApplyDist(p);                     // a Dist that waited for this hit
    unit.sw[kPads[p].track] = kPads[p].sw;
    drum808_trigger(&unit, kPads[p].track, VelocityOf(velocity));
  }

  void PitchBend(float semitones) {
    bend = semitones == semitones ? semitones : 0.0f;
  }

  void SetParam(uint16_t index, float v) {
    if (index >= P_COUNT) return;
    const fm1_param_t &prm = kParams[index];
    v = fm1_param_clamp(&prm, v);
    if (prm.type == FM1_PARAM_ENUM) v = static_cast<float>(static_cast<int>(v + 0.5f));
    switch (index) {
      case P_PAD:
        focus = static_cast<int>(v);
        return;
      case P_ACCENT:
      case P_CHOKE:
        if (index == P_ACCENT) accent = v;
        else choke = v;
        ApplyKit();
        return;
      case P_VOLUME:
        if (v == volume) return;
        volume = v;
        fm1_smooth_set(&vol_ramp, &vol_cur, v, Silent() ? 0u : steps);
        return;
      default:
        break;
    }
    const int p = focus;
    if (v == value[p][PadIndex(index)]) return;
    value[p][PadIndex(index)] = v;
    switch (index) {
      case P_TUNE: ApplyTune(p); break;
      case P_DIST: if (Silent()) ApplyDist(p); break;
      case P_LEVEL:
      case P_DRIVE: {
        const int r = index == P_LEVEL ? R_LEVEL : R_DRIVE;
        const bool jump = Silent();
        fm1_smooth_set(&ramp[p][r], &cur[p][r], v, jump ? 0u : steps);
        if (jump) ApplyRamped(p);
        break;
      }
      default: ApplyStruck(p); break;   // Decay, Tone, Snap
    }
  }

  // API v4: what set_param left; a PER_FOCUS parameter's for pad
  // `pad_focus` (FM1_FOCUS_CURRENT, or past the last pad: the focused one's).
  float GetParam(uint16_t index, uint8_t pad_focus) const {
    if (index >= P_COUNT) return 0.0f;
    if (index == P_PAD) return static_cast<float>(focus);
    if (index == P_ACCENT) return accent;
    if (index == P_CHOKE) return choke;
    if (index == P_VOLUME) return volume;
    return value[pad_focus < kNumPads ? pad_focus : focus][PadIndex(index)];
  }
};

size_t InstanceSize(const fm1_host_t *) { return (sizeof(Instance) + 15u) & ~static_cast<size_t>(15u); }

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
void NoteOff(void *, uint8_t) {}      // one-shots: a hit rings out
void Bend(void *s, float st) { static_cast<Instance *>(s)->PitchBend(st); }
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->SetParam(i, v); }
float Get(const void *s, uint16_t i, uint8_t focus) {
  return static_cast<const Instance *>(s)->GetParam(i, focus);
}
void Render(void *s, float *out, uint32_t n) { static_cast<Instance *>(s)->Render(out, n); }

}  // namespace crater
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_crater = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "crater", "Crater Kit",
  "A kit after the TR-808: fm1-x0x's 808 by Charles Vestal (GPL-3.0), ported from 8W8 by "
  "athousanddetails (GPL-3.0): circuit models after the TR-808 service notes and Werner, Abel "
  "and Smith; the rim shot after sc808 by Yoshinosuke Horiuchi and Sam Aaron (MIT)",
  fm1::crater::kParams, fm1::crater::P_COUNT, 13,   // its thirteen circuits
  fm1::crater::InstanceSize, fm1::crater::Create, fm1::crater::Destroy,
  fm1::crater::NoteOn, fm1::crater::NoteOff, fm1::crater::Bend,
  fm1::crater::Set, fm1::crater::Render,
  NULL,                     // no per-note offsets
  0, NULL,                  // API v3: no effect extension
  fm1::crater::kFirstNote, fm1::crater::kNumPads,   // a pad kit: notes 36-51
  fm1::crater::Get,         // API v4: every pad's values read back
};

// For the oracle (engines/test/crater_oracle.cc): the vendored kit inside an
// instance, to copy and drive beside it.
extern "C" const drum808_t *fm1_crater_unit(const void *self) {
  return &static_cast<const fm1::crater::Instance *>(self)->unit;
}

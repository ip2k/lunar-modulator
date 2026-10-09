// comet_kit.cc -- "Comet Kit", a 16-pad kit after the TR-909: the 909 kit of
// fm1-x0x (Charles Vestal, GPL-3.0-only), vendored with small local changes
// in third_party/fm1-x0x/ (UPSTREAM.md), behind engine API v3. It links GPL
// code, so it is built only while the GPL switch is on (FM1_GPL_MODS,
// engines/Makefile; mk/fm1-x0x.mk) and listed GPL in the licence table
// (src/registry.cc).
//
// What fm1-x0x's kit is (third_party/fm1-x0x/dsp/drum909.h has the detail):
// a port of 9W9 (athousanddetails' 909 for Schwung, GPL-3.0, grown out of
// ER-99 by Matthew Cieplak, GPL-3.0), line for line: eleven voices, the kick,
// snare, three toms, rim shot and clap modelled on the 909's circuits, the
// closed and open hi-hat, crash and ride played from ER-99's recordings;
// every voice with a drive of seven types; the kit's accent and velocity
// depth. Float, no libm (fastmath.h), no allocation; an idle voice costs
// nothing. 9W9's and X0X's send effects and master stage are not taken: our
// inserts and master effects do that job.
//
// What this file adds, and how it plays (engines/README.md, "Comet Kit"):
//   - Pads. Notes 36-51 play pads 1-16 (pad_first_note and pad_count, so a
//     host lays them on its keys); other notes, and every note-off, are
//     ignored: a hit rings for its decay, as on the machine. Eleven voices
//     on sixteen pads (comet_kit.h, kPadVoice): the second snare, two more
//     toms and the pedal hat strike the snare's, a tom's or the closed hat's
//     voice with a voicing of their own. A voice struck again is struck in
//     place, and the closed and pedal hats choke the open one, as on the
//     machine. Velocity is the unit's (vel / 127), under Accent and
//     Velocity.
//   - The rate: the host's own, 40-96 kHz (the vendored kit reads the
//     instance's rate where upstream reads 44,100, and reads its 44.1 kHz
//     cymbals at their own pitch; at 44.1 kHz it computes upstream's
//     samples). Hosts outside that are refused.
//   - A grid of 16 samples. The vendored kit's output depends on where its
//     render calls split (its envelopes re-anchor at each call), so it
//     renders whole 16-sample chunks, counted from create, and the host's
//     frames are handed out of the last chunk. A hit or a parameter lands on
//     the next chunk (0.36 ms at 44,118 Hz), so the output is the same at any
//     host block size and any split of a block. A chunk is the control block
//     of the SMOOTH ramps.
//   - The knobs. Pad chooses which pad the per-pad knobs edit, as on Drums
//     and Sophie; each pad keeps its own Tune, Decay, Level, Tone, Snap,
//     Sweep, Drive and Drive Type. Each is one of 9W9's panel pots (0-127)
//     on that pad's voice, relative to the pad's voicing, so one default
//     fits all sixteen pads and a fresh kit shows true values on every pad:
//     Tune, Decay, Level, Tone and Snap at 0.5 are the voicing's pot, 0 and 1
//     the pot's ends, linearly on either side; Sweep and Drive at 0 are the
//     voicing's pot, 1 the pot's top. A pot between two of 9W9's integer
//     positions is read between them (drum909_set_value, a local change),
//     so a knob moves smoothly. Kit, Accent, Velocity and Volume are the
//     whole kit's. The voicings: Classic is 9W9's panel at its defaults, pad
//     for pad (its kit is X0X's power-on sound before X0X's own mix); Big
//     Beat is X0X's factory voicing (a shorter, driven, quieter kick, a
//     quieter open hat). The second pads' voicings are ours, set by
//     measurement and not yet by ear.
//   - Flags. The per-pad FLOATs are SMOOTH and MOD: a change to a pad
//     ramps in that pad's own values over 2.5 ms (7 chunks at 44,118 Hz)
//     while the pad sounds, and reaches the voice while the pad is the one
//     its voice last struck; otherwise it waits for the pad's next hit. 9W9
//     reads some pots continuously (the drives, the snare's wires, the
//     kick's click, the rim's and clap's tune and level, the cymbals' pitch)
//     and the rest at a hit. Drive Type and Kit are read when a pad is
//     struck (LATCH, and MOD: a route is rounded). Accent and Velocity are
//     read at a hit (LATCH). Volume ramps while any voice sounds. Pad is the
//     edit focus, lockable without MOD, as Drums' and Sophie's.
//   - Level. Volume scales the kit's output by kOutGain (Volume / 0.7)^2, so
//     the default kick struck at full velocity peaks near -7.6 dBFS, as
//     Drums' does near -8; the kit's balance is 9W9's.
//
// No per-note offsets and no pitch bend: the 909 has neither, and its voices
// are one per drum (set_param_note is NULL; a bend is taken and ignored, as
// a note-off is). No allocation and
// no libm: the vendored kit has its own maths (fastmath.h), and every build
// computes the same bits.
//
// MIT licence (this file); the program it is linked into is GPL-3.0 while
// the vendored kit is in it.

#include "fm1_engine.h"
#include "fm1_gpl_mods.h"   // FM1_GPL_MODS, generated by engines/Makefile
#include "fm1_smooth.h"

#if !FM1_GPL_MODS
#error "comet_kit.cc links GPL code: it is built only with FM1_GPL_MODS=1 (engines/mk/fm1-x0x.mk)"
#endif

#include <new>

#include "comet_kit.h"

namespace fm1 {
namespace comet_kit {

// ---- parameters -------------------------------------------------------------------------

// The pads, as Drums labels them (General MIDI's drum keys 36-51).
const char *const kPadNames[kNumPads] = {
  "1 Kick", "2 Rim", "3 Snare", "4 Clap", "5 Snare 2", "6 Low Tom",
  "7 Closed HH", "8 Floor Tom", "9 Pedal HH", "10 Mid Tom", "11 Open HH",
  "12 Low-Mid", "13 High-Mid", "14 Crash", "15 High Tom", "16 Ride",
};
// 9W9's seven distortion types, in its order: Diode (the 909's own diode
// rounding), Clip (asymmetric soft clip), SAT, BFZ (a fuzz), PDIST (a biased
// cubic), Fold, Crush.
const int kDistTypes = 7;
const char *const kDistNames[kDistTypes] = {
  "Diode", "Clip", "Saturate", "Fuzz", "Crunch", "Fold", "Crush",
};
const int kNumKits = 2;
const char *const kKitNames[kNumKits] = { "Classic", "Big Beat" };

// New parameters go at the end, so existing indices keep their meaning.
enum Param {
  P_PAD, P_TUNE, P_DECAY, P_LEVEL,             // page 1: the pad
  P_TONE, P_SNAP, P_SWEEP, P_DRIVE,            // page 2: its sound
  P_DRVTYPE, P_ACCENT, P_VELOCITY, P_VOLUME,   // page 3: its drive type, and the kit's
  P_KIT,                                       // page 4: the kit's voicings
  P_COUNT
};
typedef char slots_match[P_TUNE + S_DECAY == P_DECAY && P_TUNE + S_LEVEL == P_LEVEL &&
                         P_TUNE + S_TONE == P_TONE && P_TUNE + S_SNAP == P_SNAP &&
                         P_TUNE + S_SWEEP == P_SWEEP && P_TUNE + S_DRIVE == P_DRIVE &&
                         P_TUNE + S_COUNT == P_DRVTYPE ? 1 : -1];

// The kit's Accent at 9W9's default pot, 42: its LIN 1..4 at 42 / 127, as
// the vendored kit computes it.
const float kAccentDef = 1.0f + 3.0f * (42.0f / 127.0f);

// Uids (API v2) are fixed: never renumber one, and give a new parameter the
// next free uid.
// API v4: Pad is the focus; each pad keeps its own Tune .. Drive and Drive
// Type (PER_FOCUS), which get_param reads from any pad, so a saved kit holds
// all sixteen (notes/2026-10-06-state-files.md ST7).
const uint16_t kPadFloat = FM1_PARAM_CONTINUOUS | FM1_PARAM_PER_FOCUS;
const uint16_t kLatch = FM1_PARAM_LATCH | FM1_PARAM_MOD;
const fm1_param_t kParams[P_COUNT] = {
  { "Pad",        FM1_PARAM_ENUM,  0, kNumPads - 1, 0, kPadNames, 0, 1, FM1_PARAM_FOCUS, FM1_UNIT_NONE, "Pad" },
  { "Tune",       FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 2, kPadFloat, FM1_UNIT_NONE, "Tune" },
  { "Decay",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kPadFloat, FM1_UNIT_NONE, "Decay" },
  { "Level",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 4, kPadFloat, FM1_UNIT_NONE, "Level" },
  { "Tone",       FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, kPadFloat, FM1_UNIT_NONE, "Tone" },
  { "Snap",       FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 6, kPadFloat, FM1_UNIT_NONE, "Snap" },
  { "Sweep",      FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 1, 7, kPadFloat, FM1_UNIT_NONE, "Sweep" },
  { "Drive",      FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 1, 8, kPadFloat, FM1_UNIT_NONE, "Drive" },
  { "Drive Type", FM1_PARAM_ENUM,  0, kDistTypes - 1, 0, kDistNames, 2, 9, kLatch | FM1_PARAM_PER_FOCUS,
    FM1_UNIT_NONE, "DrvTyp" },
  { "Accent",     FM1_PARAM_FLOAT, 1, 4, kAccentDef, NULL, 2, 10, kLatch, FM1_UNIT_NONE, "Accent" },
  { "Velocity",   FM1_PARAM_FLOAT, 0, 100, 100, NULL, 2, 11, kLatch, FM1_UNIT_PCT, "Veloc" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 2, 12, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Vol" },
  { "Kit",        FM1_PARAM_ENUM,  0, kNumKits - 1, 0, kKitNames, 3, 13, kLatch, FM1_UNIT_NONE, "Kit" },
};

// ---- voicings ---------------------------------------------------------------------------

// Where a knob slot sits on a voice: the index of the 9W9 pot it moves
// (drum909_param), by the pot's name; -1 where the voice has none. 9W9's
// Tail (the clap's) is our Decay, Pitch (the kick's, with P.Dpth) our Tone,
// Attack (the kick's click, the toms' stick) and Snappy (the snare's wires)
// our Snap, P.Dpth our Sweep; its Rev and Dly sends are not taken.
int SlotOf(const char *name) {
  struct Name { const char *pot; int slot; };
  static const Name kNames[] = {
    { "Tune", S_TUNE }, { "Decay", S_DECAY }, { "Tail", S_DECAY }, { "Level", S_LEVEL },
    { "Tone", S_TONE }, { "Pitch", S_TONE }, { "Attack", S_SNAP }, { "Snappy", S_SNAP },
    { "P.Dpth", S_SWEEP }, { "Drive", S_DRIVE }, { "Dist", S_COUNT },
  };
  for (unsigned k = 0; k < sizeof(kNames) / sizeof(kNames[0]); ++k) {
    const char *a = name, *b = kNames[k].pot;
    while (*a && *a == *b) { ++a; ++b; }
    if (*a == *b) return kNames[k].slot;
  }
  return -1;
}

// A voicing differs from 9W9's panel defaults only where this table says:
// the pot a slot of a pad sits at, in one kit (kAllKits: every kit).
const uint8_t kAllKits = 0xFF;
struct Override {
  uint8_t kit, pad, slot, pot;
};
const Override kOverrides[] = {
  // The second pads, ours (every kit). 40 Snare 2: the snare 2 semitones
  // up (205 to 229 Hz), its wires longer (Tone 1.2 to 1.9 s) and louder
  // (Snappy 0.50 to 0.76). 43: the low tom 3 semitones up (68 to 81 Hz).
  // 44 Pedal HH: the closed hat's decay 109 to 159 ms. 47: the mid tom 2
  // up (102 to 114 Hz). 48: the high tom 2 down (132 to 117 Hz). So the six
  // tom pads rise with their keys, inside 9W9's three ranges.
  { kAllKits, 4, S_TUNE, 80 }, { kAllKits, 4, S_TONE, 90 }, { kAllKits, 4, S_SNAP, 96 },
  { kAllKits, 7, S_TUNE, 104 },
  { kAllKits, 8, S_DECAY, 100 },
  { kAllKits, 11, S_TUNE, 101 },
  { kAllKits, 12, S_TUNE, 19 },
  // Big Beat: X0X's factory voicing (fm1-x0x, app/engine.c,
  // engine_sound_defaults): the kick's Level 61, Decay 80 and Drive 30, the
  // open hat's Level 60.
  { 1, 0, S_LEVEL, 61 }, { 1, 0, S_DECAY, 80 }, { 1, 0, S_DRIVE, 30 },
  { 1, 10, S_LEVEL, 60 },
};

// ---- the instance -----------------------------------------------------------------------

// The pot (0..127, a float) for knob value u about the voicing's pot `at`:
// 0.5 is `at`, 0 and 1 the pot's ends, linearly on either side.
inline float About(float at, float u) {
  return u < 0.5f ? at * (2.0f * u) : at + (127.0f - at) * (2.0f * u - 1.0f);
}
// ...for Sweep and Drive: 0 is `at`, 1 the pot's top.
inline float Added(float at, float u) { return at + (127.0f - at) * u; }

// A kit-level value's pot, snapped onto an integer within a thousandth of
// one, so a default reaches the unit as 9W9's integer pot does.
inline float SnapPot(float x) {
  const float n = static_cast<float>(static_cast<int>(x + 0.5f));
  const float d = x - n;
  return d < 1e-3f && d > -1e-3f ? n : x;
}

struct PadState {
  float value[S_COUNT];               // Tune .. Drive as the voice reads them (ramped)
  fm1_smooth_t ramp[S_COUNT];
  uint8_t dist;                       // Drive Type (LATCH: read at the pad's hit)
  uint8_t hit_kit;                    // voicing and Drive Type for the current hit
  uint8_t hit_dist;
  uint8_t pad;
};

struct Instance {
  drum909_t unit;                     // fm1-x0x's kit, first: 16-byte aligned
  PadState pads[kNumPads];
  float applied[DR_NUM][DR_MAX_PARAMS];   // the pot each of the unit's voice pots was last given
  int8_t slot_pot[DR_NUM][S_COUNT + 1];   // the 9W9 pot a slot moves (S_COUNT: Dist), or -1
  uint8_t voicing[kNumKits][kNumPads][S_COUNT + 1];   // each pad's pots, per kit
  int8_t voice_pad[DR_NUM];           // the pad a voice last struck: whose values it plays
  float kit_value[P_COUNT];           // Accent, Velocity, Volume (P_*), ramped where SMOOTH
  fm1_smooth_t kit_ramp[P_COUNT];
  float gain;                         // the chunk's output gain
  float rate;
  float dry[kChunk];
  float send[kChunk];                 // the unit's two send buses: 0 sends, never written
  float buf[kChunk];
  uint32_t pos;                       // next sample of buf to hand out; kChunk: empty
  uint32_t steps;                     // ramp length in chunks
  uint32_t ramping;                   // bit p: pad p ramps; bit kNumPads: the kit's Volume
  int focus;                          // Pad
  int kit;                            // Kit

  bool Init(const fm1_host_t *host) {
    const float r = host ? host->sample_rate : 0.0f;
    if (!(r >= kMinRate && r <= kMaxRate)) return false;
    rate = r;
    drum909_init_rate(&unit, rate);
    for (int v = 0; v < DR_NUM; ++v) {
      for (int s = 0; s <= S_COUNT; ++s) slot_pot[v][s] = -1;
      for (int i = 0; i < DR_MAX_PARAMS; ++i) applied[v][i] = -1.0f;   // the first Apply sets all
      for (int i = 0; i < drum909_nparams(v); ++i) {
        const int s = SlotOf(drum909_param(v, i)->name);
        if (s >= 0) slot_pot[v][s] = static_cast<int8_t>(i);
      }
      voice_pad[v] = -1;
    }
    for (int k = 0; k < kNumKits; ++k) {
      for (int p = 0; p < kNumPads; ++p) {
        const int v = kPadVoice[p];
        for (int s = 0; s <= S_COUNT; ++s) {
          const int i = slot_pot[v][s];
          voicing[k][p][s] = i < 0 ? 0 : drum909_param(v, i)->def;
        }
      }
    }
    for (unsigned o = 0; o < sizeof(kOverrides) / sizeof(kOverrides[0]); ++o) {
      const Override &ov = kOverrides[o];
      for (int k = 0; k < kNumKits; ++k) {
        if (ov.kit == kAllKits || ov.kit == k) voicing[k][ov.pad][ov.slot] = ov.pot;
      }
    }
    for (int p = 0; p < kNumPads; ++p) {
      PadState &pad = pads[p];
      for (int s = 0; s < S_COUNT; ++s) pad.value[s] = kParams[P_TUNE + s].def;
      fm1_smooth_init(pad.ramp, pad.value, S_COUNT);
      pad.dist = 0;
      pad.hit_kit = pad.hit_dist = pad.pad = 0;
    }
    for (int i = 0; i < P_COUNT; ++i) kit_value[i] = kParams[i].def;
    fm1_smooth_init(kit_ramp, kit_value, P_COUNT);
    focus = 0;
    kit = 0;
    steps = fm1_smooth_steps(rate, kChunk);
    ramping = 0;
    for (uint32_t k = 0; k < kChunk; ++k) dry[k] = send[k] = buf[k] = 0.0f;
    pos = kChunk;
    // Every voice starts on its first pad's voicing, and the kit on its
    // Accent and Velocity: 9W9's panel at its defaults, as fm1-x0x applies
    // it at power-on.
    for (int p = kNumPads - 1; p >= 0; --p) voice_pad[kPadVoice[p]] = static_cast<int8_t>(p);
    for (int v = 0; v < DR_NUM; ++v) Apply(voice_pad[v]);
    SetKit(P_ACCENT, kit_value[P_ACCENT]);
    SetKit(P_VELOCITY, kit_value[P_VELOCITY]);
    Gain();
    return true;
  }

  // Whether 909 voice v is sounding (its countdown runs).
  bool VoiceActive(int v) const {
    if (v <= DR_SD) return unit.bt[v].mute > 0;
    if (v <= DR_HT) return unit.tom[v - DR_LT].mute > 0;
    if (v == DR_RS) return unit.rim.mute > 0;
    if (v == DR_CP) return unit.clap.mute > 0;
    const d9_smp_t &s = unit.smp[v - DR_CH];
    return s.mute > 0 && s.playing;
  }

  // Whether pad p sounds: its voice sounds, last struck by p.
  bool Sounding(int p) const {
    const int v = kPadVoice[p];
    return voice_pad[v] == p && VoiceActive(v);
  }

  // Pad p's values onto its voice's pots, those that changed.
  void Apply(int p) {
    const int v = kPadVoice[p];
    const PadState &pad = pads[p];
    const uint8_t *at = voicing[pad.hit_kit][p];
    for (int s = 0; s <= S_COUNT; ++s) {
      const int i = slot_pot[v][s];
      if (i < 0) continue;
      float x;
      if (s == S_COUNT) x = static_cast<float>(pad.hit_dist);
      else if (s == S_SWEEP || s == S_DRIVE) x = Added(static_cast<float>(at[s]), pad.value[s]);
      else x = About(static_cast<float>(at[s]), pad.value[s]);
      if (x == applied[v][i]) continue;
      applied[v][i] = x;
      drum909_set_value(&unit, v, i, x);
    }
  }

  // Accent or Velocity onto the unit's kit pots (read at a hit).
  void SetKit(int index, float value) {
    if (index == P_ACCENT) drum909_set_value(&unit, DR_KIT, 0, SnapPot((value - 1.0f) * (127.0f / 3.0f)));
    else drum909_set_value(&unit, DR_KIT, 1, SnapPot(value * (127.0f / 100.0f)));
  }

  void Gain() {
    const float r = kit_value[P_VOLUME] / 0.7f;
    gain = kOutGain * (r * r);
  }

  void Chunk() {
    if (ramping) {
      uint32_t still = 0;
      for (int p = 0; p < kNumPads; ++p) {
        if (!(ramping & (1u << p))) continue;
        if (fm1_smooth_tick(pads[p].ramp, pads[p].value, S_COUNT)) still |= 1u << p;
        if (voice_pad[kPadVoice[p]] == p) Apply(p);
      }
      if (ramping & (1u << kNumPads)) {
        if (fm1_smooth_tick(&kit_ramp[P_VOLUME], &kit_value[P_VOLUME], 1)) still |= 1u << kNumPads;
        Gain();
      }
      ramping = still;
    }
    for (uint32_t k = 0; k < kChunk; ++k) dry[k] = 0.0f;
    drum909_render(&unit, dry, send, send, static_cast<int>(kChunk));
    for (uint32_t k = 0; k < kChunk; ++k) buf[k] = dry[k] * gain;
    // The kick's pitch-sweep offset decays geometrically for as long as the
    // kick sounds, into subnormal floats after about 1.2 s (the one float of
    // the unit's state that does: fm1-comet-oracle --state), which some FPUs
    // compute slowly. Below 1e-20 Hz it no longer moves a bit of the
    // frequency it is added to (the kick's base, 21 Hz or more), so setting
    // it to 0 there leaves every sample as it was.
    float &df = unit.bt[DR_BD].bd_df;
    if (df < 1e-20f && df > -1e-20f) df = 0.0f;
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
    if (velocity == 0 || key < kFirstNote || key >= kFirstNote + kNumPads) return;
    const int p = key - kFirstNote;
    const int v = kPadVoice[p];
    voice_pad[v] = static_cast<int8_t>(p);
    pads[p].hit_kit = static_cast<uint8_t>(kit);
    pads[p].hit_dist = pads[p].dist;
    Apply(p);                         // the pad's values, its voicing in this Kit, its Drive Type
    drum909_trigger(&unit, v, static_cast<float>(velocity > 127 ? 127 : velocity) * (1.0f / 127.0f));
  }

  void SetParam(uint16_t index, float value) {
    if (index >= P_COUNT) return;
    const fm1_param_t &prm = kParams[index];
    value = fm1_param_clamp(&prm, value);
    if (prm.type == FM1_PARAM_ENUM) value = static_cast<float>(static_cast<int>(value + 0.5f));
    if (index == P_PAD) {
      focus = static_cast<int>(value);
    } else if (index >= P_TUNE && index <= P_DRIVE) {
      PadState &pad = pads[focus];
      const int s = index - P_TUNE;
      const bool sounding = Sounding(focus);
      fm1_smooth_set(&pad.ramp[s], &pad.value[s], value, sounding ? steps : 0u);
      if (pad.ramp[s].left) ramping |= 1u << focus;
      else if (voice_pad[kPadVoice[focus]] == focus) Apply(focus);   // reaches the next chunk
    } else if (index == P_DRVTYPE) {
      pads[focus].dist = static_cast<uint8_t>(value);
    } else if (index == P_KIT) {
      kit = static_cast<int>(value);
    } else if (index == P_VOLUME) {
      fm1_smooth_set(&kit_ramp[P_VOLUME], &kit_value[P_VOLUME], value,
                     drum909_active(&unit) ? steps : 0u);
      if (kit_ramp[P_VOLUME].left) ramping |= 1u << kNumPads;
      else Gain();
    } else {                          // Accent, Velocity: read at a hit
      kit_value[index] = value;
      SetKit(index, value);
    }
  }

  // API v4: what set_param left, never a ramp's step; a PER_FOCUS
  // parameter's for pad `pad_focus` (FM1_FOCUS_CURRENT, or past the last
  // pad: the focused one's).
  float GetParam(uint16_t index, uint8_t pad_focus) const {
    if (index >= P_COUNT) return 0.0f;
    const PadState &pad = pads[pad_focus < kNumPads ? pad_focus : focus];
    if (index == P_PAD) return static_cast<float>(focus);
    if (index >= P_TUNE && index <= P_DRIVE) return pad.ramp[index - P_TUNE].target;
    if (index == P_DRVTYPE) return static_cast<float>(pad.dist);
    if (index == P_KIT) return static_cast<float>(kit);
    if (index == P_VOLUME) return kit_ramp[P_VOLUME].target;
    return kit_value[index];          // Accent, Velocity
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
void NoteOff(void *, uint8_t) { }     // a hit rings out for its decay
void Bend(void *, float) { }          // the 909 has none: taken and ignored
void Set(void *s, uint16_t i, float v) { static_cast<Instance *>(s)->SetParam(i, v); }
float Get(const void *s, uint16_t i, uint8_t focus) {
  return static_cast<const Instance *>(s)->GetParam(i, focus);
}
void Render(void *s, float *out, uint32_t n) { static_cast<Instance *>(s)->Render(out, n); }

}  // namespace comet_kit
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_comet_kit = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "comet", "Comet Kit",
  "A kit after the TR-909: fm1-x0x's 909 by Charles Vestal (GPL-3.0), ported from 9W9 "
  "by athousanddetails (GPL-3.0), which grew out of ER-99 by Matthew Cieplak (GPL-3.0); "
  "hi-hat, crash and ride recordings from ER-99 (GPL-3.0)",
  fm1::comet_kit::kParams, fm1::comet_kit::P_COUNT, DR_NUM,
  fm1::comet_kit::InstanceSize, fm1::comet_kit::Create, fm1::comet_kit::Destroy,
  fm1::comet_kit::NoteOn, fm1::comet_kit::NoteOff, fm1::comet_kit::Bend,
  fm1::comet_kit::Set, fm1::comet_kit::Render,
  NULL,                     // no per-note offsets
  0, NULL,                  // API v3: no effect extension
  // A pad kit: notes 36-51 play pads 1-16 (engines/README.md, "Pad kits").
  fm1::comet_kit::kFirstNote, fm1::comet_kit::kNumPads,
  fm1::comet_kit::Get,      // API v4: every pad's values read back
};

// For the oracle (engines/test/comet_oracle.cc): the vendored unit inside an
// instance, to copy and drive beside it.
extern "C" const drum909_t *fm1_comet_kit_unit(const void *self) {
  return &static_cast<const fm1::comet_kit::Instance *>(self)->unit;
}

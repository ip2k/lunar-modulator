// felucca_shim.cc -- "Drawbar", "Trio" and "Phase Bend": three engines of
// Felucca, open firmware for the M-VAVE FM-1 by Leo Kuroshita (@kurogedelic),
// Hügelton Instruments (GPL-3.0-only), behind engine API v3. Felucca's
// WHEEL, TRIO and PHASE are vendored unmodified in third_party/felucca/
// (UPSTREAM.md) and reached through src/felucca_bridge.c (felucca_bridge.h).
// They link GPL code, so they are built only while the GPL switch is on
// (FM1_GPL_MODS, engines/Makefile; mk/felucca.mk) and listed GPL in the
// licence table (src/registry.cc).
//
// What the three are (engines/README.md, "The Felucca engines", has more):
//   - Drawbar (WHEEL): a tonewheel-style organ, Felucca's own design: nine
//     sine partials at the drawbar footages from 16 registrations with Sub,
//     Body and Top offsets, percussion, key click, drive and a two-rotor
//     rotary folded into the partials' gains and pitches.
//   - Trio (TRIO): three oscillators (triangle, saw, pulse, pitched noise and
//     the AND-combined waves of 8-bit home-computer sound chips) with ring
//     modulation and hard sync, into a 12 dB multimode filter with a gritty
//     band-pass and a drifting cutoff. Felucca's own design.
//   - Phase Bend (PHASE): phase distortion, a port of the oscillator of
//     CrispyZebra, the author's own: eight waves, three of them windowed
//     resonant waves, a second wave on alternate cycles, a detuned second
//     line mixed or ring-modulated, a sub.
//
// What this file adds, in our own code:
//   - The control block. Felucca runs its engines in blocks of 32 samples
//     with its envelopes and modulation once a block. Here too: whole
//     32-sample blocks counted from create, the host's frames handed out of
//     the last one, so a note, a bend or a parameter lands on the next block
//     (0.73 ms) and the output is the same at any host block size or split.
//   - The rate. Felucca's tables are for 44,100 Hz, and on an FM-1, whose
//     audio runs at about 44,118 Hz, it plays them as they are: 0.7 cent
//     sharp, its times 0.04 % short. These engines do the same: they run at
//     the host's rate on Felucca's tables, and refuse a host outside
//     44,100 Hz +/- 0.25 % (the FM-1's 44,118 and the simulator's 44,118 or
//     44,100 are inside), where they would be audibly out of tune.
//   - Voices: eight, Felucca's. A key struck while it sounds is struck again
//     in its own voice; otherwise the next free voice in turn (Felucca's
//     ROTATE, so tails ring out); with none free, the oldest released one,
//     else the oldest held one that is not the lowest held key. A voice
//     struck again or taken starts again where it is, as Felucca's do: the
//     attack from the level it is at, the phases kept.
//   - The envelope and the modulation an engine reads are Felucca's laws,
//     run in the bridge: Attack, Decay, Sustain and Release take the 128
//     steps of Felucca's time curve (1 ms to 10 s); velocity scales the
//     level; a velocity above 110 opens the filter (and Phase Bend's bend)
//     with the envelope, as Felucca's accent does.
//   - Parameters in units (ms, Hz, %, semitones), mapped onto Felucca's
//     integer knobs: a percentage to 0..127, times to the step of the time
//     curve nearest to them on the LOG law (so a 7-bit lock is exactly
//     Felucca's step), Trio's Cutoff and PW and Phase Bend's DCW in steps of
//     1/256 of a knob step, through the modulation inputs Felucca's envelope
//     and LFO use, so they sweep without stepping.
//   - Flags. Lists that would click if changed under a note (Trio's Wave and
//     Mode, Phase Bend's Wave, Wave 2 and Line) are read at note-on: LATCH
//     and MOD (a route is rounded). Drawbar's Drawbars, Perc and Rotor
//     are read every block and glide (each partial's gain ramps over the
//     block, the rotor eases between speeds): MOD, as the effects' clean
//     switches. Every FLOAT is SMOOTH and MOD; a SMOOTH change ramps over
//     2.5 ms in control blocks while a voice sounds (fm1_smooth.h). The
//     FLOATs an engine reads per voice are POLY (per-note offsets,
//     note_offsets.h): the envelope and Volume everywhere, and the knobs
//     Trio and Phase Bend read in a voice's render; Drawbar's bars, click
//     and drive are the part's, read once a block, so they are not.
//   - Phase Bend takes glide's four parameters (glide.h: Glide, Voice Mode,
//     Glide Mode, Time Mode) on a page of their own, its last, as the
//     pitched engines do; Drawbar and Trio do not (their tables are full).
//   - The output. Felucca adds its voices at 24,000 a full-scale voice and
//     mixes a part at its default level, -4 dB, into a limiter; Volume 0.7
//     is that level less 12 dB, the headroom our engines leave, and Volume
//     scales it by (Volume / 0.7)^2.
//
// No allocation and no libm (fm1_math.h's log2), and Felucca's integer DSP,
// so every build computes the same bits.
//
// MIT licence (this file); the program it is linked into is GPL-3.0 while
// the bridge and Felucca's code are in it.

#include "fm1_engine.h"
#include "fm1_gpl_mods.h"   // FM1_GPL_MODS, generated by engines/Makefile
#include "fm1_math.h"
#include "fm1_smooth.h"
#include "glide.h"
#include "note_offsets.h"

#if !FM1_GPL_MODS
#error "felucca_shim.cc links GPL code: it is built only with FM1_GPL_MODS=1 (engines/mk/felucca.mk)"
#endif

#include "felucca_bridge.h"

#include <cstring>
#include <new>

namespace fm1 {
namespace felucca {

const int kMaxParams = 16;
const int kVoices = FEL_VOICES;
const uint32_t kBlock = FEL_CTL;
// The rates the engines accept: Felucca's 44,100 Hz +/- 0.25 % (top of file).
const float kMinRate = 43990.0f;
const float kMaxRate = 44210.0f;
// The output at Volume 0.7: Felucca's part at its default level, LEVEL 104,
// -4 dB (LEVEL_Q12[104] / 4096, gen_tables.py), over the 32,768 of full
// scale, less 12 dB. Felucca mixes hot into a limiter; our engines leave
// room for four sounds and the effects (a note at about -26 dB RMS, as
// Macro's and FM6's), so the Felucca engines sit 12 dB below Felucca's own
// level. All exact powers of two but 2,584: the oracle's ints times this
// are our samples, bit for bit.
const float kPartGain = 2584.0f / 4096.0f / 32768.0f / 4.0f;
const float kVolumeRef = 0.7f;

// How a parameter reaches Felucca.
enum Kind {
  K_LIST,       // an ENUM: its entry is the EDIT value
  K_INT,        // a FLOAT, rounded to the nearest integer (bars, intervals, cents)
  K_PCT,        // 0..100 % as Felucca's 0..127
  K_CUTOFF,     // Hz on Felucca's cutoff curve (30 Hz .. 16 kHz), in 1/256 of a
                // knob step, through vmod_t.cutoff; the EDIT value is 0
  K_SHAPE,      // 0..100 % in 1/256 of a knob step, through vmod_t.shape;
                // the EDIT value is 0 (Trio's PW, Phase Bend's DCW)
  K_FENV,       // -100..100 % as Felucca's ENV -> FILTER, -64..63
  K_ATTACK, K_DECAY, K_SUSTAIN, K_RELEASE,
  K_VOLUME, K_GLIDE, K_VMODE, K_GMODE, K_TMODE
};

struct Slot {
  uint8_t kind;      // Kind
  int8_t edit;       // which of P_E0..P_E7, or -1
  uint8_t latch;     // 1: a voice keeps the value it had at its note-on
};

struct Def {
  int fel;                       // FEL_WHEEL, FEL_TRIO, FEL_PHASE
  const fm1_param_t *params;
  const Slot *slots;
  int n;
  int glide, vmode, gmode, tmode;   // indices of Glide, Voice Mode, Glide Mode
                                    // and Time Mode, or -1
};

const uint16_t kCont = FM1_PARAM_CONTINUOUS;
const uint16_t kContPoly = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const uint16_t kContLogPoly = FM1_PARAM_CONTINUOUS_LOG | FM1_PARAM_POLY;
const uint16_t kLatch = FM1_PARAM_LATCH | FM1_PARAM_MOD;
const uint16_t kList = FM1_PARAM_MOD;

// The envelope's times: Felucca's time curve, 1 ms .. 10 s (gen_tables.py,
// 10,000^(v / 127) ms), on the LOG law, whose 7-bit positions are its steps.
const float kTimeMin = 1.0f;
const float kTimeMax = 10000.0f;

// ---- Drawbar (WHEEL) -------------------------------------------------------
// Names after eng_wheel.c's, spelt out.
const char *const kRegNames[] = {
  "Flute", "Mellow", "Hollow", "Smooth", "3 Bar", "Blues", "Gospel", "Rock",
  "Tops", "Clarinet", "Reed", "Strings", "Chapel", "Bright", "Bass", "Full",
};
const char *const kPercNames[] = { "Off", "2nd", "3rd", "2nd Soft", "3rd Soft", "2nd Slow", "3rd Slow" };
const char *const kRotorNames[] = { "Off", "Slow", "Fast" };

// Uids are fixed: never renumber one; a new parameter takes the next free
// uid. Defaults: eng_wheel.c's knobs, and the envelope all five of its
// factory sounds share (attack 0, decay 64, sustain 127, release 45).
const fm1_param_t kDrawbarParams[] = {
  { "Drawbars",     FM1_PARAM_ENUM, 0, 15, 4, kRegNames, 0, 1, kList, FM1_UNIT_NONE, "Bars" },
  { "Sub",          FM1_PARAM_FLOAT, -8, 8, 0, NULL, 0, 2, kCont, FM1_UNIT_NONE, "Sub" },
  { "Body",         FM1_PARAM_FLOAT, -8, 8, 0, NULL, 0, 3, kCont, FM1_UNIT_NONE, "Body" },
  { "Top",          FM1_PARAM_FLOAT, -8, 8, 0, NULL, 0, 4, kCont, FM1_UNIT_NONE, "Top" },
  { "Perc",         FM1_PARAM_ENUM, 0, 6, 0, kPercNames, 1, 5, kList, FM1_UNIT_NONE, "Perc" },
  { "Click",        FM1_PARAM_FLOAT, 0, 100, 31.5f, NULL, 1, 6, kCont, FM1_UNIT_PCT, "Click" },
  { "Drive",        FM1_PARAM_FLOAT, 0, 100, 0, NULL, 1, 7, kCont, FM1_UNIT_PCT, "Drive" },
  { "Rotor",        FM1_PARAM_ENUM, 0, 2, 1, kRotorNames, 1, 8, kList, FM1_UNIT_NONE, "Rotor" },
  { "Attack",       FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 1.0f, NULL, 2, 9, kContLogPoly, FM1_UNIT_MS, "Atk" },
  { "Decay",        FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 103.6f, NULL, 2, 10, kContLogPoly, FM1_UNIT_MS, "Dec" },
  { "Sustain",      FM1_PARAM_FLOAT, 0, 100, 100, NULL, 2, 11, kContPoly, FM1_UNIT_PCT, "Sus" },
  { "Release",      FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 26.1f, NULL, 2, 12, kContLogPoly, FM1_UNIT_MS, "Rel" },
  { "Volume",       FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 3, 13, kContPoly, FM1_UNIT_NONE, "Vol" },
};
const Slot kDrawbarSlots[] = {
  { K_LIST, 0, 0 }, { K_INT, 1, 0 }, { K_INT, 2, 0 }, { K_INT, 3, 0 },
  { K_LIST, 4, 0 }, { K_PCT, 5, 0 }, { K_PCT, 6, 0 }, { K_LIST, 7, 0 },
  { K_ATTACK, -1, 0 }, { K_DECAY, -1, 0 }, { K_SUSTAIN, -1, 0 }, { K_RELEASE, -1, 0 },
  { K_VOLUME, -1, 0 },
};

// ---- Trio (TRIO) -----------------------------------------------------------
const char *const kTrioWaveNames[] = {
  "Saw x3", "Pulse x3", "Pls+Pls+Tri", "Saw+Saw+Tri", "Tri x3", "Saw&Tri", "Pulse&Saw",
  "Pulse+Noise", "Noise", "Sync", "Sync Pulse", "Sync 3", "Ring", "Ring 3", "Ring+Sync",
  "Ring+Sync P",
};
const char *const kTrioModeNames[] = { "Low-pass", "Band-pass", "High-pass", "Notch" };

// Defaults: eng_trio.c's knobs (Cutoff 80 is 1,566.45 Hz on the curve, PW
// 64 is 50.3937 %), no
// envelope to the filter, and Felucca's part envelope (attack 10, decay 70,
// sustain 90, release 60: 2.07 ms, 160 ms, 70.9 %, 77.6 ms).
const fm1_param_t kTrioParams[] = {
  { "Wave",      FM1_PARAM_ENUM, 0, 15, 0, kTrioWaveNames, 0, 1, kLatch, FM1_UNIT_NONE, "Wave" },
  { "Int 2",     FM1_PARAM_FLOAT, -24, 24, 0, NULL, 0, 2, kContPoly, FM1_UNIT_SEMI, "Int2" },
  { "Int 3",     FM1_PARAM_FLOAT, -24, 24, -12, NULL, 0, 3, kContPoly, FM1_UNIT_SEMI, "Int3" },
  { "Detune",    FM1_PARAM_FLOAT, 0, 50, 6, NULL, 0, 4, kContPoly, FM1_UNIT_NONE, "Detune" },
  { "Mode",      FM1_PARAM_ENUM, 0, 3, 0, kTrioModeNames, 1, 5, kLatch, FM1_UNIT_NONE, "Mode" },
  { "Cutoff",    FM1_PARAM_FLOAT, 30, 16000, 1566.45f, NULL, 1, 6, kContLogPoly, FM1_UNIT_HZ, "Cut" },
  { "Resonance", FM1_PARAM_FLOAT, 0, 100, 31.5f, NULL, 1, 7, kContPoly, FM1_UNIT_PCT, "Res" },
  { "PW",        FM1_PARAM_FLOAT, 0, 100, 50.3937f, NULL, 1, 8, kContPoly, FM1_UNIT_PCT, "PW" },
  { "Env Amt",   FM1_PARAM_FLOAT, -100, 100, 0, NULL, 2, 9, kContPoly, FM1_UNIT_PCT, "EnvAmt" },
  { "Attack",    FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 2.07f, NULL, 2, 10, kContLogPoly, FM1_UNIT_MS, "Atk" },
  { "Decay",     FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 160.2f, NULL, 2, 11, kContLogPoly, FM1_UNIT_MS, "Dec" },
  { "Sustain",   FM1_PARAM_FLOAT, 0, 100, 70.9f, NULL, 2, 12, kContPoly, FM1_UNIT_PCT, "Sus" },
  { "Release",   FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 77.6f, NULL, 3, 13, kContLogPoly, FM1_UNIT_MS, "Rel" },
  { "Volume",    FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 3, 14, kContPoly, FM1_UNIT_NONE, "Vol" },
};
const Slot kTrioSlots[] = {
  { K_LIST, 0, 1 }, { K_INT, 1, 0 }, { K_INT, 2, 0 }, { K_INT, 3, 0 },
  { K_LIST, 4, 1 }, { K_CUTOFF, 5, 0 }, { K_PCT, 6, 0 }, { K_SHAPE, 7, 0 },
  { K_FENV, -1, 0 }, { K_ATTACK, -1, 0 }, { K_DECAY, -1, 0 }, { K_SUSTAIN, -1, 0 },
  { K_RELEASE, -1, 0 }, { K_VOLUME, -1, 0 },
};

// ---- Phase Bend (PHASE) ------------------------------------------------------
const char *const kPhaseWaveNames[] = {
  "Saw", "Square", "Pulse", "Double Sine", "Saw Pulse", "Reso Saw", "Reso Tri", "Reso Trap",
};
const char *const kPhaseWave2Names[] = {
  "Same", "Saw", "Square", "Pulse", "Double Sine", "Saw Pulse", "Reso Saw", "Reso Tri", "Reso Trap",
};
const char *const kPhaseLineNames[] = { "Mix", "Ring" };

// Defaults: eng_phase.c's knobs (DCW 60, 47.2441 %; ENV 64) and Felucca's part
// envelope, as Trio's. Its eighth EDIT knob is unused upstream ("-"):
// glide's four parameters take its place in the table, on page 4.
const fm1_param_t kPhaseParams[] = {
  { "Wave",       FM1_PARAM_ENUM, 0, 7, 0, kPhaseWaveNames, 0, 1, kLatch, FM1_UNIT_NONE, "Wave" },
  { "Wave 2",     FM1_PARAM_ENUM, 0, 8, 0, kPhaseWave2Names, 0, 2, kLatch, FM1_UNIT_NONE, "Wave2" },
  { "DCW",        FM1_PARAM_FLOAT, 0, 100, 47.2441f, NULL, 0, 3, kContPoly, FM1_UNIT_PCT, "DCW" },
  { "Env",        FM1_PARAM_FLOAT, 0, 100, 50.4f, NULL, 0, 4, kContPoly, FM1_UNIT_PCT, "Env" },
  { "Detune",     FM1_PARAM_FLOAT, 0, 127, 0, NULL, 1, 5, kContPoly, FM1_UNIT_NONE, "Detune" },
  { "Line",       FM1_PARAM_ENUM, 0, 1, 0, kPhaseLineNames, 1, 6, kLatch, FM1_UNIT_NONE, "Line" },
  { "Sub",        FM1_PARAM_FLOAT, 0, 100, 0, NULL, 1, 7, kContPoly, FM1_UNIT_PCT, "Sub" },
  { "Attack",     FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 2.07f, NULL, 1, 8, kContLogPoly, FM1_UNIT_MS, "Atk" },
  { "Decay",      FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 160.2f, NULL, 2, 9, kContLogPoly, FM1_UNIT_MS, "Dec" },
  { "Sustain",    FM1_PARAM_FLOAT, 0, 100, 70.9f, NULL, 2, 10, kContPoly, FM1_UNIT_PCT, "Sus" },
  { "Release",    FM1_PARAM_FLOAT, kTimeMin, kTimeMax, 77.6f, NULL, 2, 11, kContLogPoly, FM1_UNIT_MS, "Rel" },
  { "Volume",     FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 2, 12, kContPoly, FM1_UNIT_NONE, "Vol" },
  { "Glide",      FM1_PARAM_FLOAT, glide::kMinMs, glide::kMaxMs, glide::kDefaultMs, NULL, 3, 13,
    glide::kGlideFlags, FM1_UNIT_MS, "Glide" },
  { "Voice Mode", FM1_PARAM_ENUM, 0, glide::MODE_COUNT - 1, glide::MODE_POLY, glide::kModeNames, 3,
    14, glide::kModeFlags, FM1_UNIT_NONE, "VMode" },
  { "Glide Mode", FM1_PARAM_ENUM, 0, glide::GLIDE_MODE_COUNT - 1, glide::GLIDE_OFF,
    glide::kGlideModeNames, 3, 15, glide::kModeFlags, FM1_UNIT_NONE, "GMode" },
  { "Time Mode",  FM1_PARAM_ENUM, 0, glide::TIME_MODE_COUNT - 1, glide::TIME_TIME,
    glide::kTimeModeNames, 3, 16, glide::kModeFlags, FM1_UNIT_NONE, "TMode" },
};
const Slot kPhaseSlots[] = {
  { K_LIST, 0, 1 }, { K_LIST, 1, 1 }, { K_SHAPE, 2, 0 }, { K_PCT, 3, 0 },
  { K_INT, 4, 0 }, { K_LIST, 5, 1 }, { K_PCT, 6, 0 }, { K_ATTACK, -1, 0 },
  { K_DECAY, -1, 0 }, { K_SUSTAIN, -1, 0 }, { K_RELEASE, -1, 0 }, { K_VOLUME, -1, 0 },
  { K_GLIDE, -1, 0 }, { K_VMODE, -1, 0 }, { K_GMODE, -1, 0 }, { K_TMODE, -1, 0 },
};

#define FEL_COUNT(a) static_cast<int>(sizeof(a) / sizeof((a)[0]))
const Def kDrawbar = { FEL_WHEEL, kDrawbarParams, kDrawbarSlots, FEL_COUNT(kDrawbarParams), -1, -1, -1, -1 };
const Def kTrio = { FEL_TRIO, kTrioParams, kTrioSlots, FEL_COUNT(kTrioParams), -1, -1, -1, -1 };
const Def kPhase = { FEL_PHASE, kPhaseParams, kPhaseSlots, FEL_COUNT(kPhaseParams), 12, 13, 14, 15 };
typedef char slots_match[FEL_COUNT(kDrawbarSlots) == FEL_COUNT(kDrawbarParams) &&
                         FEL_COUNT(kTrioSlots) == FEL_COUNT(kTrioParams) &&
                         FEL_COUNT(kPhaseSlots) == FEL_COUNT(kPhaseParams) &&
                         FEL_COUNT(kTrioParams) <= kMaxParams && FEL_COUNT(kPhaseParams) <= kMaxParams
                         ? 1 : -1];

// ---- Maps onto Felucca's knobs ---------------------------------------------
inline int RoundI(float v) { return v < 0.0f ? -static_cast<int>(0.5f - v) : static_cast<int>(v + 0.5f); }
inline int ClampI(int v, int lo, int hi) { return v < lo ? lo : (v > hi ? hi : v); }

// 0..100 % as 0..127.
inline int Pct127(float pct) {
  const float k = pct * 1.27f;
  return ClampI(RoundI(k), 0, 127);
}

// A time on Felucca's curve: the step v whose 10,000^(v / 127) ms is nearest
// on the LOG law, round(127 x log10(ms) / 4).
inline int TimeStep(float ms) {
  const float steps = fm1_log2f(ms) * 9.5577052f;     // 127 / (4 log2 10)
  return ClampI(RoundI(steps), 0, 127);
}

// Hz on Felucca's cutoff curve, 30 x (16,000 / 30)^(v / 127), as v x 256.
inline int CutoffQ8(float hz) {
  const float octaves = fm1_log2f(hz * (1.0f / 30.0f));
  const float steps = octaves * (127.0f * 256.0f / 9.0588937f);   // log2(16,000 / 30)
  return ClampI(RoundI(steps), 0, 127 * 256);
}

// A voice's (or the part's) values in Felucca's units for a block.
struct Knobs {
  int16_t e[FEL_EDIT];
  int32_t cutoff, shape, fenv;
  uint8_t adsr[4];
  float gain;
};

// Every slot of `def` from values[] (ramped, with a voice's offsets).
void MapAll(const Def &def, const float *values, Knobs *k) {
  for (int j = 0; j < FEL_EDIT; ++j) k->e[j] = 0;
  k->cutoff = 0;
  k->shape = 64 << 8;
  k->fenv = 0;
  for (int j = 0; j < 4; ++j) k->adsr[j] = 0;
  k->gain = kPartGain;
  for (int i = 0; i < def.n; ++i) {
    const Slot &s = def.slots[i];
    const float v = values[i];
    int x = 0;
    switch (s.kind) {
      case K_LIST:
      case K_INT: x = RoundI(v); break;
      case K_PCT: x = Pct127(v); break;
      case K_CUTOFF: k->cutoff += CutoffQ8(v); break;
      case K_SHAPE: {
        const float q8 = v * (1.27f * 256.0f);
        k->shape += ClampI(RoundI(q8), 0, 127 * 256);
        break;
      }
      case K_FENV: {
        const float f = v * 0.64f;
        k->fenv = ClampI(RoundI(f), -64, 63);
        break;
      }
      case K_ATTACK: k->adsr[0] = static_cast<uint8_t>(TimeStep(v)); break;
      case K_DECAY: k->adsr[1] = static_cast<uint8_t>(TimeStep(v)); break;
      case K_SUSTAIN: k->adsr[2] = static_cast<uint8_t>(Pct127(v)); break;
      case K_RELEASE: k->adsr[3] = static_cast<uint8_t>(TimeStep(v)); break;
      case K_VOLUME: {
        const float r = v / kVolumeRef;   // exactly 1 at the default
        const float r2 = r * r;
        // Below -180 dB, silence: no product of a tiny gain is subnormal.
        k->gain = r2 >= 1.0e-9f ? r2 * kPartGain : 0.0f;
        break;
      }
      default: break;
    }
    if (s.edit >= 0) k->e[s.edit] = static_cast<int16_t>(x);
  }
}

typedef NoteOffsets<0, kMaxParams> Offsets;

struct Voice {
  uint8_t key;
  bool gate;
  bool active;
  uint32_t age;
  Offsets note;                    // per-note offsets (set_param_note)
  glide::Slew glide;               // its glide (glide.h), Phase Bend only
  int16_t latch[FEL_EDIT];         // the LATCH lists' values at its note-on
};

class Instance {
 public:
  bool Init(const Def *def, const fm1_host_t *host) {
    const float r = host ? host->sample_rate : 0.0f;
    if (!(r >= kMinRate && r <= kMaxRate)) return false;
    def_ = def;
    fel_world_init(World(), def->fel);
    for (int i = 0; i < kMaxParams; ++i) value_[i] = 0.0f;
    for (int i = 0; i < def->n; ++i) value_[i] = def->params[i].def;
    fm1_smooth_init(smooth_, value_, kMaxParams);
    smooth_steps_ = fm1_smooth_steps(r, kBlock);
    glide_block_ms_ = glide::BlockMs(r, kBlock);
    bend_ = 0.0f;
    clock_ = 0;
    rr_ = 0;
    pos_ = kBlock;
    held_.Clear();
    for (uint32_t i = 0; i < kBlock; ++i) buf_[i] = 0.0f;
    for (int i = 0; i < kVoices; ++i) {
      Voice &v = voice_[i];
      v.key = 0;
      v.gate = v.active = false;
      v.age = 0;
      v.note.Clear();
      v.glide.Clear();
      for (int j = 0; j < FEL_EDIT; ++j) v.latch[j] = 0;
    }
    return true;
  }

  static size_t WorldOffset() { return (sizeof(Instance) + 15u) & ~static_cast<size_t>(15u); }

  // The bridge's state, right after this struct in the instance's memory
  // (InstanceSize), found from `this` rather than kept as a pointer.
  unsigned char *World() { return reinterpret_cast<unsigned char *>(this) + WorldOffset(); }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (key > 127) return;
    if (velocity == 0) {
      NoteOff(key);
      return;
    }
    held_.Push(key);
    const glide::Plan<Voice> plan = glide::PlanNoteOn(voice_, kVoices, GlideConfig());
    if (plan.legato) {              // Legato over a held note: a new key, nothing restarts
      Retune(plan.mono, key);
      glide::StartFor(plan.mono, plan, key);
      return;
    }
    Voice *v = plan.mono ? plan.mono : Allocate(key);
    Start(v, key, velocity);
    glide::StartFor(v, plan, key);
  }

  void NoteOff(uint8_t key) {
    if (key > 127) return;
    held_.Remove(key);
    if (Mode() != glide::MODE_POLY) ReturnToHeld(key);
    for (int i = 0; i < kVoices; ++i) {
      Voice &v = voice_[i];
      if (v.gate && v.key == key) {
        v.gate = false;
        fel_voice_release(World(), i);
      }
    }
  }

  void PitchBend(float semitones) { bend_ = semitones == semitones ? semitones : 0.0f; }

  void SetParam(uint16_t index, float value) {
    if (index >= def_->n) return;
    const fm1_param_t &p = def_->params[index];
    value = fm1_param_clamp(&p, value);
    fm1_smooth_set(&smooth_[index], &value_[index], value, Steps(index));
  }

  // The voice sounding `key` (one at most: a key strikes again in its own
  // voice), held or releasing, takes the offset.
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (index != FM1_PARAM_NOTE_PITCH && index >= def_->n) return;
    if (!Offsets::Normalise(def_->params, index, &offset)) return;
    for (int i = 0; i < kVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  void Render(float *out, uint32_t frames) {
    uint32_t done = 0;
    while (done < frames) {
      if (pos_ == kBlock) Block();
      uint32_t n = kBlock - pos_;
      if (n > frames - done) n = frames - done;
      for (uint32_t k = 0; k < n; ++k) {
        const float y = buf_[pos_ + k];
        out[2 * (done + k)] = y;
        out[2 * (done + k) + 1] = y;
      }
      pos_ += n;
      done += n;
    }
  }

 private:
  glide::Mode Mode() const {
    return def_->vmode >= 0 ? glide::ToMode(value_[def_->vmode]) : glide::MODE_POLY;
  }

  // What Voice Mode, Glide Mode and Time Mode say now (glide.h); Poly with
  // Glide Mode Off where the engine has none of them.
  glide::Config GlideConfig() const {
    if (def_->vmode < 0) return glide::Read(glide::MODE_POLY, glide::GLIDE_OFF, glide::TIME_TIME);
    return glide::Read(value_[def_->vmode], value_[def_->gmode], value_[def_->tmode]);
  }

  // A SMOOTH parameter ramps while a voice sounds; anything else, at once.
  uint32_t Steps(uint16_t index) const {
    if (!(def_->params[index].flags & FM1_PARAM_SMOOTH)) return 0;
    for (int i = 0; i < kVoices; ++i) {
      if (voice_[i].active) return smooth_steps_;
    }
    return 0;
  }

  // The voice for a new note (Poly): the key's own if it sounds, else the
  // next free one in turn, else the oldest released, else the oldest held
  // one that is not the lowest held key.
  Voice *Allocate(uint8_t key) {
    for (int i = 0; i < kVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) return &voice_[i];
    }
    int best = -1;
    for (int i = 0; i < kVoices && best < 0; ++i) {
      const int k = (rr_ + i) % kVoices;
      if (!voice_[k].active) best = k;
    }
    rr_ = static_cast<uint8_t>(((best < 0 ? rr_ : best) + 1) % kVoices);
    if (best >= 0) return &voice_[best];
    int low = -1;
    for (int i = 0; i < kVoices; ++i) {
      if (voice_[i].gate && (low < 0 || voice_[i].key < voice_[low].key)) low = i;
    }
    for (int i = 0; i < kVoices; ++i) {
      if (!voice_[i].gate && (best < 0 || voice_[i].age < voice_[best].age)) best = i;
    }
    if (best < 0) {
      for (int i = 0; i < kVoices; ++i) {
        if (i != low && (best < 0 || voice_[i].age < voice_[best].age)) best = i;
      }
    }
    return &voice_[best < 0 ? 0 : best];
  }

  // A voice starts on key, or starts again where it is.
  void Start(Voice *v, uint8_t key, uint8_t velocity) {
    const int i = static_cast<int>(v - voice_);
    v->key = key;
    v->gate = true;
    v->active = true;
    v->age = ++clock_;
    v->note.Clear();                // a new note, a retrigger or a steal: no offsets
    v->glide.Begin();
    Knobs k;
    MapAll(*def_, value_, &k);
    for (int s = 0; s < def_->n; ++s) {
      const Slot &slot = def_->slots[s];
      if (slot.latch && slot.edit >= 0) v->latch[slot.edit] = k.e[slot.edit];
    }
    fel_voice_start(World(), def_->fel, i, key, velocity, v->age, static_cast<int32_t>(key) * 16, k.e);
  }

  // Mono and Legato: letting go of the key the voice plays while older keys
  // are held moves it back to the newest of them, gliding, never restarting.
  void ReturnToHeld(uint8_t key) {
    uint8_t top = 0;
    const glide::Plan<Voice> plan = glide::PlanNoteOff(voice_, kVoices, held_, key, GlideConfig(), &top);
    if (!plan.mono) return;
    Retune(plan.mono, top);
    glide::StartFor(plan.mono, plan, top);
  }

  // A voice takes another key without restarting: a new note for its
  // per-note offsets, the same velocity and envelope.
  void Retune(Voice *v, uint8_t key) {
    v->key = key;
    v->note.Clear();
    fel_voice_retune(World(), static_cast<int>(v - voice_), key);
  }

  // One control block: the ramps' step, every voice's values and pitch, the
  // bridge's render, the mix.
  void Block() {
    if (fm1_smooth_moving(smooth_, kMaxParams)) fm1_smooth_tick(smooth_, value_, kMaxParams);
    // This block's glide step, divided out only if some voice glides.
    glide::Step glide_step(glide_block_ms_, def_->glide >= 0 ? value_[def_->glide] : glide::kMinMs);
    Knobs part;
    MapAll(*def_, value_, &part);
    fel_vin_t in[kVoices] = {};      // a silent voice's is not read
    float own_gain[kVoices];
    int n_own = 0;
    for (uint32_t s = 0; s < kBlock; ++s) mix_[s] = 0;
    for (int i = 0; i < kVoices; ++i) {
      Voice &v = voice_[i];
      fel_vin_t &x = in[i];
      x.out = mix_;
      if (!v.active) continue;     // the bridge renders the voices that sound
      Knobs k = part;
      if (v.note.any()) {
        float value[kMaxParams];
        for (int j = 0; j < def_->n; ++j) value[j] = v.note.Value(def_->params, j, value_[j]);
        MapAll(*def_, value, &k);
      }
      for (int s = 0; s < def_->n; ++s) {
        const Slot &slot = def_->slots[s];
        if (slot.latch && slot.edit >= 0) k.e[slot.edit] = v.latch[slot.edit];
      }
      for (int j = 0; j < FEL_EDIT; ++j) x.e[j] = k.e[j];
      x.cutoff = k.cutoff;
      x.shape = k.shape;
      x.fenv = k.fenv;
      for (int j = 0; j < 4; ++j) x.adsr[j] = k.adsr[j];
      // The pitch: the key, the bend, the per-note offset and the glide, in
      // Felucca's 1/16 semitone and the 1/4096 of the increment below it.
      float semis = static_cast<float>(v.key);
      if (v.glide.active) semis += v.glide.offset;
      const float glided = semis;
      semis += bend_;
      if (v.note.has_pitch()) semis += v.note.pitch;
      v.glide.Next(glide_step);
      Pitch(semis, &x.pitch16, &x.fine);
      {
        int32_t cur = 0, unused = 0;
        Pitch(glided, &cur, &unused);
        x.pitch_cur = cur;
      }
      if (k.gain != part.gain) {
        x.out = own_[n_own];
        for (uint32_t s = 0; s < kBlock; ++s) own_[n_own][s] = 0;
        own_gain[n_own] = k.gain;
        ++n_own;
      }
    }
    fel_block(World(), def_->fel, part.e, in);
    for (uint32_t s = 0; s < kBlock; ++s) {
      float y = static_cast<float>(mix_[s]) * part.gain;
      for (int j = 0; j < n_own; ++j) {
        const float t = static_cast<float>(own_[j][s]) * own_gain[j];
        y = y + t;
      }
      buf_[s] = y;
    }
    for (int i = 0; i < kVoices; ++i) {
      Voice &v = voice_[i];
      if (v.active && !fel_voice_active(World(), i)) {    // its release has ended
        v.active = v.gate = false;
        v.note.Clear();
        v.glide.Clear();
      }
    }
    pos_ = 0;
  }

  // Semitones (MIDI keys) as Felucca's 1/16 semitone, 0..2047, and the rest
  // in 1/4096 of the phase increment (14.79 to a 1/16 semitone, as voice.c
  // converts a bend's rest).
  static void Pitch(float semis, int32_t *pitch16, int32_t *fine) {
    const float sixteenths = semis * 16.0f;
    if (!(sixteenths > 0.0f)) {
      *pitch16 = 0;
      *fine = 0;
      return;
    }
    if (sixteenths >= 2047.0f) {
      *pitch16 = 2047;
      *fine = 0;
      return;
    }
    const int32_t whole = static_cast<int32_t>(sixteenths);
    const float rest = sixteenths - static_cast<float>(whole);
    const float units = rest * 14.79f;
    *pitch16 = whole;
    *fine = static_cast<int32_t>(units + 0.5f);
  }

  const Def *def_;
  Voice voice_[kVoices];
  float value_[kMaxParams];        // what the blocks read (SMOOTH: ramped)
  fm1_smooth_t smooth_[kMaxParams];
  uint32_t smooth_steps_;          // control blocks in a ramp
  float glide_block_ms_;
  float bend_;
  uint32_t clock_;                 // voice ages
  uint8_t rr_;                     // the next free voice to try
  glide::Held held_;               // keys down, for Mono and Legato
  uint32_t pos_;                   // next sample of buf_ to hand out; kBlock: none
  float buf_[kBlock];
  int32_t mix_[kBlock];            // the voices at the part's gain
  int32_t own_[kVoices][kBlock];   // voices with a Volume of their own
};

size_t InstanceSize(const Def &def) {
  return Instance::WorldOffset() + ((fel_world_size(def.fel) + 15u) & ~static_cast<size_t>(15u));
}

void *Create(const Def *def, void *mem, const fm1_host_t *host) {
  Instance *self = new (mem) Instance();
  if (!self->Init(def, host)) {
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

size_t DrawbarSize(const fm1_host_t *) { return InstanceSize(kDrawbar); }
size_t TrioSize(const fm1_host_t *) { return InstanceSize(kTrio); }
size_t PhaseSize(const fm1_host_t *) { return InstanceSize(kPhase); }
void *DrawbarCreate(void *mem, const fm1_host_t *host) { return Create(&kDrawbar, mem, host); }
void *TrioCreate(void *mem, const fm1_host_t *host) { return Create(&kTrio, mem, host); }
void *PhaseCreate(void *mem, const fm1_host_t *host) { return Create(&kPhase, mem, host); }

}  // namespace felucca
}  // namespace fm1

#define FEL_CREDIT "Felucca by Leo Kuroshita (@kurogedelic), Hugelton Instruments (GPL-3.0): "

extern "C" const fm1_engine_t fm1_engine_drawbar = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "drawbar", "Drawbar",
  FEL_CREDIT "its WHEEL engine, a tonewheel-style organ of its own design",
  fm1::felucca::kDrawbarParams, FEL_COUNT(fm1::felucca::kDrawbarParams), fm1::felucca::kVoices,
  fm1::felucca::DrawbarSize, fm1::felucca::DrawbarCreate, fm1::felucca::Destroy,
  fm1::felucca::NoteOn, fm1::felucca::NoteOff, fm1::felucca::Bend,
  fm1::felucca::Set, fm1::felucca::Render,
  fm1::felucca::SetNote,
  0, NULL,                  // API v3: no effect extension
  0, 0,                     // not a pad kit
};

extern "C" const fm1_engine_t fm1_engine_trio = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "trio", "Trio",
  FEL_CREDIT "its TRIO engine, three oscillators and a filter in the style of 8-bit sound chips",
  fm1::felucca::kTrioParams, FEL_COUNT(fm1::felucca::kTrioParams), fm1::felucca::kVoices,
  fm1::felucca::TrioSize, fm1::felucca::TrioCreate, fm1::felucca::Destroy,
  fm1::felucca::NoteOn, fm1::felucca::NoteOff, fm1::felucca::Bend,
  fm1::felucca::Set, fm1::felucca::Render,
  fm1::felucca::SetNote,
  0, NULL,
  0, 0,
};

extern "C" const fm1_engine_t fm1_engine_phase_bend = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "phase-bend", "Phase Bend",
  FEL_CREDIT "its PHASE engine, a port of the phase-distortion oscillator of CrispyZebra "
  "by the same author (GPL-3.0)",
  fm1::felucca::kPhaseParams, FEL_COUNT(fm1::felucca::kPhaseParams), fm1::felucca::kVoices,
  fm1::felucca::PhaseSize, fm1::felucca::PhaseCreate, fm1::felucca::Destroy,
  fm1::felucca::NoteOn, fm1::felucca::NoteOff, fm1::felucca::Bend,
  fm1::felucca::Set, fm1::felucca::Render,
  fm1::felucca::SetNote,
  0, NULL,
  0, 0,
};

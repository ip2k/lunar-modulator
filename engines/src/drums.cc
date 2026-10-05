// drums.cc -- "Drums": a 16-pad kit after the classic analogue drum
// machines, on MIDI notes 36-51 (General MIDI's drum keys, the pad map
// Sophie uses).
//
// Where the sounds come from:
//   - the kicks, toms, snares and hi-hats are Mutable Instruments Plaits'
//     drum classes (Emilie Gillet, MIT; vendored unmodified in
//     third_party/mutable), called directly, one object per sounding
//     voice: AnalogBassDrum, SyntheticBassDrum, AnalogSnareDrum,
//     SyntheticSnareDrum, and HiHat with its square-wave bank or its ring
//     modulator. Plaits' own BassDrumEngine, SnareDrumEngine and
//     HiHatEngine (Macro Heavy's models 10-12) render two of these every
//     block for one output; a pad here renders the one it plays;
//   - the rim shot, clap, cowbell and cymbal are this repository's, written
//     from published analyses of the analogue circuits (drum_voices.h).
// The analogue machines that inspired the two kits are credited in the
// manual; no product name is a name here.
//
// Pads and voices. Notes 36-51 play pads 1-16 (the engine's pad_first_note
// and pad_count, so a host can lay them on its keys); other notes, and every
// note-off, are ignored: a hit rings out for its decay, as on the machines.
// Twelve voices: a pad struck again while it sounds is struck again in its
// own voice (re-excited, as the circuits are, not restarted), otherwise it
// takes a free voice, else the one being choked, else the oldest. A hit on
// one of the closed, pedal and open hi-hats cuts the others within 4 ms, as
// on the machines, where they share one circuit (the voicings' choke group).
// A voice ends once it has stayed under -80 dBFS for 10 ms.
//
// The parameters. Pad chooses which pad the per-pad parameters edit, as on
// Sophie; each of the 16 pads keeps its own Tune, Decay, Level, Tone, Snap,
// Sweep, Drive and Model. Kit, Accent and Volume are the whole kit's. Twelve
// in all: the most a sound engine may have while four of the largest fit
// the modulation runtime's shared records beside ten of the largest effects
// (FM1_MOD_SINK_PARAMS, tests/test_engines_mod_runtime.py). Every per-pad
// knob is relative to the pad's voicing (the kit's table below): Tune 0 and
// the 0..1 knobs at 0.5 are the pad as voiced, so one default fits all
// sixteen and a fresh kit shows true values on every pad. Model starts at
// "Kit", the voicing's own, and otherwise names a model; a pad given another
// model takes that model's own voicing. Kit chooses between two sets of
// voicings: Deep, the long, round analogue kit, and Punch, the shorter,
// harder one with the synthetic kick and snare and the ring-modulated hats.
//
// Flags. Every FLOAT is SMOOTH, MOD and POLY. The per-pad ones ramp in the
// pad's own values (a ramp keeps going on its pad when Pad moves on), and
// only while that pad sounds; the kit's ramp while any voice sounds. Model
// and Kit are read when a pad is struck (LATCH, and MOD: a route is
// rounded): a sounding hit keeps what it started with. Pad is the edit
// focus, lockable without MOD, as Sophie's (owner, docs/15 S8).
//
// Per-note offsets (set_param_note; note_offsets.h): a hit's offsets ride on
// its pad's values, ramped, and on the kit's; the pitch offset moves the
// hit after Tune and the bend.
//
// Rate and blocks, as Macro's and Macro Heavy's (the owner's 2026-10-01
// rule for Mutable code): the classes run at Plaits' own 47,872.34 Hz in
// its 12-sample blocks with Plaits' time constants untouched, and the mono
// mix goes through one resampler (include/fm1_resampler.h) to the host's
// rate. Hosts above 47,872.34 Hz or below a quarter of it are refused. Note
// events and parameter changes land on the next 12-sample block (0.25 ms),
// so the output does not depend on the host's block size.
//
// Noise. The Plaits classes draw from stmlib's one global generator. Here
// each pad has a generator state of its own, swapped in around its voice's
// render and the global one put back after, so a pad's noise depends only on
// its own hits: two pads struck together sound as the two struck apart,
// summed, and no other engine's noise moves ours, or ours theirs.
//
// No libm in the render: pitches and times go through stmlib's tables
// (SemitonesToRatio), filters through its polynomial tangents, and the
// classes take sqrtf twice a block (correctly rounded everywhere), so the
// browser's module renders the same samples.
//
// MIT licence (this file). Not affiliated with or endorsed by Mutable
// Instruments.

#include "fm1_engine.h"
#include "fm1_resampler.h"
#include "fm1_smooth.h"
#include "note_offsets.h"
#include "drum_voices.h"

#include <cstring>
#include <new>

#include "stmlib/dsp/dsp.h"
#include "stmlib/dsp/units.h"
#include "stmlib/utils/random.h"
#include "plaits/dsp/dsp.h"
#include "plaits/dsp/engine/engine.h"   // NoteToFrequency
#include "plaits/dsp/drums/analog_bass_drum.h"
#include "plaits/dsp/drums/analog_snare_drum.h"
#include "plaits/dsp/drums/hi_hat.h"
#include "plaits/dsp/drums/synthetic_bass_drum.h"
#include "plaits/dsp/drums/synthetic_snare_drum.h"

namespace fm1 {
namespace drums {

using namespace plaits;

const int kNumPads = 16;
const int kFirstNote = 36;
const int kNumVoices = 12;

// ---- models and voicings --------------------------------------------------------------

enum Model {
  MODEL_ANALOG_DRUM,   // Plaits AnalogBassDrum: deep kick, toms
  MODEL_PUNCH_DRUM,    // Plaits SyntheticBassDrum: punchy kick, toms
  MODEL_SNARE,         // Plaits AnalogSnareDrum
  MODEL_SNAP_SNARE,    // Plaits SyntheticSnareDrum
  MODEL_HAT,           // Plaits HiHat, six square waves, swing VCA
  MODEL_RING_HAT,      // Plaits HiHat, ring-modulated pairs, two-stage envelope
  MODEL_CYMBAL,        // drum_voices.h
  MODEL_CLAP,
  MODEL_RIM,
  MODEL_COWBELL,
  MODEL_COUNT
};

typedef HiHat<SquareNoise, SwingVCA, true, false> SquareHat;
typedef HiHat<RingModNoise, LinearVCA, false, true> RingHat;

// A pad's voicing: what its knobs at their defaults play. note is the
// pitch (MIDI note number, fractions allowed), decay, tone, snap and sweep
// the model's own 0..1 controls at the knobs' middle (sweep is -1..1 on
// the models without a sweep of their own, below), drive what Drive adds
// to, gain the pad's level in the kit.
struct Voicing {
  uint8_t model;
  uint8_t choke;       // its pad's choke group, 0 for none (1: the hi-hats)
  float note, decay, tone, snap, sweep, drive, gain;
};

// Each model's output scaled to peak near full scale at its own voicing,
// struck at full velocity [measured: fm1-render, 2026-10-05]; the voicings'
// gains then balance the kit.
const float kModelGain[MODEL_COUNT] = {
  2.45f, 1.06f, 1.0f, 1.56f, 1.28f, 0.76f, 1.0f, 1.0f, 1.0f, 1.0f,
};

// What a pad given another model by its Model knob plays: the model's own
// voicing, so a cowbell on a tom's pad is a cowbell.
const Voicing kModelVoicing[MODEL_COUNT] = {
  { MODEL_ANALOG_DRUM, 0, 33.0f, 0.80f, 0.40f, 0.35f, 0.35f, 0.0f, 1.0f },
  { MODEL_PUNCH_DRUM,  0, 34.0f, 0.55f, 0.55f, 0.55f, 0.35f, 0.0f, 1.0f },
  { MODEL_SNARE,       0, 58.4f, 0.45f, 0.35f, 0.55f, 0.00f, 0.0f, 1.0f },
  { MODEL_SNAP_SNARE,  0, 55.0f, 0.50f, 0.70f, 0.60f, 0.30f, 0.0f, 1.0f },
  { MODEL_HAT,         0, 56.0f, 0.50f, 0.60f, 0.20f, 0.00f, 0.0f, 1.0f },
  { MODEL_RING_HAT,    0, 56.0f, 0.50f, 0.65f, 0.20f, 0.00f, 0.0f, 1.0f },
  { MODEL_CYMBAL,      0, 56.0f, 0.60f, 0.45f, 0.50f, 0.00f, 0.0f, 1.0f },
  { MODEL_CLAP,        0, 83.2f, 0.45f, 0.50f, 0.50f, 0.00f, 0.0f, 1.0f },
  { MODEL_RIM,         0, 69.6f, 0.35f, 0.50f, 0.40f, 0.00f, 0.0f, 1.0f },
  { MODEL_COWBELL,     0, 72.55f, 0.50f, 0.50f, 0.50f, 0.00f, 0.0f, 1.0f },
};

// The two kits, pad by pad in Sophie's order (General MIDI's drum keys).
// Deep: the long analogue kit. Punch: the synthetic kick and snare, the
// ring-modulated hats, shorter decays. Toms take their pitch from their
// key, a fourth up (41 sounds as 46).
const int kNumKits = 2;
const Voicing kKits[kNumKits][kNumPads] = {
  {  // Deep
    { MODEL_ANALOG_DRUM, 0, 33.0f, 0.80f, 0.40f, 0.35f, 0.35f, 0.0f, 1.00f },  // 36 Kick
    { MODEL_RIM,         0, 69.6f, 0.35f, 0.50f, 0.40f, 0.00f, 0.0f, 0.70f },  // 37 Rim
    { MODEL_SNARE,       0, 58.4f, 0.45f, 0.35f, 0.55f, 0.00f, 0.0f, 0.90f },  // 38 Snare
    { MODEL_CLAP,        0, 83.2f, 0.45f, 0.50f, 0.50f, 0.00f, 0.0f, 0.90f },  // 39 Clap
    { MODEL_SNAP_SNARE,  0, 55.0f, 0.50f, 0.70f, 0.60f, 0.30f, 0.0f, 0.85f },  // 40 Snare 2
    { MODEL_ANALOG_DRUM, 0, 46.0f, 0.55f, 0.45f, 0.45f, 0.25f, 0.0f, 0.90f },  // 41 Low Tom
    { MODEL_HAT,         1, 56.0f, 0.20f, 0.60f, 0.20f, 0.00f, 0.0f, 0.70f },  // 42 Closed HH
    { MODEL_ANALOG_DRUM, 0, 48.0f, 0.55f, 0.45f, 0.45f, 0.25f, 0.0f, 0.90f },  // 43 Floor Tom
    { MODEL_HAT,         1, 56.0f, 0.40f, 0.50f, 0.25f, 0.00f, 0.0f, 0.55f },  // 44 Pedal HH
    { MODEL_ANALOG_DRUM, 0, 50.0f, 0.52f, 0.45f, 0.45f, 0.25f, 0.0f, 0.85f },  // 45 Mid Tom
    { MODEL_HAT,         1, 56.0f, 0.62f, 0.60f, 0.20f, 0.00f, 0.0f, 0.65f },  // 46 Open HH
    { MODEL_ANALOG_DRUM, 0, 52.0f, 0.50f, 0.45f, 0.45f, 0.25f, 0.0f, 0.85f },  // 47 Low-Mid
    { MODEL_ANALOG_DRUM, 0, 53.0f, 0.50f, 0.45f, 0.45f, 0.25f, 0.0f, 0.85f },  // 48 High-Mid
    { MODEL_CYMBAL,      0, 56.0f, 0.60f, 0.45f, 0.50f, 0.00f, 0.0f, 0.60f },  // 49 Crash
    { MODEL_ANALOG_DRUM, 0, 55.0f, 0.48f, 0.45f, 0.45f, 0.25f, 0.0f, 0.80f },  // 50 High Tom
    { MODEL_CYMBAL,      0, 58.0f, 0.50f, 0.65f, 0.20f, 0.00f, 0.0f, 0.55f },  // 51 Ride
  },
  {  // Punch
    { MODEL_PUNCH_DRUM,  0, 34.0f, 0.55f, 0.55f, 0.55f, 0.35f, 0.15f, 1.00f },  // 36 Kick
    { MODEL_RIM,         0, 72.0f, 0.28f, 0.65f, 0.50f, 0.00f, 0.0f, 0.70f },   // 37 Rim
    { MODEL_SNAP_SNARE,  0, 55.0f, 0.50f, 0.75f, 0.60f, 0.35f, 0.0f, 0.90f },   // 38 Snare
    { MODEL_CLAP,        0, 81.0f, 0.40f, 0.60f, 0.55f, 0.00f, 0.0f, 0.90f },   // 39 Clap
    { MODEL_SNARE,       0, 57.0f, 0.40f, 0.80f, 0.60f, 0.00f, 0.0f, 0.85f },   // 40 Snare 2
    { MODEL_PUNCH_DRUM,  0, 46.0f, 0.45f, 0.50f, 0.50f, 0.40f, 0.0f, 0.85f },   // 41 Low Tom
    { MODEL_RING_HAT,    1, 56.0f, 0.22f, 0.65f, 0.20f, 0.00f, 0.0f, 0.70f },   // 42 Closed HH
    { MODEL_PUNCH_DRUM,  0, 48.0f, 0.45f, 0.50f, 0.50f, 0.40f, 0.0f, 0.85f },   // 43 Floor Tom
    { MODEL_RING_HAT,    1, 56.0f, 0.40f, 0.55f, 0.25f, 0.00f, 0.0f, 0.55f },   // 44 Pedal HH
    { MODEL_PUNCH_DRUM,  0, 50.0f, 0.43f, 0.50f, 0.50f, 0.40f, 0.0f, 0.85f },   // 45 Mid Tom
    { MODEL_RING_HAT,    1, 56.0f, 0.70f, 0.65f, 0.20f, 0.00f, 0.0f, 0.65f },   // 46 Open HH
    { MODEL_PUNCH_DRUM,  0, 52.0f, 0.42f, 0.50f, 0.50f, 0.40f, 0.0f, 0.80f },   // 47 Low-Mid
    { MODEL_PUNCH_DRUM,  0, 53.0f, 0.42f, 0.50f, 0.50f, 0.40f, 0.0f, 0.80f },   // 48 High-Mid
    { MODEL_CYMBAL,      0, 57.0f, 0.58f, 0.60f, 0.60f, 0.00f, 0.0f, 0.60f },   // 49 Crash
    { MODEL_PUNCH_DRUM,  0, 55.0f, 0.40f, 0.50f, 0.50f, 0.40f, 0.0f, 0.80f },   // 50 High Tom
    { MODEL_CYMBAL,      0, 60.0f, 0.50f, 0.75f, 0.15f, 0.00f, 0.0f, 0.55f },   // 51 Ride
  },
};

// Whether a model has a pitch sweep of its own (the kicks' self-FM and FM
// envelope, the synthetic snare's FM): there Sweep moves it, 0..1 about the
// voicing. On the others Sweep is a pitch envelope of ours, -1..1 about the
// voicing: up to 24 semitones from above (a drop) or below (a rise),
// falling back over about 20 ms.
inline bool NativeSweep(int model) {
  return model == MODEL_ANALOG_DRUM || model == MODEL_PUNCH_DRUM || model == MODEL_SNAP_SNARE;
}

// ---- parameters -----------------------------------------------------------------------

const char *const kPadNames[kNumPads] = {
  "1 Kick", "2 Rim", "3 Snare", "4 Clap", "5 Snare 2", "6 Low Tom",
  "7 Closed HH", "8 Floor Tom", "9 Pedal HH", "10 Mid Tom", "11 Open HH",
  "12 Low-Mid", "13 High-Mid", "14 Crash", "15 High Tom", "16 Ride",
};
const char *const kModelNames[MODEL_COUNT + 1] = {
  "Kit", "Analog Drum", "Punch Drum", "Snare", "Snap Snare", "Hat", "Ring Hat",
  "Cymbal", "Clap", "Rim", "Cowbell",
};
const char *const kKitNames[kNumKits] = { "Deep", "Punch" };

// New parameters go at the end, so existing indices keep their meaning.
enum Param {
  P_PAD, P_TUNE, P_DECAY, P_LEVEL,         // page 1: the pad
  P_TONE, P_SNAP, P_SWEEP, P_DRIVE,        // page 2: its sound
  P_MODEL, P_KIT, P_ACCENT, P_VOLUME,      // page 3: its model, and the kit's
  P_COUNT
};

// The per-pad FLOATs, P_TUNE .. P_DRIVE, kept per pad with their ramps.
const int kPadFloats = P_DRIVE - P_TUNE + 1;

// Uids (API v2) are fixed: never renumber one, and give a new parameter the
// next free uid.
const uint8_t kFloat = FM1_PARAM_CONTINUOUS | FM1_PARAM_POLY;
const uint8_t kLatch = FM1_PARAM_LATCH | FM1_PARAM_MOD;
const fm1_param_t kParams[P_COUNT] = {
  { "Pad",       FM1_PARAM_ENUM,  0, kNumPads - 1, 0, kPadNames, 0, 1, 0, FM1_UNIT_NONE, "Pad" },
  { "Tune",      FM1_PARAM_FLOAT, -24, 24, 0, NULL, 0, 2, kFloat, FM1_UNIT_SEMI, "Tune" },
  { "Decay",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 3, kFloat, FM1_UNIT_NONE, "Decay" },
  { "Level",     FM1_PARAM_FLOAT, 0, 1, 0.8f, NULL, 0, 4, kFloat, FM1_UNIT_NONE, "Level" },
  { "Tone",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 5, kFloat, FM1_UNIT_NONE, "Tone" },
  { "Snap",      FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 6, kFloat, FM1_UNIT_NONE, "Snap" },
  { "Sweep",     FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1, 7, kFloat, FM1_UNIT_NONE, "Sweep" },
  { "Drive",     FM1_PARAM_FLOAT, 0, 1, 0.0f, NULL, 1, 8, kFloat, FM1_UNIT_NONE, "Drive" },
  { "Model",     FM1_PARAM_ENUM,  0, MODEL_COUNT, 0, kModelNames, 2, 9, kLatch, FM1_UNIT_NONE, "Model" },
  { "Kit",       FM1_PARAM_ENUM,  0, kNumKits - 1, 0, kKitNames, 2, 10, kLatch, FM1_UNIT_NONE, "Kit" },
  { "Accent",    FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 2, 11, kFloat, FM1_UNIT_NONE, "Accent" },
  { "Volume",    FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 2, 12, kFloat, FM1_UNIT_NONE, "Vol" },
};

// A voice's per-note offsets: Tune .. Volume (Model and Kit are not POLY,
// so their indices are refused), and its pitch.
typedef NoteOffsets<P_TUNE, P_VOLUME - P_TUNE + 1> Offsets;

// ---- the instance ---------------------------------------------------------------------

constexpr size_t cmax(size_t a, size_t b) { return a > b ? a : b; }

const size_t kModelBytes = cmax(
    cmax(cmax(sizeof(AnalogBassDrum), sizeof(SyntheticBassDrum)),
         cmax(sizeof(AnalogSnareDrum), sizeof(SyntheticSnareDrum))),
    cmax(cmax(sizeof(SquareHat), sizeof(RingHat)),
         cmax(cmax(sizeof(drum_voices::Cymbal), sizeof(drum_voices::Clap)),
              cmax(sizeof(drum_voices::Rim), sizeof(drum_voices::Cowbell)))));

// Silence: a voice under this (-80 dBFS) for kQuietBlocks blocks (10 ms) ends.
const float kSilence = 1e-4f;
const uint32_t kQuietBlocks = 40;
// A choked voice fades over this many blocks (4 ms) and ends.
const uint32_t kChokeBlocks = 16;
// The generic pitch sweep: 24 semitones at full, falling with a 20 ms time
// constant, a factor per 12-sample block.
const float kSweepSemitones = 24.0f;
const float kSweepBlockDecay = 1.0f - static_cast<float>(kBlockSize) / (0.02f * kCorrectedSampleRate);
// The kit's output scale: a pad of gain 1 at Level 0.8, Volume 0.7 and full
// velocity peaks near 0.39 of full scale (-8 dB), so a few struck together
// stay under the host's bus limiter (tests/test_engine_drums.py).
const float kOutGain = 0.7f;

struct Pad {
  float value[kPadFloats];        // Tune .. Drive as the voices read them (ramped)
  fm1_smooth_t ramp[kPadFloats];
  uint8_t model;                  // the Model parameter: 0 the kit's, else model + 1
  uint32_t rng;                   // its noise generator's state
};

struct Voice {
  alignas(16) unsigned char mem[kModelBytes];   // the model's object
  int model;                      // what mem holds; -1: nothing yet
  const Voicing *voicing;         // the pad's voicing when it was struck (LATCH)
  uint8_t pad;
  uint8_t key;
  uint8_t choke;                  // its pad's choke group: 0 none
  bool active;
  bool trigger;                   // struck, not yet rendered
  float velocity;                 // 0..1
  float sweep_env;                // the generic sweep: 1 at the hit, falling
  float tone_lp;                  // the generic tone filter's state (Snap Snare)
  uint32_t age;
  uint32_t quiet;                 // blocks under kSilence
  uint32_t choked;                // 0, else blocks of the choke's fade done + 1
  Offsets note;                   // per-note offsets (set_param_note)
};

// What a voice plays this block, from its pad's values, the kit's and its
// offsets.
struct Controls {
  float tune, decay, level, tone, snap, sweep, drive;   // the pad's knobs
  float accent, volume;                                 // the kit's
};

// x mapped so that 0.5 gives `at`, 0 gives lo and 1 gives hi, linearly on
// either side.
inline float About(float at, float x, float lo, float hi) {
  return x < 0.5f ? lo + (at - lo) * (2.0f * x) : at + (hi - at) * (2.0f * x - 1.0f);
}

inline float Clamp01(float x) { return x < 0.0f ? 0.0f : (x > 1.0f ? 1.0f : x); }

// Drive: x itself at 0, then more of a soft clip of x pushed up to 8 times.
inline void Drive(float drive, float *out, size_t size) {
  if (drive <= 0.0f) return;
  const float g = 1.0f + 7.0f * drive;
  for (size_t i = 0; i < size; ++i) {
    out[i] += drive * (stmlib::SoftClip(g * out[i]) - out[i]);
  }
}

class Instance {
 public:
  // False when the resampler refuses the host's rate.
  bool Init(const fm1_host_t *host) {
    const bool ok =
        fm1_resampler_init(&resampler_, kCorrectedSampleRate, host->sample_rate) != 0;
    for (int i = 0; i < P_COUNT; ++i) value_[i] = kParams[i].def;
    fm1_smooth_init(smooth_, value_, P_COUNT);
    smooth_steps_ = fm1_smooth_steps(kCorrectedSampleRate, kBlockSize);
    focus_ = 0;
    kit_ = 0;
    for (int p = 0; p < kNumPads; ++p) {
      Pad &pad = pads_[p];
      for (int k = 0; k < kPadFloats; ++k) pad.value[k] = kParams[P_TUNE + k].def;
      fm1_smooth_init(pad.ramp, pad.value, kPadFloats);
      pad.model = 0;
      pad.rng = 0x21u + 0x9E3779B9u * static_cast<uint32_t>(p);
    }
    ramping_ = 0;
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      v.model = -1;
      v.voicing = &kModelVoicing[0];
      v.pad = v.key = v.choke = 0;
      v.active = v.trigger = false;
      v.velocity = 0.0f;
      v.sweep_env = 0.0f;
      v.tone_lp = 0.0f;
      v.age = v.quiet = v.choked = 0;
      v.note.Clear();
    }
    bend_ = 0.0f;
    clock_ = 0;
    memset(mix_, 0, sizeof(mix_));
    pending_ = 0;
    return ok;
  }

  void NoteOn(uint8_t key, uint8_t velocity) {
    if (velocity == 0 || key < kFirstNote || key >= kFirstNote + kNumPads) return;
    const int p = key - kFirstNote;
    const Pad &pad = pads_[p];
    const Voicing *kit = &kKits[kit_][p];
    const int model = pad.model ? pad.model - 1 : kit->model;
    const Voicing *voicing = model == kit->model ? kit : &kModelVoicing[model];
    const int choke = kit->choke;

    Voice *v = Allocate(p);
    // Struck again in its own voice with the same model, the pad's object
    // is excited again; anything else starts from a fresh one.
    if (!(v->active && v->pad == p && v->model == model)) Build(v, model);
    v->voicing = voicing;
    v->pad = static_cast<uint8_t>(p);
    v->key = key;
    v->choke = static_cast<uint8_t>(choke);
    v->velocity = velocity / 127.0f;
    v->trigger = true;
    v->active = true;
    v->sweep_env = 1.0f;
    v->age = ++clock_;
    v->quiet = 0;
    v->choked = 0;
    v->note.Clear();   // a new hit, a retrigger or a steal starts at no offset

    if (choke) {   // the group's other pads fade out
      for (int i = 0; i < kNumVoices; ++i) {
        Voice &o = voice_[i];
        if (&o != v && o.active && o.choke == choke && o.pad != p && !o.choked) o.choked = 1;
      }
    }
  }

  void NoteOff(uint8_t) { }   // a hit rings out for its decay

  void PitchBend(float semitones) { bend_ = semitones; }

  void SetParam(uint16_t index, float value) {
    if (index >= P_COUNT) return;
    value = fm1_param_clamp(&kParams[index], value);
    if (index == P_PAD) {
      focus_ = static_cast<int>(value + 0.5f);
    } else if (index >= P_TUNE && index <= P_DRIVE) {
      Pad &pad = pads_[focus_];
      const int k = index - P_TUNE;
      fm1_smooth_set(&pad.ramp[k], &pad.value[k], value, Sounding(focus_) ? smooth_steps_ : 0);
      if (pad.ramp[k].left) ramping_ |= 1u << focus_;
    } else if (index == P_MODEL) {
      pads_[focus_].model = static_cast<uint8_t>(value + 0.5f);
    } else if (index == P_KIT) {
      kit_ = static_cast<int>(value + 0.5f);
    } else {
      fm1_smooth_set(&smooth_[index], &value_[index], value, Sounding(-1) ? smooth_steps_ : 0);
    }
  }

  // The voice sounding `key` (one at most: a pad is struck again in its own
  // voice) takes the offset.
  void SetParamNote(uint8_t key, uint16_t index, float offset) {
    if (!Offsets::Normalise(kParams, index, &offset)) return;
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].key == key) voice_[i].note.Set(index, offset);
    }
  }

  // Each output sample pulls the 47,872.34 Hz mix the resampler needs for
  // it, rendering a new 12-sample block whenever the last one is used up.
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
  // Whether pad p sounds (p < 0: any pad): a change then ramps.
  bool Sounding(int p) const {
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && (p < 0 || voice_[i].pad == p)) return true;
    }
    return false;
  }

  // The voice for pad p: its own if it sounds, else a free one, else the one
  // furthest into a choke, else the oldest.
  Voice *Allocate(int p) {
    for (int i = 0; i < kNumVoices; ++i) {
      if (voice_[i].active && voice_[i].pad == p) return &voice_[i];
    }
    for (int i = 0; i < kNumVoices; ++i) {
      if (!voice_[i].active) return &voice_[i];
    }
    Voice *best = &voice_[0];
    for (int i = 1; i < kNumVoices; ++i) {
      Voice *v = &voice_[i];
      if (v->choked > best->choked || (v->choked == best->choked && v->age < best->age)) best = v;
    }
    return best;
  }

  // A fresh object for `model` in the voice: a new pad's voice, a steal, or
  // a pad whose model changed since it was struck.
  void Build(Voice *v, int model) {
    switch (model) {
      case MODEL_ANALOG_DRUM: (new (v->mem) AnalogBassDrum())->Init(); break;
      case MODEL_PUNCH_DRUM: (new (v->mem) SyntheticBassDrum())->Init(); break;
      case MODEL_SNARE: (new (v->mem) AnalogSnareDrum())->Init(); break;
      case MODEL_SNAP_SNARE: (new (v->mem) SyntheticSnareDrum())->Init(); break;
      case MODEL_HAT: (new (v->mem) SquareHat())->Init(); break;
      case MODEL_RING_HAT: (new (v->mem) RingHat())->Init(); break;
      case MODEL_CYMBAL: (new (v->mem) drum_voices::Cymbal())->Init(); break;
      case MODEL_CLAP: (new (v->mem) drum_voices::Clap())->Init(); break;
      case MODEL_RIM: (new (v->mem) drum_voices::Rim())->Init(); break;
      default: (new (v->mem) drum_voices::Cowbell())->Init(); break;
    }
    v->model = model;
    v->tone_lp = 0.0f;
  }

  Controls VoiceControls(const Voice &v) const {
    const Pad &pad = pads_[v.pad];
    Controls c;
    float *pad_out[kPadFloats] = { &c.tune, &c.decay, &c.level, &c.tone, &c.snap, &c.sweep,
                                   &c.drive };
    for (int k = 0; k < kPadFloats; ++k) {
      *pad_out[k] = v.note.Value(kParams, P_TUNE + k, pad.value[k]);
    }
    c.accent = v.note.Value(kParams, P_ACCENT, value_[P_ACCENT]);
    c.volume = v.note.Value(kParams, P_VOLUME, value_[P_VOLUME]);
    return c;
  }

  // One voice's block into out[]; returns its gain for the mix.
  float RenderVoice(Voice &v, float *out) {
    const Controls c = VoiceControls(v);
    const Voicing &w = *v.voicing;
    const bool trigger = v.trigger;
    v.trigger = false;

    // The class's accent: 0.8 (Plaits' with no LEVEL patched) at Accent 0,
    // the velocity itself at 1.
    const float accent = 0.8f + c.accent * (v.velocity - 0.8f);
    const float decay = About(w.decay, c.decay, 0.0f, 1.0f);
    const float tone = About(w.tone, c.tone, 0.0f, 1.0f);
    const float snap = About(w.snap, c.snap, 0.0f, 1.0f);
    const bool native_sweep = NativeSweep(v.model);
    const float sweep = native_sweep ? About(w.sweep, c.sweep, 0.0f, 1.0f)
                                     : About(w.sweep, c.sweep, -1.0f, 1.0f);
    float pitch = w.note + c.tune + bend_;
    if (v.note.has_pitch()) pitch += v.note.pitch;
    if (!native_sweep) {
      pitch += sweep * kSweepSemitones * v.sweep_env;
      v.sweep_env *= kSweepBlockDecay;
    }
    const float f0 = NoteToFrequency(pitch);
    // Our own voices draw from the pad's generator directly: the state the
    // caller swapped in, handed back after.
    uint32_t rng = stmlib::Random::state();

    switch (v.model) {
      case MODEL_ANALOG_DRUM:
        reinterpret_cast<AnalogBassDrum *>(v.mem)->Render(
            false, trigger, accent, f0, tone, decay, snap, sweep, out, kBlockSize);
        break;
      case MODEL_PUNCH_DRUM:
        // Plaits' coupling of the phase noise to the decay
        // (bass_drum_engine.cc), Snap as the FM envelope's depth and Sweep
        // as its length.
        reinterpret_cast<SyntheticBassDrum *>(v.mem)->Render(
            false, trigger, accent, f0, tone, decay, 0.4f - 0.25f * decay * decay, snap, sweep,
            out, kBlockSize);
        break;
      case MODEL_SNARE:
        reinterpret_cast<AnalogSnareDrum *>(v.mem)->Render(
            false, trigger, accent, f0, tone, decay, snap, out, kBlockSize);
        break;
      case MODEL_SNAP_SNARE: {
        reinterpret_cast<SyntheticSnareDrum *>(v.mem)->Render(
            false, trigger, accent, f0, sweep, decay, snap, out, kBlockSize);
        // No tone of its own: a one-pole low-pass, open at Tone 1.
        const float k = Clamp01(0.05f * stmlib::SemitonesToRatio(tone * 54.0f));
        for (size_t i = 0; i < kBlockSize; ++i) {
          ONE_POLE(v.tone_lp, out[i], k);
          out[i] = v.tone_lp;
        }
        break;
      }
      case MODEL_HAT:
        reinterpret_cast<SquareHat *>(v.mem)->Render(
            false, trigger, accent, f0, tone, decay, snap, temp_[0], temp_[1], out, kBlockSize);
        break;
      case MODEL_RING_HAT:
        reinterpret_cast<RingHat *>(v.mem)->Render(
            false, trigger, accent, f0, tone, decay, snap, temp_[0], temp_[1], out, kBlockSize);
        break;
      case MODEL_CYMBAL:
        reinterpret_cast<drum_voices::Cymbal *>(v.mem)->Render(
            trigger, accent, f0, tone, decay, snap, &rng, out, kBlockSize);
        stmlib::Random::Seed(rng);
        break;
      case MODEL_CLAP:
        reinterpret_cast<drum_voices::Clap *>(v.mem)->Render(
            trigger, accent, f0, tone, decay, snap, &rng, out, kBlockSize);
        stmlib::Random::Seed(rng);
        break;
      case MODEL_RIM:
        reinterpret_cast<drum_voices::Rim *>(v.mem)->Render(
            trigger, accent, f0, tone, decay, snap, &rng, out, kBlockSize);
        stmlib::Random::Seed(rng);
        break;
      default:
        reinterpret_cast<drum_voices::Cowbell *>(v.mem)->Render(
            trigger, accent, f0, tone, decay, snap, out, kBlockSize);
        break;
    }
    const float model_gain = kModelGain[v.model];
    for (size_t i = 0; i < kBlockSize; ++i) out[i] *= model_gain;
    Drive(Clamp01(w.drive + c.drive), out, kBlockSize);

    // Velocity: at Accent 1 the level follows its square, at 0 not at all.
    const float vel_gain = 1.0f - c.accent + c.accent * v.velocity * v.velocity;
    return c.level * w.gain * vel_gain * c.volume * kOutGain;
  }

  void RenderBlock() {
    fm1_smooth_tick(smooth_, value_, P_COUNT);   // this block's step of any ramp
    for (int p = 0; p < kNumPads; ++p) {
      if ((ramping_ >> p) & 1u) {
        if (!fm1_smooth_tick(pads_[p].ramp, pads_[p].value, kPadFloats)) ramping_ &= ~(1u << p);
      }
    }

    float mix[kBlockSize] = { 0 };
    const uint32_t global_rng = stmlib::Random::state();
    for (int i = 0; i < kNumVoices; ++i) {
      Voice &v = voice_[i];
      if (!v.active) continue;
      float out[kBlockSize];
      stmlib::Random::Seed(pads_[v.pad].rng);   // the pad's noise for Plaits' classes
      const float gain = RenderVoice(v, out);
      pads_[v.pad].rng = stmlib::Random::state();

      // A choke fades the voice out linearly over kChokeBlocks blocks.
      float g0 = gain, g1 = gain;
      if (v.choked) {
        g0 = gain * (1.0f - static_cast<float>(v.choked - 1) / kChokeBlocks);
        g1 = gain * (1.0f - static_cast<float>(v.choked) / kChokeBlocks);
        ++v.choked;
      }
      const float step = (g1 - g0) / kBlockSize;
      float peak = 0.0f;
      for (size_t n = 0; n < kBlockSize; ++n) {
        const float s = out[n] * (g0 + step * static_cast<float>(n + 1));
        mix[n] += s;
        const float a = s < 0.0f ? -s : s;
        if (a > peak) peak = a;
      }
      v.quiet = peak < kSilence ? v.quiet + 1 : 0;
      if (v.quiet >= kQuietBlocks || v.choked > kChokeBlocks) {
        v.active = false;
        v.choked = 0;
      }
    }
    stmlib::Random::Seed(global_rng);
    memcpy(mix_, mix, sizeof(mix_));
  }

  Voice voice_[kNumVoices];
  Pad pads_[kNumPads];
  float value_[P_COUNT];           // the kit's FLOATs as the blocks read them (SMOOTH)
  fm1_smooth_t smooth_[P_COUNT];
  uint32_t smooth_steps_;          // 12-sample blocks in a ramp
  uint32_t ramping_;               // bit p: pad p has a ramp to go
  int focus_;                      // Pad: the pad the per-pad parameters edit
  int kit_;                        // Kit
  float bend_;
  uint32_t clock_;
  float temp_[2][kBlockSize];      // the hi-hats' scratch
  float mix_[kBlockSize];          // the current block at 47,872.34 Hz
  size_t pending_;                 // samples of mix_ not yet resampled
  fm1_resampler_t resampler_;
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

}  // namespace drums
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_drums = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "drums", "Drums",
  "Kick, tom, snare and hi-hat voices from Mutable Instruments Plaits by "
  "Emilie Gillet (MIT); rim, clap, cowbell and cymbal from this repository "
  "(MIT), after Werner, Abel and Smith's TR-808 cowbell and cymbal models",
  fm1::drums::kParams, fm1::drums::P_COUNT, fm1::drums::kNumVoices,
  fm1::drums::InstanceSize, fm1::drums::Create, fm1::drums::Destroy,
  fm1::drums::NoteOn, fm1::drums::NoteOff, fm1::drums::Bend,
  fm1::drums::Set, fm1::drums::Render,
  fm1::drums::SetNote,
  // A pad kit: notes 36-51 play pads 1-16 (engines/README.md, "Pad kits").
  fm1::drums::kFirstNote, fm1::drums::kNumPads,
};

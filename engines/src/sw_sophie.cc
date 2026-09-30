// sw_sophie.cc -- "sw-sophie": Sophie, a Schwung sound generator by Matt
// Estela (github.com/mestela/schwung-sophie, MIT; vendored unmodified in
// third_party/schwung-modules/sophie), built through the Schwung v2 shim.
//
// Sophie is a 16-pad metallic FM percussion synth with 12 one-shot voices.
// MIDI notes 36-51 play pads 1-16; other notes are silent, and note-offs are
// ignored (each hit rings for its Decay). Every pad has its own patch; the
// knobs edit the pad chosen by "Pad", through the module's own compatibility
// alias (a bare key such as "tune" edits the focused pad). A triggered voice
// keeps a snapshot of its pad's patch.
//
// The table below mirrors the module's chain_params for pad 1 (whose values
// are the defaults shown while Pad is 1), in the knob order of the module's
// ui_pages. Names are the module's own without their "Pad 1 " prefix; only
// "Ring Fdbk" is shortened, to fit 12 characters. tests/test_engines_schwung.py
// checks all of it against the live chain_params. Only the first two pages are
// exposed for now, because the registry test allows pages 0 and 1 only
// (engines/schwung.md); the rest are defined and settable through the shim.
//
// MIT licence (this file).

#include "schwung_shim.h"

extern "C" plugin_api_v2_t *fm1_sw_sophie_init(const host_api_v1_t *host);

namespace fm1 {
namespace sw_sophie {

using namespace schwung;

const char *const kPadNames[16] = {
  "1 Kick", "2 Rim", "3 Snare", "4 Clap", "5 Snare 2", "6 Low Tom",
  "7 Closed HH", "8 Floor Tom", "9 Pedal HH", "10 Mid Tom", "11 Open HH",
  "12 Low-Mid", "13 High-Mid", "14 Crash", "15 High Tom", "16 Ride",
};
const char *const kModelNames[4] = { "Fuse", "Stack", "Split", "Shard" };
const char *const kFilterNames[5] = { "LPF", "HPF", "Notch", "DJ", "BPF" };

enum Param {
  P_PAD, P_TUNE, P_DECAY, P_MODEL,
  P_COLOR, P_METAL, P_FEEDBACK, P_SWEEP,
  P_CRUSH, P_DRIVE, P_LEVEL, P_CUTOFF,
  P_RESONANCE, P_FILTER,
  P_RING_TIME, P_RING_FDBK, P_RING_MIX, P_RING_TONE,
  P_COUNT
};

const uint16_t kExposed = P_CRUSH;   // pages 0 and 1

const fm1_param_t kParams[P_COUNT] = {
  { "Pad",       FM1_PARAM_ENUM,  0, 15, 0, kPadNames, 0 },
  { "Tune",      FM1_PARAM_FLOAT, -24, 24, -5, NULL, 0 },
  { "Decay",     FM1_PARAM_FLOAT, 0.03f, 4, 0.28f, NULL, 0 },
  { "Model",     FM1_PARAM_ENUM,  0, 3, 0, kModelNames, 0 },
  { "Color",     FM1_PARAM_FLOAT, 0, 100, 24, NULL, 1 },
  { "Metal",     FM1_PARAM_FLOAT, 0, 100, 8, NULL, 1 },
  { "Feedback",  FM1_PARAM_FLOAT, 0, 100, 6, NULL, 1 },
  { "Sweep",     FM1_PARAM_FLOAT, -100, 100, 55, NULL, 1 },
  { "Crush",     FM1_PARAM_FLOAT, 0, 100, 0, NULL, 2 },
  { "Drive",     FM1_PARAM_FLOAT, 0, 100, 58, NULL, 2 },
  { "Level",     FM1_PARAM_FLOAT, 0, 100, 100, NULL, 2 },
  { "Cutoff",    FM1_PARAM_FLOAT, 0, 100, 100, NULL, 2 },
  { "Resonance", FM1_PARAM_FLOAT, 0, 100, 0, NULL, 3 },
  { "Filter Type", FM1_PARAM_ENUM, 0, 4, 0, kFilterNames, 3 },
  { "Ring Time", FM1_PARAM_FLOAT, 0.5f, 30, 6, NULL, 4 },
  { "Ring Fdbk", FM1_PARAM_FLOAT, 0, 95, 0, NULL, 4 },
  { "Ring Mix",  FM1_PARAM_FLOAT, 0, 100, 0, NULL, 4 },
  { "Ring Tone", FM1_PARAM_FLOAT, 0, 100, 70, NULL, 4 },
};

const ParamKey kKeys[P_COUNT] = {
  { "focused_pad", VALUE_INDEX, 1 },     // 1-based int
  { "tune", VALUE_FLOAT, 0 },
  { "decay", VALUE_FLOAT, 0 },
  { "model", VALUE_INDEX, 0 },
  { "color", VALUE_FLOAT, 0 },
  { "metal", VALUE_FLOAT, 0 },
  { "feedback", VALUE_FLOAT, 0 },
  { "sweep", VALUE_FLOAT, 0 },
  { "crush", VALUE_FLOAT, 0 },
  { "drive", VALUE_FLOAT, 0 },
  { "level", VALUE_FLOAT, 0 },
  { "cutoff", VALUE_FLOAT, 0 },
  { "resonance", VALUE_FLOAT, 0 },
  { "filter_type", VALUE_INDEX, 0 },
  { "ring_time", VALUE_FLOAT, 0 },
  { "ring_feedback", VALUE_FLOAT, 0 },
  { "ring_mix", VALUE_FLOAT, 0 },
  { "ring_tone", VALUE_FLOAT, 0 },
};

// create_instance makes one calloc of 76,752 bytes: the 12 voices, each with a
// 1,536-sample ring delay, and the 16 pad patches. The struct has no pointers,
// so the size is the same on 32-bit targets. With the arena's 16-byte header
// that is 76,768 bytes; the selftest fails if it outgrows this.
const size_t kArenaBytes = 75 * 1024;

ModuleState g_state;

const Module kModule = {
  FM1_KIND_SOUND, "sophie", fm1_sw_sophie_init, NULL,
  kParams, kKeys, kExposed, P_COUNT, kArenaBytes,
  0.0f,                                   // Sophie ignores pitch bend
  1.0f,                                   // no headroom: not an effect
  &g_state,
};

size_t Size(const fm1_host_t *host) { return InstanceSize(kModule, host); }
void *New(void *mem, const fm1_host_t *host) { return Create(kModule, mem, host); }

}  // namespace sw_sophie
}  // namespace fm1

extern "C" const fm1::schwung::Module *const fm1_sw_sophie_module = &fm1::sw_sophie::kModule;

extern "C" const fm1_engine_t fm1_engine_sw_sophie = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_SOUND,
  "sw-sophie", "Sophie",
  "Sophie by Matt Estela (github.com/mestela/schwung-sophie, MIT), "
  "via the Schwung v2 shim (Schwung plugin ABI by Charles Vestal, MIT)",
  fm1::sw_sophie::kParams, fm1::sw_sophie::kExposed, 12,
  fm1::sw_sophie::Size, fm1::sw_sophie::New, fm1::schwung::Destroy,
  fm1::schwung::NoteOn, fm1::schwung::NoteOff, NULL,
  fm1::schwung::SetParam, fm1::schwung::Render,
};

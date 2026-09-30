// sw_psxverb.cc -- "sw-psxverb": PSX Verb, a Schwung audio effect by Charles
// Vestal (github.com/charlesvestal/schwung-psxverb, MIT; vendored unmodified
// in third_party/schwung-modules/psxverb), built through the Schwung v2 shim.
//
// PSX Verb follows the PlayStation SPU reverb as documented in psx-spx: the
// input is decimated to half rate, runs through same- and cross-side
// reflections, four combs and two all-passes in a 16-bit work area, and is
// interpolated back. Six register presets (Room .. Space Echo), a decay that
// scales the wall reflection, and dry/wet, input and output levels.
//
// The table mirrors the module's chain_params (and module.json), in the knob
// order of its ui_hierarchy, followed by the one parameter that is not on a
// knob there. tests/test_engines_schwung.py checks it against the module.
//
// MIT licence (this file).

#include "schwung_shim.h"

extern "C" audio_fx_api_v2_t *fm1_sw_psxverb_init(const host_api_v1_t *host);

namespace fm1 {
namespace sw_psxverb {

using namespace schwung;

const char *const kModelNames[6] = {
  "Room", "Studio S", "Studio M", "Studio L", "Hall", "Space Echo",
};

enum Param { P_MODEL, P_DECAY, P_MIX, P_LEVEL, P_INPUT, P_COUNT };

const fm1_param_t kParams[P_COUNT] = {
  { "Model", FM1_PARAM_ENUM,  0, 5, 4, kModelNames, 0 },
  { "Decay", FM1_PARAM_FLOAT, 0, 1, 0.7f, NULL, 0 },
  { "Mix",   FM1_PARAM_FLOAT, 0, 1, 0.35f, NULL, 0 },
  { "Level", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Input", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 1 },
};

const ParamKey kKeys[P_COUNT] = {
  { "model", VALUE_INDEX, 0 },
  { "decay", VALUE_FLOAT, 0 },
  { "mix", VALUE_FLOAT, 0 },
  { "reverb_level", VALUE_FLOAT, 0 },
  { "input_gain", VALUE_FLOAT, 0 },
};

// create_instance makes two callocs: the instance (filter states and presets,
// 1,280 bytes on a 64-bit host, a few bytes less on 32-bit) and the SPU work
// area, a fixed 65,536 int16 samples (128 KB) whatever the preset. With the
// arena's 16-byte headers that is 132,384 bytes; the selftest fails if it
// outgrows this.
const size_t kArenaBytes = 130 * 1024;

const Module kModule = {
  FM1_KIND_AUDIO_FX, "psxverb", NULL, fm1_sw_psxverb_init,
  kParams, kKeys, P_COUNT, P_COUNT, kArenaBytes, 0.0f,
};

size_t Size(const fm1_host_t *host) { return InstanceSize(kModule, host); }
void *New(void *mem, const fm1_host_t *host) { return Create(kModule, mem, host); }

}  // namespace sw_psxverb
}  // namespace fm1

extern "C" const fm1::schwung::Module *const fm1_sw_psxverb_module = &fm1::sw_psxverb::kModule;

extern "C" const fm1_engine_t fm1_engine_sw_psxverb = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "sw-psxverb", "PSX Verb",
  "PSX Verb by Charles Vestal (github.com/charlesvestal/schwung-psxverb, MIT), "
  "via the Schwung v2 shim (Schwung plugin ABI by Charles Vestal, MIT)",
  fm1::sw_psxverb::kParams, fm1::sw_psxverb::P_COUNT, 0,
  fm1::sw_psxverb::Size, fm1::sw_psxverb::New, fm1::schwung::Destroy,
  NULL, NULL, NULL,
  fm1::schwung::SetParam, fm1::schwung::Render,
};

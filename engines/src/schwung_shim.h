// schwung_shim.h -- the Schwung v2 compatibility shim (docs/11 §3,
// engines/schwung.md).
//
// A Schwung module is a sound generator (plugin_api_v2_t) or an audio effect
// (audio_fx_api_v2_t): plain C function tables with string-keyed parameters,
// 16-bit stereo audio and blocks of up to 128 frames. The shim turns one such
// module, compiled from source into the firmware, into an fm1_engine_t:
//
//   - a stub host_api_v1_t (rate and block size from the first fm1_host_t,
//     logging and MIDI out as no-ops, no mailbox, no clock);
//   - the module's init called once, by its first create, as Schwung calls it
//     once per dlopen; later creates reuse the API table it returned;
//   - the module's calloc/malloc in create_instance served from a bounded bump
//     arena inside the fm1 instance memory (schwung_module_prefix.h), and its
//     atof/strtod/strtof from a heap-free parser here;
//   - fm1 note and pitch-bend calls sent to on_midi as 3-byte MIDI;
//   - typed fm1 parameters turned into the key/value strings set_param expects;
//   - the module always called with the same block size, re-blocked to the
//     host's frame counts (sound generators render ahead; effects go through a
//     one-block FIFO, with optional headroom around the int16 conversion).
//
// Threads: create and destroy come from one control task, never two at once;
// render, note and parameter calls may run on an audio task meanwhile. After
// the first create, a create writes only its own instance memory and the
// module's arena, never anything a running instance reads.
//
// Each module adds a small adapter (sw_<id>.cc): a static fm1_param_t table,
// the matching Schwung keys, a ModuleState, a Module descriptor, and an
// fm1_engine_t whose instance_size and create are thunks into InstanceSize and
// Create below. MIT licence.
#ifndef FM1_SCHWUNG_SHIM_H_
#define FM1_SCHWUNG_SHIM_H_

#include "fm1_engine.h"
#include "schwung_abi.h"

extern "C" {
// The arena allocator that schwung_module_prefix.h redirects module
// allocations to. Outside create_instance every call fails (returns NULL).
void *fm1_sw_malloc(size_t size);
void *fm1_sw_calloc(size_t count, size_t size);
void *fm1_sw_realloc(void *ptr, size_t size);
void fm1_sw_free(void *ptr);
// What the prefix maps atof/strtod/strtof to: decimal only (optional sign,
// digits, fraction, exponent; no hex, inf or nan), at most 9 significant
// digits, single precision, no heap and no locale. Within one ulp of the C
// library's strtof for the strings the shim writes.
float fm1_sw_strtof(const char *s, char **end);
}

namespace fm1 {
namespace schwung {

// How an fm1 parameter value becomes the string the module's set_param reads.
enum ValueFormat {
  VALUE_FLOAT = 0,  // the value with six decimals, e.g. "0.350000"
  VALUE_INDEX = 1   // the rounded value plus `offset`, as an integer, e.g. "4"
};

struct ParamKey {
  const char *key;      // the module's parameter key
  ValueFormat format;
  int offset;           // VALUE_INDEX: added to the index (1 for a 1-based int)
};

typedef plugin_api_v2_t *(*SoundInitFn)(const host_api_v1_t *host);
typedef audio_fx_api_v2_t *(*FxInitFn)(const host_api_v1_t *host);

// What the shim remembers about one module: the API table its init returned.
// Module init functions rewrite their own static tables (PSX Verb memsets its
// table), so init runs once, by the module's first create, while no instance
// of it exists. A zero-initialised static in the adapter; written only by
// creates. Exactly one Module (and one ModuleState) per init function.
struct ModuleState {
  plugin_api_v2_t *sound;       // the table init returned, once ready
  audio_fx_api_v2_t *fx;
  uint32_t inits;               // times init was called (1 once ready)
  bool ready;
};

struct Module {
  fm1_kind_t kind;              // FM1_KIND_SOUND or FM1_KIND_AUDIO_FX
  const char *id;               // the Schwung module id
  SoundInitFn sound_init;       // move_plugin_init_v2, renamed at build time
  FxInitFn fx_init;             // move_audio_fx_init_v2, renamed at build time
  const fm1_param_t *params;    // shared with the module's fm1_engine_t
  const ParamKey *keys;         // one per params entry
  uint16_t n_params;            // entries the fm1_engine_t exposes
  uint16_t n_defined;           // entries in params/keys (>= n_params)
  size_t arena_bytes;           // what create_instance may allocate, in total
  float bend_range;             // semitones at full MIDI bend; 0 = none sent
  // Effects: the float bus is divided by this on its way into int16 and
  // multiplied by it on the way back, so peaks up to this level pass the
  // module instead of saturating at full scale ahead of the host's limiter.
  // 1 (or less) = none; a power of two keeps the round trip exact. Costs one
  // bit of the module's 16 per doubling. Ignored for sound generators.
  float fx_headroom;
  ModuleState *state;           // this module's once-only state
};

// The fm1_engine_t callbacks. Render overwrites out_lr for a sound generator
// and processes it in place for an effect.
size_t InstanceSize(const Module &m, const fm1_host_t *host);
void *Create(const Module &m, void *mem, const fm1_host_t *host);
void Destroy(void *self);
void NoteOn(void *self, uint8_t key, uint8_t velocity);
void NoteOff(void *self, uint8_t key);
void PitchBend(void *self, float semitones);
void SetParam(void *self, uint16_t index, float value);
void Render(void *self, float *out_lr, uint32_t frames);

// Beyond the fm1 API: for tools, tests and a later UI.
size_t InstanceBytes(size_t arena_bytes);   // InstanceSize for a given arena
void *CreateWithArena(const Module &m, void *mem, const fm1_host_t *host,
                      size_t arena_bytes);
int GetParam(void *self, const char *key, char *buf, int buf_len);
uint32_t BlockFrames(void *self);           // frames per module call
// The module block a host's max_frames gives: even, 2..128. The first create
// fixes it (and the rate) for every module; a later host with another
// max_frames gets that block, and one with another rate is refused.
uint32_t BlockFor(uint32_t max_frames);
// The one host_api_v1_t every module's init sees; NULL before the first create.
const host_api_v1_t *HostApi();

struct ArenaStats {
  size_t capacity;
  size_t used;                  // bytes taken, headers and alignment included
  uint32_t allocations;
  uint32_t failures;            // refused because the arena was full
};
bool GetArenaStats(void *self, ArenaStats *out);

const char *LastError();          // why the last Create returned NULL, or ""
uint32_t LateAllocations();       // allocations tried outside create_instance

}  // namespace schwung
}  // namespace fm1

#endif  // FM1_SCHWUNG_SHIM_H_

// render_state.h -- fm1-render's --load and --save (stage E3; engines/state/
// README.md): state files to the renderer's units, levels, MIDI effects,
// effects chain, FM6 voices, modulation and set, and back. It stands in for
// the app's collector and applier (stage A1) on the desktop. MIT licence.
#ifndef RENDER_STATE_H_
#define RENDER_STATE_H_

#include "fm1_engine.h"
#include "fm1_mod.h"
#include "fm1_seq.h"
#include "fm1_state.h"

#include <array>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

namespace render_state {

typedef std::vector<std::pair<std::string, float> > Params;

// A unit as the renderer keeps it: its engine id and the parameters it sets,
// in order (a pad kit's per-pad values follow its Pad, the focus last).
struct UnitIn {
  std::string id;           // "" for none
  Params params;
  bool on = false;          // a MIDI effect's
};

// What a file gives the renderer.
struct Loaded {
  int kind = 0;
  bool any_slot = false;    // sounds 2-4, inserts, levels or MIDI effects: --slots
  UnitIn sound[4];
  bool has_sound[4] = { false, false, false, false };
  std::vector<UnitIn> inserts[4];
  std::vector<UnitIn> mfx[4];
  float level[4] = { 100.0f, 100.0f, 100.0f, 100.0f };
  bool has_level[4] = { false, false, false, false };
  std::vector<UnitIn> master;          // the --fx chain
  std::vector<std::pair<unsigned, std::array<uint8_t, 155> > > dx7;
  bool has_mod = false, has_seed = false;
  uint32_t seed = 0;
  std::vector<fm1_rec_t> mod;          // MODULE, module PARAM and CABLE records, remapped
  std::vector<std::string> mod_names;  // the cables' kept names, by mod index
  std::string set;                     // movy1 text
  std::vector<std::string> clip;       // a clip's lines (track 0, slot 0)
  int clip_track = -1, clip_slot = -1;
};

// --load [sK:|tT.S:]FILE: reads a project, sound (into sound unit K, 1-4),
// effects chain, mod rack, clip (into track T, slot S, 1-based) or settings
// file, JSON or binary, in two passes (§10.1): the first refuses an engine
// or kind this build lacks (UNKNOWN, unless `without`), and instances past
// the budget at 44,118 Hz (RAM, always). Merges into `into` (a sound's
// modules and cables into free places). false with a message on refusal.
bool Load(const std::string &spec, bool without, Loaded *into, std::string *err);

// What the renderer has, for --save.
struct UnitOut {
  const fm1_engine_t *e = NULL;
  const Params *params = NULL;
  bool on = false;
};
struct Have {
  UnitOut sound[4];
  std::vector<UnitOut> inserts[4];
  std::vector<UnitOut> mfx[4];
  float level[4];
  std::vector<UnitOut> fx;
  std::vector<std::pair<unsigned, std::array<uint8_t, 155> > > dx7;
  const fm1_mod_t *mod = NULL;
  uint32_t seed = 0;
  const fm1_seq_t *seq = NULL;
};

// --save KIND:FILE: project, sound[K] (sound unit K, 1-4), fx (the --fx
// chain), mods, set (movy1 text), clip:T.S; a FILE ending in .lunarb is
// written binary, any other canonical JSON. The state is the one the render
// starts from. SEAM(E2): a pad kit's pads the render never set are written
// with the parameter's default until engine API v4's get_param reads them.
bool Save(const std::string &spec, const Have &have, std::string *err);

// The DX7 voices of .syx files, as fm1-render --sysex stores them.
void Sysex(const std::vector<std::string> &paths,
           std::vector<std::pair<unsigned, std::array<uint8_t, 155> > > *out);

}  // namespace render_state

#endif  // RENDER_STATE_H_

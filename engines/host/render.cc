// render.cc -- desktop host for the engine API (docs/11 §8, stage A).
//
//   fm1-render --list
//   fm1-render --engine macro --param Model=6 --param Timbre=0
//              --note 0:69:100:1.5 --seconds 2 --out a4.wav   (one command)
//
// --list prints every engine and MIDI effect and its parameters as JSON, with the names of
// an enum parameter's values and each parameter's API v2 fields: uid, flags
// (by name), unit and abbr, whether the engine takes per-note offsets
// (per_note: it has set_param_note), what an effect asks of API v3's
// extension (fx_wants: key, tempo, transport; render_ext: it has one), and
// its pads when it is a pad kit (pads: first note and count, or null).
//
// Renders in max_frames blocks at the FM-1's rate (44,118 Hz, 64 frames),
// passes the mix through the host's bus limiter (fm1_mix_limiter.h), writes
// 16-bit stereo WAV, and prints one line of JSON: the engine's raw peak and
// clipped count, the same after the limiter, non-finite samples, instance
// size in bytes and time per block. Note, bend (--bend) and parameter
// (--param-at, and --fx-param-at T:K:NAME=VALUE for the K-th --fx, counted
// from 1) events apply at block boundaries (1.45 ms). Per-note offsets
// (--note-param-at T:KEY:NAME=OFFSET on a POLY parameter, or #INDEX=OFFSET
// to send any index, as a test of what an engine ignores; --note-pitch-at
// T:KEY:SEMITONES) apply at block boundaries too, after the note-ons there,
// as a host sends a new note's offsets right after its note-on (set_param_note
// in fm1_engine.h); they go to the --engine (sound unit 0). --fill sets the
// byte instance memory holds before create (the API promises no zeroing);
// --fault T:VALUE overwrites both channels with VALUE (nan, inf, 1e6...) at
// time T, and --fault T0..T1:VALUE every frame from T0 up to T1, after the
// source and before the effects, to test recovery from bad samples. The
// timing is the desktop's and says nothing about pi32v2; it only catches
// regressions.
//
// The sequencer (engines/seq.md): --cmd FILE plays a timed Movy verb script
// (host/seq_script.h) through the fm1_seq core, --seq FILE.movy1 loads a set
// first, --log-events FILE.jsonl writes every sequencer event, --compat
// selects Movy's exact behaviour, --tracks N sizes it, --events N sizes the
// event buffer each block's commands and advance share (default 65,536). Each
// track goes to the sound engine or to USB-MIDI (logged only): by default
// track 0 plays the engine when there is one, or --route T:engine / --route
// T:midi:CH. Notes and locks reach the engine at their own frame: the block is
// rendered in pieces split at event frames. A lock sets the engine parameter
// its lane's label names (`target:Name`, matched by name and resolved to the
// parameter's uid when the lane is labelled), scaled from 0..127; a lock on a
// NOLOCK parameter is refused. All of that per-block hosting, and the routing
// default above, is the shared bridge (include/fm1_seq_host.h). So is the
// metronome's click (owner decision O11; fm1_seq_click_mix): while `metro`
// is on, each CLICK event sounds a short integer-only click at its own
// frame, added after the effects and before the limiter, as the virtual
// FM-1 adds it. The summary adds seq_dropped (events past the buffer),
// seq_max_block_events, seq_splits (render calls that start inside a block),
// seq_locks_refused (locks on NOLOCK parameters) and seq_clicks (clicks
// sounded).
//
// Several sound units, as the virtual FM-1 runs them
// (docs/15 §3.16): --sound K:ID loads sound unit K (1..3; --engine is unit
// 0), --sound-param K:NAME=VALUE sets one of its parameters, --insert K:ID
// adds an insert effect to unit K's chain (in order) and --insert-param
// K:NAME=VALUE sets one of the last insert's on unit K, --level K:PCT sets
// unit K's level into the mix (0..100, default 100), and --sound-note
// K:T:KEY:VEL:DUR, --sound-param-at K:T:NAME=VALUE and --level-at K:T:PCT are
// --note, --param-at and a level change for unit K. Any of these, or
// --slots, turns slots on: a track routed to the engine plays the unit its
// route index names (`route t 1 K`), not unit 0 whatever the index, and an
// empty unit plays nothing (a --sound-note to it included); --input is not
// taken with slots. Each unit renders its own block (split at its
// own tracks' events, fm1_seq_host_dispatch_slots), through its inserts,
// times its level (PCT / 100, skipped at 100), and the units are summed in
// order (the first one copied, the rest added) before --fault, the --fx
// chain and the limiter. With unit 0 alone, no insert and level 100, that is
// the plain render to the sample.
//
// Modulation (docs/16, include/fm1_mod.h): --mod FILE sets up the rack of
// modules and the matrix's slots from a text file (host/mod_script.h; a line
// may start with @FRAME to apply at the first block that starts there),
// --log-mod FILE.jsonl writes every tick, --list-mod prints the module kinds,
// the system sources and the host parameters as JSON. The runtime runs as
// the bridge's control-rate hook, with or without the sequencer: notes,
// locks and the clock feed its sources, each tick runs at its own frame,
// and a render is split only where a tick writes a value (the sound's
// parameters and HOST PITCH inside the bridge, the effects' and HOST AMP
// here; HOST AMP applies before the click). --param-at, --fx-param-at and
// --bend go through the bases (rule M1). With no slot on, every render is
// byte-identical to one without --mod. The summary adds mod_* counters.
// With slots (docs/16 MG3) the runtime runs over every sound unit
// (fm1_seq_host_dispatch_slots_ticks): every note on a unit with an engine
// feeds its sources, and every unit is a destination: sound unit K as snd
// (K 0) or sndK+1, its first two inserts as sndK+1.fx1 and .fx2 (each
// rendered split at its own writes), the first two --fx as fx1 and fx2;
// --param-at and --sound-param-at move the units' bases, --bend HOST
// PITCH's, which bends sound unit 0.
//
// DX7 voice data (engines/include/fm1_dx7.h): --sysex FILE loads a .syx
// file's voices into the FM6 engine's user slots (--engine dx7, sound unit
// 0), before the first block: a 32-voice bank fills User 1..32, single
// voices go to User 1, 2... in the order given, counted across files. Each
// file's result is printed on stderr, one line: the file, the voices, the
// first slot, bad checksums and skipped messages, and the names stored.
//
// MIDI effects (engine API v3, FM1_KIND_MIDI_FX; include/fm1_mfx_host.h):
// --mfx K:ID puts MIDI effect ID (the arpeggiator, `arp`) in front of sound
// unit K (0 is --engine; 1..3 imply --slots), in the next of its chain's
// four slots, on (K:ID:off: bypassed, as the virtual FM-1 keeps each sound's
// arpeggiator until ARP switches it on); --mfx-param K:NAME=VALUE sets a parameter of unit K's last
// --mfx; --mfx-param-at K[.J]:T:NAME=VALUE and --mfx-on-at K[.J]:T:0|1 change
// one or bypass it (0) or switch it on (1) at time T, J its place in the
// chain from 1 (default 1), with the other controls, before the block's
// notes. Every note for the unit goes through the chain while one of its
// effects is on: --note and --sound-note (taken at the block they start in,
// at its first frame) and the sequencer's (at their frames); a note-off
// follows its note-on, so a bypass leaves no note hanging, and a bypass
// flushes the effect at once. The ticks are the sequencer's clock (--cmd,
// --seq), which runs on at its tempo while stopped, or --tempo without one;
// Start resets the effects, and Stop takes back the sequencer's notes from
// them (STOP: what was played live plays on). --log-mfx FILE.jsonl writes
// what the chains send their sounds, by frame and then unit (so the same at
// any block size). The summary adds mfx_* counters and
// notes_hung, the engines' note-ons still without a note-off at the end.
//
// Effects with engine API v3's extension (fm1_engine.h, render_ext): every
// effect renders through fm1_fx_render (include/fm1_fx_host.h), which calls
// a v2 effect's render as before and gives an extended one the tempo, its
// beats and the transport's Start and Stop from the sequencer (--cmd,
// --seq), each at the first frame of a piece, or --tempo BPM (default 120)
// without a sequencer; the key input is NULL (the effect's own input) until
// the side-chain stage.
//
// MIT licence.

#include "fm1_dx7.h"
#include "fm1_engine.h"
#include "fm1_fx_host.h"
#include "fm1_mfx_host.h"
#include "fm1_mix_limiter.h"
#include "fm1_mod.h"
#include "fm1_mod_host.h"
#include "fm1_seq.h"
#include "fm1_seq_host.h"
#include "mod_script.h"
#include "seq_script.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <strings.h>

namespace {

struct Event {
  double time;
  bool on;
  uint8_t key;
  uint8_t velocity;
  int sound;                         // the sound unit it plays (--sound-note), else 0
};

struct Control {                     // --bend and --param-at: one call at a time
  double time;
  bool bend;                         // pitch_bend(value), else set_param(index, value)
  std::string name;
  uint16_t index;
  float value;
  bool done;
  int sound;                         // the sound unit (--sound-param-at, --level-at), else 0
  bool level;                        // --level-at: the unit's level, not a parameter
};

struct NoteControl {                 // --note-param-at and --note-pitch-at
  double time;
  uint8_t key;
  std::string name;                  // "" for the pitch; "#N" sends index N as is
  uint16_t index;
  float offset;
  bool done;
};

const int kSounds = 4;               // sound units, as the virtual FM-1's FM1_APP_SOUNDS

// The engines' notes, per sound unit and key: note-ons not yet ended
// (notes_hung in the summary).
uint32_t g_sounding[kSounds][128];

struct MfxControl {                  // --mfx-param-at, --mfx-on-at
  double time;
  int sound, slot;                   // the unit and its chain's slot (from 0)
  bool on_off;                       // --mfx-on-at: `value` is 0 or 1
  std::string name;
  uint16_t index;
  float value;
  bool done;
};

struct FxControl {                   // --fx-param-at: an effect's set_param
  double time;
  size_t unit;                       // index into the chain (K - 1)
  std::string name;
  uint16_t index;
  float value;
  bool done;
};

void Usage() {
  fprintf(stderr,
      "usage: fm1-render --list\n"
      "       fm1-render [--engine ID [--param NAME=VALUE]... [--note T:KEY:VEL:DUR]...\n"
      "                   [--bend T:SEMITONES]... [--param-at T:NAME=VALUE]...\n"
      "                   [--note-param-at T:KEY:NAME=OFFSET]... [--note-pitch-at T:KEY:SEMITONES]...]\n"
      "                  [--input silence|impulse|noise|sine]\n"
      "                  [--fx ID [--fx-param NAME=VALUE]...]... [--fx-param-at T:K:NAME=VALUE]...\n"
      "                  [--seconds S] [--rate HZ] [--frames N] [--out FILE.wav]\n"
      "                  [--fill BYTE] [--fault T[..T1]:VALUE]...\n"
      "                  [--cmd FILE] [--seq FILE.movy1] [--log-events FILE.jsonl]\n"
      "                  [--compat] [--tracks N] [--route T:engine|T:midi:CH]...\n"
      "                  [--events N]\n"
      "                  [--sound K:ID [--sound-param K:NAME=VALUE]...] [--insert K:ID\n"
      "                   [--insert-param K:NAME=VALUE]...] [--level K:PCT] [--slots]\n"
      "                  [--sound-note K:T:KEY:VEL:DUR] [--sound-param-at K:T:NAME=VALUE]\n"
      "                  [--level-at K:T:PCT] [--mod FILE] [--log-mod FILE.jsonl]\n"
      "                  [--sysex FILE.syx]... [--tempo BPM]\n"
      "                  [--mfx K:ID[:off] [--mfx-param K:NAME=VALUE]...]\n"
      "                  [--mfx-param-at K[.J]:T:NAME=VALUE]... [--mfx-on-at K[.J]:T:0|1]...\n"
      "                  [--log-mfx FILE.jsonl]\n"
      "       fm1-render --list-mod\n"
      "The source is the sound engine, or --input when there is none; each --fx\n"
      "processes it in order, then the bus limiter. --cmd and --seq drive the\n"
      "engine from the sequencer. --sound and the flags after it add sound units\n"
      "1..3, each with its inserts and level, mixed before the --fx chain.\n"
      "--mod modulates the sound units, their first two inserts, the first two\n"
      "effects and the host. --mfx puts MIDI effects in front of a sound unit.\n");
}

// The sequencer side of a render (--cmd, --seq).
struct Route {
  int track;
  bool engine;
  int channel;
};

struct Sequencer {
  std::vector<unsigned char> mem;
  fm1_seq_t *seq = NULL;
  fm1_script_t script;
  size_t next_cmd = 0;
  std::vector<fm1_seq_ev_t> ev;
  fm1_seq_host_t host;               // the bridge over seq and ev
  FILE *log = NULL;
  uint64_t events = 0;
  Sequencer() { memset(&script, 0, sizeof(script)); memset(&host, 0, sizeof(host)); }
};

struct Fault {                       // --fault: frames [first, last] get value
  double t0, t1;
  uint32_t first, last;
  float value;
};

struct Unit {                        // one engine or effect instance
  const fm1_engine_t *e = NULL;
  void *mem = NULL;
  void *self = NULL;
  size_t bytes = 0;
  std::vector<std::pair<std::string, float> > params;
  int driven = 0;                     // FM1_PARAM_DRIVEN as last sent (0: as created)
};

bool Instantiate(Unit &u, const char *id, fm1_kind_t kind, const fm1_host_t &host, int fill) {
  u.e = fm1_engine_find(id);
  if (!u.e || u.e->magic != FM1_ENGINE_MAGIC || u.e->api_version != FM1_ENGINE_API_VERSION ||
      u.e->kind != kind) {
    fprintf(stderr, "unknown, incompatible or wrong-kind engine: %s\n", id);
    return false;
  }
  u.bytes = u.e->instance_size(&host);
  if (posix_memalign(&u.mem, 16, u.bytes ? u.bytes : 16) != 0) return false;
  memset(u.mem, fill, u.bytes);
  u.self = u.e->create(u.mem, &host);
  if (!u.self) {
    fprintf(stderr, "%s refused this host (rate %g Hz, %u frames)\n", id, host.sample_rate,
            host.max_frames);
    return false;
  }
  for (size_t p = 0; p < u.params.size(); ++p) {
    bool found = false;
    for (uint16_t q = 0; q < u.e->n_params; ++q) {
      if (strcasecmp(u.e->params[q].name, u.params[p].first.c_str()) == 0) {
        u.e->set_param(u.self, q, u.params[p].second);
        found = true;
      }
    }
    if (!found) {
      fprintf(stderr, "unknown parameter for %s: %s\n", id, u.params[p].first.c_str());
      return false;
    }
  }
  return true;
}

void Release(Unit &u) {
  if (u.self) u.e->destroy(u.self);
  free(u.mem);
}

// The bridge's sink: the sound engine, called exactly as the engine API says.
void SinkRender(void *ctx, float *lr, uint32_t n) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->render(u->self, lr, n);
}
// Which sound unit a Unit is (for the note ledger); set before the run.
const Unit *g_units[kSounds];

int UnitIndex(const Unit *u) {
  for (int k = 0; k < kSounds; ++k) if (g_units[k] == u) return k;
  return 0;
}

void LedgerOn(int k, uint8_t note) { if (note < 128) ++g_sounding[k][note]; }
void LedgerOff(int k, uint8_t note) {
  if (note < 128 && g_sounding[k][note]) --g_sounding[k][note];
}

void SinkNoteOn(void *ctx, uint8_t note, uint8_t vel) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->note_on(u->self, note, vel);
  LedgerOn(UnitIndex(u), note);
}
void SinkNoteOff(void *ctx, uint8_t note) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->note_off(u->self, note);
  LedgerOff(UnitIndex(u), note);
}
void SinkSetParam(void *ctx, uint16_t index, float value) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->set_param(u->self, index, value);
}
void SinkBend(void *ctx, float semitones) {
  const Unit *u = static_cast<const Unit *>(ctx);
  if (u->e->pitch_bend) u->e->pitch_bend(u->self, semitones);
}
void SinkSetParamNote(void *ctx, uint8_t key, uint16_t index, float offset) {
  const Unit *u = static_cast<const Unit *>(ctx);
  if (u->e->set_param_note) u->e->set_param_note(u->self, key, index, offset);
}

// A MIDI effect's flush (a bypass): its note-offs, as live note-offs on the
// unit's engine (and the modulation's note sources, as fm1-render feeds a
// --note's).
struct MfxOff {
  Unit *const *units;
  fm1_mod_t *mod;
};

void MfxNoteOff(void *ctx, unsigned chain, uint8_t key) {
  const MfxOff *o = static_cast<const MfxOff *>(ctx);
  if (chain >= unsigned(kSounds)) return;
  Unit *u = o->units[chain];
  if (!u->e) return;
  u->e->note_off(u->self, key);
  LedgerOff(static_cast<int>(chain), key);
  if (o->mod) fm1_mod_live_sound_note(o->mod, chain, key, 0);
}

// --mod: the runtime, its glue to the bridge, the script's timed lines, the
// block's writes to the effects and AMP, and the tick log.
struct ModLine {
  uint64_t frame;
  std::string text;
};

struct Modulation {
  void *mem = NULL;
  fm1_mod_t *m = NULL;
  fm1_mod_glue_t glue;
  std::vector<ModLine> lines;
  size_t next_line = 0;
  std::vector<std::pair<uint32_t, fm1_mod_write_t> > writes;   // this block's FX and AMP
  fm1_mod_ramp_t amp;
  bool amp_used = false;
  FILE *log = NULL;
  uint64_t pos = 0;                  // the block's first frame, for the log
  // Per-voice offsets since the last logged tick (MG9): frame and write.
  std::vector<std::pair<uint64_t, fm1_mod_write_t> > voiced;
  uint64_t live_voice_writes = 0;    // the live notes' first offsets
  Modulation() { memset(&glue, 0, sizeof(glue)); fm1_mod_ramp_init(&amp, 1.0f); }
};

// A live note's first per-voice offsets, right after the engine's note_on
// (fm1_mod_host.h), at the coming block's first frame.
void ModVoiceStart(Modulation &md, const Unit &u, unsigned sound, uint8_t key, uint64_t frame) {
  fm1_mod_write_t w[FM1_MOD_VDESTS + 1u];
  const uint32_t n = fm1_mod_voice_start(md.m, sound, key, w, FM1_MOD_VDESTS + 1u);
  for (uint32_t i = 0; i < n; ++i) {
    if (u.e->set_param_note) u.e->set_param_note(u.self, w[i].key, w[i].index, w[i].value);
    if (md.log) md.voiced.push_back(std::make_pair(frame, w[i]));
  }
  md.live_voice_writes += n;
}

void ModVoiced(void *ctx, uint32_t frame, const fm1_mod_write_t *w, uint32_t n) {
  Modulation *md = static_cast<Modulation *>(ctx);
  if (!md->log) return;
  for (uint32_t i = 0; i < n; ++i) md->voiced.push_back(std::make_pair(md->pos + frame, w[i]));
}

void ModWrite(void *ctx, uint32_t frame, const fm1_mod_write_t *w) {
  Modulation *md = static_cast<Modulation *>(ctx);
  md->writes.push_back(std::make_pair(frame, *w));
}

const char *ModUnitName(unsigned u) {
  const char *n = fm1_mod_script_unit_name(u);   // snd, snd2, snd1.fx2, fx1, host
  return n ? n : "?";
}

void ModTicked(void *ctx, uint32_t frame, const fm1_mod_write_t *w, uint32_t n) {
  Modulation *md = static_cast<Modulation *>(ctx);
  if (!md->log) return;
  FILE *f = md->log;
  fm1_mod_t *m = md->m;
  fm1_mod_stats_t st;
  fm1_mod_get_stats(m, &st);
  fprintf(f, "{\"k\":%llu,\"t\":%llu,\"m\":[", static_cast<unsigned long long>(st.ticks),
          static_cast<unsigned long long>(md->pos + frame));
  bool first = true;
  for (unsigned p = 0; p < FM1_MOD_POSITIONS; ++p) {
    const int k = fm1_mod_kind_at(m, p);
    if (k < 0) continue;
    const fm1_mod_kind_t *kd = fm1_mod_kinds[k];
    fprintf(f, "%s{\"p\":%u,\"id\":\"%s\",\"v\":[", first ? "" : ",", p + 1, kd->id);
    first = false;
    for (unsigned i = 0; i < kd->n_params; ++i) fprintf(f, i ? ",%.9g" : "%.9g", fm1_mod_param(m, p, i));
    fprintf(f, "],\"o\":[");
    for (unsigned i = 0; i < kd->n_out; ++i) fprintf(f, i ? ",%.9g" : "%.9g", fm1_mod_out(m, p, i));
    fprintf(f, "],\"e\":[");
    bool fe = true;
    for (unsigned i = 0; i < kd->n_out; ++i) {
      const fm1_mod_gate_t *g = fm1_mod_gate_out(m, p, i);
      for (unsigned e = 0; kd->out[i].kind == FM1_PORT_GATE && e < g->n; ++e) {
        fprintf(f, "%s[%u,%u,%u]", fe ? "" : ",", i + 1, g->ev[e].frame, g->ev[e].high);
        fe = false;
      }
    }
    fprintf(f, "]}");
  }
  fprintf(f, "],\"g\":[");          // system gates with edges in this tick
  first = true;
  for (unsigned id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    const fm1_mod_gate_t *g = fm1_mod_system_gate(m, id);
    for (unsigned e = 0; g && e < g->n; ++e) {
      fprintf(f, "%s[%u,%u,%u]", first ? "" : ",", id, g->ev[e].frame, g->ev[e].high);
      first = false;
    }
  }
  fprintf(f, "],\"s\":[");
  fm1_mod_sink_info_t si;
  for (unsigned i = 0; fm1_mod_sink(m, i, &si); ++i) {
    fprintf(f, "%s{\"u\":\"%s\",\"i\":%u,\"uid\":%u,\"b\":%.9g,\"v\":%.9g}", i ? "," : "",
            ModUnitName(si.unit), si.index, si.uid, si.base, si.value);
  }
  fprintf(f, "],\"w\":[");
  for (uint32_t i = 0; i < n; ++i) {
    fprintf(f, "%s[\"%s\",%u,%.9g]", i ? "," : "", ModUnitName(w[i].unit), w[i].index, w[i].value);
  }
  // Voices (MG9): each one sounding, its per-voice modules' outputs, and the
  // per-note offsets sent since the last tick ([frame, unit, key, index,
  // offset]; index 65535 is the note's pitch).
  fprintf(f, "],\"vo\":[");
  first = true;
  for (unsigned v = 0; v < FM1_MOD_VOICES; ++v) {
    fm1_mod_voice_info_t vi;
    if (!fm1_mod_voice(m, v, &vi)) continue;
    fprintf(f, "%s[%u,%u,%u,%u,[", first ? "" : ",", v, vi.sound, vi.key, vi.state);
    first = false;
    bool fp = true;
    fm1_mod_plan_info_t plan;
    fm1_mod_get_plan(m, &plan);
    for (unsigned p = 0; p < FM1_MOD_POSITIONS; ++p) {
      const int k = fm1_mod_kind_at(m, p);
      if (k < 0 || !((plan.poly >> p) & 1u)) continue;
      fprintf(f, "%s[%u", fp ? "" : ",", p + 1);
      fp = false;
      for (unsigned i = 0; i < fm1_mod_kinds[k]->n_out; ++i) fprintf(f, ",%.9g", fm1_mod_voice_out(m, v, p, i));
      fprintf(f, "]");
    }
    fprintf(f, "]]");
  }
  fprintf(f, "],\"vw\":[");
  for (size_t i = 0; i < md->voiced.size(); ++i) {
    const fm1_mod_write_t &x = md->voiced[i].second;
    fprintf(f, "%s[%llu,\"%s\",%u,%u,%.9g]", i ? "," : "",
            static_cast<unsigned long long>(md->voiced[i].first), ModUnitName(x.unit), x.key, x.index,
            x.value);
  }
  md->voiced.clear();
  fprintf(f, "]}\n");
}

// --list-mod: the kinds (with every parameter's uid and flags, as --list
// prints engines'), the system sources and the host unit.
void PrintFlags(uint16_t f);
const char *UnitName(uint8_t u);
void PrintJsonString(const char *s);

const char *PortKind(uint8_t k) {
  return k == FM1_PORT_CV_UNI ? "cv_uni" : k == FM1_PORT_GATE ? "gate" : "cv_bi";
}

void PrintParams(const fm1_param_t *params, unsigned n) {
  for (unsigned p = 0; p < n; ++p) {
    const fm1_param_t &q = params[p];
    printf(p ? ",{" : "{");
    printf("\"name\":"); PrintJsonString(q.name);
    printf(",\"type\":%d,\"min\":%g,\"max\":%g,\"def\":%g,\"page\":%u,\"uid\":%u,\"flags\":",
           q.type, q.min, q.max, q.def, q.page, q.uid);
    PrintFlags(q.flags);
    printf(",\"unit\":\"%s\",\"abbr\":", UnitName(q.unit));
    PrintJsonString(q.abbr ? q.abbr : "");
    if (q.type == FM1_PARAM_ENUM && q.enum_names) {
      printf(",\"names\":[");
      const int k = static_cast<int>(q.max - q.min) + 1;
      for (int i = 0; i < k; ++i) { if (i) putchar(','); PrintJsonString(q.enum_names[i]); }
      putchar(']');
    }
    putchar('}');
  }
}

void PrintPorts(const fm1_port_t *ports, unsigned n) {
  for (unsigned i = 0; i < n; ++i) {
    printf(i ? ",{" : "{");
    printf("\"name\":"); PrintJsonString(ports[i].name);
    printf(",\"kind\":\"%s\",\"unit\":\"%s\"", PortKind(ports[i].kind), UnitName(ports[i].unit));
    if (ports[i].normal != FM1_MOD_NONE) {
      const fm1_mod_source_info_t *si = fm1_mod_system_source(ports[i].normal);
      printf(",\"normal\":"); PrintJsonString(si ? si->name : "?");
    }
    putchar('}');
  }
}

void ListMod() {
  printf("{\"tick\":%u,\"positions\":%u,\"slots\":%u,\"arena\":%u,\"bytes\":%zu,"
         "\"sinks\":[", FM1_MOD_TICK, FM1_MOD_POSITIONS, FM1_MOD_SLOTS, FM1_MOD_ARENA, fm1_mod_size());
  for (unsigned i = 0; i < FM1_MOD_SINKS; ++i) {   // each sink's code and script name
    printf("%s[%u,\"%s\"]", i ? "," : "", fm1_mod_sink_unit(i), fm1_mod_script_unit_name(fm1_mod_sink_unit(i)));
  }
  printf("],\"sink_params\":%u,\"unit_params\":%u,\"kinds\":[", FM1_MOD_SINK_PARAMS, FM1_MOD_UNIT_PARAMS);
  fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
  for (size_t i = 0; i < fm1_mod_kind_count; ++i) {
    const fm1_mod_kind_t *k = fm1_mod_kinds[i];
    const uint32_t g = k->guid;
    const char guid[5] = { char(g >> 24), char(g >> 16), char(g >> 8), char(g), 0 };
    printf(i ? ",{" : "{");
    printf("\"id\":"); PrintJsonString(k->id);
    printf(",\"guid\":"); PrintJsonString(guid);
    printf(",\"name\":"); PrintJsonString(k->name);
    printf(",\"abbr\":"); PrintJsonString(k->abbr);
    printf(",\"credits\":"); PrintJsonString(k->credits);
    printf(",\"transport\":%s,\"instance_bytes\":%zu,\"params\":[",
           (k->flags & FM1_MOD_KIND_TRANSPORT) ? "true" : "false", k->instance_size(&host));
    PrintParams(k->params, k->n_params);
    printf("],\"gates\":[");
    PrintPorts(k->gate_in, k->n_gate_in);
    printf("],\"outs\":[");
    PrintPorts(k->out, k->n_out);
    printf("]}");
  }
  printf("],\"sources\":[");
  bool first = true;
  for (unsigned id = 0; id < FM1_MOD_SRC_SYSTEM; ++id) {
    const fm1_mod_source_info_t *si = fm1_mod_system_source(id);
    if (!si) continue;
    printf("%s{\"id\":%u,\"name\":", first ? "" : ",", id);
    first = false;
    PrintJsonString(si->name);
    printf(",\"kind\":\"%s\",\"unit\":\"%s\"}", PortKind(si->kind), UnitName(si->unit));
  }
  printf("],\"host\":[");
  PrintParams(fm1_mod_host_params, FM1_MOD_HOST_PARAMS);
  printf("]}\n");
}

// Renders an effect over a block, split at its own writes from the ticks;
// each piece goes through fm1_fx_render, which calls a v2 effect's render
// once and an API v3 effect's render_ext split at the beats and transport
// events it asked for (fm1_fx_host.h). First, FM1_PARAM_DRIVEN when it
// changed: 1 while a cable reaches the effect (fm1_mod_unit_routed), so an
// effect with an idle path never idles under one (owner, 2026-10-06; the
// sequencer's lanes cannot lock an effect yet).
void RenderFx(Unit &u, unsigned unit, const Modulation *md, float *block, uint32_t n,
              const fm1_fx_block_t *fxb) {
  uint32_t cur = 0;
  const int driven = md && md->m ? fm1_mod_unit_routed(md->m, unit) : 0;
  if (driven != u.driven) {
    u.e->set_param(u.self, FM1_PARAM_DRIVEN, static_cast<float>(driven));
    u.driven = driven;
  }
  if (md) {
    for (size_t k = 0; k < md->writes.size(); ++k) {
      const uint32_t f = md->writes[k].first;
      const fm1_mod_write_t &w = md->writes[k].second;
      if (w.unit != unit) continue;
      if (f > cur) { fm1_fx_render(u.e, u.self, block, cur, f, fxb); cur = f; }
      if (w.index < u.e->n_params) u.e->set_param(u.self, w.index, w.value);
    }
  }
  if (cur < n) fm1_fx_render(u.e, u.self, block, cur, n, fxb);
}

// --sysex: each file's DX7 voices into the dx7 engine's user slots, in
// order, single voices one slot after another across files.
bool LoadSysex(const Unit &u, const char *id, const std::vector<std::string> &paths) {
  if (!id || strcmp(id, "dx7") != 0) {
    fprintf(stderr, "--sysex needs --engine dx7\n");
    return false;
  }
  unsigned slot = 0;
  for (size_t k = 0; k < paths.size(); ++k) {
    FILE *f = fopen(paths[k].c_str(), "rb");
    if (!f) { fprintf(stderr, "--sysex: cannot open %s\n", paths[k].c_str()); return false; }
    std::vector<uint8_t> data;
    uint8_t buf[4096];
    size_t got;
    while ((got = fread(buf, 1, sizeof(buf), f)) > 0) data.insert(data.end(), buf, buf + got);
    fclose(f);
    fm1_dx7_sysex_result_t r;
    const int n = fm1_dx7_load_sysex(u.self, data.empty() ? NULL : &data[0], data.size(), slot, &r);
    if (n <= 0) {
      fprintf(stderr, "--sysex: no DX7 voice dump in %s\n", paths[k].c_str());
      return false;
    }
    fprintf(stderr, "sysex %s: %d voices from User %u, %u bad checksums, %u skipped:",
            paths[k].c_str(), n, r.first_slot + 1u, r.bad_checksums, r.skipped);
    for (int i = 0; i < n && i < (int)FM1_DX7_USER_SLOTS; ++i) {
      char name[FM1_DX7_NAME_BYTES + 1];
      fm1_dx7_user_name(u.self, (r.first_slot + i) % FM1_DX7_USER_SLOTS, name);
      fprintf(stderr, " \"%s\"", name);
    }
    fputc('\n', stderr);
    slot = (r.first_slot + static_cast<unsigned>(n)) % FM1_DX7_USER_SLOTS;
  }
  return true;
}

bool ParseParam(const char *arg, std::vector<std::pair<std::string, float> > *out) {
  const char *eq = strchr(arg, '=');
  if (!eq) return false;
  out->push_back(std::make_pair(std::string(arg, eq - arg), static_cast<float>(atof(eq + 1))));
  return true;
}

void PrintJsonString(const char *s) {
  putchar('"');
  for (; *s; ++s) {
    if (*s == '"' || *s == '\\') putchar('\\');
    putchar(*s);
  }
  putchar('"');
}

const char *UnitName(uint8_t u) {
  switch (u) {
    case FM1_UNIT_NONE: return "none";
    case FM1_UNIT_SEMI: return "semi";
    case FM1_UNIT_MS: return "ms";
    case FM1_UNIT_HZ: return "hz";
    case FM1_UNIT_PCT: return "pct";
    case FM1_UNIT_DEG: return "deg";
    case FM1_UNIT_DB: return "db";
    default: return "?";
  }
}

void PrintFlags(uint16_t f) {
  static const struct { uint16_t bit; const char *name; } kFlags[] = {
    { FM1_PARAM_LATCH, "latch" }, { FM1_PARAM_SMOOTH, "smooth" }, { FM1_PARAM_NOLOCK, "nolock" },
    { FM1_PARAM_MOD, "mod" }, { FM1_PARAM_INPUT, "input" }, { FM1_PARAM_POLY, "poly" },
    { FM1_PARAM_LOG, "log" },
  };
  uint16_t known = 0;
  bool first = true;
  putchar('[');
  for (size_t k = 0; k < sizeof(kFlags) / sizeof(kFlags[0]); ++k) {
    known |= kFlags[k].bit;
    if (!(f & kFlags[k].bit)) continue;
    printf(first ? "\"%s\"" : ",\"%s\"", kFlags[k].name);
    first = false;
  }
  if (f & ~known) printf(first ? "\"0x%04x\"" : ",\"0x%04x\"", unsigned(f & ~known));   // a test catches it
  putchar(']');
}

void List() {
  printf("[");
  // The engines, then the MIDI effects (their own registry, kind midi_fx).
  for (size_t i = 0; i < fm1_engine_count + fm1_midi_fx_count; ++i) {
    const fm1_engine_t *e = i < fm1_engine_count ? fm1_engines[i]
                                                 : &fm1_midi_fxs[i - fm1_engine_count]->engine;
    printf(i ? ",{" : "{");
    printf("\"id\":"); PrintJsonString(e->id);
    printf(",\"name\":"); PrintJsonString(e->name);
    printf(",\"credits\":"); PrintJsonString(e->credits);
    printf(",\"kind\":\"%s\",\"max_voices\":%u,\"per_note\":%s,\"render_ext\":%s,\"fx_wants\":[",
           e->kind == FM1_KIND_SOUND ? "sound" : e->kind == FM1_KIND_AUDIO_FX ? "audio_fx" : "midi_fx",
           e->max_voices, e->set_param_note ? "true" : "false", e->render_ext ? "true" : "false");
    {
      static const struct { uint32_t bit; const char *name; } kWants[] = {
        { FM1_FX_WANT_KEY, "key" }, { FM1_FX_WANT_TEMPO, "tempo" },
        { FM1_FX_WANT_TRANSPORT, "transport" },
      };
      bool firstw = true;
      for (size_t k = 0; k < sizeof(kWants) / sizeof(kWants[0]); ++k) {
        if (!(e->fx_wants & kWants[k].bit)) continue;
        printf(firstw ? "\"%s\"" : ",\"%s\"", kWants[k].name);
        firstw = false;
      }
      if (e->fx_wants & ~uint32_t(FM1_FX_WANT_KEY | FM1_FX_WANT_TEMPO | FM1_FX_WANT_TRANSPORT)) {
        printf(firstw ? "\"0x%x\"" : ",\"0x%x\"", unsigned(e->fx_wants));   // a test catches it
      }
    }
    printf("],");
    if (e->pad_count) printf("\"pads\":{\"first\":%u,\"count\":%u},", e->pad_first_note, e->pad_count);
    else printf("\"pads\":null,");
    printf("\"params\":[");
    for (uint16_t p = 0; p < e->n_params; ++p) {
      const fm1_param_t &q = e->params[p];
      printf(p ? ",{" : "{");
      printf("\"name\":"); PrintJsonString(q.name);
      printf(",\"type\":%d,\"min\":%g,\"max\":%g,\"def\":%g,\"page\":%u",
             q.type, q.min, q.max, q.def, q.page);
      printf(",\"uid\":%u,\"flags\":", q.uid);
      PrintFlags(q.flags);
      printf(",\"unit\":\"%s\",\"abbr\":", UnitName(q.unit));
      PrintJsonString(q.abbr ? q.abbr : "");
      if (q.type == FM1_PARAM_ENUM && q.enum_names) {   // what a UI shows for each value
        printf(",\"names\":[");
        const int n = static_cast<int>(q.max - q.min) + 1;
        for (int k = 0; k < n; ++k) {
          if (k) putchar(',');
          PrintJsonString(q.enum_names[k]);
        }
        putchar(']');
      }
      putchar('}');
    }
    printf("]}");
  }
  printf("]\n");
}

bool WriteWav(const char *path, const std::vector<float> &lr, uint32_t rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  const uint32_t frames = static_cast<uint32_t>(lr.size() / 2);
  const uint32_t data_bytes = frames * 4;
  auto u32 = [f](uint32_t v) { uint8_t b[4] = { uint8_t(v), uint8_t(v >> 8), uint8_t(v >> 16), uint8_t(v >> 24) }; fwrite(b, 1, 4, f); };
  auto u16 = [f](uint16_t v) { uint8_t b[2] = { uint8_t(v), uint8_t(v >> 8) }; fwrite(b, 1, 2, f); };
  fwrite("RIFF", 1, 4, f); u32(36 + data_bytes); fwrite("WAVE", 1, 4, f);
  fwrite("fmt ", 1, 4, f); u32(16); u16(1); u16(2); u32(rate); u32(rate * 4); u16(4); u16(16);
  fwrite("data", 1, 4, f); u32(data_bytes);
  for (float x : lr) {
    if (!(x == x)) x = 0.0f;
    if (x > 1.0f) x = 1.0f;
    if (x < -1.0f) x = -1.0f;
    u16(static_cast<uint16_t>(static_cast<int16_t>(lrintf(x * 32767.0f))));
  }
  return fclose(f) == 0;
}

}  // namespace

int main(int argc, char **argv) {
  const char *engine_id = NULL;
  const char *out_path = NULL;
  std::string input = "silence";
  double seconds = 2.0;
  float rate = 44118.0f;
  float tempo = 120.0f;             // --tempo: the effects' tempo without a sequencer
  uint32_t max_frames = 64;
  int fill = 0;
  std::vector<Fault> faults;
  Unit sound;
  std::vector<std::string> fx_ids;
  std::vector<Unit> fx;
  std::vector<Event> events;
  std::vector<Control> controls;
  std::vector<NoteControl> note_controls;
  std::vector<FxControl> fx_controls;
  const char *cmd_path = NULL, *seq_path = NULL, *log_path = NULL;
  bool compat = false, seconds_given = false, rate_given = false, frames_given = false;
  int tracks = -1;
  long events_cap = -1;            // --events: the block's event buffer
  std::vector<Route> routes;
  const char *mod_path = NULL, *mod_log_path = NULL;
  std::vector<std::string> sysex_paths;   // --sysex: DX7 voices for --engine dx7
  // Sound units 1..3 (--sound) and every unit's inserts and level; unit 0 is
  // `sound`. `slots` is set by any of their flags or --slots.
  Unit more[kSounds];
  std::vector<std::string> more_ids(kSounds), insert_ids[kSounds];
  std::vector<Unit> inserts[kSounds];
  float level[kSounds] = { 100.0f, 100.0f, 100.0f, 100.0f };
  bool slots = false;
  // MIDI effects (--mfx): each sound unit's chain, in order.
  std::vector<std::string> mfx_ids[kSounds];
  std::vector<Unit> mfx_units[kSounds];
  std::vector<int> mfx_start_on[kSounds];   // --mfx K:ID:off starts it bypassed
  std::vector<MfxControl> mfx_controls;
  const char *mfx_log_path = NULL;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    const char *next = i + 1 < argc ? argv[i + 1] : NULL;
    if (a == "--list") { List(); return 0; }
    if (a == "--list-mod") { ListMod(); return 0; }
    if (a == "--compat") { compat = true; continue; }
    if (a == "--slots") { slots = true; continue; }
    if (!next) { Usage(); return 2; }
    ++i;
    if (a == "--engine") engine_id = next;
    else if (a == "--out") out_path = next;
    else if (a == "--input") input = next;
    else if (a == "--seconds") { seconds = atof(next); seconds_given = true; }
    else if (a == "--rate") { rate = static_cast<float>(atof(next)); rate_given = true; }
    else if (a == "--frames") { max_frames = static_cast<uint32_t>(atoi(next)); frames_given = true; }
    else if (a == "--cmd") cmd_path = next;
    else if (a == "--seq") seq_path = next;
    else if (a == "--log-events") log_path = next;
    else if (a == "--mod") mod_path = next;
    else if (a == "--sysex") sysex_paths.push_back(next);
    else if (a == "--log-mod") mod_log_path = next;
    else if (a == "--log-mfx") mfx_log_path = next;
    else if (a == "--tempo") {
      tempo = static_cast<float>(atof(next));
      if (!(tempo >= 20.0f && tempo <= 300.0f)) {
        fprintf(stderr, "--tempo wants 20..300 BPM\n");
        return 2;
      }
    }
    else if (a == "--tracks") tracks = atoi(next);
    else if (a == "--events") {      // a decimal count: base 0 would read 010 as 8
      char *end = NULL;
      events_cap = strtol(next, &end, 10);
      if (end == next || *end || events_cap < 1 || events_cap > 65536) {
        fprintf(stderr, "--events wants 1..65536\n");
        return 2;
      }
    }
    else if (a == "--route") {
      Route r;
      char kind[16] = {0};
      int ch = 0;
      const int got = sscanf(next, "%d:%15[a-z]:%d", &r.track, kind, &ch);
      if (got >= 2 && strcmp(kind, "engine") == 0) { r.engine = true; r.channel = 0; }
      else if (got == 3 && strcmp(kind, "midi") == 0 && ch >= 1 && ch <= 16) { r.engine = false; r.channel = ch; }
      else { fprintf(stderr, "--route wants T:engine or T:midi:CH\n"); return 2; }
      routes.push_back(r);
    }
    else if (a == "--fill") fill = static_cast<int>(strtol(next, NULL, 0)) & 0xFF;
    else if (a == "--fault") {
      const char *colon = strchr(next, ':');
      if (!colon) { Usage(); return 2; }
      const char *dots = strstr(next, "..");
      const double t0 = atof(next);
      const double t1 = dots && dots < colon ? atof(dots + 2) : t0;
      if (t1 < t0) { Usage(); return 2; }
      faults.push_back(Fault{ t0, t1, 0, 0, strtof(colon + 1, NULL) });
    }
    else if (a == "--param") { if (!ParseParam(next, &sound.params)) { Usage(); return 2; } }
    else if (a == "--fx") { fx_ids.push_back(next); fx.push_back(Unit()); }
    else if (a == "--fx-param") {
      if (fx.empty() || !ParseParam(next, &fx.back().params)) { Usage(); return 2; }
    } else if (a == "--note") {
      double t, dur; int key, vel;
      if (sscanf(next, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) { Usage(); return 2; }
      events.push_back(Event{ t, true, uint8_t(key), uint8_t(vel), 0 });
      events.push_back(Event{ t + dur, false, uint8_t(key), 0, 0 });
    } else if (a == "--bend") {
      double t; float st;
      if (sscanf(next, "%lf:%f", &t, &st) != 2 || !(st >= -48.0f && st <= 48.0f)) {
        fprintf(stderr, "--bend wants T:SEMITONES, finite and within +/-48\n");
        return 2;
      }
      controls.push_back(Control{ t, true, std::string(), 0, st, false, 0, false });
    } else if (a == "--param-at") {
      const char *colon = strchr(next, ':');
      std::vector<std::pair<std::string, float> > one;
      if (!colon || !ParseParam(colon + 1, &one)) { Usage(); return 2; }
      controls.push_back(Control{ atof(next), false, one[0].first, 0, one[0].second, false, 0, false });
    } else if (a == "--note-param-at" || a == "--note-pitch-at") {
      const bool pitch = a == "--note-pitch-at";
      double t; int key, used = 0;
      std::vector<std::pair<std::string, float> > one;
      if (sscanf(next, "%lf:%d:%n", &t, &key, &used) != 2 || !used || key < 0 || key > 127 ||
          (pitch ? !*(next + used) : !ParseParam(next + used, &one))) {
        fprintf(stderr, "%s wants T:KEY:%s, KEY 0..127\n", a.c_str(),
                pitch ? "SEMITONES" : "NAME=OFFSET");
        return 2;
      }
      if (pitch) {
        note_controls.push_back(NoteControl{ t, uint8_t(key), std::string(),
                                             FM1_PARAM_NOTE_PITCH,
                                             static_cast<float>(atof(next + used)), false });
      } else {
        note_controls.push_back(NoteControl{ t, uint8_t(key), one[0].first, 0, one[0].second,
                                             false });
      }
    } else if (a == "--sound" || a == "--sound-param" || a == "--insert" || a == "--insert-param" ||
               a == "--level" || a == "--sound-note" || a == "--sound-param-at" || a == "--level-at") {
      // K:REST, K the sound unit (0..3; --sound wants 1..3, unit 0 is --engine).
      char *rest = NULL;
      const long k = strtol(next, &rest, 10);
      if (rest == next || *rest != ':' || k < 0 || k >= kSounds || (a == "--sound" && k == 0)) {
        fprintf(stderr, "%s wants K:... with K a sound unit (0..%d)\n", a.c_str(), kSounds - 1);
        return 2;
      }
      ++rest;
      slots = true;
      if (a == "--sound") {
        more_ids[k] = rest;
      } else if (a == "--sound-param") {
        if (!ParseParam(rest, &more[k].params)) { Usage(); return 2; }
      } else if (a == "--insert") {
        insert_ids[k].push_back(rest);
        inserts[k].push_back(Unit());
      } else if (a == "--insert-param") {
        if (inserts[k].empty() || !ParseParam(rest, &inserts[k].back().params)) { Usage(); return 2; }
      } else if (a == "--level") {
        const float v = static_cast<float>(atof(rest));
        if (!(v >= 0.0f && v <= 100.0f)) { fprintf(stderr, "--level wants 0..100\n"); return 2; }
        level[k] = v;
      } else if (a == "--sound-note") {
        double t, dur; int key, vel;
        if (sscanf(rest, "%lf:%d:%d:%lf", &t, &key, &vel, &dur) != 4) { Usage(); return 2; }
        events.push_back(Event{ t, true, uint8_t(key), uint8_t(vel), static_cast<int>(k) });
        events.push_back(Event{ t + dur, false, uint8_t(key), 0, static_cast<int>(k) });
      } else {                       // --sound-param-at, --level-at: K:T:...
        const char *colon = strchr(rest, ':');
        if (!colon) { Usage(); return 2; }
        if (a == "--level-at") {
          const float v = static_cast<float>(atof(colon + 1));
          if (!(v >= 0.0f && v <= 100.0f)) { fprintf(stderr, "--level-at wants 0..100\n"); return 2; }
          controls.push_back(Control{ atof(rest), false, std::string(), 0, v, false,
                                      static_cast<int>(k), true });
        } else {
          std::vector<std::pair<std::string, float> > one;
          if (!ParseParam(colon + 1, &one)) { Usage(); return 2; }
          controls.push_back(Control{ atof(rest), false, one[0].first, 0, one[0].second, false,
                                      static_cast<int>(k), false });
        }
      }
    } else if (a == "--mfx" || a == "--mfx-param") {
      char *rest = NULL;
      const long k = strtol(next, &rest, 10);
      if (rest == next || *rest != ':' || k < 0 || k >= kSounds) {
        fprintf(stderr, "%s wants K:... with K a sound unit (0..%d)\n", a.c_str(), kSounds - 1);
        return 2;
      }
      ++rest;
      if (k > 0) slots = true;
      if (a == "--mfx") {
        if (mfx_ids[k].size() >= FM1_MFX_SLOTS) {
          fprintf(stderr, "--mfx: sound unit %ld has %u MIDI effects already\n", k, FM1_MFX_SLOTS);
          return 2;
        }
        std::string id = rest;
        const size_t colon = id.find(':');
        const bool off = colon != std::string::npos && id.substr(colon + 1) == "off";
        if (colon != std::string::npos && !off) {
          fprintf(stderr, "--mfx wants K:ID or K:ID:off\n");
          return 2;
        }
        mfx_ids[k].push_back(id.substr(0, colon));
        mfx_units[k].push_back(Unit());
        mfx_start_on[k].push_back(off ? 0 : 1);
      } else if (mfx_units[k].empty() || !ParseParam(rest, &mfx_units[k].back().params)) {
        Usage();
        return 2;
      }
    } else if (a == "--mfx-param-at" || a == "--mfx-on-at") {
      // K[.J]:T:NAME=VALUE or K[.J]:T:0|1, J the effect's place in the chain from 1
      char *rest = NULL;
      const long k = strtol(next, &rest, 10);
      long j = 1;
      if (rest != next && *rest == '.') {
        char *r2 = NULL;
        j = strtol(rest + 1, &r2, 10);
        if (r2 == rest + 1) j = 0;
        rest = r2;
      }
      const char *c2 = rest != next && *rest == ':' ? strchr(rest + 1, ':') : NULL;
      std::vector<std::pair<std::string, float> > one;
      const bool on_off = a == "--mfx-on-at";
      if (!c2 || k < 0 || k >= kSounds || j < 1 || j > long(FM1_MFX_SLOTS) ||
          (on_off ? !*(c2 + 1) : !ParseParam(c2 + 1, &one))) {
        fprintf(stderr, "%s wants K[.J]:T:%s, K a sound unit, J from 1\n", a.c_str(),
                on_off ? "0|1" : "NAME=VALUE");
        return 2;
      }
      if (k > 0) slots = true;
      MfxControl c;
      c.time = atof(rest + 1);
      c.sound = static_cast<int>(k);
      c.slot = static_cast<int>(j - 1);
      c.on_off = on_off;
      c.index = 0;
      c.done = false;
      if (on_off) {
        c.value = atof(c2 + 1) != 0.0 ? 1.0f : 0.0f;
      } else {
        c.name = one[0].first;
        c.value = one[0].second;
      }
      mfx_controls.push_back(c);
    } else if (a == "--fx-param-at") {
      // T:K:NAME=VALUE, K the effect's place in the chain (1 = the first --fx)
      const char *c1 = strchr(next, ':');
      const char *c2 = c1 ? strchr(c1 + 1, ':') : NULL;
      std::vector<std::pair<std::string, float> > one;
      char *end = NULL;
      const long unit = c1 ? strtol(c1 + 1, &end, 10) : 0;
      if (!c2 || end != c2 || unit < 1 || !ParseParam(c2 + 1, &one)) {
        fprintf(stderr, "--fx-param-at wants T:K:NAME=VALUE, K from 1\n");
        return 2;
      }
      fx_controls.push_back(FxControl{ atof(next), static_cast<size_t>(unit - 1), one[0].first, 0,
                                       one[0].second, false });
    } else { Usage(); return 2; }
  }
  for (size_t k = 0; k < controls.size(); ++k) {
    if (!controls[k].sound && !controls[k].level && !engine_id) {
      fprintf(stderr, "--bend and --param-at need --engine\n");
      return 2;
    }
  }
  if (!note_controls.empty() && !engine_id) {
    fprintf(stderr, "--note-param-at and --note-pitch-at need --engine\n");
    return 2;
  }
  const bool use_seq = cmd_path || seq_path;
  Sequencer sq;
  uint64_t seq_end = 0;            // a script's run length, in frames (exact)
  if (use_seq) {
    char err[256];
    if (cmd_path && !fm1_script_load(cmd_path, &sq.script, err, sizeof(err))) {
      fprintf(stderr, "%s\n", err);
      return 1;
    }
    if (!cmd_path) { sq.script.rate = 44118; sq.script.block = 128; sq.script.tracks = 8; }
    if (!rate_given) rate = static_cast<float>(sq.script.rate);
    if (!frames_given) max_frames = sq.script.block;
    if (tracks < 0) tracks = sq.script.tracks;
    if (!seconds_given && (sq.script.has_end || sq.script.n)) {
      uint64_t end = sq.script.end;
      if (!sq.script.has_end) {   // through the block in which the last command applies
        const uint64_t last = sq.script.cmds[sq.script.n - 1].frame;
        end = ((last + max_frames - 1u) / max_frames + 1u) * max_frames;
      }
      seconds = static_cast<double>(end) / rate;
      seq_end = end;
    }
    if (tracks < 1 || tracks > 16 || max_frames < 1 || max_frames > 65535) { Usage(); return 2; }
  } else if (!routes.empty() || log_path || compat || tracks >= 0) {
    fprintf(stderr, "--route, --log-events, --compat and --tracks need --cmd or --seq\n");
    return 2;
  } else if (events_cap > 0) {
    fprintf(stderr, "--events needs --cmd or --seq\n");
    return 2;
  }
  bool any_sound = engine_id != NULL;
  for (int k = 1; k < kSounds; ++k) any_sound = any_sound || !more_ids[k].empty();
  if (!any_sound && fx.empty() && input == "silence" && faults.empty() && !use_seq) { Usage(); return 2; }
  if (mod_log_path && !mod_path) {
    fprintf(stderr, "--log-mod needs --mod\n");
    return 2;
  }
  // The MIDI effects' usage errors, before anything is allocated (an exit
  // after that leaks under LeakSanitizer, which turns the exit code to 1).
  bool any_mfx = false;
  for (int k = 0; k < kSounds; ++k) any_mfx = any_mfx || !mfx_units[k].empty();
  if (mfx_log_path && !any_mfx) {
    fprintf(stderr, "--log-mfx needs --mfx\n");
    return 2;
  }
  for (size_t k = 0; k < mfx_controls.size(); ++k) {
    const MfxControl &c = mfx_controls[k];
    if (size_t(c.slot) >= mfx_units[c.sound].size()) {
      fprintf(stderr, "--mfx-%s names MIDI effect %d of sound unit %d, which has %zu\n",
              c.on_off ? "on-at" : "param-at", c.slot + 1, c.sound, mfx_units[c.sound].size());
      return 2;
    }
  }
  if (input != "silence" && input != "impulse" && input != "noise" && input != "sine") {
    Usage(); return 2;
  }

  for (size_t k = 0; k < faults.size(); ++k) {
    faults[k].first = static_cast<uint32_t>(llround(faults[k].t0 * rate));
    faults[k].last = faults[k].t1 > faults[k].t0
        ? static_cast<uint32_t>(llround(faults[k].t1 * rate)) - 1 : faults[k].first;
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, max_frames };
  if (engine_id && !Instantiate(sound, engine_id, FM1_KIND_SOUND, host, fill)) return 1;
  if (!sysex_paths.empty() && !LoadSysex(sound, engine_id, sysex_paths)) return 1;
  // Every sound unit, unit 0 being `sound` (created in this order: unit 0,
  // the --fx chain, units 1..3, then each unit's inserts, as the virtual
  // FM-1's harness creates them).
  Unit *units[kSounds] = { &sound, &more[1], &more[2], &more[3] };
  for (size_t k = 0; k < controls.size(); ++k) {
    Control &c = controls[k];
    const Unit &u = *units[c.sound];
    const char *id = c.sound ? more_ids[c.sound].c_str() : engine_id;
    if (c.level) continue;
    if (c.sound && more_ids[c.sound].empty()) {
      fprintf(stderr, "--sound-param-at for sound unit %d, which has no --sound\n", c.sound);
      return 2;
    }
    if (c.bend) {
      if (!sound.e->pitch_bend) { fprintf(stderr, "%s has no pitch bend\n", engine_id); return 1; }
      continue;
    }
    if (!u.e) continue;              // resolved below, once the unit exists
    bool found = false;
    for (uint16_t q = 0; q < u.e->n_params && !found; ++q) {
      if (strcasecmp(u.e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) { fprintf(stderr, "unknown parameter for %s: %s\n", id, c.name.c_str()); return 1; }
  }
  for (size_t k = 0; k < note_controls.size(); ++k) {
    NoteControl &c = note_controls[k];
    if (!sound.e->set_param_note) {
      fprintf(stderr, "%s has no per-note offsets\n", engine_id);
      return 1;
    }
    if (c.index == FM1_PARAM_NOTE_PITCH && c.name.empty()) continue;
    if (c.name[0] == '#') {          // a raw index, sent whatever it is
      c.index = static_cast<uint16_t>(strtoul(c.name.c_str() + 1, NULL, 0));
      continue;
    }
    bool found = false;
    for (uint16_t q = 0; q < sound.e->n_params && !found; ++q) {
      if (strcasecmp(sound.e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) { fprintf(stderr, "unknown parameter for %s: %s\n", engine_id, c.name.c_str()); return 1; }
    if (!fm1_param_poly(&sound.e->params[c.index])) {
      fprintf(stderr, "%s's %s takes no per-note offset (not POLY)\n", engine_id, c.name.c_str());
      return 1;
    }
  }
  for (size_t k = 0; k < fx.size(); ++k) {
    if (!Instantiate(fx[k], fx_ids[k].c_str(), FM1_KIND_AUDIO_FX, host, fill)) return 1;
  }
  for (int k = 1; k < kSounds; ++k) {
    if (!more_ids[k].empty() && !Instantiate(more[k], more_ids[k].c_str(), FM1_KIND_SOUND, host, fill)) {
      return 1;
    }
    if (more_ids[k].empty() && !more[k].params.empty()) {
      fprintf(stderr, "--sound-param for sound unit %d, which has no --sound\n", k);
      return 2;
    }
  }
  for (int k = 0; k < kSounds; ++k) {
    for (size_t j = 0; j < inserts[k].size(); ++j) {
      if (!Instantiate(inserts[k][j], insert_ids[k][j].c_str(), FM1_KIND_AUDIO_FX, host, fill)) return 1;
    }
  }
  for (size_t k = 0; k < controls.size(); ++k) {     // a later unit's --sound-param-at
    Control &c = controls[k];
    if (c.level || c.bend || !c.sound) continue;
    const Unit &u = *units[c.sound];
    bool found = false;
    for (uint16_t q = 0; q < u.e->n_params && !found; ++q) {
      if (strcasecmp(u.e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) {
      fprintf(stderr, "unknown parameter for %s: %s\n", more_ids[c.sound].c_str(), c.name.c_str());
      return 1;
    }
  }
  // MIDI effects: each in its unit's chain, in the order given, its
  // parameters set by name; then the controls' names and places.
  bool use_mfx = false;
  for (int k = 0; k < kSounds; ++k) {
    for (size_t j = 0; j < mfx_ids[k].size(); ++j) {
      const fm1_midi_fx_t *fx = fm1_midi_fx_find(mfx_ids[k][j].c_str());
      Unit &u = mfx_units[k][j];
      if (!fx || fx->engine.magic != FM1_ENGINE_MAGIC || fx->engine.api_version != FM1_ENGINE_API_VERSION) {
        fprintf(stderr, "unknown MIDI effect: %s\n", mfx_ids[k][j].c_str());
        return 1;
      }
      u.e = &fx->engine;
      u.bytes = u.e->instance_size(&host);
      if (posix_memalign(&u.mem, 16, u.bytes ? u.bytes : 16) != 0) return 1;
      memset(u.mem, fill, u.bytes);
      u.self = u.e->create(u.mem, &host);
      if (!u.self) { fprintf(stderr, "%s refused this host\n", u.e->id); return 1; }
      for (size_t q = 0; q < u.params.size(); ++q) {
        bool found = false;
        for (uint16_t i = 0; i < u.e->n_params; ++i) {
          if (strcasecmp(u.e->params[i].name, u.params[q].first.c_str()) == 0) {
            u.e->set_param(u.self, i, u.params[q].second);
            found = true;
          }
        }
        if (!found) {
          fprintf(stderr, "unknown parameter for %s: %s\n", u.e->id, u.params[q].first.c_str());
          return 1;
        }
      }
      use_mfx = true;
    }
  }
  for (size_t k = 0; k < mfx_controls.size(); ++k) {
    MfxControl &c = mfx_controls[k];
    if (c.on_off) continue;
    const fm1_engine_t *e = mfx_units[c.sound][c.slot].e;
    bool found = false;
    for (uint16_t q = 0; q < e->n_params && !found; ++q) {
      if (strcasecmp(e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) { fprintf(stderr, "unknown parameter for %s: %s\n", e->id, c.name.c_str()); return 1; }
  }

  // A --sound-note on a unit with no --sound plays nothing, as a key on an
  // empty sound plays nothing in the virtual FM-1 (whose replays carry it).
  if (slots && input != "silence") {
    fprintf(stderr, "--input feeds the effect chain without a sound; not with --slots\n");
    return 2;
  }
  for (size_t k = 0; k < fx_controls.size(); ++k) {
    FxControl &c = fx_controls[k];
    if (c.unit >= fx.size()) {
      fprintf(stderr, "--fx-param-at names effect %zu of %zu\n", c.unit + 1, fx.size());
      return 2;
    }
    const fm1_engine_t *e = fx[c.unit].e;
    bool found = false;
    for (uint16_t q = 0; q < e->n_params && !found; ++q) {
      if (strcasecmp(e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) { fprintf(stderr, "unknown parameter for %s: %s\n", e->id, c.name.c_str()); return 1; }
  }

  if (use_seq) {
    fm1_seq_limits_t lim;
    fm1_seq_limits_default(&lim, static_cast<uint8_t>(tracks));
    if (compat) {   // Movy has no global caps: generous pools, as fm1-seq --compat
      lim.compat = 1;
      lim.notes = 16384; lim.locks = 16384; lim.trigs = 8192;
      lim.gates = 255; lim.song = 255; lim.rec_notes = 64; lim.pad_mutes = 128; lim.capture = 512;
    }
    sq.mem.resize(fm1_seq_size(&lim) + 8u);
    sq.seq = fm1_seq_create(sq.mem.data(), &lim, static_cast<uint32_t>(lrintf(rate)));
    if (!sq.seq) { fprintf(stderr, "sequencer refused these limits\n"); return 1; }
    sq.ev.resize(events_cap > 0 ? static_cast<size_t>(events_cap) : 65536u);
    fm1_seq_host_init(&sq.host, sq.seq, sq.ev.data(), static_cast<uint32_t>(sq.ev.size()));
    fm1_seq_host_bind(&sq.host, sound.e);   // lane labels resolve against the sound engine
    if (seq_path) {
      size_t len = 0;
      char *txt = fm1_read_file(seq_path, &len);
      if (!txt || !fm1_seq_host_import(&sq.host, txt, len)) {
        fprintf(stderr, "%s: not a movy1 set\n", seq_path);
        free(txt);
        return 1;
      }
      free(txt);
    }
    for (size_t k = 0; k < routes.size(); ++k) {
      if (routes[k].track < 0 || routes[k].track >= tracks ||
          !fm1_seq_set_route(sq.seq, static_cast<uint8_t>(routes[k].track),
                             routes[k].engine ? FM1_SEQ_ROUTE_ENGINE : FM1_SEQ_ROUTE_MIDI,
                             static_cast<uint8_t>(routes[k].engine ? 0 : routes[k].channel))) {
        fprintf(stderr, "bad --route for track %d\n", routes[k].track);
        return 2;
      }
    }
    // The default-route rule (engines/seq.md, Host contract; the bridge's
    // fm1_seq_default_route, which the virtual FM-1 applies too): track 0
    // plays the engine only with no --route, no routes in the set (its own
    // `rt` lines count as routing) and an engine loaded. An imported set
    // without `rt` lines routes every track to MIDI channel t+1.
    if (routes.empty()) fm1_seq_default_route(sq.seq, sound.e != NULL);
    if (log_path && !(sq.log = fopen(log_path, "w"))) { fprintf(stderr, "cannot write %s\n", log_path); return 1; }
  }
  const fm1_seq_sink_t sink = { &sound, sound.e, SinkRender, SinkNoteOn, SinkNoteOff, SinkSetParam,
                                SinkBend, SinkSetParamNote };

  // With slots: one sink and one block per sound unit, summed into the block.
  fm1_seq_sink_t unit_sink[kSounds];
  fm1_seq_slot_t unit_slot[kSounds];
  std::vector<float> unit_block[kSounds];
  for (int k = 0; k < kSounds; ++k) {
    const Unit *u = units[k];
    unit_sink[k] = fm1_seq_sink_t{ const_cast<Unit *>(u), u->e, SinkRender, SinkNoteOn, SinkNoteOff,
                                   SinkSetParam, SinkBend, SinkSetParamNote };
    unit_block[k].assign(static_cast<size_t>(max_frames) * 2u, 0.0f);
    unit_slot[k].sink = u->e ? &unit_sink[k] : NULL;
    unit_slot[k].block = unit_block[k].data();
  }

  // --mod: the runtime in its own memory (filled like the engines'), bound
  // to the sound and the first two effects, with the bases the command line
  // set, then the script's untimed lines.
  Modulation md;
  // The Unit bound to the runtime's sink i (fm1_mod_sink_unit's order), or
  // NULL: the sound units, the first two --fx as the master slots, and each
  // sound unit's first FM1_MOD_INSERTS inserts.
  auto ModUnitOf = [&](unsigned i) -> const Unit * {
    const unsigned code = fm1_mod_sink_unit(i);
    const int k = fm1_mod_unit_sound(code);
    if (k >= 0) return units[k];
    if (code == FM1_MOD_FX1 || code == FM1_MOD_FX2) {
      const size_t f = code - FM1_MOD_FX1;
      return f < fx.size() ? &fx[f] : NULL;
    }
    if (code >= FM1_MOD_INSERT && code < FM1_MOD_INSERT + 4u * FM1_MOD_SOUNDS) {
      const unsigned s = (code - FM1_MOD_INSERT) / 4u, j = (code - FM1_MOD_INSERT) % 4u;
      return j < inserts[s].size() ? &inserts[s][j] : NULL;
    }
    return NULL;
  };
  fm1_seq_host_t bare;               // the bridge without a sequencer
  memset(&bare, 0, sizeof(bare));
  // An error on the --mod path exits with everything released (the units,
  // the runtime, the sequencer's script and both logs), so a sanitizer
  // build's leak check passes the error tests (test_mod_flags_need_mod).
  auto ModFail = [&](int code) {
    if (md.log) fclose(md.log);
    md.log = NULL;
    fm1_mod_destroy(md.m);
    md.m = NULL;
    free(md.mem);
    md.mem = NULL;
    if (sq.log) fclose(sq.log);
    sq.log = NULL;
    fm1_script_free(&sq.script);
    Release(sound);
    for (size_t k = 0; k < fx.size(); ++k) Release(fx[k]);
    for (int k = 1; k < kSounds; ++k) Release(more[k]);
    for (int k = 0; k < kSounds; ++k) {
      for (size_t j = 0; j < inserts[k].size(); ++j) Release(inserts[k][j]);
    }
    return code;
  };
  if (mod_path) {
    FILE *f = fopen(mod_path, "r");
    if (!f) { fprintf(stderr, "cannot read %s\n", mod_path); return ModFail(1); }
    char buf[1024];
    uint32_t seed = 0;
    while (fgets(buf, sizeof(buf), f)) {
      const char *t = buf;
      uint64_t frame = 0;
      while (*t == ' ' || *t == '\t') ++t;
      if (*t == '@') {
        char *end = NULL;
        frame = strtoull(t + 1, &end, 10);
        if (end == t + 1) {
          fprintf(stderr, "%s: bad @FRAME: %s", mod_path, buf);
          fclose(f);
          return ModFail(2);
        }
        t = end;
      }
      std::string text(t);
      while (!text.empty() && (text.back() == '\n' || text.back() == '\r')) text.pop_back();
      if (frame == 0) fm1_mod_script_seed(text.c_str(), &seed);
      md.lines.push_back(ModLine{ frame, text });
    }
    fclose(f);
    std::stable_sort(md.lines.begin(), md.lines.end(),
                     [](const ModLine &x, const ModLine &y) { return x.frame < y.frame; });
    if (posix_memalign(&md.mem, 16, fm1_mod_size()) != 0) {
      md.mem = NULL;
      return ModFail(1);
    }
    memset(md.mem, fill, fm1_mod_size());
    md.m = fm1_mod_create(md.mem, &host, seed);
    if (!md.m) { fprintf(stderr, "modulation runtime refused its memory\n"); return ModFail(1); }
    // Every unit the run has, by the runtime's codes: the sound units and
    // their first FM1_MOD_INSERTS inserts (with slots), the first two --fx
    // as the master slots.
    for (unsigned i = 0; i < FM1_MOD_SINKS; ++i) {
      const Unit *un = ModUnitOf(i);
      const unsigned code = fm1_mod_sink_unit(i);
      if (!un || !un->e) continue;
      fm1_mod_bind(md.m, code, un->e);
      for (size_t p = 0; p < un->params.size(); ++p) {
        for (uint16_t q = 0; q < un->e->n_params; ++q) {
          if (strcasecmp(un->e->params[q].name, un->params[p].first.c_str()) == 0) {
            fm1_mod_set_base(md.m, code, q, un->params[p].second);
          }
        }
      }
    }
    fm1_mod_glue_init(&md.glue, md.m, sound.e);
    md.glue.ctx = &md;
    md.glue.write = ModWrite;
    md.glue.ticked = ModTicked;
    md.glue.voiced = ModVoiced;
    if (mod_log_path && !(md.log = fopen(mod_log_path, "w"))) {
      fprintf(stderr, "cannot write %s\n", mod_log_path);
      return ModFail(1);
    }
    fm1_seq_host_init(&bare, NULL, NULL, 0);
    fm1_seq_host_bind(&bare, sound.e);
  }
  auto ModApplyLines = [&](uint64_t upto) -> bool {
    const fm1_engine_t *mod_units[FM1_MOD_SINKS];
    for (unsigned i = 0; i < FM1_MOD_SINKS; ++i) mod_units[i] = ModUnitOf(i) ? ModUnitOf(i)->e : NULL;
    while (md.next_line < md.lines.size() && md.lines[md.next_line].frame <= upto) {
      char err[256];
      if (!fm1_mod_script_apply(md.m, md.lines[md.next_line].text.c_str(), mod_units, err, sizeof(err))) {
        fprintf(stderr, "%s: %s\n", mod_path, err);
        return false;
      }
      ++md.next_line;
    }
    return true;
  };
  if (md.m && !ModApplyLines(0)) return ModFail(2);

  // The MIDI effects' stage on the bridge: the sequencer's, or the bare one
  // (its own clock at --tempo).
  static fm1_mfx_t mfx;
  FILE *mfx_log = NULL;
  for (int k = 0; k < kSounds; ++k) g_units[k] = units[k];
  MfxOff mfx_off_ctx = { units, md.m };
  const fm1_mfx_sink_t mfx_off = { &mfx_off_ctx, MfxNoteOff };
  if (use_mfx) {
    fm1_mfx_init(&mfx, static_cast<uint32_t>(lrintf(rate)));
    fm1_mfx_set_tempo(&mfx, static_cast<uint32_t>(lrintf(tempo * 100.0f)));
    for (int k = 0; k < kSounds; ++k) {
      for (size_t j = 0; j < mfx_units[k].size(); ++j) {
        fm1_mfx_set(&mfx, unsigned(k), unsigned(j), fm1_midi_fx_of(mfx_units[k][j].e), mfx_units[k][j].self,
                    mfx_start_on[k][j], &mfx_off);
      }
    }
    if (!md.m) {
      fm1_seq_host_init(&bare, NULL, NULL, 0);
      fm1_seq_host_bind(&bare, sound.e);
    }
    bare.mfx = &mfx;
    if (use_seq) sq.host.mfx = &mfx;
    if (mfx_log_path && !(mfx_log = fopen(mfx_log_path, "w"))) {
      fprintf(stderr, "cannot write %s\n", mfx_log_path);
      return 1;
    }
  }

  const uint32_t total = seq_end ? static_cast<uint32_t>(seq_end)
                                 : static_cast<uint32_t>(seconds * rate);
  std::vector<float> out(static_cast<size_t>(total) * 2);
  std::vector<float> raw(out.size());
  std::vector<bool> done(events.size(), false);
  fm1_mix_limiter_t limiter;
  fm1_mix_limiter_init(&limiter, rate);
  fm1_seq_click_t click;
  fm1_seq_click_init(&click, static_cast<uint32_t>(lrintf(rate)));
  uint32_t noise = 0x12345678u;       // deterministic white noise
  double sine_phase = 0.0;
  double render_ns = 0.0, seq_ns = 0.0;
  uint32_t blocks = 0;
  bool implicit_play = use_seq && !cmd_path;   // --seq alone plays the set from the start

  for (uint32_t pos = 0; pos < total; pos += max_frames) {
    const double now = pos / static_cast<double>(rate);
    const uint32_t n = total - pos < max_frames ? total - pos : max_frames;
    float *block = &out[static_cast<size_t>(pos) * 2];
    for (size_t k = 0; k < mfx_controls.size(); ++k) {   // the MIDI effects', in the order given
      MfxControl &c = mfx_controls[k];
      if (c.done || c.time > now) continue;
      if (c.on_off) {
        fm1_mfx_set_on(&mfx, unsigned(c.sound), unsigned(c.slot), c.value != 0.0f, &mfx_off);
      } else {
        Unit &u = mfx_units[c.sound][c.slot];
        u.e->set_param(u.self, c.index, c.value);
      }
      c.done = true;
    }
    for (size_t k = 0; k < fx_controls.size(); ++k) {  // the effects' turns, in the order given
      FxControl &c = fx_controls[k];
      if (c.done || c.time > now) continue;
      const float v = md.m && c.unit < 2
          ? fm1_mod_set_base(md.m, static_cast<unsigned>(c.unit + 1), c.index, c.value) : c.value;
      fx[c.unit].e->set_param(fx[c.unit].self, c.index, v);
      c.done = true;
    }
    if (slots) {
      for (size_t k = 0; k < controls.size(); ++k) {   // controls first, in the order given
        Control &c = controls[k];
        if (c.done || c.time > now) continue;
        Unit &u = *units[c.sound];
        if (c.level) {
          level[c.sound] = c.value;
        } else if (c.bend) {        // sound unit k's bend is the base of its pitch (MG9)
          const float v = md.m
              ? fm1_mod_set_base(md.m, FM1_MOD_HOST, fm1_mod_host_pitch(static_cast<unsigned>(c.sound)), c.value)
              : c.value;
          u.e->pitch_bend(u.self, v);
        } else {                     // the sound unit's base (rule M1)
          const float v = md.m
              ? fm1_mod_set_base(md.m, fm1_mod_sound_unit(static_cast<unsigned>(c.sound)), c.index, c.value)
              : c.value;
          u.e->set_param(u.self, c.index, v);
        }
        c.done = true;
      }
      for (size_t k = 0; k < events.size(); ++k) {     // offs before ons, each to its unit
        Unit &u = *units[events[k].sound];
        if (!done[k] && !events[k].on && events[k].time <= now) {
          if (!(use_mfx && fm1_mfx_live_note(&mfx, unsigned(events[k].sound), events[k].key, 0))) {
            if (u.e) { u.e->note_off(u.self, events[k].key); LedgerOff(events[k].sound, events[k].key); }
            if (u.e && md.m) fm1_mod_live_sound_note(md.m, static_cast<unsigned>(events[k].sound), events[k].key, 0);
          }
          done[k] = true;
        }
      }
      for (size_t k = 0; k < events.size(); ++k) {
        Unit &u = *units[events[k].sound];
        if (!done[k] && events[k].on && events[k].time <= now) {
          if (!(use_mfx &&
                fm1_mfx_live_note(&mfx, unsigned(events[k].sound), events[k].key, events[k].velocity))) {
            if (u.e) {
              u.e->note_on(u.self, events[k].key, events[k].velocity);
              LedgerOn(events[k].sound, events[k].key);
            }
            if (u.e && md.m) {
              fm1_mod_live_sound_note(md.m, static_cast<unsigned>(events[k].sound), events[k].key,
                                      events[k].velocity);
              ModVoiceStart(md, u, static_cast<unsigned>(events[k].sound), events[k].key, pos);
            }
          }
          done[k] = true;
        }
      }
      for (size_t k = 0; k < note_controls.size(); ++k) {   // unit 0 (--engine), after the note-ons
        NoteControl &c = note_controls[k];
        if (c.done || c.time > now) continue;
        sound.e->set_param_note(sound.self, c.key, c.index, c.offset);
        c.done = true;
      }
    } else if (sound.e) {
      for (size_t k = 0; k < controls.size(); ++k) {   // controls first, in the order given
        Control &c = controls[k];
        if (c.done || c.time > now) continue;
        if (c.bend) {
          const float v = md.m ? fm1_mod_set_base(md.m, FM1_MOD_HOST, FM1_MOD_HOST_PITCH, c.value) : c.value;
          sound.e->pitch_bend(sound.self, v);
        } else {
          const float v = md.m ? fm1_mod_set_base(md.m, FM1_MOD_SOUND, c.index, c.value) : c.value;
          sound.e->set_param(sound.self, c.index, v);
        }
        c.done = true;
      }
      for (size_t k = 0; k < events.size(); ++k) {     // offs before ons at the same time
        if (!done[k] && !events[k].on && events[k].time <= now) {
          if (!(use_mfx && fm1_mfx_live_note(&mfx, 0, events[k].key, 0))) {
            sound.e->note_off(sound.self, events[k].key);
            LedgerOff(0, events[k].key);
            if (md.m) fm1_mod_live_note(md.m, events[k].key, 0);
          }
          done[k] = true;
        }
      }
      for (size_t k = 0; k < events.size(); ++k) {
        if (!done[k] && events[k].on && events[k].time <= now) {
          if (!(use_mfx && fm1_mfx_live_note(&mfx, 0, events[k].key, events[k].velocity))) {
            sound.e->note_on(sound.self, events[k].key, events[k].velocity);
            LedgerOn(0, events[k].key);
            if (md.m) {
              fm1_mod_live_note(md.m, events[k].key, events[k].velocity);
              ModVoiceStart(md, sound, 0, events[k].key, pos);
            }
          }
          done[k] = true;
        }
      }
      for (size_t k = 0; k < note_controls.size(); ++k) {   // after the note-ons, in the order given
        NoteControl &c = note_controls[k];
        if (c.done || c.time > now) continue;
        sound.e->set_param_note(sound.self, c.key, c.index, c.offset);
        c.done = true;
      }
    } else {
      for (uint32_t f = 0; f < n; ++f) {
        float x = 0.0f;
        if (input == "impulse") {
          x = (pos + f == 0) ? 1.0f : 0.0f;
        } else if (input == "noise") {
          noise = noise * 1664525u + 1013904223u;
          x = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
        } else if (input == "sine") {
          x = 0.5f * static_cast<float>(sin(sine_phase));
          sine_phase += 2.0 * 3.141592653589793 * 440.0 / rate;
        }
        block[2 * f] = block[2 * f + 1] = x;
      }
    }
    uint32_t n_seq = 0;                 // the block's events, for the click
    if (use_seq) {
      // Commands due now, then the block (fm1_seq_host.h, steps 2-4).
      auto s0 = std::chrono::steady_clock::now();
      if (implicit_play) {
        fm1_seq_host_line(&sq.host, "play", 4);
        implicit_play = false;
      }
      while (sq.next_cmd < sq.script.n && sq.script.cmds[sq.next_cmd].frame <= pos) {
        const char *ops = sq.script.cmds[sq.next_cmd].ops;
        if (!sq.script.cmds[sq.next_cmd].snap) {     // test directives are fm1-seq's
          fm1_seq_host_line(&sq.host, ops, strlen(ops));
        }
        ++sq.next_cmd;
      }
      n_seq = fm1_seq_host_advance(&sq.host, n);
      seq_ns += std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - s0).count();
      if (sq.log) {
        for (uint32_t k = 0; k < n_seq; ++k) fm1_script_log_event(sq.log, blocks, pos, &sq.ev[k]);
      }
      sq.events += n_seq;
    }
    if (md.m) {
      if (!ModApplyLines(pos)) return ModFail(2);
      md.writes.clear();
      md.pos = pos;
    }
    // What the effects hear about this block (engine API v3, fm1_fx_host.h):
    // the sequencer's clock and its Start and Stop, or --tempo without one.
    fm1_fx_block_t fxb;
    fxb.clock = use_seq ? &sq.host.clock : NULL;
    fxb.ev = use_seq ? sq.ev.data() : NULL;
    fxb.n_ev = n_seq;
    fxb.frames = n;
    fxb.bpm = tempo;
    auto t0 = std::chrono::steady_clock::now();
    if (slots) {
      // Each unit into its own block, split at its own tracks' events; then
      // its inserts and level, and the sum in unit order.
      if (use_seq) {
        fm1_seq_host_dispatch_slots_ticks(&sq.host, n, unit_slot, kSounds, md.m ? &md.glue.hook : NULL);
      } else if (md.m) {
        fm1_seq_host_dispatch_slots_ticks(&bare, n, unit_slot, kSounds, &md.glue.hook);
      } else if (use_mfx) {
        fm1_seq_host_dispatch_slots_ticks(&bare, n, unit_slot, kSounds, NULL);
      } else {
        for (int k = 0; k < kSounds; ++k) {
          if (units[k]->e) units[k]->e->render(units[k]->self, unit_block[k].data(), n);
        }
      }
      bool first = true;
      for (int k = 0; k < kSounds; ++k) {
        if (!units[k]->e) continue;
        float *b = unit_block[k].data();
        for (size_t j = 0; j < inserts[k].size(); ++j) {   // split at their writes (MG3)
          const unsigned code = j < FM1_MOD_INSERTS ? fm1_mod_insert_unit(static_cast<unsigned>(k),
                                                                          static_cast<unsigned>(j))
                                                    : FM1_MOD_NONE;
          RenderFx(inserts[k][j], code, md.m ? &md : NULL, b, n, &fxb);
        }
        if (level[k] != 100.0f) {
          const float g = level[k] / 100.0f;
          for (uint32_t f = 0; f < 2 * n; ++f) b[f] *= g;
        }
        if (first) std::copy(b, b + 2 * n, block);
        else for (uint32_t f = 0; f < 2 * n; ++f) block[f] += b[f];
        first = false;
      }
    } else if (use_seq) {
      // Split the block at each event the engine receives (D1: an event's own
      // frame; in compat mode every event is at the block start), and where a
      // modulation tick writes to it. Without an engine the events are only
      // logged.
      fm1_seq_host_dispatch_ticks(&sq.host, n, block, sound.e ? &sink : NULL,
                                  md.m ? &md.glue.hook : NULL);
    } else if (md.m) {
      fm1_seq_host_dispatch_ticks(&bare, n, block, sound.e ? &sink : NULL, &md.glue.hook);
    } else if (use_mfx) {
      fm1_seq_host_dispatch_ticks(&bare, n, block, sound.e ? &sink : NULL, NULL);
    } else if (sound.e) {
      sound.e->render(sound.self, block, n);
    }
    if (mfx_log) {        // what the chains sent, by frame, then chain: the same at any block size
      std::vector<std::pair<std::pair<uint32_t, unsigned>, fm1_midi_ev_t> > sent;
      for (unsigned c = 0; c < FM1_MFX_CHAINS; ++c) {
        uint32_t m = 0;
        const fm1_midi_ev_t *o = fm1_mfx_output(&mfx, c, &m);
        for (uint32_t i = 0; i < m; ++i) sent.push_back(std::make_pair(std::make_pair(uint32_t(o[i].frame), c), o[i]));
      }
      std::stable_sort(sent.begin(), sent.end(),
                       [](const std::pair<std::pair<uint32_t, unsigned>, fm1_midi_ev_t> &x,
                          const std::pair<std::pair<uint32_t, unsigned>, fm1_midi_ev_t> &y) {
                         return x.first < y.first;
                       });
      for (size_t i = 0; i < sent.size(); ++i) {
        const fm1_midi_ev_t &e = sent[i].second;
        const unsigned c = sent[i].first.second;
        if (e.kind == FM1_MIDI_EV_NOTE_ON && e.b) {
          fprintf(mfx_log, "{\"t\":%llu,\"u\":%u,\"k\":\"on\",\"key\":%u,\"vel\":%u}\n",
                  static_cast<unsigned long long>(pos) + e.frame, c, e.a, e.b);
        } else {
          fprintf(mfx_log, "{\"t\":%llu,\"u\":%u,\"k\":\"off\",\"key\":%u}\n",
                  static_cast<unsigned long long>(pos) + e.frame, c, e.a);
        }
      }
    }
    for (size_t k = 0; k < faults.size(); ++k) {
      for (uint32_t f = 0; f < n; ++f) {
        if (pos + f >= faults[k].first && pos + f <= faults[k].last) {
          block[2 * f] = block[2 * f + 1] = faults[k].value;
        }
      }
    }
    for (size_t k = 0; k < fx.size(); ++k) {
      RenderFx(fx[k], static_cast<unsigned>(k + 1), md.m && k < 2 ? &md : NULL, block, n, &fxb);
    }
    if (md.m) {                       // HOST AMP, before the limiter
      uint32_t cur = 0;
      for (size_t k = 0; k < md.writes.size(); ++k) {
        const fm1_mod_write_t &w = md.writes[k].second;
        if (w.unit != FM1_MOD_HOST || w.index != FM1_MOD_HOST_AMP) continue;
        const uint32_t f = md.writes[k].first;
        if (md.amp_used && f > cur) fm1_mod_ramp_apply(&md.amp, pos + cur, block + 2u * cur, f - cur);
        fm1_mod_ramp_set(&md.amp, pos + f, w.value);
        md.amp_used = true;
        cur = f;
      }
      if (md.amp_used && cur < n) fm1_mod_ramp_apply(&md.amp, pos + cur, block + 2u * cur, n - cur);
    }
    if (use_seq) fm1_seq_click_mix(&click, sq.seq, sq.ev.data(), n_seq, n, block);   // O11, after AMP
    auto t1 = std::chrono::steady_clock::now();
    render_ns += std::chrono::duration<double, std::nano>(t1 - t0).count();
    ++blocks;
    std::copy(block, block + 2 * n, &raw[static_cast<size_t>(pos) * 2]);
    fm1_mix_limiter_process(&limiter, block, n);
  }

  float peak = 0.0f, raw_peak = 0.0f;
  uint32_t clipped = 0, raw_clipped = 0, nonfinite = 0;
  double sum2 = 0.0;
  for (size_t k = 0; k < out.size(); ++k) {
    float x = out[k], r = raw[k];
    if (!std::isfinite(r)) { ++nonfinite; continue; }
    if (fabsf(r) > raw_peak) raw_peak = fabsf(r);
    if (fabsf(r) > 1.0f) ++raw_clipped;
    float a = fabsf(x);
    if (a > peak) peak = a;
    if (a > 1.0f) ++clipped;
    sum2 += static_cast<double>(x) * x;
  }
  if (out_path && !WriteWav(out_path, out, static_cast<uint32_t>(lrintf(rate)))) {
    fprintf(stderr, "cannot write %s\n", out_path);
    return 1;
  }
  const double audio_s = total / static_cast<double>(rate);
  printf("{\"engine\":");
  if (sound.e) PrintJsonString(sound.e->id); else printf("null");
  printf(",\"fx\":[");
  for (size_t k = 0; k < fx.size(); ++k) { if (k) putchar(','); PrintJsonString(fx[k].e->id); }
  printf("],\"fx_bytes\":[");
  for (size_t k = 0; k < fx.size(); ++k) printf(k ? ",%zu" : "%zu", fx[k].bytes);
  printf("],\"input\":");
  PrintJsonString(sound.e ? "engine" : input.c_str());
  if (slots) {
    printf(",\"sounds\":[");
    for (int k = 0; k < kSounds; ++k) {
      if (k) putchar(',');
      if (units[k]->e) PrintJsonString(units[k]->e->id); else printf("null");
    }
    printf("],\"inserts\":[");
    for (int k = 0; k < kSounds; ++k) {
      printf(k ? ",[" : "[");
      for (size_t j = 0; j < inserts[k].size(); ++j) {
        if (j) putchar(',');
        PrintJsonString(inserts[k][j].e->id);
      }
      putchar(']');
    }
    printf("],\"levels\":[%g,%g,%g,%g]", level[0], level[1], level[2], level[3]);
  }
  printf(",\"rate\":%g,\"frames\":%u,\"block\":%u,"
         "\"instance_bytes\":%zu,\"raw_peak\":%.6f,\"raw_clipped\":%u,"
         "\"peak\":%.6f,\"rms\":%.6f,\"clipped\":%u,"
         "\"nonfinite\":%u,\"ns_per_block\":%.1f,\"realtime_x\":%.1f",
         rate, total, max_frames, sound.bytes, raw_peak, raw_clipped, peak,
         out.empty() ? 0.0 : sqrt(sum2 / out.size()), clipped, nonfinite,
         blocks ? render_ns / blocks : 0.0,
         render_ns > 0 ? audio_s / (render_ns * 1e-9) : 0.0);
  {
    uint32_t hung = 0;
    for (int k = 0; k < kSounds; ++k) for (int key = 0; key < 128; ++key) hung += g_sounding[k][key];
    printf(",\"notes_hung\":%u", hung);
  }
  if (use_mfx) {
    printf(",\"mfx\":[");
    for (int k = 0; k < kSounds; ++k) {
      printf(k ? ",[" : "[");
      for (size_t j = 0; j < mfx_units[k].size(); ++j) {
        if (j) putchar(',');
        PrintJsonString(mfx_units[k][j].e->id);
      }
      putchar(']');
    }
    printf("],\"mfx_bytes\":%zu,\"mfx_blocks\":%llu,\"mfx_ticks\":%llu,\"mfx_notes_in\":%llu,"
           "\"mfx_notes_out\":%llu,\"mfx_direct\":%llu,\"mfx_deferred_offs\":%llu,\"mfx_dropped\":%llu",
           sizeof(fm1_mfx_t), static_cast<unsigned long long>(mfx.stats.blocks),
           static_cast<unsigned long long>(mfx.stats.ticks),
           static_cast<unsigned long long>(mfx.stats.notes_in),
           static_cast<unsigned long long>(mfx.stats.notes_out),
           static_cast<unsigned long long>(mfx.stats.direct),
           static_cast<unsigned long long>(mfx.stats.deferred_offs),
           static_cast<unsigned long long>(mfx.stats.dropped));
    if (mfx_log) fclose(mfx_log);
  }
  if (use_seq) {
    fm1_seq_stats_t st;
    fm1_seq_get_stats(sq.seq, &st);
    printf(",\"seq_bytes\":%zu,\"seq_events\":%llu,\"seq_notes_to_engine\":%llu,"
           "\"seq_locks_to_engine\":%llu,\"seq_locks_refused\":%llu,\"seq_refused\":%lu,"
           "\"seq_dropped\":%lu,"
           "\"seq_max_block_events\":%lu,\"seq_splits\":%llu,\"seq_clicks\":%lu,"
           "\"seq_ns_per_block\":%.1f",
           sq.mem.size() - 8u, static_cast<unsigned long long>(sq.events),
           static_cast<unsigned long long>(sq.host.notes_to_engine),
           static_cast<unsigned long long>(sq.host.locks_to_engine),
           static_cast<unsigned long long>(sq.host.locks_refused),
           static_cast<unsigned long>(st.refused), static_cast<unsigned long>(st.dropped_events),
           static_cast<unsigned long>(sq.host.max_n),
           static_cast<unsigned long long>(sq.host.splits), static_cast<unsigned long>(click.clicks),
           blocks ? seq_ns / blocks : 0.0);
    {
      uint8_t root, scale;   // the project key at the end (the `key` verb's)
      fm1_seq_get_key(sq.seq, &root, &scale);
      printf(",\"seq_key\":[%u,%u]", root, scale);
    }
    if (sq.log) fclose(sq.log);
    fm1_script_free(&sq.script);
  }
  if (md.m) {
    fm1_mod_stats_t st;
    fm1_mod_plan_info_t plan;
    fm1_mod_get_stats(md.m, &st);
    fm1_mod_get_plan(md.m, &plan);
    auto bits = [](uint32_t x) { unsigned c = 0; for (; x; x &= x - 1) ++c; return c; };
    printf(",\"mod_bytes\":%zu,\"mod_ticks\":%llu,\"mod_writes\":%llu,\"mod_sound_writes\":%llu,"
           "\"mod_other_writes\":%llu,\"mod_active\":%u,\"mod_refused\":%u,\"mod_delayed\":%u,"
           "\"mod_splits\":%llu,\"mod_edges_dropped\":%u,\"mod_nonfinite\":%u,"
           "\"mod_refused_bits\":%u,\"mod_voice_slots\":%u,\"mod_poly\":%u,\"mod_voice_cap\":%u,"
           "\"mod_voice_bytes\":%u,\"mod_voice_starts\":%u,\"mod_voice_steals\":%u,"
           "\"mod_voice_ends\":%u,\"mod_voice_writes\":%llu",
           fm1_mod_size(), static_cast<unsigned long long>(st.ticks),
           static_cast<unsigned long long>(st.writes),
           static_cast<unsigned long long>(md.glue.sound_writes),
           static_cast<unsigned long long>(md.glue.other_writes), bits(plan.active),
           bits(plan.refused), bits(plan.delayed),
           static_cast<unsigned long long>(use_seq ? sq.host.splits : bare.splits),
           st.edges_dropped, st.nonfinite, static_cast<unsigned>(plan.refused),
           static_cast<unsigned>(plan.voice), static_cast<unsigned>(plan.poly),
           static_cast<unsigned>(plan.voice_cap), static_cast<unsigned>(plan.voice_bytes),
           static_cast<unsigned>(st.voice_starts), static_cast<unsigned>(st.voice_steals),
           static_cast<unsigned>(st.voice_ends), static_cast<unsigned long long>(st.voice_writes));
    if (md.log) fclose(md.log);
    fm1_mod_destroy(md.m);
    free(md.mem);
  }
  printf("}\n");
  Release(sound);
  for (size_t k = 0; k < fx.size(); ++k) Release(fx[k]);
  for (int k = 1; k < kSounds; ++k) Release(more[k]);
  for (int k = 0; k < kSounds; ++k) {
    for (size_t j = 0; j < inserts[k].size(); ++j) Release(inserts[k][j]);
    for (size_t j = 0; j < mfx_units[k].size(); ++j) Release(mfx_units[k][j]);
  }
  return 0;
}

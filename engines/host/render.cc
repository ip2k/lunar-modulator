// render.cc -- desktop host for the engine API (docs/11 §8, stage A).
//
//   fm1-render --list
//   fm1-render --engine macro --param Model=6 --param Timbre=0
//              --note 0:69:100:1.5 --seconds 2 --out a4.wav   (one command)
//
// --list prints every engine and its parameters as JSON, with the names of
// an enum parameter's values.
//
// Renders in max_frames blocks at the FM-1's rate (44,118 Hz, 64 frames),
// passes the mix through the host's bus limiter (fm1_mix_limiter.h), writes
// 16-bit stereo WAV, and prints one line of JSON: the engine's raw peak and
// clipped count, the same after the limiter, non-finite samples, instance
// size in bytes and time per block. Note, bend (--bend) and parameter
// (--param-at) events apply at block boundaries (1.45 ms). --fill sets the
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
// its lane's label names (`target:Name`, matched by name), scaled from
// 0..127. All of that per-block hosting, and the routing default above, is
// the shared bridge (include/fm1_seq_host.h).
// The summary adds seq_dropped (events past the buffer), seq_max_block_events
// and seq_splits (render calls that start inside a block). MIT licence.

#include "fm1_engine.h"
#include "fm1_mix_limiter.h"
#include "fm1_seq.h"
#include "fm1_seq_host.h"
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
};

struct Control {                     // --bend and --param-at: one call at a time
  double time;
  bool bend;                         // pitch_bend(value), else set_param(index, value)
  std::string name;
  uint16_t index;
  float value;
  bool done;
};

void Usage() {
  fprintf(stderr,
      "usage: fm1-render --list\n"
      "       fm1-render [--engine ID [--param NAME=VALUE]... [--note T:KEY:VEL:DUR]...\n"
      "                   [--bend T:SEMITONES]... [--param-at T:NAME=VALUE]...]\n"
      "                  [--input silence|impulse|noise|sine]\n"
      "                  [--fx ID [--fx-param NAME=VALUE]...]...\n"
      "                  [--seconds S] [--rate HZ] [--frames N] [--out FILE.wav]\n"
      "                  [--fill BYTE] [--fault T[..T1]:VALUE]...\n"
      "                  [--cmd FILE] [--seq FILE.movy1] [--log-events FILE.jsonl]\n"
      "                  [--compat] [--tracks N] [--route T:engine|T:midi:CH]...\n"
      "                  [--events N]\n"
      "The source is the sound engine, or --input when there is none; each --fx\n"
      "processes it in order, then the bus limiter. --cmd and --seq drive the\n"
      "engine from the sequencer.\n");
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
void SinkNoteOn(void *ctx, uint8_t note, uint8_t vel) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->note_on(u->self, note, vel);
}
void SinkNoteOff(void *ctx, uint8_t note) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->note_off(u->self, note);
}
void SinkSetParam(void *ctx, uint16_t index, float value) {
  const Unit *u = static_cast<const Unit *>(ctx);
  u->e->set_param(u->self, index, value);
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

void List() {
  printf("[");
  for (size_t i = 0; i < fm1_engine_count; ++i) {
    const fm1_engine_t *e = fm1_engines[i];
    printf(i ? ",{" : "{");
    printf("\"id\":"); PrintJsonString(e->id);
    printf(",\"name\":"); PrintJsonString(e->name);
    printf(",\"credits\":"); PrintJsonString(e->credits);
    printf(",\"kind\":\"%s\",\"max_voices\":%u,\"params\":[",
           e->kind == FM1_KIND_SOUND ? "sound" : e->kind == FM1_KIND_AUDIO_FX ? "audio_fx" : "midi_fx",
           e->max_voices);
    for (uint16_t p = 0; p < e->n_params; ++p) {
      const fm1_param_t &q = e->params[p];
      printf(p ? ",{" : "{");
      printf("\"name\":"); PrintJsonString(q.name);
      printf(",\"type\":%d,\"min\":%g,\"max\":%g,\"def\":%g,\"page\":%u",
             q.type, q.min, q.max, q.def, q.page);
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
  uint32_t max_frames = 64;
  int fill = 0;
  std::vector<Fault> faults;
  Unit sound;
  std::vector<std::string> fx_ids;
  std::vector<Unit> fx;
  std::vector<Event> events;
  std::vector<Control> controls;
  const char *cmd_path = NULL, *seq_path = NULL, *log_path = NULL;
  bool compat = false, seconds_given = false, rate_given = false, frames_given = false;
  int tracks = -1;
  long events_cap = -1;            // --events: the block's event buffer
  std::vector<Route> routes;

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    const char *next = i + 1 < argc ? argv[i + 1] : NULL;
    if (a == "--list") { List(); return 0; }
    if (a == "--compat") { compat = true; continue; }
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
      events.push_back(Event{ t, true, uint8_t(key), uint8_t(vel) });
      events.push_back(Event{ t + dur, false, uint8_t(key), 0 });
    } else if (a == "--bend") {
      double t; float st;
      if (sscanf(next, "%lf:%f", &t, &st) != 2 || !(st >= -48.0f && st <= 48.0f)) {
        fprintf(stderr, "--bend wants T:SEMITONES, finite and within +/-48\n");
        return 2;
      }
      controls.push_back(Control{ t, true, std::string(), 0, st, false });
    } else if (a == "--param-at") {
      const char *colon = strchr(next, ':');
      std::vector<std::pair<std::string, float> > one;
      if (!colon || !ParseParam(colon + 1, &one)) { Usage(); return 2; }
      controls.push_back(Control{ atof(next), false, one[0].first, 0, one[0].second, false });
    } else { Usage(); return 2; }
  }
  if (!controls.empty() && !engine_id) {
    fprintf(stderr, "--bend and --param-at need --engine\n");
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
  if (!engine_id && fx.empty() && input == "silence" && faults.empty() && !use_seq) { Usage(); return 2; }
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
  for (size_t k = 0; k < controls.size(); ++k) {
    Control &c = controls[k];
    if (c.bend) {
      if (!sound.e->pitch_bend) { fprintf(stderr, "%s has no pitch bend\n", engine_id); return 1; }
      continue;
    }
    bool found = false;
    for (uint16_t q = 0; q < sound.e->n_params && !found; ++q) {
      if (strcasecmp(sound.e->params[q].name, c.name.c_str()) == 0) { c.index = q; found = true; }
    }
    if (!found) { fprintf(stderr, "unknown parameter for %s: %s\n", engine_id, c.name.c_str()); return 1; }
  }
  for (size_t k = 0; k < fx.size(); ++k) {
    if (!Instantiate(fx[k], fx_ids[k].c_str(), FM1_KIND_AUDIO_FX, host, fill)) return 1;
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
    if (seq_path) {
      size_t len = 0;
      char *txt = fm1_read_file(seq_path, &len);
      if (!txt || !fm1_seq_import_movy1(sq.seq, txt, len)) {
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
    sq.ev.resize(events_cap > 0 ? static_cast<size_t>(events_cap) : 65536u);
    fm1_seq_host_init(&sq.host, sq.seq, sq.ev.data(), static_cast<uint32_t>(sq.ev.size()));
  }
  const fm1_seq_sink_t sink = { &sound, sound.e, SinkRender, SinkNoteOn, SinkNoteOff, SinkSetParam };

  const uint32_t total = seq_end ? static_cast<uint32_t>(seq_end)
                                 : static_cast<uint32_t>(seconds * rate);
  std::vector<float> out(static_cast<size_t>(total) * 2);
  std::vector<float> raw(out.size());
  std::vector<bool> done(events.size(), false);
  fm1_mix_limiter_t limiter;
  fm1_mix_limiter_init(&limiter, rate);
  uint32_t noise = 0x12345678u;       // deterministic white noise
  double sine_phase = 0.0;
  double render_ns = 0.0, seq_ns = 0.0;
  uint32_t blocks = 0;
  bool implicit_play = use_seq && !cmd_path;   // --seq alone plays the set from the start

  for (uint32_t pos = 0; pos < total; pos += max_frames) {
    const double now = pos / static_cast<double>(rate);
    const uint32_t n = total - pos < max_frames ? total - pos : max_frames;
    float *block = &out[static_cast<size_t>(pos) * 2];
    if (sound.e) {
      for (size_t k = 0; k < controls.size(); ++k) {   // controls first, in the order given
        Control &c = controls[k];
        if (c.done || c.time > now) continue;
        if (c.bend) sound.e->pitch_bend(sound.self, c.value);
        else sound.e->set_param(sound.self, c.index, c.value);
        c.done = true;
      }
      for (size_t k = 0; k < events.size(); ++k) {     // offs before ons at the same time
        if (!done[k] && !events[k].on && events[k].time <= now) { sound.e->note_off(sound.self, events[k].key); done[k] = true; }
      }
      for (size_t k = 0; k < events.size(); ++k) {
        if (!done[k] && events[k].on && events[k].time <= now) { sound.e->note_on(sound.self, events[k].key, events[k].velocity); done[k] = true; }
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
      const uint32_t n_seq = fm1_seq_host_advance(&sq.host, n);
      seq_ns += std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - s0).count();
      if (sq.log) {
        for (uint32_t k = 0; k < n_seq; ++k) fm1_script_log_event(sq.log, blocks, pos, &sq.ev[k]);
      }
      sq.events += n_seq;
    }
    auto t0 = std::chrono::steady_clock::now();
    if (use_seq) {
      // Split the block at each event the engine receives (D1: an event's own
      // frame; in compat mode every event is at the block start). Without an
      // engine the events are only logged.
      fm1_seq_host_dispatch(&sq.host, n, block, sound.e ? &sink : NULL);
    } else if (sound.e) {
      sound.e->render(sound.self, block, n);
    }
    for (size_t k = 0; k < faults.size(); ++k) {
      for (uint32_t f = 0; f < n; ++f) {
        if (pos + f >= faults[k].first && pos + f <= faults[k].last) {
          block[2 * f] = block[2 * f + 1] = faults[k].value;
        }
      }
    }
    for (size_t k = 0; k < fx.size(); ++k) fx[k].e->render(fx[k].self, block, n);
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
  printf(",\"rate\":%g,\"frames\":%u,\"block\":%u,"
         "\"instance_bytes\":%zu,\"raw_peak\":%.6f,\"raw_clipped\":%u,"
         "\"peak\":%.6f,\"rms\":%.6f,\"clipped\":%u,"
         "\"nonfinite\":%u,\"ns_per_block\":%.1f,\"realtime_x\":%.1f",
         rate, total, max_frames, sound.bytes, raw_peak, raw_clipped, peak,
         out.empty() ? 0.0 : sqrt(sum2 / out.size()), clipped, nonfinite,
         blocks ? render_ns / blocks : 0.0,
         render_ns > 0 ? audio_s / (render_ns * 1e-9) : 0.0);
  if (use_seq) {
    fm1_seq_stats_t st;
    fm1_seq_get_stats(sq.seq, &st);
    printf(",\"seq_bytes\":%zu,\"seq_events\":%llu,\"seq_notes_to_engine\":%llu,"
           "\"seq_locks_to_engine\":%llu,\"seq_refused\":%lu,\"seq_dropped\":%lu,"
           "\"seq_max_block_events\":%lu,\"seq_splits\":%llu,\"seq_ns_per_block\":%.1f",
           sq.mem.size() - 8u, static_cast<unsigned long long>(sq.events),
           static_cast<unsigned long long>(sq.host.notes_to_engine),
           static_cast<unsigned long long>(sq.host.locks_to_engine),
           static_cast<unsigned long>(st.refused), static_cast<unsigned long>(st.dropped_events),
           static_cast<unsigned long>(sq.host.max_n),
           static_cast<unsigned long long>(sq.host.splits), blocks ? seq_ns / blocks : 0.0);
    if (sq.log) fclose(sq.log);
    fm1_script_free(&sq.script);
  }
  printf("}\n");
  Release(sound);
  for (size_t k = 0; k < fx.size(); ++k) Release(fx[k]);
  return 0;
}

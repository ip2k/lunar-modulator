// render.cc -- desktop host for the engine API (docs/11 §8, stage A).
//
//   fm1-render --list
//   fm1-render --engine macro --param Model=6 --param Timbre=0
//              --note 0:69:100:1.5 --seconds 2 --out a4.wav   (one command)
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
// regressions. MIT licence.

#include "fm1_engine.h"
#include "fm1_mix_limiter.h"

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
      "The source is the sound engine, or --input when there is none; each --fx\n"
      "processes it in order, then the bus limiter.\n");
}

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
      printf(",\"type\":%d,\"min\":%g,\"max\":%g,\"def\":%g,\"page\":%u}",
             q.type, q.min, q.max, q.def, q.page);
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

  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    const char *next = i + 1 < argc ? argv[i + 1] : NULL;
    if (a == "--list") { List(); return 0; }
    if (!next) { Usage(); return 2; }
    ++i;
    if (a == "--engine") engine_id = next;
    else if (a == "--out") out_path = next;
    else if (a == "--input") input = next;
    else if (a == "--seconds") seconds = atof(next);
    else if (a == "--rate") rate = static_cast<float>(atof(next));
    else if (a == "--frames") max_frames = static_cast<uint32_t>(atoi(next));
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
  if (!engine_id && fx.empty() && input == "silence" && faults.empty()) { Usage(); return 2; }
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

  const uint32_t total = static_cast<uint32_t>(seconds * rate);
  std::vector<float> out(static_cast<size_t>(total) * 2);
  std::vector<float> raw(out.size());
  std::vector<bool> done(events.size(), false);
  fm1_mix_limiter_t limiter;
  fm1_mix_limiter_init(&limiter, rate);
  uint32_t noise = 0x12345678u;       // deterministic white noise
  double sine_phase = 0.0;
  double render_ns = 0.0;
  uint32_t blocks = 0;

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
    auto t0 = std::chrono::steady_clock::now();
    if (sound.e) sound.e->render(sound.self, block, n);
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
         "\"nonfinite\":%u,\"ns_per_block\":%.1f,\"realtime_x\":%.1f}\n",
         rate, total, max_frames, sound.bytes, raw_peak, raw_clipped, peak,
         out.empty() ? 0.0 : sqrt(sum2 / out.size()), clipped, nonfinite,
         blocks ? render_ns / blocks : 0.0,
         render_ns > 0 ? audio_s / (render_ns * 1e-9) : 0.0);
  Release(sound);
  for (size_t k = 0; k < fx.size(); ++k) Release(fx[k]);
  return 0;
}

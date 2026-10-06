// smooth_test.cc -- fm1-smooth-test: drives any registered engine or effect
// through its fm1_engine_t with parameter changes at any frame, where
// fm1-render cannot (it applies --param-at only at block starts and sets an
// effect's parameters only before the first block). docs/15 stage S7b: a
// SMOOTH parameter's ramp is keyed to samples, so the output must not depend
// on how the host cuts its render calls. tests/test_engine_smooth.py runs it
// once per cut and compares the files.
//
//   fm1-smooth-test --engine ID [--split 64|1|7|random] [--schedule S]
//                   [--set NAME=VALUE@FRAME]... [--source noise|dc]
//                   [--seconds S] [--rate HZ] --out FILE.f32
//
// One process per render, so nothing global (stmlib's random generator, a
// Schwung module's once-only init) carries over from another. The output is
// every frame as raw little-endian float32, L then R, before any limiter.
//
// What it plays, at absolute frames, whatever the split:
//   - a sound engine: a note every 4,410 frames, cycling through five keys,
//     each held 3,000 frames, so voices sound across most changes (a pad
//     kit, fm1_engine.h: five of its pads, the first, which Pad focuses at
//     its default, among them);
//   - an effect: --source, generated before rendering (an LCG, or 0.5 DC);
//   - --schedule changes (the default): every parameter that is not NOLOCK,
//     in table order, k = 0, 1, ...: at frame 3,001 + 2,203k to its max (its
//     min when that is the default), 37 frames later to 30 % of its range (a
//     ramp turned mid-way), 1,003 frames after the first to its default;
//     then NaN, +inf and a value beyond the range on the first one;
//   - --schedule repeat: the same, each write sent again 5 and 20 frames
//     later, mid-ramp and before the next write (a repeated write must
//     change nothing);
//   - --schedule none: no change after the start;
//   - each --set NAME=VALUE@FRAME, in the order given, after the schedule's.
// At one frame: note-offs, parameter writes, note-ons (D2, engines/seq.md).
// Renders are cut at every event frame and at the split's boundaries:
// multiples of 64, 1 or 7, or random lengths of 1-64 from a fixed seed.
// MIT licence.

#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <algorithm>
#include <string>
#include <vector>

namespace {

struct Event {
  uint32_t frame;
  int order;        // 0 note-off, 1 parameter, 2 note-on
  uint32_t seq;     // insertion order, to keep writes at one frame in order
  int index;        // parameter index, or the key
  float value;      // parameter value, or the velocity
};

bool Before(const Event &a, const Event &b) {
  if (a.frame != b.frame) return a.frame < b.frame;
  if (a.order != b.order) return a.order < b.order;
  return a.seq < b.seq;
}

int Usage() {
  fprintf(stderr,
          "usage: fm1-smooth-test --engine ID [--split 64|1|7|random] "
          "[--schedule changes|repeat|none]\n"
          "                       [--set NAME=VALUE@FRAME]... [--source noise|dc] "
          "[--seconds S] [--rate HZ] --out FILE.f32\n");
  return 2;
}

int ParamIndex(const fm1_engine_t *e, const char *name, size_t len) {
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strlen(e->params[i].name) == len && strncmp(e->params[i].name, name, len) == 0) return i;
  }
  return -1;
}

}  // namespace

int main(int argc, char **argv) {
  const char *id = NULL, *out_path = NULL;
  std::string split = "64", schedule = "changes", source = "noise";
  double seconds = 0.6;
  float rate = 44118.0f;
  std::vector<std::string> sets;
  for (int i = 1; i < argc; ++i) {
    const std::string a = argv[i];
    if (i + 1 >= argc) return Usage();
    const char *v = argv[++i];
    if (a == "--engine") id = v;
    else if (a == "--out") out_path = v;
    else if (a == "--split") split = v;
    else if (a == "--schedule") schedule = v;
    else if (a == "--source") source = v;
    else if (a == "--seconds") seconds = atof(v);
    else if (a == "--rate") rate = static_cast<float>(atof(v));
    else if (a == "--set") sets.push_back(v);
    else return Usage();
  }
  if (!id || !out_path) return Usage();
  if (split != "64" && split != "1" && split != "7" && split != "random") return Usage();
  if (schedule != "changes" && schedule != "repeat" && schedule != "none") return Usage();
  const fm1_engine_t *e = fm1_engine_find(id);
  if (!e || e->kind == FM1_KIND_MIDI_FX) {
    fprintf(stderr, "no such engine or effect: %s\n", id);
    return 1;
  }
  const bool sound = e->kind == FM1_KIND_SOUND;
  const uint32_t total = static_cast<uint32_t>(seconds * rate);

  std::vector<Event> ev;
  uint32_t seq = 0;
  if (sound) {
    static const uint8_t kKeys[5] = { 48, 55, 60, 64, 67 };
    // A pad kit plays five of its pads instead, its first (the kick, on the
    // focused pad) every fifth note: kick, snare, clap, closed and open hat.
    static const uint8_t kPads[5] = { 0, 2, 3, 6, 10 };
    for (uint32_t f = 0, k = 0; f < total; f += 4410, ++k) {
      const int pad_note = fm1_engine_pad_note(e, kPads[k % 5] < e->pad_count ? kPads[k % 5] : 0);
      const uint8_t key = e->pad_count ? static_cast<uint8_t>(pad_note) : kKeys[k % 5];
      ev.push_back(Event{ f, 2, seq++, key, static_cast<float>(70 + 11 * (k % 5)) });
      ev.push_back(Event{ f + 3000, 0, seq++, key, 0.0f });
    }
  }
  if (schedule != "none") {
    std::vector<std::pair<uint32_t, std::pair<int, float> > > w;
    int k = 0, first = -1;
    for (uint16_t i = 0; i < e->n_params; ++i) {
      const fm1_param_t &p = e->params[i];
      if (p.flags & FM1_PARAM_NOLOCK) continue;
      if (first < 0) first = i;
      const uint32_t at = 3001u + 2203u * static_cast<uint32_t>(k++);
      w.push_back(std::make_pair(at, std::make_pair(static_cast<int>(i), p.def == p.max ? p.min : p.max)));
      w.push_back(std::make_pair(at + 37, std::make_pair(static_cast<int>(i), p.min + 0.3f * (p.max - p.min))));
      w.push_back(std::make_pair(at + 1003, std::make_pair(static_cast<int>(i), p.def)));
    }
    if (first >= 0) {
      const fm1_param_t &p = e->params[first];
      const uint32_t at = 3001u + 2203u * static_cast<uint32_t>(k);
      w.push_back(std::make_pair(at, std::make_pair(first, nanf(""))));
      w.push_back(std::make_pair(at + 500, std::make_pair(first, HUGE_VALF)));
      w.push_back(std::make_pair(at + 1000, std::make_pair(first, p.max + (p.max - p.min))));
      w.push_back(std::make_pair(at + 1500, std::make_pair(first, p.def)));
    }
    for (size_t j = 0; j < w.size(); ++j) {
      ev.push_back(Event{ w[j].first, 1, seq++, w[j].second.first, w[j].second.second });
      if (schedule == "repeat") {
        ev.push_back(Event{ w[j].first + 5, 1, seq++, w[j].second.first, w[j].second.second });
        ev.push_back(Event{ w[j].first + 20, 1, seq++, w[j].second.first, w[j].second.second });
      }
    }
  }
  for (size_t j = 0; j < sets.size(); ++j) {
    const char *s = sets[j].c_str();
    const char *eq = strchr(s, '='), *at = strrchr(s, '@');
    const int index = eq ? ParamIndex(e, s, static_cast<size_t>(eq - s)) : -1;
    if (index < 0 || !at || at < eq) {
      fprintf(stderr, "bad --set %s\n", s);
      return 2;
    }
    ev.push_back(Event{ static_cast<uint32_t>(atol(at + 1)), 1, seq++, index,
                        static_cast<float>(atof(eq + 1)) });
  }
  std::stable_sort(ev.begin(), ev.end(), Before);

  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t bytes = e->instance_size(&host);
  void *mem = NULL;
  if (posix_memalign(&mem, 16, bytes ? bytes : 16) != 0) return 1;
  memset(mem, 0xA5, bytes);
  void *self = e->create(mem, &host);
  if (!self) {
    fprintf(stderr, "%s refused the host\n", id);
    return 1;
  }

  std::vector<float> out(static_cast<size_t>(total) * 2, 0.0f);
  if (!sound) {
    uint32_t s = 0x12345678u;
    for (uint32_t f = 0; f < total; ++f) {
      s = s * 1664525u + 1013904223u;
      const float x = source == "dc" ? 0.5f : 0.5f * (static_cast<int32_t>(s) / 2147483648.0f);
      out[2 * f] = x;
      out[2 * f + 1] = source == "dc" ? x : -0.5f * x;
    }
  }
  uint32_t lcg = 7u, next_cut = 0, pos = 0;
  size_t k = 0;
  while (pos < total) {
    for (; k < ev.size() && ev[k].frame <= pos; ++k) {
      const Event &x = ev[k];
      if (x.order == 0) e->note_off(self, static_cast<uint8_t>(x.index));
      else if (x.order == 1) e->set_param(self, static_cast<uint16_t>(x.index), x.value);
      else e->note_on(self, static_cast<uint8_t>(x.index), static_cast<uint8_t>(x.value));
    }
    if (next_cut <= pos) {
      uint32_t len = 64;
      if (split == "1") len = 1;
      else if (split == "7") len = 7;
      else if (split == "random") {
        lcg = lcg * 1664525u + 1013904223u;
        len = 1 + (lcg >> 16) % 64;
      }
      next_cut = split == "random" ? pos + len : (pos / len + 1) * len;
    }
    uint32_t end = next_cut < total ? next_cut : total;
    if (k < ev.size() && ev[k].frame < end) end = ev[k].frame;
    e->render(self, &out[static_cast<size_t>(pos) * 2], end - pos);
    pos = end;
  }
  e->destroy(self);
  free(mem);

  uint32_t nonfinite = 0;
  for (size_t j = 0; j < out.size(); ++j) nonfinite += !(out[j] - out[j] == 0.0f);
  FILE *f = fopen(out_path, "wb");
  if (!f || fwrite(out.data(), sizeof(float), out.size(), f) != out.size() || fclose(f) != 0) {
    fprintf(stderr, "cannot write %s\n", out_path);
    return 1;
  }
  printf("{\"engine\":\"%s\",\"frames\":%u,\"events\":%zu,\"nonfinite\":%u}\n", id, total,
         ev.size(), nonfinite);
  return 0;
}

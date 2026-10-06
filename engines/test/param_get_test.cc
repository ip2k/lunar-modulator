// param_get_test.cc -- fm1-param-get-test: engine API v4's promise that a host
// can read back every value it can set (fm1_engine.h, get_param; engines/
// README.md, "Engine API v4"; notes/2026-10-06-state-files.md ST7), checked
// on every registered engine, effect and MIDI effect through its
// fm1_engine_t only.
//
//   get        an engine with get_param: a fresh instance reads every
//              parameter, every focus entry's included, within range (the
//              defaults where the table gives them); after random values,
//              out-of-range ones among them, are set on every entry with
//              the focus moved there, each reads back exactly what
//              set_param kept (the clamped value, an ENUM's entry as a whole
//              number), on its own entry and through FM1_FOCUS_CURRENT;
//              reading never moves the focus;
//   copy       fm1_engine_copy_params into a fresh instance gives every
//              value back, bit for bit, and the two render the same samples
//              (a kit plays every pad): a saved kit restores exactly, and
//              so does a fresh one (Sophie's pads start from patches of
//              their own, which the shim reads at create);
//   replay     an engine without get_param: random values set in a random
//              order, several times each, against a fresh instance given
//              only each parameter's last value, clamped as a host keeps
//              it, once, in table order: the same samples (MIDI effects:
//              the same events). What a host saves is then enough, and a
//              load that replays a file in uid order restores the sound.
//
// Each render starts stmlib's global generator, which the Plaits-based
// engines share, from one seed, as two fresh hosts would. One JSON line
// per engine and check; tests/test_engine_api_v4.py reads them. MIT
// licence, like the rest of this repository.

#include "fm1_engine.h"
#include "stmlib/utils/random.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <string>
#include <vector>

namespace {

const fm1_host_t kHost = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
const uint32_t kBlock = 64;
const uint32_t kBlocks = 160;        // 0.23 s

struct Rng {
  uint64_t s;
  explicit Rng(uint64_t seed) : s(seed * 0x9E3779B97F4A7C15ull + 1) {}
  uint32_t Next() {
    s ^= s << 13;
    s ^= s >> 7;
    s ^= s << 17;
    return static_cast<uint32_t>(s >> 11);
  }
  float Unit() { return (Next() & 0xFFFFFF) / 16777216.0f; }
};

struct Mem {
  void *p;
  explicit Mem(size_t n) : p(NULL) {
    if (posix_memalign(&p, 16, n ? n : 16) != 0) abort();
    memset(p, 0xA5, n);
  }
  ~Mem() { free(p); }
};

bool SameBits(float a, float b) { return memcmp(&a, &b, sizeof(a)) == 0; }

// A value for p: mostly in range, sometimes past an end (to be clamped);
// an ENUM sometimes between two entries (to be rounded).
float RandomValue(const fm1_param_t &p, Rng &r) {
  const uint32_t k = r.Next() % 16;
  const float span = p.max - p.min;
  if (k == 0) return p.min - 1.0f - span * r.Unit();
  if (k == 1) return p.max + 1.0f + span * r.Unit();
  if (p.type == FM1_PARAM_ENUM) {
    const float v = p.min + static_cast<float>(r.Next() % (static_cast<uint32_t>(span + 0.5f) + 1));
    return k == 2 ? v + 0.3f : v;
  }
  return p.min + span * r.Unit();
}

// What set_param keeps of v, as a host saves it: clamped, an ENUM rounded.
float Kept(const fm1_param_t &p, float v) {
  v = fm1_param_clamp(&p, v);
  if (p.type == FM1_PARAM_ENUM) v = floorf(v + 0.5f);
  return v;
}

std::string Num(double v) {
  char b[48];
  snprintf(b, sizeof(b), "%.9g", v);
  return b;
}

void Report(const char *engine, const char *check, bool pass, const std::string &extra) {
  printf("{\"engine\":\"%s\",\"check\":\"%s\",\"pass\":%s%s%s}\n", engine, check,
         pass ? "true" : "false", extra.empty() ? "" : ",", extra.c_str());
}

// Renders an instance: a kit's every pad, a pitched engine's chord and
// line, an effect's noise burst and tail; a MIDI effect's events as
// numbers. Returns the samples (or events) as floats.
std::vector<float> Play(const fm1_engine_t &e, void *self) {
  std::vector<float> out;
  // The Plaits-based engines draw on stmlib's one global generator (Drums
  // swaps in a pad's own around each voice): both renders start from the
  // same state of it, as two fresh hosts would.
  stmlib::Random::Seed(0x21u);
  const fm1_midi_fx_t *mfx = fm1_midi_fx_of(&e);
  if (mfx) {
    uint16_t ticks[8];
    fm1_midi_ev_t in[4], ev[FM1_MIDI_FX_OUT_MIN];
    for (uint32_t b = 0; b < kBlocks; ++b) {
      uint32_t n_in = 0;
      if (b == 0 || b == 40) {
        static const uint8_t keys[3] = { 60, 64, 67 };
        for (int k = 0; k < 3; ++k) {
          in[n_in].frame = 0;
          in[n_in].kind = b == 0 ? FM1_MIDI_EV_NOTE_ON : FM1_MIDI_EV_NOTE_OFF;
          in[n_in].a = keys[k];
          in[n_in].b = b == 0 ? static_cast<uint16_t>(90 + 10 * k) : 0;
          ++n_in;
        }
      }
      uint32_t nt = 0;
      for (uint32_t f = 0; f < kBlock; f += 16) ticks[nt++] = static_cast<uint16_t>(f);
      fm1_midi_fx_ctx_t ctx;
      memset(&ctx, 0, sizeof(ctx));
      ctx.ticks = ticks;
      ctx.n_ticks = nt;
      ctx.frames = kBlock;
      ctx.bpm_x100 = 12000;
      ctx.running = 1;
      const uint32_t n = mfx->process(self, in, n_in, &ctx, ev, FM1_MIDI_FX_OUT_MIN);
      for (uint32_t i = 0; i < n; ++i) {
        out.push_back(static_cast<float>(b * kBlock + ev[i].frame));
        out.push_back(static_cast<float>(ev[i].kind));
        out.push_back(static_cast<float>(ev[i].a));
        out.push_back(static_cast<float>(ev[i].b));
      }
    }
    return out;
  }
  std::vector<float> block(2 * kBlock);
  uint32_t noise = 0x12345u;
  for (uint32_t b = 0; b < kBlocks; ++b) {
    if (e.kind == FM1_KIND_SOUND) {
      if (e.pad_count) {
        const uint32_t pad = b / 4;
        if (b % 4 == 0 && pad < e.pad_count) e.note_on(self, static_cast<uint8_t>(e.pad_first_note + pad), 100);
      } else if (b == 0) {
        e.note_on(self, 48, 100);
        e.note_on(self, 60, 80);
        e.note_on(self, 67, 120);
      } else if (b == 60) {
        e.note_off(self, 60);
        e.note_on(self, 72, 90);
      } else if (b == 110) {
        e.note_off(self, 48);
        e.note_off(self, 67);
        e.note_off(self, 72);
      }
    } else {
      for (uint32_t i = 0; i < 2 * kBlock; ++i) {
        noise = noise * 1664525u + 1013904223u;
        block[i] = b < 60 ? (static_cast<int32_t>(noise) >> 8) * (0.5f / 8388608.0f) : 0.0f;
      }
    }
    e.render(self, block.data(), kBlock);
    out.insert(out.end(), block.begin(), block.end());
  }
  return out;
}

bool SameOutput(const std::vector<float> &a, const std::vector<float> &b, size_t *first) {
  *first = 0;
  if (a.size() != b.size()) return false;
  for (size_t i = 0; i < a.size(); ++i) {
    if (!SameBits(a[i], b[i])) {
      *first = i;
      return false;
    }
  }
  return true;
}

struct Instance {
  const fm1_engine_t &e;
  Mem mem;
  void *self;
  explicit Instance(const fm1_engine_t &eng) : e(eng), mem(eng.instance_size(&kHost)), self(NULL) {
    self = e.create(mem.p, &kHost);
  }
  ~Instance() {
    if (self && e.destroy) e.destroy(self);
  }
};

// get: fresh values in range, then random values on every entry read back.
bool CheckGet(const fm1_engine_t &e, uint64_t seed, std::string *why) {
  Instance a(e);
  if (!a.self) return true;   // refused this host: nothing to read
  const int focus = fm1_engine_focus(&e);
  const unsigned entries = focus >= 0 ? fm1_engine_focus_count(&e) : 1u;
  char b[160];
  for (uint16_t i = 0; i < e.n_params; ++i) {
    const fm1_param_t &p = e.params[i];
    for (unsigned k = 0; k < (fm1_param_per_focus(&p) ? entries : 1u); ++k) {
      const float v = e.get_param(a.self, i, fm1_param_per_focus(&p) ? static_cast<uint8_t>(k)
                                                                     : FM1_FOCUS_CURRENT);
      const bool in = v >= p.min && v <= p.max && (p.type != FM1_PARAM_ENUM || v == floorf(v));
      // A table's default is what an instance starts with, every entry's
      // where the engine keeps no other (Drums); Sophie's pads differ.
      const bool def_ok = fm1_param_per_focus(&p) && k > 0 ? true : SameBits(v, Kept(p, p.def));
      if (!in || !def_ok) {
        snprintf(b, sizeof(b), "fresh %s entry %u reads %.9g", p.name, k, v);
        *why = b;
        return false;
      }
    }
  }
  Rng r(seed);
  std::vector<float> want(e.n_params * entries, 0.0f);
  for (int round = 0; round < 3; ++round) {
    for (unsigned k = 0; k < entries; ++k) {
      if (focus >= 0) e.set_param(a.self, static_cast<uint16_t>(focus), e.params[focus].min + k);
      for (uint16_t i = 0; i < e.n_params; ++i) {
        const fm1_param_t &p = e.params[i];
        if (static_cast<int>(i) == focus) continue;
        if (!fm1_param_per_focus(&p) && k > 0) continue;
        const float v = RandomValue(p, r);
        e.set_param(a.self, i, v);
        want[i * entries + (fm1_param_per_focus(&p) ? k : 0)] = Kept(p, v);
      }
    }
  }
  const unsigned at = focus >= 0 ? r.Next() % entries : 0;
  if (focus >= 0) e.set_param(a.self, static_cast<uint16_t>(focus), e.params[focus].min + at + 0.2f);
  for (uint16_t i = 0; i < e.n_params; ++i) {
    const fm1_param_t &p = e.params[i];
    if (static_cast<int>(i) == focus) {
      const float v = e.get_param(a.self, i, 0);
      if (!SameBits(v, e.params[focus].min + at)) {
        snprintf(b, sizeof(b), "focus reads %.9g, set %u", v, at);
        *why = b;
        return false;
      }
      continue;
    }
    for (unsigned k = 0; k < (fm1_param_per_focus(&p) ? entries : 1u); ++k) {
      const float w = want[i * entries + k];
      const float v = e.get_param(a.self, i, fm1_param_per_focus(&p) ? static_cast<uint8_t>(k)
                                                                     : FM1_FOCUS_CURRENT);
      if (!SameBits(v, w)) {
        snprintf(b, sizeof(b), "%s entry %u reads %.9g, kept %.9g", p.name, k, v, w);
        *why = b;
        return false;
      }
    }
    if (fm1_param_per_focus(&p)) {
      const float w = want[i * entries + at];
      if (!SameBits(e.get_param(a.self, i, FM1_FOCUS_CURRENT), w) ||
          !SameBits(e.get_param(a.self, i, 200), w)) {
        snprintf(b, sizeof(b), "%s: the current entry does not read as entry %u", p.name, at);
        *why = b;
        return false;
      }
    }
  }
  // Reading moved nothing: a set now lands on the entry the focus names.
  for (uint16_t i = 0; i < e.n_params; ++i) {
    const fm1_param_t &p = e.params[i];
    if (!fm1_param_per_focus(&p)) continue;
    const float v = Kept(p, p.min + (p.max - p.min) * 0.25f);
    e.set_param(a.self, i, v);
    if (!SameBits(e.get_param(a.self, i, static_cast<uint8_t>(at)), v)) {
      snprintf(b, sizeof(b), "%s: a set after reading missed entry %u", p.name, at);
      *why = b;
      return false;
    }
    break;
  }
  if (e.get_param(a.self, e.n_params, 0) != 0.0f) {
    *why = "an index past the table does not read 0";
    return false;
  }
  return true;
}

// copy: get -> fm1_engine_copy_params -> the same values and samples.
bool CheckCopy(const fm1_engine_t &e, uint64_t seed, bool randomise, std::string *why) {
  Instance a(e), c(e);
  if (!a.self || !c.self) return true;
  const int focus = fm1_engine_focus(&e);
  const unsigned entries = focus >= 0 ? fm1_engine_focus_count(&e) : 1u;
  Rng r(seed);
  if (randomise) {
    for (unsigned k = 0; k < entries; ++k) {
      if (focus >= 0) e.set_param(a.self, static_cast<uint16_t>(focus), e.params[focus].min + k);
      for (uint16_t i = 0; i < e.n_params; ++i) {
        if (static_cast<int>(i) == focus) continue;
        if (!fm1_param_per_focus(&e.params[i]) && k > 0) continue;
        e.set_param(a.self, i, RandomValue(e.params[i], r));
      }
    }
    if (focus >= 0) e.set_param(a.self, static_cast<uint16_t>(focus), e.params[focus].min + r.Next() % entries);
  }
  const unsigned calls = fm1_engine_copy_params(&e, c.self, a.self);
  char b[160];
  if (!calls) {
    *why = "fm1_engine_copy_params made no call";
    return false;
  }
  for (uint16_t i = 0; i < e.n_params; ++i) {
    const fm1_param_t &p = e.params[i];
    for (unsigned k = 0; k < (fm1_param_per_focus(&p) ? entries : 1u); ++k) {
      const uint8_t f = fm1_param_per_focus(&p) ? static_cast<uint8_t>(k) : FM1_FOCUS_CURRENT;
      if (!SameBits(e.get_param(a.self, i, f), e.get_param(c.self, i, f))) {
        snprintf(b, sizeof(b), "%s entry %u: %.9g copied as %.9g", p.name, k,
                 e.get_param(a.self, i, f), e.get_param(c.self, i, f));
        *why = b;
        return false;
      }
    }
  }
  size_t first;
  const std::vector<float> x = Play(e, a.self), y = Play(e, c.self);
  if (!SameOutput(x, y, &first)) {
    snprintf(b, sizeof(b), "the copy renders otherwise from sample %zu", first);
    *why = b;
    return false;
  }
  return true;
}

// replay: a host's own record of what it set, replayed in table order.
bool CheckReplay(const fm1_engine_t &e, uint64_t seed, std::string *why) {
  Instance a(e), c(e);
  if (!a.self || !c.self) return true;
  Rng r(seed);
  std::vector<float> kept(e.n_params);
  std::vector<bool> set(e.n_params, false);
  for (uint32_t n = 0; n < 4u * e.n_params; ++n) {
    const uint16_t i = static_cast<uint16_t>(r.Next() % e.n_params);
    const float v = RandomValue(e.params[i], r);
    e.set_param(a.self, i, v);
    kept[i] = fm1_param_clamp(&e.params[i], v);   // what a host keeps
    set[i] = true;
  }
  for (uint16_t i = 0; i < e.n_params; ++i) {
    e.set_param(c.self, i, set[i] ? kept[i] : e.params[i].def);
  }
  size_t first;
  const std::vector<float> x = Play(e, a.self), y = Play(e, c.self);
  if (!SameOutput(x, y, &first)) {
    char b[96];
    snprintf(b, sizeof(b), "the replay renders otherwise from value %zu of %zu", first, x.size());
    *why = b;
    return false;
  }
  return true;
}

}  // namespace

int main(int argc, char **argv) {
  const uint64_t seeds = argc > 1 ? strtoull(argv[1], NULL, 10) : 4;
  for (size_t n = 0; n < fm1_engine_count + fm1_midi_fx_count; ++n) {
    const fm1_engine_t &e = n < fm1_engine_count ? *fm1_engines[n]
                                                 : fm1_midi_fxs[n - fm1_engine_count]->engine;
    std::string why;
    bool ok = true;
    if (e.get_param) {
      for (uint64_t s = 1; ok && s <= seeds; ++s) ok = CheckGet(e, s, &why);
      Report(e.id, "get", ok, "\"why\":\"" + why + "\"");
      ok = CheckCopy(e, 0, false, &why);
      for (uint64_t s = 1; ok && s <= seeds; ++s) ok = CheckCopy(e, s, true, &why);
      Report(e.id, "copy", ok, "\"why\":\"" + why + "\"");
    } else {
      for (uint64_t s = 1; ok && s <= seeds; ++s) ok = CheckReplay(e, s, &why);
      Report(e.id, "replay", ok, "\"why\":\"" + why + "\",\"params\":" + Num(e.n_params));
    }
  }
  return 0;
}

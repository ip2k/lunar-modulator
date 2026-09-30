// schwung_selftest.cc -- fm1-schwung-selftest: checks of the Schwung shim that
// the renderer cannot make (engines/schwung.md). Run by
// tests/test_engines_schwung.py.
//
//   fm1-schwung-selftest                        every check, one JSON line each
//   fm1-schwung-selftest --contract sw-sophie   the fm1 parameter table next to
//                                               the module's own chain_params,
//                                               ui_hierarchy and ui_pages
//
// Two probe modules written here (a sound generator and an effect) record
// what the shim sends them, which the real modules cannot report: MIDI bytes,
// parameter strings, the frame count of every call, allocations after create.
// This is a desktop tool: it allocates and prints; the shim does neither.
// MIT licence.

#include "../src/schwung_shim.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

extern "C" {
extern const fm1_engine_t fm1_engine_sw_sophie;
extern const fm1_engine_t fm1_engine_sw_psxverb;
extern const fm1::schwung::Module *const fm1_sw_sophie_module;
extern const fm1::schwung::Module *const fm1_sw_psxverb_module;
}

namespace {

using namespace fm1::schwung;

const fm1_host_t kHost = { FM1_ENGINE_API_VERSION, 44118.0f, 64 };
const size_t kGuard = 256;
int g_passed = 0;
int g_failed = 0;

std::string Quote(const char *s) {
  std::string out = "\"";
  for (; *s; ++s) {
    if (*s == '"' || *s == '\\') out += '\\';
    out += *s;
  }
  return out + "\"";
}

std::string Num(double v) {
  char b[40];
  snprintf(b, sizeof(b), "%.9g", v);
  return b;
}

void Report(const char *check, bool ok, const std::string &detail = "") {
  printf("{\"check\":\"%s\",\"ok\":%s%s%s}\n", check, ok ? "true" : "false",
         detail.empty() ? "" : ",", detail.c_str());
  if (ok) ++g_passed; else ++g_failed;
}

// Instance memory as a host would provide it, plus a guard band after it that
// must survive whatever the instance does.
struct Mem {
  unsigned char *p = NULL;
  size_t bytes = 0;
  explicit Mem(size_t n) : bytes(n) {
    void *q = NULL;
    if (posix_memalign(&q, 16, n + kGuard) != 0) abort();
    p = static_cast<unsigned char *>(q);
    memset(p, 0, n);
    memset(p + n, 0xA5, kGuard);
  }
  ~Mem() { free(p); }
  bool GuardIntact() const {
    for (size_t i = 0; i < kGuard; ++i) {
      if (p[bytes + i] != 0xA5) return false;
    }
    return true;
  }
  Mem(const Mem &) = delete;
  Mem &operator=(const Mem &) = delete;
};

// ---------------------------------------------------------------- probes ---

enum ProbeMode { PROBE_NORMAL, PROBE_OVERFLOW, PROBE_BIG };
ProbeMode g_probe_mode = PROBE_NORMAL;
struct Probe;
Probe *g_last_probe = NULL;       // the probe instance most recently created

struct Probe {
  uint8_t midi[16][3];
  int n_midi;
  char key[32];
  char val[32];
  uint32_t frame;
  int min_frames;
  int max_frames;
  int calls;
  bool realloc_kept;
  bool late_alloc_refused;
};

void *ProbeCreate(const char *module_dir, const char *defaults) {
  if (!module_dir || module_dir[0] || defaults) return NULL;  // "" and NULL expected
  if (g_probe_mode == PROBE_BIG) return fm1_sw_calloc(1, 1 << 20);
  Probe *p = static_cast<Probe *>(fm1_sw_calloc(1, sizeof(Probe)));
  if (!p) return NULL;
  p->min_frames = 1 << 30;
  g_last_probe = p;
  if (g_probe_mode == PROBE_OVERFLOW) {
    // An overflowing calloc is refused; the probe carries on regardless, and
    // the shim must still refuse the instance.
    fm1_sw_calloc(static_cast<size_t>(-1) / 2, 4);
    return p;
  }
  unsigned char *b = static_cast<unsigned char *>(fm1_sw_malloc(10));
  if (!b) return NULL;
  for (int i = 0; i < 10; ++i) b[i] = static_cast<unsigned char>(i + 1);
  b = static_cast<unsigned char *>(fm1_sw_realloc(b, 100));
  if (!b) return NULL;
  p->realloc_kept = true;
  for (int i = 0; i < 10; ++i) p->realloc_kept &= b[i] == i + 1;
  fm1_sw_free(b);
  return p;
}

void ProbeDestroy(void *inst) { fm1_sw_free(inst); }

void ProbeMidi(void *inst, const uint8_t *msg, int len, int source) {
  Probe *p = static_cast<Probe *>(inst);
  if (len != 3 || source != MOVE_MIDI_SOURCE_INTERNAL || p->n_midi >= 16) return;
  memcpy(p->midi[p->n_midi++], msg, 3);
}

void ProbeSet(void *inst, const char *key, const char *val) {
  Probe *p = static_cast<Probe *>(inst);
  snprintf(p->key, sizeof(p->key), "%s", key);
  snprintf(p->val, sizeof(p->val), "%s", val);
}

int ProbeGet(void *, const char *, char *, int) { return -1; }
int ProbeError(void *, char *, int) { return 0; }

void ProbeCount(Probe *p, int frames) {
  ++p->calls;
  if (frames < p->min_frames) p->min_frames = frames;
  if (frames > p->max_frames) p->max_frames = frames;
  if (p->calls == 1) p->late_alloc_refused = fm1_sw_malloc(16) == NULL;
}

// A ramp, so that every frame can be checked to arrive once and in order.
void ProbeRender(void *inst, int16_t *out, int frames) {
  Probe *p = static_cast<Probe *>(inst);
  ProbeCount(p, frames);
  for (int i = 0; i < frames; ++i) {
    const int16_t v = static_cast<int16_t>(p->frame++ % 20000);
    out[2 * i] = v;
    out[2 * i + 1] = static_cast<int16_t>(-v);
  }
}

void ProbeProcess(void *inst, int16_t *, int frames) {  // identity
  ProbeCount(static_cast<Probe *>(inst), frames);
}

plugin_api_v2_t g_probe_sound = {
  MOVE_PLUGIN_API_VERSION_2, ProbeCreate, ProbeDestroy, ProbeMidi, ProbeSet,
  ProbeGet, ProbeError, ProbeRender,
};
audio_fx_api_v2_t g_probe_fx = {
  AUDIO_FX_API_VERSION_2, ProbeCreate, ProbeDestroy, ProbeProcess, ProbeSet,
  ProbeGet, NULL,
};
plugin_api_v2_t *ProbeSoundInit(const host_api_v1_t *) { return &g_probe_sound; }
audio_fx_api_v2_t *ProbeFxInit(const host_api_v1_t *) { return &g_probe_fx; }

const char *const kModeNames[4] = { "A", "B", "C", "D" };
const fm1_param_t kProbeParams[4] = {
  { "Gain", FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0 },
  { "Mode", FM1_PARAM_ENUM, 0, 3, 0, kModeNames, 0 },
  { "Slot", FM1_PARAM_ENUM, 0, 15, 0, NULL, 0 },
  { "Tune", FM1_PARAM_FLOAT, -24, 24, 0, NULL, 0 },
};
const ParamKey kProbeKeys[4] = {
  { "gain", VALUE_FLOAT, 0 }, { "mode", VALUE_INDEX, 0 },
  { "slot", VALUE_INDEX, 1 }, { "tune", VALUE_FLOAT, 0 },
};
const Module kProbeSound = {
  FM1_KIND_SOUND, "probe", ProbeSoundInit, NULL, kProbeParams, kProbeKeys, 4, 4,
  4096, 2.0f,
};
const Module kProbeFx = {
  FM1_KIND_AUDIO_FX, "probe-fx", NULL, ProbeFxInit, kProbeParams, kProbeKeys, 4, 4,
  4096, 0.0f,
};

// Chunk sizes that never line up with the 64-frame module block.
const uint32_t kChunks[] = { 1, 3, 64, 7, 63, 2, 64, 13, 50, 5 };

uint32_t NextChunk(size_t *i, uint32_t left) {
  uint32_t n = kChunks[(*i)++ % (sizeof(kChunks) / sizeof(kChunks[0]))];
  return n < left ? n : left;
}

// ---------------------------------------------------------------- checks ---

void CheckArena(const char *name, const fm1_engine_t &e, const Module &m,
                size_t *used_out) {
  Mem mem(e.instance_size(&kHost));
  void *self = e.create(mem.p, &kHost);
  ArenaStats st = {};
  const bool ok = self && GetArenaStats(self, &st) && st.used > 0 &&
                  st.used <= st.capacity && st.failures == 0;
  Report("arena_bounds", ok && mem.GuardIntact(),
         "\"engine\":" + Quote(e.id) + ",\"module\":" + Quote(m.id) +
         ",\"instance_bytes\":" + Num(static_cast<double>(mem.bytes)) +
         ",\"arena_capacity\":" + Num(static_cast<double>(st.capacity)) +
         ",\"arena_used\":" + Num(static_cast<double>(st.used)) +
         ",\"allocations\":" + Num(st.allocations) +
         ",\"block\":" + Num(self ? BlockFrames(self) : 0) +
         ",\"name\":" + Quote(name));
  if (self) e.destroy(self);
  *used_out = st.used;
}

void CheckExhaustion(const fm1_engine_t &e, const Module &m, size_t used) {
  // One header short of what create_instance took: its last allocation fails.
  const size_t arena = used - 16;
  Mem mem(InstanceBytes(arena));
  void *self = CreateWithArena(m, mem.p, &kHost, arena);
  const std::string why = LastError();
  Report("arena_exhaustion_refused", self == NULL && why.find("arena") != std::string::npos &&
         mem.GuardIntact(),
         "\"engine\":" + Quote(e.id) + ",\"arena\":" + Num(static_cast<double>(arena)) +
         ",\"error\":" + Quote(why.c_str()));
  if (self) e.destroy(self);
}

void CheckProbeFailures() {
  g_probe_mode = PROBE_OVERFLOW;
  {
    Mem mem(InstanceSize(kProbeSound, &kHost));
    void *self = Create(kProbeSound, mem.p, &kHost);
    Report("overflowing_calloc_fails_create", self == NULL && mem.GuardIntact(),
           "\"error\":" + Quote(LastError()));
  }
  g_probe_mode = PROBE_BIG;
  {
    Mem mem(InstanceSize(kProbeSound, &kHost));
    void *self = Create(kProbeSound, mem.p, &kHost);
    Report("oversized_calloc_fails_create", self == NULL && mem.GuardIntact(),
           "\"error\":" + Quote(LastError()));
  }
  g_probe_mode = PROBE_NORMAL;
}

void CheckProbeSound() {
  Mem mem(InstanceSize(kProbeSound, &kHost));
  void *self = Create(kProbeSound, mem.p, &kHost);
  Probe *p = self ? g_last_probe : NULL;
  if (!p) {
    Report("probe_sound_created", false, "\"error\":" + Quote(LastError()));
    return;
  }
  Report("probe_realloc_keeps_contents", p->realloc_kept);

  // MIDI: notes, velocity 0 as note-off, pitch bend at a 2-semitone range.
  NoteOn(self, 60, 100);
  NoteOn(self, 61, 0);
  NoteOff(self, 62);
  PitchBend(self, 2.0f);
  PitchBend(self, 0.0f);
  PitchBend(self, -2.0f);
  PitchBend(self, -7.0f);
  PitchBend(self, 1.0f);
  const uint8_t want[8][3] = {
    { 0x90, 60, 100 }, { 0x80, 61, 0 }, { 0x80, 62, 0 }, { 0xE0, 0x7F, 0x7F },
    { 0xE0, 0x00, 0x40 }, { 0xE0, 0x00, 0x00 }, { 0xE0, 0x00, 0x00 }, { 0xE0, 0x00, 0x60 },
  };
  Report("midi_encoding", p->n_midi == 8 && memcmp(p->midi, want, sizeof(want)) == 0,
         "\"messages\":" + Num(p->n_midi));

  // Parameter strings.
  struct Case { uint16_t index; float value; const char *key; const char *val; };
  const Case cases[] = {
    { 0, 0.35f, "gain", "0.350000" }, { 0, 7.0f, "gain", "1.000000" },
    { 0, NAN, "gain", "0.000000" }, { 1, 2.4f, "mode", "2" }, { 1, 9.0f, "mode", "3" },
    { 2, 15.0f, "slot", "16" }, { 2, 0.0f, "slot", "1" },
    { 3, -5.25f, "tune", "-5.250000" }, { 3, -24.0f, "tune", "-24.000000" },
    { 3, 12.5f, "tune", "12.500000" },
  };
  bool strings_ok = true;
  std::string bad;
  for (const Case &c : cases) {
    SetParam(self, c.index, c.value);
    if (strcmp(p->key, c.key) != 0 || strcmp(p->val, c.val) != 0) {
      strings_ok = false;
      bad = std::string(p->key) + "=" + p->val;
    }
  }
  SetParam(self, 4, 1.0f);   // out of range: ignored
  Report("parameter_strings", strings_ok && strcmp(p->key, "tune") == 0,
         "\"last_bad\":" + Quote(bad.c_str()));

  // Render-ahead: any chunking yields the module's ramp, every frame once, and
  // the module is always asked for exactly one block.
  const uint32_t total = 5000;
  std::vector<float> out(2 * total);
  size_t ci = 0;
  for (uint32_t pos = 0; pos < total;) {
    const uint32_t n = NextChunk(&ci, total - pos);
    Render(self, &out[2 * pos], n);
    pos += n;
  }
  bool ramp_ok = true;
  for (uint32_t i = 0; i < total; ++i) {
    const float v = static_cast<float>(i % 20000) / 32768.0f;
    ramp_ok &= out[2 * i] == v && out[2 * i + 1] == -v;
  }
  Report("sound_reblocking", ramp_ok && p->min_frames == 64 && p->max_frames == 64,
         "\"min_frames\":" + Num(p->min_frames) + ",\"max_frames\":" + Num(p->max_frames));

  const uint32_t late_before = LateAllocations();
  SetParam(self, 0, 0.5f);
  Report("allocation_after_create_refused", p->late_alloc_refused && late_before >= 1,
         "\"late_allocations\":" + Num(late_before));
  Destroy(self);
}

void CheckProbeFx() {
  Mem mem(InstanceSize(kProbeFx, &kHost));
  void *self = Create(kProbeFx, mem.p, &kHost);
  Probe *p = self ? g_last_probe : NULL;
  if (!p) {
    Report("probe_fx_created", false, "\"error\":" + Quote(LastError()));
    return;
  }
  // An identity effect through the FIFO: the input, exactly one block late.
  const uint32_t total = 3000, block = BlockFrames(self);
  std::vector<float> in(2 * total), io(2 * total);
  for (uint32_t i = 0; i < total; ++i) {
    in[2 * i] = static_cast<float>(static_cast<int>(i % 20000) - 10000) / 32768.0f;
    in[2 * i + 1] = -in[2 * i];
  }
  io = in;
  size_t ci = 0;
  for (uint32_t pos = 0; pos < total;) {
    const uint32_t n = NextChunk(&ci, total - pos);
    Render(self, &io[2 * pos], n);
    pos += n;
  }
  bool ok = true;
  for (uint32_t i = 0; i < total; ++i) {
    for (int c = 0; c < 2; ++c) {
      const float want = i < block ? 0.0f : in[2 * (i - block) + c];
      ok &= io[2 * i + c] == want;
    }
  }
  Report("fx_fifo_latency_is_one_block", ok && p->min_frames == 64 && p->max_frames == 64,
         "\"latency_frames\":" + Num(block));

  Destroy(self);

  // Out-of-range input saturates instead of wrapping, and NaN becomes 0.
  Mem mem2(InstanceSize(kProbeFx, &kHost));
  void *fx = Create(kProbeFx, mem2.p, &kHost);
  float hot[2 * 64] = { 1.5f, -1.5f, NAN, 0.25f };
  float quiet[2 * 64] = {};
  bool sat = false;
  if (fx) {
    Render(fx, hot, 64);        // comes out one block later
    Render(fx, quiet, 64);
    sat = quiet[0] == 32767.0f / 32768.0f && quiet[1] == -1.0f && quiet[2] == 0.0f &&
          quiet[3] == 0.25f;
    Destroy(fx);
  }
  Report("fx_input_saturates", sat);
}

void CheckBlockSizes() {
  const uint32_t hosts[][2] = { { 64, 64 }, { 1, 2 }, { 37, 36 }, { 128, 128 }, { 300, 128 } };
  bool ok = true;
  std::string seen;
  for (const auto &h : hosts) {
    const fm1_host_t host = { FM1_ENGINE_API_VERSION, 44118.0f, h[0] };
    Mem mem(InstanceSize(kProbeSound, &host));
    void *self = Create(kProbeSound, mem.p, &host);
    const uint32_t b = self ? BlockFrames(self) : 0;
    ok &= b == h[1];
    seen += (seen.empty() ? "" : ",") + Num(b);
    if (self) Destroy(self);
  }
  Report("block_size_from_host", ok, "\"blocks\":[" + seen + "]");
}

void CheckNullSafety() {
  float buf[4] = { 0.5f, 0.5f, 0.5f, 0.5f };
  Render(NULL, buf, 2);
  SetParam(NULL, 0, 1.0f);
  NoteOn(NULL, 60, 100);
  NoteOff(NULL, 60);
  PitchBend(NULL, 1.0f);
  Destroy(NULL);
  char text[8];
  Report("null_instance_is_harmless", GetParam(NULL, "x", text, 8) == -1 && buf[0] == 0.5f);
}

// The real modules give the same output however the host chunks its calls.
void CheckChunking(const fm1_engine_t &e) {
  const uint32_t total = 12000;
  std::vector<float> a(2 * total, 0.0f), b(2 * total, 0.0f);
  uint32_t noise = 0x12345678u;
  if (e.kind == FM1_KIND_AUDIO_FX) {
    for (uint32_t k = 0; k < 2 * total; k += 2) {
      noise = noise * 1664525u + 1013904223u;
      a[k] = a[k + 1] = 0.5f * (static_cast<int32_t>(noise) / 2147483648.0f);
    }
    b = a;
  }
  Mem ma(e.instance_size(&kHost)), mb(e.instance_size(&kHost));
  void *sa = e.create(ma.p, &kHost);
  void *sb = e.create(mb.p, &kHost);
  if (!sa || !sb) {
    Report("chunking_invariant", false, "\"engine\":" + Quote(e.id));
    return;
  }
  if (e.note_on) {
    e.note_on(sa, 36, 110);
    e.note_on(sb, 36, 110);
    e.note_on(sa, 42, 90);
    e.note_on(sb, 42, 90);
  }
  for (uint32_t pos = 0; pos < total; pos += 64) {
    e.render(sa, &a[2 * pos], total - pos < 64 ? total - pos : 64);
  }
  size_t ci = 0;
  for (uint32_t pos = 0; pos < total;) {
    const uint32_t n = NextChunk(&ci, total - pos);
    e.render(sb, &b[2 * pos], n);
    pos += n;
  }
  double energy = 0.0;
  for (float x : a) energy += static_cast<double>(x) * x;
  Report("chunking_invariant", a == b && energy > 0.0 && ma.GuardIntact() && mb.GuardIntact(),
         "\"engine\":" + Quote(e.id));
  e.destroy(sa);
  e.destroy(sb);
}

int Contract(const char *id) {
  const fm1_engine_t *e = NULL;
  const Module *m = NULL;
  if (strcmp(id, fm1_engine_sw_sophie.id) == 0) {
    e = &fm1_engine_sw_sophie;
    m = fm1_sw_sophie_module;
  } else if (strcmp(id, fm1_engine_sw_psxverb.id) == 0) {
    e = &fm1_engine_sw_psxverb;
    m = fm1_sw_psxverb_module;
  } else {
    fprintf(stderr, "unknown engine %s\n", id);
    return 2;
  }
  Mem mem(e->instance_size(&kHost));
  void *self = e->create(mem.p, &kHost);
  if (!self) {
    fprintf(stderr, "create failed: %s\n", LastError());
    return 1;
  }
  printf("{\"id\":%s,\"exposed\":%u,\"params\":[", Quote(e->id).c_str(), e->n_params);
  for (uint16_t i = 0; i < m->n_defined; ++i) {
    const fm1_param_t &p = m->params[i];
    const ParamKey &k = m->keys[i];
    printf("%s{\"name\":%s,\"key\":%s,\"format\":\"%s\",\"offset\":%d,\"type\":%d,"
           "\"min\":%s,\"max\":%s,\"def\":%s,\"page\":%u,\"enum_names\":",
           i ? "," : "", Quote(p.name).c_str(), Quote(k.key).c_str(),
           k.format == VALUE_INDEX ? "index" : "float", k.offset, p.type,
           Num(p.min).c_str(), Num(p.max).c_str(), Num(p.def).c_str(), p.page);
    if (p.enum_names) {
      printf("[");
      const int n = static_cast<int>(p.max - p.min + 1.5f);
      for (int j = 0; j < n; ++j) printf("%s%s", j ? "," : "", Quote(p.enum_names[j]).c_str());
      printf("]}");
    } else {
      printf("null}");
    }
  }
  printf("]");
  static char buf[1 << 16];
  const char *keys[] = { "chain_params", "ui_hierarchy", "ui_pages" };
  for (const char *key : keys) {
    const int n = GetParam(self, key, buf, sizeof(buf));
    printf(",\"%s\":%s", key, n > 0 && n < static_cast<int>(sizeof(buf)) ? buf : "null");
  }
  printf("}\n");
  e->destroy(self);
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc == 3 && strcmp(argv[1], "--contract") == 0) return Contract(argv[2]);
  if (argc != 1) {
    fprintf(stderr, "usage: fm1-schwung-selftest [--contract ENGINE_ID]\n");
    return 2;
  }
  size_t sophie_used = 0, psx_used = 0;
  CheckArena("Sophie", fm1_engine_sw_sophie, *fm1_sw_sophie_module, &sophie_used);
  CheckArena("PSX Verb", fm1_engine_sw_psxverb, *fm1_sw_psxverb_module, &psx_used);
  if (sophie_used) CheckExhaustion(fm1_engine_sw_sophie, *fm1_sw_sophie_module, sophie_used);
  if (psx_used) CheckExhaustion(fm1_engine_sw_psxverb, *fm1_sw_psxverb_module, psx_used);
  CheckProbeFailures();
  CheckProbeSound();
  CheckProbeFx();
  CheckBlockSizes();
  CheckNullSafety();
  CheckChunking(fm1_engine_sw_sophie);
  CheckChunking(fm1_engine_sw_psxverb);
  printf("{\"summary\":{\"passed\":%d,\"failed\":%d}}\n", g_passed, g_failed);
  return g_failed ? 1 : 0;
}

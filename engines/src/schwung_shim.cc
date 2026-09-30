// schwung_shim.cc -- the Schwung v2 compatibility shim; see schwung_shim.h and
// engines/schwung.md. No heap, no file I/O, no threads, no locks: the only
// memory is the fm1 instance memory the host provides, one static
// host_api_v1_t and each module's small ModuleState. MIT licence.

#include "schwung_shim.h"

#include <cstring>
#include <new>

namespace fm1 {
namespace schwung {

namespace {

// Schwung promises modules at most MOVE_FRAMES_PER_BLOCK frames per call.
const uint32_t kMaxBlock = MOVE_FRAMES_PER_BLOCK;
const size_t kAlign = 16;
const float kFromPcm = 1.0f / 32768.0f;

inline size_t AlignUp(size_t n) { return (n + (kAlign - 1)) & ~(kAlign - 1); }

struct Arena {
  unsigned char *base;
  size_t capacity;
  size_t used;
  uint32_t allocations;
  uint32_t failures;
};

struct Instance {
  const Module *module;
  void *inst;                   // the module's own instance
  plugin_api_v2_t *sound;       // exactly one of sound / fx is set
  audio_fx_api_v2_t *fx;
  Arena arena;                  // lives right after this struct
  uint32_t block;               // frames per module call, even, <= 128
  uint32_t pos;                 // sound: frames of `a` not yet served
                                // fx: frames of the current block queued in `a`
  float to_pcm;                 // fx: bus -> int16 scale, 32768 / headroom
  float from_pcm;               // int16 -> bus scale
  alignas(16) int16_t a[2 * kMaxBlock];  // sound: rendered block; fx: input
  alignas(16) int16_t b[2 * kMaxBlock];  // fx: the previous block, processed
};

// Modules keep the host pointer from their init call in a global and use it
// after create (logging from destroy, clock queries from get_param), so the
// struct must outlive every instance. There is one for every module, filled in
// once, by the first create, before any module's init has seen it, and never
// written again: a later create for a host with another rate is refused
// rather than rewriting what running instances read. The FM-1 has one rate
// and one block size.
host_api_v1_t g_host_api;
bool g_host_configured = false;
Arena *g_open_arena = NULL;     // set only while a create_instance runs
uint32_t g_late_allocations = 0;
const char *g_last_error = "";

void HostLog(const char *) {}
// 0 is the ABI's "not queued"; there is no MIDI output to queue to.
int HostMidiSend(const uint8_t *, int) { return 0; }
int HostClockStatus() { return MOVE_CLOCK_STATUS_UNAVAILABLE; }
float HostBpm() { return 120.0f; }                // the ABI's documented default
double HostBeatPosition() { return -1.0; }         // "no transport running"

// Only ever called while g_host_configured is false, when no module has been
// handed the struct yet.
void FillHostApi(int rate, uint32_t block) {
  memset(&g_host_api, 0, sizeof(g_host_api));      // reserved tail stays NULL
  g_host_api.api_version = MOVE_PLUGIN_API_VERSION;
  g_host_api.sample_rate = rate;
  g_host_api.frames_per_block = static_cast<int>(block);
  g_host_api.mapped_memory = NULL;                 // no Move mailbox, no audio in
  g_host_api.log = HostLog;
  g_host_api.midi_send_internal = HostMidiSend;
  g_host_api.midi_send_external = HostMidiSend;
  g_host_api.get_clock_status = HostClockStatus;
  g_host_api.get_bpm = HostBpm;
  g_host_api.get_beat_position = HostBeatPosition;
  // mod_emit_value, mod_clear_source, midi_inject_to_move, slot_recv_channel:
  // NULL, which the ABI defines as "not supported".
}

// The first create sets the rate and block for every module; later ones must
// match its rate. Returns false with g_last_error set when the host cannot be
// served.
bool ConfigureHost(const fm1_host_t *host) {
  if (!(host->sample_rate >= 1.0f && host->sample_rate <= 1e6f)) {  // NaN too
    g_last_error = "host sample rate out of range";
    return false;
  }
  const int rate = static_cast<int>(host->sample_rate + 0.5f);
  if (!g_host_configured) {
    FillHostApi(rate, BlockFor(host->max_frames));
    g_host_configured = true;
    return true;
  }
  if (rate != g_host_api.sample_rate) {
    g_last_error = "host sample rate differs from the one the Schwung modules were set up with";
    return false;
  }
  return true;
}

// Calls the module's init once and keeps the table it returns. Until an init
// has succeeded, no instance of the module exists, so whatever init writes
// (its own static table, its copy of the host pointer) has no reader.
bool InitModule(const Module &m) {
  ModuleState *st = m.state;
  if (!st) {
    g_last_error = "module has no ModuleState";
    return false;
  }
  if (st->ready) return true;
  ++st->inits;
  if (m.kind == FM1_KIND_SOUND && m.sound_init) {
    plugin_api_v2_t *api = m.sound_init(&g_host_api);
    if (api && api->api_version == MOVE_PLUGIN_API_VERSION_2 && api->create_instance &&
        api->render_block) {
      st->sound = api;
      st->ready = true;
    }
  } else if (m.kind == FM1_KIND_AUDIO_FX && m.fx_init) {
    // Only the fields up to get_param are read: a module's own copy of
    // audio_fx_api_v2_t may predate on_midi, and reading it would read past
    // the module's struct.
    audio_fx_api_v2_t *api = m.fx_init(&g_host_api);
    if (api && api->api_version == AUDIO_FX_API_VERSION_2 && api->create_instance &&
        api->process_block) {
      st->fx = api;
      st->ready = true;
    }
  }
  if (!st->ready) g_last_error = "module has no usable v2 API";
  return st->ready;
}

// Bump allocation from the open arena. Each block carries a kAlign-byte header
// holding its size, for realloc.
void *ArenaAlloc(size_t size, bool zero) {
  Arena *a = g_open_arena;
  if (!a) {
    ++g_late_allocations;
    return NULL;
  }
  if (size > a->capacity || kAlign + AlignUp(size) > a->capacity - a->used) {
    ++a->failures;
    return NULL;
  }
  unsigned char *block = a->base + a->used;
  memcpy(block, &size, sizeof(size));
  a->used += kAlign + AlignUp(size);
  ++a->allocations;
  unsigned char *p = block + kAlign;
  if (zero) memset(p, 0, size);
  return p;
}

inline Instance *Self(void *self) { return static_cast<Instance *>(self); }

inline int16_t ToPcm(float x, float scale) {
  float y = x * scale;
  if (!(y == y)) return 0;                         // NaN
  if (y >= 32767.0f) return 32767;
  if (y <= -32768.0f) return -32768;
  return static_cast<int16_t>(y >= 0.0f ? y + 0.5f : y - 0.5f);
}

inline int RoundToInt(float x) {
  return static_cast<int>(x >= 0.0f ? x + 0.5f : x - 0.5f);
}

char *WriteUint(char *p, uint32_t v) {
  char digits[10];
  int n = 0;
  do {
    digits[n++] = static_cast<char>('0' + v % 10);
    v /= 10;
  } while (v);
  while (n) *p++ = digits[--n];
  return p;
}

// "-12.345678": six decimals, as Schwung's own host writes floats. No printf
// and no double, so it costs nothing on a core without a double-precision FPU.
void FormatFloat(char *out, float v) {
  char *p = out;
  if (v < 0.0f) {
    *p++ = '-';
    v = -v;
  }
  if (v > 1e9f) v = 1e9f;
  uint32_t whole = static_cast<uint32_t>(v);
  uint32_t frac = static_cast<uint32_t>((v - static_cast<float>(whole)) * 1e6f + 0.5f);
  if (frac >= 1000000u) {
    ++whole;
    frac -= 1000000u;
  }
  p = WriteUint(p, whole);
  *p++ = '.';
  for (uint32_t d = 100000u; d; d /= 10) *p++ = static_cast<char>('0' + (frac / d) % 10);
  *p = '\0';
}

void FormatInt(char *out, int v) {
  char *p = out;
  if (v < 0) {
    *p++ = '-';
    v = -v;
  }
  *WriteUint(p, static_cast<uint32_t>(v)) = '\0';
}

void SendMidi(Instance *self, uint8_t status, uint8_t d1, uint8_t d2) {
  if (!self || !self->sound || !self->sound->on_midi) return;
  const uint8_t msg[3] = { status, d1, d2 };
  self->sound->on_midi(self->inst, msg, 3, MOVE_MIDI_SOURCE_INTERNAL);
}

void RenderSound(Instance *self, float *out, uint32_t frames) {
  while (frames) {
    if (!self->pos) {
      memset(self->a, 0, sizeof(self->a));
      self->sound->render_block(self->inst, self->a, static_cast<int>(self->block));
      self->pos = self->block;
    }
    const uint32_t take = frames < self->pos ? frames : self->pos;
    const int16_t *src = self->a + 2 * (self->block - self->pos);
    for (uint32_t k = 0; k < 2 * take; ++k) out[k] = src[k] * kFromPcm;
    out += 2 * take;
    frames -= take;
    self->pos -= take;
  }
}

// In place, through a FIFO one module block long: each input frame goes into
// `a`, and the frame the same distance into the previous, processed block `b`
// comes out. The latency is exactly self->block frames, whatever the host's
// frame counts are.
void ProcessFx(Instance *self, float *io, uint32_t frames) {
  while (frames) {
    const uint32_t room = self->block - self->pos;
    const uint32_t take = frames < room ? frames : room;
    int16_t *in = self->a + 2 * self->pos;
    const int16_t *done = self->b + 2 * self->pos;
    const float to_pcm = self->to_pcm, from_pcm = self->from_pcm;
    for (uint32_t k = 0; k < 2 * take; ++k) {
      const int16_t x = ToPcm(io[k], to_pcm);
      io[k] = done[k] * from_pcm;
      in[k] = x;
    }
    io += 2 * take;
    frames -= take;
    self->pos += take;
    if (self->pos == self->block) {
      self->fx->process_block(self->inst, self->a, static_cast<int>(self->block));
      memcpy(self->b, self->a, sizeof(int16_t) * 2 * self->block);
      self->pos = 0;
    }
  }
}

}  // namespace

size_t InstanceBytes(size_t arena_bytes) {
  return AlignUp(sizeof(Instance)) + AlignUp(arena_bytes);
}

size_t InstanceSize(const Module &m, const fm1_host_t *) {
  return InstanceBytes(m.arena_bytes);
}

uint32_t BlockFor(uint32_t max_frames) {
  // The host's largest block, kept even (some modules process frames in
  // pairs) and within Schwung's 128.
  uint32_t block = max_frames < kMaxBlock ? max_frames : kMaxBlock;
  block &= ~1u;
  return block < 2 ? 2 : block;
}

const host_api_v1_t *HostApi() { return g_host_configured ? &g_host_api : NULL; }

void *CreateWithArena(const Module &m, void *mem, const fm1_host_t *host,
                      size_t arena_bytes) {
  g_last_error = "";
  if (!mem || !host) {
    g_last_error = "no instance memory or host";
    return NULL;
  }
  if (!ConfigureHost(host) || !InitModule(m)) return NULL;
  const ModuleState &st = *m.state;

  Instance *self = new (mem) Instance();
  self->module = &m;
  self->sound = m.kind == FM1_KIND_SOUND ? st.sound : NULL;
  self->fx = m.kind == FM1_KIND_AUDIO_FX ? st.fx : NULL;
  self->arena.base = static_cast<unsigned char *>(mem) + AlignUp(sizeof(Instance));
  self->arena.capacity = AlignUp(arena_bytes);
  // One block size for every module's whole life, set by the first host.
  self->block = static_cast<uint32_t>(g_host_api.frames_per_block);
  const float headroom =
      self->fx && m.fx_headroom > 1.0f && m.fx_headroom <= 256.0f ? m.fx_headroom : 1.0f;
  self->to_pcm = 32768.0f / headroom;
  self->from_pcm = headroom / 32768.0f;
  void *(*create)(const char *, const char *) =
      self->sound ? self->sound->create_instance : self->fx->create_instance;

  // The module sees an empty module_dir (it has no files) and no defaults.
  g_open_arena = &self->arena;
  void *inst = create("", NULL);
  g_open_arena = NULL;

  if (self->arena.failures) {
    // Fail loudly even when the module carried on without the memory.
    g_last_error = "arena too small for create_instance";
    if (inst) {
      if (self->sound && self->sound->destroy_instance) self->sound->destroy_instance(inst);
      if (self->fx && self->fx->destroy_instance) self->fx->destroy_instance(inst);
    }
    self->~Instance();
    return NULL;
  }
  if (!inst) {
    g_last_error = "create_instance returned NULL";
    self->~Instance();
    return NULL;
  }
  self->inst = inst;
  return self;
}

void *Create(const Module &m, void *mem, const fm1_host_t *host) {
  return CreateWithArena(m, mem, host, m.arena_bytes);
}

void Destroy(void *s) {
  Instance *self = Self(s);
  if (!self) return;
  if (self->inst) {
    if (self->sound && self->sound->destroy_instance) self->sound->destroy_instance(self->inst);
    if (self->fx && self->fx->destroy_instance) self->fx->destroy_instance(self->inst);
    self->inst = NULL;
  }
  self->~Instance();
}

void NoteOn(void *s, uint8_t key, uint8_t velocity) {
  if (velocity == 0) {
    NoteOff(s, key);
    return;
  }
  SendMidi(Self(s), 0x90, key & 0x7F, velocity & 0x7F);
}

void NoteOff(void *s, uint8_t key) { SendMidi(Self(s), 0x80, key & 0x7F, 0); }

void PitchBend(void *s, float semitones) {
  Instance *self = Self(s);
  if (!self || !(self->module->bend_range > 0.0f)) return;
  float norm = semitones / self->module->bend_range;
  if (!(norm > -1.0f)) norm = -1.0f;               // NaN too
  if (norm > 1.0f) norm = 1.0f;
  int v = 8192 + RoundToInt(norm * 8192.0f);
  if (v > 16383) v = 16383;
  SendMidi(self, 0xE0, static_cast<uint8_t>(v & 0x7F), static_cast<uint8_t>((v >> 7) & 0x7F));
}

void SetParam(void *s, uint16_t index, float value) {
  Instance *self = Self(s);
  if (!self) return;
  const Module &m = *self->module;
  if (index >= m.n_defined) return;
  const fm1_param_t &p = m.params[index];
  if (!(value >= p.min)) value = p.min;            // NaN too
  if (value > p.max) value = p.max;
  const ParamKey &k = m.keys[index];
  char text[24];
  if (k.format == VALUE_INDEX) {
    FormatInt(text, RoundToInt(value) + k.offset);
  } else {
    FormatFloat(text, value);
  }
  void (*set)(void *, const char *, const char *) =
      self->sound ? self->sound->set_param : self->fx->set_param;
  if (set) set(self->inst, k.key, text);
}

void Render(void *s, float *out_lr, uint32_t frames) {
  Instance *self = Self(s);
  if (!self) return;
  if (self->sound) {
    RenderSound(self, out_lr, frames);
  } else {
    ProcessFx(self, out_lr, frames);
  }
}

int GetParam(void *s, const char *key, char *buf, int buf_len) {
  Instance *self = Self(s);
  if (!self || !key || !buf || buf_len <= 0) return -1;
  int (*get)(void *, const char *, char *, int) =
      self->sound ? self->sound->get_param : self->fx->get_param;
  return get ? get(self->inst, key, buf, buf_len) : -1;
}

uint32_t BlockFrames(void *s) { return s ? Self(s)->block : 0; }

bool GetArenaStats(void *s, ArenaStats *out) {
  Instance *self = Self(s);
  if (!self || !out) return false;
  out->capacity = self->arena.capacity;
  out->used = self->arena.used;
  out->allocations = self->arena.allocations;
  out->failures = self->arena.failures;
  return true;
}

const char *LastError() { return g_last_error; }
uint32_t LateAllocations() { return g_late_allocations; }

}  // namespace schwung
}  // namespace fm1

extern "C" {

void *fm1_sw_malloc(size_t size) { return fm1::schwung::ArenaAlloc(size, false); }

void *fm1_sw_calloc(size_t count, size_t size) {
  if (size && count > static_cast<size_t>(-1) / size) {
    if (fm1::schwung::g_open_arena) ++fm1::schwung::g_open_arena->failures;
    else ++fm1::schwung::g_late_allocations;
    return NULL;
  }
  return fm1::schwung::ArenaAlloc(count * size, true);
}

void *fm1_sw_realloc(void *ptr, size_t size) {
  using fm1::schwung::g_open_arena;
  using fm1::schwung::kAlign;
  if (!ptr) return fm1_sw_malloc(size);
  fm1::schwung::Arena *a = g_open_arena;
  unsigned char *p = static_cast<unsigned char *>(ptr);
  if (!a || p < a->base + kAlign || p > a->base + a->used) {
    // Not from the open arena: outside create, or a pointer we never gave out.
    if (a) ++a->failures;
    else ++fm1::schwung::g_late_allocations;
    return NULL;
  }
  size_t old_size;
  memcpy(&old_size, p - kAlign, sizeof(old_size));
  void *q = fm1::schwung::ArenaAlloc(size, false);
  if (q) memcpy(q, ptr, old_size < size ? old_size : size);
  return q;                     // the old block stays allocated, like free()
}

void fm1_sw_free(void *) {}     // the arena goes when the fm1 instance goes

// Modules parse their parameter strings with atof/strtof. Some C libraries'
// strtod allocate internally (newlib's big-number path takes its freelist
// from the heap on first use), and set_param may run on the audio task, so
// module sources get this instead (schwung_module_prefix.h). Up to nine
// significant digits are kept as an integer, trailing zeros are folded into
// the exponent, and the value is one float multiply or divide by an exact
// power of ten: correctly rounded while the digits fit in 24 bits, within an
// ulp otherwise. Pure float, no heap, no locale, the same on every target.
float fm1_sw_strtof(const char *s, char **end) {
  static const float kPow10[11] = {
    1e0f, 1e1f, 1e2f, 1e3f, 1e4f, 1e5f, 1e6f, 1e7f, 1e8f, 1e9f, 1e10f,
  };
  const char *p = s;
  while (*p == ' ' || (*p >= '\t' && *p <= '\r')) ++p;
  bool neg = false;
  if (*p == '+' || *p == '-') neg = *p++ == '-';
  uint32_t mant = 0;
  int kept = 0;                 // significant digits in mant
  int exp10 = 0;
  bool any = false;
  for (; *p >= '0' && *p <= '9'; ++p) {
    any = true;
    if (kept < 9) {
      mant = mant * 10u + static_cast<uint32_t>(*p - '0');
      if (mant) ++kept;
    } else {
      ++exp10;                  // an integer digit past the precision kept
    }
  }
  if (*p == '.') {
    const char *q = p + 1;
    for (; *q >= '0' && *q <= '9'; ++q) {
      any = true;
      if (kept < 9) {
        mant = mant * 10u + static_cast<uint32_t>(*q - '0');
        if (mant) ++kept;
        --exp10;
      }
    }
    if (any) p = q;             // "." alone is not a number
  }
  if (!any) {
    if (end) *end = const_cast<char *>(s);
    return 0.0f;
  }
  if (*p == 'e' || *p == 'E') {
    const char *q = p + 1;
    bool eneg = false;
    if (*q == '+' || *q == '-') eneg = *q++ == '-';
    if (*q >= '0' && *q <= '9') {
      int e = 0;
      for (; *q >= '0' && *q <= '9'; ++q) {
        if (e < 1000) e = e * 10 + (*q - '0');
      }
      exp10 += eneg ? -e : e;
      p = q;
    }
  }
  if (end) *end = const_cast<char *>(p);
  while (mant && mant % 10u == 0) {
    mant /= 10u;
    ++exp10;
  }
  float v = static_cast<float>(mant);
  if (mant) {
    // Beyond +-60 the result is inf or 0 for any 9-digit mantissa.
    if (exp10 > 60) exp10 = 60;
    if (exp10 < -60) exp10 = -60;
    for (; exp10 > 10; exp10 -= 10) v *= 1e10f;
    for (; exp10 < -10; exp10 += 10) v /= 1e10f;
    v = exp10 >= 0 ? v * kPow10[exp10] : v / kPow10[-exp10];
  }
  return neg ? -v : v;
}

}  // extern "C"

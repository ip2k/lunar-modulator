// schwung_shim.cc -- the Schwung v2 compatibility shim; see schwung_shim.h and
// engines/schwung.md. No heap, no file I/O, no threads, no locks: the only
// memory is the fm1 instance memory the host provides and one static
// host_api_v1_t. MIT licence.

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
  alignas(16) int16_t a[2 * kMaxBlock];  // sound: rendered block; fx: input
  alignas(16) int16_t b[2 * kMaxBlock];  // fx: the previous block, processed
};

// Modules keep the host pointer from their init call in a global and use it
// after create (logging from destroy, clock queries from get_param), so the
// struct must outlive every instance. There is one, filled in again by each
// Create; the FM-1 has one rate and one block size.
host_api_v1_t g_host_api;
Arena *g_open_arena = NULL;     // set only while a create_instance runs
uint32_t g_late_allocations = 0;
const char *g_last_error = "";

void HostLog(const char *) {}
// 0 is the ABI's "not queued"; there is no MIDI output to queue to.
int HostMidiSend(const uint8_t *, int) { return 0; }
int HostClockStatus() { return MOVE_CLOCK_STATUS_UNAVAILABLE; }
float HostBpm() { return 120.0f; }                // the ABI's documented default
double HostBeatPosition() { return -1.0; }         // "no transport running"

void FillHostApi(float rate, uint32_t block) {
  memset(&g_host_api, 0, sizeof(g_host_api));      // reserved tail stays NULL
  g_host_api.api_version = MOVE_PLUGIN_API_VERSION;
  g_host_api.sample_rate = static_cast<int>(rate + 0.5f);
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

inline int16_t ToPcm(float x) {
  float y = x * 32768.0f;
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
    for (uint32_t k = 0; k < 2 * take; ++k) {
      const int16_t x = ToPcm(io[k]);
      io[k] = done[k] * kFromPcm;
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

void *CreateWithArena(const Module &m, void *mem, const fm1_host_t *host,
                      size_t arena_bytes) {
  g_last_error = "";
  if (!mem || !host) {
    g_last_error = "no instance memory or host";
    return NULL;
  }
  Instance *self = new (mem) Instance();
  self->module = &m;
  self->arena.base = static_cast<unsigned char *>(mem) + AlignUp(sizeof(Instance));
  self->arena.capacity = AlignUp(arena_bytes);
  // One block size for the module's whole life: the host's largest block,
  // kept even (some modules process frames in pairs) and within Schwung's 128.
  uint32_t block = host->max_frames < kMaxBlock ? host->max_frames : kMaxBlock;
  block &= ~1u;
  self->block = block < 2 ? 2 : block;
  FillHostApi(host->sample_rate, self->block);

  void *(*create)(const char *, const char *) = NULL;
  if (m.kind == FM1_KIND_SOUND && m.sound_init) {
    self->sound = m.sound_init(&g_host_api);
    if (self->sound && self->sound->api_version == MOVE_PLUGIN_API_VERSION_2 &&
        self->sound->render_block) {
      create = self->sound->create_instance;
    }
  } else if (m.kind == FM1_KIND_AUDIO_FX && m.fx_init) {
    // Only the fields up to get_param are read: a module's own copy of
    // audio_fx_api_v2_t may predate on_midi, and reading it would read past
    // the module's struct.
    self->fx = m.fx_init(&g_host_api);
    if (self->fx && self->fx->api_version == AUDIO_FX_API_VERSION_2 &&
        self->fx->process_block) {
      create = self->fx->create_instance;
    }
  }
  if (!create) {
    g_last_error = "module has no usable v2 API";
    self->~Instance();
    return NULL;
  }

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

}  // extern "C"

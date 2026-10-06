// test_ext.cc -- "Test Ext": the smallest effect that uses engine API v3's
// extension (fm1_engine.h, fm1_fx_ext_t). It exists to prove the hosts'
// plumbing (include/fm1_fx_host.h): what each piece of a block receives, at
// which frame, at any block size. MIT licence.
//
// It passes its input through (Listen Off) or its key (Listen Key: the key
// buffer, or the input itself when the host gives none, so the output is
// then the same bit for bit), and marks what it hears with single-sample
// clicks added to both channels at the first frame of a piece:
//   Start  +Click; Stop -Click;
//   a beat +Click on a downbeat (every fourth beat from Start), +Click / 2
//          on the others.
// Probe Tempo adds bpm / 1000 to every sample (0.12 at 120 BPM), so a
// render shows the tempo the host gave.
//
// Click is read at each click: a change reaches the next one, so it has
// nothing to ramp; it is flagged CONTINUOUS as every float here is.

#include "fm1_engine.h"

#include <new>

namespace fm1 {
namespace test_ext {

enum { P_CLICK, P_PROBE, P_LISTEN, P_COUNT };

const char *const kProbeNames[2] = { "Off", "Tempo" };
const char *const kListenNames[2] = { "Off", "Key" };

// Uids (API v2) are fixed: never renumber one; a new parameter takes the next
// free uid. The switches change no state, so they lock; no MOD, as a test
// effect has no use for a rounded route.
const fm1_param_t kParams[P_COUNT] = {
  { "Click",  FM1_PARAM_FLOAT, 0, 1, 0.5f, NULL, 0, 1, FM1_PARAM_CONTINUOUS, FM1_UNIT_NONE, "Click" },
  { "Probe",  FM1_PARAM_ENUM, 0, 1, 0.0f, kProbeNames, 0, 2, 0, FM1_UNIT_NONE, "Probe" },
  { "Listen", FM1_PARAM_ENUM, 0, 1, 0.0f, kListenNames, 0, 3, 0, FM1_UNIT_NONE, "Listen" },
};

struct Instance {
  float click;
  int probe, listen;
  float bpm;                // the last tempo heard, for render
};

size_t InstanceSize(const fm1_host_t *) { return sizeof(Instance); }

void *Create(void *mem, const fm1_host_t *) {
  Instance *self = new (mem) Instance();
  self->click = kParams[P_CLICK].def;
  self->probe = 0;
  self->listen = 0;
  self->bpm = 120.0f;
  return self;
}

void Destroy(void *self) { static_cast<Instance *>(self)->~Instance(); }

void Set(void *s, uint16_t i, float v) {
  Instance *self = static_cast<Instance *>(s);
  if (i >= P_COUNT) return;
  v = fm1_param_clamp(&kParams[i], v);
  if (i == P_CLICK) self->click = v;
  else if (i == P_PROBE) self->probe = v >= 0.5f;
  else self->listen = v >= 0.5f;
}

void RenderExt(void *s, float *lr, uint32_t n, const fm1_fx_ext_t *ext) {
  Instance *self = static_cast<Instance *>(s);
  if (self->listen && ext->key_lr) {
    for (uint32_t k = 0; k < 2 * n; ++k) lr[k] = ext->key_lr[k];   // never aliases lr
  }
  self->bpm = ext->bpm;
  if (self->probe) {
    const float dc = ext->bpm * 0.001f;
    for (uint32_t k = 0; k < 2 * n; ++k) lr[k] += dc;
  }
  if (n && ext->events) {
    float mark = 0.0f;
    if (ext->events & FM1_FX_EV_STOP) mark -= self->click;
    if (ext->events & FM1_FX_EV_START) mark += self->click;
    if (ext->events & FM1_FX_EV_BEAT) mark += ext->beat % 4u == 0u ? self->click : 0.5f * self->click;
    lr[0] += mark;
    lr[1] += mark;
  }
}

void Render(void *s, float *lr, uint32_t n) {
  const Instance *self = static_cast<const Instance *>(s);
  fm1_fx_ext_t ext = {};
  ext.key_lr = NULL;
  ext.bpm = self->bpm;
  RenderExt(s, lr, n, &ext);
}

}  // namespace test_ext
}  // namespace fm1

extern "C" const fm1_engine_t fm1_engine_test_ext = {
  FM1_ENGINE_MAGIC, FM1_ENGINE_API_VERSION, FM1_KIND_AUDIO_FX,
  "test-ext", "Test Ext", "This repository (MIT)",
  fm1::test_ext::kParams, fm1::test_ext::P_COUNT, 0,
  fm1::test_ext::InstanceSize, fm1::test_ext::Create, fm1::test_ext::Destroy,
  NULL, NULL, NULL,
  fm1::test_ext::Set, fm1::test_ext::Render,
  NULL,                     // no notes, so no per-note offsets
  FM1_FX_WANT_KEY | FM1_FX_WANT_TEMPO | FM1_FX_WANT_TRANSPORT,
  fm1::test_ext::RenderExt,
  0, 0,                     // not a pad kit
  NULL,                     // API v4: no get_param, the host keeps its values
};

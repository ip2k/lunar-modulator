// fx_ext_test.cc -- fm1-fx-ext-test: engine API v3 where fm1-render cannot
// reach it (tests/test_engine_api_v3.py reads its JSON):
//
//   the extension's plumbing (include/fm1_fx_host.h): a v2 effect is called
//   through render once per piece, as before; Test Ext (src/test_ext.cc)
//   hears its key (NULL, a copy of its input, another buffer), the tempo,
//   and a real sequencer's Start, Stop and beats at their exact frames, the
//   same at block sizes 1, 7, 13 and 64;
//
//   the LOG law (fm1_engine.h): position and value at the ends, round
//   trips, a detent's ratio, and the 7-bit lock grid (fm1_seq_host.h) for
//   LOG parameters, every value 0..127 back to itself.
//
// MIT licence.

#include "fm1_engine.h"
#include "fm1_fx_host.h"
#include "fm1_seq.h"
#include "fm1_seq_host.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <vector>

extern "C" const fm1_engine_t fm1_engine_test_ext;
extern "C" const fm1_engine_t fm1_engine_test_gain;

namespace {

const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[4096];

void *Make(const fm1_engine_t *e) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  memset(g_mem, 0xA5, sizeof(g_mem));
  return e->create(g_mem, &host);
}

int Index(const fm1_engine_t *e, const char *name) {
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strcmp(e->params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  exit(2);
}

void Set(const fm1_engine_t *e, void *self, const char *name, float v) {
  e->set_param(self, static_cast<uint16_t>(Index(e, name)), v);
}

uint32_t g_noise = 1u;
float Noise() {
  g_noise = g_noise * 1664525u + 1013904223u;
  return static_cast<int32_t>(g_noise) / 2147483648.0f;
}

// ---- 1. A v2 effect through fm1_fx_render ----------------------------------

struct Count {
  int calls;
  const float *first;
  uint32_t frames;
};
Count g_count;
void CountRender(void *, float *lr, uint32_t n) {
  ++g_count.calls;
  g_count.first = lr;
  g_count.frames = n;
}

void V2() {
  // A fake v2 effect (no render_ext): one render call per piece, at the
  // piece's frames, whatever the block holds.
  fm1_engine_t fake = fm1_engine_test_gain;
  fake.render = CountRender;
  float block[128] = {};
  fm1_seq_ev_t ev[2] = {};
  ev[0].kind = FM1_SEQ_EV_START;
  ev[0].frame = 5;
  ev[1].kind = FM1_SEQ_EV_STOP;
  ev[1].frame = 9;
  fm1_seq_clock_t clock = {};
  clock.playing = 1;
  clock.threshold = 44118u * 6000u;
  clock.inc = 12000u * 96u;
  clock.accum = clock.threshold - 1u;             // a tick at frame 0
  const fm1_fx_block_t b = { &clock, ev, 2, 64, 120.0f };
  memset(&g_count, 0, sizeof(g_count));
  const uint32_t calls = fm1_fx_render(&fake, NULL, block, 3, 40, &b);
  const int ok = calls == 1 && g_count.calls == 1 && g_count.first == block + 6 && g_count.frames == 37;
  // Test Gain through fm1_fx_render equals Test Gain's render, bit for bit.
  float a[128], c[128];
  for (int i = 0; i < 128; ++i) a[i] = c[i] = Noise();
  void *self = Make(&fm1_engine_test_gain);
  Set(&fm1_engine_test_gain, self, "Gain", 1.37f);
  fm1_engine_test_gain.render(self, a, 64);
  fm1_engine_test_gain.destroy(self);
  self = Make(&fm1_engine_test_gain);
  Set(&fm1_engine_test_gain, self, "Gain", 1.37f);
  fm1_fx_render(&fm1_engine_test_gain, self, c, 0, 64, &b);
  fm1_engine_test_gain.destroy(self);
  printf("\"v2\":{\"one_call\":%s,\"same_as_render\":%s}", ok ? "true" : "false",
         memcmp(a, c, sizeof(a)) == 0 ? "true" : "false");
}

// ---- 2. The key -------------------------------------------------------------

void Key() {
  const fm1_engine_t *e = &fm1_engine_test_ext;
  float in[128], key[128], key_copy[128], out_null[128], out_copy[128], out_key[128];
  for (int i = 0; i < 128; ++i) {
    in[i] = Noise();
    key[i] = 0.25f * Noise();
  }
  memcpy(key_copy, key, sizeof(key));
  int listen_null_is_input = 1, null_is_self = 1, key_heard = 1, key_untouched = 1;
  for (int listen = 0; listen < 2; ++listen) {
    fm1_fx_ext_t ext = {};
    ext.bpm = 120.0f;
    void *self = Make(e);
    Set(e, self, "Listen", static_cast<float>(listen));
    memcpy(out_null, in, sizeof(in));
    ext.key_lr = NULL;
    e->render_ext(self, out_null, 64, &ext);
    e->destroy(self);
    self = Make(e);
    Set(e, self, "Listen", static_cast<float>(listen));
    memcpy(out_copy, in, sizeof(in));
    float self_key[128];
    memcpy(self_key, in, sizeof(in));            // a copy of its input, as the key
    ext.key_lr = self_key;
    e->render_ext(self, out_copy, 64, &ext);
    e->destroy(self);
    null_is_self &= memcmp(out_null, out_copy, sizeof(in)) == 0;
    listen_null_is_input &= memcmp(out_null, in, sizeof(in)) == 0;
    if (listen) {
      self = Make(e);
      Set(e, self, "Listen", 1.0f);
      memcpy(out_key, in, sizeof(in));
      ext.key_lr = key;
      e->render_ext(self, out_key, 64, &ext);
      e->destroy(self);
      key_heard &= memcmp(out_key, key, sizeof(key)) == 0;
      key_untouched &= memcmp(key, key_copy, sizeof(key)) == 0;
    }
  }
  // render, called directly, is render_ext with no key, no events and the
  // transport stopped (Probe Off, so the tempo does not show).
  float r1[128], r2[128];
  memcpy(r1, in, sizeof(in));
  memcpy(r2, in, sizeof(in));
  void *self = Make(e);
  e->render(self, r1, 64);
  e->destroy(self);
  self = Make(e);
  fm1_fx_ext_t ext = {};
  ext.bpm = 97.0f;
  e->render_ext(self, r2, 64, &ext);
  e->destroy(self);
  // Probe Tempo: bpm / 1000 on every sample.
  float z[128] = {};
  self = Make(e);
  Set(e, self, "Probe", 1.0f);
  ext.bpm = 90.0f;
  e->render_ext(self, z, 64, &ext);
  e->destroy(self);
  printf("\"key\":{\"null_is_self\":%s,\"listen_null_is_input\":%s,\"key_heard\":%s,"
         "\"key_untouched\":%s,\"render_is_render_ext\":%s,\"probe\":%.9g}",
         null_is_self ? "true" : "false", listen_null_is_input ? "true" : "false",
         key_heard ? "true" : "false", key_untouched ? "true" : "false",
         memcmp(r1, r2, sizeof(r1)) == 0 ? "true" : "false", z[0]);
}

// ---- 3. A sequencer's Start, Stop and beats ----------------------------------

struct Run {
  std::vector<std::pair<uint64_t, float> > clicks;   // frame, value (left)
  std::vector<uint64_t> beats;                       // the sequencer's beat ticks' frames
  std::vector<uint64_t> starts, stops;
  uint64_t pieces;
  std::vector<float> out;
};

// Silence through Test Ext (Click 0.8) while a sequencer at `bpm` plays
// from frame 0 and stops at `stop`, in blocks of `block` frames.
Run Play(uint32_t block, uint32_t bpm, uint64_t stop, uint64_t total) {
  Run r;
  r.pieces = 0;
  fm1_seq_limits_t lim;
  fm1_seq_limits_default(&lim, 4);
  std::vector<unsigned char> mem(fm1_seq_size(&lim) + 8u);
  fm1_seq_t *seq = fm1_seq_create(mem.data(), &lim, static_cast<uint32_t>(kRate));
  std::vector<fm1_seq_ev_t> ev(4096);
  fm1_seq_host_t h;
  fm1_seq_host_init(&h, seq, ev.data(), static_cast<uint32_t>(ev.size()));
  char line[32];
  snprintf(line, sizeof line, "bpm %u", bpm);
  fm1_seq_host_line(&h, line, strlen(line));
  fm1_seq_host_line(&h, "play", 4);
  const fm1_engine_t *e = &fm1_engine_test_ext;
  void *self = Make(e);
  Set(e, self, "Click", 0.8f);
  std::vector<float> buf(2u * block);
  for (uint64_t pos = 0; pos < total; pos += block) {
    if (pos == stop) fm1_seq_host_line(&h, "stop", 4);
    const uint32_t n = static_cast<uint32_t>(total - pos < block ? total - pos : block);
    const uint32_t k = fm1_seq_host_advance(&h, n);
    for (uint32_t i = 0; i < k; ++i) {
      const fm1_seq_ev_t &x = ev[i];
      if (x.kind == FM1_SEQ_EV_CLOCK && x.tick % FM1_SEQ_PPQN == 0) r.beats.push_back(pos + x.frame);
      if (x.kind == FM1_SEQ_EV_START) r.starts.push_back(pos + x.frame);
      if (x.kind == FM1_SEQ_EV_STOP) r.stops.push_back(pos + x.frame);
    }
    const fm1_fx_block_t b = { &h.clock, ev.data(), k, n, 0.0f };
    std::fill(buf.begin(), buf.end(), 0.0f);
    r.pieces += fm1_fx_render(e, self, buf.data(), 0, n, &b);
    for (uint32_t i = 0; i < n; ++i) {
      r.out.push_back(buf[2 * i]);
      if (buf[2 * i] != 0.0f) r.clicks.push_back(std::make_pair(pos + i, buf[2 * i]));
    }
    fm1_seq_host_dispatch(&h, n, NULL, NULL);
  }
  e->destroy(self);
  return r;
}

void PrintFrames(const char *name, const std::vector<uint64_t> &v) {
  printf("\"%s\":[", name);
  for (size_t i = 0; i < v.size(); ++i) printf(i ? ",%llu" : "%llu", static_cast<unsigned long long>(v[i]));
  printf("]");
}

void Transport() {
  // 2.24 s: a stop at frame 99,008, a multiple of 1, 7, 13 and 64, so
  // every block size applies it at the same frame.
  const uint64_t stop = 99008, total = 110000;
  const uint32_t blocks[] = { 64, 7, 13, 1 };
  Run ref = Play(64, 12000, stop, total);
  int same = 1;
  uint64_t pieces[4] = {};
  for (int i = 0; i < 4; ++i) {
    Run r = i ? Play(blocks[i], 12000, stop, total) : ref;
    pieces[i] = r.pieces;
    same &= r.out == ref.out;
  }
  printf("\"transport\":{\"block_independent\":%s,\"pieces\":[%llu,%llu,%llu,%llu],",
         same ? "true" : "false", static_cast<unsigned long long>(pieces[0]),
         static_cast<unsigned long long>(pieces[1]), static_cast<unsigned long long>(pieces[2]),
         static_cast<unsigned long long>(pieces[3]));
  PrintFrames("beats", ref.beats);
  printf(",");
  PrintFrames("starts", ref.starts);
  printf(",");
  PrintFrames("stops", ref.stops);
  printf(",\"clicks\":[");
  for (size_t i = 0; i < ref.clicks.size(); ++i) {
    printf("%s[%llu,%.9g]", i ? "," : "", static_cast<unsigned long long>(ref.clicks[i].first),
           ref.clicks[i].second);
  }
  printf("]}");
  // At 87.5 BPM, beats fall on frames that are not whole multiples of any
  // block: the same frames at every block size.
  Run a = Play(64, 8750, 0xFFFFFFFFu, 70000), c = Play(7, 8750, 0xFFFFFFFFu, 70000);
  printf(",\"odd_tempo\":{\"same\":%s,", a.out == c.out ? "true" : "false");
  PrintFrames("beats", a.beats);
  printf(",\"clicks\":[");
  for (size_t i = 0; i < a.clicks.size(); ++i) {
    printf(i ? ",%llu" : "%llu", static_cast<unsigned long long>(a.clicks[i].first));
  }
  printf("]}");
}

// ---- 4. Position: beat and phase at every frame of a playing clock ---------

void Position() {
  fm1_seq_clock_t clock = {};
  clock.playing = 1;
  clock.threshold = 44118u * 6000u;
  clock.inc = 13377u * 96u;                     // 133.77 BPM
  clock.master_tick = 950;                      // 9 beats and 86 ticks in
  clock.accum = 123456789u;
  clock.bpm_x100 = 13377;
  const fm1_fx_block_t b = { &clock, NULL, 0, 4096, 0.0f };
  double prev = -1.0;
  int monotonic = 1, in_range = 1, starts = 0, start_ok = 1;
  uint32_t first_beat = 0;
  for (uint32_t f = 0; f < 4096; ++f) {
    fm1_fx_ext_t ext;
    fm1_fx_block_ext(&b, f, &ext);
    const double pos = ext.beat + static_cast<double>(ext.phase);
    if (pos <= prev) monotonic = 0;
    if (!(ext.phase >= 0.0f && ext.phase < 1.0f) || !ext.running) in_range = 0;
    if (fm1_fx_block_next_beat(&b, f, f + 1) == f) {   // a beat starts at f
      ++starts;
      if (!first_beat) first_beat = f;
      if (!(ext.phase < 1e-3f) || (prev >= 0.0 && static_cast<uint32_t>(prev) + 1u != ext.beat)) {
        start_ok = 0;
      }
    }
    prev = pos;
  }
  // The frame of the first beat from the integers: tick 960 is serviced
  // where accum + (f + 1) inc first reaches (960 + 1 - 950) threshold.
  const uint64_t need = 11u * clock.threshold - clock.accum;
  const uint64_t want = (need + clock.inc - 1u) / clock.inc - 1u;
  fm1_fx_ext_t stopped;
  clock.playing = 0;
  fm1_fx_block_ext(&b, 100, &stopped);
  fm1_fx_ext_t none;
  const fm1_fx_block_t nob = { NULL, NULL, 0, 64, 87.0f };
  fm1_fx_block_ext(&nob, 3, &none);
  printf("\"position\":{\"monotonic\":%s,\"in_range\":%s,\"starts\":%d,\"start_ok\":%s,"
         "\"first_beat\":%u,\"first_beat_want\":%llu,\"bpm\":%.9g,"
         "\"stopped\":[%u,%u,%.9g,%.9g],\"no_clock\":[%u,%u,%.9g,%.9g]}",
         monotonic ? "true" : "false", in_range ? "true" : "false", starts,
         start_ok ? "true" : "false", first_beat, static_cast<unsigned long long>(want),
         0.01f * 13377.0f, stopped.running, stopped.beat, stopped.phase, stopped.bpm,
         none.running, none.beat, none.phase, none.bpm);
}

// ---- 5. The LOG law and the lock grid -----------------------------------------

void Log() {
  const fm1_param_t ps[] = {
    { "Cutoff", FM1_PARAM_FLOAT, 20, 18000, 2000, NULL, 0, 1, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "Cut" },
    { "Release", FM1_PARAM_FLOAT, 1, 1000, 100, NULL, 0, 2, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Rel" },
    { "Time", FM1_PARAM_FLOAT, 10, 1000, 300, NULL, 0, 3, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_MS, "Time" },
    { "Xover", FM1_PARAM_FLOAT, 80, 400, 250, NULL, 0, 4, FM1_PARAM_CONTINUOUS_LOG, FM1_UNIT_HZ, "Xov" },
  };
  printf("\"log\":[");
  for (size_t i = 0; i < sizeof(ps) / sizeof(ps[0]); ++i) {
    const fm1_param_t *p = &ps[i];
    double worst_trip = 0.0, worst_lock = 0.0, worst_ratio = 0.0;
    int lock_ok = 1, monotonic = 1;
    float last = 0.0f;
    for (unsigned v = 0; v <= FM1_SEQ_VAL_MAX; ++v) {
      const float x = fm1_seq_lock_value(p, v);
      if (fm1_seq_value7(p, x) != v) lock_ok = 0;
      if (v && !(x > last)) monotonic = 0;
      // the grid is geometric: value v is min x (max / min)^(v / 127)
      const double want = p->min * pow(static_cast<double>(p->max) / p->min, v / 127.0);
      worst_lock = fmax(worst_lock, fabs(x / want - 1.0));
      last = x;
    }
    for (int k = 0; k <= 1000; ++k) {
      const float u = k / 1000.0f;
      worst_trip = fmax(worst_trip, fabs(fm1_param_pos(p, fm1_param_at(p, u)) - u));
    }
    // a detent: a hundredth of the octaves, a constant ratio
    const double ratio = pow(static_cast<double>(p->max) / p->min, 0.01);
    for (int k = 10; k < 90; ++k) {
      const float a = fm1_param_at(p, k / 100.0f), b = fm1_param_at(p, (k + 1) / 100.0f);
      worst_ratio = fmax(worst_ratio, fabs(static_cast<double>(b) / a / ratio - 1.0));
    }
    printf("%s{\"name\":\"%s\",\"is_log\":%d,\"at0\":%.9g,\"at1\":%.9g,\"pos_min\":%.9g,"
           "\"pos_max\":%.9g,\"pos_nan\":%.9g,\"trip\":%.3g,\"lock_round_trip\":%s,"
           "\"lock_monotonic\":%s,\"lock_vs_geometric\":%.3g,\"detent_ratio_error\":%.3g,"
           "\"lock_ends\":[%.9g,%.9g]}",
           i ? "," : "", p->name, fm1_param_is_log(p), fm1_param_at(p, 0.0f), fm1_param_at(p, 1.0f),
           fm1_param_pos(p, p->min), fm1_param_pos(p, p->max),
           fm1_param_pos(p, NAN) - fm1_param_pos(p, p->def), worst_trip,
           lock_ok ? "true" : "false", monotonic ? "true" : "false", worst_lock, worst_ratio,
           fm1_seq_lock_value(p, 0), fm1_seq_lock_value(p, FM1_SEQ_VAL_MAX));
  }
  // A LOG flag on a parameter that cannot take it (min 0, an ENUM) is
  // ignored: the linear law.
  const fm1_param_t zero = { "Attack", FM1_PARAM_FLOAT, 0, 100, 10, NULL, 0, 9, FM1_PARAM_CONTINUOUS_LOG,
                             FM1_UNIT_MS, "Atk" };
  printf("],\"log_needs_min_above_0\":%s",
         !fm1_param_is_log(&zero) && fm1_seq_lock_value(&zero, 127) == 100.0f &&
         fm1_param_pos(&zero, 50.0f) == 0.5f ? "true" : "false");
  // fm1_math.h: exact powers of two, and the shift by a route's octaves.
  printf(",\"exp2_exact\":%s,\"log_shift\":[%.9g,%.9g,%.9g]",
         fm1_exp2f(1.0f) == 2.0f && fm1_exp2f(-2.0f) == 0.25f && fm1_exp2f(0.0f) == 1.0f &&
         fm1_log2f(8.0f) == 3.0f && fm1_log2f(1.0f) == 0.0f ? "true" : "false",
         fm1_param_log_shift(&ps[0], 1000.0f, 1.0f), fm1_param_log_shift(&ps[0], 1000.0f, -1.0f),
         fm1_param_log_shift(&ps[0], 1000.0f, 20.0f));
}

}  // namespace

int main() {
  printf("{");
  V2(); printf(",");
  Key(); printf(",");
  Transport(); printf(",");
  Position(); printf(",");
  Log();
  printf("}\n");
  return 0;
}

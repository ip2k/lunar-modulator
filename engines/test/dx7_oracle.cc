// dx7_oracle.cc -- fm1-dx7-oracle: one DX7 voice rendered by the FM6
// engine (engine id dx7, through its fm1_engine_t, the voice loaded as a
// VCED dump into User 1) and by Felucca's fm6_core.c (Leo Kuroshita,
// Apache-2.0, an integer C port of Dexed's msfa; set up in dx7_felucca.c),
// and how far apart they are (tests/test_engines_dx7.py, engines/msfa.md).
//
//   fm1-dx7-oracle --vced FILE.syx [--key K] [--vel V] [--gate S] [--seconds S]
//                  [--rate HZ] [--out-ours F.f32] [--out-ref F.f32]
//   fm1-dx7-oracle --tables        msfa's start-up tables, summarised
//   fm1-dx7-oracle --loop-check    the loop of algorithms 4 and 6 against msfa
//
// Both play the same note: key-on at frame 0, key-off at --gate (rounded to
// a whole 64-frame block, where both apply it), Volume 1 and every macro at
// its default on the engine. The engine's output is brought back to msfa's
// Q24 scale (x 2^27 at Volume 1); Felucca's is Q24. Printed, as JSON:
//   snr_db      the whole render: 10 log10(sum ref^2 / sum (ours - ref)^2);
//   env_db      the largest difference of the two 10 ms RMS envelopes, in
//               dB, over the windows where the reference is within 60 dB
//               of its loudest window;
//   peak_ours, peak_ref, rms_ours, rms_ref (Q24 units).
// --out-* write each render as float32 (Q24 units).
//
// --loop-check runs src/dx7_loop.cc's chain against msfa's FmCore on random
// operators (phases, frequencies, gains on both sides of the threshold,
// feedback histories): a chain of one operator with feedback, the sixth of
// algorithm 32, must give FmCore's own feedback operator (compute_fb) to the
// bit, output, feedback history and phases; the chains of algorithms 4 and 6
// without feedback must give FmCore's render of those algorithms to the bit.
// It prints the trials and the mismatches of each.
//
// --tables prints sums and samples of msfa's tables as the engine's first
// create fills them (Sin, Exp2, Freqlut at the rate), for the test that
// checks them against exact values (libm's last bits must not move them).
//
// MIT licence.

#include "fm1_dx7.h"
#include "fm1_engine.h"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <string>
#include <vector>

#include "../src/dx7_loop.h"
#include "../src/msfa.h"

namespace fm1_msfa {
extern int32_t lut[1025];   // freqlut.cc's table, which no msfa header declares
}

extern "C" {
void felucca_init(double rate);
void felucca_render(const uint8_t *p155, int key, int vel, int gate, int total, int32_t *out);
}

namespace {

bool ReadFile(const char *path, std::vector<uint8_t> *out) {
  FILE *f = fopen(path, "rb");
  if (!f) return false;
  uint8_t buf[4096];
  size_t got;
  while ((got = fread(buf, 1, sizeof(buf), f)) > 0) out->insert(out->end(), buf, buf + got);
  fclose(f);
  return true;
}

void WriteF32(const char *path, const std::vector<double> &x) {
  FILE *f = fopen(path, "wb");
  if (!f) return;
  for (size_t i = 0; i < x.size(); ++i) {
    const float v = static_cast<float>(x[i]);
    fwrite(&v, sizeof(v), 1, f);
  }
  fclose(f);
}

uint32_t g_seed = 12345u;
uint32_t Rand() {
  g_seed = g_seed * 1664525u + 1013904223u;
  return g_seed;
}

// A random operator: any phase, a frequency up to a quarter of the rate,
// gains up to 2^26, each under the threshold one time in four.
void RandomOp(fm1_msfa::FmOpParams *q) {
  q->phase = static_cast<int32_t>(Rand());
  q->freq = static_cast<int32_t>(Rand() >> 10);
  for (int k = 0; k < 2; ++k) {
    q->gain[k] = (Rand() & 3) ? static_cast<int32_t>(Rand() >> 6) : static_cast<int32_t>(Rand() % 1120);
  }
}

bool Same(const int32_t *a, const int32_t *b, int n) {
  for (int i = 0; i < n; ++i) {
    if (a[i] != b[i]) return false;
  }
  return true;
}

int LoopCheck(float rate) {
  // msfa's tables come from the engine's first create, as in the engine.
  const fm1_engine_t *e = fm1_engine_find("dx7");
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  std::vector<unsigned char> mem(e->instance_size(&host) + 16);
  void *self = e->create(&mem[0], &host);
  if (!self) return 1;
  static fm1_msfa::FmCore core;
  const int kN = fm1_msfa::kN;
  int trials[3] = { 0, 0, 0 }, bad[3] = { 0, 0, 0 };
  for (int t = 0; t < 3000; ++t) {
    fm1_msfa::FmOpParams a[6], b[6];
    for (int k = 0; k < 6; ++k) RandomOp(&a[k]);
    int32_t out_a[64], out_b[64], fb_a[2], fb_b[2];
    for (int i = 0; i < kN; ++i) out_a[i] = out_b[i] = static_cast<int32_t>(Rand() >> 8);
    fb_a[0] = fb_b[0] = static_cast<int32_t>(Rand() >> 6) - (1 << 25);
    fb_a[1] = fb_b[1] = static_cast<int32_t>(Rand() >> 6) - (1 << 25);
    const int kind = t % 3;
    if (kind == 0) {
      // Algorithm 32's sixth operator with feedback, kept above the threshold.
      a[0].gain[0] |= 1 << 20;
      const int shift = 1 + static_cast<int>(Rand() % 7);
      for (int k = 0; k < 6; ++k) b[k] = a[k];
      core.compute(out_a, a, 31, fb_a, shift);
      fm1::dx7::RenderWithLoop(&core, b, 31, 1, shift, fb_b, out_b);
      const bool ok = Same(out_a, out_b, kN) && Same(fb_a, fb_b, 2) &&
                      a[0].phase == b[0].phase && a[5].phase == b[5].phase;
      ++trials[0];
      bad[0] += ok ? 0 : 1;
    } else {
      // Algorithms 4 and 6 without feedback: FmCore runs no loop there.
      const int alg = kind == 1 ? 3 : 5, n = kind == 1 ? 3 : 2;
      for (int k = 0; k < 6; ++k) b[k] = a[k];
      core.compute(out_a, a, alg, fb_a, 16);
      fm1::dx7::RenderChain(b, n, false, 0, fb_b, out_b);
      int32_t saved[3][2];
      for (int j = 0; j < n; ++j) {
        saved[j][0] = b[j].gain[0];
        saved[j][1] = b[j].gain[1];
        b[j].gain[0] = b[j].gain[1] = 0;
      }
      core.compute(out_b, b, alg, fb_b, 16);
      bool ok = Same(out_a, out_b, kN);
      for (int j = 0; j < n; ++j) ok = ok && b[j].phase == a[j].phase && saved[j][1] == a[j].gain[1];
      ++trials[kind];
      bad[kind] += ok ? 0 : 1;
    }
  }
  e->destroy(self);
  printf("{\"self_feedback\":[%d,%d],\"alg4_chain\":[%d,%d],\"alg6_chain\":[%d,%d]}\n",
         trials[0], bad[0], trials[1], bad[1], trials[2], bad[2]);
  return bad[0] + bad[1] + bad[2] ? 1 : 0;
}

int Tables(float rate) {
  const fm1_engine_t *e = fm1_engine_find("dx7");
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  std::vector<unsigned char> mem(e->instance_size(&host) + 16);
  void *self = e->create(&mem[0], &host);
  if (!self) return 1;
  long long sin_sum = 0, exp_sum = 0, lut_sum = 0;
  for (int i = 0; i < SIN_N_SAMPLES << 1; ++i) sin_sum += fm1_msfa::sintab[i];
  for (int i = 0; i < EXP2_N_SAMPLES << 1; ++i) exp_sum += fm1_msfa::exp2tab[i];
  for (int i = 0; i <= 1024; ++i) lut_sum += fm1_msfa::lut[i];
  printf("{\"rate\":%g,\"sin_sum\":%lld,\"exp2_sum\":%lld,\"freqlut_sum\":%lld,"
         "\"sin\":[%d,%d,%d],\"exp2\":[%d,%d,%d],\"freqlut\":[%d,%d,%d],\"osc_fine\":[",
         rate, sin_sum, exp_sum, lut_sum,
         fm1_msfa::sintab[1], fm1_msfa::sintab[257], fm1_msfa::sintab[2047],
         fm1_msfa::exp2tab[1], fm1_msfa::exp2tab[1023], fm1_msfa::exp2tab[2047],
         fm1_msfa::lut[0], fm1_msfa::lut[512], fm1_msfa::lut[1024]);
  for (int fine = 0; fine < 100; ++fine) {     // osc_freq's fine term, libm's log
    printf("%s%d", fine ? "," : "",
           fm1_msfa::osc_freq(0, 0, 1, fine, 7) - fm1_msfa::osc_freq(0, 0, 1, 0, 7));
  }
  printf("]}\n");
  e->destroy(self);
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  const char *vced_path = NULL, *out_ours = NULL, *out_ref = NULL;
  int key = 60, vel = 100;
  double gate_s = 0.5, seconds = 1.0;
  float rate = 44118.0f;
  bool tables = false, loop_check = false;
  for (int i = 1; i < argc; ++i) {
    std::string a = argv[i];
    if (a == "--tables") { tables = true; continue; }
    if (a == "--loop-check") { loop_check = true; continue; }
    if (i + 1 >= argc) { fprintf(stderr, "%s wants a value\n", a.c_str()); return 2; }
    const char *v = argv[++i];
    if (a == "--vced") vced_path = v;
    else if (a == "--key") key = atoi(v);
    else if (a == "--vel") vel = atoi(v);
    else if (a == "--gate") gate_s = atof(v);
    else if (a == "--seconds") seconds = atof(v);
    else if (a == "--rate") rate = static_cast<float>(atof(v));
    else if (a == "--out-ours") out_ours = v;
    else if (a == "--out-ref") out_ref = v;
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 2; }
  }
  if (tables) return Tables(rate);
  if (loop_check) return LoopCheck(rate);
  std::vector<uint8_t> syx;
  if (!vced_path || !ReadFile(vced_path, &syx) || syx.size() != FM1_DX7_VCED_BYTES + 8 ||
      syx[0] != 0xF0 || syx[3] != 0x00) {
    fprintf(stderr, "--vced wants a 163-byte single-voice dump\n");
    return 2;
  }
  const int total = static_cast<int>(seconds * rate);
  const int gate = (static_cast<int>(gate_s * rate) + 63) / 64 * 64;

  // The engine.
  const fm1_engine_t *e = fm1_engine_find("dx7");
  const fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  std::vector<unsigned char> mem(e->instance_size(&host) + 16);
  void *self = e->create(&mem[0], &host);
  if (!self) { fprintf(stderr, "dx7 refused %g Hz\n", rate); return 1; }
  if (fm1_dx7_load_sysex(self, &syx[0], syx.size(), 0, NULL) != 1) return 1;
  for (uint16_t i = 0; i < e->n_params; ++i) {
    if (strcmp(e->params[i].name, "Patch") == 0) e->set_param(self, i, e->params[i].max - 31);
    if (strcmp(e->params[i].name, "Volume") == 0) e->set_param(self, i, 1.0f);
  }
  e->note_on(self, static_cast<uint8_t>(key), static_cast<uint8_t>(vel));
  std::vector<double> ours(total), ref(total);
  float block[128];
  for (int f = 0; f < total; f += 64) {
    if (f == gate) e->note_off(self, static_cast<uint8_t>(key));
    e->render(self, block, 64);
    for (int k = 0; k < 64 && f + k < total; ++k) ours[f + k] = block[2 * k] * 134217728.0;
  }
  e->destroy(self);

  // Felucca's core.
  felucca_init(rate);
  std::vector<int32_t> fel(total);
  felucca_render(&syx[6], key, vel, gate, total, &fel[0]);
  for (int i = 0; i < total; ++i) ref[i] = fel[i];

  double num = 0, den = 0, peak_o = 0, peak_r = 0, sum_o = 0, sum_r = 0;
  for (int i = 0; i < total; ++i) {
    den += (ours[i] - ref[i]) * (ours[i] - ref[i]);
    num += ref[i] * ref[i];
    sum_o += ours[i] * ours[i];
    sum_r += ref[i] * ref[i];
    if (fabs(ours[i]) > peak_o) peak_o = fabs(ours[i]);
    if (fabs(ref[i]) > peak_r) peak_r = fabs(ref[i]);
  }
  const int win = static_cast<int>(rate / 100);
  std::vector<double> eo, er;
  double loud = 0;
  for (int a = 0; a + win <= total; a += win) {
    double so = 0, sr = 0;
    for (int i = a; i < a + win; ++i) { so += ours[i] * ours[i]; sr += ref[i] * ref[i]; }
    eo.push_back(sqrt(so / win));
    er.push_back(sqrt(sr / win));
    if (er.back() > loud) loud = er.back();
  }
  double env_db = 0;
  for (size_t k = 0; k < er.size(); ++k) {
    if (er[k] < loud * 1e-3) continue;
    const double d = fabs(20 * log10((eo[k] + 1e-9) / er[k]));
    if (d > env_db) env_db = d;
  }
  printf("{\"snr_db\":%.2f,\"env_db\":%.3f,\"peak_ours\":%.0f,\"peak_ref\":%.0f,"
         "\"rms_ours\":%.1f,\"rms_ref\":%.1f,\"frames\":%d,\"gate\":%d}\n",
         den > 0 ? 10 * log10(num / den) : 999.0, env_db, peak_o, peak_r,
         sqrt(sum_o / total), sqrt(sum_r / total), total, gate);
  if (out_ours) WriteF32(out_ours, ours);
  if (out_ref) WriteF32(out_ref, ref);
  return 0;
}

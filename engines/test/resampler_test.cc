// resampler_test.cc -- fm1-resampler-test: measurements and contract checks
// for engines/include/fm1_resampler.h, run by tests/test_engines_resampler.py
// (method and results in engines/resampler.md). Each mode prints one line of
// JSON.
//
//   fm1-resampler-test sweep --in-rate A --out-rate B [--from F] [--to F] [--step S]
//       A unit sine at each input frequency through a fresh resampler; per
//       point the output component at the expected frequency (the input's, or
//       its alias), fitted by least squares: gain in dB and, for inputs below
//       the output's Nyquist, the group delay's deviation from 16 output
//       samples. Then the largest remaining component, from a Kaiser-windowed
//       FFT of what the fit leaves, below and above the pass edge
//       (0.408 x out-rate: 18 kHz at 44,118 Hz).
//   fm1-resampler-test bench --in-rate A --out-rate B [--outputs N]
//       Nanoseconds per output sample on noise, best of seven runs.
//   fm1-resampler-test passthrough
//       Equal rates: every float (no NaNs) comes out bit for bit.
//   fm1-resampler-test blocks --in-rate A --out-rate B
//       The same input taken one sample at a time, and through
//       fm1_resampler_process in uneven input and output chunks: identical.
//   fm1-resampler-test extreme --in-rate A --out-rate B
//       The worst-case gains (L1 norms); inputs up to the largest float
//       divided by them stay finite; a burst of NaN and infinities is
//       forgotten once it leaves the filters' memory.
//   fm1-resampler-test refuse
//       Which rate pairs init accepts, and what a refused instance does.
//   fm1-resampler-test tables
//       The header's coefficient tables, for the design check.
//   fm1-resampler-test file --in-rate A --out-rate B --in IN.wav --out OUT.wav
//       Resamples channel 0 of a 16-bit or 32-bit float WAV to a mono float WAV.
//   fm1-resampler-test tones --in IN.wav [--start N] [--length N] --freq F...
//       Amplitude (full scale = 1) at each frequency of channel 0, by a
//       Kaiser-windowed DFT (beta 20): the alias measurements on Shapes.
//   fm1-resampler-test peaks --in IN.wav [--start N] [--length N] [--floor DB]
//       The spectral peaks of channel 0 above --floor dB (full scale = 0),
//       from a Kaiser-windowed FFT (beta 20) of the largest power-of-two
//       stretch: frequency (parabolic interpolation) and amplitude.
//
// MIT licence.

#include "fm1_resampler.h"

#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

namespace {

const double kPi = 3.14159265358979323846;
const double kPassEdge = 18000.0 / 44118.0;  // of the output rate

double BesselI0(double x) {
  double s = 1.0, t = 1.0;
  for (int k = 1; k < 500; ++k) {
    t *= (x / (2.0 * k)) * (x / (2.0 * k));
    s += t;
    if (t < 1e-21 * s) break;
  }
  return s;
}

std::vector<double> KaiserWindow(size_t n, double beta) {
  std::vector<double> w(n);
  const double norm = BesselI0(beta);
  for (size_t i = 0; i < n; ++i) {
    const double r = 2.0 * i / (n - 1) - 1.0;
    w[i] = BesselI0(beta * sqrt(r * r < 1.0 ? 1.0 - r * r : 0.0)) / norm;
  }
  return w;
}

// In-place radix-2 FFT, n a power of two.
void Fft(std::vector<double> &re, std::vector<double> &im) {
  const size_t n = re.size();
  for (size_t i = 1, j = 0; i < n; ++i) {
    size_t bit = n >> 1;
    for (; j & bit; bit >>= 1) j ^= bit;
    j ^= bit;
    if (i < j) {
      double t = re[i]; re[i] = re[j]; re[j] = t;
      t = im[i]; im[i] = im[j]; im[j] = t;
    }
  }
  for (size_t len = 2; len <= n; len <<= 1) {
    const double a = -2.0 * kPi / len;
    for (size_t k = 0; k < len / 2; ++k) {
      const double c = cos(a * k), s = sin(a * k);
      for (size_t i = k; i < n; i += len) {
        const size_t j = i + len / 2;
        const double vr = re[j] * c - im[j] * s, vi = re[j] * s + im[j] * c;
        re[j] = re[i] - vr; im[j] = im[i] - vi;
        re[i] += vr; im[i] += vi;
      }
    }
  }
}

// The input frequency f as it lands below the output's Nyquist.
double Fold(double f, double rate) {
  double g = fmod(f, rate);
  return g > rate / 2 ? rate - g : g;
}

double Db(double amplitude) { return 20.0 * log10(amplitude + 1e-30); }

uint32_t Lcg(uint32_t *state) { return *state = *state * 1664525u + 1013904223u; }
float Noise(uint32_t *state) { return static_cast<int32_t>(Lcg(state)) / 2147483648.0f; }

bool Init(fm1_resampler_t *r, double in_rate, double out_rate) {
  if (!fm1_resampler_init(r, static_cast<float>(in_rate), static_cast<float>(out_rate))) {
    fprintf(stderr, "init refused %g -> %g\n", in_rate, out_rate);
    return false;
  }
  return true;
}

// Pulls n outputs, feeding inputs from next() one at a time as needed.
template <typename Source>
void Pull(fm1_resampler_t *r, Source &next, float *out, size_t n) {
  for (size_t k = 0; k < n; ++k) {
    while (fm1_resampler_needed(r)) {
      const float x = next();
      fm1_resampler_push(r, &x, 1);
    }
    out[k] = fm1_resampler_pop(r);
  }
}

struct SineSource {
  double w;
  long n;
  float operator()() { return static_cast<float>(sin(w * n++)); }
};

struct NoiseSource {
  uint32_t state;
  float operator()() { return Noise(&state); }
};

int Sweep(double in_rate, double out_rate, double from, double to, double step) {
  const size_t kSettle = 128, kN = 16384;
  const std::vector<double> win = KaiserWindow(kN, 20.0);
  double wsum = 0.0;
  for (size_t i = 0; i < kN; ++i) wsum += win[i];
  const double edge = kPassEdge * out_rate;
  std::vector<float> y(kSettle + kN);
  printf("{\"in_rate\":%.3f,\"out_rate\":%.3f,\"pass_edge\":%.3f,\"points\":[", in_rate, out_rate,
         edge);
  bool first = true;
  for (double f = from; f < to && f < in_rate / 2; f += step) {
    const double fo = Fold(f, out_rate);
    if (fo < 20.0 || fo > out_rate / 2 - 20.0) continue;   // DC or Nyquist: no fit
    fm1_resampler_t r;
    if (!Init(&r, in_rate, out_rate)) return 1;
    SineSource src = { 2.0 * kPi * f / in_rate, 0 };
    Pull(&r, src, &y[0], y.size());
    // Least squares at the output frequency, over output samples kSettle..:
    // y[k] ~ a sin(wk) + b cos(wk). The input's sine at the output instants
    // delayed by d samples is sin(w(k - d)), so a = G cos(wd), b = -G sin(wd).
    const double w = 2.0 * kPi * fo / out_rate;
    double ss = 0, sc = 0, cc = 0, ys = 0, yc = 0;
    for (size_t i = kSettle; i < y.size(); ++i) {
      const double s = sin(w * i), c = cos(w * i);
      ss += s * s; sc += s * c; cc += c * c; ys += y[i] * s; yc += y[i] * c;
    }
    const double det = ss * cc - sc * sc;
    const double a = (ys * cc - yc * sc) / det, b = (yc * ss - ys * sc) / det;
    const double gain = sqrt(a * a + b * b);
    double delay_err = 0.0;
    if (f < out_rate / 2) {
      const double period = 2.0 * kPi / w;
      double d = atan2(-b, a) / w - fm1_resampler_delay(&r);
      d = fmod(d, period);
      if (d > period / 2) d -= period;
      if (d < -period / 2) d += period;
      delay_err = d;
    }
    std::vector<double> re(kN), im(kN, 0.0);
    for (size_t i = 0; i < kN; ++i) {
      const size_t k = kSettle + i;
      re[i] = (y[k] - a * sin(w * k) - b * cos(w * k)) * win[i];
    }
    Fft(re, im);
    double pass = 0.0, upper = 0.0;
    for (size_t k = 1; k <= kN / 2; ++k) {
      const double amp = 2.0 * sqrt(re[k] * re[k] + im[k] * im[k]) / wsum;
      const double fk = k * out_rate / kN;
      if (fk <= edge) { if (amp > pass) pass = amp; } else if (amp > upper) upper = amp;
    }
    printf("%s{\"f\":%.2f,\"fo\":%.2f,\"gain_db\":%.6f,\"delay_err\":%.6f,"
           "\"pass_db\":%.2f,\"upper_db\":%.2f}", first ? "" : ",", f, fo, Db(gain), delay_err,
           Db(pass), Db(upper));
    first = false;
  }
  printf("],\"delay\":%d}\n", in_rate == out_rate ? 0 : FM1_RESAMPLER_HB_K);
  return 0;
}

int Bench(double in_rate, double out_rate, size_t outputs) {
  std::vector<float> in(static_cast<size_t>(outputs * in_rate / out_rate) + 4096);
  uint32_t state = 0x12345678u;
  for (size_t i = 0; i < in.size(); ++i) in[i] = 0.5f * Noise(&state);
  std::vector<float> out(outputs);
  double best = 1e30;
  float sink = 0.0f;
  for (int run = 0; run < 7; ++run) {
    fm1_resampler_t r;
    if (!Init(&r, in_rate, out_rate)) return 1;
    const auto t0 = std::chrono::steady_clock::now();
    uint32_t used = 0;
    const uint32_t made = fm1_resampler_process(&r, &in[0], static_cast<uint32_t>(in.size()),
                                                &used, &out[0], static_cast<uint32_t>(outputs));
    const auto t1 = std::chrono::steady_clock::now();
    if (made != outputs) { fprintf(stderr, "short input\n"); return 1; }
    sink += out[outputs - 1];
    const double ns = std::chrono::duration<double, std::nano>(t1 - t0).count() / outputs;
    if (ns < best) best = ns;
  }
  printf("{\"in_rate\":%.3f,\"out_rate\":%.3f,\"outputs\":%zu,\"ns_per_output\":%.2f,"
         "\"sink\":%g}\n", in_rate, out_rate, outputs, best, static_cast<double>(sink));
  return 0;
}

int Passthrough() {
  fm1_resampler_t r;
  if (!Init(&r, 96000.0, 96000.0)) return 1;
  // Bit patterns across the whole float range, NaNs left out (a NaN's
  // payload need not survive a copy through an FPU register); zeros of both
  // signs, subnormals and infinities included.
  std::vector<float> in;
  uint32_t state = 1;
  const uint32_t specials[] = { 0x00000000u, 0x80000000u, 0x00000001u, 0x807FFFFFu,
                                0x7F800000u, 0xFF800000u, 0x7F7FFFFFu, 0x3F800000u };
  for (size_t i = 0; i < sizeof(specials) / sizeof(specials[0]); ++i) {
    float f; memcpy(&f, &specials[i], 4); in.push_back(f);
  }
  while (in.size() < 100000) {
    uint32_t bits = Lcg(&state);
    if ((bits & 0x7F800000u) == 0x7F800000u && (bits & 0x007FFFFFu)) continue;   // NaN
    float f; memcpy(&f, &bits, 4); in.push_back(f);
  }
  std::vector<float> out(in.size());
  size_t mismatches = 0, k = 0;
  // Half one sample at a time, half through process() in chunks of 7.
  for (; k < in.size() / 2; ++k) {
    if (fm1_resampler_needed(&r) != 1) { ++mismatches; break; }
    if (fm1_resampler_push(&r, &in[k], 5) != 1) ++mismatches;   // takes one only
    if (fm1_resampler_needed(&r) != 0) ++mismatches;
    out[k] = fm1_resampler_pop(&r);
  }
  while (k < in.size()) {
    uint32_t used = 0;
    const uint32_t n = static_cast<uint32_t>(in.size() - k < 7 ? in.size() - k : 7);
    const uint32_t made = fm1_resampler_process(&r, &in[k], n, &used, &out[k], n);
    if (made != n || used != n) { ++mismatches; break; }
    k += n;
  }
  for (size_t i = 0; i < in.size(); ++i) {
    if (memcmp(&in[i], &out[i], 4) != 0) ++mismatches;
  }
  printf("{\"samples\":%zu,\"mismatches\":%zu,\"delay\":%g}\n", in.size(), mismatches,
         static_cast<double>(fm1_resampler_delay(&r)));
  return 0;
}

int Blocks(double in_rate, double out_rate) {
  const size_t kOut = 20000;
  std::vector<float> in(static_cast<size_t>(kOut * in_rate / out_rate) + 256);
  uint32_t state = 99;
  for (size_t i = 0; i < in.size(); ++i) in[i] = Noise(&state);
  // Reference: one input at a time, one output at a time.
  std::vector<float> ref(kOut);
  {
    fm1_resampler_t r;
    if (!Init(&r, in_rate, out_rate)) return 1;
    size_t pos = 0;
    for (size_t k = 0; k < kOut; ++k) {
      while (fm1_resampler_needed(&r)) fm1_resampler_push(&r, &in[pos++], 1);
      ref[k] = fm1_resampler_pop(&r);
    }
  }
  const uint32_t in_chunks[][4] = { { 1, 1, 1, 1 }, { 7, 7, 7, 7 }, { 24, 24, 24, 24 },
                                    { 64, 3, 100, 1 }, { 1000, 1000, 1000, 1000 } };
  const uint32_t out_chunks[][4] = { { 1, 1, 1, 1 }, { 64, 64, 64, 64 }, { 7, 1, 64, 13 },
                                     { 100, 3, 5, 64 }, { 1, 1000, 2, 7 } };
  int patterns = 0, differing = 0;
  for (size_t a = 0; a < 5; ++a) {
    for (size_t b = 0; b < 5; ++b) {
      fm1_resampler_t r;
      if (!Init(&r, in_rate, out_rate)) return 1;
      std::vector<float> got;
      size_t pos = 0, step = 0;
      while (got.size() < kOut) {
        const uint32_t ni = in_chunks[a][step % 4], no = out_chunks[b][step % 4];
        ++step;
        // Hand over one input chunk; draw output chunks until it runs dry.
        uint32_t offered = static_cast<uint32_t>(in.size() - pos < ni ? in.size() - pos : ni);
        uint32_t taken = 0;
        for (;;) {
          std::vector<float> out(no);
          uint32_t used = 0;
          uint32_t want = static_cast<uint32_t>(kOut - got.size() < no ? kOut - got.size() : no);
          const uint32_t made = fm1_resampler_process(&r, in.data() + pos + taken, offered - taken,
                                                      &used, &out[0], want);
          taken += used;
          got.insert(got.end(), out.begin(), out.begin() + made);
          if (made < want || got.size() >= kOut) break;
        }
        pos += taken;
        if (pos >= in.size()) break;
      }
      ++patterns;
      if (got.size() != kOut || memcmp(&got[0], &ref[0], kOut * sizeof(float)) != 0) ++differing;
    }
  }
  printf("{\"in_rate\":%.3f,\"out_rate\":%.3f,\"outputs\":%zu,\"patterns\":%d,\"differing\":%d}\n",
         in_rate, out_rate, kOut, patterns, differing);
  return 0;
}

// The largest |intermediate| / |input| any input can give: the kernel's L1
// norm, the worst over 65,536 input phases, each summed with the header's
// own table interpolation. Times the half-band's L1 norm it bounds the
// output; twice it bounds the half-band's pre-added pairs.
double KernelBound(const fm1_resampler_t &r) {
  const uint32_t end = (uint32_t)(FM1_RESAMPLER_KERNEL_LEN - 1) << 16;
  const float *k = fm1_resampler_kernel;
  double worst = 0.0;
  for (uint32_t p = 0; p < 65536; ++p) {
    const uint32_t frac = p << 16;
    double sum = 0.0;
    for (int side = 0; side < 2; ++side) {
      uint32_t t = side ? (uint32_t)((((uint64_t)1 << 32) - frac) * r.tap_step >> 32)
                        : (uint32_t)(((uint64_t)frac * r.tap_step) >> 32);
      for (; t < end; t += r.tap_step) {
        const uint32_t i = t >> 16;
        const float f = (float)(t & 0xFFFFu) * (1.0f / 65536.0f);
        sum += fabs(k[i] + f * (k[i + 1] - k[i]));
      }
    }
    if (sum * r.gain > worst) worst = sum * r.gain;
  }
  return worst;
}

double HalfbandL1() {
  double hb = 0.5;
  for (int j = 0; j < FM1_RESAMPLER_HB_PAIRS; ++j) hb += 2.0 * fabs(fm1_resampler_halfband[j]);
  return hb;
}

int Extreme(double in_rate, double out_rate) {
  const size_t kOut = 4000;
  // 1. Inputs as large as the bounds allow: the largest float over the
  //    larger of the output's bound and the pairs', at the input's Nyquist,
  //    as noise, and as a square wave of period 10 (Gibbs overshoot). No
  //    output may overflow.
  {
    fm1_resampler_t r;
    if (!Init(&r, in_rate, out_rate)) return 1;
    const double kernel = KernelBound(r), bound = kernel * HalfbandL1();
    const double limit = bound > 2.0 * kernel ? bound : 2.0 * kernel;
    const float big = static_cast<float>(3.4028234e38 / limit * 0.999);
    uint32_t state = 7;
    long n = 0;
    size_t nonfinite = 0;
    float peak = 0.0f;
    std::vector<float> out(kOut);
    struct Src {
      long *n; uint32_t *state; float big;
      float operator()() {
        const long i = (*n)++;
        if (i < 2000) return (i & 1) ? big : -big;
        if (i < 4000) return big * Noise(state);
        return ((i / 5) & 1) ? big : -big;
      }
    } src = { &n, &state, big };
    Pull(&r, src, &out[0], kOut);
    for (size_t k = 0; k < kOut; ++k) {
      if (!std::isfinite(out[k])) ++nonfinite;
      else if (fabsf(out[k]) > peak) peak = fabsf(out[k]);
    }
    printf("{\"kernel_bound\":%.6f,\"halfband_l1\":%.6f,\"gain_bound\":%.6f,"
           "\"input_peak\":%g,\"finite_input_nonfinite_outputs\":%zu,\"peak_gain\":%.6f,",
           kernel, HalfbandL1(), bound, static_cast<double>(big), nonfinite,
           static_cast<double>(peak) / big);
  }
  // 2. A burst of NaN, +inf and -inf inside noise, against the same noise
  //    without it: the outputs differ only while the burst is in the filters.
  {
    fm1_resampler_t clean, dirty;
    if (!Init(&clean, in_rate, out_rate) || !Init(&dirty, in_rate, out_rate)) return 1;
    const float bad[] = { NAN, INFINITY, -INFINITY, NAN, 1e38f };
    struct Src {
      long n; uint32_t state; bool burst; const float *bad;
      float operator()() {
        const long i = n++;
        const float x = Noise(&state);
        return burst && i >= 3000 && i < 3005 ? bad[i - 3000] : x;
      }
    } a = { 0, 5, false, bad }, b = { 0, 5, true, bad };
    std::vector<float> ya(kOut), yb(kOut);
    Pull(&clean, a, &ya[0], kOut);
    Pull(&dirty, b, &yb[0], kOut);
    long first = -1, last = -1;
    size_t nonfinite = 0;
    for (size_t k = 0; k < kOut; ++k) {
      if (!std::isfinite(yb[k])) ++nonfinite;
      if (memcmp(&ya[k], &yb[k], 4) != 0) {
        if (first < 0) first = static_cast<long>(k);
        last = static_cast<long>(k);
      }
    }
    printf("\"burst_outputs_differing_from\":%ld,\"to\":%ld,\"nonfinite\":%zu}\n", first, last,
           nonfinite);
  }
  return 0;
}

int Refuse() {
  const float inf = INFINITY;
  const float pairs[][2] = { { 96000.0f, 44118.0f }, { 96000.0f, 96000.0f },
                             { 47872.34f, 44118.0f }, { 176472.0f, 44118.0f },
                             { 44118.0f, 96000.0f }, { 176473.0f, 44118.0f },
                             { 44117.0f, 44118.0f }, { 0.0f, 44118.0f }, { 96000.0f, 0.0f },
                             { -96000.0f, 44118.0f }, { NAN, 44118.0f }, { 96000.0f, NAN },
                             { inf, 44118.0f }, { inf, inf } };
  printf("[");
  for (size_t i = 0; i < sizeof(pairs) / sizeof(pairs[0]); ++i) {
    fm1_resampler_t r;
    memset(&r, 0xA5, sizeof(r));
    const int ok = fm1_resampler_init(&r, pairs[i][0], pairs[i][1]);
    const float x = 1.0f;
    const uint32_t needed = fm1_resampler_needed(&r);
    const uint32_t took = ok ? 0 : fm1_resampler_push(&r, &x, 1);
    const float y = ok ? 0.0f : fm1_resampler_pop(&r);
    printf("%s{\"in\":\"%.9g\",\"out\":\"%.9g\",\"ok\":%d,\"needed\":%u,\"took\":%u,"
           "\"pop\":%g}", i ? "," : "", static_cast<double>(pairs[i][0]),
           static_cast<double>(pairs[i][1]), ok, needed, took, static_cast<double>(y));
  }
  printf("]\n");
  return 0;
}

int Tables() {
  printf("{\"span\":%d,\"phases\":%d,\"hb_k\":%d,\"kernel\":[", FM1_RESAMPLER_SPAN,
         FM1_RESAMPLER_PHASES, FM1_RESAMPLER_HB_K);
  for (int i = 0; i < FM1_RESAMPLER_KERNEL_LEN; ++i) {
    printf(i ? ",%.9g" : "%.9g", static_cast<double>(fm1_resampler_kernel[i]));
  }
  printf("],\"halfband\":[");
  for (int i = 0; i < FM1_RESAMPLER_HB_PAIRS; ++i) {
    printf(i ? ",%.9g" : "%.9g", static_cast<double>(fm1_resampler_halfband[i]));
  }
  printf("],\"state_bytes\":%zu}\n", sizeof(fm1_resampler_t));
  return 0;
}

bool ReadWav(const char *path, std::vector<float> *channel0, double *rate) {
  FILE *f = fopen(path, "rb");
  if (!f) return false;
  std::vector<unsigned char> d;
  unsigned char buf[65536];
  size_t got;
  while ((got = fread(buf, 1, sizeof(buf), f)) > 0) d.insert(d.end(), buf, buf + got);
  fclose(f);
  auto u32 = [&](size_t p) { return uint32_t(d[p]) | uint32_t(d[p + 1]) << 8 |
                                    uint32_t(d[p + 2]) << 16 | uint32_t(d[p + 3]) << 24; };
  auto u16 = [&](size_t p) { return unsigned(d[p]) | unsigned(d[p + 1]) << 8; };
  if (d.size() < 12 || memcmp(&d[0], "RIFF", 4) || memcmp(&d[8], "WAVE", 4)) return false;
  unsigned tag = 0, channels = 0, bits = 0;
  for (size_t p = 12; p + 8 <= d.size();) {
    const uint32_t size = u32(p + 4);
    if (!memcmp(&d[p], "fmt ", 4) && p + 24 <= d.size()) {
      tag = u16(p + 8); channels = u16(p + 10); *rate = u32(p + 12); bits = u16(p + 22);
    } else if (!memcmp(&d[p], "data", 4)) {
      if (!channels || !((tag == 1 && bits == 16) || (tag == 3 && bits == 32))) return false;
      const size_t frame = channels * bits / 8;
      const size_t end = p + 8 + size <= d.size() ? p + 8 + size : d.size();
      for (size_t q = p + 8; q + frame <= end; q += frame) {
        if (tag == 1) {
          channel0->push_back(static_cast<int16_t>(u16(q)) / 32767.0f);
        } else {
          float x; uint32_t bitsv = u32(q); memcpy(&x, &bitsv, 4); channel0->push_back(x);
        }
      }
      return true;
    }
    p += 8 + size + (size & 1);
  }
  return false;
}

bool WriteFloatWav(const char *path, const std::vector<float> &x, double rate) {
  FILE *f = fopen(path, "wb");
  if (!f) return false;
  auto w32 = [f](uint32_t v) { unsigned char b[4] = { (unsigned char)v, (unsigned char)(v >> 8),
                                                      (unsigned char)(v >> 16),
                                                      (unsigned char)(v >> 24) };
                               fwrite(b, 1, 4, f); };
  auto w16 = [f](unsigned v) { unsigned char b[2] = { (unsigned char)v, (unsigned char)(v >> 8) };
                               fwrite(b, 1, 2, f); };
  const uint32_t bytes = static_cast<uint32_t>(x.size() * 4);
  const uint32_t r = static_cast<uint32_t>(lround(rate));
  fwrite("RIFF", 1, 4, f); w32(36 + bytes); fwrite("WAVE", 1, 4, f);
  fwrite("fmt ", 1, 4, f); w32(16); w16(3); w16(1); w32(r); w32(r * 4); w16(4); w16(32);
  fwrite("data", 1, 4, f); w32(bytes);
  for (size_t i = 0; i < x.size(); ++i) {
    uint32_t v; memcpy(&v, &x[i], 4); w32(v);
  }
  return fclose(f) == 0;
}

int File(double in_rate, double out_rate, const char *in_path, const char *out_path) {
  std::vector<float> in;
  double file_rate = 0.0;
  if (!ReadWav(in_path, &in, &file_rate)) { fprintf(stderr, "cannot read %s\n", in_path); return 1; }
  fm1_resampler_t r;
  if (!Init(&r, in_rate, out_rate)) return 1;
  std::vector<float> out(static_cast<size_t>(in.size() * out_rate / in_rate) + 2);
  uint32_t used = 0;
  const uint32_t made = fm1_resampler_process(&r, in.empty() ? NULL : &in[0],
                                              static_cast<uint32_t>(in.size()), &used,
                                              &out[0], static_cast<uint32_t>(out.size()));
  out.resize(made);
  if (!WriteFloatWav(out_path, out, out_rate)) { fprintf(stderr, "cannot write\n"); return 1; }
  printf("{\"inputs\":%zu,\"used\":%u,\"outputs\":%u,\"file_rate\":%g}\n", in.size(), used, made,
         file_rate);
  return 0;
}

int Tones(const char *path, size_t start, size_t length, const std::vector<double> &freqs) {
  std::vector<float> x;
  double rate = 0.0;
  if (!ReadWav(path, &x, &rate)) { fprintf(stderr, "cannot read %s\n", path); return 1; }
  if (!length || start + length > x.size()) length = x.size() > start ? x.size() - start : 0;
  if (length < 64) { fprintf(stderr, "too short\n"); return 1; }
  const std::vector<double> win = KaiserWindow(length, 20.0);
  double wsum = 0.0;
  for (size_t i = 0; i < length; ++i) wsum += win[i];
  printf("{\"rate\":%g,\"length\":%zu,\"tones\":[", rate, length);
  for (size_t j = 0; j < freqs.size(); ++j) {
    const double w = 2.0 * kPi * freqs[j] / rate;
    // Rotate by a complex recurrence, renormalised, rather than call sin/cos
    // per sample.
    double c = 1.0, s = 0.0, re = 0.0, im = 0.0;
    const double cw = cos(w), sw = sin(w);
    for (size_t i = 0; i < length; ++i) {
      re += x[start + i] * win[i] * c;
      im -= x[start + i] * win[i] * s;
      const double nc = c * cw - s * sw, ns = s * cw + c * sw;
      const double g = 1.5 - 0.5 * (nc * nc + ns * ns);
      c = nc * g; s = ns * g;
    }
    printf("%s{\"f\":%.3f,\"amp\":%.6e}", j ? "," : "", freqs[j], 2.0 * sqrt(re * re + im * im) / wsum);
  }
  printf("]}\n");
  return 0;
}

int Peaks(const char *path, size_t start, size_t length, double floor_db) {
  std::vector<float> x;
  double rate = 0.0;
  if (!ReadWav(path, &x, &rate)) { fprintf(stderr, "cannot read %s\n", path); return 1; }
  if (!length || start + length > x.size()) length = x.size() > start ? x.size() - start : 0;
  size_t n = 1;
  while (n * 2 <= length) n *= 2;
  if (n < 1024) { fprintf(stderr, "too short\n"); return 1; }
  const std::vector<double> win = KaiserWindow(n, 20.0);
  double wsum = 0.0;
  std::vector<double> re(n), im(n, 0.0);
  for (size_t i = 0; i < n; ++i) { wsum += win[i]; re[i] = x[start + i] * win[i]; }
  Fft(re, im);
  std::vector<double> db(n / 2 + 1);
  for (size_t k = 0; k <= n / 2; ++k) db[k] = Db(2.0 * sqrt(re[k] * re[k] + im[k] * im[k]) / wsum);
  printf("{\"rate\":%g,\"length\":%zu,\"peaks\":[", rate, n);
  bool first = true;
  for (size_t k = 2; k + 2 <= n / 2; ++k) {
    if (db[k] < floor_db || db[k] < db[k - 1] || db[k] <= db[k + 1]) continue;
    // A Kaiser beta-20 main lobe spans about +/-6 bins: keep only the
    // largest bin within it.
    bool top = true;
    for (size_t j = k > 8 ? k - 8 : 0; j <= k + 8 && j <= n / 2; ++j) {
      if (j != k && db[j] > db[k]) top = false;
    }
    if (!top) continue;
    const double a = db[k - 1], b = db[k], c = db[k + 1];
    const double shift = 0.5 * (a - c) / (a - 2.0 * b + c);
    printf("%s{\"f\":%.3f,\"db\":%.2f}", first ? "" : ",", (k + shift) * rate / n, b);
    first = false;
  }
  printf("]}\n");
  return 0;
}

}  // namespace

int main(int argc, char **argv) {
  if (argc < 2) {
    fprintf(stderr, "usage: fm1-resampler-test sweep|bench|passthrough|blocks|extreme|refuse|"
                    "tables|file|tones|peaks [options]\n");
    return 2;
  }
  const std::string mode = argv[1];
  double in_rate = 96000.0, out_rate = 44118.0, from = 50.0, to = 1e9, step = 250.0;
  double floor_db = -120.0;
  size_t outputs = 1u << 20, start = 0, length = 0;
  const char *in_path = NULL, *out_path = NULL;
  std::vector<double> freqs;
  for (int i = 2; i < argc; ++i) {
    const std::string a = argv[i];
    if (i + 1 >= argc) { fprintf(stderr, "%s needs a value\n", a.c_str()); return 2; }
    const char *v = argv[++i];
    if (a == "--in-rate") in_rate = atof(v);
    else if (a == "--out-rate") out_rate = atof(v);
    else if (a == "--from") from = atof(v);
    else if (a == "--to") to = atof(v);
    else if (a == "--step") step = atof(v);
    else if (a == "--outputs") outputs = static_cast<size_t>(atol(v));
    else if (a == "--in") in_path = v;
    else if (a == "--out") out_path = v;
    else if (a == "--start") start = static_cast<size_t>(atol(v));
    else if (a == "--length") length = static_cast<size_t>(atol(v));
    else if (a == "--freq") freqs.push_back(atof(v));
    else if (a == "--floor") floor_db = atof(v);
    else { fprintf(stderr, "unknown option %s\n", a.c_str()); return 2; }
  }
  if (!(step > 0.0) || !outputs) return 2;
  if (mode == "sweep") return Sweep(in_rate, out_rate, from, to, step);
  if (mode == "bench") return Bench(in_rate, out_rate, outputs);
  if (mode == "passthrough") return Passthrough();
  if (mode == "blocks") return Blocks(in_rate, out_rate);
  if (mode == "extreme") return Extreme(in_rate, out_rate);
  if (mode == "refuse") return Refuse();
  if (mode == "tables") return Tables();
  if (mode == "file" && in_path && out_path) return File(in_rate, out_rate, in_path, out_path);
  if (mode == "tones" && in_path && !freqs.empty()) return Tones(in_path, start, length, freqs);
  if (mode == "peaks" && in_path) return Peaks(in_path, start, length, floor_db);
  fprintf(stderr, "unknown mode or missing options\n");
  return 2;
}

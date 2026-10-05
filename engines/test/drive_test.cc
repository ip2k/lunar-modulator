// drive_test.cc -- fm1-drive-test: checks the Drive effect (src/fx_drive.cc)
// where fm1-render cannot. It includes the effect's source, so it reaches the
// curves and the instance as well as the engine struct:
//
//   - the anti-aliased mean of each curve against quadrature, and for tiny
//     steps against the curve at the midpoint (no cancellation);
//   - aliasing of a sine against a plain per-sample curve, per Type;
//   - the tape emphasis: quiet signals flat, loud highs softened;
//   - parameters and Types changed while audio runs, between blocks of any
//     size, NaN and infinities included; the glide; the Type crossfade;
//     silence while the controls move; host rates.
//
// `fm1-drive-test` prints one JSON object (tests/test_engines_drive.py reads
// it); `fm1-drive-test bench` prints the cost per 64-frame block, and
// `fm1-drive-test hash` a hash of the output's bits per Type, to compare
// builds. MIT licence.

#include "../src/fx_drive.cc"

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

namespace {

const fm1_engine_t &E = fm1_engine_drive;
const float kRate = 44118.0f;
alignas(16) unsigned char g_mem[4096];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

DriveInstance *Make(float rate, int fill) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = E.instance_size(&host);
  if (n > sizeof(g_mem)) return NULL;
  memset(g_mem, fill, sizeof(g_mem));
  return static_cast<DriveInstance *>(E.create(g_mem, &host));
}

int Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  return -1;
}

void Set(void *self, const char *name, float v) {
  E.set_param(self, static_cast<uint16_t>(Index(name)), v);
}

// ---------------------------------------------------------------------------
// 1. The anti-aliased mean against quadrature.

// The plain shaper at u, through the effect's own code (a zero-length step).
double Plain(const DriveCurve *c, double u, float t, float b) {
  const float v = static_cast<float>(u);
  return DriveShaper(c, v, v, t, b);
}

// The mean of the plain shaper over [a, b] by composite Simpson's rule, in
// double, with the dead zone's and the knots' corners as panel edges.
double Quadrature(const DriveCurve *c, double a, double b, float t, float bias) {
  double edges[16];
  int n = 0;
  edges[n++] = a;
  const double cand[] = { -t, t };
  double inner[12];
  int m = 0;
  for (double e : cand) inner[m++] = e;
  for (int k = 0; k < c->n; ++k) {
    const double x = c->x[k] - bias;               // a knot, mapped back to u
    inner[m++] = x >= 0 ? x + t : x - t;
    if (x == 0 && t > 0) inner[m++] = x - t;
  }
  for (int i = 0; i < m; ++i) {                    // sorted, inside (a, b)
    for (int j = i + 1; j < m; ++j) {
      if (inner[j] < inner[i]) { const double s = inner[i]; inner[i] = inner[j]; inner[j] = s; }
    }
  }
  for (int i = 0; i < m; ++i) {
    if (inner[i] > a && inner[i] < b) edges[n++] = inner[i];
  }
  edges[n++] = b;
  double sum = 0.0;
  for (int p = 0; p + 1 < n; ++p) {
    const double lo = edges[p], hi = edges[p + 1];
    const int steps = 200;
    const double h = (hi - lo) / steps;
    double s = Plain(c, lo, t, bias) + Plain(c, hi, t, bias);
    for (int i = 1; i < steps; ++i) s += (i & 1 ? 4.0 : 2.0) * Plain(c, lo + i * h, t, bias);
    sum += s * h / 3.0;
  }
  return sum / (b - a);
}

void Means() {
  printf("\"means\":{");
  for (int type = 0; type < T_COUNT; ++type) {
    const DriveCurve *c = &kCurves[type];
    Lcg rng = { 7u + static_cast<uint32_t>(type) };
    double worst = 0.0, worst_small = 0.0;
    for (int trial = 0; trial < 3000; ++trial) {
      const float t = (trial % 3 == 0) ? 0.0f : 0.5f * rng.Unit() + c->gate;
      const float bias = (trial % 4 == 0) ? 0.0f : rng.Bipolar() + c->bias;
      // Steps from small to wide (many pieces), centred anywhere in +/-8.
      const double centre = 8.0 * rng.Bipolar();
      const double width = pow(10.0, -2.0 + 3.5 * rng.Unit());
      const double a = static_cast<float>(centre - 0.5 * width);
      const double b = static_cast<float>(centre + 0.5 * width);
      if (!(b > a)) continue;
      const double ours = DriveShaper(c, static_cast<float>(a), static_cast<float>(b), t, bias);
      const double want = Quadrature(c, a, b, t, bias);
      if (fabs(ours - want) > worst) worst = fabs(ours - want);
      // Tiny steps, near the knots and the dead zone's edges as often as
      // not: a formula that divided a difference of antiderivatives by the
      // step would be off by about (float resolution) / step, 0.1 at 1e-6.
      const float near = (trial & 1) ? c->x[rng.Next() % c->n] - bias + (rng.Next() & 2 ? t : -t)
                                     : static_cast<float>(4.0 * rng.Bipolar());
      for (float d = 1e-6f; d < 2e-3f; d *= 10.0f) {
        const float u0 = near - 0.5f * d, u1 = near + 0.5f * d;
        if (!(u1 > u0)) continue;
        const double err = fabs(DriveShaper(c, u0, u1, t, bias) - Quadrature(c, u0, u1, t, bias));
        if (err > worst_small) worst_small = err;
      }
    }
    printf("%s\"%s\":{\"vs_quadrature\":%.3g,\"tiny_steps\":%.3g}", type ? "," : "",
           kTypeNames[type], worst, worst_small);
  }
  printf("}");
}

// ---------------------------------------------------------------------------
// 2. Aliasing: a sine through the effect against the same path with the curve
// applied plainly, sample by sample. Both run the emphasis (Tape) and the DC
// blocker; Tone 0.5, Mix 1, Auto off, Level 0 dB.

const uint32_t kTotal = 44118;
float g_a[kTotal], g_b[kTotal], g_c[kTotal];

void RenderSineThrough(DriveInstance *self, double hz, float amp, float *out_left,
                       uint32_t block) {
  float buf[128];
  for (uint32_t pos = 0; pos < kTotal;) {
    const uint32_t n = kTotal - pos < block ? kTotal - pos : block;
    for (uint32_t i = 0; i < n; ++i) {
      const float x = amp * static_cast<float>(sin(2.0 * 3.141592653589793 * hz * (pos + i) / kRate));
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
}

void PlainSine(DriveInstance *self, double hz, float amp, float *out) {
  const DriveCurve *c = &kCurves[self->type_from];
  const float t = self->value[S_GATE] + c->gate, b = self->value[S_BIAS] + c->bias;
  const float silence = DriveShaper(c, 0.0f, 0.0f, t, b);
  const float ge = self->g_emph, k = self->value[S_EMPH];
  const float kk = self->emph_kk, inv = self->emph_inv, gain = self->value[S_GAIN];
  float pre = 0.0f, post = 0.0f, dx = 0.0f, dy = 0.0f;
  for (uint32_t n = 0; n < kTotal; ++n) {
    const float x = amp * static_cast<float>(sin(2.0 * 3.141592653589793 * hz * n / kRate));
    const float vp = (x - pre) * ge;
    const float lp = vp + pre;
    pre = lp + vp;
    const float u = gain * (x + k * (x - lp));
    const float m = DriveShaper(c, u, u, t, b) - silence;
    const float d = (m + kk * post) * inv;
    const float vd = (d - post) * ge;
    post = vd + post + vd;
    const float y = d - dx + self->dc_r * dy;
    dx = d;
    dy = y;
    out[n] = y;
  }
}

// Power of the component at hz (an exact bin of seg: 2 Hz apart over 0.5 s).
double Goertzel(const float *seg, uint32_t n, double hz) {
  const double w = 2.0 * 3.141592653589793 * hz / kRate, c = 2.0 * cos(w);
  double s1 = 0.0, s2 = 0.0;
  for (uint32_t i = 0; i < n; ++i) {
    const double s0 = seg[i] + c * s1 - s2;
    s2 = s1;
    s1 = s0;
  }
  const double re = s1 - s2 * cos(w), im = s2 * sin(w);
  return (re * re + im * im) / (0.25 * n * n);
}

// Aliases of harmonics 1..kmax of hz reflected about Nyquist, below band and
// off the harmonics, against the fundamental, in dB; over 0.5..1.0 s.
double AliasDb(const float *y, double hz, double band) {
  const float *seg = y + kTotal / 2;
  const uint32_t n = kTotal / 2;
  static char seen[22060];
  memset(seen, 0, sizeof(seen));
  double sum = 0.0;
  const int kmax = static_cast<int>(440000.0 / hz);
  for (int k = 1; k <= kmax; ++k) {
    double f = fmod(hz * k, static_cast<double>(kRate));
    if (f > kRate / 2) f = kRate - f;
    const int bin = static_cast<int>(f / 2.0 + 0.5);
    if (!(f > 20.0 && f < band) || fmod(f, hz) == 0.0 || seen[bin]) continue;
    seen[bin] = 1;
    sum += Goertzel(seg, n, f);
  }
  return 10.0 * log10(sum / Goertzel(seg, n, hz));
}

void Alias() {
  printf("\"alias\":[");
  const float drives[] = { 12.0f, 24.0f, 36.0f };
  const double freqs[] = { 440.0, 1760.0 };
  int first = 1;
  for (int type = 0; type < T_COUNT; ++type) {
    for (float drive : drives) {
      for (double hz : freqs) {
        DriveInstance *self = Make(kRate, 0);
        Set(self, "Type", static_cast<float>(type));
        Set(self, "Drive", drive);
        Set(self, "Auto", 0.0f);
        RenderSineThrough(self, hz, 0.5f, g_a, 64);
        PlainSine(self, hz, 0.5f, g_b);
        printf("%s{\"type\":\"%s\",\"drive\":%g,\"hz\":%g,\"adaa_5k\":%.2f,\"plain_5k\":%.2f,"
               "\"adaa_all\":%.2f,\"plain_all\":%.2f}", first ? "" : ",", kTypeNames[type],
               drive, hz, AliasDb(g_a, hz, 5000.0), AliasDb(g_b, hz, 5000.0),
               AliasDb(g_a, hz, kRate / 2 - 20.0), AliasDb(g_b, hz, kRate / 2 - 20.0));
        first = 0;
      }
    }
  }
  printf("]");
}

// ---------------------------------------------------------------------------
// 3. Tape: the gain of the fundamental at 200 Hz and 5 kHz, quiet and loud,
// Auto off. With the emphasis, quiet signals pass flat and loud highs
// saturate first.

double Gain(int type, float drive, double hz, float amp) {
  DriveInstance *self = Make(kRate, 0);
  Set(self, "Type", static_cast<float>(type));
  Set(self, "Drive", drive);
  Set(self, "Auto", 0.0f);
  RenderSineThrough(self, hz, amp, g_a, 64);
  const double in = amp * amp;
  return 10.0 * log10(Goertzel(g_a + kTotal / 2, kTotal / 2, hz) / in);
}

void Tape() {
  printf("\"emphasis\":{");
  const int types[] = { T_SOFT, T_TAPE };
  for (int i = 0; i < 2; ++i) {
    const int type = types[i];
    printf("%s\"%s\":{\"quiet_200\":%.3f,\"quiet_5k\":%.3f,\"loud_200\":%.3f,\"loud_5k\":%.3f}",
           i ? "," : "", kTypeNames[type], Gain(type, -12.0f, 200.0, 0.05f),
           Gain(type, -12.0f, 5000.0, 0.05f), Gain(type, 24.0f, 200.0, 0.5f),
           Gain(type, 24.0f, 5000.0, 0.5f));
  }
  printf("}");
}

// ---------------------------------------------------------------------------
// 4. Every parameter, at every kind of value (min, max, default, random,
// beyond the range, NaN, infinities), changed between blocks of random size
// while noise plays, for 20 s. The output must stay finite and bounded.

void Sweep() {
  DriveInstance *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0;
  float peak = 0.0f;
  while (samples < static_cast<uint64_t>(20 * kRate)) {
    const uint32_t n = 1 + rng.Next() % 64;
    for (int changes = rng.Next() % 3; changes > 0; --changes) {
      const fm1_param_t &p = E.params[rng.Next() % E.n_params];
      float v;
      switch (rng.Next() % 8) {
        case 0: v = p.min; break;
        case 1: v = p.max; break;
        case 2: v = p.def; break;
        case 3: v = 4 * p.max - 3 * p.min + 1; break;
        case 4: v = NAN; break;
        case 5: v = (rng.Next() & 1) ? INFINITY : -INFINITY; break;
        default: v = p.min + (p.max - p.min) * rng.Unit(); break;
      }
      E.set_param(self, static_cast<uint16_t>(&p - E.params), v);
    }
    for (uint32_t i = 0; i < n; ++i) buf[2 * i] = buf[2 * i + 1] = 0.5f * rng.Bipolar();
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(nonfinite),
         peak);
}

// ---------------------------------------------------------------------------
// 5. Changes mid-stream: the same output whatever the block size, a Level
// step that glides and then lands exactly, and a Type crossfade without a
// click.

struct Change { uint32_t at; const char *name; float value; };

float g_fade_step = 0.0f;   // when nonzero, replaces the instance's crossfade step

void RenderSine(uint32_t block, const Change *changes, int n_changes, float amplitude,
                float *out_left, int *final_type) {
  DriveInstance *self = Make(kRate, 0);
  if (g_fade_step > 0.0f) self->fade_step = g_fade_step;
  float buf[128];
  int next = 0;
  for (uint32_t pos = 0; pos < kTotal;) {
    while (next < n_changes && changes[next].at <= pos) {
      Set(self, changes[next].name, changes[next].value);
      ++next;
    }
    uint32_t n = kTotal - pos < block ? kTotal - pos : block;
    if (next < n_changes && changes[next].at - pos < n) n = changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      const float x = amplitude * static_cast<float>(sin(2.0 * 3.141592653589793 * 440.0 *
                                                         (pos + i) / kRate));
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < n; ++i) out_left[pos + i] = buf[2 * i];
    pos += n;
  }
  if (final_type) *final_type = self->type_from;
  E.destroy(self);
}

void Glide() {
  const Change ch[] = {
    { 0, "Drive", 18.0f }, { 0, "Auto", 0.0f },
    { 4410, "Type", 1.0f }, { 4410, "Drive", 30.0f }, { 4410, "Bias", 0.4f },
    { 4410, "Tone", 0.2f }, { 4410, "Mix", 0.7f }, { 4410, "Gate", 0.3f },
    { 8820, "Type", 4.0f }, { 8900, "Type", 3.0f },        // the second waits for the first
    { 13230, "Auto", 1.0f }, { 13230, "Mix", 1.0f },
    { 22050, "Level", -24.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  int final_type = -1;
  RenderSine(64, ch, n, 0.5f, g_a, &final_type);
  RenderSine(7, ch, n, 0.5f, g_b, NULL);
  RenderSine(1, ch, n, 0.5f, g_c, NULL);
  const int same = memcmp(g_a, g_b, sizeof(g_a)) == 0 && memcmp(g_a, g_c, sizeof(g_a)) == 0;
  // The same run with Level at -24 dB from 13230 on: after the glide, the
  // output is that one's exactly (Level is the last gain, Mix 1).
  Change ref[n];
  memcpy(ref, ch, sizeof(ch));
  ref[n - 1].at = 13230;
  RenderSine(64, ref, n, 0.5f, g_b, NULL);
  float before = 0.0f, first_ms = 0.0f;
  uint32_t lands = kTotal;
  for (uint32_t i = 22050 - 441; i < 22050; ++i) before = fmaxf(before, fabsf(g_a[i]));
  for (uint32_t i = 22050; i < 22050 + 44; ++i) first_ms = fmaxf(first_ms, fabsf(g_a[i]));
  for (uint32_t i = kTotal; i-- > 22050;) {
    if (g_a[i] != g_b[i]) break;
    lands = i;
  }
  printf("\"glide\":{\"block_independent\":%s,\"final_type\":\"%s\",\"before\":%.6f,"
         "\"first_ms\":%.6f,\"lands_ms\":%.2f}", same ? "true" : "false",
         final_type >= 0 ? kTypeNames[final_type] : "?", before, first_ms,
         (lands - 22050) * 1000.0 / kRate);
}

// The largest step between successive samples, over [from, to).
float MaxStep(const float *y, uint32_t from, uint32_t to) {
  float m = 0.0f;
  for (uint32_t i = from + 1; i < to; ++i) m = fmaxf(m, fabsf(y[i] - y[i - 1]));
  return m;
}

// Type changes every 100 ms on a 440 Hz sine (Drive 24, Auto on): the
// largest sample-to-sample step at a change against the largest in steady
// state, and the same changes made at once (fade_step 1) for comparison.
void Switch() {
  Change ch[10];
  int n = 0;
  for (int k = 0; k < 9; ++k) {
    ch[n++] = { static_cast<uint32_t>(4411 * (k + 1)), "Type", static_cast<float>((k * 3 + 1) % 5) };
  }
  ch[n++] = { 0, "Drive", 24.0f };
  // Sorted by time: the Drive change first.
  Change sorted[10];
  sorted[0] = ch[9];
  for (int k = 0; k < 9; ++k) sorted[k + 1] = ch[k];
  RenderSine(64, sorted, n, 0.5f, g_a, NULL);
  g_fade_step = 1.0f;
  RenderSine(64, sorted, n, 0.5f, g_b, NULL);
  g_fade_step = 0.0f;
  float steady = 0.0f, at_change = 0.0f, at_once = 0.0f;
  for (int k = 0; k < 9; ++k) {
    const uint32_t at = 4411 * (k + 1);
    steady = fmaxf(steady, MaxStep(g_a, at - 2205, at - 10));
    at_change = fmaxf(at_change, MaxStep(g_a, at - 10, at + 400));
    at_once = fmaxf(at_once, MaxStep(g_b, at - 10, at + 400));
  }
  printf("\"switch\":{\"steady_step\":%.6f,\"change_step\":%.6f,\"at_once_step\":%.6f}",
         steady, at_change, at_once);
}

// ---------------------------------------------------------------------------
// 6. Silence in while Type, Drive, Bias and Gate move: next to nothing while
// they glide (the shaper of silence is subtracted as it moves), then exact
// silence once the filter states flush.

void Silence() {
  DriveInstance *self = Make(kRate, 0xFF);
  float buf[128];
  float moving = 0.0f, settled = 0.0f;
  const float bias[] = { 0.0f, 1.0f, -1.0f, 0.3f, -0.7f };
  const float gate[] = { 0.0f, 0.5f, 1.0f, 0.2f, 0.9f };
  for (int step = 0; step < 5; ++step) {
    Set(self, "Bias", bias[step]);
    Set(self, "Gate", gate[step]);
    Set(self, "Type", static_cast<float>(step));
    Set(self, "Drive", -12.0f + 12.0f * step);
    for (int b = 0; b < 200; ++b) {                     // 290 ms per step
      memset(buf, 0, sizeof(buf));
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        if (b < 100) moving = fmaxf(moving, fabsf(buf[i]));
        else settled = fmaxf(settled, fabsf(buf[i]));
      }
    }
  }
  float last = 0.0f;
  for (int b = 0; b < 1400; ++b) {                      // 2 s more
    memset(buf, 0, sizeof(buf));
    E.render(self, buf, 64);
    if (b == 1399) {
      for (int i = 0; i < 128; ++i) last = fmaxf(last, fabsf(buf[i]));
    }
  }
  E.destroy(self);
  printf("\"silence\":{\"moving_peak\":%.9g,\"settled_peak\":%.9g,\"last_block_peak\":%.9g}",
         moving, settled, last);
}

// 7. Host rates: refused outside 8 kHz..384 kHz, and when not a number.
void Rates() {
  const float rates[] = { 0.0f, 7999.0f, 8000.0f, 44118.0f, 48000.0f, 96000.0f, 384000.0f,
                          400000.0f, NAN, INFINITY, -44118.0f };
  printf("\"rates\":[");
  for (size_t i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
    void *self = Make(rates[i], 0);
    printf("%s[\"%g\",%s]", i ? "," : "", rates[i], self ? "true" : "false");
    if (self) E.destroy(self);
  }
  printf("]");
}

// ---------------------------------------------------------------------------
// bench: ns per 64-frame stereo block of noise, per Type, heavy settings.

double Now() {
  timespec ts;
  clock_gettime(CLOCK_MONOTONIC, &ts);
  return ts.tv_sec * 1e9 + ts.tv_nsec;
}

void Bench() {
  float noise[128 * 64];
  Lcg rng = { 3u };
  for (int i = 0; i < 128 * 64; ++i) noise[i] = 0.5f * rng.Bipolar();
  printf("{\"bytes\":%zu,\"ns_per_block\":{", sizeof(DriveInstance));
  for (int type = 0; type <= T_COUNT; ++type) {
    DriveInstance *self = Make(kRate, 0);
    Set(self, "Type", static_cast<float>(type % T_COUNT));
    Set(self, "Drive", 30.0f);
    Set(self, "Bias", 0.2f);
    Set(self, "Gate", 0.2f);
    Set(self, "Tone", 0.3f);
    Set(self, "Mix", 0.8f);
    float buf[128];
    const int blocks = 200000;
    double best = 1e30;
    for (int rep = 0; rep < 5; ++rep) {
      const double t0 = Now();
      for (int b = 0; b < blocks; ++b) {
        if (type == T_COUNT && b % 8 == 0) Set(self, "Type", static_cast<float>((b / 8) % T_COUNT));
        memcpy(buf, noise + 128 * (b % 64), sizeof(buf));
        E.render(self, buf, 64);
      }
      const double dt = (Now() - t0) / blocks;
      if (dt < best) best = dt;
    }
    printf("%s\"%s\":%.1f", type ? "," : "", type == T_COUNT ? "switching" : kTypeNames[type], best);
  }
  printf("}}\n");
}

// hash: the float output's bits, FNV-1a, for each Type on 2 s of noise with
// every parameter moving between blocks. Equal hashes from two builds mean
// they compute the same bits (compilers, CPUs, the WebAssembly module).
void Hash() {
  printf("{");
  for (int type = 0; type < T_COUNT; ++type) {
    DriveInstance *self = Make(kRate, 0x5A);
    Lcg rng = { 11u + static_cast<uint32_t>(type) };
    Set(self, "Type", static_cast<float>(type));
    uint32_t h = 2166136261u;
    float buf[128];
    for (int b = 0; b < 1400; ++b) {
      if (b % 50 == 0) {
        for (uint16_t i = 1; i < E.n_params; ++i) {
          const fm1_param_t &p = E.params[i];
          E.set_param(self, i, p.min + (p.max - p.min) * rng.Unit());
        }
      }
      for (int i = 0; i < 128; ++i) buf[i] = 0.7f * rng.Bipolar();
      E.render(self, buf, 64);
      for (int i = 0; i < 128; ++i) {
        uint32_t bits;
        memcpy(&bits, &buf[i], sizeof bits);
        for (int k = 0; k < 4; ++k) h = (h ^ ((bits >> (8 * k)) & 0xFFu)) * 16777619u;
      }
    }
    printf("%s\"%s\":\"%08x\"", type ? "," : "", kTypeNames[type], h);
  }
  printf("}\n");
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "bench") == 0) {
    Bench();
    return 0;
  }
  if (argc > 1 && strcmp(argv[1], "hash") == 0) {
    Hash();
    return 0;
  }
  printf("{");
  Means(); printf(",");
  Alias(); printf(",");
  Tape(); printf(",");
  Sweep(); printf(",");
  Glide(); printf(",");
  Switch(); printf(",");
  Silence(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}

// plate_test.cc -- fm1-plate-test: drives Plate (src/mi_fx.cc) through its
// engine struct where fm1-render cannot: Freeze turned while audio runs
// (fm1-render sets an effect's parameters only before the first block),
// block sizes that change from call to call, instance memory filled with
// junk, and the cost of each Freeze path. Prints one JSON object;
// tests/test_engines_plate_freeze.py reads it. `--bench` prints timings
// instead. MIT licence.

#include "fm1_engine.h"

#include <chrono>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_plate;

namespace {

const fm1_engine_t &E = fm1_engine_plate;
const float kRate = 44118.0f;
const size_t kMem = 70000;
alignas(16) unsigned char g_mem[kMem];

struct Lcg {
  uint32_t s;
  uint32_t Next() { s = s * 1664525u + 1013904223u; return s; }
  float Bipolar() { return static_cast<int32_t>(Next()) / 2147483648.0f; }  // [-1, 1)
  float Unit() { return (Next() >> 8) / 16777216.0f; }                        // [0, 1)
};

void *Make(float rate, int fill) {
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t n = E.instance_size(&host);
  if (n > kMem) return NULL;
  memset(g_mem, fill, kMem);
  return E.create(g_mem, &host);
}

uint16_t Index(const char *name) {
  for (uint16_t i = 0; i < E.n_params; ++i) {
    if (strcmp(E.params[i].name, name) == 0) return i;
  }
  fprintf(stderr, "no parameter %s\n", name);
  return 0xFFFF;
}

// The sources. NOISE_BURST: noise (+/-0.5) up to `until`, then silence.
// SINE: a 440 Hz sine of 0.5. NOISE_BAD: noise with NaN, infinities and 1e6
// mixed in after `until`.
enum Source { NOISE_BURST, SINE, NOISE_BAD, SILENCE_AFTER };

struct Change { uint32_t at; const char *name; float value; };

struct Run {
  float rate;
  int fill;
  uint32_t block;               // 0: random sizes 1..64
  Source source;
  uint32_t until;               // see Source
  const Change *changes;
  int n_changes;
  uint32_t total;               // frames
};

// Renders r into out (interleaved stereo, 2 * total floats).
void Render(const Run &r, float *out) {
  void *self = Make(r.rate, r.fill);
  Lcg noise = { 12345u }, sizes = { 777u }, bad = { 99u };
  float buf[128];
  double phase = 0.0;
  int next = 0;
  for (uint32_t pos = 0; pos < r.total;) {
    while (next < r.n_changes && r.changes[next].at <= pos) {
      E.set_param(self, Index(r.changes[next].name), r.changes[next].value);
      ++next;
    }
    uint32_t n = r.block ? r.block : 1 + sizes.Next() % 64;
    if (n > r.total - pos) n = r.total - pos;
    if (next < r.n_changes && r.changes[next].at - pos < n) n = r.changes[next].at - pos;
    for (uint32_t i = 0; i < n; ++i) {
      const uint32_t t = pos + i;
      float x = 0.0f;
      switch (r.source) {
        case NOISE_BURST: x = t < r.until ? 0.5f * noise.Bipolar() : 0.0f; break;
        case SINE:
          x = 0.5f * static_cast<float>(sin(phase));
          phase += 2.0 * 3.141592653589793 * 440.0 / r.rate;
          break;
        case NOISE_BAD: {
          x = 0.5f * noise.Bipolar();
          if (t >= r.until) {
            const uint32_t k = bad.Next() % 16;
            if (k == 0) x = NAN;
            else if (k == 1) x = INFINITY;
            else if (k == 2) x = -INFINITY;
            else if (k == 3) x = 1e6f;
          }
          break;
        }
        case SILENCE_AFTER: x = t < r.until ? 0.5f * noise.Bipolar() : 0.0f; break;
      }
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, n);
    memcpy(out + 2 * pos, buf, 2 * n * sizeof(float));
    pos += n;
  }
  E.destroy(self);
}

const uint32_t kMaxFrames = static_cast<uint32_t>(62 * 44118);
float g_a[2 * kMaxFrames], g_b[2 * kMaxFrames], g_c[2 * kMaxFrames];

uint32_t S(double seconds) { return static_cast<uint32_t>(seconds * kRate + 0.5); }

// RMS of both channels over [t0, t1) seconds.
double Rms(const float *x, double t0, double t1) {
  double sum = 0.0;
  const uint32_t a = S(t0), b = S(t1);
  for (uint32_t i = 2 * a; i < 2 * b; ++i) sum += static_cast<double>(x[i]) * x[i];
  return sqrt(sum / (2.0 * (b - a)));
}

double Db(double a, double b) { return 20.0 * log10(a / b); }

// Largest sample-to-sample step of either channel over frames [a, b).
float MaxStep(const float *x, uint32_t a, uint32_t b) {
  float m = 0.0f;
  for (uint32_t i = a + 1; i < b; ++i) {
    m = fmaxf(m, fabsf(x[2 * i] - x[2 * i - 2]));
    m = fmaxf(m, fabsf(x[2 * i + 1] - x[2 * i - 1]));
  }
  return m;
}

float Peak(const float *x, uint32_t a, uint32_t b) {
  float m = 0.0f;
  for (uint32_t i = 2 * a; i < 2 * b; ++i) m = fmaxf(m, fabsf(x[i]));
  return m;
}

// 1. Every parameter, Freeze included, at every kind of value (min, max,
// default, random, beyond the range, NaN, infinities), changed between
// blocks of random size while noise with NaN, infinities and 1e6 plays, for
// 20 s. The output must stay finite and bounded.
void Sweep() {
  void *self = Make(kRate, 0xA5);
  Lcg rng = { 1u };
  float buf[128];
  uint64_t samples = 0, nonfinite = 0, freeze_sets = 0;
  float peak = 0.0f;
  while (samples < static_cast<uint64_t>(20 * kRate)) {
    const uint32_t n = 1 + rng.Next() % 64;
    for (int changes = rng.Next() % 3; changes > 0; --changes) {
      const uint16_t index = static_cast<uint16_t>(rng.Next() % E.n_params);
      const fm1_param_t &p = E.params[index];
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
      if (strcmp(p.name, "Freeze") == 0) ++freeze_sets;
      E.set_param(self, index, v);
    }
    for (uint32_t i = 0; i < n; ++i) {
      float x = 0.5f * rng.Bipolar();
      const uint32_t k = rng.Next() % 512;
      if (k == 0) x = NAN;
      else if (k == 1) x = INFINITY;
      else if (k == 2) x = -1e6f;
      buf[2 * i] = buf[2 * i + 1] = x;
    }
    E.render(self, buf, n);
    for (uint32_t i = 0; i < 2 * n; ++i) {
      if (!(fabsf(buf[i]) <= 3.4e38f)) ++nonfinite;            // NaN or infinite
      else if (fabsf(buf[i]) > peak) peak = fabsf(buf[i]);
    }
    samples += n;
  }
  E.destroy(self);
  printf("\"sweep\":{\"samples\":%llu,\"freeze_sets\":%llu,\"nonfinite\":%llu,\"peak\":%.6f}",
         static_cast<unsigned long long>(samples), static_cast<unsigned long long>(freeze_sets),
         static_cast<unsigned long long>(nonfinite), peak);
}

// 2. Freeze, Decay and Mix turned mid-stream, rapid toggles that reverse the
// ramp half way included, rendered at blocks of 64, 7, 1 and random sizes,
// and from memory filled with 0x00, 0xA5 and 0xFF: all identical.
void Blocks() {
  const Change ch[] = {
    { 0, "Mix", 0.6f },
    { 22050, "Freeze", 1.0f }, { 30000, "Decay", 0.1f }, { 31000, "Damping", 0.9f },
    { 44118, "Mix", 0.9f }, { 66150, "Freeze", 0.0f },
    { 70000, "Freeze", 1.0f }, { 70100, "Freeze", 0.0f }, { 70150, "Freeze", 0.7f },
    { 70290, "Freeze", 0.2f }, { 80000, "Freeze", 1.0f }, { 80000, "Freeze", 0.0f },
    { 90000, "Freeze", 1.0f },
  };
  const int n = static_cast<int>(sizeof(ch) / sizeof(ch[0]));
  const uint32_t total = 110000;
  Run r = { kRate, 0, 64, NOISE_BURST, 44118, ch, n, total };
  Render(r, g_a);
  int same = 1;
  const uint32_t blocks[] = { 7, 1, 0 };
  for (int k = 0; k < 3; ++k) {
    r.block = blocks[k];
    Render(r, g_b);
    same &= memcmp(g_a, g_b, 2 * total * sizeof(float)) == 0;
  }
  r.block = 64;
  const int fills[] = { 0xA5, 0xFF };
  int same_fill = 1;
  for (int k = 0; k < 2; ++k) {
    r.fill = fills[k];
    Render(r, g_b);
    same_fill &= memcmp(g_a, g_b, 2 * total * sizeof(float)) == 0;
  }
  printf("\"blocks\":{\"block_independent\":%s,\"fill_independent\":%s}",
         same ? "true" : "false", same_fill ? "true" : "false");
}

// RMS over [t0, t1) seconds of the left channel through a one-pole low-pass
// at about 300 Hz: the body of the tail, without the highs the loop's
// interpolation wears away.
double LowRms(const float *x, double t0, double t1) {
  const float k = 1.0f - expf(-6.28318530718f * 300.0f / kRate);
  float y = 0.0f;
  double sum = 0.0;
  const uint32_t warm = S(t0) > 4410 ? S(t0) - 4410 : 0, a = S(t0), b = S(t1);
  for (uint32_t i = warm; i < b; ++i) {
    y += k * (x[2 * i] - y);
    if (i >= a) sum += static_cast<double>(y) * y;
  }
  return sqrt(sum / (b - a));
}

// 3. The hold. A second of noise, then silence; Freeze engages at 1.2 s in
// the falling tail. The level just before and just after, then 1 s windows
// up to a minute later, broadband and below about 300 Hz, at Decay 0, 0.5
// and 1.
void Hold() {
  printf("\"hold\":[");
  const float decays[] = { 0.0f, 0.5f, 1.0f };
  for (int k = 0; k < 3; ++k) {
    const Change ch[] = { { 0, "Mix", 1.0f }, { 0, "Decay", decays[k] }, { S(1.2), "Freeze", 1.0f } };
    const Run r = { kRate, 0, 64, NOISE_BURST, S(1.0), ch, 3, S(61.2) };
    Render(r, g_a);
    const double before = Rms(g_a, 1.17, 1.2), after = Rms(g_a, 1.21, 1.24);
    const double ref = Rms(g_a, 1.25, 2.25), low = LowRms(g_a, 1.25, 2.25);
    printf("%s{\"decay\":%g,\"before\":%.6g,\"after\":%.6g,\"step_db\":%.3f,\"ref\":%.6g,"
           "\"db_10s\":%.3f,\"db_30s\":%.3f,\"db_60s\":%.3f,"
           "\"low_db_10s\":%.3f,\"low_db_30s\":%.3f,\"low_db_60s\":%.3f}",
           k ? "," : "", decays[k], before, after, Db(after, before), ref,
           Db(Rms(g_a, 10.2, 11.2), ref), Db(Rms(g_a, 30.2, 31.2), ref),
           Db(Rms(g_a, 60.2, 61.2), ref), Db(LowRms(g_a, 10.2, 11.2), low),
           Db(LowRms(g_a, 30.2, 31.2), low), Db(LowRms(g_a, 60.2, 61.2), low));
  }
  printf("]");
}

// 3b. How long a frozen tail lasts. The loop stores 16-bit words truncated
// towards zero, so every pass loses up to a step per store and a quiet tail
// runs out: the time from Freeze to the last non-zero output sample, for a
// burst of noise at 0.5 and at 0.05 (Decay 0.5, Mix 1), streamed for up to
// 600 s.
void Lifetime() {
  printf("\"lifetime\":[");
  const float amps[] = { 0.5f, 0.05f };
  for (int k = 0; k < 2; ++k) {
    void *self = Make(kRate, 0);
    E.set_param(self, Index("Mix"), 1.0f);
    Lcg noise = { 12345u };
    float buf[128];
    const uint32_t at = S(1.2), total = S(601.2);
    uint32_t last = 0;
    double frozen = 0.0;
    for (uint32_t pos = 0; pos < total; pos += 64) {
      if (pos == at - at % 64) E.set_param(self, Index("Freeze"), 1.0f);
      for (uint32_t i = 0; i < 64; ++i) {
        const float x = pos + i < S(1.0) ? amps[k] * noise.Bipolar() : 0.0f;
        buf[2 * i] = buf[2 * i + 1] = x;
      }
      E.render(self, buf, 64);
      for (uint32_t i = 0; i < 128; ++i) {
        if (buf[i] != 0.0f) last = pos + i / 2;
        if (pos >= S(1.25) && pos < S(2.25)) frozen += static_cast<double>(buf[i]) * buf[i];
      }
    }
    E.destroy(self);
    printf("%s{\"amp\":%g,\"frozen_dbfs\":%.2f,\"lasts_s\":%.2f}", k ? "," : "", amps[k],
           10.0 * log10(frozen / (2.0 * (S(2.25) - S(1.25))) + 1e-30),
           (last + 1 - (at - at % 64)) / kRate);
  }
  printf("]");
}

// 4. Frozen, the reverb ignores its input: two renders alike up to the end
// of the ramp, then one goes silent and the other plays noise with NaN,
// infinities and 1e6 mixed in. At Mix 1 the outputs must be equal.
void Ignores() {
  const Change ch[] = { { 0, "Mix", 1.0f }, { S(1.0), "Freeze", 1.0f } };
  const uint32_t from = S(1.0) + 300, total = S(3.0);
  Run r = { kRate, 0, 64, SILENCE_AFTER, from, ch, 2, total };
  Render(r, g_a);
  r.source = NOISE_BAD;
  Render(r, g_b);
  uint32_t differ = 0;
  for (uint32_t i = 2 * from; i < 2 * total; ++i) differ += !(g_a[i] == g_b[i]);
  printf("\"ignores_input\":{\"differ\":%u,\"rms\":%.6g}", differ, Rms(g_a, 1.5, 3.0));
}

// 5. Clean switching, the owner's test for a switch: Freeze toggled every
// third 64-frame block for two seconds over a sine, against renders with it
// held off and held on. No step of the output may exceed the larger held
// render's largest step plus a 5 ms crossfade's 2P/220 (P the peak).
void Clean() {
  const uint32_t start = S(1.0), end = S(3.0), total = S(3.0);
  static Change toggles[700];
  int n = 0;
  toggles[n++] = { 0, "Mix", 0.5f };
  for (uint32_t at = start, on = 1; at < end && n < 700; at += 192, on ^= 1u) {
    toggles[n++] = { at, "Freeze", static_cast<float>(on) };
  }
  Run r = { kRate, 0, 64, SINE, 0, toggles, n, total };
  Render(r, g_a);
  const Change off[] = { { 0, "Mix", 0.5f } };
  Run r0 = { kRate, 0, 64, SINE, 0, off, 1, total };
  Render(r0, g_b);
  const Change on[] = { { 0, "Mix", 0.5f }, { start, "Freeze", 1.0f } };
  Run r1 = { kRate, 0, 64, SINE, 0, on, 2, total };
  Render(r1, g_c);
  const float held = fmaxf(MaxStep(g_b, start, end), MaxStep(g_c, start + 256, end));
  const float peak = Peak(g_a, start, end);
  const float toggled = MaxStep(g_a, start, end);
  // The single engage of r1, against its own steady steps.
  const float engage = MaxStep(g_c, start - 64, start + 256);
  printf("\"clean\":{\"toggles\":%d,\"held_step\":%.6g,\"peak\":%.6g,\"allowance\":%.6g,"
         "\"toggled_step\":%.6g,\"engage_step\":%.6g}",
         n - 1, held, peak, 2.0f * peak / 220.0f, toggled, engage);
}

// 6. Release: frozen for two seconds, then off with silence in: the tail
// decays as at Decay 0.5 and ends in exact zeros.
void Release() {
  const Change ch[] = { { 0, "Mix", 1.0f }, { S(1.0), "Freeze", 1.0f }, { S(3.0), "Freeze", 0.0f } };
  const uint32_t total = S(12.0);
  const Run r = { kRate, 0, 64, NOISE_BURST, S(1.0), ch, 3, total };
  Render(r, g_a);
  uint32_t last = 0;
  for (uint32_t i = 0; i < 2 * total; ++i) {
    if (g_a[i] != 0.0f) last = i / 2;
  }
  printf("\"release\":{\"frozen_rms\":%.6g,\"after_1s_db\":%.3f,\"zero_after_s\":%.3f}",
         Rms(g_a, 2.0, 3.0), Db(Rms(g_a, 3.9, 4.0), Rms(g_a, 2.9, 3.0)),
         (last + 1) / kRate - 3.0);
}

// 7. While frozen, Decay and Damping wait: a render that turns them during
// the hold equals one that does not, until release. Diffusion and Mix stay
// live.
void Waits() {
  const Change plain[] = { { 0, "Mix", 1.0f }, { S(1.0), "Freeze", 1.0f }, { S(2.0), "Freeze", 0.0f } };
  const Change turned[] = { { 0, "Mix", 1.0f }, { S(1.0), "Freeze", 1.0f },
                            { S(1.5), "Decay", 1.0f }, { S(1.6), "Damping", 1.0f },
                            { S(2.0), "Freeze", 0.0f } };
  const uint32_t total = S(2.5);
  Run r = { kRate, 0, 64, NOISE_BURST, S(1.0), plain, 3, total };
  Render(r, g_a);
  r.changes = turned;
  r.n_changes = 5;
  Render(r, g_b);
  uint32_t differ_frozen = 0, differ_after = 0;
  for (uint32_t i = 2 * S(1.0); i < 2 * S(2.0); ++i) differ_frozen += !(g_a[i] == g_b[i]);
  for (uint32_t i = 2 * S(2.0); i < 2 * total; ++i) differ_after += !(g_a[i] == g_b[i]);
  // Diffusion is live while frozen.
  const Change diffused[] = { { 0, "Mix", 1.0f }, { S(1.0), "Freeze", 1.0f },
                              { S(1.5), "Diffusion", 0.0f }, { S(2.0), "Freeze", 0.0f } };
  r.changes = diffused;
  r.n_changes = 4;
  Render(r, g_c);
  uint32_t differ_diffusion = 0;
  for (uint32_t i = 2 * S(1.5); i < 2 * S(2.0); ++i) differ_diffusion += !(g_a[i] == g_c[i]);
  printf("\"waits\":{\"differ_frozen\":%u,\"differ_after_release\":%u,"
         "\"differ_diffusion\":%u}", differ_frozen, differ_after, differ_diffusion);
}

// 8. Host rates: the ramp is sized to 5 ms at any rate and the hold works.
void Rates() {
  printf("\"rates\":[");
  const float rates[] = { 8000.0f, 32000.0f, 48000.0f, 96000.0f };
  for (int k = 0; k < 4; ++k) {
    const float rate = rates[k];
    const uint32_t at = static_cast<uint32_t>(1.2f * rate);
    const Change ch[] = { { 0, "Mix", 1.0f }, { at, "Freeze", 1.0f } };
    const Run r = { rate, 0, 64, NOISE_BURST, static_cast<uint32_t>(rate), ch, 2,
                    static_cast<uint32_t>(4.2f * rate) };
    Render(r, g_a);
    // Windows in frames of this rate.
    double s1 = 0.0, s2 = 0.0;
    const uint32_t a1 = static_cast<uint32_t>(1.25f * rate), b1 = static_cast<uint32_t>(2.25f * rate);
    const uint32_t a2 = static_cast<uint32_t>(3.2f * rate), b2 = static_cast<uint32_t>(4.2f * rate);
    for (uint32_t i = 2 * a1; i < 2 * b1; ++i) s1 += static_cast<double>(g_a[i]) * g_a[i];
    for (uint32_t i = 2 * a2; i < 2 * b2; ++i) s2 += static_cast<double>(g_a[i]) * g_a[i];
    uint64_t nonfinite = 0;
    for (uint32_t i = 0; i < 2 * r.total; ++i) nonfinite += !(fabsf(g_a[i]) <= 3.4e38f);
    printf("%s{\"rate\":%g,\"db_2s\":%.3f,\"nonfinite\":%llu}", k ? "," : "", rate,
           10.0 * log10(s2 / s1), static_cast<unsigned long long>(nonfinite));
  }
  printf("]");
}

// --bench: nanoseconds per 64-frame block of noise with Freeze off, frozen,
// and ramping all the time (toggled every 3 blocks, so the ramp never lands).
void Bench() {
  float buf[128];
  Lcg rng = { 5u };
  const int blocks = 20000;
  const char *modes[] = { "off", "frozen", "ramping" };
  printf("{");
  for (int m = 0; m < 3; ++m) {
    double best = 1e30;
    for (int rep = 0; rep < 5; ++rep) {
      void *self = Make(kRate, 0);
      if (m == 1) E.set_param(self, Index("Freeze"), 1.0f);
      const std::chrono::steady_clock::time_point t0 = std::chrono::steady_clock::now();
      for (int b = 0; b < blocks; ++b) {
        if (m == 2 && b % 3 == 0) E.set_param(self, Index("Freeze"), static_cast<float>((b / 3) & 1));
        for (int i = 0; i < 64; ++i) buf[2 * i] = buf[2 * i + 1] = 0.5f * rng.Bipolar();
        E.render(self, buf, 64);
      }
      const double ns = std::chrono::duration<double, std::nano>(
          std::chrono::steady_clock::now() - t0).count() / blocks;
      if (ns < best) best = ns;
      E.destroy(self);
    }
    printf("%s\"%s\":%.1f", m ? "," : "", modes[m], best);
  }
  fm1_host_t host = { FM1_ENGINE_API_VERSION, kRate, 64 };
  printf(",\"instance_bytes\":%zu}\n", E.instance_size(&host));
}

}  // namespace

int main(int argc, char **argv) {
  if (argc > 1 && strcmp(argv[1], "--bench") == 0) { Bench(); return 0; }
  printf("{");
  Sweep(); printf(",");
  Blocks(); printf(",");
  Hold(); printf(",");
  Lifetime(); printf(",");
  Ignores(); printf(",");
  Clean(); printf(",");
  Release(); printf(",");
  Waits(); printf(",");
  Rates();
  printf("}\n");
  return 0;
}

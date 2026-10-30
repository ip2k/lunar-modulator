// dx7_sine_oracle.cc -- fm1-dx7-sine-oracle: how close the build's DX7 sine
// (FM1_DX7_SINE, engines/Makefile; engines/msfa.md, "The trunc12 sine") comes
// to frequency modulation computed in doubles.
//
//   fm1-dx7-sine-oracle            # one line of JSON
//
// Every case runs msfa's own operator kernels (FmOpKernel::compute_pure,
// compute and compute_fb, third_party/msfa) through the Sin::lookup this
// build has, msfa's or trunc12's, for one second at 44,118 Hz in 64-sample
// blocks with fixed gains, and compares the output with the same operators
// in double precision: the same integer phase increments and the same
// gains, sin() in place of the table. The figure is the signal-to-error
// ratio in dB over the whole second. Feedback cases compare with the same
// recurrence in doubles; they are reported but are only meaningful while the
// recurrence is well conditioned (low feedback), which the test checks by
// requiring msfa's sine to reach them too.
//
// It also sweeps Sin::lookup itself over 2^20 phases (every 16th Q24 phase)
// for its largest magnitude and its largest error against sin().
//
// tests/test_dx7_sine.py builds it with each value of the switch and holds
// trunc12 to at least 50 dB in every two- and three-operator case. MIT
// licence (this file).

#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#include <vector>

#include "../src/msfa.h"

namespace {

const double kRate = 44118.0;
const int kN = fm1_msfa::kN;                       // 64
const int kBlocks = (44118 + kN - 1) / kN;         // one second
const int kSamples = kBlocks * kN;
const double kQ24 = 16777216.0;
const double kTwoPi = 6.283185307179586476925286766559;

int32_t Freq(double hz) { return static_cast<int32_t>(floor(hz / kRate * kQ24 + 0.5)); }
int32_t Gain(double g) { return static_cast<int32_t>(floor(g * kQ24 + 0.5)); }

// The phase of sample n of an operator starting at 0: what msfa's int32
// accumulator holds (it wraps; Sin::lookup reads its low 24 bits), as a
// fraction of a cycle.
double Cycles(int32_t freq, int n) {
  const uint32_t p = static_cast<uint32_t>(freq) * static_cast<uint32_t>(n);
  return static_cast<double>(p & 0xFFFFFFu) / kQ24;
}

double Snr(const std::vector<double> &ref, const std::vector<int32_t> &got) {
  double s = 0, e = 0;
  for (size_t i = 0; i < ref.size(); ++i) {
    const double x = got[i] / kQ24, d = x - ref[i];
    s += ref[i] * ref[i];
    e += d * d;
  }
  return e > 0 ? 10.0 * log10(s / e) : 999.0;
}

struct Op { double ratio, gain; };

// A stack: ops[0] the carrier at `hz`, each next one modulating the one
// before (ops[k] at hz * ratio). Rendered by msfa's kernels block by block.
double Stack(double hz, const Op *ops, int n) {
  std::vector<int32_t> freq(n), gain(n), phase(n, 0);
  for (int k = 0; k < n; ++k) {
    freq[k] = Freq(hz * ops[k].ratio);
    gain[k] = Gain(ops[k].gain);
  }
  std::vector<int32_t> got(kSamples);
  int32_t bus[2][64];
  for (int b = 0; b < kBlocks; ++b) {
    int cur = 0;
    for (int k = n - 1; k >= 0; --k) {
      int32_t *out = k == 0 ? &got[b * kN] : bus[cur ^ 1];
      if (k == n - 1)
        fm1_msfa::FmOpKernel::compute_pure(out, phase[k], freq[k], gain[k], gain[k], false);
      else
        fm1_msfa::FmOpKernel::compute(out, bus[cur], phase[k], freq[k], gain[k], gain[k], false);
      cur ^= 1;
      phase[k] = static_cast<int32_t>(static_cast<uint32_t>(phase[k]) +
                                      (static_cast<uint32_t>(freq[k]) << 6));
    }
  }
  std::vector<double> ref(kSamples);
  for (int i = 0; i < kSamples; ++i) {
    double in = 0;   // the modulation, in cycles
    for (int k = n - 1; k >= 0; --k) {
      // msfa's gain multiplies a Q24 sine and the result is a Q24 phase
      // offset: an operator at gain g moves the next one's phase by g cycles.
      in = gain[k] / kQ24 * sin(kTwoPi * (Cycles(freq[k], i) + in));
    }
    ref[i] = in;
  }
  return Snr(ref, got);
}

// One operator modulating itself (compute_fb, DX7 feedback through msfa's
// shift): y[n] = g sin(2 pi (phase + (y[n-1] + y[n-2]) / 2^(shift+1))).
double Feedback(double hz, double g, int shift) {
  const int32_t freq = Freq(hz), gain = Gain(g);
  std::vector<int32_t> got(kSamples);
  int32_t fb[2] = { 0, 0 }, phase = 0;
  for (int b = 0; b < kBlocks; ++b) {
    fm1_msfa::FmOpKernel::compute_fb(&got[b * kN], phase, freq, gain, gain, fb, shift, false);
    phase = static_cast<int32_t>(static_cast<uint32_t>(phase) + (static_cast<uint32_t>(freq) << 6));
  }
  std::vector<double> ref(kSamples);
  double y0 = 0, y = 0;
  const double scale = 1.0 / static_cast<double>(1 << (shift + 1));
  for (int i = 0; i < kSamples; ++i) {
    const double in = (y0 + y) * scale;
    y0 = y;
    y = gain / kQ24 * sin(kTwoPi * (Cycles(freq, i) + in));
    ref[i] = y;
  }
  return Snr(ref, got);
}

}  // namespace

int main() {
  struct StackCase { const char *name; double hz; Op ops[3]; int n; };
  const StackCase stacks[] = {
    { "pure 110", 110.0, { { 1, 0.5 } }, 1 },
    { "pure 440", 440.0, { { 1, 0.5 } }, 1 },
    { "pure 1760.3", 1760.3, { { 1, 0.5 } }, 1 },
    { "pure 7040", 7040.0, { { 1, 0.5 } }, 1 },
    { "1:1 idx0.25 220", 220.0, { { 1, 0.5 }, { 1, 0.25 } }, 2 },
    { "tine 1:14 idx0.05 523", 523.25, { { 1, 0.5 }, { 14, 0.05 } }, 2 },
    { "1:3.5 idx0.5 110", 110.0, { { 1, 0.5 }, { 3.5, 0.5 } }, 2 },
    { "1:1 idx1 220", 220.0, { { 1, 0.5 }, { 1, 1.0 } }, 2 },
    { "1:2 idx2 110", 110.0, { { 1, 0.5 }, { 2, 2.0 } }, 2 },
    { "1:1 idx4 55", 55.0, { { 1, 0.5 }, { 1, 4.0 } }, 2 },
    { "3-op 1:2:3 330", 330.0, { { 1, 0.5 }, { 2, 0.5 }, { 3, 0.3 } }, 3 },
    { "3-op 1:1:7 svar 196", 196.0, { { 1, 0.5 }, { 1, 0.8 }, { 7, 0.2 } }, 3 },
  };
  printf("{\"dx7_sine\":\"%s\",\"rate\":%g,\"samples\":%d,\"stacks\":[",
         FM1_DX7_SINE_TRUNC12 ? "trunc12" : "msfa", kRate, kSamples);
  for (size_t c = 0; c < sizeof(stacks) / sizeof(stacks[0]); ++c) {
    const StackCase &s = stacks[c];
    printf("%s{\"name\":\"%s\",\"ops\":%d,\"snr_db\":%.2f}", c ? "," : "", s.name, s.n,
           Stack(s.hz, s.ops, s.n));
  }
  printf("],\"feedback\":[");
  const int shifts[] = { 5, 4, 3, 2, 1 };
  for (size_t c = 0; c < sizeof(shifts) / sizeof(shifts[0]); ++c) {
    printf("%s{\"shift\":%d,\"hz\":220,\"snr_db\":%.2f}", c ? "," : "", shifts[c],
           Feedback(220.0, 0.5, shifts[c]));
  }
  // Sin::lookup over every 16th Q24 phase: its largest magnitude (never past
  // 2^24, msfa's full scale) and its largest error against sin() in Q24.
  int32_t peak = 0;
  double max_err = 0;
  for (uint32_t p = 0; p < (1u << 24); p += 16) {
    const int32_t y = fm1_msfa::Sin::lookup(static_cast<int32_t>(p));
    if (abs(y) > peak) peak = abs(y);
    const double err = fabs(y - kQ24 * sin(kTwoPi * p / kQ24));
    if (err > max_err) max_err = err;
  }
  printf("],\"lookup\":{\"phases\":%u,\"peak\":%d,\"max_err_q24\":%.1f,\"max_err_db\":%.2f}}\n",
         (1u << 24) / 16, peak, max_err, 20.0 * log10(max_err / kQ24));
  return 0;
}

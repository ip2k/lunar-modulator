// dx7_loop.cc -- the feedback loops of DX7 algorithms 4 and 6 (dx7_loop.h).
// MIT licence (this file).

#include "dx7_loop.h"

namespace fm1 {
namespace dx7 {

namespace {

// a + b modulo 2^32, as msfa's phases wrap (its own files are built with
// -fwrapv; this one is not, so the sum is taken unsigned).
inline int32_t Wrap(int32_t a, int32_t b) {
  return static_cast<int32_t>(static_cast<uint32_t>(a) + static_cast<uint32_t>(b));
}

// The chain for a fixed n, so the compiler can unroll it. An operator
// under the threshold gets gain and slope 0: its output is then exactly 0,
// as FmCore's skip gives.
template <int n>
void Chain(const fm1_msfa::FmOpParams *params, bool feedback, int fb_shift, int32_t fb_buf[2],
           int32_t *out) {
  const int kN = fm1_msfa::kN;
  int32_t phase[n], freq[n], gain[n], dgain[n];
  for (int j = 0; j < n; ++j) {
    const fm1_msfa::FmOpParams &q = params[j];
    const bool on = q.gain[0] >= kLevelThresh || q.gain[1] >= kLevelThresh;
    phase[j] = q.phase;
    freq[j] = q.freq;
    gain[j] = on ? q.gain[0] : 0;
    dgain[j] = on ? (q.gain[1] - q.gain[0] + (kN >> 1)) >> fm1_msfa::kLgN : 0;
  }
  int32_t y0 = fb_buf[0], y = fb_buf[1];
  for (int i = 0; i < kN; ++i) {
    int32_t in = feedback ? (y0 + y) >> (fb_shift + 1) : 0;
    for (int j = 0; j < n; ++j) {
      gain[j] += dgain[j];
      in = static_cast<int32_t>(
          (static_cast<int64_t>(fm1_msfa::Sin::lookup(Wrap(phase[j], in))) * gain[j]) >> 24);
      phase[j] = Wrap(phase[j], freq[j]);
    }
    y0 = y;
    y = in;
    out[i] += in;
  }
  if (feedback) {
    fb_buf[0] = y0;
    fb_buf[1] = y;
  }
}

}  // namespace

void RenderChain(const fm1_msfa::FmOpParams *params, int n, bool feedback, int fb_shift,
                 int32_t fb_buf[2], int32_t *out) {
  switch (n) {
    case 1: Chain<1>(params, feedback, fb_shift, fb_buf, out); break;
    case 2: Chain<2>(params, feedback, fb_shift, fb_buf, out); break;
    default: Chain<3>(params, feedback, fb_shift, fb_buf, out); break;
  }
}

void RenderWithLoop(fm1_msfa::FmCore *core, fm1_msfa::FmOpParams *params, int alg, int n,
                    int fb_shift, int32_t fb_buf[2], int32_t *out) {
  if (n > 3) n = 3;
  RenderChain(params, n, true, fb_shift, fb_buf, out);
  int32_t saved[3][2];
  for (int j = 0; j < n; ++j) {
    saved[j][0] = params[j].gain[0];
    saved[j][1] = params[j].gain[1];
    params[j].gain[0] = params[j].gain[1] = 0;
  }
  int32_t unused_fb[2] = { 0, 0 };
  core->compute(out, params, alg, unused_fb, 16);
  for (int j = 0; j < n; ++j) {
    params[j].gain[0] = saved[j][0];
    params[j].gain[1] = saved[j][1];
  }
}

}  // namespace dx7
}  // namespace fm1

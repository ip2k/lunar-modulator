// msfa_prelude.h -- what the vendored msfa files (third_party/msfa, Google's
// music-synthesizer-for-android, Apache-2.0) need before they are included
// inside namespace fm1_msfa: the system headers they include (so their
// include guards keep those out of the namespace) and a stand-in for
// msfa's synth.h.
//
// synth.h is not used. It turns on msfa's NEON kernels on any aarch64 target
// (Apple's desktops included), which compute the operators in float and would
// make this desktop's output differ from the browser's and the FM-1's, and on
// Apple it includes a system header that cannot sit inside a namespace. This
// header defines what synth.h defines instead (LG_N, N, min, max, hasNeon()
// returning false, an empty SynthMemoryBarrier), with the same values, and
// claims synth.h's include guard so the vendored file is never read. The
// operators then run msfa's portable integer kernels everywhere.
//
// Included by src/msfa.h (our code's view of msfa) and src/msfa_unit.cc
// (which compiles each vendored .cc file). MIT licence (this file).

#ifndef FM1_MSFA_PRELUDE_H_
#define FM1_MSFA_PRELUDE_H_

#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include <cstring>

#ifndef M_PI   // sin.cc's; a strict -std=c++11 on musl does not define it
#define M_PI 3.14159265358979323846
#endif

#define __SYNTH_H   // synth.h's guard: the vendored file is never read
#define LG_N 6
#define N (1 << LG_N)
#define SynthMemoryBarrier()

namespace fm1_msfa {

template <typename T>
inline static T min(const T &a, const T &b) { return a < b ? a : b; }
template <typename T>
inline static T max(const T &a, const T &b) { return a > b ? a : b; }
static inline bool hasNeon() { return false; }

}  // namespace fm1_msfa

#endif  // FM1_MSFA_PRELUDE_H_

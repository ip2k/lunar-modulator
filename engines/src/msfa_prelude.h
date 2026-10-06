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
// msfa's tables as const data (flash on the FM-1; engines/msfa.md, "Tables in
// flash"). msfa declares its sine and exp2 tables as plain int32_t arrays
// (sin.h, exp2.h) that Sin::init and Exp2::init fill at start-up, and
// freqlut.cc defines its frequency table the same way, 28.7 KB of RAM with
// exp2.cc's unused tanhtab. Here each name is a macro for the array a pointer
// points to: msfa's code reads `(*fm1_sintab)[i]` where it wrote
// `sintab[i]` and is otherwise unchanged (the vendored files stay
// byte-identical), its headers declare the pointers in place of the arrays,
// and our src/msfa_tables.cc points them at const tables generated ahead of
// time (src/msfa_rom.cc, tools/msfa_tables.py). sin.cc and exp2.cc, which
// only define and fill the tables (Sin::compute is used by nothing but
// `#if 0` code), are not compiled; freqlut.cc is, for Freqlut::lookup, and
// defines the pointer `fm1_freqlut`, which the engine points at the 44,118 Hz
// table or at its instance's own at another rate. Defining FM1_MSFA_REF
// leaves the names alone: the test oracle compiles msfa's own init with it,
// to compare (fm1-dx7-oracle --tables-vs-msfa).
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

#ifndef M_PI   // sin.cc's (the oracle's build of it); strict C++11 on musl lacks it
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

#ifndef FM1_MSFA_REF
#define sintab (*fm1_sintab)      // sin.h: int32_t (*fm1_sintab)[2048]
#define exp2tab (*fm1_exp2tab)    // exp2.h: int32_t (*fm1_exp2tab)[2048]
#define lut (*fm1_freqlut)        // freqlut.cc: int32_t (*fm1_freqlut)[1025]
#endif

#endif  // FM1_MSFA_PRELUDE_H_

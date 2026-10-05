// dx7_loop.h -- the multi-operator feedback loops of DX7 algorithms 4 and 6
// for the FM6 engine (src/msfa_dx7.cc), on msfa's operators.
//
// msfa's algorithm table marks the loops (the sixth operator takes FB_IN,
// the fourth in algorithm 4 and the fifth in 6 give FB_OUT) but its FmCore
// runs only single-operator feedback ("todo: more than one op in a feedback
// loop"), so with msfa alone those two algorithms play without feedback.
// Here the operators of the loop run sample by sample as a chain, the last
// one's output fed back to the first as msfa feeds an operator back to
// itself, and FmCore runs the rest.
//
// Our own code on msfa's kernel conventions (fm_op_kernel.cc, Apache-2.0):
// the same gain ramp, the same sine lookup, the same feedback scaling, so
// that a chain of one operator is msfa's own feedback operator to the bit,
// and a chain without feedback is FmCore's to the bit (fm1-dx7-oracle
// --loop-check). MIT licence (this file).

#ifndef FM1_DX7_LOOP_H_
#define FM1_DX7_LOOP_H_

#include <stdint.h>

#include "msfa.h"

namespace fm1 {
namespace dx7 {

// An operator gain (Q24) under this is silent: fm_core.cc's kLevelThresh,
// under which FmCore skips the operator.
const int32_t kLevelThresh = 1120;

// Operators 0..n-1 of params (msfa's order: the sixth first; n 1..3) over
// one block as a chain, each modulating the next, the last one added to
// out. With feedback, the first takes the mean of the last one's previous
// two outputs (fb_buf, updated) shifted right by fb_shift + 1, as msfa's
// FmOpKernel::compute_fb; without, nothing, and fb_buf is left alone. An
// operator whose gains are both under msfa's threshold is silent, as FmCore
// skips it. Phases are not advanced (FmCore advances them).
void RenderChain(const fm1_msfa::FmOpParams *params, int n, bool feedback, int fb_shift,
                 int32_t fb_buf[2], int32_t *out);

// Algorithm `alg` (0..31) of params into out, as FmCore::compute with
// feedback_shift fb_shift, except that the first n operators run as a
// chain with its loop closed (RenderChain); the rest through `core` with
// the chain's gains set to 0 for the call, which skips them. fb_buf is the
// chain's.
void RenderWithLoop(fm1_msfa::FmCore *core, fm1_msfa::FmOpParams *params, int alg, int n,
                    int fb_shift, int32_t fb_buf[2], int32_t *out);

}  // namespace dx7
}  // namespace fm1

#endif  // FM1_DX7_LOOP_H_

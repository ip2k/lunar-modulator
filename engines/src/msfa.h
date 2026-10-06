// msfa.h -- the parts of msfa (Google's music-synthesizer-for-android FM
// core, Apache-2.0; vendored byte-identical in third_party/msfa) that the FM6
// engine (src/msfa_dx7.cc) uses, inside namespace fm1_msfa.
//
// Every msfa header is included here, inside the namespace, after
// msfa_prelude.h has included the system headers they need (their include
// guards keep those out of it) and stood in for synth.h (it says why). msfa's
// classes and globals (Env, Lfo, Sin, `lut`, `sintab`...) then live in
// fm1_msfa and cannot collide with anything else the firmware links;
// msfa_unit.cc compiles the vendored .cc files the same way.
//
// N and LG_N are macros in msfa; they are #undef'd at the end of this header.
// Our code uses fm1_msfa::kN and kLgN.
//
// MIT licence (this file). The vendored files keep their Apache-2.0 headers.

#ifndef FM1_MSFA_H_
#define FM1_MSFA_H_

#include "msfa_prelude.h"

namespace fm1_msfa {

#include "aligned_buf.h"
#include "controllers.h"
#include "env.h"
#include "exp2.h"
#include "fm_core.h"
#include "fm_op_kernel.h"
#include "freqlut.h"
#include "lfo.h"
#include "patch.h"
#include "pitchenv.h"
#include "sin.h"

// dx7note.cc's note set-up, which it defines without a header.
int32_t midinote_to_logfreq(int midinote);
int32_t osc_freq(int midinote, int mode, int coarse, int fine, int detune);
int ScaleVelocity(int velocity, int sensitivity);
int ScaleRate(int midinote, int sensitivity);
int ScaleLevel(int midinote, int break_pt, int left_depth, int right_depth,
               int left_curve, int right_curve);

const int kLgN = LG_N;   // samples per msfa block: 64
const int kN = N;

}  // namespace fm1_msfa

#undef N
#undef LG_N

#endif  // FM1_MSFA_H_

// msfa_unit.cc -- compiles one vendored msfa source file (third_party/msfa,
// Apache-2.0, byte-identical to upstream) inside namespace fm1_msfa. The
// build compiles this file once per msfa .cc, naming it in FM1_MSFA_UNIT
// (mk/msfa.mk), with the vendored-code flags: each upstream file stays its
// own translation unit, as upstream builds them (five of msfa's headers have
// no include guard, so two of its .cc files cannot share one). Nothing of
// ours is here but the includes; src/msfa_prelude.h says why the namespace.
//
// MIT licence (this file).

#include "msfa_prelude.h"

#ifndef FM1_MSFA_UNIT
#error "compile with -DFM1_MSFA_UNIT='\"env.cc\"' (mk/msfa.mk)"
#endif

namespace fm1_msfa {
#include FM1_MSFA_UNIT
}  // namespace fm1_msfa

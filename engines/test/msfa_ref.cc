// msfa_ref.cc -- msfa's own start-up tables for fm1-dx7-oracle
// --tables-vs-msfa: Sin::init, Exp2::init and Freqlut::init as upstream's
// sin.cc, exp2.cc and freqlut.cc (third_party/msfa, Apache-2.0) compute them
// into their plain arrays. Those files are compiled with FM1_MSFA_REF into
// namespace fm1_msfa_ref (mk/msfa.mk); the engine reads const copies made by
// tools/msfa_tables.py instead (src/msfa_prelude.h), and the oracle compares
// the two word for word. A desktop test tool. MIT licence (this file).

#define FM1_MSFA_REF 1
#include "../src/msfa_prelude.h"

namespace fm1_msfa_ref {
#include "sin.h"
#include "exp2.h"
#include "freqlut.h"
extern int32_t lut[1025];   // freqlut.cc's, which no msfa header declares
}  // namespace fm1_msfa_ref

#include "msfa_ref.h"

void MsfaRefTables(double rate, const int32_t **sin, const int32_t **exp2, const int32_t **lut) {
  fm1_msfa_ref::Sin::init();
  fm1_msfa_ref::Exp2::init();
  fm1_msfa_ref::Freqlut::init(rate);
  *sin = fm1_msfa_ref::sintab;
  *exp2 = fm1_msfa_ref::exp2tab;
  *lut = fm1_msfa_ref::lut;
}

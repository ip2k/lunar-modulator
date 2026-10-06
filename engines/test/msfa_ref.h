// msfa_ref.h -- msfa's own start-up tables, as upstream computes them
// (test/msfa_ref.cc), for fm1-dx7-oracle --tables-vs-msfa. MIT licence.
#ifndef FM1_MSFA_REF_H_
#define FM1_MSFA_REF_H_

#include <stdint.h>

// Runs msfa's Sin::init, Exp2::init and Freqlut::init(rate) and points at
// their tables: 2,048, 2,048 and 1,025 words. Valid until the next call.
void MsfaRefTables(double rate, const int32_t **sin, const int32_t **exp2, const int32_t **lut);

#endif  // FM1_MSFA_REF_H_

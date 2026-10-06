// msfa_tables.cc -- msfa's tables as const data (msfa_prelude.h, engines/msfa.md
// "Tables in flash"): the pointers through which msfa's code reads its sine
// and exp2 tables, aimed at the const tables of src/msfa_rom.cc, and
// FillFreqLut, the frequency table for a rate other than the FM-1's.
//
// The pointers are not const (msfa's headers declare them so), but nothing
// writes through them: Sin::init and Exp2::init, which wrote the tables, are
// not compiled, and the const_cast only lets the declared type point at
// const data. Being constant initialised, they are set before any code runs
// (no start-up function).
//
// MIT licence (this file).

#include "msfa.h"

namespace fm1_msfa {

int32_t (*fm1_sintab)[SIN_N_SAMPLES << 1] =
    const_cast<int32_t (*)[SIN_N_SAMPLES << 1]>(&kSinTab);
int32_t (*fm1_exp2tab)[EXP2_N_SAMPLES << 1] =
    const_cast<int32_t (*)[EXP2_N_SAMPLES << 1]>(&kExp2Tab);

// 2^(1/1024), the double nearest it: what Freqlut::init's pow(2, 1.0 / 1024)
// folds to (tools/msfa_tables.py's INC; the oracle compares the tables).
const double kOctaveStep = 1.0006771306930664;

void FillFreqLut(int32_t lut[kFreqLutSize], uint32_t hz) {
  // Freqlut::init: y = 2^44 / rate, then y *= 2^(1/1024) per entry, each
  // entry floor(y + 0.5); y is positive, so the conversion's truncation is
  // that floor (no libm).
  double y = static_cast<double>(1LL << 44) / static_cast<double>(hz);
  for (int i = 0; i < kFreqLutSize; ++i) {
    lut[i] = static_cast<int32_t>(y + 0.5);
    y *= kOctaveStep;
  }
}

}  // namespace fm1_msfa

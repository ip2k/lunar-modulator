/* mp_rng.c -- the primitives' PRNG: xorshift64* (Sebastiano Vigna), the same
 * generator fm1_seq rolls with (engines/seq/seq_engine.c, R7), seeded through
 * splitmix64 so that every 32-bit seed, 0 included, gives a good state. */
#include "mp_int.h"

void fm1_mp_rng_seed(fm1_mp_rng_t *r, uint32_t seed) {
  uint64_t z = (uint64_t)seed + 0x9E3779B97F4A7C15ull;
  z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
  z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
  z ^= z >> 31;
  r->s = z ? z : 0x9E3779B97F4A7C15ull;
}

uint32_t fm1_mp_rng_next(fm1_mp_rng_t *r) {
  uint64_t x = r->s;
  x ^= x >> 12;
  x ^= x << 25;
  x ^= x >> 27;
  r->s = x;
  return (uint32_t)((x * 0x2545F4914F6CDD1Dull) >> 32);
}

float fm1_mp_rng_bipolar(fm1_mp_rng_t *r) {
  const int32_t v = (int32_t)(fm1_mp_rng_next(r) >> 8) - 8388608;
  return (float)v * (1.0f / 8388608.0f);
}

/* mp_turing.c -- the Turing-machine shift register (fm1_mp.h).
 *
 * After the Turing Machine by Tom Whitwell (Music Thing Modular), from its
 * published behaviour: a looping shift register whose recirculating bit is
 * inverted with a set probability. Workshop Computer card 20 (Chris Johnson,
 * MIT) is an implementation the 2026-10-01 options note lists [reported];
 * this one is our own and was not written from it. No mask is built from the
 * length, so length 32 has none of the shift-by-32 undefined behaviour noted
 * in O_C's util_turing.h (notes/upstream-candidates.md). */
#include "mp_int.h"

void fm1_mp_turing_init(fm1_mp_turing_t *t, uint32_t seed) {
  fm1_mp_rng_seed(&t->rng, seed);
  t->reg = fm1_mp_rng_next(&t->rng);
  t->length = 16;
  t->flip_threshold = 0;
  t->pad_[0] = t->pad_[1] = t->pad_[2] = 0;
}

void fm1_mp_turing_set_length(fm1_mp_turing_t *t, int length) {
  t->length = (uint8_t)(length < 1 ? 1 : length > 32 ? 32 : length);
}

void fm1_mp_turing_set_flip(fm1_mp_turing_t *t, float p) {
  t->flip_threshold = (uint64_t)(mp_clampf(p, 0.0f, 1.0f, 0.0f) * 4294967296.0f);
}

float fm1_mp_turing_clock(fm1_mp_turing_t *t) {
  const uint32_t draw = fm1_mp_rng_next(&t->rng);
  uint32_t bit = (t->reg >> (t->length - 1u)) & 1u;
  if ((uint64_t)draw < t->flip_threshold) bit ^= 1u;
  t->reg = (t->reg << 1) | bit;
  return fm1_mp_turing_value(t);
}

float fm1_mp_turing_value(const fm1_mp_turing_t *t) {
  return (float)(t->reg & 0xFFu) * (1.0f / 255.0f);
}

int fm1_mp_turing_gate(const fm1_mp_turing_t *t) {
  return (int)(t->reg & 1u);
}

uint32_t fm1_mp_turing_bits(const fm1_mp_turing_t *t) {
  return t->reg;
}

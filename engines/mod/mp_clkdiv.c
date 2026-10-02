/* mp_clkdiv.c -- clock divider and multiplier on integer ticks (fm1_mp.h).
 * Pulse k falls on the first tick t with t x mul >= k x period, so the count
 * of pulses up to tick t is floor(t x mul / period) + 1: a Bresenham
 * distribution, exact and drift-free over any number of ticks. */
#include "mp_int.h"

static uint32_t clampu(uint32_t x, uint32_t lo, uint32_t hi) {
  return x < lo ? lo : x > hi ? hi : x;
}

void fm1_mp_clkdiv_init(fm1_mp_clkdiv_t *c, uint32_t ref, uint32_t mul, uint32_t div) {
  c->period = clampu(ref, 1u, 65535u) * clampu(div, 1u, 256u);
  c->mul = clampu(mul, 1u, 256u);
  c->pad_[0] = c->pad_[1] = c->pad_[2] = 0;
  fm1_mp_clkdiv_reset(c);
}

void fm1_mp_clkdiv_reset(fm1_mp_clkdiv_t *c) {
  c->acc = 0;
  c->started = 0;
}

uint32_t fm1_mp_clkdiv_tick(fm1_mp_clkdiv_t *c) {
  return fm1_mp_clkdiv_advance(c, 1);
}

uint32_t fm1_mp_clkdiv_advance(fm1_mp_clkdiv_t *c, uint32_t ticks) {
  uint64_t pulses = 0, sum;
  if (ticks == 0) return 0;
  if (!c->started) {
    c->started = 1;
    c->acc = 0;
    pulses = 1;
    --ticks;
  }
  sum = (uint64_t)c->acc + (uint64_t)ticks * c->mul;
  pulses += sum / c->period;
  c->acc = (uint32_t)(sum % c->period);
  return pulses > 0xFFFFFFFFull ? 0xFFFFFFFFu : (uint32_t)pulses;
}

uint32_t fm1_mp_clkdiv_phase(const fm1_mp_clkdiv_t *c) {
  return c->started ? (uint32_t)(((uint64_t)c->acc << 32) / c->period) : 0;
}

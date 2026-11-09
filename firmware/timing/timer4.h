/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_TIMER4_H
#define LUNAR_TIMER4_H
enum lunar_timer_register { LUNAR_TIMER_CON, LUNAR_TIMER_CNT, LUNAR_TIMER_PRD };
struct lunar_timer_io {
    void *context;
    unsigned (*read)(void *, enum lunar_timer_register);
    void (*write)(void *, enum lunar_timer_register, unsigned);
    void (*sync)(void *);
};
struct lunar_timer {
    struct lunar_timer_io io;
    unsigned ticks_per_ms, poll_limit, failed, active;
};
/* Software only. Caller must establish OSC rate, exclusive TIMER4 ownership,
 * current-core/IRQ policy and a disabled timer. No guessed default clock.
 * Supported integral-kHz OSC rate 1..40 MHz. Short periods <=40,000 ticks. */
int lunar_timer_bind(struct lunar_timer *, const struct lunar_timer_io *,
                     unsigned oscillator_hz, unsigned poll_limit);
/* Finite one-shot millisecond periods; no IRQ enable/routing. Zero is a no-op.
 * Max request 1000 ms. Failure stops timer and latches; no implicit retry.
 * Physical duration remains dependent on the caller-verified OSC rate. */
int lunar_timer_delay(struct lunar_timer *, unsigned milliseconds);
#ifdef LUNAR_PI32V2
void lunar_timer_native_io(struct lunar_timer_io *);
#endif
#endif

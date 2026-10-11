/* SPDX-License-Identifier: MIT
 * Independent one-shot timer logic; primary SDK facts in timing/README.md. */
#include "timer4.h"
#define PENDING (1u << 15)
#define CLEAR (1u << 14)
#define OSC_ENABLE 9u /* OSC clock bit 3, run bit 0, prescaler /1. */
static int pending(struct lunar_timer *s, unsigned expected)
{
    unsigned n;
    for (n = 0; n < s->poll_limit; ++n)
        if ((s->io.read(s->io.context, LUNAR_TIMER_CON) & PENDING) == expected)
            return 1;
    return 0;
}
static void control(struct lunar_timer *s, unsigned value)
{
    s->io.write(s->io.context, LUNAR_TIMER_CON, value);
    s->io.sync(s->io.context);
}
int lunar_timer_bind(struct lunar_timer *s, const struct lunar_timer_io *io,
                     unsigned hz, unsigned limit)
{
    if (!s || !io || !io->read || !io->write || !io->sync ||
        hz < 1000000u || hz > 32000000u || hz % 1000u ||
        !limit || limit > 65536u) return 0;
    s->io.context = io->context;
    s->io.read = io->read;
    s->io.write = io->write;
    s->io.sync = io->sync;
    s->ticks_per_ms = hz / 1000u;
    s->poll_limit = limit;
    s->failed = s->active = 0;
    return 1;
}
int lunar_timer_delay(struct lunar_timer *s, unsigned ms)
{
    unsigned i;
    if (!s || !s->ticks_per_ms || s->ticks_per_ms > 32000u ||
        !s->poll_limit || s->poll_limit > 65536u || !s->io.read ||
        !s->io.write || !s->io.sync || s->failed || s->active || ms > 1000u)
        return 0;
    if (!ms) return 1;
    /* Caller owns the timer. Refuse an enabled peripheral without changing it. */
    if (s->io.read(s->io.context, LUNAR_TIMER_CON) & 3u) {
        s->failed = 1;
        return 0;
    }
    s->active = 1;
    for (i = 0; i < ms; ++i) {
        control(s, CLEAR);
        if (!pending(s, 0)) goto failure;
        s->io.write(s->io.context, LUNAR_TIMER_CNT, 0);
        s->io.write(s->io.context, LUNAR_TIMER_PRD, s->ticks_per_ms);
        control(s, OSC_ENABLE);
        if (!pending(s, PENDING)) goto failure;
        control(s, CLEAR);
    }
    control(s, 0);
    s->active = 0;
    return 1;
failure:
    control(s, 0);
    s->failed = 1;
    s->active = 0;
    return 0;
}
#ifdef LUNAR_PI32V2
static unsigned native_read(void *context, enum lunar_timer_register reg)
{
    (void)context;
    if (reg < LUNAR_TIMER_CON || reg > LUNAR_TIMER_PRD) return 0;
    return ((volatile unsigned *)0x10800u)[reg];
}
static void native_write(void *context, enum lunar_timer_register reg, unsigned value)
{
    (void)context;
    if (reg >= LUNAR_TIMER_CON && reg <= LUNAR_TIMER_PRD)
        ((volatile unsigned *)0x10800u)[reg] = value;
}
static void native_sync(void *context)
{
    (void)context;
    __asm__ volatile("csync;" ::: "memory");
}
void lunar_timer_native_io(struct lunar_timer_io *io)
{
    if (!io) return;
    io->context = 0;
    io->read = native_read;
    io->write = native_write;
    io->sync = native_sync;
}
#endif

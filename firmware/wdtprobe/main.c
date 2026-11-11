/* SPDX-License-Identifier: MIT
 * K1-K3 watchdog probe entry for the AC79 dev kit: RAM-only, SDK-free, core 0,
 * interrupts masked. The mode is fixed at build time (LUNAR_WDTPROBE_MODE,
 * 1 read, 2 kick, 3 disarm, 4 mailbox; see wdtprobe.h). Output on UART1 TX,
 * PB3, 1,000,000 baud, as ramtest. Logic: wdtprobe.c.
 */
#include "wdtprobe.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
#ifndef LUNAR_WDTPROBE_MODE
#define LUNAR_WDTPROBE_MODE 1
#endif
/* 150 beats of 150,000 TIMER4 ticks: 15 s at a 24 MHz oscillator, 9 s at
 * 40 MHz; a 4 s watchdog fires long before in READ and MAILBOX mode. */
#define BEATS 150u
#define SPIN_PER_TENTH 1000000u /* uncalibrated, as ramtest */

static const char build_id[] = LUNAR_BUILD_ID;
extern unsigned __bss_begin[], __bss_end[];
extern char _start[], __image_end[];

static unsigned native_read(void *context, unsigned address, unsigned width)
{
    (void)context;
    if (width == 1u) return *(volatile unsigned char *)address;
    if (width == 2u) return *(volatile unsigned short *)address;
    return *(volatile unsigned *)address;
}

static void native_write(void *context, unsigned address, unsigned width, unsigned value)
{
    (void)context;
    if (width == 1u) *(volatile unsigned char *)address = (unsigned char)value;
    else if (width == 2u) *(volatile unsigned short *)address = (unsigned short)value;
    else *(volatile unsigned *)address = value;
}

static void native_sync(void *context)
{
    (void)context;
    __asm__ volatile("csync;" ::: "memory");
}

static void native_pause(void *context, unsigned tenths)
{
    volatile unsigned i;
    (void)context;
    while (tenths--)
        for (i = 0; i < SPIN_PER_TENTH; ++i) {}
}

void lunar_wdtprobe_main(void)
{
    struct lunar_ramtest_io io;
    unsigned core, beat = 0;
    volatile unsigned *word;
    /* The ROM does not clear BSS; volatile keeps this a plain loop. */
    for (word = __bss_begin; word < __bss_end; ++word) *word = 0;
    __asm__ volatile("%0 = cnum;" : "=r"(core));
    if (core != 0) for (;;) {} /* Only core 0 runs this image. */
    io.context = 0;
    io.read = native_read;
    io.write = native_write;
    io.sync = native_sync;
    io.pause = native_pause;
    io.uart_failed = 0;
    lunar_wdtprobe_run(&io, LUNAR_WDTPROBE_MODE, build_id,
                       (unsigned)(__image_end - _start), BEATS);
    for (;;) {
        native_pause(0, 10u);
        lunar_ramtest_puts(&io, "LUNAR_WDTPROBE stuck beat=");
        lunar_ramtest_putu(&io, ++beat);
        lunar_ramtest_puts(&io, "\r\n");
    }
}

/* SPDX-License-Identifier: MIT
 * M4 RAM test image entry for the AC79 dev kit: RAM-only, SDK-free, core 0,
 * interrupts masked. Prints a build id and heartbeats on the debug UART
 * (UART1 TX, PB3, 1,000,000 baud), then clears the UBOOT boot marker and
 * asks P33 for a chip reset so the kit boots its application again. If the
 * reset does not happen it says so and keeps beating. Logic: ramtest.c.
 */
#include "ramtest.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
#define BEATS 10u
/* Uncalibrated: the CPU clock under the mask ROM is not known [inferred:
 * between 24 and 320 MHz], so a tenth is somewhere near 15 to 200 ms. */
#define SPIN_PER_TENTH 1000000u

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

void lunar_ramtest_main(void)
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
    lunar_ramtest_run(&io, build_id, (unsigned)(__image_end - _start), BEATS);
    for (;;) {
        native_pause(0, 10u);
        lunar_ramtest_puts(&io, "LUNAR_RAMTEST stuck beat=");
        lunar_ramtest_putu(&io, ++beat);
        lunar_ramtest_puts(&io, "\r\n");
    }
}

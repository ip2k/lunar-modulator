/* SPDX-License-Identifier: MIT
 * m5-plan-2 entry: RAM-only, SDK-free, core 0, interrupts masked. The logic
 * is in m5p2.c and is the same object in every build; only this file reads
 * the build switches (both off by default):
 *
 *   LUNAR_M5P2_KIT=1      dev-kit build: the FM-1 pins and SPI1 are stubbed
 *                         (the kit's PA0-PA10, PB7 and PC7-PC10 belong to its
 *                         camera, keys and LCD), a UART1 trace on PB3, and a
 *                         P33 soft reset into the kit's application after
 *                         9,000 ms of nominal waits (26.6 s on the kit: the
 *                         waits run 1.67x long at 24 MHz, and cadence B, the
 *                         frame and the trace come on top).
 *   LUNAR_M5P2_MAILBOX=1  write the "usb_update_mode" marker at entry, and
 *                         stop kicking after FINISH_MS so the ROM's watchdog
 *                         resets into UBOOT with the breadcrumbs kept.
 *
 * The FM-1 default (neither switch) kicks and blinks until power-off.
 */
#include "m5p2.h"

#ifndef LUNAR_BUILD_ID
#define LUNAR_BUILD_ID "UNKNOWN"
#endif
#ifndef LUNAR_M5P2_KIT
#define LUNAR_M5P2_KIT 0
#endif
#ifndef LUNAR_M5P2_MAILBOX
#define LUNAR_M5P2_MAILBOX 0
#endif

#if LUNAR_M5P2_KIT
#define FINISH (LUNAR_M5P2_MAILBOX ? LUNAR_M5P2_STOP_KICKING : LUNAR_M5P2_RESET_APP)
#define FINISH_MS 9000u
#define BEATS 20u
#else
#define FINISH (LUNAR_M5P2_MAILBOX ? LUNAR_M5P2_STOP_KICKING : LUNAR_M5P2_FOREVER)
/* Mailbox: 18,000 ms of nominal waits (30 s of waits at 24 MHz plus cadence
 * B and the frame, ~40 s at kit clocks); default: never. */
#define FINISH_MS (LUNAR_M5P2_MAILBOX ? 18000u : 0u)
#define BEATS 0u
#endif

static const char build_id[] = LUNAR_BUILD_ID;
static const struct lunar_m5p2_config config = {
    build_id, LUNAR_M5P2_KIT, LUNAR_M5P2_KIT, LUNAR_M5P2_MAILBOX, FINISH, FINISH_MS, BEATS
};
extern unsigned __bss_begin[], __bss_end[];

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

static void native_spin(void *context, unsigned iterations)
{
    volatile unsigned i;
    (void)context;
    for (i = 0; i < iterations; ++i) {}
}

/* Used only by lunar_ramtest_reset_to_app, after the reset request. */
static void native_pause(void *context, unsigned tenths)
{
    while (tenths--) native_spin(context, 1000000u);
}

void lunar_m5p2_main(void)
{
    struct lunar_m5p2_io io;
    unsigned core;
    volatile unsigned *word;
    /* The ROM does not clear BSS; volatile keeps this a plain loop. */
    for (word = __bss_begin; word < __bss_end; ++word) *word = 0;
    __asm__ volatile("%0 = cnum;" : "=r"(core));
    if (core != 0) for (;;) {} /* Only core 0 runs this image. */
    io.base.context = 0;
    io.base.read = native_read;
    io.base.write = native_write;
    io.base.sync = native_sync;
    io.base.pause = native_pause;
    io.base.uart_failed = 0;
    io.spin = native_spin;
    lunar_m5p2_run(&io, &config);
    /* Reached only after STOP_KICKING (or a failed reset): no more kicks, so
     * an armed watchdog resets the chip. */
    for (;;) {}
}

/* SPDX-License-Identifier: MIT
 * M4 RAM test image for the AC79 dev kit: portable logic. Every register
 * access goes through `struct lunar_ramtest_io`, so the host tests can record
 * and check the exact sequence (tests/test_ramtest_image.py). Register facts
 * and their sources are in ramtest.c.
 */
#ifndef LUNAR_RAMTEST_H
#define LUNAR_RAMTEST_H

struct lunar_ramtest_io {
    void *context;
    /* width is 1, 2 or 4 bytes: the SFR's declared width in WL82.h. */
    unsigned (*read)(void *, unsigned address, unsigned width);
    void (*write)(void *, unsigned address, unsigned width, unsigned value);
    void (*sync)(void *);
    void (*pause)(void *, unsigned tenths); /* coarse, uncalibrated */
    /* Set by the first byte whose TX-pending flag never came; later output
     * is skipped, so a dead UART costs one timeout and the reset still runs. */
    unsigned uart_failed;
};

enum lunar_ramtest_result {
    LUNAR_RAMTEST_RESET_REQUESTED = 0, /* never seen on hardware: it resets */
    LUNAR_RAMTEST_FAIL_ARGS,
    LUNAR_RAMTEST_FAIL_MARKER,      /* boot marker did not read back cleared */
    LUNAR_RAMTEST_FAIL_P33_BUSY,    /* P33 bus busy before or during a byte */
    LUNAR_RAMTEST_FAIL_NO_RESET     /* the write went out but nothing reset */
};

#define LUNAR_RAMTEST_UART_CLOCK 48000000u
#define LUNAR_RAMTEST_UART_BAUD 1000000u
#define LUNAR_RAMTEST_BOOT_MARKER 0x01c7fd80u
#define LUNAR_RAMTEST_POLLS 200000u

/* SDK uart_init's divisor choice: returns the BAUD register value and sets
 * *by3 to 1 when CON0 bit 4 (divide by 3) is used. 0 on invalid input. */
unsigned lunar_ramtest_baud(unsigned clock_hz, unsigned baud, unsigned *by3);
/* UART1 TX only, on PB3 through output channel 0, 1,000,000 baud. */
int lunar_ramtest_uart_init(const struct lunar_ramtest_io *io);
/* Bounded wait for the TX-pending flag; 0 (and uart_failed set) if it never
 * came, or if an earlier byte already failed. */
int lunar_ramtest_putc(struct lunar_ramtest_io *io, char c);
void lunar_ramtest_puts(struct lunar_ramtest_io *io, const char *s);
void lunar_ramtest_putu(struct lunar_ramtest_io *io, unsigned value);
/* Clear the 16-byte "usb_update_mode" boot marker, then the SDK's
 * __cpu_reset sequence on P33 (read P3_PR_PWR 0xa0, write it back with bit
 * 4). Only returns on failure, or on the host where nothing resets. */
enum lunar_ramtest_result lunar_ramtest_reset_to_app(const struct lunar_ramtest_io *io);
/* Banner, `beats` heartbeats, reset line, reset. Returns only on failure. */
enum lunar_ramtest_result lunar_ramtest_run(struct lunar_ramtest_io *io,
                                            const char *build_id, unsigned image_bytes,
                                            unsigned beats);
#endif

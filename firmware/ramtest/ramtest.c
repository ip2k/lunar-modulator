/* SPDX-License-Identifier: MIT
 * M4 RAM test image, portable logic. Independently written; the P33 byte
 * transfer follows the shape of Codex's MIT firmware/recovery/request.c
 * (installable-firmware branch), with the reset itself taken from the SDK's
 * own __cpu_reset instead of that file's OR operation.
 *
 * Register facts (addresses from WL82.h of the pinned AC79 SDK [verified]):
 *   UART1 0x12100: CON0 u16 +0, CON1 u16 +4, BAUD u16 +8, BUF u8 +0xc.
 *   CLK_CON1 0x10010: [11:10] = 1 clocks the UARTs from PLL 48 MHz [reported:
 *     Felucca; also firmware/board/midi_uart.c].
 *   IOMAP 0x5101c: CON1 +4 [11:8] picks output channel 0's signal, 1 = UT1
 *     TX; CON3 +0xc bit 7 = 0 sends UART1 through the channels [verified: SDK
 *     cpu.a uart.c.o uart_set_port_map and gpio.c.o gpio_output_channle].
 *   PORTB 0x50040: OUT +0, DIR +8, DIE +0xc, PU +0x10, PD +0x14. A pin
 *     carries output channel 0 with PU = PD = 1, DIR = 0, OUT = 0, DIE = 0
 *     [verified: gpio_output_channle; SDK sdram_re_trim.c putbyte_init].
 *   Baud: div = clock / baud; div % 4 >= div % 3 sets CON0 bit 4 and
 *     BAUD = div / 3 - 1, otherwise BAUD = div / 4 - 1; then CON0 |= 1
 *     [verified: uart_init]. TX: CON0 |= bit 13 (clear pending), BUF = c,
 *     csync, wait for bit 15 [verified: uart_putbyte].
 *   P33 0x13e00: CON +8 (bit 0 select, bit 1 busy, bit 4 start, bit 8 RTC),
 *     DAT +0xc. __cpu_reset: select (clear bit 8, set bit 0), bytes 0x80,
 *     0xa0, 0x5e read P3_PR_PWR; deselect; select; bytes 0x00, 0xa0,
 *     value | 0x10 write it with the chip-reset bit; deselect [verified: SDK
 *     cpu.a p33.c.o __cpu_reset and p33_buf].
 *   Boot marker: nvram_set_boot_state copies 16 bytes to 0x01c7fd80 and
 *     resets [verified: SDK cpu.a usb.c.o]; the string is "usb_update_mode"
 *     [reported: Codex request.c]. The dev kit's boot control enters UBOOT
 *     through it (firmware/devkit/boot_control.c), so it is cleared before
 *     the reset to land in the application [inferred: that the ROM or SPL
 *     reads it there and has not already cleared it].
 */
#include "ramtest.h"

#define UART1_CON0 0x12100u
#define UART1_CON1 0x12104u
#define UART1_BAUD 0x12108u
#define UART1_BUF 0x1210cu
#define CLK_CON1 0x10010u
#define IOMAP_CON1 0x51020u
#define IOMAP_CON3 0x51028u
#define PORTB_OUT 0x50040u
#define PORTB_DIR 0x50048u
#define PORTB_DIE 0x5004cu
#define PORTB_PU 0x50050u
#define PORTB_PD 0x50054u
#define PB3 (1u << 3)
#define P33_CON 0x13e08u
#define P33_DAT 0x13e0cu
#define P33_SELECT 0x001u
#define P33_BUSY 0x002u
#define P33_START 0x010u
#define P33_RTC 0x100u
#define P3_PR_PWR 0xa0u
#define P3_CHIP_RESET 0x10u

static void change(const struct lunar_ramtest_io *io, unsigned address, unsigned width,
                   unsigned clear, unsigned set)
{
    io->write(io->context, address, width,
              (io->read(io->context, address, width) & ~clear) | set);
}

unsigned lunar_ramtest_baud(unsigned clock_hz, unsigned baud, unsigned *by3)
{
    unsigned div, value;
    if (!by3 || !baud || clock_hz < baud) return 0;
    div = clock_hz / baud;
    *by3 = (div % 4u) >= (div % 3u);
    value = div / (*by3 ? 3u : 4u);
    if (!value || value - 1u > 0xffffu) return 0;
    return value - 1u;
}

int lunar_ramtest_uart_init(const struct lunar_ramtest_io *io)
{
    unsigned by3, baud;
    if (!io || !io->read || !io->write || !io->sync) return 0;
    baud = lunar_ramtest_baud(LUNAR_RAMTEST_UART_CLOCK, LUNAR_RAMTEST_UART_BAUD, &by3);
    if (!baud) return 0;
    io->write(io->context, UART1_CON0, 2, 0);
    io->write(io->context, UART1_CON1, 2, 0);
    change(io, CLK_CON1, 4, 3u << 10, 1u << 10);
    change(io, IOMAP_CON3, 4, 1u << 7, 0);
    change(io, IOMAP_CON1, 4, 0xfu << 8, 1u << 8);
    change(io, PORTB_PU, 4, 0, PB3);
    change(io, PORTB_PD, 4, 0, PB3);
    change(io, PORTB_OUT, 4, PB3, 0);
    change(io, PORTB_DIR, 4, PB3, 0);
    change(io, PORTB_DIE, 4, PB3, 0);
    io->write(io->context, UART1_CON0, 2, by3 ? 0x10u : 0);
    io->write(io->context, UART1_BAUD, 2, baud);
    change(io, UART1_CON0, 2, 0, 1u);
    io->sync(io->context);
    return 1;
}

int lunar_ramtest_putc(const struct lunar_ramtest_io *io, char c)
{
    unsigned n;
    change(io, UART1_CON0, 2, 0, 1u << 13);
    io->write(io->context, UART1_BUF, 1, (unsigned char)c);
    io->sync(io->context);
    for (n = 0; n < LUNAR_RAMTEST_POLLS; ++n)
        if (io->read(io->context, UART1_CON0, 2) & (1u << 15)) return 1;
    return 0;
}

void lunar_ramtest_puts(const struct lunar_ramtest_io *io, const char *s)
{
    while (*s) lunar_ramtest_putc(io, *s++);
}

void lunar_ramtest_putu(const struct lunar_ramtest_io *io, unsigned value)
{
    char digits[10];
    unsigned n = 0;
    do {
        digits[n++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value && n < sizeof digits);
    while (n) lunar_ramtest_putc(io, digits[--n]);
}

static int p33_idle(const struct lunar_ramtest_io *io)
{
    unsigned n;
    for (n = 0; n < LUNAR_RAMTEST_POLLS; ++n)
        if (!(io->read(io->context, P33_CON, 4) & P33_BUSY)) return 1;
    return 0;
}

/* One byte each way, as p33_buf: DAT, start, csync, wait, read DAT. */
static int p33_byte(const struct lunar_ramtest_io *io, unsigned out, unsigned *in)
{
    io->write(io->context, P33_DAT, 4, out);
    change(io, P33_CON, 4, 0, P33_START);
    io->sync(io->context);
    if (!p33_idle(io)) return 0;
    *in = io->read(io->context, P33_DAT, 4) & 0xffu;
    return 1;
}

static void p33_select(const struct lunar_ramtest_io *io)
{
    change(io, P33_CON, 4, P33_RTC, P33_SELECT);
}

static void p33_deselect(const struct lunar_ramtest_io *io)
{
    change(io, P33_CON, 4, P33_SELECT | P33_RTC, 0);
}

enum lunar_ramtest_result lunar_ramtest_reset_to_app(const struct lunar_ramtest_io *io)
{
    unsigned i, ignored, value;
    if (!io || !io->read || !io->write || !io->sync) return LUNAR_RAMTEST_FAIL_ARGS;
    for (i = 0; i < 16u; i += 4u)
        io->write(io->context, LUNAR_RAMTEST_BOOT_MARKER + i, 4, 0);
    io->sync(io->context);
    for (i = 0; i < 16u; i += 4u)
        if (io->read(io->context, LUNAR_RAMTEST_BOOT_MARKER + i, 4))
            return LUNAR_RAMTEST_FAIL_MARKER;
    if (!p33_idle(io)) return LUNAR_RAMTEST_FAIL_P33_BUSY;
    p33_select(io);
    if (!p33_byte(io, 0x80u | ((P3_PR_PWR >> 8) & 3u), &ignored) ||
        !p33_byte(io, P3_PR_PWR & 0xffu, &ignored) ||
        !p33_byte(io, 0x5eu, &value)) {
        p33_deselect(io);
        return LUNAR_RAMTEST_FAIL_P33_BUSY;
    }
    p33_deselect(io);
    p33_select(io);
    if (!p33_byte(io, 0x00u | ((P3_PR_PWR >> 8) & 3u), &ignored) ||
        !p33_byte(io, P3_PR_PWR & 0xffu, &ignored) ||
        !p33_byte(io, value | P3_CHIP_RESET, &ignored)) {
        p33_deselect(io);
        return LUNAR_RAMTEST_FAIL_P33_BUSY;
    }
    p33_deselect(io);
    io->sync(io->context);
    /* The chip resets here on hardware. Give it time before giving up. */
    if (io->pause) io->pause(io->context, 10u);
    return LUNAR_RAMTEST_FAIL_NO_RESET;
}

static const char *const failures[] = {
    "none", "args", "marker", "p33_busy", "no_reset"
};

enum lunar_ramtest_result lunar_ramtest_run(const struct lunar_ramtest_io *io,
                                            const char *build_id, unsigned image_bytes,
                                            unsigned beats)
{
    unsigned beat;
    enum lunar_ramtest_result result;
    if (!io || !io->pause || !build_id || !lunar_ramtest_uart_init(io))
        return LUNAR_RAMTEST_FAIL_ARGS;
    lunar_ramtest_puts(io, "\r\nLUNAR_RAMTEST ready=1 build=");
    lunar_ramtest_puts(io, build_id);
    lunar_ramtest_puts(io, " entry=0x01c02000 bytes=");
    lunar_ramtest_putu(io, image_bytes);
    lunar_ramtest_puts(io, " uart=uart1-pb3-1000000\r\n");
    for (beat = 1; beat <= beats; ++beat) {
        io->pause(io->context, 1u);
        lunar_ramtest_puts(io, "LUNAR_RAMTEST beat=");
        lunar_ramtest_putu(io, beat);
        lunar_ramtest_puts(io, "\r\n");
    }
    lunar_ramtest_puts(io, "LUNAR_RAMTEST reset=app\r\n");
    io->pause(io->context, 1u); /* let the last byte leave the shifter */
    result = lunar_ramtest_reset_to_app(io);
    lunar_ramtest_puts(io, "LUNAR_RAMTEST reset_failed=");
    lunar_ramtest_puts(io, failures[result < 5u ? result : 1u]);
    lunar_ramtest_puts(io, "\r\n");
    return result;
}

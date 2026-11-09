/* SPDX-License-Identifier: MIT
 * Independently authored from register/pin facts, not a copied vendor driver.
 */
#include "spi1_transport.h"
typedef char lunar_register_width_must_be_32_bits[sizeof(unsigned) == 4 ? 1 : -1];
#define CS (1u << 7)
#define DC (1u << 8)
#define PINS (CS | DC | (1u << 9) | (1u << 10))
#define CLEAR_PENDING (1u << 14)
#define PENDING (1u << 15)
#define CONFIG 0x4021u

static void change(struct lunar_spi1 *s, enum lunar_spi1_register reg,
                   unsigned clear, unsigned set)
{
    unsigned value = s->io.read(s->io.context, reg);
    s->io.write(s->io.context, reg, (value & ~clear) | set);
}
static void abort_transfer(struct lunar_spi1 *s)
{
    /* Stop SPI before releasing CS: no later byte may escape this transaction.
     * A failed transport stays failed until explicitly rebound/reconfigured. */
    s->io.write(s->io.context, LUNAR_SPI1_CON, CONFIG & ~1u);
    change(s, LUNAR_PANEL_PORTC_OUT, 0, CS);
    s->active = 0;
    s->failed = 1;
}
static int byte(struct lunar_spi1 *s, unsigned char value)
{
    unsigned i;
    s->io.write(s->io.context, LUNAR_SPI1_CON, CONFIG | CLEAR_PENDING);
    /* Reject a stale/stuck completion flag rather than mistaking it for the
     * new byte. Each phase has its own finite register-read budget. */
    for (i = 0; i < s->poll_limit; ++i)
        if (!(s->io.read(s->io.context, LUNAR_SPI1_CON) & PENDING)) break;
    if (i == s->poll_limit) { abort_transfer(s); return 0; }
    s->io.write(s->io.context, LUNAR_SPI1_BUF, value);
    for (i = 0; i < s->poll_limit; ++i) {
        if (s->io.read(s->io.context, LUNAR_SPI1_CON) & PENDING) {
            s->io.write(s->io.context, LUNAR_SPI1_CON, CONFIG | CLEAR_PENDING);
            return 1;
        }
    }
    abort_transfer(s);
    return 0;
}
static int begin(void *context, unsigned char command)
{
    struct lunar_spi1 *s = context;
    if (!s->configured || s->failed) return 0;
    if (s->active) { abort_transfer(s); return 0; }
    change(s, LUNAR_PANEL_PORTC_OUT, DC, CS);
    change(s, LUNAR_PANEL_PORTC_OUT, CS, 0);
    s->active = 1;
    if (!byte(s, command)) return 0;
    change(s, LUNAR_PANEL_PORTC_OUT, 0, DC);
    return 1;
}
static int write_data(void *context, unsigned char value)
{
    struct lunar_spi1 *s = context;
    if (!s->configured || !s->active || s->failed) return 0;
    return byte(s, value);
}
static void end(void *context)
{
    struct lunar_spi1 *s = context;
    if (s->active) {
        change(s, LUNAR_PANEL_PORTC_OUT, 0, CS);
        s->active = 0;
    }
}
static int wait_ms(void *context, unsigned milliseconds)
{
    struct lunar_spi1 *s = context;
    if (!s->configured || s->failed || s->active) return 0;
    if (!s->io.wait_ms(s->io.context, milliseconds)) {
        abort_transfer(s);
        return 0;
    }
    return 1;
}
int lunar_spi1_bind(struct lunar_spi1 *s, const struct lunar_spi1_io *io,
                   unsigned polls, struct lunar_panel_transport *bus)
{
    if (!s || !io || !bus || !io->read || !io->write || !io->wait_ms ||
        !polls || polls > 65536u) return 0;
    /* JieLi lowers whole-structure assignment to an external memcpy even
     * with -fno-builtin. Keep this SDK-free object self-contained. */
    s->io.context = io->context;
    s->io.read = io->read;
    s->io.write = io->write;
    s->io.wait_ms = io->wait_ms;
    s->poll_limit = polls;
    s->configured = s->active = s->failed = 0;
    bus->context = s;
    bus->begin = begin;
    bus->write = write_data;
    bus->end = end;
    bus->wait_ms = wait_ms;
    return 1;
}
int lunar_spi1_configure(struct lunar_spi1 *s)
{
    if (!s || !s->io.read || !s->io.write || !s->io.wait_ms ||
        !s->poll_limit || s->poll_limit > 65536u || s->configured) return 0;
    /* Establish inactive levels before changing direction. Preserve other pins.
     * Port B selects PC9 clock/PC10 output; PC8 is GPIO D/C in TX-only mode. */
    change(s, LUNAR_PANEL_PORTC_OUT, DC, CS);
    change(s, LUNAR_PANEL_PORTC_DIR, PINS, 0);
    change(s, LUNAR_PANEL_IOMAP_CON1, 0, 1u << 4);
    s->io.write(s->io.context, LUNAR_SPI1_CON, CONFIG);
    s->io.write(s->io.context, LUNAR_SPI1_BAUD, 4);
    s->configured = 1;
    return 1;
}
static volatile unsigned *register_address(enum lunar_spi1_register reg)
{
    switch (reg) {
    case LUNAR_SPI1_CON: return (volatile unsigned *)0x11d00u;
    case LUNAR_SPI1_BAUD: return (volatile unsigned *)0x11d04u;
    case LUNAR_SPI1_BUF: return (volatile unsigned *)0x11d08u;
    case LUNAR_PANEL_PORTC_OUT: return (volatile unsigned *)0x50080u;
    case LUNAR_PANEL_PORTC_DIR: return (volatile unsigned *)0x50088u;
    case LUNAR_PANEL_IOMAP_CON1: return (volatile unsigned *)0x51020u;
    }
    return 0;
}
static unsigned native_read(void *context, enum lunar_spi1_register reg)
{
    volatile unsigned *address = register_address(reg);
    (void)context;
    return address ? *address : 0;
}
static void native_write(void *context, enum lunar_spi1_register reg, unsigned value)
{
    volatile unsigned *address = register_address(reg);
    (void)context;
    if (address) *address = value;
}
void lunar_spi1_native_io(struct lunar_spi1_io *io, void *context,
                         int (*delay)(void *, unsigned))
{
    if (!io) return;
    io->context = context;
    io->read = native_read;
    io->write = native_write;
    io->wait_ms = delay;
}

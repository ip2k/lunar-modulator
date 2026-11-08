/* SPDX-License-Identifier: MIT
 * Independently authored. UART1 facts [reported: Felucca hal, facts only;
 * register offsets verified against pinned WL82.h]: CON0 0x3400 stops the
 * port and clears its pendings; UART clock source CLK_CON1[11:10] = 1 (PLL
 * 48 MHz); IOMAP CON3[7] = 0 and [6:4] = 5 route input channel 1 to UT1 RX;
 * IOMAP CON2[13:8] = 49 selects PH8 for input channel 1; BAUD = 48 MHz /
 * 31,250 / 4 - 1 = 383; OTCNT 60000; CON0 bits 6 (RX DMA), 7 (latch count),
 * 10 and 12 (clear pendings), then bit 0 (enable).
 * lunar_midi_uart_drain is adapted from Codex's MIT midi_uart_stream.c
 * (installable-firmware branch, 66196f54): a power-of-two mask replaces the
 * 64-bit modulo so the pi32v2 link needs no division helper, and the parser
 * state lives in the caller's struct rather than a global.
 */
#include "midi_uart.h"

#define CON0_ENABLE 0x0001u
#define CON0_RX_DMA 0x0040u
#define CON0_LATCH 0x0080u
#define CON0_CLEAR 0x1400u
#define CON0_STOPPED 0x3400u
#define PH(field) ((enum lunar_board_register)(LUNAR_PH + (field)))
#define PH8 (1u << 8)

int lunar_midi_uart_drain(struct lunar_midi_uart *s, unsigned newly_received,
                          unsigned byte_budget, lunar_midi_emit_fn emit, void *ctx)
{
    unsigned consumed = 0, mask;
    if (!s || !s->ring || !emit || !s->ring_bytes ||
        (s->ring_bytes & (s->ring_bytes - 1u)) ||
        s->cursor >= s->ring_bytes || s->pending > s->ring_bytes)
        return -1;
    mask = s->ring_bytes - 1u;
    if (newly_received > s->ring_bytes || s->pending > s->ring_bytes - newly_received) {
        /* The DMA lapped the reader: skip everything written so far. */
        s->cursor = (s->cursor + s->pending + (newly_received & mask)) & mask;
        s->pending = 0;
        ++s->overruns;
        lunar_midi_parser_reset(&s->parser);
        return -1;
    }
    s->pending += newly_received;
    while (s->pending && consumed < byte_budget) {
        struct lunar_midi_message message;
        unsigned char byte = s->ring[s->cursor];
        s->cursor = (s->cursor + 1u) & mask;
        --s->pending;
        ++consumed;
        if (lunar_midi_parse(&s->parser, byte, &message)) emit(ctx, &message);
    }
    return (int)consumed;
}

int lunar_midi_uart_configure(struct lunar_midi_uart *s, const struct lunar_board_io *io,
                              const volatile unsigned char *ring, unsigned ring_bytes,
                              unsigned address)
{
    if (!s || !lunar_board_io_valid(io) || !ring || ring_bytes < 16u ||
        ring_bytes > 4096u || (ring_bytes & (ring_bytes - 1u)) || (address & 15u) ||
        address > 0xffffffffu - ring_bytes)
        return 0;
    s->io = io;
    s->ring = ring;
    s->ring_bytes = ring_bytes;
    s->cursor = s->pending = s->overruns = s->configured = 0;
    lunar_midi_parser_reset(&s->parser);
    if (io->read(io->context, LUNAR_UART1_CON0) & CON0_ENABLE) return 0;
    io->write(io->context, LUNAR_UART1_CON0, CON0_STOPPED);
    io->write(io->context, LUNAR_UART1_CON1, 0);
    lunar_board_change(io, LUNAR_CLOCK_CON1, 3u << 10, 1u << 10);
    lunar_board_change(io, LUNAR_IOMAP_CON3, 0xf0u, 5u << 4);
    lunar_board_change(io, LUNAR_IOMAP_CON2, 0x3fu << 8, 49u << 8);
    lunar_board_change(io, PH(LUNAR_PD), PH8, 0);
    lunar_board_change(io, PH(LUNAR_DIE), 0, PH8);
    lunar_board_change(io, PH(LUNAR_DIR), 0, PH8);
    lunar_board_change(io, PH(LUNAR_PU), 0, PH8);
    io->write(io->context, LUNAR_UART1_RXSADR, address);
    io->write(io->context, LUNAR_UART1_RXEADR, address + ring_bytes);
    io->write(io->context, LUNAR_UART1_RXCNT, ring_bytes);
    io->write(io->context, LUNAR_UART1_BAUD, 383);
    io->write(io->context, LUNAR_UART1_OTCNT, 60000);
    io->sync(io->context);
    io->write(io->context, LUNAR_UART1_CON0, CON0_RX_DMA | CON0_LATCH | CON0_CLEAR);
    io->sync(io->context);
    lunar_board_change(io, LUNAR_UART1_CON0, 0, CON0_ENABLE);
    s->configured = 1;
    return 1;
}

int lunar_midi_uart_poll(struct lunar_midi_uart *s, unsigned byte_budget,
                         lunar_midi_emit_fn emit, void *ctx)
{
    unsigned received;
    if (!s || !s->configured) return -1;
    lunar_board_change(s->io, LUNAR_UART1_CON0, 0, CON0_LATCH);
    s->io->sync(s->io->context);
    lunar_board_change(s->io, LUNAR_UART1_CON0, 0, CON0_CLEAR);
    received = s->io->read(s->io->context, LUNAR_UART1_HRXCNT) & 0xffffu;
    return lunar_midi_uart_drain(s, received, byte_budget, emit, ctx);
}

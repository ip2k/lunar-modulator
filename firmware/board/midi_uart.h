/* SPDX-License-Identifier: MIT
 * Independently authored UART1 receive path for the TRS MIDI input (PH8).
 * Register facts are listed with their sources in firmware/board/README.md;
 * no GPL code was copied.
 */
#ifndef LUNAR_MIDI_UART_H
#define LUNAR_MIDI_UART_H
#include "board_io.h"
#include "midi_parser.h"

typedef void (*lunar_midi_emit_fn)(void *ctx, const struct lunar_midi_message *message);

struct lunar_midi_uart {
    const struct lunar_board_io *io;
    const volatile unsigned char *ring;
    unsigned ring_bytes, cursor, pending, overruns, configured;
    struct lunar_midi_parser parser;
};

/* Consume a DMA ring snapshot (adapted from Codex's MIT
 * firmware/native/midi_uart_stream.c at 66196f54). ring_bytes must be a power
 * of two. Returns bytes consumed, or -1 after an overrun: the backlog is
 * skipped and the parser reset, so a torn message is never emitted. */
int lunar_midi_uart_drain(struct lunar_midi_uart *s, unsigned newly_received,
                          unsigned byte_budget, lunar_midi_emit_fn emit, void *ctx);

/* Configure UART1 RX DMA at 31,250 baud from the 48 MHz PLL clock into
 * `ring` (DMA address `ring_address`, 16-byte aligned, power-of-two length
 * 16..4096). Refuses a UART1 that is already enabled. Receive only: no TX
 * pin is mapped and nothing is ever transmitted. */
int lunar_midi_uart_configure(struct lunar_midi_uart *s, const struct lunar_board_io *io,
                              const volatile unsigned char *ring, unsigned ring_bytes,
                              unsigned ring_address);

/* Latch the DMA count, then drain at most byte_budget bytes. */
int lunar_midi_uart_poll(struct lunar_midi_uart *s, unsigned byte_budget,
                         lunar_midi_emit_fn emit, void *ctx);
#endif

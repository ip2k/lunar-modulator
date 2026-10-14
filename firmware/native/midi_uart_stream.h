/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_MIDI_UART_STREAM_H
#define LUNAR_MIDI_UART_STREAM_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef void (*lunar_midi_uart_event_fn)(void *ctx, uint8_t status,
                                         uint8_t data1, uint8_t data2);
/* Consume a DMA ring snapshot. Returns bytes consumed, or -1 after discarding
 * an overrun and resetting the parser. All indices/counts are caller-owned. */
int lunar_midi_uart_drain(const volatile uint8_t *ring, uint32_t ring_bytes,
                          uint32_t *cursor, uint32_t *pending,
                          uint32_t newly_received, uint32_t byte_budget,
                          lunar_midi_uart_event_fn emit, void *ctx);
#ifdef __cplusplus
}
#endif
#endif

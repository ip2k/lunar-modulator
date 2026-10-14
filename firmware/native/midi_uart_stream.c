/* SPDX-License-Identifier: MIT */
#include "midi_uart_stream.h"
#include "midi_stream.h"

int lunar_midi_uart_drain(const volatile uint8_t *ring, uint32_t ring_bytes,
                          uint32_t *cursor, uint32_t *pending,
                          uint32_t newly_received, uint32_t byte_budget,
                          lunar_midi_uart_event_fn emit, void *ctx)
{
    uint32_t consumed = 0;
    if (!ring || !ring_bytes || !cursor || !pending || !emit ||
        *cursor >= ring_bytes || *pending > ring_bytes)
        return -1;
    if (newly_received > ring_bytes || *pending > ring_bytes - newly_received) {
        *cursor = (uint32_t)(((uint64_t)*cursor + newly_received) % ring_bytes);
        *pending = 0;
        lunar_midi_stream_reset();
        return -1;
    }
    *pending += newly_received;
    while (*pending && consumed < byte_budget) {
        uint8_t status, a, b;
        uint8_t byte = ring[*cursor];
        *cursor = (*cursor + 1u) % ring_bytes;
        --*pending;
        ++consumed;
        if (lunar_midi_stream_feed(byte, &status, &a, &b))
            emit(ctx, status, a, b);
    }
    return (int)consumed;
}

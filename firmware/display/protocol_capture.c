/* SPDX-License-Identifier: MIT */
#include "protocol_capture.h"
#include "panel_probe.h"

/* FNV-1a over tagged events: B, command; W, byte; E; T, u32 little endian.
 * Unsigned 32-bit wrap is intentional. No unbounded trace buffer is needed. */
static void hash_byte(volatile struct lunar_panel_capture *s, unsigned char b)
{
    s->hash = (s->hash ^ b) * 16777619u;
}
static int begin(void *context, unsigned char command)
{
    volatile struct lunar_panel_capture *s = context;
    if (s->active || s->commands >= 22u) {
        s->protocol_error = 1;
        return 0;
    }
    s->active = 1;
    ++s->commands;
    hash_byte(s, 'B');
    hash_byte(s, command);
    return 1;
}
static int write_byte(void *context, unsigned char data)
{
    volatile struct lunar_panel_capture *s = context;
    if (!s->active || s->data_bytes >= 115254u) {
        s->protocol_error = 1;
        return 0;
    }
    ++s->data_bytes;
    hash_byte(s, 'W');
    hash_byte(s, data);
    return 1;
}
static void end(void *context)
{
    volatile struct lunar_panel_capture *s = context;
    if (!s->active || s->ends >= 22u) s->protocol_error = 1;
    s->active = 0;
    if (s->ends < 22u) ++s->ends;
    hash_byte(s, 'E');
}
static int record_wait(void *context, unsigned milliseconds)
{
    volatile struct lunar_panel_capture *s = context;
    unsigned i;
    if (s->active || s->wait_calls >= 2u || milliseconds > 220u ||
        s->requested_wait_ms > 220u - milliseconds) {
        s->protocol_error = 1;
        return 0;
    }
    ++s->wait_calls;
    s->requested_wait_ms += milliseconds;
    hash_byte(s, 'T');
    for (i = 0; i < 4; ++i) hash_byte(s, (unsigned char)(milliseconds >> (8u * i)));
    return 1;
}
void lunar_panel_capture_run(volatile struct lunar_panel_capture *s)
{
    const struct lunar_panel_transport transport = {
        (void *)s, begin, write_byte, end, record_wait
    };
    s->magic = 0x4c504354u; /* LPCT */
    s->version = 1;
    s->result = 0xffffffffu; /* Pending: no observation mechanism is provided. */
    s->commands = s->data_bytes = s->ends = 0;
    s->wait_calls = s->requested_wait_ms = 0;
    s->hash = 2166136261u;
    s->active = s->protocol_error = 0;
    s->result = (diag_u32)lunar_panel_probe(&transport);
}

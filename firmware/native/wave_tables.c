/* SPDX-License-Identifier: MIT */
#include <stddef.h>
#include <stdint.h>
#include "tinf.h"

typedef struct {
    unsigned char *output;
    unsigned output_bytes;
    const unsigned char *packed;
    unsigned packed_bytes;
    unsigned width;
    uint32_t fnv32;
} lunar_wave_table_t;
#include "wave_tables.inc"

/* One bounded table, also exercised with damaged inputs by the host checks. */
static int lunar_wave_table_decode(const lunar_wave_table_t *table)
{
    if (!table->output || !table->packed || !table->output_bytes ||
        (table->width != 1 && table->width != 2) ||
        table->output_bytes % table->width) return -1;
    unsigned bytes = table->output_bytes;
    if (tinf_uncompress(table->output, &bytes, table->packed, table->packed_bytes) ||
        bytes != table->output_bytes) return -1;
    uint16_t value = 0;
    uint32_t hash = 2166136261u;
    for (unsigned n = 0; n < bytes; n += table->width) {
        unsigned char *p = table->output + n;
        value = (uint16_t)(value + p[0] + (table->width == 2 ? (unsigned)p[1] * 256u : 0u));
        p[0] = (unsigned char)value;
        hash = (hash ^ p[0]) * 16777619u;
        if (table->width == 2) {
            p[1] = (unsigned char)(value >> 8);
            hash = (hash ^ p[1]) * 16777619u;
        }
    }
    if (hash != table->fnv32) return -1;
    return 0;
}

/* Startup only, before any engine holds a pointer. Never runs in rendering.
 * Failure leaves the image inadmissible for audio/engine startup. */
int lunar_wave_tables_init(void)
{
    for (size_t i = 0; i < sizeof lunar_wave_tables / sizeof lunar_wave_tables[0]; ++i)
        if (lunar_wave_table_decode(&lunar_wave_tables[i])) return -1;
    return 0;
}

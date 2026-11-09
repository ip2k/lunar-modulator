/* SPDX-License-Identifier: Apache-2.0
 * Copyright Keitark (fm1-nes); adapted by Lunar Modulator, 2026-11-08.
 * Upstream 870f3054869c77f03fc1c8a3a425dafa3dfa7b22:
 *   firmware/nes/src/fm1_stock_keys.c   (cell table, column pack, decode)
 *   firmware/usb-diag/peripheral_logic.c (encoder contacts, names, sampler)
 * fm1-nes recovered both tables from stock FM-1_010 (runtime 0x02046334 and
 * XIP 0x020462fc) and named the encoders by one-at-a-time physical tests.
 * Changes (UPSTREAM.md): cells re-indexed from fm1-nes's scan-phase labels to
 * physical 595 columns, col = (label + 10) % 11, which agrees 41/41 with an
 * independent second source; 64-bit key mask replaced by two 32-bit words;
 * NULL guards; stdint/string.h dropped for the SDK-free pi32v2 link.
 */
#include "fm1_keys.h"

static const unsigned char key_cells[LUNAR_KEY_COUNT] = {
    0x04, 0x14, 0x61, 0x41, 0x21, 0x01, 0x92, 0x82, 0x71, 0x51, 0x31, 0x11,
    0xa2, 0x72, 0x34, 0x24, 0x54, 0x44, 0x74, 0x64, 0x84, 0x94, 0xa4, 0x03,
    0x13, 0x23, 0x33, 0x43, 0x53, 0x63, 0x73, 0x83, 0x93, 0xa3, 0x02, 0x12,
    0x22, 0x32, 0x42, 0x62, 0x52
};
/* A then B contact per encoder, physical column << 4 | row bit. */
static const unsigned char encoder_contacts[2 * LUNAR_ENCODER_COUNT] = {
    0x00, 0x10, 0x20, 0x30, 0x81, 0x91, 0x80, 0x90, 0x60, 0x70, 0x40, 0x50,
    0x05, 0x15
};
const char *const lunar_encoder_names[LUNAR_ENCODER_COUNT] = {
    "SELECT", "ALGORITHM", "KNOB1", "KNOB2", "KNOB3", "KNOB4", "PRESETS"
};

unsigned lunar_keys_pack(unsigned a, unsigned b)
{
    return (a & 1u) | ((a >> 4) & 0x1eu) | ((b >> 2) & 0x20u);
}

static unsigned closed(const unsigned char *rows, unsigned cell)
{
    return !(rows[cell >> 4] & (1u << (cell & 15u)));
}

unsigned lunar_key_cell(unsigned id)
{
    return id < LUNAR_KEY_COUNT ? key_cells[id] : 0xffu;
}

void lunar_keys_decode(const unsigned char rows[LUNAR_MATRIX_COLUMNS], unsigned pressed[2])
{
    unsigned i;
    if (!pressed) return;
    pressed[0] = pressed[1] = 0;
    if (!rows) return;
    for (i = 0; i < LUNAR_KEY_COUNT; ++i)
        if (closed(rows, key_cells[i])) pressed[i >> 5] |= 1u << (i & 31u);
}

void lunar_encoders_reset(struct lunar_encoders *s)
{
    unsigned i;
    if (!s) return;
    for (i = 0; i < LUNAR_ENCODER_COUNT; ++i) {
        s->previous[i] = s->candidate[i] = 0;
        s->count[i] = 0;
        s->invalid[i] = 0;
    }
    s->valid = 0;
}

void lunar_encoders_sample(struct lunar_encoders *s, const unsigned char rows[LUNAR_MATRIX_COLUMNS])
{
    unsigned i;
    if (!s || !rows) return;
    for (i = 0; i < LUNAR_ENCODER_COUNT; ++i) {
        unsigned value = closed(rows, encoder_contacts[2 * i]) |
                         (closed(rows, encoder_contacts[2 * i + 1]) << 1);
        unsigned transition = ((unsigned)s->previous[i] << 2) | value;
        /* Stock: a first differing sample only updates the candidate; decode
         * on its next identical scan. No guessed missing edges. */
        if (!s->valid) {
            s->previous[i] = s->candidate[i] = (unsigned char)value;
            continue;
        }
        if (value != s->candidate[i]) {
            s->candidate[i] = (unsigned char)value;
            continue;
        }
        if (value != s->previous[i]) {
            if ((value ^ s->previous[i]) == 3u) ++s->invalid[i];
            else if ((0x2814u >> transition) & 1u) { if (s->count[i] < 2147483647) s->count[i]++; }
            else if ((0x4182u >> transition) & 1u) { if (s->count[i] > -2147483647 - 1) s->count[i]--; }
        }
        s->previous[i] = (unsigned char)value;
    }
    s->valid = 1;
}

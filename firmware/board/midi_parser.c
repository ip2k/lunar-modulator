/* SPDX-License-Identifier: MIT
 * Independently authored from the MIDI 1.0 specification's message lengths.
 */
#include "midi_parser.h"

void lunar_midi_parser_reset(struct lunar_midi_parser *p)
{
    if (!p) return;
    p->status = p->need = p->count = p->in_sysex = 0;
    p->data[0] = p->data[1] = 0;
}

static int emit(struct lunar_midi_message *out, unsigned char status,
                unsigned char a, unsigned char b, unsigned char length)
{
    out->status = status;
    out->data1 = a;
    out->data2 = b;
    out->length = length;
    return 1;
}

int lunar_midi_parse(struct lunar_midi_parser *p, unsigned char byte,
                     struct lunar_midi_message *out)
{
    if (!p || !out) return 0;
    if (byte >= 0xf8u) return emit(out, byte, 0, 0, 1);
    if (byte & 0x80u) {
        p->count = 0;
        p->in_sysex = byte == 0xf0u;
        if (byte < 0xf0u) {
            unsigned kind = byte & 0xf0u;
            p->status = byte;
            p->need = (kind == 0xc0u || kind == 0xd0u) ? 1 : 2;
            return 0;
        }
        p->status = p->need = 0;
        switch (byte) {
        case 0xf1: case 0xf3: p->status = byte; p->need = 1; return 0;
        case 0xf2: p->status = byte; p->need = 2; return 0;
        case 0xf6: return emit(out, byte, 0, 0, 1);
        default: return 0; /* 0xf0, 0xf7, undefined 0xf4/0xf5 */
        }
    }
    if (p->in_sysex || !p->status) return 0;
    p->data[p->count++] = byte;
    if (p->count < p->need) return 0;
    p->count = 0;
    emit(out, p->status, p->data[0], p->need == 2 ? p->data[1] : 0,
         (unsigned char)(p->need + 1));
    if (p->status >= 0xf0u) p->status = p->need = 0; /* no running status */
    return 1;
}

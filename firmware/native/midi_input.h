/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_NATIVE_MIDI_INPUT_H
#define LUNAR_NATIVE_MIDI_INPUT_H
#include <stdint.h>

/* Decoded USB-MIDI channel messages only. SysEx/realtime and unsupported
 * voice messages belong to their own handlers, never the note-input path.
 * The shared setting is 0 for omni and 1..16 for a selected channel. */
static inline int lunar_midi_input_accept(uint8_t status, uint8_t a,
                                          uint8_t b, uint8_t channel)
{
    if (channel > 16u || a > 127u || b > 127u) return 0;
    switch (status & 0xf0u) {
    case 0x80u: case 0x90u: case 0xb0u: case 0xe0u: break;
    default: return 0;
    }
    return channel == 0u || channel == (status & 15u) + 1u;
}
#endif

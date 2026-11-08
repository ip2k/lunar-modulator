/* SPDX-License-Identifier: MIT
 * Independently authored C99 MIDI 1.0 byte-stream parser for the TRS input.
 */
#ifndef LUNAR_MIDI_PARSER_H
#define LUNAR_MIDI_PARSER_H

struct lunar_midi_message {
    unsigned char status, data1, data2, length; /* length 1..3 bytes */
};

struct lunar_midi_parser {
    unsigned char status, need, count, in_sysex, data[2];
};

void lunar_midi_parser_reset(struct lunar_midi_parser *p);

/* Feed one byte. Returns 1 when `out` holds a complete message.
 * - Channel voice messages use running status.
 * - Real-time bytes (0xF8-0xFF) are returned at once, even in the middle of
 *   another message, and leave it undisturbed.
 * - SysEx (0xF0 .. 0xF7) is skipped entirely: the input never acts on it.
 * - System common messages cancel running status; undefined 0xF4/0xF5 are
 *   dropped. Data bytes without a status are dropped. */
int lunar_midi_parse(struct lunar_midi_parser *p, unsigned char byte,
                     struct lunar_midi_message *out);
#endif

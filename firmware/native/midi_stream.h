/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_MIDI_STREAM_H
#define LUNAR_MIDI_STREAM_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
/* One jack stream, owned by the main loop. Reset at startup and on byte loss.
 * Each feed consumes exactly one byte. Returns one channel event (status/data)
 * or zero. System messages are parsed and discarded, never used for flashing. */
void lunar_midi_stream_reset(void);
int lunar_midi_stream_feed(uint8_t byte, uint8_t *status, uint8_t *a, uint8_t *b);
#ifdef __cplusplus
}
#endif
#endif

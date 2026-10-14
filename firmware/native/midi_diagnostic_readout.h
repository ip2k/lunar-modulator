/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_MIDI_DIAGNOSTIC_READOUT_H
#define LUNAR_MIDI_DIAGNOSTIC_READOUT_H
#include <stdint.h>

/* Fixed-width, bounded TFT row. Counters saturate at 99999 so the display
 * never wraps; A is the latest direct MASTER ADC sample. */
static inline void lunar_midi_diagnostic_readout(char line[27],
    uint32_t usb_messages, uint32_t uart_bytes, uint32_t accepted_noteons,
    uint32_t master_adc)
{
    const char label[] = "U00000 B00000 N00000 A0000";
    uint32_t values[4] = {usb_messages, uart_bytes, accepted_noteons, master_adc};
    for (unsigned i = 0; i < sizeof label; ++i) line[i] = label[i];
    for (unsigned field = 0; field < 4u; ++field) {
        unsigned width = field == 3u ? 4u : 5u;
        unsigned start = field == 0u ? 1u : field == 1u ? 8u :
                         field == 2u ? 15u : 22u;
        uint32_t maximum = field == 3u ? 9999u : 99999u;
        uint32_t value = values[field] > maximum ? maximum : values[field];
        for (unsigned digit = width; digit; --digit) {
            line[start + digit - 1u] = (char)('0' + value % 10u);
            value /= 10u;
        }
    }
}
#endif

/* SPDX-License-Identifier: MIT
 * Independently authored polled ADC for the MASTER pot and the battery.
 * Register sequence facts: pinned AC79 SDK cpu/wl82/key/adc_api.c
 * (Apache-2.0) and fm1-nes fm1_volume.c (Apache-2.0); see README.md.
 */
#ifndef LUNAR_ADC_H
#define LUNAR_ADC_H
#include "board_io.h"

#define LUNAR_ADC_BATTERY 3u /* PB1 [reported] */
#define LUNAR_ADC_MASTER 4u  /* PB6 [reported] */

struct lunar_adc {
    const struct lunar_board_io *io;
    unsigned poll_limit, ready, failed;
};
/* Refuses an ADC that is already enabled or has its interrupt enabled (CON
 * bits 4/5): someone else owns it. Sets PB1/PB6 analog (input, no digital
 * input, no pulls) and the analog bias bits the SDK's __adc_init sets. */
int lunar_adc_init(struct lunar_adc *s, const struct lunar_board_io *io, unsigned poll_limit);
/* One conversion of channel 3 or 4: launch, poll CON bit 7 at most
 * poll_limit reads, take the 10-bit RES, stop. 0 on failure (latched). */
int lunar_adc_read(struct lunar_adc *s, unsigned channel, unsigned *value);

/* Stock-style pot filter [reported: fm1-nes]: a reading more than 6 away from
 * the accepted value on 10 consecutive samples is accepted; level = raw >> 3. */
struct lunar_pot {
    unsigned accepted, debounce, level;
};
void lunar_pot_reset(struct lunar_pot *p);
/* Returns 1 when the 7-bit level changed. */
int lunar_pot_update(struct lunar_pot *p, unsigned raw);
#endif

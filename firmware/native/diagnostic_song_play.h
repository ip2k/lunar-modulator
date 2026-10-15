/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DIAGNOSTIC_SONG_PLAY_H
#define LUNAR_DIAGNOSTIC_SONG_PLAY_H
#include <stdint.h>
/* Opt-in diagnostic only. Readiness starts after initial audio production;
 * the independent recovery deadline is never reset. Consume the action even
 * if the caller finds playback already running, so Stop stays stopped. */
static inline int lunar_diagnostic_song_play_poll(uint32_t now, uint32_t ready,
                                                  uint8_t *attempted)
{
    if (!attempted || *attempted || (uint32_t)(now - ready) < 2000u) return 0;
    *attempted = 1u;
    return 1;
}
#endif

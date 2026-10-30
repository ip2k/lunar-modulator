/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_FM6_LIVE_H
#define LUNAR_DEVKIT_FM6_LIVE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
struct lunar_fm6_live_status {
    uint32_t test_case, patch, voices, cycles, note_batches, invalid, clipped;
    /* Latched at the end of each complete case; PCM16 stereo, little endian.
     * A snapshot during a case must never report a partial fingerprint. */
    uint32_t completed_cases, completed_case, completed_hash;
};
/* Init on the worker before DAC start. Render/status have one audio owner;
 * the worker reads status only while the audio IRQ is excluded. */
int lunar_devkit_fm6_live_init(void);
void lunar_devkit_fm6_live_render(int16_t *four_channel_64_frames);
void lunar_devkit_fm6_live_status(struct lunar_fm6_live_status *out);
#ifdef __cplusplus
}
#endif
#endif

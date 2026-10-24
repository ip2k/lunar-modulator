/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DEVKIT_RENDERER_LIVE_H
#define LUNAR_DEVKIT_RENDERER_LIVE_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
struct lunar_renderer_status {
    uint32_t test_case, cycles, blocks, controls, invalid, clipped;
    uint32_t completed_cases, completed_case, completed_hash, arena_bytes, init_error;
    uint32_t unit_bytes[8];
};
/* One audio owner, initialized before DAC start. Status must be copied with
 * that IRQ excluded. Initialization failure refuses output, not a smaller kit. */
int lunar_devkit_renderer_init(void);
void lunar_devkit_renderer_render(int16_t *four_channel_64_frames);
void lunar_devkit_renderer_status(struct lunar_renderer_status *out);
#ifdef __cplusplus
}
#endif
#endif

/* SPDX-License-Identifier: GPL-3.0-only */
#include "fm1_audio.h"
#include "audio_pause.h"
/* The included IRQ HAL requires an application fault handler even in this
 * compile-only translation unit. This harness is never linked or booted. */
static void fm1_fault(const fm1_crash_t *crash) {
    (void)crash;
    for (;;) {}
}
int native_audio_pause_begin(lunar_audio_pause_t *p, lunar_audio_queue_t *q,
                            int32_t *dma, uint32_t words) {
    return lunar_audio_pause_begin(p, q, dma, words);
}
int native_audio_pause_end(lunar_audio_pause_t *p) {
    return lunar_audio_pause_end(p);
}

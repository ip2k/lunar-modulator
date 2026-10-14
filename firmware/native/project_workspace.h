/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PROJECT_WORKSPACE_H
#define LUNAR_PROJECT_WORKSPACE_H
#include "fm1_tft.h"
#include <stddef.h>
#include <stdint.h>
#if !FM1_TFT_INDEXED
#error "Native project workspace requires the indexed framebuffer"
#endif
/* Main-task exclusive lease. The caller must stop audio, drawing and display
 * reads for its duration. Native panel DMA uses cv_px, never these pixels.
 * Release leaves the frame invalid: redraw before resuming display reads.
 * This supplies scratch only; it grants no flash ownership or write authority. */
typedef struct {
    fm1_tft_t *frame;
    void *memory;
    size_t bytes;
} lunar_project_workspace;
static inline void *lunar_project_workspace_begin(lunar_project_workspace *lease,
        fm1_tft_t *frame, size_t bytes, int audio_stopped,
        int drawing_stopped, int display_reads_stopped) {
    uintptr_t start, aligned;
    size_t skip;
    if (!lease || lease->frame || lease->memory || lease->bytes || !frame || !bytes ||
        audio_stopped != 1 || drawing_stopped != 1 || display_reads_stopped != 1)
        return NULL;
    start = (uintptr_t)frame->px;
    if (start > UINTPTR_MAX - 15u) return NULL;
    aligned = (start + 15u) & ~(uintptr_t)15u;
    skip = (size_t)(aligned - start);
    if (skip > sizeof frame->px || bytes > sizeof frame->px - skip) return NULL;
    frame->pixel_overflow = 1; /* Never show scratch bytes as pixel indices. */
    lease->frame = frame; lease->memory = (void *)aligned; lease->bytes = bytes;
    return lease->memory;
}
static inline int lunar_project_workspace_end(lunar_project_workspace *lease) {
    if (!lease || !lease->frame || !lease->memory || !lease->bytes) return -1;
    lease->frame->pixel_overflow = 1;
    lease->frame = NULL; lease->memory = NULL; lease->bytes = 0;
    return 0;
}
#endif

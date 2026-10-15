/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_RENDER_STAGE_PROFILE_H
#define LUNAR_RENDER_STAGE_PROFILE_H

#include <stdint.h>

/* Stage IDs are part of private diagnostic schema 2. Inclusive sequence
 * dispatch contains engine callbacks; stage totals must not be summed. */
enum lunar_render_profile_stage {
    LUNAR_PROFILE_SEQ_DISPATCH = 0,
    LUNAR_PROFILE_SOUND_0,
    LUNAR_PROFILE_SOUND_1,
    LUNAR_PROFILE_SOUND_2,
    LUNAR_PROFILE_SOUND_3,
    LUNAR_PROFILE_MASTER_FX_0,
    LUNAR_PROFILE_MASTER_FX_1,
    LUNAR_PROFILE_POSTMIX,
    LUNAR_PROFILE_DISPLAY_STRIP,
    LUNAR_RENDER_PROFILE_STAGE_COUNT
};

#ifdef LUNAR_RENDER_STAGE_PROFILE
uint32_t lunar_profile_ticks(void);
void lunar_profile_finish(unsigned stage, uint32_t start_ticks);
#define LUNAR_PROFILE_START(name) uint32_t name = lunar_profile_ticks()
#define LUNAR_PROFILE_FINISH(stage, name) lunar_profile_finish((stage), (name))
#else
/* The normal desktop/web and native builds compile out all profiling code. */
#define LUNAR_PROFILE_START(name) ((void)0)
#define LUNAR_PROFILE_FINISH(stage, name) ((void)0)
#endif

#endif

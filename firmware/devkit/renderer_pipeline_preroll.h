/* SPDX-License-Identifier: MIT. Music starts only on DMA window zero. */
#ifndef LUNAR_RENDERER_PIPELINE_PREROLL_H
#define LUNAR_RENDERER_PIPELINE_PREROLL_H
#define PRE_QUIET 0u
#define PRE_ARM 1u
#define PRE_MUSIC 2u
static inline int preroll_step(unsigned *phase,unsigned window) {
    if(window>2u || *phase>PRE_MUSIC)return -1;
    if(*phase==PRE_ARM && window==0u)*phase=PRE_MUSIC;
    return *phase==PRE_MUSIC;
}
#endif

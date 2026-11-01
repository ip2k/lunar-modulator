/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DIAGNOSTIC_API_H
#define LUNAR_DIAGNOSTIC_API_H
#include <stdint.h>
#define LUNAR_DIAGNOSTIC_RATE 44118.0f
#define LUNAR_DIAGNOSTIC_VOICES 8u
#define LUNAR_DIAGNOSTIC_ARENA_BYTES 65536u
/* A one-shot fixed FM6 arrangement. No heap, engine switching or persistence.
 * All calls belong to one rendering owner; no concurrent app/UI access. */
int lunar_diagnostic_init(void);
void lunar_diagnostic_key(int key, int down);
void lunar_diagnostic_note(int note, int velocity, int down);
void lunar_diagnostic_knob(int encoder, int delta);
int lunar_diagnostic_render(int32_t *pcm, uint32_t frames);
void lunar_diagnostic_fault(uint32_t reason);
uint32_t lunar_diagnostic_status(void);
#endif

/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_ENGINE_ADAPTER_H
#define LUNAR_ENGINE_ADAPTER_H
#include <stdint.h>
int lunar_engine_init(uint32_t sample_rate);
void lunar_engine_note_on(uint8_t key, uint8_t velocity);
void lunar_engine_note_off(uint8_t key);
void lunar_engine_render(int32_t *out, uint32_t frames);
#endif

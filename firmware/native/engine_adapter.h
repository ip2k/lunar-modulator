/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_ENGINE_ADAPTER_H
#define LUNAR_ENGINE_ADAPTER_H
#include <stdint.h>
int lunar_engine_init(uint32_t sample_rate);
/* Audio-task-only mutation. Status 1 is a panel detent: a=index, b=int8 step. */
void lunar_engine_event(uint8_t status, uint8_t a, uint8_t b);
uint16_t lunar_engine_param_count(void);
const char *lunar_engine_param_name(uint16_t index);
/* Atomic byte snapshot for the screen: knob position in percent, not units. */
uint8_t lunar_engine_param_position(uint16_t index);
void lunar_engine_note_on(uint8_t key, uint8_t velocity);
void lunar_engine_note_off(uint8_t key);
void lunar_engine_all_notes_off(void);
void lunar_engine_render(int32_t *out, uint32_t frames);
#endif

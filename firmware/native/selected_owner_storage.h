/* SPDX-License-Identifier: MIT. Single permanent aggregate/binding storage. */
#ifndef LUNAR_SELECTED_OWNER_STORAGE_H
#define LUNAR_SELECTED_OWNER_STORAGE_H
#include "selected_interactive_owner.h"
enum { LUNAR_SELECTED_INPUT_CAPACITY=16, LUNAR_SELECTED_PCM_CAPACITY=2 };
/* Defined once in selected_aggregate_layout_roots.c; never reconstructed. */
extern lunar_selected_platform_t lunar_selected_aggregate_platform;
extern lunar_input_t lunar_selected_aggregate_input[LUNAR_SELECTED_INPUT_CAPACITY];
extern lunar_pcm_t lunar_selected_aggregate_pcm[LUNAR_SELECTED_PCM_CAPACITY];
#endif

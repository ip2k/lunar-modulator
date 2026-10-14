/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_NATIVE_CONTENT_CATALOGUE_H
#define LUNAR_NATIVE_CONTENT_CATALOGUE_H

#include <stdint.h>

/* Generated read-only XIP content. The reader must validate CRCs and application
 * admission before using these bytes; this catalogue is not acceptance evidence.
 * Count zero uses one unused sentinel so the generated source remains C99. */
typedef struct lunar_content_asset {
    const uint8_t *bytes;
    uint32_t size;
    uint8_t kind; /* FM1_STATE_PROJECT or FM1_STATE_SET from fm1_state.h */
    const char *title; /* bounded printable source basename; never a path */
    uint32_t parent_project_index; /* catalogue index; UINT32_MAX for PROJECT */
} lunar_content_asset_t;

extern const lunar_content_asset_t lunar_content_catalogue[];
extern const uint32_t lunar_content_count;
extern uint32_t lunar_selected_companion_set_index; /* UINT32_MAX means keep project sequence */

#endif

/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DIAGNOSTIC_APP_H
#define LUNAR_DIAGNOSTIC_APP_H
#include <stdint.h>
#include "fm1_app.h"
#if !FM1_APP_EXTERNAL_ARENAS
#error "diagnostic profile requires FM1_APP_EXTERNAL_ARENAS=1 in every TU"
#endif
#include "diagnostic_api.h"
const fm1_app_t *lunar_diagnostic_state(void);
#ifdef LUNAR_DIAGNOSTIC_OFFLINE_PROOF
#ifdef FM1_APP_RENDER_PIPELINE
#error "offline owner proof does not admit pending app pipeline work"
#endif
/* Explicit single-owner host proof only, absent from the default diagnostic.
 * The display lease owner serializes every call; pixels stay permanent. */
int lunar_diagnostic_owner_button(int button, int down);
int lunar_diagnostic_owner_encoder(int encoder, int delta);
int lunar_diagnostic_owner_select(int engine);
int lunar_diagnostic_owner_render(int32_t *pcm, uint32_t frames);
const uint16_t *lunar_diagnostic_owner_draw(void *unused, uint32_t min_frames);
#endif
#endif

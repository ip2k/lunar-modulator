/* SPDX-License-Identifier: MIT. Explicit host-only, single-owner proof. */
#ifndef LUNAR_SELECTED_INTERACTIVE_APP_H
#define LUNAR_SELECTED_INTERACTIVE_APP_H
#include "diagnostic_transport.h"
#ifdef FM1_APP_RENDER_PIPELINE
#error "selected owner does not admit pending pipeline work"
#endif
/* Main owner only. apply returns command admission, not semantic success of a
 * panel action. render writes one complete block in the existing ALNK scale.
 * draw's permanent native RGB565 frame must stay leased until all rows finish.
 * No calls to these or diagnostic key/knob/note APIs from scanner/audio IRQs. */
int lunar_selected_interactive_apply(void *, const lunar_input_t *);
int lunar_selected_interactive_render(void *, int32_t *);
const uint16_t *lunar_selected_interactive_draw(void *, uint32_t min_frames);
#endif

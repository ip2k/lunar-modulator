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
#ifdef LUNAR_SELECTED_PROJECT_STAGE_PROOF
#include "fm1_app_state.h"
/* Explicit offline operation only: caller stops and excludes all owner main,
 * Timer/audio producers/consumers and app/display access before entry and until
 * return. No live pause, IRQ lock or deadline is implemented by this flag or
 * the reentry guard. Never call while the interactive owner is being serviced.
 *
 * Stages the actual private app using one 64-KiB arena previously used by cold
 * startup. Modes2/3 and callbacks obey fm1_app_state_project_stage's complete
 * ownership contract; context/backing/report must be disjoint from all live
 * objects. This does not enable store_ready or the SAVE UI.
 *
 * Input/render/draw/init and nested stage calls refuse without mutation while
 * staging, including abort/commit hooks; early wrapper refusal leaves report
 * untouched. Valid calls retain the core's bytes/reports. A diagnostic fault
 * during precommit hooks closes the candidate and prevents publication. A
 * fault during commit preserves REFUSED, otherwise returns INDETERMINATE:
 * rescan required, no automatic retry/abort. Fault remains sticky afterward.
 * The caller's opaque callback extents and external exclusion are obligations,
 * not checks that an ordinary boolean guard can prove. */
int lunar_selected_interactive_stage(unsigned binary,
    const fm1_app_state_stage_t *, void *ctx, fm1_state_report_t *report);
#endif
#endif

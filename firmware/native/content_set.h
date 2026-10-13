/* MIT: packed set loading without a whole-set text buffer. */
#ifndef LUNAR_CONTENT_SET_H
#define LUNAR_CONTENT_SET_H
#include "fm1_seq.h"
#include "fm1_state.h"
#include "fm1_app.h"
#include "instance_pool.h"

/* Main-thread only: the binary reader needs more than 8 KiB of stack.
 * bytes must remain immutable throughout this call. scratch must be a
 * caller-owned, initialized sequencer, never the currently playing instance.
 * Failure may mutate scratch: discard it. Success follows the existing Movy
 * importer semantics (including ignored unknown lines and capacity truncation),
 * and is not proof that every requested event fitted or can play in real time.
 * This accepts standalone SET containers; project application is separate. */
int lunar_content_load_set(const uint8_t *bytes, uint32_t size,
                           fm1_seq_t *scratch, fm1_state_report_t *report);
/* Refuses observed range/text/unknown-field/capacity loss before activation.
 * Zero diagnostics still do not prove all grammar/dependencies are valid. */
int lunar_content_load_set_checked(const uint8_t *bytes, uint32_t size,
                                   fm1_seq_t *scratch, fm1_state_report_t *report);
/* Checked read plus shared-app activation. Same rendering task, immutable bytes,
 * separately initialized scratch with current limits/rate. A rejected container
 * leaves the live app untouched. Scratch is disposable after either outcome.
 * The caller supplies the staging arena; this function allocates none. */
int lunar_content_activate_set(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                               fm1_seq_t *scratch, fm1_state_report_t *report);
/* Startup/main-task helper: borrow pool memory for initialized staging, activate
 * only after checked loading, and reclaim staging before engine allocation.
 * app/limits and pool must be initialized; rate must match the live sequencer.
 * Failure before activation preserves the live app. No permanent arena is added.
 * Stack/dependency/playback admission still belongs to the caller. */
int lunar_content_start_set(fm1_app_t *app, lunar_instance_pool_t *pool,
                            const uint8_t *bytes, uint32_t size, uint32_t rate,
                            fm1_state_report_t *report);
#endif

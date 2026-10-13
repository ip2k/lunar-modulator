/* MIT: packed set loading without a whole-set text buffer. */
#ifndef LUNAR_CONTENT_SET_H
#define LUNAR_CONTENT_SET_H
#include "fm1_seq.h"
#include "fm1_state.h"

/* Main-thread only: the binary reader needs more than 8 KiB of stack.
 * bytes must remain immutable throughout this call. scratch must be a
 * caller-owned, initialized sequencer, never the currently playing instance.
 * Failure may mutate scratch: discard it. Success follows the existing Movy
 * importer semantics (including ignored unknown lines and capacity truncation),
 * and is not proof that every requested event fitted or can play in real time.
 * This accepts standalone SET containers; project application is separate. */
int lunar_content_load_set(const uint8_t *bytes, uint32_t size,
                           fm1_seq_t *scratch, fm1_state_report_t *report);
#endif

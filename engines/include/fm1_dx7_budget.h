/* SPDX-License-Identifier: MIT. Opt-in, render-owned DX7 voice admission. */
#ifndef FM1_DX7_BUDGET_H_
#define FM1_DX7_BUDGET_H_
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

typedef struct fm1_dx7_budget_stats {
  uint32_t active, limit;
  uint32_t retired;  /* budget retirements completed; wraps modulo 2^32 */
  uint32_t stolen;   /* new notes reusing an active slot; wraps modulo 2^32 */
} fm1_dx7_budget_stats_t;

/* Only a DX7 instance returned by that engine's create method is valid.
 * Call from its rendering owner between render calls, or with audio stopped.
 * No locking, allocation, IRQ access or automatic timing policy is provided.
 * Default is twelve. Accepts 1..12; returns 0 for NULL or an invalid limit,
 * without changing state. Applies at the next internal 64-frame block:
 * released voices first, then lower carrier gain, then older voice age.
 * Retiring voices render one final block fading to zero, so a reduction does
 * not save CPU immediately. Active count can exceed limit until that block.
 * New-note stealing retains released/age priority and same-key retrigger.
 * Raising the limit admits future notes; it does not resurrect retired ones.
 * Audio changes intentionally when voices are retired/stolen at a lower cap.
 * This extension is not persisted as a patch parameter or enabled by default.
 */
int fm1_dx7_set_voice_limit(void *self, unsigned limit);

/* Same owner-only contract. Returns 0 for NULL self/out and leaves out intact.
 * Snapshot counters only; no claim of remaining CPU or deadline acceptance.
 */
int fm1_dx7_get_budget_stats(const void *self, fm1_dx7_budget_stats_t *out);
#ifdef __cplusplus
}
#endif
#endif

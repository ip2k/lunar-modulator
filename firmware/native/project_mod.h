/* MIT: stage project modulation using the shared applier and runtime planner. */
#ifndef LUNAR_PROJECT_MOD_H
#define LUNAR_PROJECT_MOD_H
#include "project_units.h"

/* Main-task-only. Caller owns an aligned, disposable fm1_mod_size() workspace
 * disjoint from immutable bytes, descriptors, host/report and live state.
 * On failure the workspace may be changed; no live runtime is touched.
 * Validates the unit plan, creates modules, applies their parameters/data and
 * cables, restores engine modulation bases for the final focused pad, and refuses skipped records or enabled routes the planner refuses.
 * Success returns a staged runtime, to be destroyed with fm1_mod_destroy.
 * Does not allocate/construct sound/effect engines, apply their parameters or
 * sequence bindings, reserve a pool, activate a project, or prove timing.
 * Per-voice capacity is the shared planner's policy (may be below12 voices),
 * not a guarantee of the selected sound engine's advertised polyphony.
 * Caller must hold stable registries and provide enough main-task stack for
 * the binary codec (>8KiB). This is not a flash/install admission gate. */
fm1_mod_t *lunar_project_mod_stage(const uint8_t *bytes, uint32_t size,
                                  const fm1_state_names_t *names,
                                  const fm1_host_t *host,
                                  void *workspace, size_t workspace_bytes,
                                  fm1_state_report_t *report);
#endif

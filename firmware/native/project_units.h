/* MIT: bounded catalogue/allocation planning for immutable binary projects. */
#ifndef LUNAR_PROJECT_UNITS_H
#define LUNAR_PROJECT_UNITS_H
#include "fm1_state.h"

#define LUNAR_PROJECT_UNITS 18u
/* Compact plan indices: sounds 0..3, inserts 4..11 (sound*2+slot),
 * master effects 12..13, MIDI effects 14..17. Not shared-app unit codes. */
typedef struct {
    const fm1_engine_t *engine[LUNAR_PROJECT_UNITS];
    size_t size[LUNAR_PROJECT_UNITS];
    uint32_t given;
    const fm1_mod_kind_t *module[8];
    uint8_t modules_given;
} lunar_project_units_t;

/* Main-task-only; binary codec uses >8 KiB stack. Caller guarantees immutable
 * bytes and stable registries/host for the whole call. On failure out is intact.
 * Validates CRC/container, project kind, unit/rack positions, duplicates and
 * selected catalogue availability, parameter UID/type/range/pad bindings;
 * collects nonzero engine instance sizes. Refuses values requiring clamping.
 * Does NOT validate modulation cables/data, sequence bindings or
 * semantics; allocate, initialize, reserve capacity, apply or activate anything.
 * Module/workspace and sequencer storage are NOT included in these sizes.
 * Success is a unit plan, never permission to install/activate a project. */
int lunar_project_units_plan(const uint8_t *bytes, uint32_t size,
                             const fm1_state_names_t *names,
                             const fm1_host_t *host,
                             lunar_project_units_t *out,
                             fm1_state_report_t *report);
#endif

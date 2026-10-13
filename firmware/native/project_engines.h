/* MIT: owned, disposable candidate engine instances. */
#ifndef LUNAR_PROJECT_ENGINES_H
#define LUNAR_PROJECT_ENGINES_H
#include "project_units.h"
#include "instance_pool.h"

typedef struct {
    const fm1_engine_t *engine;
    void *memory, *self;
} lunar_project_instance_t;
typedef struct {
    lunar_instance_pool_t *pool;
    lunar_project_instance_t unit[LUNAR_PROJECT_UNITS];
} lunar_project_engines_t;

/* Main-task-only. Caller owns initialized empty out and a pool with exclusive
 * control-task ownership; outputs, input/registries/host/report are stable and
 * disjoint from pool/live state. First validates all units and constructors,
 * then retains allocations and constructs with defaults. On failure destroys
 * successful candidates and releases every candidate allocation; out is empty.
 * Existing instances stay allocated. Success transfers candidate ownership to
 * caller, who must release it or explicitly transfer each allocation/handle.
 * No project parameters, modulation, sequence, UI or activation are applied.
 * Pool free-list order and engine shared read-only first-create caches may change.
 * Constructors obey the engine ABI and may refuse a host. Codec needs >8KiB stack.
 * This is actual capacity admission, not permission for device installation. */
int lunar_project_engines_stage(const uint8_t *bytes, uint32_t size,
                                const fm1_state_names_t *names, const fm1_host_t *host,
                                lunar_instance_pool_t *pool,
                                lunar_project_engines_t *out,
                                fm1_state_report_t *report);
/* Releases only an owned candidate produced by stage (or its remaining units
 * after explicit ownership transfer). Main task, no concurrent render calls. */
void lunar_project_engines_release(lunar_project_engines_t *candidate);
#endif

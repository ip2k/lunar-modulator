/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_BRINGUP_H
#define LUNAR_BRINGUP_H
#include "../display/panel_probe.h"
#include "../recovery/request.h"

enum lunar_bringup_dwell {
    LUNAR_BRINGUP_DWELL_SKIPPED = 0,
    LUNAR_BRINGUP_DWELL_OK = 1,
    LUNAR_BRINGUP_DWELL_FAILED = 2
};
enum lunar_bringup_run {
    LUNAR_BRINGUP_INVALID = 0,
    LUNAR_BRINGUP_COMPLETE = 1,
    LUNAR_BRINGUP_ALREADY_ATTEMPTED = 2
};
struct lunar_bringup {
    const struct lunar_panel_transport *bus;
    struct lunar_recovery *recovery;
    unsigned dwell_ms;
    unsigned bound;
    unsigned attempted;
    enum lunar_panel_result display;
    enum lunar_bringup_dwell dwell;
    unsigned recovery_requested;
    unsigned request_transmitted;
};
/* Start with zero-initialized, caller-owned storage. Bind invokes no callbacks.
 * References and their callback contexts must remain alive and quiescent.
 * A used controller cannot be rebound. This is not an activation permit. */
int lunar_bringup_bind(struct lunar_bringup *controller,
                      const struct lunar_panel_transport *bus,
                      struct lunar_recovery *recovery, unsigned dwell_ms);
/* Single owner, no concurrency. A second call performs no I/O. COMPLETE means
 * the software sequence finished, even when display/dwell/request failed.
 * request_transmitted is not observation of reset, USB or usable recovery. */
enum lunar_bringup_run lunar_bringup_run(struct lunar_bringup *controller);
#endif

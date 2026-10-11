/* SPDX-License-Identifier: MIT */
#include "bringup.h"

static int valid_bus(const struct lunar_panel_transport *bus)
{
    return bus && bus->begin && bus->write && bus->end && bus->wait_ms;
}
static int valid_recovery(const struct lunar_recovery *s)
{
    return s && !s->attempted && !s->failed && s->poll_limit &&
           s->poll_limit <= 65536u && s->io.read && s->io.write &&
           s->io.sync && s->io.mailbox_write && s->io.mailbox_read;
}
int lunar_bringup_bind(struct lunar_bringup *s,
                      const struct lunar_panel_transport *bus,
                      struct lunar_recovery *recovery, unsigned ms)
{
    if (!s || s->attempted || !valid_bus(bus) ||
        !valid_recovery(recovery) || ms > 1000u) return 0;
    s->bus = bus;
    s->recovery = recovery;
    s->dwell_ms = ms;
    s->bound = 1;
    s->display = LUNAR_PANEL_INVALID;
    s->dwell = LUNAR_BRINGUP_DWELL_SKIPPED;
    s->recovery_requested = 0;
    s->request_transmitted = 0;
    return 1;
}
enum lunar_bringup_run lunar_bringup_run(struct lunar_bringup *s)
{
    if (!s) return LUNAR_BRINGUP_INVALID;
    if (s->attempted) return LUNAR_BRINGUP_ALREADY_ATTEMPTED;
    if (!s->bound) return LUNAR_BRINGUP_INVALID;
    /* Latch before validation or the first possible callback, including errors. */
    s->attempted = 1;
    if (!valid_bus(s->bus) || !valid_recovery(s->recovery) ||
        s->dwell_ms > 1000u) return LUNAR_BRINGUP_INVALID;
    s->display = lunar_panel_probe(s->bus);
    if (s->display == LUNAR_PANEL_OK && s->dwell_ms)
        s->dwell = s->bus->wait_ms(s->bus->context, s->dwell_ms) ?
                   LUNAR_BRINGUP_DWELL_OK : LUNAR_BRINGUP_DWELL_FAILED;
    /* The transport owns cleanup. Complete it before any recovery callback. */
    s->bus->end(s->bus->context);
    s->recovery_requested = 1;
    s->request_transmitted = lunar_recovery_request(s->recovery) ? 1u : 0u;
    return LUNAR_BRINGUP_COMPLETE;
}

/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PANEL_PROTOCOL_CAPTURE_H
#define LUNAR_PANEL_PROTOCOL_CAPTURE_H
#include "../diagnostic/runtime.h"

/* Offline RAM sink: requests are recorded, never transmitted or delayed.
 * This is deliberately not a usable hardware transport implementation. */
struct lunar_panel_capture {
    diag_u32 magic, version, result, commands, data_bytes, ends;
    diag_u32 wait_calls, requested_wait_ms, hash, active, protocol_error;
};
void lunar_panel_capture_run(volatile struct lunar_panel_capture *);
#endif

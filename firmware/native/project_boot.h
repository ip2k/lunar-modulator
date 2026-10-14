/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PROJECT_BOOT_H
#define LUNAR_PROJECT_BOOT_H
#include "project_start.h"
#if FM1_APP_EXTERNAL_ARENAS
/* Cold main task, immutable complete PROJECT, after all other records restore.
 * Validates codec/CRC before applying the saved screen through shared UI APIs.
 * No VIEW leaves UI intact. Preflight refusal leaves app intact. */
int lunar_project_restore_view(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                               fm1_state_report_t *report);
/* Compose startup for an initialized, empty, unrendered external-arena app.
 * Its storage provider must be this exclusively owned initialized empty pool.
 * Input/report/app/pool metadata and arena must be disjoint. Sequence and DX7
 * scratch are reclaimed before engine allocation. Candidate MIDI storage is
 * reclaimed after inline restoration. Full codec reads require >8KiB stack,
 * plus caller/local frames; actual target stack/timing admission is separate.
 * Failure can leave the cold app partially restored: do not render; return to
 * recovery or discard it. This is not a live transactional project replacement.
 * No flash writes or automatic sequence playback. rate matches app's sequencer. */
int lunar_project_start_with_set(fm1_app_t *app, lunar_instance_pool_t *pool,
                                 const uint8_t *project_bytes, uint32_t project_size,
                                 const uint8_t *set_bytes, uint32_t set_size, uint32_t rate,
                                 fm1_state_report_t *report);
int lunar_project_start(fm1_app_t *app, lunar_instance_pool_t *pool,
                         const uint8_t *bytes, uint32_t size, uint32_t rate,
                         fm1_state_report_t *report);
#endif
#endif

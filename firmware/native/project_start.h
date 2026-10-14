/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PROJECT_START_H
#define LUNAR_PROJECT_START_H
#include "fm1_app.h"
#include "project_engines.h"

#if FM1_APP_EXTERNAL_ARENAS
/* Cold-start main task only, before input/render. Read a complete immutable
 * binary PROJECT, retain four levels/current sound/octave/transpose, then
 * apply through shared setters. CRC/type/range/duplicate refusal leaves app
 * intact. Input and report must be disjoint from app. SESSION's key is only
 * descriptive, as in the browser loader; SETTINGS records are not applied.
 * Other project records require their separate staging/activation steps.
 * No allocation; the binary reader still needs >8KiB main-task stack. */
int lunar_project_restore_scalars(fm1_app_t *app,
                                  const uint8_t *bytes, uint32_t size,
                                  fm1_state_report_t *report);

/* Cold main task, immutable PROJECT, after audio/MIDI engines are restored.
 * Preflight validates complete unit plan and exact installed engine identities.
 * Construct modulation in final app storage, preserve saved bases/routes and
 * attach rendering/UI with the file seed. Input/report disjoint from app.
 * Preflight refusal preserves app. Failure after default-rack release requires
 * discarding the cold app; never render after failure. No complete startup or
 * live project replacement transaction. Reader requires >8KiB stack. */
int lunar_project_restore_mod(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                              fm1_state_report_t *report);

/* Caller-owned disposable scratch; not part of app or its allocation pool. */
typedef struct {
    uint32_t seen;
    uint8_t voice[FM1_DX7_USER_SLOTS][FM1_DX7_VCED_BYTES];
} lunar_project_dx7_scratch_t;

/* Cold-start main task, immutable complete PROJECT. Validate CRC, unique slots
 * and exact VCED ranges/printable names before changing the app. Missing FM6
 * refuses voice records. Success preserves file slot numbers (PROJECT semantics)
 * and updates installed FM6 instances through the shared API. Scratch may change
 * on refusal; app does not. All arguments must be pairwise disjoint. */
int lunar_project_restore_dx7(fm1_app_t *app, const uint8_t *bytes, uint32_t size,
                              lunar_project_dx7_scratch_t *scratch,
                              fm1_state_report_t *report);

/* Cold-start only, before input/render: reconstruct the four prepared MIDI
 * effects in the app's fixed inline storage and restore their parameter values.
 * on[] comes from the same checked project's ON records (absent means bypass).
 * Candidate remains owned and unchanged, including its MIDI allocations.
 * Preflight refusals do not mutate app. Constructor refusal can leave app
 * partially restored: discard the cold app, never render it after failure.
 * No live replacement/rollback transaction or complete project activation. */
int lunar_project_restore_midi_units(fm1_app_t *app,
                                    const lunar_project_engines_t *candidate,
                                    const uint8_t on[FM1_APP_SOUNDS]);

/* Cold empty app, before input/render. Candidate was staged/applied for this
 * host and registry with the app's configured pool provider. Transfer only
 * sounds/audio effects; MIDI effect candidates remain owned by candidate.
 * Failure leaves both ownership sets intact. Success clears transferred rows,
 * leaving the pool association for remaining candidate cleanup. Does not
 * activate a complete project or adopt sequence/modulation/settings records. */
int lunar_project_adopt_audio_units(fm1_app_t *app,
                                    lunar_project_engines_t *candidate);
#endif
#endif

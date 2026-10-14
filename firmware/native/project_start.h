/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PROJECT_START_H
#define LUNAR_PROJECT_START_H
#include "fm1_app.h"
#include "project_engines.h"

#if FM1_APP_EXTERNAL_ARENAS
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

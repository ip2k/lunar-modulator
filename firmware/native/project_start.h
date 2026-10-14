/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_PROJECT_START_H
#define LUNAR_PROJECT_START_H
#include "fm1_app.h"
#include "project_engines.h"

#if FM1_APP_EXTERNAL_ARENAS
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

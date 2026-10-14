/* MIT: disposable project sequence staging and selected-engine bindings. */
#ifndef LUNAR_PROJECT_SEQ_H
#define LUNAR_PROJECT_SEQ_H
#include "project_units.h"
#include "fm1_seq.h"

/* Main-task-only; caller supplies a separately initialized, disposable scratch
 * sequencer with the intended sample rate and limits, disjoint from immutable input, descriptors/report/output and live
 * state. Failure may mutate scratch; has_set remains intact. No allocation or
 * activation occurs. A project without SET lines leaves scratch intact and
 * succeeds with has_set=0. Otherwise the checked streaming importer rejects
 * observed loss, then internal sound routes and assigned lane labels must bind
 * to selected, lockable parameters. MIDI routes remain external dependencies.
 * Stable input/registries and >8KiB codec stack are caller requirements.
 * This does not prove full grammar, playback, MIDI delivery, timing or capacity
 * for coexisting engines. Caller must discard scratch after failure. */
int lunar_project_seq_stage_companion(const uint8_t *project_bytes, uint32_t project_size,
                                      const uint8_t *set_bytes, uint32_t set_size,
                                      const fm1_state_names_t *names, const fm1_host_t *host,
                                      fm1_seq_t *scratch, unsigned *has_set,
                                      fm1_state_report_t *report);
int lunar_project_seq_stage(const uint8_t *bytes, uint32_t size,
                            const fm1_state_names_t *names, const fm1_host_t *host,
                            fm1_seq_t *scratch, unsigned *has_set,
                            fm1_state_report_t *report);
#endif

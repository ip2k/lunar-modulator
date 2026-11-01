/* A deliberately narrow PROJECT applier for the selected Trio diagnostic.
 * MIT; no vendor or GPL HAL source is copied here. The file format parser is
 * the shared state codec, not a native-specific second decoder. */
#ifndef LUNAR_SELECTED_PROJECT_H_
#define LUNAR_SELECTED_PROJECT_H_

#include "fm1_app.h"
#include "fm1_state.h"

#ifdef __cplusplus
extern "C" {
#endif

/* The caller owns an aligned fm1_state_bin_reader_size() workspace and a
 * stable, immutable packed source for both synchronous passes. The app must
 * have been initialized with external arenas and have no selected units or
 * rendered frames. Every record is validated twice before app mutation.
 * A successful record preflight does not guarantee the engine constructor
 * accepts the target rate or that its arena fits; those remain app errors. */
int lunar_selected_project_load(fm1_app_t *app, const uint8_t *packed,
    uint32_t packed_bytes, void *reader, size_t reader_bytes,
    fm1_state_report_t *report);

#ifdef __cplusplus
}
#endif
#endif

/* Current PROJECT values for the shared canonical emitter. Internal, MIT.
 * This is not a general document store: only the current app collector supplies
 * whole INFO/DATA records. All source/getter results are exclusively stable;
 * callbacks and referenced record bytes are borrowed synchronously. */
#ifndef FM1_STATE_JSON_PROJECT_H_
#define FM1_STATE_JSON_PROJECT_H_
#include "fm1_state.h"
typedef struct fm1_state_json_project {
  void *ctx;
  /* Unit indices: sounds0-3, inserts4-11, MIDI FX12-27, master28-31, rack32-39.
   * Visit the same PARAM records/order as collection; stop when sink refuses. */
  void (*params)(void *ctx, unsigned unit, fm1_rec_sink_t sink, void *sctx);
  const uint8_t *(*voice)(void *ctx, unsigned slot);
  int (*data)(void *ctx, unsigned pos, fm1_rec_t *out);
  int (*cable)(void *ctx, unsigned slot, fm1_rec_t *out);
  int (*lines)(void *ctx, fm1_rec_sink_t sink, void *sctx);
  const fm1_midi_map_t *midi_map;
} fm1_state_json_project_t;
size_t fm1_state_json_project_size(void);
/* validation_map is temporary, disjoint storage, unused after collection END.
 * The provider's map is emitted only after validation of its collected records.
 * The writer has no large backing; all borrowed sources must outlive emission. */
fm1_state_writer_t *fm1_state_json_project_writer(void *memory,
    const fm1_state_names_t *names, const fm1_state_json_project_t *source,
    fm1_midi_map_t *validation_map, fm1_put_t put, void *ctx, fm1_state_report_t *report);
/* Collection END validates only; emit may repeat while the source is stable.
 * A fresh report seeded with collection counters preserves host accounting. */
int fm1_state_json_project_emit(fm1_state_writer_t *writer, fm1_put_t put,
                                void *ctx, fm1_state_report_t *report);
#endif

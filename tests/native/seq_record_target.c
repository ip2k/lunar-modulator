/* Compile the real record adapter with the device compiler. */
#include "state_seq_export.h"
int fm1_seq_record_target(const fm1_seq_t *seq, fm1_rec_sink_t sink, void *ctx) {
    return fm1_state_seq_export(seq, sink, ctx);
}

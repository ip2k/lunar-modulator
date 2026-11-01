/* MIT: sequencer text fragments as the state codec's SET line records. */
#ifndef FM1_STATE_SEQ_EXPORT_H
#define FM1_STATE_SEQ_EXPORT_H
#include "fm1_seq.h"
#include "fm1_state.h"
#include <string.h>

typedef struct {
    fm1_rec_sink_t sink;
    void *ctx;
    unsigned open;
} fm1_state_seq_export_t;

static inline int fm1_state_seq_fragment(void *ctx, const char *text, size_t n) {
    fm1_state_seq_export_t *e = (fm1_state_seq_export_t *)ctx;
    while (n) {
        size_t part = 0;
        fm1_rec_t r;
        while (part < n && text[part] != '\n') ++part;
        memset(&r, 0, sizeof r);
        r.type = FM1_REC_LINE;
        r.u.line.which = FM1_LINES_SET;
        r.u.line.s = text;
        if (part) {
            r.piece = e->open ? 0 : FM1_REC_FIRST;
            r.u.line.n = (uint32_t)part;
            if (!e->sink(e->ctx, &r)) return -1;
            e->open = 1;
            text += part; n -= part;
        }
        if (n) { /* Complete the line without including the newline byte. */
            r.piece = FM1_REC_LAST | (e->open ? 0 : FM1_REC_FIRST);
            r.u.line.n = 0;
            r.u.line.s = text;
            if (!e->sink(e->ctx, &r)) return -1;
            e->open = 0;
            ++text; --n;
        }
    }
    return 0;
}

/* Emit SET line records only: the caller emits HEAD/END and owns the writer.
 * Returns 1 on complete export, 0 on invalid arguments or record refusal.
 * No whole-set or line buffer, allocation, application mutation or rollback.
 * Sink consumes each ephemeral record/text synchronously, returning 1 on
 * success and 0 on refusal. On failure discard the enclosing transaction.
 * Keep seq stable throughout; main-task-only when used with application state.
 * The downstream codec's line/file limits and scratch requirements still apply. */
static inline int fm1_state_seq_export(const fm1_seq_t *seq,
                                       fm1_rec_sink_t sink, void *ctx) {
    fm1_state_seq_export_t e = { sink, ctx, 0 };
    size_t length;
    if (!seq || !sink) return 0;
    if (fm1_seq_export_movy1_stream(seq, fm1_state_seq_fragment, &e, &length)) return 0;
    /* The formatter always emits a trailing newline. Refuse an incomplete
     * line rather than letting a downstream writer commit partial records. */
    return !e.open;
}
#endif

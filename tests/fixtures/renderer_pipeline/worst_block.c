/* Worst-block recorder under synthetic ticks: selection, wrap, faults, report. */
#include <assert.h>
#include <stdio.h>   /* the header leaves printf to its includer, as the SDK does */
#include "renderer_pipeline_worst.h"

static lunar_worst_t w;
static lunar_worst_marks_t m;

/* One produced block: begin, six marks at begin+offsets, end. */
static int block(unsigned c, uint32_t tag, uint32_t begin, const uint32_t at[6], uint32_t end, uint32_t ready) {
    lunar_worst_begin(&m, begin);
    for (unsigned i = 0; i < LUNAR_WORST_MARKS; ++i) lunar_worst_mark(&m, i, begin + at[i]);
    return lunar_worst_end(&w, &m, c, tag, begin + end, ready);
}

int main(void) {
    static const uint32_t plain[6] = {100, 150, 300, 20000, 24000, 25000};
    static const uint32_t spike[6] = {100, 150, 300, 20000, 24000, 39000};
    lunar_worst_reset(&w, &m);
    /* The first block of a case is always recorded, later ones only when larger. */
    assert(block(0, 0, 1000, plain, 26000, 8));
    assert(!block(0, 1, 50000, plain, 25999, 7));
    assert(block(0, 2, 90000, spike, 40000, 6));
    lunar_worst_consumer(&w, 0, 1, 31000);
    assert(!w.worst[0].c_seen);
    lunar_worst_consumer(&w, 0, 2, 32000);
    assert(w.worst[0].c_seen && w.worst[0].c_ticks == 32000);
    assert(w.worst[0].complete && w.worst[0].tag == 2 && w.worst[0].p_ticks == 40000 && w.worst[0].ready == 6);
    assert(w.worst[0].stage[0] == 100 && w.worst[0].stage[3] == 19700 && w.worst[0].stage[5] == 15000 &&
           w.worst[0].stage[6] == 1000);
    /* Timer wrap inside the block still telescopes to p_ticks. */
    assert(block(1, 5513, 0xFFFFF000u, plain, 30000, 5));
    uint32_t sum = 0;
    for (unsigned i = 0; i < LUNAR_WORST_STAGES; ++i) sum += w.worst[1].stage[i];
    assert(w.worst[1].complete && sum == 30000 && w.worst[1].p_ticks == 30000);
    lunar_worst_consumer(&w, 1, 5513, 33000);
    /* A missing mark: recorded as incomplete, never with invented stages. */
    lunar_worst_begin(&m, 7000);
    for (unsigned i = 0; i < LUNAR_WORST_MARKS; ++i) if (i != 2) lunar_worst_mark(&m, i, 7000 + plain[i]);
    assert(lunar_worst_end(&w, &m, 2, 11026, 7000 + 27000, 4));
    assert(!w.worst[2].complete && w.incomplete == 1 && !w.worst[2].stage[0]);
    lunar_worst_consumer(&w, 2, 11026, 30000);
    /* Marks out of order (a stale mark from before begin) are refused. */
    static const uint32_t stale[6] = {100, 150, 300, 20000, 24000, 25000};
    lunar_worst_begin(&m, 9000);
    for (unsigned i = 0; i < LUNAR_WORST_MARKS; ++i) lunar_worst_mark(&m, i, 9000 + stale[i]);
    m.t[4] = 8000;
    assert(lunar_worst_end(&w, &m, 3, 16539, 9000 + 26000, 3));
    assert(!w.worst[3].complete && w.misordered == 1);
    lunar_worst_mark(&m, 6, 1);
    assert(m.out_of_range == 1);
    /* Consumer maxima are kept per case by their own tag. */
    lunar_worst_consumer(&w, 3, 16540, 34000);
    lunar_worst_consumer(&w, 3, 16541, 33000);
    lunar_worst_consumer(&w, 9, 1, 1);
    assert(w.cmax[3] == 34000 && w.cmax_tag[3] == 16541 && w.unmatched_consumer == 1);
    assert(w.blocks == 6 && sizeof w.worst == 256);
    lunar_worst_report(&w, 256, 7, 3);
    return 0;
}

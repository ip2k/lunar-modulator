/* SPDX-License-Identifier: MIT. Per-case worst producer block, stage vector only.
 *
 * CPU0 producer task only (marks, end) plus the CPU0 harvest (consumer);
 * no IRQ access, no allocation, no SDK dependency. One mark is a timer read at
 * an existing stage boundary of the sealed producer block:
 *
 *   begin | controls | preflight | seq | dispatch | inserts | capture | ui | end
 *
 * begin and end are the producer's existing p_ticks reads; the six marks in
 * between are the only new timer reads, so a block costs eight reads in all.
 * Only each case's max-p_ticks block is kept: tag, totals, queue depth and the
 * seven stage deltas (64 bytes per case, 256 for the four cases). Deltas telescope, so their
 * unsigned sum equals p_ticks across a 24 MHz timer wrap. A block missing any
 * mark is recorded with complete=0 and zero stages, never silently mixed.
 *
 * printf must already be declared by the includer: the SDK build gets it from
 * system/includes.h, whose utils/fs/fs.h defines its own FILE, so newlib's
 * <stdio.h> must not be pulled in here (it fails the vendor pi32v2 compile). */
#ifndef LUNAR_RENDERER_PIPELINE_WORST_H
#define LUNAR_RENDERER_PIPELINE_WORST_H
#include <stdint.h>
#include <string.h>

#define LUNAR_WORST_MARKS 6u
#define LUNAR_WORST_STAGES (LUNAR_WORST_MARKS + 1u)
#define LUNAR_WORST_CASES 4u
#define LUNAR_WORST_ALL_MARKS ((1u << LUNAR_WORST_MARKS) - 1u)

/* Stage i ends at mark i (i < 6) or at the producer's end read (i == 6). */
static const char *const lunar_worst_stage_names[LUNAR_WORST_STAGES] = {
    "controls", "preflight", "seq", "dispatch", "inserts", "capture", "ui"};

typedef struct {
    uint32_t valid, complete, tag, p_ticks, c_ticks, c_seen, ready;
    uint32_t stage[LUNAR_WORST_STAGES];
    uint32_t reserved[2]; /* keeps the record at sixteen words, 64 bytes */
} lunar_worst_block_t;

typedef struct {
    uint32_t begin, seen, out_of_range;
    uint32_t t[LUNAR_WORST_MARKS];
} lunar_worst_marks_t;

typedef struct {
    lunar_worst_block_t worst[LUNAR_WORST_CASES];
    uint32_t cmax[LUNAR_WORST_CASES], cmax_tag[LUNAR_WORST_CASES];
    uint32_t blocks, incomplete, misordered, unmatched_consumer;
} lunar_worst_t;

/* begin and mark run inside the timed block: forced inline, so a caller placed
 * in RAM (.volatile_ram_code) does not call out to a flash (XIP) copy. */
#if defined(__GNUC__) || defined(__clang__)
#define LUNAR_WORST_HOT static inline __attribute__((always_inline))
#else
#define LUNAR_WORST_HOT static inline
#endif

typedef char lunar_worst_block_is_64_bytes[sizeof(lunar_worst_block_t) == 64u ? 1 : -1];

static inline void lunar_worst_reset(lunar_worst_t *w, lunar_worst_marks_t *m) {
    memset(w, 0, sizeof *w);
    memset(m, 0, sizeof *m);
}

LUNAR_WORST_HOT void lunar_worst_begin(lunar_worst_marks_t *m, uint32_t begin) {
    m->begin = begin;
    m->seen = 0;
}

LUNAR_WORST_HOT void lunar_worst_mark(lunar_worst_marks_t *m, unsigned point, uint32_t tick) {
    if (point >= LUNAR_WORST_MARKS) { ++m->out_of_range; return; }
    m->t[point] = tick;
    m->seen |= 1u << point;
}

/* Cheap test on every block: only a new per-case maximum is recorded. */
static inline int lunar_worst_exceeds(const lunar_worst_t *w, unsigned c, uint32_t p_ticks) {
    return c < LUNAR_WORST_CASES && (!w->worst[c].valid || p_ticks > w->worst[c].p_ticks);
}

/* Counts every observed block; records stage deltas only for a new max. */
static inline int lunar_worst_end(lunar_worst_t *w, const lunar_worst_marks_t *m, unsigned c,
                                  uint32_t tag, uint32_t end, uint32_t ready) {
    uint32_t total = end - m->begin;
    ++w->blocks;
    if (m->seen != LUNAR_WORST_ALL_MARKS) ++w->incomplete;
    if (!lunar_worst_exceeds(w, c, total)) return 0;
    lunar_worst_block_t *b = &w->worst[c];
    memset(b, 0, sizeof *b);
    b->valid = 1; b->tag = tag; b->p_ticks = total; b->ready = ready;
    if (m->seen == LUNAR_WORST_ALL_MARKS) {
        uint32_t previous = m->begin, sum = 0;
        int ordered = 1;
        for (unsigned i = 0; i < LUNAR_WORST_STAGES; ++i) {
            uint32_t at = i < LUNAR_WORST_MARKS ? m->t[i] : end;
            uint32_t delta = at - previous;
            /* A mark outside [begin, end] shows up as a delta beyond the total. */
            if (delta > total || sum + delta > total) ordered = 0;
            b->stage[i] = delta; sum += delta; previous = at;
        }
        if (ordered && sum == total) b->complete = 1;
        else { ++w->misordered; memset(b->stage, 0, sizeof b->stage); }
    }
    return 1;
}

/* Harvest side: attach the consumer ticks of the recorded producer block, and
 * keep each case's own consumer maximum (tag + ticks only; CPU1 stages are not
 * instrumented). A harvest is always later than its own production. */
static inline void lunar_worst_consumer(lunar_worst_t *w, unsigned c, uint32_t tag, uint32_t c_ticks) {
    if (c >= LUNAR_WORST_CASES) { ++w->unmatched_consumer; return; }
    lunar_worst_block_t *b = &w->worst[c];
    if (b->valid && b->tag == tag) { b->c_ticks = c_ticks; b->c_seen = 1; }
    if (c_ticks > w->cmax[c] || !w->cmax_tag[c]) { w->cmax[c] = c_ticks; w->cmax_tag[c] = tag + 1u; }
}

/* UART report. cmax_tag is stored +1 so that zero means "none observed".
 * overhead_* are on-target self-measurements of this recorder (see caller). */
static inline void lunar_worst_report(const lunar_worst_t *w, uint32_t reps,
                                      uint32_t mark_ticks, uint32_t observe_ticks) {
    for (unsigned c = 0; c < LUNAR_WORST_CASES; ++c) {
        const lunar_worst_block_t *b = &w->worst[c];
        printf("LUNAR_WORST_BLOCK case=%u valid=%u complete=%u tag=%u p_ticks=%u c_ticks=%u c_seen=%u ready=%u",
               c, (unsigned)b->valid, (unsigned)b->complete, (unsigned)b->tag, (unsigned)b->p_ticks,
               (unsigned)b->c_ticks, (unsigned)b->c_seen, (unsigned)b->ready);
        for (unsigned i = 0; i < LUNAR_WORST_STAGES; ++i)
            printf(" %s=%u", lunar_worst_stage_names[i], (unsigned)b->stage[i]);
        printf("\n");
        printf("LUNAR_WORST_CONSUMER case=%u seen=%u tag=%u c_ticks=%u\n", c,
               w->cmax_tag[c] ? 1u : 0u, w->cmax_tag[c] ? (unsigned)(w->cmax_tag[c] - 1u) : 0u,
               (unsigned)w->cmax[c]);
    }
    printf("LUNAR_WORST_SUMMARY marks=%u stages=%u blocks=%u incomplete=%u misordered=%u unmatched=%u "
           "record_bytes=%u reps=%u overhead_mark_ticks=%u overhead_observe_ticks=%u\n",
           LUNAR_WORST_MARKS, LUNAR_WORST_STAGES, (unsigned)w->blocks, (unsigned)w->incomplete,
           (unsigned)w->misordered, (unsigned)w->unmatched_consumer, (unsigned)sizeof w->worst,
           (unsigned)reps, (unsigned)mark_ticks, (unsigned)observe_ticks);
}
#endif

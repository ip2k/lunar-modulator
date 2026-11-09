/* SPDX-License-Identifier: MIT. Lunar fail-open boot core; see failopen_core.h. */
#include "failopen_core.h"

uint32_t lunar_failopen_check(const struct lunar_failopen_record *r)
{
    const uint32_t words[7] = {r->magic, r->build_id, r->count, r->boots,
                               r->last_reason, r->fault, r->flags};
    uint32_t h = 2166136261u;
    unsigned i, b;
    for (i = 0; i < 7; ++i)
        for (b = 0; b < 4; ++b) {
            h ^= (words[i] >> (8 * b)) & 0xffu;
            h *= 16777619u;
        }
    return h;
}

int lunar_failopen_valid(const struct lunar_failopen_record *r)
{
    return r->magic == LUNAR_FAILOPEN_MAGIC && r->check == lunar_failopen_check(r);
}

void lunar_failopen_seal(struct lunar_failopen_record *r)
{
    r->check = lunar_failopen_check(r);
}

static void restart(struct lunar_failopen_record *r, uint32_t build_id)
{
    r->magic = LUNAR_FAILOPEN_MAGIC;
    r->build_id = build_id;
    r->count = 0;
    r->boots = 0;
    r->last_reason = 0;
    r->fault = LUNAR_FAILOPEN_FAULT_NONE;
    r->flags = 0;
}

enum lunar_failopen_decision lunar_failopen_boot(struct lunar_failopen_record *r,
        uint32_t build_id, uint32_t reason, uint32_t limit,
        enum lunar_failopen_start *start)
{
    enum lunar_failopen_start found = LUNAR_FAILOPEN_CONTINUED;
    enum lunar_failopen_decision decision;
    if (!lunar_failopen_valid(r))
        found = LUNAR_FAILOPEN_FRESH_INVALID;
    else if (reason & LUNAR_FAILOPEN_REASON_COLD)
        found = LUNAR_FAILOPEN_FRESH_COLD;
    else if (r->build_id != build_id)
        found = LUNAR_FAILOPEN_FRESH_BUILD;
    if (found != LUNAR_FAILOPEN_CONTINUED)
        restart(r, build_id);
    if (limit == 0)
        limit = 1;
    if (r->boots != UINT32_MAX)
        ++r->boots;
    r->last_reason = reason;
    r->flags &= ~(LUNAR_FAILOPEN_FLAG_HEALTHY | LUNAR_FAILOPEN_FLAG_KEY);
    if (r->count >= limit) {
        decision = LUNAR_FAILOPEN_FALLBACK;   /* sticky; count is not raised */
    } else {
        ++r->count;
        decision = LUNAR_FAILOPEN_RUN;
        r->fault = LUNAR_FAILOPEN_FAULT_NONE;  /* the old fault was reported */
    }
    lunar_failopen_seal(r);
    if (start)
        *start = found;
    return decision;
}

int lunar_failopen_claim_early(struct lunar_failopen_record *r)
{
    if (r->flags & LUNAR_FAILOPEN_FLAG_EARLY_TRIED)
        return 0;
    r->flags |= LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
    lunar_failopen_seal(r);
    return 1;
}

void lunar_failopen_mark_healthy(struct lunar_failopen_record *r)
{
    r->count = 0;
    r->fault = LUNAR_FAILOPEN_FAULT_NONE;
    r->flags = (r->flags | LUNAR_FAILOPEN_FLAG_HEALTHY) & ~LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
    lunar_failopen_seal(r);
}

void lunar_failopen_note_fault(struct lunar_failopen_record *r, uint32_t fault)
{
    r->fault = fault;
    lunar_failopen_seal(r);
}

void lunar_failopen_note_key(struct lunar_failopen_record *r)
{
    r->flags |= LUNAR_FAILOPEN_FLAG_KEY;
    lunar_failopen_seal(r);
}

void lunar_failopen_monitor_init(struct lunar_failopen_monitor *m, uint32_t now_ms,
                                 uint32_t healthy_ms)
{
    unsigned i;
    m->start_ms = now_ms;
    m->healthy_ms = healthy_ms;
    m->slots = 0;
    m->healthy_reported = 0;
    for (i = 0; i < LUNAR_FAILOPEN_SLOTS; ++i) {
        m->timeout_ms[i] = 0;
        m->last_ms[i] = now_ms;
        m->beats[i] = 0;
    }
}

int lunar_failopen_monitor_add(struct lunar_failopen_monitor *m, uint32_t timeout_ms,
                               uint32_t now_ms)
{
    uint32_t slot = m->slots;
    if (slot >= LUNAR_FAILOPEN_SLOTS || timeout_ms == 0)
        return -1;
    /* Publish the slot first with timeout 0 (skipped by poll), then fill it. */
    m->timeout_ms[slot] = 0;
    m->slots = slot + 1;
    m->last_ms[slot] = now_ms;
    m->beats[slot] = 0;
    m->timeout_ms[slot] = timeout_ms;
    return (int)slot;
}

void lunar_failopen_monitor_beat(struct lunar_failopen_monitor *m, int slot, uint32_t now_ms)
{
    if (slot < 0 || (uint32_t)slot >= m->slots)
        return;
    m->last_ms[slot] = now_ms;
    m->beats[slot] = m->beats[slot] + 1;
}

enum lunar_failopen_verdict lunar_failopen_monitor_poll(struct lunar_failopen_monitor *m,
        uint32_t now_ms, int *stalled_slot)
{
    uint32_t i;
    int all_seen;
    uint32_t slots = m->slots;
    all_seen = slots > 0;
    for (i = 0; i < slots; ++i) {
        uint32_t timeout = m->timeout_ms[i];
        if (!timeout) {                  /* registration still in progress */
            all_seen = 0;
            continue;
        }
        if ((uint32_t)(now_ms - m->last_ms[i]) > timeout) {
            if (stalled_slot)
                *stalled_slot = (int)i;
            return LUNAR_FAILOPEN_STALLED;
        }
        if (!m->beats[i])
            all_seen = 0;
    }
    if (!m->healthy_reported && all_seen &&
            (uint32_t)(now_ms - m->start_ms) >= m->healthy_ms) {
        m->healthy_reported = 1;
        return LUNAR_FAILOPEN_HEALTHY;
    }
    return LUNAR_FAILOPEN_WAIT;
}

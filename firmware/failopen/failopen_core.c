/* SPDX-License-Identifier: MIT. Lunar fail-open boot core; see failopen_core.h. */
#include "failopen_core.h"

/* The linker reserves 64 bytes for the record (prepare-failopen-devkit.py). */
typedef char lunar_failopen_record_fits[sizeof(struct lunar_failopen_record) <= 64 ? 1 : -1];

#define FNV_OFFSET 2166136261u
#define FNV_PRIME 16777619u
#define RECORD_WORDS 8u

uint32_t lunar_failopen_image_id(const void *data, uint32_t len)
{
    const unsigned char *p = (const unsigned char *)data;
    uint32_t h = FNV_OFFSET;
    while (len--) {
        h ^= *p++;
        h *= FNV_PRIME;
    }
    return h ? h : 1u;
}

uint32_t lunar_failopen_check(const struct lunar_failopen_record *r)
{
    const uint32_t words[RECORD_WORDS] = {r->magic, r->image_id, r->count, r->boots,
                                          r->cycles, r->last_reason, r->fault, r->flags};
    uint32_t h = FNV_OFFSET;
    unsigned i, b;
    for (i = 0; i < RECORD_WORDS; ++i)
        for (b = 0; b < 4; ++b) {
            h ^= (words[i] >> (8 * b)) & 0xffu;
            h *= FNV_PRIME;
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

static void restart(struct lunar_failopen_record *r, uint32_t image_id)
{
    r->magic = LUNAR_FAILOPEN_MAGIC;
    r->image_id = image_id;
    r->count = 0;
    r->boots = 0;
    r->cycles = 0;
    r->last_reason = 0;
    r->fault = LUNAR_FAILOPEN_FAULT_NONE;
    r->flags = 0;
}

static uint32_t up(uint32_t value)
{
    return value == UINT32_MAX ? value : value + 1;
}

enum lunar_failopen_decision lunar_failopen_boot(struct lunar_failopen_record *r,
        uint32_t image_id, uint32_t reason, uint32_t limit,
        enum lunar_failopen_start *start)
{
    enum lunar_failopen_start found = LUNAR_FAILOPEN_CONTINUED;
    enum lunar_failopen_decision decision;
    lunar_failopen_lock();
    if (!lunar_failopen_valid(r))
        found = LUNAR_FAILOPEN_FRESH_INVALID;
    else if (reason & LUNAR_FAILOPEN_REASON_COLD)
        found = LUNAR_FAILOPEN_FRESH_COLD;
    else if (r->image_id != image_id)
        found = LUNAR_FAILOPEN_FRESH_BUILD;
    if (found != LUNAR_FAILOPEN_CONTINUED)
        restart(r, image_id);
    if (limit == 0)
        limit = 1;
    r->boots = up(r->boots);
    r->last_reason = reason;
    r->flags &= ~(LUNAR_FAILOPEN_FLAG_HEALTHY | LUNAR_FAILOPEN_FLAG_KEY |
                  LUNAR_FAILOPEN_FLAG_STABLE);
    if (r->count >= limit || r->cycles >= limit) {
        decision = LUNAR_FAILOPEN_FALLBACK;   /* sticky; nothing is raised */
    } else {
        ++r->count;
        decision = LUNAR_FAILOPEN_RUN;
        r->fault = LUNAR_FAILOPEN_FAULT_NONE;  /* the old fault was reported */
    }
    lunar_failopen_seal(r);
    lunar_failopen_unlock();
    if (start)
        *start = found;
    return decision;
}

int lunar_failopen_claim_early(struct lunar_failopen_record *r)
{
    int claimed = 0;
    lunar_failopen_lock();
    if (!(r->flags & LUNAR_FAILOPEN_FLAG_EARLY_TRIED)) {
        r->flags |= LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
        lunar_failopen_seal(r);
        claimed = 1;
    }
    lunar_failopen_unlock();
    return claimed;
}

void lunar_failopen_mark_healthy(struct lunar_failopen_record *r)
{
    lunar_failopen_lock();
    r->count = 0;
    r->cycles = up(r->cycles);
    r->fault = LUNAR_FAILOPEN_FAULT_NONE;
    r->flags = (r->flags | LUNAR_FAILOPEN_FLAG_HEALTHY) & ~LUNAR_FAILOPEN_FLAG_EARLY_TRIED;
    lunar_failopen_seal(r);
    lunar_failopen_unlock();
}

void lunar_failopen_mark_stable(struct lunar_failopen_record *r)
{
    lunar_failopen_lock();
    r->cycles = 0;
    r->flags |= LUNAR_FAILOPEN_FLAG_STABLE;
    lunar_failopen_seal(r);
    lunar_failopen_unlock();
}

void lunar_failopen_note_fault(struct lunar_failopen_record *r, uint32_t fault)
{
    lunar_failopen_lock();
    r->fault = fault;
    lunar_failopen_seal(r);
    lunar_failopen_unlock();
}

void lunar_failopen_note_key(struct lunar_failopen_record *r)
{
    lunar_failopen_lock();
    r->flags |= LUNAR_FAILOPEN_FLAG_KEY;
    lunar_failopen_seal(r);
    lunar_failopen_unlock();
}

void lunar_failopen_monitor_init(struct lunar_failopen_monitor *m, uint32_t now_ms,
                                 uint32_t healthy_ms, uint32_t stable_ms, uint32_t expected)
{
    unsigned i;
    lunar_failopen_lock();
    m->start_ms = now_ms;
    m->healthy_ms = healthy_ms;
    m->stable_ms = stable_ms;
    m->expected = expected;
    m->refused = 0;
    m->slots = 0;
    m->healthy_reported = 0;
    m->stable_reported = 0;
    for (i = 0; i < LUNAR_FAILOPEN_SLOTS; ++i) {
        m->timeout_ms[i] = 0;
        m->last_ms[i] = now_ms;
        m->beats[i] = 0;
    }
    lunar_failopen_unlock();
}

int lunar_failopen_monitor_add(struct lunar_failopen_monitor *m, uint32_t timeout_ms,
                               uint32_t now_ms)
{
    uint32_t slot;
    lunar_failopen_lock();
    slot = m->slots;
    if (slot >= LUNAR_FAILOPEN_SLOTS || timeout_ms < LUNAR_FAILOPEN_MIN_TIMEOUT_MS) {
        m->refused = up(m->refused);
        lunar_failopen_unlock();
        return -1;
    }
    /* Under the lock no reader sees a half-filled slot; poll still skips a
     * timeout of 0 so a torn record could never read as stalled. */
    m->timeout_ms[slot] = 0;
    m->slots = slot + 1;
    m->last_ms[slot] = now_ms;
    m->beats[slot] = 0;
    m->timeout_ms[slot] = timeout_ms;
    lunar_failopen_unlock();
    return (int)slot;
}

void lunar_failopen_monitor_beat(struct lunar_failopen_monitor *m, int slot, uint32_t now_ms)
{
    lunar_failopen_lock();
    if (slot >= 0 && (uint32_t)slot < m->slots) {
        m->last_ms[slot] = now_ms;
        m->beats[slot] = up(m->beats[slot]);
    }
    lunar_failopen_unlock();
}

enum lunar_failopen_verdict lunar_failopen_monitor_poll(struct lunar_failopen_monitor *m,
        uint32_t now_ms, int *stalled_slot)
{
    enum lunar_failopen_verdict verdict = LUNAR_FAILOPEN_WAIT;
    uint32_t i, slots, elapsed;
    int all_seen;
    lunar_failopen_lock();
    slots = m->slots;
    elapsed = now_ms - m->start_ms;
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
            verdict = LUNAR_FAILOPEN_STALLED;
            goto done;
        }
        if (!m->beats[i])
            all_seen = 0;
    }
    if (elapsed < m->healthy_ms)
        goto done;
    /* From the healthy time on, for the rest of the boot: a late extra slot
     * or a late refusal would otherwise leave a task unwatched. */
    if (m->refused || m->expected == 0 || slots != m->expected) {
        verdict = LUNAR_FAILOPEN_UNREGISTERED;
    } else if (m->healthy_reported) {
        if (!m->stable_reported && elapsed >= m->stable_ms) {
            m->stable_reported = 1;
            verdict = LUNAR_FAILOPEN_STABLE;
        }
    } else if (all_seen) {
        m->healthy_reported = 1;
        verdict = LUNAR_FAILOPEN_HEALTHY;
    }
done:
    lunar_failopen_unlock();
    return verdict;
}

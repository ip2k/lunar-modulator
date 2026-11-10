/* SPDX-License-Identifier: MIT
 * M6 RAM image core (m6_core.h). Written for this project; the voice is
 * a small two-operator FM pair on the trunc12 sine, not msfa code.
 */
#include "m6_core.h"

#include "m6_sine.h"

/* Phase increments for A3, C#4, E4, A4 at the nominal 44,118 Hz: round(f *
 * 2^32 / 44118), f in mHz. Constant-folded; no 64-bit arithmetic at run time. */
#define INC(mhz) ((uint32_t)((((uint64_t)(mhz) << 32) + 22059000ull) / 44118000ull))
static const uint32_t note_inc[4] = {
    INC(220000), INC(277183), INC(329628), INC(440000)
};

int32_t lunar_m6_sine(uint32_t phase)
{
    uint32_t index = phase >> 20;          /* the top 12 bits, as trunc12 */
    uint32_t point = index & 1023u;
    int32_t value = lunar_m6_sine_quarter[(index & 1024u) ? 1023u - point : point];
    return (index & 2048u) ? -value : value;
}

void lunar_m6_voice_init(struct lunar_m6_voice *v)
{
    v->carrier = v->modulator = 0;
    v->env = 0;
    v->note = v->block_in_note = 0;
    v->attack = 1;
}

void lunar_m6_voice_render(struct lunar_m6_voice *v, int32_t *words)
{
    unsigned i;
    const uint32_t inc = note_inc[v->note & 3u];
    const int32_t top = (int32_t)LUNAR_M6_LEVEL << 16;
    const int32_t step = top / LUNAR_M6_ATTACK;
    if (v->block_in_note == 0) v->attack = 1;
    for (i = 0; i < LUNAR_M6_FRAMES; ++i) {
        int32_t gain, mod, out;
        if (v->attack) {
            v->env += step;
            if (v->env >= top) {
                v->env = top;
                v->attack = 0;
            }
        } else {
            v->env -= v->env >> 13;   /* time constant 8,192 samples, ~0.19 s */
        }
        gain = v->env >> 16;          /* Q15, 0..LUNAR_M6_LEVEL */
        /* depth <= 2^15, so the phase offset is at most a quarter cycle */
        mod = lunar_m6_sine(v->modulator) * (gain << 3);
        /* peak 32,767 * 4,096 / 128 = 1,048,544: -18 dBFS of Q23 */
        out = (lunar_m6_sine(v->carrier + (uint32_t)mod) * gain) >> 7;
        words[2u * i] = out;
        words[2u * i + 1u] = out;
        v->carrier += inc;
        v->modulator += inc << 1;
    }
    if (++v->block_in_note == LUNAR_M6_NOTE_BLOCKS) {
        v->block_in_note = 0;
        v->note = (v->note + 1u) & 3u;
    }
}

uint32_t lunar_m6_hash_words(uint32_t hash, const int32_t *words, unsigned count)
{
    unsigned i;
    for (i = 0; i < count; ++i) hash = (hash ^ (uint32_t)words[i]) * 16777619u;
    return hash;
}

void lunar_m6_status_init(volatile struct lunar_m6_status *s, const char *build_id)
{
    volatile uint32_t *word = (volatile uint32_t *)s;
    unsigned i;
    for (i = 0; i < sizeof *s / 4u; ++i) word[i] = 0;
    s->magic = LUNAR_M6_MAGIC;
    s->layout = LUNAR_M6_LAYOUT;
    s->step = LUNAR_M6_ENTERED;
    s->tick_mod = LUNAR_M6_TIMER_MOD;
    s->render_min = s->interval_min = 0xffffffffu;
    s->pcm_hash = LUNAR_M6_HASH_SEED;
    for (i = 0; build_id && build_id[i] && i < sizeof s->build_id - 1u; ++i)
        s->build_id[i] = build_id[i];
}

void lunar_m6_stopwatch_start(const struct lunar_timer_io *io)
{
    io->write(io->context, LUNAR_TIMER_CON, 1u << 14);
    io->sync(io->context);
    io->write(io->context, LUNAR_TIMER_CNT, 0);
    io->write(io->context, LUNAR_TIMER_PRD, LUNAR_M6_TIMER_PRD);
    io->write(io->context, LUNAR_TIMER_CON, LUNAR_M6_TIMER_RUN);
    io->sync(io->context);
}

uint32_t lunar_m6_tick(const struct lunar_timer_io *io)
{
    return io->read(io->context, LUNAR_TIMER_CNT) % LUNAR_M6_TIMER_MOD;
}

uint32_t lunar_m6_ticks_between(uint32_t then, uint32_t now)
{
    return now >= then ? now - then : now + LUNAR_M6_TIMER_MOD - then;
}

int lunar_m6_stopwatch_alive(const struct lunar_timer_io *io, uint32_t polls)
{
    uint32_t first = io->read(io->context, LUNAR_TIMER_CNT);
    while (polls--)
        if (io->read(io->context, LUNAR_TIMER_CNT) != first) return 1;
    return 0;
}

uint32_t lunar_m6_wait_ticks(const struct lunar_timer_io *io, uint32_t ticks)
{
    uint32_t waited = 0, polls = 0, last = lunar_m6_tick(io);
    while (waited < ticks) {
        uint32_t now = lunar_m6_tick(io);
        waited += lunar_m6_ticks_between(last, now);
        last = now;
        ++polls;
    }
    return polls;
}

void lunar_m6_on_boundary(struct lunar_m6 *m, uint32_t now, uint32_t half)
{
    volatile struct lunar_m6_status *s = m->status;
    /* The first boundary is seen only after ALNK0's settle delay, which spans
     * several blocks, so the interval to the second boundary is short and is
     * not counted; intervals count from the third boundary on. */
    if (m->have_last == 2u) {
        uint32_t interval = lunar_m6_ticks_between(m->last_tick, now);
        int missed = half == m->last_half;
        if (s->blocks >= 8u && s->interval_min != 0xffffffffu &&
            interval > s->interval_min + (s->interval_min >> 1))
            missed = 1;
        if (missed) ++s->missed;
        s->interval_last = interval;
        if (interval < s->interval_min) s->interval_min = interval;
        if (interval > s->interval_max) s->interval_max = interval;
        m->acc_interval += interval;
    }
    else ++m->have_last;
    m->last_tick = now;
    m->last_half = half;
}

void lunar_m6_on_rendered(struct lunar_m6 *m, uint32_t start, uint32_t rendered)
{
    volatile struct lunar_m6_status *s = m->status;
    uint32_t render = lunar_m6_ticks_between(start, rendered);
    s->render_last = render;
    if (render < s->render_min) s->render_min = render;
    if (render > s->render_max) s->render_max = render;
    m->acc_render += render;
    ++s->blocks;
    if (++m->acc_blocks == LUNAR_M6_WINDOW) {
        s->win_render = m->acc_render;
        s->win_interval = m->acc_interval;
        ++s->windows;
        m->acc_blocks = m->acc_render = m->acc_interval = 0;
    }
}

void lunar_m6_on_done(struct lunar_m6 *m, uint32_t start, uint32_t done, int pending_again)
{
    volatile struct lunar_m6_status *s = m->status;
    uint32_t busy = lunar_m6_ticks_between(start, done);
    if (busy > s->busy_max) s->busy_max = busy;
    if (pending_again) ++s->late;
}

int lunar_m6_slack_left(const struct lunar_m6 *m, uint32_t start, uint32_t now)
{
    const volatile struct lunar_m6_status *s = m->status;
    if (s->blocks < 8u || s->interval_min == 0xffffffffu) return 0;
    return lunar_m6_ticks_between(start, now) < (s->interval_min >> 1);
}

/* The core's ALNK0 ops forward register access to the platform's and
 * supply a polled IRQ stub and a stopwatch delay; context is the run. */
static uint32_t fwd_read(void *context, uint32_t address, unsigned bytes)
{
    const struct lunar_alnk0_ops *p = ((struct lunar_m6 *)context)->platform->alnk0;
    return p->read(p->context, address, bytes);
}

static void fwd_write(void *context, uint32_t address, unsigned bytes, uint32_t value)
{
    const struct lunar_alnk0_ops *p = ((struct lunar_m6 *)context)->platform->alnk0;
    p->write(p->context, address, bytes, value);
}

static void fwd_sync(void *context)
{
    const struct lunar_alnk0_ops *p = ((struct lunar_m6 *)context)->platform->alnk0;
    p->sync(p->context);
}

static int stub_attach(void *context, unsigned irq, unsigned priority)
{
    (void)context; (void)irq; (void)priority;
    return 0;   /* polled: nothing is enabled or routed */
}

static int stopwatch_delay(void *context, unsigned ms)
{
    lunar_m6_wait_ticks(((struct lunar_m6 *)context)->platform->timer,
                        ms * LUNAR_M6_TICKS_PER_MS_UPPER);
    return 0;
}

/* Poll for channel 3's boundary for at most `timeout` ticks; 1 when seen. */
static int wait_boundary(const struct lunar_alnk0_ops *ops, const struct lunar_timer_io *timer,
                         uint32_t timeout, uint32_t *at)
{
    uint32_t waited = 0, last = lunar_m6_tick(timer);
    for (;;) {
        uint32_t now = lunar_m6_tick(timer);
        if (lunar_alnk0_pending(ops) & (1u << LUNAR_ALNK0_TX_CH)) {
            *at = now;
            return 1;
        }
        waited += lunar_m6_ticks_between(last, now);
        last = now;
        if (waited >= timeout) return 0;
    }
}

int lunar_m6_run(struct lunar_m6 *m, const struct lunar_m6_platform *p,
                 int32_t *buffer, uint32_t dma_address, uint32_t max_blocks)
{
    volatile struct lunar_m6_status *s = m->status;
    struct lunar_alnk0_ops ops;
    struct lunar_alnk0_config config;
    const struct lunar_timer_io *timer;
    uint32_t start, first = 1;
    int end;
    if (!s || !p || !p->alnk0 || !p->timer || !p->report || !buffer) return LUNAR_M6_END_ARGS;
    timer = p->timer;
    m->platform = p;
    m->buffer = buffer;
    m->dma_address = dma_address;
    m->have_last = m->acc_blocks = m->acc_render = m->acc_interval = 0;
    lunar_m6_voice_init(&m->voice);

    /* Polled ALNK0. Member-wise: JieLi lowers struct assignment to memcpy. */
    ops.context = m;
    ops.read = fwd_read;
    ops.write = fwd_write;
    ops.sync = fwd_sync;
    ops.attach_irq = stub_attach;
    ops.delay_ms = stopwatch_delay;
    lunar_alnk0_default_config(&config, buffer, dma_address);

    start = lunar_m6_tick(timer);
    s->alnk0_result = lunar_alnk0_start(&ops, &config);
    if (s->alnk0_result != LUNAR_ALNK0_OK) {
        s->flags |= LUNAR_M6_FLAG_ALNK0_FAILED;
        s->end = LUNAR_M6_END_ALNK0;
        return LUNAR_M6_END_ALNK0;
    }
    s->step = LUNAR_M6_ALNK0_OK;

    for (;;) {
        uint32_t at, rendered, half;
        int32_t *words;
        if (!wait_boundary(&ops, timer,
                           (first ? LUNAR_M6_FIRST_TIMEOUT_MS : LUNAR_M6_STALL_TIMEOUT_MS)
                               * LUNAR_M6_TICKS_PER_MS_UPPER, &at)) {
            s->flags |= first ? LUNAR_M6_FLAG_NO_CLOCK : LUNAR_M6_FLAG_STALL;
            end = first ? LUNAR_M6_END_NO_CLOCK : LUNAR_M6_END_STALL;
            break;
        }
        if (first) {
            /* the settle delay sits inside this wait; it bounds first_wait below */
            s->first_wait = lunar_m6_ticks_between(start, at);
            s->step = LUNAR_M6_FIRST_BLOCK;
            first = 0;
        }
        half = lunar_alnk0_free_half(&ops);
        lunar_alnk0_ack(&ops, 1u << LUNAR_ALNK0_TX_CH);
        lunar_m6_on_boundary(m, at, half);

        words = buffer + half * LUNAR_M6_HALF_WORDS;
        lunar_m6_voice_render(&m->voice, words);
        if (s->pcm_hash_blocks < LUNAR_M6_HASH_BLOCKS) {
            s->pcm_hash = lunar_m6_hash_words(s->pcm_hash, words, LUNAR_M6_HALF_WORDS);
            if (++s->pcm_hash_blocks == LUNAR_M6_HASH_BLOCKS) s->step = LUNAR_M6_HASHED;
        }
        rendered = lunar_m6_tick(timer);
        lunar_m6_on_rendered(m, at, rendered);
        if (p->kick && (s->blocks & (LUNAR_M6_KICK_BLOCKS - 1u)) == 0u) p->kick(p->context);

        while (lunar_m6_slack_left(m, at, lunar_m6_tick(timer)) && p->report(p->context)) {}
        lunar_m6_on_done(m, at, lunar_m6_tick(timer),
                         (lunar_alnk0_pending(&ops) & (1u << LUNAR_ALNK0_TX_CH)) != 0u);

        if (max_blocks && s->blocks >= max_blocks) {
            end = LUNAR_M6_END_DONE;
            s->step = LUNAR_M6_FINISHED;
            break;
        }
    }
    lunar_alnk0_stop(&ops);
    s->end = (uint32_t)end;
    return end;
}

int lunar_m6_kit_masks(uint32_t address)
{
    return address == LUNAR_PORTC_OUT || address == LUNAR_PORTC_DIR ||
           address == LUNAR_PORTC_PU || address == LUNAR_PORTC_PD;
}

unsigned lunar_m6_put_u(char *out, unsigned room, uint32_t value)
{
    char digits[10];
    unsigned n = 0, written = 0;
    do {
        digits[n++] = (char)('0' + value % 10u);
        value /= 10u;
    } while (value && n < sizeof digits);
    while (n && written < room) out[written++] = digits[--n];
    return written;
}

unsigned lunar_m6_put_hex(char *out, unsigned room, uint32_t value)
{
    static const char hex[] = "0123456789ABCDEF";
    unsigned i;
    for (i = 0; i < 8u && i < room; ++i) out[i] = hex[(value >> (28u - 4u * i)) & 15u];
    return i;
}

uint32_t lunar_m6_fs_estimate(uint32_t win_interval, uint32_t tick_hz)
{
    /* fs = 64 * WINDOW * tick_hz / win_interval, with the window mean held
     * in 1/16 ticks so every product fits 32 bits for tick_hz <= 4 MHz. */
    uint32_t mean16 = win_interval >> 6;
    if (!mean16 || tick_hz > 4000000u) return 0;
    return (tick_hz * 1024u + (mean16 >> 1)) / mean16;
}

uint32_t lunar_m6_load_permille(uint32_t win_render, uint32_t win_interval)
{
    while (win_render > 4000000u || win_interval > 4000000u) {
        win_render >>= 1;
        win_interval >>= 1;
    }
    if (!win_interval) return 0;
    return (win_render * 1000u + (win_interval >> 1)) / win_interval;
}

static unsigned put_s(char *out, unsigned room, const char *s)
{
    unsigned n = 0;
    while (s[n] && n < room) {
        out[n] = s[n];
        ++n;
    }
    return n;
}

unsigned lunar_m6_format_window(const volatile struct lunar_m6_status *s,
                                char *out, unsigned room)
{
    unsigned n = 0;
    if (!out || !room) return 0;
    --room;   /* the NUL */
    n += put_s(out + n, room - n, "M6 win=");
    n += lunar_m6_put_u(out + n, room - n, s->windows);
    n += put_s(out + n, room - n, " blk=");
    n += lunar_m6_put_u(out + n, room - n, s->blocks);
    n += put_s(out + n, room - n, " render=");
    n += lunar_m6_put_u(out + n, room - n, s->win_render);
    n += put_s(out + n, room - n, " interval=");
    n += lunar_m6_put_u(out + n, room - n, s->win_interval);
    n += put_s(out + n, room - n, " busy_max=");
    n += lunar_m6_put_u(out + n, room - n, s->busy_max);
    n += put_s(out + n, room - n, " late=");
    n += lunar_m6_put_u(out + n, room - n, s->late);
    n += put_s(out + n, room - n, " missed=");
    n += lunar_m6_put_u(out + n, room - n, s->missed);
    n += put_s(out + n, room - n, "\r\n");
    out[n] = 0;
    return n;
}

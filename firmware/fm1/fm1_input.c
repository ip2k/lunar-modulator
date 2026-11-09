/* SPDX-License-Identifier: MIT
 * FM-1 application input (fm1_input.h). Portable C99.
 * USB-MIDI packet decoding follows the USB Device Class Definition for MIDI
 * Devices 1.0, section 4 (Code Index Numbers); written from the
 * specification, no code copied.
 */
#include "fm1_input.h"
#include "fm1_panel.h"

#if defined(LUNAR_PI32V2)
#define FENCE() __asm__ __volatile__("csync;" ::: "memory")
#else
#define FENCE() __asm__ __volatile__("" ::: "memory")
#endif

const uint8_t lunar_fm1_button_map[14] = {
    FM1_BTN_OCT_DOWN, FM1_BTN_OCT_UP, FM1_BTN_FX, FM1_BTN_SEL, FM1_BTN_ENV,
    FM1_BTN_LFO, FM1_BTN_EDIT, FM1_BTN_GLO, FM1_BTN_HOME, FM1_BTN_SAVE,
    FM1_BTN_ARP, FM1_BTN_SEQ, FM1_BTN_PLAY, FM1_BTN_REC
};
const uint8_t lunar_fm1_encoder_map[LUNAR_ENCODER_COUNT] = {
    FM1_ENC_SELECT, FM1_ENC_ALGORITHM, FM1_ENC_KNOB1, FM1_ENC_KNOB2,
    FM1_ENC_KNOB3, FM1_ENC_KNOB4, FM1_ENC_PRESETS
};
const int8_t lunar_fm1_encoder_sign[LUNAR_ENCODER_COUNT] = {1, 1, 1, 1, 1, 1, 1};

typedef char lunar_fm1_queue_pow2[(LUNAR_FM1_QUEUE_SIZE & (LUNAR_FM1_QUEUE_SIZE - 1u)) ? -1 : 1];
typedef char lunar_fm1_key_ids[LUNAR_KEY_COUNT == 14u + FM1_APP_KEYS ? 1 : -1];

void lunar_fm1_queue_reset(struct lunar_fm1_queue *q)
{
    if (!q) return;
    q->head = q->tail = q->dropped = 0;
}

int lunar_fm1_queue_push(struct lunar_fm1_queue *q, const struct lunar_fm1_event *e)
{
    uint32_t head;
    if (!q || !e) return 0;
    head = q->head;
    if (head - q->tail >= LUNAR_FM1_QUEUE_SIZE) {
        ++q->dropped;
        return 0;
    }
    q->slot[head & (LUNAR_FM1_QUEUE_SIZE - 1u)] = *e;
    FENCE();          /* the slot is written before the consumer can see it */
    q->head = head + 1u;
    return 1;
}

int lunar_fm1_queue_pop(struct lunar_fm1_queue *q, struct lunar_fm1_event *e)
{
    uint32_t tail;
    if (!q || !e) return 0;
    tail = q->tail;
    if (tail == q->head) return 0;
    FENCE();          /* read the slot only after seeing the new head */
    *e = q->slot[tail & (LUNAR_FM1_QUEUE_SIZE - 1u)];
    FENCE();          /* finish reading before the producer may reuse it */
    q->tail = tail + 1u;
    return 1;
}

void lunar_fm1_panel_reset(struct lunar_fm1_panel *p)
{
    unsigned i;
    if (!p) return;
    p->stable[0] = p->stable[1] = p->candidate[0] = p->candidate[1] = 0;
    lunar_encoders_reset(&p->encoders);
    for (i = 0; i < LUNAR_ENCODER_COUNT; ++i) p->used[i] = 0;
    lunar_pot_reset(&p->pot);
    p->master_seen = 0;
    p->scans = 0;
}

static unsigned push(struct lunar_fm1_queue *q, unsigned kind, unsigned a, unsigned b,
                     unsigned c, int value)
{
    struct lunar_fm1_event e;
    e.kind = (uint8_t)kind;
    e.a = (uint8_t)a;
    e.b = (uint8_t)b;
    e.c = (uint8_t)c;
    e.value = (int16_t)value;
    return (unsigned)lunar_fm1_queue_push(q, &e);
}

unsigned lunar_fm1_panel_update(struct lunar_fm1_panel *p,
                                const unsigned char rows[LUNAR_MATRIX_COLUMNS],
                                int master_raw, struct lunar_fm1_queue *q)
{
    unsigned raw[2], next[2], changed, w, bit, n = 0;
    if (!p || !rows || !q) return 0;
    lunar_keys_decode(rows, raw);
    for (w = 0; w < 2; ++w) {
        unsigned agree = ~(raw[w] ^ p->candidate[w]);
        next[w] = (p->stable[w] & ~agree) | (raw[w] & agree);
        p->candidate[w] = raw[w];
    }
    /* The first pass only seeds the candidate: nothing is pressed yet. */
    if (!p->scans) next[0] = next[1] = 0;
    for (w = 0; w < 2; ++w) {
        changed = next[w] ^ p->stable[w];
        for (bit = 0; changed; ++bit, changed >>= 1) {
            unsigned id = 32u * w + bit, down;
            if (!(changed & 1u) || id >= LUNAR_KEY_COUNT) continue;
            down = (next[w] >> bit) & 1u;
            if (id < 14u)
                n += push(q, LUNAR_FM1_EV_BUTTON, lunar_fm1_button_map[id], down, 0, 0);
            else
                n += push(q, LUNAR_FM1_EV_KEY, id - 14u, down, LUNAR_FM1_KEY_VELOCITY, 0);
        }
        p->stable[w] = next[w];
    }
    lunar_encoders_sample(&p->encoders, rows);
    for (w = 0; w < LUNAR_ENCODER_COUNT; ++w) {
        int edges = p->encoders.count[w] - p->used[w];
        int detents = edges / LUNAR_FM1_EDGES_PER_DETENT; /* toward zero */
        if (!detents) continue;
        if (detents > 127) detents = 127;
        if (detents < -127) detents = -127;
        if (push(q, LUNAR_FM1_EV_ENCODER, lunar_fm1_encoder_map[w], 0, 0,
                 detents * lunar_fm1_encoder_sign[w])) {
            ++n;
            p->used[w] += detents * LUNAR_FM1_EDGES_PER_DETENT;
        }
    }
    if (master_raw >= 0) {
        int moved = lunar_pot_update(&p->pot, (unsigned)master_raw);
        if (moved || !p->master_seen) {
            /* The first reading is sent too, so the level follows the knob. */
            if (push(q, LUNAR_FM1_EV_MASTER, p->pot.level, 0, 0, 0)) {
                ++n;
                p->master_seen = 1;
            }
        }
    }
    ++p->scans;
    return n;
}

int lunar_fm1_midi_event(const struct lunar_midi_message *m, struct lunar_fm1_event *e)
{
    unsigned type;
    if (!m || !e || m->length < 1u) return 0;
    type = m->status & 0xf0u;
    e->a = e->b = e->c = 0;
    e->value = 0;
    if (type == 0x90u && m->length == 3u && m->data2) {
        e->kind = LUNAR_FM1_EV_NOTE_ON;
        e->a = m->data1 & 0x7fu;
        e->b = m->data2 & 0x7fu;
        e->c = m->status & 0x0fu;
        return 1;
    }
    if ((type == 0x80u || type == 0x90u) && m->length == 3u) {
        e->kind = LUNAR_FM1_EV_NOTE_OFF;
        e->a = m->data1 & 0x7fu;
        e->c = m->status & 0x0fu;
        return 1;
    }
    if (type == 0xe0u && m->length == 3u) {
        e->kind = LUNAR_FM1_EV_BEND;
        e->value = (int16_t)((int)(((m->data2 & 0x7fu) << 7) | (m->data1 & 0x7fu)) - 8192);
        return 1;
    }
    if (type == 0xb0u && m->length == 3u && m->data1 == 7u) {
        e->kind = LUNAR_FM1_EV_MASTER;
        e->a = m->data2 & 0x7fu;
        return 1;
    }
    if (type == 0xb0u && m->length == 3u && m->data1 == 123u) {
        e->kind = LUNAR_FM1_EV_PANIC;
        return 1;
    }
    return 0;
}

int lunar_fm1_usb_midi_packet(const unsigned char packet[4], struct lunar_midi_message *m)
{
    unsigned cin, status;
    if (!packet || !m) return 0;
    cin = packet[0] & 0x0fu;
    status = packet[1];
    if (cin >= 0x8u && cin <= 0xeu) {
        /* A channel voice message whose status agrees with its CIN. */
        if ((status >> 4) != cin) return 0;
        m->status = (unsigned char)status;
        m->data1 = packet[2] & 0x7fu;
        m->data2 = (cin == 0xcu || cin == 0xdu) ? 0 : (unsigned char)(packet[3] & 0x7fu);
        m->length = (cin == 0xcu || cin == 0xdu) ? 2u : 3u;
        return 1;
    }
    if (cin == 0xfu && (status & 0x80u) && status != 0xf0u && status != 0xf7u) {
        m->status = (unsigned char)status;
        m->data1 = m->data2 = 0;
        m->length = 1u;
        return 1;
    }
    return 0;
}

/* ---- the router ---------------------------------------------------------- */

void lunar_fm1_router_reset(struct lunar_fm1_router *r)
{
    unsigned i, n;
    if (!r) return;
    r->octave = 0;
    for (i = 0; i < 27u; ++i) r->key_note[i] = 0;
    for (i = 0; i < LUNAR_FM1_SOUNDS; ++i)
        for (n = 0; n < 128u; ++n) r->held[i][n] = 0;
    r->cutoff = LUNAR_FM1_CUTOFF_START;
    r->resonance = LUNAR_FM1_RESONANCE_START;
    r->applied = r->deferred = r->ignored = 0;
}

int lunar_fm1_channel_sound(unsigned channel)
{
    if (channel == 0u) return 0;
    if (channel == 1u) return -1;   /* sound 2: deferred in the pipelined app */
    if (channel == 2u) return 2;
    if (channel == 3u) return 3;
    return 0;
}

static unsigned act(lunar_fm1_action_fn emit, void *ctx, unsigned kind, unsigned sound,
                    unsigned note, unsigned velocity, float value)
{
    struct lunar_fm1_action a;
    a.kind = (uint8_t)kind;
    a.sound = (uint8_t)sound;
    a.note = (uint8_t)note;
    a.velocity = (uint8_t)velocity;
    a.value = value;
    if (emit) emit(ctx, &a);
    return 1;
}

static unsigned note_on(struct lunar_fm1_router *r, unsigned sound, unsigned note,
                        unsigned velocity, lunar_fm1_action_fn emit, void *ctx)
{
    if (r->held[sound][note] == 255u) { ++r->ignored; return 0; }
    ++r->held[sound][note];
    ++r->applied;
    return act(emit, ctx, LUNAR_FM1_ACT_NOTE_ON, sound, note, velocity ? velocity : 1u, 0.0f);
}

static unsigned note_off(struct lunar_fm1_router *r, unsigned sound, unsigned note,
                         lunar_fm1_action_fn emit, void *ctx)
{
    /* Only a note this router started: the app's counts stay balanced. */
    if (!r->held[sound][note]) { ++r->ignored; return 0; }
    --r->held[sound][note];
    ++r->applied;
    return act(emit, ctx, LUNAR_FM1_ACT_NOTE_OFF, sound, note, 0, 0.0f);
}

/* 2^(x/12) for |x| <= 127 semitones without libm: whole octaves by halving
 * and doubling, the remainder from a twelve-entry table. */
static float semitones(int x)
{
    static const float step[12] = {
        1.0f, 1.0594631f, 1.1224620f, 1.1892071f, 1.2599210f, 1.3348399f,
        1.4142136f, 1.4983071f, 1.5874011f, 1.6817928f, 1.7817974f, 1.8877486f
    };
    float v = 1.0f;
    while (x >= 12) { v *= 2.0f; x -= 12; }
    while (x < 0) { v *= 0.5f; x += 12; }
    return v * step[x];
}

unsigned lunar_fm1_route(struct lunar_fm1_router *r, const struct lunar_fm1_event *e,
                         lunar_fm1_action_fn emit, void *ctx)
{
    unsigned n = 0, s, k;
    int sound, note;
    if (!r || !e) return 0;
    switch (e->kind) {
    case LUNAR_FM1_EV_KEY:
        if (e->a >= 27u) { ++r->ignored; return 0; }
        if (e->b) {
            if (r->key_note[e->a]) { ++r->ignored; return 0; }   /* already down */
            note = LUNAR_FM1_KEY_BASE_NOTE + (int)e->a + 12 * r->octave;
            if (note < 0 || note > 127) { ++r->ignored; return 0; }
            n = note_on(r, 0, (unsigned)note, e->c ? e->c : LUNAR_FM1_KEY_VELOCITY, emit, ctx);
            if (n) r->key_note[e->a] = (uint8_t)(note + 1);
        } else {
            /* The note the key started, whatever the octave is now. */
            if (!r->key_note[e->a]) { ++r->ignored; return 0; }
            n = note_off(r, 0, r->key_note[e->a] - 1u, emit, ctx);
            r->key_note[e->a] = 0;
        }
        return n;
    case LUNAR_FM1_EV_BUTTON:
        if (e->b && e->a == FM1_BTN_OCT_DOWN && r->octave > -LUNAR_FM1_OCTAVE_MAX) {
            --r->octave; ++r->applied; return 0;
        }
        if (e->b && e->a == FM1_BTN_OCT_UP && r->octave < LUNAR_FM1_OCTAVE_MAX) {
            ++r->octave; ++r->applied; return 0;
        }
        if (e->a == FM1_BTN_OCT_DOWN || e->a == FM1_BTN_OCT_UP) { ++r->ignored; return 0; }
        ++r->deferred;            /* TODO(app): the panel's modes and menus */
        return 0;
    case LUNAR_FM1_EV_ENCODER:
        if (e->a == FM1_ENC_KNOB1 && e->value) {
            float v = r->cutoff * semitones(e->value);
            if (v < LUNAR_FM1_CUTOFF_MIN) v = LUNAR_FM1_CUTOFF_MIN;
            if (v > LUNAR_FM1_CUTOFF_MAX) v = LUNAR_FM1_CUTOFF_MAX;
            r->cutoff = v; ++r->applied;
            return act(emit, ctx, LUNAR_FM1_ACT_CUTOFF, 0, 0, 0, v);
        }
        if (e->a == FM1_ENC_KNOB2 && e->value) {
            float v = r->resonance + 0.05f * (float)e->value;
            if (v < 0.0f) v = 0.0f;
            if (v > 1.0f) v = 1.0f;
            r->resonance = v; ++r->applied;
            return act(emit, ctx, LUNAR_FM1_ACT_RESONANCE, 0, 0, 0, v);
        }
        ++r->deferred;            /* TODO(app): the other encoders' pages */
        return 0;
    case LUNAR_FM1_EV_MASTER:
        ++r->applied;
        return act(emit, ctx, LUNAR_FM1_ACT_MASTER, 0, 0, 0, (float)(e->a & 0x7fu) / 127.0f);
    case LUNAR_FM1_EV_NOTE_ON:
        sound = lunar_fm1_channel_sound(e->c & 0x0fu);
        if (sound < 0) { ++r->deferred; return 0; }
        return note_on(r, (unsigned)sound, e->a & 0x7fu, e->b & 0x7fu, emit, ctx);
    case LUNAR_FM1_EV_NOTE_OFF:
        sound = lunar_fm1_channel_sound(e->c & 0x0fu);
        if (sound < 0) { ++r->deferred; return 0; }
        return note_off(r, (unsigned)sound, e->a & 0x7fu, emit, ctx);
    case LUNAR_FM1_EV_BEND:
        ++r->deferred;            /* TODO(app): fm1_app_pitch_bend is fenced */
        return 0;
    case LUNAR_FM1_EV_PANIC:
        for (s = 0; s < LUNAR_FM1_SOUNDS; ++s)
            for (k = 0; k < 128u; ++k)
                while (r->held[s][k]) n += note_off(r, s, k, emit, ctx);
        for (k = 0; k < 27u; ++k) r->key_note[k] = 0;
        return n;
    default:
        ++r->ignored;
        return 0;
    }
}

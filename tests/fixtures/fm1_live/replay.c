/* SPDX-License-Identifier: MIT
 * Host replay of the FM-1 audio adapter (firmware/fm1/fm1_live.c) with the
 * pipelined shared app and a synchronous stand-in for the native pipeline:
 * the stand-in prepares each result as renderer_pipeline_sdk.c worker_step
 * does (cleared, tag set) and applies its post-consume checks. In "delayed"
 * mode block N+1 is produced, with the panel and MIDI events applied,
 * before block N is consumed, so every control runs while the app has a
 * block in flight (pipeline_busy). No IRQ, no timing, no hardware.
 *
 *   replay delayed   -> one summary line on stdout, exit 0
 *   replay guard     -> calls fm1_app_key while a block is in flight;
 *                       the app's fence must refuse (exit 72)
 *
 * Built with -DLUNAR_FM1_FULL_UI=1 (full-UI image) it also has
 *   replay full      -> the whole panel script through the drain barrier:
 *                       events wait for a drained app, the loop is the one in
 *                       fm1_sdk_main.c (hold, harvest, ask again, produce)
 *   replay gestures  -> PRESETS, ALGORITHM, SEL+PRESETS, the effect swap
 *   replay swaps     -> engine and insert changes on every sound, emptied
 *                       sounds, every Macro model with notes held on Sound 2,
 *                       Chip's random arpeggio beside Drums, effect swaps
 *   replay inserts   -> inserts on every sound (render_ext ones too, in a
 *                       build with the test-ext module)
 *   replay ref MODE  -> the same script on the same arrangement with no
 *                       pipeline (built without FM1_APP_RENDER_PIPELINE and
 *                       with -DREPLAY_REF=1): the pipelined MODE must equal
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef REPLAY_REF
#define LUNAR_FM1_HOST_REFERENCE 1   /* fm1_live.c without the pipelined app */
#endif
#include "fm1_live.c"
#include "fm1_panel.h"

#ifdef REPLAY_REF
/* No pipeline in this build: the symbols fm1_live.c names but fm1_app.c
 * only defines under FM1_APP_RENDER_PIPELINE. */
static const float *ref_samples;
void *fm1_app_pipeline_work(unsigned i) { (void)i; return 0; }
int fm1_app_pipeline_busy(void) { return 0; }
int fm1_app_pipeline_sealed(void) { return 0; }
int fm1_app_pipeline_service_due(const fm1_app_t *a) { (void)a; return 0; }
int fm1_app_pipeline_service(fm1_app_t *a) { (void)a; return 0; }
int fm1_app_pipeline_produce(fm1_app_t *a, void *w) { (void)a; (void)w; return 0; }
const float *fm1_app_pipeline_consume(void *w) { (void)w; return ref_samples; }
int fm1_app_pipeline_retire(void *w) { (void)w; return 1; }
#endif

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "check failed line %d: %s\n", __LINE__, #x); exit(3); } } while (0)

static lunar_pipeline_consume_fn consume_fn;
static lunar_pipeline_retire_fn retire_fn;
static void *works[2];

int lunar_pipeline_bind(void *a, void *b, lunar_pipeline_consume_fn c, lunar_pipeline_retire_fn r)
{
    CHECK(a && b && a != b && c && r && !consume_fn);
    works[0] = a; works[1] = b; consume_fn = c; retire_fn = r;
    return 1;
}
uint32_t lunar_pipeline_error(void) { return 0; }
void lunar_pipeline_fail_park(uint32_t code)
{
    fprintf(stderr, "pipeline refusal %u\n", code);
    exit(72);
}

static uint64_t fnv = 1469598103934665603ull;
static void fnv_bytes(const void *p, size_t n)
{
    const unsigned char *b = p;
    while (n--) { fnv ^= *b++; fnv *= 1099511628211ull; }
}

static int peak_silent, peak_sound, dup_ok = 1;
static unsigned blocks_out;

static void complete(uint32_t tag, int sounding)
{
    int16_t pcm[LUNAR_PIPELINE_OUTPUT_SAMPLES];
    lunar_pipeline_result_t r;
    unsigned i;
    memset(&r, 0, sizeof r);
    r.tag = tag;                             /* as worker_step, before consume */
    CHECK(consume_fn(works[tag % 2u], tag, pcm, &r));
    CHECK(r.tag == tag);                     /* worker_step: E_TAG otherwise */
    CHECK(r.case_total == tag + 1u);
    CHECK(retire_fn(works[tag % 2u]));
#if LUNAR_FM1_FULL_UI
    fnv_bytes(pcm, sizeof pcm);
#endif
    for (i = 0; i < LUNAR_FM1_BLOCK; ++i) {
        int k;
        if (pcm[4u * i] != pcm[4u * i + 2u] || pcm[4u * i + 1u] != pcm[4u * i + 3u]) dup_ok = 0;
        for (k = 0; k < 2; ++k) {
            int v = pcm[4u * i + (unsigned)k];
            if (v < 0) v = -v;
            if (sounding) { if (v > peak_sound) peak_sound = v; }
            else if (v > peak_silent) peak_silent = v;
        }
    }
    ++blocks_out;
}

static void ev(unsigned kind, unsigned a, unsigned b, unsigned c, int value)
{
    struct lunar_fm1_event e;
    e.kind = (uint8_t)kind; e.a = (uint8_t)a; e.b = (uint8_t)b; e.c = (uint8_t)c;
    e.value = (int16_t)value;
    CHECK(lunar_fm1_queue_push(lunar_fm1_live_queue(), &e));
}

/* The events pushed before block `tag` is produced. */
static unsigned script(uint32_t tag)
{
    switch (tag) {
    case 40:
        ev(LUNAR_FM1_EV_MASTER, 100, 0, 0, 0);
        ev(LUNAR_FM1_EV_BUTTON, FM1_BTN_OCT_UP, 1, 0, 0);
        ev(LUNAR_FM1_EV_BUTTON, FM1_BTN_OCT_UP, 0, 0, 0);
        ev(LUNAR_FM1_EV_KEY, 0, 1, LUNAR_FM1_KEY_VELOCITY, 0);           /* sound 1 */
        ev(LUNAR_FM1_EV_ENCODER, FM1_ENC_KNOB1, 0, 0, 3);
        ev(LUNAR_FM1_EV_ENCODER, FM1_ENC_KNOB2, 0, 0, -2);
        ev(LUNAR_FM1_EV_NOTE_ON, 60, 90, 0, 0);                          /* ch 1: sound 1 */
        ev(LUNAR_FM1_EV_NOTE_ON, 36, 110, 2, 0);                         /* ch 3: sound 3 */
        ev(LUNAR_FM1_EV_NOTE_ON, 67, 80, 3, 0);                          /* ch 4: sound 4 */
        ev(LUNAR_FM1_EV_NOTE_ON, 64, 80, 1, 0);                          /* ch 2: deferred */
        ev(LUNAR_FM1_EV_BEND, 0, 0, 0, 4000);                            /* deferred */
        ev(LUNAR_FM1_EV_BUTTON, FM1_BTN_FX, 1, 0, 0);                    /* deferred */
        ev(LUNAR_FM1_EV_ENCODER, FM1_ENC_SELECT, 0, 0, 1);               /* deferred */
        return 13;
    case 200:
        ev(LUNAR_FM1_EV_KEY, 0, 0, 0, 0);
        ev(LUNAR_FM1_EV_NOTE_OFF, 60, 0, 0, 0);
        ev(LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1, 0);                          /* deferred */
        return 3;
    case 260:
        ev(LUNAR_FM1_EV_KEY, 7, 1, LUNAR_FM1_KEY_VELOCITY, 0);
        ev(LUNAR_FM1_EV_MASTER, 127, 0, 0, 0);
        return 2;
    case 400:
        ev(LUNAR_FM1_EV_PANIC, 0, 0, 0, 0);
        return 1;
    default:
        return 0;
    }
}

#if LUNAR_FM1_FULL_UI
/* ---- the full-UI script: every control, in ticks (blocks) ---------------- */
struct step { unsigned tick, kind, a, b, c; int value; };
#define BTN(t, b, d) {t, LUNAR_FM1_EV_BUTTON, b, d, 0, 0}
#define ENC(t, e, v) {t, LUNAR_FM1_EV_ENCODER, e, 0, 0, v}
#define KEYS(t, k, d) {t, LUNAR_FM1_EV_KEY, k, d, LUNAR_FM1_KEY_VELOCITY, 0}
static const struct step full_script[] = {
    BTN(10, FM1_BTN_OCT_UP, 1), BTN(11, FM1_BTN_OCT_UP, 0),
    BTN(12, FM1_BTN_OCT_DOWN, 1), BTN(13, FM1_BTN_OCT_DOWN, 0),
    BTN(14, FM1_BTN_OCT_UP, 1), BTN(15, FM1_BTN_OCT_UP, 0),
    KEYS(20, 0, 1), KEYS(21, 7, 1), KEYS(60, 0, 0), KEYS(61, 7, 0),
    {70, LUNAR_FM1_EV_MASTER, 90, 1, 0, 0},
    {71, LUNAR_FM1_EV_BEND, 0, 0, 0, 4000},
    /* the four knobs and SELECT on the home page, both ways */
    ENC(80, FM1_ENC_KNOB1, 2), ENC(81, FM1_ENC_KNOB1, -1), ENC(82, FM1_ENC_KNOB2, 3),
    ENC(83, FM1_ENC_KNOB3, -2), ENC(84, FM1_ENC_KNOB4, 1), ENC(85, FM1_ENC_SELECT, 1),
    ENC(86, FM1_ENC_SELECT, -1),
    /* FX, then SEL grab and SELECT, then home */
    BTN(100, FM1_BTN_FX, 1), BTN(101, FM1_BTN_FX, 0), ENC(102, FM1_ENC_SELECT, 1),
    ENC(103, FM1_ENC_KNOB1, 1),
    BTN(104, FM1_BTN_SEL, 1), BTN(105, FM1_BTN_SEL, 0),
    BTN(106, FM1_BTN_HOME, 1), BTN(107, FM1_BTN_HOME, 0),
    /* global pages, env, lfo, edit */
    BTN(120, FM1_BTN_GLO, 1), BTN(121, FM1_BTN_GLO, 0), ENC(122, FM1_ENC_SELECT, 1),
    ENC(123, FM1_ENC_KNOB1, 1),
    BTN(130, FM1_BTN_ENV, 1), BTN(131, FM1_BTN_ENV, 0), ENC(132, FM1_ENC_KNOB1, 1),
    BTN(140, FM1_BTN_LFO, 1), BTN(141, FM1_BTN_LFO, 0), ENC(142, FM1_ENC_KNOB2, 1),
    BTN(150, FM1_BTN_EDIT, 1), BTN(151, FM1_BTN_EDIT, 0),
    BTN(160, FM1_BTN_HOME, 1), BTN(161, FM1_BTN_HOME, 0),
    /* SAVE (no store: a popup), SEL combos */
    BTN(170, FM1_BTN_SAVE, 1), BTN(171, FM1_BTN_SAVE, 0),
    BTN(180, FM1_BTN_SEL, 1), BTN(181, FM1_BTN_PLAY, 1), BTN(182, FM1_BTN_PLAY, 0),
    BTN(183, FM1_BTN_SEL, 0),
    /* ARP: a tap, then a hold past FM1_APP_ARP_HOLD_S (about 345 blocks) */
    BTN(200, FM1_BTN_ARP, 1), BTN(202, FM1_BTN_ARP, 0),
    BTN(220, FM1_BTN_ARP, 1), BTN(600, FM1_BTN_ARP, 0),
    BTN(610, FM1_BTN_HOME, 1), BTN(611, FM1_BTN_HOME, 0),
    /* the sequencer: SEQ, a step key, PLAY, REC, STOP */
    BTN(620, FM1_BTN_SEQ, 1), BTN(621, FM1_BTN_SEQ, 0),
    KEYS(625, 0, 1), KEYS(626, 0, 0),
    BTN(630, FM1_BTN_PLAY, 1), BTN(631, FM1_BTN_PLAY, 0),
    BTN(700, FM1_BTN_REC, 1), BTN(701, FM1_BTN_REC, 0),
    BTN(760, FM1_BTN_PLAY, 1), BTN(761, FM1_BTN_PLAY, 0),
    BTN(780, FM1_BTN_HOME, 1), BTN(781, FM1_BTN_HOME, 0),
    /* a held key across a panic */
    KEYS(800, 3, 1), {805, LUNAR_FM1_EV_PANIC, 0, 0, 0, 0}, KEYS(806, 3, 0),
};
#define FULL_BLOCKS 1700u    /* the last step at 806, then a popup's second and more */

static void state_line(const char *tag)
{
    uint64_t screen = 1469598103934665603ull;
    unsigned i;
    char leds[42];
    fm1_app_draw(&app, 0);
    for (i = 0; i < sizeof app.tft.px; ++i) {
        screen ^= ((const unsigned char *)app.tft.px)[i];
        screen *= 1099511628211ull;
    }
    for (i = 0; i < 41u; ++i) leds[i] = app.led[i] ? '1' : '0';
    leds[41] = 0;
    printf("%s units=", tag);              /* the arrangement: every unit's engine */
    for (i = 0; i < FM1_APP_UNITS; ++i) printf("%s%s", i ? "," : "", app.unit[i].e ? app.unit[i].e->id : "-");
    printf(" model=%g ", app.unit[fm1_app_sound_unit(1)].e ? (double)fm1_app_get_param(&app, fm1_app_sound_unit(1), 0) : -1.0);
    printf("dx7_limit=");                  /* each sound's DX7 voice limit, 0 when it is not a DX7 */
    for (i = 0; i < 4u; ++i) {
        const fm1_app_unit_t *u = &app.unit[fm1_app_sound_unit((int)i)];
        fm1_dx7_budget_stats_t st;
        unsigned lim = 0;
        if (u->e && !strcmp(u->e->id, "dx7")) lim = fm1_dx7_get_budget_stats(u->self, &st) ? (unsigned)st.limit : 99u;
        printf("%s%u", i ? "," : "", lim);
    }
    printf(" ");
    printf("seq=%d play_led=%d mode=%d page=%d sound=%d octave=%d transpose=%d popup_lines=%d popup0=[%s] leds=%s "
           "screen=%016llx pcm=%016llx frames=%llu\n",
           app.seq != 0, app.led[27 + FM1_BTN_PLAY], app.mode, app.page, app.sound, app.octave, app.transpose, app.popup_lines,
           app.popup_lines ? app.popup[0] : "", leds, (unsigned long long)screen,
           (unsigned long long)fnv, (unsigned long long)app.frames);
}

/* The active script and its snapshot ticks (the state lines must agree at
 * each, not only at the end). */
static const struct step *cur_script = full_script;
static unsigned cur_n = sizeof full_script / sizeof *full_script;
static const unsigned full_at[] = {18, 66, 90, 110, 190, 330, 450, 615, 640, 770, 850, 1200};
static const unsigned *cur_at = full_at;
static unsigned cur_at_n = sizeof full_at / sizeof *full_at;

static int checkpoint(unsigned tick)
{
    unsigned i;
    for (i = 0; i < cur_at_n; ++i) if (cur_at[i] == tick) return 1;
    return 0;
}

static unsigned script_at(unsigned tick, unsigned from)
{
    unsigned n = 0, i;
    for (i = from; i < cur_n; ++i)
        if (cur_script[i].tick == tick) {
            const struct step *s = &cur_script[i];
            ev(s->kind, s->a, s->b, s->c, s->value);
            ++n;
        }
    return n;
}

static void complete_hashed(uint32_t tag) { complete(tag, 1); }

/* The producer loop of fm1_sdk_main.c: hold while the next event needs a
 * drained app, harvest (complete the oldest block), ask again, produce. */
static int run_full(void)
{
    uint32_t tag, done = 0;
    unsigned holds_seen = 0, pushed = 0;
    struct lunar_fm1_live_status s;
    for (tag = 0; tag < FULL_BLOCKS; ++tag) {
        pushed += script_at(tag, 0);
        while (lunar_fm1_live_barrier_hold()) {
            CHECK(done < tag);                 /* a hold needs a block in flight */
            CHECK(fm1_app_pipeline_busy());
            ++holds_seen;
            complete_hashed(done++);
        }
        CHECK(lunar_fm1_live_produce(works[tag % 2u]));
        while (done + 1u < tag + 1u) complete_hashed(done++);
        if (checkpoint(tag)) {
            char name[32];
            while (done < tag + 1u) complete_hashed(done++);
            snprintf(name, sizeof name, "t%u", (unsigned)tag);
            state_line(name);
            lunar_fm1_live_status(&s);
            printf("holds t%u %u\n", (unsigned)tag, (unsigned)s.barrier_holds);
        }
    }
    while (done < FULL_BLOCKS) complete_hashed(done++);
    CHECK(!fm1_app_pipeline_busy());
    lunar_fm1_live_status(&s);
    CHECK(s.dropped == 0 && s.events == pushed && s.invalid == 0);
    CHECK(s.init_error == 0);                 /* 23: a new DX7 was left unlimited */
    CHECK(s.barrier_holds >= 1 && s.barrier_events >= 1 && s.services >= 1);
    CHECK(holds_seen == s.barrier_holds);
    printf("pushed=%u events=%u applied=%u barrier_events=%u barrier_holds=%u services=%u\n",
           pushed, s.events, s.applied, s.barrier_events, s.barrier_holds, s.services);
    state_line("state");
    return 0;
}

/* The gestures where the pipelined app diverged from R0 until 2026-11-10 (the
 * soft locks; now a differential against it), through the live
 * adapter and the barrier (a guard trip here would be exit 72, a warm-reset
 * loop on the device): PRESETS and ALGORITHM turns on a DX7 and on Macro as
 * the current sound, SEL+PRESETS choosing sound 2, keys with Macro current,
 * FX mode with SEL grabbed and SELECT turned (the effect swap), ALGORITHM in
 * FX (an effect pick), and MIDI notes on channel 2. */
#define MIDI(t, k, n, v, ch) {t, k, n, v, ch, 0}
static const struct step gesture_script[] = {
    ENC(10, FM1_ENC_PRESETS, 1), ENC(30, FM1_ENC_PRESETS, -1), ENC(50, FM1_ENC_ALGORITHM, 1),
    BTN(70, FM1_BTN_SEL, 1), ENC(71, FM1_ENC_PRESETS, 1), BTN(72, FM1_BTN_SEL, 0),
    KEYS(80, 0, 1), KEYS(120, 0, 0),
    ENC(130, FM1_ENC_PRESETS, 1), ENC(150, FM1_ENC_ALGORITHM, 1), ENC(170, FM1_ENC_ALGORITHM, -1),
    BTN(190, FM1_BTN_FX, 1), BTN(191, FM1_BTN_FX, 0),
    BTN(200, FM1_BTN_SEL, 1), ENC(201, FM1_ENC_SELECT, 1), ENC(220, FM1_ENC_SELECT, -1),
    BTN(221, FM1_BTN_SEL, 0),
    ENC(240, FM1_ENC_ALGORITHM, 1), ENC(260, FM1_ENC_PRESETS, 1),
    BTN(280, FM1_BTN_HOME, 1), BTN(281, FM1_BTN_HOME, 0),
    MIDI(290, LUNAR_FM1_EV_NOTE_ON, 64, 90, 1), MIDI(330, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    BTN(340, FM1_BTN_SEL, 1), ENC(341, FM1_ENC_PRESETS, -1), BTN(342, FM1_BTN_SEL, 0),
    KEYS(350, 2, 1), KEYS(390, 2, 0),
};
static const unsigned gesture_at[] = {11, 31, 51, 72, 81, 131, 151, 171, 202, 241, 261, 291, 343, 351, 1400};

/* Engine and insert changes on every sound, emptied sounds, every Macro
 * model with notes held on Sound 2, Chip's random arpeggio (Timbre high)
 * beside Drums (both used stmlib::Random's one global before 2026-11-10),
 * Sound 2 as DX7, as Drums with Sound 3 also Drums (rendered on CPU0: they
 * share the generator) and empty, then the effect swap and picks. */
static const struct step swap_script[] = {
    /* Sound 2 current; Timbre and Harmonics up */
    BTN(10, FM1_BTN_SEL, 1), ENC(11, FM1_ENC_PRESETS, 1), BTN(12, FM1_BTN_SEL, 0),
    ENC(14, FM1_ENC_KNOB3, 45), ENC(15, FM1_ENC_KNOB2, 20),
    /* Drums and DX7 play throughout; a note held on Sound 2 across a model change */
    MIDI(16, LUNAR_FM1_EV_NOTE_ON, 36, 110, 2), MIDI(17, LUNAR_FM1_EV_NOTE_ON, 67, 80, 3),
    MIDI(18, LUNAR_FM1_EV_NOTE_ON, 60, 100, 1), ENC(20, FM1_ENC_ALGORITHM, 1),
    MIDI(30, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 1), MIDI(31, LUNAR_FM1_EV_NOTE_OFF, 36, 0, 2),
    MIDI(36, LUNAR_FM1_EV_NOTE_ON, 62, 100, 1), ENC(40, FM1_ENC_ALGORITHM, 1),
    MIDI(50, LUNAR_FM1_EV_NOTE_OFF, 62, 0, 1),
    MIDI(56, LUNAR_FM1_EV_NOTE_ON, 64, 100, 1), ENC(60, FM1_ENC_ALGORITHM, 1),   /* Chip */
    MIDI(62, LUNAR_FM1_EV_NOTE_ON, 38, 120, 2), MIDI(63, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    /* Chip's arpeggio clocks on every note: a run of them between drum hits */
    MIDI(64, LUNAR_FM1_EV_NOTE_ON, 65, 100, 1), MIDI(66, LUNAR_FM1_EV_NOTE_ON, 40, 120, 2),
    MIDI(67, LUNAR_FM1_EV_NOTE_OFF, 65, 0, 1), MIDI(68, LUNAR_FM1_EV_NOTE_ON, 67, 100, 1),
    MIDI(70, LUNAR_FM1_EV_NOTE_ON, 42, 120, 2), MIDI(71, LUNAR_FM1_EV_NOTE_OFF, 67, 0, 1),
    MIDI(72, LUNAR_FM1_EV_NOTE_ON, 69, 100, 1), MIDI(74, LUNAR_FM1_EV_NOTE_ON, 36, 120, 2),
    MIDI(75, LUNAR_FM1_EV_NOTE_OFF, 69, 0, 1), MIDI(76, LUNAR_FM1_EV_NOTE_ON, 71, 100, 1),
    MIDI(78, LUNAR_FM1_EV_NOTE_OFF, 71, 0, 1),
    MIDI(84, LUNAR_FM1_EV_NOTE_ON, 60, 100, 1), ENC(90, FM1_ENC_ALGORITHM, 1),
    MIDI(94, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 1),
    MIDI(104, LUNAR_FM1_EV_NOTE_ON, 62, 100, 1), ENC(110, FM1_ENC_ALGORITHM, 1),
    MIDI(114, LUNAR_FM1_EV_NOTE_OFF, 62, 0, 1),
    MIDI(124, LUNAR_FM1_EV_NOTE_ON, 64, 100, 1), ENC(130, FM1_ENC_ALGORITHM, 1),
    MIDI(134, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    MIDI(144, LUNAR_FM1_EV_NOTE_ON, 65, 100, 1), ENC(150, FM1_ENC_ALGORITHM, 1),
    MIDI(154, LUNAR_FM1_EV_NOTE_OFF, 65, 0, 1),
    MIDI(164, LUNAR_FM1_EV_NOTE_ON, 67, 100, 1), ENC(170, FM1_ENC_ALGORITHM, 1),   /* back to 0 */
    MIDI(180, LUNAR_FM1_EV_NOTE_OFF, 67, 0, 1), MIDI(181, LUNAR_FM1_EV_NOTE_OFF, 67, 0, 3),
    /* Sound 2's engine: the next ones in PRESETS, a note on each */
    ENC(200, FM1_ENC_PRESETS, 1), MIDI(204, LUNAR_FM1_EV_NOTE_ON, 60, 100, 1),
    MIDI(220, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 1),
    MIDI(238, LUNAR_FM1_EV_NOTE_ON, 62, 100, 1), ENC(240, FM1_ENC_PRESETS, 1),
    MIDI(244, LUNAR_FM1_EV_NOTE_ON, 38, 100, 1), MIDI(246, LUNAR_FM1_EV_NOTE_ON, 36, 110, 2),
    MIDI(260, LUNAR_FM1_EV_NOTE_OFF, 38, 0, 1), MIDI(261, LUNAR_FM1_EV_NOTE_OFF, 36, 0, 2),
    ENC(280, FM1_ENC_PRESETS, 1), MIDI(284, LUNAR_FM1_EV_NOTE_ON, 64, 100, 1),
    MIDI(300, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    ENC(320, FM1_ENC_PRESETS, 1), MIDI(324, LUNAR_FM1_EV_NOTE_ON, 64, 100, 1),
    MIDI(340, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    /* Sound 1 (the first DX7): other engines, then back */
    BTN(350, FM1_BTN_SEL, 1), ENC(351, FM1_ENC_PRESETS, -1), BTN(352, FM1_BTN_SEL, 0),
    /* away from the DX7 and back in one drained batch: the new DX7 lands at
     * the old one's address and must still get the eight-voice limit */
    ENC(355, FM1_ENC_PRESETS, 1), ENC(355, FM1_ENC_PRESETS, -1),
    ENC(360, FM1_ENC_PRESETS, 1), MIDI(364, LUNAR_FM1_EV_NOTE_ON, 36, 110, 0),
    MIDI(380, LUNAR_FM1_EV_NOTE_OFF, 36, 0, 0),
    ENC(400, FM1_ENC_PRESETS, -2), MIDI(404, LUNAR_FM1_EV_NOTE_ON, 60, 110, 0),
    MIDI(420, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 0),
    /* The effects: FX mode, a swap, picks on a master and an insert */
    MIDI(440, LUNAR_FM1_EV_NOTE_ON, 67, 80, 3), MIDI(441, LUNAR_FM1_EV_NOTE_ON, 60, 100, 1),
    BTN(450, FM1_BTN_FX, 1), BTN(451, FM1_BTN_FX, 0),
    BTN(460, FM1_BTN_SEL, 1), ENC(461, FM1_ENC_SELECT, 1), BTN(462, FM1_BTN_SEL, 0),
    ENC(480, FM1_ENC_ALGORITHM, 1), ENC(500, FM1_ENC_ALGORITHM, 1),
    BTN(510, FM1_BTN_SEL, 1), ENC(511, FM1_ENC_SELECT, -1), BTN(512, FM1_BTN_SEL, 0),
    ENC(520, FM1_ENC_SELECT, -2), ENC(530, FM1_ENC_ALGORITHM, 1), ENC(550, FM1_ENC_ALGORITHM, 2),
    MIDI(570, LUNAR_FM1_EV_NOTE_OFF, 67, 0, 3), MIDI(571, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 1),
    BTN(580, FM1_BTN_HOME, 1), BTN(581, FM1_BTN_HOME, 0),
};
static const unsigned swap_at[] = {13, 19, 21, 41, 61, 79, 91, 111, 131, 151, 171, 201, 241, 262,
                                   281, 321, 353, 356, 361, 401, 452, 463, 481, 501, 513, 521, 531,
                                   551, 582, 1500};

/* Inserts on every sound and on Sound 2 one with engine API v3's extension
 * (render_ext; built with the test-ext module), through FX mode. */
static const struct step insert_script[] = {
    /* Sound 2 current: its inserts first, with its engine changed under them */
    BTN(2, FM1_BTN_SEL, 1), ENC(3, FM1_ENC_PRESETS, 1), BTN(4, FM1_BTN_SEL, 0),
    MIDI(5, LUNAR_FM1_EV_NOTE_ON, 60, 100, 0), MIDI(6, LUNAR_FM1_EV_NOTE_ON, 64, 100, 1),
    MIDI(7, LUNAR_FM1_EV_NOTE_ON, 36, 110, 2), MIDI(8, LUNAR_FM1_EV_NOTE_ON, 67, 100, 3),
    BTN(10, FM1_BTN_FX, 1), BTN(11, FM1_BTN_FX, 0), ENC(12, FM1_ENC_SELECT, -3),
    ENC(20, FM1_ENC_ALGORITHM, 1), ENC(30, FM1_ENC_SELECT, 1), ENC(31, FM1_ENC_ALGORITHM, 2),
    BTN(40, FM1_BTN_SEL, 1), ENC(41, FM1_ENC_PRESETS, 1), BTN(42, FM1_BTN_SEL, 0),
    ENC(50, FM1_ENC_ALGORITHM, -1), ENC(60, FM1_ENC_SELECT, -1), ENC(61, FM1_ENC_ALGORITHM, -1),
    BTN(70, FM1_BTN_SEL, 1), ENC(71, FM1_ENC_PRESETS, 1), BTN(72, FM1_BTN_SEL, 0),
    ENC(80, FM1_ENC_ALGORITHM, 1), ENC(90, FM1_ENC_SELECT, 1), ENC(91, FM1_ENC_ALGORITHM, 1),
    BTN(100, FM1_BTN_SEL, 1), ENC(101, FM1_ENC_PRESETS, 1), BTN(102, FM1_BTN_SEL, 0),
    ENC(110, FM1_ENC_ALGORITHM, 1), ENC(120, FM1_ENC_SELECT, -1), ENC(121, FM1_ENC_ALGORITHM, 3),
    /* then Sound 1's inserts */
    BTN(130, FM1_BTN_HOME, 1), BTN(131, FM1_BTN_HOME, 0),
    BTN(140, FM1_BTN_SEL, 1), ENC(141, FM1_ENC_PRESETS, -1), BTN(142, FM1_BTN_SEL, 0),
    BTN(150, FM1_BTN_FX, 1), BTN(151, FM1_BTN_FX, 0), ENC(152, FM1_ENC_SELECT, -3),
    ENC(160, FM1_ENC_ALGORITHM, 1), ENC(170, FM1_ENC_SELECT, 1), ENC(171, FM1_ENC_ALGORITHM, 2),
    MIDI(200, LUNAR_FM1_EV_NOTE_OFF, 60, 0, 0), MIDI(201, LUNAR_FM1_EV_NOTE_OFF, 64, 0, 1),
    MIDI(202, LUNAR_FM1_EV_NOTE_OFF, 36, 0, 2), MIDI(203, LUNAR_FM1_EV_NOTE_OFF, 67, 0, 3),
    BTN(210, FM1_BTN_HOME, 1), BTN(211, FM1_BTN_HOME, 0),
};
static const unsigned insert_at[] = {13, 21, 32, 43, 51, 62, 73, 81, 92, 103, 111, 122, 132, 143,
                                     161, 172, 204, 1200};

static int run_full(void);
static void use_script(const char *mode)
{
#define USE(s, at) do { cur_script = s; cur_n = sizeof s / sizeof *s; cur_at = at; \
                         cur_at_n = sizeof at / sizeof *at; } while (0)
    if (!strcmp(mode, "gestures")) USE(gesture_script, gesture_at);
    else if (!strcmp(mode, "swaps")) USE(swap_script, swap_at);
    else if (!strcmp(mode, "inserts")) USE(insert_script, insert_at);
    else { CHECK(!strcmp(mode, "full")); USE(full_script, full_at); }
#undef USE
}
#endif

#ifdef REPLAY_REF
/* The same script on the same arrangement, no pipeline: events at the start
 * of the block through the same router and apply(), then fm1_app_render. */
static int run_ref(void)
{
    uint32_t tag;
    struct lunar_fm1_event e;
    unsigned pushed = 0;
    for (tag = 0; tag < FULL_BLOCKS; ++tag) {
        int16_t pcm[LUNAR_PIPELINE_OUTPUT_SAMPLES];
        lunar_pipeline_result_t r;
        pushed += script_at(tag, 0);
        while (lunar_fm1_queue_pop(&queue, &e)) lunar_fm1_route(&router, &e, apply, 0);
        CHECK(limit_dx7());                  /* as lunar_fm1_live_produce after its events */
        ref_samples = fm1_app_render(&app, LUNAR_FM1_BLOCK);
        memset(&r, 0, sizeof r);
        r.tag = tag;
        CHECK(convert(0, tag, pcm, &r));
        fnv_bytes(pcm, sizeof pcm);
        if (checkpoint(tag)) {
            char name[32];
            snprintf(name, sizeof name, "t%u", (unsigned)tag);
            state_line(name);
        }
    }
    printf("pushed=%u\n", pushed);
    state_line("state");
    return 0;
}
#endif

int main(int argc, char **argv)
{
    struct lunar_fm1_live_status s;
    unsigned pushed = 0;
    uint32_t tag;
    const uint32_t total = 600;
    CHECK(argc >= 2);
#ifdef REPLAY_REF
    CHECK(argc == 3 && !strcmp(argv[1], "ref"));
    use_script(argv[2]);
    CHECK(lunar_fm1_live_init());
    return run_ref();
#endif
    CHECK(!lunar_fm1_live_produce(0));        /* nothing before init and bind */
    CHECK(lunar_fm1_live_init());
    CHECK(!lunar_fm1_live_init());
    CHECK(lunar_fm1_live_bind());
    CHECK(!lunar_fm1_live_bind());
    if (!strcmp(argv[1], "guard")) {
        CHECK(lunar_fm1_live_produce(works[0]));
        fm1_app_key(&app, 0, 1, 100);         /* fenced while block 0 is in flight */
        return 0;                             /* reached only if the fence is off */
    }
#if LUNAR_FM1_FULL_UI
    if (strcmp(argv[1], "delayed")) {        /* full, gestures, swaps, inserts */
        use_script(argv[1]);
        return run_full();
    }
#endif
    CHECK(!strcmp(argv[1], "delayed"));
    for (tag = 0; tag < total; ++tag) {
        pushed += script(tag);
        CHECK(lunar_fm1_live_produce(works[tag % 2u]));
        if (tag) complete(tag - 1u, tag - 1u >= 40u);
    }
    complete(total - 1u, 1);
    lunar_fm1_live_status(&s);
    printf("blocks=%u out=%u pushed=%u events=%u applied=%u deferred=%u ignored=%u dropped=%u "
           "invalid=%u clipped=%u init_error=%u dx7_voices=%u peak_silent=%d peak_sound=%d "
           "dup_ok=%d octave=%d cutoff=%.3f resonance=%.3f\n",
           s.blocks, blocks_out, pushed, s.events, s.applied, s.deferred, s.ignored, s.dropped,
           s.invalid, s.clipped, s.init_error, s.dx7_voices, peak_silent, peak_sound, dup_ok,
           router.octave, (double)router.cutoff, (double)router.resonance);
    return 0;
}

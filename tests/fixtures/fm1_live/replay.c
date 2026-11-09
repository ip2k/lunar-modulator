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
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fm1_live.c"
#include "fm1_panel.h"

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

int main(int argc, char **argv)
{
    struct lunar_fm1_live_status s;
    unsigned pushed = 0;
    uint32_t tag;
    const uint32_t total = 600;
    CHECK(argc == 2);
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

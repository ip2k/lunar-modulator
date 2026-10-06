/* drum909_drive.c -- fm1-x0x's 909 kit (dsp/drum909.c) driven through its own
 * API only, as fm1-x0x drives it: drum909_init, integer pots through
 * drum909_set, drum909_trigger between render calls, drum909_render in calls
 * of up to 256 frames at 44.1 kHz. Writes the dry output as raw float32 to
 * stdout.
 *
 * tests/test_engine_comet_kit.py builds it twice, against fm1-x0x's own
 * drum909.c (reference/fm1-x0x, when cloned) and against the vendored,
 * patched one (engines/third_party/fm1-x0x), and asserts the same bytes: the
 * local changes (UPSTREAM.md) leave upstream's samples at 44.1 kHz.
 *
 * Four passes over the same pattern (every voice, accents, the closed and
 * open hats choking each other, retriggers inside a tail): the panel's
 * defaults; every voice's pots moved (tunes, decays, levels, attacks, the
 * kick's pitch depth); each of the seven distortion types on every voice at
 * a high drive; and the kit's accent and velocity depth with soft hits, in
 * odd call lengths. MIT licence (this file).
 */
#include <stdio.h>
#include <stdint.h>
#include "drum909.h"

#define SR 44100
#define STEP (SR / 8)              /* a 16th at 120 BPM: 5,512 frames */
#define STEPS 32

static drum909_t d;
static float dry[256], rev[256], dly[256];

/* which voices sound on each 16th; bit v is voice v (DR_BD .. DR_RD) */
static uint32_t hits(int k)
{
    uint32_t m = 0;
    if (k % 4 == 0) m |= 1u << DR_BD;
    if (k % 8 == 4) m |= 1u << DR_SD;
    if (k % 2 == 0) m |= 1u << DR_CH;
    if (k % 8 == 6) m |= 1u << DR_OH;             /* the closed hat on 8 chokes it */
    if (k == 3 || k == 19) m |= 1u << DR_RS;
    if (k == 12 || k == 28) m |= 1u << DR_CP;
    if (k == 14) m |= 1u << DR_LT;
    if (k == 15) m |= 1u << DR_MT;
    if (k == 30) m |= (1u << DR_HT) | (1u << DR_LT);
    if (k == 0) m |= 1u << DR_CR;
    if (k == 16) m |= 1u << DR_RD;
    if (k == 9 || k == 25) m |= 1u << DR_BD;      /* a kick retriggered inside its tail */
    return m;
}

static void out(int n)
{
    for (int i = 0; i < n; ++i) dry[i] = rev[i] = dly[i] = 0.0f;
    drum909_render(&d, dry, rev, dly, n);
    fwrite(dry, sizeof(float), (size_t)n, stdout);
}

static void play(int split, int soft)
{
    for (int k = 0; k < STEPS; ++k) {
        const uint32_t m = hits(k);
        for (int v = 0; v < DR_NUM; ++v)
            if (m & (1u << v))
                drum909_trigger(&d, v, soft ? (k % 3 == 0 ? 1.0f : 0.31f + 0.1f * (float)(v % 4)) : 1.0f);
        int left = STEP;
        while (left > 0) {
            int n = left < split ? left : split;
            out(n);
            left -= n;
        }
    }
}

int main(void)
{
    /* 1: the panel's defaults */
    drum909_init(&d);
    for (int v = 0; v <= DR_KIT; ++v)
        for (int i = 0; i < drum909_nparams(v); ++i)
            drum909_set(&d, v, i, drum909_param(v, i)->def);
    play(256, 0);

    /* 2: every continuous pot moved off its default */
    drum909_init(&d);
    for (int v = 0; v < DR_NUM; ++v)
        for (int i = 0; i < drum909_nparams(v); ++i) {
            const x0x_param_t *p = drum909_param(v, i);
            if (p->max == 127 && p->names == 0)
                drum909_set(&d, v, i, (p->def + 37 + 11 * v) % 128);
        }
    play(256, 0);

    /* 3: each distortion type on every voice, the drive high */
    for (int type = 0; type < 7; ++type) {
        drum909_init(&d);
        for (int v = 0; v < DR_NUM; ++v)
            for (int i = 0; i < drum909_nparams(v); ++i) {
                const x0x_param_t *p = drum909_param(v, i);
                if (p->names)
                    drum909_set(&d, v, i, type);
                else if (p->name[0] == 'D' && p->name[1] == 'r')
                    drum909_set(&d, v, i, 100);
            }
        play(256, 0);
    }

    /* 4: soft hits under the kit's accent and velocity depth, odd calls */
    drum909_init(&d);
    drum909_set(&d, DR_KIT, 0, 90);
    drum909_set(&d, DR_KIT, 1, 70);
    play(37, 1);
    return 0;
}

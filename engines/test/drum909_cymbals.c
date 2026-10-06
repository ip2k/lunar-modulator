/* drum909_cymbals.c -- the 909 kit's four sampled voices (closed and open
 * hat, crash, ride; fm1-x0x's dsp/drum909.c), each struck alone on the
 * panel's defaults, at three tunings (pot 0, 64 and 127: a quarter, once and
 * four times the recording's speed) and once with its drive at 100, rendered
 * at 44.1 kHz in calls of 256 frames. Writes the dry output as raw float32 to
 * stdout: 4 voices x 4 settings, SEG frames each, in that order.
 *
 * tests/test_engine_comet_kit.py builds it twice, against the 8-bit mu-law
 * cymbals the kit plays (gen/x0x_drum_samples.h) and against fm1-x0x's int16
 * ones (tools/gen_drum_samples.py --int16, built with -DX0X_SMP_INT16), and
 * measures what the mu-law costs in the kit's own output (engines/README.md,
 * "Comet Kit"). MIT licence (this file).
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "drum909.h"

#define SEG 88200                  /* two seconds a hit */

static drum909_t d;
static float dry[256], rev[256], dly[256];

static int pot(int voice, const char *name)
{
    for (int i = 0; i < drum909_nparams(voice); ++i)
        if (strcmp(drum909_param(voice, i)->name, name) == 0)
            return i;
    return -1;
}

int main(void)
{
    static const int voices[4] = { DR_CH, DR_OH, DR_CR, DR_RD };
    for (int k = 0; k < 4; ++k) {
        for (int s = 0; s < 4; ++s) {
            const int v = voices[k];
            drum909_init(&d);
            for (int w = 0; w <= DR_KIT; ++w)
                for (int i = 0; i < drum909_nparams(w); ++i)
                    drum909_set(&d, w, i, drum909_param(w, i)->def);
            if (s < 3)
                drum909_set(&d, v, pot(v, "Tune"), s == 0 ? 0 : s == 1 ? 64 : 127);
            else
                drum909_set(&d, v, pot(v, "Drive"), 100);
            drum909_trigger(&d, v, 1.0f);
            for (int left = SEG; left > 0; left -= 256) {
                const int n = left < 256 ? left : 256;
                memset(dry, 0, sizeof dry);
                memset(rev, 0, sizeof rev);
                memset(dly, 0, sizeof dly);
                drum909_render(&d, dry, rev, dly, n);
                fwrite(dry, sizeof(float), (size_t)n, stdout);
            }
        }
    }
    return 0;
}

/* White-box regression for the PSX Verb's 2x half-band interpolator.
 *
 * The independent oracle below evaluates the pinned 39-tap kernel directly
 * over the zero-stuffed signal.  The coefficient fixture is from Charles
 * Vestal's MIT-licensed CVCHothouse/PSXVerb/PSXVerb/Halfband39.h at
 * b94500f72be70140f3d094d69d0c43d04ce72ecc.  This keeps the test independent
 * of the production polyphase decomposition and history indexing.
 */
#include <math.h>
#include <stdio.h>
#include <string.h>

#include "../third_party/schwung-modules/psxverb/psxverb.c"

static const float kReferenceCoeffs[HB_TAPS] = {
    -0.000275135f, 0.0f, -0.001467466f, 0.0f, -0.004356503f,
    0.0f, -0.009765625f, 0.0f, -0.018493652f, 0.0f,
    -0.031494141f, 0.0f, -0.050598145f, 0.0f, -0.079833984f,
    0.0f, -0.130859375f, 0.0f, -0.281494141f, 0.632812500f,
    -0.281494141f, 0.0f, -0.130859375f, 0.0f, -0.079833984f,
    0.0f, -0.050598145f, 0.0f, -0.031494141f, 0.0f,
    -0.018493652f, 0.0f, -0.009765625f, 0.0f, -0.004356503f,
    0.0f, -0.001467466f, 0.0f, -0.000275135f,
};

typedef struct {
    float history[HB_STATE_SIZE];
    int pos;
} oracle_t;

static float oracle_convolve(const oracle_t *o) {
    float sum = 0.0f;
    for (int i = 0; i < HB_TAPS; ++i) {
        const int idx = (o->pos - 1 - i) & HB_STATE_MASK;
        sum += kReferenceCoeffs[i] * o->history[idx];
    }
    return sum * 2.0f;
}

static void oracle_interpolate(oracle_t *o, float in, float *even, float *odd) {
    o->history[o->pos] = in;
    o->pos = (o->pos + 1) & HB_STATE_MASK;
    *even = oracle_convolve(o);
    o->history[o->pos] = 0.0f;
    o->pos = (o->pos + 1) & HB_STATE_MASK;
    *odd = oracle_convolve(o);
}

static int check_sequence(const char *name, float rate, int kind) {
    halfband_t actual;
    oracle_t expected;
    memset(&expected, 0, sizeof(expected));
    halfband_init(&actual);
    for (int n = 0; n < 128; ++n) {
        float in;
        if (kind == 0) {
            in = n == 0 ? 0.5f : 0.0f;
        } else if (kind == 1) {
            in = (float)(n - 63) / 127.0f;
        } else {
            const float phase = 6.2831853071795864769f * (rate * 0.037f) *
                                (float)n / rate;
            in = 0.7f * sinf(phase);
        }
        float got0, got1, want0, want1;
        halfband_interpolate(&actual, in, &got0, &got1);
        oracle_interpolate(&expected, in, &want0, &want1);
        if (!isfinite(got0) || !isfinite(got1) ||
            fabsf(got0 - want0) > 1.0e-6f || fabsf(got1 - want1) > 1.0e-6f) {
            fprintf(stderr,
                    "%s rate=%.0f tick=%d got=(%.9g,%.9g) expected=(%.9g,%.9g)\n",
                    name, rate, n, got0, got1, want0, want1);
            return 0;
        }
    }
    return 1;
}

int main(void) {
    for (int i = 0; i < HB_TAPS; ++i) {
        if (fabsf(g_hb_coeffs[i] - kReferenceCoeffs[i]) > 1.0e-9f) {
            fprintf(stderr, "production half-band tap %d differs from pinned reference\n", i);
            return 1;
        }
    }
    /* Rates exercise the rate-independent 2x filter with audio at a fixed
     * normalized frequency; the full engine is separately smoke-rendered at
     * the nominal FM-1 rate and at these host rates by pytest. */
    static const float rates[] = { 22050.0f, 44118.0f, 48000.0f, 96000.0f, 192000.0f };
    for (unsigned r = 0; r < sizeof(rates) / sizeof(rates[0]); ++r) {
        if (!check_sequence("impulse", rates[r], 0) ||
            !check_sequence("ramp", rates[r], 1) ||
            !check_sequence("sine", rates[r], 2)) return 1;
    }
    puts("PSX Verb interpolator matches direct zero-stuffed FIR at 5 host rates");
    return 0;
}

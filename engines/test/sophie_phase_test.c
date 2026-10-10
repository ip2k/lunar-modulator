/* Focused regression for Sophie’s high-ratio oscillator phase wrapping. */
#include "../third_party/schwung-modules/sophie/sophie.c"

#include <assert.h>
#include <math.h>
#include <stdio.h>

static double modulo_reference(double x) {
    double wrapped = fmod(x, (double)SOPHIE_TAU);
    return wrapped < 0.0 ? wrapped + (double)SOPHIE_TAU : wrapped;
}

int main(void) {
    static const int rates[] = {44118, 8000};
    static const float ratios[] = {8.07f, 12.48f, 17.8f};
    const float in_range[] = {0.0f, 0.25f, SOPHIE_TAU * 0.5f,
                              SOPHIE_TAU - 0.001f};
    size_t i, r, j;

    /* The normal path must preserve its input exactly. */
    for (i = 0; i < sizeof(in_range) / sizeof(in_range[0]); ++i)
        assert(wrap_phase(in_range[i]) == in_range[i]);
    {
        const float one_turn = 1.5f * SOPHIE_TAU - SOPHIE_TAU;
        const float negative_turn = -0.25f + SOPHIE_TAU;
        assert(wrap_phase(SOPHIE_TAU + 0.25f) == 0.25f);
        assert(wrap_phase(1.5f * SOPHIE_TAU) == one_turn);
        assert(wrap_phase(-0.25f) == negative_turn);
    }
    {
        const float multi_turn[] = {40.0f * SOPHIE_TAU + 0.25f,
                                    -40.0f * SOPHIE_TAU - 0.25f};
        for (i = 0; i < sizeof(multi_turn) / sizeof(multi_turn[0]); ++i) {
            const double expected = modulo_reference((double)multi_turn[i]);
            assert(fabs((double)wrap_phase(multi_turn[i]) - expected) < 6.0e-5);
        }
    }

    for (r = 0; r < sizeof(rates) / sizeof(rates[0]); ++r) {
        const float hz = 18000.0f;
        const float carrier_inc = SOPHIE_TAU * hz / (float)rates[r];
        for (j = 0; j < sizeof(ratios) / sizeof(ratios[0]); ++j) {
            const float increment = carrier_inc * ratios[j];
            float phase = 0.13f;
            int n;
            assert(increment > SOPHIE_TAU);
            for (n = 0; n < 10000; ++n) {
                const float advanced = phase + increment;
                const double expected = modulo_reference((double)advanced);
                phase = wrap_phase(advanced);
                assert(phase >= 0.0f && phase < SOPHIE_TAU);
                /* The production float quotient loses a few ulps at the
                 * largest increment; the bound still rejects missing turns. */
                assert(fabs((double)phase - expected) < 6.0e-5);
            }
        }
    }
    puts("{\"check\":\"sophie_phase_wrap\",\"rates\":[44118,8000],\"ratios\":3,\"steps_per_rate\":30000,\"total_steps\":60000,\"result\":\"pass\"}");
    return 0;
}

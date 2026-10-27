/* SPDX-License-Identifier: MIT. Desktop replay of the target workload. */
#include "renderer_live.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#if defined(__GLIBC__)
#include <fenv.h>
extern int feenableexcept(int);
#endif

int main(int argc, char **argv) {
    FILE *pcm = NULL;
#if defined(__GLIBC__)
    /* Match the chip's divide-by-zero trap in offline regression runs. */
    if (getenv("LUNAR_TRAP_DIVZERO")) feenableexcept(FE_DIVBYZERO);
#endif
    if (argc > 2) return 2;
    if (argc == 2 && !(pcm = fopen(argv[1], "wb"))) return 2;
    if (!lunar_devkit_renderer_init()) {
        struct lunar_renderer_status failure;
        lunar_devkit_renderer_status(&failure);
        fprintf(stderr, "full renderer initialization refused: stage %u\n", failure.init_error);
        for (unsigned i = 0; i < 8; ++i) fprintf(stderr, "unit %u: %u bytes\n", i, failure.unit_bytes[i]);
        if (pcm) fclose(pcm);
        return 1;
    }
    struct lunar_renderer_status state;
    uint32_t completed = 0;
    uint64_t energy = 0;
    unsigned nonzero_cases = 0;
    struct { uint32_t before; int16_t samples[256]; uint32_t after; } output;
    output.before = 0xa5c31f9bu; output.after = 0x71d9b3e5u;
    do {
        lunar_devkit_renderer_render(output.samples);
        assert(output.before == 0xa5c31f9bu && output.after == 0x71d9b3e5u);
        for (unsigned i = 0; i < 64; ++i) {
            for (unsigned ch = 0; ch < 2; ++ch) {
                int32_t x = output.samples[4*i+ch];
                assert(x == output.samples[4*i+ch+2]);
                energy += (uint64_t)(x*x);
                if (pcm) {
                    unsigned char bytes[2] = {(unsigned char)x, (unsigned char)((uint16_t)x >> 8)};
                    if (fwrite(bytes, 1, 2, pcm) != 2) return 2;
                }
            }
        }
        lunar_devkit_renderer_status(&state);
        assert(!state.invalid && !state.clipped);
        if (state.completed_cases != completed) {
            assert(state.completed_cases == completed + 1);
            assert(state.completed_case == completed % 4);
            assert(energy > 0);
            ++nonzero_cases; energy = 0; completed = state.completed_cases;
            printf("LUNAR_RENDERER completed=%u case=%u hash=%08x blocks=%u controls=%u arena=%u invalid=%u clipped=%u workload=" LUNAR_RENDERER_WORKLOAD_NAME "\n",
                completed, state.completed_case, state.completed_hash, state.blocks,
                state.controls, state.arena_bytes, state.invalid, state.clipped);
        }
        assert(state.blocks <= 8u * ((8u * 44100u + 63u) / 64u));
    } while (state.cycles < 2);
    assert(nonzero_cases == 8 && state.controls > 100 && state.arena_bytes > 0);
#ifdef LUNAR_RENDERER_PROFILE
    for (unsigned i = 0; i < 8; ++i) {
        struct lunar_renderer_profile p;
        lunar_devkit_renderer_profile_read(i, &p);
        if (i < (LUNAR_RENDERER_WORKLOAD == 1 ? 4u : 8u)) {
            assert(p.calls && p.frames == state.blocks * 64u);
        } else {
            assert(!p.calls && !p.frames && !p.ticks && !p.max_ticks);
        }
    }
#endif
    if (pcm && fclose(pcm)) return 2;
    return 0;
}

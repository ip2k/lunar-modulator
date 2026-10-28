/* SPDX-License-Identifier: MIT */
#include "fm6_benchmark.h"
#include "fm1_engine.h"
#include <string.h>

extern "C" const fm1_engine_t fm1_engine_dx7;
/* Capacity is deliberate, not the engine's actual size. Report the latter
 * per case; static aligned storage avoids heap and task-stack dependency. */
static unsigned char memory[65536] __attribute__((aligned(16)));
static float output[128];

extern "C" int lunar_devkit_fm6_benchmark(uint32_t (*now)(void),
                                        void (*emit)(const lunar_fm6_result *)) {
    const fm1_engine_t *e = &fm1_engine_dx7;
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, 44100.f, 64};
    const unsigned voices[] = {1, 4, 8, 12};
    const unsigned patches[] = {0, 19, 25}; /* TINE EP, WARM PAD, SAW LEAD */
    if (!now || !emit) return 0;
    const size_t bytes = e->instance_size(&host);
    if (bytes > sizeof(memory)) return 0;
    for (unsigned p = 0; p < 3; ++p) for (unsigned v = 0; v < 4; ++v) {
        lunar_fm6_result r = {};
        r.patch = patches[p]; r.voices = voices[v]; r.blocks = 256;
        r.instance_bytes = static_cast<uint32_t>(bytes);
        r.min_ticks = UINT32_MAX; r.checksum = 2166136261u;
        void *s = e->create(memory, &host);
        if (!s) return 0;
        e->set_param(s, 0, static_cast<float>(r.patch));
        uint32_t start = now();
        for (unsigned n = 0; n < r.voices; ++n) e->note_on(s, 36 + n * 3, 100);
        r.note_on_ticks = now() - start;
        // Include the first cold render. Measure note events separately;
        // checksums and result emission are never inside a timed region.
        for (unsigned b = 0; b < r.blocks; ++b) {
            if (b == 192) {
                start = now();
                for (unsigned n = 0; n < r.voices; ++n) e->note_off(s, 36 + n * 3);
                r.note_off_ticks = now() - start;
            }
            start = now(); e->render(s, output, 64);
            const uint32_t dt = now() - start;
            r.ticks += dt;
            if (dt < r.min_ticks) r.min_ticks = dt;
            if (dt > r.max_ticks) r.max_ticks = dt;
            for (unsigned i = 0; i < 128; ++i) {
                uint32_t bits; memcpy(&bits, output + i, sizeof(bits));
                if ((bits & 0x7f800000u) == 0x7f800000u) ++r.invalid_samples;
                if (bits & 0x7fffffffu) ++r.nonzero_samples;
                r.checksum = (r.checksum ^ bits) * 16777619u;
            }
        }
        e->destroy(s);
        emit(&r);
        if (r.invalid_samples || !r.nonzero_samples) return 0;
    }
    return 1;
}

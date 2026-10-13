/* SPDX-License-Identifier: MIT */
/* Host oracle for native adapter output and caller-buffer boundaries. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "fm1_engine.h"
#include "engine_adapter.h"
extern const fm1_engine_t fm1_engine_trio;
static unsigned char reference_mem[128u * 1024u] __attribute__((aligned(16)));
int main(int argc, char **argv)
{
    const fm1_engine_t *engine = &fm1_engine_trio;
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, 44100.0f, 64};
    unsigned shard, trial, block, i;
    if (argc != 2) return 2;
    shard = (unsigned)strtoul(argv[1], NULL, 10);
    if (shard >= 16) return 2;
    if (lunar_engine_init(32000)) return 3; /* engine must reject unsupported rate */
    {
        int32_t guarded[130];
        for (i = 0; i < 130; i++) guarded[i] = 0x12345;
        lunar_engine_render(guarded, 64); /* rejected init must not render */
        lunar_engine_note_on(60, 100);
        lunar_engine_all_notes_off();
        if (!lunar_engine_init(44100)) return 4;
        lunar_engine_render(guarded, 65); /* oversized blocks must not write */
        lunar_engine_render(guarded, 0);
        for (i = 0; i < 130; i++) if (guarded[i] != 0x12345) return 9;
    }
    for (trial = shard; trial < 128; trial += 16) {
        unsigned note = 24 + trial % 80, velocity = 1 + trial % 127;
        void *ref;
        if (!lunar_engine_init(44100)) return 4;
        if (engine->instance_size(&host) > sizeof reference_mem) return 5;
        ref = engine->create(reference_mem, &host);
        if (!ref) return 6;
        lunar_engine_note_on(note, velocity);
        engine->note_on(ref, note, velocity);
        for (block = 0; block < 96; block++) {
            unsigned frames = 1 + (trial + block) % 64;
            int32_t actual[130];
            float expected[128];
            for (i = 0; i < 130; i++) actual[i] = 0x12345;
            if (block == 32) { lunar_engine_note_off(note); engine->note_off(ref, note); }
            if (block == 64) {
                lunar_engine_all_notes_off();
                for (i = 0; i < 128; i++) engine->note_off(ref, (uint8_t)i);
            }
            lunar_engine_render(actual + 1, frames);
            engine->render(ref, expected, frames);
            if (actual[0] != 0x12345 || actual[frames * 2 + 1] != 0x12345) return 7;
            for (i = 0; i < frames * 2; i++) {
                float x = expected[i];
                if (!(x == x)) x = 0;
                if (x > 1) x = 1;
                if (x < -1) x = -1;
                if (actual[i + 1] != 0x12345 + (int32_t)(x * 32767)) {
                    fprintf(stderr, "shard=%u trial=%u block=%u sample=%u\n", shard, trial, block, i);
                    return 8;
                }
            }
        }
        engine->destroy(ref);
    }
    printf("shard %u: 8 note/velocity trials, 768 blocks passed\n", shard);
    return 0;
}

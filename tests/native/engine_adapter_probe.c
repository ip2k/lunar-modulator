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
        if (trial & 1u) lunar_engine_event(0x93, note, velocity);
        else lunar_engine_note_on(note, velocity);
        engine->note_on(ref, note, velocity);
        for (block = 0; block < 96; block++) {
            unsigned frames = 1 + (trial + block) % 64;
            int32_t actual[130];
            float expected[128];
            for (i = 0; i < 130; i++) actual[i] = 0x12345;
            if (block == 8 || block == 16 || block == 24) {
                uint16_t raw = block == 8 ? 0 : block == 16 ? 16383 : 8192;
                lunar_engine_event(0xe5, raw & 127u, raw >> 7);
                engine->pitch_bend(ref, block == 8 ? -2.0f : block == 16 ? 2.0f : 0.0f);
            }
            if (block == 12 || block == 20) {
                uint16_t index = trial % engine->n_params;
                const fm1_param_t *p = &engine->params[index];
                unsigned value7 = block == 12 ? trial % 128 : 127;
                float value = fm1_param_at(p, (float)value7 / 127.0f);
                if (p->type == FM1_PARAM_ENUM) value = p->min + (float)(int)(value - p->min + 0.5f);
                lunar_engine_event(0xb2, 16 + index, value7);
                engine->set_param(ref, index, value);
                if (lunar_engine_param_position(index) !=
                    (uint8_t)(fm1_param_pos(p, value) * 100.0f + 0.5f)) return 10;
            }
            if (block == 28) {
                uint16_t index = trial % engine->n_params;
                const fm1_param_t *p = &engine->params[index];
                /* Previous CC set the maximum. A negative detent must move
                 * one enum choice or one percent along the continuous law. */
                float value = p->type == FM1_PARAM_ENUM ? p->max - 1.0f : fm1_param_at(p, 0.99f);
                value = fm1_param_clamp(p, value);
                lunar_engine_event(1, index, (uint8_t)(int8_t)-1);
                engine->set_param(ref, index, value);
                lunar_engine_event(1, 255, 1); /* invalid index cannot touch audio */
                lunar_engine_event(0xb0, 15, 127); /* unmapped controller */
            }
            if (block == 32) { lunar_engine_event(0x90, note, 0); engine->note_off(ref, note); }
            if (block == 64) {
                lunar_engine_event(0xbf, 123, 0);
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
    if (lunar_engine_param_count() != engine->n_params ||
        strcmp(lunar_engine_param_name(0), engine->params[0].abbr) ||
        strcmp(lunar_engine_param_name(65535), "") || lunar_engine_param_position(65535)) return 11;
    if (lunar_engine_init(32000)) return 12;
    {
        int32_t out[128] = {0};
        lunar_engine_event(0x90, 60, 127);
        lunar_engine_render(out, 64);
        for (i = 0; i < 128; i++) if (out[i]) return 13;
    }
    printf("shard %u: 8 control/note/velocity trials, 768 blocks passed\n", shard);
    return 0;
}

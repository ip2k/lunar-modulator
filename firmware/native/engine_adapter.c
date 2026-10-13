/* SPDX-License-Identifier: GPL-3.0-only */
/* Separate standard-library declarations from the freestanding platform libc. */
#include "engine_adapter.h"
#include "fm1_engine.h"
extern const fm1_engine_t fm1_engine_trio;
static const fm1_engine_t *const engine = &fm1_engine_trio;
static unsigned char instance_mem[128u * 1024u]
    __attribute__((section(".pool"), aligned(16)));
static float render_lr[64u * 2u];
static void *instance;
int lunar_engine_init(uint32_t sample_rate)
{
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, (float)sample_rate, 64u};
    if (engine->instance_size(&host) > sizeof instance_mem) return 0;
    instance = engine->create(instance_mem, &host);
    return instance != NULL;
}
void lunar_engine_note_on(uint8_t key, uint8_t velocity)
{ engine->note_on(instance, key, velocity); }
void lunar_engine_note_off(uint8_t key)
{ engine->note_off(instance, key); }
void lunar_engine_render(int32_t *out, uint32_t frames)
{
    uint32_t i;
    engine->render(instance, render_lr, frames);
    for (i = 0; i < frames * 2u; i++) {
        float x = render_lr[i];
        if (!(x == x)) x = 0.0f;
        if (x > 1.0f) x = 1.0f;
        if (x < -1.0f) x = -1.0f;
        out[i] += (int32_t)(x * 32767.0f);
    }
}

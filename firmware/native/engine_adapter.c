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
static float parameter[16];
static volatile uint8_t position[16];
int lunar_engine_init(uint32_t sample_rate)
{
    uint16_t i;
    const fm1_host_t host = {FM1_ENGINE_API_VERSION, (float)sample_rate, 64u};
    if (instance) engine->destroy(instance);
    instance = NULL;
    if (engine->n_params > 16u || engine->instance_size(&host) > sizeof instance_mem) return 0;
    instance = engine->create(instance_mem, &host);
    for (i = 0; i < engine->n_params; i++) {
        parameter[i] = engine->params[i].def;
        position[i] = (uint8_t)(fm1_param_pos(&engine->params[i], parameter[i]) * 100.0f + 0.5f);
    }
    return instance != NULL;
}
uint16_t lunar_engine_param_count(void) { return engine->n_params; }
const char *lunar_engine_param_name(uint16_t index)
{ return index < engine->n_params ? engine->params[index].abbr : ""; }
uint8_t lunar_engine_param_position(uint16_t index)
{ return index < engine->n_params && index < 16u ? position[index] : 0; }
static void parameter_set(uint16_t index, float value)
{
    const fm1_param_t *p = &engine->params[index];
    value = fm1_param_clamp(p, value);
    if (p->type == FM1_PARAM_ENUM) value = p->min + (float)(int)(value - p->min + 0.5f);
    parameter[index] = value;
    engine->set_param(instance, index, value);
    position[index] = (uint8_t)(fm1_param_pos(p, value) * 100.0f + 0.5f);
}
void lunar_engine_event(uint8_t status, uint8_t a, uint8_t b)
{
    uint8_t kind = status & 0xf0u;
    if (!instance) return;
    if (status == 1u) {
        if (a < engine->n_params && a < 16u && engine->set_param) {
            const fm1_param_t *p = &engine->params[a];
            int step = (int8_t)b;
            float value = p->type == FM1_PARAM_ENUM ? parameter[a] + (float)step
                : fm1_param_at(p, fm1_param_pos(p, parameter[a]) + (float)step / 100.0f);
            parameter_set(a, value);
        }
    } else if (kind == 0x90u && b) lunar_engine_note_on(a & 127u, b & 127u);
    else if (kind == 0x80u || kind == 0x90u) lunar_engine_note_off(a & 127u);
    else if (kind == 0xe0u && engine->pitch_bend) {
        int bend = ((int)(b & 127u) << 7) + (a & 127u) - 8192;
        engine->pitch_bend(instance, 2.0f * (float)bend / (bend < 0 ? 8192.0f : 8191.0f));
    } else if (kind == 0xb0u) {
        if (a == 123u) lunar_engine_all_notes_off();
        else if (a >= 16u && a < 32u && (uint16_t)(a - 16u) < engine->n_params && engine->set_param)
            parameter_set(a - 16u, fm1_param_at(&engine->params[a - 16u], (float)(b & 127u) / 127.0f));
    }
}
void lunar_engine_note_on(uint8_t key, uint8_t velocity)
{ if (instance) engine->note_on(instance, key, velocity); }
void lunar_engine_note_off(uint8_t key)
{ if (instance) engine->note_off(instance, key); }
void lunar_engine_all_notes_off(void)
{
    uint32_t key;
    for (key = 0; key < 128u; key++) lunar_engine_note_off((uint8_t)key);
}
void lunar_engine_render(int32_t *out, uint32_t frames)
{
    uint32_t i;
    if (!instance || !out || frames > 64u || frames == 0u) return;
    engine->render(instance, render_lr, frames);
    for (i = 0; i < frames * 2u; i++) {
        float x = render_lr[i];
        if (!(x == x)) x = 0.0f;
        if (x > 1.0f) x = 1.0f;
        if (x < -1.0f) x = -1.0f;
        out[i] += (int32_t)(x * 32767.0f);
    }
}

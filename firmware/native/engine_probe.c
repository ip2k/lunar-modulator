/* SPDX-License-Identifier: GPL-3.0-only */
/* Native engine integration probe. Build only; device admission is separate. */
#define APP_NAME "LUNAR MODULATOR"
#define APP_VER "NATIVE PROBE"
#include "platform.c"
#include "engine_adapter.h"

static volatile uint32_t engine_ready;
static volatile uint32_t render_ticks_max, render_overruns, event_overflow;
static volatile uint32_t event_write, event_read;
static uint32_t events[64];

/* Main loop produces, audio ISR consumes. Payload precedes publication. */
static void enqueue(uint8_t status, uint8_t note, uint8_t velocity)
{
    uint32_t w = event_write;
    if (w - event_read == 64u) { event_overflow++; return; }
    events[w & 63u] = status | ((uint32_t)note << 8) | ((uint32_t)velocity << 16);
    RING_PUBLISH();
    event_write = w + 1u;
}
static void app_audio(int32_t *out, uint32_t n)
{
    uint32_t start, offset, r;
    if (!engine_ready) return;
    start = fm1_ticks();
    r = event_read;
    while (r != event_write) {
        uint32_t e = events[r & 63u];
        uint8_t st = e & 0xf0u, key = (e >> 8) & 127u, vel = (e >> 16) & 127u;
        if (st == 0x90u && vel) lunar_engine_note_on(key, vel);
        else if (st == 0x80u || st == 0x90u) lunar_engine_note_off(key);
        r++;
    }
    RING_PUBLISH();
    event_read = r;
    for (offset = 0; offset < n; offset += 64u) {
        uint32_t count = n - offset;
        if (count > 64u) count = 64u;
        lunar_engine_render(out + offset * 2u, count);
    }
    start = fm1_ticks() - start;
    if (start > render_ticks_max) render_ticks_max = start;
    if (start > (24000000u / FS) * n) render_overruns++;
}
static void app_main(void)
{
    uint32_t previous = 0, last_status = 0;
    uint8_t held[27] = {0};
    int octave = 0;
    uint32_t ready = lunar_engine_init(FS);
    lcd_fill(0, 0, 240, 240, C_BLACK);
    draw_text_box(0, 18, 240, &FONT_S, APP_NAME, C_WHITE, 1);
    draw_text_box(0, 52, 240, &FONT_S, ready ? "TRIO ENGINE PROBE" : "ENGINE INIT FAILED", C_WHITE, 1);
    RING_PUBLISH();
    engine_ready = ready;
    for (;;) {
        uint32_t k, released, buttons, keys, down, up;
        uint8_t st, a, b;
        platform_poll();
        keys = fm1_in.notes; down = keys & ~previous; up = previous & ~keys; previous = keys;
        for (k = 0; k < 27u; k++) {
            if ((down >> k) & 1u) {
                held[k] = (uint8_t)(53 + 12 * octave + (int)k);
                enqueue(0x90, held[k], 100); midi_send(0x90, held[k], 100);
            }
            if ((up >> k) & 1u) { enqueue(0x80, held[k], 0); midi_send(0x80, held[k], 0); }
            fm1_led_key(KEY_LED(k), (keys >> k) & 1u);
        }
        buttons = fm1_input_edges(&released);
        if ((buttons & (1u << BTN_OCT_DOWN)) && octave > -2) octave--;
        if ((buttons & (1u << BTN_OCT_UP)) && octave < 2) octave++;
        while (midi_get(&st, &a, &b)) enqueue(st, a, b);
        if (fm1_ms - last_status >= 500u) {
            char text[16];
            last_status = fm1_ms;
            fmt_int(text, (int32_t)(render_ticks_max / FM1_TICKS_PER_US));
            draw_text_box(0, 100, 240, &FONT_S, "PEAK AUDIO US", C_WHITE, 1);
            draw_text_box(0, 124, 240, &FONT_S, text, C_WHITE, 1);
            fmt_int(text, (int32_t)render_overruns);
            draw_text_box(0, 158, 240, &FONT_S, "OVERRUNS", C_WHITE, 1);
            draw_text_box(0, 182, 240, &FONT_S, text, C_WHITE, 1);
        }
    }
}

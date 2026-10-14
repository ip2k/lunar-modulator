/* SPDX-License-Identifier: GPL-3.0-only */
#ifndef LUNAR_NATIVE_SAVE_QUIESCE_H
#define LUNAR_NATIVE_SAVE_QUIESCE_H
#include "audio_pause.h"
/* Include after the generated native platform. Core-0 main loop only, entered
 * with global IRQs enabled. The synchronous caller owns drawing/application
 * state until end. TIMER5 remains enabled between these short critical sections.
 * No storage ownership is granted. USB packets already queued may still drain. */
static int lunar_save_quiesce_begin(void *ctx)
{
    lunar_audio_pause_t *p = ctx;
    if (!p || p->active) return -1;
    if (lcd_busy && !(FM1_LCD_SPI_CON & 0x8000u)) return 0;
    lcd_sync();
    fm1_irq_off();
    int ok = lunar_audio_pause_begin(p, &audio_queue, abuf,
                                     sizeof abuf / sizeof abuf[0]);
    if (ok) {
        /* With ALNK masked, no producer can re-prime during SAVE. TIMER5's
         * uac_packet emits silence while go=0, instead of repeating last. */
        uac.go = 0;
        uac.feed = 0;
        uac.last = 0;
        ua_w = ua_r;
        lunar_audio_publish();
    }
    fm1_irq_on();
    return ok ? 1 : -1;
}

static void lunar_save_quiesce_end(void *ctx)
{
    fm1_irq_off();
    (void)lunar_audio_pause_end(ctx);
    /* Do not restore the old USB ring/go state. Its next ALNK render primes
     * from silence, including resampler history if the host selected 48 kHz. */
    fm1_irq_on();
}
#endif

/* SPDX-License-Identifier: GPL-3.0-only
 * New bounded adapter over Dinghy's GPL base HAL. No updater, settings,
 * USB commands, SDK calls or CPU1 backend are included. The separately guarded
 * return binding is unqualified and refuses functional startup in this candidate. */
#include <stdint.h>
#include "diagnostic_api.h"
#include "selected_return_pi32v2.h"
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
#include "platform_hal.h" /* host test only; actual owner body below is shared */
#else
#include "fm1_time.h"
#include "fm1_irq.h"
#include "fm1_input.h"
#include "fm1_timer.h"
#include "fm1_lcd_hw.h"
#include "fm1_audio.h"
#include "lcd.c"
#endif

#define HALF_FRAMES 64u
#define HALF_WORDS (2u * HALF_FRAMES)
static int32_t audio[2u * HALF_WORDS] __attribute__((aligned(16)));
static uint32_t keys;
static lunar_selected_return_t return_policy;
static volatile uint32_t audio_may_run;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
const lunar_selected_return_t *lunar_sr_platform_test_state(void) { return &return_policy; }
#endif
extern void isr_timer5(void), isr_alnk0(void);

void fm1_timer5_irq(void) { fm1_timer5_ack(); fm1_input_tick(); }
void fm1_alnk0_irq(void) {
  uint8_t p = fm1_audio_pending();
  fm1_audio_ack_aux(p);
  if (p & FM1_AUDIO_HALF) {
    int32_t *out = audio + fm1_audio_free_half() * HALF_WORDS;
    uint32_t now = fm1_in.notes, changed = now ^ keys;
    for (unsigned k = 0; k < 27; ++k)
      if (changed & (1u << k)) lunar_diagnostic_key(k, (now >> k) & 1u);
    keys = now;
    /* Preserve IRQ state while draining encoder deltas. The upstream
     * fm1_enc_take helper unconditionally enables IRQs, so it is not used
     * from this ISR. Timer5 can resume before app mutation/render. */
    for (unsigned e = 3; e <= 6; ++e) {
      uint32_t icfg = fm1_icfg();
      fm1_icfg_set(icfg & ~0x100u);
      int delta = fm1_in.enc_steps[e];
      fm1_in.enc_steps[e] = 0;
      fm1_icfg_set(icfg);
      lunar_diagnostic_knob((int)e, delta);
    }
    (void)lunar_diagnostic_render(out, HALF_FRAMES);
    for (unsigned i = 0; i < HALF_WORDS; ++i) out[i] *= 128;
    fm1_audio_ack_half();
  }
}
void lunar_selected_return_stop_audio(void) {
  /* Called only after policy terminal publication; no app/P33 or retry. */
  if (audio_may_run) { audio_may_run=0; fm1_audio_stop(); }
}
static void fm1_fault(const fm1_crash_t *crash) {
  (void)crash;
  lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
}
void lunar_diagnostic_cstart(void) {
#ifndef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  extern uint32_t _data_start[], _data_end[], _data_load[], _bss_start[], _bss_end[];
  uint32_t *s, *d;
  /* Initialise C storage before calling code which reads/writes globals. */
  for (s = _data_load, d = _data_start; d < _data_end;) *d++ = *s++;
  for (d = _bss_start; d < _bss_end;) *d++ = 0;
#endif /* host C runtime already initialized storage in the injected test */
  /* Exact real qualification is all zero: this call halts before timer,
   * mailbox/P33, IRQ/app/LCD/audio work. A future physical qualification must
   * separately establish exclusive configured TIMER4 ownership before entry.
   * No inherited write guard is disabled by this candidate. */
  (void)lunar_selected_return_target_prepare(&return_policy);
  fm1_irq_init();
  int healthy=lunar_diagnostic_init()==0;
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_APP_READY,healthy);
  lcd_init();
  lcd_fill(0, 0, 240, 240, 0); /* diagnostic has no interactive screen */
  lcd_sync();
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_LCD_READY,
                                      fm1_lcd_timeouts==0);
  fm1_input_init();
  audio_may_run=1;
  fm1_audio_init(audio, HALF_WORDS, isr_alnk0, 3);
  fm1_timer5_start(isr_timer5, 4);
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_IO_READY,1);
  fm1_irq_enable_all();
  for (;;) {
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
    lunar_sr_test_barrier();
#else
    __asm__ volatile("csync" ::: "memory");
#endif
    (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_MAIN,
                                        lunar_diagnostic_status()==0);
  }
}

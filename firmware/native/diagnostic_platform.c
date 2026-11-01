/* SPDX-License-Identifier: GPL-3.0-only
 * New bounded adapter over Dinghy's GPL base HAL. No updater, settings,
 * reset/UBOOT, USB commands, SDK calls or CPU1 backend are included. */
#include <stdint.h>
#include "diagnostic_api.h"
#include "fm1_time.h"
#include "fm1_irq.h"
#include "fm1_input.h"
#include "fm1_timer.h"
#include "fm1_lcd_hw.h"
#include "fm1_audio.h"
#include "lcd.c"

#define HALF_FRAMES 64u
#define HALF_WORDS (2u * HALF_FRAMES)
static int32_t audio[2u * HALF_WORDS] __attribute__((aligned(16)));
static uint32_t keys;
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
      fm1_irq_off();
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
static void fm1_fault(const fm1_crash_t *crash) {
  (void)crash;
  fm1_audio_stop();
  lunar_diagnostic_fault(6);
  /* Deliberately no reset or fail-open claim: later install admission must
   * supply reviewed bootguard/fallback. Keep exception state for debugger. */
  for (;;) __asm__ volatile("csync" ::: "memory");
}
void lunar_diagnostic_cstart(void) {
  extern uint32_t _data_start[], _data_end[], _data_load[], _bss_start[], _bss_end[];
  uint32_t *s, *d;
  /* Initialise C storage before calling code which reads/writes globals. */
  for (s = _data_load, d = _data_start; d < _data_end;) *d++ = *s++;
  for (d = _bss_start; d < _bss_end;) *d++ = 0;
  fm1_time_init();
  fm1_irq_init();
  if (lunar_diagnostic_init()) for (;;) __asm__ volatile("csync");
  lcd_init();
  lcd_fill(0, 0, 240, 240, 0); /* diagnostic has no interactive screen */
  lcd_sync();
  fm1_input_init();
  fm1_audio_init(audio, HALF_WORDS, isr_alnk0, 3);
  fm1_timer5_start(isr_timer5, 4);
  fm1_irq_enable_all();
  for (;;) __asm__ volatile("csync" ::: "memory");
}

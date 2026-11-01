/* SPDX-License-Identifier: GPL-3.0-only
 * Typed host-only HAL shims. No SPI/completion/clock model or target MMIO. */
#ifndef LUNAR_SELECTED_RETURN_TARGET_INJECTED
#error "platform test HAL is injected-host only"
#endif
typedef struct { uint32_t unused; } fm1_crash_t;
static void fm1_fault(const fm1_crash_t *);
typedef struct { uint32_t notes; int enc_steps[7]; } platform_input_t;
extern platform_input_t fm1_in;
extern uint32_t fm1_lcd_timeouts;
#define FM1_AUDIO_HALF 0x80u
void lunar_sr_platform_irq_init(void);
static inline void fm1_irq_init(void) {
  (void)fm1_fault; lunar_sr_platform_irq_init();
}
void fm1_timer5_ack(void),fm1_input_tick(void),fm1_audio_ack_aux(uint8_t);
void fm1_audio_ack_half(void),fm1_audio_stop(void),fm1_irq_enable_all(void);
uint8_t fm1_audio_pending(void);
uint32_t fm1_audio_free_half(void),fm1_icfg(void);
void fm1_icfg_set(uint32_t);
void lcd_init(void),lcd_fill(int,int,int,int,int),lcd_sync(void),fm1_input_init(void);
void fm1_audio_init(int32_t *,uint32_t,void (*)(void),uint32_t);
void fm1_timer5_start(void (*)(void),uint32_t);

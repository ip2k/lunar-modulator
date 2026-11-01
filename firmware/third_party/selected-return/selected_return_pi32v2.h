/* SPDX-License-Identifier: GPL-3.0-only
 * Offline candidate only; see UPSTREAM.md. No physical qualification supplied. */
#ifndef LUNAR_SELECTED_RETURN_PI32V2_H
#define LUNAR_SELECTED_RETURN_PI32V2_H
#ifndef LUNAR_SELECTED_RETURN_PI32V2_BINDING
#error "explicit target binding selection required"
#endif
#include "selected_return.h"
/* Independent, measured upper bounds are required; none has a default value.
 * phase + final feed + post-arm tail must fit inside the shortest reset lease.
 * Masked feed allowance must also fit inside the qualified audio IRQ budget.
 * All units are the independently qualified TIMER4 ticks. */
typedef struct {
  lunar_selected_return_qualification_t policy;
  uint32_t timer_frequency_qualified,p33_timing_qualified;
  uint32_t feed_bound_ticks,post_arm_tail_bound_ticks;
  uint32_t masked_feed_bound_ticks,audio_irq_allowance_ticks;
} lunar_selected_return_target_qualification_t;
int lunar_selected_return_target_prepare(lunar_selected_return_t *);
/* Pure validation of a supplied evidence record; does not grant write access. */
int lunar_selected_return_target_bounds(const lunar_selected_return_target_qualification_t *);
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
const lunar_selected_return_target_qualification_t *lunar_sr_test_qualification(void);
extern volatile uint8_t lunar_sr_test_mailbox[LUNAR_SR_MAILBOX_BYTES];
uint32_t lunar_sr_test_timer_con(void),lunar_sr_test_timer_prd(void),lunar_sr_test_timer_count(void);
uint32_t lunar_sr_test_icfg_read(void),lunar_sr_test_p33_con_read(void);
void lunar_sr_test_icfg_write(uint32_t),lunar_sr_test_p33_con_write(uint32_t);
uint8_t lunar_sr_test_p33_dat_read(void);
void lunar_sr_test_p33_dat_write(uint8_t),lunar_sr_test_barrier(void);
_Noreturn void lunar_sr_test_halt(void);
#else
/* Defined only by the separately selected candidate platform. Called after the
 * policy is already sticky terminal. No app, logging, allocation or P33 here. */
void lunar_selected_return_stop_audio(void);
#endif
#endif

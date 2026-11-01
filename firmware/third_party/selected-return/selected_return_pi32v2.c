/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments
 * Narrow Dinghy-derived register binding; provenance and limits in UPSTREAM.md.
 * Exact register operations, never a generic MMIO/reset API. */
#include "selected_return_pi32v2.h"

#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
#define MAILBOX lunar_sr_test_mailbox
static void sync(void) { lunar_sr_test_barrier(); }
#define READ32(name,address,hook) static uint32_t name(void *p) { \
  (void)p; uint32_t v=hook(); sync(); return v; }
#define WRITE32(name,address,hook) static void name(void *p,uint32_t v) { \
  (void)p; hook(v); sync(); }
#else
static volatile uint8_t mailbox[LUNAR_SR_MAILBOX_BYTES]
  __attribute__((section(".selected_return_mailbox"),aligned(4),used));
#define MAILBOX mailbox
static void sync(void) { __asm__ volatile("csync" ::: "memory"); }
#define READ32(name,address,hook) static uint32_t name(void *p) { \
  (void)p; uint32_t v=*(volatile uint32_t *)(address); sync(); return v; }
#define WRITE32(name,address,hook) static void name(void *p,uint32_t v) { \
  (void)p; *(volatile uint32_t *)(address)=v; sync(); }
#endif
READ32(timer_con,0x10800u,lunar_sr_test_timer_con)
READ32(timer_prd,0x10808u,lunar_sr_test_timer_prd)
READ32(timer_count,0x10804u,lunar_sr_test_timer_count)
READ32(p33_con_read,0x13e08u,lunar_sr_test_p33_con_read)
WRITE32(p33_con_write,0x13e08u,lunar_sr_test_p33_con_write)
static uint32_t icfg_read(void *p) {
  (void)p;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  return lunar_sr_test_icfg_read();
#else
  uint32_t v; __asm__ volatile("%0 = icfg" : "=r"(v) : : "memory"); return v;
#endif
}
static void icfg_write(void *p,uint32_t v) {
  (void)p;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  lunar_sr_test_icfg_write(v);
#else
  __asm__ volatile("icfg = %0" : : "r"(v) : "memory");
#endif
  sync();
}
static uint8_t p33_dat_read(void *p) {
  (void)p;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  uint8_t v=lunar_sr_test_p33_dat_read(); sync(); return v;
#else
  /* Historical DAT is a 32-bit register; low byte is protocol data. */
  uint32_t v=*(volatile uint32_t *)0x13e0cu; sync(); return (uint8_t)v;
#endif
}
static void p33_dat_write(void *p,uint8_t v) {
  (void)p;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  lunar_sr_test_p33_dat_write(v); sync();
#else
  *(volatile uint32_t *)0x13e0cu=v; sync();
#endif
}
static void publish(void *p) { (void)p; sync(); }
static _Noreturn void halt(void *p) {
  (void)p;
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  lunar_sr_test_halt();
#else
  lunar_selected_return_stop_audio();
  for(;;) sync();
#endif
}
static const lunar_selected_return_io_t io={0,timer_con,timer_prd,timer_count,
  icfg_read,icfg_write,p33_con_read,p33_con_write,p33_dat_read,p33_dat_write,
  &MAILBOX,publish,halt};

int lunar_selected_return_target_bounds(const lunar_selected_return_target_qualification_t *q) {
  if(!q || q->timer_frequency_qualified!=1 || q->p33_timing_qualified!=1 ||
     !q->feed_bound_ticks || !q->post_arm_tail_bound_ticks ||
     !q->masked_feed_bound_ticks || !q->audio_irq_allowance_ticks ||
     q->masked_feed_bound_ticks>q->feed_bound_ticks ||
     q->masked_feed_bound_ticks>=q->audio_irq_allowance_ticks ||
     q->feed_bound_ticks>=q->policy.lease_ticks) return 0;
  uint32_t remaining=q->policy.lease_ticks-q->feed_bound_ticks;
  if(q->post_arm_tail_bound_ticks>=remaining) return 0;
  remaining-=q->post_arm_tail_bound_ticks;
  return q->policy.max_phase_ticks<remaining;
}
int lunar_selected_return_target_prepare(lunar_selected_return_t *s) {
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  const lunar_selected_return_target_qualification_t *q=lunar_sr_test_qualification();
#else
  /* No CLI/weak override/magic retained RAM can qualify physical behavior.
   * No measured watchdog lease, inherited guard permission, frequency or P33
   * latency record exists. This exact target candidate MUST refuse startup. */
  static const lunar_selected_return_target_qualification_t unqualified={0};
  const lunar_selected_return_target_qualification_t *q=&unqualified;
#endif
  lunar_selected_return_qualification_t policy={0};
  if(q) policy=q->policy;
  if(!lunar_selected_return_target_bounds(q)) policy.watchdog_qualified=0;
  return lunar_selected_return_prepare(s,&io,&policy);
}

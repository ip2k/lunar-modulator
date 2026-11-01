/* SPDX-License-Identifier: GPL-3.0-only
 * Reuse the register fake, never a second policy. Execute actual target binding. */
#include "selected_return_pi32v2.h"
#define main portable_main
#include "../selected_return/check.c"
#undef main

_Static_assert(_Generic(&f.policy.state,volatile uint32_t *:1,default:0),
               "exception-shared state must remain compiler-visible");
_Static_assert(_Generic(&f.policy.io,const lunar_selected_return_io_t *volatile *:1,default:0),
               "exception-shared port pointer must remain compiler-visible");
volatile uint8_t lunar_sr_test_mailbox[LUNAR_SR_MAILBOX_BYTES];
static lunar_selected_return_target_qualification_t target_q;
static unsigned dirty;
const lunar_selected_return_target_qualification_t *lunar_sr_test_qualification(void) {
  return &target_q;
}
static void access(void) { assert(!dirty); dirty=1; }
uint32_t lunar_sr_test_timer_con(void) { access(); return timer_con(0); }
uint32_t lunar_sr_test_timer_prd(void) { access(); return timer_prd(0); }
uint32_t lunar_sr_test_timer_count(void) {
  access(); ++f.reads;
  if(f.reads==1) {
    assert(f.wdt==0x1a && !(f.mode&0x40));
    for(unsigned i=0;i<16;++i) assert(lunar_sr_test_mailbox[i]==(uint8_t)"usb_update_mode"[i]);
  }
  return f.now;
}
uint32_t lunar_sr_test_icfg_read(void) { return icfg_read(0); }
void lunar_sr_test_icfg_write(uint32_t v) { icfg_write(0,v); }
uint32_t lunar_sr_test_p33_con_read(void) { access(); return p33_con_read(0); }
void lunar_sr_test_p33_con_write(uint32_t v) { access(); p33_con_write(0,v); }
uint8_t lunar_sr_test_p33_dat_read(void) { access(); return p33_dat_read(0); }
void lunar_sr_test_p33_dat_write(uint8_t v) { access(); p33_dat_write(0,v); }
void lunar_sr_test_barrier(void) { dirty=0; atomic_signal_fence(memory_order_seq_cst); }
_Noreturn void lunar_sr_test_halt(void) { halt(0); __builtin_trap(); }
#ifndef LUNAR_SR_PLATFORM_TEST
void lunar_selected_return_stop_audio(void) { /* no active audio in register tests */ }
#endif
static void target_call(void) { (void)lunar_selected_return_target_prepare(&f.policy); }
static void fresh_target(void) {
  fresh(100);dirty=0;
  for(unsigned i=0;i<16;++i) lunar_sr_test_mailbox[i]=0xa5;
  target_q=(lunar_selected_return_target_qualification_t){f.q,1,1,100,100,100,200};
}
static void target_prepare(void) {
  uint32_t saved=f.icfg;
  assert(!lunar_selected_return_target_prepare(&f.policy));
  assert(f.policy.state==LUNAR_SR_ARMED && f.policy.backstop_armed);
  assert(f.policy.origin==f.now && f.reads==1 && f.transfers==24);
  assert(f.icfg==saved && !f.feed && !f.reset && !dirty);
}
int lunar_selected_return_binding_checks(void) {
  portable_main(); /* all 90 portable cases also run with volatile target fields */
  cases=0;
  for(unsigned n=0;n<11;++n) {
    fresh_target();
    switch(n) {
      case 0:memset(&target_q,0,sizeof target_q);break; /* real candidate record */
      case 1:target_q.timer_frequency_qualified=0;break;
      case 2:target_q.p33_timing_qualified=0;break;
      case 3:target_q.feed_bound_ticks=target_q.policy.lease_ticks;break;
      case 4:target_q.post_arm_tail_bound_ticks=target_q.policy.lease_ticks;break;
      case 5:target_q.policy.lease_ticks=target_q.policy.max_phase_ticks+200;break;
      case 6:target_q.masked_feed_bound_ticks=target_q.audio_irq_allowance_ticks;break;
      case 7:target_q.feed_bound_ticks=UINT32_MAX;break;
      case 8:target_q.masked_feed_bound_ticks=target_q.feed_bound_ticks+1;break;
      case 9:target_q.policy.mailbox_write_qualified=0;break;
      case 10:target_q.policy.watchdog_qualified=0;break;
    }
    expect_stop(target_call,LUNAR_SR_QUALIFICATION);
    assert(!f.reads && !f.transfers && !f.reset && !f.feed && !dirty);
    for(unsigned i=0;i<16;++i) assert(lunar_sr_test_mailbox[i]==0xa5);
  }
  fresh_target();
  target_q.policy.lease_ticks=target_q.policy.max_phase_ticks+201;
  assert(lunar_selected_return_target_bounds(&target_q)); /* strict sum boundary */
  target_prepare();phase=LUNAR_SR_APP_READY;++f.now;
  phase_call();assert(f.feed==1 && !f.reset && !dirty);
  unsigned tx=f.transfers;
  expect_stop(fault_call,LUNAR_SR_FAULT);assert(f.transfers==tx && !f.reset);
  for(unsigned n=1;n<=9;++n) {
    fresh_target();target_prepare();phase=LUNAR_SR_APP_READY;++f.now;
    f.fault_at=f.transfers+n;f.nested=1;
    expect_stop(phase_call,LUNAR_SR_FAULT);
    assert(f.transfers==24+n && !f.feed && !f.reset && f.halts==2);
  }
  for(unsigned n=1;n<=24;++n) {
    fresh_target();f.timeout_at=n;
    expect_stop(target_call,LUNAR_SR_P33);
    assert(f.transfers==n && f.policy.failed_byte==n && f.timeout_polls==4);
    assert(!f.reads && !f.feed && !f.reset && !dirty);
  }
  for(unsigned n=1;n<=9;++n) {
    fresh_target();target_prepare();phase=LUNAR_SR_APP_READY;++f.now;
    f.timeout_at=f.transfers+n;
    expect_stop(phase_call,LUNAR_SR_P33);
    assert(f.transfers==24+n && f.policy.failed_byte==24+n && f.timeout_polls==4);
    assert(!f.feed && !f.reset && !dirty);
  }
  for(unsigned n=1;n<=3;++n) {
    fresh_target();target_prepare();f.timeout_at=f.transfers+n;
    expect_stop(refuse_call,LUNAR_SR_INIT);
    assert(f.transfers==24+n && f.policy.failed_byte==24+n && f.timeout_polls==4);
    assert(!f.feed && !f.reset && !dirty);
  }
  fresh_target();target_prepare();phase=LUNAR_SR_APP_READY;++f.now;
  f.fault_after_feed=1;
  expect_stop(phase_call,LUNAR_SR_FAULT);
  assert(f.transfers==33 && f.feed==1 && !f.reset && !dirty);
  for(unsigned wrap=0;wrap<2;++wrap) {
    fresh_target();if(wrap) f.now=UINT32_MAX-8;target_prepare();
    for(phase=LUNAR_SR_APP_READY;phase<=LUNAR_SR_IO_READY;++phase) {
      ++f.now;phase_call();
    }
    phase=LUNAR_SR_MAIN;
    for(unsigned n=1;n<=4;++n) { f.now=f.policy.origin+n*100000000u;phase_call(); }
    f.now=f.policy.origin+LUNAR_SR_DEADLINE_TICKS-1;phase_call();tx=f.feed;
    ++f.now;expect_stop(phase_call,LUNAR_SR_DEADLINE);
    assert(f.feed==tx && f.reset==1 && !dirty);
  }
  printf("selected target binding passed terminal_cases=%u\n",cases);
  return 0;
}
#ifndef LUNAR_SR_BINDING_NO_MAIN
int main(void) { return lunar_selected_return_binding_checks(); }
#endif

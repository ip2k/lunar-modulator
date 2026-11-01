/* SPDX-License-Identifier: GPL-3.0-only
 * Register fake, not a second policy. */
#include "selected_return.h"
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <stdatomic.h>

static struct {
  lunar_selected_return_t policy;
  lunar_selected_return_io_t io;
  lunar_selected_return_qualification_t q;
  struct { uint8_t before[8], bytes[16], after[8]; } region;
  uint32_t con,prd,now,icfg,p33con;
  uint8_t dat,wdt,mode,command,address;
  unsigned pos,pending,started,transfers,timeout_at,fault_at,nested;
  unsigned feed,reset,reads,origin_after_arm,barriers,halts,allow_halt;
  unsigned corrupt_mailbox,wrong_wdt,byte_log[128];
  unsigned timeout_polls,dat_reads,readback_at,readbacks,corrupt_timer_after_arm;
  unsigned fault_after_feed;
} f;
static jmp_buf stopped;
static unsigned cases,phase;
static uint32_t timer_con(void *p) {
  (void)p;
  if(f.corrupt_timer_after_arm && f.policy.backstop_armed) return f.con^0x10;
  return f.con;
}
static uint32_t timer_prd(void *p) { (void)p; return f.prd; }
static uint32_t timer_count(void *p) {
  (void)p; ++f.reads;
  if(f.reads==1) {
    assert(f.wdt==0x1a && !(f.mode&0x40));
    assert(!memcmp(f.region.bytes,"usb_update_mode",16));
    f.origin_after_arm=1;
  }
  return f.now;
}
static uint32_t icfg_read(void *p) { (void)p; return f.icfg; }
static void icfg_write(void *p,uint32_t v) { (void)p; f.icfg=v; }
static void barrier(void *p) {
  (void)p; atomic_signal_fence(memory_order_seq_cst); ++f.barriers;
  assert(!memcmp(f.region.bytes,"usb_update_mode",16));
  if(f.corrupt_mailbox) f.region.bytes[5]^=1;
}
static void complete_byte(void) {
  if(f.pos==0) f.command=f.dat;
  else if(f.pos==1) f.address=f.dat;
  else {
    uint8_t *reg=0;
    if(f.address==0x80) reg=&f.wdt;
    else if(f.address==0x17) reg=&f.mode;
    else assert(f.address==0xa0 && f.command==0x20 && f.dat==0x10);
    if(f.command==0x80) {
      assert(reg); f.dat=*reg;
      if(++f.readbacks==f.readback_at) f.dat^=f.address==0x17?0x40:0x10;
      if(f.wrong_wdt && f.address==0x80) f.dat^=0x10;
    } else {
      if(f.command==0x00) { assert(reg); *reg=f.dat; }
      else if(f.command==0x40) { assert(reg); *reg&=f.dat; }
      else {
        assert(f.command==0x20);
        if(reg) *reg|=f.dat;
        if(f.address==0xa0) ++f.reset;
        if(f.address==0x80 && f.dat==0x40) ++f.feed;
      }
      if(reg==&f.wdt) f.wdt&=(uint8_t)~0x40; /* fake self-clearing strobe */
    }
  }
  ++f.pos; assert(f.pos<=3);
}
static uint32_t p33_con_read(void *p) {
  (void)p; assert(!(f.icfg&0x100));
  if(f.started) {
    if(f.fault_at==f.transfers) {
      f.fault_at=0; lunar_selected_return_fault(&f.policy,LUNAR_SR_FAULT);
    }
    if(f.timeout_at==f.transfers) { ++f.timeout_polls; return f.p33con|2u; }
    complete_byte(); f.started=f.pending=0; f.p33con&=~0x12u;
  }
  return f.p33con;
}
static void p33_con_write(void *p,uint32_t v) {
  (void)p; assert(!(f.icfg&0x100));
  assert(!(v&0x100)); /* never RTC domain */
  if(!(f.p33con&1) && (v&1)) { f.pos=0; assert(!f.pending); }
  if((f.p33con&1) && !(v&1)) { assert(f.pos==3 && !f.pending); }
  f.p33con=v;
  if((v&0x10) && f.pending) f.started=1;
}
static uint8_t p33_dat_read(void *p) {
  (void)p; assert(!f.pending); ++f.dat_reads;
  if(f.fault_after_feed && f.feed) {
    f.fault_after_feed=0; lunar_selected_return_fault(&f.policy,LUNAR_SR_FAULT);
  }
  return f.dat;
}
static void p33_dat_write(void *p,uint8_t v) {
  (void)p; assert(!(f.icfg&0x100)); assert(f.p33con&1); assert(!f.pending);
  f.dat=v; f.pending=1; ++f.transfers;
  assert(f.transfers<=128); f.byte_log[f.transfers-1]=v;
}
static void halt(void *p) {
  (void)p; assert(f.allow_halt && !(f.icfg&0x100));
  ++f.halts;
  if(f.nested) { f.nested=0; lunar_selected_return_fault(&f.policy,LUNAR_SR_INIT); }
  longjmp(stopped,1);
}
static void fresh(uint32_t initial) {
  memset(&f,0,sizeof f); memset(&f.region,0xa5,sizeof f.region);
  f.con=0x4009; f.prd=UINT32_MAX; f.now=initial; f.icfg=0xdead0304;
  f.mode=0xff;
  f.io=(lunar_selected_return_io_t){0,timer_con,timer_prd,timer_count,
    icfg_read,icfg_write,p33_con_read,p33_con_write,p33_dat_read,p33_dat_write,
    &f.region.bytes,barrier,halt};
  f.q=(lunar_selected_return_qualification_t){1,1,1,10,240000000u,120000000u,4};
}
static void sentinels(void) {
  for(unsigned i=0;i<8;++i) assert(f.region.before[i]==0xa5 && f.region.after[i]==0xa5);
}
static void prepare(void) {
  uint32_t saved=f.icfg;
  assert(!lunar_selected_return_prepare(&f.policy,&f.io,&f.q));
  assert(f.policy.state==LUNAR_SR_ARMED && f.policy.backstop_armed);
  assert(f.policy.origin==f.now && f.reads==1 && f.origin_after_arm);
  assert(f.icfg==saved && f.transfers==24 && !f.feed && !f.reset);
  assert(!memcmp(f.region.bytes,"usb_update_mode",16)); sentinels();
}
static void prepare_call(void) { (void)lunar_selected_return_prepare(&f.policy,&f.io,&f.q); }
static void phase_call(void) { (void)lunar_selected_return_progress(&f.policy,phase,1); }
static void refuse_call(void) { (void)lunar_selected_return_progress(&f.policy,LUNAR_SR_APP_READY,0); }
static void fault_call(void) { lunar_selected_return_fault(&f.policy,LUNAR_SR_FAULT); }
static void expect_stop(void (*call)(void),unsigned reason) {
  f.allow_halt=1;
  if(!setjmp(stopped)) { call(); assert(0); }
  assert(f.policy.state==LUNAR_SR_TERMINAL && f.policy.first_error==reason);
  assert(!(f.icfg&0x100)); sentinels(); ++cases;
}
static void start_running(void) {
  prepare();
  for(phase=LUNAR_SR_APP_READY;phase<=LUNAR_SR_IO_READY;++phase) {
    ++f.now; uint32_t saved=f.icfg;
    assert(!lunar_selected_return_progress(&f.policy,phase,1)); assert(f.icfg==saved);
  }
  assert(f.policy.state==LUNAR_SR_RUNNING && f.feed==3);
}
static void clock_cases(void) {
  for(unsigned wrap=0;wrap<2;++wrap) {
    fresh(wrap?UINT32_MAX-8:100); start_running(); phase=LUNAR_SR_MAIN;
    for(unsigned n=1;n<=4;++n) { f.now=f.policy.origin+n*100000000u; phase_call(); }
    f.now=f.policy.origin+LUNAR_SR_DEADLINE_TICKS-1;
    phase_call(); unsigned feeds=f.feed,reads=f.reads;
    f.now++; expect_stop(phase_call,LUNAR_SR_DEADLINE);
    assert(f.reset==1 && f.feed==feeds && f.reads==reads+1 && f.policy.reset_attempted);
    unsigned tx=f.transfers; reads=f.reads;
    expect_stop(phase_call,LUNAR_SR_DEADLINE);
    expect_stop(fault_call,LUNAR_SR_DEADLINE);
    assert(f.transfers==tx && f.reads==reads && f.reset==1 && f.feed==feeds);
  }
  fresh(100);prepare();phase=LUNAR_SR_APP_READY;
  expect_stop(phase_call,LUNAR_SR_CLOCK);assert(!f.feed && !f.reset);
  fresh(100);prepare();--f.now;
  expect_stop(phase_call,LUNAR_SR_CLOCK);assert(!f.feed && !f.reset);
  fresh(100);prepare();f.now+=f.q.max_phase_ticks+1;
  expect_stop(phase_call,LUNAR_SR_CLOCK);assert(!f.feed && !f.reset);
  fresh(100);prepare();++f.now;f.con^=0x10;
  expect_stop(phase_call,LUNAR_SR_CLOCK);assert(!f.feed && !f.reset);
  fresh(100);prepare();++f.now;f.prd=600;
  expect_stop(phase_call,LUNAR_SR_CLOCK);assert(!f.feed && !f.reset);
}
static void refusal_cases(void) {
  for(unsigned i=0;i<9;++i) {
    fresh(100);
    switch(i) {
      case 0:f.con=0x19;break;
      case 1:f.prd=600;break;
      case 2:f.q.timer4_exclusive=0;break;
      case 3:f.q.mailbox_write_qualified=0;break;
      case 4:f.q.watchdog_qualified=0;break;
      case 5:f.q.lease_ticks=f.q.max_phase_ticks;break;
      case 6:f.q.max_phase_ticks=0;break;
      case 7:f.q.byte_poll_limit=0;break;
      case 8:f.q.watchdog_selector=16;break;
    }
    expect_stop(prepare_call,i<2?LUNAR_SR_CLOCK:LUNAR_SR_QUALIFICATION);
    assert(!f.reads && !f.transfers && !f.policy.backstop_armed);
    for(unsigned k=0;k<16;++k) assert(f.region.bytes[k]==0xa5);
  }
  fresh(0);f.corrupt_mailbox=1;
  expect_stop(prepare_call,LUNAR_SR_MAILBOX);assert(!f.transfers && !f.reads);
  fresh(0);prepare();expect_stop(refuse_call,LUNAR_SR_INIT);
  assert(!f.feed && f.reset==1);
  fresh(0);prepare();phase=LUNAR_SR_MAIN;++f.now;
  expect_stop(phase_call,LUNAR_SR_PHASE);assert(!f.feed && !f.reset);
  fresh(0);prepare();phase=LUNAR_SR_APP_READY;++f.now;f.wrong_wdt=1;
  expect_stop(phase_call,LUNAR_SR_WATCHDOG);assert(!f.feed && !f.reset);
}
static void timeout_cases(void) {
  for(unsigned i=1;i<=24;++i) {
    fresh(100); f.timeout_at=i;
    expect_stop(prepare_call,LUNAR_SR_P33);
    assert(f.transfers==i && f.policy.failed_byte==i && f.pending && (f.p33con&1));
    assert(!f.feed && !f.reset && !f.reads);
    assert(f.timeout_polls==f.q.byte_poll_limit && f.dat_reads==i-1);
  }
  for(unsigned i=1;i<=9;++i) {
    fresh(100); prepare(); phase=LUNAR_SR_APP_READY; ++f.now;
    f.timeout_at=f.transfers+i;
    expect_stop(phase_call,LUNAR_SR_P33);
    assert(f.transfers==24+i && f.policy.failed_byte==24+i && !f.feed && !f.reset);
    assert(f.timeout_polls==f.q.byte_poll_limit && f.dat_reads==24+i-1);
  }
  for(unsigned i=1;i<=3;++i) {
    fresh(100);prepare(); f.timeout_at=f.transfers+i;
    expect_stop(refuse_call,LUNAR_SR_INIT);
    assert(f.transfers==24+i && f.policy.failed_byte==24+i && !f.feed && !f.reset);
    assert(f.timeout_polls==f.q.byte_poll_limit && f.dat_reads==24+i-1);
  }
}
static void binding_cases(void) {
  /* An already selected command is not safe to restart or append to. */
  for(unsigned con=1;con<=3;++con) {
    fresh(100);f.p33con=con;
    expect_stop(prepare_call,LUNAR_SR_P33);
    assert(!f.transfers && !f.reads && !f.policy.backstop_armed);
    assert(f.p33con==con); /* no guessed cancel/deassert sequence */
  }
  for(unsigned readback=1;readback<=4;++readback) {
    fresh(100);f.readback_at=readback;
    expect_stop(prepare_call,LUNAR_SR_WATCHDOG);
    assert(f.transfers==readback*6 && !f.reads && !f.feed && !f.reset);
    assert(!f.policy.backstop_armed);
  }
  fresh(100);f.corrupt_timer_after_arm=1;
  expect_stop(prepare_call,LUNAR_SR_CLOCK);
  assert(f.policy.backstop_armed && f.transfers==24 && !f.reads && !f.feed && !f.reset);
  fresh(100);prepare();phase=LUNAR_SR_APP_READY;++f.now;f.mode|=0x40;
  expect_stop(phase_call,LUNAR_SR_WATCHDOG);
  assert(f.transfers==27 && !f.feed && !f.reset);
  fresh(100);prepare();
  expect_stop(prepare_call,LUNAR_SR_REENTRY);
  assert(f.transfers==24 && f.reads==1 && !f.feed && !f.reset);
}
static void fault_cases(void) {
  for(unsigned enabled=0;enabled<2;++enabled) {
    fresh(100); f.icfg=0xdead0204u|(enabled?0x100u:0); prepare();
    phase=LUNAR_SR_APP_READY;++f.now;uint32_t saved=f.icfg;
    phase_call();assert(saved==f.icfg && f.feed==1);
  }
  for(unsigned i=1;i<=9;++i) {
    fresh(100);prepare();phase=LUNAR_SR_APP_READY;++f.now;
    f.fault_at=f.transfers+i;f.nested=1;
    expect_stop(phase_call,LUNAR_SR_FAULT);
    assert(f.transfers==24+i && !f.feed && !f.reset && f.halts==2);
    unsigned tx=f.transfers;
    expect_stop(fault_call,LUNAR_SR_FAULT);
    assert(f.transfers==tx && !f.reset && !f.feed);
  }
  /* A fault cannot undo a feed whose data byte already completed. It still
   * performs no additional P33 access, CS abort or reset request. */
  fresh(100);prepare();phase=LUNAR_SR_APP_READY;++f.now;f.fault_after_feed=1;
  expect_stop(phase_call,LUNAR_SR_FAULT);
  assert(f.transfers==33 && f.feed==1 && !f.reset && (f.p33con&1));
  unsigned tx=f.transfers,reads=f.dat_reads;
  expect_stop(fault_call,LUNAR_SR_FAULT);
  assert(f.transfers==tx && f.dat_reads==reads && f.feed==1 && !f.reset);
}
int main(void) {
  clock_cases();refusal_cases();timeout_cases();binding_cases();fault_cases();
  printf("selected return proof passed terminal_cases=%u\n",cases);
  return 0;
}

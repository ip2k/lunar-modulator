/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments
 * Narrow derivation of Dinghy fad3a965 fm1_sys.h (not imported wholesale).
 * See UPSTREAM.md. Portable fake or separately guarded unqualified candidate.
 */
#include "selected_return.h"
#ifndef __PI32V2__
#include <stdatomic.h>
#endif

/* The vendor pi32v2 compiler lowers atomic_signal_fence to an unresolved
 * __sync_synchronize call. This compiler-only barrier preserves ordering at
 * every policy boundary; target ICFG/MMIO/publication callbacks separately
 * retain their explicit csync instructions and memory clobbers. */
static inline void compiler_fence(void) {
#ifdef __PI32V2__
  __asm__ volatile("" ::: "memory");
#else
  atomic_signal_fence(memory_order_seq_cst);
#endif
}

/* P33 CON 0x13e08 / DAT 0x13e0c source facts. No arbitrary-address API. */
enum { P33_CS=1u, P33_BUSY=2u, P33_KICK=16u, P33_RTC=256u };
enum { REG_MODE=0x17u, REG_WDT=0x80u, REG_RESET=0xa0u };
enum { OP_WRITE=0u, OP_OR=0x20u, OP_AND=0x40u, OP_READ=0x80u };
static _Noreturn void terminal(lunar_selected_return_t *,uint32_t,int);
static void irq_mask(lunar_selected_return_t *s) {
  const lunar_selected_return_io_t *io=s->io;
  uint32_t saved=io->icfg_read(io->context);
  io->icfg_write(io->context,saved&~0x100u);
  compiler_fence();
}
static uint8_t byte(lunar_selected_return_t *s,uint8_t value) {
  const lunar_selected_return_io_t *io=s->io; void *p=io->context;
  ++s->p33_bytes;
  io->p33_dat_write(p,value);
  io->p33_con_write(p,io->p33_con_read(p)|P33_KICK);
  /* Iteration cap bounds only returning MMIO reads, not a stalled bus. No retry
   * or CS abort on timeout: safe cancellation of an in-flight byte is unproven. */
  for(uint32_t n=0;n<s->qualification.byte_poll_limit;++n) {
    if(!(io->p33_con_read(p)&P33_BUSY)) return io->p33_dat_read(p);
  }
  s->failed_byte=s->p33_bytes;
  terminal(s,LUNAR_SR_P33,0);
}
static uint8_t transaction(lunar_selected_return_t *s,uint8_t op,uint8_t reg,uint8_t data) {
  const lunar_selected_return_io_t *io=s->io; void *p=io->context;
  uint32_t con=io->p33_con_read(p);
  /* Never append to an inherited/incomplete command, even if BUSY is low. */
  if(con&(P33_BUSY|P33_CS)) terminal(s,LUNAR_SR_P33,0);
  io->p33_con_write(p,(con&~P33_RTC)|P33_CS);
  (void)byte(s,op); (void)byte(s,reg); uint8_t result=byte(s,data);
  /* Successful command only: drop CS and keep non-RTC domain. A failed byte
   * never reaches this store or any subsequent byte/read/command. */
  io->p33_con_write(p,io->p33_con_read(p)&~(P33_CS|P33_RTC));
  return result;
}
static uint8_t read_register(lunar_selected_return_t *s,uint8_t reg) {
  return transaction(s,OP_READ,reg,0x5e);
}
static uint32_t p33_begin(lunar_selected_return_t *s) {
  if(s->p33_owned) terminal(s,LUNAR_SR_REENTRY,0);
  s->p33_owned=1;
  uint32_t saved=s->io->icfg_read(s->io->context);
  s->io->icfg_write(s->io->context,saved&~0x100u);
  compiler_fence(); return saved;
}
static void p33_end(lunar_selected_return_t *s,uint32_t saved) {
  compiler_fence();
  s->p33_owned=0;
  s->io->icfg_write(s->io->context,saved); /* exact entry state, never STI */
}
static _Noreturn void terminal(lunar_selected_return_t *s,uint32_t reason,int reset) {
  unsigned already=s->state==LUNAR_SR_TERMINAL;
  if(!s->first_error) s->first_error=reason;
  s->state=LUNAR_SR_TERMINAL; /* sticky before any port call or fault nesting */
  irq_mask(s);
  if(reset && !already && s->backstop_armed && !s->p33_owned && !s->reset_attempted) {
    s->reset_attempted=1; s->p33_owned=1;
    (void)transaction(s,OP_OR,REG_RESET,0x10); /* exactly one normal request */
    s->p33_owned=0;
  }
  s->io->halt(s->io->context);
  __builtin_trap(); /* a misbound returning halt can never continue or feed */
}
_Noreturn void lunar_selected_return_fault(lunar_selected_return_t *s,uint32_t reason) {
  if(!s || !s->io || !s->io->halt) __builtin_trap();
  terminal(s,reason?reason:LUNAR_SR_FAULT,0); /* never enters P33 from fault */
}
static void qualify_timer(lunar_selected_return_t *s) {
  uint32_t con=s->io->timer4_con(s->io->context);
  uint32_t prd=s->io->timer4_prd(s->io->context);
  if((con&0xffu)!=9u || prd!=UINT32_MAX) terminal(s,LUNAR_SR_CLOCK,0);
}
static void arm(lunar_selected_return_t *s) {
  uint32_t saved=p33_begin(s),selector=s->qualification.watchdog_selector;
  (void)transaction(s,OP_WRITE,REG_WDT,0);
  if(read_register(s,REG_WDT)&0x1f) terminal(s,LUNAR_SR_WATCHDOG,0);
  (void)transaction(s,OP_AND,REG_MODE,0xbf);
  if(read_register(s,REG_MODE)&0x40) terminal(s,LUNAR_SR_WATCHDOG,0);
  (void)transaction(s,OP_WRITE,REG_WDT,(uint8_t)(selector|0x40));
  if((read_register(s,REG_WDT)&0x1f)!=selector) terminal(s,LUNAR_SR_WATCHDOG,0);
  (void)transaction(s,OP_OR,REG_WDT,0x10);
  if((read_register(s,REG_WDT)&0x1f)!=(selector|0x10)) terminal(s,LUNAR_SR_WATCHDOG,0);
  /* Stable fields only; never require self-clearing clear-strobe bit6 set.
   * This contract is deliberately unqualified for actual silicon here. */
  s->backstop_armed=1; p33_end(s,saved);
}
static void feed(lunar_selected_return_t *s) {
  uint32_t saved=p33_begin(s);
  if((read_register(s,REG_MODE)&0x40) ||
     (read_register(s,REG_WDT)&0x1f)!=(s->qualification.watchdog_selector|0x10))
    terminal(s,LUNAR_SR_WATCHDOG,0);
  (void)transaction(s,OP_OR,REG_WDT,0x40);
  p33_end(s,saved);
}
static int port_complete(const lunar_selected_return_io_t *io) {
  return io && io->timer4_con && io->timer4_prd && io->timer4_count &&
    io->icfg_read && io->icfg_write && io->p33_con_read && io->p33_con_write &&
    io->p33_dat_read && io->p33_dat_write && io->mailbox &&
    io->mailbox_publish_barrier && io->halt;
}
int lunar_selected_return_prepare(lunar_selected_return_t *s,
    const lunar_selected_return_io_t *io,const lunar_selected_return_qualification_t *q) {
  if(!s) return -1;
  if(s->state) {
    if(port_complete(s->io)) terminal(s,LUNAR_SR_REENTRY,0);
    return -1;
  }
  if(!port_complete(io) || !q) {
    s->state=LUNAR_SR_TERMINAL; s->first_error=LUNAR_SR_QUALIFICATION; return -1;
  }
  s->io=io; s->qualification=*q; s->state=LUNAR_SR_BOOTSTRAP;
  if(q->timer4_exclusive!=1 || q->mailbox_write_qualified!=1 || q->watchdog_qualified!=1 ||
     q->watchdog_selector>15 || !q->max_phase_ticks ||
     q->max_phase_ticks>=q->lease_ticks || q->lease_ticks>INT32_MAX ||
     q->max_phase_ticks>=LUNAR_SR_DEADLINE_TICKS ||
     !q->byte_poll_limit || q->byte_poll_limit>100000)
    terminal(s,LUNAR_SR_QUALIFICATION,0);
  qualify_timer(s);
  static const uint8_t marker[LUNAR_SR_MAILBOX_BYTES]="usb_update_mode";
  for(unsigned i=0;i<LUNAR_SR_MAILBOX_BYTES;++i) (*io->mailbox)[i]=marker[i];
  compiler_fence();
  io->mailbox_publish_barrier(io->context);
  for(unsigned i=0;i<LUNAR_SR_MAILBOX_BYTES;++i)
    if((*io->mailbox)[i]!=marker[i]) terminal(s,LUNAR_SR_MAILBOX,0);
  arm(s);
  qualify_timer(s); /* catch configuration changes during backstop setup */
  s->origin=io->timer4_count(io->context); /* exactly one ordered raw origin */
  s->last_tick=s->origin; s->next_phase=LUNAR_SR_APP_READY; s->state=LUNAR_SR_ARMED;
  return 0;
}
int lunar_selected_return_progress(lunar_selected_return_t *s,unsigned phase,int healthy) {
  if(!s || !port_complete(s->io)) return -1;
  if(s->state==LUNAR_SR_TERMINAL) terminal(s,s->first_error,0);
  if((s->state!=LUNAR_SR_ARMED && s->state!=LUNAR_SR_RUNNING) ||
     phase!=s->next_phase) terminal(s,LUNAR_SR_PHASE,0);
  if(healthy!=1) terminal(s,LUNAR_SR_INIT,1);
  qualify_timer(s);
  uint32_t now=s->io->timer4_count(s->io->context),delta=now-s->last_tick;
  if(!delta || delta>s->qualification.max_phase_ticks) terminal(s,LUNAR_SR_CLOCK,0);
  if((uint32_t)(now-s->origin)>=LUNAR_SR_DEADLINE_TICKS) terminal(s,LUNAR_SR_DEADLINE,1);
  s->last_tick=now;
  feed(s); /* only after valid time advancement and allowed completed phase */
  if(s->next_phase<LUNAR_SR_MAIN) ++s->next_phase;
  if(s->next_phase==LUNAR_SR_MAIN) s->state=LUNAR_SR_RUNNING;
  return 0;
}

/* SPDX-License-Identifier: GPL-3.0-only
 * Explicit audio-only adapter over Dinghy's GPL base HAL. The immutable zero
 * return qualification still refuses actual startup. No display, storage,
 * CPU1, updater or SDK binding. See UPSTREAM.md and the dated source note. */
#if !defined(LUNAR_SELECTED_AUDIO_OWNER_PROOF) || LUNAR_SELECTED_AUDIO_OWNER_PROOF != 1
#error "explicit audio-only offline selection required"
#endif
#include "diagnostic_api.h"
#include "selected_owner_storage.h"
#include "selected_return_pi32v2.h"
static void accepted_key(uint32_t,unsigned,int);
static void accepted_encoder(uint32_t,unsigned,int);
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
#include "audio_owner_hal.h"
#else
#include "fm1_time.h"
#include "fm1_irq.h"
#define FM1_INPUT_ACCEPTED_KEY(scan,id,down) accepted_key(scan,id,down)
#define FM1_INPUT_ACCEPTED_ENCODER(scan,id,delta) accepted_encoder(scan,id,delta)
#include "fm1_input.h"
#include "fm1_timer.h"
#include "fm1_audio.h"
#endif
#define HALF_WORDS LUNAR_PCM_WORDS
#define START_TAIL_TICKS (5000u * FM1_TICKS_PER_US)
static int32_t audio[2u * HALF_WORDS] __attribute__((aligned(16)));
static lunar_selected_return_t return_policy;
static volatile uint32_t audio_may_run, timer_may_run;
static uint32_t tail_origin, tail_done;
#define PLATFORM (&lunar_selected_aggregate_platform)
extern void isr_timer5(void),isr_alnk0(void);

static uint32_t word(const lunar_transport_word_t *p) {
#ifdef LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION
  return lunar_pub_load(p);
#else
  return atomic_load_explicit(p,memory_order_acquire);
#endif
}
static int poisoned(void) {
  return return_policy.state==LUNAR_SR_TERMINAL ||
      word(&PLATFORM->owner.transport.fault) || lunar_diagnostic_status();
}
static void check(void) {
  if(poisoned()) lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
}
static void accepted_key(uint32_t scan,unsigned id,int down) {
  if(!poisoned()) (void)lunar_transport_matrix(&PLATFORM->owner.transport,scan,id,down);
}
static void accepted_encoder(uint32_t scan,unsigned id,int delta) {
  if(!poisoned()) (void)lunar_transport_encoder(&PLATFORM->owner.transport,scan,id,delta);
}
static int scan_init(void *ctx) {
  (void)ctx;
  check();
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_APP_READY,1);
  fm1_input_init();
  return poisoned()?-1:0;
}
static void scan_tick(void *ctx) { (void)ctx; fm1_input_tick(); }
static int prepare(void *ctx) {
  (void)ctx;
  check();
  fm1_audio_prepare(audio,HALF_WORDS,isr_alnk0,3);
  if(poisoned()) return -1;
  /* One startup-only consumer. DMA/IRQs are OFF throughout these four real
   * blocks. Handover to the sole ALNK consumer happens only after return. */
  for(unsigned half=0;half<2;++half) {
    if(lunar_transport_irq(&PLATFORM->owner.transport,audio+half*HALF_WORDS)!=1 ||
       poisoned()) return -1;
    if(half==0 && lunar_selected_owner_step(&PLATFORM->owner)!=1) return -1;
  }
  for(unsigned n=0;n<LUNAR_SELECTED_PCM_CAPACITY;++n)
    if(lunar_selected_owner_step(&PLATFORM->owner)!=1 || poisoned()) return -1;
  return 0;
}
void fm1_timer5_irq(void) {
  fm1_timer5_ack();
  if(!poisoned()) lunar_selected_platform_timer(PLATFORM);
}
void fm1_alnk0_irq(void) {
  uint8_t p=fm1_audio_pending();
  fm1_audio_ack_aux(p);
  if(p & FM1_AUDIO_HALF) {
    int32_t *out=audio+fm1_audio_free_half()*HALF_WORDS;
    /* PCM was already converted by the main-owner render callback. */
    (void)lunar_selected_platform_audio(poisoned()?NULL:PLATFORM,out);
    fm1_audio_ack_half();
  }
}
void lunar_selected_return_stop_audio(void) {
  /* Policy terminal is published first. Keep every buffer/lease permanent;
   * clearing DMA enable is not a proof of bus-read retirement. */
  if(timer_may_run) { timer_may_run=0; fm1_irq_mask(FM1_IRQ_TIMER5); }
  if(audio_may_run) {
    audio_may_run=0; fm1_irq_mask(FM1_IRQ_ALNK0); fm1_audio_stop();
  }
}
static void fm1_fault(const fm1_crash_t *crash) {
  (void)crash; lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
}
static void main_step(void) {
  check();
  if(word(&PLATFORM->owner.transport.underruns))
    lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
  if(lunar_selected_platform_main(PLATFORM)<0)
    lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
  check();
  if(word(&PLATFORM->owner.transport.underruns))
    lunar_selected_return_fault(&return_policy,LUNAR_SR_FAULT);
  uint32_t now=fm1_ticks();
  /* Health cadence is evidence-relative, never a feed in a fast full-queue
   * spin or an IRQ. The policy independently checks configuration/deadline. */
  uint32_t cadence=return_policy.qualification.max_phase_ticks/2u;
  if(!cadence) cadence=1;
  if((uint32_t)(now-return_policy.last_tick)>=cadence) {
    (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_MAIN,1);
    check();
  }
  if(!tail_done && (uint32_t)(now-tail_origin)>=START_TAIL_TICKS) {
    check();
    tail_done=1; /* no repeated tail, including fault/reentry during the write */
    fm1_audio_finish_start();
    check();
  }
}
void lunar_diagnostic_cstart(void) {
#ifndef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  extern uint32_t _data_start[],_data_end[],_data_load[],_bss_start[],_bss_end[];
  uint32_t *s,*d;
  for(s=_data_load,d=_data_start;d<_data_end;) *d++=*s++;
  for(d=_bss_start;d<_bss_end;) *d++=0;
#endif
  /* Immutable real zero qualification halts before all functional work. */
  (void)lunar_selected_return_target_prepare(&return_policy);
  fm1_irq_init();
  const lunar_selected_audio_prepare_ops_t ops={scan_init,scan_tick,prepare,NULL};
  int healthy=lunar_selected_platform_prepare_audio(PLATFORM,&ops,
      lunar_selected_aggregate_input,LUNAR_SELECTED_INPUT_CAPACITY,
      lunar_selected_aggregate_pcm,LUNAR_SELECTED_PCM_CAPACITY,0,16)==0;
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_FRONTEND_READY,healthy);
  check();
  (void)lunar_selected_return_progress(&return_policy,LUNAR_SR_IO_READY,1);
  check();
  /* All app work, prefill and P33 phase feeds precede this short interval.
   * No wait or app callback between DMA start and IRQ enable. */
  tail_origin=fm1_ticks();
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
  lunar_sr_test_barrier();
#else
  __asm__ volatile("csync" ::: "memory");
#endif
  check();
  audio_may_run=1;
  fm1_audio_start_prepared();
  check();
  timer_may_run=1;
  fm1_timer5_start(isr_timer5,4);
  check();
  fm1_irq_enable_all();
  for(;;) {
#ifdef LUNAR_SELECTED_RETURN_TARGET_INJECTED
    lunar_audio_owner_test_iteration();
#endif
    main_step();
  }
}

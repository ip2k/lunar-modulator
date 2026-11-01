/* GPL-3.0-only fixture: actual app/owner/scanner, policy and target adapter.
 * Only register/IRQ dispatch/clock behavior is injected. */
#define LUNAR_SR_BINDING_NO_MAIN
#define LUNAR_SR_PLATFORM_TEST
#define lunar_sr_test_barrier original_test_barrier
#include "../selected_return_target/check.c"
#undef lunar_sr_test_barrier
#include "diagnostic_app.h"
#include "selected_project_blob.h"
#include "fm1_app_state.h"
#include <math.h>
#include <stdlib.h>

/* Keep actual adapter private functions distinct from the reused policy fake. */
#define prepare audio_prepare_callback
#define main_step audio_main_step
#include "selected_audio_owner_platform.c"
#undef prepare
#undef main_step

/* Same single platform/input/PCM storage contract, host C11 publication ABI. */
lunar_selected_platform_t lunar_selected_aggregate_platform;
lunar_input_t lunar_selected_aggregate_input[LUNAR_SELECTED_INPUT_CAPACITY];
lunar_pcm_t lunar_selected_aggregate_pcm[LUNAR_SELECTED_PCM_CAPACITY];
static fm1_app_t reference;
static unsigned char reference_arena[16384] FM1_APP_ALIGN16;
static fm1_app_arena_t reference_arenas[FM1_APP_UNITS];
static unsigned char reference_workspace[655360] FM1_APP_ALIGN16;
static fm1_app_state_report_t reference_report;
static int32_t expected[8192][128];
static unsigned expected_head,consumed,nonzero,irq_init_calls,scans,prepare_calls;
static unsigned dma_starts,irq_enables,tail_calls,stop_calls,timer_starts,masks,iterations;
static unsigned scan_depth,audio_depth,half_index,pending=FM1_AUDIO_HALF,ack_count;
static const char *mode;
static unsigned trigger,seen;
static uint8_t scan_raw[11];
static uint32_t fake_gpio[8][8];
static unsigned accepted;

/* Actual scanner implementation with fake GPIO reads and time, not a second
 * decoder. Keep its static state in this same platform fixture TU. */
#define fm1_ticks original_hal_ticks
#include "fm1_time.h"
#undef fm1_ticks
#include "fm1_gpio.h"
#include "fm1_cc.h"
#undef FM1_PR
#define FM1_PR(p,r) fake_gpio[p][(r)/4]
#define fm1_ticks scanner_ticks
static uint32_t scanner_ticks(void) { return f.now++; }
#define fm1_input_init actual_input_init
#define fm1_input_tick actual_input_tick
#define FM1_INPUT_ACCEPTED_KEY(scan,id,down) scanner_key(scan,id,down)
#define FM1_INPUT_ACCEPTED_ENCODER(scan,id,delta) scanner_encoder(scan,id,delta)
#define FM1_BTN_OCT_DOWN HAL_BTN_OCT_DOWN
#define FM1_BTN_OCT_UP HAL_BTN_OCT_UP
static void scanner_key(uint32_t,unsigned,int),scanner_encoder(uint32_t,unsigned,int);
#include "fm1_input.h"
#undef FM1_BTN_OCT_DOWN
#undef FM1_BTN_OCT_UP
#undef fm1_input_init
#undef fm1_input_tick
#undef fm1_ticks

void lunar_sr_test_barrier(void) { original_test_barrier(); ++f.now; }
void isr_timer5(void) {} void isr_alnk0(void) {}
static uint32_t read_blob(void *ctx,uint32_t off,uint8_t *out,uint32_t n) {
  (void)ctx;
  if(off>=lunar_selected_project_blob_bytes) return 0;
  if(n>lunar_selected_project_blob_bytes-off) n=lunar_selected_project_blob_bytes-off;
  memcpy(out,lunar_selected_project_blob+off,n);return n;
}
static void init_reference(void) {
  reference_arenas[0]=(fm1_app_arena_t){reference_arena,sizeof reference_arena};
  assert(!fm1_app_init_arenas(&reference,LUNAR_DIAGNOSTIC_RATE,reference_arenas));
  fm1_app_load_opts_t opts;fm1_app_load_opts_init(&opts);
  opts.kind=FM1_STATE_PROJECT;opts.flags=FM1_APP_LOAD_QUIET;
  fm1_app_state_workspace_t workspace={reference_workspace,sizeof reference_workspace};
  assert(fm1_app_state_load_with_workspace(&reference,read_blob,NULL,
      lunar_selected_project_blob_bytes,&opts,&workspace,&reference_report));
  assert(reference_report.r.code==FM1_STATE_OK && !reference_report.r.skipped);
}
static void reference_input(const lunar_input_t *e) {
  if(e->kind==LUNAR_INPUT_KEY) fm1_app_key(&reference,e->id,e->value,100);
  else if(e->kind==LUNAR_INPUT_BUTTON) fm1_app_button(&reference,e->id,e->value);
  else fm1_app_encoder(&reference,e->id,e->value);
}
static void reference_block(void) {
  assert(!scan_depth && !audio_depth && expected_head<8192);
  const float *v=fm1_app_render(&reference,64);
  for(unsigned i=0;i<128;++i) {
    assert(isfinite(v[i]));
    expected[expected_head][i]=(v[i]>=1?32767:v[i]<=-1?-32767:(int32_t)(v[i]*32767.0f))*128;
    nonzero+=expected[expected_head][i]!=0;
  }
  ++expected_head;
}
static void catchup(void) {
  while(reference.frames<lunar_diagnostic_state()->frames) reference_block();
  assert(reference.frames==lunar_diagnostic_state()->frames);
  assert(!memcmp(reference.key_note,lunar_diagnostic_state()->key_note,sizeof reference.key_note));
}
static void inject(const char *boundary) {
  (void)boundary;
  if(++seen!=trigger) return;
  if(!strcmp(mode,"fault")) lunar_transport_fault(&PLATFORM->owner.transport,77);
  if(!strcmp(mode,"reenter")) {
    const lunar_selected_audio_prepare_ops_t ops={scan_init,scan_tick,audio_prepare_callback,NULL};
    assert(lunar_selected_platform_prepare_audio(PLATFORM,&ops,
        lunar_selected_aggregate_input,16,lunar_selected_aggregate_pcm,2,0,16)==-1);
  }
  if(!strcmp(mode,"early-irq")) fm1_alnk0_irq();
}
static void fm1_irq_init(void) {
  assert(return_policy.backstop_armed && !dma_starts);f.icfg&=~0x100u;
  ++irq_init_calls;++f.now;inject("irq-init");
}
static void fm1_input_init(void) {
  assert(irq_init_calls==1 && !dma_starts && !(f.icfg&0x100u));
  actual_input_init();inject("scan-init");
  if(!strcmp(mode,"positive") || !strcmp(mode,"wrap")) {
    accepted_key(77,18,1);
    lunar_input_t event={77,LUNAR_INPUT_KEY,4,1};reference_input(&event);
  }
}
static void fm1_audio_prepare(int32_t *buf,uint32_t n,void (*isr)(void),uint32_t prio) {
  assert(buf==audio && n==128 && isr==isr_alnk0 && prio==3);
  assert(!dma_starts && !(f.icfg&0x100u) && !PLATFORM->started);
  assert(lunar_diagnostic_state()->frames==64);
  ++prepare_calls;f.now+=120000;inject("audio-prepare");
}
static void fm1_audio_start_prepared(void) {
  assert(PLATFORM->started && !PLATFORM->preparing && !(f.icfg&0x100u));
  assert(return_policy.next_phase==LUNAR_SR_MAIN && prepare_calls==1);
  assert(lunar_diagnostic_state()->frames==256);
  catchup();assert(expected_head==4);
  assert(!memcmp(audio,expected[0],512) && !memcmp(audio+128,expected[1],512));
  assert(word(&PLATFORM->owner.transport.pcm_head)-word(&PLATFORM->owner.transport.pcm_tail)==2);
  assert(!memcmp(lunar_selected_aggregate_pcm[0].word,expected[2],512));
  assert(!memcmp(lunar_selected_aggregate_pcm[1].word,expected[3],512));
  consumed=2;++dma_starts;inject("dma-start");
}
static void fm1_timer5_start(void (*isr)(void),uint32_t prio) {
  assert(dma_starts==1 && isr==isr_timer5 && prio==4 && !(f.icfg&0x100u));
  ++timer_starts;inject("timer-start");
}
static void audio_irq(void) {
  uint64_t frames=lunar_diagnostic_state()->frames;
  ++audio_depth;fm1_alnk0_irq();--audio_depth;
  assert(lunar_diagnostic_state()->frames==frames);
  if(pending&FM1_AUDIO_HALF) {
    if(!poisoned() && word(&PLATFORM->owner.transport.underruns)==0) {
      assert(consumed<expected_head);
      assert(!memcmp(audio+half_index*128,expected[consumed++],512));
    } else {
      for(unsigned i=0;i<128;++i) assert(!audio[half_index*128+i]);
    }
    half_index^=1;
  }
}
static void fm1_irq_enable_all(void) {
  assert(PLATFORM->started && dma_starts==1 && timer_starts==1);
  f.icfg|=0x100u;++irq_enables;
  /* First immediate IRQ is legal only after facade readiness/publication. */
  audio_irq();inject("irq-enabled");
}
static void fm1_audio_finish_start(void) {
  assert(irq_enables==1 && !poisoned() && !tail_calls);
  assert((uint32_t)(f.now-tail_origin)>=START_TAIL_TICKS);
  ++tail_calls;inject("finish-tail");
}
static void fm1_audio_stop(void) { assert(return_policy.state==LUNAR_SR_TERMINAL);++stop_calls; }
static void fm1_irq_mask(unsigned irq) { assert(irq==11 || irq==63);++masks; }
static uint32_t fm1_ticks(void) { return f.now; }
static uint8_t fm1_audio_pending(void) { return (uint8_t)pending; }
static uint32_t fm1_audio_free_half(void) { return half_index; }
static void fm1_audio_ack_aux(uint8_t p) { assert(p==pending); }
static void fm1_audio_ack_half(void) { ++ack_count; }
static void fm1_timer5_ack(void) { ++scans; }
static void fm1_input_tick(void) {
  uint64_t frames=lunar_diagnostic_state()->frames;
  ++scan_depth;
  uint32_t v=(uint32_t)~scan_raw[fm1__tick_col];
  fake_gpio[FM1_PA][FM1_IN/4]=((v&1u)?1u:0u)|((v&0x1eu)<<4);
  fake_gpio[FM1_PB][FM1_IN/4]=(v&0x20u)<<2;
  actual_input_tick();--scan_depth;
  assert(frames==lunar_diagnostic_state()->frames);
}
static void scanner_key(uint32_t scan,unsigned id,int down) {
  unsigned h=word(&PLATFORM->owner.transport.input_head);
  accepted_key(scan,id,down);
  assert(PLATFORM->owner.transport.input[h&15].scan==scan);++accepted;
}
static void scanner_encoder(uint32_t scan,unsigned id,int delta) {
  unsigned h=word(&PLATFORM->owner.transport.input_head);
  accepted_encoder(scan,id,delta);
  assert(PLATFORM->owner.transport.input[h&15].scan==scan);++accepted;
}
static void reference_pending(void) {
  lunar_transport_t *t=&PLATFORM->owner.transport;
  if(word(&t->pcm_head)-word(&t->pcm_tail)==2) return;
  uint32_t tail=word(&t->input_tail),head=word(&t->input_head);
  for(unsigned n=0;tail!=head && n<16;++n,++tail) reference_input(&t->input[tail&15]);
}
static void lunar_audio_owner_test_iteration(void) {
  catchup();
  if(++iterations==1) {
    /* Queue-full main is backpressure; it must not feed on an unchanged tick. */
    unsigned feeds=f.feed;uint64_t frames=lunar_diagnostic_state()->frames;
    if(lunar_selected_platform_main(PLATFORM)==1) catchup();
    assert(lunar_selected_platform_main(PLATFORM)==0);
    assert(lunar_diagnostic_state()->frames<=frames+64 && f.feed==feeds);
    if(!strcmp(mode,"empty")) { audio_irq();audio_irq();audio_irq();return; }
    if(!strcmp(mode,"overflow")) {
      for(unsigned i=0;i<17;++i) accepted_key(i,18,i&1);
      assert(word(&PLATFORM->owner.transport.fault)==LUNAR_TRANSPORT_OVERFLOW);return;
    }
  }
  if(!strcmp(mode,"clock-back")) { f.now=return_policy.last_tick-1;return; }
  if(iterations==20) {
    assert(tail_calls==1 && nonzero>0);
    assert(!PLATFORM->owner.display.initialized && !PLATFORM->owner.spi.initialized);
    /* Finish with a deliberate sticky fault; no auto-retry/pause teardown. */
    lunar_transport_fault(&PLATFORM->owner.transport,88);return;
  }
  f.now+=10000;
  /* Actual scanner edge, then representative accepted controls. */
  if(iterations==2 || iterations==3) {
    scan_raw[0]=iterations==2?8:0;
    for(unsigned i=0;i<(iterations==2?22u:88u);++i) fm1_timer5_irq();
  }
  if(iterations>=4 && iterations<11) accepted_encoder(iterations,iterations-4,1);
  audio_irq();
  reference_pending();
}
int main(int argc,char **argv) {
  assert(argc>=2);mode=argv[1];trigger=argc==3?(unsigned)atoi(argv[2]):0;
  fresh_target();f.allow_halt=1;f.icfg&=~0x100u;
  target_q.policy.max_phase_ticks=1000000;target_q.policy.lease_ticks=2000000;
  if(!strcmp(mode,"wrap")) f.now=UINT32_MAX-200000;
  if(!strcmp(mode,"unqualified")) memset(&target_q,0,sizeof target_q);
  init_reference();
  if(!setjmp(stopped)) { lunar_diagnostic_cstart();assert(0); }
  assert(return_policy.state==LUNAR_SR_TERMINAL && !(f.icfg&0x100u));
  if(!strcmp(mode,"unqualified")) {
    assert(!irq_init_calls && !prepare_calls && !dma_starts && !irq_enables && !f.transfers);
  } else if(!strcmp(mode,"fault") || !strcmp(mode,"reenter") || !strcmp(mode,"early-irq")) {
    assert(seen>=trigger);assert(word(&PLATFORM->owner.transport.fault));
    if(trigger<=3) assert(!dma_starts && !irq_enables && !tail_calls);
    if(trigger==4 || trigger==5) assert(!irq_enables && !tail_calls);
  } else if(!strcmp(mode,"empty")) assert(word(&PLATFORM->owner.transport.underruns)==1 && !tail_calls);
  else if(!strcmp(mode,"overflow")) assert(!tail_calls);
  else if(!strcmp(mode,"clock-back")) assert(return_policy.first_error==LUNAR_SR_CLOCK && !tail_calls);
  else { assert(iterations==20 && tail_calls==1 && accepted>=2 && nonzero); }
  if(dma_starts) assert(stop_calls==1);
  uint64_t frames=lunar_diagnostic_state()->frames;unsigned tx=f.transfers,tail=tail_calls;
  fm1_timer5_irq();audio_irq();lunar_selected_return_stop_audio();
  assert(lunar_diagnostic_state()->frames==frames && f.transfers==tx && tail_calls==tail);
  printf("audio owner %s boundary=%u frames=%llu blocks=%u nonzero=%u scans=%u accepted=%u tail=%u passed\n",
      mode,trigger,(unsigned long long)frames,consumed,nonzero,scans,accepted,tail_calls);
  return 0;
}

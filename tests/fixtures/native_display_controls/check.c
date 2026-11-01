/* SPDX-License-Identifier: MIT. Host mocks/oracle buffers are test-only. */
#include "diagnostic_app.h"
#include "diagnostic_display.h"
#include "diagnostic_transport.h"
#include "fm1_dx7_budget.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <pthread.h>
#include <sched.h>

static fm1_app_t reference;
static unsigned char reference_sound[LUNAR_DIAGNOSTIC_ARENA_BYTES] FM1_APP_ALIGN16;
static fm1_app_arena_t reference_arenas[FM1_APP_UNITS];
static lunar_diagnostic_display_t display;
static struct {
  const uint8_t *lease;
  uint8_t bytes[LUNAR_DISPLAY_ROW_BYTES];
  uint32_t row, ticket, calls;
  int reject;
} mock;
static int submit(void *context, uint32_t row, uint32_t ticket,
                  const uint8_t *bytes, size_t count) {
  assert(context == &mock && count == sizeof mock.bytes);
  mock.lease = bytes; mock.row = row; mock.ticket = ticket; ++mock.calls;
  memcpy(mock.bytes, bytes, count);
  return !mock.reject;
}
static void check_row(const uint16_t *pixels) {
  assert(!memcmp(mock.lease, mock.bytes, sizeof mock.bytes));
  for (unsigned x = 0; x < LUNAR_DISPLAY_WIDTH; ++x) {
    uint16_t color = pixels[mock.row * LUNAR_DISPLAY_WIDTH + x];
    assert(mock.bytes[2*x] == (uint8_t)(color >> 8));
    assert(mock.bytes[2*x+1] == (uint8_t)color);
  }
}
static const uint16_t *pattern_draw(void *context, uint32_t min_frames) {
  assert(min_frames == 1470); return context;
}
static void display_guards(void) {
  static uint16_t pattern[LUNAR_DISPLAY_WIDTH * LUNAR_DISPLAY_HEIGHT];
  for (unsigned i=0;i<sizeof pattern/sizeof *pattern;++i) pattern[i]=(uint16_t)i;
  pattern[0]=0xf800; pattern[1]=0x07e0; pattern[2]=0x001f;
  static lunar_diagnostic_display_t unbound, timeout, wrong, rejected, failed;
  assert(lunar_display_init(&unbound,LUNAR_DISPLAY_UNBOUND,submit,&mock)==-1);
  assert(!unbound.submit && !unbound.active && !unbound.pending);
  assert(lunar_display_frame(&unbound,pattern_draw,pattern,1470)==-1);
  assert(lunar_display_init(&display,LUNAR_DISPLAY_HOST_MOCK,submit,&mock)==0);
  display.ticket=UINT32_MAX; /* ticket zero is a valid outstanding lease */
  assert(lunar_display_frame(&display,pattern_draw,pattern,1470)==1);
  for(unsigned y=0;y<240;++y) {
    assert(lunar_display_pump(&display)==1 && mock.row==y);
    if(!y) assert(!mock.ticket && !memcmp(mock.bytes,"\xf8\0\x07\xe0\0\x1f",6));
    check_row(pattern);
    for(unsigned delay=0;delay<3;++delay) {
      assert(!lunar_display_pump(&display));
      assert(!lunar_display_frame(&display,pattern_draw,pattern,1470));
      assert(!lunar_display_complete(&display,mock.ticket,0));
      check_row(pattern);
    }
    assert(lunar_display_complete(&display,mock.ticket,1)==1);
  }
  assert(!display.active && !display.pending && !display.pixels);
  assert(!lunar_display_pump(&display));
  assert(!lunar_display_init(&timeout,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  assert(lunar_display_frame(&timeout,pattern_draw,pattern,1470)==1);
  assert(lunar_display_pump(&timeout)==1);
  lunar_display_timeout(&timeout);
  assert(timeout.fault==LUNAR_DISPLAY_TIMEOUT && timeout.pending && timeout.active);
  assert(lunar_display_complete(&timeout,mock.ticket,1)==-1);
  assert(lunar_display_pump(&timeout)==-1);
  assert(lunar_display_init(&timeout,LUNAR_DISPLAY_HOST_MOCK,submit,&mock)==-1);
  check_row(pattern); /* no timeout release or reuse */
  assert(!lunar_display_init(&wrong,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  assert(lunar_display_frame(&wrong,pattern_draw,pattern,1470)==1);
  assert(lunar_display_pump(&wrong)==1);
  assert(lunar_display_complete(&wrong,mock.ticket+1,1)==-1 && wrong.pending);
  assert(!lunar_display_init(&rejected,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  assert(lunar_display_frame(&rejected,pattern_draw,pattern,1470)==1);
  mock.reject=1;
  assert(lunar_display_pump(&rejected)==-1 && rejected.pending);
  mock.reject=0;
  assert(!lunar_display_init(&failed,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  assert(lunar_display_frame(&failed,pattern_draw,pattern,1470)==1);
  assert(lunar_display_pump(&failed)==1);
  assert(lunar_display_complete(&failed,mock.ticket,-1)==-1 && failed.pending);
}
static void init_reference(void) {
  reference_arenas[0].mem=reference_sound;
  reference_arenas[0].bytes=sizeof reference_sound;
  assert(!fm1_app_init_arenas(&reference,LUNAR_DIAGNOSTIC_RATE,reference_arenas));
  assert(!fm1_app_select(&reference,0,fm1_app_find("dx7")));
  assert(fm1_dx7_set_voice_limit(reference.unit[0].self,8));
}
static void render_pair(void) {
  int32_t pcm[128];
  assert(!lunar_diagnostic_render(pcm,64));
  const float *expected=fm1_app_render(&reference,64);
  for(unsigned i=0;i<128;++i) {
    float v=expected[i];
    int32_t q=v>=1?32767:v<=-1?-32767:(int32_t)(v*32767.0f);
    assert(pcm[i]==q);
  }
}
static void actual_app_display(void) {
  static lunar_diagnostic_display_t actual;
  assert(!lunar_diagnostic_init()); init_reference();
  lunar_diagnostic_key(4,1); fm1_app_key(&reference,4,1,100);
  render_pair();
  assert(!lunar_display_init(&actual,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  assert(lunar_display_frame(&actual,lunar_diagnostic_owner_draw,0,1470)==1);
  assert(fm1_app_draw(&reference,1470)==1);
  assert(!memcmp(lunar_diagnostic_state()->tft.px,reference.tft.px,sizeof reference.tft.px));
  /* Controls/render may dirty state during a transfer but cannot write pixels.
   * The frame API must not invoke draw again until every row is complete. */
  lunar_diagnostic_knob(FM1_ENC_KNOB1,1);
  fm1_app_encoder(&reference,FM1_ENC_KNOB1,1);
  for(unsigned y=0;y<240;++y) {
    assert(lunar_display_pump(&actual)==1 && mock.row==y);
    if(y<8) render_pair();
    assert(!lunar_display_frame(&actual,lunar_diagnostic_owner_draw,0,1470));
    check_row(reference.tft.px);
    assert(lunar_display_complete(&actual,mock.ticket,1)==1);
  }
  assert(!lunar_display_frame(&actual,lunar_diagnostic_owner_draw,0,1470));
  /* min_frames*4 remains the current app's cadence, not one native LCD row. */
  assert(lunar_diagnostic_state()->last_draw==64);
  while(reference.frames<64+5888) render_pair();
  assert(lunar_display_frame(&actual,lunar_diagnostic_owner_draw,0,1470)==1);
  assert(fm1_app_draw(&reference,1470)==1);
  assert(!memcmp(lunar_diagnostic_state()->tft.px,reference.tft.px,sizeof reference.tft.px));
  for(unsigned y=0;y<240;++y) {
    assert(lunar_display_pump(&actual)==1);
    check_row(reference.tft.px);
    assert(lunar_display_complete(&actual,mock.ticket,1)==1);
  }
  assert(!lunar_diagnostic_status() && !reference.store_ready);
  printf("display proof passed app=%zu display=%zu row=%u framebuffer=%zu\n",
         sizeof reference,sizeof actual,LUNAR_DISPLAY_ROW_BYTES,sizeof reference.tft.px);
}

/* Capacities are offline experiment inputs. No target latency admission. */
enum { INPUT_SLOTS=16, PCM_SLOTS=4 };
static lunar_transport_t queue;
static lunar_input_t inputs[INPUT_SLOTS];
static lunar_pcm_t blocks[PCM_SLOTS];
static int32_t expected_pcm[LUNAR_PCM_WORDS];
static uint32_t applied, last_scan;
static int apply_reference(const lunar_input_t *e) {
  switch(e->kind) {
    case LUNAR_INPUT_KEY: fm1_app_key(&reference,e->id,e->value,100); break;
    case LUNAR_INPUT_BUTTON: fm1_app_button(&reference,e->id,e->value); break;
    case LUNAR_INPUT_ENCODER: fm1_app_encoder(&reference,e->id,e->value); break;
    default: return -1;
  }
  assert(reference.unit[0].index==fm1_app_find("dx7"));
  assert(fm1_dx7_set_voice_limit(reference.unit[0].self,8));
  return 0;
}
static int apply_actual(void *ctx,const lunar_input_t *e) {
  assert(ctx==&queue); ++applied; last_scan=e->scan;
  assert(!apply_reference(e));
  switch(e->kind) {
    case LUNAR_INPUT_KEY: lunar_diagnostic_key(e->id,e->value); break;
    case LUNAR_INPUT_BUTTON: return lunar_diagnostic_owner_button(e->id,e->value);
    case LUNAR_INPUT_ENCODER: return lunar_diagnostic_owner_encoder(e->id,e->value);
    default: return -1;
  }
  return lunar_diagnostic_status()?-1:0;
}
static int render_actual(void *ctx,int32_t *pcm) {
  assert(ctx==&queue);
  if(lunar_diagnostic_owner_render(pcm,LUNAR_PCM_FRAMES)) return -1;
  const float *expected=fm1_app_render(&reference,LUNAR_PCM_FRAMES);
  for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) {
    float v=expected[i];
    int32_t q=v>=1?32767:v<=-1?-32767:(int32_t)(v*32767.0f);
    expected_pcm[i]=q*128; pcm[i]*=128;
  }
  return 0;
}
static void projection(void) {
  const fm1_app_t *a=lunar_diagnostic_state();
  assert(a->frames==reference.frames && a->mode==reference.mode);
  assert(!memcmp(a->tft.px,reference.tft.px,sizeof reference.tft.px));
  assert(!a->store_ready && !reference.store_ready);
  assert(!memcmp(a->key_note,reference.key_note,sizeof a->key_note));
  assert(!memcmp(a->led,reference.led,sizeof a->led));
  assert(a->scope_pos==reference.scope_pos && a->scope_block==reference.scope_block);
  assert(!memcmp(a->scope,reference.scope,sizeof a->scope));
  for(unsigned u=0;u<FM1_APP_UNITS;++u) {
    assert(a->unit[u].index==reference.unit[u].index);
    assert(!memcmp(a->unit[u].value,reference.unit[u].value,sizeof a->unit[u].value));
  }
  fm1_dx7_budget_stats_t stats;
  assert(fm1_dx7_get_budget_stats(a->unit[0].self,&stats) && stats.limit==8);
}
static void step(void) {
  int32_t out[LUNAR_PCM_WORDS];
  assert(lunar_transport_produce(&queue,INPUT_SLOTS,apply_actual,render_actual,&queue)==1);
  /* Published PCM is copied only by the IRQ surface. */
  assert(lunar_transport_irq(&queue,out)==1);
  assert(!memcmp(out,expected_pcm,sizeof out)); projection();
}
static void matrix(uint32_t scan,unsigned id,int down) {
  assert(lunar_transport_matrix(&queue,scan,id,down)==1);
}
static void encoder(uint32_t scan,unsigned id,int delta) {
  assert(lunar_transport_encoder(&queue,scan,id,delta)==1);
}
static void actual_panel_transport(void) {
  static lunar_diagnostic_display_t panel_display;
  assert(!lunar_transport_init(&queue,inputs,INPUT_SLOTS,blocks,PCM_SLOTS,UINT32_MAX-3));
  assert(!lunar_display_init(&panel_display,LUNAR_DISPLAY_HOST_MOCK,submit,&mock));
  lunar_diagnostic_key(4,0); fm1_app_key(&reference,4,0,100);
  assert(!lunar_diagnostic_owner_select(fm1_app_find("dx7")));
  assert(!fm1_app_select(&reference,0,fm1_app_find("dx7")));
  assert(fm1_dx7_set_voice_limit(reference.unit[0].self,8));
  fm1_dx7_budget_stats_t stats;
  assert(fm1_dx7_get_budget_stats(lunar_diagnostic_state()->unit[0].self,&stats));
  assert(stats.limit==8); /* recreation cannot retain the global default 12 */
  /* Every physical matrix ID, press/release in capture order. HOME before
   * each button makes this a bounded mapping replay rather than a random UI. */
  for(unsigned id=0;id<41;++id) {
    matrix(100+id,8,1); matrix(100+id,8,0); step();
    matrix(200+id,id,1); step(); matrix(200+id,id,0); step();
  }
  matrix(300,8,1); matrix(300,8,0); step();
  for(unsigned id=0;id<7;++id) {
    encoder(400+id,id,1); step(); encoder(500+id,id,-1); step();
  }
  /* Nonmonotonic timestamps remain FIFO; modifier spans an encoder event. */
  matrix(900,3,1); encoder(2,3,1); matrix(1,3,0); step();
  assert(last_scan==1);
  /* ARP hold elapsed in rendered samples, not wall time or LCD completion. */
  matrix(1000,10,1); step();
  for(unsigned n=0;n<400;++n) step();
  matrix(1001,10,0); step();
  matrix(1002,8,1); matrix(1002,8,0); step();
  /* SEQ editing with held REC and note/step keys, then PLAY/STOP. */
  matrix(1050,11,1); matrix(1051,11,0); step();
  matrix(1052,13,1); matrix(1053,18,1); step();
  matrix(1054,18,0); matrix(1055,13,0); step();
  matrix(1056,12,1); matrix(1057,12,0); step();
  for(unsigned n=0;n<16;++n) step();
  matrix(1058,12,1); matrix(1059,12,0); step();
  matrix(1060,8,1); matrix(1061,8,0); step();
  /* Real SAVE uses the existing no-store refusal; no persistence adapter. */
  matrix(1100,9,1); matrix(1101,9,0); step();
  assert(!lunar_diagnostic_state()->store_ready);
  /* Draw after the input/audio loop; drain rows while app renders/preempts.
   * No new draw can happen while the framebuffer lease is held. */
  assert(lunar_display_frame(&panel_display,lunar_diagnostic_owner_draw,0,1470)==1);
  assert(fm1_app_draw(&reference,1470)==1);
  for(unsigned y=0;y<240;++y) {
    assert(lunar_display_pump(&panel_display)==1); check_row(reference.tft.px);
    step(); assert(!lunar_display_frame(&panel_display,lunar_diagnostic_owner_draw,0,1470));
    check_row(reference.tft.px);
    assert(lunar_display_complete(&panel_display,mock.ticket,1)==1);
  }
  projection();
  printf("panel transport passed events=%u queue=%zu inputs=%zu pcm=%zu block=%zu\n",
         applied,sizeof queue,sizeof inputs,sizeof blocks,sizeof(lunar_pcm_t));
}
static int nothing(void *p,const lunar_input_t *e) { (void)p;(void)e; return 0; }
static int render_fail(void *p,int32_t *out) { (void)p;(void)out; return -1; }
static void zeros(const int32_t *out) { for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(!out[i]); }
static void transport_guards(void) {
  static lunar_transport_t q[9];
  static lunar_input_t in[9][2]; static lunar_pcm_t pcm[9][2];
  int32_t out[LUNAR_PCM_WORDS],*slot; uint32_t ticket;
  assert(lunar_transport_init(&q[0],in[0],3,pcm[0],2,0)==-1);
  assert(lunar_transport_irq(&q[0],out)==-1); zeros(out);
  for(unsigned k=1;k<9;++k) assert(!lunar_transport_init(&q[k],in[k],2,pcm[k],2,UINT32_MAX));
  assert(!lunar_transport_irq(&q[1],out)); zeros(out);
  assert(atomic_load(&q[1].underruns)==1);
  for(unsigned n=0;n<6;++n) { /* both indices cross wrap; no overwrite before retire */
    assert(lunar_transport_reserve(&q[1],&slot,&ticket)==1);
    for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) slot[i]=(int32_t)(n+1);
    assert(!lunar_transport_irq(&q[1],out)); zeros(out); /* unpublished */
    assert(lunar_transport_publish(&q[1],ticket)==1);
    assert(lunar_transport_irq(&q[1],out)==1);
    for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(out[i]==(int32_t)n+1);
  }
  for(unsigned n=0;n<2;++n) {
    assert(lunar_transport_reserve(&q[2],&slot,&ticket)==1);
    memset(slot,42,sizeof(lunar_pcm_t)); assert(lunar_transport_publish(&q[2],ticket)==1);
  }
  assert(!lunar_transport_reserve(&q[2],&slot,&ticket)); /* full: no fault/drop */
  assert(!atomic_load(&q[2].fault));
  lunar_transport_fault(&q[2],77);
  assert(lunar_transport_irq(&q[2],out)==-1); zeros(out); /* queued sound suppressed */
  assert(lunar_transport_reserve(&q[3],&slot,&ticket)==1);
  assert(lunar_transport_reserve(&q[3],&slot,&ticket)==-1 && q[3].leased);
  assert(lunar_transport_reserve(&q[4],&slot,&ticket)==1);
  assert(lunar_transport_publish(&q[4],ticket+1)==-1 && q[4].leased);
  assert(lunar_transport_publish(&q[5],0)==-1);
  assert(lunar_transport_matrix(&q[6],0,14,1)==1);
  assert(lunar_transport_matrix(&q[6],0,14,0)==1);
  assert(lunar_transport_matrix(&q[6],0,15,1)==-1);
  assert(atomic_load(&q[6].fault)==LUNAR_TRANSPORT_OVERFLOW);
  assert(lunar_transport_irq(&q[6],out)==-1); zeros(out);
  assert(lunar_transport_encoder(&q[7],0,7,1)==-1);
  assert(lunar_transport_produce(&q[8],2,nothing,render_fail,0)==-1 && q[8].leased);
  assert(lunar_transport_irq(&q[8],out)==-1); zeros(out);
  printf("transport guard proof passed\n");
}

/* Real host threads exercise publication visibility independently of the
 * deterministic actual-app oracle. This is not a target IRQ timing test. */
static lunar_transport_t stress;
static lunar_input_t stress_input[16];
static lunar_pcm_t stress_pcm[4];
static _Atomic unsigned stress_done;
static unsigned stress_applied, stress_rendered;
static void *capture_thread(void *unused) {
  (void)unused;
  for(unsigned n=0;n<10000;++n) {
    while(atomic_load_explicit(&stress.input_head,memory_order_acquire)-
          atomic_load_explicit(&stress.input_tail,memory_order_acquire)>=16) sched_yield();
    assert(lunar_transport_matrix(&stress,n,14,n&1)==1);
  }
  return NULL;
}
static void *irq_thread(void *unused) {
  (void)unused; unsigned received=0;
  int32_t out[LUNAR_PCM_WORDS];
  for(;;) {
    int r=lunar_transport_irq(&stress,out);
    assert(r>=0);
    if(r) {
      for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(out[i]==(int32_t)(received*128+i));
      ++received;
    } else {
      zeros(out);
      if(atomic_load_explicit(&stress_done,memory_order_acquire) &&
         atomic_load(&stress.pcm_head)==atomic_load(&stress.pcm_tail)) break;
      sched_yield();
    }
  }
  return (void *)(uintptr_t)received;
}
static int stress_apply(void *unused,const lunar_input_t *e) {
  (void)unused;
  assert(e->scan==stress_applied && e->kind==LUNAR_INPUT_KEY && !e->id);
  assert(e->value==(int)(stress_applied&1)); ++stress_applied; return 0;
}
static int stress_render(void *unused,int32_t *pcm) {
  (void)unused;
  for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) pcm[i]=(int32_t)(stress_rendered*128+i);
  ++stress_rendered; return 0;
}
static void concurrency(void) {
  pthread_t capture,irq; void *received;
  assert(!lunar_transport_init(&stress,stress_input,16,stress_pcm,4,UINT32_MAX-8));
  assert(!pthread_create(&capture,NULL,capture_thread,NULL));
  assert(!pthread_create(&irq,NULL,irq_thread,NULL));
  while(stress_applied<10000 || stress_rendered<10000) {
    assert(lunar_transport_produce(&stress,8,stress_apply,stress_render,NULL)>=0);
    sched_yield();
  }
  assert(!pthread_join(capture,NULL));
  atomic_store_explicit(&stress_done,1,memory_order_release);
  assert(!pthread_join(irq,&received));
  assert((uintptr_t)received==stress_rendered && stress_applied==10000);
  printf("SPSC publication passed inputs=%u blocks=%u\n",stress_applied,stress_rendered);
}
int main(void) {
  display_guards(); actual_app_display(); transport_guards(); actual_panel_transport(); concurrency(); return 0;
}

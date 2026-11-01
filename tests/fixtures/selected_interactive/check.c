/* Fixture MIT; linked imported scanner GPL-3.0-only. No hardware. */
#include "selected_interactive_owner.h"
#include "diagnostic_app.h"
#include "selected_project_blob.h"
#include "fm1_app_state.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

static lunar_selected_platform_t platform;
static lunar_input_t inputs[16];
static lunar_pcm_t blocks[2];
static fm1_app_t reference;
static unsigned char arena[16384] FM1_APP_ALIGN16;
static fm1_app_arena_t arenas[FM1_APP_UNITS];
static unsigned char work_space[655360] FM1_APP_ALIGN16;
static fm1_app_state_report_t report;
static uint32_t fake_gpio[8][8], fake_clock;
static uint8_t scan_raw[11];
static void matrix(unsigned, int);
static void encoder(unsigned, int);
#include "fm1_time.h"
#include "fm1_gpio.h"
#include "fm1_cc.h"
#undef FM1_PR
#define FM1_PR(p,r) fake_gpio[p][(r)/4]
static uint32_t fake_ticks(void) { return fake_clock++; }
#define fm1_ticks fake_ticks
#define FM1_INPUT_ACCEPTED_KEY(scan,id,down) matrix(id,down)
#define FM1_INPUT_ACCEPTED_ENCODER(scan,id,delta) encoder(id,delta)
#include "fm1_input.h"
static uint32_t now, launches, rows, selected, data, live, done_flag;
static unsigned row_phase, polls, draw_count, nonzero;
static int fail_scan, fail_audio, fail_spi;
static const uint8_t *borrowed;
static uint8_t borrowed_copy[480];
static size_t borrowed_n;
static int32_t expected[2][128], out[128];
static uint32_t expected_head, expected_tail;
static lunar_input_t pending[16];
static unsigned pending_n, applied;
static uint16_t frozen[240*240];
static uint32_t frozen_ticket;
static const char *frame_path;
static int scan_init(void *ctx) {
  assert(ctx==&platform && lunar_diagnostic_state()->unit[0].e);
  assert(!strcmp(lunar_diagnostic_state()->unit[0].e->id,"trio"));
  assert(!platform.started && !launches);
  if(!fail_scan) fm1_input_init();
  return fail_scan;
}
static void scan_tick(void *ctx) {
  assert(ctx==&platform);
  uint32_t v=(uint32_t)~scan_raw[fm1__tick_col];
  fake_gpio[FM1_PA][FM1_IN/4]=(v&1u)|((v&0x1eu)<<4);
  fake_gpio[FM1_PB][FM1_IN/4]=(v&0x20u)<<2;
  fm1_input_tick();
}
static int audio_start(void *ctx) {
  assert(ctx==&platform && !platform.started);
  assert(atomic_load(&platform.owner.transport.pcm_head)-
         atomic_load(&platform.owner.transport.pcm_tail)==1);
  assert(lunar_diagnostic_state()->frames==64);
  return fail_audio;
}
static int pins(void *ctx,int s,int d) {
  assert(ctx==&platform);
  if(fail_spi) return -1;
  if(!s) { assert(live && done_flag); live=0; borrowed=0; }
  selected=(unsigned)s; data=(unsigned)d; return 0;
}
static int clear(void *ctx) { assert(ctx==&platform); done_flag=0; return 0; }
static int done(void *ctx) {
  assert(ctx==&platform);
  if(borrowed) assert(!memcmp(borrowed,borrowed_copy,borrowed_n));
  if(live && polls++>=1) done_flag=1;
  return (int)done_flag;
}
static int fence(void *ctx) { assert(ctx==&platform); return 0; }
static int launch(void *ctx,const uint8_t *p,size_t n) {
  assert(ctx==&platform && selected && !live && !done_flag);
  assert(data==(row_phase&1u));
  if(!(row_phase&1u)) { static const uint8_t cmd[]={0x2a,0x2b,0x2c}; assert(n==1 && *p==cmd[row_phase/2]); }
  else if(row_phase==1) assert(n==4 && !memcmp(p,"\0\0\0\357",4));
  else if(row_phase==3) assert(n==4 && p[0]==0 && p[1]==rows%240 && p[2]==0 && p[3]==rows%240);
  else {
    assert(n==480);
    const uint16_t *px=platform.owner.display.pixels+(rows%240)*240;
    for(unsigned x=0;x<240;++x) assert(p[2*x]==(uint8_t)(px[x]>>8) && p[2*x+1]==(uint8_t)px[x]);
    ++rows;
  }
  row_phase=(row_phase+1)%6; ++launches;
  borrowed=p; borrowed_n=n; memcpy(borrowed_copy,p,n); live=1; polls=0;
  return 1;
}
static uint32_t ticks(void *ctx) { assert(ctx==&platform); return now; }
static uint32_t read_bytes(void *ctx,uint32_t off,uint8_t *dest,uint32_t n) {
  (void)ctx;
  if(off>=lunar_selected_project_blob_bytes) return 0;
  if(n>lunar_selected_project_blob_bytes-off) n=lunar_selected_project_blob_bytes-off;
  memcpy(dest,lunar_selected_project_blob+off,n); return n;
}
static void init_reference(void) {
  arenas[0].mem=arena; arenas[0].bytes=sizeof arena;
  assert(!fm1_app_init_arenas(&reference,LUNAR_DIAGNOSTIC_RATE,arenas));
  fm1_app_load_opts_t opts; fm1_app_load_opts_init(&opts);
  opts.kind=FM1_STATE_PROJECT; opts.flags=FM1_APP_LOAD_QUIET;
  fm1_app_state_workspace_t work={work_space,sizeof work_space};
  assert(fm1_app_state_load_with_workspace(&reference,read_bytes,0,
      lunar_selected_project_blob_bytes,&opts,&work,&report));
  assert(report.r.code==FM1_STATE_OK && !report.r.skipped && !report.r.unknown);
  assert(reference.unit[0].e && reference.unit[0].e->n_params==14);
}
static void ref_input(const lunar_input_t *e) {
  if(e->kind==LUNAR_INPUT_KEY) fm1_app_key(&reference,e->id,e->value,100);
  else if(e->kind==LUNAR_INPUT_BUTTON) fm1_app_button(&reference,e->id,e->value);
  else { assert(e->kind==LUNAR_INPUT_ENCODER); fm1_app_encoder(&reference,e->id,e->value); }
  ++applied;
}
static void ref_render(void) {
  assert(expected_head-expected_tail<2);
  const float *p=fm1_app_render(&reference,64);
  int32_t *q=expected[expected_head++%2];
  for(unsigned i=0;i<128;++i) {
    assert(isfinite(p[i]));
    q[i]=(p[i]>=1?32767:p[i]<=-1?-32767:(int32_t)(p[i]*32767.0f))*128;
    if(q[i]) ++nonzero;
  }
}
static void projection(void) {
  const fm1_app_t *a=lunar_diagnostic_state();
  assert(a->frames==reference.frames && a->mode==reference.mode);
  assert(a->level[0]==reference.level[0] && !memcmp(&a->info,&reference.info,sizeof a->info));
  assert(!memcmp(a->key_note,reference.key_note,sizeof a->key_note));
  assert(!memcmp(a->led,reference.led,sizeof a->led));
  assert(a->scope_pos==reference.scope_pos && a->scope_block==reference.scope_block);
  assert(!memcmp(a->scope,reference.scope,sizeof a->scope));
  assert(!memcmp(a->tft.px,reference.tft.px,sizeof a->tft.px));
  for(unsigned u=0;u<FM1_APP_UNITS;++u) {
    assert(a->unit[u].index==reference.unit[u].index);
    assert(!memcmp(a->unit[u].value,reference.unit[u].value,sizeof a->unit[u].value));
  }
}
static void draw_reference_if_called(unsigned active,unsigned row) {
  lunar_diagnostic_display_t *d=&platform.owner.display;
  /* Observe actual frame boundaries, not a mirrored draw/cadence algorithm. */
  if(!active || (row==239 && d->next_row!=239)) {
    int drew=fm1_app_draw(&reference,1470);
    if(drew) {
      assert(d->pixels==lunar_diagnostic_state()->tft.px);
      assert(!memcmp(d->pixels,reference.tft.px,sizeof frozen));
      ++draw_count; memcpy(frozen,d->pixels,sizeof frozen); frozen_ticket=d->ticket;
    }
  }
  if(d->active) { assert(!memcmp(frozen,d->pixels,sizeof frozen)); (void)frozen_ticket; }
}
static void consume(void) {
  assert(expected_tail!=expected_head);
  uint64_t frames=lunar_diagnostic_state()->frames;
  assert(lunar_selected_platform_audio(&platform,out)==1);
  assert(lunar_diagnostic_state()->frames==frames); /* IRQ cannot render/apply */
  assert(!memcmp(out,expected[expected_tail++%2],sizeof out));
}
static int main_step(void) {
  uint32_t old_tail=atomic_load(&platform.owner.transport.input_tail);
  unsigned active=platform.owner.display.active,row=platform.owner.display.next_row;
  int r=lunar_selected_platform_main(&platform);
  assert(r>=0);
  unsigned used=atomic_load(&platform.owner.transport.input_tail)-old_tail;
  assert(used<=pending_n);
  for(unsigned i=0;i<used;++i) ref_input(pending+i);
  memmove(pending,pending+used,(pending_n-used)*sizeof *pending); pending_n-=used;
  if(r) ref_render();
  draw_reference_if_called(active,row); projection();
  return r;
}
static void step(void) { assert(main_step()==1); consume(); }
static void matrix(unsigned id,int down) {
  assert(pending_n<16);
  pending[pending_n++]=(lunar_input_t){platform.scan,id<14?LUNAR_INPUT_BUTTON:LUNAR_INPUT_KEY,
      id<14?id:id-14,(int16_t)down};
  lunar_selected_platform_matrix(&platform,id,down);
}
static void encoder(unsigned id,int delta) {
  assert(pending_n<16);
  pending[pending_n++]=(lunar_input_t){platform.scan,LUNAR_INPUT_ENCODER,id,(int16_t)delta};
  lunar_selected_platform_encoder(&platform,id,delta);
}
static void save_frame(void) {
  FILE *f=fopen(frame_path,"wb"); assert(f); fputs("P6\n240 240\n255\n",f);
  const uint16_t *px=lunar_diagnostic_state()->tft.px;
  for(unsigned i=0;i<240*240;++i) {
    unsigned v=px[i];
    unsigned char rgb[3]={(unsigned char)(((v>>11)&31)*255/31),
        (unsigned char)(((v>>5)&63)*255/63),(unsigned char)((v&31)*255/31)};
    assert(fwrite(rgb,1,3,f)==3);
  }
  assert(!fclose(f));
}
static void scan_frames(unsigned n) {
  uint64_t before=lunar_diagnostic_state()->frames;
  for(unsigned i=0;i<n*11;++i) lunar_selected_platform_timer(&platform);
  assert(lunar_diagnostic_state()->frames==before); /* real accepted hooks enqueue only */
}
static void positive(void) {
  ref_render(); draw_reference_if_called(0,0); projection(); consume();
  /* Actual scanner -> accepted hooks -> platform -> queued app input. */
  scan_frames(2);
  scan_raw[0]=1u<<3; scan_frames(2); assert(pending_n==1); step();
  scan_raw[0]=0; scan_frames(8); assert(pending_n==1); step();
  static const unsigned turn[]={1,3,2,0};
  for(unsigned i=0;i<4;++i) {
    scan_raw[0]=(uint8_t)((turn[i]>>1)&1u); scan_raw[1]=(uint8_t)(turn[i]&1u);
    scan_frames(2);
  }
  assert(pending_n==1); step();
  /* Repeated main calls cannot consume events or render through full PCM. */
  assert(main_step()==1 && main_step()==1);
  matrix(18,1); uint64_t frames=reference.frames;
  assert(main_step()==0 && reference.frames==frames && pending_n==1);
  consume(); assert(main_step()==1 && !pending_n); consume(); consume();
  matrix(18,0); step(); assert(nonzero);
  for(unsigned id=0;id<41;++id) {
    matrix(8,1); matrix(8,0); step();
    matrix(id,1); step(); matrix(id,0); step();
  }
  matrix(8,1); matrix(8,0); step();
  for(unsigned id=0;id<7;++id) { encoder(id,1); step(); encoder(id,-1); step(); }
  matrix(3,1); encoder(3,1); matrix(3,0); step();
  /* Prefix split keeps the modifier held until its queued release. */
  for(unsigned i=0;i<8;++i) matrix(18+(i%3),i<4);
  step(); assert(pending_n==4); step(); assert(!pending_n);
  matrix(11,1); matrix(11,0); step();
  matrix(13,1); matrix(18,1); step();
  matrix(18,0); matrix(13,0); step();
  matrix(3,1); matrix(13,1); matrix(13,0); matrix(3,0); step();
  matrix(12,1); matrix(12,0); step();
  for(unsigned i=0;i<16;++i) step();
  matrix(12,1); matrix(12,0); step();
  matrix(8,1); matrix(8,0); step();
  matrix(9,1); matrix(9,0); step();
  assert(!lunar_diagnostic_state()->store_ready);
  /* LCD continues while audio queue is full, with frame/row bytes frozen. */
  for(unsigned i=0;i<15000 && rows<240;++i) { if(main_step()==1) consume(); }
  assert(rows>=240 && draw_count>=1 && !lunar_diagnostic_status());
  /* Retain an actual app frame after the next eligible HOME redraw. */
  matrix(8,1); matrix(8,0); step();
  unsigned previous_draws=draw_count;
  for(unsigned i=0;i<15000 && draw_count==previous_draws;++i) step();
  assert(draw_count>previous_draws); save_frame();
  printf("actual selected owner passed: events=%u blocks=%llu rows=%u draws=%u nonzero=%u app=%zu owner=%zu platform=%zu\n",
      applied,(unsigned long long)(reference.frames/64),rows,draw_count,nonzero,
      sizeof reference,sizeof platform.owner,sizeof platform);
}
int main(int argc,char **argv) {
  assert(argc==3); frame_path=argv[2];
  lunar_selected_platform_ops_t ops={scan_init,scan_tick,audio_start,&platform};
  lunar_spi_model_ops_t spi={pins,clear,done,fence,launch,ticks,&platform};
  fail_scan=!strcmp(argv[1],"scan-fail"); fail_audio=!strcmp(argv[1],"audio-fail");
  int bad_config=!strcmp(argv[1],"bad-config");
  init_reference();
  assert(lunar_selected_platform_audio(&platform,out)<0);
  for(unsigned i=0;i<128;++i) assert(!out[i]);
  int r=lunar_selected_platform_start(&platform,&ops,inputs,16,blocks,2,UINT32_MAX-3,
      bad_config?0:4,1470,&spi,100000,1000);
  if(fail_scan || fail_audio || bad_config) {
    assert(r<0 && !platform.started);
    assert(lunar_selected_platform_audio(&platform,out)<0);
    for(unsigned i=0;i<128;++i) assert(!out[i]);
  } else if(!strcmp(argv[1],"positive")) { assert(!r); positive(); }
  else {
    assert(!r);
    if(!strcmp(argv[1],"overflow")) {
      for(unsigned i=0;i<17;++i) lunar_selected_platform_matrix(&platform,18,i&1);
      assert(atomic_load(&platform.owner.transport.fault)==LUNAR_TRANSPORT_OVERFLOW);
    } else if(!strcmp(argv[1],"spi-fault")) {
      /* Fault after first actual draw has an active framebuffer/row lease. */
      while(!platform.owner.display.active) {
        assert(lunar_selected_platform_audio(&platform,out)==1);
        assert(lunar_selected_platform_main(&platform)==1);
      }
      fail_spi=1;
    } else { assert(!strcmp(argv[1],"repeat")); assert(lunar_selected_platform_start(&platform,
        &ops,inputs,16,blocks,2,0,4,1470,&spi,100000,1000)<0); }
    assert(lunar_selected_platform_main(&platform)<0);
    uint64_t frames=lunar_diagnostic_state()->frames;
    for(unsigned i=0;i<8;++i) {
      assert(lunar_selected_platform_main(&platform)<0);
      assert(lunar_selected_platform_audio(&platform,out)<0);
      for(unsigned j=0;j<128;++j) assert(!out[j]);
    }
    assert(lunar_diagnostic_state()->frames==frames);
    assert(atomic_load(&platform.owner.transport.fault));
    if(fail_spi) assert(platform.owner.display.active && platform.owner.display.pending && platform.owner.spi.active);
  }
  printf("composition case %s passed\n",argv[1]);
  return 0;
}

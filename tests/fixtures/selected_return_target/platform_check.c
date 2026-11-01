/* SPDX-License-Identifier: GPL-3.0-only
 * Execute the actual candidate owner over typed HAL stubs and actual binding. */
#define LUNAR_SR_BINDING_NO_MAIN
#include "check.c"
/* The platform header's private exception declaration belongs to that TU. */
typedef struct { uint32_t notes; int enc_steps[7]; } platform_input_t;
platform_input_t fm1_in;
uint32_t fm1_lcd_timeouts;
static unsigned irq_init_calls,app_calls,lcd_calls,input_calls,audio_calls,enabled,stops;
static const char *mode;
extern void lunar_diagnostic_cstart(void);
extern const lunar_selected_return_t *lunar_sr_platform_test_state(void);
void isr_timer5(void) {} void isr_alnk0(void) {}
void fm1_timer5_ack(void) {} void fm1_input_tick(void) {}
void fm1_audio_ack_aux(uint8_t v) { (void)v; }
void fm1_audio_ack_half(void) {}
uint8_t fm1_audio_pending(void) { return 0; }
uint32_t fm1_audio_free_half(void) { return 0; }
uint32_t fm1_icfg(void) { return f.icfg; }
void fm1_icfg_set(uint32_t v) { f.icfg=v; }
void lunar_diagnostic_key(int k,int d) { (void)k;(void)d;assert(0); }
void lunar_diagnostic_knob(int e,int d) { (void)e;(void)d;assert(0); }
int lunar_diagnostic_render(int32_t *p,uint32_t n) { (void)p;(void)n;assert(0);return -1; }
int lunar_diagnostic_init(void) { ++app_calls;++f.now;return !strcmp(mode,"app-fail")?-1:0; }
uint32_t lunar_diagnostic_status(void) { assert(enabled);return 1; }
void lunar_sr_platform_irq_init(void) {
  assert(lunar_sr_platform_test_state()->backstop_armed);++irq_init_calls;
}
void lcd_init(void) { assert(app_calls==1);++lcd_calls; }
void lcd_fill(int x,int y,int w,int h,int c) {
  assert(x==0 && y==0 && w==240 && h==240 && c==0);++lcd_calls;
}
void lcd_sync(void) {
  ++lcd_calls;++f.now;
  if(!strcmp(mode,"lcd-fail")) ++fm1_lcd_timeouts;
}
void fm1_input_init(void) {
  if(fm1_lcd_timeouts)
    fprintf(stderr,"unexpected IO after LCD failure: feeds=%u\n",f.feed);
  assert(!fm1_lcd_timeouts);++input_calls;
}
void fm1_audio_init(int32_t *p,uint32_t n,void (*isr)(void),uint32_t prio) {
  assert(p && n==128 && isr==isr_alnk0 && prio==3);++audio_calls;
}
void fm1_timer5_start(void (*isr)(void),uint32_t prio) {
  assert(audio_calls==1 && isr==isr_timer5 && prio==4);++f.now;
}
void fm1_irq_enable_all(void) { assert(f.feed==3);enabled=1; }
void fm1_audio_stop(void) {
  assert(lunar_sr_platform_test_state()->state==LUNAR_SR_TERMINAL);++stops;
}
int main(int argc,char **argv) {
  assert(argc==2);mode=argv[1];fresh_target();f.allow_halt=1;
  if(!strcmp(mode,"unqualified")) memset(&target_q,0,sizeof target_q);
  if(!setjmp(stopped)) { lunar_diagnostic_cstart();assert(0); }
  const lunar_selected_return_t *p=lunar_sr_platform_test_state();
  assert(p->state==LUNAR_SR_TERMINAL && !(f.icfg&0x100));
  if(!strcmp(mode,"unqualified")) {
    assert(p->first_error==LUNAR_SR_QUALIFICATION && !f.transfers && !f.reads);
    assert(!irq_init_calls && !app_calls && !lcd_calls && !input_calls && !audio_calls && !enabled);
  } else {
    assert(p->first_error==LUNAR_SR_INIT && f.reset==1 && app_calls==1 && irq_init_calls==1);
    if(!strcmp(mode,"app-fail")) assert(!f.feed && !lcd_calls && !input_calls && !audio_calls);
    else if(!strcmp(mode,"lcd-fail")) {
      assert(f.feed==1 && lcd_calls==3 && fm1_lcd_timeouts==1);
      assert(!input_calls && !audio_calls && !enabled && !stops);
    } else {
      assert(!strcmp(mode,"main-fail"));
      assert(f.feed==3 && input_calls==1 && audio_calls==1 && enabled && stops==1);
    }
  }
  printf("actual selected platform passed %s\n",mode);
  return 0;
}

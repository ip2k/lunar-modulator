/* Negative ownership/fault probe only. Positive PCM uses the actual Trio app. MIT. */
#include "selected_interactive_owner.h"
#include "selected_interactive_app.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static lunar_selected_owner_t owner;
static lunar_input_t input[4];
static lunar_pcm_t pcm[2];
static unsigned applied,rendered,drawn,actions,app_fault,reenter,draw_fault,clock_fault,action_fault,live;
static uint16_t pixels[240*240];
int lunar_diagnostic_init(void) { return 0; }
void lunar_diagnostic_fault(uint32_t why) { if(!app_fault) app_fault=why; }
uint32_t lunar_diagnostic_status(void) { return app_fault; }
int lunar_selected_interactive_apply(void *ctx,const lunar_input_t *e) {
  (void)ctx; (void)e; ++applied;
  /* Simulate Timer publication overflow interrupting the first app callback. */
  lunar_transport_fault(&owner.transport,LUNAR_TRANSPORT_OVERFLOW); return 0;
}
int lunar_selected_interactive_render(void *ctx,int32_t *out) {
  (void)ctx; (void)out; ++rendered;
  if(reenter) assert(lunar_selected_owner_step(&owner)<0);
  return 0;
}
const uint16_t *lunar_selected_interactive_draw(void *ctx,uint32_t n) {
  (void)ctx; (void)n; ++drawn;
  if(clock_fault || action_fault) return pixels;
  if(draw_fault) {
    lunar_transport_fault(&owner.transport,LUNAR_TRANSPORT_OVERFLOW);
    return pixels;
  }
  return 0;
}
static void touch(void) {
  if(++actions==action_fault) lunar_transport_fault(&owner.transport,LUNAR_TRANSPORT_OVERFLOW);
}
static int pins(void *p,int a,int b) { (void)p;(void)a;(void)b; touch();return 0; }
static int op(void *p) { (void)p;touch();return 0; }
static int clear(void *p) { (void)p;touch();live=0;return 0; }
static int done(void *p) { (void)p;touch();return (int)live; }
static int launch(void *p,const uint8_t *s,size_t n) { (void)p;(void)s;(void)n;touch();live=1;return 1; }
static uint32_t ticks(void *p) {
  static unsigned calls; (void)p;
  if(clock_fault && ++calls==2) lunar_transport_fault(&owner.transport,LUNAR_TRANSPORT_OVERFLOW);
  return 0;
}
int main(int argc,char **argv) {
  reenter=argc>1 && !strcmp(argv[1],"reentry");
  draw_fault=argc>1 && !strcmp(argv[1],"draw-fault");
  clock_fault=argc>1 && !strcmp(argv[1],"clock-fault");
  if(argc>1 && !strncmp(argv[1],"action-",7)) action_fault=(unsigned)atoi(argv[1]+7);
  lunar_spi_model_ops_t ops={pins,clear,done,op,launch,ticks,0};
  assert(!lunar_selected_owner_init(&owner,input,4,pcm,2,0,4,1470,&ops,1000,100));
  if(action_fault) {
    assert(action_fault<=48 && lunar_selected_owner_step(&owner)==1);
    int r; unsigned n=0;
    do { r=lunar_selected_owner_step(&owner); assert(++n<60); } while(r>=0);
    assert(actions==action_fault && owner.spi.active && owner.spi.row==owner.display.row);
    assert(owner.display.active && owner.display.pending);
    for(unsigned i=0;i<3;++i) assert(lunar_selected_owner_step(&owner)<0 && actions==action_fault);
    printf("owner negative IRQ-in-SPI-action %u: retained row/frame passed\n",action_fault);
    return 0;
  }
  if(clock_fault) {
    assert(lunar_selected_owner_step(&owner)==1 && owner.spi.active && owner.display.pending);
    assert(lunar_selected_owner_step(&owner)<0 && !actions);
    assert(owner.spi.active && owner.spi.row==owner.display.row && owner.display.pending);
    for(unsigned i=0;i<3;++i) assert(lunar_selected_owner_step(&owner)<0 && !actions);
    puts("owner negative IRQ-in-SPI-clock: no bus action, retained row/frame passed");
    return 0;
  }
  if(!reenter && !draw_fault) {
    assert(lunar_transport_matrix(&owner.transport,1,18,1)==1);
    assert(lunar_transport_matrix(&owner.transport,2,18,0)==1);
  }
  assert(lunar_selected_owner_step(&owner)<0);
  assert(applied==((reenter||draw_fault)?0u:1u) && rendered==((reenter||draw_fault)?1u:0u));
  assert(drawn==(draw_fault?1u:0u) && !actions);
  if(draw_fault) {
    assert(!owner.transport.leased && owner.display.active && owner.display.pixels==pixels);
    assert(!owner.display.pending && !owner.spi.active && !owner.spi.row);
  } else assert(owner.transport.leased);
  unsigned first=atomic_load(&owner.transport.fault);
  assert(first==(reenter?LUNAR_TRANSPORT_APP:LUNAR_TRANSPORT_OVERFLOW));
  for(unsigned i=0;i<3;++i) {
    int32_t out[128];
    assert(lunar_selected_owner_step(&owner)<0);
    assert(lunar_transport_irq(&owner.transport,out)<0);
    for(unsigned j=0;j<128;++j) assert(!out[j]);
  }
  assert(drawn==(draw_fault?1u:0u) && !actions && atomic_load(&owner.transport.fault)==first);
  printf("owner negative %s: no subsequent apply/render/draw/SPI after fault passed\n",reenter?"reentry":draw_fault?"IRQ-in-draw":"IRQ-in-apply");
  return 0;
}

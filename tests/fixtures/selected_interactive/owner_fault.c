/* Negative ownership/fault probe only. Positive PCM uses the actual Trio app. MIT. */
#include "selected_interactive_owner.h"
#include "selected_interactive_app.h"
#include <assert.h>
#include <stdio.h>
static lunar_selected_owner_t owner;
static lunar_input_t input[4];
static lunar_pcm_t pcm[2];
static unsigned applied,rendered,drawn,actions,app_fault,reenter;
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
  (void)ctx; (void)n; ++drawn; return 0;
}
static int pins(void *p,int a,int b) { (void)p;(void)a;(void)b; ++actions;return 0; }
static int op(void *p) { (void)p;++actions;return 0; }
static int launch(void *p,const uint8_t *s,size_t n) { (void)p;(void)s;(void)n;++actions;return 1; }
static uint32_t ticks(void *p) { (void)p;return 0; }
int main(int argc,char **argv) {
  (void)argv; reenter=argc>1;
  lunar_spi_model_ops_t ops={pins,op,op,op,launch,ticks,0};
  assert(!lunar_selected_owner_init(&owner,input,4,pcm,2,0,4,1470,&ops,1000,100));
  if(!reenter) {
    assert(lunar_transport_matrix(&owner.transport,1,18,1)==1);
    assert(lunar_transport_matrix(&owner.transport,2,18,0)==1);
  }
  assert(lunar_selected_owner_step(&owner)<0);
  assert(applied==(reenter?0u:1u) && rendered==(reenter?1u:0u));
  assert(!drawn && !actions && owner.transport.leased);
  unsigned first=atomic_load(&owner.transport.fault);
  assert(first==(reenter?LUNAR_TRANSPORT_APP:LUNAR_TRANSPORT_OVERFLOW));
  for(unsigned i=0;i<3;++i) {
    int32_t out[128];
    assert(lunar_selected_owner_step(&owner)<0);
    assert(lunar_transport_irq(&owner.transport,out)<0);
    for(unsigned j=0;j<128;++j) assert(!out[j]);
  }
  assert(!drawn && !actions && atomic_load(&owner.transport.fault)==first);
  printf("owner negative %s: no subsequent apply/render/draw/SPI after fault passed\n",reenter?"reentry":"IRQ-in-apply");
  return 0;
}

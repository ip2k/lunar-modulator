/* SPDX-License-Identifier: MIT */
#include "selected_interactive_owner.h"
#include "selected_interactive_app.h"
#include "diagnostic_api.h"
static uint32_t fault(const lunar_transport_t *t) {
#ifdef LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION
  return lunar_pub_load(&t->fault);
#else
  return atomic_load_explicit(&t->fault,memory_order_acquire);
#endif
}
static int stop(lunar_selected_owner_t *o) {
  lunar_transport_fault(&o->transport,LUNAR_TRANSPORT_APP);
  lunar_diagnostic_fault(8);
  return -1;
}
static int apply(void *ctx,const lunar_input_t *event) {
  lunar_selected_owner_t *o=ctx;
  return fault(&o->transport) ? -1 : lunar_selected_interactive_apply(NULL,event);
}
static int render(void *ctx,int32_t *pcm) {
  lunar_selected_owner_t *o=ctx;
  return fault(&o->transport) ? -1 : lunar_selected_interactive_render(NULL,pcm);
}
int lunar_selected_owner_init(lunar_selected_owner_t *o,lunar_input_t *input,uint32_t ni,
    lunar_pcm_t *pcm,uint32_t np,uint32_t initial,uint32_t max_events,
    uint32_t min_frames,const lunar_spi_model_ops_t *ops,uint32_t ticks,uint32_t steps) {
  if(!o) return -1;
  if(o->initialized) return stop(o);
  o->initialized=1;
  if(!max_events || !min_frames ||
     lunar_transport_init(&o->transport,input,ni,pcm,np,initial) ||
     lunar_spi_model_init(&o->spi,ops,ticks,steps) ||
     lunar_display_init(&o->display,LUNAR_DISPLAY_HOST_MOCK,lunar_spi_model_submit,&o->spi) ||
     lunar_diagnostic_init()) return stop(o);
  o->max_events=max_events; o->min_draw_frames=min_frames;
  return 0;
}
static int service(lunar_selected_owner_t *o) {
  uint32_t ticket;
  int r, rendered;
  if(!o || !o->initialized) return -1;
  if(fault(&o->transport) || o->display.fault || o->spi.fault) return stop(o);
  /* Real PCM first. A full queue is backpressure, not a fault or a render. */
  rendered=lunar_transport_produce(&o->transport,o->max_events,
      apply,render,o);
  if(rendered<0 || fault(&o->transport) || lunar_diagnostic_status()) return stop(o);
  r=lunar_spi_model_step(&o->spi,&ticket);
  if(fault(&o->transport) || lunar_diagnostic_status()) return stop(o);
  if(r<0) { lunar_display_timeout(&o->display); return stop(o); }
  if(r==1 && lunar_display_complete(&o->display,ticket,1)<0) return stop(o);
  if(lunar_display_frame(&o->display,lunar_selected_interactive_draw,NULL,
                         o->min_draw_frames)<0) return stop(o);
  /* A Timer/audio fault may interrupt the app draw callback. Retain pixels
   * without submitting a new row after that fault becomes observable. */
  if(fault(&o->transport) || lunar_diagnostic_status()) return stop(o);
  if(lunar_display_pump(&o->display)<0) return stop(o);
  return rendered;
}
int lunar_selected_owner_step(lunar_selected_owner_t *o) {
  if(!o || !o->initialized) return -1;
  if(o->stepping) return stop(o);
  o->stepping=1;
  int r=service(o);
  o->stepping=0;
  return r;
}

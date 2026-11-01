/* SPDX-License-Identifier: MIT. Injected host facade, no hardware binding. */
#include "selected_interactive_owner.h"
static int stop(lunar_selected_platform_t *p) {
  lunar_transport_fault(&p->owner.transport,LUNAR_TRANSPORT_APP);
  return -1;
}
int lunar_selected_platform_start(lunar_selected_platform_t *p,
    const lunar_selected_platform_ops_t *ops,lunar_input_t *input,uint32_t ni,
    lunar_pcm_t *pcm,uint32_t np,uint32_t initial,uint32_t max_events,
    uint32_t min_frames,const lunar_spi_model_ops_t *spi,uint32_t ticks,uint32_t steps) {
  if(!p) return -1;
  if(p->initialized) return stop(p);
  p->initialized=1;
  if(!ops || !ops->scan_init || !ops->scan_tick || !ops->audio_start) return stop(p);
  p->ops=*ops;
  if(lunar_selected_owner_init(&p->owner,input,ni,pcm,np,initial,max_events,
                               min_frames,spi,ticks,steps) ||
     p->ops.scan_init(p->ops.ctx)) return stop(p);
  /* First hardware-consumed block is real app PCM, not a fabricated zero.
   * Draw/scan/audio ownership remains serialized until start returns. */
  if(lunar_selected_owner_step(&p->owner)!=1 || p->ops.audio_start(p->ops.ctx))
    return stop(p);
  p->started=1;
  return 0;
}
int lunar_selected_platform_main(lunar_selected_platform_t *p) {
  return p && p->started ? lunar_selected_owner_step(&p->owner) : -1;
}
void lunar_selected_platform_timer(lunar_selected_platform_t *p) {
  if(p && p->started) { ++p->scan; p->ops.scan_tick(p->ops.ctx); }
}
int lunar_selected_platform_audio(lunar_selected_platform_t *p,int32_t *out) {
  /* Even before admission/following a startup failure, output is zeroed. */
  return lunar_transport_irq(p && p->started ? &p->owner.transport : NULL,out);
}
void lunar_selected_platform_matrix(lunar_selected_platform_t *p,unsigned id,int down) {
  if(p && p->started) (void)lunar_transport_matrix(&p->owner.transport,p->scan,id,down);
}
void lunar_selected_platform_encoder(lunar_selected_platform_t *p,unsigned id,int delta) {
  if(p && p->started) (void)lunar_transport_encoder(&p->owner.transport,p->scan,id,delta);
}

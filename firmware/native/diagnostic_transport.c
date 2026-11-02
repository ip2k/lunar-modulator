/* SPDX-License-Identifier: MIT */
#include "diagnostic_transport.h"
#include <string.h>
#ifdef LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION
#define LOAD(p) lunar_pub_load(p)
#define STORE(p,v) lunar_pub_store((p),(v))
#else
#define LOAD(p) atomic_load_explicit((p), memory_order_acquire)
#define STORE(p,v) atomic_store_explicit((p),(v),memory_order_release)
#endif
void lunar_transport_fault(lunar_transport_t *t, uint32_t reason) {
#ifdef LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION
  if(t) lunar_pub_fault_first(&t->fault,reason ? reason : LUNAR_TRANSPORT_APP);
#else
  uint32_t zero=0;
  if(t) atomic_compare_exchange_strong_explicit(&t->fault,&zero,
      reason ? reason : LUNAR_TRANSPORT_APP,memory_order_acq_rel,memory_order_acquire);
#endif
}
static int bad(lunar_transport_t *t, uint32_t reason) {
  lunar_transport_fault(t,reason); return -1;
}
static int power2(uint32_t n) { return n && n<=65536 && !(n&(n-1)); }
int lunar_transport_init(lunar_transport_t *t,lunar_input_t *input,uint32_t ni,
                         lunar_pcm_t *pcm,uint32_t np,uint32_t initial) {
  if(!t) return -1;
  if(t->initialized || LOAD(&t->fault)) return bad(t,LUNAR_TRANSPORT_CONFIG);
  t->initialized=1;
  if(!input || !pcm || !power2(ni) || !power2(np))
    return bad(t,LUNAR_TRANSPORT_CONFIG);
  t->input=input; t->input_capacity=ni; t->pcm=pcm; t->pcm_capacity=np;
  STORE(&t->input_head,initial); STORE(&t->input_tail,initial);
  STORE(&t->pcm_head,initial); STORE(&t->pcm_tail,initial);
  return 0;
}
static int enqueue(lunar_transport_t *t,lunar_input_t e) {
  if(!t || !t->initialized || LOAD(&t->fault)) return -1;
  uint32_t h=LOAD(&t->input_head), tail=LOAD(&t->input_tail);
  if(h-tail>=t->input_capacity) return bad(t,LUNAR_TRANSPORT_OVERFLOW);
  t->input[h&(t->input_capacity-1)]=e;
  STORE(&t->input_head,h+1); return 1;
}
int lunar_transport_matrix(lunar_transport_t *t,uint32_t scan,unsigned id,int down) {
  if(id>40 || (down!=0 && down!=1)) return bad(t,LUNAR_TRANSPORT_INPUT);
  return enqueue(t,(lunar_input_t){scan,id<14?LUNAR_INPUT_BUTTON:LUNAR_INPUT_KEY,
                                  id<14?id:id-14,down});
}
int lunar_transport_encoder(lunar_transport_t *t,uint32_t scan,unsigned id,int delta) {
  if(id>6 || !delta || delta< -64 || delta>64) return bad(t,LUNAR_TRANSPORT_INPUT);
  return enqueue(t,(lunar_input_t){scan,LUNAR_INPUT_ENCODER,id,delta});
}
int lunar_transport_reserve(lunar_transport_t *t,int32_t **pcm,uint32_t *ticket) {
  if(!t || !t->initialized || LOAD(&t->fault)) return -1;
  if(!pcm || !ticket || t->leased) return bad(t,LUNAR_TRANSPORT_LEASE);
  uint32_t h=LOAD(&t->pcm_head),tail=LOAD(&t->pcm_tail);
  if(h-tail>=t->pcm_capacity) return 0;
  t->leased=1; t->ticket=h;
  *ticket=h; *pcm=t->pcm[h&(t->pcm_capacity-1)].word; return 1;
}
int lunar_transport_publish(lunar_transport_t *t,uint32_t ticket) {
  if(!t || !t->initialized || LOAD(&t->fault)) return -1;
  if(!t->leased || ticket!=t->ticket) return bad(t,LUNAR_TRANSPORT_LEASE);
  STORE(&t->pcm_head,ticket+1); t->leased=0; return 1;
}
int lunar_transport_produce(lunar_transport_t *t,uint32_t max_events,
                            lunar_input_apply_fn apply,lunar_pcm_render_fn render,void *ctx) {
  if(!apply || !render || !max_events) return bad(t,LUNAR_TRANSPORT_CONFIG);
  int32_t *pcm; uint32_t ticket;
  int r=lunar_transport_reserve(t,&pcm,&ticket);
  if(r!=1) return r;
  /* Snapshot a bounded prefix. New input waits for the next block. */
  uint32_t tail=LOAD(&t->input_tail), head=LOAD(&t->input_head);
  for(uint32_t n=0;tail!=head && n<max_events;++n,++tail) {
    lunar_input_t e=t->input[tail&(t->input_capacity-1)];
    if(apply(ctx,&e)) return bad(t,LUNAR_TRANSPORT_APP);
    STORE(&t->input_tail,tail+1);
  }
  if(LOAD(&t->fault) || render(ctx,pcm)) return bad(t,LUNAR_TRANSPORT_APP);
  return lunar_transport_publish(t,ticket);
}
int lunar_transport_irq(lunar_transport_t *t,int32_t out[LUNAR_PCM_WORDS]) {
  if(!out) return bad(t,LUNAR_TRANSPORT_CONFIG);
  if(!t || !t->initialized || LOAD(&t->fault)) {
    memset(out,0,sizeof(lunar_pcm_t)); return -1;
  }
  uint32_t tail=LOAD(&t->pcm_tail),head=LOAD(&t->pcm_head);
  if(tail==head) {
#ifdef LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION
    lunar_pub_increment(&t->underruns);
#else
    atomic_fetch_add_explicit(&t->underruns,1,memory_order_relaxed);
#endif
    memset(out,0,sizeof(lunar_pcm_t)); return 0;
  }
  memcpy(out,t->pcm[tail&(t->pcm_capacity-1)].word,sizeof(lunar_pcm_t));
  /* A fault observed during copy silences this output too. The target must
   * separately admit interrupt priority, publication codegen and latency. */
  int failed=LOAD(&t->fault)!=0;
  if(failed) memset(out,0,sizeof(lunar_pcm_t));
  STORE(&t->pcm_tail,tail+1); return failed?-1:1;
}

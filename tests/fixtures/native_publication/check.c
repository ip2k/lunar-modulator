/* SPDX-License-Identifier: MIT. Single-thread directed IRQ model, not hardware. */
#include "diagnostic_transport.h"
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
#include "diagnostic_publication_pi32v2.h"
#endif
#include <assert.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

static uint64_t digest = 1469598103934665603ull;
static void hash(const void *p, size_t n) {
  const unsigned char *b=p;
  for(size_t i=0;i<n;++i) digest=(digest^b[i])*1099511628211ull;
}
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
static uint32_t icfg=0xabc00100u;
static unsigned event, inject_at, pending, delivered, priority, in_irq;
static unsigned primitive_cases, queue_cases;
static void (*interrupt_action)(void);
static void boundary(void) {
  if(in_irq) return;
  ++event;
  if(event==inject_at) { pending=1; inject_at=0; }
  if(pending && (icfg&0x100u)) {
    uint32_t before=icfg;
    pending=0; ++delivered; in_irq=1;
    interrupt_action();
    assert(icfg==before); in_irq=0;
  }
}
uint32_t lunar_pub_test_icfg_read(void) {
  boundary(); uint32_t v=icfg; boundary(); return v;
}
void lunar_pub_test_icfg_write(uint32_t v) {
  boundary(); icfg=v; boundary();
}
void lunar_pub_test_barrier(void) { boundary(); boundary(); }
uint32_t lunar_pub_test_word_read(const uint32_t *p) {
  assert(!(icfg&0x100u)); boundary(); uint32_t v=*p; boundary(); return v;
}
void lunar_pub_test_word_write(uint32_t *p,uint32_t v) {
  assert(!(icfg&0x100u)); boundary(); *p=v; boundary();
}
#define GET(p) (*(p)) /* test inspection only, no concurrent model action */
#else
#define GET(p) atomic_load(p)
#endif

static unsigned copy_fault;
static lunar_transport_t *copy_queue;
static void require_unmasked(void) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  assert(icfg&0x100u);
#endif
}
void *publication_copy(void *out,const void *in,size_t n) {
  require_unmasked();
  unsigned char *d=out; const unsigned char *s=in;
  for(size_t i=0;i<n;++i) {
    d[i]=s[i];
    if(copy_fault && i==n/2) {
      copy_fault=0; lunar_transport_fault(copy_queue,73);
    }
  }
  return out;
}
void *publication_zero(void *out,int value,size_t n) {
  require_unmasked(); unsigned char *d=out;
  for(size_t i=0;i<n;++i) d[i]=(unsigned char)value;
  return out;
}
static void zeros(const int32_t *out) {
  for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(!out[i]);
}
static unsigned applied, rendered;
static uint32_t scans[8];
static int apply(void *ctx,const lunar_input_t *e) {
  (void)ctx; require_unmasked(); assert(applied<8); scans[applied++]=e->scan; return 0;
}
static int render(void *ctx,int32_t *pcm) {
  (void)ctx; require_unmasked();
  for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) pcm[i]=(int32_t)(++rendered);
  return 0;
}
static int fail(void *ctx,int32_t *pcm) { (void)ctx;(void)pcm; require_unmasked(); return -1; }
static void guards(void) {
  lunar_transport_t q[12]={0}; lunar_input_t in[12][2]={0}; lunar_pcm_t blocks[12][2]={0};
  int32_t out[LUNAR_PCM_WORDS],*slot; uint32_t ticket;
  assert(lunar_transport_init(&q[0],in[0],3,blocks[0],2,0)==-1);
  assert(lunar_transport_irq(&q[0],out)==-1); zeros(out);
  for(unsigned k=1;k<12;++k) assert(!lunar_transport_init(&q[k],in[k],2,blocks[k],k==1?1:2,UINT32_MAX));
  assert(!lunar_transport_irq(&q[1],out)); zeros(out);
  assert(GET(&q[1].underruns)==1);
  for(unsigned n=0;n<9;++n) {
    assert(lunar_transport_reserve(&q[1],&slot,&ticket)==1);
    for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) slot[i]=(int32_t)(n*128+i);
    assert(!lunar_transport_irq(&q[1],out)); zeros(out);
    assert(lunar_transport_publish(&q[1],ticket)==1);
    assert(!lunar_transport_reserve(&q[1],&slot,&ticket));
    assert(lunar_transport_irq(&q[1],out)==1);
    for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(out[i]==(int32_t)(n*128+i));
    hash(out,sizeof out);
  }
  assert(lunar_transport_matrix(&q[2],9,3,1)==1);
  assert(lunar_transport_encoder(&q[2],2,6,-1)==1);
  applied=rendered=0;
  assert(lunar_transport_produce(&q[2],1,apply,render,0)==1 && applied==1 && scans[0]==9);
  assert(lunar_transport_irq(&q[2],out)==1); hash(out,sizeof out);
  assert(lunar_transport_produce(&q[2],1,apply,render,0)==1 && applied==2 && scans[1]==2);
  assert(lunar_transport_irq(&q[2],out)==1); hash(out,sizeof out);
  assert(lunar_transport_reserve(&q[3],&slot,&ticket)==1);
  assert(lunar_transport_reserve(&q[3],&slot,&ticket)==-1 && q[3].leased);
  assert(lunar_transport_reserve(&q[4],&slot,&ticket)==1);
  assert(lunar_transport_publish(&q[4],ticket+1)==-1 && q[4].leased);
  assert(lunar_transport_publish(&q[5],0)==-1);
  assert(lunar_transport_matrix(&q[6],0,14,1)==1);
  assert(lunar_transport_matrix(&q[6],0,14,0)==1);
  assert(lunar_transport_matrix(&q[6],0,15,1)==-1 && GET(&q[6].fault)==LUNAR_TRANSPORT_OVERFLOW);
  assert(lunar_transport_irq(&q[6],out)==-1); zeros(out);
  assert(lunar_transport_encoder(&q[7],0,7,1)==-1);
  assert(lunar_transport_produce(&q[8],2,apply,fail,0)==-1 && q[8].leased);
  assert(lunar_transport_irq(&q[8],out)==-1); zeros(out);
  assert(lunar_transport_reserve(&q[9],&slot,&ticket)==1);
  for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) slot[i]=123;
  assert(lunar_transport_publish(&q[9],ticket)==1);
  copy_queue=&q[9]; copy_fault=1;
  assert(lunar_transport_irq(&q[9],out)==-1); zeros(out);
  assert(GET(&q[9].fault)==73 && !copy_fault);
  lunar_transport_fault(&q[9],99); assert(GET(&q[9].fault)==73);
  assert(lunar_transport_reserve(&q[10],&slot,&ticket)==1);
  lunar_transport_fault(&q[10],0);
  assert(lunar_transport_publish(&q[10],ticket)==-1 && q[10].leased);
  assert(lunar_transport_irq(&q[10],out)==-1); zeros(out);
  for(unsigned k=0;k<12;++k) { uint32_t f=GET(&q[k].fault); hash(&f,sizeof f); }
}

#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
static lunar_publication_word_t scalar;
static uint32_t observed;
static unsigned operation;
static void interrupt_scalar(void) {
  require_unmasked();
  if(operation==0 || operation==2) lunar_pub_fault_first(&scalar,77);
  else observed=lunar_pub_load(&scalar);
}
static void scalar_operation(void) {
  switch(operation) {
    case 0: observed=lunar_pub_load(&scalar); break;
    case 1: lunar_pub_store(&scalar,42); break;
    case 2: lunar_pub_fault_first(&scalar,42); break;
    case 3: lunar_pub_increment(&scalar); break;
    default: assert(0);
  }
}
static void primitive_boundaries(void) {
  for(operation=0;operation<4;++operation) {
    scalar=0; event=inject_at=pending=delivered=0; scalar_operation();
    unsigned count=event;
    assert(count>=12 && count<=16);
    for(unsigned enabled=0;enabled<2;++enabled) for(unsigned step=1;step<=count;++step) {
      ++primitive_cases;
      scalar=0; observed=999; event=0; inject_at=step; pending=delivered=0;
      uint32_t original=0xdead0204u | (enabled?0x100u:0);
      icfg=original; interrupt_action=interrupt_scalar;
      scalar_operation(); assert(icfg==original);
      if(enabled) {
        assert(delivered==1 && !pending);
        if(operation==0) assert(observed==0 || observed==77);
        if(operation==1) assert(scalar==42 && (observed==0 || observed==42));
        if(operation==2) assert(scalar==42 || scalar==77);
        if(operation==3) assert(scalar==1 && (observed==0 || observed==1));
      } else {
        assert(!delivered && pending);
        icfg|=0x100u; boundary(); assert(delivered==1 && !pending);
      }
      icfg=0xabc00100u;
    }
  }
  scalar=UINT32_MAX; lunar_pub_increment(&scalar); assert(!scalar);
}
static lunar_transport_t *interrupt_queue;
static unsigned interrupt_kind;
static int32_t irq_out[LUNAR_PCM_WORDS];
static int irq_result;
static void interrupt_queue_action(void) {
  require_unmasked();
  if(interrupt_kind==0) assert(lunar_transport_matrix(interrupt_queue,2,14,0)==1);
  else { ++priority; irq_result=lunar_transport_irq(interrupt_queue,irq_out); --priority; }
}
static unsigned run_queue_boundary(unsigned step,unsigned kind) {
  lunar_transport_t q={0}; lunar_input_t in[4]={0}; lunar_pcm_t pcm[2]={0};
  int32_t out[LUNAR_PCM_WORDS];
  event=inject_at=pending=delivered=0; interrupt_queue=&q;
  assert(!lunar_transport_init(&q,in,4,pcm,2,UINT32_MAX));
  assert(lunar_transport_matrix(&q,1,14,1)==1);
  applied=rendered=0; event=0; inject_at=step; interrupt_kind=kind;
  interrupt_action=interrupt_queue_action; irq_result=-9;
  assert(lunar_transport_produce(&q,4,apply,render,0)==1);
  unsigned count=event; inject_at=0;
  assert(!pending && GET(&q.fault)==0);
  if(step) assert(delivered==1);
  if(kind==0) {
    assert(applied==1 || applied==2); assert(scans[0]==1);
    assert(lunar_transport_irq(&q,out)==1);
    assert(lunar_transport_produce(&q,4,apply,render,0)==1);
    assert(applied==(step?2u:1u));
    if(step) assert(scans[1]==2);
    assert(lunar_transport_irq(&q,out)==1);
  } else {
    if(step && irq_result==1) {
      for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(irq_out[i]==(int32_t)(i+1));
      assert(!lunar_transport_irq(&q,out)); zeros(out);
    } else {
      if(step) { assert(irq_result==0); zeros(irq_out); }
      assert(lunar_transport_irq(&q,out)==1);
      for(unsigned i=0;i<LUNAR_PCM_WORDS;++i) assert(out[i]==(int32_t)(i+1));
    }
  }
  assert(icfg==0xabc00100u); return count;
}
static void queue_boundaries(void) {
  for(unsigned kind=0;kind<2;++kind) {
    unsigned count=run_queue_boundary(0,kind);
    for(unsigned step=1;step<=count;++step) { ++queue_cases; run_queue_boundary(step,kind); }
  }
}
#endif
int main(void) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  primitive_boundaries(); queue_boundaries();
  printf("directed primitive cases %u; queue cases %u\n",primitive_cases,queue_cases);
  event=inject_at=pending=delivered=0;
#endif
  guards();
  printf("{\"digest\":\"%016llx\",\"transport\":%zu,\"input\":%zu,\"pcm\":%zu,\"alignment\":%zu,\"offsets\":[%zu,%zu,%zu,%zu,%zu,%zu]}\n",
    (unsigned long long)digest,sizeof(lunar_transport_t),sizeof(lunar_input_t),sizeof(lunar_pcm_t),
    _Alignof(lunar_transport_t),
    offsetof(lunar_transport_t,input_head),offsetof(lunar_transport_t,input_tail),
    offsetof(lunar_transport_t,pcm_head),offsetof(lunar_transport_t,pcm_tail),
    offsetof(lunar_transport_t,fault),offsetof(lunar_transport_t,underruns));
  return 0;
}

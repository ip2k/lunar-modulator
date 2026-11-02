/* SPDX-License-Identifier: MIT.
 * Shared protocol implementation. Include exactly once from an explicit port
 * translation unit: no SDK includes, hardware defaults or OS dependencies.
 * Keep state transitions and callback ordering common to target/host adapters. */
#include "renderer_pipeline_core.h"
#include "renderer_pipeline_port.h"
#include <string.h>
#define LIFETIME_MS LUNAR_PIPELINE_LIFETIME_MS
#define FREE 0u
#define PRODUCING 1u
#define SEALED 2u
#define CONSUMING 3u
#define DONE 4u
#define RESERVED 1u
#define READY 2u
#define LEASED 3u
/* Internal failures are low numbers; caller guard codes may carry source lines. */
enum { E_CORE=1,E_API,E_TAG,E_BIND,E_CALLBACK,E_TIMEOUT,E_LIFETIME,E_CREATE,E_FINISH,E_STATE };
typedef struct {
    lunar_pipeline_word_t state;
    uint32_t tag;
    void *work;
    lunar_pipeline_completion_t completion;
} Work;
typedef struct {
    lunar_pipeline_word_t state;
    uint32_t tag;
    lunar_pipeline_result_t result;
    int16_t pcm[LUNAR_PIPELINE_OUTPUT_SAMPLES];
} Output;
static Work works[LUNAR_PIPELINE_WORK_SLOTS] __attribute__((aligned(64)));
static Output outputs[LUNAR_PIPELINE_OUTPUT_SLOTS] __attribute__((aligned(64)));
static struct {
    lunar_pipeline_word_t ready,stop,exited,bound;
    /* Separate writers: CPU0 error0, CPU1 error1. First error per core wins. */
    lunar_pipeline_word_t error0,error1;
    lunar_pipeline_word_t produced,consumed,harvested,output_retired;
    lunar_pipeline_word_t stack_unused;
    uint32_t invoked,started_ms,parent_blocks,parent_wrong;
    uint32_t (*clock)(void);
    lunar_pipeline_consume_fn consume;
    lunar_pipeline_retire_fn retire;
} s;
static void fence(void) { port_fence(); }
uint32_t lunar_pipeline_error(void) {
    uint32_t a=s.error0,b=s.error1; fence(); return a?a:b;
}
void lunar_pipeline_refuse(uint32_t code) {
    if(!code)code=E_API;
    if(port_cpu()==1) { if(!s.error1){s.error1=code;} }
    else { unsigned flags=port_irq_save(); if(!s.error0){s.error0=code;} port_irq_restore(flags); }
    fence();port_wake_abort();
}
void lunar_pipeline_fail_park(uint32_t code) {
    lunar_pipeline_refuse(code);
    /* Deliberately retain current slot, stacks, clock and arenas. The other
     * task sees poison; no callback continuation or unsafe cleanup occurs. */
    for(;;)port_delay(1);
}
static int bad(uint32_t code) { lunar_pipeline_refuse(code); return -1; }
static int cpu0(void) {
    if(port_cpu()!=0)return bad(E_CORE);
    if(lunar_pipeline_error())return -1;
    return 1;
}
int lunar_pipeline_wait_check(uint32_t *ticket) {
    uint32_t now;
    if(!ticket || !s.clock)return bad(E_API);
    if(lunar_pipeline_error())return -1;
    now=port_ms();
    if(lunar_pipeline_error())return -1;
    if((uint32_t)(now-s.started_ms)>=LIFETIME_MS)return bad(E_LIFETIME);
    now=s.clock();
    if(lunar_pipeline_error())return -1;
    /* Store encoded first timestamp; zero is the unstarted sentinel.
     * At the one value where now+1 wraps, start at now-1 (one tick earlier). */
    if(!*ticket) { *ticket=now+1u; if(!*ticket)*ticket=0xffffffffu; }
    if((uint32_t)(now-(*ticket-1u))>=LUNAR_PIPELINE_PROTOCOL_TICKS)return bad(E_TIMEOUT);
    return 1;
}
int lunar_pipeline_bind(void *a,void *b,lunar_pipeline_consume_fn consume,lunar_pipeline_retire_fn retire) {
    if(cpu0()<0)return -1;
    if(!s.invoked || !s.ready || s.exited || s.bound || !a || !b || a==b ||
       !consume || !retire)return bad(E_BIND);
    works[0].work=a;works[1].work=b;s.consume=consume;s.retire=retire;
    fence();s.bound=1;fence();port_signal(1,0);return lunar_pipeline_error()?-1:1;
}
int lunar_pipeline_reserve_work(uint32_t tag,void **work) {
    Work *w;
    if(cpu0()<0)return -1;
    if(!work)return bad(E_API);
    *work=0;
    if(!s.bound || s.stop || s.exited || tag!=s.produced || tag==0xffffffffu)return bad(E_TAG);
    w=&works[tag%LUNAR_PIPELINE_WORK_SLOTS];
    if(w->state!=FREE) {
        /* Calling reserve twice for an already leased producer slot is misuse. */
        if(w->state==PRODUCING)return bad(E_STATE);
        return 0;
    }
    fence();w->tag=tag;memset(&w->completion,0,sizeof w->completion);
    w->completion.tag=tag;w->state=PRODUCING;*work=w->work;return 1;
}
int lunar_pipeline_publish(uint32_t tag,uint32_t p_start,uint32_t p_end) {
    Work *w;
    if(cpu0()<0)return -1;
    if(!s.bound || s.stop || tag!=s.produced || tag==0xffffffffu)return bad(E_TAG);
    w=&works[tag%LUNAR_PIPELINE_WORK_SLOTS];
    if(w->state!=PRODUCING || w->tag!=tag)return bad(E_STATE);
    if((uint32_t)(p_end-p_start)>=0x80000000u)return bad(E_API);
    w->completion.p_start=p_start;w->completion.p_end=p_end;
    w->completion.p_ticks=p_end-p_start;w->completion.published=s.clock();
    if(lunar_pipeline_error())return -1;
    /* Count before publication; count is diagnostics, not the worker gate. */
    s.produced=tag+1u;fence();w->state=SEALED;fence();port_signal(1,0);return lunar_pipeline_error()?-1:1;
}
int lunar_pipeline_harvest(lunar_pipeline_completion_t *completion) {
    uint32_t tag;Work *w;
    if(cpu0()<0)return -1;
    if(!completion || !s.bound)return bad(E_API);
    tag=s.harvested;
    if(tag==s.produced)return 0;
    w=&works[tag%LUNAR_PIPELINE_WORK_SLOTS];
    if(w->state!=DONE)return 0;
    fence();if(w->tag!=tag || w->completion.tag!=tag)return bad(E_TAG);
    *completion=w->completion;
    if(!s.retire(w->work) || lunar_pipeline_error())return bad(E_CALLBACK);
    s.harvested=tag+1u;fence();w->state=FREE;return 1;
}
int lunar_pipeline_output_acquire(uint32_t tag,const int16_t **pcm,const lunar_pipeline_result_t **result) {
    Output *o;
    if(cpu0()<0)return -1;
    if(!pcm || !result)return bad(E_API);
    *pcm=0;*result=0;
    if(!s.bound || tag!=s.output_retired || tag==0xffffffffu)return bad(E_TAG);
    o=&outputs[tag%LUNAR_PIPELINE_OUTPUT_SLOTS];
    if(o->state==LEASED)return bad(E_STATE);
    if(o->state!=READY)return 0;
    fence();if(o->tag!=tag || o->result.tag!=tag)return bad(E_TAG);
    o->state=LEASED;*pcm=o->pcm;*result=&o->result;return 1;
}
int lunar_pipeline_output_retire(uint32_t tag) {
    Output *o;
    if(cpu0()<0)return -1;
    if(!s.bound || tag!=s.output_retired)return bad(E_TAG);
    o=&outputs[tag%LUNAR_PIPELINE_OUTPUT_SLOTS];
    if(o->state!=LEASED || o->tag!=tag)return bad(E_STATE);
    s.output_retired=tag+1u;fence();o->state=FREE;fence();port_signal(1,2);return lunar_pipeline_error()?-1:1;
}
static int worker_step(void) {
    uint32_t tag=s.consumed;Work *w;Output *o;
    if(lunar_pipeline_error())return -1;
    if(!s.bound)return 0;
    fence();w=&works[tag%LUNAR_PIPELINE_WORK_SLOTS];
    if(w->state!=SEALED)return 0;
    fence();if(w->tag!=tag)return bad(E_TAG);
    o=&outputs[tag%LUNAR_PIPELINE_OUTPUT_SLOTS];
    if(o->state!=FREE)return 0;
    fence();o->state=RESERVED;o->tag=tag;
    memset(&o->result,0,sizeof o->result);o->result.tag=tag;
    w->state=CONSUMING;w->completion.c_start=s.clock();
    w->completion.ready_wait_ticks=w->completion.c_start-w->completion.published;
    /* Clock hooks may synchronously poison. Retain both slots and the work
     * context, and never admit a user callback after observing that poison. */
    if(lunar_pipeline_error())return -1;
    int consumed_ok=s.consume(w->work,tag,o->pcm,&o->result);
    if(!consumed_ok || lunar_pipeline_error())return bad(E_CALLBACK);
    if(o->result.tag!=tag)return bad(E_TAG);
    w->completion.result=o->result;w->completion.c_end=s.clock();
    if(lunar_pipeline_error())return -1;
    w->completion.c_ticks=w->completion.c_end-w->completion.c_start;
    if(w->completion.c_ticks>=0x80000000u)return bad(E_API);
    /* No work/output field access after its respective release. */
    fence();o->state=READY;s.consumed=tag+1u;fence();w->state=DONE;fence();port_signal(0,1);
    return 1;
}
static void worker(void *unused) {
    uint32_t blocked=0;(void)unused;
    if(port_cpu()!=1){lunar_pipeline_refuse(E_CORE);goto done;}
    fence();s.ready=1;
    for(;;) {
        int result;uint32_t now;
        if(port_wake_drain(1)<0)break;
        if(lunar_pipeline_error())break;
        if(s.stop)break;
        now=port_ms();
        if(lunar_pipeline_error())break;
        if((uint32_t)(now-s.started_ms)>=LIFETIME_MS){lunar_pipeline_refuse(E_LIFETIME);break;}
        result=worker_step();
        if(result<0)break;
        /* Bound output-full blockage only when an actual sealed job waits.
         * Normal idle before binding or between jobs uses finite lifetime. */
        if(!result && s.bound && works[s.consumed%LUNAR_PIPELINE_WORK_SLOTS].state==SEALED) {
            if(lunar_pipeline_wait_check(&blocked)<0)break;
        } else blocked=0;
        if(!result) {
            fence();
            if(lunar_pipeline_error() || s.stop)continue;
            if(s.bound && works[s.consumed%LUNAR_PIPELINE_WORK_SLOTS].state==SEALED &&
               outputs[s.consumed%LUNAR_PIPELINE_OUTPUT_SLOTS].state==FREE)continue;
            if(port_wake_wait(1)<0)break;
        }
    }
done:
    s.stack_unused=port_stack_unused();
    fence();s.exited=1;
    for(;;)port_delay(100);
}

LUNAR_PIPELINE_CORE_COLD
int lunar_pipeline_core_start(uint32_t (*clock)(void)) {
    uint32_t first;int status;
    if(s.invoked || port_cpu()!=0 || !clock){lunar_pipeline_refuse(E_API);return 0;}
    s.invoked=1;s.clock=clock;s.started_ms=port_ms();fence();
    if(lunar_pipeline_error())return 0;
    if(!port_wake_init(clock)){lunar_pipeline_refuse(10711);return 0;}
    status=port_launch(worker,NULL);
    if(status){lunar_pipeline_refuse(E_CREATE);return 0;}
    first=port_ms();
    while(!s.ready && !s.exited && !lunar_pipeline_error() &&
          (uint32_t)(port_ms()-first)<1000u)port_delay(1);
    fence();if(!s.ready || s.exited || lunar_pipeline_error()){lunar_pipeline_refuse(E_TIMEOUT);s.stop=1;return 0;}
    return 1;
}
void lunar_pipeline_core_parent_block(void) {
    ++s.parent_blocks;
    if(port_cpu()!=0){++s.parent_wrong;lunar_pipeline_refuse(E_CORE);}
}
int lunar_pipeline_core_finish(void) {
    uint32_t first;
    if(port_cpu()!=0){lunar_pipeline_refuse(E_CORE);return 0;}
    fence();
    if(!s.bound || !s.produced || s.produced!=s.consumed || s.produced!=s.harvested ||
       s.produced!=s.output_retired || lunar_pipeline_error()) {
        /* Poison admission. Never falsely drain/free unfinished work. */
        lunar_pipeline_refuse(E_FINISH);return 0;
    }
    s.stop=1;fence();port_wake_abort();first=port_ms();
    while(!s.exited && !lunar_pipeline_error() &&
          (uint32_t)(port_ms()-first)<1000u)port_delay(1);
    if(!s.exited || lunar_pipeline_error()){lunar_pipeline_refuse(E_TIMEOUT);return 0;}
    fence();return 1;
}
unsigned lunar_pipeline_ready_outputs(void) { unsigned n=0; for(unsigned i=0;i<LUNAR_PIPELINE_OUTPUT_SLOTS;++i) if(outputs[i].state==READY) ++n; fence(); return n; }

void lunar_pipeline_core_stats(lunar_pipeline_stats_t *out) {
    out->produced=s.produced;out->consumed=s.consumed;
    out->harvested=s.harvested;out->output_retired=s.output_retired;
    out->error0=s.error0;out->error1=s.error1;
    out->parent_blocks=s.parent_blocks;out->parent_wrong=s.parent_wrong;
    out->exited=s.exited;out->stack_unused=s.stack_unused;fence();
}
size_t lunar_pipeline_core_bytes(void) { return sizeof works+sizeof outputs+sizeof s; }

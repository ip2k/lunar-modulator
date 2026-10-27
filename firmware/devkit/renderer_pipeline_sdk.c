/* SPDX-License-Identifier: MIT. Finite two-work-slot / eight-output pi32v2 SDK transport.
 * Target protocol follows existing queue volatile-word/csync convention.
 * NOT a portable C threaded implementation; host tests need an atomic shim. */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "renderer_pipeline_sdk.h"
#include <string.h>
#if defined(LUNAR_DEVKIT_FM6_SDK) || defined(LUNAR_DEVKIT_FM6_PAIR) || defined(LUNAR_DEVKIT_QUEUE_SDK)
#error Renderer pipeline must not nest another SDK worker
#endif
#define STACK_WORDS 1536u
#define WORKER_PRIORITY 16u
#define LIFETIME_MS (35u*60u*1000u)
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
static unsigned char worker_memory[sizeof(StaticTask_t)+STACK_WORDS*4u]
    __attribute__((aligned(4)));
typedef struct {
    volatile uint32_t state;
    uint32_t tag;
    void *work;
    lunar_pipeline_completion_t completion;
} Work;
typedef struct {
    volatile uint32_t state;
    uint32_t tag;
    lunar_pipeline_result_t result;
    int16_t pcm[LUNAR_PIPELINE_OUTPUT_SAMPLES];
} Output;
static Work works[LUNAR_PIPELINE_WORK_SLOTS] __attribute__((aligned(64)));
static Output outputs[LUNAR_PIPELINE_OUTPUT_SLOTS] __attribute__((aligned(64)));
static struct {
    volatile uint32_t ready,stop,exited,bound;
    /* Separate writers: CPU0 error0, CPU1 error1. First error per core wins. */
    volatile uint32_t error0,error1;
    volatile uint32_t produced,consumed,harvested,output_retired;
    volatile uint32_t stack_unused;
    uint32_t invoked,started_ms,parent_blocks,parent_wrong;
    uint32_t (*clock)(void);
    lunar_pipeline_consume_fn consume;
    lunar_pipeline_retire_fn retire;
} s;
#pragma code_seg(".volatile_ram_code")

/* V107: counted wake tokens; authoritative queue states remain separate. */
static OS_SEM pipeline_sem[2];
static volatile uint32_t pipeline_ready;
static volatile uint32_t pipeline_waiting[2]; /* Each target task writes its own flag. */
static uint32_t (*pipeline_clock)(void);
static struct {
    volatile uint32_t seq, tick;
} pipeline_source[4]; /* Single writers: publish, DONE, output-retire, DAC-drain. */
static struct {
    uint32_t drains, accepted, waits, timeouts, pend_max, resume_max;
} pipeline_stats[2]; /* Each task writes only its own row; read after worker exit. */
static volatile int pipeline_sem_status[2];
static void pipeline_barrier(void) { __asm__ volatile("csync;" ::: "memory"); }
static int pipeline_wake_init(uint32_t (*clock)(void)) {
    pipeline_clock=clock;
    if(!clock || os_sem_create(&pipeline_sem[0],0) || os_sem_create(&pipeline_sem[1],0))return 0;
    pipeline_barrier();pipeline_ready=1;return 1;
}
/* Error-only wake: no recursive refusal if a semaphore itself has failed. */
static void pipeline_wake_abort(void) {
    if(!pipeline_ready)return;
    pipeline_barrier();(void)os_sem_post(&pipeline_sem[0]);(void)os_sem_post(&pipeline_sem[1]);
    vPortYield();
}
static void pipeline_signal(unsigned cpu,unsigned source) {
    if(!pipeline_ready)return;
    if(cpu>1 || source>3){lunar_pipeline_refuse(10701);return;}
    ++pipeline_source[source].seq;pipeline_barrier();
    pipeline_source[source].tick=pipeline_clock();pipeline_barrier();
    ++pipeline_source[source].seq;pipeline_barrier();
    if(os_sem_post(&pipeline_sem[cpu])){lunar_pipeline_refuse(10702);return;}
    /* Tokens remain unconditional. A running receiver rechecks its predicate;
       an armed receiver needs the explicit equal-priority cross-core yield. */
    pipeline_barrier();
    if(pipeline_waiting[cpu])vPortYield();
}
int lunar_pipeline_wake_drain(unsigned cpu) {
    if(cpu>1 || current_cpu_id()!=cpu || !pipeline_ready){lunar_pipeline_refuse(10703);return -1;}
    ++pipeline_stats[cpu].drains;
    for(unsigned i=0;i<16;++i) {
        int r=os_sem_accept(&pipeline_sem[cpu]);pipeline_sem_status[cpu]=r;
        if(r==11)return 1; /* OS_TIMEOUT: exact pinned wrapper's empty code. */
        if(r){lunar_pipeline_refuse(10704);return -1;}
        ++pipeline_stats[cpu].accepted;
    }
    return 1; /* Remaining tokens cause harmless immediate predicate rechecks. */
}
int lunar_pipeline_wake_wait(unsigned cpu) {
    uint32_t seen[4],start,end;
    if(cpu>1 || current_cpu_id()!=cpu || !pipeline_ready){lunar_pipeline_refuse(10705);return -1;}
    if(lunar_pipeline_error())return -1;
    for(unsigned j=0;j<4;++j)seen[j]=pipeline_source[j].seq;
    ++pipeline_stats[cpu].waits;start=pipeline_clock();
    pipeline_waiting[cpu]=1;pipeline_barrier();
    int r=os_sem_pend(&pipeline_sem[cpu],1);pipeline_sem_status[cpu]=r; /* Guard timeout, never audio pacing. */
    pipeline_waiting[cpu]=0;pipeline_barrier();
    end=pipeline_clock();pipeline_barrier();
    uint32_t elapsed=end-start;
    if(elapsed>pipeline_stats[cpu].pend_max)pipeline_stats[cpu].pend_max=elapsed;
    if(r==11)++pipeline_stats[cpu].timeouts;
    else if(r){lunar_pipeline_refuse(10706);return -1;}
    for(unsigned j=0;j<4;++j) {
        unsigned target=(j==0 || j==2)?1u:0u;
        uint32_t a=pipeline_source[j].seq;pipeline_barrier();
        uint32_t tick=pipeline_source[j].tick;pipeline_barrier();
        uint32_t b=pipeline_source[j].seq;
        if(target==cpu && a==b && !(a&1u) && a!=seen[j]) {
            uint32_t dt=end-tick;
            if(dt<0x80000000u && dt>pipeline_stats[cpu].resume_max)pipeline_stats[cpu].resume_max=dt;
        }
    }
    return lunar_pipeline_error()?-1:1;
}
void lunar_pipeline_wake_drain_done(void) { pipeline_signal(0,3); }
static void pipeline_wake_report(void) {
    for(unsigned cpu=0;cpu<2;++cpu)
        printf("LUNAR_PIPELINE_WAKE core=%u drains=%u tokens=%u waits=%u timeouts=%u pend_max_ticks=%u last_post_to_resume_max_ticks=%u\n",
          cpu,pipeline_stats[cpu].drains,pipeline_stats[cpu].accepted,pipeline_stats[cpu].waits,
          pipeline_stats[cpu].timeouts,pipeline_stats[cpu].pend_max,pipeline_stats[cpu].resume_max);
}

#pragma code_seg(".volatile_ram_code")
static void fence(void) { __asm__ volatile("csync;" ::: "memory"); }
uint32_t lunar_pipeline_error(void) {
    uint32_t a=s.error0,b=s.error1; fence(); return a?a:b;
}
void lunar_pipeline_refuse(uint32_t code) {
    if(!code)code=E_API;
    if(current_cpu_id()==1) { if(!s.error1){s.error1=code;} }
    else { unsigned flags; local_irq_save(flags); if(!s.error0){s.error0=code;} local_irq_restore(flags); }
    fence();pipeline_wake_abort();
}
void lunar_pipeline_fail_park(uint32_t code) {
    lunar_pipeline_refuse(code);
    /* Deliberately retain current slot, stacks, clock and arenas. The other
     * task sees poison; no callback continuation or unsafe cleanup occurs. */
    for(;;)os_time_dly(1);
}
static int bad(uint32_t code) { lunar_pipeline_refuse(code); return -1; }
static int cpu0(void) {
    if(current_cpu_id()!=0)return bad(E_CORE);
    if(lunar_pipeline_error())return -1;
    return 1;
}
int lunar_pipeline_wait_check(uint32_t *ticket) {
    uint32_t now;
    if(!ticket || !s.clock)return bad(E_API);
    if(lunar_pipeline_error())return -1;
    if((uint32_t)(timer_get_ms()-s.started_ms)>=LIFETIME_MS)return bad(E_LIFETIME);
    now=s.clock();
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
    fence();s.bound=1;fence();pipeline_signal(1,0);return lunar_pipeline_error()?-1:1;
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
    /* Count before publication; count is diagnostics, not the worker gate. */
    s.produced=tag+1u;fence();w->state=SEALED;fence();pipeline_signal(1,0);return lunar_pipeline_error()?-1:1;
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
    s.output_retired=tag+1u;fence();o->state=FREE;fence();pipeline_signal(1,2);return lunar_pipeline_error()?-1:1;
}
static int worker_step(void) {
    uint32_t tag=s.consumed;Work *w;Output *o;
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
    int consumed_ok=s.consume(w->work,tag,o->pcm,&o->result);
    if(!consumed_ok || lunar_pipeline_error())return bad(E_CALLBACK);
    if(o->result.tag!=tag)return bad(E_TAG);
    w->completion.result=o->result;w->completion.c_end=s.clock();
    w->completion.c_ticks=w->completion.c_end-w->completion.c_start;
    if(w->completion.c_ticks>=0x80000000u)return bad(E_API);
    /* No work/output field access after its respective release. */
    fence();o->state=READY;s.consumed=tag+1u;fence();w->state=DONE;fence();pipeline_signal(0,1);
    return 1;
}
static void worker(void *unused) {
    uint32_t blocked=0;(void)unused;
    if(current_cpu_id()!=1){lunar_pipeline_refuse(E_CORE);goto done;}
    fence();s.ready=1;
    for(;;) {
        int result;
        if(lunar_pipeline_wake_drain(1)<0)break;
        if(lunar_pipeline_error())break;
        if(s.stop)break;
        if((uint32_t)(timer_get_ms()-s.started_ms)>=LIFETIME_MS){lunar_pipeline_refuse(E_LIFETIME);break;}
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
            if(lunar_pipeline_wake_wait(1)<0)break;
        }
    }
done:
    s.stack_unused=(uint32_t)uxTaskGetStackHighWaterMark(NULL);
    fence();s.exited=1;
    for(;;)os_time_dly(100);
}
#pragma code_seg()
int lunar_pipeline_sdk_start(uint32_t (*clock)(void)) {
    uint32_t first;int status;
    if(s.invoked || current_cpu_id()!=0 || !clock){lunar_pipeline_refuse(E_API);return 0;}
    s.invoked=1;s.clock=clock;s.started_ms=timer_get_ms();fence();
    if(!pipeline_wake_init(clock)){lunar_pipeline_refuse(10711);return 0;}
    status=os_task_create_static(worker,NULL,WORKER_PRIORITY,STACK_WORDS,0,"#C1lunar_queue",worker_memory);
    if(status){lunar_pipeline_refuse(E_CREATE);return 0;}
    first=timer_get_ms();
    while(!s.ready && !s.exited && (uint32_t)(timer_get_ms()-first)<1000u)os_time_dly(1);
    fence();if(!s.ready || s.exited || lunar_pipeline_error()){lunar_pipeline_refuse(E_TIMEOUT);s.stop=1;return 0;}
    printf("LUNAR_PIPELINE ready=1 lifetime_ms=%u stack_words=%u priority=%u outputs=%u\n",LIFETIME_MS,STACK_WORDS,WORKER_PRIORITY,LUNAR_PIPELINE_OUTPUT_SLOTS);
    return 1;
}
void lunar_pipeline_sdk_parent_block(void) {
    ++s.parent_blocks;
    if(current_cpu_id()!=0){++s.parent_wrong;lunar_pipeline_refuse(E_CORE);}
}
void lunar_pipeline_sdk_report(unsigned test_case) {
    printf("LUNAR_PIPELINE case=%u produced=%u consumed=%u harvested=%u output_retired=%u error0=%u error1=%u parent_blocks=%u parent_wrong=%u exited=%u\n",test_case,s.produced,s.consumed,s.harvested,s.output_retired,s.error0,s.error1,s.parent_blocks,s.parent_wrong,s.exited);
}
int lunar_pipeline_sdk_finish(void) {
    uint32_t first;
    if(current_cpu_id()!=0){lunar_pipeline_refuse(E_CORE);return 0;}
    fence();
    if(!s.bound || !s.produced || s.produced!=s.consumed || s.produced!=s.harvested ||
       s.produced!=s.output_retired || lunar_pipeline_error()) {
        /* Poison admission. Never falsely drain/free unfinished work. */
        lunar_pipeline_refuse(E_FINISH);return 0;
    }
    s.stop=1;fence();pipeline_wake_abort();first=timer_get_ms();
    while(!s.exited && (uint32_t)(timer_get_ms()-first)<1000u)os_time_dly(1);
    if(!s.exited){lunar_pipeline_refuse(E_TIMEOUT);return 0;}
    fence();lunar_pipeline_sdk_report(4);
    pipeline_wake_report();
    printf("LUNAR_PIPELINE final=1 stack_unused_words=%u word_bytes=4 backend_bytes=%u\n",s.stack_unused,(unsigned)(sizeof works+sizeof outputs+sizeof s+sizeof worker_memory));
    return !lunar_pipeline_error() && !s.parent_wrong;
}

unsigned lunar_pipeline_ready_outputs(void) { unsigned n=0; for(unsigned i=0;i<LUNAR_PIPELINE_OUTPUT_SLOTS;++i) if(outputs[i].state==READY) ++n; fence(); return n; }

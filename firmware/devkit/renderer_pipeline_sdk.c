/* SPDX-License-Identifier: MIT. pi32v2 SDK adapter for the shared protocol.
 * The default port preserves the existing volatile-word/csync convention.
 * Host tests supply an atomic SDK shim; no target visibility claim follows. */
#ifndef LUNAR_PIPELINE_SDK_PLATFORM_HEADER
#define LUNAR_PIPELINE_SDK_PLATFORM_HEADER "renderer_pipeline_sdk_platform.h"
#endif
#include LUNAR_PIPELINE_SDK_PLATFORM_HEADER
#include "renderer_pipeline_sdk.h"
#if defined(LUNAR_DEVKIT_FM6_SDK) || defined(LUNAR_DEVKIT_FM6_PAIR) || defined(LUNAR_DEVKIT_QUEUE_SDK)
#error Renderer pipeline must not nest another SDK worker
#endif
#define STACK_WORDS 1536u
#define WORKER_PRIORITY 16u
static unsigned char worker_memory[sizeof(StaticTask_t)+STACK_WORDS*4u]
    __attribute__((aligned(4)));
#pragma code_seg(".volatile_ram_code")
/* V107: counted wake tokens; authoritative queue states remain separate. */
static OS_SEM pipeline_sem[2];
static lunar_pipeline_word_t pipeline_ready;
static lunar_pipeline_word_t pipeline_waiting[2]; /* Each target task writes its own flag. */
static uint32_t (*pipeline_clock)(void);
static struct {
    lunar_pipeline_word_t seq, tick;
} pipeline_source[4]; /* Single writers: publish, DONE, output-retire, DAC-drain. */
static struct {
    uint32_t drains, accepted, waits, timeouts, pend_max, resume_max;
} pipeline_stats[2]; /* Each task writes only its own row; read after worker exit. */
static lunar_pipeline_status_t pipeline_sem_status[2];
static void pipeline_barrier(void) { port_fence(); }
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


static unsigned port_cpu(void) { return current_cpu_id(); }
static uint32_t port_ms(void) { return timer_get_ms(); }
static unsigned port_irq_save(void) { unsigned flags;local_irq_save(flags);return flags; }
static void port_irq_restore(unsigned flags) { local_irq_restore(flags); }
static void port_delay(unsigned ticks) { os_time_dly(ticks); }
static int port_launch(void (*entry)(void *),void *arg) {
    return os_task_create_static(entry,arg,WORKER_PRIORITY,STACK_WORDS,0,"#C1lunar_queue",worker_memory);
}
static uint32_t port_stack_unused(void) { return (uint32_t)uxTaskGetStackHighWaterMark(NULL); }
static int port_wake_init(uint32_t (*clock)(void)) { return pipeline_wake_init(clock); }
static int port_wake_drain(unsigned cpu) { return lunar_pipeline_wake_drain(cpu); }
static int port_wake_wait(unsigned cpu) { return lunar_pipeline_wake_wait(cpu); }
static void port_signal(unsigned cpu,unsigned source) { pipeline_signal(cpu,source); }
static void port_wake_abort(void) { pipeline_wake_abort(); }
/* One translation unit retains native inlining/section placement. The core is
 * also compiled unchanged by an independent host-only port in protocol tests. */
#include "../common/renderer_pipeline_core.c"
#pragma code_seg()
int lunar_pipeline_sdk_start(uint32_t (*clock)(void)) {
    if(!lunar_pipeline_core_start(clock))return 0;
    printf("LUNAR_PIPELINE ready=1 lifetime_ms=%u stack_words=%u priority=%u outputs=%u\n",
      LUNAR_PIPELINE_LIFETIME_MS,STACK_WORDS,WORKER_PRIORITY,LUNAR_PIPELINE_OUTPUT_SLOTS);
    return 1;
}
void lunar_pipeline_sdk_parent_block(void) { lunar_pipeline_core_parent_block(); }
void lunar_pipeline_sdk_report(unsigned test_case) {
    lunar_pipeline_stats_t r;lunar_pipeline_core_stats(&r);
    printf("LUNAR_PIPELINE case=%u produced=%u consumed=%u harvested=%u output_retired=%u error0=%u error1=%u parent_blocks=%u parent_wrong=%u exited=%u\n",
      test_case,r.produced,r.consumed,r.harvested,r.output_retired,r.error0,r.error1,r.parent_blocks,r.parent_wrong,r.exited);
}
int lunar_pipeline_sdk_finish(void) {
    if(!lunar_pipeline_core_finish())return 0;
    lunar_pipeline_stats_t r;lunar_pipeline_core_stats(&r);
    lunar_pipeline_sdk_report(4);pipeline_wake_report();
    printf("LUNAR_PIPELINE final=1 stack_unused_words=%u word_bytes=4 backend_bytes=%u\n",
      r.stack_unused,(unsigned)(lunar_pipeline_core_bytes()+sizeof worker_memory));
    return !lunar_pipeline_error() && !r.parent_wrong;
}

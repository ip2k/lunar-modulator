/* Includes a GENERATED atomic-word copy of the actual native backend. */
#include "sdk_shim.h"
#include "backend.c"
#include <string.h>
#define N 2000u
#define CHECK(x) do { if(!(x)){fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#x);exit(2);} }while(0)
typedef struct { uint32_t tag, cookie, retired; } HostWork;
static HostWork hw[2];
static _Atomic uint32_t calls, callback_entered, callback_release;
/* Protocol time is controlled by the test, independently of host scheduling.
 * Wall-clock guards still bound startup, waits and the test subprocess. */
static _Atomic uint32_t protocol_ticks=1000u;
static uint32_t protocol_clock(void) { return atomic_load(&protocol_ticks); }
static _Atomic uint32_t seen[N], retired_count[N];
static int callback_failure,retire_failure,slow_callback,park_callback;
static uint32_t next_harvest,next_output;
static int16_t expected_sample(uint32_t tag,unsigned i) { return (int16_t)((tag*17u+i)%32000u); }
static int consume(void *ptr,uint32_t tag,int16_t *pcm,lunar_pipeline_result_t *r) {
    HostWork *w=ptr;
    CHECK(current_cpu_id()==1 && w==&hw[tag%2] && w->tag==tag && w->cookie==(tag^0x35aee781u));
    CHECK(tag<N && atomic_fetch_add(&seen[tag],1)==0);
    CHECK(atomic_fetch_add(&calls,1)==tag);atomic_store(&callback_entered,1);
    if(park_callback)lunar_pipeline_fail_park(700u);
    if(slow_callback)while(!atomic_load(&callback_release))os_time_dly(1);
    if(callback_failure)return 0;
    for(unsigned i=0;i<LUNAR_PIPELINE_OUTPUT_SAMPLES;++i)pcm[i]=expected_sample(tag,i);
    r->case_index=tag/5513u;r->case_block=tag%5513u;r->hash=tag^0x12345678u;
    r->case_total=tag+1;r->user[0]=w->cookie;
    return 1;
}
static int retire(void *ptr) {
    HostWork *w=ptr;uint32_t tag=w->tag;
    CHECK(current_cpu_id()==0 && tag==next_harvest && w==&hw[tag%2]);
    CHECK(atomic_fetch_add(&retired_count[tag],1)==0);
    if(retire_failure)return 0;
    w->retired=1;return 1;
}
static void setup(void) {
    clock_gettime(CLOCK_MONOTONIC,&host_epoch);host_cpu=0;
    CHECK(lunar_pipeline_sdk_start(protocol_clock)==1);
    CHECK(lunar_pipeline_bind(&hw[0],&hw[1],consume,retire)==1);
}
static int produce(uint32_t tag) {
    void *p=NULL;int r=lunar_pipeline_reserve_work(tag,&p);
    CHECK(r>=0);if(!r){CHECK(!p);return 0;}
    uint32_t start=protocol_clock();HostWork *w=p;
    CHECK(w==&hw[tag%2]);
    if(tag>=2)CHECK(w->retired==1);
    w->tag=tag;w->cookie=tag^0x35aee781u;w->retired=0;
    int published=lunar_pipeline_publish(tag,start,protocol_clock());
    /* An injected callback may poison the worker before publish returns. The
     * slot was still published once; both schedules must retain its ownership. */
    if(callback_failure || park_callback)
        CHECK(published==1 || (published==-1 &&
            lunar_pipeline_error()==(park_callback?700u:E_CALLBACK)));
    else CHECK(published==1);
    lunar_pipeline_sdk_parent_block();return 1;
}
static int harvest_one(void) {
    lunar_pipeline_completion_t c;int r=lunar_pipeline_harvest(&c);CHECK(r>=0);
    if(!r)return 0;
    CHECK(c.tag==next_harvest && c.result.tag==c.tag && c.result.hash==(c.tag^0x12345678u));
    CHECK(c.p_ticks==(uint32_t)(c.p_end-c.p_start) && c.c_ticks==(uint32_t)(c.c_end-c.c_start));
    CHECK(c.ready_wait_ticks==(uint32_t)(c.c_start-c.published));
    ++next_harvest;return 1;
}
static int acquire_one(const int16_t **pcm) {
    const lunar_pipeline_result_t *r=NULL;int rc=lunar_pipeline_output_acquire(next_output,pcm,&r);CHECK(rc>=0);
    if(!rc)return 0;
    CHECK(r && r->tag==next_output && r->hash==(next_output^0x12345678u));
    CHECK(r->case_index==next_output/5513u && r->case_block==next_output%5513u);
    for(unsigned i=0;i<LUNAR_PIPELINE_OUTPUT_SAMPLES;++i)CHECK((*pcm)[i]==expected_sample(next_output,i));
    return 1;
}
static int output_one(void) {
    const int16_t *pcm;if(!acquire_one(&pcm))return 0;
    CHECK(lunar_pipeline_output_retire(next_output)==1);++next_output;return 1;
}
static void wait_ok(uint32_t *ticket,int progress) {
    CHECK(lunar_pipeline_wake_drain(0)==1);
    if(progress)*ticket=0;
    else CHECK(lunar_pipeline_wait_check(ticket)==1);
}
static void drain(unsigned n) {
    uint32_t ticket=0;
    while(next_harvest<n || next_output<n) {
        int progress=harvest_one();progress|=output_one();wait_ok(&ticket,progress);
    }
}
static void run_stream(void) {
    uint32_t tag=0,ticket=0;
    while(tag<N || next_harvest<N || next_output<N) {
        int progress=0;
        if(tag<N && produce(tag)){++tag;progress=1;}
        progress|=harvest_one();progress|=output_one();wait_ok(&ticket,progress);
    }
    CHECK(atomic_load(&calls)==N);
    for(unsigned i=0;i<N;++i)CHECK(seen[i]==1 && retired_count[i]==1);
    CHECK(lunar_pipeline_sdk_finish()==1);host_cleanup();
}
static void run_output_full(unsigned host_delay_ms) {
    uint32_t ticket=0;const int16_t *held=NULL;
    for(unsigned tag=0;tag<8;++tag) {
        while(!produce(tag)){int p=harvest_one();wait_ok(&ticket,p);}
        while(next_harvest<=tag)wait_ok(&ticket,harvest_one());
        if(!tag){while(!acquire_one(&held))wait_ok(&ticket,0);}
    }
    CHECK(held && outputs[0].state==LEASED && s.output_retired==0);
    CHECK(produce(8)==1 && produce(9)==1);
    /* Simulate a host deschedule longer than the target protocol timeout.
     * Test time has not advanced, so output backpressure must retain ownership. */
    if(host_delay_ms)os_time_dly(host_delay_ms);
    CHECK(atomic_load(&calls)==8);
    CHECK(works[0].state==SEALED && works[1].state==SEALED);
    CHECK(s.consumed==8 && s.harvested==8);
    /* Old output lease survives FOUR uses of the same work storage. */
    for(unsigned i=0;i<LUNAR_PIPELINE_OUTPUT_SAMPLES;++i)CHECK(held[i]==expected_sample(0,i));
    CHECK(lunar_pipeline_output_retire(0)==1);next_output=1;
    drain(10);CHECK(lunar_pipeline_sdk_finish()==1);host_cleanup();
}
static void wait_error(void) {
    unsigned t=timer_get_ms();
    while(!lunar_pipeline_error() && timer_get_ms()-t<500u)os_time_dly(1);
    CHECK(lunar_pipeline_error()!=0);
}
static void expect_poison(void) {
    void *p=(void*)1;lunar_pipeline_completion_t c;uint32_t before=s.produced;
    CHECK(lunar_pipeline_reserve_work(s.produced,&p)==-1);
    CHECK(lunar_pipeline_harvest(&c)==-1);
    CHECK(s.produced==before);
}
static void run_fault(const char *mode) {
    void *p=NULL;const int16_t *pcm=NULL;const lunar_pipeline_result_t *result=NULL;uint32_t ticket=0;
    if(!strcmp(mode,"reserve_twice")) {
        CHECK(lunar_pipeline_reserve_work(0,&p)==1);CHECK(lunar_pipeline_reserve_work(0,&p)==-1);
        CHECK(works[0].state==PRODUCING && s.produced==0);
    } else if(!strcmp(mode,"publish_wrong")) {
        CHECK(lunar_pipeline_reserve_work(0,&p)==1);CHECK(lunar_pipeline_publish(1,0,0)==-1);
        CHECK(works[0].state==PRODUCING && s.produced==0);
    } else if(!strcmp(mode,"acquire_twice") || !strcmp(mode,"retire_wrong")) {
        CHECK(produce(0));while(!acquire_one(&pcm))wait_ok(&ticket,harvest_one());
        if(!strcmp(mode,"acquire_twice"))CHECK(lunar_pipeline_output_acquire(0,&pcm,&result)==-1);
        else CHECK(lunar_pipeline_output_retire(1)==-1);
        CHECK(outputs[0].state==LEASED && s.output_retired==0);
    } else if(!strcmp(mode,"callback_failure")) {
        callback_failure=1;CHECK(produce(0));wait_error();
        CHECK(lunar_pipeline_error()==E_CALLBACK);
        CHECK(works[0].state==CONSUMING && outputs[0].state==RESERVED);
        CHECK(s.consumed==0 && s.harvested==0 && calls==1);
    } else if(!strcmp(mode,"retire_failure")) {
        retire_failure=1;CHECK(produce(0));lunar_pipeline_completion_t c;int rc=0;
        while(!(rc=lunar_pipeline_harvest(&c)))wait_ok(&ticket,0);
        CHECK(rc==-1 && works[0].state==DONE && s.harvested==0 && retired_count[0]==1);
    } else if(!strcmp(mode,"timeout_late")) {
        slow_callback=1;CHECK(produce(0));
        unsigned started=timer_get_ms();
        while(!callback_entered && timer_get_ms()-started<500u)os_time_dly(1);
        CHECK(callback_entered && works[0].state==CONSUMING);
        CHECK(lunar_pipeline_wait_check(&ticket)==1);
        atomic_fetch_add(&protocol_ticks,LUNAR_PIPELINE_PROTOCOL_TICKS-1u);
        CHECK(lunar_pipeline_wait_check(&ticket)==1); /* One tick before expiry. */
        atomic_fetch_add(&protocol_ticks,1u);
        CHECK(lunar_pipeline_wait_check(&ticket)==-1);
        CHECK(lunar_pipeline_error()==E_TIMEOUT && works[0].state==CONSUMING);
        expect_poison();
        CHECK(!s.exited && outputs[0].state==RESERVED);
        atomic_store(&callback_release,1);
        started=timer_get_ms();
        while(!s.exited && timer_get_ms()-started<500u)os_time_dly(1);
        CHECK(s.exited && works[0].state==CONSUMING && outputs[0].state==RESERVED);
        CHECK(s.consumed==0 && s.harvested==0 && s.output_retired==0 && hw[0].tag==0);
    } else if(!strcmp(mode,"guard_park")) {
        park_callback=1;CHECK(produce(0));wait_error();
        CHECK(lunar_pipeline_error()==700 && !s.exited && works[0].state==CONSUMING);
        CHECK(outputs[0].state==RESERVED && s.consumed==0);
    } else if(!strcmp(mode,"finish_pending")) {
        CHECK(lunar_pipeline_reserve_work(0,&p)==1);
        CHECK(lunar_pipeline_sdk_finish()==0 && works[0].state==PRODUCING);
    } else CHECK(0);
    wait_error();expect_poison();
    /* Poison stops worker between callbacks; permanent parked guard is cancelled
     * only by the HOST test harness after asserting retained target state. */
    if(!park_callback){unsigned t=timer_get_ms();while(!s.exited && timer_get_ms()-t<500u)os_time_dly(1);CHECK(s.exited);}
    host_cleanup();
}
int main(int argc,char **argv) {
    CHECK(argc==2);setup();
    if(!strcmp(argv[1],"stream"))run_stream();
    else if(!strcmp(argv[1],"output_full"))run_output_full(0);
    else if(!strcmp(argv[1],"output_full_descheduled"))run_output_full(200);
    else run_fault(argv[1]);
    printf("LUNAR_PIPELINE_HOST PASS mode=%s calls=%u produced=%u consumed=%u harvested=%u retired=%u\n",argv[1],atomic_load(&calls),s.produced,s.consumed,s.harvested,s.output_retired);
    return 0;
}

/* SPDX-License-Identifier: MIT. Actual adapter/core, fault injection at backend. */
#define LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER "native_platform.h"
#include "renderer_pipeline_native.c"
#include <assert.h>
#include <string.h>
static struct { uint32_t tag; } arena[2];
static _Atomic unsigned callbacks;
static uint32_t ticks(void) { return (uint32_t)(host_ns()/1000u); }
static int consume(void *work,uint32_t tag,int16_t *pcm,lunar_pipeline_result_t *result) {
    assert(setup_finished && launch_context.command==N_RUN);
    assert(work==&arena[tag%2] && arena[tag%2].tag==tag);
    for(unsigned i=0;i<256;++i)pcm[i]=(int16_t)(tag+i);
    result->hash=tag+17; ++callbacks; return 1;
}
static int retire(void *work) { assert(work==&arena[0] || work==&arena[1]);return 1; }
static void wait_until(unsigned expected) {
    for(unsigned i=0;i<3000 && callbacks<expected;++i)os_time_dly(1);
    assert(callbacks==expected);
}
static void stream(void) {
    assert(lunar_pipeline_bind(&arena[0],&arena[1],consume,retire)==1);
    for(uint32_t tag=0;tag<24;++tag) {
        void *work=0;const int16_t *pcm=0;const lunar_pipeline_result_t *result=0;
        lunar_pipeline_completion_t completion;
        assert(lunar_pipeline_reserve_work(tag,&work)==1);
        assert(work==&arena[tag%2]);arena[tag%2].tag=tag;
        assert(lunar_pipeline_publish(tag,ticks(),ticks())==1);
        wait_until(tag+1);
        int h=0,o=0;
        for(unsigned i=0;i<3000 && (!h || !o);++i) {
            if(!h)h=lunar_pipeline_harvest(&completion);
            if(!o)o=lunar_pipeline_output_acquire(tag,&pcm,&result);
            assert(h>=0 && o>=0); if(!h || !o)os_time_dly(1);
        }
        assert(h==1 && o==1 && completion.tag==tag && result->hash==tag+17);
        for(unsigned i=0;i<256;++i)assert(pcm[i]==(int16_t)(tag+i));
        assert(lunar_pipeline_output_retire(tag)==1);
    }
    assert(lunar_pipeline_native_finish()==1);
}
static void *observe_entered(void *unused) {
    (void)unused;
    while(!setup_arrived)os_time_dly(1);
    assert(launch_context.entered==1 && !launch_context.ready && launch_context.command==N_PUBLISHED);
    release_setup=1;return NULL;
}
int main(int argc,char **argv) {
    assert(argc==2);const char *mode=argv[1];
    clock_gettime(CLOCK_MONOTONIC,&host_epoch);atexit(host_cleanup);
    assert(!lunar_pipeline_native_hardware_admitted());
    if(!strcmp(mode,"missing_irq")) {
        assert(!lunar_pipeline_native_start(ticks));assert(!launch_calls);
        assert(!lunar_pipeline_native_primary_irq_ready());
    } else if(!strcmp(mode,"wrong_core")) {
        host_cpu=1;assert(!lunar_pipeline_native_primary_irq_ready());host_cpu=0;
        assert(!lunar_pipeline_native_start(ticks));assert(!launch_calls);
    } else {
        assert(lunar_pipeline_native_primary_irq_ready());
        if(!strcmp(mode,"stale_ack")) {launch_context.entered=1;launch_context.ready=1;}
        if(!strcmp(mode,"launch_fail"))mode_launch_fail=1;
        if(!strcmp(mode,"late_entry") || !strcmp(mode,"timeout"))mode_no_entry=1;
        if(!strcmp(mode,"setup_fail"))mode_setup_fail=1;
        if(!strcmp(mode,"bad_argument"))mode_bad_argument=1;
        if(!strcmp(mode,"late_launch_fail"))mode_late_launch_fail=1;
        if(!strcmp(mode,"deadline"))mode_deadline=1;
        if(!strcmp(mode,"late_ready") || !strcmp(mode,"entered_before_ready"))mode_hold_setup=1;
        if(!strcmp(mode,"clock_wrap"))host_ms_offset=UINT32_MAX-5;
        pthread_t observer;int observed=!strcmp(mode,"entered_before_ready");
        if(observed)assert(!pthread_create(&observer,NULL,observe_entered,NULL));
        int ok=lunar_pipeline_native_start(ticks);
        if(observed)pthread_join(observer,NULL);
        if(!strcmp(mode,"stream") || observed || !strcmp(mode,"clock_wrap")) {
            assert(ok);stream();
            assert(!lunar_pipeline_native_start(ticks));assert(launch_calls==1);
        } else if(!strcmp(mode,"irq_reinit")) {
            assert(ok);assert(!lunar_pipeline_native_primary_irq_ready());
            assert(lunar_pipeline_error());
        } else {
            assert(!ok && lunar_pipeline_error() && !callbacks);
            if(!strcmp(mode,"late_entry")) {
                assert(host_argument==&launch_context);host_cpu=1;
                host_entry(host_argument);host_cpu=0;
                assert(!launch_context.entered && !launch_context.ready);
            }
            if(!strcmp(mode,"late_ready")) {
                assert(setup_arrived && launch_context.entered && !launch_context.ready);
                release_setup=1;pthread_join(host_worker,NULL);host_created=0;
                assert(!launch_context.ready);
            }
            assert(!lunar_pipeline_native_start(ticks));assert(!callbacks);
        }
    }
    lunar_pipeline_native_status_t status;lunar_pipeline_native_status(&status);
    assert(status.refused);
    printf("NATIVE_LIFECYCLE PASS %s callbacks=%u\n",mode,callbacks);
    return 0;
}

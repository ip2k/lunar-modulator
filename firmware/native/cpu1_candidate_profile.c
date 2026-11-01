/* SPDX-License-Identifier: MPL-2.0. OFFLINE stock-SPL candidate profile only.
 * No hardware output or transport, SDK, app, engine, flash, reset or cache code.
 * Successful completion would still NOT admit this backend for production.
 */
#include "cpu1_candidate_target.h"
#include "renderer_pipeline_native.h"

/* Debugger-readable permanent evidence, not a device protocol or success claim.
 * Zero admission is unconditional, including if this witness were to complete. */
volatile struct {
    uint32_t hardware_admitted,stock_spl_route,boot_argument,early_debug,phase,error,tag,pcm_hash;
} lunar_cpu1_candidate_evidence;
static struct { uint32_t tag; } work[2];
static int consume(void *arena,uint32_t tag,int16_t *pcm,lunar_pipeline_result_t *r) {
    if(arena!=&work[tag%2u] || work[tag%2u].tag!=tag)return 0;
    uint32_t hash=0;
    for(unsigned i=0;i<256;++i){pcm[i]=(int16_t)(tag+i);hash=hash*33u+(uint16_t)pcm[i];}
    r->hash=hash;return 1;
}
static int retire(void *arena) { return arena==&work[0] || arena==&work[1]; }
static void terminal(uint32_t error) __attribute__((noreturn));
static void terminal(uint32_t error) {
    lunar_cpu1_candidate_evidence.error=error;
    lunar_cpu1_candidate_evidence.phase=error?0xffu:6u;
    /* This is a terminal CPU0 owner path, never wake_abort or normal finish.
     * State/arenas/stacks/code are not reclaimed, even after a successful hold. */
    if(error)cpu1_candidate_hold(&lunar_cpu1_candidate);
    for(;;)__asm__ volatile("csync" ::: "memory");
}
void lunar_cpu1_candidate_cstart(uint32_t boot_argument,uint32_t early_debug) {
    extern uint32_t _candidate_data_load[],_candidate_data_lo[],_candidate_data_hi[];
    extern uint32_t _candidate_bss_lo[],_candidate_bss_hi[];
    uint32_t *from=_candidate_data_load,*to=_candidate_data_lo;
    /* CPU0 early hold already finished. CPU1 never calls this C initializer. */
    while(to<_candidate_data_hi)*to++=*from++;
    for(to=_candidate_bss_lo;to<_candidate_bss_hi;)*to++=0;
    lunar_cpu1_candidate_evidence.stock_spl_route=1;
    lunar_cpu1_candidate_evidence.boot_argument=boot_argument;
    lunar_cpu1_candidate_evidence.early_debug=early_debug;
    lunar_cpu1_candidate_evidence.phase=1;
    /* TIMER4 register facts: OSC 24 MHz, /1, free-running 32-bit. Preserve a
     * compatible running source; otherwise configure this profile's timebase.
     * No system clock, rails or cache allocation is changed. Units need target
     * qualification; a stopped counter is bounded by the candidate poll cap. */
    volatile uint32_t *timer=(volatile uint32_t *)0x10800u;
    if((timer[0]&0xffu)!=9u || timer[2]!=UINT32_MAX) {
        timer[0]=0;timer[2]=UINT32_MAX;timer[1]=0;timer[0]=0x4009u;
    }
    if(!lunar_cpu1_candidate_target_prepare())terminal(1);
    lunar_cpu1_candidate_evidence.phase=2;
    if(!lunar_pipeline_native_start(lunar_cpu1_candidate_ticks))terminal(2);
    lunar_cpu1_candidate_evidence.phase=3;
    if(!lunar_pipeline_bind(&work[0],&work[1],consume,retire))terminal(3);
    for(uint32_t tag=0;tag<24u;++tag) {
        void *arena=0;const int16_t *pcm=0;const lunar_pipeline_result_t *result=0;
        lunar_pipeline_completion_t completion;
        if(lunar_pipeline_reserve_work(tag,&arena)!=1)terminal(4);
        work[tag%2u].tag=tag;
        if(lunar_pipeline_publish(tag,lunar_cpu1_candidate_ticks(),lunar_cpu1_candidate_ticks())!=1)terminal(5);
        int harvested=0,output=0;unsigned polls=0;
        uint32_t first=cpu1_candidate_ms(&lunar_cpu1_candidate);
        while(!harvested || !output) {
            if(!harvested)harvested=lunar_pipeline_harvest(&completion);
            if(!output)output=lunar_pipeline_output_acquire(tag,&pcm,&result);
            if(harvested<0 || output<0 || lunar_cpu1_candidate.failed ||
               ++polls>=CPU1_CANDIDATE_POLLS ||
               (uint32_t)(cpu1_candidate_ms(&lunar_cpu1_candidate)-first)>=1000u)terminal(6);
        }
        uint32_t hash=0;
        for(unsigned i=0;i<256u;++i) {
            if(pcm[i]!=(int16_t)(tag+i))terminal(7);
            hash=hash*33u+(uint16_t)pcm[i];
        }
        if(completion.tag!=tag || result->hash!=hash || lunar_pipeline_output_retire(tag)!=1)terminal(8);
        lunar_cpu1_candidate_evidence.tag=tag;lunar_cpu1_candidate_evidence.pcm_hash=hash;
    }
    lunar_cpu1_candidate_evidence.phase=4;
    if(!lunar_pipeline_native_finish() || lunar_cpu1_candidate.failed)terminal(9);
    lunar_cpu1_candidate_evidence.phase=5;
    if(lunar_pipeline_native_hardware_admitted())terminal(10);
    terminal(0);
}
/* Only byte-memory functions required by the actual common core. */
void *memset(void *dst,int byte,size_t n) {
    unsigned char *p=dst;for(size_t i=0;i<n;++i)p[i]=(unsigned char)byte;return dst;
}
void *memcpy(void *dst,const void *src,size_t n) {
    unsigned char *d=dst;const unsigned char *s=src;
    for(size_t i=0;i<n;++i)d[i]=s[i];return dst;
}

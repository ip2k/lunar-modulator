/* SPDX-License-Identifier: MIT. Opt-in continuous dev-board internal-DAC pipeline. */
#include "renderer_pipeline_dac.h"
#include "renderer_pipeline_live.h"
#if !LUNAR_DEVKIT_RENDERER_PIPELINE || !FM1_APP_RENDER_PIPELINE
#error Pipeline DAC requires the app and native pipeline backend
#endif
#ifndef asm
#define asm __asm__
#endif
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "asm/dac.h"
#include <string.h>
#define CASE_BLOCKS 5513u
#ifndef LUNAR_PIPELINE_CYCLES
#define LUNAR_PIPELINE_CYCLES 3u
#endif
#if LUNAR_PIPELINE_CYCLES < 1 || LUNAR_PIPELINE_CYCLES > 57
#error Pipeline DAC requires 1..57 complete cycles
#endif
#define SOAK_CYCLES LUNAR_PIPELINE_CYCLES
#define CASE_ORDINALS (4u*SOAK_CYCLES)
#define TOTAL (CASE_ORDINALS*CASE_BLOCKS)
#define SOAK_WATCHDOG_MS (35u*60u*1000u)
#define BUDGET 34829u
#define ZERO_DRAIN_BLOCKS 64u
extern void malloc_stats(void);
static struct { uint64_t p,c; uint32_t count,pmax,cmax,plate,clate; } service[4];
/* IRQ is sole writer after prefill/handoff. Task reads only aligned words. */
static struct {
    volatile uint32_t fault,next,callbacks,drain,hash,case_hash[4],cases_checked,case_fold;
    volatile uint32_t cb_max,irq_max,gap_max,late,gaps,previous,ready_min;
    volatile uint32_t last_pcm_ticks, zero_drain_ticks, idle, idle_callbacks;
    uintptr_t base;
} transport;
static uint32_t produced,harvested;
#include "renderer_pipeline_preroll.h"
static volatile uint32_t preroll_phase,preroll_zeros;
static uint32_t preroll_ms;
static void task_fault103(uint32_t code) { unsigned f; local_irq_save(f); if(!transport.fault)transport.fault=code; local_irq_restore(f); }
static uint32_t (*clock_now)(void);
static void fence103(void) { __asm__ volatile("csync;" ::: "memory"); }
/* A malformed length never permits a write outside this known 1536-byte ring. */
static int valid_window(u8 *data,int len) {
    uintptr_t a=(uintptr_t)data;
    return len==512 && transport.base && a>=transport.base &&
        a-transport.base<1536 && !((a-transport.base)%512);
}
static void fault_silence(u8 *data,int len,uint32_t code) {
    if(!transport.fault)transport.fault=code;
    if(valid_window(data,len))memset(data,0,512);
    fence103();lunar_pipeline_wake_drain_done();
}
#pragma code_seg(".volatile_ram_code")
static void copy_output(u8 *data,int len) {
    const int16_t *pcm=0;const lunar_pipeline_result_t *r=0;
    uint32_t tag=transport.next,hash=transport.hash;
    if(!valid_window(data,len)){fault_silence(data,len,10301);return;}
    /* Static zero-idle never touches the completed worker/queue. */
    if(transport.idle){memset(data,0,512);++transport.idle_callbacks;fence103();return;}
    if(transport.fault||lunar_pipeline_error()){fault_silence(data,len,10302);return;}
    unsigned observed=preroll_phase,phase=observed;
    int music=preroll_step(&phase,((uintptr_t)data-transport.base)/512u);
    if(music<0){fault_silence(data,len,16101);return;}
    if(phase!=observed){preroll_phase=phase;fence103();}
    if(!music){memset(data,0,512);++preroll_zeros;fence103();return;}
    if(tag==TOTAL){memset(data,0,512);++transport.drain;fence103();if(transport.drain==ZERO_DRAIN_BLOCKS){transport.zero_drain_ticks=clock_now();fence103();lunar_pipeline_wake_drain_done();}return;}
    /* Each tag maps to its fixed DMA window, including the three prefills. */
    if((uintptr_t)data-transport.base!=(tag%3u)*512u){fault_silence(data,len,10303);return;}
    unsigned ready=lunar_pipeline_ready_outputs();
    if(ready<transport.ready_min)transport.ready_min=ready;
    if(lunar_pipeline_output_acquire(tag,&pcm,&r)!=1){fault_silence(data,len,10304);return;}
    if(!r||r->tag!=tag||r->case_index!=(tag/CASE_BLOCKS)%4u||r->case_block!=tag%CASE_BLOCKS||
       r->case_total!=tag+1||r->invalid||r->clipped){fault_silence(data,len,10305);return;}
    int16_t *out=(int16_t *)data;
    for(unsigned i=0;i<64;++i)for(unsigned ch=0;ch<2;++ch) {
        int16_t word=pcm[4*i+ch];
        if(word!=pcm[4*i+ch+2]){fault_silence(data,len,10306);return;}
        out[4*i+ch]=out[4*i+ch+2]=word;
        uint16_t u=(uint16_t)out[4*i+ch];
        hash=(hash^(u&255u))*16777619u;hash=(hash^(u>>8))*16777619u;
    }
    if(hash!=r->hash){fault_silence(data,len,10307);return;}
    if(tag%CASE_BLOCKS+1==CASE_BLOCKS) {
        /* V142 dynamic decision trace must match independent host replay. */
        transport.case_hash[(tag/CASE_BLOCKS)%4u]=hash;
        uint32_t fold=transport.case_fold,ordinal=transport.cases_checked;
        for(unsigned b=0;b<4;++b)fold=(fold^((hash>>(8*b))&255u))*16777619u;
        for(unsigned b=0;b<4;++b)fold=(fold^((ordinal>>(8*b))&255u))*16777619u;
        transport.case_fold=fold;++transport.cases_checked;hash=2166136261u;
    }
    if(!lunar_pipeline_live_output(tag,pcm,r)){fault_silence(data,len,10308);return;}
    if(lunar_pipeline_output_retire(tag)!=1){fault_silence(data,len,10309);return;}
    transport.hash=hash;fence103();transport.next=tag+1;
    if(tag+1==TOTAL){transport.last_pcm_ticks=clock_now();fence103();}
}
static void fill103(void *unused,u8 *data,int len) {
    (void)unused;
    if(transport.idle){copy_output(data,len);return;}
    uint32_t begin=clock_now();
    if(transport.previous){uint32_t gap=begin-transport.previous;
        if(gap>transport.gap_max)transport.gap_max=gap;
        if(gap>BUDGET*3u/2u)++transport.gaps;}
    transport.previous=begin;copy_output(data,len);
    uint32_t elapsed=clock_now()-begin;
    if(elapsed>transport.cb_max)transport.cb_max=elapsed;
    if(elapsed>=BUDGET)++transport.late;
    ++transport.callbacks;
}
static ___interrupt void irq103(void) {
    if(transport.idle){dac_irq_handler();return;}
    uint32_t begin=clock_now();dac_irq_handler();uint32_t elapsed=clock_now()-begin;
    if(elapsed>transport.irq_max)transport.irq_max=elapsed;
}
#pragma code_seg()
static struct {uint32_t tag,p_ticks,c_ticks;} late_trace[8];
static uint32_t late_count;
static int harvest103(void) {
    lunar_pipeline_completion_t r;int n=lunar_pipeline_harvest(&r);if(n<=0)return n;
    if(r.tag!=harvested || r.result.tag!=r.tag || r.tag>=TOTAL) return -1;
    unsigned c=(r.tag/CASE_BLOCKS)%4u;
    service[c].p+=r.p_ticks;service[c].c+=r.c_ticks;++service[c].count;
    if(r.p_ticks>service[c].pmax)service[c].pmax=r.p_ticks;
    if(r.c_ticks>service[c].cmax)service[c].cmax=r.c_ticks;
    if(r.p_ticks>=BUDGET) {
        ++service[c].plate;
        if(late_count<8u){late_trace[late_count].tag=r.tag;late_trace[late_count].p_ticks=r.p_ticks;late_trace[late_count].c_ticks=r.c_ticks;}
        ++late_count;
    }
    if(r.c_ticks>=BUDGET)++service[c].clate;
    ++harvested;return 1;
}

#include "voice_budget.h"
/* Complete trace, bounded; overflow rejects acceptance. */
#ifdef LUNAR_PIPELINE_ADAPTIVE_THREE
static uint32_t budget_trace[64];
static uint32_t budget_events,budget_overflow;
static lunar_voice_budget_t budget_state;
#define budget_limit (budget_state.limit)
#define budget_mean (budget_state.mean)
static int budget_apply(void *ignored,unsigned limit) {
    (void)ignored;return lunar_pipeline_live_voice_limit(limit);
}
static __attribute__((noinline, section(".text"))) int budget_feedback(uint32_t tag,uint32_t ticks) {
    if(!budget_state.deadline && !lunar_voice_budget_init_burst_safety_three(&budget_state,BUDGET))return 0;
    /* Advisory count only; the native IRQ is the sole live output owner.
       Exclude its reader while the task scans, without acquiring a PCM lease. */
    unsigned flags,ready;
    local_irq_save(flags);ready=lunar_pipeline_ready_outputs();local_irq_restore(flags);
    int changed=lunar_voice_budget_feedback(&budget_state,tag,ticks,
                          ready,budget_apply,0);
    if(changed<0)return 0;
    if(changed) {
        if(budget_events<64u) {
            budget_trace[budget_events++]=(tag<<4)|budget_state.limit;
        } else if(budget_overflow!=UINT32_MAX)++budget_overflow;
    }
    return 1;
}
static __attribute__((noinline, section(".text"))) void budget_report(void) {
    unsigned stats[4];
    if(!lunar_pipeline_live_voice_stats(stats)){puts("LUNAR_ADAPTIVE stats_error=1");return;}
    printf("LUNAR_V142 summary=1 events=%u overflow=%u active=%u limit=%u shed=%u stolen=%u mean=%u controller_cpu=0\n",
      budget_events,budget_overflow,stats[0],stats[1],stats[2],stats[3],budget_mean);
    for(unsigned i=0;i<budget_events;++i)
      printf("LUNAR_V142 event=%u tag=%u limit=%u\n",i,budget_trace[i]>>4,budget_trace[i]&15u);
}

#else
static const uint32_t budget_overflow = 0;
static int budget_feedback(uint32_t tag,uint32_t ticks) {(void)tag;(void)ticks;return 1;}
static void budget_report(void) {puts("LUNAR_POLYPHONY fixed=12 adaptive=0");}
#endif

static int produce103(void) {
    void *work=0;int n=lunar_pipeline_reserve_work(produced,&work);if(n<=0)return n;
    lunar_pipeline_sdk_parent_block();uint32_t begin=clock_now();
    if(!lunar_pipeline_live_produce(work,produced))return -1;
    uint32_t end=clock_now();
    if(lunar_pipeline_publish(produced,begin,end)!=1)return -1;
    if(!budget_feedback(produced+1,end-begin))return -1;
    ++produced;return 1;
}
static int v110_failure(unsigned line) {
    printf("LUNAR_V110 transport_fault=%u produced=%u harvested=%u ready=%u\n",
      transport.fault,produced,harvested,lunar_pipeline_ready_outputs());
    lunar_pipeline_refuse(11000u+line);
    printf("LUNAR_PIPELINE failure_line=%u\n",line);return 0;
}
int lunar_pipeline_dac_run(uint32_t (*now)(void)) {
    static const struct dac_platform_data config={.pa_mute_port=0xff,.hw_channel=0x05,
        .ch_num=4,.sr_points=192,.vcm_init_delay_ms=1000};
    static unsigned invoked;
    if(invoked++ || !now)return 0;
    clock_now=now;
    if(!lunar_pipeline_sdk_start(now)||!lunar_devkit_renderer_init()||!lunar_pipeline_live_bind(SOAK_CYCLES))return v110_failure(__LINE__);
    memset(service,0,sizeof service);memset(&transport,0,sizeof transport);
    transport.hash=2166136261u;transport.ready_min=8;
    puts("LUNAR_DAC103 post_init_heap=1");malloc_stats();
    /* Calibration never writes CFG_DAC_TRIM. Configure while transport is off. */
    dac_early_init(1,config.hw_channel,1000);
    int opened=dac_open(&config);if(opened){printf("LUNAR_DAC103 ERROR open=%d\n",opened);return v110_failure(__LINE__);}
    if(dac_set_sample_rate(44100)){puts("LUNAR_DAC103 ERROR rate");return v110_failure(__LINE__);}
    transport.base=(uintptr_t)JL_AUDIO->DAC_ADR;
    /* Exact pinned SDK registers checked before touching its allocated ring.
       dac_on does not prefill or reset these pointers. */
    if(transport.base<0x01c00000u||transport.base>0x01c80000u-1536u||JL_AUDIO->DAC_LEN!=192||JL_AUDIO->DAC_PNS!=64||
       JL_AUDIO->DAC_HRP!=0||JL_AUDIO->DAC_SWP!=0||(JL_AUDIO->DAC_CON&32u)) {
        printf("LUNAR_DAC103 ERROR geometry adr=%x len=%u pns=%u hrp=%u swp=%u con=%x\n",
          (unsigned)transport.base,JL_AUDIO->DAC_LEN,JL_AUDIO->DAC_PNS,JL_AUDIO->DAC_HRP,JL_AUDIO->DAC_SWP,JL_AUDIO->DAC_CON);return v110_failure(__LINE__);
    }
    puts("LUNAR_DAC103 post_open_heap=1");malloc_stats();
    uint32_t wait=0;
    while(harvested<8) {
        if(lunar_pipeline_wake_drain(0)<0)return v110_failure(__LINE__);
        int changed=harvest103();if(changed<0)return v110_failure(__LINE__);
        if(produced<8){int r=produce103();if(r<0)return v110_failure(__LINE__);changed|=r;}
        if(changed)wait=0;
        else {if(lunar_pipeline_wait_check(&wait)<0)return v110_failure(__LINE__);if(lunar_pipeline_wake_wait(0)<0)return v110_failure(__LINE__);}
    }
    /* No logical output lease retires before MUSIC. IRQ alone owns live DMA. */
    memset((void *)transport.base,0,1536);preroll_phase=PRE_QUIET;fence103();
    if(transport.fault||transport.next!=0)return v110_failure(__LINE__);
    /* Publish all three prepared windows using the same frame-credit register
       the SDK IRQ handler writes after each refill. No pointer is invented. */
    fence103();JL_AUDIO->DAC_SWN=192;fence103();
    if(JL_AUDIO->DAC_SWP!=0){puts("LUNAR_DAC103 ERROR startup_write_pointer");return v110_failure(__LINE__);}
    dac_set_data_handler(NULL,fill103);request_irq(13,5,irq103,0);
    dac_set_volume(100);dac_set_gain(0,FADE_DISABLE);fence103();
#ifdef LUNAR_PIPELINE_ADAPTIVE_THREE
    puts("LUNAR_ADAPTIVE experiment=burst-safety65-floor3 initial=12 floor=3 fade_frames=64 host_replay_required=1");
#else
    puts("LUNAR_POLYPHONY fixed=12 adaptive=0");
#endif
    printf("LUNAR_DAC103 start=1 prefills=0 delayed_release=1 ready=%u total=%u busy_diagnostic=0 wake107=1\n",lunar_pipeline_ready_outputs(),TOTAL);
    int on=dac_on();if(on){printf("LUNAR_DAC103 ERROR on=%d\n",on);return v110_failure(__LINE__);}
    uint32_t pre=timer_get_ms();
    /* Worker has no sealed job while all eight outputs are held, so its normal
       idle lifetime applies; no queue protocol timeout is extended. */
    while((uint32_t)(timer_get_ms()-pre)<50u && !transport.fault && !lunar_pipeline_error())os_time_dly(1);
    for(unsigned gain=10;gain<=100 && !transport.fault && !lunar_pipeline_error();gain+=10) {
        dac_set_gain(gain,FADE_DISABLE);
        uint32_t step=timer_get_ms();
        while((uint32_t)(timer_get_ms()-step)<10u && !transport.fault && !lunar_pipeline_error())os_time_dly(1);
    }
    uint32_t settle=timer_get_ms();
    while((uint32_t)(timer_get_ms()-settle)<100u && !transport.fault && !lunar_pipeline_error())os_time_dly(1);
    preroll_ms=timer_get_ms()-pre;
    if(transport.fault||lunar_pipeline_error())return v110_failure(__LINE__);
    fence103();preroll_phase=PRE_ARM;fence103();
    uint32_t started_ms=timer_get_ms();wait=0;
    uint32_t observed_drain=0,drain_progress=0;
    /* V107: latched SDK wake, unchanged V105 PCM/transport/controls. */
    while(transport.drain<ZERO_DRAIN_BLOCKS && !transport.fault && !lunar_pipeline_error()) {
        if(lunar_pipeline_wake_drain(0)<0)break;
        int changed=harvest103();if(changed<0){task_fault103(10310);break;}
        if(produced<TOTAL){int r=produce103();if(r<0){task_fault103(10311);break;}changed|=r;}
        /* No work remains in the queue. Advancing zero DMA is completion progress,
           not a stuck queue; keep the existing nonprogress timeout unchanged. */
        if(produced==TOTAL && harvested==TOTAL && transport.next==TOTAL) {
            fence103();uint32_t seen=transport.drain;
            if(seen>observed_drain){observed_drain=seen;changed=1;++drain_progress;}
        }
        if(changed)wait=0;
        else {
            if(lunar_pipeline_wait_check(&wait)<0)break;
            fence103();
            if(transport.drain>=ZERO_DRAIN_BLOCKS || transport.fault || lunar_pipeline_error())continue;
            if(lunar_pipeline_wake_wait(0)<0)break;
        }
        if((uint32_t)(timer_get_ms()-started_ms)>SOAK_WATCHDOG_MS){task_fault103(10312);break;}
    }
    /* Normal instruments remain clocked at the same analog gain between notes.
       Keep the static ring alive; never use finished queue contexts in idle. */
    int off=-1,closed=-1;
    if(!transport.fault&&!lunar_pipeline_error()&&produced==TOTAL&&harvested==TOTAL&&
       transport.next==TOTAL&&transport.drain>=ZERO_DRAIN_BLOCKS) {
        unsigned flags;local_irq_save(flags);fence103();transport.idle=1;fence103();local_irq_restore(flags);
        uint32_t quiet=timer_get_ms();
        while((uint32_t)(timer_get_ms()-quiet)<250u&&!transport.fault)os_time_dly(1);
    } else {off=dac_off();closed=dac_close();}
    printf("LUNAR_DAC173 idle=%u idle_callbacks=%u gain_unchanged=1 clock_running=%u off_called=%u close_called=%u\n",
      transport.idle,transport.idle_callbacks,transport.idle,!transport.idle,!transport.idle);
    printf("LUNAR_DRAIN175 observations=%u seen=%u protocol_ticks_unchanged=1\n",drain_progress,observed_drain);
    fence103();
    while(harvested<produced&&!transport.fault&&!lunar_pipeline_error())if(harvest103()<0)break;
    printf("LUNAR_DAC103 end=1 produced=%u harvested=%u submitted=%u callbacks=%u drain=%u fault=%u backend=%u off=%d close=%d cb_max=%u irq_max=%u gap_max=%u late=%u gaps=%u ready_min=%u parent_unused=%u\n",
      produced,harvested,transport.next,transport.callbacks,transport.drain,transport.fault,lunar_pipeline_error(),off,closed,
      transport.cb_max,transport.irq_max,transport.gap_max,transport.late,transport.gaps,transport.ready_min,(unsigned)uxTaskGetStackHighWaterMark(NULL));
    for(unsigned c=0;c<4;++c)printf("LUNAR_DAC103_CASE case=%u blocks=%u hash=%08x p_mean=%u p_max=%u p_late=%u c_mean=%u c_max=%u c_late=%u\n",
      c,service[c].count,transport.case_hash[c],service[c].count?(unsigned)(service[c].p/service[c].count):0,service[c].pmax,service[c].plate,
      service[c].count?(unsigned)(service[c].c/service[c].count):0,service[c].cmax,service[c].clate);
    for(unsigned i=0;i<late_count && i<8u;++i)printf("LUNAR_LATE146 event=%u tag=%u p_ticks=%u c_ticks=%u\n",i,late_trace[i].tag,late_trace[i].p_ticks,late_trace[i].c_ticks);
    printf("LUNAR_LATE146 count=%u overflow=%u\n",late_count,late_count>8u?late_count-8u:0u);
    budget_report();
    printf("LUNAR_PREROLL161 phase=%u zeros=%u duration_ms=%u held_initial_outputs=8 pcm_discarded=0\n",preroll_phase,preroll_zeros,preroll_ms);
    printf("LUNAR_PIPELINE_SOAK cases=%u expected_cases=%u cycles=%u total=%u elapsed_ms=%u fold=%08x replay_required=1\n",transport.cases_checked,CASE_ORDINALS,SOAK_CYCLES,TOTAL,(uint32_t)(timer_get_ms()-started_ms),transport.case_fold);
    if(!lunar_pipeline_sdk_finish())return v110_failure(__LINE__);
    if(preroll_phase!=PRE_MUSIC||!preroll_zeros||transport.fault||lunar_pipeline_error()||!transport.idle||transport.idle_callbacks<100u||produced!=TOTAL||harvested!=TOTAL||transport.next!=TOTAL||transport.drain<ZERO_DRAIN_BLOCKS||transport.cases_checked!=CASE_ORDINALS||budget_overflow||transport.late||transport.gaps||transport.irq_max>=BUDGET)return v110_failure(__LINE__);
    for(unsigned c=0;c<4;++c)if(service[c].count!=SOAK_CYCLES*CASE_BLOCKS||service[c].plate||service[c].clate)return v110_failure(__LINE__);
    return 1;
}

int lunar_pipeline_dac_idle(void){fence103();return transport.idle!=0;}

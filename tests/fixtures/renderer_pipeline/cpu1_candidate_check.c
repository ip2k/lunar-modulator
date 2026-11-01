/* SPDX-License-Identifier: MIT. Real candidate + native adapter + common core. */
#define _POSIX_C_SOURCE 200809L
#define LUNAR_CPU1_CANDIDATE_HOST 1
#include "cpu1_candidate.h"
#include <assert.h>
#include <pthread.h>
#include <sched.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
static _Thread_local unsigned mock_cpu;
static _Thread_local uint32_t mock_icfg;
static cpu1_candidate candidate;
static cpu1_word raw_fault_claimed[2];
static _Atomic uint32_t regs[1280],vectors[128],divider;
static _Atomic unsigned reads,writes,releases,worker_created;
static _Atomic unsigned setup_bad,no_entry,late_entry,cleanup_bad,do_shutdown,hang_ready;
static _Atomic unsigned fail_write_at,fail_read_at,ambiguous_write;
static _Atomic unsigned write_failure_count,run_seen,callbacks;
static pthread_t worker_thread;
static struct timespec epoch;
static _Atomic unsigned manual;
static _Atomic uint32_t raw;
static uint32_t *unused_pointer;
static cpu1_word *reg_at(uint32_t address){
 if(address==C1_DIV)return &divider;
 if(address>=0x01eee000u && address<0x01eef400u && !(address&3u))return &regs[(address-0x01eee000u)/4u];
 if(address>=C1_VECTORS && address<C1_VECTORS+512u && !(address&3u))return &vectors[(address-C1_VECTORS)/4u];
 assert(!"unexpected MMIO address");return NULL;
}
static uint32_t peek(uint32_t a){return *reg_at(a);}
static void poke(uint32_t a,uint32_t v){*reg_at(a)=v;}
static int read32(void *ctx,uint32_t a,uint32_t *v){
 (void)ctx;if(++reads==fail_read_at)return 0;*v=peek(a);return 1;
}
static void *worker_main(void *unused){(void)unused;mock_cpu=1;mock_icfg=0;cpu1_candidate_secondary(&candidate);return NULL;}
static int write32(void *ctx,uint32_t a,uint32_t v){
 (void)ctx;unsigned n=++writes;
 int bad=fail_write_at==n;
 if(cleanup_bad && a==C1_DIV && v==0x12340000u && candidate.attempted)bad=1;
 if(bad){++write_failure_count;if(!ambiguous_write)return 0;}
 if(a==C1_ACCESS){assert(v==0xe7u);poke(a,peek(a)^1u);}
 else if(a==C1_DBG_CLR)poke(C1_DBG_MSG,peek(C1_DBG_MSG)&~v);
 else {
  if(a>=C1_VECTORS && a<C1_VECTORS+512u)assert(!(peek(C1_TOP)&4u));
  if(a>=C1_PC_H0 && a<=C1_PC_L1)assert(peek(C1_ACCESS)&1u);
  uint32_t prior=peek(a);poke(a,v);
  if(a==C1_CON && (prior&2u) && !(v&2u) && (v&8u)){
   assert(mock_cpu==0);++releases;
   if(!no_entry && !late_entry){assert(!worker_created);worker_created=1;assert(!pthread_create(&worker_thread,NULL,worker_main,NULL));}
  }
 }
 return !bad;
}
static unsigned cpu(void *ctx){(void)ctx;return mock_cpu;}
static uint32_t ticks(void *ctx){
 (void)ctx;if(manual)return raw;
 struct timespec now;assert(!clock_gettime(CLOCK_MONOTONIC,&now));
 uint64_t ns=(uint64_t)(now.tv_sec-epoch.tv_sec)*1000000000ull+(uint64_t)now.tv_nsec-(uint64_t)epoch.tv_nsec;
 return (uint32_t)(ns*24u/1000u);
}
static uint32_t ticks_callback(void){return ticks(NULL);}
static void mock_fence(void *ctx){(void)ctx;atomic_thread_fence(memory_order_seq_cst);}
static void pause_cpu(void *ctx){(void)ctx;if(!manual)sched_yield();}
static int irq_get(void *ctx,uint32_t *p){(void)ctx;*p=mock_icfg;return 1;}
static int irq_set(void *ctx,uint32_t p){(void)ctx;mock_icfg=p;return 1;}
static int registers(void *ctx,cpu1_registers *r){
 (void)ctx;*r=(cpu1_registers){0x01c12000u,0x01c12000u,0x01c14000u,mock_icfg};
 if(setup_bad)r->ssp=0x01c14008u;return 1;
}
static const cpu1_ops ops={NULL,read32,write32,cpu,ticks,mock_fence,pause_cpu,irq_get,irq_set,registers};
#define LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER "cpu1_candidate_mock_platform.h"
#include "renderer_pipeline_native.c"
static void native_delay(unsigned ms){
 if(mock_cpu==1 && (do_shutdown || s.exited))pthread_exit(NULL);
 if(!cpu1_candidate_delay(&candidate,ms))native_refuse(0xc103);
}
static void initialize(void){
 assert(!clock_gettime(CLOCK_MONOTONIC,&epoch));
 poke(C1_ACCESS,0);poke(C1_TOP,0x13570004u);poke(C1_DIV,0x12340000u);
 poke(C1_CON,2);poke(C1_DBG_EN,0x003f0040u);
 poke(C1_PC_H0,0x02070000u);poke(C1_PC_L0,0x02000120u);
 poke(C1_PC_H1,0x01c73000u);poke(C1_PC_L1,0x01c08000u);
 cpu1_layout l={0x02001000u,0x02002000u,0x02003000u,
  0x01c10000u,0x01c12000u,0x01c13000u,0x01c14000u,0x01c15000u,0x01c15400u,
  0x02000120u,0x02080000u,0x1234567u};
 assert(cpu1_candidate_prepare(&candidate,&ops,&l));
}
static void restored(void){
 assert(peek(C1_ACCESS)==0 && peek(C1_TOP)==0x13570004u);
 assert(peek(C1_DIV)==0x12340000u);
 assert(peek(C1_PC_H0)==0x02070000u && peek(C1_PC_L0)==0x02000120u);
 assert(peek(C1_PC_H1)==0x01c73000u && peek(C1_PC_L1)==0x01c08000u);
 assert(peek(C1_ENTRY)==candidate.layout.unexpected);
}
static struct {uint32_t tag;} arena[2];
static int consume(void *work,uint32_t tag,int16_t *pcm,lunar_pipeline_result_t *result){
 assert(candidate.launch_ok && !candidate.cleanup_failed && launch_context.command==N_RUN);
 restored();run_seen=1;assert(work==&arena[tag%2] && arena[tag%2].tag==tag);
 for(unsigned i=0;i<256;++i)pcm[i]=(int16_t)(tag+i);
 result->hash=tag+17u;++callbacks;return 1;
}
static int retire(void *work){assert(work==&arena[0] || work==&arena[1]);return 1;}
static void stream(void){
 assert(lunar_pipeline_bind(&arena[0],&arena[1],consume,retire)==1);
 for(uint32_t tag=0;tag<24u;++tag){
  void *work=NULL;const int16_t *pcm=NULL;const lunar_pipeline_result_t *result=NULL;
  lunar_pipeline_completion_t completion;assert(lunar_pipeline_reserve_work(tag,&work)==1);
  arena[tag%2].tag=tag;
  uint32_t p_start=ticks(NULL);
  uint32_t p_end=ticks(NULL);
  assert(lunar_pipeline_publish(tag,p_start,p_end)==1);
  int h=0,o=0;uint32_t start=ticks(NULL);
  while(!h || !o){
   if(!h)h=lunar_pipeline_harvest(&completion);
   if(!o)o=lunar_pipeline_output_acquire(tag,&pcm,&result);
   assert(h>=0 && o>=0 && ticks(NULL)-start<24000000u);sched_yield();
  }
  assert(result->hash==tag+17u && completion.tag==tag);
  for(unsigned i=0;i<256;++i)assert(pcm[i]==(int16_t)(tag+i));
  assert(lunar_pipeline_output_retire(tag)==1);
 }
 assert(lunar_pipeline_native_finish());
}
static void clock_checks(void){
 manual=1;raw=UINT32_MAX-100u;initialize();
 uint64_t elapsed=0;
 for(unsigned i=0;i<35u;++i){
  raw+=1440000000u;elapsed+=1440000000ull;
  mock_cpu=0;assert(cpu1_candidate_ms(&candidate)==elapsed/24000u);
  mock_cpu=1;assert(cpu1_candidate_ms(&candidate)==elapsed/24000u);
 }
 assert(candidate.clocks[0].ms==LUNAR_PIPELINE_LIFETIME_MS);
 assert(candidate.clocks[0].remainder==0 && candidate.clocks[1].remainder==0);
 candidate.clocks[1].ms=UINT32_MAX-1u;raw+=48000u;
 assert(cpu1_candidate_ms(&candidate)==0u);mock_cpu=0;
}
/* Exercise the actual common worker in this adapter TU with one permanently
 * owned SEALED job. Deterministic scheduling avoids racing fault injection with
 * a host thread: this is protocol setup, not a second worker implementation. */
static unsigned poison_clock_at,poison_clock_calls,poison_consumes;
static uint32_t poison_clock(void){
 if(++poison_clock_calls==poison_clock_at){native_refuse(0xc106);native_refuse(0xc107);}
 return poison_clock_calls;
}
static int poison_consume(void *w,uint32_t tag,int16_t *pcm,lunar_pipeline_result_t *r){
 (void)pcm;assert(w==&arena[0] && tag==0 && r->tag==0);
 assert(!lunar_pipeline_error());++poison_consumes;return 1;
}
static void *run_poison_worker(void *p){(void)p;mock_cpu=1;worker(NULL);return NULL;}
static void poison_checks(const char *mode){
 s.clock=poison_clock;s.bound=1;s.consume=poison_consume;
 works[0].state=SEALED;works[0].tag=0;works[0].work=&arena[0];
 unsigned raw_fault=strstr(mode,"_raw_fault")!=NULL;
 unsigned failed=strstr(mode,"_failed")!=NULL;
 if(raw_fault)raw_fault_claimed[1]=1;
 if(failed)candidate.failed=1;
 if(strstr(mode,"_clock_start") || !strcmp(mode,"poison_wait_clock") ||
    !strcmp(mode,"poison_publish_clock"))poison_clock_at=1;
 if(strstr(mode,"_clock_end"))poison_clock_at=2;
 if(!strncmp(mode,"poison_wait_",12)){
  uint32_t ticket=0;
  assert(lunar_pipeline_wait_check(&ticket)==-1);assert(ticket==0);
  assert(!poison_consumes && works[0].state==SEALED && outputs[0].state==FREE);
 }else if(!strcmp(mode,"poison_publish_clock")){
  works[0].state=PRODUCING;
  assert(lunar_pipeline_publish(0,1,2)==-1);
  assert(!s.produced && works[0].state==PRODUCING && outputs[0].state==FREE);
 }else if(!strcmp(mode,"poison_direct_step")){
  lunar_pipeline_refuse(0xc108);
  assert(worker_step()==-1);assert(!poison_consumes);
  assert(works[0].state==SEALED && outputs[0].state==FREE);
 }else{
  pthread_t t;assert(!pthread_create(&t,NULL,run_poison_worker,NULL));
  assert(!pthread_join(t,NULL));assert(s.exited && !s.consumed);
  assert(poison_consumes==(!strcmp(mode,"poison_worker_clock_end")?1u:0u));
  assert(works[0].state==(failed || raw_fault?SEALED:CONSUMING));
  assert(outputs[0].state==(failed || raw_fault?FREE:RESERVED));
 }
 uint32_t expected=failed || raw_fault?0xc104u:
  !strcmp(mode,"poison_direct_step")?0xc108u:0xc106u;
 assert(lunar_pipeline_error()==expected);
 assert(!lunar_pipeline_ready_outputs() && !s.harvested && !s.output_retired);
 assert(works[0].work==&arena[0] && !releases && !worker_created);
}
int main(int argc,char **argv){
 assert(argc==2);const char *mode=argv[1];(void)unused_pointer;
 if(!strcmp(mode,"clock")){clock_checks();goto done;}
 if(!strcmp(mode,"clock_fraction")){
  manual=1;raw=UINT32_MAX-10u;initialize();
  raw+=12000u;assert(cpu1_candidate_ms(&candidate)==0u);
  raw+=24000u;mock_cpu=1;assert(cpu1_candidate_ms(&candidate)==1u);
  raw+=12000u;mock_cpu=0;assert(cpu1_candidate_ms(&candidate)==2u);
  mock_cpu=1;assert(cpu1_candidate_ms(&candidate)==2u);
  assert(!candidate.clocks[0].remainder && !candidate.clocks[1].remainder);goto done;
 }
 initialize();
 if(!strncmp(mode,"poison_",7)){poison_checks(mode);goto done;}
 if(!strcmp(mode,"nested_irq")){
  uint32_t a,b;mock_icfg=0x1234ffefu;
  assert(cpu1_candidate_irq_save(&candidate,&a));assert(!(mock_icfg&0x100u));
  assert(cpu1_candidate_irq_save(&candidate,&b));assert(b==mock_icfg);
  assert(cpu1_candidate_irq_restore(&candidate,b));assert(!(mock_icfg&0x100u));
  assert(cpu1_candidate_irq_restore(&candidate,a));assert(mock_icfg==0x1234ffefu);goto done;
 }
 if(!strcmp(mode,"frozen_clock")){
  manual=1;assert(!cpu1_candidate_delay(&candidate,1));assert(candidate.failed);goto done;
 }
 if(!strcmp(mode,"fault_records")){
  mock_cpu=1;cpu1_candidate_fault(&candidate,1,2,3,4,5,6);
  cpu1_candidate_fault(&candidate,9,9,9,9,9,9);assert(candidate.faults[1].reti==2);
  mock_cpu=0;cpu1_candidate_fault(&candidate,7,8,9,10,11,12);
  assert(candidate.faults[0].valid && candidate.faults[1].valid && candidate.failed);
  assert(!writes && !releases);goto done;
 }
 if(!strcmp(mode,"wrong_core")){
  mock_cpu=1;assert(!cpu1_candidate_install_vectors(&candidate));
  assert(!cpu1_candidate_hold(&candidate));assert(!cpu1_candidate_early_hold(&ops));
  assert(!writes && !releases);goto done;
 }
 if(!strcmp(mode,"enabled_irq")){
  mock_icfg=0x100u;assert(!cpu1_candidate_install_vectors(&candidate));
  assert(candidate.failed && !writes && !releases);goto done;
 }
 if(!strcmp(mode,"early_hold")){
  poke(C1_DBG_MSG,0x003f1234u);uint32_t prior=0;
  assert(cpu1_candidate_early_hold_record(&ops,&prior));assert(prior==0x003f1234u);
  assert(cpu1_candidate_early_hold(&ops));assert(peek(C1_CON)==2u);
  assert(peek(C1_DBG_EN)==0x003f0040u && !peek(C1_ACCESS));goto done;
 }
 if(!strncmp(mode,"invalid_",8)){
  static cpu1_candidate invalid;cpu1_layout l=candidate.layout;
  unsigned which=(unsigned)strtoul(mode+8,NULL,10);
  if(which==0)l.nonce=0;
  if(which==1)l.entry=l.executable_hi;
  if(which==2)l.exception=l.executable_lo-2u;
  if(which==3)l.unexpected|=1u;
  if(which==4)l.user_lo=0x01c07ff8u;
  if(which==5)l.user_hi=l.user_lo;
  if(which==6)l.super_lo=l.user_hi-8u;
  if(which==7)l.super_hi=l.super_lo;
  if(which==8)l.fault_lo=l.super_hi-8u;
  if(which==9)l.fault_hi=l.fault_lo;
  if(which==10)l.fault_hi=0x01c7fd58u;
  if(which==11)l.fault_lo|=4u;
  assert(!cpu1_candidate_prepare(&invalid,&ops,&l));assert(invalid.failed && !writes && !releases);goto done;
 }
 if(!strncmp(mode,"vector_",7)){
  ambiguous_write=mode[7]=='a';fail_write_at=(unsigned)strtoul(mode+9,NULL,10);
  assert(!cpu1_candidate_install_vectors(&candidate));
  assert(candidate.failed && !candidate.vectors && !candidate.attempted && !releases);
  assert(!cpu1_candidate_launch(&candidate,NULL,NULL));goto done;
 }
 assert(cpu1_candidate_install_vectors(&candidate));
 assert(peek(C1_IRQ0)==0xf0u && peek(C1_IRQ0+60u)==0u && peek(C1_ENTRY)==candidate.layout.unexpected);
 if(!strcmp(mode,"prepoison"))lunar_pipeline_refuse(77);
 if(!strcmp(mode,"bad_setup"))setup_bad=1;
 if(!strcmp(mode,"no_entry"))no_entry=1;
 if(!strcmp(mode,"late_entry"))late_entry=1;
 if(!strcmp(mode,"cleanup_failure"))cleanup_bad=1;
 if(!strcmp(mode,"stalled_ready"))hang_ready=1;
 if(!strcmp(mode,"stalled_launch")){manual=1;no_entry=1;}
 if(!strncmp(mode,"write_",6)){
  fail_write_at=writes+(unsigned)strtoul(mode+8,NULL,10);ambiguous_write=mode[6]=='a';no_entry=1;
 }
 if(!strncmp(mode,"read_",5)){fail_read_at=reads+(unsigned)strtoul(mode+5,NULL,10);no_entry=1;}
 assert(lunar_pipeline_native_primary_irq_ready() || !strcmp(mode,"prepoison"));
 int ok=lunar_pipeline_native_start(ticks_callback);
 if(!strcmp(mode,"stream")){
  assert(ok);stream();assert(run_seen && callbacks==24u);restored();
  assert(!lunar_pipeline_native_start(ticks_callback));assert(releases==1u);
 }else if(!strcmp(mode,"lifetime")){
  assert(ok);candidate.clocks[0].ms=LUNAR_PIPELINE_LIFETIME_MS;
  uint32_t ticket=0;assert(lunar_pipeline_wait_check(&ticket)==-1);assert(!callbacks);
 }else{
  assert(!ok && !callbacks && !run_seen);
  if(!strcmp(mode,"late_entry")){mock_cpu=1;cpu1_candidate_secondary(&candidate);mock_cpu=0;assert(!launch_context.ready);}
  if(!strcmp(mode,"cleanup_failure"))assert(candidate.cleanup_failed);
  if(!candidate.cleanup_failed)restored();
  unsigned before=releases;assert(!lunar_pipeline_native_start(ticks_callback));assert(releases==before);
 }
 do_shutdown=1;
 if(worker_created){assert(!pthread_join(worker_thread,NULL));worker_created=0;}
 assert(!lunar_pipeline_native_hardware_admitted());
done:
 printf("CPU1_CANDIDATE PASS %s writes=%u releases=%u callbacks=%u\n",mode,writes,releases,callbacks);return 0;
}

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
static _Atomic uint32_t regs[1280],vectors[128],divider;
static _Atomic unsigned reads,writes,releases,worker_created;
static _Atomic unsigned setup_bad,no_entry,late_entry,cleanup_bad,do_shutdown;
static _Atomic unsigned fail_write_at,ambiguous_write;
static _Atomic unsigned write_failure_count,run_seen,callbacks;
static pthread_t worker_thread;
static struct timespec epoch;
static unsigned manual;
static uint32_t raw;
static uint32_t *unused_pointer;
static cpu1_word *reg_at(uint32_t address){
 if(address==C1_DIV)return &divider;
 if(address>=0x01eee000u && address<0x01eef400u && !(address&3u))return &regs[(address-0x01eee000u)/4u];
 if(address>=C1_VECTORS && address<C1_VECTORS+512u && !(address&3u))return &vectors[(address-C1_VECTORS)/4u];
 assert(!"unexpected MMIO address");return NULL;
}
static uint32_t peek(uint32_t a){return *reg_at(a);}
static void poke(uint32_t a,uint32_t v){*reg_at(a)=v;}
static int read32(void *ctx,uint32_t a,uint32_t *v){(void)ctx;++reads;*v=peek(a);return 1;}
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
#define LUNAR_NATIVE_PIPELINE_TEST_PLATFORM_HEADER "cpu1_candidate_platform.h"
#include "renderer_pipeline_native.c"
static void native_delay(unsigned ms){
 if(mock_cpu==1 && (do_shutdown || s.exited))pthread_exit(NULL);
 if(!cpu1_candidate_delay(&candidate,ms))lunar_pipeline_refuse(0xc103);
}
static void initialize(void){
 assert(!clock_gettime(CLOCK_MONOTONIC,&epoch));
 poke(C1_ACCESS,0);poke(C1_TOP,0x13570004u);poke(C1_DIV,0x12340000u);
 poke(C1_CON,2);poke(C1_DBG_EN,0x003f0040u);
 poke(C1_PC_H0,0x02070000u);poke(C1_PC_L0,0x02000120u);
 poke(C1_PC_H1,0x01c73000u);poke(C1_PC_L1,0x01c08000u);
 cpu1_layout l={0x02001000u,0x02002000u,0x02003000u,
  0x01c10000u,0x01c12000u,0x01c13000u,0x01c14000u,0x02000120u,0x02080000u,0x1234567u};
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
  arena[tag%2].tag=tag;assert(lunar_pipeline_publish(tag,ticks(NULL),ticks(NULL))==1);
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
int main(int argc,char **argv){
 assert(argc==2);const char *mode=argv[1];(void)unused_pointer;
 if(!strcmp(mode,"clock")){clock_checks();goto done;}
 initialize();
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
  mock_cpu=1;assert(!cpu1_candidate_install_vectors(&candidate));assert(!writes && !releases);goto done;
 }
 if(!strcmp(mode,"early_hold")){
  assert(cpu1_candidate_early_hold(&ops));assert(peek(C1_CON)==2u);
  assert(peek(C1_DBG_EN)==0x003f0040u && !peek(C1_ACCESS));goto done;
 }
 assert(cpu1_candidate_install_vectors(&candidate));
 if(!strcmp(mode,"prepoison"))lunar_pipeline_refuse(77);
 if(!strcmp(mode,"bad_setup"))setup_bad=1;
 if(!strcmp(mode,"no_entry"))no_entry=1;
 if(!strcmp(mode,"late_entry"))late_entry=1;
 if(!strcmp(mode,"cleanup_failure"))cleanup_bad=1;
 if(!strncmp(mode,"partial_",8)){
  fail_write_at=writes+(unsigned)strtoul(mode+8,NULL,10);ambiguous_write=1;no_entry=1;
 }
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
  if(strcmp(mode,"cleanup_failure"))restored();else assert(candidate.cleanup_failed);
  unsigned before=releases;assert(!lunar_pipeline_native_start(ticks_callback));assert(releases==before);
 }
 do_shutdown=1;
 if(worker_created){assert(!pthread_join(worker_thread,NULL));worker_created=0;}
 assert(!lunar_pipeline_native_hardware_admitted());
done:
 printf("CPU1_CANDIDATE PASS %s writes=%u releases=%u callbacks=%u\n",mode,writes,releases,callbacks);return 0;
}

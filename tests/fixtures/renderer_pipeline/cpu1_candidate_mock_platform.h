/* SPDX-License-Identifier: MIT. Actual candidate binding, mocked hardware only. */
typedef cpu1_word lunar_pipeline_word_t;
#define LUNAR_PIPELINE_PORT_DEFINED 1
#define LUNAR_PIPELINE_CORE_COLD
static void port_fence(void){atomic_thread_fence(memory_order_seq_cst);}
static unsigned native_cpu(void){return mock_cpu;}
static void native_refuse(uint32_t);
/* Match both actual target native_ms poison conditions. raw_fault_claimed
 * models the assembly-owned claimed word, without executing target assembly. */
static uint32_t native_ms(void){
 if(candidate.failed || raw_fault_claimed[0] || raw_fault_claimed[1])native_refuse(0xc104);
 return cpu1_candidate_ms(&candidate);
}
static unsigned native_irq_save(void){uint32_t p=0;(void)cpu1_candidate_irq_save(&candidate,&p);return p;}
static void native_irq_restore(unsigned p){(void)cpu1_candidate_irq_restore(&candidate,p);}
static void native_delay(unsigned);
static int native_launch_allowed(void){return mock_cpu==0 && candidate.prepared && candidate.vectors && !candidate.attempted && !candidate.failed;}
static int native_launch(void (*entry)(void *),void *arg){return cpu1_candidate_launch(&candidate,entry,arg)?0:-1;}
static int native_worker_setup(void){
 int ok=cpu1_candidate_worker_setup(&candidate);
 if(hang_ready){
  raw=ticks(NULL);manual=1;
  while(!do_shutdown)sched_yield();
  return 0;
 }
 return ok;
}
static uint32_t native_stack_unused(void){return 8192u;}

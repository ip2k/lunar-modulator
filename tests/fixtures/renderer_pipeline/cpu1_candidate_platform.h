/* SPDX-License-Identifier: MIT. Actual candidate binding, mocked hardware only. */
typedef cpu1_word lunar_pipeline_word_t;
#define LUNAR_PIPELINE_PORT_DEFINED 1
#define LUNAR_PIPELINE_CORE_COLD
static void port_fence(void){atomic_thread_fence(memory_order_seq_cst);}
static unsigned native_cpu(void){return mock_cpu;}
static uint32_t native_ms(void){return cpu1_candidate_ms(&candidate);}
static unsigned native_irq_save(void){uint32_t p=0; if(!cpu1_candidate_irq_save(&candidate,&p))lunar_pipeline_refuse(0xc101);return p;}
static void native_irq_restore(unsigned p){if(!cpu1_candidate_irq_restore(&candidate,p))lunar_pipeline_refuse(0xc102);}
static void native_delay(unsigned);
static int native_launch_allowed(void){return mock_cpu==0 && candidate.prepared && candidate.vectors && !candidate.attempted && !candidate.failed;}
static int native_launch(void (*entry)(void *),void *arg){return cpu1_candidate_launch(&candidate,entry,arg)?0:-1;}
static int native_worker_setup(void){return cpu1_candidate_worker_setup(&candidate);}
static uint32_t native_stack_unused(void){return 8192u;}

/* SPDX-License-Identifier: MPL-2.0. Unadmitted freestanding target extension. */
#include "cpu1_candidate_target.h"
typedef cpu1_word lunar_pipeline_word_t;
#define LUNAR_PIPELINE_PORT_DEFINED 1
#define LUNAR_PIPELINE_CORE_COLD
/* Aligned volatile words + csync are an explicit target hypothesis, NOT a C11
 * or silicon memory-model guarantee. Qualification of this exact image is open. */
static void port_fence(void) { __asm__ volatile("csync" ::: "memory"); }
static unsigned native_cpu(void) { return lunar_cpu1_candidate_cpu(); }
static void native_refuse(uint32_t);
static uint32_t native_ms(void) {
    if(lunar_cpu1_candidate.failed || lunar_cpu1_candidate_faulted())native_refuse(0xc104);
    return cpu1_candidate_ms(&lunar_cpu1_candidate);
}
static unsigned native_irq_save(void) {
    uint32_t prior=0;
    /* Failure latches backend poison. Do not recurse through native_refuse:
     * common refuse itself saves/restores IRQ state using these hooks. */
    (void)cpu1_candidate_irq_save(&lunar_cpu1_candidate,&prior);
    return prior;
}
static void native_irq_restore(unsigned prior) {
    (void)cpu1_candidate_irq_restore(&lunar_cpu1_candidate,prior);
}
static void native_delay(unsigned ms) {
    if(!cpu1_candidate_delay(&lunar_cpu1_candidate,ms))native_refuse(0xc103);
}
static uint32_t native_stack_unused(void) {
    uint32_t unused=lunar_cpu1_candidate_stack_unused();
    if(lunar_cpu1_candidate.failed)native_refuse(0xc105);
    return unused;
}
static int native_launch_allowed(void) {
    return native_cpu()==0 && lunar_cpu1_candidate.prepared && lunar_cpu1_candidate.vectors &&
        !lunar_cpu1_candidate.attempted && !lunar_cpu1_candidate.failed && !lunar_cpu1_candidate_faulted();
}
static int native_launch(void (*entry)(void *),void *arg) {
    return cpu1_candidate_launch(&lunar_cpu1_candidate,entry,arg)?0:-1;
}
static int native_worker_setup(void) { return lunar_cpu1_candidate_target_setup(); }

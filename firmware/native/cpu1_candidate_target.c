/* SPDX-License-Identifier: MPL-2.0.
 * Small freestanding adapter for the pinned BSP primitives; see UPSTREAM.md.
 * No SDK, clock-tree, cache-way, voltage, flash, reset or peripheral-output API.
 */
#include "cpu1_candidate_target.h"
#include "renderer_pipeline_native.h"

cpu1_candidate lunar_cpu1_candidate __attribute__((section(".candidate_state"),aligned(64)));
/* Assembly captures before switching to a dedicated emergency stack. A nested
 * exception sees claimed!=0 and parks without overwriting its first record. */
typedef struct {
    volatile uint32_t claimed,vector,reti,rete,sp,usp,ssp,icfg;
    uint32_t reserved[8];
} raw_fault;
raw_fault lunar_cpu1_raw_fault[2] __attribute__((section(".candidate_fault"),aligned(64)));
_Static_assert(sizeof(raw_fault)==64,"assembly raw-fault stride");
extern uint32_t _cpu1_user_lo[],_cpu1_user_top[],_cpu1_super_lo[],_cpu1_super_top[];
extern uint32_t _cpu1_guard_lo[],_cpu1_guard_middle[],_cpu1_guard_hi[];
extern uint32_t _cpu0_guard_lo[],_cpu0_guard_middle[],_cpu0_guard_hi[];
extern uint32_t _cpu0_fault_guard[],_cpu1_fault_guard[];
extern uint32_t _candidate_text_lo[],_candidate_text_hi[];
extern void lunar_cpu1_entry(void),lunar_cpu1_exception(void),lunar_cpu1_unexpected(void);

static int target_read(void *ctx,uint32_t address,uint32_t *value) {
    (void)ctx; *value=*(volatile uint32_t *)(uintptr_t)address; return 1;
}
static int target_write(void *ctx,uint32_t address,uint32_t value) {
    (void)ctx; *(volatile uint32_t *)(uintptr_t)address=value; return 1;
}
unsigned lunar_cpu1_candidate_cpu(void) {
    uint32_t cpu; __asm__ volatile("%0 = cnum":"=r"(cpu)); return cpu;
}
static unsigned target_cpu(void *ctx) { (void)ctx; return lunar_cpu1_candidate_cpu(); }
uint32_t lunar_cpu1_candidate_ticks(void) { return *(volatile uint32_t *)0x10804u; }
static uint32_t target_ticks(void *ctx) { (void)ctx; return lunar_cpu1_candidate_ticks(); }
static void target_fence(void *ctx) { (void)ctx; __asm__ volatile("csync" ::: "memory"); }
static void target_pause(void *ctx) { (void)ctx; __asm__ volatile("nop" ::: "memory"); }
static int target_irq_get(void *ctx,uint32_t *value) {
    (void)ctx; __asm__ volatile("%0 = icfg":"=r"(*value)); return 1;
}
static int target_irq_set(void *ctx,uint32_t value) {
    (void)ctx; __asm__ volatile("icfg = %0"::"r"(value):"memory"); return 1;
}
static int target_registers(void *ctx,cpu1_registers *r) {
    (void)ctx;
    __asm__ volatile("%0 = sp":"=r"(r->sp));
    __asm__ volatile("%0 = usp":"=r"(r->usp));
    __asm__ volatile("%0 = ssp":"=r"(r->ssp));
    __asm__ volatile("%0 = icfg":"=r"(r->icfg)); return 1;
}
static const cpu1_ops target_ops={0,target_read,target_write,target_cpu,target_ticks,
    target_fence,target_pause,target_irq_get,target_irq_set,target_registers};
int lunar_cpu1_candidate_target_early_hold(uint32_t *prior_debug) {
    /* target_ops and its callees are XIP constants; no C storage read/write. */
    return cpu1_candidate_early_hold_record(&target_ops,prior_debug);
}
static void mark(uint32_t *lo,uint32_t *hi) {
    while(lo<hi)*lo++=CPU1_CANDIDATE_MARK;
}
static int guard(const uint32_t *lo) {
    for(unsigned i=0;i<16;++i)if(lo[i]!=CPU1_CANDIDATE_MARK)return 0;
    return 1;
}
static int guards(void) {
    return guard(_cpu1_guard_lo) && guard(_cpu1_guard_middle) && guard(_cpu1_guard_hi) &&
        guard(_cpu0_guard_lo) && guard(_cpu0_guard_middle) && guard(_cpu0_guard_hi) &&
        guard(_cpu0_fault_guard) && guard(_cpu1_fault_guard);
}
int lunar_cpu1_candidate_target_prepare(void) {
    if(lunar_cpu1_candidate_cpu()!=0)return 0;
    mark(_cpu1_user_lo,_cpu1_user_top);mark(_cpu1_super_lo,_cpu1_super_top);
    mark(_cpu1_guard_lo,_cpu1_guard_lo+16);mark(_cpu1_guard_middle,_cpu1_guard_middle+16);
    mark(_cpu1_guard_hi,_cpu1_guard_hi+16);mark(_cpu0_guard_lo,_cpu0_guard_lo+16);
    mark(_cpu0_guard_middle,_cpu0_guard_middle+16);mark(_cpu0_guard_hi,_cpu0_guard_hi+16);
    mark(_cpu0_fault_guard,_cpu0_fault_guard+16);mark(_cpu1_fault_guard,_cpu1_fault_guard+16);
    cpu1_layout layout={
        (uint32_t)(uintptr_t)lunar_cpu1_entry,(uint32_t)(uintptr_t)lunar_cpu1_exception,
        (uint32_t)(uintptr_t)lunar_cpu1_unexpected,
        (uint32_t)(uintptr_t)_cpu1_user_lo,(uint32_t)(uintptr_t)_cpu1_user_top,
        (uint32_t)(uintptr_t)_cpu1_super_lo,(uint32_t)(uintptr_t)_cpu1_super_top,
        (uint32_t)(uintptr_t)_candidate_text_lo,(uint32_t)(uintptr_t)_candidate_text_hi,
        lunar_cpu1_candidate_ticks()^0xc101b007u
    };
    if(!layout.nonce)layout.nonce=1;
    if(!cpu1_candidate_prepare(&lunar_cpu1_candidate,&target_ops,&layout) ||
       !cpu1_candidate_install_vectors(&lunar_cpu1_candidate))return 0;
    return lunar_pipeline_native_primary_irq_ready();
}
int lunar_cpu1_candidate_target_setup(void) {
    if(!guards() || lunar_cpu1_candidate_faulted()) {
        lunar_cpu1_candidate.failed=1;target_fence(0);return 0;
    }
    return cpu1_candidate_worker_setup(&lunar_cpu1_candidate);
}
int lunar_cpu1_candidate_faulted(void) {
    target_fence(0);
    return lunar_cpu1_raw_fault[0].claimed || lunar_cpu1_raw_fault[1].claimed;
}
uint32_t lunar_cpu1_candidate_stack_unused(void) {
    if(lunar_cpu1_candidate_cpu()!=1 || !guards()) {
        lunar_cpu1_candidate.failed=1;target_fence(0);return 0;
    }
    const volatile uint32_t *p=_cpu1_user_lo;
    while(p<_cpu1_user_top && *p==CPU1_CANDIDATE_MARK)++p;
    return (uint32_t)(p-_cpu1_user_lo)*4u;
}
static void park(void) __attribute__((noreturn));
static void park(void) { for(;;)__asm__ volatile("csync" ::: "memory"); }
void lunar_cpu1_candidate_secondary(void) {
    cpu1_candidate_secondary(&lunar_cpu1_candidate);park();
}
void lunar_cpu1_candidate_fault_c(void) {
    unsigned cpu=lunar_cpu1_candidate_cpu();
    if(cpu>1)park();
    volatile raw_fault *raw=&lunar_cpu1_raw_fault[cpu];
    uint32_t emu=*(volatile uint32_t *)(uintptr_t)(cpu?0x01eef2d4u:0x01eef0d4u);
    uint32_t debug=*(volatile uint32_t *)C1_DBG_MSG;
    cpu1_candidate_fault(&lunar_cpu1_candidate,raw->vector,raw->reti,raw->rete,raw->sp,emu,debug);
    /* Raw fault preserves the original USP/SSP/ICFG. The ordinary record's
     * SSP is the emergency stack used by this C recorder, not the fault SSP. */
    park();
}

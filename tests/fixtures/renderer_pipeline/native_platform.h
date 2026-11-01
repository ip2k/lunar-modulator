/* SPDX-License-Identifier: MIT. Atomic host contract, never target admission. */
#include "sdk_shim.h"
static int mode_setup_fail,mode_hold_setup,mode_no_entry,mode_launch_fail;
static _Atomic unsigned setup_arrived, release_setup, setup_finished;
static unsigned launch_calls;
static int mode_bad_argument,mode_late_launch_fail,mode_deadline;
static unsigned native_cpu(void) { return host_cpu; }
static uint32_t native_ms(void) { return timer_get_ms(); }
static unsigned native_irq_save(void) { return 0; }
static void native_irq_restore(unsigned flags) { (void)flags; }
static void native_delay(unsigned ticks) { os_time_dly(ticks); }
static int native_launch_allowed(void) { return 1; }
static int native_launch(void (*entry)(void *),void *arg) {
    ++launch_calls;
    host_entry=entry;host_argument=arg;
    if(mode_bad_argument)arg=NULL;
    if(mode_launch_fail)return -1;
    if(mode_no_entry)return 0;
    int r=os_task_create_static(entry,arg,0,0,0,"native-host",NULL);
    return mode_late_launch_fail ? -1 : r;
}
static int native_worker_setup(void) {
    setup_arrived=1;
    while(mode_hold_setup && !release_setup)os_time_dly(1);
    if(mode_deadline)host_ms_offset+=LUNAR_NATIVE_STARTUP_MS;
    setup_finished=1;
    return !mode_setup_fail;
}
static uint32_t native_stack_unused(void) { return 0; }

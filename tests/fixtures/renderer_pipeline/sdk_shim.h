/* Private pthread SDK shim: protocol semantics only, no target timing claim. */
#ifndef LUNAR_PIPELINE_PIPELINE_HOST_SHIM_H
#define LUNAR_PIPELINE_PIPELINE_HOST_SHIM_H
#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdatomic.h>
#include <pthread.h>
#include <time.h>
#include <errno.h>
typedef struct { unsigned unused; } StaticTask_t;
static _Thread_local unsigned host_cpu;
static struct timespec host_epoch;
static pthread_t host_worker;
static int host_created;
static void (*host_entry)(void *);
static void *host_argument;
static uint64_t host_ns(void) {
    struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);
    return (uint64_t)(t.tv_sec-host_epoch.tv_sec)*UINT64_C(1000000000)+
        (uint64_t)t.tv_nsec-(uint64_t)host_epoch.tv_nsec;
}
static uint32_t host_clock(void) { return (uint32_t)(host_ns()*24u/1000u); }
static unsigned timer_get_ms(void) { return (unsigned)(host_ns()/1000000u); }
static unsigned current_cpu_id(void) { return host_cpu; }
static void os_time_dly(unsigned ticks) {
    /* One host ms per fake tick keeps startup/parking bounded. NOT SDK cadence. */
    struct timespec t={(time_t)(ticks/1000u),(long)(ticks%1000u)*1000000L};
    while(nanosleep(&t,&t) && errno==EINTR){}
}
static unsigned uxTaskGetStackHighWaterMark(void *p) { (void)p;return 0; }
static void *host_thread_entry(void *unused) {
    (void)unused;host_cpu=1;host_entry(host_argument);return NULL;
}
static int os_task_create_static(void (*entry)(void *),void *arg,unsigned priority,
        unsigned stack,unsigned queue,const char *name,void *memory) {
    (void)priority;(void)stack;(void)queue;(void)name;(void)memory;
    host_entry=entry;host_argument=arg;
    int r=pthread_create(&host_worker,NULL,host_thread_entry,NULL);
    if(!r)host_created=1;
    return r;
}
static void host_cleanup(void) {
    if(host_created){pthread_cancel(host_worker);pthread_join(host_worker,NULL);host_created=0;}
}
/* Private host semaphore model. No target ISR/scheduling/timing claim. */
#include <sched.h>
typedef struct { pthread_mutex_t mutex; pthread_cond_t cond; unsigned count; } OS_SEM;
static int os_sem_create(OS_SEM *sem,unsigned count) {
    if(count>255u)return -1;
    if(pthread_mutex_init(&sem->mutex,NULL)||pthread_cond_init(&sem->cond,NULL))return -1;
    sem->count=count;return 0;
}
static int os_sem_accept(OS_SEM *sem) {
    int r=11;pthread_mutex_lock(&sem->mutex);
    if(sem->count){--sem->count;r=0;}
    pthread_mutex_unlock(&sem->mutex);return r;
}
static int os_sem_post(OS_SEM *sem) {
    int r=-14;pthread_mutex_lock(&sem->mutex);
    if(sem->count<255u){++sem->count;pthread_cond_signal(&sem->cond);r=0;}
    pthread_mutex_unlock(&sem->mutex);return r;
}
static void pipeline_host_unlock(void *p){pthread_mutex_unlock((pthread_mutex_t *)p);}
static int os_sem_pend(OS_SEM *sem,unsigned ticks) {
    int r=0;struct timespec until;clock_gettime(CLOCK_REALTIME,&until);
    until.tv_sec+=ticks/1000u;until.tv_nsec+=(long)(ticks%1000u)*1000000L;
    if(until.tv_nsec>=1000000000L){++until.tv_sec;until.tv_nsec-=1000000000L;}
    pthread_mutex_lock(&sem->mutex);
    pthread_cleanup_push(pipeline_host_unlock,&sem->mutex);
    while(!sem->count && !r)r=ticks?pthread_cond_timedwait(&sem->cond,&sem->mutex,&until):pthread_cond_wait(&sem->cond,&sem->mutex);
    if(sem->count){--sem->count;r=0;}else r=11;
    pthread_cleanup_pop(1);
    return r;
}
static void vPortYield(void){sched_yield();}

#define local_irq_save(flags) do { (flags)=0; } while(0)
#define local_irq_restore(flags) ((void)(flags))
#endif

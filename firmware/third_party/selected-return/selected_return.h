/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments
 * Offline selected-diagnostic return proof, derived from Dinghy source facts.
 * Leo Kuroshita (@kurogedelic), Hügelton Instruments; see provenance note.
 * No physical watchdog lease, target execution or hardware admission is supplied.
 */
#ifndef LUNAR_SELECTED_RETURN_H
#define LUNAR_SELECTED_RETURN_H
#if !defined(LUNAR_SELECTED_RETURN_OFFLINE_PROOF) || LUNAR_SELECTED_RETURN_OFFLINE_PROOF != 1
#error "selected return is offline proof only"
#endif
#if defined(LUNAR_SELECTED_RETURN_PI32V2_BINDING)
#if LUNAR_SELECTED_RETURN_PI32V2_BINDING != 1 || defined(LUNAR_SELECTED_RETURN_FAKE_MMIO)
#error "target and portable fake bindings are mutually exclusive"
#endif
#if !defined(__PI32V2__) && !defined(LUNAR_SELECTED_RETURN_TARGET_INJECTED)
#error "target compiler or explicit injected target test required"
#endif
#if defined(__PI32V2__) && defined(LUNAR_SELECTED_RETURN_TARGET_INJECTED)
#error "injected target binding is host only"
#endif
#if defined(LUNAR_SELECTED_RETURN_TARGET_INJECTED) && LUNAR_SELECTED_RETURN_TARGET_INJECTED != 1
#error "injected target selection must equal one"
#endif
/* CPU0 exception handlers never resume the interrupted owner. Volatile aligned
 * scalar accesses make its shared state compiler-visible; this is not C11
 * thread synchronization, CPU1 support or a cache/exception timing proof. */
#define LUNAR_SR_SHARED volatile
#else
#if !defined(LUNAR_SELECTED_RETURN_FAKE_MMIO) || LUNAR_SELECTED_RETURN_FAKE_MMIO != 1
#error "selected return needs fake MMIO"
#endif
#ifdef __PI32V2__
#error "target binding is not admitted"
#endif
#define LUNAR_SR_SHARED
#endif
#include <stdint.h>
#define LUNAR_SR_DEADLINE_TICKS 480000000u
#define LUNAR_SR_MAILBOX_BEGIN 0x01c7fd80u
#define LUNAR_SR_MAILBOX_BYTES 16u
#define LUNAR_SR_MAILBOX_END (LUNAR_SR_MAILBOX_BEGIN+LUNAR_SR_MAILBOX_BYTES)
_Static_assert(LUNAR_SR_MAILBOX_END==0x01c7fd90u, "exact mailbox extent");
_Static_assert(LUNAR_SR_MAILBOX_BEGIN>=0x01c7fd50u && LUNAR_SR_MAILBOX_END<=0x01c7fe00u,
               "outside retained-state ceiling and below vectors");
enum { LUNAR_SR_FRESH, LUNAR_SR_BOOTSTRAP, LUNAR_SR_ARMED,
       LUNAR_SR_RUNNING, LUNAR_SR_TERMINAL };
enum { LUNAR_SR_APP_READY=1, LUNAR_SR_LCD_READY, LUNAR_SR_IO_READY, LUNAR_SR_MAIN };
enum { LUNAR_SR_QUALIFICATION=1, LUNAR_SR_CLOCK, LUNAR_SR_MAILBOX,
       LUNAR_SR_WATCHDOG, LUNAR_SR_P33, LUNAR_SR_INIT, LUNAR_SR_PHASE,
       LUNAR_SR_DEADLINE, LUNAR_SR_FAULT, LUNAR_SR_REENTRY };
/* Private typed port. It has no arbitrary address, reset or MMIO operation.
 * Portable fake and unqualified target candidate are mutually exclusive.
 * Physical use requires separate qualification/source/codegen review.
 * Single CPU0 main owner, no other P33 user, CPU1 or OS threads. halt must not
 * return (the fake uses longjmp); a returning halt traps, never resumes work.
 * mailbox is exactly the borrowed 16-byte object, never a 128-byte clear area.
 */
typedef struct {
  void *context;
  uint32_t (*timer4_con)(void *), (*timer4_prd)(void *), (*timer4_count)(void *);
  uint32_t (*icfg_read)(void *);
  void (*icfg_write)(void *,uint32_t);
  uint32_t (*p33_con_read)(void *);
  void (*p33_con_write)(void *,uint32_t);
  uint8_t (*p33_dat_read)(void *);
  void (*p33_dat_write)(void *,uint8_t);
  volatile uint8_t (*mailbox)[LUNAR_SR_MAILBOX_BYTES];
  void (*mailbox_publish_barrier)(void *); /* target csync is UNBOUND */
  void (*halt)(void *);
} lunar_selected_return_io_t;
/* Explicit OFFLINE assumptions, not source-proven silicon facts. All three
 * qualification flags must be exactly 1; no default qualifies. The caller
 * must separately establish write guards, timer ownership, stable readback
 * semantics/reset mode and a measured watchdog lease. Selector has no implied
 * seconds value. Poll count/phase interval are named offline parameters only.
 */
typedef struct {
  uint32_t timer4_exclusive,mailbox_write_qualified,watchdog_qualified;
  uint32_t watchdog_selector,lease_ticks,max_phase_ticks,byte_poll_limit;
} lunar_selected_return_qualification_t;
typedef struct {
  const lunar_selected_return_io_t * LUNAR_SR_SHARED io;
  lunar_selected_return_qualification_t qualification;
  LUNAR_SR_SHARED uint32_t state,first_error,backstop_armed,origin,last_tick,next_phase;
  LUNAR_SR_SHARED uint32_t p33_owned,p33_bytes,failed_byte,reset_attempted;
} lunar_selected_return_t;
#undef LUNAR_SR_SHARED
_Static_assert(sizeof(uint32_t)==4 && _Alignof(lunar_selected_return_t)>=4,
               "aligned 32-bit fault-shared scalar storage");
/* Fresh zeroed permanent object/port/mailbox only; never reset/reinitialize it.
 * Returns 0 only after qualification, exact marker readback, watchdog arm and
 * one ordered origin sample AFTER arm. Before that is an unsupported bootstrap
 * window. Invalid pointer/port arguments return -1 without hardware access;
 * that object is unusable. Semantic refusal halts terminal, never starts app.
 */
int lunar_selected_return_prepare(lunar_selected_return_t *,
    const lunar_selected_return_io_t *,const lunar_selected_return_qualification_t *);
/* Report completed APP, LCD, IO phases once in order, then each MAIN iteration.
 * Call before/after bounded risky work as the future startup contract requires.
 * A new qualified advancing tick within max_phase and a successful phase are
 * required for each feed. Check deadline BEFORE feed. Missed full counter wraps
 * are not detected by modular arithmetic; separately qualified lease covers
 * hangs. No call from Timer5, ALNK, delays or fault handlers.
 */
int lunar_selected_return_progress(lunar_selected_return_t *,unsigned phase,int healthy);
/* First/nested fault: sticky terminal, IRQs disabled, no P33, waits for the
 * prearmed backstop through halt. This cannot undo a byte already transmitted.
 */
_Noreturn void lunar_selected_return_fault(lunar_selected_return_t *,uint32_t reason);
#endif

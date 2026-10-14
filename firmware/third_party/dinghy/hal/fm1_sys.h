/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* FM-1 system HAL: P33 access, watchdog, reset reason, reboot / UBOOT entry.
 * Call with interrupts off so nothing else touches P33.
 *
 *   fm1_reset_reason()   snapshot P3_RST_SRC / RST_SRC (call first thing)
 *   fm1_wdt_arm(t)       reset-mode watchdog, t = 0xA 1 s .. 0xF 32 s
 *   fm1_wdt_feed()       in the main loop
 *   fm1_reboot()         chip reset through P33 (P3_PR_PWR bit 4)
 *   fm1_enter_uboot()    "usb_update_mode" at 0x01C7FD80 + chip reset
 *   fm1_enter_update(p)  112-byte UPDATA_PARM record at 0x01C7FD88 + core reset
 *                        (the SPL then runs the staged update loader)
 *   fm1_core_reset()     PWR_CON core reset
 *   fm1_updata_parm_clear()  zero the record (CRC 0: ignored on a warm reset)
 *   fm1_mailbox_clear()  zero 0x01C7FD80..0x01C7FDFF (boot info, mailbox) at cold start
 *   fm1_mem_readable(a, n) / fm1_peek8(a)   debug reads of RAM / XIP only
 */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include "fm1_cc.h"

#ifndef FM1_P33_CON
#define FM1_P33_CON (*(volatile uint32_t *)0x13E08u)
#endif
#ifndef FM1_P33_DAT
#define FM1_P33_DAT (*(volatile uint32_t *)0x13E0Cu)
#endif
#ifndef FM1_P33_XFER_LIMIT
#define FM1_P33_XFER_LIMIT 100000u
#endif
#ifndef FM1_P33_START
#define FM1_P33_START() (FM1_P33_CON |= 1u << 4)
#endif
#ifndef FM1_P33_BUSY
#define FM1_P33_BUSY() (FM1_P33_CON & (1u << 1))
#endif
#ifndef FM1_P33_DESELECT
#define FM1_P33_DESELECT() (FM1_P33_CON &= ~((1u << 0) | (1u << 8)))
#endif
#define FM1_RST_SRC (*(volatile uint32_t *)0x100C0u)
#define FM1_BOOT_STATE ((volatile uint8_t *)0x01C7FD80u)
#define FM1_PWR_CON (*(volatile uint32_t *)0x10000u)
#define FM1_UPDATA_PARM ((volatile uint8_t *)0x01C7FD88u)
#define FM1_UPDATA_PARM_LEN 112u

static uint32_t fm1_p33_timeouts;

/* Checked P33 transfers are required for watchdog control. A timeout is not
 * data: callers must stop the transaction and must not issue dependent bytes. */
static int fm1__p33_xfer_checked(uint8_t b, uint8_t *result)
{
    uint32_t n = FM1_P33_XFER_LIMIT;
    FM1_P33_DAT = b;
    FM1_P33_START();
    (void)FM1_P33_CON;                           /* stands in for csync */
    while (FM1_P33_BUSY()) {
        if (--n == 0) {
            fm1_p33_timeouts++;
            return -1;
        }
    }
    if (result) *result = (uint8_t)FM1_P33_DAT;
    return 0;
}

/* Legacy callers retain a sentinel on failure; safety-sensitive paths use
 * checked functions and never treat the sentinel as data. */
static uint8_t fm1__p33_xfer(uint8_t b)
{
    uint8_t result = 0xFFu;
    (void)fm1__p33_xfer_checked(b, &result);
    return result;
}

static void fm1__p33_cs(uint32_t a)
{
    if (a & 0x8000u) {
        FM1_P33_CON |= (1u << 0) | (1u << 8);    /* R3 (RTC) domain */
    } else {
        FM1_P33_CON &= ~(1u << 8);
        FM1_P33_CON |= 1u << 0;
    }
}

static int fm1__p33_op_checked(uint32_t op, uint32_t a, uint8_t d)
{
    int rc = 0;
    fm1__p33_cs(a);
    if (fm1__p33_xfer_checked((uint8_t)((op << 5) | ((a >> 8) & 3u)), NULL) ||
        fm1__p33_xfer_checked((uint8_t)a, NULL) ||
        fm1__p33_xfer_checked(d, NULL)) rc = -1;
    FM1_P33_DESELECT();
    return rc;
}
static int fm1_p33_read_checked(uint32_t a, uint8_t *value)
{
    uint8_t v = 0xFFu;
    int rc = 0;
    if (!value) return -1;
    fm1__p33_cs(a);
    if (fm1__p33_xfer_checked((uint8_t)(0x80u | ((a >> 8) & 3u)), NULL) ||
        fm1__p33_xfer_checked((uint8_t)a, NULL) ||
        fm1__p33_xfer_checked(0x5Eu, &v)) rc = -1;
    FM1_P33_DESELECT();
    if (!rc) *value = v;
    return rc;
}
static int fm1_p33_write_checked(uint32_t a, uint8_t d)
{ return fm1__p33_op_checked(0u, a, d); }
static int fm1_p33_or_checked(uint32_t a, uint8_t d)
{ return fm1__p33_op_checked(1u, a, d); }
static int fm1_p33_and_checked(uint32_t a, uint8_t d)
{ return fm1__p33_op_checked(2u, a, d); }
static int fm1_p33_xor_checked(uint32_t a, uint8_t d)
{ return fm1__p33_op_checked(3u, a, d); }

static uint8_t fm1_p33_read(uint32_t a)
{
    uint8_t value = 0xFFu;
    (void)fm1_p33_read_checked(a, &value);
    return value;
}
static void fm1_p33_write(uint32_t a, uint8_t d) { (void)fm1_p33_write_checked(a, d); }
static void fm1_p33_or(uint32_t a, uint8_t d) { (void)fm1_p33_or_checked(a, d); }
static void fm1_p33_and(uint32_t a, uint8_t d) { (void)fm1_p33_and_checked(a, d); }

/* ------------------------------------------------------------ watchdog --- */
#define FM1_P3_WDT_CON 0x80u
#define FM1_P3_VLD_KEEP 0x17u
#define FM1_P3_RST_SRC 0x12u
#define FM1_P3_PR_PWR 0xA0u

static int fm1_wdt_arm_checked(uint8_t t)
{
    uint8_t verify;
    if (fm1_p33_write_checked(FM1_P3_WDT_CON, 0) ||
        fm1_p33_and_checked(FM1_P3_VLD_KEEP, (uint8_t)~0x40u) ||
        fm1_p33_write_checked(FM1_P3_WDT_CON,
                              (uint8_t)((t & 0x0Fu) | 0x40u)) ||
        fm1_p33_or_checked(FM1_P3_WDT_CON, 0x10u) ||
        fm1_p33_read_checked(FM1_P3_WDT_CON, &verify)) return -1;
    return ((verify & 0x1Fu) == ((t & 0x0Fu) | 0x10u)) ? 0 : -1;
}
static int fm1_wdt_stop_checked(uint8_t *previous)
{
    uint8_t before, vld, verify;
    if (!previous || fm1_p33_read_checked(FM1_P3_WDT_CON, &before) ||
        fm1_p33_read_checked(FM1_P3_VLD_KEEP, &vld)) return -1;
    /* This adapter only restores the reset-mode watchdog used by platform.c. */
    if ((before & 0x10u) && (vld & 0x40u)) return -1;
    if (before & 0x10u) {
        int write_rc = fm1_p33_write_checked(FM1_P3_WDT_CON, 0);
        int read_rc = fm1_p33_read_checked(FM1_P3_WDT_CON, &verify);
        if (write_rc || read_rc || (verify & 0x10u)) return -1;
    }
    *previous = before;
    return 0;
}
static int fm1_wdt_restore_checked(uint8_t previous)
{
    if (!(previous & 0x10u)) return 0;
    return fm1_wdt_arm_checked((uint8_t)(previous & 0x0Fu));
}
static int fm1_wdt_arm(uint8_t t) { return fm1_wdt_arm_checked(t); }
static int fm1_wdt_feed(void)
{ return fm1_p33_or_checked(FM1_P3_WDT_CON, 0x40u); }
static int fm1_wdt_stop(void)
{
    uint8_t previous;
    return fm1_wdt_stop_checked(&previous);
}

/* ---------------------------------------------------- reset and reboot --- */
static struct {
    uint8_t p3_rst;      /* bit0 power-on, 1 VDDIO low, 2 WDT, 3 VCM, 4 long press, 5 1.2 V, 6 soft (P33) */
    uint32_t rst_src;    /* bit5 soft (PWR_CON) */
    uint8_t wdt_con;     /* as found at boot */
} fm1_boot;

static void fm1_reset_reason(void)
{
    fm1_boot.p3_rst = fm1_p33_read(FM1_P3_RST_SRC);
    fm1_boot.rst_src = FM1_RST_SRC;
    fm1_boot.wdt_con = fm1_p33_read(FM1_P3_WDT_CON);
}

static void fm1_reboot(void)
{
    __asm__ volatile("cli");
    fm1_p33_or(FM1_P3_PR_PWR, 0x10);
    for (;;)
        ;
}

static void fm1_enter_uboot(void)
{
    static const char k[16] = "usb_update_mode";
    uint32_t i;
    __asm__ volatile("cli");
    /* CPU0 write limits (fm1_guard.h) may cover the mailbox: drop them all */
    if (!(*(volatile uint32_t *)0x1EEE240u & 1u))
        *(volatile uint32_t *)0x1EEE240u = 0xE7u;
    *(volatile uint32_t *)0x1EEE348u = 0;
    for (i = 0; i < 16u; i++)
        FM1_BOOT_STATE[i] = (uint8_t)k[i];
    fm1_p33_or(FM1_P3_PR_PWR, 0x10);
    for (;;)
        ;
}

FM1_INLINE void fm1_core_reset(void)
{
    FM1_PWR_CON |= 0x10u;
    for (;;)
        ;
}

FM1_INLINE void fm1_enter_update(const uint8_t *parm)
{
    uint32_t i;
    __asm__ volatile("cli");
    if (!(*(volatile uint32_t *)0x1EEE240u & 1u))       /* drop CPU0 write limits, as fm1_enter_uboot */
        *(volatile uint32_t *)0x1EEE240u = 0xE7u;
    *(volatile uint32_t *)0x1EEE348u = 0;
    for (i = 0; i < FM1_UPDATA_PARM_LEN; i++)
        FM1_UPDATA_PARM[i] = parm[i];
    fm1_core_reset();
}

FM1_INLINE void fm1_updata_parm_clear(void)
{
    uint32_t i;
    for (i = 0; i < FM1_UPDATA_PARM_LEN; i++)
        FM1_UPDATA_PARM[i] = 0;
}

FM1_INLINE void fm1_mailbox_clear(void)   /* before fm1_guard_enable (it write-protects the top) */
{
    uint32_t *s;
    for (s = (uint32_t *)0x01C7FD80u; s < (uint32_t *)0x01C7FE00u; s++)
        *s = 0;
}

/* RAM and the XIP window only: SFR reads can have side effects */
static int fm1_mem_readable(uint32_t a, uint32_t n)
{
    return (a >= 0x01C00000u && a + n <= 0x01C80000u && a + n >= a) ||
           (a >= 0x02000000u && a + n <= 0x02100000u && a + n >= a);
}
FM1_INLINE uint8_t fm1_peek8(uint32_t a) { return *(const volatile uint8_t *)a; }

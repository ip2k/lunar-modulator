/* SPDX-License-Identifier: GPL-3.0-only
 * Copyright (C) 2026 Leo Kuroshita (@kurogedelic), Hügelton Instruments */
/* FM-1 SPI NOR at runtime: erase / program / read. Used only when
 * FELUCCA_FLASH is 1.
 *
 * Everything that executes while the SFC (XIP) is switched off lives in
 * .ram_text and touches only SFRs, the stack and RAM buffers: no .rodata, no
 * libcalls, no XIP-resident helpers. Call the fl_*_ram() entry points with
 * interrupts disabled. Same sequence as the AC79 SDK flash driver
 * (enter_spi_code, norflash_erase, norflash_wait_ok, exit_spi_code).
 */
#pragma once
#include <stdint.h>
#include "fm1_xip.h"

#ifndef RAMFN
#define RAMFN  __attribute__((section(".ram_text"), noinline, used))
#endif
#define RAMINL static inline __attribute__((always_inline))

/* XIP (0x02xxxxxx) -> RAM (0x01C0xxxx) is beyond the 23-bit call range:
 * call RAM code through a pointer the compiler cannot fold back. */
static inline void *fl_far(void *p) { void *volatile q = p; return q; }
#define FL_FAR(fn) ((__typeof__(&fn))fl_far((void *)&fn))

#ifndef REG32
#define REG32(a) (*(volatile uint32_t *)(a))
#endif
#define SFC_CON         REG32(0x40200u)            /* bit31 busy; [11:8] read mode */
#define SFCENC_CON      (*(volatile uint8_t *)0x40300u)  /* b0 decrypt, b1 plain window */
#define SFCENC_UNENC_H  REG32(0x40308u)            /* WO, XIP (CPU) address */
#define SFCENC_UNENC_L  REG32(0x4030Cu)            /* WO, XIP (CPU) address */
#define SPI0_CON        REG32(0x11C00u)            /* b15 PND, b14 PCLR, b12 DIR=rx */
#define SPI0_BUF        REG32(0x11C08u)
#define IOMAP_CON0      REG32(0x5101Cu)            /* b5: 1 = SFC owns the flash pins */
#define PORTD_OUT       REG32(0x500C0u)            /* PD0 = flash CS# */
#define PORTD_DIR       REG32(0x500C8u)
#define CACHE_CON       REG32(0x1EEE008u)          /* b14 = cache idle */
#define T4_CNT          REG32(0x10804u)            /* TIMER4, 24 MHz free-running */

#define FL_XIP(off)     FM1_XIP(off)              /* fm1_xip.h */
#define FL_DATA_LO      0x00097000u                /* Felucca main store */
#define FL_DATA_HI      0x000E0000u
#define FL_GLOB_LO      0x000FC000u                /* Felucca superblock / globals */
#define FL_GLOB_HI      0x000FF000u
#define FL_OTA_LO       0x000E0000u                /* M-UPGRADE loader staging, ota.c */
#define FL_OTA_HI       0x000E5000u
/* [off, off + n) inside [lo, hi), without wrapping: off + n can overflow, and
 * the 1 MiB part ignores the high address bits, so a wrapped range lands low. */
#define FL_IN(off, n, lo, hi) ((uint32_t)(off) >= (lo) && (uint32_t)(off) <= (hi) && \
                               (uint32_t)(n) <= (hi) - (uint32_t)(off))
/* Felucca's own store (projects, user samples; settings) */
#define FL_STORE_OK(off, n) (FL_IN(off, n, FL_DATA_LO, FL_DATA_HI) || FL_IN(off, n, FL_GLOB_LO, FL_GLOB_HI))
/* Where the RAM driver may erase / program. The app build allows only its own
 * data regions; the update loader (firmware/loader) defines its own window. */
#ifndef FL_RANGE_OK
#define FL_RANGE_OK(off, n) (FL_STORE_OK(off, n) || FL_IN(off, n, FL_OTA_LO, FL_OTA_HI))
#endif

typedef struct { uint32_t sfc_con, spi_con, iomap_con0; } fl_saved_t;

#ifndef FL_CSYNC
#define FL_CSYNC() __asm__ volatile("csync" ::: "memory")
#endif
#ifndef FL_FLUSHINV
#define FL_FLUSHINV(a) __asm__ volatile("flushinv [%0]" :: "r"(a) : "memory")
#endif
#ifndef FL_CS_LEVEL
#define FL_CS_LEVEL(high) do { \
    PORTD_DIR &= ~1u; \
    if (high) PORTD_OUT |= 1u; else PORTD_OUT &= ~1u; \
} while (0)
#endif
#ifndef FL_SPI_WAIT
#define FL_SPI_WAIT() fl_spi_wait()
#endif
#ifndef FL_SFC_RESTORE
#define FL_SFC_RESTORE(value) (SFC_CON = (value))
#endif
#ifndef FL_IRQ_DISABLE
#define FL_IRQ_DISABLE() __asm__ volatile("cli" ::: "memory")
#endif
#ifndef FL_IRQ_RESTORE_ENABLED
#define FL_IRQ_RESTORE_ENABLED() __asm__ volatile("csync\n\tsti" ::: "memory")
#endif
RAMINL void fl_csync(void) { FL_CSYNC(); }
RAMINL void fl_cache_idle(void) { while (!(CACHE_CON & 0x4000u)) ; }
RAMINL void fl_delay(uint32_t n) { volatile uint32_t i = n; while (i--) ; }

RAMINL void fl_cs(int high)
{
    FL_CS_LEVEL(high);
    fl_delay(10);
}
RAMINL int fl_spi_wait(void)
{
    uint32_t n = 50000000u;
    fl_csync();
    while (!(SPI0_CON & 0x8000u))
        if (--n == 0) break;
    SPI0_CON |= 0x4000u;
    return n ? 0 : -1;
}
RAMINL int fl_tx(uint8_t b)
{
    int rc;
    SPI0_CON |= 8u; SPI0_CON &= ~0x1000u;
    SPI0_BUF = b; rc = FL_SPI_WAIT();
    SPI0_CON &= ~8u;
    return rc;
}
RAMINL int fl_rx(uint8_t *value)
{
    int rc;
    SPI0_CON |= 8u; SPI0_CON |= 0x1000u;
    SPI0_BUF = 0xFFu; rc = FL_SPI_WAIT();
    if (!rc) *value = (uint8_t)SPI0_BUF;
    SPI0_CON &= ~8u;
    return rc;
}
RAMINL int fl_addr(uint32_t a)
{
    if (fl_tx((uint8_t)(a >> 16))) return -5;
    if (fl_tx((uint8_t)(a >> 8))) return -5;
    if (fl_tx((uint8_t)a)) return -5;
    return 0;
}
RAMINL int fl_rdsr(uint8_t cmd, uint8_t *value)
{
    int rc;
    fl_cs(0); rc = fl_tx(cmd);
    if (!rc) rc = fl_rx(value);
    fl_cs(1);
    return rc ? -5 : 0;
}
RAMINL int fl_wren(void)
{
    int rc;
    fl_cs(0); rc = fl_tx(0x06); fl_cs(1);
    return rc ? -5 : 0;
}

RAMINL int fl_enter(fl_saved_t *s)
{
    uint32_t mode;
    fl_cache_idle();
    s->sfc_con = SFC_CON;
    s->spi_con = SPI0_CON;
    s->iomap_con0 = IOMAP_CON0;
    mode = (s->sfc_con >> 8) & 0xFu;
    if (mode == 6u || mode == 7u)                 /* continuous-read XIP: not handled here */
        return -1;
    fl_csync();
    while ((int32_t)SFC_CON < 0) ;                /* SFC idle */
    SFC_CON = 0;                                  /* XIP OFF from here on */
    IOMAP_CON0 &= ~0x20u;                         /* pins -> SPI0 / GPIO */
    SPI0_CON = 0;
    SPI0_CON = 0x1029u;                           /* SDK default */
    fl_csync();
    return 0;
}
RAMINL void fl_exit(const fl_saved_t *s)
{
    SPI0_CON = s->spi_con;
    IOMAP_CON0 = (IOMAP_CON0 & ~0x20u) | (s->iomap_con0 & 0x20u);
    fl_csync();
    while ((int32_t)SFC_CON < 0) ;
    FL_SFC_RESTORE(s->sfc_con);                   /* XIP back on */
    fl_csync();
}
RAMINL void fl_inval(uint32_t off, uint32_t len)
{
    uint32_t a = FL_XIP(off) & ~31u, e = FL_XIP(off) + len;
    fl_cache_idle();
    for (; a < e; a += 32u) {
        fl_csync();
        FL_FLUSHINV(a);
        fl_csync();
        fl_cache_idle();
    }
}
RAMINL int fl_wait_ready(uint32_t max_us, uint32_t *took_us)
{
    uint32_t t0 = T4_CNT, dt;
    int exceeded = 0, transfer_error = 0;
    /* Never return to XIP unless a completed status transaction observed WIP
     * clear. The limit reports lateness; it is not permission to restore XIP.
     * If status cannot be read or WIP never clears, remain in this RAM loop. */
    for (;;) {
        uint8_t status;
        int read_rc = fl_rdsr(0x05, &status);
        /* Include the completed SPI transaction in the deadline. Unsigned
         * subtraction handles timer rollover between successive samples. */
        dt = (T4_CNT - t0) / 24u;
        if (dt > max_us) exceeded = 1;
        if (read_rc) {
            transfer_error = 1;
            continue;
        }
        if (!(status & 1u)) {
            *took_us = dt;
            return transfer_error ? -5 : (exceeded ? -4 : 0);
        }
    }
}

/* ---- entry points: IRQs OFF, args/buffers in RAM ---- */

static RAMFN int fl_jedec_checked_ram(uint32_t *result) /* expect 0x856014 */
{
    fl_saved_t s; uint32_t id = 0; uint8_t byte; int rc = 0;
    if (fl_enter(&s)) return -2;
    fl_cs(0);
    if (fl_tx(0x9F) || fl_rx(&byte)) rc = -5;
    else id = (uint32_t)byte << 16;
    if (!rc && fl_rx(&byte)) rc = -5;
    else if (!rc) id |= (uint32_t)byte << 8;
    if (!rc && fl_rx(&byte)) rc = -5;
    else if (!rc) id |= byte;
    fl_cs(1); fl_exit(&s);
    if (rc) return rc;
    *result = id;
    return 0;
}
/* Compatibility for existing boot checks: transport errors cannot equal the
 * sole accepted JEDEC ID, and checked callers should use the status API. */
static RAMFN uint32_t fl_jedec_ram(void) { uint32_t id; return fl_jedec_checked_ram(&id) ? 0xFFFFFFFFu : id; }

static RAMFN int fl_status_checked_ram(uint32_t *result) /* SR1 | SR2 << 8 */
{
    fl_saved_t s; uint8_t sr1, sr2; int rc;
    if (fl_enter(&s)) return -2;
    rc = fl_rdsr(0x05, &sr1);
    if (!rc) rc = fl_rdsr(0x35, &sr2);
    fl_exit(&s);
    if (rc) return rc;
    *result = (uint32_t)sr1 | ((uint32_t)sr2 << 8);
    return 0;
}

static RAMFN int fl_erase4k_ram(uint32_t off, uint32_t *took_us)
{
    fl_saved_t s; int rc, destructive_attempted = 0;
    if (!FL_RANGE_OK(off, 0x1000u) || (off & 0xFFFu))
        return -1;
    if (fl_enter(&s)) return -2;
    rc = fl_wren();
    if (!rc) {
        uint8_t status;
        rc = fl_rdsr(0x05, &status);
        if (!rc && !(status & 2u)) rc = -3;       /* WEL did not set */
    }
    if (rc && rc != -3) rc = -5;
    if (!rc) {
        fl_cs(0);
        destructive_attempted = 1;               /* CS release can commit despite timeout */
        if (fl_tx(0x20) || fl_addr(off)) rc = -5;
        fl_cs(1);
    }
    if (destructive_attempted) {
        int ready_rc;
        fl_inval(off, 4096u);
        ready_rc = fl_wait_ready(500000u, took_us); /* return only after verified WIP clear */
        if (!rc) rc = ready_rc;
    }
    fl_exit(&s);
    return rc;
}

static RAMFN int fl_prog_ram(uint32_t off, const uint8_t *src, uint32_t n, uint32_t *took_us)
{
    fl_saved_t s; int rc, destructive_attempted = 0; uint32_t i;
    if (!FL_RANGE_OK(off, n) ||
        n == 0 || n > 256u || ((off & 0xFFu) + n) > 256u) return -1;    /* one page, no wrap */
    if (fl_enter(&s)) return -2;
    rc = fl_wren();
    if (!rc) {
        uint8_t status;
        rc = fl_rdsr(0x05, &status);
        if (!rc && !(status & 2u)) rc = -3;
    }
    if (rc && rc != -3) rc = -5;
    if (!rc) {
        fl_cs(0);
        destructive_attempted = 1;               /* CS release can commit despite timeout */
        if (fl_tx(0x02) || fl_addr(off)) rc = -5;
        for (i = 0; !rc && i < n; i++) if (fl_tx(src[i])) rc = -5;
        fl_cs(1);
    }
    if (destructive_attempted) {
        int ready_rc;
        fl_inval(off, n);
        ready_rc = fl_wait_ready(10000u, took_us); /* return only after verified WIP clear */
        if (!rc) rc = ready_rc;
    }
    fl_exit(&s);
    return rc;
}

static RAMFN int fl_read_ram(uint32_t off, uint8_t *dst, uint32_t n)   /* 0x0B fast read */
{
    fl_saved_t s; uint32_t i; int rc = 0;
    if (fl_enter(&s)) return -2;
    fl_cs(0);
    if (fl_tx(0x0B) || fl_addr(off) || fl_tx(0xFF)) rc = -5;
    for (i = 0; !rc && i < n; i++) { uint8_t byte; if (fl_rx(&byte)) rc = -5; else dst[i] = byte; }
    fl_cs(1); fl_exit(&s);
    return rc;
}

/* ---- XIP side (normal .text) ---- */

/* Once at boot, before any XIP read of the data region: map the data area
 * as an unencrypted XIP window (as the SDK's IOCTL_SET_VM_INFO does). */
static void fl_plain_window_init(void)
{
    SFCENC_CON &= (uint8_t)~2u;
    SFCENC_UNENC_L = FL_XIP(0x93000u);            /* 0x0208F000 */
    SFCENC_UNENC_H = 0x07FFFFFFu;
    SFCENC_CON |= 2u;
    FL_IRQ_DISABLE();
    fl_inval(0x93000u, 0x100000u - 0x93000u);     /* drop any decrypted lines */
    FL_IRQ_RESTORE_ENABLED();
}

static inline uint32_t irq_save(void) { FL_IRQ_DISABLE(); return 0; }
static inline void irq_restore(uint32_t f) { (void)f; FL_IRQ_RESTORE_ENABLED(); }

static int fl_erase4k(uint32_t off, uint32_t *took_us)
{
    uint32_t f = irq_save();
    int rc = FL_FAR(fl_erase4k_ram)(off, took_us);
    irq_restore(f);
    return rc;
}

static int fl_write(uint32_t off, const uint8_t *src_ram, uint32_t n)
{
    uint32_t took;
    while (n) {
        uint32_t chunk = 256u - (off & 0xFFu);
        int rc;
        uint32_t f;
        if (chunk > n) chunk = n;
        f = irq_save();
        rc = FL_FAR(fl_prog_ram)(off, src_ram, chunk, &took);
        irq_restore(f);
        if (rc) return rc;
        off += chunk; src_ram += chunk; n -= chunk;
    }
    return 0;
}

/* Read back through XIP (needs fl_plain_window_init) and compare. */
static int fl_verify_xip(uint32_t off, const uint8_t *ref, uint32_t n)
{
    const volatile uint8_t *p = (const volatile uint8_t *)FL_XIP(off);
    uint32_t i;
    for (i = 0; i < n; i++) if (p[i] != ref[i]) return -(int)(i + 1);
    return 0;
}

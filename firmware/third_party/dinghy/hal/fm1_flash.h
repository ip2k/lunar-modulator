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
#include "fm1_sys.h"

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

/* Match app.ld stack reservations. Both stacks grow down; keep at least 1 KiB
 * below the live SP for this wrapper, the RAM writer and checked P33 path. */
#ifndef FL_USER_STACK_LO
#define FL_USER_STACK_LO 0x01C74100u
#define FL_USER_STACK_HI 0x01C7A000u
#define FL_SUPER_STACK_LO 0x01C7A100u
#define FL_SUPER_STACK_HI 0x01C7C000u
#endif
#ifndef FL_STACK_HEADROOM
#define FL_STACK_HEADROOM 1024u
#endif
#ifndef FL_RAM_LO
#define FL_RAM_LO 0x01C00000u
#define FL_RAM_HI 0x01C80000u
#endif
#ifndef FL_READ_SP
#define FL_READ_SP(value) __asm__ volatile ("%0 = sp" : "=r"(value) : : "memory")
#endif
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

/* The stack pointer is sampled in the wrapper before masking IRQs. Requiring
 * the complete page below the selected stack top prevents an XIP-off writer
 * from reading a staged page outside ordinary SRAM. */
static inline int fl_ram_span_ok(uintptr_t start, uint32_t size)
{
    return start >= FL_RAM_LO && start <= FL_RAM_HI && size <= FL_RAM_HI - start;
}
static inline int fl_stack_region(uintptr_t sp, uintptr_t *lo, uintptr_t *hi)
{
    if (sp >= FL_USER_STACK_LO && sp < FL_USER_STACK_HI) {
        *lo = FL_USER_STACK_LO; *hi = FL_USER_STACK_HI; return 1;
    }
    if (sp >= FL_SUPER_STACK_LO && sp < FL_SUPER_STACK_HI) {
        *lo = FL_SUPER_STACK_LO; *hi = FL_SUPER_STACK_HI; return 1;
    }
    return 0;
}
static inline int fl_stack_context_ok(uintptr_t sp)
{
    uintptr_t lo, hi;
    return fl_stack_region(sp, &lo, &hi) && sp - lo >= FL_STACK_HEADROOM && sp < hi;
}
static inline int fl_stack_page_ok(uintptr_t sp, uintptr_t page)
{
    uintptr_t lo, hi;
    return fl_stack_region(sp, &lo, &hi) && sp - lo >= FL_STACK_HEADROOM &&
           page >= sp && page >= lo && page <= hi && 256u <= hi - page;
}
static inline int fl_timing_word_ok(const uint32_t *took)
{
    uintptr_t p = (uintptr_t)took;
    return took && !(p & 3u) && fl_ram_span_ok(p, sizeof *took);
}

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
#ifndef FL_IRQ_SAVE
/* Match the pinned AC79 SDK local_irq_save contract: save ICFG, then clear
 * only its global interrupt-enable bit. Keep this inline so the call site
 * never depends on XIP while the NOR controller has disabled reads. */
#define FL_IRQ_SAVE(flags) do { \
    __asm__ volatile ("%0 = icfg" : "=r"(flags) : : "memory"); \
    uint32_t fl_irq_masked = (flags) & ~0x100u; \
    __asm__ volatile ("icfg = %0" :: "r"(fl_irq_masked) : "memory"); \
} while (0)
#endif
#ifndef FL_IRQ_RESTORE
#define FL_IRQ_RESTORE(flags) \
    __asm__ volatile ("icfg = %0" :: "r"(flags) : "memory")
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

static inline uint32_t irq_save(void)
{
    uint32_t flags;
    FL_IRQ_SAVE(flags);
    return flags;
}
static inline void irq_restore(uint32_t f) { FL_IRQ_RESTORE(f); }

/* Once at boot, before any XIP read of the data region: map the data area
 * as an unencrypted XIP window (as the SDK's IOCTL_SET_VM_INFO does). */
static void fl_plain_window_init(void)
{
    uint32_t irq_flags;
    SFCENC_CON &= (uint8_t)~2u;
    SFCENC_UNENC_L = FL_XIP(0x93000u);            /* 0x0208F000 */
    SFCENC_UNENC_H = 0x07FFFFFFu;
    SFCENC_CON |= 2u;
    irq_flags = irq_save();
    fl_inval(0x93000u, 0x100000u - 0x93000u);     /* drop any decrypted lines */
    irq_restore(irq_flags);
}

static int fl_erase4k(uint32_t off, uint32_t *took_us)
{
    uint8_t prior_wdt;
    uint32_t f;
    int rc;
    uintptr_t sp;
    FL_READ_SP(sp);
    if (!FL_RANGE_OK(off, 0x1000u) || (off & 0xFFFu)) return -1;
    if (!fl_stack_context_ok(sp) || !fl_timing_word_ok(took_us)) return -8;
    f = irq_save();
    /* P33 stays serialized with the SFC operation. The RAM driver is not
     * entered unless the watchdog stop is positively read back as disabled. */
    if (fm1_wdt_stop_checked(&prior_wdt)) {
        irq_restore(f);
        return -6;
    }
    rc = FL_FAR(fl_erase4k_ram)(off, took_us);
    /* RAM driver returns only after ready was observed (or before XIP-off).
     * Restore the existing reset-mode watchdog while IRQs remain masked. */
    if (fm1_wdt_restore_checked(prior_wdt) && !rc) rc = -7;
    irq_restore(f);
    return rc;
}

/* Source bytes are read while XIP is enabled, then copied to a stack page
 * before fl_prog_ram disables it. Accept only ordinary SRAM or the mapped
 * 1 MiB flash window; reject SFR/MMIO and wrapping spans before any writes. */
static int fl_source_span_ok(const uint8_t *src, uint32_t n, uint32_t off)
{
    uintptr_t start = (uintptr_t)src, end;
    const uintptr_t ram_lo = 0x01C00000u, ram_hi = 0x01C80000u;
    const uintptr_t xip_lo = 0x02000000u, xip_hi = 0x020FC000u;
    uint32_t source_off;

    if (!n) return 1;
    if (!src || (uintptr_t)n > UINTPTR_MAX - start || n > UINT32_MAX - off) return 0;
    end = start + (uintptr_t)n;
    if (start >= ram_lo && end <= ram_hi) return 1;
    if (start < xip_lo || end > xip_hi) return 0;

    /* A page-sized copy protects residency, but cannot protect future source
     * pages if this call overwrites them while streaming from the same flash. */
    source_off = (uint32_t)(start - xip_lo) + 0x4000u;
    if (source_off < off + n && off < source_off + n) return 0;
    return 1;
}

#ifndef FL_SOURCE_SPAN_OK
#define FL_SOURCE_SPAN_OK(src, n, off) fl_source_span_ok((src), (n), (off))
#endif

#ifndef FL_PROGRAM_PAGE
#define FL_PROGRAM_PAGE(off, page, chunk, took) FL_FAR(fl_prog_ram)(off, page, chunk, took)
#endif

static int fl_write(uint32_t off, const uint8_t *src_ram, uint32_t n)
{
    uint32_t took;
    if (!n) return 0;
    if (!FL_SOURCE_SPAN_OK(src_ram, n, off)) return -1;
    while (n) {
        uint32_t chunk = 256u - (off & 0xFFu);
        int rc;
        uint32_t f, i;
        uint8_t page[256] __attribute__((aligned(4)));
        uintptr_t sp;
        FL_READ_SP(sp);
        if (!fl_stack_page_ok(sp, (uintptr_t)page) || !fl_timing_word_ok(&took)) return -8;
        if (chunk > n) chunk = n;
        /* Copy while XIP is still available. The RAM routine must never
         * dereference an unverified caller pointer after SFC is switched off. */
        for (i = 0; i < chunk; ++i) page[i] = src_ram[i];
        uint8_t prior_wdt;
        f = irq_save();
        if (fm1_wdt_stop_checked(&prior_wdt)) {
            irq_restore(f);
            return -6;
        }
        rc = FL_PROGRAM_PAGE(off, page, chunk, &took);
        /* The target RAM writer returns only after a positive ready read.
         * A failed re-arm is reported after XIP is back, without retrying. */
        if (fm1_wdt_restore_checked(prior_wdt) && !rc) rc = -7;
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

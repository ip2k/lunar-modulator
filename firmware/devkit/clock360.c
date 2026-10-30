/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic.
 *
 * Meant to run the AC79 dev kit at the FM-1's stock clock and power profile,
 * so a board run times the firmware as the FM-1 would. App-only: the kit's
 * flash head, isd_config and SPL are untouched.
 *
 * WHAT A KIT BUILD DOES NOW (2026-10-29): it reads the clock tree, the rails,
 * the OS tick and the PLL/SDRAM registers, prints them, checks that the kit
 * is in the state below, and then refuses (reason 10) without writing
 * anything. No reviewed run-time path to 360 MHz exists from that state:
 *
 * - The kit boots on CLK_CON2[3:0] = 2, a fixed 320 MHz tap, with both
 *   post-dividers /1 ([7:4] = 0) [verified: bench 2026-10-29 before line
 *   con2=2; decode from the SDK's clk_early_init and sys_clock_update IR,
 *   tap table {192, 137, 320, 480, 107} MHz]. The SPL picks the tap because
 *   isd_config asks for exactly 320 MHz [verified: stock V15 SPL, vendor
 *   objdump; the kit's own SPL matched by byte pattern only]. The
 *   programmable PLL2 then feeds SDRAM (sdram_clk 192 MHz in the boot log),
 *   not the core. PLL2 is 384 MHz (24 MHz / 12 x 192) and PLL3 480 MHz
 *   [verified: bench 2026-10-29 r3 pll= line, pll2_con0=940022b
 *   pll2_con1=75030be usb_com0=7796cb3]; sdram_clk 192 MHz = PLL2 / 2
 *   [inferred].
 * - The 2026-10-28 design assumed PLL source 6 (sys = PLL2 x 2/3, PLL2 480
 *   MHz) on the kit. That was the FM-1's tree (source 6, PLL2 540 MHz at
 *   360 [reported: fm1-x0x 80b7d40; verified: stock isd_config + SPL]),
 *   wrongly marked verified for the kit.
 * - system_clock_set(clk) is clock_set(clk, sdram, -1) and keeps the CLASS
 *   of the current source [verified: clock.c IR, sys_clock_update]. From a
 *   fixed tap (0-4) it only searches tap x {1,3,5,7} x {1,2,4,8}; 360 MHz is
 *   not among them, so it sets its error flag before any register write and
 *   returns -22 (after running the clock-critical section with IRQs off).
 *   From PLL2 sources 5-7 it keeps the source but REWRITES PLL2_CON1[11:0]
 *   (PLL2 = sys x {4,3,2}/2): the earlier claim that it "keeps the PLL" was
 *   wrong. Either way the design's own ban on PLL and CLK_CON2 writes cannot
 *   be met through it.
 * - The only SDK run-time route (system_pll12_sdram_pll3_enable(1), then
 *   system_clock_set) writes CLK_CON2 and PLL2, may move SDRAM to 270 MHz
 *   with timing set for 192, and cannot return to the boot tap without a
 *   reset, which breaks the restore path below. A 360 MHz isd_config head
 *   changes the kit's flash head. Both are owner decisions; neither is built.
 *
 * The switch path from the 2026-10-28 design (rails up with readback, then
 * system_clock_set, SFC BAUD held, the fail path that never lowers the rails
 * under a core above 320 MHz) is kept behind LUNAR_DEVKIT_CLOCK360_SWITCH for
 * the host model of its decisions only (tests/fixtures/clock360); it cannot
 * be built for the kit. Its evidence, for a future reviewed design:
 * - The rail macros are the SDK's own (asm/p33.h): SYSVDD P3_ANA_CON9[3:0],
 *   VDC14 P3_ANA_CON6[2:0], VDDIOM P3_ANA_CON5[2:0], VDDIOW P3_ANA_CON5[5:4],
 *   VLVD P3_VLVD_CON[5:3] enable [0], DCDC13_EN P3_ANA_CON0[3]
 *   [verified: header]; power_init writes them through the same
 *   P33_CON_SET calls [verified: power_hw.c IR]. system_vdd_clock_set()
 *   is not used: its table lowers the rails. clk_set("sys") is a no-op
 *   [verified: clock.c IR].
 * - FM-1 stock levels: SYSVDD 1.38 V, VDC14 1.60 V with DCDC, VDDIOM and
 *   VDDIOW 3.2 V, LVD 2.6 V [reported: fm1-nes board_power.c, from stock
 *   FM-1_010]. VDDIOW is the weak VDDIO, the IO supply's low-power
 *   (sleep) level, not an RF rail [reported: demo_hello board.c calls it
 *   the "weak VDDIO" level; its use in sleep inferred]. The kit boots at
 *   SYSVDD 1.26 V, VDC14 1.40 V with DCDC, VDDIOM 3.2 V, VDDIOW 2.1 V and
 *   LVD 2.5 V [verified: bench 2026-10-29 p33=fb,44,b,1b,31].
 * - The OS tick follows a clock change: port.c's clock_critical_exit sets
 *   TTMR_PRD = clk_get("sys") / 100 [verified: port.c IR]. TIMER4 runs from
 *   the 24 MHz oscillator (CON = 9, set by sdk_worker.c) and the UARTs from
 *   the 48 MHz USB PLL (PLL_48M) [verified: board.c, clk_early_init IR].
 * - SFC = HSB / (BAUD + 1): BAUD 1 at HSB 180 MHz is 90 MHz, BAUD 2 60 MHz.
 *   The kit's flash (JEDEC 5E4017 [reported: Codex bring-up note]) has no
 *   established 90 MHz rating.
 * - JL_SFC->BAUD is write-only in WL82.h; the receipts print a raw read of
 *   it as evidence only (the bench before line read the boot BAUD, 1).
 */
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include "clock360.h"

#ifndef LUNAR_DEVKIT_SYS_CLK
#error "clock360.c needs LUNAR_DEVKIT_SYS_CLK from the preparer"
#endif
#if LUNAR_DEVKIT_SYS_CLK != 360000000
#error "Only the FM-1's 360 MHz has been reviewed"
#endif
#ifndef LUNAR_DEVKIT_SFC_BAUD
#define LUNAR_DEVKIT_SFC_BAUD 2
#endif
#ifndef LUNAR_DEVKIT_STOCK_POWER
#define LUNAR_DEVKIT_STOCK_POWER 0
#endif
#if LUNAR_DEVKIT_SFC_BAUD != 1 && LUNAR_DEVKIT_SFC_BAUD != 2
#error "SFC BAUD 1 (90 MHz) or 2 (60 MHz) only"
#endif
#ifndef LUNAR_DEVKIT_CLOCK360_SWITCH
#define LUNAR_DEVKIT_CLOCK360_SWITCH 0
#endif
#if LUNAR_DEVKIT_CLOCK360_SWITCH && !defined(LUNAR_CLOCK360_HOST_MODEL)
#error "No reviewed 360 MHz switch exists for the kit (fixed 320 MHz tap); see the top of clock360.c"
#endif

#define KIT_SYS 320000000
#define FM1_SYS 360000000
/* Ten OS ticks of 10 ms in TIMER4 counts, -2 %..+1 % (wake-up latency). */
#define TICK_LOW 2352000u
#define TICK_HIGH 2424000u
static __attribute__((noinline)) int tick_ok(uint32_t t) { return t - TICK_LOW <= TICK_HIGH - TICK_LOW; }

struct clocks { int sys, hsb, lsb, sfc, uart; u32 con2, div; };
/* The five P33 bytes, in receipt order. */
enum { CON0, CON5, CON6, CON9, VLVD };
struct rails { u8 b[5]; };

static void clocks_read(struct clocks *c)
{
    c->sys = clk_get("sys"); c->hsb = clk_get("hsb"); c->lsb = clk_get("lsb");
    c->sfc = clk_get("sfc"); c->uart = clk_get("uart");
    c->con2 = JL_CLOCK->CLK_CON2; c->div = JL_CLOCK->SYS_DIV;
}

static void rails_read(struct rails *r)
{
    r->b[CON0] = P33_CON_GET(P3_ANA_CON0); r->b[CON5] = P33_CON_GET(P3_ANA_CON5);
    r->b[CON6] = P33_CON_GET(P3_ANA_CON6); r->b[CON9] = P33_CON_GET(P3_ANA_CON9);
    r->b[VLVD] = P33_CON_GET(P3_VLVD_CON);
}

/* Ten OS ticks, aligned to a tick edge first, in TIMER4 counts. */
static uint32_t tick_ticks(uint32_t (*now)(void))
{
    os_time_dly(1);
    uint32_t before = now();
    os_time_dly(10);
    return now() - before;
}

/* One line per phase, "<phase>=<result>": before=-, after=PASS|FAIL,
 * restored=OK rails=kit or restored=FAIL rails=kept, end=- (judged by
 * tools/devkit_pipeline_result.py against the after line). A kit build
 * prints only before=- (and pll=-, below). The P33 bytes are printed raw, in the order
 * ana_con0,ana_con5,ana_con6,ana_con9,vlvd_con; decode them with the field
 * map at the top of this file (SYSVDD = con9 & 15, VDC14 = con6 & 7,
 * VDDIOM = con5 & 7, VDDIOW = (con5 >> 4) & 3, LVD = (vlvd >> 3) & 7, LVD
 * enable = vlvd & 1, DCDC13 = (con0 >> 3) & 1). con2 is CLK_CON2: [3:0] the
 * system clock source (2 = the fixed 320 MHz tap, 6 = PLL2 x 2/3), [5:4]
 * and [7:6] the tap post-dividers. baud is the raw JL_SFC->BAUD read. tick
 * is ten OS ticks in TIMER4 counts (2,400,000 at 10 ms; 0 on the restored
 * line). The UART clock and TIMER4's CON are checked but not printed. */
static void receipt(const char *phase, const char *result, const struct clocks *c,
                    const struct rails *r, uint32_t ticks, int rc)
{
    printf("LUNAR_CLOCK360 %s=%s sys=%d hsb=%d lsb=%d sfc=%d baud=%x "
           "con2=%x div=%x p33=%x,%x,%x,%x,%x tick=%u rc=%d\n",
           phase, result, c->sys, c->hsb, c->lsb, c->sfc, (unsigned)JL_SFC->BAUD,
           (unsigned)c->con2, (unsigned)c->div,
           r->b[CON0], r->b[CON5], r->b[CON6], r->b[CON9], r->b[VLVD],
           (unsigned)ticks, rc);
}

/* The registers a reviewed 360 MHz design needs and nothing printed yet,
 * raw, read only: JL_ANA PLL_CON0 (0x119A0; [27:26] = 2 selects a 40 MHz
 * reference), PLL2_CON0 (0x119A8; [6:2] the reference divider) and
 * PLL2_CON1 (0x119AC; [11:0] the feedback divider), so PLL2 = ref /
 * (con0[6:2] + 2) x (con1[11:0] + 2); HUSB_COM_CON0 and HUSB_COM_CON2
 * (0x16A00, 0x16A08: PLL3, the USB PLL); JL_SDR->CON0 (0x40400). The SDK's
 * own clk_early_init reads each of them at boot [verified: clock.c IR
 * loads of 72096, 72104, 72108, 92672, 92680 and 263168]. */
static void pll_receipt(void)
{
    printf("LUNAR_CLOCK360 pll=- pll_con0=%x pll2_con0=%x pll2_con1=%x usb_com0=%x usb_com2=%x sdr_con0=%x\n",
           (unsigned)JL_ANA->PLL_CON0, (unsigned)JL_ANA->PLL2_CON0, (unsigned)JL_ANA->PLL2_CON1,
           (unsigned)HUSB_COM_CON0, (unsigned)HUSB_COM_CON2, (unsigned)JL_SDR->CON0);
}

/* Failure reasons, printed as numbers to keep the image inside the kit's
 * writer region; clock360.h lists them. 7-9 exist only in the host model. */
enum { NOT_AT_320 = 1, NOT_KIT_SOURCE, BUS_DIVIDERS, TICK_BEFORE, UART_CLOCK, DCDC_OFF,
       RAIL_READBACK, READBACK, NOT_BACK, NO_REVIEWED_SWITCH };

static int fail(int reason)
{
    printf("LUNAR_CLOCK360 result=FAIL reason=%d\n", reason);
    return 0;
}

static int near(int value, int expected) { return value >= expected - 1000 && value <= expected + 1000; }

/* sys, and HSB at sys / 2, each within 1 kHz. Outlined so the 32-bit clock
 * constants are loaded once per check, not once per comparison. */
static __attribute__((noinline)) int tree(const struct clocks *c, int sys)
{
    return near(c->sys, sys) && near(c->hsb, sys >> 1);
}

#if LUNAR_DEVKIT_CLOCK360_SWITCH
/* HOST MODEL ONLY (the #error above): the 2026-10-28 switch, kept so its
 * decisions stay tested for a future reviewed design. Its source-6
 * precondition describes no state the kit boots in, and on source 6 the
 * real SDK rewrites PLL2_CON1, which that design did not intend. */
#define SOURCE_OK(con2) (((con2) & 15u) == 6u)

/* Exported by the pinned SDK libraries without a public prototype
 * [verified: vm_sfc.c and clock.c IR]. */
extern void cpu_enter_sfc_critical(void (*cb)(void *), void *priv);
extern void cpu_exit_sfc_critical(void);
extern int sfc_flash_baud_div(u8 div);

#define FM1_LSB 60000000
#define SFC_EXPECTED (FM1_SYS / 2 / (LUNAR_DEVKIT_SFC_BAUD + 1))

/* The rails in stock order (power_init): VDDIOM, VDC14, VDDIOW, SYSVDD,
 * then the LVD level, its enable untouched. Each row is one of the SDK's
 * macros, spelled out so one loop can raise them (this order, before the
 * clock goes up) and put them back (reverse order, only after the clock is
 * back down): VDDIOM_VOL_SEL, VDC14_VOL_SEL, VDDIOW_VOL_SEL, SYSVDD_VOL_SEL
 * and VLVD_SEL are each P33_CON_SET(addr, start, len, level) [verified:
 * asm/p33.h]. */
static const struct { u16 addr; u8 start, len, byte, stock; } RAIL[5] = {
    { P3_ANA_CON5, 0, 3, CON5, VDDIOM_VOL_32V },
    { P3_ANA_CON6, 0, 3, CON6, VDC14_VOL_SEL_160V },
    { P3_ANA_CON5, 4, 2, CON5, VDDIOW_VOL_32V },
    { P3_ANA_CON9, 0, 4, CON9, SYSVDD_VOL_SEL_138V },
    { P3_VLVD_CON, 3, 3, VLVD, VLVD_SEL_26V },
};

static u8 rail_level(const struct rails *r, int i)
{
    return (r->b[RAIL[i].byte] >> RAIL[i].start) & ((1u << RAIL[i].len) - 1u);
}

/* saved NULL: raise to the stock levels; else lower back to saved's. */
static void rails_write(const struct rails *saved)
{
    for (int k = 0; k < 5; k++) {
        int i = saved ? 4 - k : k;
        P33_CON_SET(RAIL[i].addr, RAIL[i].start, RAIL[i].len, saved ? rail_level(saved, i) : RAIL[i].stock);
        os_time_dly(2);
    }
}

/* Every level stock, LVD enabled, DCDC13 on. */
static int rails_are_stock(const struct rails *r)
{
    for (int i = 0; i < 5; i++)
        if (rail_level(r, i) != RAIL[i].stock) return 0;
    return (r->b[VLVD] & 1u) && ((r->b[CON0] >> 3) & 1u);
}

/* The FM-1's clock tree, the OS tick, and (with stock power) its rails. */
static __attribute__((noinline)) int at_fm1(const struct clocks *c, const struct rails *r, uint32_t ticks)
{
    (void)r;
    return tree(c, FM1_SYS) && near(c->lsb, FM1_LSB) &&
           near(c->sfc, SFC_EXPECTED) && c->uart == 48000000 && SOURCE_OK(c->con2) &&
           tick_ok(ticks) && (JL_TIMER4->CON & 15u) == 9u
#if LUNAR_DEVKIT_STOCK_POWER
           && rails_are_stock(r)
#endif
           ;
}

#if LUNAR_DEVKIT_SFC_BAUD == 2
/* The SDK restores the boot-time SFC BAUD (1) inside every clock change.
 * Set BAUD 2 with the other core held and this core's interrupts off,
 * running from SRAM as the SDK's own sfc_flash_baud_div does [verified:
 * vm_sfc.c IR: a NULL callback holds the other core]. */
static __attribute__((noinline)) AT_VOLATILE_RAM_CODE void sfc_baud_held(u8 div)
{
    cpu_enter_sfc_critical(NULL, NULL);
    sfc_flash_baud_div(div);
    cpu_exit_sfc_critical();
}
#endif

static int switch_to_360(uint32_t (*now)(void), const struct rails *r0)
{
    struct clocks c1;
    struct rails r1;
#if LUNAR_DEVKIT_STOCK_POWER
    rails_write(NULL);
    rails_read(&r1);
    if (!rails_are_stock(&r1)) {
        /* The clock has not been touched: the kit's rails are safe. */
        rails_write(r0);
        return fail(RAIL_READBACK);
    }
#else
    (void)r0;
#endif
    int rc = system_clock_set(FM1_SYS);
#if LUNAR_DEVKIT_SFC_BAUD == 2
    if (!rc) sfc_baud_held(LUNAR_DEVKIT_SFC_BAUD);
#endif
    clocks_read(&c1);
    rails_read(&r1);
    uint32_t ticks1 = tick_ticks(now);
    /* Bitwise, so the after receipt has one call site. */
    int ok = at_fm1(&c1, &r1, ticks1) & !rc;
    receipt("after", ok ? "PASS" : "FAIL", &c1, &r1, ticks1, rc);
    if (ok) return 1;
    /* Fail closed. Back to the kit's clock if it moved (a refused switch may
     * still have moved it), then read it again. The rails come down only once
     * sys and HSB read back at 320/160 MHz; otherwise the stock rails stay,
     * since they are the FM-1's own at 360 MHz and above the kit's at 320, so
     * safe at either clock. Lowering them with the core still fast would
     * undervolt it. Either way audio stays halted until a reset. */
    int back = near(c1.sys, KIT_SYS) ? 0 : system_clock_set(KIT_SYS);
    clocks_read(&c1);
    int down = !back && tree(&c1, KIT_SYS);
#if LUNAR_DEVKIT_STOCK_POWER
    if (down) rails_write(r0);
#endif
    rails_read(&r1);
    receipt("restored", down ? "OK rails=kit" : "FAIL rails=kept", &c1, &r1, 0, back);
    return fail(down ? READBACK : NOT_BACK);
}
#else
/* The kit's boot tree: the fixed 320 MHz tap, both post-dividers /1. */
#define SOURCE_OK(con2) (((con2) & 0xFFu) == 2u)
#endif

int lunar_clock360_apply(uint32_t (*now)(void))
{
    struct clocks c0;
    struct rails r0;
    clocks_read(&c0);
    rails_read(&r0);
    uint32_t ticks0 = tick_ticks(now);
    receipt("before", "-", &c0, &r0, ticks0, 0);
    pll_receipt();
    /* Read only so far. Check the kit is in the state the corrected analysis
     * describes: 320/160/53.3 MHz from the fixed 320 MHz tap, HSB /2, LSB /3,
     * a 10 ms tick, the 48 MHz UART, DCDC on. */
    if (!tree(&c0, KIT_SYS)) return fail(NOT_AT_320);
    if (!SOURCE_OK(c0.con2)) return fail(NOT_KIT_SOURCE);
    if (((c0.div >> 16) & 3u) != 1u || ((c0.div >> 8) & 7u) != 2u) return fail(BUS_DIVIDERS);
    if (!tick_ok(ticks0)) return fail(TICK_BEFORE);
    if (c0.uart != 48000000) return fail(UART_CLOCK);
    if (!((r0.b[CON0] >> 3) & 1u)) return fail(DCDC_OFF);
#if LUNAR_DEVKIT_CLOCK360_SWITCH
    return switch_to_360(now, &r0);
#else
    /* The state is as analysed, and from it no reviewed path to 360 MHz
     * exists (top of file). Nothing has been written. */
    return fail(NO_REVIEWED_SWITCH);
#endif
}

void lunar_clock360_end(uint32_t (*now)(void))
{
    struct clocks c;
    struct rails r;
    clocks_read(&c);
    rails_read(&r);
    uint32_t ticks = tick_ticks(now);
    receipt("end", "-", &c, &r, ticks, 0);
}

int lunar_clock360_audio_rate(uint32_t callbacks, uint32_t ticks)
{
    /* 64 frames per callback, TIMER4 at 24 MHz; milli-hertz. */
    uint32_t mhz = ticks ? (uint32_t)((uint64_t)callbacks * 64u * 24000000000ull / ticks) : 0;
    /* +-0.5 %: a rate tied to the system PLL would move by 360/320 (+12.5 %). */
    int ok = mhz >= 43879500u && mhz <= 44320500u;
    printf("LUNAR_CLOCK360 audio=preroll cb=%u t4=%u rate_mhz=%u result=%s\n",
           (unsigned)callbacks, (unsigned)ticks, (unsigned)mhz, ok ? "PASS" : "FAIL");
    return ok;
}

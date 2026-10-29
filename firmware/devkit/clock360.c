/* SPDX-License-Identifier: MIT. Private dev-kit diagnostic.
 *
 * Runs the AC79 dev kit at the FM-1's stock clock and power profile, so a
 * board run times the firmware as the FM-1 would. App-only: the kit's flash
 * head, isd_config and SPL are untouched; everything here happens at run
 * time, after boot, before audio starts.
 *
 * Evidence (SDK V1.2.13 at e30b1ee; vendor IR kept private):
 * - system_clock_set(clk) is clock_set(clk, sdram, index -1): it keeps the
 *   PLL source and the HSB/LSB dividers, writes no rail, and refuses with
 *   -22 while a low-power target such as the running DAC is busy or when
 *   the clock is unchanged [verified: clock.c IR]. clk_set("sys") is a
 *   no-op [verified: clock.c IR]. system_vdd_clock_set() is not used: its
 *   table lowers the rails.
 * - The rail macros are the SDK's own (asm/p33.h): SYSVDD P3_ANA_CON9[3:0],
 *   VDC14 P3_ANA_CON6[2:0], VDDIOM P3_ANA_CON5[2:0], VDDIOW P3_ANA_CON5[5:4],
 *   VLVD P3_VLVD_CON[5:3] enable [0], DCDC13_EN P3_ANA_CON0[3]
 *   [verified: header]; power_init writes them through the same
 *   P33_CON_SET calls [verified: power_hw.c IR].
 * - FM-1 stock levels: SYSVDD 1.38 V, VDC14 1.60 V with DCDC, VDDIOM and
 *   VDDIOW 3.2 V, LVD 2.6 V [reported: fm1-nes board_power.c, from stock
 *   FM-1_010]. The kit's demo board asks for SYSVDD 1.26 V, VDC14 1.40 V
 *   with DCDC, VDDIOM 3.2 V and LVD 2.5 V [verified: demo_hello board.c and
 *   app_config.h]; the boot values are read back here, not assumed.
 * - The OS tick follows the change: port.c's clock_critical_exit sets
 *   TTMR_PRD = clk_get("sys") / 100 [verified: port.c IR]. TIMER4 runs from
 *   the 24 MHz oscillator (CON = 9, set by sdk_worker.c) and the UARTs from
 *   the 48 MHz USB PLL (PLL_48M) [verified: board.c, clk_early_init IR].
 * - SFC = HSB / (BAUD + 1). At HSB 180 MHz the kit's saved BAUD 1 gives
 *   90 MHz, which is what the FM-1 is thought to run [inferred]; BAUD 2 gives
 *   60 MHz. The kit's flash is JEDEC 5E4017 [reported: Codex bring-up note]
 *   and its 90 MHz rating is not established, so 60 MHz is the default.
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

/* Exported by the pinned SDK libraries without a public prototype
 * [verified: vm_sfc.c and clock.c IR]. */
extern void cpu_enter_sfc_critical(void (*cb)(void *), void *priv);
extern void cpu_exit_sfc_critical(void);
extern int sfc_flash_baud_div(u8 div);

#define KIT_SYS 320000000
#define KIT_HSB 160000000
#define FM1_SYS 360000000
#define FM1_HSB 180000000
#define FM1_LSB 60000000
#define SFC_EXPECTED (FM1_HSB / (LUNAR_DEVKIT_SFC_BAUD + 1))
/* Ten OS ticks of 10 ms in TIMER4 counts, -2 %..+1 % (wake-up latency). */
#define TICK_LOW 2352000u
#define TICK_HIGH 2424000u

struct clocks { int sys, hsb, lsb, sfc, uart; u32 con2, div, pll0, pll1; };
struct rails { u8 con0, con5, con6, con9, vlvd; };

static void clocks_read(struct clocks *c)
{
    c->sys = clk_get("sys"); c->hsb = clk_get("hsb"); c->lsb = clk_get("lsb");
    c->sfc = clk_get("sfc"); c->uart = clk_get("uart");
    c->con2 = JL_CLOCK->CLK_CON2; c->div = JL_CLOCK->SYS_DIV;
    c->pll0 = JL_ANA->PLL2_CON0; c->pll1 = JL_ANA->PLL2_CON1;
}

static void rails_read(struct rails *r)
{
    r->con0 = P33_CON_GET(P3_ANA_CON0); r->con5 = P33_CON_GET(P3_ANA_CON5);
    r->con6 = P33_CON_GET(P3_ANA_CON6); r->con9 = P33_CON_GET(P3_ANA_CON9);
    r->vlvd = P33_CON_GET(P3_VLVD_CON);
}

/* Ten OS ticks, aligned to a tick edge first, in TIMER4 counts. */
static uint32_t tick_ticks(uint32_t (*now)(void))
{
    os_time_dly(1);
    uint32_t before = now();
    os_time_dly(10);
    return now() - before;
}

/* One line per phase. The P33 bytes are printed raw, in the order
 * ana_con0,ana_con5,ana_con6,ana_con9,vlvd_con; decode them with the field
 * map at the top of this file (SYSVDD = con9 & 15, VDC14 = con6 & 7, VDDIOM =
 * con5 & 7, VDDIOW = (con5 >> 4) & 3, LVD = (vlvd >> 3) & 7, LVD enable =
 * vlvd & 1, DCDC13 = (con0 >> 3) & 1). tick is ten OS ticks in TIMER4
 * counts (2,400,000 at 10 ms). Kept short: the kit's writer region has
 * under 1 KB to spare at 360 MHz. */
static void receipt(const char *phase, const char *result, const struct clocks *c,
                    const struct rails *r, uint32_t ticks, int rc)
{
    printf("LUNAR_CLOCK360 phase=%s result=%s sys=%d hsb=%d lsb=%d sfc=%d uart=%d "
           "con2=%x div=%x pll=%x,%x p33=%x,%x,%x,%x,%x tick=%u t4=%x rc=%d\n",
           phase, result, c->sys, c->hsb, c->lsb, c->sfc, c->uart,
           (unsigned)c->con2, (unsigned)c->div, (unsigned)c->pll0, (unsigned)c->pll1,
           r->con0, r->con5, r->con6, r->con9, r->vlvd,
           (unsigned)ticks, (unsigned)JL_TIMER4->CON, rc);
}

/* Failure reasons, printed as numbers to keep the image inside the kit's
 * writer region; clock360.h lists them. */
enum { NOT_AT_320 = 1, PLL_SOURCE_NOT_6, BUS_DIVIDERS, TICK_BEFORE, UART_CLOCK, DCDC_OFF,
       RAIL_READBACK, READBACK };

static int fail(int reason)
{
    printf("LUNAR_CLOCK360 result=FAIL reason=%d audio=halted\n", reason);
    return 0;
}

static int near(int value, int expected) { return value >= expected - 1000 && value <= expected + 1000; }

/* Stock order (power_init): VDDIOM, VDC14, VDDIOW, then SYSVDD; LVD level
 * last, its enable untouched. Raise before the clock goes up. */
static void rails_stock(void)
{
    VDDIOM_VOL_SEL(VDDIOM_VOL_32V); os_time_dly(2);
    VDC14_VOL_SEL(VDC14_VOL_SEL_160V); os_time_dly(2);
    VDDIOW_VOL_SEL(VDDIOW_VOL_32V); os_time_dly(2);
    SYSVDD_VOL_SEL(SYSVDD_VOL_SEL_138V); os_time_dly(2);
    VLVD_SEL(VLVD_SEL_26V); os_time_dly(2);
}

/* Lower only after the clock is back down; reverse order. */
static void rails_restore(const struct rails *r)
{
    VLVD_SEL((r->vlvd >> 3) & 7u); os_time_dly(2);
    SYSVDD_VOL_SEL(r->con9 & 15u); os_time_dly(2);
    VDDIOW_VOL_SEL((r->con5 >> 4) & 3u); os_time_dly(2);
    VDC14_VOL_SEL(r->con6 & 7u); os_time_dly(2);
    VDDIOM_VOL_SEL(r->con5 & 7u); os_time_dly(2);
}

static int rails_are_stock(const struct rails *r)
{
    return (r->con9 & 15u) == SYSVDD_VOL_SEL_138V && (r->con6 & 7u) == VDC14_VOL_SEL_160V &&
           (r->con5 & 7u) == VDDIOM_VOL_32V && ((r->con5 >> 4) & 3u) == VDDIOW_VOL_32V &&
           ((r->vlvd >> 3) & 7u) == VLVD_SEL_26V && (r->vlvd & 1u) &&
           ((r->con0 >> 3) & 1u);
}

#if LUNAR_DEVKIT_SFC_BAUD == 2
/* The SDK restores the kit's boot-time SFC BAUD (1) inside every clock
 * change, which is 90 MHz at HSB 180. Set BAUD 2 with the other core held
 * and this core's interrupts off, running from SRAM as the SDK's own
 * sfc_flash_baud_div does [verified: vm_sfc.c IR: a NULL callback holds the
 * other core]. noinline keeps LTO from folding it back into XIP code. */
static __attribute__((noinline)) AT_VOLATILE_RAM_CODE void sfc_baud_held(u8 div)
{
    cpu_enter_sfc_critical(NULL, NULL);
    sfc_flash_baud_div(div);
    cpu_exit_sfc_critical();
}
#endif

int lunar_clock360_apply(uint32_t (*now)(void))
{
    struct clocks c0, c1;
    struct rails r0, r1;
    clocks_read(&c0);
    rails_read(&r0);
    uint32_t ticks0 = tick_ticks(now);
    /* The targets (sys 360, HSB 180, LSB 60 MHz, SFC, rails) are in the
     * build receipt, lunar-devkit-input.json, not printed here. */
    receipt("before", "-", &c0, &r0, ticks0, 0);
    /* Preconditions: change nothing unless the kit is in the state the
     * analysis assumed: 320/160/53.3 MHz from PLL source 6 (PLL = 1.5 x sys,
     * so 540 MHz after), HSB /2, LSB /3, a 10 ms tick, the 48 MHz UART. */
    if (!near(c0.sys, KIT_SYS) || !near(c0.hsb, KIT_HSB)) return fail(NOT_AT_320);
    if ((c0.con2 & 15u) != 6u) return fail(PLL_SOURCE_NOT_6);
    if (((c0.div >> 16) & 3u) != 1u || ((c0.div >> 8) & 7u) != 2u) return fail(BUS_DIVIDERS);
    if (ticks0 < TICK_LOW || ticks0 > TICK_HIGH) return fail(TICK_BEFORE);
    if (c0.uart != 48000000) return fail(UART_CLOCK);
    if (!((r0.con0 >> 3) & 1u)) return fail(DCDC_OFF);
#if LUNAR_DEVKIT_STOCK_POWER
    rails_stock();
    rails_read(&r1);
    if (!rails_are_stock(&r1)) {
        rails_restore(&r0);
        receipt("rails", "FAIL", &c0, &r1, ticks0, 0);
        return fail(RAIL_READBACK);
    }
#endif
    int rc = system_clock_set(FM1_SYS);
#if LUNAR_DEVKIT_SFC_BAUD == 2
    if (!rc) sfc_baud_held(LUNAR_DEVKIT_SFC_BAUD);
#endif
    clocks_read(&c1);
    rails_read(&r1);
    uint32_t ticks1 = tick_ticks(now);
    int ok = !rc && near(c1.sys, FM1_SYS) && near(c1.hsb, FM1_HSB) && near(c1.lsb, FM1_LSB) &&
             near(c1.sfc, SFC_EXPECTED) && c1.uart == 48000000 && (c1.con2 & 15u) == 6u &&
             ticks1 >= TICK_LOW && ticks1 <= TICK_HIGH && (JL_TIMER4->CON & 15u) == 9u;
#if LUNAR_DEVKIT_STOCK_POWER
    ok = ok && rails_are_stock(&r1);
#endif
    receipt("after", ok ? "PASS" : "FAIL", &c1, &r1, ticks1, rc);
    if (ok) return 1;
    /* Fail closed: back to the kit's clock, then its rails, then halt audio. */
    int back = rc ? 0 : system_clock_set(KIT_SYS);
#if LUNAR_DEVKIT_STOCK_POWER
    rails_restore(&r0);
#endif
    clocks_read(&c1);
    rails_read(&r1);
    receipt("restored", "FAIL", &c1, &r1, tick_ticks(now), back);
    return fail(READBACK);
}

int lunar_clock360_audio_rate(const char *window, uint32_t callbacks, uint32_t ticks)
{
    /* 64 frames per callback, TIMER4 at 24 MHz; milli-hertz. */
    uint32_t mhz = ticks ? (uint32_t)((uint64_t)callbacks * 64u * 24000000000ull / ticks) : 0;
    /* +-0.5 %: a rate tied to the system PLL would move by 360/320 (+12.5 %). */
    int ok = mhz >= 43879500u && mhz <= 44320500u;
    printf("LUNAR_CLOCK360 audio=%s cb=%u t4=%u rate_mhz=%u result=%s\n",
           window, (unsigned)callbacks, (unsigned)ticks, (unsigned)mhz, ok ? "PASS" : "FAIL");
    return ok;
}

/* Behavioural host model for firmware/devkit/clock360.c. One scenario per
 * run (argv[1]); prints the module's own lines plus FAKE lines for the test.
 * Models: the SDK clock change keeps PLL source and bus dividers and restores
 * the boot SFC BAUD; the OS tick period is TTMR_PRD system clocks; TIMER4
 * counts 24 MHz; P33 fields are plain bit fields. */
#include <stdlib.h>
#include <string.h>
#include "clock360_sdk_stub.h"
#include "clock360.h"

fake_clock_t fake_clock;
fake_ana_t fake_ana;
fake_timer_t fake_timer4;
JL_TypeDef_q32DSP fake_q32;
fake_sfc_t fake_sfc;
static u8 p33[256];
static uint64_t t24;          /* TIMER4 time, 24 MHz */
static uint32_t sys = 320000000, hsb_div = 2, lsb_div = 3, baud = 1, boot_baud = 1;
static int refuse, refuse_320, moved, bad_hsb, stale_tick, rail_stuck, critical, critical_max;
static unsigned clock_sets, p33_writes;

int clk_get(const char *n)
{
    uint32_t hsb = sys / hsb_div;
    if (!strcmp(n, "sys")) return (int)sys;
    if (!strcmp(n, "hsb")) return (int)hsb;
    if (!strcmp(n, "lsb")) return (int)(hsb / lsb_div);
    if (!strcmp(n, "sfc")) return (int)(hsb / (baud + 1));
    if (!strcmp(n, "uart")) return 48000000;
    return 0;
}

int system_clock_set(u32 clk)
{
    ++clock_sets;
    printf("FAKE system_clock_set %u rails_set_before=%u\n", (unsigned)clk, p33_writes);
    if (moved && clk == 360000000u) {
        /* Refused, but the PLL moved anyway: a partial change. */
        sys = clk;
        fake_q32.TTMR_PRD = sys / 100u;
        return -22;
    }
    if (refuse || (refuse_320 && clk == 320000000u) || clk == sys) return -22;
    sys = clk;
    if (bad_hsb && clk == 360000000u) hsb_div = 3;
    if (clk == 320000000u) hsb_div = 2;
    baud = boot_baud;
    fake_sfc.BAUD = baud;
    fake_q32.TTMR_PRD = stale_tick && clk == 360000000u ? 3200000u : sys / 100u;
    fake_ana.PLL2_CON1 = sys / 100000u;
    return 0;
}

int sfc_flash_baud_div(u8 d)
{
    printf("FAKE sfc_flash_baud_div %u held=%d\n", d, critical);
    baud = d;
    fake_sfc.BAUD = d;
    return 0;
}
void cpu_enter_sfc_critical(void (*cb)(void *), void *priv)
{
    (void)priv;
    if (cb) abort();
    if (++critical > critical_max) critical_max = critical;
}
void cpu_exit_sfc_critical(void) { --critical; }

static void advance(uint64_t ticks)
{
    t24 += ticks;
    fake_timer4.CNT = (u32)t24;
    uint64_t cycles = t24 * (sys / 1000000u) / 24u;
    fake_q32.TTMR_CNT = (u32)(cycles % fake_q32.TTMR_PRD);
}

void os_time_dly(int ticks)
{
    /* One OS tick = TTMR_PRD system clocks, in TIMER4 counts. */
    uint64_t period = (uint64_t)fake_q32.TTMR_PRD * 24000000u / sys;
    advance(period * (uint64_t)ticks + 300u);
}

static uint32_t now(void) { advance(11); return (uint32_t)t24; }

void P33_CON_SET(u16 a, u8 start, u8 len, u8 v)
{
    if (rail_stuck && a == P3_ANA_CON9 && v == 15) return;
    u8 mask = (u8)(((1u << len) - 1u) << start);
    p33[a] = (u8)((p33[a] & ~mask) | ((v << start) & mask));
    ++p33_writes;
}
u8 P33_CON_GET(u16 a) { return p33[a]; }

int main(int argc, char **argv)
{
    const char *s = argc > 1 ? argv[1] : "pass";
    fake_clock.CLK_CON2 = 6;
    fake_clock.SYS_DIV = (1u << 16) | (2u << 8);
    fake_q32.TTMR_PRD = sys / 100u;
    fake_timer4.CON = 9;
    fake_sfc.BAUD = baud;
    /* Kit boot rails (demo_hello): DCDC on, SYSVDD 1.26, VDC14 1.40, VDDIOM
     * 3.2, VDDIOW 2.1, LVD 2.5 enabled. */
    p33[P3_ANA_CON0] = 1u << 3;
    p33[P3_ANA_CON5] = 4u;
    p33[P3_ANA_CON6] = 3u;
    p33[P3_ANA_CON9] = 11u;
    p33[P3_VLVD_CON] = (6u << 3) | 1u;
    if (!strcmp(s, "refuse")) refuse = 1;
    else if (!strcmp(s, "bad_hsb")) bad_hsb = 1;
    else if (!strcmp(s, "stale_tick")) stale_tick = 1;
    else if (!strcmp(s, "rail_stuck")) rail_stuck = 1;
    else if (!strcmp(s, "at_240")) sys = 240000000;
    else if (!strcmp(s, "pll_source")) fake_clock.CLK_CON2 = 5;
    else if (!strcmp(s, "dcdc_off")) p33[P3_ANA_CON0] = 1u << 2;
    /* A readback fails at 360 MHz, then the SDK refuses the way back. */
    else if (!strcmp(s, "restore_refuse")) stale_tick = refuse_320 = 1;
    /* The switch is refused but the clock moved; the way back works. */
    else if (!strcmp(s, "moved")) moved = 1;
    /* The switch is refused, the clock moved, and the way back is refused. */
    else if (!strcmp(s, "moved_stuck")) moved = refuse_320 = 1;
    else if (strcmp(s, "pass") && strcmp(s, "end_drift")) return 2;
    int ok = lunar_clock360_apply(now);
    if (ok) {
        /* The end-of-run readback; end_drift has an SDK path put the boot
         * BAUD back behind the module's back. */
        if (!strcmp(s, "end_drift")) fake_sfc.BAUD = baud = boot_baud;
        lunar_clock360_end(now);
    }
    printf("FAKE result=%d sys=%u hsb=%d sfc=%d clock_sets=%u critical=%d critical_max=%d "
           "sysvdd=%u vdc14=%u vddiom=%u vddiow=%u vlvd=%u\n",
           ok, (unsigned)sys, clk_get("hsb"), clk_get("sfc"), clock_sets, critical, critical_max,
           p33[P3_ANA_CON9] & 15u, p33[P3_ANA_CON6] & 7u, p33[P3_ANA_CON5] & 7u,
           (p33[P3_ANA_CON5] >> 4) & 3u, (p33[P3_VLVD_CON] >> 3) & 7u);
    /* The audio-rate gate: 44,100 Hz and a PLL-tied +12.5 %. */
    lunar_clock360_audio_rate("nominal", 10000, (uint32_t)(10000ull * 64u * 24000000u / 44100u));
    lunar_clock360_audio_rate("shifted", 10000, (uint32_t)(10000ull * 64u * 24000000u / 49612u));
    return 0;
}

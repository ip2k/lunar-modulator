/* A host model of the few SDK V1.2.13 names firmware/devkit/clock360.c uses,
 * for a behavioural test of its decisions (fake_sdk.c). Not the SDK: the
 * register numbers and enum values are copied from asm/p33.h so the macros
 * expand the same way; clocks, rails and timers are simulated. */
#ifndef CLOCK360_SDK_STUB_H
#define CLOCK360_SDK_STUB_H
#include <stdint.h>
#include <stdio.h>
#include <stddef.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;

#define AT_VOLATILE_RAM_CODE
#define local_irq_save(f) ((f) = 0)
#define local_irq_restore(f) ((void)(f))

int clk_get(const char *name);
int system_clock_set(u32 clk);
void os_time_dly(int ticks);
static inline int current_cpu_id(void) { return 0; }

typedef struct { volatile u32 CLK_CON2, SYS_DIV; } fake_clock_t;
typedef struct { volatile u32 PLL_CON0, PLL2_CON0, PLL2_CON1; } fake_ana_t;
typedef struct { volatile u32 CON0; } fake_sdr_t;
typedef struct { volatile u32 CON, CNT, PRD; } fake_timer_t;
typedef struct { volatile u32 TTMR_CNT, TTMR_PRD; } JL_TypeDef_q32DSP;
typedef struct { volatile u32 CON, BAUD; } fake_sfc_t;
extern fake_clock_t fake_clock;
extern fake_ana_t fake_ana;
extern fake_timer_t fake_timer4;
extern JL_TypeDef_q32DSP fake_q32;
extern fake_sfc_t fake_sfc;
extern fake_sdr_t fake_sdr;
extern volatile u32 fake_husb_com[3];
#define JL_CLOCK (&fake_clock)
#define JL_ANA (&fake_ana)
#define JL_TIMER4 (&fake_timer4)
#define JL_SFC (&fake_sfc)
#define JL_SDR (&fake_sdr)
#define HUSB_COM_CON0 (fake_husb_com[0])
#define HUSB_COM_CON2 (fake_husb_com[2])
#define q32DSP(n) ((void)(n), &fake_q32)

/* asm/p33.h */
#define P3_ANA_CON0 0x00
#define P3_ANA_CON5 0x05
#define P3_ANA_CON6 0x06
#define P3_ANA_CON9 0x09
#define P3_VLVD_CON 0x11
void P33_CON_SET(u16 addr, u8 start, u8 len, u8 data);
u8 P33_CON_GET(u16 addr);
#define VDDIOM_VOL_SEL(lev) P33_CON_SET(P3_ANA_CON5, 0, 3, lev)
#define VDDIOW_VOL_SEL(lev) P33_CON_SET(P3_ANA_CON5, 4, 2, lev)
#define VDC14_VOL_SEL(sel) P33_CON_SET(P3_ANA_CON6, 0, 3, sel)
#define SYSVDD_VOL_SEL(sel) P33_CON_SET(P3_ANA_CON9, 0, 4, sel)
#define VLVD_SEL(lev) P33_CON_SET(P3_VLVD_CON, 3, 3, lev)
enum { VDDIOM_VOL_32V = 4 };
enum { VDDIOW_VOL_21V = 0, VDDIOW_VOL_32V = 3 };
enum { VDC14_VOL_SEL_140V = 3, VDC14_VOL_SEL_160V = 7 };
enum { SYSVDD_VOL_SEL_126V = 11, SYSVDD_VOL_SEL_138V = 15 };
enum { VLVD_SEL_25V = 6, VLVD_SEL_26V = 7 };
#endif

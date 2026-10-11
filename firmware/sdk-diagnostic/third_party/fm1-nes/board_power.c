/* FM-1_010 power parameters recovered from its inlined power-init path.
 * Use SDK-owned state/helpers/IRQs, never stock RAM/function addresses.
 * Public build checks SDK instructions and these parameters with audit_power.py.
 * Stock images and private disassembly evidence are not redistributed.
 */
#ifndef FM1_BOARD_POWER_TEST
#include "app_config.h"
#if __SDRAM_SIZE__ != 0
#error "FM-1 stock power profile is qualified for no-SDRAM builds only"
#endif
#if defined(CONFIG_EXCEPTION_AUTO_FIX_ENABLE) || defined(CONFIG_RF_TEST_ENABLE) || defined(CONFIG_READ_RF_PARAM_FROM_CFGTOOL_ENABLE)
#error "Do not enable automatic flash repair or cfg-tool voltage overrides in FM-1"
#endif
#endif
#include "board_power.h"
#include "asm/power_interface.h"
#include "asm/p33.h"
#include <stddef.h>

typedef char power_param_layout_check[
    sizeof(struct low_power_param)==20 &&
    offsetof(struct low_power_param,config)==10 &&
    offsetof(struct low_power_param,vddiom_lev)==12 &&
    offsetof(struct low_power_param,sysvdd_lev)==16 &&
    offsetof(struct low_power_param,vlvd_enable)==19 ? 1 : -1];
typedef char power_selector_check[
    VDDIOM_VOL_32V==4 && VDDIOW_VOL_32V==3 && VDC14_VOL_SEL_160V==7 &&
    SYSVDD_VOL_SEL_138V==15 && VLVD_SEL_26V==7 ? 1 : -1];

#if defined(__clang__) || defined(__GNUC__)
__attribute__((used))
#endif
const struct low_power_param fm1_stock_power_param = {
    /* Pinned SDK ignores osc_type/osc_hz/delay_us/pd_wdvdd_lev in this path:
     * it selects LRC and 32000 internally, matching stock's reviewed path.
     * Keep unused input fields zero; do not invent stock source values. */
    .osc_type=0, .osc_hz=0, .delay_us=0,
    .config=0, .btosc_disable=0,
    .vddiom_lev=VDDIOM_VOL_32V,       /* stock 0x02004A6E: reg5 bits0..2 = 4 */
    .vddiow_lev=VDDIOW_VOL_32V,      /* stock 0x02004A8A: reg5 bits4..5 = 3 */
    .vdc14_lev=VDC14_VOL_SEL_160V,   /* stock 0x02004A7C: reg6 bits0..2 = 7 */
    .vdc14_dcdc=1,                  /* stock 0x020049D2..0x02004A1E */
    .sysvdd_lev=SYSVDD_VOL_SEL_138V, /* stock 0x02004ADC: reg9 bits0..3 = 15 */
    .pd_wdvdd_lev=0,
    .vlvd_value=VLVD_SEL_26V,        /* stock 0x0200499E: reg11 bits3..5 = 7 */
    .vlvd_enable=1                  /* stock 0x020049B8: reg11 bit0 = 1 */
};
volatile uint32_t fm1_power_stage;
static int initialized;

#if defined(__clang__) || defined(__GNUC__)
__attribute__((noinline,used))
#endif
void fm1_board_power_init(void) {
    if(initialized)return;
    fm1_power_stage=1;
    power_init(&fm1_stock_power_param);
    initialized=1;
    fm1_power_stage=2;
}

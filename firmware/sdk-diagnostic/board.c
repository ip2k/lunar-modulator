/* SPDX-License-Identifier: MIT */
#include "app_config.h"
#include "system/includes.h"
#include "device/includes.h"
#include "board_power.h"
REGISTER_DEVICES(device_table) = {};
volatile unsigned lunar_sdk_board_stage;
void board_early_init(void) { lunar_sdk_board_stage = 1; }
void board_init(void) {
    fm1_board_power_init();
    lunar_sdk_board_stage = 2;
}

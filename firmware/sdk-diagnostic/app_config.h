/* SPDX-License-Identifier: MIT */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H
#define __FLASH_SIZE__ (1024 * 1024)
#define __SDRAM_SIZE__ 0
#define LIB_DEBUG 0
#define CONFIG_DEBUG_LIB(x) 0
#if defined(CONFIG_EXCEPTION_AUTO_FIX_ENABLE) || defined(CONFIG_RF_TEST_ENABLE) || defined(CONFIG_READ_RF_PARAM_FROM_CFGTOOL_ENABLE)
#error "No flash repair, RF test or voltage overrides in the diagnostic"
#endif
#endif

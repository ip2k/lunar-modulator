/* SPDX-License-Identifier: MIT. Existing pi32v2 SDK convention only.
 * This is NOT an SDK-free native CPU1/cache implementation. */
#ifndef LUNAR_RENDERER_PIPELINE_SDK_PLATFORM_H
#define LUNAR_RENDERER_PIPELINE_SDK_PLATFORM_H
#include "app_config.h"
#include "system/includes.h"
#include "os/os_api.h"
#include "asm/includes.h"
#include <stdint.h>
typedef volatile uint32_t lunar_pipeline_word_t;
typedef volatile int lunar_pipeline_status_t;
static inline __attribute__((always_inline)) void port_fence(void) { __asm__ volatile("csync;" ::: "memory"); }
#define LUNAR_PIPELINE_PORT_DEFINED 1
#define LUNAR_PIPELINE_CORE_COLD _Pragma("code_seg()")
#endif

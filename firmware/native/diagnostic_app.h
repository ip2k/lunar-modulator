/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_DIAGNOSTIC_APP_H
#define LUNAR_DIAGNOSTIC_APP_H
#include <stdint.h>
#include "fm1_app.h"
#if !FM1_APP_EXTERNAL_ARENAS
#error "diagnostic profile requires FM1_APP_EXTERNAL_ARENAS=1 in every TU"
#endif
#include "diagnostic_api.h"
const fm1_app_t *lunar_diagnostic_state(void);
#endif

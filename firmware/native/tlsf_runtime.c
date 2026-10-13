/* SPDX-License-Identifier: MIT */
/* Private native adapter; the BSD-3-Clause TLSF sources remain unmodified.
 * Invalid pool parameters still return failure. Suppress upstream console
 * diagnostics because this bare-metal runtime has no standard output sink. */
#include <stdio.h>
#define printf(...) ((void)0)
#include "tlsf.c"

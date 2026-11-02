// SPDX-License-Identifier: MIT
#ifdef LUNAR_MUSL_HOST_TEST
#include_next <features.h>
#endif
/* Experimental math-only visibility adapter; no libc feature emulation. */
#define hidden __attribute__((visibility("hidden")))

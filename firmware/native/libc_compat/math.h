// SPDX-License-Identifier: MIT
/* Separate toolchain/libc declarations from musl internal kernel names. */
#define __signgam __lunar_toolchain__signgam
#define __sin __lunar_toolchain__sin
#define __cos __lunar_toolchain__cos
#define __tan __lunar_toolchain__tan
#define __sinl __lunar_toolchain__sinl
#define __cosl __lunar_toolchain__cosl
#define __tanl __lunar_toolchain__tanl
#include_next <math.h>
#undef __signgam
#undef __sin
#undef __cos
#undef __tan
#undef __sinl
#undef __cosl
#undef __tanl

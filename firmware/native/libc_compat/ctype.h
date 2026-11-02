/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_NATIVE_CTYPE_H
#define LUNAR_NATIVE_CTYPE_H
#include_next <ctype.h>
/* Use the selected portable functions rather than newlib locale tables. */
#undef isspace
#undef isdigit
#undef isspace_l
#undef isdigit_l
#undef __isspace_l
#undef __isdigit_l
#ifndef LUNAR_MUSL_HOST_TEST
/* The selected ASCII predicates ignore this opaque argument. No locale
 * service is provided; the native app does not call the _l entry points. */
typedef struct lunar_unused_locale *locale_t;
#endif
#endif

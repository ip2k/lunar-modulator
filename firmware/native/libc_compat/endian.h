// SPDX-License-Identifier: MIT
#ifndef LUNAR_MUSL_ENDIAN_H
#define LUNAR_MUSL_ENDIAN_H
#if !defined(__BYTE_ORDER__) || __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error pi32 experiment requires compiler-confirmed little endian
#endif
#define __LITTLE_ENDIAN __ORDER_LITTLE_ENDIAN__
#define __BIG_ENDIAN __ORDER_BIG_ENDIAN__
#define __BYTE_ORDER __BYTE_ORDER__
#endif

/* SPDX-License-Identifier: MIT */
/* Freestanding C++11 construction into caller-owned storage. No allocator. */
#ifndef FM1_PLACEMENT_NEW_H
#define FM1_PLACEMENT_NEW_H
#include <stddef.h>
inline void *operator new(size_t, void *storage) noexcept { return storage; }
inline void operator delete(void *, void *) noexcept {}
#endif

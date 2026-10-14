/* SPDX-License-Identifier: MIT */
#ifndef LUNAR_STACK_WATERMARK_H
#define LUNAR_STACK_WATERMARK_H
#include <stddef.h>
#include <stdint.h>

#define LUNAR_STACK_PATTERN UINT32_C(0xA55AA55A)

/* Memory below the first changed word is still patterned. This is an
 * observed margin, not a worst-case bound: untouched reservations and a write
 * coincidentally equal to the pattern can understate actual stack depth.
 * Only use on word-aligned, entry-painted RAM ranges, excluding guard bands.
 * Interrupts may consume more space during scanning; a later scan observes
 * those stores. Reading never changes the pattern or any active frame. */
static inline size_t lunar_stack_pattern_margin(
    const volatile uint32_t *words, size_t count)
{
    size_t i = 0;
    while (i < count && words[i] == LUNAR_STACK_PATTERN) ++i;
    return i * sizeof *words;
}
#endif

/* SPDX-License-Identifier: GPL-3.0-only
 * Offline CPU0 publication proof. No target startup/profile selects this port.
 * Saved ICFG pattern: Dinghy hal/fm1_irq.h (Leo Kuroshita / Hügelton Instruments);
 * instruction facts cross-checked against AC79 SDK e30b1ee asm/irq.h.
 */
#ifndef LUNAR_DIAGNOSTIC_PUBLICATION_PI32V2_H
#define LUNAR_DIAGNOSTIC_PUBLICATION_PI32V2_H
#if !defined(LUNAR_DIAGNOSTIC_OFFLINE_PROOF) || LUNAR_DIAGNOSTIC_OFFLINE_PROOF != 1
#error "offline proof required"
#endif
#if !defined(LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION) || LUNAR_DIAGNOSTIC_PI32V2_PUBLICATION != 1
#error "explicit publication selection required"
#endif
#if !defined(LUNAR_DIAGNOSTIC_CPU0_ONLY) || LUNAR_DIAGNOSTIC_CPU0_ONLY != 1
#error "CPU0-only proof required"
#endif
#if !defined(__PI32V2__) && !defined(LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED)
#error "pi32v2 compiler or injected test required"
#endif
#if defined(LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED) && defined(__PI32V2__)
#error "injected backend is host test only"
#endif
#include <stdint.h>
/* Private scalar storage, NOT ISO C11 atomics. CPU0 main/normal IRQ SPSC only:
 * no CPU1, DMA, OS threads, asynchronous reset, or outside field access. Each
 * word is aligned normal SRAM. Payload lifetime still belongs to transport.
 */
typedef uint32_t lunar_publication_word_t;
_Static_assert(sizeof(lunar_publication_word_t)==4, "32-bit publication word");
_Static_assert(_Alignof(lunar_publication_word_t)==4, "aligned publication word");
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
uint32_t lunar_pub_test_icfg_read(void);
void lunar_pub_test_icfg_write(uint32_t);
void lunar_pub_test_barrier(void);
uint32_t lunar_pub_test_word_read(const uint32_t *);
void lunar_pub_test_word_write(uint32_t *,uint32_t);
#endif
/* Include-only implementation keeps every primitive inline at its caller even
 * without LTO. No callable helper may survive inside a masked target region. */
#define LUNAR_PUBLICATION_IMPLEMENTATION
#include "diagnostic_publication_pi32v2.c"
#undef LUNAR_PUBLICATION_IMPLEMENTATION
#endif

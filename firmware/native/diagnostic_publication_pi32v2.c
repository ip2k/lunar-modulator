/* SPDX-License-Identifier: GPL-3.0-only. See paired header for provenance.
 * Include-only: this is not a separately compiled runtime or profile. */
#ifndef LUNAR_PUBLICATION_IMPLEMENTATION
#error "include diagnostic_publication_pi32v2.h instead"
#endif
#define LUNAR_PUB_INLINE static inline __attribute__((always_inline))
LUNAR_PUB_INLINE uint32_t lunar_pub_icfg_read(void) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  return lunar_pub_test_icfg_read();
#else
  uint32_t v; __asm__ volatile("%0 = icfg" : "=r"(v) : : "memory"); return v;
#endif
}
LUNAR_PUB_INLINE void lunar_pub_icfg_write(uint32_t v) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  lunar_pub_test_icfg_write(v);
#else
  __asm__ volatile("icfg = %0" : : "r"(v) : "memory");
#endif
}
LUNAR_PUB_INLINE void lunar_pub_barrier(void) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  lunar_pub_test_barrier();
#else
  __asm__ volatile("csync" : : : "memory");
#endif
}
LUNAR_PUB_INLINE uint32_t lunar_pub_word_read(const lunar_publication_word_t *p) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  return lunar_pub_test_word_read(p);
#else
  uint32_t v; __asm__ volatile("%0 = [%1]" : "=r"(v) : "r"(p) : "memory"); return v;
#endif
}
LUNAR_PUB_INLINE void lunar_pub_word_write(lunar_publication_word_t *p,uint32_t v) {
#ifdef LUNAR_DIAGNOSTIC_PUBLICATION_INJECTED
  lunar_pub_test_word_write(p,v);
#else
  __asm__ volatile("[%0] = %1" : : "r"(p),"r"(v) : "memory");
#endif
}
/* No loop, copy or app callback occurs between capture and exact restoration.
 * csync plus compiler clobbers orders payload access around publication; this
 * is a source/codegen proof only, not cache, DMA or latency admission. */
LUNAR_PUB_INLINE uint32_t lunar_pub_load(const lunar_publication_word_t *p) {
  uint32_t saved=lunar_pub_icfg_read();
  lunar_pub_icfg_write(saved&~0x100u); lunar_pub_barrier();
  uint32_t v=lunar_pub_word_read(p);
  lunar_pub_barrier(); lunar_pub_icfg_write(saved); return v;
}
LUNAR_PUB_INLINE void lunar_pub_store(lunar_publication_word_t *p,uint32_t v) {
  uint32_t saved=lunar_pub_icfg_read();
  lunar_pub_icfg_write(saved&~0x100u); lunar_pub_barrier();
  lunar_pub_word_write(p,v);
  lunar_pub_barrier(); lunar_pub_icfg_write(saved);
}
LUNAR_PUB_INLINE void lunar_pub_fault_first(lunar_publication_word_t *p,uint32_t v) {
  uint32_t saved=lunar_pub_icfg_read();
  lunar_pub_icfg_write(saved&~0x100u); lunar_pub_barrier();
  if(!lunar_pub_word_read(p)) lunar_pub_word_write(p,v);
  lunar_pub_barrier(); lunar_pub_icfg_write(saved);
}
LUNAR_PUB_INLINE void lunar_pub_increment(lunar_publication_word_t *p) {
  uint32_t saved=lunar_pub_icfg_read();
  lunar_pub_icfg_write(saved&~0x100u); lunar_pub_barrier();
  uint32_t v=lunar_pub_word_read(p); lunar_pub_word_write(p,v+1);
  lunar_pub_barrier(); lunar_pub_icfg_write(saved);
}
#undef LUNAR_PUB_INLINE

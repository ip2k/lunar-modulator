/* schwung_module_prefix.h -- force-included (`-include`) ahead of every
 * vendored Schwung module source (engines/mk/schwung.mk).
 *
 * Schwung modules calloc their instance and their buffers in create_instance.
 * The FM-1 has no heap to give them, so after the C library's own headers have
 * been read, malloc/calloc/realloc/free are redirected to the shim's bump
 * arena (schwung_shim.cc). The arena lives inside the fm1 instance memory the
 * host provides, is only open while create_instance runs, and free() does
 * nothing. The vendored sources stay byte-identical to upstream.
 *
 * The macros are function-like, so a struct member or variable that happens
 * to be called `free` is left alone. MIT licence (this file).
 */
#ifndef FM1_SCHWUNG_MODULE_PREFIX_H_
#define FM1_SCHWUNG_MODULE_PREFIX_H_

#include <stddef.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif
void *fm1_sw_malloc(size_t size);
void *fm1_sw_calloc(size_t count, size_t size);
void *fm1_sw_realloc(void *ptr, size_t size);
void fm1_sw_free(void *ptr);
#ifdef __cplusplus
}
#endif

#define malloc(size) fm1_sw_malloc(size)
#define calloc(count, size) fm1_sw_calloc(count, size)
#define realloc(ptr, size) fm1_sw_realloc(ptr, size)
#define free(ptr) fm1_sw_free(ptr)

#endif /* FM1_SCHWUNG_MODULE_PREFIX_H_ */

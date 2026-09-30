/* schwung_abi.h -- includes Schwung's vendored ABI headers
 * (third_party/schwung, MIT, unmodified) so that they build for every target
 * the engines build for.
 *
 * One adaptation is needed. plugin_api_v1.h ends with
 *
 *   _Static_assert(offsetof(host_api_v1_t, reserved) == 120, "...");
 *
 * which pins the aarch64 layout that shipped Move binaries depend on. Two
 * problems follow for us:
 *
 *   - `_Static_assert` is C11. Clang accepts it in C++ as an extension, but g++
 *     does not know it at all, so the header does not compile as C++ with GCC.
 *   - With 4-byte pointers (pi32v2, and CI's -m32 build) `reserved` sits at
 *     +68, so the assertion fails. The offset matters only for binary
 *     compatibility with prebuilt aarch64 modules, which the FM-1 cannot load
 *     anyway: every module here is compiled from source against the same
 *     struct definition as the shim.
 *
 * So, while the vendored headers are read, `_Static_assert` is redirected to
 * C++11 `static_assert` with the condition checked only where pointers are
 * 8 bytes wide. On a 64-bit build the upstream check still runs unchanged.
 * MIT licence (this file).
 */
#ifndef FM1_SCHWUNG_ABI_H_
#define FM1_SCHWUNG_ABI_H_

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wkeyword-macro"
#endif
#define _Static_assert(cond, msg) static_assert(sizeof(void *) != 8 || (cond), msg)
extern "C" {
#endif

#include "plugin_api_v1.h"
#include "audio_fx_api_v2.h"

#ifdef __cplusplus
}
#undef _Static_assert
#if defined(__clang__)
#pragma clang diagnostic pop
#endif
#endif

#endif /* FM1_SCHWUNG_ABI_H_ */

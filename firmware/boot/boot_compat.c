/* firmware/boot/boot_compat.c -- bridge the stock FM-1 SPL's boot hand-off to
 * the AC79 SDK V1.2.13 input ABI.
 *
 * Why this exists (notes/2026-10-05-softkey-efuse.md §4). The FM-1's SPL is
 * SDK V1.1.9's uboot.boot, which we never replace (CLAUDE.md trap 11). It
 * copies six words plus a 32-byte header into the boot_info hand-off. From
 * V1.2.1 the SDK's boot_info_init reads further -- out to +92 bytes
 * (sdram_info at +80, ex_app_info at +88) -- which the stock SPL never writes,
 * so those words are uninitialised SPL RAM [verified: boot.c IR of V1.2.1+ and
 * both SPLs copy six words]. This wrapper hands boot_info_init a 23-word buffer
 * whose first six words are the stock hand-off and whose remaining words are
 * zero, so the extra reads see a defined zero rather than stale RAM.
 *
 * Link it with the LLVM linker's symbol wrapping:
 *     --wrap=boot_info_init
 * which routes the SDK's call to boot_info_init here and exposes the original
 * as __real_boot_info_init.
 *
 * Runs before application RAM is initialised: stack and XIP only -- no globals,
 * library calls, peripherals, logging or key queries. The volatile accesses
 * stop the compiler turning the copy into a memcpy/memset, which would not yet
 * be available. The first word is a pointer to the SPL's separately
 * initialised 32-byte flash header; it is preserved, like every other word of
 * the six.
 *
 * The 6-copy / zero-6..22 contract and the --wrap mechanism follow Keitark's
 * fm1-nes (Apache-2.0) boot_compat.c, which runs this on an FM-1; this is our
 * own MIT implementation. The audit tools/jieli/audit_link.py and
 * fm1-nes's audit_boot.py both pin the resulting machine code.
 *
 * MIT licence, like the rest of this repository.
 */
#include <stdint.h>

#ifndef FM1_BOOT_COMPAT_TEST
#include "app_config.h"
#if defined(__SDRAM_SIZE__) && __SDRAM_SIZE__ != 0
#error "the FM-1 boot bridge is for internal-RAM builds only (SDRAM_SIZE must be 0)"
#endif
#ifdef CONFIG_SDFILE_EXT_ENABLE
#error "the FM-1 boot bridge does not supply external-app metadata"
#endif
#endif

/* The number of words the stock SPL actually fills, and the width the V1.2.x
 * boot_info_init reads. 23 words = 92 bytes. */
#define FM1_STOCK_HANDOFF_WORDS 6
#define FM1_SDK_HANDOFF_WORDS   23

extern void __real_boot_info_init(const volatile uint32_t *argument);

#if defined(__clang__) || defined(__GNUC__)
__attribute__((noinline, used))
#endif
void __wrap_boot_info_init(const volatile uint32_t *stock_argument)
{
    volatile uint32_t sdk_argument[FM1_SDK_HANDOFF_WORDS];
    unsigned i;

    for (i = 0; i < FM1_STOCK_HANDOFF_WORDS; ++i)
        sdk_argument[i] = stock_argument[i];
    for (i = FM1_STOCK_HANDOFF_WORDS; i < FM1_SDK_HANDOFF_WORDS; ++i)
        sdk_argument[i] = 0;

    __real_boot_info_init(sdk_argument);
}

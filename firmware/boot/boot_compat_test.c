/* firmware/boot/boot_compat_test.c -- desktop test for boot_compat.c.
 *
 * Compiles boot_compat.c with -DFM1_BOOT_COMPAT_TEST (no SDK headers) and
 * stands in for the SDK's boot_info_init. Checks the bridge's contract:
 * the six stock words reach the SDK unchanged, words 6..22 arrive zeroed,
 * the source buffer is never written, and the argument stays word-aligned.
 *
 * Built and run by tests/test_boot_compat.py on the desktop. Nothing here
 * runs on a JieLi chip. MIT licence.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void __wrap_boot_info_init(const volatile uint32_t *argument);

static uint32_t expected_prefix[6];
static unsigned calls;

#define CHECK(c) do { if (!(c)) { \
    fprintf(stderr, "FAIL line %d: %s\n", __LINE__, #c); exit(1); } } while (0)

/* The stand-in SDK initializer: it receives the normalized 23-word buffer. */
void __real_boot_info_init(const volatile uint32_t *argument)
{
    unsigned i;
    ++calls;
    CHECK(((uintptr_t)argument & 3u) == 0u);          /* word aligned */
    for (i = 0; i < 6; ++i)
        CHECK(argument[i] == expected_prefix[i]);      /* six stock words kept */
    for (i = 6; i < 23; ++i)
        CHECK(argument[i] == 0u);                      /* extensions zeroed */
}

int main(void)
{
    unsigned i, run;
    uint32_t source[23];

    for (run = 0; run < 3; ++run) {
        /* A recognisable pattern across the full 23 words the SDK may read. */
        for (i = 0; i < 23; ++i)
            source[i] = 0xA5A50000u + (run << 8) + i;
        memcpy(expected_prefix, source, sizeof expected_prefix);

        __wrap_boot_info_init(source);

        /* The source buffer must be untouched (the bridge only reads it). */
        for (i = 0; i < 23; ++i)
            CHECK(source[i] == 0xA5A50000u + (run << 8) + i);
    }
    CHECK(calls == 3);
    puts("boot_compat: prefix copied, extensions zeroed, source preserved");
    return 0;
}

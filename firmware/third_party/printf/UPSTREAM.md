# Standalone formatted output

Source: https://github.com/eyalroz/printf
Pinned commit: `22318ed6bd87b0d597b4a4868d5b00daf66540fd` (2026-06-27).
Authors: Marco Paland and Eyal Rozenberg; MIT licence in LICENSE.
The two source files are unmodified; inventory.json pins their bytes.

Native runtime evaluation, 2026-10-12: Lunar needs bounded string formatting,
including decimal floats, dynamic precision, general/exponential formatting,
and size_t lengths. This maintained implementation supports those formats,
uses no heap or standard-library functions, and permits ordinary target C99
compilation without adding a full libc, syscalls or OS reentrancy structures.
That describes the source: the pi32v2 optimizer emits a memcpy dependency.
The native build can compile with PRINTF_ALIAS_STANDARD_FUNCTION_NAMES_HARD=1
and function/data sections so existing snprintf calls resolve naturally;
unneeded printf/UART entry points must be discarded by the link.

Picolibc was also evaluated through its upstream build documentation/source.
It provides broader libc/math support but requires a new pi32v2 architecture
configuration; it remains a candidate for the remaining functions, not an
implemented runtime. This narrow formatting import does not satisfy math,
parsing, allocation or C++ runtime dependencies. Actual device linkage and
ABI/numerical verification remain required.

[verified] Sixteen concurrent Hera ASan/UBSan cases compare the bounded UI
formats against host libc, with capacities 0, 1, 2, 7, 32 and 128, return-length
checks and untouched buffer guards. All passed; the pytest wrapper also passed
16 cases. The actual pi32v2 r3 -mfprev1 -Oz compile passed with the hard alias.
Its undefined symbols are fourteen double arithmetic/conversion/comparison
helpers, memcpy and putchar_. The last belongs to ordinary printf output,
which the snprintf-only native integration must discard rather than stub.
This is compilation and host format evidence, not device formatting acceptance.

Root MIT licensing remains unchanged. Linking the GPL native HAL makes the
combined application GPL-3.0-only; this MIT component is compatible with it.

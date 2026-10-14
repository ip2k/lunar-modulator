# Wavetable aliases use the compilation target prefix

[verified] Explicit assembler aliases in generated `wave_tables.inc` bypass
the compiler's ordinary object-symbol prefix. The previous literal Itanium
name links on ELF but fails on Darwin, whose resource definitions have an
additional underscore. Generation now stringifies `__USER_LABEL_PREFIX__` at
compilation time, so the generating host does not determine the target ABI.
Packed table bytes and resource definitions are unchanged.

[verified] All sixteen `tests/test_native_wavetables.py` shards passed on this
Mac with AddressSanitizer and UndefinedBehaviorSanitizer. Apple clang defines
the prefix as `_`. The pinned JieLi clang 4.0.1 in a bounded, network-disabled
Hera container defines the prefix as empty for `-target pi32v2 -mcpu=r3
-mfprev1`. The latter checks preprocessing compatibility; it is not a new
firmware build or hardware acceptance.

[verified] Serena and Rarefaction currently select the primary checkout,
not this coordinator worktree. That shared selection was left unchanged to
avoid disturbing other sessions. This narrow generator fix used file
inspection and real compiler/linker tests; no worktree semantic-index coverage
is claimed.

# NOR runtime stack guard and linked writer depth

This offline review binds the stack guard to the exact linked pi32v2 writer bodies. The runtime guard samples SP after the XIP wrapper prologue and, for program operations, after the page has been copied into the wrapper's stack. Its 1,024-byte threshold is measured from that sampled SP to the configured lower bound. Do not subtract the already-consumed wrapper frame from this headroom a second time.

The pinned analysis artifact is /home/claude/mvave-fm1/nor-runtime-stack-guard-20261014/current-stack-guard/linked/:

- lunar-app-probe.elf: SHA-256 17bf4597b5f47d18473fdee7f97fc0ae97c0478808cb448aafe64a53c56e03a7
- full-disassembly.txt: SHA-256 2568be20c64b6629754ee96c331bd30d823798d82e9b7901ffbec54c2341dbce
- symbols.txt: SHA-256 9949be366206c33745c8c0df7b387a3cf6345377f670643b00238df8da77a025

The linked listing shows downward stack growth via [--sp] saves, with four-byte register slots, and exact inverse restores. Return state rets is part of those saves. fl_write saves rets,r10-r4 (32 bytes) and allocates 272 local bytes: 304 bytes total. fl_prog_ram saves rets,r15-r4 (52 bytes) and allocates 52 local bytes: 104 total. The audited program path therefore reaches 408 bytes below fl_write entry SP, of which 304 bytes are already consumed when the guard samples SP. From the guard sample, the RAM entry uses 104 bytes and leaves 920 bytes of the 1,024-byte guarded headroom.

For erase, fl_erase4k saves rets,r7-r4 (20 bytes) and allocates 12 bytes: 32 total. fl_erase4k_ram saves 52 bytes and allocates 52: 104 total. The path totals 136 bytes from wrapper entry; from the post-prologue guard sample the RAM entry uses 104 bytes and leaves 920 bytes. The verifier rejects unknown register-save sets, local stack allocations, unbalanced epilogues, nested calls or dynamic SP adjustments in the RAM writer entries. Saved-register writes are included in the calculation.

I corrected the receipt field to report the guard sampling point and remaining headroom after each RAM entry. It no longer reports 616 bytes by subtracting the complete 408-byte entry-relative path from a post-prologue 1,024-byte measurement.

Checks on Hera:
- Python py_compile passed for the verifier and fixture files.
- python3 -m unittest discover -s tests -p test_native_nor_writer_closure.py -v passed, 18 tests.
- The C register-mock fixture compiled with cc -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast and ran successfully.
- Direct audit_writer_callers() against the pinned target full-disassembly.txt and symbols.txt passed: wrapper and RAM frames match the bounds above; no calls or dynamic SP adjustments were found in fl_prog_ram or fl_erase4k_ram.

Limitations: this is a bound for the audited linked synchronous writer path, not a whole-program worst-case stack proof. It does not prove the runtime SP begins in SRAM or had sufficient space before the wrapper prologue; the linked audit explicitly keeps runtime_stack_address_in_sram_proven false. The target listing is pi32v2 evidence for this exact build, not a generic ABI guarantee. SAVE remains disabled and unbound; no device commands or flash operations were run.

## Follow-up: make receipt units and stack operations explicit

The machine-readable receipt now names 408/136 bytes as entry-relative decrease from wrapper entry. A separate post-guard field records the RAM-entry decrease as 104 bytes for each path; 920 bytes is the remaining guarded headroom. This keeps the 1,024-byte sample and wrapper-entry totals in distinct fields.

The frame verifier now requires exactly one known save, allocation, inverse allocation, and restore in each RAM entry, rejects any extra SP mutation/predecrement save/postincrement restore, and still refuses nested calls. Stack-relative local reads/writes remain allowed within the fixed declared frame. Mutation cases cover extra allocation, register save, and register restore. A duplicate epilogue can be rejected by either the duplicate/unbalanced epilogue check or the explicit unexpected-SP-mutation check; both fail closed.

Follow-up checks: Python byte-compilation passed; focused unittest suite passed 18/18; target listing audit passed with entry-relative {program: 408, erase: 136}, post-guard {program RAM entry: 104, erase RAM entry: 104}, and 920-byte remaining headroom in both cases; strict host C fixture compiled and ran; git diff --check passed.

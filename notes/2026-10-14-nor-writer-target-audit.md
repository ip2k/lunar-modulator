# NOR writer target-link audit (offline, analysis only)

Date: 2026-10-14
Source base: `1f020b4b497ce8f71add8cca07e0ba86352dc540`
Worker branch: `codex/2026-10-14-nor-writer-target-audit`

## Result

The retained pi32v2 target ELF contains substantial linked RAM implementations of the NOR erase, page-program, read, status, and JEDEC-check paths. The audit verifies actual disassembled command operands (WREN `0x06`, erase `0x20`, page-program `0x02`, status `0x05`, JEDEC `0x9F`), non-stub symbol extents, direct branch bounds, and that RAM calls resolve to linked RAM functions. There are no calls out of the erase/program RAM entry functions. The only RAM call found is `fl_jedec_ram -> fl_jedec_checked_ram`.

This is useful link evidence, not a safe writer closure. The exported `fl_erase4k`, `fl_write`, `irq_save`, and `fm1_wdt_feed` all link in XIP `.text`. Thus a production operation enters via XIP wrappers, and the watchdog feed is not RAM-resident. The builder linked `project_save_service`, but kept `storage_admitted=false`, `flash_io_bound=false`, `save_service_armed=false`, `runtime_verified=false`, `hardware_tested=false`, `installable=false`, `hardware_candidate=false`, and `release_accepted=false`. No package/app artifact was emitted and no flash/device operation was performed.

## Target artifacts and reproduction

Retained build directory:
`/home/claude/mvave-fm1/nor-writer-target-audit-20261014/build-04/build`

The linked ELF was `build/linked/lunar-app-probe.elf`, SHA-256
`7ac7928466e803fd3f0c4b3084d60c24921908f1e098642f2711fc264f0b35bf`.
Other retained evidence: map `a70db790d660926a1923c78b1e62cd2a5fb543f28a811ce115a75083738ba57b`; RAM disassembly `b0cbc75a9b0f3a0535d43804f67cf0c7f4139436320de90d53cf40b9dd927c58`; full disassembly `8172e4d901ebc1f560b9ccd52009ce25a9553bc53f4007602da9b7e13514e958`; sections `c4f6d85676c303431a164635119373e5d10a7f058960ec837b30d0e47ce56c2a`; relocation listing `151e4a521a2d27dce291316b9e527a4f5ff3a7a58d791e1a4d524ed0c63b611d`; symbol listing `1cb9d2960c5e6a5c82c69cabeb4ec15d494d82152a5ecdfd35f05d8cfe9fd7ea`. The source manifest used for the target build is pinned as `f24402da89fac8e226427dad3ddc972b9a07afe9dc1f59652129ef46618cffa4`.

The follow-up checker was run directly against these retained ELF-derived `ram-text.txt`, `symbols.txt`, `linked-relocations.txt`, and `sections.txt` files. Its positive and negative host fixtures pass in `python3 tests/test_native_nor_writer_closure.py` (14 tests).

RAM symbol placement/size/instruction counts:
- `fl_erase4k_ram`: `0x1c00000`, 1002 bytes, 320 instructions.
- `fl_prog_ram`: `0x1c00580`, 1084 bytes, 343 instructions.
- `fl_read_ram`: `0x1c009bc`, 478 bytes, 151 instructions.
- `fl_status_checked_ram`: `0x1c00b9a`, 454 bytes, 154 instructions.
- `fl_jedec_checked_ram`: `0x1c003ea`, 384 bytes, 126 instructions.
- `fl_jedec_ram`: `0x1c0056a`, 22 bytes, 10 instructions.

The linked XIP symbols include `fm1_wdt_feed` at `0x0204ebfc` (10 bytes), `fl_erase4k` at `0x0204e820` (32 bytes), `fl_write` at `0x0204e840` (68 bytes), and `irq_save` at `0x0204e808` (14 bytes). No WDT feed symbol is in `.ram_text`.

Build provenance: pinned toolchain directory `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1`; clang SHA-256 `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`; vendor objdump SHA-256 `cffc304e1a9be5dac22984a6ad48e81ef82b17166fd8864c251cf635c9663b73b`; container `lunar-jieli-check:bookworm`, image SHA-256 `0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`. The build ran offline in the bounded Docker batch slice with 4 CPUs, 8 GiB memory and equal swap, and 256 PIDs.

## Limits / next dependency

The target audit is intentionally conservative. Static relocation output is empty and no `.rodata` section exists, but static data closure remains unproven: caller-provided buffers and pointers are not shown to reside in RAM. Direct branches are bounded, but computed/indirect control flow and runtime caller dispatch are not proven. Link evidence does not establish real XIP-off behavior, watchdog timing, worst-case NOR busy duration, or power-loss behavior. In particular, the WDT helper and ordinary wrappers are in XIP, while persistent-WIP/status-failure recovery has not been shown safe. SAVE remains disarmed.

Next useful dependency: a reviewed RAM-resident entry/exit and watchdog strategy, plus complete source/buffer residency proof and target-runtime evidence, before any storage-admission change. Physical validation and device writes remain coordinator-owned and are outside this audit.

# NOR ready-poll RAM closure review — 2026-10-14

## Result

Independent review of transport-error revision `8abae944f819180f230c7d34760599eb822fb09c` found no new concrete control-flow defect in the erase/program readiness gate. Once a destructive opcode transaction is attempted, the code does not restore SFC/XIP until a successful status read observes WIP clear. Transfer errors are retained and returned after readiness; if status stays unreadable or WIP never clears, execution remains in the RAM-side loop rather than returning through `fl_exit()`.

This revision remains **not admitted for physical use**. Two existing blockers are concrete:

1. `irq_save()` executes `cli` but returns zero, while `irq_restore()` always executes `csync; sti` (`firmware/third_party/dinghy/hal/fm1_flash.h:264-275`). It does not preserve prior interrupt state. Callers disable global interrupts across the full read/erase/program operation; if readiness never resolves, interrupts remain disabled indefinitely.
2. The watchdog is armed at startup (`firmware/third_party/dinghy/src/platform.c:313`), but the RAM wait path does not feed it. Reset behavior while NOR may still be busy is unresolved. Do not infer recovery safety from the loop staying in RAM.

No hardware operation, writer enablement, or physical acceptance is part of this review.

## Target-code evidence and limits

The review compiled current `platform.c` (which includes the current `fm1_flash.h`) using the pinned pi32v2 compiler 4.0.1 with `-target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -Oz -ffunction-sections -fdata-sections`.

Inputs:
- `platform.c` SHA-256: `6cfb23b317af3d95da4d6eeeb8a34de59ee77a626d7d17484398feeb2535bfd7`
- `fm1_flash.h` SHA-256: `cfd6f073cf18ee4da510a701624a61aa313e7b9e235f0565298b6c0bbb508f65`
- Compiler: `/home/claude/mvave-fm1/sdk-v1213/toolchain/current/pi32v2/bin/clang`

The object has one `.ram_text` section (0xd70 bytes) and no `.rela.ram_text` relocation section. I linked it with `firmware/third_party/dinghy/app.ld` and a five-function synthetic shim for application/ISR entry symbols to inspect RAM placement and the resulting disassembly. The fixture map places `.ram_text` at `0x01c00000`, load address `0x02005dd4`; `fl_erase4k_ram` is `0x01c0035c` (0x3f0 bytes), and `fl_prog_ram` is `0x01c0074c` (0x446 bytes). The inlined entry closure has only local branches, immediate SFR accesses, and `flushinv`; no external relocation or literal-pool relocation leaves the RAM section. The `FL_FAR` bridge is called from XIP-side wrappers before entering the RAM routine.

Fixture artifacts were temporary under `/tmp` and are not checked in:
- object SHA-256: `719f4ddd4f9e9a0c09b229847d02cbf4644eac17ae98c9c981c6cbeea0dd80a4`
- fixture ELF SHA-256: `8c91568b26fdf0ed90edb4e31f564791767dd226fe5c1e014d44f8bea35611b3`
- fixture map SHA-256: `ee363c41c7829a43d80122d17cfa90dfaae7d6bdff09ecb6fc43b85823886156`

I also inspected the existing all-module target application probe at `/home/claude/mvave-fm1/d7000-target-link-20261014/link/lunar-app-probe.elf`. Its copied `platform.c` matches the current source hash, but its map contains only a 0x468-byte `.ram_text` block and no `fl_erase4k_ram`, `fl_prog_ram`, or `fl_wait_ready` symbols. Therefore that full application probe does **not** validate retention/placement of this candidate writer closure; the synthetic fixture is the only link-closure evidence here. It is static compiler/linker evidence only—not a full retained production ELF with the writer enabled, not execution, and not device validation.

The routine contract requires source/destination buffers to reside in RAM while XIP is disabled. In the minimal platform link, OTA staging buffer `ota_stage.b` is in `.bss` at `0x01c0a228` and OTA calls `ota_prog` with that buffer (`firmware/third_party/dinghy/src/ota.c:318`). This does not establish buffer placement for every future caller.

## Checks

- `pytest -q tests/test_dinghy_flash_transport.py`: **1 passed** (bounded mocked transport test).
- pi32v2 compile, link/map placement, and disassembly inspection: completed as described above.
- No hardware, target execution, watchdog recovery, actual application-retention proof, or physical NOR-busy behavior was tested.

## Next required evidence

Before any physical writer admission, preserve prior interrupt state (or prove and enforce the exact entry-state contract), establish a bounded watchdog/recovery strategy that is safe if NOR remains busy, and inspect the final release-candidate ELF with the writer enabled to prove RAM placement/closure and RAM buffer provenance. Then separately obtain explicit hardware authorization and conduct a reviewed, bounded device validation.
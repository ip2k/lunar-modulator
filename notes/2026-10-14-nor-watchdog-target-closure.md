# NOR watchdog prototype: final linked target audit

**Status: offline diagnostic link and analysis only.** No hardware, USB, MIDI, flash, power, or reboot command was issued. SAVE remains unbound and unadmitted. Source branch codex/2026-10-14-nor-watchdog-target-closure is based on coordinator seed a30274e48ba5dfd845122cfb1bb9d83c57d8de16 plus watchdog prototype b4721056590a8cc874e4ac6c0b4e1cd897b9cea7.

The fresh all13/all55 Shapes8 Event Horizon Showcase 120-second diagnostic link passed the existing builder gates. Link directory: /home/claude/mvave-fm1/nor-watchdog-target-closure-20261014/link-final; ELF SHA-256 ca347f1179922da49f687131446f92ec472d70c141169afbcc13df5afcf4c63e; artifact/app.bin SHA-256 141e79e96c53743723838e9ed1e3b743166a610d7949e9d33e91cfc93f330379b. It uses the prepared selection profile SHA bfe627dc60ca5552dfd2f749611105989f7fcfb3c8637840225b377c38ac6972. Receipt says runtime song-diagnostic, 120 seconds, Shapes voices 8, one selected project, startup index 0, all 55 production modules; storage_admitted, flash_io_bound, save_service_armed, runtime_verified, hardware_tested, installable, and hardware_candidate are false. This is not a runnable or installable image claim.

## Target closure findings

I ran tools/native/verify_nor_writer_closure.py against the fresh ELF and profile using pinned image lunar-jieli-check:bookworm (sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc). The analysis-only overlay is not a normal app receipt and never executes a NOR operation. Its output is /home/claude/mvave-fm1/nor-watchdog-target-closure-20261014/nor-closure-analysis-v2; ELF SHA-256 c0429a5f8849f1afa17043953fca4fc5582a4466a75934c2e4ff939bb895e2c6, map SHA-256 cbc2a087450f8531bc8b8b062036d82e1715ae26aa605b9e6538ecc06c65586b, and disassembly SHA-256 9f05effd9a2e68a3fadc1139409f2ae4ab4bb2d24bbefc746855d7cdaee9969e.

The linked .ram_text occupies [0x01c00000, 0x01c00d60) (0xd60 bytes). fl_erase4k_ram is 1,002 bytes/320 instructions; fl_prog_ram is 1,084 bytes/343 instructions; checked status is 454 bytes; checked JEDEC is 384 bytes. The audit found no direct outcalls from the two destructive writer entries, no static relocations, no .rodata, and complete bounds for direct branches. fl_write copies each page to its local stack buffer before disabling XIP; the linked user stack is SRAM [0x01c74100,0x01c7a000) (24,320 bytes).

The surrounding fl_erase4k, fl_write, IRQ helper, and WDT stop/restore/arm functions are in XIP .text. In the wrappers, the order is save/mask ICFG, checked watchdog stop/readback, RAM NOR call, checked WDT restore, then restore exact ICFG. The RAM status loop must positively observe WIP clear before returning to XIP. When status never becomes readable/ready, it does not return, restore XIP, re-arm WDT, or restore ICFG. This is an unbounded non-returning wait, not proof of physical recovery or a hardware fail-safe. Watchdog startup/feed remains XIP.

The audit deliberately reports static_data_closure_complete=false, control_flow_closure_complete=false, runtime_pointer_residency_proven=false, and watchdog_feed_in_ram=false; its own limits say indirect/computed control flow and caller-supplied pointers are unproven and it establishes no runtime XIP-off, watchdog, timing, or physical flash behavior. Thus this link supports a narrow placement observation about the writer symbols, not complete RAM closure or permission to bind SAVE.

## Focused host checks

I added two regression cases to tests/native/test_dinghy_flash_transport.c: an already-disabled reset-mode watchdog remains disabled after erase; and a destructive NOR transfer error remains the returned error if the single WDT re-arm attempt also fails, with one destructive command, positive-ready observation, one XIP/SFC restore, and no retry.

Both passed in the bounded networkless container lunar-jieli-check:bookworm, GCC 12.2.0, using strict warnings except unused static included HAL functions and 32-bit target-register casts. The same test binary also passed GCC AddressSanitizer and UndefinedBehaviorSanitizer with halt-on-error enabled. git diff --check passed. Full stdout is retained at `/home/claude/mvave-fm1/nor-watchdog-target-closure-20261014/host-tests-final/host-tests.log` (SHA-256 `579bccf2de84efbe197c219a1de30b277deb21e0fb59678ebca6c091c0323d83`).

Exact host commands run inside the bounded container:
- gcc -std=c11 -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast -I/source/firmware/third_party/dinghy/hal /source/tests/native/test_dinghy_flash_transport.c -o /tmp/test-flash && /tmp/test-flash
- gcc -std=c11 -O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast -I/source/firmware/third_party/dinghy/hal /source/tests/native/test_dinghy_flash_transport.c -o /tmp/test-flash-san && ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 UBSAN_OPTIONS=halt_on_error=1 /tmp/test-flash-san

Container used docker-batch.slice and image lunar-jieli-check:bookworm with network none, 1 CPU, 2 GiB memory and equal swap, 128 pids. Verification JSON has hardware_candidate=false, hardware_tested=false and installable=false; there is no hardware_admitted field in this receipt.

## Remaining safety boundary

The prototype does not resolve unknown watchdog state if the stop command may have reached P33 but readback times out. It does not report a secondary re-arm failure when a NOR error already has precedence. A persistent/unreadable NOR WIP keeps execution in the RAM poll with WDT stopped. The target audit does not prove that all indirect pointers, caller context, buffers, and control paths are RAM-safe. These require additional source/target evidence before any SAVE binding or admission change.

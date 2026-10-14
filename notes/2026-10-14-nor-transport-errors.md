# Dinghy SPI NOR transport error handling - 2026-10-14

## Scope and result

At base 620cc306a83addb0104fc2c3f328e53e070a0446, Dinghy SPI routines called fl_spi_wait() but discarded its timeout result. Transmit, status, JEDEC and read paths could consume untrusted register contents; erase/program could report success after failed transfers. The change keeps the pre-existing range gate and IRQ behavior unchanged while propagating transport failures (-5).

fl_tx now returns its wait result. fl_rx writes its output only after success. Address, status and WREN helpers return failure and close CS. The checked JEDEC/status APIs leave output untouched on failure; the legacy JEDEC wrapper returns a value that cannot pass existing exact equality checks for 0x856014. Existing callers are platform.c:329, recovery.c:59, and st_read() at platform.c:74-86; no old status-reader caller was found. st_read() already propagates fl_read_ram() failure.

For erase/program, the driver marks the destructive transaction attempted before sending its opcode. A timed-out SPI byte might still have reached NOR and CS release can commit it, so the code always polls status after CS rises. fl_wait_ready() only returns after a valid status transfer observes WIP clear. If status reads keep timing out or WIP never clears, it remains in .ram_text with SFC/XIP disabled and does not restore interrupts through the normal caller. The original transport error remains the return value after readiness is established. Existing time limits report a late-completion result (-4) only after a later valid ready observation; they are not permission to return to XIP while busy. Status transport failures are retried until a valid status result and reported as -5 after ready is proven.

fl_exit() restores SFC/SPI and restores IOMAP bit 5 to its saved value while preserving other current IOMAP bits. Unsupported continuous-read SFC modes still fail before reconfiguration. IRQ save/restore semantics, storage ranges, profiles, and writer enablement were not changed.

## Verification

- tests/native/test_dinghy_flash_transport.c includes the actual HAL header, mocks registers and SPI waits, and models NOR CS transaction boundaries, WREN/WEL, destructive-command commit on CS rise, WIP, and eventual WIP clear. Transfer failures are injected across JEDEC/status/read/erase/program phases. It asserts that failed destructive transfers retain their error result, status failures are not treated as data, and XIP restoration occurs only after valid WIP-clear observation.
- Two bounded test escape cases interrupt the host simulation after repeated status-read failures or persistent WIP and assert that SFC remains disabled, CS is high, and the XIP-restore hook was never called. These do not model electrical timing or invoke a physical watchdog/reset path.
- /home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_dinghy_flash_transport.py: 1 passed. The wrapper compiles with strict warnings and runs the harness.
- The pinned 2025-03-24 JieLi pi32v2 compiler compiled a temporary probe for checked JEDEC/status, read, erase and program paths using -target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -Oz; pi32v2/bin/nm -u reported no undefined symbols. Compile-only: no full application link/map or target execution.
- git diff --check passed. ASan/UBSan could not link because Hera lacks sanitizer runtime libraries.

## Limits and next gates

The RAM fail-stop deliberately sacrifices availability if readiness cannot be established. It may leave execution in RAM with interrupts disabled and XIP off; the watchdog could still reset the device, and this patch does not prove such a reset is safe while NOR may be busy or provide a recovery path from that state. The host model checks control flow under mock semantics, not actual flash timing, command acceptance, status reliability, power-cut behavior, watchdog margin, XIP/linker residency, or physical recovery.

No storage profile, app driver binding, writer enablement, device operation, or installation admission was performed. notes/2026-10-14-native-nor-adapter-contract.md remains controlling for IRQ, watchdog, linker residency, profile, readback and physical acceptance. Serena/Rarefaction remained selected to another active Mac checkout; direct source/caller inspection was used on this assigned Hera worktree.

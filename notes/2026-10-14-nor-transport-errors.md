# Dinghy SPI NOR transport error propagation — 2026-10-14

## Scope and result

At base `620cc306a83addb0104fc2c3f328e53e070a0446`, the Dinghy NOR routines called the bounded `fl_spi_wait()` but discarded its timeout result. A timeout therefore left transmit, status, JEDEC, and read paths consuming untrusted bytes; erase/program could report success after a failed transfer. This change keeps the existing range gate and IRQ behavior unchanged while propagating a distinct transport failure (`-5`) through the RAM transaction routines.

`fl_tx` now returns the wait result. `fl_rx` takes an output pointer and only assigns it after a successful wait. `fl_addr`, `fl_rdsr`, and `fl_wren` propagate transfer failures and always deassert CS. `fl_wait_ready` distinguishes a failed status transfer (`-5`) from WIP timeout (`-4`) and ready. The checked JEDEC/status operations write output only on complete success. Erase and page program check WREN and WEL transport before issuing their destructive command, stop at the first failed SPI transfer, close CS, return failure, and restore the prior peripheral state. Read returns failure for any command, address, dummy, or data-byte transfer timeout; partial destination data is not reported as success.

The two existing boot identity callers in `firmware/third_party/dinghy/src/platform.c:329` and `src/recovery.c:59` use `fl_jedec_ram() == 0x856014`. The compatibility wrapper returns `0xFFFFFFFF` on transport failure, which cannot pass those exact-equality checks. New code that needs the transport reason can use `fl_jedec_checked_ram(uint32_t *)`. The sole external read caller, `st_read()` in `src/platform.c:74-86`, already propagates `fl_read_ram()` errors. No caller of the old `fl_status_ram()` was found, so that ambiguous sentinel API was removed in favor of `fl_status_checked_ram(uint32_t *)`.

`fl_enter` now snapshots IOMAP bit 5, the only IOMAP bit it changes; `fl_exit` restores that bit to its original state while preserving other current IOMAP bits. Unsupported continuous-read SFC modes still fail before changing SFC/SPI/IOMAP state. IRQ save/restore code, range admission, region limits, and writer enabling were not changed.

## Verification

- `tests/native/test_dinghy_flash_transport.c` executes the actual header routines against mocked SFR registers and a scripted wait hook. It injects failures at each transfer position in JEDEC, status, read, erase, and program operations, checks unchanged checked-result outputs, verifies no status byte is trusted after timeout, and checks CS/SPI/SFC/IOMAP cleanup. It also exercises both initial values of the IOMAP owner bit.
- `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_dinghy_flash_transport.py`: **1 passed**. The pytest wrapper compiles the C harness with strict warnings and runs it.
- The same host C harness compiled with `cc -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast` and executed successfully. `-Wno-int-to-pointer-cast` is limited to the host test because the HAL intentionally represents the 32-bit device XIP address in a host pointer type.
- A temporary compile probe for the real pi32v2 target compiled the checked JEDEC/status, read, erase and program call paths to an object using the pinned 2025-03-24 toolchain and `-target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -Oz`. `pi32v2/bin/nm -u` reported no undefined symbols. This was compile-only evidence; no full application link/map audit or device run was performed.
- An ASan/UBSan attempt could not link because Hera lacks `libasan.so.8.0.0` and `libubsan.so.1.0.0`; no sanitizer result is claimed.

## Limits and next gate

A timed-out transfer after an erase/program command may have an indeterminate physical effect: the API now returns an error and does not claim completion, but this patch does not prove command non-acceptance, readback, rollback, NOR timing, watchdog margin, XIP safety, or power-cut recovery. It does not enable Dinghy's source-level writer, grant storage ownership, create a Lunar NOR profile, or authorize device operations. The audited contract in `notes/2026-10-14-native-nor-adapter-contract.md` remains controlling for IRQ, watchdog, linker residency, profile, readback and physical acceptance gates.

The host harness injects a deterministic failing wait hook at each transaction transfer. It does not emulate electrical SPI timing or flash state transitions. Target object compilation is not link/map or hardware proof. Serena and Rarefaction were not redirected from the concurrently used Mac project selection; this review used the assigned isolated Hera checkout and direct source/caller inspection.
EOF"

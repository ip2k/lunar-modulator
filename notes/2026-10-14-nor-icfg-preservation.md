# NOR ICFG save/restore preservation — 2026-10-14

## Change

The FM-1 flash wrapper previously issued `cli` and then unconditional `sti`. If its caller had already disabled global interrupts, returning from erase/program could enable them unexpectedly. The wrapper now saves the full ICFG value, clears only bit 8 while the operation runs, and writes the saved value on exit. Nested saves retain the already-disabled state, so an inner restore cannot enable interrupts prematurely. The plain XIP-window cache invalidation uses the same save/restore contract and restores the caller's prior state.

The implementation follows the pinned SDK's `local_irq_save/local_irq_restore` behavior rather than assuming a `cli` state bit or using unconditional enable. The SDK source is:
`/home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/driver/cpu/wl82/asm/irq.h`, lines 16–28; SHA-256 `2e1d58fc758635ab7cc8ad27ce3e5cb5bfbe754dac13438f3202b058fe233961`. The vendor helper reads ICFG, clears BIT(8), then restores the saved ICFG word. Existing Dinghy SPDX/copyright headers were left intact; this small assembly pattern is not a wholesale SDK code import.

## Checks

- `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/python -m pytest -q tests/test_dinghy_flash_transport.py` — **1 passed**. This compiles and executes the C register-mock harness.
- Direct strict host compile/run with `cc -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast` — **passed**.
- Pinned target compiler compile: `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -Oz` — **passed**.
- Target assembly for `irq_probe` is `r0 = icfg`, `r1 = r0 & 0xFFFFFEFF`, `icfg = r1`; `irq_restore_probe` emits `icfg = r0`. Probe source SHA-256: `3370da8fd7e1fbe68fa4ff7604f3d8c2fc467f0ebed6e5ea6659e99ffafa5759`; target object SHA-256: `34c501175cffbc45f8157b8d961ff92441f65f00e5f5b17df572c8ee47d845a3`.
- Mock coverage checks enabled and disabled prior state, nested save/restore, preservation of unrelated ICFG bits, wrapper return state, and that interrupts remain globally disabled while the mock confirms XIP is restored only after NOR-ready.
- `git diff --check` — passed.

An ASan/UBSan host link was attempted but could not run because the Hera host lacks `libasan.so.8.0.0` and `libubsan.so.1.0.0`. This is an environment limitation, not a test pass.

## Limits and next dependency

This verifies host state transitions and the pinned compiler's emitted ICFG instructions; it does not establish pi32v2 interrupt semantics beyond the SDK implementation, full application RAM closure, watchdog behavior, or physical NOR operation. There was no hardware/device action. The NOR writer remains unadmitted; watchdog strategy and complete RAM-residency proof remain open acceptance gates.

# NOR ready deadline accounting - 2026-10-14

## Change

`fl_wait_ready()` previously sampled `T4_CNT` before issuing each status transaction and only latched an over-budget result after a successful busy status. A status receive that crossed the deadline could therefore be omitted from the elapsed time, and a successful ready status sampled after the deadline could return success. The loop now samples the timer immediately after every completed status-read attempt, latches lateness even when transport failed, and only then handles the read result. A failed status transport remains higher priority (`-5`) than a late-ready result (`-4`), while the loop still does not return or restore XIP until a readable status shows WIP clear.

Unsigned subtraction preserves elapsed time across timer rollover between successive samples. The mock advances the 24 MHz timer on every SPI transfer and also starts one case near `UINT32_MAX` to exercise wrap.

## Verification

- `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest tests/test_dinghy_flash_transport.py -q`: **1 passed**. This compiles and runs the host register-mock C harness with `-Wall -Wextra -Werror`.
- New advancing-timer scenarios check: a ready observation after 15 ms against a 10 ms program budget returns `-4` only after ready is observed; a 2.5 ms completion returns `0`; an unreadable status followed by eventual late readiness returns `-5`; timer wrap with 6 ms elapsed returns `0`. Assertions also check readiness and XIP restoration state.
- Pinned JieLi compiler 4.0.1 compile probe: `/home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -ffreestanding -fno-builtin -Oz -I. -c /tmp/lunar_flash_target_probe.c -o /tmp/lunar_flash_target_probe_deadline.o`. The object has `.ram_text` (`0xd86` bytes) and `pi32v2/bin/nm -u` reports no undefined symbols. Probe source SHA-256: `fbb39a768945328992512c34b14bc437cff213858b355e848615a0d7cdad5562`; updated object SHA-256: `da868f3cbdefa60c08be2f3b400ac4b1d9ee604429febb7482628b910e5419b8`.
- `git diff --check`: passed.

## Limits

The compile probe is not a full application link/map or a proof of runtime RAM closure; `.ram_text` section presence and absence of unresolved object references do not establish the final call/data graph. The host harness checks mock control flow only, not NOR timing, electrical behavior, watchdog recovery, power interruption, or hardware operation. No interrupt policy, writer admission, device state, or production acceptance changed. The earlier transport-error note's target probe predates this adjustment; this compile was repeated against the current header.

# NOR ready-deadline review - 2026-10-14

Reviewed `7f370e20db135432b50db2598e4f72e3c39a1802` against its preceding
`8abae944` transport implementation. Review was read-only; no firmware source or
device state changed.

## Findings

The deadline-accounting delta in `firmware/third_party/dinghy/hal/fm1_flash.h`
`fl_wait_ready()` (lines 180-202) is internally consistent for the documented
24 MHz TIMER4 counter. It samples after each complete SR1 attempt, including
failed attempts; unsigned subtraction handles one 32-bit wrap provided the
interval is less than one full counter period (~179 s). `dt > max_us` latches
lateness, and only a successful status transaction with WIP clear may return.
A status transport error takes precedence (`-5`) over lateness (`-4`); callers
also preserve an earlier destructive-command transfer error. The erase/program
callers reach `fl_exit()` only after `fl_wait_ready()` returns, so persistent
WIP or status-read errors do not restore XIP through the ordinary return path.

The limit is deliberately a reporting budget, not a hard timeout: after the
budget expires, the code keeps polling until a valid ready observation. This
avoids returning into potentially busy XIP, but can wait indefinitely. The
existing host fail-stop tests model this with `longjmp`; they do not establish
what the real watchdog does during a prolonged RAM wait. Watchdog/reset-to-SPL
safety therefore remains an independent target/hardware blocker and must not be
inferred from these tests.

## Checks and test coverage

At the reviewed checkout, `/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest tests/test_dinghy_flash_transport.py -q` passed (1 test; this compiles/runs the C register mock with strict warnings). New cases exercise a late ready sample, a normal in-budget sample, timer wrap, and a late poll transport error followed by readiness. Existing cases assert no XIP restore while WIP persists or status is unreadable.

Small coverage opportunity: the persistent-WIP and persistent-status-error cases do not advance the mock timer past `max_us` before their simulated fail-stop. A focused case could cross the budget and then assert that XIP remains off while the mock is still unready. This would document the intentional "late but continue waiting" behavior; it would still not prove watchdog or physical behavior. The threshold uses strict `dt > max_us`, so an observation at exactly the budget reports on-time; this is coherent if the argument is a maximum elapsed duration, but should remain an explicit contract.

## Limits / handoff

No physical NOR timing, watchdog behavior, interrupt behavior, powered interruption,
full link/map, or device action was checked. No recommendation to enable the writer
follows from this review. Next useful evidence is a reviewed target watchdog/reset
analysis and, if desired, the small persistent-late host case above.

Reviewed source: `firmware/third_party/dinghy/hal/fm1_flash.h` and
`tests/native/test_dinghy_flash_transport.c`, commit `7f370e20`.

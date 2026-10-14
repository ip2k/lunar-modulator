# SAVE operation-lease host contract

This focused harness exercises the production `lunar_project_save_service_poll` and the real `lunar_project_save_app` / two-slot transaction headers with deterministic host-only callbacks. The compact state writer, quiesce callbacks, and NOR behavior are fakes. They prove ordering at the service boundary, not device capability, watchdog safety, XIP behavior, or flash recovery.

The cases establish four service outcomes:

- `storage_admitted != 1` is refused before quiesce or I/O and consumes that SAVE generation once.
- A quiesce callback returning zero defers: it does not consume the generation, enter storage, or resume a lease it did not acquire.
- A returned erase error is reported as failure; the service redraws and resumes once, then ignores another poll for the consumed generation.
- A fake erase callback representing unknown NOR readiness and unrestored XIP never returns to firmware control. The host test uses `longjmp` only to inspect the service state after that simulated non-return; it checks that resume, redraw, watchdog service, and a second I/O attempt did not occur.

The harness deliberately adds no production lease, watchdog hook, admission bit, or retry policy. The current production path still lacks a verified transport capability binding. `project_save_service.h` documents an I/O contract that must service the watchdog and permit unrelated interrupts, while the inspected NOR wrapper masks interrupts across its XIP-off transaction. The actual WDT behavior if status cannot establish ready remains unresolved. This work does not claim that the model closes that gap.

Run on Hera from the repository root:

```sh
/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_native_save_operation_lease_contract.py
```

Result: **1 passed**. The pytest test compiles `tests/native/save_operation_lease_contract.c` with host `cc -std=c99 -Wall -Wextra -Werror`, then executes it; output is `actual SAVE service callback composition: PASS`.

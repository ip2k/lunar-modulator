# SAVE operation-lease host contract

This focused harness exercises the production `lunar_project_save_service_poll` and real `lunar_project_save_app` / two-slot transaction flow with deterministic host-only callbacks. The compact state writer, quiesce callbacks, and NOR behavior are fakes. They prove ordering at the service boundary, not device capability, watchdog safety, XIP behavior, or flash recovery.

Cases cover these service outcomes:

- `storage_admitted != 1` is refused before quiesce or I/O and consumes that SAVE generation once.
- A quiesce callback returning zero defers: no storage call, generation consumption, or release of a lease it did not acquire.
- Returned erase and program errors are reported as failures; the service redraws and resumes once, then ignores another poll for each consumed generation.
- A fake transaction reaches successful commit through the real service and two-slot store path.
- A fake erase callback representing unknown NOR readiness and unrestored XIP never returns to firmware control. `longjmp` lets the host test inspect that boundary; it checks only that the service did not resume, redraw, or make another I/O attempt. The host test does not exercise watchdog behavior.

The `fm1_app_t` and service objects are static in the longjmp test so their state remains defined after the simulated nonlocal exit. The `longjmp` is a host inspection mechanism only; it does not claim a target fail-stop or recovery mechanism.

The harness adds no production lease, watchdog hook, admission bit, or retry policy. The production path still lacks a verified transport capability binding. `project_save_service.h` documents an I/O contract that must service the watchdog and permit unrelated interrupts, while the inspected NOR wrapper masks interrupts across its XIP-off transaction. What the watchdog does when status cannot establish ready remains unresolved. This host test does not address it.

Run on Hera from the repository root:

```sh
/home/claude/.cache/lunar-venvs/wave-receipt-validation-20261014/bin/pytest -q tests/test_native_save_operation_lease_contract.py
```

Result: **1 passed**. Pytest compiles `tests/native/save_operation_lease_contract.c` with host `cc -std=c99 -Wall -Wextra -Werror`, then executes it; output is `actual SAVE service callback composition: PASS`.

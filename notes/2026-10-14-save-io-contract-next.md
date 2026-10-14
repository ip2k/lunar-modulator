# SAVE I/O contract: bounded path and admission blockers

Status: offline source review only. No HAL, service, watchdog or storage binding changed; no device command or NOR operation ran. Source base `b0db316372ca65e92b20a097480e2a8f81c1d995`.

## Finding

The SAVE service and the existing NOR transport currently require incompatible execution contracts. `firmware/native/project_save_service.h` says I/O must service the watchdog and safely permit unrelated interrupts. Its poll runs the entire save synchronously on core 0, after `pause`, then redraws and resumes (`lunar_project_save_service_poll`). `firmware/native/save_quiesce.h` only pauses audio and restores global IRQs before it returns; USB packets may still drain and it does not establish storage/P33 exclusivity.

By contrast, `firmware/third_party/dinghy/hal/fm1_flash.h` enters the RAM writer through wrappers that globally mask IRQs, disable XIP/SFC, and restore the saved ICFG after each erase or page program. Following a destructive CS assertion, `fl_erase4k_ram` and `fl_prog_ram` conservatively poll until a *completed* SR1 read observes WIP clear. The 500 ms erase and 10 ms program values are lateness-report thresholds: crossing them records an error but is not permission to return into XIP. Status transfer failures and persistent WIP therefore leave execution in RAM with XIP disabled. This is the correct fail-closed direction for uncertain flash state, but the 8-second reset-mode WDT remains armed and no evidence proves that its reset while NOR is busy is safe.

`fm1_sys.h` starts reset-mode WDT at `0x0D` and exposes a P33 feed helper. Normal platform/recovery loops feed it; the NOR wait does not. The current whole-save poll does not yield to those loops. There is no demonstrated complete RAM-resident P33 feed path, nor proof of pi32v2 prior-IRQ-state restoration. The final-link closure note `notes/2026-10-14-nor-real-writer-closure.md` proves only static call closure for the selected link, not runtime XIP behavior, P33 concurrency, stack/data residency for arbitrary callers, or watchdog safety.

## Safest progress path

1. Keep `storage_admitted` false and the runtime writer unbound. Do not add a feed, stop, or reset workaround to the RAM wait loop.
2. Specify a storage-operation lease at the service/I/O boundary. It must prove the save owns all NOR/SFC/P33 users and that callbacks cannot run unrelated XIP-dependent ISR work while XIP is unavailable. Current audio-only quiescence is not that lease. The writer should return only after verified WIP-clear; interrupt restoration must use a pi32v2 protocol supported by authoritative ISA evidence, not a guessed PSR/ICFG rewrite.
3. Make watchdog progress occur only at a verified-ready boundary while normal XIP execution is available. A viable candidate is to split the synchronous save at existing storage operations (sector erase and page program), and allow the active transaction to feed between completed operations only after a fresh ready observation and successful XIP restoration. Do not feed from the unbounded busy/status loop. This is a design candidate, not yet established safe: prove the feed's P33 serialization and interrupt requirements, and prevent unrelated callers from turning it into an unconditional keepalive.
4. Before adopting that candidate, obtain the exact installed NOR part's authoritative maximum erase/program/WIP times and reset behavior, plus the MCU WDT timeout tolerance. The software currently uses `0x0D` as 8 seconds, but there is no evidence that a watchdog reset while a command remains active leaves the boot path safe. A status-read failure cannot be converted to “ready” based only on elapsed time. If a vendor guarantee cannot bound command completion before reset, a separately reviewed recovery path is required; until then persistent WIP/status loss remains an admission blocker.
5. Preserve the existing two-slot transaction semantics: erase only the inactive slot; keep the current valid slot intact; validate/hash body; write and read back the header; write commit marker last; read back the complete header. `tests/test_native_project_store.py` exercises torn mutations in a host model, which supports logical rollback behavior only. It does not prove physical NOR power-cut behavior, flash ownership, or reboot recovery.

## Evidence and focused checks

- `firmware/third_party/dinghy/hal/fm1_flash.h`: `fl_wait_ready` (line 190), destructive erase/program (249, 278), and IRQ/XIP wrappers (322–369).
- `firmware/third_party/dinghy/hal/fm1_irq.h`: `fm1_irq_off/on` use `cli` and `csync; sti` (38–39); no save/restore API is present.
- `firmware/third_party/dinghy/hal/fm1_sys.h`: WDT arm/feed/stop helpers (85–93); code alone does not establish WDT behavior during busy NOR.
- `firmware/native/project_save_service.h` (lines 24–49) and `firmware/native/save_quiesce.h` (9–39) expose the callback/quiescence mismatch.
- `firmware/native/project_store.h` (begin/write/commit) provides two-slot logical commit ordering.
- Existing `tests/native/test_dinghy_flash_transport.c` is already stateful: conservative CS release can commit a destructive command; it checks transfer-error propagation, deadline/error precedence, timer wrap, WIP/unreadable-status non-return before XIP restoration, and IRQ mock behavior. Adding another host test limited to this unchanged behavior would duplicate coverage, so no new test was added.

On Hera, `pytest -q tests/test_dinghy_flash_transport.py` passed (1 test). A broader attempt at `tests/test_dinghy_flash_transport.py tests/test_native_project_store.py tests/test_native_project_save_app.py` failed in test setup because the installed `cc` cannot link `/usr/lib64/libasan.so.8.0.0`; this is a host sanitizer-runtime dependency failure, not a test assertion or firmware failure. No target build or hardware validation was performed.

## Required next dependency

The coordinator should obtain authoritative part-specific NOR timing/reset guarantees and pi32v2 interrupt-state semantics, then review whether a transaction-gated ready-boundary watchdog lease can satisfy the existing SAVE service contract. If not, identify a separately validated recovery mechanism before changing admission. Any implementation still needs target-link RAM closure for the exact feed/status path and owner-controlled physical timing/fault/recovery tests; host mocks cannot provide those proofs.

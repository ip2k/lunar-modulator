# Native NOR SAVE watchdog strategy review

Date: 2026-10-14. Review-only, no production source changes or device operations.
Source checkout: `codex/2026-10-14-native-nor-wdt-safety`, starting at `96693fbded69a95bcd56f067aa42cb2841be870d`.

## Decision

There is no evidenced safe bounded watchdog strategy to implement for destructive NOR SAVE yet. Keep storage admission, flash binding, and SAVE arming false. A pre-operation ready check or a finite “lease” does not make the currently possible post-command state safe: a command may have been accepted at chip-select release, and after an erase/program attempt XIP must remain unavailable until a completed status transaction positively observes WIP clear. If WIP stays set or status cannot be read, the current fail-closed RAM wait never returns. Allowing the 8-second watchdog to reset in that state has no demonstrated NOR/SPL recovery guarantee; feeding or disabling it can leave a stuck device indefinitely. No implementation choice resolves both cases from current evidence.

## Verified code behavior

- `firmware/third_party/dinghy/hal/fm1_sys.h:32-44,56-77,85-93`: the P33 transfer helper increments a diagnostic timeout counter but still returns the sampled data; the void WDT feed calls `fm1_p33_or(0x80, 0x40)`, with no status proving that the feed completed. These helpers are ordinary C and are not marked as a RAM closure.
- `firmware/third_party/dinghy/src/platform.c:254-284,305-343`: startup arms reset-mode WDT with `0x0D` before entering the main loop; the pinned SDK header names this setting `WDT_8S`. Normal `platform_poll()` feeds at line 259, before the application loop returns to SAVE polling. This is ordinary idle-loop service, not coverage for synchronous NOR IO.
- `firmware/third_party/dinghy/hal/fm1_flash.h:190-212,249-305`: `fl_wait_ready()` polls from RAM and refuses to return until one completed status transaction reports WIP clear. Persistent WIP or status-read errors therefore leave the CPU in the RAM loop. Erase/program set `destructive_attempted` before sending opcode/address/data because CS release may commit the command, then wait for verified readiness before restoring SFC/XIP via `fl_exit()`.
- `firmware/native/project_save_service.h:22-27,39-53`: the service performs SAVE synchronously from the main-loop owner and states its I/O callback must service the watchdog and safely permit unrelated interrupts. The destructive writer instead keeps interrupts disabled while XIP is unavailable. No admitted adapter reconciles those contracts.

## Exact retained target evidence

The retained continuous500 target is `/home/claude/mvave-fm1/continuous500-link-20261014/out3/build` from source base `b7998a28ea1d6805c52fbbf69cc8ab45a9764c20`. Its relevant HAL and service source files match this task's `96693fbd` checkout (`git diff --quiet` on `fm1_flash.h`, `fm1_sys.h`, `platform.c`, `project_save_service.h`, and `app_probe.c`).

- ELF SHA-256: `4b8ae5a1f68550bcbedc2442d98f03f5af85daa88fcfbb69af37985b3d9f0120`.
- App SHA-256: `5c923197629121ce90a33919b516ced23ef8edbaa1943ea1e9568b596b6557ee`.
- `verification.json` SHA-256: `d1ec99dd5c45862a921b6579949ee6b71cc16eef2391eabaff5f2e57a578083f`.
- The receipt identifies `runtime_mode=continuous`, SAVE service linked, and `storage_admitted=false`, `flash_io_bound=false`, `save_service_armed=false`, `runtime_verified=false`, `hardware_tested=false`, `installable=false`.
- ELF disassembly at `fm1_wdt_feed` (`0x0204EB54`) calls XIP `fm1_p33_or` (`0x0204EB48`), so the existing feed path cannot be called while XIP is unavailable. In this retained image, `fl_erase4k_ram` at `0x01C00000` and `fl_prog_ram` at `0x01C0019A` are fail-closed `-1` stubs; this ELF does not exercise the production writer and cannot validate SAVE timing, reset behavior, or readiness handling.

## Why the plausible policies are insufficient

1. **Feed only before SAVE:** lowers the chance of expiry during a normal operation, but the observed maximum timing is not a proof that every erase/program/status transaction completes before the 8-second reset deadline. It does nothing for stuck WIP.
2. **Feed while WIP is set:** existing `fm1_wdt_feed()` is XIP code and depends on P33 helpers with no propagated timeout. Moving only the wrapper into RAM would still leave its call/data closure unverified. Even a verified RAM feed could suppress reset forever if the NOR never becomes ready.
3. **Bound the wait and return an error:** unsafe because returning restores XIP while NOR readiness is unknown. The current deliberate non-return avoids this, but then the watchdog may reset during WIP.
4. **Stop/reconfigure the watchdog or force reset:** no source or authoritative device-specific evidence establishes safe behavior while the exact installed NOR is busy. Do not add this based on general SDK examples.

## Evidence needed before implementation

The smallest useful next evidence is an authoritative, exact-part guarantee for reset/power loss during each relevant NOR WIP operation, plus confirmation of the installed part suffix and the SPL's behavior after such a reset. The current identification is only JEDEC `0x856014`; a family-level timing table is not enough to infer reset-during-WIP recovery. Alternatively, a separately authorized staged physical experiment could establish behavior, but it would require the owner's existing backup/recovery gates and must not be initiated by this review.

No non-writing test can reproduce NOR WIP during a CPU watchdog reset, so there is no honest no-write bench experiment that closes this blocker. A safe software-only follow-up can check ordinary feed/P33 transport under the normal runtime, but that proves neither RAM-resident feed closure nor reset safety while the flash is busy. If future evidence permits feeding during the wait, the target build must include and inspect the complete RAM-resident P33 transaction/data closure and propagate transport failure; a host mock alone is insufficient.

## Limits

No firmware or production code was changed, no tests were run, and no USB/MIDI/flash/power/reset command was issued. The retained continuous500 link is a non-admitted diagnostic image with writer stubs, not a SAVE-capable target. This review does not establish physical NOR timing, watchdog-reset semantics, or recovery acceptance.

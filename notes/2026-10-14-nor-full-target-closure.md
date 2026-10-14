# Full target NOR RAM-closure audit — 2026-10-14

## Result

The available all-module pi32v2 application ELF does **not** prove the runtime NOR erase/program closure. It is the deliberately non-writing application probe, and its generated `platform.c` forces `FL_RANGE_OK(off, n)` to constant false. The linker retains the `fl_erase4k_ram` and `fl_prog_ram` symbols, but each is a four-byte `r0 = -1; rts` stub. The inline writer/readiness/interrupt-save body is optimized away; `fl_wait_ready` and `fl_irq_save` do not appear in the retained image. Thus there is no actual erase/program path in this ELF to trace while XIP is off.

The final `.ram_text` in this probe is 0x468 (1128) bytes at `0x01c00000`. It retains real `fl_jedec_ram`, `fl_read_ram`, and `fl_status_ram` code. The inspected section disassembly contains no `call` instructions and these retained helper bodies use immediate SFR addresses / stack state; that is evidence only for the retained diagnostic read/identity/status helpers. It is not proof for the omitted writer, readiness loop, caller wrappers, interrupt preservation, watchdog behavior, or any release candidate.

## Exact evidence

Source checkout: exact base `454046b40e9e2869d061585c0aa71e0b86e915f3`, isolated branch `codex/2026-10-14-nor-full-target-closure`.

Retained target artifacts from `/home/claude/mvave-fm1/d7000-target-link-20261014/link/`:

- `lunar-app-probe.elf`, SHA-256 `db9d800022a4e73e672b049ee1aa350a01858a4baad58ef50eebe732e6d03134`.
- `lunar-app-probe.map`, SHA-256 `dd88e6cd0cc67b5d2a6dee8165207d5575d5c1cfb96cd8720506a6c9da68dde3`.
- `platform.c` generated copy, SHA-256 `d8c79fcce3d4ba50e7326b43f400970858fee4211edef468349ea424d4985fb7`; checked-in source SHA-256 `6cfb23b317af3d95da4d6eeeb8a34de59ee77a626d7d17484398feeb2535bfd7`.
- Checked-in `tools/native/build_application_probe.py`, SHA-256 `e539a75f4f6f67a2af39d03c701fc32231de15cd375c7adc7236449b907f6f94`.
- Checked-in `firmware/third_party/dinghy/hal/fm1_flash.h`, SHA-256 `c592536796274b0ca49cfad2fc1e8e3e0350cc6f115f27120fe582c5743cbe7d`.

`tools/native/build_application_probe.py` constructs the generated `platform.c` by replacing the checked-in allowed OTA/settings range macro with `#define FL_RANGE_OK(off, n) (0) /* Timed probe: no NOR writes. */` (around lines 332–334). `verification.json` confirms `flash_write_range: "empty"`, project SAVE code linked, `flash_io_bound: false`, `save_service_armed: false`, `runtime_verified: false`, `hardware_tested: false`, and `installable: false`. The ELF symbol table gives `fl_erase4k_ram` at `0x01c00000` size 4 and `fl_prog_ram` at `0x01c0014e` size 4; both disassemble to `r0 = -1; rts`. The final table has no `fl_wait_ready` symbol. The range guard constant-folding explains these results; this is an intentional probe safeguard, not evidence of a production linker-GC defect.

Checked-in `firmware/third_party/dinghy/src/platform.c` contains OTA and settings call paths into `fl_erase4k`/`fl_write`, but the probe source transform makes those writers refuse and cannot serve as a production writer link. No source was modified for this audit. No device, transport, writer-enable, or SAVE-arming operation was performed.

## Closure assessment and limits

- Read/identity/status diagnostic helper placement: observed in the exact retained probe ELF; final `.ram_text` disassembly has no call instruction. This is static code-generation evidence only.
- Actual erase/program closure: **not present and not auditable in this artifact**. `fl_wait_ready`, `fl_erase4k_ram` body, `fl_prog_ram` body, `fl_irq_save` body, and any post-disable reachable data/literal closure cannot be inferred from the synthetic earlier object fixture or these stubs.
- Source-level implementation now saves/restores ICFG using the pinned SDK pattern, but that sequence is compiled out of this image because the write path is unreachable after the false macro.
- Watchdog service/recovery while XIP is off remains unresolved and is an independent admission blocker. Do not weaken the no-write probe or enable SAVE to make this artifact appear production-like.
- Rarefaction and Serena were not queried against this Hera worktree: their live project roots were selected by another session. Direct exact-source, generated-copy, map, symbol, and disassembly inspection was used instead; this audit does not claim semantic-index coverage.

## Required next evidence

A separately named offline-only target link is needed from exact checked-in sources with a clearly labeled test-only writer policy, preserving the production range guards and all release checks in normal builds. Its link must retain the real callers and prove post-LTO placement/reachability of `fl_erase4k_ram`, `fl_prog_ram`, inlined `fl_wait_ready`, ICFG save/restore, and every data/literal access during the XIP-off interval; inspect map, symbols, relocations and disassembly. Record linker-GC roots and verify the caller buffers are RAM-resident. Keep the ELF non-installable and do not run it. Watchdog policy and hardware acceptance must be resolved separately; a successful static link is not execution or physical proof.

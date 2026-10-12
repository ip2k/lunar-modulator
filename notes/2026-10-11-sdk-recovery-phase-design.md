# SDK diagnostic recovery phase record: design only

2026-10-11, personal/non-commercial. No firmware source edit, build, device operation or source-pin change. Root owns current stock-return reset/identity, future implementation approval and hardware. This design follows the source/native diagnosis in `notes/2026-10-11-diagnostic-recovery-cause.md`, whose exact source and installed ELF pins remain unchanged.

Insight before implementation: stage6 is recorded before lock acquisition and remains compatible with a nonreturning final reset transfer. Evidence must be stored before that transfer; a return value cannot distinguish a reset that never returns. The trace should expose execution order while retaining the existing hardware sequence and its healthy-runtime premises.

[verified against current source] `app_main.c` calls `p33_lock`, then the bounded recovery request and `p33_unlock`. The request writes/verifies the 16-byte stock marker, selects P33 and sends exactly 0x20, 0xa0, 0x10. `send` writes DAT, reads CON, writes CON|START, synchronizes and polls idle. A hook after idle or after the request is too late for a nonreturning reset. No source identifies a demonstrated clock defect; no clock/rail/watchdog/reset-domain change is proposed.

Recommended minimal implementation [proposal]: add a diagnostic-only compile switch `LUNAR_SDK_RECOVERY_TRACE` and a small owned trace interface. The ordinary recovery IO struct/ABI stays unchanged. The worker records before-lock and acquired phases. The request has a conditional trace call immediately after all marker bytes match and before select. Only the final fixed `send(...,0x10)` has a conditional final-START-intent call, after reading CON and immediately before the existing CON|START write. The hook stores owned RAM and executes the existing pi32v2 CSYNC form with a compiler memory clobber. It calls no SDK service, timer, allocator, scheduler or P33 IO while locked. Current code cannot concurrently select another transfer under its held SDK lock; no new lock primitive or force-unlock is introduced. The original DAT/CON reads/writes, 4096 polls, select cleanup, marker bytes, reset mask, integrity scheduling and clocks remain ordered exactly as before, apart from bounded trace stores/barriers.

The hook should have a required strong definition when enabled, so an omitted trace object is a link failure. A macro-disabled build should compile the existing recovery path without hook calls or a changed IO layout. A weak global hook or a new generic IO callback is less attractive: it changes ordinary builds or a reusable ABI and adds authority unnecessary for this single diagnostic. Enabling the switch only in the SDK diagnostic build and recording it in its manifest keeps RAM-recovery/core-reset builds outside this experiment.

[proposal] Allocate one aligned 64-byte owned ELF symbol, e.g. `lunar_sdk_recovery_trace_record`, in normal diagnostic RAM storage. Do not select an address manually or place it in the ROM mailbox. Startup initializes it for the new image; retention across return to ROM remains a separately tested premise. A candidate layout is:

| Offset | Bytes | Field |
| --- | --- | --- |
| 0 | 4 | magic |
| 4 | 2 + 2 | version and exact length 64 |
| 8 | 16 | per-image nonce, pinned to this build/campaign |
| 24 | 4 | phase |
| 28 | 4 | bitwise phase complement |
| 32 | 4 | mailbox-verified flag |
| 36 | 4 | signed panel result |
| 40 | 4 | elapsed milliseconds |
| 44 | 4 | heartbeat snapshot |
| 48 | 4 | cached startup reset reason, or explicit unavailable sentinel |
| 52 | 4 | cached SDK sys Hz |
| 56 | 4 | cached SDK lsb Hz |
| 60 | 4 | publication sequence, odd while updating/even when committed |

Payload fields should be captured before lock once, then only bounded phase/complement/mailbox flag/sequence stores occur inside the lock. The writer marks the sequence odd, writes the coherent phase fields, CSYNCs, commits an even sequence and CSYNCs before proceeding. Exact generated native order must be audited; volatile alone is insufficient. The nonce is freshly generated 128-bit build input and is embedded in the ELF/manifest. It distinguishes this image from older RAM; it does not prove a unique boot of a repeatedly installed image. No cryptographic authenticity claim is made for RAM contents.

Phase values should distinguish initialized, before-lock, acquired, mailbox-verified and final-START-intent. Optional returning-failure/returning-request phases may be useful only if clearly labeled; they do not establish reset or USB enumeration. The mailbox-verified flag is set only after the existing complete byte comparison, and phase/flag consistency is checked by the decoder. This trace must not mark the final START as completed: it records intent just before the unchanged write. A final-START record plus new ROM enumeration is stronger execution evidence under the retention premise, not proof of reset cause, electrical transmission or ROM mailbox consumption.

Cached startup reason is the existing SDK value for entry into this application, not the later ROM reset reason. Its source declaration/type/address must be verified against the exact linked SDK before use. If the SDK does not expose a safe read of that already cached value, use a sentinel rather than adding P33 reads. Sys/lsb are cached reported clocks; this record does not measure physical frequency or capture truly inherited pre-initialization PLL state. No raw SFR reads are needed for this minimal trial.

Scoped prospective files [proposal]: a new small `firmware/sdk-diagnostic/recovery_trace.h/.c`; conditional call sites in `firmware/sdk-diagnostic/app_main.c` and `firmware/recovery/request.c`; explicit switch/nonce wiring in `tools/jieli/build-sdk-diagnostic.py` and its current compile/link helpers; a narrow trace-allocation/native-order audit extending the SDK diagnostic audit; a separate decoder/test module for the exact record. Existing physical adapters/read windows remain frozen. The proposed symbol name, section and build helpers must be reconciled with the actual link before editing. No vendor code needs modification.

Required gates before a new trial:

1. Host tests prove macro-disabled recovery requests retain the existing IO sequence and exactly one attempt; enabled tests prove phase order, mailbox mismatch has no verified/final phase, and timeout/selection failures cannot fabricate later phases. Simulating a nonreturning final START must retain final-intent without requiring post-return code. These tests establish source behavior only.
2. The exact private SDK build has a fresh nonce and passing current link/key/package/registration guards. Vendor pi32v2 objdump, not Ghidra or clangd, establishes trace-store/barrier order, strong hook references, unchanged P33/lock/clock calls and no SDK callback or additional SFR write from the trace.
3. ELF/map/allocation audit proves exactly one 64-byte aligned symbol, no overlap with mailbox `0x01c7fd80..0x01c7fdd7` (including SDK-cleared tail), stack/boot handover/reserved memory, SDK variables or selected loader/ROM upload windows. Derive VMA from this exact ELF. `.bss` allocation alone does not prove ROM preserves it.
4. A distinct read-only policy seals only the new ELF-derived 64-byte window and current stage symbol, exact image/nonce/schema and two bounded FD07 reads. It cannot widen an old read adapter or authorize arbitrary RAM addresses. Decoder negatives cover stale nonce, length/version/magic, unknown phase, mismatched complement, odd sequence, phase/flag disagreement, truncation and inconsistent repeated reads. Two identical coherent reads help reject publication races; they do not prove RAM retention in general.
5. Independent source/native/allocation/packet review precedes root's one-shot install/reset/read trial. Capture fresh ROM enumeration and the exact owned record, then complete separately reviewed stock restore/reset/identity. Physical display acceptance and warm recovery from SPL-rejected partial/corrupt applications without USB_KEY remain separate open gates. No physical fault injection is part of this design.

Insight after design: a compile-time owned hook avoids broadening the recovery API while making the nonreturning boundary observable. Its strongest justified conclusion is that the new image reached a particular phase and retained coherent trial-bound bytes; reset causality and reliable recovery still require actual observations.

Checks/limits: current worker/request/header/audit source inspected; exact existing native order and source/ELF hashes are recorded in the cause note. No new native build or test was run for this proposal. Shared semantic servers are still selected to the primary checkout; no isolated worktree language coverage is claimed and neither server was retargeted. Parent checkpoint at design start `d4ddb022ec92e7ac0dd8ee2f596034239759b9c8`, pushed/remote verified by root. Next dependency is accepted current stock-return reset/identity, then root approval of scoped implementation/native gates. Root alone checkpoints and pushes this design note.

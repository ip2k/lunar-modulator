# Stage-last exact-stock rollback cut-point review

Date: 2026-10-14
Scope: offline design only. No hardware or flash commands; no implementation or admission.

## Finding

Restoring the stock app and its app-area header before removing the five-sector stage can eliminate the stage's self-erasure as a loader-recovery problem: the byte-verified FM-1_092 SPL ordinary path selects an app when its top record and application-area header pass checks, then calls its XIP entry; successful selection bypasses the trailing flash-record search. Thus, after the exact stock app body and header have been readback-verified, the stage record need not survive for SPL to select that app.

This does not yet make the sequence an accepted power-loss-safe exact-stock rollback. The staged loader occupies USR sectors F2000-F7000. The historical matching FM-1_092 archive has those sectors all 0xFF, but there is no version-matched stock VM/USR decoder or startup trace proving the stock app ignores them, tolerates loader bytes in them, or tolerates an interrupted sector erase while they are restored. Since a cut during the final stage erase can leave arbitrary partially erased bytes in those USR sectors, ordinary SPL app selection alone does not prove the stock app will initialize successfully. Do not accept the sequence until that runtime dependency is resolved.

## Candidate order and reset behavior

Use the existing FM-1_092 geometry and the prior proposal's stage at F2000-F7000, record at F6F00. Keep SPL, OTA, cfg, BTIF, the top-level flash records and all unspecified ranges byte-identical.

1. Keep the expanded app selected and make no target changes until the five-sector loader and persistent record have passed full hash/CRC/readback checks. If power is lost before a valid record exists, no new recovery property is established.
2. Invalidate the expanded application's application-area header before changing any VM/USR or application payload. A cut before the invalidation takes effect leaves the existing app and its state intact; a cut after it must take the SPL failure path and find the still-intact stage. The exact one-way header mutation and SPL rejection must be proven against the candidate bytes before coding.
3. With the header invalid, restore the complete stock VM and USR content except F2000-F7000; preserve BTIF unchanged. Restore and readback-verify every stock application-body sector while keeping the application header invalid. A reset during this phase is expected to reach the still-valid loader record, which can resume. This relies on the prior verified conditional SPL scan and on the record staying outside every target erase.
4. Program the original stock application header last and read it back. If it is still invalid on reset, the loader remains the recovery route. Once it is valid, the SPL chooses the stock XIP app and skips flash-record discovery; the app body and every non-stage stock storage extent must already match the backup.
5. The loader is still executing from RAM. Restore/erase the five stage sectors to their exact archived stock bytes only after the stock header is valid; readback each sector and reset when complete. Erase the sector containing the record last. A power cut here no longer needs the stage to be a valid loader if ordinary stock app selection succeeds. However, the stage sectors are inside USR: cuts during any sector erase can leave partially erased data, and neither SPL selection nor the existing loader source proves stock app startup is safe with those bytes.

No assumption is made that a flash sector erase is atomic under power loss. A model that assumes atomic erase, ignores stock app reads, or treats historical all-FF as free would mask the unresolved cut point.

## Evidence and limits

- notes/2026-10-11-stock-spl-final-contract.md records the byte-verified normal selection path: helper 0x1320 locates the app_dir_head record, reads and CRC-checks the application-area header, sets entry metadata, and the ordinary XIP path calls it. With successful selection, invalid inherited RAM record flows around the trailing-flash-record search. This is evidence about SPL selection only, not all app code or runtime inputs.
- notes/2026-10-14-stock-spl-update-record-staging-review.md records that a failed ordinary app selection can reach the conditional record scan. The record is sector-end minus 0x100, and the new byte-level review checked the scan and CRC contract. This supports a staged loader before stock-header commit; it does not show that a bad/incomplete loader still works.
- firmware/third_party/dinghy/src/ota.c stages five sectors at its own 0xE0000 address, and reference/dinghy/firmware/loader/ldr_core.c writes its own fixed [0x4000,0x93000) app range. Those are implementation precedents, not direct evidence for an FM-1_092 USR stage or a d9000 rollback.
- notes/2026-10-14-stock-bank-characterization.md and the retained pair show USR is materially populated and opaque. The stage range F2000-F7000 was all 0xFF in the historical pair, but the note explicitly says that does not establish ownership or future-use behavior. Earlier stock-V15 diagnostics are not an FM-1_092 allocator or startup proof.

The requested host model is not implemented: without exact stock storage semantics and an erase-failure model, a test would only encode an assumption. A future planner can model the proven SPL branch predicates and enumerate every operation prefix, but must label any prefix after stock-header commit as only ∫w^~)ﬁtSPL selects stock XIP entry+ßuÁ‚ùÁ] not+ßuÁ‚ùÁ\stock boot/recovery succeeds+ßuÁ‚ùÁ] The acceptance blocker is specifically the stock app's behavior with a damaged/intermediate stage extent in USR.

## Next evidence needed

Find a version-matched FM-1_092 stock runtime path or use a reviewed, reversible bench plan to establish the storage contract; neither is available in this offline review. At minimum, determine whether stock startup reads F2000-F7000 or scans/repairs USR, how it handles partial sectors, and whether any invalid bytes can prevent a usable stock update UI. Until then, keep the five-sector USR layout as a capacity proposal only and do not claim exact-stock rollback is power-fail recoverable.

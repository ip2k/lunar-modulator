# FM-1_092 startup evidence and rollback cutpoint model

Date: 2026-10-14
Scope: offline only. No hardware, flash, USB or MIDI commands. Private stock binary remains outside Git.

## Finding

The proposed stage-last order is still not proven power-loss safe. The SPL evidence proves only that a valid application-area header makes the SPL select the stock XIP entry and skip its flash recovery-record scan. It does not prove that the selected app reaches usable startup, VM initialization, MIDI, or the stock updater after arbitrary damage to USR sectors F2000-F7000.

I inspected the retained matching FM-1_092 application offline with the pinned JieLi pi32v2 objdump. The 691744-byte extracted app was wrapped as ELF32 machine 0xf1 and disassembled as pi32v2. A targeted search of the disassembly and exact little-endian application bytes found no literal references to EA000, F2000, F7000, or F6F00. The app has no usable symbol table in this artifact, so this is not a call graph or proof of non-use: computed addresses, shared SDK routines, runtime tables, alternate encodings, and indirect reads remain possible.

The pinned SDK exposes generic VM interfaces in source-sdk/include_lib/driver/device/vm.h. Its comment says VM initialization is performed on every power-up; vm_init accepts a device handle, start address, length, and mode. Implementation is in closed SDK libraries. The SDK source tree contains no FM-1_092 application startup call site and does not establish which addresses the stock app passes. This source makes it especially important not to equate a valid SPL-selected entry with a usable stock app.

Therefore no offline evidence here proves that a partially erased stage sector is ignored, tolerated, or recoverable by FM-1_092 startup. Keep the stage-last proposal blocked on app-readiness evidence or design a recovery path that does not require the stock app to tolerate partial stage contents.

## Cutpoint planner

Added tools/native/rollback_cutpoints.py and tests/test_native_rollback_cutpoints.py. The pure host model emits before, during, and after points for each described mutation. During a mutation it reports unknown rather than assuming sector erase/program atomicity. It distinguishes:

- stock_xip_selected: the proven SPL app-header gate selects the stock XIP entry;
- loader_record_scan_reachable: the selected app gate is false and a valid recovery record is assumed present;
- no_verified_spl_entry / unknown: no modeled path is proven; and
- stock_app_ready: always "unknown".

The model is not an installer, image validator, storage simulator, or acceptance gate. In particular it cannot promote stock_app_ready from unknown. Its state inputs are declarative test fixtures and do not read target evidence.

## Evidence and limits

- notes/2026-10-11-stock-spl-final-contract.md: byte-level SPL selection and branch evidence; establishes app entry selection, not app runtime.
- notes/2026-10-14-stock-spl-update-record-staging-review.md: conditional record scan and record placement evidence.
- Retained matching private archive: /home/claude/mvave-fm1/native-external-arenas-16-20261012/out/expanded-private-geometry-v1/identity.json identifies FM-1_092 and archive SHA-256 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4. Extracted files/app.bin is 691744 bytes. No raw binary or extracted payload is committed.
- Pinned SDK source: /home/claude/mvave-fm1/sdk-v1213/source-sdk/include_lib/driver/device/vm.h exposes vm_init and its power-up initialization comment; VM implementation is not present as source.
- Semantic-index coverage: the available Mac Rarefaction/Serena selections were not this Hera isolated checkout, so I did not use them as evidence for the Hera files. Target binary navigation used the pinned vendor pi32v2 objdump and direct inspection.
- Pinned target objdump: /home/claude/mvave-fm1/sdk-v1213/toolchain/jieli-linux-toolchains-20250324.1/pi32v2/bin/objdump, LLVM 4.0.1, registered pi32v2 target. The app was disassembled offline with an ELF wrapper using machine id 0xf1. Exact literal-search negatives are not proof of absence of indirect or computed access.
- Earlier stock V15 diagnostics and generic SDK examples do not match the FM-1_092 app and are not substituted for its startup trace.

## Next step

Obtain a version-matched FM-1_092 startup trace or source/matching map that resolves whether its VM/syscfg initialization scans or accesses F2000-F7000, and how it handles interrupted sectors. If that cannot be established, select a rescue design whose boot path remains independent of stock-app startup until stage cleanup is complete. The cutpoint model should then be driven by the resulting verified transition predicates; it must continue to report app readiness as unknown until separate evidence supports that predicate.

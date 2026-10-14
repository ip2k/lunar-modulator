# Five-sector USR rescue staging and combined-storage review

Date: 2026-10-14
Scope: offline design review only. No hardware commands, device writes, or install admission.

## Conclusion

A 20 KiB persistent staging area is capacity-feasible alongside two 48 KiB project slots and the existing 8 KiB settings journal if the FM-1_092 VM and USR ranges are deliberately repartitioned. This avoids relying on an unproven 3.5 KiB replacement loader. It does not establish semantic migration, physical ownership, installability, or power-fail-atomic rollback. In particular, replacing the persistent rescue-stage sectors with their original stock bytes destroys the staged recovery image during rollback; the current 136 KiB VM+USR budget cannot hold two five-sector stages plus 96 KiB projects and the journal.

The existing compressed loader is a concrete precedent: 19,937 compressed bytes plus its 32-byte JLFS header fits five 4 KiB sectors with only 31 bytes under the current 0x4e00 body limit. Reuse/adapt that streaming loader architecture and its chunked transfer, not a speculative loader-size reduction. Its current fixed app boundary and recovery semantics are not suitable unchanged for the expanded d9000 target.

## Evidence and exact capacity proposal

The retained matching FM-1_092 pair is historical evidence only, not a fresh device backup or authorization. Its manifest pair digest is 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4. Byte occupancy observed in stockA.bin: VM D9000-E9000 is 64 KiB / 16 sectors; BTIF E9000-EA000 is 4 KiB and contains 10 non-FF bytes; USR EA000-FC000 is 72 KiB / 18 sectors. VM has 142 non-FF bytes at D9000 and 213 at E8000; the other VM sectors were all FF. USR EA000-F1000 is populated, F2000-F9000 was all FF, FA000 is populated, and FB000 contains 3,594 non-FF bytes. These are byte observations only; FF does not prove free ownership. The SPL, OTA, cfg, BTIF and all other protected bytes remain preservation requirements.

Proposed logical allocation (4 KiB sectors; half-open ranges):

- Project slot A: D9000-E5000 (12 sectors, 48 KiB).
- Existing two-sector settings journal: E5000-E7000 (8 KiB).
- Preserve VM tail: E7000-E9000 (8 KiB), including the historically populated E8000 sector.
- Five-sector persistent loader stage: F2000-F7000 (20 KiB), within the historically all-FF USR run. Record offset F6F00 (sector end minus 0x100).
- Project slot B: two extents EA000-F2000 (8 sectors / 32 KiB) and F7000-FB000 (4 sectors / 16 KiB), totaling 48 KiB.
- Preserve USR tail: FB000-FC000 (4 KiB), including its observed non-FF bytes.
- Preserve BTIF E9000-EA000.

Combined VM+USR capacity is 136 KiB / 34 sectors. This proposal accounts for 96 KiB project slots + 8 KiB journal + 20 KiB staging = 124 KiB, leaving 12 KiB. It intentionally overwrites historically populated bytes in D9000, EA000-F1000 and FA000-FB000; a byte-for-byte archive alone does not migrate those contents.

This layout deliberately scatters slot B around the rescue area. firmware/native/project_store.h currently models two contiguous equal slots (LP_HEADER 32, LP_SECTOR 4096, LP_MAX 98,304); 48 KiB physical slots permit only 49,120 payload bytes after the header. A bounded scatter-extent mapper and stricter per-slot capacity validation are required. firmware/native/settings_journal.h uses two sectors and a 256-byte payload with commit-last/readback behavior; its supplied geometry must be changed to the planned sectors only in a future authorized implementation.

## Existing mechanisms and limits

- tools/native/storage_backup.py requires two matching full-flash images bound to an expected full-image hash, validates geometry, archives raw and named VM/BTIF/USR/gap bytes, and verifies their hashes. The receipt explicitly leaves semantic migration, physical rollback and hardware admission false. The retained old pair cannot substitute for fresh matching physical backups before any real transition.
- firmware/third_party/dinghy/src/ota.c defines OTA_AREA 0xE0000, OTA_AREA_LEN 0x5000, OTA_RES 0xE4F00 and OTA_LDR_LEN 0x4DE1 (19,937). It stages in 512-byte chunks, checks CRC and readback, writes the header, and commits the record only after host success. This is the strongest existing five-sector sizing evidence. Its fixed address/host flow cannot be copied unchanged into the proposed F2000 region.
- The retained loader at /home/claude/mvave-fm1/native-baseline-20261012/firmware/loader/ldr_core.c documents 512-byte streaming input, one 4 KiB sector buffer, validation before erase, sector programming/readback/retry, and a persisted update record. Its current app bounds are 4000-93000 and record scan is 93000-FC000. It must be adapted and re-audited for D9000 app end, new storage map and the exact stock SPL record discovery path; current binary/size/recovery behavior is not thereby proven for such a build.
- The matching FM-1_092 SPL scan result is in handoff lunar--stock-spl-update-record-byte-review-20261014.md. The SPL tail scan is only reached after ordinary app selection fails. The record occupies the sector-end-minus-0x100 location and is CRC/signature checked. This creates a plausible persistent fallback entry while the app is invalid, but does not prove an app-independent recovery UI or host-resume behavior for a new stage.
- Existing expanded candidate/transport tooling preserves bytes after the app region and deliberately marks settings migration, hardware admission and installability false. Its byte-preservation behavior must be replaced by an explicit, reviewed repartition transaction before these proposed extents can be used.

## Transaction phases and power-loss ownership

A future offline implementation should model and test the ordered transaction below before any device approval:

1. Obtain fresh identity-bound, matching complete backups; verify the original SPL, OTA, cfg, BTIF and all protected ranges. Produce and verify an opaque whole-flash archive plus component hashes. Stop if pair identity/content differs.
2. Construct and validate the exact target allocation map, project slot mapping, journal sectors, stage range and candidate image. Reject overlap with protected components; require exact package/app/profile/selection hashes. Do not treat erased-looking sectors as free.
3. Seed the stage only through a reviewed stock-compatible bootstrap/package path. Stream in bounded chunks, verify body hash/CRC and flash readback, write header and valid OTA/update record last. Until the record is committed, old app remains authoritative.
4. On recovery entry, authenticate/read the record and staged loader, verify target identity and every target component before erasing. Stream the candidate app sectorwise with bounded RAM; preserve SPL/OTA/cfg/BTIF; initialize/migrate projects/settings only under an explicit migration contract; verify each write/readback.
5. Commit the target app directory/head last. Recovery code must remain outside every sector it may erase until the new directory and image verify. Interrupted writes should re-enter the staged loader when the SPL fallback scan applies.
6. Do not erase the stage or its record until target app, storage layout and migrated state have been verified. Exact-stock rollback must restore the archived original app/VM/USR bytes and all checksummed components. But if rollback also restores the original contents of F2000-F7000, the loader image is overwritten by that rollback itself. Directory-last alone does not make this step power-fail atomic. A browser-resumable rollback needs a second durable recovery copy, an independently proven ROM/recovery bridge, or a changed rollback contract. Two five-sector copies plus 96 KiB slots and 8 KiB journal require 144 KiB, exceeding the 136 KiB pool by 8 KiB.

The owner-approved expanded layout and settings migration/rollback authorize this design exploration only. They do not authorize current-device repartition or writes. Physical admission still depends on fresh backups, an implemented and reviewed transaction/recovery path, exact candidate correspondence, and the separately authorized staged bench plan.

## Recommended next implementation

Implement a host-only allocation/transaction planner for this exact map that consumes the verified backup receipt and candidate/transport manifest, emits ordered sector ranges and explicit protected/preserved/relocated classifications, and refuses stale inputs, overlap, non-verified backups, or unsupported migration. Add table-driven power-loss phase tests that assert which recovery artifact survives each cut point. In parallel, define/export the FM-1_092 VM/USR schema and a deterministic migration/rollback fixture from the matching baseline without modifying raw bytes. Before encoding a rollback claim, resolve the self-erasure problem: either reserve a second durable loader copy and reduce storage scope, prove a separate stock recovery mechanism survives, or precisely limit the accepted rollback guarantee. No target code or physical action should precede those checks.

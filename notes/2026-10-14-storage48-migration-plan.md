# FM-1_092 storage migration and rollback plan for two 48 KiB slots - 2026-10-14

## Decision

[verified] The retained FM-1_092 geometry admits a sector-count candidate for two 49,152-byte slots only by combining VM and USR extents and excluding the existing five-sector OTA staging range. This is arithmetic, not permission or proof that any sector is free. The historical 092 archive contains opaque, non-FF VM and USR data; even sectors reading all 0xFF are not established as allocator-free. Do not enable SAVE or change the profile based on this plan.

[verified] The current Dinghy OTA implementation erases [0xE0000,0xE5000) and writes its 112-byte persistent UPDATA_PARM at 0xE4F00; both lie in the stock 092 VM descriptor [0xD9000,0xE9000). Retaining that OTA path therefore requires excluding all five sectors from project storage unless a separately reviewed staging design replaces it. The FELUCCA_OTA_RAMONLY option removes the persistent record only; its own comment says a power cycle can leave a broken staged loader with no resume. It is not a storage migration.

## Evidence and exact geometry

tools/jieli/raw_flash_profile.py:37-41 pins the recorded 092 reserved ranges:

| Name | Half-open flash extent | Capacity |
|---|---:|---:|
| VM | [0xD9000,0xE9000) | 16 sectors / 64 KiB |
| BTIF | [0xE9000,0xEA000) | 1 sector / 4 KiB |
| USR | [0xEA000,0xFC000) | 18 sectors / 72 KiB |
| key_mac | [0xFF000,0x100000) | 1 sector / 4 KiB |

The existing characterization in notes/2026-10-14-stock-bank-characterization.md:37-51 hashes the archived VM and USR components against their manifest. It found two VM sectors with non-FF bytes and fourteen erased sectors; USR has ten non-FF and eight erased sectors. These are historical archived bytes, not a fresh device read, schema, reachability analysis, or allocation authority. The same note explains that no FM-1_092 VM/USR decoder or allocator was found (:53-66).

The checked-in OTA code defines the five-sector window and record address (firmware/third_party/dinghy/src/ota.c:24-29); it erases every sector in that window before staging (:303-333), persists and reads back the record at OTA_RES before ota_commit (:363-390), and erases the staging window on failure and during boot cleanup (:342-347,393-407). Thus [0xE0000,0xE5000) is a live update-path conflict, not merely a possible collision at 0xE4F00.

### Arithmetic-only candidate if ownership is later established

A 48 KiB journal slot is 12 x 4 KiB sectors. The aggregate VM+USR capacity is 34 sectors. Excluding the five OTA sectors leaves 29 sectors, enough arithmetically for two slots and five unallocated sectors. One explicit scatter map is:

| Logical slot | Physical extents | Sector count |
|---|---|---:|
| A | VM [0xD9000,0xE0000) (7 sectors), VM [0xE5000,0xE9000) (4), USR [0xEA000,0xEB000) (1) | 12 |
| B | USR [0xEB000,0xF7000) | 12 |
| Unassigned remainder | USR [0xF7000,0xFC000) | 5 |
| Reserved for current Dinghy OTA staging | [0xE0000,0xE5000) | 5 |

The map uses only sector-aligned extents and avoids the current OTA erase window. It crosses named reservations and Slot A is discontiguous, so project_store.h's adjacent-slot arithmetic cannot represent it as-is. The separate extent_io.h mapper is a possible implementation primitive, not evidence that these extents may be overwritten. Slot payload would need to remain at most 49,120 bytes after the 32-byte slot header (the exact journal format is in firmware/native/project_store.h); this is below the current generic 98,304-byte import limit, so the product schema and API must also enforce a 49,120-byte payload ceiling for this geometry. No source change is proposed here.

An alternative is to relocate the staging transaction into a separately authorized and proven extent outside VM/USR. [0xD7000,0xD9000) is sometimes discussed as application tail space, but this note does not establish it as durable staging, SPL-visible, size-safe, or power-loss recoverable. Any such plan must first show that the maximum app/config/tool footprint leaves the entire extent unused, derive and test the loader's exact record discovery and cleanup behavior there, and establish boot recovery after interruption. Do not move OTA constants or reuse this tail by inference.

## Required gates before any migration or SAVE enablement

1. **Fresh baseline and semantic ownership.** Obtain two matching, complete, read-only FM-1_092 dumps under the owner's separately reviewed device campaign; bind identity, acquisition log, per-file hashes and exact stock SPL/app/config versions. Decode VM/USR with a version-matched stock allocator/format or establish a reversible migration that preserves every unknown byte. Confirm which sectors and records stock firmware may allocate now and after reboot/update. The historical archive is not a substitute for a fresh baseline.
2. **Explicit extent approval and complete cross-map.** Have the owner approve the exact sector list and intended bank semantics. Validate the candidate against app/config limits, VM/BTIF/USR boundaries, the OTA write/erase range, all project writes/erases, stock loader app-write bounds, cleanup scans, SPL record scan candidates, key_mac and all other protected ranges. The earlier review documents that the stock loader cleanup range intersects VM, BTIF and USR; that behavior must be accounted for, not bypassed.
3. **SPL trailer-record collision prevention.** 0xE4F00 is a 4 KiB boundary-minus-256 record location. The reviewed SPL work describes conditional scanning for an UPDATA_PARM signature/CRC, while the scan-loop bounds remain qualified in notes/2026-10-14-stock-spl-update-record-staging-review.md:7-10,23-25. Before storing arbitrary project bytes in any scanned sectors, reproduce the exact FM-1_092 scan offsets and validation predicates from the pinned SPL. Then prove by construction and mutation tests that every stored state is rejected as a trailer record at every scanned candidate offset, or reserve/exclude the vulnerable bytes/sectors. A probabilistic "unlikely signature" argument is insufficient. Also ensure Dinghy cleanup cannot erase a project sector while searching for update records.
4. **Power-loss-safe migration protocol.** Do not destroy the sole stock state before the new layout is durable and independently verified. A candidate sequence is: archive two fresh full images and decode/retain opaque extents; write the new app while stock suffix bytes remain untouched; verify app and preserved-bank readback; initialize both journal slots without erasing the only old copy; import/round-trip all migratable state and compare semantic plus raw hashes; boot-test stock rollback and new app separately; only then consider sector reassignment. This sequence remains a design proposal until erase granularity, programming order, old-stock access and failure recovery are shown for the actual boot path.
5. **Rollback evidence.** A rollback must restore more than the app entry: include the exact matching stock 092 app, SPL, config and every original VM/BTIF/USR/key_mac/unnamed suffix byte from the verified baseline. Verify the reconstructed full image byte-for-byte offline before use. The project notes record a bounded sector restore, but not full-image restoration or stock readiness after rewriting stock state; do not call rollback proven until the authorized recovery path has restored and booted the exact stock image/state. Keep an independent ROM/USB recovery route available for the case where the running app or stock OTA service no longer starts.
6. **Implementation and acceptance.** Only after the above gates: implement a profile-specific scatter map and bounds-checked IO adapter; keep format/migration versions explicit; cap imports to 49,120 payload bytes; add host fault-injection for interruption during each erase/program/header/commit boundary and prove the older committed generation survives; then perform target-link/source-freshness checks. Hardware writes and enablement remain the coordinator/owner's separate approval and test scope.

## Risks and residual unknowns

- The archived 092 banks are opaque; stock semantics and erased-sector ownership are unresolved.
- The OTA stage/record window conflicts with VM today. Relocation is not validated, and RAM-only mode loses restart safety.
- The exact FM-1_092 SPL trailer scan loop still needs a fresh exact-byte/disassembly reproduction; project data could overlap a candidate tail-record location.
- Stock loader cleanup scans beyond its stage and can intersect the proposed banks; stock OTA behavior after migration is unknown.
- No fresh baseline, target writer test, physical power-loss test, full stock restore, stock rollback boot, or SAVE admission was performed for this plan.

## Scope

This is offline design research based on checked-in source, prior committed analysis notes and the retained historical archive characterization. It performed no USB, MIDI, flash, power, reboot, package emission, or physical operation. The map above is proposed capacity arithmetic only. It does not authorize changing storage descriptors, writing any device sector, enabling the writer, or claiming rollback, update-path, or product acceptance.

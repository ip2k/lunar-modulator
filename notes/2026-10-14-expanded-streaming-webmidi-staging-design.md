# Expanded streaming WebMIDI staging and recovery design

Date: 2026-10-14
Scope: offline design from retained FM-1_092 capture and checked sources. No device commands, physical writes, admission, or playback claims.

## Recommendation

One candidate persistent browser updater design uses RAM streaming with a small compressed rescue stage in one explicitly reserved 4 KiB sector inside the expanded app extent. It would reserve sector D8000 and its SPL-scan record slot at D8F00 in the profile. Keep D8000-D8FFF intact while writing the expanded app, then reclaim it only after a validated app boots. Do not infer sector ownership from erased bytes; the reservation must become explicit profile policy and pass package/candidate validators. This is not the only possible allocation: the owner approved settings migration and rollback verification for the expanded layout. A separate follow-up evaluates a five-sector reservation using the existing loader and an explicit export/migration of stock USR contents, alongside the required project and settings banks. Neither allocation is admitted here.

The exact expanded profile currently computes an 862,272-byte app extent to end at D6960, then places tool/config records through D765C, leaving D8000-D8FFF clear in the named geometry. These values are a geometry calculation, not a fresh app receipt. The expansion must reject any app/profile whose metadata overlaps the reserved sector or whose config records extend past the verified bound.

## Why one sector can be enough, conditionally

Felucca's maintained GPL-3.0-only OTA code at firmware/third_party/dinghy/src/ota.c documents a persistent staged-loader design:
- OTA_AREA is E0000, OTA_AREA_LEN is 0x5000 (five 4 KiB sectors), record at E4F00.
- The pinned official compressed loader is 0x4DE1 bytes (19,937), plus its 32-byte header and a 256-byte record area. Its conservative guard requires len <= OTA_AREA_LEN - 0x200. This needs five sectors.
- The same code separately bounds an uncompressed Felucca loader at 0x14000 (80 KiB); 80 KiB is an uncompressed maximum, not the compressed official stage size.
- LUNAR_OTA_RAMONLY suppresses the persistent record and explicitly loses recovery after power interruption.

A smaller custom first-stage bootstrap could fit one sector only if its compressed artifact, header, padding, and the reserved 256-byte scan slot together fit within 4096 bytes. That leaves at most 0xE00 (3584) bytes for the stored body under the same conservative guard. No evidence currently shows this implementation fits. The first implementation step is a pinned pi32v2 -Os build and link-map check against this 3584-byte limit, including all code required before streaming starts. If it misses, do not reuse E0000-E4FFF: that entire five-sector region is within the FM-1_092 VM bank. Reduce features/code or return to owner for a separately authorized allocation review.

## Transaction and recovery sequence

1. With the current app running, WebMIDI explicitly selects a validated device session and pinned candidate. The app stores the small rescue stage and a CRC-protected record in the reserved sector, verifies both by readback, and only then requests reset.
2. The stock SPL chooses the normal app when its directory is valid. Its sector-tail record scan is conditional on app selection failure; byte review says a successful ordinary app selection bypasses the tail scan. Therefore a valid but crashing app does not automatically enter the stage.
3. The first stage is entered through a tested valid RAM mailbox while the app is still intact, or through the SPL's invalid-app scan only after app selection fails. This reachability difference must be tested on matching hardware before claiming browser recovery.
4. The first stage stays resident in SRAM and receives the larger updater/application as bounded WebMIDI chunks. It hashes and validates the complete stream without holding the 862,272-byte image in RAM. A second RAM-resident finalizer is then loaded and verified before it erases/programs the app. It streams sectors and reads them back; it writes directory/records last. The rescue sector is outside the app record extent and remains available through interruption.
5. A completed image must pass structural/hash checks and an explicit boot check before the rescue record is retired. Failure before app erase leaves the existing app; interruption during replacement relies on the SPL invalid-app scan and the persistent rescue stage. A malformed or valid-but-nonbooting directory is a known gap until proven to take the SPL invalid-app path.
6. A host may resume only the same pinned candidate, device identity, session nonce and stage hash. Require bounded queues, deadlines, exact sequence/offset, end-to-end image hash, and readback acknowledgments. No arbitrary raw flash-range API.

## Settings migration and rollback

The retained matching FM-1_092 pair is historical input, not a fresh baseline for installation. The capture/pair digest is 96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4; its evidence marks physical recovery unverified. Matching backups and current physical identity are still preconditions.

The 862,272-byte profile leaves only a small number of named sectors in the expanded app bank. It does not authorize borrowing VM/USR/BTIF, and the existing OTA E0000-E4FFF lies inside the VM bank. Keep the existing opaque settings banks byte-identical through the first install and keep SAVE/journal disabled. A later migration needs a decoded FM-1_092 schema, export/import fixture, idempotency and rollback tests, and an explicitly allocated two-sector journal. The current native settings journal needs two 4 KiB sectors; no physical allocation is admitted. Never erase or reinterpret the existing settings bank based only on all-FF observations.

If app replacement fails, the rescue stage can reinstall the same pinned app or restore a separately retained exact old app only when the prior raw baseline and geometry are admitted. Settings rollback also requires preserving the original opaque banks; no settings migration or user-data round trip is currently verified.

## Exact byte and source evidence

- notes/2026-10-14-stock-spl-update-record-byte-review.md and coordination handoff lunar--stock-spl-update-record-byte-review-20261014.md: pinned SPL compared byte-for-byte after vendor objdump/objcopy. Its sector-tail scan checks offsets 0x1f00..0xfef00 in 0x1000 steps, with an 80-byte record at boundary-0x100. This proves scan bounds in the image, not the device's behavior under interruption.
- firmware/third_party/dinghy/src/ota.c:24-29 defines the five-sector stage and 19,937-byte compressed official loader; lines 280-292 validate loader framing and 80 KiB own-loader bound; lines 303 onward stage and verify it.
- tools/jieli/expanded_flash_profile.py:12-29 computes profile bounds; tools/native/expanded_candidate.py:47-60 preserves bytes outside the expanded app area and regenerates only app records; it does not reserve the rescue sector yet.
- tools/native/expanded_transport_manifest.py and expanded_sg.py remain offline/host-SCSI manifest paths; they do not establish a browser-capable transaction.

## Practical next implementation

Add a new profile invariant reserving D8000-D8FFF and D8F00 without changing device behavior. Build a minimal GPL/permissive-licence-reviewed RAM loader candidate, measure compressed and uncompressed sizes, and test its parser/CRC/SPL-record serialization offline. In parallel specify WebMIDI chunk protocol and a RAM finalizer based on existing guarded sector ordering/readback code. Only after the size/reachability and settings-preservation gates pass should the coordinator plan a separately reviewed hardware test. The only acceptance today is offline source/geometry design; no package is installable, and no browser/device write or recovery path has been validated.

# SPL app-header validity and rescue-record ordering audit — 2026-10-14

## Finding

[verified] The pinned FM-1 stock SPL only scans its trailer rescue-record slots after normal application selection fails. The exact 14,384-byte SPL used in the existing byte-column comparison has SHA-256 `730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`. Its retained JieLi-objdump listing is `/tmp/lunar-spl-record-byte-review/spl.lst` on Hera; this audit read the relevant regions rather than re-running the vendor decoder.

The application lookup at `0x1320` searches the top `app_dir_head` entry, validates its 32-byte header and the selected `app_area_head` 32-byte header, and returns success only after the CRC checks. The caller at `0x2d72` sets `r13 = 0` at `0x2d7e` on success. At `0x2e08`, `r13 == 0` branches to `0x2f78` and bypasses the rescue scan. When lookup failed (`r13 != 0`), code at `0x2e1a..0x2e36` walks candidate slots; at each slot `boundary - 0x100`, it checks the `0x5441` tag at +6, CRC16/XMODEM over +2..+79 against +0, and nonzero +2. A match then follows +72 and validates/decompresses the referenced loader as recorded in `notes/2026-10-11-stock-spl-final-contract.md` and `notes/2026-10-14-stock-spl-update-record-byte-review.md`.

[verified] Therefore the existing “write app body, then write app directory/header last” sequence does not make the trailer loader a fallback during body writes. The old valid directory and area header remain selectable until the final metadata-sector update. If power is lost after an app-body sector is changed but before that final update, the next SPL pass can still select the old header and skip the trailer-record scan. The SPL metadata checks are not proof that the entire XIP application body is intact or runnable. A header-valid/XIP-selected state is distinct from stock application readiness.

## Header-invalidation candidate, strictly offline

The selected `app_area_head` record begins at raw flash offset `0x4000` in the historical expanded candidate. The repositorys SFC decoder is a positional XOR-LFSR transform, so a raw bit flip maps to the same decoded bit. The SPLs record-header predicate compares the decoded CRC at +0 against CRC16 over decoded bytes +2..+31 (the lookup helper around `0x1398..0x13a8`); this is distinct from the rescue-record CRC at +0 over 78 bytes.

A bounded offline check of the retained historical expanded candidate (`target.bin`, SHA-256 `0eaa6bd5501c64bb6f1e76c5e089dcd543816de35434d5cf4ed1170ba01df8c7`) found the decoded `app_area_head` header CRC valid. Nine currently-1 raw bits in its two-byte stored-CRC field, at raw offset `0x4000` or `0x4001`, can be cleared in a pure byte model to make the decoded stored CRC disagree with the unchanged decoded header bytes. This demonstrates only that a single raw 1→0 bit transition could encode an invalid stored CRC in this artifact. It does **not** prove that a physical FM-1 write API can clear that isolated bit, that an interrupted program has a useful monotonic result, or that the SPL on hardware observes the same state. The probe imported `tools/jieli/inspect_fwsc.py` with `PYTHONPATH=tools/jieli`, applied `sfc_decode(raw[0x4000:0x4020], 0)`, and evaluated the existing `crc16` predicate; it printed only artifact/header hashes, validity and candidate bit positions, never header bytes.

The precise gate is not merely “make some header invalid.” Before touching any app body sector, a future transaction would need to establish, in the actual raw representation and under documented target flash semantics, that the ordinary app lookup rejects the selected `app_area_head` (or the directory), and read back that state. It must separately verify a complete SPL-accepted record and complete referenced loader already exist in an authorized scanned extent. Keep that pair untouched while writing and reading back the full app body. Publish the new valid app metadata only after body verification. This ordering is a logical design constraint, not a tested NOR transaction or a physical write recommendation.

## Existing-artifact and layout limits

[verified] The historical stock capture pair and historical expanded candidate were scanned at all 255 SPL slots from `0x1f00` through `0xfef00` (stride `0x1000`); no `0x5441` tag or complete rescue record was present in either raw or decoded app-span view. Details and hashes are in `notes/2026-10-14-protected-rescue-record-audit.md`. Thus neither exact artifact currently supplies the precondition above. The scans are historical offline evidence, not a current device observation, and empty slots do not imply ownership.

The newer 6,954-byte maintained compressed RAM-loader geometry is separate work and is not validated by this audit. Parent review corrected its proposed tail arithmetic: app origin is `0x4120`, not `0x4000`, and current retained metadata ends at `0xD7674`; the apparent tail overlaps preserved metadata. Treat loader fit as unresolved and geometric figures as non-admission. Even a corrected extent does not establish ownership, SPL reachability, torn-write safety, loader acceptance, or stock readiness.

## Required gates and failure cases

- An authorized physical extent must be identified for both loader bytes and the complete accepted 80-byte record at an SPL-scanned slot; neither may overlap retained VM/BTIF/USR/configuration or another protected range.
- The exact SPL record format, pointer bounds, inner 32-byte header CRC/length, block limits, decompression length and output CRC must pass against the exact staged bytes, then be read back. SPL CRCs are integrity checks, not authentication.
- A concrete invalidation of ordinary app selection must be proven using the exact encoded raw bytes and target program/erase granularity. Readback must establish selection fails before any app-body rewrite begins. No device semantics were established here.
- App metadata must be published only after all app content is restored and read back. On interruption, an invalid app header is recoverable only while both the record and full loader remain valid.
- Cleanup and stock readiness remain unresolved. Once a valid app header is restored, SPL bypasses rescue even if VM/settings initialization or the stock app later fails. Conversely, removing the record or payload while app selection can still fail reopens the no-rescue terminal path described in `notes/2026-10-14-spl-empty-rescue-fallback.md`. App-header validity is not a safe cleanup criterion.

## Limits and next dependency

This was a read-only offline audit of retained disassembly, source format code and a historical image. It did not run SPL, use a device, test flash erase/program behavior, change production code, allocate flash, or authorize installation. It does not establish the observed reset symptom after a partial app-body write, mask-ROM/USB availability, or target header-publishing atomicity.

Next, the coordinator must resolve an owned staging layout and establish target-specific raw read/erase/program semantics and readback behavior before converting this ordering constraint into a transaction. A separate readiness criterion must cover stock startup/settings state before cleanup. Until those dependencies are closed, no software-only rollback guarantee is supported.

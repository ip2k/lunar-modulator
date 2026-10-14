# Private stock-path acceptance plan for the FM-1_500 candidate

2026-10-14. Offline source review only. No device command, USB/MIDI operation, flash operation, package transfer, or hardware acceptance was performed.

## Decision

There is an OTA service in the native application. `firmware/third_party/dinghy/src/platform.c` sets `FELUCCA_OTA=1`, includes `ota.c`, calls `ota_service()` in the main loop, and consumes `usb.ota_req` (`platform.c:62-63, 90-92, 260-266`). `usb.c` identifies distinct command bytes: `F0 22 24 35 7F F7` sets `ota_req`; `F0 22 24 35 7D F7` is the separate UBOOT soft key (`usb.c:140-146, 685-719`). OTA identity query command `0x11` is answered by `ota_service()`; normal app identity is the configured `FELUCCA_ID`/`FM-1_500`, recovery identity is `FM-1_000` (`platform.c:91`, `ota.c:130-159,165`). Thus the assumption that Lunar has no Step-1 service is incorrect.

However, the current diagnostic target is intentionally non-writing. `tools/native/build_application_probe.py` rewrites the platform guard to `#define FL_RANGE_OK(off, n) (0)` and omits boot cleanup; its receipt says `flash_write_range="empty"` (`build_application_probe.py:342-343, 517`). The production OTA callbacks call guarded `fl_erase4k` and `fl_write` for staging (`platform.c:100-124`). The handlers can answer the read-only identity query, but `ota_stage()` fails at its first erase and cannot enter the loader. Keep the build this way until a safe, durable staging layout is proven.

Re-enabling the current staging code is not a safe shortcut: `ota.c` erases `[0xE0000,0xE5000)` and stores the persistent 112-byte update record at `0xE4F00` (`ota.c:24-26,303-339,363-389`). The recorded 092 layout reserves VM `[0xD9000,0xE9000)`, so both ranges overlap VM. `FELUCCA_OTA_RAMONLY` only drops the persistent record; the source comment says power loss leaves a broken staged loader (`ota.c:378-382`). See `notes/2026-10-14-stock-spl-update-record-staging-review.md`. Do not alter the range guard or use an erased-looking VM sector without allocator/ownership and interrupted-update recovery evidence.

## Exact candidate and scope

The explicit-identity target note describes an **FM-1_500 song-diagnostic** app, not a continuous-runtime release: 845,272-byte `app.bin`, SHA-256 `27600a10bae2ec177699ae2a1e3794b739e6085f61d088c47348db7a0eb515e4`, target ELF SHA-256 `335c448e67919e2bc52e7421164033ddd505956016531897aebe73f15772a4d1`. The offline FWSC candidate is 978,484 bytes, SHA-256 `04eff46e475b54678be580269f0a1683410048b636ea53fc871e7c4a391cb38d`; it binds app/ELF/receipts and retains source 092 package components. See `notes/2026-10-14-native-identity-target.md` and `notes/2026-10-14-package500-offline.md`.

These are offline model/composition results only. Freeze the exact artifact intended for a physical test. Do not relabel this song-diagnostic artifact as a continuous build or infer package identity acceptance from its embedded string. Keep `installable`, updater acceptance, hardware, SAVE, and release admission false.

## Recommended executable path

1. **Freeze a test packet offline.** Select one exact artifact and record source commit, profile/catalogue hashes, app/ELF/FWSC hashes, identity literals, protected-component hashes, build/composition receipts, and restore-image hash. The current `FM-1_500` candidate above is diagnostic, not automatically the later continuous candidate. Run the independent package parser and malformed-length/CRC/identity negative cases against these exact bytes.
2. **Use the existing application OTA endpoint only for read-only identity verification.** On an independently admitted, recoverable target, issue the documented OTA identity query (`M-UPGRADE` command `0x11`) and capture the full response. The `0x7F` upgrade command starts the staging/session path; do not send it while safe staging is unresolved. The distinct `0x7D` UBOOT command remains governed by its own staged authorization.
3. **For stock-loader acceptance, establish a known-good stock updater state through the separately audited ROM route.** Existing exact-bound returned-ROM backup/restore adapters are design references (`tools/fm1_returned_rom_stock_restore.py`, `tools/fm1_sdk_trace_admitted_stock_restore.py` and their associated adapters), not reusable admissions. A new physical campaign needs a fresh device-specific identity/mode witness, two matching complete dumps, explicit reviewed admission, exact target/restore hashes, and a fresh recovery route. Historical 092 tests and prior device campaigns do not authorize or prove a new device write.
4. **Run paired positive-control and candidate through the actual stock updater.** From the verified stock app, record identity query, then exact host request/response captures for a known-good matching-baseline 092 package before testing the frozen FM-1_500 candidate. Compare Step-1 acceptance/refusal and identity state; if Step 1 accepts, capture loader re-enumeration, Step-2 request addresses/lengths, completion reply, and actual flash readback against intended changed extents plus unchanged protected SPL/OTA/cfg/key ranges. A terminal `0xF0000000`/`success` response alone is not proof of write or boot. Do not mutate `cfg`, outer identity, lengths, or CRCs to guess around refusal.
5. **Verify independently after any accepted write.** Read device identity after reboot, capture normal/recovery USB modes and relevant startup behavior, then prove the exact recovery/stock-return path by full readback against the fresh baseline. Only after this may owner musical/perceptual acceptance be requested. Runtime, loader, recovery, and musical acceptance are separate gates.

## Evidence status

- **Source-established:** the app contains a read-only OTA identity service and distinct upgrade trigger; the current probe image denies erase/program by construction; the OTA staging and persistent record overlap the known 092 VM reservation; source handlers validate internal UFW/JLFS fields and verify staged loader contents before asking the host to continue.
- **Offline artifact-established:** candidate bytes, modeled FWSC nesting/CRCs, explicit app/recovery identity literals, and source-receipt correspondence. See `notes/2026-10-14-package500-loader-review.md`.
- **Not established:** stock Step-1 acceptance of this exact 978,484-byte package; proprietary loader acceptance of expanded D7000 extents and size; actual erase/program bounds; device execution of app OTA or stock loader; successful boot, recovery, or owner acceptance. The proprietary loader is closed; earlier vendor-disassembly review did not establish a general maximum extent from attributable code. Reported V15/092 updates do not close candidate-specific checks.

## Smallest next dependency

Before a write-capable browser path is tested, choose and prove a restart-safe staging/record allocation compatible with the target partition map, or use a fresh device-specific ROM restore to establish a known-good stock updater state and test the stock loader from there. Do not make the current Lunar OTA handler write to overlapping `0xE0000`. Freeze the exact continuous candidate if continuous runtime is intended, then seek fresh device-specific admission for the paired package test. This is a plan, not approval to issue the update command or proof the proprietary loader accepts the candidate.

## Tooling coverage

Serena initial instructions were read. Serena remained selected on the Mac authoritative project, so it was not retargeted to this concurrent Hera checkout; Rarefaction status could not resolve the Hera worktree. The review used direct source inspection and existing repository evidence. No semantic index result is claimed.

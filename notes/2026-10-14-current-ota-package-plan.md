# Current full-song candidate and stock OTA package boundary (2026-10-14)

Status: read-only offline review. No package was composed, no candidate was
changed, and no device command or write occurred. No installer or hardware
admission is implied.

## Finding

There is no safe parameter-only change that would make the fresh full-song
candidate install through the preserved stock V15 FWSC/OTA route. Two
independent constraints fail:

1. The current application is 862,296 bytes (SHA-256
   `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956`).
   The exact stock V15 nested package profile inspected in
   `tools/jieli/inspect_stock_flash.py` has an app resource entry sized
   581,564 bytes; `tools/jieli/model_app_replacement.py::_build` rejects a
   replacement larger than that original entry. The current app is 280,732
   bytes over the bound. `tools/native/ota_candidate.py::inputs` rejects it
   earlier because that prototype pins a different 20-second app hash,
   V15-container hash, and identity `FM-1_990`.
2. The actual offline full-song candidate is a raw 1 MiB `FM-1_092`
   expanded-d9000 image, SHA-256
   `cd8f0de6548714868461f960de15dcc65fbc4a5e8c278f8f02d93e65010d6d76`.
   Its app-area/records extend to `0xD9000`. Stock V15's FWSC flash payload
   is exactly `0x93000` bytes; `inspect_stock_flash.py` enforces that size,
   with V15 VM beginning at `0x93000`. A raw expanded candidate is neither
   a stock FWSC payload nor an OTA package.

The upstream Dinghy GPL-3.0-only loader source at pinned commit
[d44df7db09b98ccad2f1233b8f83f5f09c04829e](https://github.com/zvenson/dinghy/tree/d44df7db09b98ccad2f1233b8f83f5f09c04829e)
provides the clearest maintained implementation evidence. In
[firmware/loader/ldr_core.c](https://github.com/zvenson/dinghy/blob/d44df7db09b98ccad2f1233b8f83f5f09c04829e/firmware/loader/ldr_core.c),
`LDR_APP_HI` is `0x93000` (lines 623-628). `ldr_pass` rejects a flash payload
smaller than that bound (768-770), then erases/programs sectors only from
`LDR_APP_LO` to `LDR_APP_HI` (806-857); bytes after that are read only to
complete the package CRC (859-868). Therefore a longer outer `flash.bin`
record does not extend the actual write interval. The matching pinned
[fm1pkg_make.py](https://github.com/zvenson/dinghy/blob/d44df7db09b98ccad2f1233b8f83f5f09c04829e/tools/fm1pkg_make.py)
fixes `FLASH_SIZE` and `APP_SLOT` to its stock V15 extent. This is source
behavior for Dinghy's maintained loader, not a claim that every proprietary
M-VAVE loader revision has identical internals. It is enough to reject
wrapping this expanded raw image as though the stock write path supported it.

The package preservation gate also matters: `tools/jieli/package_guard.py`
requires byte-identical stock `top/uboot.boot`, `top/isd_config.ini`,
`ota.bin`, and `files/cfg`. Modifying the shipped OTA loader to widen its
range is outside the allowed preserved-component profile, and there is no
reviewed replacement loader or new stock-package identity contract here.

## Exact current candidate evidence

The prior offline candidate handoff
`/home/claude/.local/share/codex-coordination/handoffs/lunar--fullsong-current-candidate.md`
and note
`/home/claude/worktrees/fullsong-current-candidate/notes/2026-10-14-fullsong-current-candidate.md`
bind this application to ELF SHA-256
`f370fdb840b723e78388b81f56a076d30a130ad560485281fbe6c2ad406d294a`,
selection request SHA-256
`0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a`,
profile SHA-256
`b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`,
and one adapted Event Horizon Showcase project at startup index 0. Its
expanded raw target and manifest are privately prepared and keep all
installability, hardware admission, OTA verification, recovery, and settings
migration flags false. The source candidate uses a retained historical backup
pair, not a fresh prewrite pair.

The last line of the external handoff is not a package correspondence check:
`ota.bin` in the outer FWSC is a distinct component from the raw NOR target.
No FWSC or OTA package for the 092 expanded candidate was generated or
verified in this task.

## Smallest safe next step

Do not add a `--size`, `--identity`, or alternate app-slot override to
`ota_candidate.py`, `model_app_replacement.py`, or `inspect_stock_flash.py`.
Those would bypass independent identity, allocation, outer-container, and
actual-loader bounds rather than establish a valid path. For the current
expanded target, continue on the existing separate raw-image/transport-manifest
route and first complete the owner-reviewed backup, migration, recovery,
transport, and hardware gates. If a stock OTA route remains a requirement,
it needs a separately authorized loader/package design with an explicit
identity, write map, recovery behavior, and offline simulator/fake-loader tests;
changing the preserved OTA bytes is not an implementation detail.

Before any future *bounded* OTA candidate builder is considered, its negative
suite must prove that this 862,296-byte app and the 0xD9000 profile are
rejected before output creation. Positive format tests must independently
verify identity/version markers, UFW header/entry/payload CRCs, JLFS and SFC
bounds/checksums, unchanged SPL/config/OTA/cfg hashes, unchanged V15
allocation/partition positions, and exact app-length bounds. These tests
would validate the package contract only; they cannot prove proprietary-loader
execution, device recovery, migration, or physical installation.

## Review coverage and limits

Reviewed the branch's `ota_candidate.py`, `model_app_replacement.py`,
`inspect_fwsc.py`, `inspect_stock_flash.py`, `package_guard.py`, current
expanded candidate note, and pinned upstream loader/packer source. Rarefaction
and Serena remain selected to the Mac primary checkout, not this Hera worktree;
no cross-session project selection was changed, so this review used direct
source inspection. No new package builder or tests were added because the
existing evidence rejects the requested route before a builder can be safely
parameterized.

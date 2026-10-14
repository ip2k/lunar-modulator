# Expanded FM-1 package and transport decision — 2026-10-14

**Evidence correction:** `2026-10-14-expanded-ota-feasibility.md` supersedes
the universal stock-path exclusion below. FM-1_092's recorded stock-OTA
installation is a counterexample to attributing the open Dinghy loader's
`0x93000` write bound to the proprietary stock loader. Its acceptance of the
current larger Lunar candidate remains unproved. A strict 092-derived offline
package model is the next investigation; neither a raw image nor that model
is an admitted browser package.

Status: offline source review only. No package was emitted, no device command
was sent, and no install, migration, rollback, or release is admitted here.

## Decision

The current stock FWSC/OTA route has no supported way to install
`expanded-d9000`. The container's outer UFW records can describe variable-size
payloads, but the update path writes only the fixed app interval ending at
`0x93000`. A larger `flash.bin` does not enlarge that write interval. The
expanded raw profile changes app-area records through `0xD9000`, so merely
wrapping its bytes in FWSC would leave the upper records unwritten and cannot
produce the intended layout. Do not prototype that package as installable.

The viable engineering route is the already-audited, offline native recovery
writer built around the exact `FM-1_092` raw geometry, not stock OTA. The
existing `expanded_candidate.construct` creates a private complete raw image;
the next useful code task is a transport-facing package/receipt adapter for
that artifact, followed by a separate owner-reviewed recovery transaction.
This is not yet a web/browser transport: the existing `expanded_sg.py` is Linux
SCSI Generic and host-specific. A browser route needs a purpose-built audited
mask-ROM USB transport with the same exact identity, backup, allowlist,
transaction and readback checks. Do not reuse unreviewed generic USB commands.

## Evidence and limits

- `tools/jieli/inspect_stock_flash.py` accepts the guarded stock update
  `flash.bin` only at `0x93000` bytes. The current small-app OTA prototype
  (`tools/native/ota_candidate.py`) is correspondingly pinned to
  `model_app_replacement`'s 581,564-byte app extent. `tools/jieli/package_guard.py`
  also requires byte-identical stock `uboot.boot`, `isd_config.ini`, `ota.bin`
  and `cfg`.
- Primary upstream Dinghy source, commit
  [`d44df7db09b98ccad2f1233b8f83f5f09c04829e`](https://github.com/zvenson/dinghy/tree/d44df7db09b98ccad2f1233b8f83f5f09c04829e),
  independently documents the constrained path. Its
  [`ldr_core.c`](https://github.com/zvenson/dinghy/blob/d44df7db09b98ccad2f1233b8f83f5f09c04829e/firmware/loader/ldr_core.c)
  defines `LDR_APP_HI = 0x93000` and erases/programs only
  `[0x4000, 0x93000)`. Its
  [`fm1pkg_make.py`](https://github.com/zvenson/dinghy/blob/d44df7db09b98ccad2f1233b8f83f5f09c04829e/tools/fm1pkg_make.py)
  fixes `FLASH_SIZE = 0x93000`, `APP_SLOT = 0x8DFBC`, and rejects an app-area
  region extending past the flash payload. This is GPL-3.0-only source; this
  note uses the observed constraints only and copies no code.
- The current upstream [Felucca packer](https://github.com/hugelton/Felucca/blob/1727537624390cc3f9c7dff2456b43b3a8edb005/tools/fm1pkg_make.py)
  and [SLOOP packer](https://github.com/isod89/sloop-fm1/blob/d315ad88c5fbaad232ce9426b06db66395bd87db/tools/fm1pkg_make.py)
  likewise model a 0x93000 flash payload and 0x8DFBC app slot. Their builders
  supply their own SPL/config/OTA material, which conflicts with Lunar's pinned
  stock-component policy; they are not reusable package builders for this
  target. These sources are GPL-3.0-only; no source is copied.
- This establishes the limits of these maintained loader/packer paths and
  Lunar's observed stock profile. It does not prove every proprietary M-VAVE
  loader revision has identical internals. The exact stock OTA loader's
  runtime acceptance of larger `flash.bin` remains unverified. Since the
  known write interval ends at `0x93000`, that uncertainty cannot justify an
  expanded package.
- `tools/jieli/expanded_flash_profile.py` and
  `tools/native/expanded_candidate.py` are expressly raw-flash constructors,
  not FWSC composers. The former targets recorded `FM-1_092` geometry ending
  at `0xD9000`, preserves bytes outside the app area and preserves opaque
  VM/BTIF/USR banks; its receipts leave OTA, migration, hardware admission and
  installability false. `tools/native/expanded_sg.py` is an offline-reviewed
  Linux SCSI Generic path, not a browser/API adapter.
- The requested payload size needs exact rebinding: the new task specifies
  862,272 bytes, while the retained all-13/Event Horizon receipt cited in
  `notes/2026-10-14-ota-package-correspondence-review.md` records 862,320.
  Treat neither number as interchangeable. The package adapter must consume
  the current exact artifact and receipt hashes, verify app/ELF/selection
  correspondence, and reject stale or mismatched sizes.

## Scope for the next implementation

1. Keep the target profile explicit to the recorded `FM-1_092`; require two
   fresh matching backups, provenance/profile checks, exact app/ELF/link and
   selection receipts, and the independently verified expanded raw candidate.
2. Build only a private transport manifest/receipt from the verified candidate
   and allowed sector map. Do not wrap it as FWSC or mark it installable.
3. Before any transport implementation is admitted, prove a complete recovery
   transaction: identity, fresh pair of backups, exact command allowlist,
   protected ranges, write order with directory sector last, interrupted-write
   recovery, full readback, and tested restore. Separately characterize and
   verify settings migration/rollback; the expanded profile currently
   preserves bank bytes but does not establish settings semantics.
4. For browser support, implement a dedicated audited mask-ROM USB transport
   and fake-transport tests without auto-connecting or sending commands. The
   current Linux SG backend cannot be represented as a browser capability.
   Physical admission remains with the Mac coordinator under the staged
   hardware policy.

## Research coverage

Inspected the guarded stock package parser/geometry, current expanded raw
constructor and writer boundaries, and current primary-source packers/loaders
for Dinghy, Felucca and SLOOP. Rarefaction remained rooted at the primary
checkout rather than this worktree, so it was not used; Serena was active on
the exact worktree. This is source and offline-format evidence only, not a
stock-loader execution test or physical acceptance.

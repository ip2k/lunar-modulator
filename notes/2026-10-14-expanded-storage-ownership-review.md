# Expanded-layout storage ownership review — 2026-10-14

## Finding

[verified] Two 102,400-byte project slots require 204,800 bytes (50 × 4 KiB
sectors). They do not fit in the 144 KiB aggregate candidate ledger described
in `notes/2026-10-14-native-size-savings.md`; that ledger is 147,456 bytes and
is already 57,344 bytes (56 KiB) below the two-slot requirement. More
importantly, this ledger is not a set of
admitted project-storage extents: most of it is occupied by named firmware
banks or preserved as opaque bytes, and the current store accepts two
contiguous slots rather than a scatter map.

[verified] The latest retained all13 SAVE link is 863,380 bytes, ELF SHA-256
`ed067d2233d8b2b7994a3d8a0740a5a9b3ddfa6ec5acf06b990e0b49365cb9ab`.
Applying the existing expanded-profile extent formula to this link gives:

| Candidate content | Raw byte extent | Evidence/status |
| --- | --- | --- |
| App | `[0x04120, 0xD6DB4)` | 863,380 bytes from retained link receipt; this is the link image, not a new raw package. |
| `cfg_tool.bin` | `[0xD6DB4, 0xD6F33)` | 383 bytes copied from recorded baseline by the geometry helper. |
| Alignment byte | `[0xD6F33, 0xD6F34)` | One erased byte. |
| `cfg` | `[0xD6F34, 0xD7AAD)` | 2,937 bytes copied from recorded baseline by the geometry helper. |
| Aligned records end | `0xD7AB0` | Three erased alignment bytes after `cfg`. |
| Erased expanded-area tail | `[0xD7AB0, 0xD9000)` | 5,456 bytes total; only the full sector `[0xD8000, 0xD9000)` is an untouched 4 KiB sector. The preceding sector contains `cfg`. |

The helper’s full app budget is 868,836 bytes after reserving 384 bytes for
aligned `cfg_tool.bin` and 2,940 bytes for aligned `cfg`; the retained link is
5,456 bytes under that bound. `raw_flash_profile.py` and
`expanded_flash_profile.py` establish the arithmetic and candidate geometry.
There is no current raw-package receipt for the 863,380-byte link, so these
current offsets are derived from the audited helper formula, not evidence of a
new emitted image or write admission.

## What the flash map establishes

[verified] The strict recorded FM-1_092 parser names these reservations:

| Region | Extent | What is established |
| --- | --- | --- |
| App/PRCT area | `[0x04000, 0xD9000)` | Expanded candidate area; contains the app, moved `cfg_tool.bin`, `cfg`, descriptors and erased padding. PRCT is a descriptor, not write permission. |
| VM | `[0xD9000, 0xE9000)` | Named 64 KiB bank; exact bytes are preserved in expanded geometry. Content semantics and safe reuse are not established. |
| BTIF | `[0xE9000, 0xEA000)` | Named 4 KiB bank; exact bytes are preserved. |
| USR | `[0xEA000, 0xFC000)` | Named 72 KiB bank; exact bytes are preserved. Content semantics and safe reuse are not established. |
| Globals gap | `[0xFC000, 0xFF000)` | 12 KiB unnamed/opaque in the profile; a historical pair was erased, but erased bytes do not prove ownership. |
| key_mac | `[0xFF000, 0x100000)` | Named 4 KiB key bank; protected. |

`tools/native/storage_window.py` accepts a proposed two-sector settings journal
at either `[0xFC000, 0xFE000)` or `[0xFD000, 0xFF000)`. Those are alternative
windows, not permission for project storage. Its verifier explicitly returns
`ownership_verified: false`, `backup_provenance_verified: false`,
`semantic_migration_verified: false`, and `hardware_admitted: false`. The
historical backup/archive and candidate prove that the tested bytes were
retained and the selected window was erased at that snapshot; they do not
establish fresh current-device ownership. The 8 KiB settings journal is also
not project capacity.

For 092-derived expanded geometry, the candidate builder preserves every raw
byte from `0xD9000` to 1 MiB. Therefore the VM, BTIF, USR, gap and key ranges
cannot be counted as free while retaining that preservation rule. The one
whole erased app-tail sector is a geometric candidate only; no project extent
has been allocated or admitted there. Without moving or changing protected
content, two 100 KiB slots do not fit. Even counting the size-savings ledger’s
entire 144 KiB as hypothetical capacity would still leave the exact 56 KiB
shortfall by binary units; it would also ignore migration, ownership, headers,
alignment and noncontiguous layout costs.

V15 has a different VM reservation, `[0x93000, 0xE9000)` (344 KiB), while the
recorded 092 profile places VM at `[0xD9000, 0xE9000)` (64 KiB). Expanded
geometry supports only the recorded 092 baseline and preserves that VM bank.
Stock V15 data cannot be treated as reclaimed space until it is exported,
understood, migrated and recoverable. The retained 845,916-byte candidate
receipt (`build/native-current-candidate-20261013/receipts/candidate.json`)
also says settings migration, hardware admission and installability are false;
it is historical and is not the current 863,380-byte link.

## Bounded alternatives and next dependency

- **Smaller user-editable projects:** the densest accepted fixture measured so
  far is 32,924 bytes, but the measurement explicitly does not establish a
  maximum app-reachable project size. With the 32-byte store header, a
  sector-aligned slot for that fixture needs 9 sectors (36 KiB); two such slots
  would be 72 KiB. This is only a measured-fixture bound, not a safe product
  cap or currently allocated storage. A smaller supported maximum needs an
  explicit product decision, serializer/store enforcement and clear refusal
  behavior for larger projects, followed by a fresh capacity proof.
- **Preloaded content:** immutable demo projects can be packaged with the app
  and loaded read-only, subject to the app-size budget. That can provide
  examples without NOR writes, but does not provide user-editable persistent
  projects or a two-generation SAVE guarantee.
- **Migration/reallocation:** keep the current limits until complete stock
  VM/USR/gap data has a reviewed export and restore path, semantic migration is
  tested, and a new raw-layout profile names exact independently owned extents.
  The allocation must then either provide 204,800 contiguous bytes or update
  the store and recovery format for an explicitly tested scatter layout. Stock
  V15 relocation and rollback remain separate gates.

There is no proven smaller maximum or in-device project extent today. The
immediate dependency is an owner-reviewed storage ownership/migration plan;
after that, bind an exact allocation to the raw-layout verifier and only then
admit a NOR driver. This review performed no device, USB, flash or hardware
operation.

## Evidence and verification scope

- `tools/jieli/raw_flash_profile.py` SHA-256
  `43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f`;
  `tools/jieli/expanded_flash_profile.py`
  `07ab3acd14e14bf5f2a7e60f26ee5a7b82ca6e2e9e17aa9a5d70fc41c2685987`;
  `tools/jieli/package_guard.py`
  `78643b8a13114293afc1b3b0880e56858371669cf42a4cadbb31a7bb7557dc51`.
- `notes/2026-10-14-save-scheduler-verification/link-receipt.json` SHA-256
  `7d8775421160143d278abbb47dfb4c099220ac866d69f7f65d131c3af1919db1`;
  `sections.txt` SHA-256
  `e851a2efc9bc8a04cf59263a7afc97963beb85f2b051fc91344ce7992da0000d`.
  The corresponding private ELF is retained at Hera
  `/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/save-scheduler-link-v1/save-retained.elf`.
- `notes/2026-10-13-storage-window-verification/RESULTS.md` SHA-256
  `acd410000b2266e9f7bb4471ba07d933ccbd95a51116e6600e4699bf3f229e0e`;
  `notes/2026-10-13-storage-backup-verification/RESULTS.md`
  `d504ddaa702d4379b1bf8f4d94d59e4354f9769447ab94b7335344b217a04cb2`;
  `notes/2026-10-13-settings-journal-verification/RESULTS.md`
  `7218cf50bf9f686af7ebcd5d44fc027b66c17bc5b6faeb9492f5569826ccb9a8`.
- `firmware/native/project_store.h` SHA-256
  `237803b17d17c3c2311e89493b586c373c04ab0dc4788cb11ff3580d548a5045`;
  its contract caps payloads at 98,304 bytes, reserves a 32-byte header and
  accepts sector-aligned contiguous slot sizes. Existing host/Hera tests prove
  transaction behavior under their models, not physical allocation.
- Serena is active on the exact worktree and resolved `expanded_flash_profile.extents`;
  the source body matches the inspected helper. Rarefaction rejected the
  worktree as outside its configured workspace root. Direct source and retained
  receipts supplied this bounded review; no shared semantic-tool selection was
  changed.

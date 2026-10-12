# Private SDK diagnostic raw-image path

[verified: exact Hera snapshot] The new offline emitter derives an application-only
raw NOR target from matching FM-1_092 backups, recomputes SDK key/eFuse and native
ELF/image contracts, preserves stock SPL/configuration/partition data and the
unused application tail, and publishes private files with exclusive/fsynced
receipts. It does not open USB or grant a physical write permit.

The original SDK-free gate and original-loader backup provenance are unchanged.
Fixed-loader backups use a separate explicit profile with the candidate, profile,
profile source, framing reader and command inventory pinned; actual adapter and
campaign hashes remain receipt data to be independently pinned at the physical
experiment boundary. Neither an offline receipt nor its `passed` audit authorizes
an arbitrary worker or adapter revision.

## Frozen checks

[verified] Hera `/home/claude/mvave-fm1/sdk-raw-final-20261011` ran exactly 95
collected tests in 16 parallel containers (15 chunks of 6, one of 5): all passed,
no failures/errors/skips, no OOM kills, all containers removed. The run includes
actual private ELF mutation checks and the historical dual-backup/reference
fixture. This supersedes the initial 91-pass/one-optional-skip run.

- Base commit: `54037db3fbe9c411b9cbf60dd75ee78d7586e979` plus the exact overlay below.
- Archive SHA-256: `115a65ef7c2f61e5e8429d0342cacf867c97c1347501d698c9cdf89926ae6eed`.
- Plan SHA-256: `8d89515a274d86707956861de2a74ac3a4dfa57e35bb6140c5b0741141be7514`.
- Image ID: `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
- Actual private ELF: `8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2`.
- Historical baseline: `96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
- Evidence: ignored `build/sdk-raw-final-hera/{snapshot,plan,aggregate}.json` and per-chunk logs/XML/inspect files.

- `tools/jieli/raw_flash_profile.py`: `43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f`.
- `tools/jieli/build_raw_diagnostic.py`: `d1aafdaec887b5a041aefc19176fdcd7a25bdef1d5340996a9c86a3b000d9971`.
- `tools/jieli/raw_sdk_diagnostic.py`: `8c59b67da2c5b66d48dacadf4d90e48bd80272d1868fab21b2a3a80eb1496f07`.
- `tools/jieli/build_raw_sdk_diagnostic.py`: `3f4c9b82abacbfc78f22b23b2e6baeb1fea6ae7f8f75d541c88235f05fa47580`.
- `tests/test_raw_sdk_diagnostic.py`: `94ab1b848316da2c61772421409b97ee0b91729e3dc5cee7b62c9ef407134f7b`.
- `tools/jieli/audit_sdk_diagnostic.py`: `e8ce7a43e43ef127ecaf87db55578b7cad7bb1a926f2be3ce92b8688ae7dff8b`.
- `tests/test_sdk_diagnostic_build.py`: `001d1004296bf06d60bf92794008db9c04ac07ee68688fb549f6d068435c2e77`.

[verified: independent review] The initial review found a missing ELF machine
check. The corrected native audit requires ET_EXEC, EM_PI32V2 and the stock
entry. Original pi32v2 bytes pass; machine 0, ARM and RISC-V mutations fail.
The source-pinned independent review and bounded probe are saved in the adjacent
review note. Its native checks do not establish arbitrary application behavior.

## Acceptance limits and next work

Hardware boot, panel output, delayed recovery and interrupted-write physical
restoration remain unverified. Heavy tests are protocol/NOR models, not an AC791N
CPU emulator. A concrete physical policy must bind the independently reviewed
app/ELF, actual adapter, fresh same-port entry and fresh matching full backups,
then install and restore data sectors before the application-directory sector.

Rarefaction rejected this absolute worktree outside its configured root; Serena
ignored Python paths. Python investigation used file inspection without changing
another active session's shared project. pi32v2 native evidence comes from vendor
instructions and exact ELF bytes, not substitute clangd ABI assumptions.

## Concrete historical-baseline emission

[verified: private Hera construction] The exact reviewed SDK app/ELF produced
`target-historical-offline/target.bin` under the Hera evidence directory:
1,048,576 bytes, SHA-256
`df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`.
The complete private receipt SHA-256 is
`c1a8ee419d255ae74e361731fbaf90e0dfcb05b6de2770d9cc47f6595607846e`.
There are 30 changed 4 KiB sectors, `0x4000` through `0x21000` inclusive.
All protected bytes and unused application tail match the historical baseline.
This is a generated raw target; physical-writer readiness and hardware approval
remain false. It is not a stock MIDI-updater package, nor a live-backup permit.
Private target and receipt are mirrored in ignored `build/sdk-raw-final-hera/`;
no vendor or stock-derived binary is committed or published.

## Fresh-baseline emission

[verified: private Hera construction] The fresh physical fixed-loader dumps
produced the same complete target hash `df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`
in Hera `/home/claude/mvave-fm1/sdk-raw-fresh-20261011/target-fresh-offline/`.
The private 10,542-byte construction receipt is
`71af81e827b96fbc385bf2efe4459b1ad12e151648657073645f74cca5c3456d`.
The target and receipt were copied locally to ignored
`build/sdk-raw-fresh-hera/target-fresh-offline/` and their hashes rechecked.
This verifies reproducible construction against today's physical backup; it
does not establish installation, boot, display or physical recovery.

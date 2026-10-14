# Replacement demo sources in the native catalogue (2026-10-14)

## Result

The four replacement showcase candidates from `fb92cc0d4c312bbc77866c915d6fb8f159f5f92d` are now materialized byte-for-byte under `engines/state/examples/replacement-showcases/`. The original legacy example files remain at their original paths and are unchanged. The production image catalogue exposes both groups as selectable project sources, but retains an empty `default_profile.content`, `full_song_default.status: pending`, `default_candidate: false` for every project, and `installable: false`.

The replacement IDs, source provenance and exact content digests are pinned in `tools/native/export_image_catalogue.py`; export refuses a replacement file whose digest differs from the pinned source. Exported replacement records say category `replacement-showcase-candidate` and owner disposition `replacement showcase candidate; owner musical acceptance pending`. The registered BPM/bar/scene values come from the source commit's `sim/web/test/showcase-songs.json`; the shown duration is explicitly an estimate from bars × four beats × 60 / BPM. It is not a current playback receipt.

| Title | Materialized source | Bytes | SHA-256 | BPM / bars / scenes |
| --- | --- | ---: | --- | --- |
| Afterglow Relay | `engines/state/examples/replacement-showcases/afterglow-relay-showcase.lunar` | 22,903 | `53373bf4c508d360eccdf2751fd4242f23478d575adf893a703e6179dcd9c77f` | 104 / 44 / 4 |
| Event Horizon | `engines/state/examples/replacement-showcases/event-horizon-showcase.lunar` | 24,610 | `0d5d871bd31db1e628efbf291fd306671b81c93bef254a950291bf95f5413d1c` | 150 / 68 / 7 |
| Packet Bloom | `engines/state/examples/replacement-showcases/packet-bloom-showcase.lunar` | 18,937 | `eb55a36129ef3db02136b2ed0859fafcad94e3b2cbc3fa42761383d380249731` | 82 / 40 / 5 |
| Satellite Hearts | `engines/state/examples/replacement-showcases/satellite-hearts.lunar` | 31,610 | `090996484a125f5bde3fe4fb0a6dc3284cf7a260d6c6603298206921e78ed5d6` | 124 / 60 / 6 |

## Backend trust boundary

The catalogue exporter hashes source bytes and emits the repository-relative source path. The server staging registry still resolves a selected ID against its fixed registry, rejects a differing path, checks the catalogue hash against the actual file, and stages the verified bytes. Replacement staging tests exercise all four exact-source assets. The browser selection adapter exposes only the allowed user-facing fields and constructs the narrow module/project/startup request; it does not carry paths, hashes, dependencies, or dependency-validation claims. Replacement dependency metadata remains `pending-packed-backend-validation`, with no validated module IDs.

## Validation and limits

- `tests/test_native_image_catalogue.py`: all 30 parameterized real Make-catalogue request cases passed; the case-0 assertions cover all eight exported IDs, source paths and hashes, metadata values, pending dependency status and false default flags.
- `tests/test_native_stage_demo_profile.py`: all 13 tests passed, including exact staged-byte and SHA checks for each of the four replacements.
- `node --test sim/web/test/native-demo-selection.test.mjs`: all 6 tests passed, including replacement-candidate disposition and proving source/dependency metadata does not enter the request.
- `node --check sim/web/www/native-demo-selection-view.js` and `git diff --check`: passed.
- Rendered and inspected the updated chooser with all eight rows in a temporary local fixture, both initially and with legacy plus replacement selections and an explicit selected startup project. Screenshots: `/tmp/native-demo-selection-replacements-full.png` and `/tmp/native-demo-selection-replacements-active.png`. The temporary HTML and local server were removed/stopped.

These checks prove materialization, catalogue metadata, staging integrity and adapter shape. They do not prove fresh native codec output, exact embedded content, dependency/link fit, replacement musical semantics, full-song playback, save/reload, an installer/build-service route, or hardware acceptance. The inventory note `notes/2026-10-14-demo-preload-catalogue.md` marks the Packet Bloom and Satellite Hearts runtime receipt hashes stale after serialization repairs. Do not reuse those runtime-duration claims; no fresh replacement runtime receipt was generated here. Prior Packet Bloom/Satellite native receipts remain stale.

## Next dependency

Run fresh codec pack/decoder and dependency/link-fit checks for each replacement source in the bounded Hera workflow. Then perform the separate native full-song playback/save-reload and owner musical-acceptance reviews before choosing any default. The chooser remains a reusable disconnected component until an actual installer route and trusted catalogue/profile-loading call site exist.

Serena and Rarefaction were checked, but both still selected the primary checkout rather than this isolated worktree. They were not redirected because those selections are shared. Source, tests and the pinned source Git tree were verified directly.

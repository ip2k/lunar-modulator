# Native builder selection and payload model — 2026-10-14

## Scope

`sim/web/www/native-build-selection.js` is a pure browser-side validation
module for the future selectable native builder. It consumes the existing
catalogue export and prepared content manifest fields. It validates module
group membership, duplicate/unknown choices, the required sound engine, packed
asset bounds, and dependencies only where the project dependency scan is
marked complete. Set dependency coverage remains explicitly unresolved.
The module does not call the codec, compile, link, create an installable image,
or write to a device. It returns `installable: false` and leaves all firmware
size claims unmeasured unless a receipt carries an exact module selection, app
byte count, and app budget.

## Measured source limits and what they mean

- The canonical exported production catalogue contains 13 engines, 24 audio
  effects, 2 MIDI modules, and 16 modulation modules. The exporter marks the
  catalogue and default profile `installable: false`; catalogue counts are
  available choices, not a promise that any combination fits. Source:
  `notes/2026-10-13-image-catalogue-verification/catalogue.json` and
  `tools/native/export_image_catalogue.py`.
- The native content embedder permits at most 64 assets, each packed file from
  32 through 98,304 bytes, and 1,048,576 total packed bytes. The per-file value
  is the current `FM1_STATE_BIN_MAX`; the aggregate value is the entire FM-1
  flash capacity, explicitly not the application link budget or usable project
  storage. Sources: `tools/native/embed_image_content.py` and
  `tools/native/prepare_image_profile.py`.
- The retained SAVE-scheduler link receipt reports 863,380 app bytes and 5,456
  bytes of margin under its 868,836-byte expanded application budget. Its
  `link-receipt.json` has no exact module selection field, so the UI model must
  not associate this margin with a user selection or subtract uploaded project
  bytes from it. The receipt says `installable: false`,
  `physical_storage_admitted: false`, and `hardware_tested: false`.
- A separate all13 v3 link receipt records the full catalogue selection, with a
  separate content receipt of 2,784 embedded bytes. That older receipt does
  not provide an app byte count, so these facts cannot be combined with the
  retained SAVE-scheduler measurement to infer remaining capacity. Its content
  is measured for that build only; it does not predict additional content or
  another engine/effect selection.
- Two 98,304-byte maximum packed projects total 196,608 bytes (192 KiB). The
  candidate native storage ledger is 144 KiB, 48 KiB short of those two format-
  maximum projects; it is not a physically admitted storage layout. The
  separate 56 KiB gap in `notes/2026-10-14-native-size-savings.md` compares that
  ledger to two 100 KiB targets, not this format's 96 KiB per-project cap.

The UI should show three independent values: selected packed project bytes,
an exact-selection link receipt (or “not measured for this selection”), and
the separately admitted project-storage capacity (currently none). The input
format ceiling must never be presented as storage availability, and neither
selected content bytes nor metadata counts predict final linked firmware size.
The receipt model associates selected content with an embed receipt only when
the ordered asset count, kind, packed byte count, and packed SHA-256 match for
every asset and the receipt aggregate agrees. Matching aggregate bytes alone is
not content identity; missing per-asset hashes leave the selected-content flag
false. The existing application probe's compact `embedded_content` summary does
not carry kinds and byte counts per asset, so that receipt cannot establish this
identity until it includes the full embed asset descriptors.

## Validation

Focused Node tests are in `sim/web/test/native-build-selection.test.mjs`. They
cover catalogue group errors, missing engine, packed file and aggregate bounds,
complete versus incomplete dependency scans, exact-selection receipt matching,
missing hashes, same-size different content, and reordered assets. Receipt
fixtures in the unit tests are synthetic contract fixtures, not evidence for an
actual build. No build service, image, installer, or device operation is added
by this change.

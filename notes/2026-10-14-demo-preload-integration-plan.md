# Demo preloads and native image selection — integration plan (2026-10-14)

## Recommendation

Keep the existing JSON image profile and native builder backend as the source
of truth. Add demo projects to the generated image catalogue as source-backed
choices, let the web installer compose a profile with selected projects and
module IDs, then call the existing preparation/verification/build stages. A
project selection must never be treated as a linked image or a flashed device.
Do not add project-name-to-engine aliases: project JSON and the packed state
records use the same registry IDs. Display labels such as **FM6** can be
separate presentation metadata; the actual sound-engine ID is `dx7`.

The production default profile already selects every production module, but
currently contains `content: []`. A default full-song asset must be chosen and
released only after its exact packed payload, dependencies, fresh native link
and RAM profile, full-song playback, and native save/reload have passed. The
owner’s full-song requirement does not authorize calling the old Round-5 songs
accepted showcases: their status and the separate musical acceptance decision
remain as recorded in `notes/2026-10-11-showcase-diversity-matrix.md` and
`notes/2026-10-11-four-showcase-integration.md`.

## Existing path and canonical identities

- `tools/native/export_image_catalogue.py:18-47` runs the real Make catalogue
  resolver and emits the four builder groups plus an all-production-module
  default profile. The default currently has an empty content list. Test IDs
  are filtered out.
- `tools/native/module_selection.py:31-65` obtains module IDs, kinds, selected
  bits and object lists through `make ... print-modules`; this is the canonical
  resolver. `engines/modules/catalogue.mk:35-37,165-192` defines the sound,
  effect, MIDI and modulation IDs and kinds. The state engine lookup in
  `engines/state/state_names.c:88-103` compares packed unit IDs to registry
  engine IDs. `engines/src/registry.cc:129-130` confirms FM6 is registered as
  ID `dx7`. Thus project `sounds[].engine = "dx7"` resolves directly to the
  `dx7` catalogue choice; “FM6” is a user-facing name, not a second ID.
- `tools/native/prepare_image_profile.py:54-123` accepts profile-relative
  content paths, snapshots source bytes, packs JSON projects with the supplied
  `fm1-state`, reads the packed record stream, checks required unit/module IDs
  against selected modules, and records ordered source/packed SHA-256 values,
  kind and byte size. A set’s dependency coverage is explicitly incomplete.
  Projects set `dependency_scan_complete` true, but this only means the packed
  records were scanned; it is not playback acceptance.
- `tools/native/verify_image_profile.py:35-76` later checks the retained
  manifest digest and each regular non-symlink source/payload file’s hashes,
  sizes, kinds, module header and selected dependencies. The controller must
  retain the expected manifest SHA across the worker handoff.
- `tools/native/embed_image_content.py:20-64` generates read-only XIP C data
  and an ordered embedded-content receipt. `tools/native/build_application_probe.py`
  consumes the checked profile, derives `--modules` from its canonical
  selection, and can opt into the project loader and a startup project index.
  It is explicitly a timed private probe, not an installer or accepted release.
  Startup project loading is compiled only when `--link-project-loader` and
  `--startup-project-index` are passed; `firmware/native/app_probe.c:195-213`
  attempts startup restore and enters UBOOT on failure. This is a diagnostic
  code path, not proof of normal product startup or full-song operation.
- `sim/web/www/native-build-selection.js:1-178` is a pure request/receipt
  validator. It checks group membership, content count and packed byte bounds,
  requires exact per-asset kind/size/SHA agreement in the link receipt, and
  reports `installable: false` and firmware size unmeasured until an exact link
  receipt. Its tests are `sim/web/test/native-build-selection.test.mjs`.
  There is no installer/build-selection UI in `sim/web/www/index.html` or
  `app.js`; those currently launch the virtual FM-1. The helper is not a user
  interface or a build service.

## Smallest implementation sequence

1. **Materialize and freeze selected source projects.** Store each chosen
   project at a stable repository path (the current native example convention
   is `engines/state/examples/*.lunar`; the browser mirror convention is
   `sim/web/www/examples/*.lunar`). Record source commit/path/SHA, title,
   category, duration evidence and owner disposition in a generated or checked
   catalogue. Do not fetch sibling worktrees at build time. If native and web
   copies are both used, assert byte identity in tests.
2. **Expose the catalogue and profile in the installer.** Extend
   `export_image_catalogue.py` to return project entries and a default
   `content` selection, but retain exact source paths and stable IDs. Provide a
   full-production default module set plus at least one approved full-song
   project. The selectable profile builder should support choosing zero or
   more project/set entries and module groups; it should not infer that all
   module dependencies have been covered until `prepare_image_profile.py`
   validates the packed records.
3. **Keep the backend gates authoritative.** On submit, write a profile JSON
   and place chosen assets beneath its profile directory, run
   `prepare_image_profile.py`, and pass only the resulting immutable prepared
   manifest digest and files to the worker. Return exact source and packed
   hashes, required canonical module IDs, per-asset byte counts and aggregate
   content bytes to the UI. Use the existing JS validator for request shape and
   receipt binding; do not let browser-side metadata replace backend packing.
4. **Separate choices from image/product claims.** The selected list is a
   build request; “embedded” requires an exact `embedded_content` receipt;
   “linked” requires a fresh link for the exact modules and content; “default”
   requires reviewed profile selection; “installable” and “flashed” require
   their separate release/install gates. Keep those states distinct in UI and
   serialized receipts.
5. **Prove a full-project default on native.** Link the chosen profile with
   project startup/restore in the actual product startup path, verify content
   hash and startup result, play the complete arrangement, and save/reload it.
   The current `build_application_probe.py` startup option can help measure a
   candidate but cannot stand in for the product startup integration or the
   required physical-device verification.

## Catalogue and fit observations

The candidate inventory is in `notes/2026-10-14-demo-preload-catalogue.md`,
with machine output from `tools/native/demo_preload_catalogue.py`. It currently
describes four legacy Round-5 source assets and four replacement showcase
candidates. The exact original files have been materialized in the current
checkout; replacements are referenced through their pinned source commits.
All eight remain `default_candidate: false`. The Round-5 originals have exact
189–208 second receipts but were rejected as showcases; replacements have
owner musical acceptance pending, and Packet Bloom/Satellite Hearts have stale
runtime receipt asset hashes. Durations alone do not settle “full-length” or
musical approval.

The content prepare path sets a per-asset cap at 98,304 bytes and aggregate
packed-input cap at 1 MiB, while the app’s actual link budget is smaller and
must be measured on the selected profile. `sim/web/www/native-build-selection.js`
reports these as container/flash-input limits, not a fit prediction. The
native probe has separate project loader, startup restore, stack/RAM and
flash-layout choices; neither a successfully prepared bundle nor its content
byte total proves the profile links or fits runtime arenas. Preserve the exact
module and per-content receipt checks in `summarizeLinkReceipt`.

## Blocking dependency and next step

The blocking decision for a product default is an owner-approved full-song
candidate (or a new accepted composition) and exact native acceptance. The
original Afterglow Relay is a plausible duration candidate based on an exact
198.260870-second receipt, but it remains categorized as a legacy example and
must not be silently promoted. The replacement set is not owner-approved yet.

For implementation, the next concrete dependency is to materialize the chosen
source project(s) into this branch and pin their bytes, then extend the exporter
so a full-song default asset path is explicit. Before claiming complete
dependency coverage, run the checked state packer and validate its unit/module
records resolve through the canonical registry; then produce a fresh exact
profile/link receipt. Only after that should the parent add the visible
installer choices and bind the request to a real build worker. No current UI
choice, generated catalogue, native probe, or simulator launch is an image
install or physical-device acceptance.

## Inspection limits

This was a bounded source inspection only. No source or production catalogue
was changed, no image was built, and no hardware command was used. Rarefaction
and Serena shared project selection was not redirected; the installed worktree
was inspected directly to avoid altering the active primary-checkout context.

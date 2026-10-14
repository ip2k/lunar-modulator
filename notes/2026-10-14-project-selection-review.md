# Project and set selection review (2026-10-14)

## Scope and result

Reviewed the selectable preload path at exact base `847f43378996824624e2d6d612a08e26a6e194ca`, on Hera branch `codex/2026-10-14-project-selection-review`. No source changes were justified: the path already carries an ordered set of one to eight trusted project IDs and an explicit startup index, and validates project dependencies against the selected module profile before preparation. This is a private offline diagnostic path; it is not an installer admission or a device test.

This selection means “which trusted projects are built into the image, and which one starts first.” It does not currently provide an in-device project browser. In the diagnostic target `firmware/native/app_probe.c`, the build-selected index is used to start a single project (lines 203-219); adding runtime navigation is a separate firmware/UI feature.

## Code path checked

- `sim/web/www/native-demo-selection-view.js`: catalogue rows, reversible proposed Event Horizon Showcase preselection, checkboxes for multiple projects, startup radios, and explicit submit. Rejected showcase candidates are disabled in the control and guarded again in the event/request layer.
- `sim/web/www/native-demo-selection.js`: validates catalogue/dependency metadata, rejects duplicate/unknown project IDs and rejected candidates, checks every selected project’s required modules against the current profile, and emits ordered `project_ids` plus `startup_index` (lines 93-136).
- `tools/native/stage_demo_profile.py`: validates unique IDs, trusted registry source paths/hashes, and startup-index bounds; copies the requested projects in order and retains selected IDs/index/startup ID in the staged selection receipt (lines 90-153).
- `tools/native/prepare_demo_selection.py`: passes staged project content through the existing packer and verifies source/content correspondence before producing a receipt; receipt flags remain non-installable/unverified.
- `tools/native/build_demo_image.py`: passes the startup index to the app builder, checks project/build receipt correspondence, and writes a private diagnostic image receipt (lines 185-198).
- `tools/installer_service/api.py`: rejects duplicate/invalid requests and independently binds the worker receipt’s ordered IDs, startup index, startup ID, content list, and unadmitted flags.
- `firmware/native/app_probe.c`: invokes the selected startup project on boot; it does not expose a post-boot project chooser.

## Candidate availability caveat

The chooser labels legacy Event Horizon and Neon Transit as having refused the historical host startup diagnostic (report 5). That test uses a 192,000-byte app pool and a different profile; the current compressed showcase test exercises only Event Horizon Showcase at 165,376 bytes with the current 12-voice Shapes profile. Those historical failures are not sufficient evidence to blacklist those legacy projects under the current profile. The chooser marks their current-profile allocation reservation as pending, rather than claiming they pass. A focused cold-start matrix for all four legacy examples under the exact current tables, voices, and arena is the evidence needed before changing availability.

The project chooser tests already cover multi-project ordering, explicit startup choice, removal of the proposed default, dependency omissions, and rejection of known over-budget replacement candidates: `sim/web/test/native-demo-selection.test.mjs`, `sim/web/test/native-demo-selection-view.test.mjs`, `sim/web/test/installer-page.test.mjs`, `tests/test_native_demo_selection.py`, `tests/test_native_demo_image_controller.py`, and `tests/test_installer_service.py`.

## Checks and limits

- Inspected current source and test assertions at the exact seeded base; no files other than this note were changed.
- Hera has no Node executable, so the JS tests could not be executed in this worker.
- `tests/test_native_demo_selection.py` with the available Hera project venv initially lacked `FM1_STATE_TOOL`. Pointing it at the existing `ci-contract-repairs-20261012` binary ran but failed because that stale state tool lacks the current `comet` engine; this is a tool/profile mismatch, not a selection-path failure. No test result is claimed.
- No build, API service, browser, device, MIDI, USB, flash, or deployment operation was run.
- Serena remains selected to the Mac authoritative worktree. I did not change the shared semantic-server project selection to this Hera checkout. Rarefaction could not be used against the Hera checkout from this worker; source inspection was direct.

## Next useful step

Run the current cold-start harness across the legacy examples using the exact production all-55 module profile, compressed Plaits/Braids tables, current Shapes voice count, and 165,376-byte arena. Update the catalogue reservation and UI only for results from that exact profile. Separately, if the product requirement includes changing projects after boot, implement a runtime project picker; do not conflate that with the existing prebuild selection.

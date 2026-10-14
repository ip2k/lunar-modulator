# Installer browser review

The installer page now composes the shared native module selector and demo-project chooser. The module controls use the build-generated catalogue, validate each change, and feed the exact engine/effect/MIDI/modulation selection into the request. The project list remains generated from `tools/native/export_image_catalogue.py`; Pages already exports that JSON as `_site/demo-image-catalogue.json`.

This integration keeps a useful boundary clear: browser-side validation can check catalogue IDs and request shape, while packed dependency checks, image size, full-song musical approval, device playback/save-reload and installation remain backend/owner/device acceptance gates. The page continues to say its build service is disconnected, offers an offline JSON export only, and exposes `full_song_default.status` as pending.

## Why the browser pass was added

Before this pass, DOM-level tests covered the chooser contract but could not catch missing static imports, font loading, narrow-screen layout, clipping, or whether the browser downloaded the actual ordered request. The browser pass runs against the real static files and the exported catalogue in an isolated container. It exercises one effect removal, attempts to remove the last engine and confirms rollback/status, verifies unique control IDs across two module-view instances, selects Packet Bloom followed by Event Horizon as startup, and checks the downloaded arrays against the live controls. After recording the negative-action checks, it restores defaults before capturing the screenshots.

## Reproduction and evidence

- Hera host: `claude@192.168.1.48`; container image: `mcr.microsoft.com/playwright:v1.63.0-noble`, immutable image ID `sha256:eff16c30e6f3f4af0a3fa4b706120d5e9b0891c344a27d64559aff5900a4a27`.
- Container ran with 2 CPUs, 3 GiB memory and equal swap cap, `--network=none`, `docker-batch.slice`, task labels, read-only root, a bounded `/tmp`, and read-only mounts for static inputs and the existing Playwright 1.63.0 package. A loopback HTTP server ran inside the container.
- Browser: Chromium 153.0.8010.12. Desktop viewport 1440×1000; mobile viewport 375×812. Both loaded local fonts, had zero horizontal overflow, and emitted no page/console/request errors.
- Download selected `legacy-example-packet-bloom`, then `replacement-showcase-candidate-event-horizon`, with `startup_index: 1`; it contained the current module selections and omitted the deselected `plate` effect. The UI reported “Request exported. No build or install was performed.”
- Both images were inspected at full resolution. Text and controls had no overlapping labels or clipping; the mobile page is intentionally long because it exposes every catalogue module and project.

Files saved here:

- `installer-desktop.png` — SHA-256 `632ec5711c98a8d17b6e73f96b700a4679453dcadba019945354492246982984`
- `installer-mobile.png` — SHA-256 `b43f555adb7434595d25fbbd8f80f939592757a388f4e8ea2d813a822589ff57`
- `installer-request.json` — SHA-256 `33d2eb63a1dcfb1d6839e223e0b46bc01d6504111a23e04f51590ef80e8e06a7`
- `installer-browser-report.json` — SHA-256 `4e2ad06aecd40e719a27dbdeb98f51552271cb5a03f9fa7471bfcd271a5e60b4`; includes the full static-input hash manifest and browser assertions.

Run the helper with `node sim/web/test/installer-browser-review.mjs <static-site-dir> <artifact-dir> <image-digest>` in the pinned container, mounting the repo's `sim/web/www` assets plus generated catalogue and the existing Playwright package. This is a UI/request test only; it does not run the image builder, validate packed project dependencies, install firmware or establish musical/device acceptance. All catalogue projects remain `default_candidate: false`, and the generated full-song default remains pending.

# Installer profile bridge handoff — 2026-10-16

## Outcome

The installer request path now carries an explicit optional native build configuration from `mountInstallerPage` through `mountNativeDemoSelectionView` into `buildNativeDemoSelectionRequest`. The browser API client accepts the fixed `expanded-d7000` + `song-diagnostic` pair only, checks that Macro and Shapes are selected, and rejects partial/incompatible profile fields before fetch. With the option omitted, request fields and canonical legacy D9000 shape remain unchanged. No public UI control, default profile, deployment marker, diagnostic status, or installability claim changed.

## Files

- `sim/web/www/installer-page.js`
- `sim/web/www/native-demo-selection-view.js`
- `sim/web/www/native-demo-selection.js`
- `sim/web/www/installer-build-client.js`
- Focused tests in the corresponding `sim/web/test/` files.

## Branch and backup

- Base: `d168869b5aa77385ccbecaaf32dbaa2379d65887`
- Branch: `codex/installer-profile-bridge-20261016`
- Code commit: `20d44c459a7f9a468257d7925db09c3f8782e271`
- `origin/codex/installer-profile-bridge-20261016` was read back and matched that SHA after push.

## Checks and limits

`node --test sim/web/test/native-demo-selection.test.mjs sim/web/test/installer-build-client.test.mjs sim/web/test/installer-page.test.mjs` passed: 32 tests, 0 failures, 0 skips. `git diff --check` passed. The page-to-POST test uses a mocked API response and verifies exact request bytes; it does not claim a deployed service integration. No firmware build, browser preview, hardware operation, packaging, installability, playback, or release acceptance was tested.

## Next dependency

Parent review and integration through the required CI/review gates. Physical and release acceptance remain separate owner gates.

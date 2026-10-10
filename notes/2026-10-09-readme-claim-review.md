# README claim review — 2026-10-09

Checked `README.md` against the current browser app, `sim/web/README.md`,
`DEVELOPERS.md`, the 2026-10-07 Safari/audio note, the 2026-10-08 firmware
audit-remediation note, and the 2026-10-07 FM-1 bench note. This is a product-page
claim check, not a new hardware or listening session.

## Corrected from stale claims

- Browser support now distinguishes the Chromium/Firefox/WebKit Playwright
  runs from the native Safari dropdown and A/B UI checks. The Safari/A-B WAV
  listening judgment and physical touch/MIDI-hardware checks remain pending;
  see `notes/2026-10-07-editor-audio.md`.
- SAVE, Open/Save files, browser storage and the DX7 `.syx` importer are now
  described as existing browser features (`sim/web/www/index.html`,
  `sim/web/www/files.js`, `sim/web/README.md`). The simulator has MIDI input,
  not MIDI output (`sim/web/www/app.js`, `files.js`).
- The old roadmap claimed DX7 browser import and project/set saves were future
  work. Those claims were removed; current unbuilt firmware and hardware work
  remains distinct from the working simulator.
- Hardware wording now reflects the bounded sector write/restore and matching
  full-image comparisons, while retaining the limit that whole-image restore,
  broken-app recovery and a Lunar application on the chip are untested
  (`notes/2026-10-07-fm1-softkey-bench.md`,
  `notes/2026-10-08-audit-remediation.md`). The recovery wording follows the
  corresponding PR #102 update so it can be integrated without reverting the
  verified bench result.

## Checked and retained

- The current browser catalogue has thirteen production sound engines plus
  Test Sine; its modulation catalogue has sixteen kinds (`sim/web/www/meta.json`).
- MIDI input is note/velocity, pitch bend, CC 7 and CC 123; there is no MIDI
  output path in the page (`sim/web/www/app.js`, `files.js`).
- The simulator page is self-contained and does not upload project files
  (`sim/web/README.md`, `sim/web/www/index.html`).
- The project has not linked or run its Lunar application on the JieLi chip;
  the audit-remediation note records compile-only target profiles.

## Still deferred

- The owner has not provided the requested listening judgment for the captured
  WAV / live Safari A-B comparison. Measurements and UI observations do not
  substitute for listening.
- Physical touchscreen and external MIDI-hardware checks remain unverified.
- A full-image rewrite, recovery from a nonbooting application and Lunar
  application execution on the FM-1 remain unverified.

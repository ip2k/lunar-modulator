# Web flasher: install and roll-back panel on installer.html (2026-11-08)

Lane `web-flasher`, wave 1 of the FM-1 release plan (docs/18, milestone M12w part 1).
Base: `feature/2026-11-01@milestone-integration` (PR #161's branch). No device traffic:
the FM-1 and the dev kit were not touched; every MIDI port in the tests is a fake.

## What was built

- `sim/web/www/installer-ota-flow.js` (GPL-3.0-only, because it links the GPL controller):
  the panel. Choose a package in the existing inspection panel, its bytes go (opt-in
  `onPackage` callback) to the flow, which runs the verifier and shows the admission
  result. Install/Roll back stays disabled until the verifier admits the package and
  the mode fits (install: not the stock V15; roll back: the user's own FM-1_015
  package plus the identity the unit runs now). The click re-runs admission, then
  asks for Web MIDI with SysEx, then walks 14 stages, each shown as pending, active,
  done, failed or skipped: admission, MIDI access, running pair, running identity,
  7F + 2 s pause, E0000000 verify, re-enumeration into the loader, loader pair,
  `ota-FM-1_nnn` identity, 7F + pause, F0000000 write, re-enumeration, application
  pair, fresh identity. Served-request counts show on the two transfer stages.
- Port pairs are an explicit user choice per phase. A pair is offered only when exactly
  one connected input and one connected output share a name (two same-named devices are
  reported as ambiguous and cannot be selected: the first version cross-paired them,
  found by the resume test). Virtual, audio-interface and network ports (IAC, Midi
  Through, Komplete Audio 6, Bluetooth, ...) are always hidden; names that do not look
  like an FM-1 appear only behind "Show other MIDI devices". The handshake identity
  check remains the real guard: names are not device-mode evidence.
- Failure guidance maps the controller's messages (admission, SysEx permission, pair
  unavailable, no re-enumeration, interrupted or lost transfer, wrong identity,
  cancel) to next steps, pointing at docs/17 for recovery.
- `native-ota-controller.js` gained, backwards compatibly: `onStage(name, detail)`
  (observer errors cannot affect the transfer), `runningProduct` (default FM-1_015;
  roll back passes the identity the unit runs now, the loader must be
  `ota-<runningProduct>`), and `startPhase: 'loader'` (resume with a unit already in
  its OTA loader). The "target equals running" guard now fires before MIDI access.
- Licence note on the page (installer.html): GPL-3.0-only, the fm1-ota module, the
  Felucca upstream link, UPSTREAM.md, the four GPL files, `licences/GPL-3.0.txt`, source.
- The admission gate is untouched: `verifyNativePackage` still rejects everything, so
  in a published build the button never enables and no MIDI permission is requested.
  A V15 package is refused the same way (no special case).

## Tests

- `sim/web/test/installer-ota-flow.test.mjs` (20): unadmitted refusal with the real
  verifier (no `requestMIDIAccess` call), no Web MIDI, full install, roll back, mode
  mismatch, wrong running identity, wrong loader identity, stalled verify transfer,
  stalled write transfer, port lost mid-transfer, finish without re-enumeration,
  wrong post-write identity, cancel at port selection, unrelated devices hidden,
  ambiguous same-name devices, pair lost before confirmation, resume from loader,
  package cleared, guidance mapping, page hand-off with a missing catalogue.
- `native-ota-controller.test.mjs` +3: stage order, roll back identities, resume.
- Shared fakes: `test/fake-dom.mjs`, `test/fake-midi.mjs` (extracted from existing tests).
- `test/installer-ota-ui.mjs`: Chromium (Playwright 1.63, container on the LAN build
  host): licence links and files reachable, unadmitted refusal with zero MIDI requests,
  no horizontal scroll at 375 px, full flow against the scripted fake FM-1 in the real
  DOM, cancel. Added to the Chromium-only page-test step in ci.yml; the node tests are
  picked up by the existing `installer-*.test.mjs` and `native-ota-*.test.mjs` globs.

## Limits (not tested, not claimed)

- Nothing ran against a real FM-1, real WebMIDI or a real browser permission prompt;
  Firefox and Safari have no Web MIDI SysEx path and are untested here.
- The loader-after-roll-back identity (`ota-<running>`) and what a real unit does when
  resumed in its loader are [inferred] from the controller's existing design and from
  Felucca; the resume path and the guidance text are verified against fakes only.
- Real port names of the FM-1 and its OTA loader are unknown here; the "likely FM-1"
  name pattern is a guess, which is why unmatched names stay selectable.
- `adapter.resume()` (resume tokens) is still not exposed; resume here re-runs the
  loader phases from a fresh admission.
- Licence boundary: `installer-page.js` (MIT) now imports the GPL flow, so the served
  page is a combined work; the page says so. Decision for the owner: keep this under
  the GPL switch with the simulator, or gate the flow behind a separate page.

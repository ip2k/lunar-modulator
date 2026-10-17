# Browser-local FWSC package inspection

The installer chooser can export a build request, but it had no browser control
for invoking the existing FWSC structural inspector on a user-supplied package.
This change adds a bounded local file inspection panel. It accepts at most 2 MiB,
matching `native-fwsc-inspection.js`'s parser limit, reads only after the size
check, and reports package identity, available envelope CRCs, entry names/sizes,
and the known nested-profile result. It uses text nodes and keeps the bytes in
the page; no upload, API request, download, Web MIDI, or hardware operation is
added.

Every report explicitly says that release admission is not established and
installation is unavailable. The existing `inspectNativePackage` remains an
inspection API, while `verifyNativePackage` continues to reject. This UI does
not prove protected-stock correspondence, provenance, OTA behavior, flash
admission, or physical installation. Chrome visual review remains a coordinator
acceptance step.

Focused verification:
`node --test sim/web/test/installer-package-inspection.test.mjs sim/web/test/installer-page.test.mjs sim/web/test/native-package-admission.test.mjs sim/web/test/native-fwsc-inspection.test.mjs`
passed 18 tests, with the existing private-composer fixture test skipped because
that private artifact is not in this checkout. `git diff --check` passed. No
firmware build, service/API write, Hera work, or device interaction is required.

Coordinator Chrome preview: copy `sim/web/www/` into a temporary static-site
directory, generate `demo-image-catalogue.json` there with
`python tools/native/export_image_catalogue.py`, serve that directory with
`python -m http.server 8000 --directory <preview-directory>`, then open
`http://localhost:8000/installer.html` in Chrome. A tiny local `.fwsc` file can
exercise the malformed-file state. Review desktop/mobile spacing and verify the
report never suggests admission or installation before accepting the UI.

Coordinator follow-up [verified, 2026-10-16]: the panel was rendered in real
Chrome at its normal desktop viewport and 390×844. Added bounded panel padding,
44-pixel Clear button and wrapping report text. Screenshot is ignored local
`scratch/installer-preview-20261016/inspection-mobile.jpg`. The real file chooser
opened, but extension file selection was refused because Allow access to file
URLs is disabled. End-to-end browser parsing and long populated-report visual
acceptance remain pending; automated parser/report tests are separate evidence.
Focused root rerun: 11 passed, one optional private fixture skipped.

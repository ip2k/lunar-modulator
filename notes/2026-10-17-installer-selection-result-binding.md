# Installer selection and diagnostic flash-result binding

[verified: focused host behavior tests] Module, project, startup and companion
set edits now invalidate the displayed result. Each submission captures a
selection revision. Progress from an older revision is ignored; its success or
failure cannot replace current-selection feedback or display old flash bytes.
The chooser also receives the changed-selection error instead of reporting a
late obsolete request as submitted. A completed measurement is invalidated by
later edits, including edits back to the original configuration. A fresh build
is required rather than assuming that an old measurement applies.

The revision is a UI correspondence check, not a server authorization token or
artifact identity. Request serialization, backend validation and diagnostic-only
admission are unchanged. No installable image, device access or public service
is added. The module and project choices remain editable during a build.

Validation: `node --test sim/web/test/installer-page.test.mjs
sim/web/test/native-demo-selection-view.test.mjs
sim/web/test/native-demo-selection.test.mjs
sim/web/test/installer-build-client.test.mjs` passed 49 tests. New deferred-build
cases cover success and error after each of four edit kinds, suppressed stale
progress, and completed-measurement invalidation. These are DOM-model tests,
not live service or hardware acceptance. Real Chrome verified the preceding
companion-warning fix; the asynchronous result scenarios here have not yet
been repeated in Chrome.

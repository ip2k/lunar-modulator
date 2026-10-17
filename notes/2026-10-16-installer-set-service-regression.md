# Event Horizon companion SET service-flow regression

At source base `4b21faedd720e15d02b515efb5f2a5a8e6001bb3`, added a browser-page
regression proving that the default Event Horizon project/startup plus an
explicitly selected companion SET reaches the same-origin diagnostic builder
request through the real page-created client. The mocked diagnostic receipt
is validated and the page presents measured linked application bytes, budget,
and remaining bytes while retaining the no-installable-firmware statement.

The SET remains optional and the checked-in service marker remains disabled.
The test does not run the native API/worker or establish linking, packaging,
installation, or hardware behavior.

Validation: `node --test sim/web/test/installer-page.test.mjs` — 14 passed,
0 failed, 0 skipped; `git diff --check` passed.

Remaining product gap: a separately trusted packaging job must bind the exact
build tuple to operator-controlled stock reference inputs and independently
verify its candidate before any authenticated download or browser admission
path is considered. The diagnostic `app.bin` must not be presented as firmware.

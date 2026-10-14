# Native demo selection view (2026-10-14)

## Result

Added `sim/web/www/native-demo-selection-view.js`, a reusable browser-DOM chooser module on top of `native-demo-selection.js`. It has not been wired into a route, simulator page, build worker, or installer. The existing page is explicitly the virtual FM-1 (`sim/web/www/index.html:22-30`, `sim/web/www/app.js:1-9`); the integration plan says there is no installer/build-selection UI in `index.html` or `app.js` (`notes/2026-10-14-demo-preload-integration-plan.md:55-62`). This avoids adding a disconnected second product page.

The component provides keyboard-operable native checkbox and radio inputs with `fieldset`/`legend` grouping and explicit labels. Users can select one or more projects; click order is retained in `project_ids`; a separate radio choice explicitly selects the startup project. The submit control stays disabled until both requirements are met, and the handler repeats the checks before invoking the callback. Unchecking the startup project clears that choice. `destroy()` removes the component when its future route closes.

It displays each title, category, owner disposition and metadata-derived duration as text. Duration copy says it is an estimate, not verified playback. It shows the catalogue's full-song-default status and blockers; while pending, it explicitly says there is no approved default and that legacy examples are not approved showcases/defaults. Catalogue title strings are assigned with `textContent`; no `innerHTML` is used. The callback receives only the immutable object returned by `buildNativeDemoSelectionRequest`, which excludes paths, hashes and dependencies (`sim/web/www/native-demo-selection.js:51-75`). It does not fetch assets, resolve dependencies, estimate fit, call a service, build, install, or claim product admission.

## Integration boundary and next call site

A future installer route should load the generated catalogue and selected module profile, mount this module in its own route root, and connect the callback to the backend request path. The callback contract is the adapter's narrow v1 request; project bytes, paths, hashes and dependency resolution stay backend-owned. Backend preparation and exact link/embedded-content receipts remain required before describing output as prepared, linked, embedded, installable, or flashed. The integration plan documents those separate gates at `notes/2026-10-14-demo-preload-integration-plan.md:27-53,69-91`.

The four catalogue examples still have `legacy-example` disposition and are not approved defaults; the exported full-song default is pending (`notes/2026-10-14-demo-preload-export.md:1-20,39-48`). The component therefore has no selected/default project on first render.

## UI dependency decision

Used built-in HTML form controls and DOM APIs rather than adding a dialog/form framework. The existing web page identifies itself as dependency-free (`sim/web/www/app.js:1-5`); this view needs only checkbox/radio/fieldset/label/button semantics and a small callback adapter. Native controls retain browser keyboard behavior and accessibility semantics without a runtime package or license/maintenance/bundle burden. This does not settle future route styling or a framework decision for the whole installer.

## Verification

- `node --test sim/web/test/native-demo-selection-view.test.mjs sim/web/test/native-demo-selection.test.mjs sim/web/test/native-build-selection.test.mjs`: 14 passed after coordinator integration and the replacement-catalogue adapter check.
- `node --check sim/web/www/native-demo-selection-view.js`: passed.
- `git diff --check`: passed.
- Re-rendered the temporary eight-project fixture against the current chooser module with a cache-busted import and headless Chrome cache disabled (1000×2800). Fresh initial/active screenshots are `/tmp/native-demo-selection-category-fresh-initial-20261014.png` (04:21:07 host-local display) and `/tmp/native-demo-selection-category-fresh-active-20261014.png` (04:21:08); inspected both. Startup radio labels include category qualifiers, so duplicate titles are distinguishable; spacing is clear, nothing is clipped or overlapping, and selected candidates remain marked pending with no approved default. The temporary fixture and local HTTP server were removed. Chrome logged only its optional `/favicon.ico` 404.
- The Mac's interactive browser surface reports the host locked. The component was still rendered by the installed headless Chrome executable; no interactive keyboard/screen-reader test was performed.
- Serena/Rarefaction roots remain on the primary checkout; they were not redirected because those semantic selections are shared. Direct source and test inspection were used for this worktree.

## Next dependency and limits

The coordinator needs an actual installer route and catalogue/profile-loading owner to integrate the module, then should run browser keyboard/a11y checks in that surface with its real stylesheet and backend callback. There is no build service, public install admission, accepted full-song default, or device acceptance implied by this component or its tests. No hardware command was run.

## Coordinator integration review

The callback now supports asynchronous preparation: it awaits rejection, reports
the error in the live status region, and prevents repeat submissions while busy.
After failure users can retry their preserved selection. Category copy uses
friendly labels and distinguishes legacy examples from pending showcase
candidates. An additional test holds a pending callback, attempts a duplicate
submission and rejects it, proving one invocation and retry availability.
Startup labels include the category so duplicated legacy/replacement song titles
remain distinguishable at the point of selection.

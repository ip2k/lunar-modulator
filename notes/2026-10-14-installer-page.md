# Standalone installer project chooser

Implemented `sim/web/www/installer.html` as a static project-selection request
route. The page uses `mountNativeDemoSelectionView` and its existing request
validator rather than duplicating chooser state or maintaining a browser-side
catalogue copy. The Pages workflow exports
`_site/demo-image-catalogue.json` from `tools/native/export_image_catalogue.py`
after the engine build. That trusted generated catalogue supplies both
selectable project metadata and the production module profile.

Selecting projects preserves check order and an explicit startup index. The
download contains only the v1 module IDs, ordered project IDs and startup
index. Project paths, hashes and dependency claims stay out of the request. The
route says the build service is not connected, and exporting does not build or
install firmware. The shared chooser surfaces full-song default blockers;
legacy examples remain unapproved and all showcase candidates remain
unaccepted with `default_candidate: false`.

Checks: `node --test sim/web/test/installer-page.test.mjs
sim/web/test/native-demo-selection.test.mjs
sim/web/test/native-demo-selection-view.test.mjs` passed 11/11;
`python3 tools/native/export_image_catalogue.py` succeeded locally and reported
8 projects, production groups (13 engines, 24 effects, 2 MIDI effects, 16
modulation modules), pending full-song status and false candidate flags;
`git diff --check` passed.

Visual review remains outstanding. The Mac CUA browser reported a locked
workstation. Hera was checked under the LAN coordination process; it has no
Chromium/Chrome or `/pw` Playwright installation. Installing/running a new
container was not justified for this static-page screenshot. No browser render
or overlap inspection is claimed. Next visual check: use the project CI
Playwright runtime or an existing authorized browser, inspect desktop and
narrow widths, and fix any collisions found.

Files are on `feature/2026-10-11@installable-firmware`; root owns broader
integration. The branch HEAD observed during this update was
`c4945664a678395cd75ffbef953aeecedecd3693`; unrelated builder/controller
changes are not part of the installer commit.

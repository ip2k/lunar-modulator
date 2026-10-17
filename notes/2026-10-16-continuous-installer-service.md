# Private continuous installer service

Ready for coordinator review on `feature/2026-10-16@continuous-installer-service`,
based on `2788c82dc098f68f41919d4c00f10d4a81911bd2`. Coordinator owns integration,
CI and fresh target links. This worker owns installer API/worker/provenance/browser
and the approved narrow continuous-only native selection adapter changes.
No Hera, device, USB, MIDI, flash, power, or heavy container actions were used.

[verified] Implemented a distinct private continuous D7000 contract, FM-1_500
explicit identity with FM-1_000 recovery identity, no return timer, Shapes8 RAM
compressed tables and indexed TFT, selected namespace/pool validation, TRS enabled
with 256-byte ring/32-byte poll and USB preserved, linked/disarmed SAVE, and
separate continuous provenance/evidence. Exact profile digest is shared with the
browser and checked by a cross-language test. Imported worker contract/catalogue
modules must resolve under the exact extracted pinned source; stale preloaded
modules are refused. Production catalogue membership and kinds exclude tests.

[verified] Caller-selected engines/effects/MIDI/modulation, project ordering,
startup project and optional correctly parented SET remain available. Native
module and packed-content dependency checks still apply: a Trio-only module
selection requires compatible content, not Event Horizon's different dependencies.
Diagnostic defaults/canonical request encoding and the Hall stage7 contract remain.
The HTML service marker remains disabled. The explicit browser profile selector
preserves choices, clears old measured usage and performs no automatic submission.
No binary/download route or operator trust anchor was added. Continuous response
remains private link only, non-installable, untested/unadmitted on hardware, with
RAM/playback/full-song acceptance false and trusted FWSC compatibility false.

[verified] Both lower evidence and API-facing image receipts enforce exact
all-off diagnostic instrumentation/timers/optimizations and hot DSP RAM policy.
The shared native builder produces this continuous metadata; legacy diagnostic
receipt shapes remain unchanged. Size is checked from the actual artifact and
matching receipt, with an exact 860644-byte app budget.

[verified] Focused Python run: 317 passed, 1 skipped, 1 warning. Command:

```
FM1_STATE_TOOL=/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware/engines/build/fm1-state /Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware/.venv/bin/python -m pytest -o addopts='' -q tests/test_installer_continuous_profile.py tests/test_installer_service.py tests/test_installer_native_profile.py tests/test_native_demo_image_controller.py tests/test_native_demo_selection.py
```

Skip: retained real Hera build test requires LUNAR_RETAINED_BUILD. Warning:
pre-existing Starlette/httpx deprecation. Continuous adversarial coverage includes
request/kind/identity/profile/instrumentation/runtime/MIDI/SAVE/size/storage/
provenance tampering and preloaded wrong-source imports. Trio/no bank,
Macro/plaits, Shapes/braids, Macro+Shapes/two banks run the actual generator,
worker retain/read evidence and API round trip; all55 production selection is
also admitted in host fixtures. These use synthetic link/object artifacts and
do not constitute actual target compilation or measured target fit.

[verified] Focused browser module tests: 54 passed. Command:
`node --test sim/web/test/installer-build-client.test.mjs sim/web/test/installer-page.test.mjs sim/web/test/native-demo-selection.test.mjs sim/web/test/native-demo-selection-view.test.mjs`.
[verified] All 13 browser unit files: 107 passed, 1 skipped
(`node --test sim/web/test/*.test.mjs`).
Real Google Chrome rendered the current generated catalogue and continuous
selector on an isolated loopback origin; labels, spacing, selected profile and
production choices were inspected. Initial reused loopback origin had stale
cached JS; a fresh origin removed it. Generated catalogue is ignored/local only.

Semantic MCP limitation: Serena initial instructions/current config and Rarefaction
Python status identify /Users/likwid/Developer/mvave-fm1-firmware. Bounded
BuildRequest/find_symbol and worker/orient requests fail ENOENT because primary
checkout lacks these files. Did not retarget shared active servers; worktree
file inspection and meaningful tests provide current coverage.

Next dependency: coordinator reviews/integrates this source, then builds fresh
source-bound continuous all55/Event Horizon and compatible Trio-only, Macro-only,
Shapes-only, Macro+Shapes target subsets on Aeon. Every new subset needs actual
target sizeof(fm1_app_t), selected pool and app<=860644 checks. Existing
CONTINUOUS_TARGET_STORAGE is historical all55 target ABI evidence (220848
RGB565 / 163760 indexed / 57088 pool credit), reused rather than invented or
newly measured. A changed measured ABI must be reported and reconciled; host
success is not a target ABI measurement. No source closure/trace, package tuple,
CI, hardware playback, SAVE runtime, installability, recovery or publication
acceptance is claimed by this worker.

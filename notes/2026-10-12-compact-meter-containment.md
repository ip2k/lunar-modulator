# Compact resource-meter containment

[verified] At 667×375, Firefox and WebKit placed the RAM percentage beyond its control by 1.267 and 1.047 pixels respectively. The toolbar test retained both failures; the native/sync/fit checks used the combined editor source recorded in `scratch/combined-gate-20261012/manifest.json` in the integration worktree.

[verified] For 641–720-pixel landscape widths, resource-meter horizontal padding is now 4 pixels rather than 10. The 6-pixel label/bar/value gaps remain. Other widths retain their existing styles. This provides room for the meter text without reducing its font or hiding content.

[verified] `compact-toolbar-check.mjs` passes at 1440×900, 1024×768, 844×390, 667×375 and 390×844 in Chromium, Firefox and WebKit, on Hera in `lunar-playwright-audio:1.63.0`, Playwright 1.63.0, isolated container networking, 2 CPUs/2 GiB and the CI PulseAudio null sink. Chromium and Firefox passed first run. WebKit first timed out waiting for Pause→Resume before geometry checks; an independent full rerun passed. Both logs are retained. No tolerance or assertion changed.

[verified] Inspected 667-pixel Firefox and Chromium toolbar captures and the 390-pixel Chromium portrait capture: text fits controls and viewport. Browser artifacts and logs are in this worktree `scratch/meter-containment-20261012/` and Hera `/home/claude/mvave-fm1/meter-containment-20261012/`. This is browser validation, not physical-touch, listening or FM-1 acceptance. Semantic servers selected another active checkout, so their roots were not changed; this tiny CSS edit used direct file inspection.

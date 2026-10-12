# GitHub Actions browser failure: run 38201714094

Run: [38201714094](https://github.com/ip2k/lunar-modulator/actions/runs/38201714094)

The run tested commit `069333cddd3dde8fbe0b73797f97add8a0a28ae4` and Wasm
SHA-256 `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.
The WebKit browser job passed. Chromium and Firefox failed in editor page
tests:

- Chromium's native sequencer report passed 13 checks. Its sync suite passed
  the first three checks, then timed out waiting for the native velocity
  acknowledgement while preparing the stale-redo case. The captured field
  showed invalid `0072` after typing `72` over the previous value `100`.
- Firefox failed the native Automation-tab check: the Automation tab received
  focus, but Scenes remained selected. Its sync suite timed out waiting for a
  fixture note while setting up, with Clip focused and Scenes still selected.

The root cause diagnosis is a race between the settled project refresh and the
native content-generation refresh. The saved deterministic reproduction in
`refresh-race-repro-results.json` returned `reproduced: true`: an injected
refresh between pointer-down and pointer-up left Scenes selected, and another
between select-all and typing produced invalid `10072`. The saved
`source-hashes.json` binds that reproduction to the Wasm and relevant UI/test
files. This confirms the refresh-timing failure mechanism; it does not turn the
CI run into a pass. `midi_model` owns the production fix and deterministic
regression, after which the exact required CI must run again.

The browser result JSON and the two failing screenshots are retained here.
Full downloaded workflow artifacts, including unrelated editor captures and
audio diagnostics, remain under ignored `scratch/ci-failure-run38201714094/`.
Workflow console logs were unavailable when this diagnosis was recorded.

# Final native sequencer browser acceptance

Run date: 2026-10-11. The current managed-worktree browser tests were staged to Hera and run in isolated Playwright containers against the source snapshot listed below.

All six runs passed: mock-host and native-Wasm suites in Chromium, Firefox, and WebKit. The native assertion `native clip matrix launch advances real transport and playhead` passed in all three browsers without altering the assertion. Firefox therefore reproduced no playback stall on this snapshot. Each native report also confirms real AudioWorklet/Wasm loading, fader and meter state, MIDI import, project round-trip, and offline rendering of six WAV exports.

The mock suite covered desktop and phone-landscape mixer/scene/clip interactions, Files & export disclosure, Routing & FX disclosure defaults and focus, fader telemetry, device inspector focus restoration, and keyboard navigation. Its full check names and final native report are in [browser-results.json](browser-results.json). Screenshots and raw browser logs are under the ignored scratch folder listed below.

## Tested snapshot

- Managed checkout: `/Users/likwid/.codex/worktrees/midi-sequencer-workspace/mvave-fm1-firmware`
- Branch: `feature/2026-10-11@midi-sequencer-workspace`
- Checkout HEAD when results were collected: `6958d6415dfe99b4c2edeb54350085e4dbf515a7`
- Wasm SHA-256: `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`
- Wasm metadata SHA-256: `f7f6e5f825be5bf5da1950c91599ecbc4f3ea8ef30894ea24ed276c4a2b7999c`
- `sim/web/www/editor/sequencer.js`: `58ee6c7a039b4c00ceb128669dbe7273dc482c73f78eef1bd17d651b3672e2f7`
- `sim/web/www/editor/sequencer.css`: `eac603871cb16dfc295d1f8c911f98f21f636c79bbc52c7202aeda3fad566e84`
- `sim/web/www/editor/editor.js`: `71f0294c0c2ce121c4a828c2fe32eee91e8a5ac0dac96af0a69f4a383a2f624a`
- `sim/web/www/editor/editor.css`: `c4b58595b95cd6a55a0741b4c21caeac5d102ba179e1d0add3a5bfcdcf0b10f5`
- `sim/web/test/sequencer-ui.mjs`: `f013789436a1ef2105e64e760e637ce9c92e2b15c594b907bc5730338b45c4f2`
- `sim/web/test/sequencer-native.mjs`: `348890b70862f7a85e349585643691e61cb964a81a05944ce1ae20683ba57e38`

After the browser stage completed, the checkout's `fm1.wasm.json` was refreshed with pinned build-image digests and a current engine source hash. Its current hash is `8a209d7f3fe1340a94bf7435aed7e8454c655a3abcb332c348efed70268894fe`; it reports `engines=b6c6a546f91f071d0ef3494128e11a6d4a8ad6edf28e7fedc865df53cafa01e5` and `sim=626e98a7f06fb7fba0b6cf2b67602b4c909c793e6ceab86b90552db2e2ae8a15`. Parent confirmed the build-stage sync restored examples from `main` at `62149` and updated metadata only; no compilation occurred. Thus the tested Wasm remains the same hash and all tested frontend/test hashes still match. The post-run provenance metadata was not present in the browser stage and does not affect runtime behavior.

## Hera test environment

The tests ran on Hera inside `mcr.microsoft.com/playwright:v1.63.0-noble`, with 2 CPUs, 2 GiB memory, and `--network host`. The PulseAudio configuration matches CI: system daemon, `module-null-sink sink_name=lunar rate=48000 channels=2 norewinds=1`, and anonymous Unix protocol at `/tmp/pa.sock`; the test environment exported `PULSE_SERVER=unix:/tmp/pa.sock` and `PULSE_SOURCE=lunar.monitor`. PulseAudio reported the `lunar` sink and monitor source at 48 kHz stereo. Firefox's run log records the real transport/playhead assertion as PASS.

Raw logs, per-browser results, and selected desktop/landscape screenshots are at `scratch/final-native-acceptance/hera-out/`. Remote isolated stage: `/home/claude/mvave-fm1/final-native-acceptance-20261011`. No project source was edited for this acceptance run.

## Limits

This verifies browser runtime behavior in a headless Linux environment. It does not establish physical FM-1 behavior or listening/perceptual acceptance. Browser test success also does not replace CI's full build and integration gates.

## Follow-on evidence — 2026-10-12 UTC

The six passing Hera suites above remain preserved for their original
snapshot. A later GitHub Actions run,
[38201714094](https://github.com/ip2k/lunar-modulator/actions/runs/38201714094),
tested HEAD `069333cddd3dde8fbe0b73797f97add8a0a28ae4` and the same Wasm
SHA-256 `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.
WebKit passed; Chromium's sequencer-sync suite timed out awaiting native
velocity acknowledgement, and Firefox's native and sync suites failed during
Automation-tab and fixture-note setup. Per-suite JSON, workflow summaries and
screenshots are retained in [ci-failure-38201714094/](ci-failure-38201714094/);
the full downloaded artifacts remain in ignored
`scratch/ci-failure-run38201714094/`.

The diagnostic in `scratch/CI_FAILURE_HANDOFF.md` and the focused reproducer in
`scratch/ci-sync-review/` identify refresh timing as the common cause: an
asynchronous redraw can replace the numeric field between select-all and
typing, or redraw the tab between pointer-down and pointer-up. The failed CI
reports remain failed evidence. The production fix and deterministic regression
are owned by `midi_model`; exact-head CI has not yet passed after that change.

Separately, Codex performed a bounded native Safari check on the owner’s Mac, using
this HEAD and module; its unmodified receipt is [native-safari.json](native-safari.json).
The check recorded actual pointer/keyboard fader input and measured non-silent
meters in addition to Song, MIDI routing, Undo, transport and inspector focus
behavior. It does not establish a complete browser suite, owner by-ear
acceptance, physical-phone behavior or FM-1 hardware acceptance.

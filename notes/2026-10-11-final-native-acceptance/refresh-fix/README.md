# Sequencer refresh race: focused acceptance

2026-10-11. Baseline `069333cddd3dde8fbe0b73797f97add8a0a28ae4`, feature branch `feature/2026-10-11@midi-sequencer-workspace`.

**[verified]** CI run `38201714094` exposed a production refresh race. A redundant native project read replaced unchanged controls during pointer-down/up or after select-all in a number input. The controlled before reproduction left Scenes selected after an Automation click and changed velocity `100` to invalid `10072`. The preserved CI and reproduction evidence is in `../ci-failure-38201714094/`.

**[verified]** `sequencer.js` now keeps controls when a normal refresh reads the same project. Forced refresh still redraws after local edits. An invalidation revision retries an older in-flight read before clearing dirty state; reads themselves do not generate invalidations. This consumes finite panel-edit bursts without adding project polling. A project is parsed before publishing any document/model state; a failed parse retains dirty state and its original valid document/model.

**[verified]** The real-browser regression deliberately refreshes between pointer-down/up and between select-all/type, delays an old snapshot across a native note edit, and verifies malformed-read recovery without another generation event. Recovery then opens Mixer and requires the original instrument name, catching partial document publication. The original four synchronization/history checks remain intact; no additional sleeps or relaxed assertions were introduced.

## Exact focused results

Final source hashes are in `source-hashes.json`; the Hera copies matched the managed worktree. The unchanged module SHA-256 is `2a2ad121431f6e7fac5aa186d00eb0b75848187441ffe0d4ec4222451ed65cc3`.

| Check | Result | Receipt |
| --- | --- | --- |
| Chromium 153.0.8010.12 synchronization | 6/6, zero page errors | `chromium/sequencer-sync-chromium.json` |
| Firefox 155.0 synchronization | 6/6, zero page errors | `firefox/sequencer-sync-firefox.json` |
| WebKit 26.6 synchronization | 6/6, zero page errors | `webkit/sequencer-sync-webkit.json` |
| Firefox 155.0 native integration | 12 recorded checks, passed, zero page errors | `native-firefox/results.json` |
| Host Node regressions | 8/8 | `node --test sim/web/test/sequencer-host.test.mjs` |
| MIDI/model/actual-module Node checks | 30/30 | `node sim/web/test/midi-import.mjs` |
| Syntax and whitespace | passed | `node --check sim/web/test/sequencer-sync.mjs`; `git diff --check` |

The Firefox native receipt includes real transport, Automation editing, meters, imports, roundtrips and six offline WAV downloads (five stereo and one eight-channel, 24-bit, 44,118 Hz, 35,392 frames). Its final run completed after the independent review was recorded; `../refresh-fix-review.md` preserves that review's earlier timing unchanged. The console prints 11 PASS lines; the JSON records the additional measured-meter check, totaling 12.

Hera stage: `/home/claude/mvave-fm1/ci-sync-review-069333`. Playwright 1.63.0 in `mcr.microsoft.com/playwright:v1.63.0-noble` (`sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27`), Docker batch slice, 2 CPUs, 2 GiB RAM, 2 GiB combined memory/swap, host network. PulseAudio uses the CI 48 kHz stereo null sink with `norewinds=1` and anonymous Unix socket. `final-matrix.log` retains the run output. Run commands are `BROWSER=<chromium|firefox|webkit> node test/sequencer-sync.mjs www <out>` and `BROWSER=firefox node test/sequencer-native.mjs www <out>`; the latter was run once against the final atomic parse edit.

## Limits and next step

These are focused simulated runtime checks, not new-head CI, native Safari, by-ear or physical FM-1 acceptance. No module rebuild or device writes were performed. Full suite CI and release/merge remain root-owned. WAV artifacts stay in the isolated stage; only compact validation receipts are tracked.

This investigation used bounded source/caller inspection. Root's previously verified Rarefaction TS session selected the primary checkout; Serena's shared primary session lacked its TS backend. Neither shared session was retargeted or restarted, and no semantic-tool success on this managed checkout is claimed.

# Advanced editor: Safari and external audio checks — 2026-10-07

## Real Safari

[verified: native Safari UI on this Mac] Safari 26.6.2 on macOS 26.7,
serving the follow-up branch from `http://localhost:8778/`. Loaded First
orbit, powered on and selected Sound 4 (FM6). Its Patch filter initially
has 64 entries. Typing `bell` and opening the **native** dropdown shows
TUBE BELL, GLASS BELL and the retained current User 1, and nothing else.
Choosing TUBE BELL updates the selected value and creates the history entry
`S4 Patch User 1 → TUBE BELL`. Clearing the filter restores the 64-entry
native menu, with TUBE BELL still selected. This closes the real-Mac
check left in the design note's §30; it is not just Playwright WebKit.

[verified: native Safari UI] First orbit stays at 116 BPM, playing, while
switching project A/B and Sound 2 A/B. The comparison is audible material:
project B changes Sound 2's Timbre to 1; the sound comparison keeps that
as A and changes B to 0. The page shows Hearing A and Hearing B after each
switch and still shows playing. Listening judgment is recorded separately
below; this UI observation alone does not establish audible continuity.

## External audio harness

`sim/web/test/audio-loopback.mjs` records the browser's actual output from
an isolated PulseAudio null sink's monitor at 48 kHz, float32 stereo. This
is outside the page's AudioContext; the output path includes the browser
backend and PulseAudio. Chromium explicitly omits Playwright's default
`--mute-audio`, without changing the defaults for other page tests.

The first recording holds A4 on the repository's independent Test Sine
engine while eight parameter records are sent every three milliseconds
for 30 seconds. The analyzer trims only the note's attack/release and
capture margins, checks sufficient signal duration and finite samples,
and fails on a near-zero run of 128 samples (2.67 ms at 48 kHz) or a
440 Hz cycle error over two samples. The latter also detects held/repeated
blocks and skipped phase. `audio-analysis-check.mjs` proves a clean sine
passes and injected silent, held and skipped blocks, and absent output,
fail. This does not certify every possible distortion or a physical device.

A second recording plays First orbit, edits Sound 2's timbre, and switches
project A/B four times and Sound 2 A/B four times. It saves a WAV for
listening plus the scope, side and playing-state observations around each
switch. Musical pauses are not classified as dropouts by the sine detector.

All runs use disposable Playwright 1.63.0 containers on aeon, with the batch
slice, a 4 GB memory limit and task labels; no host audio services are changed.

## Results and the A/B defect found

[verified: final LAN runs] All three browser/backend captures pass:

| Browser | Sustained signal | Maximum cycle error (samples) | Silent runs / bad cycles / channel mismatches |
| --- | --- | --- | --- |
| Chromium 153.0.8010.12 | 32.000 s | 0.00960 | 0 / 0 / 0 |
| Firefox 155.0 | 32.009 s | 0.00854 | 0 / 0 / 0 |
| WebKit 26.6 | 32.009 s | 0.00952 | 0 / 0 / 0 |

Every browser accepts every storm batch with no refused record or resync.
Each musical capture contains all eight successful switches (four project,
four Sound 2), alternating A/B, with no stopped transport message or
non-finite audio. The WAVs are approximately 30 seconds, with peaks near
0.26. The detector's right-channel-loss fixture also fails as intended;
reanalysis of the original monitor captures has no channel mismatches.
Recordings and JSON reports are local, ignored build output under
`sim/web/build/audio-results/`; CI retains them on failure.

[verified: failing capture, source and native/browser regressions] The longer
A/B test found a defect the previous two-switch check missed: a sound restore
used an external import's modulation merge, allocating another module and
cable every time. The third attempt to hear A was refused with “The rack is
full (8 of 8)”. Sound A/B now uses `FM1_APP_LOAD_RESTORE_SOUND`: it restores
original identities and replaces the sound's own cables, preserves unchanged
modules and their phase, and refuses to overwrite changed shared modules or
a cable slot taken by another destination. External imports still remap.
Picks, their preview and redo use the same restore rules.

The rebuilt module passes 104 parity scenarios and the native edit checks,
including twelve repeated sound restores with unchanged rack/cable counts,
a refused shared-source replacement with unchanged state, and an ordinary
external import that still remaps. The affected Python run passes 272 tests
(app state, simulator, editor UI source guards, metadata/schema, manual and
CI pins), without stale-artifact warnings. Real Safari on the final build
also switches Sound 2 four times, alternating Hearing A/B, with playback
still running and no refusal.

**Listening judgment:** pending the owner's response to the live Safari
comparison and the captured WAV. Do not label this a completed “by ear”
check from the signal/transport measurements alone.

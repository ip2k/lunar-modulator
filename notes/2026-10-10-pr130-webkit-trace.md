# PR130 WebKit panel-follow trace (2026-10-10)

## Observation

The CI run for PR #130 (`d7170e043b1824f537613b65efddcb3de72d12e2`, run
`38027209756`, WebKit job `114140484818`) failed only the `editor-ui`
assertion that a panel knob reaches its editor row within 12 animation frames.
It reported key `s2:2`, 49 frames / 784 ms. The remaining WebKit checks passed:
editor reach, 41/41 editor-map checks, 99/99 editor-v1 checks, all info-dialog
checks, and the 30-second editor storm.

The captured main-thread trace shows animation frames continuing at roughly
16 ms intervals while audio `currentTime` remained `0.7140136` from frame 1
through frame 47 (0–752 ms). Audio time advanced at frame 48 (768 ms); the
worklet's `changes` message arrived immediately afterward, and the editor row
changed from `0.30` to `0.33` by frame 49 (784 ms). At message delivery,
editor generation advanced 4→5 and both pending and in-flight change counts
were zero. The test helper posts the encoder event, counts requestAnimationFrame
callbacks until the row changes, and records main-thread message delivery; it
does not timestamp receipt inside the AudioWorklet.

This run therefore records a browser/audio-worklet scheduling stall with a
prompt editor update once the worklet resumes. It does not establish whether
the stall came from CI resource pressure or another browser/runtime cause, and
is not evidence of delayed editor application logic. No assertion was changed
and no PR #130 source was edited. An exact-head rerun remains necessary before
classifying this as transient.

Evidence source: GitHub Actions job log for run `38027209756`, job
`114140484818`; retrieved with `gh api .../logs`. This is a CI observation,
not a simulator, hardware, or product-readiness claim.

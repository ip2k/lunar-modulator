# Chromium startup and edit-storm localization

[verified] This investigation starts from PR142 exact
`ef39b23869a9d06b19ad4478554792508d186d29`. Its
[Chromium job](https://github.com/ip2k/lunar-modulator/actions/runs/38035944467/job/114166263556)
failed the unchanged zero-underrun storm gate: one event, 11.609 ms
(512 frames at 44,100 Hz), 7,279 edits, zero rejected codes/resyncs,
905 telemetry messages and a valid binary snapshot. The separate strict
loopback passed (32.000375 s, eight A/B swaps, no transport stops,
nonfinite samples or measured silence). This does not prove a listening pass.

[verified] Its complete post-startup audio trace has no explicit named
SyncReader timeout, Glitch!, FIFO shortage or overrun. Maximum
RealtimeAudioDestinationHandler::Render duration is 1,073 microseconds,
below the 2,902-microsecond quantum. The recorded window cannot locate
a startup glitch or prove that every browser glitch emits these events.

[verified] The opt-in pre-power-on phase/raw-counter diagnostic is preserved
from `e25916d0776ec756984fbdd5490f42c345dddcfc`; no baseline, drain,
assertion, tolerance, retry or acceptance window is changed. Diagnostic
files alter simulator source-hash inputs; the PR142 Wasm is retained for
observation, and this tree is not a fresh built-artifact acceptance tree.

[inferred] Per-edit typed views and per-change-check RAM scratch allocations
are avoidable, but they have not been tied to the observed event. No runtime
change is justified merely by their presence. A bounded idle/storm pair
will trace before power-on with the actual PR142 Wasm. Getter graph locks
and tracing perturb scheduling; absence of reproduction cannot explain CI.

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

[verified] One bounded paired run on aeon with the exact PR142 Wasm completed:
30-second idle control: zero published events; 30-second storm: 7,304 edits,
zero published events, rejected codes or resyncs, 905 telemetry messages and
valid snapshot. Both complete traces had zero dropped events and no explicit
named timeout/glitch/shortage/overrun. Both baselines still showed only
0.002902 seconds of published total duration while audio time was about
0.34 seconds. This directly shows publication lag; it cannot assign CI's
event to startup. The source/provenance, original failure and both raw
counter timelines are preserved in
[data/2026-10-10-pr142-chromium-startup-pair.json](data/2026-10-10-pr142-chromium-startup-pair.json).

[verified] The existing CI capture now begins before page navigation/power-on
and saves bounded phase/raw-counter history, instead of capturing only after
startup. The exact original pre-loop baseline, loop, snapshot drain and
zero-underrun pass expression remain unchanged. No retry or baseline discard
is introduced. Node helper regressions: 13/13 pass; syntax and diff checks
pass. This is an observability checkpoint; it does not repair the unknown
cause. A merge-ready artifact must be rebuilt against the changed simulator
source inputs.

[inferred] A separate startup ordering concern is measurable: the page connects
the live worklet to the destination before Wasm instantiate, static constructors,
firmware initialization and default-chain creation finish. No published CI
event has yet been attributed to that work. The next bounded probe measures
initialization time and message delivery with the node disconnected; it keeps
the context wake inside the user's gesture to preserve browser autoplay rules.

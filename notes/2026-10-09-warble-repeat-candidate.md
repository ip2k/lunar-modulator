# Warble + Repeat isolated integration candidate

This branch is a preparation candidate, not merged or accepted for demos.
Parent controls merges after all required exact-head checks pass. No hardware
traffic, device timing evidence or native Safari listening pass is claimed.

## Source provenance

[verified: Git merge parents] Starting main is
`c5fd5e9e01d5c8204e287d3986c929626f19422e`. Warble PR123 parent is
`0e43e503be47737446c1ccd03915f1a888ce9803`; Repeat PR137 parent is
`9b2d80c4c6a9df47c794fa4d413a72e12b645225`. Both source histories are retained.
Pending PR123/137 worktrees and CI heads are unchanged.

[verified: source conflict inspection] Both MIT DSP implementations are
retained unchanged. Shared catalogue/default list, editor effect groups and
user documentation include both effects. Registry and scenarios merged with
both entries. The stable existing parameter UIDs are retained. New metadata
must come from the actual combined native/Wasm build.

## WIP source checkpoint and recovery

The source milestone deliberately removes `sim/web/www/fm1.wasm`,
`fm1.wasm.json` and `meta.json` rather than selecting either branch's stale
binary. This checkpoint cannot pass simulator tests or be served as a preview.
The example metadata ID has been refreshed from the combined native export
as described below. No failing checkpoint is eligible for merge.

Next: merge the accepted PSX correction, refresh the native export if needed,
then build musl and Wasm from the exact combined sources;
run full parity/screens/metadata/edit checks and focused effect, API,
parameter, smoothing and state checks; then checkpoint generated artifacts
with recomputed source hashes and build provenance. Final combined acceptance
also requires the normal browser/CI gates. Existing frozen-clock WebKit and
owner listening receipts remain failures until independently resolved.

Recovery worktree: `~/.codex/worktrees/warble-repeat-candidate/mvave-fm1-firmware`.
LAN sources: `/home/claude/mvave-fm1/warble-repeat-candidate-20261009/src`.

## Combined preparation and failure receipts

[verified: Git merge parents] Configuration-only main
`bdba4476570b0a77d13c76a38dfb3bcfd364277b` and Repeat's contract correction
`e1416ac0578bde81192362554089c88ece65c3f9` are merged normally into this
candidate. The latter appends Repeat's three new UID pins and two ENUM flag
decisions; all prior pins are preserved, including Warble's. Before correction,
the bounded combined native parameter suite failed exactly those two contract
checks; the corrected Repeat branch passed all 15 parameter / Repeat tests.

[verified: actual native export] The combined native build completed in the
pinned Emscripten 6.0.10 image. Its metadata ID is `53ec1875`, and only that
field changes in the example metadata subset. A new
`four-sounds-warble-repeat-hold` parity scenario puts Warble then Repeat in the
two MASTER slots with four active sounds and a Crush insert, using explicit
sequencer Start / BEAT / Stop. It still requires actual combined musl and
Wasm regeneration; no old binary is accepted as combined evidence.

[verified: CI job log] Warble PR123 exact head
`0e43e503be47737446c1ccd03915f1a888ce9803`, run `38025769986`, WebKit job
`114136174695`, failed panel-follow at 46 frames / 734 ms. The audio clock
stayed at `0.7169160997732427` through frame 45 (714 ms); state and change
messages arrived at 725–728 ms, then the correct value / source / flash
appeared. Trace declares timing perturbation and zero dropped events. External
audio loopback passed. The exact trace is in
`data/warble-0e43-webkit-panel-follow.json`. This is a failed latency gate with
the recurring frozen-clock signature, not evidence assigning cause to Warble
or permitting a retry / gate waiver. Existing owner listening failure remains
unresolved by these offline checks.

[verified: bounded native preflight] With both effects and the corrected
parameter fixture, 142 / 142 tests passed across `test_engine_params.py`,
`test_engines_repeat.py`, `test_engines_warble.py`, `test_engine_api_v3.py`,
`test_engine_smooth.py` and `test_state_schema.py`. Receipt: aeon
`/home/claude/mvave-fm1/warble-repeat-candidate-20261009/src/combined-native-check.log`.
The final combined regeneration waits for the accepted PSX interpolation
source correction; this native preflight does not replace the future
exact-source musl / Wasm / browser checks.

[verified: native full-chain preflight] The added combined scenario rendered
132,354 frames at 44,118 Hz through Warble then Repeat with all four sound
instances and the Crush insert. The actual native summary reports 146
sequencer events, zero dropped / refused events, zero nonfinite or clipped
samples and no hung notes. Warble instance is 16,464 bytes; Repeat is 65,648
bytes. These are instance sizes, not total project or device RAM use. This
does not establish musl / Wasm parity or browser timing. Receipt: aeon
`/home/claude/mvave-fm1/warble-repeat-candidate-20261009/src/combined-native-case.json`.

[verified: actual combined native metadata] The `audio_fx` registry contains
24 user audio effects after excluding Test Gain and Test Ext. Both Warble and
Repeat and their descriptions are present. The README heading now uses this
count. The final generated metadata must be checked again after regeneration.

[verified: CI job log] The independent review / receipt PR138 exact head
`75aaf658324f119f413090d0e989ddfe44bf41b4`, run `38030495406`, WebKit job
`114150219567`, also failed only panel-follow: 51 frames / 810 ms. Frames
1–50 retain audio time `0.7169160997732427` through 793 ms; the first state
message arrives at 794 ms, the editor applies the correct value at 800 ms,
and frame 51 observes it at 810 ms. The trace reports timing perturbation
and zero dropped observer events. Exact failed trace is preserved in
`data/review-75aa-webkit-panel-follow.json` without changing PR138's tested
head. This recurring signature does not establish a root cause or excuse the
failed gate.

[verified: Git merge parent and independent source review] The accepted PSX
interpolator / screen-oracle checkpoint
`0e897f1cd00a9f7938bbfcf93a02bd23aa01c3bc` is merged normally. Its branch-only
Wasm and record are deliberately removed, so all three generated simulator
files still await an actual combined build. The 142-test and 132,354-frame
native preflight receipts above preceded this correction; the final build
must validate the corrected exact source, including the musl screen oracle.

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

The actual combined regeneration and focused validation are recorded below.
Final combined acceptance still requires the normal browser/CI gates. Existing frozen-clock WebKit and
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

## Final coherent editor / effects source preparation

[verified: Git merge parents] Parent-authorized integration also retains the
reviewed exact heads for sound A/B continuity (PR128
`1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5`), Compare MIDI pulses (PR113
`b43960680760092bf1eb13ad2371b2039326abd9`), native scope verification
(PR129 `ac3d9571b8a2db6860db60b1afb5f10246134e26`), pixel preview
(PR125 `7fe4e6cd10e5d4aa895c5df18d0273364788be5d`), and Picks history
(PR118 `b4234c1b816d71f777796404eb4f0a5190f4eace`). PR129 adds a native
probe and regressions; it does not change the native renderer. No inherited
generated binary is retained.

[verified: source review] PSX follow-up
`0637bf2befd6ac0646b00157a16f4712840fbc4f` records the selected exact screen
oracle and nullable glibc / musl diagnostics in the generated build record,
and corrects the source-hash note and no-additional-mask wording. Its hashed
script changes precede final regeneration. PR132's reviewed CI-only lifecycle
configuration can integrate after its gate without changing these DSP / sim
hashes. This new combined source still requires the complete exact-head CI;
individual failed WebKit heads are not treated as passing.

## Actual combined regeneration and corrected fixture contracts

[verified: exact source build] Source checkpoint
`3519c3857d9bddb8007e14de7ef84525ef8df96a` also normally merges reviewed
HTTP test-server containment PR105 `cc43875c7b205fcfbe530c04e4e7950cd6370bae`
and Movy oracle bounds PR114 `a97659f56cd54499a09e99f7689df4aff74cf7b3`.
The server's two actual HTTP regressions pass. Static musl references and
the native / Wasm pipeline were built from the combined source tree, using
the image digests recorded in `sim/web/www/fm1.wasm.json`. LAN containers
used `docker-batch.slice`, four CPUs and 8 GiB limits. Build stage:
`/home/claude/mvave-fm1/warble-repeat-psx-dbbfe939/src`; final log:
`combined-final-build.log`. This replaces absent WIP artifacts with actual
combined output, not a selected parent binary.

[verified: binary and source checks] Wasm SHA-256 is
`c88938845cd93e52f5cb99c53a650b4eaf559833e5f39fb58ecc0f0c4ab09502`
(1,561,111 bytes). Local and LAN inputs exactly match the build record:
engine hash `b97e01d8ff7c98ad36a3f5301fae9486af5cc7602fadc2e263968a4c7036ad38`,
sim hash `4d861adaacdcbd3454fb125fd4c5d19330aa1223d47959a65148020a85fe4377`.
Both later manifest / fixture corrections below leave these hashes unchanged.

[verified: actual build] All 108 parity scenarios pass, with exact audio
against JS and musl in all 108, and 105 exact against glibc under the existing
libm-sensitive policy. All 4,658 native screens pass with zero layout faults;
18 DX7 checks and metadata pass. Native metadata ID is `53ec1875`; Wasm ID
is `5d726997` (instance-size differences are recorded). Native example
metadata is exact, and actual metadata contains 24 user audio effects after
excluding Test Gain and Test Ext. The 30-second offline edit storm applies
82,728 edits across 10,341 quanta with zero late quanta / resyncs; edit parity
is zero LSB. These checks do not measure browser audio scheduling.

[verified: combined four-sound scenario] `four-sounds-warble-repeat-hold`
compares 264,708 stereo samples (132,354 frames), all zero difference against
JS, musl and glibc, with zero screen difference and dropped sequencer events.
The app RAM summary is 177,904 bytes for Wasm32 and 192,536 for native64;
this is simulator accounting, not verified device placement or timing.
The PSX screen oracle selection and nullable diagnostics are retained in all
108 record entries: 104 select glibc, four select musl. Sophie kit's 34 glibc
pixel differences remain visible as diagnostics; its accepted musl comparison
is exactly zero pixels. No new mask or threshold is introduced.

[verified: focused regression and discovered omissions] The first expanded
native batch passed 259 tests and failed only the strict PSX vendored-file
manifest parser: a prose suffix after the hash prevented its row from being
parsed, although the actual source hash matched. The machine-readable row is
restored; the existing Local changes prose still credits and describes the
interpolation correction. The corrected expanded batch passes 271 tests in
11.90 seconds, including effects, parameter/API/smoothing/state, native scope,
Schwung / direct PSX oracle, modulation kinds, edit layer and committed record.

[verified: serialized enum contract] Follow-up PR137 macOS failure evidence
identified Repeat's separately pinned enum entry names, omitted by the earlier
UID / flag correction. The actual combined named checks reproduce one failed
name contract and six passes; the metadata example test passes here. Only
Repeat Hold UID1 (`Off`, `On`) and Max slice UID2 (`1/8 max`, `1/16 max`,
`1/32 max`) are appended to `enum-names.json`, preserving every old engine
and modulation entry. Names / metadata example / parameter / Repeat checks
then pass 22 tests. The actual editor unit script also passes all 36 checks,
including Picks structural undo/redo. Initial selector / argument invocation
mistakes executed no relevant tests and are not counted as source failures or
validation. Compact receipts and before / after logs accompany this note in
`data/combined-3519-*`.

Full candidate browser / exact-head CI acceptance is still pending. Earlier
individual WebKit latency failures and the owner's unmeasured Safari A/B
listening failure are preserved; these offline results do not overwrite them.

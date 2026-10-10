# Automatic integration and demo prerequisites

Owner, 2026-10-09: merge all completed work automatically from now on and
start the demo songs if prerequisite work is out of the way. The identical
policy is saved in AGENTS.md and CLAUDE.md. No CI/review gate is waived.

Integration starts from remote main c35dbadc39bd77f182c1bd34599cc1717394a477,
the verified merge of resampler CLI bounds PR106. The primary historical
editor checkout is left untouched; current integration uses the managed
completed-work-integration worktree and branch
chore/2026-10-09@completed-work-integration.

Merged and verified on remote main: PR106, PR108, PR115, PR119, PR122,
PR124, PR111, PR101, PR112, PR116, PR117 and PR120. The latest verified
remote main is 9cfc46dc35c2fb859f22a1f5315f6990c415a099. This includes the delayed-envelope
graph and curves, offline firmware preparation, and bounded audit fixes.

Pending: integrate the combined Warble effect build;
complete exact-head browser checks for the native screen preview, Picks
history and semantic configuration; integrate the held-note
A/B correction (PR128); reconcile stale documentation PRs without restoring old state.
Rebuild and validate combined generated simulator artifacts after engine
changes rather than selecting conflicting binaries arbitrarily.

The demo brief and original Voltage-inspired transition plans are in PR121.
Four completed demo assets do not yet exist. Composition implementation starts
after its prerequisite streams are integrated. Offline firmware diagnostics
are preparation: no Lunar application has run on the FM-1, and no installable
release is claimed. Full-image/broken-app recovery remains a separate gate.

Recovery: use live PR state and exact-head checks, not this dated snapshot;
fetch origin/main before integration and preserve pushed source branches.

Active checkpoints: Warble PR123 requires a real combined Wasm/metadata
rebuild after PR101; A/B PR128 then needs the same integration. Information
dialog PR120 passed exact-head CI at f8d70df96e4ecd3b458018ed4c7f36a28d776d39
and merged at 9cfc46dc. PR117 passed exact-head CI at a973087d3eab736e25b487ab8011f69d882fb6a1
and merged at cafd77e0.
PR109 ledger reconciliation and the shared WebKit frozen-audio-clock
investigation remain active. No completed demo songs are claimed.

Additional integration checkpoints: Picks PR118 now targets main and has
current-main integration plus passing combined editor unit checks at
b4234c1b816d71f777796404eb4f0a5190f4eace. Recovery documentation PR102 keeps
current README claims and has its remaining unique docs at
962e8ba900f7c223b46f7dd058874fabe96ace20. Both are pushed; fresh CI is pending.
Completed standalone work is now attached as PR129 (scope raster assertions),
PR130 (distinct-effect research) and PR131 (SDK/runtime/licensing evaluation).
They still need review/check completion before merging. PR109 reconciliation
is pushed at c69f9af06cbf977d26285f724d8f8604976d7221. PR105/107/110/114 have
current-main updates pushed, retaining their unique changes; fresh CI is pending.

## Current integration recovery checkpoint

[verified] PR125 native-preview/modal integration is pushed at
7fe4e6cd10e5d4aa895c5df18d0273364788be5d; semantic configuration PR126 at
af1558248b7a670fe38e1afee9d3ff657b79a733; demo brief PR121 at
32d4747f900a47de4054618195ffe269f73ccef6; reconciled SDK/licensing note PR131
at 78101317052b2eb990d7a24fbe855dbb506ce1eb. All await fresh full CI.
Warble PR123 is now at 0e43e503be47737446c1ccd03915f1a888ce9803; A/B PR128
at 1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5 and Compare PR113 at
b43960680760092bf1eb13ad2371b2039326abd9 retain combined native/Wasm checks.
Merge a green engine stream first, then rebuild the others against its actual
integration rather than choosing a conflicting Wasm binary.

[verified] Scope assertion PR129 WebKit job 114129330510 (run 38023499052)
failed panel-follow at 60 frames/962 ms. Its trace reports audioTime
0.7111111111111111 unchanged through frame 59 despite running state; frame 60
advances to 0.7314285714285714. The same job passed 30-second loopback with
3756 storm replies, no resyncs and no reported audio defects. This repeats the
frozen-clock signature; cause remains unproven. Investigation continues in
PR132, with strict assertions preserved.

[verified] PR133 at d66e199790f2ba7f09cbdfe3d5404c88fe81a675 ports remaining
verified control-count and Movy tag facts from old PR58. Wait for PR109 and
PR133 integration before closing obsolete PR22/58; do not merge their stale
snapshots wholesale. Only queued runs for superseded remote branch heads were
cancelled to release CI capacity; current-head checks and failing evidence
were retained.

Firmware work continues with a separate offline inert panel-protocol link
variant, RAM-only callback accounting, and retained packaging rejection.
There is still no device execution or installable firmware claim.

## Continued prerequisite checkpoint

[verified] PR110 passed all 14 executable checks (Pages deploy skipped for
the PR), then merged at `7eb55b1fd05b8e03fc9dcaf663ce194019299dbf`; the remote
main SHA matched. Its factual corrections keep the Safari Sound 2 listening
retest open. PR135 at `e1868110e6ffb69ce92b83f30f0c88a3461ef233` corrects the
audit disposition: unknown-MFX false application and X0X signed shifts were
fixed by PR100; separate demo admission and GPL distribution checks remain.
PR135 still awaits full CI.

[verified] Independently reviewed PR136 at
`1299c590408e6d919181294bdadc8c28b4b7503a`: its offline tool recomputes the
link audit and ELF-derived report, excludes the 16-byte stock bank header
from loaded RAM, checks protected boot data and reserved alignment gaps,
and retains unresolved ownership. The author's bounded LAN suite reports
89 passing tests including the held stock bytes. Root reviewed source/tests
and receipts; it did not independently rerun that private-stock check.
Full CI is pending. No hardware authorization follows from this receipt.

[reported] PR132's strict editor UI checks passed 93/93 with 37 screenshots
in each browser. Its candidate null-sink setting still failed the two-CPU
WebKit external capture (maximum silence 39.729 ms). The preserved run also
recorded 76.572 seconds of CPU throttling; a four-CPU paired backend test is
in progress. The backend change is not adopted and no audio assertion was
relaxed. PR-only CI concurrency at `fda3539a91db82ae5753cecbe4e896b45c6dee29`
preserves every matrix/check and main run. Only queued superseded PR heads
were cancelled; current heads and failure evidence remain.

Repeat is now an original MIT implementation stream, separate from the
effect-inspiration research. Its reviewed direction uses the existing
tempo/transport API, a single bounded stereo capture ring, an honest maximum
slice control and octave subdivisions to fit the buffer. It remains unbuilt
at this checkpoint; Warble and Repeat must integrate with real rebuilt
Wasm/metadata before their features are used in canonical demos.

## Handover research merge and effect review

[verified] PR107's exact head `93a7c1ba25c89780059f859b331ed7ab39ed7bf5`
passed all 13 checks and was clean/mergeable. Root merged it with a merge
commit and an exact-head guard; GitHub and the remote main ref both identify
`c5fd5e9e01d5c8204e287d3986c929626f19422e`. This is stock-loader research,
not a device execution or RAM-ownership proof.

[verified: bounded source review] Repeat's initial short-loop cursor read
the oldest full-ring history. The implementer corrected it to end each
selected window at the frozen write head and added a nonperiodic capture
regression. The original seam crossfade also approached a later head sample
before wrapping to the first; it now reaches the first sample exactly without
shortening the loop period. The implementer's focused native suite reports
8/8 passing checks; full integration, Wasm, CI and listening remain pending.

[verified] The controlled PR128 Sound 2 listening fixture is served at
`http://127.0.0.1:8781/` from an immutable copy of head
`1c09c5a229dd8c4ec4dd9e725f9c7bdb27f889c5`. Load First orbit, start playback,
keep Sound 2 as A at Volume 0.70, set B's Volume to 0.15 and alternate A/B
during notes. Existing previews on 8778/8780 are preserved. HTTP/source-byte
checks establish delivery only; the owner's crackle retest remains open.

[verified: reviewed configuration] PR132 head
`c6db9587c1d8d1ca6f993d8f433875761f3b2b6e` selects supported `norewinds=1`
only for the private headless PulseAudio sink. Its four-CPU WebKit capture
passed the strict external audio gate, with 3,756 replies and no bad periods
or refusal/resync; the failed two-CPU receipt remains. Three additional
uninstrumented cold pairs passed. No production runtime or assertion changes.
Its exact-head GitHub checks are queued; this is not a CI-success claim.

## Final Repeat artifact verification and remaining gates

[verified: independent artifact inspection] PR137 at
`9b2d80c4c6a9df47c794fa4d413a72e12b645225` has committed Wasm SHA256
`edda579cc762bc225246cd8204a0652729e7d24d65bea13b5d2eeb8360898b6f`.
Root recomputed both source-tree hashes and the binary hash against the
actual clean checkout; all match its build record. Metadata and module ID
both equal `0d1d0b8b`, with no imports and 106/106 passing parity scenarios.
The beat-held Repeat scenario has 264,708 frames, no dropped events and
zero sample/screen differences. The four-active-sound admission scenario
has 123,530 frames and zero differences, using 185,840 bytes in Wasm32
and 200,472 bytes in native64. Repeat alone is 65,648 bytes, including its
65,536-byte ring; these totals are simulator evidence, not device SRAM proof.

[verified: source review] The focused independent review and original
failure traces are backed up in PR138 at
`75aaf658324f119f413090d0e989ddfe44bf41b4`. PR113 and PR114 retain strict
WebKit failures; passing external loopback in those runs does not erase
their panel-follow failures or establish a human listening result.

PR133 and PR135 integrated current main normally and are pushed at
`a5bac822d9ed9b938393ca1ef5e575d453616775` and
`475c859c5187ecf94a6881f4620b93ae4d8fb614`, respectively. Their fresh
exact-head checks remain pending. Continue the audible audit disposition,
strict WebKit correction, combined Warble/Repeat regeneration and reviewed
green merges before composition implementation. Preserve the pending owner
Sound 2 A/B ear check and the independent device-readiness boundaries.

[verified: CI/remote] PR126 at
`af1558248b7a670fe38e1afee9d3ff657b79a733` passed all 14 executable checks
(Pages deployment skipped for the PR), was marked ready, and merged with an
exact-head guard at `bdba4476570b0a77d13c76a38dfb3bcfd364277b`.
The remote main ref matched. This integrates the portable semantic-tool
configuration and its explicitly bounded session evaluation.

[verified: source] The audible PSX Verb audit finding remains present on
main: the odd phase table is entirely zero, the even phase table differs
from the full kernel's even taps, and interpolation walks the zero-stuffed
history with unit-stride phase coefficients. A focused repair is active;
validate against an independent full-kernel calculation and retain vendor
provenance. Avoiding this available effect in demos is not its remediation.

## PSX repair review and independent offline checks

[verified: independent local checks] Root ran PR136's exact
`1299c590408e6d919181294bdadc8c28b4b7503a` `test_handover_layout.py`
with the project's Python environment: 28 passed; the optional locally held
stock SPL check skipped. This verifies synthetic offline contracts, not a
device execution or an independent repeat of the author's private-stock test.

[verified: independent source/test review] PR139 at
`0e897f1cd00a9f7938bbfcf93a02bd23aa01c3bc` corrects PSX Verb's two
interpolation phases and history domain. Root reviewed the direct 39-tap
zero-stuffed FIR oracle and independently ran its focused test successfully.
The implementer's bounded LAN run reports 104/104 exact JS/musl audio cases,
DX7 18/18 and zero late quanta in the 30-second edit storm. The corrected
Sophie framebuffer is exact against native musl; the 34 glibc scope-pixel
differences remain diagnostics. The existing bottom-right RAM mask remains;
there is no additional waveform mask or tolerance.

[verified: acceptance issue] Root's artifact test verified PR139's binary
hash but warned that its sim input hash was stale. Build/test inputs changed
after staging the successful build; identify and regenerate the record using
the actual pipeline before final acceptance. The record serializer also needs
to retain the selected screen reference and glibc/musl diagnostics. These
follow-ups are assigned to the implementer. Source review permits the combined
Warble/Repeat candidate to incorporate the repair and perform its required full
regeneration; PR139's current artifact is not accepted as the final combined
artifact. Its exact-head CI remains pending.

[reported: bounded reproduction] The browser investigator reproduced PR131's
exact Chromium storm three times under a four-CPU LAN quota with the original
Pulse sink; all passed. Its CI failure remains one 11.609-ms playback underrun.
A Chromium shared-memory callback timeout can produce a buffer-duration glitch,
but the failed trace does not localize that cause. Do not claim a production
runtime fix or that PR132's headless sink correction resolves this separate
failure. Continue exact-head CI and preserve failed receipts.

## Combined candidate and renewed bench work — 2026-10-10

[verified: live GitHub and source inspection] PR140 is open at
`9a5fb72a54f5117169840f331fd1f756071e6fd5`; it is not merged. It combines
the reviewed source histories, actual regenerated artifacts, reconciled docs,
Warble/Repeat manual sections, and bounded separately named Node CI steps.
The current module SHA-256 is
`c88938845cd93e52f5cb99c53a650b4eaf559833e5f39fb58ecc0f0c4ab09502`.
Engine/simulator input hashes match its record. Root independently checked
the committed-artifact contract and reviewed the final documentation/CI edits.
The candidate's recorded validation includes 108 parity scenarios, 4,658
screens, 271 native checks, 22 contract checks and 36 editor checks. The
documentation author reports the complete 42-entry manual now builds with
zero errors/warnings. Fresh exact-head full CI is required before merge.
Earlier candidate Pages succeeded with two missing-section warnings; those
warnings prompted the actual manual correction rather than a waived gate.

[verified: completed CI logs] PR132's Chromium job timed out before browser
launch: nine Node helper tests passed, followed by an opaque stall in the
combined Node step. The precise hanging process is not localized. PR140
separates the commands, keeps editor-unit output, and gives each a five-minute
timeout; no assertions or audio tolerances changed. PR134 and PR136 each
failed WebKit startup latency on their exact heads and remain unmerged.
No retry, full-CI pass, native Safari listening pass, or device execution is
inferred from focused checks. The owner's Sound 2 crackle retest is pending.

[verified: live inventory] GitHub has 25 open PRs. The owner explicitly
requested disposition of all of them. The reconciliation agent is identifying
fully/partly subsumed work and independent firmware streams; superseded PRs
are not closed before the replacement actually merges. Four queued outdated
PR139 runs were cancelled after checking their heads against current PR139;
current-head and main runs were left intact. The source branches stay backed up.

[reported: owner, this session] The actual FM-1 remains powered on and
connected to bench01, and firmware work in parallel is authorized again.
Cynthion is available if a specific USB trace is needed; the device remains
on direct bench USB for the initial checks. The hardware investigator uses
an isolated `fm1-live-bringup` worktree, beginning with current USB identity
and private backup verification. Revised staged device policy applies.
Successful scratch-sector restoration is distinct from untested full-image
restore and broken-app recovery; no new hardware traffic is claimed here.

No schema/API blocker was found for the four demo songs. Existing four sounds,
eight tracks/eight scenes and song chains suffice. Full-song admission,
native/Wasm render, session roundtrip, browser workflow and musical listening
acceptance will apply to the authored assets. Generic project-example filename
tests and an obsolete schema-test docstring should be corrected with those
assets. Remaining rate/input-bound audit findings stay tracked, not blanket
closed. A separately pushed readiness ledger records these distinctions.

## Exact-head follow-up — 2026-10-10

[verified] GitHub inventory is now 26 open PRs after replacement #141 was
opened. Every open head matches its remote source-branch SHA. Nineteen older
heads are ancestors of #140; #134 and #136 are ancestors of #141. #139's
unique WebKit trace note is byte-identical in #141, while its runtime fixes
are already integrated in #140. #22 and #58 are stale snapshots whose useful
factual corrections have been reconciled into the current documentation;
they must not overwrite current HANDOFF. No superseded PR has been closed
before replacement acceptance.

#140 remains frozen at `9a5fb72a54f5117169840f331fd1f756071e6fd5`.
CI run 38034115528 has passed Chromium, Firefox, WebKit, Ubuntu, macOS,
32-bit, both module-list builds, MIT/BSD, dongle and reference checks.
Sanitizer engine tests passed; its virtual-app step is still running. Pages
run 38034115529 built 17 chapters / 42 entries / 275 pages with zero manual
warnings, errors or outline boxes; deployment is intentionally skipped.
This is not yet full CI acceptance or merged-main evidence.

#141 is frozen at `9ecd5ad2373ad0bd15106f31a44f50d68bc9c28e`.
Root independently ran 33 passing offline layout/capture tests with two
private-artifact skips. CI run 38034613510 failed Chromium's strict storm
gate with one 11.609 ms underrun; its loopback and UI gates passed, as did
Firefox/WebKit. Captured scheduling data does not establish the cause.
The failure is retained; no blind retry or tolerance waiver is authorized.
Detailed receipts are backed up on `chore/2026-10-10@pr140-ci-diagnostics`
at `40791988c17aeca754c451187acc9cfdbb9daea0`.

A new focused DSP branch, `fix/2026-10-10@audited-dsp-boundaries`,
corrects Sophie multi-turn phase wrapping and Mutable FX NaN default handling,
and clarifies Gate's fixed lookahead cap. Sophie also affects normal-rate
high-ratio operation, correcting the earlier readiness note's low-rate-only
claim. Root reviewed the source/provenance and independently passed the C
60,000-step regression; the author reports old-source failure, 167 focused
passes and regenerated 108-scenario Wasm parity. It is not yet a merged fix.

Hardware research is backed up on `chore/2026-10-10@fm1-live-bringup`
at `e2c977d3a42463ee1548001d65208444b8ed2dee`. Fresh identity is
FM-1_092; no new firmware execution or flash writes occurred. Loader FB08
is rejected by the audited loader, and FB42 leads to flash erase, so neither
is an execution alternative. A bounded loader FD07 mask-ROM code-read
proposal is undergoing offline command/bounds review before device action.

## Accepted editor integration and PR dispositions

[verified] Root re-fetched #140 at its unchanged final head: all 14 checks
were SUCCESS, with only Pages deployment SKIPPED. Merged with a normal merge
commit, `40c94300428acfc5688a203c2c928723ed98270a`; GitHub state and
remote `refs/heads/main` both confirm that commit. No CI retry or gate waiver.
The 19 fully contained source PRs were automatically marked merged.

#22 and #58 were then explicitly closed as reconciled/superseded, with links
to the accepted replacement and durable reconciliation. Their source branches
remain retained and remotely backed up. Four PRs remain open: #139, #134,
#136 and #141. #141's final checks are all successful except its recorded
Chromium storm failure. #139's runtime fixes are now on main, but its unique
final diagnostic note remains in the unmerged offline candidate, so it stays
open until that note is accepted. A forthcoming focused DSP replacement will
preserve the offline history and failed receipts while obtaining fresh CI for
its actual changed head. No firmware/device runtime or human listening pass
is inferred from #140's integration.

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

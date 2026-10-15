# CPU / flash timing campaign, 2026-10-15

[verified: owner observation] A physical cold boot still had a severely laggy
waveform display and bad distorted audio. Playback acceptance remains FAILED.
SAVE remains disarmed; the overall firmware/web-installer goal remains ACTIVE.

[verified: offline and bench file checks] The coordinator finalized the CPU
schema8 campaign after rejecting stale copied source inventory pins, the old
60-file native count (this target has61), and the prior receipt-schema field.
The CPU compatibility seal uses `original_frozen_receipt_sha256`, not the old
`original_v3_receipt_sha256`. Exact raw receipt bytes remain pinned. Eight
focused package checks passed. Bench file-only preflight passed, including all
175 runtime dependencies, exact2c tools and the61-file native source inventory.
Independent lifecycle review confirmed fresh paired reads before preparation,
completed installation/readback and durable result before capture and reset,
one reset submission without retry, and CPU/clock-only input capture.

Private package: `scratch/cpu-rate-calibration-deployment/stageable-rom109/`.
Archive SHA256 da49be39ea0039d5992c77922ea2417c7edf0e178e59603a1125238011a40821;
index43ea1bedd31fd04e09d30a9b5796278d1df4ad357815b6968319c83e90d784c8;
stager44776623aeda9f9b51986338ac2f0e34b145c06f552e22ac9325c5733239c65b.
After staging, an explicitly reviewed file-only correction changed preflight's
compatibility receipt field and added its regression check; deployment inventory
was regenerated and all8 tests passed. Final preflight SHA256
cfdd44b55a8b96a68f8572aab78ba58fecf7944f22898abd96d74a5a9e1b5e46;
final deployment inventory5ecfbe70027de1e9c5c3dbd1eca4f8d83176ea594e3f7fcb8bceede30e5f8de8.
These final staged hashes supersede those members in the original archive.

[verified: started, not completed] Root launched the one-use campaign on
bench01 as PID262731 after full preflight. BASE:
`/home/claude/fm1-cpu-rate-8a8fb2b8-20261015`, cycle `rom109-cpu-rate-cycle`.
Expected ROM port1-1/dev109; expected current flash23150dca74404733e377a9c5c74ff883bfa2ef09d67b1f84c0650ccbd9474409;
target5b3ebc0b4a1672662137677bb08de5017c17319ebc25290a676d548654dfa7aa.
Campaign pins c3cbda23cb7a4f828251241695f196965831b5cd3200f2c3f951e250b44ad973.
No second launch or retry is permitted. Inspect sudo-readable cycle.stdout,
cycle.stderr, fresh-read and installation receipts, and diagnostic-audio first.
Positive schema8 timings, status3 and checksum3446819522 are expected;
these are expectations, not yet hardware results. No clock writes or autoplay;
120s timed recovery. No musical or frequency acceptance is claimed.

## V1 stopped read-only; corrected V2 started

[verified] PID262731 exited after fresh paired backups matched current23150dca.
Its manifest explicitly records zero flash and reset operations. Preparation
refused the bound template's stale candidate path before a write transaction.
The coordinator rebased candidate/receipt paths to the staged BASE, added an
explicit candidate-path preflight check and regression test, and regenerated
template/binding/pin hashes. All22 referenced build/candidate/stock input files
were separately read and hash-verified on bench01. Nine package tests passed.

[verified: started, not completed] Distinct campaign rom109-cpu-rate-cycle-v2
started PID263390. Its launch-v2.json and cycle-v2.stdout/stderr do not reuse the
consumed V1 marker or read evidence; V2 starts its own fresh paired reads.
Campaign pins1d03f1f73b0d2d8f00faf584561c8c95f044e365f7fde147fb7e50fdd50e6b99.
The exact overlay is preserved in scratch/cpu-rate-calibration-deployment/
rom109-v2-correction.tar with its per-member JSON manifest. Do not relaunch V2.
Pending completed write/readback, one boot, telemetry, and timed recovery.

## V2 install completed; capture gate rejected campaign suffix

[verified] V2 PID263390 exited after installing target5b3ebc0b and completing
full-image readback. Root independently compared all4096 final256-byte page
response hashes to the exact1MiB candidate; all matched and all SG completion
fields were clean. Transcript SHA256:
`b5f0f658684a264711a3d7bd3d35b8681813ccafcf011949b2e17a904e0b5e5d`.
Result envelope SHA256 field:
`f5ede68721bf2ebf1224ed6c4f0ace9482b1effc7221b9edf4af3a2fcb1c09f2`.
Result reports210 sectors with directory sector0x4000 last.

[verified] Capture failed at require_campaign_pins before creating audio
output: the frozen contract accepts `rom109-cpu-rate-cycle-v2`, but its helper's
separate regex only accepts names ending in `-cycle`. This caused
`fresh CPU-rate cycle identity/runtime pins are unset`. The completed-install
runner stopped before its post-install snapshot and reset gate. No boot marker
or command journal exists in V2. Do not relaunch or mutate this consumed attempt.
Local evidence: scratch/cpu-rate-calibration-result/install-evidence.tar.

[inferred: next action, not executed] Use the established generic fresh-read
boot API in a distinct campaign. Take matching fresh reads of the now-installed
target, validate the same ROM109 connection and passive snapshot, start passive
KA6 capture, then issue exactly one reset. This avoids rewriting the image and
does not represent detached receipts as same-process install proof. Capture
must validate that API's actual read/boot evidence and same-port native USB.
No physical timing, audio improvement, or musical acceptance is claimed.

## Distinct read/boot-only follow-up launched

[verified: launched, not yet measured] PID270568 at
`/home/claude/fm1-cpu-rate-boot-only-20261015`, evidence root
`rom109-cpu-rate-read-boot-cycle`. Never relaunch this attempt. Target/current
both5b3ebc0b; ROM109 same connection. The new runner takes fresh matching dual
reads, starts KA6 recording, then invokes the established one-use generic boot
API once. No flash erase/program and no installation-history claim.

Eight focused helper/gate tests passed, including actual pinned verifier
imports, current==target/environment pins, incomplete journal prefixes,
ambiguous SG evidence and duplicate/partial trailing rows. Bench file-only
preflight passed. It reuses the immutable175-dependency capture inventory,
not the consumed V2 install campaign's preflight. A first file-only check
correctly refused that consumed campaign before any new device access; root
replaced that coupling with explicit helper/runtime/source checks.

Externally anchored launch pins: runner
`c90ca4b377a7ac7ff8756cdba9b99143d63f40ea4bb6f6572b2eecfb720fb12d`,
capture helper `79b07ae2b9484678b0e2242932fd3213dc837f1b335f12046558dc97cca7f16b`,
gate `e74b595f50c91afdc2d571ac749e25eeb4884c23ad6310ff9294ce4eac374da1`.
Private source copies exist on Mac scratch and bench BASE. Independent audit
predates the final consumed-preflight correction; its runner hash is superseded
by the launch pin above. Root verified the final file-only check on bench.

[verified: offline only] Matched Hall-Os/O2 builds at cc501db both passed16
shards/link; only Hall's catalogue object differs. O2 app855616B leaves5028B;
this proves fit/codegen, not runtime speed. Compact sequencer route getter
f0277c94174a3936b71d9346af70f5444cebcb11 is backed up on
origin/fix/2026-10-15@compact-seq-dispatch with matching remote SHA. Root reran
the route oracle, sequencer core and render tests successfully. Neither change
has been physically accepted or integrated into the current diagnostic.

## Physical result and recovery

[verified] The distinct read/boot-only follow-up completed its fresh dual-read
proof and issued exactly one reset submission. The SG reply had host7/resid16/
info1, so the runner stopped as ambiguous and did not retry. Independent capture
validated the read/boot evidence and observed native USB1209:0001 at port1-1,
bus1/dev110. Capture110s and KA6 audio180s both finished rc0 with child cleanup.
Subsequent passive sysfs observed ROM4c4a:8057 at the same port, bus1/dev111.
This is observed timed return to ROM, not stock restoration or musical acceptance.

[verified] Root independently checked107 schema1 frames across106 intervals:
53448 produced blocks and22029 underruns over109.492 device seconds, giving
488.145252621 blocks/s and201.192781208 underruns/s. Required production is
689.34375 blocks/s, a29.187% throughput shortfall. No accepted note-ons occurred.
This run has not fixed the owner-rejected cold-boot audio or display performance.

[verified] All three schema8 reports repeat ONE startup result; they are not
three measurements. Iterations4096/trials4/status3; both checksums independently
match expected3446819522. XIP17497/RAM17491 raw TIMER4 ticks: ratio1.00034303356.
The linked kernels are instruction-identical36-byte warmed integer loops.
[inferred] This supports parity for that small test only. It cannot establish
CPU frequency, rule out full-renderer cache issues, or prove RAM relocation helps.
Independent offline interpretation: scratch/cpu-rate-calibration-deployment/
cpu-rate-result-review.md, SHA256cfb38310…ea01b5f (full hash in local file inventory).

[verified] Local evidence archive1a5c1b43fc3608459f4ba215846e4d8ea434028599a7e6b060637d78206b0207;
events5ff35012fd8dcc152abfa8b1da5149391892a63581475f9e7ca648ada0c10190;
rawc88ae14b3de4f8bc2457b1f5a8d9b7dd0fcad3c96b1194c0e5f5420ad911b787;
capturelogf3f06391cc55a5e265aed43feca46261ceb842bf93b7fd23974e77338fce1119.
WAV stays on bench,207360044B,6ch/48kHz/S32,180s; SHA256
2d448cee8b16e62eb78f3ce43c7c236f23df8e8ba3d4b59895b30295c8f080e5.
No listening acceptance is inferred from recording completion.

[verified: source only] Compact getter cherry-pick f9dc614fbb044418e88592f222c3d654625061e6
is backed up on the active feature branch with exact remote SHA verified.
Root host oracle/core/render tests pass. Matched target builds pending.
Next causal experiment targets measured Hall cost; prepare a Hall-O2 variant
on exact physical CPU8a source rather than comparing unrelated9f82 sources.
No new hardware write/boot campaign has been prepared or launched.

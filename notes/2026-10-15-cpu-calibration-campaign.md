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

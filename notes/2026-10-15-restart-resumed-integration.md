# Restart resumed: installer profile binding

[verified: source and host tests] Resumed from checkpoint17b92837 in the named
installable-firmware worktree. Reviewed worker commit
f138766f266c3ebf8a8ef7e651857c222c84f259 and integrated as
6b6ae4b6813afe96cf9863ab5d499840ac5b8a97. Origin independently matched that SHA.
Explicit D7000 and D9000 requests now require their fixed wavetable profiles
before output creation. Legacy requests without profile keys retain their
previous behavior. Reviewed all call sites of validate_build_profile.

[verified] Worker-checkout selection suite:17 passed with the actual fm1-state
codec. Integrated selection and installer-service suites:121 passed,1 skipped,
one Starlette/httpx deprecation warning. Interpreter:
`/tmp/lunar-installer-service-test-venv/bin/python`; FM1_STATE_TOOL was the
coordinator worktree's `engines/build/fm1-state`. No target link or hardware
acceptance is established by these tests.

[verified: passive] bench01 still enumerated port1-1, bus1/device113,
4c4a:8057 WL80UBOOT1.00 after restart. No device command, flash or reset issued.
Historical installed image and failed audio acceptance remain as checkpointed.

[verified: source review] Designated exact Hall source66c95bb2/tree542445ed as
the source for a coherent new deployment-tools export. Its current candidate,
boot and SG pins agree on the complete14-body profile. An offline worker is
regenerating the archive/manifests and downstream pins in the isolated ROM113
scratch preparation; no physical campaign is authorized by that assignment.
Other workers own bounded private installer evidence retention and read-only
current-target audio codegen review. Root retains exclusive device authority.

Semantic tools: Serena activated the exact coordinator absolute worktree and
successfully returned validate_build_profile, matching the source/caller found
by rg. Rarefaction still selects the primary Developer checkout and its bounded
named query found no symbol; do not infer missing callers from that result or
retarget a shared server while other work is active. Native ABI/codegen checks
continue to require the real pi32v2 tools and hardware evidence.

## Recovery regression and independent package review

[verified: host] Expanded candidate, generic diagnostic boot, SG adapter and
flash suites completed:82 passed. This does not establish physical recovery.

[verified: offline bytes] Independently regenerated the exact66c95bb tools
archive and compared it bytewise with the worker export; checked all manifest
file sizes/hashes and the constructed target/receipt hash. Protected stock
regions0..0x4000 and0xD7000..end match the archived baseline. Evidence:
`scratch/hall-gain-target-independent-review/root-construction-review.json`.
The remaining source/campaign bindings are still being regenerated; no package
staging, fresh-read admission, device write or reset occurred.

[verified: review finding] Private installer evidence worker commit ed6adc5f
is NOT integrated. Its new collector admits /catalogue and /output/build/link,
but the actual worker mounts /input/catalogue and builds under
/tmp/lunar-worker/output/build. Synthetic fixtures therefore do not prove the
real service boundary. Root requested corrected actual-path fixtures, original
receipt ordering, actual generated provenance coverage, canonical path checks,
and file/aggregate caps before allocation. Worker owns corrections and checks.

[reported: worker] Fresh current-source stage2/engine7 profiling catalogue
completed16 Hera shards; bounded target link is running. It preserves all13
engines, Event Horizon+SET, no autoplay/SAVE and120-second recovery. No current
stage timing or hardware improvement has been measured from that build.

## Fresh stage profiling build and malformed pin rejection

[verified: offline bytes] Root copied the stage2/engine7 frozen receipt and
all10 required outputs from Hera and independently rehashed each. All16 shard
and link policy/exit/no-OOM checks pass. Source66c95bb/tree542445ed, receipt
95b57466b48a06c4395132c062a34eb52a952bd0463779b4c3813a43a901b400.
App854644/860644B, all13 production engines, EH+SET, autoplayfalse,
save_service_armedfalse,120-second return. sdk_archives=[]; worker corrected
an unsupported closed-SDK claim in its shared handoff. This is instrumentation
build evidence, not physical audio improvement or installability.
Root evidence: scratch/current-stage7-independent-review/root-hash-review.json.

[verified: review finding] The new ROM113 scratch package carried a65-character
current-flash hash, with its fixture repeating the same malformed value. Root
requested strict64-lowercase-hex checks and negative regression. Read-only
bench filesystem hash and preceding ROM111 install result independently agree:
28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f.
Prior result:210sectors, simulatedfalse, full verified hash as above. Retained
result at scratch/current-stage7-independent-review/preceding-rom111-install-session-result.json.
This is historical evidence only; no fresh ROM113 admission or USB/reset/write.

## Private evidence integration

[verified: source/host] Reviewed ed6adc5f and corrective81858558, including
actual worker mounts, original receipt/link order, eleven generated inputs,
pre-read file/aggregate bounds, and canonical path rejection. Integrated as
2e470147 and0fe454aea992a663d047410208eb56866dfd2eb7; remote matched exactHEAD.
Combined selection/service/trusted-package suite135passed,14skipped because
private retained package fixtures are unavailable on this Mac (plus explicit
optional gates), one Starlette/httpx deprecation. No actual package composition
was established. Assigned retained-fixture verification on Hera; new service
receipt optimization/namespace/runtime compatibility needs a separate adapter.

[verified: host] Root reran corrected runtime export/bound-ROM113 package suite:
14passed. Private Hall preparation now coherently pins its10raw outputs and
source exports. It is not the newly built stage7 image; that sibling package
is assigned separately and remains non-admissible until fresh-read checks.
No device command/write/reset this segment. Overall audio/release unfinished.

[review limit] Returning evidence in memory is bounded per job512MiB but the
private service can retain64completed records. Before production deployment,
use a service-wide retention budget or private on-disk evidence handles; current
per-file/aggregate limits do not establish a suitable process memory ceiling.

## Matched-profile correction and retained-package verification

[verified: independent comparison] Fresh schema2/7 target above was NOT a
matched Hall profile: catalogue_hall_o2=false/Hall-Os, whereas the designated
Hall build uses Hall-O2. Stopped its offline packaging before a seal/candidate.
All original outputs remain preserved; do not relabel their optimization.
Reviewed exact corrected runner diff: add --hall-o2 in compile and link,
require per-shard and linked exact override maps and true catalogue_hall_o2.
Runner60448560af6f6bbe479a1510b1af4e4cd84e6186f3d01fdd0e0f61425915f446
assigned bounded fresh16-shard build in Hera current-stage7-hall-o2-20261015.
No prior catalogue/link outputs reused; same source/profile/settings retained.

[reported: worker; shared handoff read by root] Actual retained trusted-package
fixtures on Hera provide11required paths,167catalogue objects,11generated
inputs.20tests pass, zero skips, with actual in-memory package composition.
Follow-up obeyed owner16-way request:20unique collected nodes partitioned
2,2,2,2,1x12;16pytest processes, all exits0, exact union/no duplicates/skips.
Hera evidence: /home/claude/.local/share/codex-coordination/handoffs/evidence/mvave-fm1-trusted-fwsc-16shards-20261015.
No new service-generated tuple/composition or hardware acceptance follows.

[verified: passive bench] FM1 still bus1/device113 WL80UBOOT1.00. KA6 remains
ALSA card2. No USB/vendor command, flash/reset or fresh-read admission occurred.

## Corrected profiling build and optimization contract

[verified: independent offline review] The corrected Hall-O2 stage2/schema7
build completed all16 fresh Hera shards and the bounded link. Root rehashed
all10 receipt outputs. Receipt6db18a773eeb48cd18b64d1d01ad184b6a691182f5800bf9e727f2cafcc0fd56,
app855920/860644B (4724B slack), SHA
012726b9e4d6b978f8cf9895a5476ebced6cf0d7218604d48b29d125a07ccb91.
Exact source66c95bb2/tree542445ed; Hall-O2/SixOp-Os, all13 engines, EH+SET,
14 RAM bodies, stage2+engine7+clock3/4, no CPU8/producer5/IRQ6,
120-second return, autoplay/SAVE false. Private package preparation is underway;
no physical performance result or admission follows from this build.

[verified: source/host] Reviewed and integrated workerfba10cd6 as
eee62e6c7e790b4ba8521091363ff010db0cf611; origin independently matched.
Schema2 catalogue manifests preserve per-object optimization metadata and
validate it against recognized override maps and Hall/limiter flags. Schema1
compatibility is restricted to historical receipts without that metadata.
Raw receipt hashes and exact object bytes/file sets remain checked.
Root focused suite50passed14fixture-dependent skips. Actual retained Hera
fixtures are assigned for independent compatibility verification.

[verified: source audit] Current installer worker does not reproduce the native
candidate's executable profile: optimization/RAM flags, explicit identity,
UART MIDI and telemetry differ. D7000 song-diagnostic/Shapes8 allocation and
disarmed SAVE match. Requests support selected content but do not establish
the desired13-engine/Event Horizon+SET default. A reviewed versioned build
profile and separate defaults layer remain necessary before release. See
private scratch/service-native-profile-review-20261015/HANDOFF.md.

## Retained compatibility and bench file-only gate

[verified: retained Hera fixtures] Exact integration eee62e6c passed39 trusted
FWSC/capture tests with zero skips. Root independently checked the16-shard
manifest:39unique test IDs, no omissions/duplicates, all16 exits0. The worker
used four waves of four bounded processes. This verifies historical schema1
compatibility, not a new service-generated package or hardware acceptance.
Evidence: Hera coordination handoffs/evidence/lunar-metadata-eee62e6c-16shards-20261015/manifest.json.

[verified: offline/remote files] Root reviewed the corrected stage7 launch
package, reran10 tests plus6 subtests, staged348 inventoried files to bench01
`/home/claude/fm1-current-stage7-66c95bb-20261015`, and independently verified
every remote file hash and complete recursive inventory. File-only preflight
stopped at a missing build/prepared-profile.json before device access. The
package worker is completing required inputs; do not launch this package until
the exact full preflight succeeds. No fresh paired read, flash or reset occurred.

[verified: review finding] Proposed private native profile1f749165 passed156
focused tests, one existing conditional skip, but root's validation against the
actual corrected target receipt failed target_app_storage. It is not integrated.
Worker is checking the real storage-profile difference and regression fixture;
do not weaken provenance checks or infer actual-target compatibility from mocks.

## Actual profile correction and ROM113 campaign started

[verified: source/host] Reviewed1f749165+748116d5 and integrated553e587f+
26320a41d93c3e4ef85b23a4e75fb79a0e1d9e46; exactremoteSHA verified. Namedprivate
D7000profile forwards matched native options and binds rawreceipt bytes to
versionedsidecar. Requiredcaller modules failclosed withoutinjection. Actual
targetABI storage is220848RGB565/163760indexed, alignedcredit57088 andpool165376.
Separatepolicy preserves legacyD9000values. Actualcorrected receipt passes
profile,builder,APIstoragegates. Root315passed1skip (Starlettedeprecation),
17selectiontests passed withactualfm1-state. FullCI38815188217dispatched;
noCIresult, actualservicebuild, subsetRAMpolicy orreleaseacceptance claimed.

[verified: bench] Added exactpreparedprofile andselectionreceipt missingfrom
originalpackage. Fullfixture now exercises realbuildvalidator;11tests+6subtests
pass. Restaged350files; remoteinventorySHA330726af73e48d08ead2f7642545f032dba60ca5df18ce943efa7a973625ef76
and all350hashes independentlyverified; exactbenchfile-onlypreflight passes.
Campaignpins007e348128fec4bd7341f60b3ce66faea77a38386a25d5cfd5c4a85b783ae3c6.
Rootlaunchedonce PID347366. Bothfresh1MiBreads match28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f.
Boundedinstallation/readback isrunning; noreset observedyet. BASEandcycle are
consumed; inspectdurableevidence ratherthanretrying. Capture/boot results pending.

[verified: inventory/research] Hera's installedpi32v2toolchain hascompiler,
linker,disassembler utilities butnoCPU simulator executable. PublicJieLiAC79
development/debug docs andQEMUsupportedtargets revealnoavailablepi32v2system
simulator; thisdoesnotproveprivatevendortoolsdonotexist. Recommendbounded
hardware-calibrated deadline replay alongsidehostaudiorenders, preserving
uncertaintyaboutcache/memory/interrupttiming. Fullcycleaccurateemulatorwould
needinstructiontimingandSoCmodels absentfromtheSDKreview. Read-onlydesign
taskassigned; notimplemented orrepresentedashardwareaccuracy.

## USB interruption during stage7 install — 2026-10-15

[verified] Campaign stopped after bench USB disconnect at 15:13:08 Pacific;
owner confirmed changing cabling and will reconnect USB. Keep FM1 powered;
no reset/boot/retry has been sent. Passive lsusb still lacks FM1. Frozen BASE
`/home/claude/fm1-current-stage7-66c95bb-20261015` is consumed; never rerun launcher.
Transaction `rom113-current-stage7-engine-render-profile-cycle/transaction`
has state recovery_required, last intent program address607744 (0x94600).
No installation result, capture, boot or new audio acceptance exists. Flash
contains an incomplete app; directory-last sector0x4000 was not reached.
Preserve original paired backups (28483c41...) and target18132474...; do not
assert original hash describes current flash. Next: reconnect identity/retained
loader review, fresh paired mixed-image reads, immutable-region checks and
reviewed resume of this transaction. Root owns device; offline recovery review
assigned. Audio remains FAILED. CI38815188217 pending at last check.


### Interrupted-write evidence and CPU simulation follow-up

[verified] Private interrupted transaction archive copied off bench into ignored
`scratch/current-stage7-interruption-20261015/interrupted-evidence.tar`, SHA-256
`c56f4f2944a643f5bf50faa77596decdab1b25f86e318c3dd41caa2c1a2ae67a`.
Root offline replay and independent review agree on an expected stopped-image
SHA-256 `3fdaaebd73159132f7338db0f7c544935533d914fc59411cc27fe2326bbbb270`.
This is NOT actual device readback. The log contains15,923 matched successful
submit/completion pairs; last program0x94500, next journal intent0x94600 has no
program submit. Boot directory/protected ranges are unchanged in the model.
Fresh paired actual reads and explicit reconnect admission remain required.
No reset or loader-upload fallback is authorized by the offline replay.

[verified] Installed Hera pi32v2 toolchain inventory contains compiler/linker/
inspection tools, no observed CPU simulator. Primary JieLi AC79 compiler/debug
manuals and QEMU's supported system targets do not establish a usable public
pi32v2 cycle-accurate simulator. This does not prove no private vendor simulator
exists. Containers and host CPU throttling cannot reproduce pi32v2 instruction,
cache, IRQ and DMA timing. Proposed near-term approach: functional host renders,
actual-device stage profiling, then explicitly modeled deadline/queue replay.
TIMER4 24MHz conversion is nominal source configuration until independently
calibrated. A standalone RAM DSP benchmark is plausible but needs a reviewed
runner, memory-ownership/link audit and bounded upload/result-readback path;
existing exact recovery probe does not provide that general facility. Offline
reports: `scratch/cpu-speed-replay-design-20261015/HANDOFF.md` and
`scratch/ram-dsp-microbench-feasibility-20261015.md`.

[verified] CI38815188217's32-bit engine test job completed4289pass,16skip,
2xfail,1failure: vendored Plaits closure pin differs after documented diagnostic
RAM-placement annotations. Build passed; virtual app job was skipped after the
failure. Assigned focused provenance-preserving fix; do not simply accept a
new digest or weaken the upstream DSP reference check. Other CI jobs pending.

## Power-loss update, 22:29 UTC

[verified: owner] Power was also interrupted; display is blank. This invalidates
all retained-RAM-loader continuity assumptions. Passive lsusb has no FM1; no
SG node is available. No reset, upload, flash, MIDI or capture command followed
the interrupted install. Direct data-cable confirmation is pending.

[verified: source review] Existing Pico 2 W notes record successful programming
and repeatable late console output, but state=FAULT and unresolved external GPIO
wiring, not USB_KEY recovery acceptance. If ROM enumeration cannot be obtained,
physical app-independent recovery remains a real blocker, not a software retry.

[verified: source/CI] d3a54fe2 includes the Plaits pin correction and two MIT
helper-header provenance corrections. Earlier-head ASan completed with4289pass,
16skip,2xfail and the single known Plaits pin failure. No sanitizer runtime
failure is shown in that result. Fresh generated WASM and full GPL gates are
assigned to Hera; exact final-source CI remains required.

## Browser refresh integrated

[verified] Worker718637ca reviewed and integrated asdde25270; origin branch
SHA matched dde25270c3bc5fde4132ddccfd6cf2b401a633fb. Only fm1.wasm, its
build record and meta.json changed. Full web catalogue/GPL enabled; 108 parity
scenarios passed in the retained Hera record. Hera reported all11 GPL switch
checks passed; root independently matched artifact/source hashes and ran
CI-mode freshness:1passed, no warnings after removing an ignored generated
vendor.cpython-313.pyc cache that the engine hash scanner had included.

[verified] CI38817684903 dispatched on dde25270. Results are pending; this
is not hardware timing, audible acceptance, release or deployment evidence.
Passive USB still lacks FM1 at22:30UTC after direct-cable request. Owner Pico
GPIO wiring/alternative physical recovery hardware clarification is pending.

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

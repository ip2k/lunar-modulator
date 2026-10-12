# Exact SDK recovery-trace image admission and install successor

Status: design/source investigation; no new hardware permit or production opener
is prepared. The parent owns device work, commits and push. This is a personal,
non-commercial private SDK experiment. [verified: current task authorization]

The old bound SDK gate pins app `991b569d…`, ELF `8832aa46…`, complete target
`df6c963e…`, and the original fixed-backup adapter. The frozen rehearsal and
install-only runner cannot admit another image by relabeling a receipt. [verified:
`tools/fm1_bound_sdk_diagnostic.py`, `tools/fm1_sdk_rehearsal.py`,
`tools/fm1_sdk_install.py`]

## Exact candidate and immutable dependencies

Proposed app SHA:
`76382f531491b63a9cb75258ae9299185219b55f201e5110a74eb03ab328bf44`.
ELF SHA:
`e9d54172bda7dd085fbd1a46ef35c353210f75ec5f621a3e352a075d7f2a6035`.
Trace nonce `6b5482dbb66b5f45ed73e2f26c4a4657`; ELF-allocated record
`0x01c02880..0x01c028c0` (64 bytes); diagnostic stage symbol `0x01c03418`.
Artifacts reside in `build/sdk-recovery-trace-hera/native-enabled/`; its
`build-manifest.json`, key/link audit, image audit, native listing/map and the
trace lane's `evidence-index.json` must be literal-pinned after independent
native/allocation acceptance. [reported: trace author; manifest read here]

The initial design required emission of a new complete raw NOR target by
the reviewed exact raw emitter and independently validated against stock
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
The unchanged emitter has now derived exactly 30 changed sectors from the
actual bytes; independent target acceptance remains separate. [verified:
`build/sdk-trace-install-hera/emitter-evidence-v1/target-v1/receipt.json`]

## Minimal separate successor

1. `tools/fm1_bound_sdk_trace.py`: offline actual-file admission, with exact
   app/ELF/nonce/allocation/build-audit pins and fresh matching stock-backup
   provenance. Recompute the unchanged SDK key/native/raw geometry gates; add
   trace-specific evidence only where the old gate does not describe the record.
   Build separate exact-instance install and restore policies using the reviewed
   transaction/framing primitives. Preserve stock SPL/config/OTA/protected tail,
   direction-bound payloads and application directory sector `0x4000` last.
2. `tools/fm1_sdk_trace_install.py`: strict new campaign and one-use install-only
   runner. Reuse only source-pinned `f696…` SG framing/binding through a new
   prepared object; do not alter its globals or invoke its old factory. Validate
   both directions first, then run install and verify the full new target. Add
   no ROM entry, upload, reset, retry or boot-success claim.
3. Private closed prepare/capture template under a new ignored build directory:
   literal pins are absent until exact candidate, fresh session and recovery
   packet review. It must issue unique destination/marker, own capture lifecycle,
   one child and preserved nonzero/ambiguous failure evidence.

The factory binds a fresh successful FM-1_092 identity/soft-key entry, full
8,757-command fixed-loader replay, two complete matching stock dumps, exact
loader/profile/reader source pins and the **new** USB/SG identity. Existing
historical receipts are evidence of past work only. After insertion of Cynthion,
neither the old USB path nor old SG identity is presumed usable. The operator's
no-later-command attestation is scoped to the new backup. [inferred: successor
design; verified: existing source requirements]

All source/evidence must be checked before opening and rechecked across durable
mutation intents. Prepared/policy objects require exact identity registry
membership; copies acquire no authority. Any uncertain command closes/latches
the handle, keeps the marker and forbids replay. The initial full-NOR read must
equal stock before any write; final full-NOR read must equal the new target
before success publication. Genuine stock restoration must be preflighted, not
claimed performed. [inferred: required preserved behavior]

## Remaining gates and limits

Before source activation: independent trace native/allocation review, unchanged
raw validator acceptance of exact candidate, exact emitted target/ranges, new
source/factory review and 16 isolated Hera chunks plus genuine private-file
modeled composition. Heavy work uses the pinned `7e32…` image, source read-only,
no device/network/privileged access and retained exit/OOM/removal evidence.
Before hardware: fresh entry/backups/current session, exact concrete install
packet and recovery packet. Reset, retained trace reads and recovery after this
new target need separate successors; the old target-reset and returned-ROM
helpers hard-pin the old image and stay frozen. Physical display/recovery, warm
recovery after a corrupt app and USB_KEY availability remain separate claims.

Semantic status/config were read during this task: both MCPs select the shared
primary checkout, not this worktree; Serena exposes C++ only and Rarefaction's
Python server was not started. No retarget/restart occurred. Bounded direct file
inspection is the fallback; no semantic worktree coverage is claimed.

Owned task paths are distinct new modules/tests/templates and this note. Parent
checkpoint for the preceding accepted model is
`a6164e5369e9cfb940ad1f456b52b3b7786b668d` [reported: parent push verification].

## Saved closed implementation and raw emission

[verified] The new policy/source files are saved with exact own-instance
registries. They reuse frozen `f6964845…` SG framing through duck-typed
prepared fields, without invoking the old image factory or replacing its
globals. The frozen SG constructor checks the new prepared object's `check()`,
exact policy membership, header/mapping/bridge and binding. It does not require
the old Prepared class or old image hash. The new policy subclasses the pinned
old policy privately; only actual-file factory instances are entered in both
its own registry and the inherited constructor's registry. Ordinary copied
objects retain no authority. Python caller code remains outside the security
boundary.

The image allocation check uses the exact native symbol
`lunar_sdk_recovery_trace_record`, size 64, address 0x01c02880, entirely contained
in `.ram0_bss`, as shown by the current ELF/map. The new policy freezes the
build manifest, image audit, native independent report, actual app/ELF, all
repository `/source/` files in the build manifest, build/audit sources, stock
reference files and old reviewed protocol/dependency files. [verified]

The unchanged emitter ran on Hera in image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
2 CPU/2 GiB, network none, no devices, nonprivileged, exit 0, OOM false and
container removal exit 0. Its source/native archive has 77 files, SHA
`0e6294428d724098772ede82fb4c7c3eaed690f8907e732f72e736eaab673b40`.
The complete 1 MiB target SHA is
`5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d`.
Exactly 30 changed sectors are 0x4000..0x21000 inclusive; the application
directory is processed last by the transaction plan. Stock SPL/config and all
bytes outside derived application geometry remain covered by the unchanged
emitter's validation. The emitter receipt/input inventory uses historical
matching stock backups; it does not establish a new physical session. [verified]

Evidence: `build/sdk-trace-install-hera/emitter-evidence-v1/` contains the
private target/receipt, input hash inventory, run/inspection/removal receipts.
The private emitted files were root-owned by the container; only their file
ownership was changed to retrieve them off Hera. No device command occurred.

New installation admission requires a fresh completed full 8757-command stock
backup replay, <=120s at initial factory admission, exact new USB/SG binding,
operator no-later-command state, and <=10s final preparation-to-open. The
120s admission age is not reapplied during the 900s bounded operation. Before
opening, an exclusive durable `.sdk-rehearsal.consumed` marker shares the old
consumption boundary. Source/campaign/policy evidence remains frozen, including
a second check after mutation intents; live FD/sysfs binding and marker checks
continue for all requests. Install-only results bind the trace image, nonce,
record geometry, full target readback and sector order; boot, display, physical
recovery and kernel exclusivity remain false. [verified: saved source; runtime
acceptance pending]

At this checkpoint all new policy/worker activation literals remain `None`.
The closed authority/drift unit gate is staged in 16 isolated Hera chunks under
`build/sdk-trace-install-hera/`, version `closed-v1`. The genuine new-byte
factory/model test is saved but awaits independently accepted literals and
private trace/native-report mounts. No firmware build or old source changed.

The next physical dependency is the parent's existing vetted normal identity
query -> one soft key -> same-port ROM -> source79 fixed-loader dual stock
backup, with a newly issued exact campaign and topology after Cynthion wiring.
The old campaign cannot stand in for it. A distinct trace target core-reset
factory and returned-ROM proof are parent-owned follow-ons; the injected-only
trace reader cannot claim their absent authority.

## Closed-source gate and target acceptance

[verified: offline Hera] Closed version `closed-v1` passed 37 unique cases in
16 chunks plus one separate unit smoke. It deliberately excludes the genuine
trace-image factory case while activation pins are `None`. The 1714-file
archive SHA is
`31121c93d647f8545fbfeae26bb0713df5b53448148d339793ccdc64c7f48761`;
plan SHA is `5d89c1a2330330612c54712dc38f08efecff84ca29982dfe78285b7ab0deeb5c`.
All 18 containers (collection, smoke and 16 chunks) used the exact image above,
2 CPU/2 GiB, source read-only, network none and no devices; each exited zero,
reported no OOM and was removed. A fresh structured label lookup also returned
zero container IDs. Receipts are in `evidence-closed-v1/`,
`aggregate-closed-v1.json` and `cleanup-closed-v1.json` under the ignored gate
directory. This establishes authority/drift unit behavior, not a live install.

[verified: independent offline review] Complete target/native preservation
acceptance is saved in `build/sdk-trace-install-hera/independent-target-review.md`,
SHA `b903322ef33b4c8a93f025e1697180e0b916bd1bbdd548393afb9b070237b7bd`.
Native allocation/instruction review is
`build/sdk-recovery-trace-hera/independent-review.md`,
SHA `cf706b9c95ea0635a9d4521b04d3d42730b80b0dfd97070931892ae163c5d690`.
The latter confirms the conditional native trace mechanism, while the former
strictly parsed/audited the exact new image and all protected stock bytes.
Neither establishes physical execution, current loader provenance or fresh
backups. The next source successor binds these exact accepted artifacts, then
runs the genuine new-byte factory/full-install model with transport and time
explicitly modeled. Existing sources and consumed receipts remain frozen.

## Exact accepted-byte successor staged

The closed gate was checkpointed and pushed at
`8f687392ab0f2be4722a04e85ffdfbdd6f7f7338` [reported: parent remote SHA
verification]. The separate successor binds only the accepted target, build
manifest and native-review literals and then its own policy SHA. Frozen source
SHA `54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835`
(policy), `6be77170f28fff7d7ca9c794ac44592a9c4bd4bae2cc2affd22a1cebf0936720`
(install worker) and
`526f5bb719e8f00ca88046910cdb2cacf127ee68b96f1e538afbf0435da4a27e`
(test) are saved pending runtime and independent review. No frozen incumbent
source was edited or globally monkeypatched. [verified]

Exact archive `a48952e653f3d35c34117dd129ec59c55c06ceaccaa82f5b3ade197abcb2c49e`
contains 1714 regular source files. `final-v1` collected 54 unique cases,
distributed across 16 chunks. Strict actual private inputs and exact native,
target and review mounts are required. The smoke selects only the genuine
new-byte factory/full-install case before those chunks run. Factory source
checks and all image literals remain unchanged. Historical wall-clock admission
and live SG/NOR transport are modeled; the factory also rejects copied actual
policies and a changed actual identity file before any transport construction.
Sixteen added synthetic manifest/ELF cases reject metadata/nonce and allocated
span incoherence; their ELF model is explicitly a unit boundary, with actual
ELF allocation checked separately by the genuine case and native review.

Insight after implementation: the reusable SG layer is image-independent,
but its registry and frozen policy files are part of admission. A private
subclass with its own instance registry allows a new exact image without
changing the incumbent image's constants or replaying its physical receipts.
The fresh-session plan can use the unchanged vetted identity/soft-key and
source79 backup adapter with a new topology/entry campaign. The root's new
target-reset/returned-ROM authority remains a distinct dependency for trace
reads before loader upload. No source test establishes CPU/SPL acceptance,
pixels, warm recovery after partial NOR or USB_KEY availability.

## Next exact recovery envelope

[design, not execution authority] Before a physical install, a separate returned
trace-target backup and stock-return worker are required. The legacy stopped
choice backup/restore envelopes bind the old target and remain frozen. The new
backup can reuse the pinned fixed-loader SG framing/upload inventory through
its own exact-instance factory. Its evidence-only admission must consume the
parent's reviewed new install/reset wire proof, fresh same-port ROM snapshot,
completed or strictly stopped bounded trace-read receipt and owned capture,
original complete-install journal preservation and a distinct current passive
connection witness. No loader upload precedes trace capture. A consumed failed
read must retain its exact prefix/ambiguity and permit only the separately
reviewed recovery route, without retrying the read or deleting markers.

The new backup must require both complete 1-MiB dumps to equal the exact target
`5dbada…`, with exact fixed-loader/profile/source/inventory and new USB/SG
binding, private exclusive receipts and its own durable one-use marker. It
grants no NOR write. Current witness age is checked at open; immutable original
boot/read evidence and live FD/sysfs identity persist throughout the bounded
backup. Historical admission timestamps cannot be refreshed.

A new stock-return worker must bind that completed dual-target proof to the
original genuine stock manifest/dumps/reference and exact new SDK app/ELF/plan.
It preserves the original complete-install journal before any restore, requires
a full initial target readback, writes only the same thirty derived sectors
with 0x4000 last, verifies sector readbacks and the full stock hash, and seals
its completed result/journal/transcript. The reviewed new policy already
admits both directions, while a separate worker supplies the new live binding
and restore-only transaction. The root's boot evidence helper needs an explicit
preserved-install-journal option for later completed-proof reconstruction; it
must separately verify live complete-restore state. Stock reset and identity
observation remain another exact one-shot gate. No partial-NOR, CPU/SPL warm
recovery or USB_KEY authority follows from this design.

## Final successor runtime completed

[verified: isolated model] `final-v1` passed all 54 unique planned cases in
16 chunks and one separate genuine private-file smoke, with zero failures,
errors or skips. The smoke took 167.40 s. The exact same-version actual case
also passed inside shard 5; both summaries hash
`236fa3659680c2b89f05c3dfe637fc6ea9813074d623349e1de631c83d420cf0`.
It executed unchanged actual production factories with the exact new app, ELF,
manifest, native review, protected stock reference and target. Only historical
admission time and SG/USB/NOR transport were modeled. It asserted the complete
model's final flash bytes equal the full target, one handle closed once, 10,653
commands, 30 erases with directory last, 480 programmed pages, initial complete
stock reads, sector verification and final complete target readback. Commands
and results are retained. No final standalone full-NOR dump is exported by this
model; the full-byte equality assertion and page response hashes remain the
actual model evidence. Boot/display/physical recovery remain false.

Aggregate SHA is
`6e9edb59bbe0238d3496af5a765bd6757b5ed56d9711fea6687c95d669b88998`;
plan SHA `f4f614b8d4625937d8559446252c7e7350deee7235ede8372629b3c5350337db`.
All 1714 archive file pins were checked, and the three frozen candidate source
files still match. All 18 collection/smoke/shard containers used image7e32,
2 CPU/2 GiB, source read-only, network none, no devices and nonprivileged; all
exited zero, no OOM and named removal exit zero. A fresh structured exact-label
lookup confirmed empty IDs, SHA
`88d0a02c0dc9d8e81b7ed0cc7e660a5e18bfd3a4fcd791b11bc4847aafc11808`.
`input-inventory-final-v1.json` retains exact native/target/review/supervisor
pins, and `author-check-final-v1.json` independently rechecks this local
archive/XML/isolation/cleanup inventory. Complete receipts are in
`build/sdk-trace-install-hera/evidence-final-v1/`, with aggregate/plan/snapshot
and supervisor files beside it. Independent new-source/runtime acceptance is
pending; physical sessions and every future recovery/boot/read gate remain
separate.

## Final independent offline acceptance

[verified offline] Startup resolution independently accepted frozen policy
`54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835`,
installer `6be77170f28fff7d7ca9c794ac44592a9c4bd4bae2cc2affd22a1cebf0936720`
and tests `526f5bb719e8f00ca88046910cdb2cacf127ee68b96f1e538afbf0435da4a27e`.
The final report is `build/sdk-trace-install-hera/independent-install-review.md`,
SHA `5ca89303605ed0cdf3ec81c4b6c0a3dd0c3a9e8b84b64e5933ea6c9981c28d95`;
its replay check is `8d05c1de559e429277b47a3e2c40cd2a11d6ea2824e39f4ac830c6b38c29cea0`.
It independently verifies 1714 archive pins, all 54 exact XML cases in16 chunks
plus actual-private modeled smoke, 18 isolation/cleanup receipts, 10,653 modeled
command pairs, full stock/target response hashes,480 payloads and30 directory-last
erases. This supersedes the preceding pending-review status. Ordinary inherited
transaction file reads retain the reviewed private-owned exact-directory premise.
No physical installation, CPU/SPL recovery, boot or display acceptance follows.
Root owns source commits/push and future hardware activation.

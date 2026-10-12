# Recovery after the actual stopped chooser and distinct RAM read

Design and evidence admission, 2026-10-11. This dependency does not delay the separately authorized
two-read RAM milestone. No hardware was opened, no command was sent, and no old
source or marker was changed. Root owns activation, commits and verified pushes.
The branch is feature/2026-10-11@installable-firmware; the last parent-confirmed
backed-up checkpoint is aca0e686d60e2224993ee4450919a14b0702f079. The new closed
stopped-restore lineage helper's independent 33-case gate is accepted separately.

Insight before implementation: a historical kernel-generated failed PREVENT
ALLOW command is evidence to interpret, not another command to admit to the
loader inventory. The original reset, chooser stop and RAM-read attempt must
remain distinguishable from the subsequent fixed-loader backup and restore.

## Exact inspected source boundary

[verified: local files] Frozen existing adapters:

- tools/fm1_returned_rom_backup.py:
  afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be.
- tools/fm1_returned_rom_stock_restore.py:
  f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33.
- tools/fm1_diagnostic_detached_probe.py:
  8fb33694f3daa26e3a824f33f1b9fa8d646dc5e9295795ea8fff6ea3a983b733.
- tools/fm1_sdk_rehearsal.py:
  f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4.

[verified: independently accepted source/runtime and actual two-read receipt] Root's distinct
tools/fm1_diagnostic_stage_resume.py currently hashes
70d57d7a3294794ebc84647666bd22f195822027a0c96c22a3ed8495fbe53279.
It privately loads exact 8fb and 8ad native transport, replaces only the
historical wire verifier with the stronger exact paired actual-chooser verifier,
and uses its own registered Prepared/consumed marker. Its only live operations
are INQUIRY 36 bytes and FD07 32 bytes. The historical single failed 1e prevent1
and immediately matching 05/24/00 REQUEST SENSE are never live operations.
The old adapters continue to reject this actual lineage.

The final stage source/runtime review is
build/diagnostic-stage-resume-independent-review.md, SHA
9d5805f909dc816df4919e7c1a9e11d6a60b2ba696667ee562581a7855a2ede7.
Root separately executed exactly two successful reads and retained the actual
receipt and owned capture. The new admission literal pins the accepted stage70d
and actual bound wrapper770; it grants no opener authority.

Semantic tools still select the primary checkout, not this worktree. Rarefaction
Python readiness there and Serena's cpp-only coverage do not provide semantic
coverage here. Selection was preserved; this design uses bounded actual-file
inspection of the stage factory, afeefe factory/FixedSG/inventory and f583
policy, transport, worker and completed-restore replay.

## Smallest distinct admission

Create a new evidence-only admission module, then a new backup and restore
adapter; leave afeefe/8fb/f583 unchanged. Admission must consume the exact old
chooser path/pins and the distinct resumed-read campaign, receipt, consumed
marker and owned capture. It must not call stage prepare again: completed and
stopped attempts have legitimately consumed the new marker.

The proof interface should provide canonical original snapshot and original SDK
inputs, original backup manifest SHA, private parent, original rehearsal campaign
SHA, original install journal SHA, stage outcome, immutable positive evidence,
exact absolute absent paths, and check(). It grants no opener capability. An
attempt's validated admission timestamp is historical; check() rechecks evidence
without aging the original snapshot again. Recovery issues a separate passive
current witness with unchanged original USB/SG identity and its own observed_at.

The current stage ReturnedProof delegates snapshot/original_inputs/manifest/
private_parent/policies and retains historical. Its historical proof already
contains the two journal/rehearsal identities required by backup completion.
For post-restore historical reconstruction, a new isolated evidence-only loader
may wrap only the privately loaded 8fb validate_returned_state call to supply the
exact preserved install journal. The fresh backup admission supplies no preserved
journal override. This is an explicit reviewed callback on a private source
instance, never a mutation of the original file/module or stage opener registry.
If a separate stage receipt helper supplies this interface, use that exact pinned
helper instead; coordinate one owner before implementation.

Completed stage proof requires the exact two request/completion pairs, status,
sense, sizes, raw/decoded/inquiry hashes, completed event, successful child exit,
durable result and owned capture lifecycle. Stopped proof requires a strict
zero/one/two-request prefix, one terminal caught ambiguity, failed child/stop
receipt, closed owned capture, no additional command and absent success result.
An INQUIRY or FD07 failure remains read-only and must leave the recovery route
available without retrying the RAM read. Missing terminal or capture evidence
does not justify relabeling an attempt as unattempted.

## New fixed-loader backup envelope

Proposed schema 1, kind fm1-stopped-choice-fixed-loader-target-backup:
adapter_sha256; returned_admission_path and SHA; loader/profile/profile-source
paths; connection_witness_path and SHA; active_session_state exactly
same-returned-rom-after-bounded-stage-no-loader-upload-no-later-commands;
receipt_path. Admission itself records exact original chooser and stage attempt
pins/outcome, so the backup does not pretend to be an old soft-key or old optional
probe campaign. Final field names wait for the stage evidence helper freeze.

The new factory freezes its own source, stage/admission source, all SDK policy
files, original stock/target/plan and candidate dependencies before opening. Its
exact-instance WeakSet and distinct marker authorize only its own Prepared.
It reuses the pinned afeefe inventory and FixedSG body through a private source
instance with an explicit new Prepared/require_prepared boundary. The new worker,
manifest and completed validator own their distinct envelope and marker; they do
not call the old factory or old worker's marker namespace.

Inventory remains exactly 8757 operations: ROM inquiry, all 47 exact candidate
512-byte uploads at 0x01c02000, one jump, FC14/FC0A and two complete 1 MiB FD05
target dumps with FC0A every 16 pages plus end of pass. Loader SHA/profile/source
and inventory digest remain the reviewed fixed pins. Both durable full dumps must
equal df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db.
Mismatch/ambiguity closes and consumes with no retry; it does not publish a
successful manifest. Fresh current witness/open and binding bounds are distinct
from the historical chooser timestamp and the 900-second backup window.

The evidence-only completed validator replays every intent/completion/hash and
both dumps, validates the distinct consumed marker and success exit, and freezes
all positive/negative provenance. It accepts a preserved original install journal
only for historical completion validation, never fresh opener admission.

## New restore envelope and gates

Create a separate restore-only schema and factory pinning the new completed
backup helper. Require its successful exit, exact new USB/SG/loader binding,
genuine original stock/SDK/candidate policy, original complete install journal,
and preserved private journal-before-restore. Own a distinct restore marker.

Reuse the reviewed f583 Policy/RestoreSG behavior and pure receipt replay in a
private exact source instance; the new factory, registry, binding policy and
worker own the new authority and envelope. First actual read must verify all
4096 target pages before any mutation. Only the same 30 addressed sectors are
writable, with 0x4000 directory last. Final actual full NOR must equal
96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4.
Stock SPL, OTA/cfg and all protected ranges remain exact. Positive source/file
pins and negative stage-result/ambiguity assertions survive durable intent and
binding checks. A subsequent reset needs a separately pinned completed-restore
helper; baseline bytes alone do not establish the current loader lineage.

## Tests and acceptance still required

Bounded cheap adversarial tests cover exact instance copies, wrong actual chooser
or stage source/campaign, extra live 1e/vendor command, malformed prefix/status/
sense/CSW, missing capture close/exit/result, swapped witness USB/SG, original
timestamp refresh, source drift and positive/negative evidence appearing after
durable intent. One genuine private-input composed model is sufficient to prove
actual factory integration; parameterize cheap variants rather than duplicating
full modeled installs unnecessarily. The actual stage receipt should also be
replayed in a file-only private factory smoke with unchanged source hashes.

Run focused tests in 16 Hera chunks, retain exact source archive, unique node/XML
coverage, private-fixture scope, container resources/OOM/removal and independent
review. Model success proves source/evidence enforcement, never device boot,
display, recovery, RAM retention or kernel exclusivity. Physical activation stays
root-only after exact current packet and independently accepted gates.

Next dependency: final stage adapter/receipt-helper API/source and actual terminal
receipt/capture, coordinated with diagnostic_path_review. No hardware command is
needed to finish this design or build the closed software scaffold.

## Recovery availability boundary

[verified] Existing bench evidence has not established that the stock SPL returns
to ROM after a warm reset of a partial or corrupt application without USB_KEY.
The complete diagnostic target returned to ROM on the owner's unit, but that
observation does not prove the failure branch or diagnostic execution. Physical
USB_KEY remains untried. Retained-loader repair avoids resetting a partial app;
a new-ROM repair requires independently observed ROM lineage. The pure NOR
model and full byte restore checks cannot establish CPU/SPL recovery availability.
No flash fault injection is part of this lane.

## Historical closed scaffold checkpoint

The new `tools/fm1_stopped_choice_recovery_evidence.py` and focused test module
are saved. At that V1 checkpoint stage and exact bound wrapper pins were `None`; factory
admission therefore rejected before reading any evidence. The pure receipt/capture kernels
check exact two-read prefixes, durable completion, raw/decoded bytes, child stdout,
owned capture chronology and unchanged historical/current witness identities.
The first cheap 16-chunk Hera gate was prepared. Genuine private-input composition,
final stage66 acceptance, exact bound wrapper pin and independent source/runtime
review remain required before removing those closures. No hardware was accessed.

Checkpoint limit: the first pure Hera gate collected and passed 62 unique cases
across 16 chunks in 2.62 seconds; aggregate a98ebdfc88924d2594be9f4c55612460b22f3c0386d945bd5d72ba1cd3f39c5c.
This is modeled receipt evidence only. Independent review found missing negative
artifact checks for stopped prefixes and pending result publication. Source
repair, a second gate and genuine private-input composition remain necessary;
the activation pins stay closed. Root retains this as a WIP checkpoint.

## Final admission candidate and exact Hera gates

[verified: source files] The evidence-only source is
`tools/fm1_stopped_choice_recovery_evidence.py`, SHA
8875f0f0ab625d437d8596d1eb28a157f9bab931d6ffeffc74fb28e16fe27340.
Pure tests SHA54ca49d86e0cd816edafa8dfcac9f0d855a43fa5e3433400e9abf6d02b13f668;
`tests/test_stopped_choice_recovery_actual.py` SHA
3c7be4df61d8174ea4837b68faa6a3ee6e7b0ecaf3bded628737271266d2f9c8.
The repair retains positive or negative raw/decoded/pending evidence according
to the exact publication phase. Consumed missing/empty logs are a distinct
pretransport zero-CBW branch requiring exact owned capture, nonzero child and
all success artifacts absent. Nonempty malformed prefixes remain rejected.

[verified: Hera containers] V2 passed90 unique pure cases in16 chunks, no
failures/errors/skips,2.67s; it retains the repaired pre-literal source separately.
V3 passed95 unique cases in16 chunks plus one exact actual-file factory smoke,
no failures/errors/skips,5.97s. All1688 archived files were hash-checked;18 exact
image containers used2CPU/2GiB, network none, no devices, nonprivileged, exited0
and had no OOM. Named removal receipts and a structured fresh empty label lookup
are saved. Source and original historical timestamps were not refreshed.

Artifacts are `build/stopped-choice-recovery-evidence-hera/` with the source
archive, snapshot, plan,16 XML/log/run receipts, smoke,18 inspections/removals,
aggregate and own coverage checks for each version. V3 archive
102d8fc5dfb1ae2c3ad15f3f28447b533c19efd0130156443c1e279f3db15c5a; snapshot
ad20302e2905ffdbf1db306f265a672d4b3451c8a0183a09e5bd16ebb157f0a9; aggregate
d86371304df520e37a2f1892ef99ae9acc78d2de562853762df90275baeeb564; cleanup
8fc63c66b70a6e4f8140111b5e238342319fb42b899a6f8e901b7393f9abec1c.
Image sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d.

The physical-file smoke consumed the exact root-exportedb266 RAM evidence and
unchanged literalstage70d/wrapper770 factory, froze113 positive files and32
absent paths, and preserved originale79 snapshot,1791775862.0725162 admission
and0d797 install journal. This smoke only reads private files. The four composed
completed/stopped/consumed-empty/consumed-missing variants use injected transport
and disposable wrapper substitutions; their captured wire is modeled. These
checks grant no upload, NOR, reset, boot/display or recovery acceptance.
Independent final evidence review is pending; no new backup/restore literal
authority is granted by a passing admission test.

Insight after implementation: a caught stop can occur after both read completions
but during file publication. Recovery must preserve exact surviving bytes and
missing artifacts at that phase; syscall or file presence alone cannot be promoted
to successful publication. This distinction also lets a consumed pretransport
read attempt remain recoverable without rewriting its marker or history.

## Dependent ownership after RAM admission

Diagnostic lane owns `tools/fm1_stopped_choice_backup.py` and focused tests.
This lane owns `tools/fm1_stopped_choice_stock_restore.py` and focused tests.
New backup uses the proof above, separate fresh passive same-ROM witness and
its own marker. New restore will pin the completed-backup helper, reuse exact
privatef583 transport/policy/replay kernels through an independently registered
new factory, and own the restore schema/marker/worker. The new completed helper
must preserve the original journal-before-restore for any subsequent reset.
Existingafeefe/f583/8fb sources and consumed markers remain frozen.

## Independent admission acceptance

[verified: independent archive/XML/resource replay] Final source 8875, pure tests
54ca and actual tests 3c7 are accepted for evidence-only admission. Review
`build/stopped-choice-recovery-evidence-independent-review.md` SHA
6ce3437fb744d7778eb0c36201720456c1eaf9fa4b55692b7d0c7e5e5e622a9b
and independent evidence check 3b7ae96b confirm all 1688 archive pins, 95 unique
XML cases across 16 chunks plus the actual-file smoke, 18 isolated no-OOM
containers/removals and the structured fresh empty lookup. This supersedes the
pending final-review sentence above. No device was opened by either test lane;
new backup and restore authority remains a separate reviewed dependency.

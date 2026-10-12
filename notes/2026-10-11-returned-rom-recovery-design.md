# Returned-ROM recovery after the exact diagnostic install

Personal, non-commercial. This began as a read-only design, requested by root while
source regression gates run. No hardware traffic, new transport activation,
old-source edits, commit or push was performed by this lane. Root has authorized the separate implementation and owns independent review,
physical staging, commits and verified pushes.

The bounded next milestone is: after the exact SDK target has been installed,
reset requested and a new mask-ROM device observed, admit that new connection,
optionally retain the exact diagnostic-stage probe, upload the same reviewed
fixed loader, obtain two matching complete target backups, and restore the
original stock NOR. Neither installed target readback nor USB ROM enumeration
alone proves diagnostic execution, display, recovery cause or stock boot.

## Verified source constraints

[verified] `tools/fm1_recovery_campaign.py` is synthetic-only. Its reopening and
fault catalog are model tests, not a physical provenance factory. The original
`fm1_fixed_loader_backup.py` requires the real ordered five-event successful092
softkey receipt, at most600seconds old before open; it must not be handed a
manufactured receipt for this new ROM return. It binds the exact new SG/USB
ancestry before and after each operation, but its published manifest still
identifies the original softkey path. Its fixed47 uploads, jump, FC14, FC0A and
dual FD05 inventory is usable protocol evidence, not permission to bypass its
entry validator.

[verified] `raw_flash_profile.profile_dump_fixed_loader` classifies stock092
content and requires the recorded stock payload fingerprint. Two df6 target
dumps must not be represented as a stock profile. `fm1_bound_sdk_diagnostic`
validates original stock, raw target, native link and fixed-loader evidence;
its constructor also seals the original backup campaign/entry/USB binding.
`fm1_sdk_rehearsal` similarly binds the original backup and supports one exact
install/restore rehearsal. Passing either an old manifest with a new USB
identity or a new target manifest to the old stock classifier is invalid.

[verified] `fm1_flash_transaction.run_transaction` supports restore from an
actual complete/install journal. It reads the entire NOR at start and finish,
checks protected bytes, derives permitted sectors from the sealed plan, and
processes commit sector0x4000 last. A fresh prepared journal requires current
NOR to equal baseline. A complete journal checks only protected bytes at the
initial preflight, so a new exact-target restore factory must additionally
require that first full read equals the newly verified df6 target pair before
allowing any erase. Do not fabricate a prepared-to-complete journal transition.
The existing worker has valid resume semantics, but this initial design admits
only the exact complete target, not arbitrary partial app content.

## Smallest proposed split (new files; old factories unchanged)

1. A distinct returned-ROM evidence factory and fixed-loader backup adapter
   (`fm1_returned_rom_backup.py`, proposed). Reuse pinned, reviewed request,
   SGHeader and discovery/binding mechanics as dependencies, with its own
   factory-only exact-instance registry and precise new schema. Never invoke
   original79 prepare with a fake softkey record. Factory checks all source
   and private input hashes before open and again at the durable upload/jump
   boundary. Same original physical unit/port is an explicit operator premise;
   topology and known NOR contents are not a silicon serial-number proof.
2. A distinct restore-only factory/SG envelope
   (`fm1_returned_rom_stock_restore.py`, proposed). Recompute the unchanged
   original-stock SDK validation using the actual old private artifacts;
   independently validate new ROM provenance, upload/read inventory and new
   matching target backups. Its own policy/session constructor seals the new
   USB/SG binding. It must not edit471, f696,79, their authority registries,
   original manifests or consumed markers. Reuse guarded request/framing and
   transaction methods only behind this separate authority.

No new loader bytes or generic memory/write interface is needed. The candidate
is exactly24064bytes, fe6d1; upload47 fixed512byte pages at0x01c02000 through
0x01c07c00, extent ending0x01c07e00, then jump0x01c02000. Optional stage evidence
at0x01c033d8 must be collected before upload because this span is overwritten.
The stage probe remains a separately reviewed two-command campaign, not part
of this backup allowlist. Its positive classification must not become a
precondition for stock restore: a failed diagnostic still needs recovery. If
probe traffic occurred, require its exact exit/log/result/inventory and stable
same-ROM binding; stopped/ambiguous probe is not an automatic upload retry.

## Proposed exact campaign and receipt handshake

The following is a design schema to review, not an executable campaign.
All paths are absolute, direct regular bounded NOFOLLOW/NONBLOCK inputs; JSON
has exact keys/types, finite ordered times and no additional executable fields.
Each evidence reference is `{path, sha256}`; source map values are literal
reviewed hashes, not self-declared authority.

Returned-ROM backup campaign fields:

- schema1; kind `fm1-exact-target-returned-rom-backup`; adapter_sha256;
  source_sha256; original_stock_evidence; install_evidence; target_reset_evidence;
  returned_rom_snapshot; optional_stage_probe (null or exact reviewed envelope);
  loader_path; profile_path; profile_source_path; usb_binding; receipt_path;
  origin_consumed_marker; active_session_state.
- original_stock_evidence pins the accepted original pair/manifest/campaign/
  identity/log/reference/app/ELF/native audit and immutable transaction plan;
  install_evidence pins successful exit0, exact completed install result,
  full replayable SG/checkpoint log and complete/install df6 journal snapshot.
- target_reset_evidence pins the actual oneFC0Carg1 campaign/log/exit/capture and
  accepted request outcome. Initial admission should use the already reviewed
  exact successful request envelope. If actual reset reply is detached/ambiguous,
  do not silently generalize its schema: separately review transferred CBW plus
  fresh returned-ROM observation and the exact terminal ambiguity boundary.
- returned_rom_snapshot has observation time, same physical port, new bus/devnum,
  mask-ROM4c4a:8057, previous installed-loader binding, previous-handle closed
  attestation and operator unit continuity. Snapshot freshness is checked at
  preparation/open (suggest the existing120seconds snapshot/10seconds pre-submit
  limits); historical install/backup evidence is checked at its completion time,
  never described as presently fresh. USB and opened FD/sysfs identity are
  independently checked before/after every operation.
- active_session_state is exactly `returned-rom-no-unrecorded-commands` or,
  with the optional exact successful probe envelope,
  `returned-rom-after-recorded-stage-probe-no-later-commands`.
- origin_consumed_marker is one fixed common marker attached to this returned
  ROM origin, across every receipt directory. Durable exclusive consumption
  occurs before any device open/submit; ambiguity retains consumption and
  closes/latches. Old softkey/backup/install/reset markers remain untouched.

The new success-only backup manifest must carry a distinct kind, not79's kind;
original unit lineage and historical identity are labeled as such. Required
claims: exact source/campaign/ROM/reset/probe/inventory hashes; new actual USB
and SG binding; loaderfe6d/originald41/profile3c03/source966; two complete1MiB
files with the actual df6 hash; identical true; exact8757command completion
count and replay; no flash operations; no retry; kernel_exclusivity false;
stock_boot/display/physical_recovery_verified false. Per FD05 completion records
must include the exact256byte response SHA, so every page of each dump can be
independently replayed against the saved file. Completion log, dumps, manifest
and containing directory must be synced; exit0 + final completed event + exact
manifest are required together, never a filename alone. Preserve any partial
private receipts on failure without publishing a success manifest.

Inventory remains exactly8757: ROM inquiry;47 FB06; one FB08; one FC14; initial
FC0A; for each1MiB pass,256groups of FC0A then16 FD05 pages, plus final FC0A.
No FC0C, FB01, FB04, FC12, eFuse, arbitrary ROM memory reads, alternate uploads,
blanket erase or automatic retries are admitted in this phase. Factory derives
and hashes the inventory; caller cannot supply extra commands. Probe, if any,
is an earlier separate sealed campaign, not an8757inventory alteration.

Restore campaign fields:

- schema1; kind `fm1-exact-returned-rom-target-to-stock`; adapter_sha256;
  source_sha256; original_policy_inputs; original_install_evidence;
  returned_backup_campaign; returned_backup_manifest; returned_backup_commands;
  returned_backup_exit_status0; usb_binding; sg_binding; active_session_state
  `matching-returned-target-backup-no-later-commands`; receipt_path;
  origin_consumed_marker (a distinct one-use restore marker sharing this origin).
- Bind the original immutable plan/baseline/target and actual genuine
  complete/install journal. Save its completed install snapshot privately before
  restore mutates the live journal. Existing worker then runs directionrestore
  on that journal under the new restore-only policy. Preserve original install
  receipts and all old markers. No cloned/forged complete journal is admitted.
- Freeze all immutable originals/new receipts/source pins and recheck after
  durable SG submit intent. The mutable live journal is independently checked
  against exact direction/intent/state, not treated as immutable file bytes.
- The worker's initial4096pages must reconstruct exact newly backed-up df6
  before first mutation; reject any drift even within app scope. Read full NOR
  afresh on the new bound handle. Protected bytes must equal original stock.
  Permit only30 derived4KiB sectors0x4000..0x22000, order0x5000..0x21000 then
  commit0x4000; FB01 exact aligned sector; FB04 exact stock256byte page/CRC.
  Before every mutation require the durable directionrestore intent, unchanged
  evidence/source and current SG/sysfs binding. Complete final4096pages must
  equal stock96006 and result/journal/log must agree before success publication.

Restored96006 does not imply current-loader provenance or stock boot. A later
one-shot stock-return FC0C gate needs a separate reviewed factory tied to this
new restore receipt/current new SG binding; none of the old original-binding
reset factories can be reused by altering their JSON. Boot identity/display
observation remains separate. Interrupted restore needs a new reviewed recovery
resume envelope admitting only its own durable app-sector journal and intact
protected bytes; it is a follow-on dependency, not silently covered here.

## Source pins and acceptance limits

[verified] Inspected source SHA-256 at this design snapshot:

- recovery_campaign: aadd244d0324f4585b2764f1586756ce1ccfc1da56c05fac3627c2f169cc53ce
- bound_sdk_diagnostic: 4718825ab07c05364d3141f9281554b22d3eb2c902af759f4bc68a83ca648847
- fixed_loader_backup: 79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb
- sdk_rehearsal: f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4
- flash_transaction: d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908
- bound_diagnostic: 25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36
- raw_flash_profile: 43e4d23f665fac1a73dee2b5ae6e05bc5c3d0ab9bee04b886abad34c6289ae8f
- fixed_target_reset: b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a

Fixed loader fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c;
profile3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe;
original loaderd41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376;
stock96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4;
targetdf6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db.
The pending stage-probe source was read for ordering only (ff593853 snapshot);
its final independent freeze/capture/native retention acceptance belongs to
that lane. It is excluded from this lane's whole-suite snapshot.

Meaningful offline negative tests must cover real new-ROM receipt shape,
wrong/old devnum/port/unit link, stale/nonfinite time, forged/reordered reset or
probe log, unexpected extra command, omitted/mismatched upload/page hash,
unequal/incomplete/stock-labeled target dumps, protected drift, old source
mismatch, copied prepared factory object, marker reuse across receipts,
artifact drift after durable intent, FD/sysfs drift, SG status/sense/residue,
failed completion publication, exact-target initial read mismatch and final
stock mismatch. Use actual private factory inputs only in disposable Hera
containers, with mocked SG and exact inventory/coverage/resource/removal proof.
A model or vendor native handler review does not prove physical NOR safety,
RAM-retention semantics, hardware exclusivity, display or recovery reliability.
The reviewed native FC0C assurance remains conditional; external initializer
0x01e00428 and actual diagnostic boot/display are unresolved physical limits.

[verified] Branch feature/2026-10-11@installable-firmware; local HEAD at authoring
22cae292f2b689e08e67cdc425bc2005df17e680. This new note is uncommitted, root-owned.
Next dependency: root review this smallest split and freeze the actual returned
ROM/reset/probe receipt schema before substantive new factory implementation;
then independent source review, exact16chunk Hera tests and actual-file preflight
before any separately authorized hardware campaign. Whole6389/selector287 gates
continue concurrently, with their own durable notes and evidence directories.

## Implementation checkpoint: unaccepted WIP

The distinct backup scaffold and injected adversarial tests are saved in
`tools/fm1_returned_rom_backup.py` and `tests/test_returned_rom_backup.py`.
Only Python syntax compilation has passed so far; no hardware was accessed.
The current scaffold admits only a successful four-event target-reset receipt
and a null probe. It cannot yet accept the intended detached-reset provenance
or a completed stage probe. Do not use it for physical activation.

The next edit replaces copied provenance checks with the separately frozen
`validate_returned_state` evidence helper from diagnostic_path_review. Its
evidence validation grants no opener authority and must preserve completed
probe markers. A separate restore-only policy will then bind the new dual-target
backup to genuine original stock/SDK/install evidence. Old source pins remain
unchanged. Focused Hera tests and startup_resolution independent review remain
required before freezing either physical adapter. Root owns checkpoint/push.

[verified] Initial injected WIP regression on Hera passed 53 cases in 9.88 s
using the pinned recovery image, four CPU/four GiB, network none and no devices.
This tests the separate backup authority/latch/inventory and restore ordered
4,096-page target gate before writes, copied-instance rejection and source
freeze closure. Evidence is `build/returned-recovery-wip-hera/`; both containers
were removed, successful v2 exited zero without OOM. The first bootstrap used
unvenved Python without pytest and exited one before collection; that receipt
is preserved rather than hidden. It made no SG calls.

`tools/fm1_returned_rom_stock_restore.py` and its focused tests are now saved;
the factory deliberately rejects until the new backup literal source pin and
completed evidence helper freeze. This is not a complete actual-private factory
validation, independent review or the required focused 16-chunk gate.

## Evidence-only helpers and current integration

[verified] The older successful-only copied provenance is now replaced in the
backup factory by the separate returned-state evidence helper. Its literal
source pin remains `None` until that helper's successful/detached and consumed
failed-probe paths finish their own review. The failed-probe wrapper literal
pin also remains `None`. Therefore this WIP cannot open physical SG through
its production factory. Shared helper authority is evidence only; this backup
factory creates its own exact-instance registry and new consumed marker.
The proof's immutable check is retained throughout SG operations, including
absent probe evidence. Historical admission age is distinct from current live
binding and the 900-second dual-read campaign; current opener still rejects
an original passive ROM snapshot older than 120 seconds. A longer stopped-probe
recovery needs explicitly reviewed historical admission/current witness handling.

`validate_completed_backup` strictly replays all 8,757 intents/completions,
including 8,192 actual 256-byte response hashes against both private 1 MiB
target files. It reconstructs the exact manifest and verifies consumed new
marker, chronology and all false boot/display/recovery flags. Actual protocol
reply digests for inquiry/online/buffer are shape checked; their original bytes
are unavailable to this offline helper, so it retains the reviewed execution
semantic-check premise. All source, provenance, optional capture and actual SDK
policy evidence/plan/backup/target files enter the caller's immutable freeze.

`validate_completed_restore` does not call an opener factory. It reconstructs
the original completed install using the exact privately saved
`journal-before-restore.json`, validates the current complete/restore journal
independently, and strictly replays the initial 4,096 target pages, all derived
30 sector erases/programs/durable intents/readbacks with `0x4000` last, and all
final 4,096 stock pages. It requires exact terminal result/event, rejects later
stop/extra events, and checks restore starts after completed target backups.
Exit zero and no later commands remain explicit trusted operator assertions;
file presence alone establishes neither. The original source policies and
consumed markers remain unchanged. Root owns a distinct stock-return reset
scaffold whose literal restore pin stays `None` until this helper freezes.

[verified] A new preliminary Hera WIP run completed 96 tests and found one
fixture-only AttributeError in the added erase-address adversarial test
(the fixture supplied Replay class, while the test called module wire).
The test now constructs the corrupt CDB directly. This failed run is retained
in `build/returned-recovery-wip2-hera/`; it is not an accepted final gate.
Source syntax compilation passes. Focused sixteen-chunk and actual private
factory/model checks, independent source/evidence review and literal pins
remain required. No hardware operation was made by this lane.

[verified] Last freshly compared local/remote checkpoint is
`6b8ed4b277783fb447a5eb03712b8134b93fcd1d` on
`feature/2026-10-11@installable-firmware`; current helper edits are WIP,
saved to disk and root-owned for checkpoint/push. Next dependencies: shared
returned-state helper freeze, exact optional wrapper pin, actual modeled
backup/restore factory smoke, sixteen-chunk gate and startup independent review.

## Historical admission and current connection separation

[verified: source inspection; focused runtime gate pending] New backup schema
now pins `probe_admission_path`/`probe_admission_sha256` and
`connection_witness_path`/`connection_witness_sha256`. No attempted probe requires
null admission fields. Completed probe admission comes from the original first
prepared log event; stopped probe admission comes from its exact native
preflight path, independently checked by the owned-capture helper. The original
ROM snapshot is never rewritten. Shared proof evaluates the original120-second
admission age historically; it does not reapply that age after lengthy reads.

A separately frozen passive connection witness has exact schema1, kind
`fm1-passive-returned-rom-backup-connection`, observed_at, USB/SG binding,
original ROM snapshot SHA and quiet_state
`returned-rom-after-read-only-probe-no-loader-upload`. It must match the original
connection exactly and be at most120seconds old at factory admission and open.
The first operation remains bounded to ten seconds after opening; the entire
backup remains bounded to900seconds. Every operation checks actual descriptor
and discovered USB/sysfs identity. A new enumeration cannot reuse this witness.
Witness timestamps are actual passive observations owned by the root bench
wrapper; source tests cannot establish their physical truth.

[verified: source inspection] Successful and detached failed-probe wrappers
require separate literal pins in `PROBE_WRAPPER_SHAS`. Both currently remain
None pending independent acceptance; the shared provenance source also remains
None. No current production backup/restore factory can activate. Source checks
precede hardware discovery. Shared negative evidence is propagated as
`_absent_paths`, tuple of exact absolute Path instances, through completed
backup and restore; the restore policy checks lexists before every operation.
The distinct root reset retains and rechecks that same tuple at open/intent
binding boundaries. This preserves no-probe marker/destination absence, and
failed-probe missing result/ambiguity/missing-log absence without opener authority.

[verified] Preliminary WIP3 Hera run:111passed/one fixture-only failure,
23.83seconds. The manually injected test authority omitted newly required
manifest fields; fixture is repaired. Archive553files
`c04378a9ddd348d79048728c7aa1a45ec2bb4a30823975d196fd47b3715d801d`,
logs/XML/container receipt under `build/returned-recovery-wip3-hera/`.
One four-CPU/four-GiB/no-device/network-none container removed, noOOM.
A wrong optional loader mount pointed at an absent path that Docker created
as an empty directory; that exact empty directory was removed. This gate used
synthetic module fixtures and makes no actual-private source-factory claim.
Next run uses the already verified fixed-loader-directory original fixture.

`tests/test_returned_rom_actual.py` is saved as a pending complete private
factory/model smoke: actual SDK/ELF/stock/source checks, install-only target,
new returned ROM binding,8757modeledbackup requests, actual restore worker with
initial full target comparison,30directory-last sectors and final full stock,
then evidence-only completed restore using preserved original install journal.
Only syscalls/NOR/reset/enumeration/fixed experiment campaign literal are
modeled; no source-hash bypass is permitted. It cannot execute successfully
until new literal source pins freeze. Final sixteen-chunk and independent
review gates remain pending. Latest root-reported verified checkpoint is
`b8b2f257114aac2d76a86d8eef585664a665942e`; subsequent edits are saved WIP.

## Final candidate and composed gate (in progress)

[verified: source/file checks] The subsequent literal candidate opens only the
new returned-ROM schema: backup source
`afeefe7bd7e9044cb34106081766d6104cda7ab0196d0de903c35a5c1a52b4be`,
restore source
`f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33`.
The shared evidence helper is `8fb33694…`; the successful stopped wrapper is
`b3b8186e…`, detached stopped wrapper `f88c09ed…`. Their source-only independent
acceptance is distinct from final runtime and physical acceptance. The earlier
None-pin descriptions above are historical WIP states. Existing source guards,
original backups and consumed markers remain unchanged.

[verified: source inspection] Backup and restore binding now recheck propagated
negative evidence with `lexists` after the durable intent callback and before
ioctl, including loader read commands. A late file or dangling symlink closes
and consumes the attempt. Positive multi-MiB evidence remains checked by the
factory and required mutation/publication boundaries; readonly binding checks
source/descriptor/sysfs and negative evidence. Completed evidence helpers freeze
all positive files and carry exact absolute Path tuples into the distinct reset.

[verified] WIP4 synthetic Hera gate passed112 cases in25.10seconds with the real
original loader fixture. Archive602 files SHA
`5fa1ce66e7026ac0479cb9b8807db57126a4a60b9f95d3565daa0b17f62f4de2`;
`build/returned-recovery-wip4-hera/evidence/` retains XML/log/run/inspect/removal.
The four-CPU/four-GiB pinned-image container had no device mounts, no network,
no privilege and noOOM, and was removed. This was not the genuine private
composed factory gate.

[verified] Final V1 archive602 files SHA
`4ce1dab8d91b231efbfc53aa69e401b9ebb26a08e986f75282144aa33865ef53`
collected124 nodes with sixteen planned chunks. Its one actual-private smoke
stopped after187.49seconds at a test fixture's nonexistent profile-source path;
production source guards rejected it before new backup transport. The fixture
now names `tools/jieli/loader_config_profile.py`. Both collect/smoke containers
were removed with noOOM. Evidence remains under
`build/returned-recovery-final-hera/evidence-v1/`; this failed attempt is not a
passing gate. Root owns a separate genuine-map repair in the returned stock
reset scaffold before V2. No source-hash gate is bypassed.

The composed model cases cover successful reset/no probe, successful and
detached reset/stopped read-only probe, definite zero-command stops, and genuine
backup-to-restore post-durable-intent absence drift. Successful/no-probe also
runs the distinct root reset's genuine completed-restore factory, with an
explicit test-only reviewed restore literal while production stays None, then
introduces absence drift after actual intent fsync/directory sync. Required
result: zero reset ioctl, consumed marker preserved, exactly one close and no
retry. The fixed experiment campaign literal and syscall/reset/enumeration/
capture evidence are explicitly modeled in disposable Hera containers. All
private SDK/ELF/stock/target and production source checks execute unchanged.
The six expensive cases are planned in separate round-robin chunks; smoke
selects only successful/no-probe.

[verified: syntax only] Concrete closed private templates are saved at
`build/returned-rom-recovery-bench-template/`, archive
`d3d0ec5d9bf212899ebae1b81b0a71512c40e6026e28ec11955e66fa6389054f`
(current closed template; original archive fccf9e9c… is historical).
Preparation preserves original completed install journal and passive current
connection witness without rewriting the original ROM snapshot or probe
admission. Exact old packet/plan/stock/target/dependencies and mode-specific
wrappers are pinned. Backup and restore require separate actual sealed campaign
execution policies, owned capture cleanup and no retry. `execute-once.py`
remains closed with `EXECUTION_POLICY_SHA=None`; root alone stages/activates
following actual file/source/capture review. No physical request occurred in
this lane. Boot, display, stock return and physical recovery remain false.

At this historical setup boundary, root's verified pushed checkpoint was
`f45a2b016d5629fc76dbb85b5a4bcfba7145c023`. Root subsequently checkpointed the
production candidate/tests/note at verified pushed
`4391433161f6fe61d30d54a8b79b53c67362177b`. The final mixed runtime and independent
review remain required dependencies, followed by root's actual packet gates. Semantic tool worktree Python coverage remains unavailable;
file inspection is used without changing another session's MCP selection.

## V2 archive freeze and reviewed source boundary

[verified: files/source review] Backup afeefe7b… and restore f5835237… are
independently source accepted in `build/returned-recovery-independent-review.md`
SHA `2926f969b8d68fc0064a9ec78b0070ef1d76044056795916539f9692affaf0ed`.
Shared helper/native/mode wrappers now have independent source/runtime acceptance
`build/diagnostic-detached-independent-review.md` SHA
`cd990cc891dfd99e06dfd477583c2d0b257599eeaa341b67eaffdfbd5d26d915`:101
unique cases across16 chunks plus real-private factory smoke, all modeled hardware.

[verified: preparation/collection] V2 archive602 files SHA
`f57cb52630113773fa489c7341dcd04c1bc8c6eccd9b0322f8b0702088d9bf5c`,
snapshot SHA `8ed528c58a48e6c925f7255bfab475a198a9a0134829d5f1f84fabdf5eb9fc32`,
includes root stock-reset17b9f005…/tests71f01093… and actual fixture
`c544732e1bc602346f20d0b17cda6d1b77ef1b4bcee8be7de020763bb190e8b0`.
The fixture repair includes the correct jieli profile-source path and recursive
test-only experiment-literal adaptation when root loads the genuine restore
module. Production file hash gates remain unmodified. V2 collected182 unique
nodes; chunks12 cases in six shards and11 in ten, with each expensive actual
case in a distinct shard. One successful/no-probe smoke precedes16 chunks.
This historical V2 run has completed; its passing and failed receipt boundaries
are recorded below. Production source bytes remain unchanged.

[verified: syntax/source inspection only] Closed template repairs retain the
None activation policy. Journal fdopen failure closes its descriptor. Restore
preparation binds owned capture PID/process group, exact SIGTERM returncode-15
and finite ordered attempt/open/exit/stop times. If a probe wrapper stops before
creating its campaign, the template may consume the genuine chooser selection
envelope only as the distinct unconsumed no-probe branch. The production factory
still requires original snapshot120-second freshness for this branch; no
historical time override or snapshot refresh is permitted. A stale chooser-only
state needs a distinct reviewed provenance gate before it can progress.

## V2 failures and reviewed V3 fixture repair

[verified: Hera XML/container receipts] V2 completed all182 unique planned nodes:
179 passed and3 fixture failures. The standalone successful/no-probe actual
smoke passed in386.65seconds. Actual successful-none/failed/zero shards6/7/8
passed in610/620/620seconds concurrently. Detached-failed and detached-zero
failed before returned-backup SG opening because the disposable fixture named
its snapshot original-rom.json instead of the detached helper's required
rom-snapshot.json. Successful-intent-drift reached its intended zero-ioctl,
one-close rejection after durable intent, then asserted the consumed marker in
the wrong parent directory. All18 collect/smoke/shard containers had noOOM, no
device mounts, network none and no privilege, and were removed; a fresh label
lookup was empty. Failed XML/logs remain under evidence-v2 and are not a passing
gate.

[verified: source diff/independent review] Only two fixture lines changed:
choose rom-snapshot.json for detached mode, preserving the exact successful
mode path; assert the restore consumed marker in rr rather than parent. Final
fixture SHA
`5f7fd57650e551ac6de3575f46ee48432d58bf5b5f74f7d3ab63027697f2a858`.
V3 archive602 files SHA
`99a28aeccfe432feabb89967212c3d1346eeaf020e14cae4ec97ccf7f19bb43f`,
snapshot SHA
`cbe8cede9b530986ddde49f3d2c74f19ecb0e0e9e2168e3920a82bad3a498e27`.
All601 other files are byte-identical to V2. Startup-resolution independently
accepted retaining the three passing V2 successful actual branches as unchanged
and rerunning every other179 case across16 V3 chunks, including all affected
actual cases. The final aggregate must map each of182 exact unique nodes to its
V2 or V3 archive and fixture hash; this is a mixed gate, not an all-V3 run. The
V2 singleton actual smoke is retained separately. V3 execution completed as recorded below; no hardware/native/boot/display/recovery
acceptance follows from this modeled gate.

## Final mixed runtime receipt

[verified: XML/archive/container receipts] The explicit mixed gate passed182
unique ordered cases with zero failures, errors or skips:179 rerun V3 cases
in16 chunks plus the independently reviewed three unchanged passing V2 actual
successful branches. The separate V2 singleton successful-none factory smoke
is retained. This is not an all-V3 run. Aggregate
`build/returned-recovery-final-hera/aggregate-mixed.json` SHA
`87848de7d3b2760da34c1af1f6ac3ff2cc8146afee5ca0c183b446f598def365`
maps every exact planned node to its V2/V3 archive, actual fixture hash and XML
hash; failed V2 nodes and the equivalence premise remain explicit.

V3 plan SHA
`f7247f998998b00abe7fa187f8724f9fe424d1a40584c56ef9acb585b92e2a64`
collected182 and executed179: three chunks of12 and13 chunks of11. Repaired
actual detached-failed/zero were chunks6/7, each passed11 cases in589.81/590.02
seconds; post-intent restore drift chunk8 passed11 in295.29seconds. V3 wall
time592.62seconds; summed V2+V3 container runtime4708.84seconds. Pinned image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
was used throughout. All35 V2+V3 collect/smoke/shard containers were checked:
2CPU,2GiB memory and swap, network none, no privilege/devices, noOOM, exact
exit status matching XML/run receipts, named removal receipts and fresh empty
label lookup. V1's separate two failed-setup containers remain historical.

[verified: pinned actual-input model assertions] All six genuine private-input
composed cases executed the complete source factories. Five full restore cases
required8757 returned fixed-loader commands,10653 restore commands, identical
full target df6c… dumps, initial full target comparison, all30 directory-last
stock restoration sectors and final full stock96006… readback. The completed
restore helper froze138–165 positive files according to provenance mode, plus
propagated exact absent paths.
The sixth case validated late absence after the real restore intent sync:
zero ioctl, one close, consumed marker preserved and no retry. Successful-none
also ran the genuine root17b reset factory with test-only restore literal, then
late absence after the real reset intent sync: zero reset ioctl, one close,
consumed/no retry. At the sealed runtime snapshot, production root17b reset restore literal and
execution template policy remained None. Root's separately reviewed7af successor
binds f583 and has its own58-case runtime gate; it is outside this archive. SDK/ELF/stock/target/source guards were unmodified; only
USB/reset/capture/syscalls/NOR and fixed experiment campaign literal were
modeled. Boot, display and physical recovery remain false.

Independent preserved V2 evidence check
`build/returned-recovery-final-hera/startup-resolution-preserved-v2-check.json`
SHA `274b2ee9c7f24a49fe8cb6ed4d1f248891b6dac521ad90841fc1201888a7f960`
confirmed the three exact retained green node IDs, expected three old fixture
failures and601 identical files. Final independent mixed runtime acceptance is recorded below. Root's feature branch and remote were independently checked at
`4391433161f6fe61d30d54a8b79b53c67362177b`; current602 sealed source files match.
The two-line fixture repair and this final note await root checkpoint/push.

The next dependency is root's concrete physical packet factory/source/owned-
capture gates and separately reviewed literal production integration. The earliest file-only preparation preserves the actual completed
install journal in a distinct staging file; it must leave the exclusive
RUN/original-install-journal.json destination absent. Only after actual reset,
original ROM snapshot and terminal probe review may preparation issue the
fresh current connection witness, while retaining original admission/snapshot
times unchanged. The no-attempt branch's120-second original-snapshot gate
remains explicit; consumed stopped/completed probe provenance uses verified
historical admission plus separately fresh current binding. Interrupted restore
resume is a distinct pending follow-on, not granted by this one-shot adapter.


## Independent final acceptance and checkpoint freeze

[verified: independent offline review] Startup-resolution accepted the exact
mixed182 source/runtime gate in
`build/returned-recovery-independent-review.md` SHA
`4d3076dcb65e07d3c1ed3d58e45fe350815d64f25e91c009f7c45abb187b8db2`.
Its independent structured check
`build/returned-recovery-final-hera/startup-resolution-mixed-independent-check.json`
SHA `cd5a2d92d71204952a003ef261452dd5c153051c93d83765b6606271e97da6c5`
verified all602 archive/current pins, the601-file equivalence, exact182 ordered
XML records, six composed summaries and35 resource/removal receipts. Fresh
structured cleanup receipt
`build/returned-recovery-final-hera/evidence-v3/removal-lookup-structured.json`
SHA `1ef2e4c93ae24f62891c00fa93d22578da886d1bc2163c4ae338115dd06e8268`
records the exact Docker label lookup, times, exit0, empty container_ids and
empty stderr. Acceptance is offline only: physical NOR, loader quiescence,
reset, boot, display and recovery require their separate actual observations.

Final source remains backup afeefe7b…, restore f5835237… and actual fixture
5f7fd576…; production files were unchanged by the two-line fixture repair.
This note and the fixture are frozen for root checkpoint/push. The distinct
interrupted-restore design is saved in
`notes/2026-10-11-returned-stock-resume-design.md`; its new implementation is
authorised behind closed execution, preserving every accepted source and marker.

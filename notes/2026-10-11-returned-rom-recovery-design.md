# Returned-ROM recovery after the exact diagnostic install

Personal, non-commercial. This is a read-only design, requested by root while
source regression gates run. No hardware traffic, new transport activation,
old-source edits, commit or push was performed by this lane. Root owns review,
implementation authorization, physical staging, commits and verified pushes.

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

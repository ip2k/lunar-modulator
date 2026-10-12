# Interrupted returned-stock restore: separate recovery design

2026-10-11. Personal, non-commercial. Design-only, no opener authority, source
changes or hardware requests. Root owns any implementation, activation, commits
and pushes. Existing returned backup/restore/reset guards and markers remain
frozen. Latest independently checked feature/remote checkpoint:
4391433161f6fe61d30d54a8b79b53c67362177b.

[verified: source inspection] The transaction worker already supports resumption:
`tools/fm1_flash_transaction.py:185` loads the durable journal and plan, performs
fresh complete NOR readback, compares every protected byte against the original
baseline, rebuilds differing allowed sectors from the immutable desired image,
and verifies the whole final NOR. It follows the sealed directory-last sector
order and never treats a journal cursor or torn page as flash truth. An ambiguous
command exits, records recovery_required and cannot retry on that stale handle.

[verified] The frozen one-shot returned restore source
f583523740bb709dde0cf8bc2e07677e2ab26063d511dcb3ba84a6b232e9af33 intentionally
requires initial complete target df6c… and a completed original install journal.
Its marker and exclusive receipt close reopening. Its completed helper requires
all30 sectors changed, the exact full initial target, full final stock and a
complete single-run transcript. A partial restore cannot become this success
by altering its initial backup manifest, journal or marker. Frozen returned
backup afeefe7b… likewise only authorizes dual complete target dumps.

The smallest separate authority is an interrupted-restore envelope with these
positive evidence pins: exact prior restore source/campaign, consumed marker,
commands log, journal-before-restore, current stopped journal, original genuine
SDK/stock/target/plan inputs, original returned backup and preserved returned-ROM
lineage, and an owned terminal wrapper/capture receipt proving stopped exit and
no later command. It retains every propagated absent path through factory,
open, post-intent binding and publication. It does not call the prior opener's
prepare function or require its consumed marker to be absent.

[design] Strict replay accepts the exact initial4096 target page hashes and the
completed prefix of FC0A/FD05/FB01/FB04 requests, padding, CRC, payload hashes,
status and durable intents. Requests remain the existing bounded stock restore
inventory. Terminal stop, exclusive marker and source/campaign/journal linkage
must agree. A stopped run before any mutation has no permission to treat new
NOR differences as our writes. A crash with no terminal record needs a separately
reviewed owned-capture branch; it is not silently accepted as a normal stop.

Replay reconstructs the exact last known NOR from the target and stock images.
A final submitted but unreturned erase can leave only its addressed4KiB sector
uncertain; a final submitted but unreturned program can leave only its exact
256-byte page uncertain. All other bytes must equal the replayed expected state.
The sole uncertainty is bounded by the actual final mutation request, not by
all30 writable sectors. If the stop occurs on a read/query or after a confirmed
mutation, there is no additional uncertain write range. Missing software
completion does not mean transmission or completion; an owned wire capture,
where used, must be scoped to actual observed requests. Native external driver
and initializer limits from the existing NOR review remain conditional.

[design] A distinct new read-only admission phase acquires a new FD and exact
current USB/sysfs/SG binding, then obtains two complete matching partial-NOR
dumps. It verifies the protected stock bytes and the reconstructed expected
state outside the single bounded uncertainty range before any erase/program.
These are recovery-state backups with their own manifest/source/marker. They
must not be labeled target df6c backups unless actually identical to that target.
The live binding and original loader lineage are separate from flash state.

Two possible acquisition paths need explicit review before implementation:

- Retained active fixed loader: a newly opened handle under unchanged exact
  USB/SG identity, owned stopped transport/capture and trusted no-later-command
  statement. No reuse of the failed handle and no automatic retry. Whether the
  transport has fully quiesced is an explicit physical admission issue.
- Newly returned ROM: exact returned-ROM witness and a distinct reviewed fixed
  loader upload, preserving original reset/probe evidence and timestamps.
  Existing target-only backup authority cannot accept partial NOR; the new
  recovery-state backup must bind the fresh USB/SG identity and loader source.

A new factory-only WeakSet policy then binds the original restore-only target
(stock96006…) to the admitted actual partial snapshot. The worker can be reused
with a new adapter whose initial readback requires that exact snapshot, not
complete target df6c. It retains full protected comparison, exact30-sector
allowlist, directory0x4000 last, durable intent and stock-derived256-byte CRC
payloads. It rebuilds differing sectors; already-stock sectors are verified and
skipped. A stopped write creates a new exclusive consumed recovery marker; no
old marker or old journal snapshot is removed or overwritten.

[design] A separate evidence-only completed-resume helper must freeze the
interrupted prefix plus the resumed transcript and source lineage. It requires
complete actual initial partial-NOR readback, all chosen mutations/readbacks,
exact final4096 stock page hashes, complete/restore journal, matching result,
exit0 and no later commands. Sectors_written is the actual ordered subset size
0..30; full stock verification, not a fixed count30, proves flash completion.
The result records both prior and resumed campaign lineage. Existing f583's
completed helper and the frozen one-shot stock-reset source must not silently
accept it. A distinct stock-return reset envelope/helper successor is needed.

Meaningful offline tests cover stops before writes, during sector erase, during
page program and at directory commit; bytes changed outside the sole uncertain
range or protected areas; journal/log disagreement; source or absence drift
post durable intent; full fresh readback on admission and completion; already
stock0-write resumption; exactly one new attempt/marker; and ambiguous new
transport exits with no retry. Private actual-input model coverage must execute
the real original factories before injected interruption and the actual new
factory/worker afterward. Heavy gates belong on Hera in16 chunks. Model success
does not prove stock boot, loader quiescence, physical recovery or display.

Next dependency: a distinct implementation is authorised behind closed
execution, followed by independent source/runtime review and root selection of
a concrete acquisition/provenance path and bounded terminal-log contract. This
design grants no hardware command or reuse of a consumed attempt. The accepted one-shot returned recovery path remains
the first physical boot/restore candidate; interrupted resumption is a separate
follow-on and must not delay or rewrite that accepted scope.

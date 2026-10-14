# FC0C reset receipt semantics after expected loader detach

**Scope:** read-only source review on Hera at host-CI base . No adapter, test, campaign, or device was changed or run. The coordinator reports a watched FC0C path where the old SG node disappears, the native USB interface appears, then ROM returns; that observation is not independently reproduced in this lane.

## Finding

The common reset implementation in  checks the original SG/USB binding before and after the single  at lines 230-237 and 248-253. It only records  after the second binding succeeds (254-259). If FC0C causes the expected loader detach during the ioctl, the post-ioctl  can fail before the completion fields and echoed response are recorded.  then logs  (300-313). The SDK target wrapper inherits this method unchanged (); expanded boot does too (). Its caller labels any such exception  (). Thus the watched disconnect can currently be represented only as ambiguous by these adapters, even when the syscall may have returned a clean FC0C response before the node disappeared.

The ambiguity is real when  itself returns an error, incomplete status/sense/residue, mismatched echo, or no trustworthy response. A USB detach alone cannot distinguish accepted reset from unplug, transport loss, or an interrupted command. The existing no-retry behavior is correct. The current result fields correctly keep , , display and recovery false; USB enumeration is not proof that Lunar or stock application booted.

All three consumers pin the base reset implementation by SHA-256 (,  through ); modifying the pinned base in place would invalidate the reviewed campaign/adapter lineage. Keep this review note-only.

## Recommended receipt model for a separately reviewed adapter revision

1. Preserve the durable  immediately before the one ioctl. Record the syscall return separately from transport state. If the ioctl returns, immediately snapshot and fsync the complete SG status fields, bounded sense bytes and 16-byte data buffer **before** querying USB/SG topology again.
2. Classify  only when the ioctl returned and all current acceptance checks pass ( clean plus exact FC0C echo). This means only “the host received a complete accepted command response”; it is not , , or proof of installation/runtime. A post-call old-SG disappearance should be a separate  field/event and must not erase an already captured clean response.
3. If the ioctl raises, SG completion is incomplete/error, or the response/echo is invalid, retain . Record any independently witnessed disconnect/re-enumeration in a separate observer receipt with monotonic/UTC times and exact interface identities. Never retry either outcome.
4. Promote boot/recovery fields only from a distinct accepted observation of the expected runtime identity and behavior. If ROM reappears, record , , and let the operator-directed recovery policy handle it; do not rewrite an earlier ambiguous transport outcome as success.
5. For existing receipts, preserve  as written. An independent watcher log may be attached as additional evidence, but must not retroactively claim SG response completion when the adapter did not save it.

A focused fake-SG regression should cover: clean ioctl response followed by disappearance of the old SG mapping; expected USB re-enumeration recorded independently; ioctl exception after intent; nonzero/incomplete SG completion; corrupt echo; and repeated-call refusal. Assert one ioctl maximum and all boot/recovery flags false. Current mock coverage is in , , , and trace-envelope semantics in ; source pins, frozen evidence, and receipt schemas must be revised together in a new reviewed stream.

## Evidence and limits

- [verified] Source hashes: base reset ; target wrapper ; expanded boot .
- [verified] Existing notes explicitly require no retry on disconnect and keep reset/boot false ( and ). Tests model completed response separately from detach ambiguity.
- [reported by coordinator] A watched FC0C sequence removed the old SG, showed native USB, then ROM. This review has no new hardware trace, USB monitor capture, or raw receipt to independently validate event order or exact identities.
- [verified] No live reset, USB/MIDI operation, adapter invocation, or hardware access occurred. No claim of Lunar boot or recovery is made.
- Serena and Rarefaction both point to the primary Mac checkout, not this Hera worktree. Shared project selection was not changed; findings came from direct source/test/note inspection.

**Next dependency:** owner/coordinator should decide whether the existing ambiguous receipt plus separate watched enumeration is sufficient for the present recovery decision. If a cleaner machine-verifiable request result is needed, authorize a new adapter/schema version and add the fake-SG regression above; do not alter any currently pinned adapter or retry the target reset.

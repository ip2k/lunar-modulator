# FC0C reset receipt semantics after expected loader detach

Scope: read-only review on Hera at host-CI base 843b33c3bcfd6ffd8d8ce69947ad28aa9a4c0bd4. No adapter, test, campaign, or device was changed or run. The coordinator reports a watched FC0C path where the old SG node disappears, native USB appears, then ROM returns. That observation is not independently reproduced in this lane.

## Finding

The common reset implementation in tools/fm1_fixed_loader_reset.py checks the original SG/USB binding before and after the single SG_IO at lines 230-237 and 248-253. It records reset_sg_completion only after the second binding succeeds (254-259). If FC0C causes the expected loader detach during ioctl, post-ioctl binding can fail before completion fields and the echoed response are recorded. run_campaign then logs reset_stopped_ambiguous (300-313). The SDK target wrapper inherits this method unchanged (tools/fm1_fixed_target_reset.py:311-335); expanded boot does too (tools/native/expanded_boot.py:78-98). Its caller labels any such exception native_boot_stopped_ambiguous (expanded_boot.py:110-121). Thus the watched disconnect can currently be represented only as ambiguous by these adapters, even when the syscall may have returned a clean FC0C response before the node disappeared.

The ambiguity is real when SG_IO itself returns an error, incomplete status/sense/residue, mismatched echo, or no trustworthy response. A USB detach alone cannot distinguish accepted reset from unplug, transport loss, or an interrupted command. The existing no-retry behavior is correct. The current result fields correctly keep core_reset_observed, boot_observed, display and recovery false; USB enumeration is not proof that Lunar or stock application booted.

All three consumers pin the base reset implementation by SHA-256 (fm1_fixed_target_reset.py:RESET_SOURCE_SHA; expanded_boot.py imports that exact reset module). Modifying the pinned base in place would invalidate the reviewed campaign/adapter lineage. Keep this review note-only.

## Recommended receipt model for a separately reviewed adapter revision

1. Preserve durable reset_submit_intent immediately before the one ioctl. Record the syscall return separately from transport state. If ioctl returns, immediately snapshot and fsync the complete SG status fields, bounded sense bytes and 16-byte data buffer before querying USB/SG topology again.
2. Classify request_completion=true only when ioctl returned and all current acceptance checks pass: status/masked/msg/host/driver/resid/info/sense are clean and the exact FC0C echo matches. This means only "the host received a complete accepted command response"; it is not core_reset_observed, boot_observed, or proof of installation/runtime. A post-call old-SG disappearance should be a separate original_binding_after_request=detached field/event and must not erase an already captured clean response.
3. If ioctl raises, SG completion is incomplete/error, or the response/echo is invalid, retain request_outcome=ambiguous. Record independently witnessed disconnect/re-enumeration in a separate observer receipt with monotonic/UTC times and exact interface identities. Never retry either outcome.
4. Promote boot/recovery fields only from a distinct accepted observation of expected runtime identity and behavior. If ROM reappears, record rom_observed=true and boot_observed=false, and let the operator-directed recovery policy handle it; do not rewrite an earlier ambiguous transport outcome as success.
5. For existing receipts, preserve reset_stopped_ambiguous as written. An independent watcher log may be attached as additional evidence, but must not retroactively claim SG response completion when the adapter did not save it.

A focused fake-SG regression should cover: clean ioctl response followed by disappearance of old SG mapping; expected USB re-enumeration recorded independently; ioctl exception after intent; nonzero/incomplete SG completion; corrupt echo; and repeated-call refusal. Assert one ioctl maximum and all boot/recovery flags false. Current mock coverage is in tests/test_fixed_loader_reset.py, tests/test_fixed_target_reset.py, tests/expanded_boot_model.py, and trace-envelope semantics in tests/test_reset_wire.py. Source pins, frozen evidence, and receipt schemas must be revised together in a new reviewed stream.

## Evidence and limits

- [verified] Source hashes: base reset dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116; target wrapper b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a; expanded boot 2ec7931831eb534260b1dcf80d18862fb0771409725fdbec75240537fcba24ec.
- [verified] Existing notes explicitly require no retry on disconnect and keep reset/boot false (notes/2026-10-11-fixed-loader-baseline-reset.md and notes/2026-10-11-fixed-loader-target-reset.md). Tests model completed response separately from detach ambiguity.
- [reported by coordinator] A watched FC0C sequence removed old SG, showed native USB, then ROM. This review has no new hardware trace, USB monitor capture, or raw receipt to independently validate event order or exact identities.
- [verified] No live reset, USB/MIDI operation, adapter invocation, or hardware access occurred. No claim of Lunar boot or recovery is made.
- Serena and Rarefaction both point to the primary Mac checkout, not this Hera worktree. Shared project selection was not changed; findings came from direct source/test/note inspection.

Next dependency: owner/coordinator should decide whether the existing ambiguous receipt plus separate watched enumeration is sufficient for the present recovery decision. If a cleaner machine-verifiable request result is needed, authorize a new adapter/schema version and add the fake-SG regression above; do not alter any currently pinned adapter or retry the target reset.

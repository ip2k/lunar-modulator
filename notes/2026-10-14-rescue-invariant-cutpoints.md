# Rescue record and payload invariants at rollback cutpoints

Date: 2026-10-14. Offline model review and focused host tests only. No hardware, USB, MIDI, flash, power, reset, install, or runtime operation occurred.

## Conclusion

[verified from current source plus SPL byte review] For the recorded stock FM1_092 baseline and the current expanded offline candidate, a rescue record cannot be assumed to exist: the preceding byte audit found zero SPL tags at all 255 scanned positions in raw and decoded views. Therefore a rollback proof that starts with `initial_recovery_record_valid=True` is hypothetical for these exact images. It describes a future design only if a valid record and complete loader can first be created in an independently approved extent and read back successfully.

[verified model result] Once such a design exists, its recovery invariant while the application header may be invalid is conjunctive:

`invalid app header => valid rescue record AND complete referenced loader/header`

The earlier cutpoint model tracked only the record bit and could incorrectly report `loader_record_scan_reachable` while the record pointed at a missing/incomplete payload. It now represents record and payload validity separately. A partial write to either extent marks only the touched predicate unknown during that operation; untouched extents retain their state. This avoids treating erase/program operations as atomic and makes a record with no complete payload an explicit `no_verified_spl_entry` case when the app header is known invalid.

The model continues to distinguish `stock_xip_selected` from stock application readiness. A valid app header only shows the SPL selects the XIP entry and bypasses the trailer scan; `stock_app_ready` remains `unknown`. Thus the model does not prove cleanup is safe after merely restoring an app header, especially where VM/settings readiness after interrupted sectors is unresolved.

## Ordering implications

A candidate future sequence would have to satisfy all of these conditions before any app-invalidating write:

1. Prove an exact, allowed extent that the SPL will scan and whose ownership permits staging. Current empty scan slots do not grant ownership; VM/BTIF/USR and protected boot/config remain out of scope.
2. Program and verify the complete loader and its accepted inner header first. Do not publish a record that can point to partially written bytes.
3. Write/publish the record only after payload readback and format/CRC checks pass; verify the full 80-byte record and referenced payload before treating the rescue invariant as established.
4. Keep both record and payload untouched while the app header can be invalid. The focused model test confirms that invalidating the app header while both remain valid yields `loader_record_scan_reachable` at every modeled cutpoint.
5. Only after a separately established application readiness condition may cleanup begin. Remove/invalidate the record before erasing its payload; if the record remains valid but its payload is erased, an invalid app header has no verified SPL entry. The current model deliberately does not claim readiness, so this cleanup gate is not closed by these tests.

Even the ordering above is a conditional design constraint, not an implementable safe plan yet: no owned SPL-scanned extent, valid source rescue record, target execution, exact erase/program granularity proof, or stock-app readiness evidence exists in this task. Existing notes prove that when the app selection fails and the full record scan finds no valid entry, the pinned SPL enters its observed terminal loop; that is control-flow evidence, not a claim about physical symptoms or the separate USB_KEY/mask-ROM route.

## Changes and checks

Changed only `tools/native/rollback_cutpoints.py` and `tests/test_native_rollback_cutpoints.py`.
The model adds `loader_payload_valid_after` and `initial_loader_payload_valid`; each `CutPoint` reports payload validity. `loader_record_scan_reachable` now requires app header false, record true, and payload true. If the app is invalid and either is false, the route is `no_verified_spl_entry`. During a mutation the fields affected by that operation are unknown; unaffected fields retain their previous values. Existing `stock_app_ready="unknown"` behavior is unchanged.

Added regressions for a present record with absent payload, partial payload programming, preserving the record+payload while the app header is invalid, and payload-first cleanup failure. Updated the previous stage test to state its complete-loader assumption explicitly.

- Focused tests: 7 passed with the project Mac venv's pytest, against a temporary directory containing byte-for-byte copies of the exact Hera files (no shared checkout changes).
- Hera system `python3 -m pytest` could not run because that interpreter has no pytest installed; this is recorded as an environment limitation, not a test failure.
- `git diff --check` passed on Hera.
- Grep found no other repository callers or tests of this model API and no expectations for the removed `unknown-during-mutation` string.

## Evidence boundaries and next dependency

The model is an abstract state machine. Its `loader_payload_valid` flag means “complete referenced loader plus required header are accepted,” not merely all bytes written; the model does not implement the SPL parser, CRCs, pointer bounds, multiple-record ordering, sector geometry, flash polarity, erase/program behavior, or physical readback. Those predicates must be bound to a concrete reviewed image and exact SPL parser before using the model as an acceptance gate.

Relevant evidence:

- Commit `35b200b1bdb93690580c660ac6e81334ec59acac`, note `notes/2026-10-14-protected-rescue-record-audit.md`: no recognized rescue record in the retained stock pair or expanded candidate. That worker note is a separate checkpoint and is not present in this branch base; the SPL slot contract is also documented in the local byte-review note below.
- `notes/2026-10-14-spl-empty-rescue-fallback.md`: conditional scan terminal path when no valid rescue record is found; no ROM/USB fallback established by that path.
- `notes/2026-10-14-rollback-stage-last-cutpoint-review.md`: app-header selection is not stock-app readiness; settings/VM initialization remains unresolved.
- `notes/2026-10-14-stock-spl-update-record-byte-review.md`: candidate slot arithmetic and acceptance format.

Next, the owner/coordinator needs independent evidence for both a permitted SPL-scanned staging extent and a stock-app startup/readiness criterion, or must retain external/manual recovery as a required fallback. No update ordering alone closes those missing premises. Do not infer a physical rescue plan or erase permission from these model tests.

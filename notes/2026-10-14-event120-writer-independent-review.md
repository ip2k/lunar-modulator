# Event120 writer independent review

Reviewed writer commit 9d579461aabd9f2d870904d2039601e4b3ec1883 offline. No device, USB, MIDI, SG_IO, flash, reset, or power operations were issued.

## Fixed blocker: live SG mapping serialization

tools/native/event120_bench_live.py built Prepared.mapping using default json.dumps(..., sort_keys=True), which includes spaces. tools/native/expanded_sg.py:canonical encodes sorted compact JSON. RehearsalSG.__init__ compares the compact encoding from discover_sg() directly with prepared.mapping; therefore the real transport constructor rejected the same binding prepared by the campaign with “Backup connection replaced” before opening a usable session. The review branch now encodes Prepared.mapping with sorted compact ASCII JSON, allow_nan=False, and adds a regression comparing it directly to expanded_sg.canonical.

## Replay and transaction review

The real event ordering is compatible with the replay command model through the mutation loop: native_transaction_prepared; SG submit/completion pairs; transaction durable intent; mutation; operation returned; sector readback and sector_verified; complete flash readback; terminal native_transaction_completed. BoundDiagnosticSession mutation guards require the matching running journal intent; RehearsalSG rechecks exact source/evidence and direction-specific page/sector constraints before each mutation. An attempted SG command increments its index before ioctl and errors latch/close the handle; no retry path was found. The marker is created exclusively and fsynced, then its parent is synced before session creation/commands. Failed runs retain the marker, so the same variant/direction cannot be automatically retried.

One remaining interface dependency is terminal result shape: writer run() adds hardware_admitted: false and installable: false to the completion event and result file, whereas the reviewed tools/native/event120_install_proof.py replay at its current checkout compares the event/result against an exact accepted dictionary without those two fields. The coordinator is harmonizing this root-owned replay contract. Do not treat replay as passing until it is run against the exact merged writer and proof commits and both sides use the same explicit false-gate schema.

The replay test fixture uses a simulated ModelTransport, not production RehearsalSG; the new mapping test covers the constructor's serialization precondition but no live SG path was exercised. The transport policy/source pins and artifact binding still need a fresh exact-campaign regeneration/replay after this source correction, because the campaign binds the adapter hash.

## Validation and tool coverage

/home/claude/mvave-fm1/ci-contract-repairs-20261012/.venv/bin/pytest -q tests/test_event120_bench_live.py: 10 passed. These are offline private-fixture policy/orchestration tests; they do not establish hardware admission, NOR completion, recovery, USB exclusivity, or boot.

Serena was already selected to the Mac primary checkout and Rarefaction to the Mac editor checkout. I did not change either shared selection; source navigation used file inspection in the exact Hera review worktree. Semantic navigation coverage is therefore unavailable for this Hera checkout.

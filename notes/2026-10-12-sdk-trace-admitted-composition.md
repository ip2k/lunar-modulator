# Canonical trace return through target backup and stock restore

This is the next separate modeled factory gate after closed mechanics V3.
Parent owns source activation, commits, pushes and hardware. Existing frozen
sources and the original read/boot/install snapshots remain unchanged.

Before implementation: returned proof provenance and current connection freshness
have different lifetimes. A restored current journal also cannot be used as a
completed-install journal. The genuine composition must retain the original
snapshot and pre-restore journal while independently replaying current restore.

The two new test files `tests/sdk_trace_admitted_fixture.py` and
`tests/test_sdk_trace_admitted_composed.py` reuse the frozen canonical owned-return
fixture. They call the actual install, boot, reader, native transport, owned
receipt admission, new backup and new restore factories. Only device syscalls,
clocks and capture process lifecycle are modeled; source pins, registries and
Prepared authority are never replaced. Dependency preflight rejects None pins
before the expensive install. AST parsing was checked here; no local tests or
device operations were run [verified].

Two independently parallelizable branches are proposed: complete restore and
an actual durable mutation-intent callback that creates a previously absent
provenance ambiguity. The latter calls real sync_dir first, then inspects the
worker's final durable_intent record. It must produce no erase/program ioctl,
retain consumption and journal-before-restore, close the second handle and refuse
another attempt. The completed branch checks both target dumps, all 4,096 initial
pages before mutation, thirty directory-last sector erases, 480 programs, final
stock bytes, strict completed-helper replay, copied proof rejection, marker/result/
lineage/preserved-journal drift and late negative-evidence appearance.

Admission, current witness and historical completed-helper paths remain separate.
The original ROM snapshot bytes/hash/time are never updated. Completed restore
reconstructs installation from the preserved journal and requires current
complete/restore state independently. Artifacts are copied privately with source
and byte hashes; summaries explicitly keep physical boot, reset cause, hardware
recovery and actual capture-supervisor execution false.

Required before a runtime archive: parent independently accepts canonical
admission candidate `5ca132fc2f2595400bc9ccb231c3e5cd44ecc9886cd830e201272b33a677b34a`
and its 75-case gate; then separately reviews literal-only backup PROOF_SOURCE_SHA
and restore BACKUP_SOURCE_SHA/POLICY_SOURCE_SHA successors. Exact trace policy
`54bd9a2990d0055b1d102bc8481a71d883d586649aa2d79d62a185a415296835` was accepted for
offline installer/model scope. Current production pins stay None until that
review. No test monkeypatch may activate those pins. The two source-contract
assertions of literal None belong to the retained closed V3 gate; a successor
runtime selection must explicitly distinguish them from remaining unit mechanics.

After implementation: source-backed tests are saved but not executed. They are
not evidence of loader access after a corrupt application's reset. CPU/SPL and
USB_KEY physical availability remain unresolved. Runtime is Hera-only, thirty
chunks, exact image 7e32, 2 CPU/2 GiB with combined 4 GiB memory/swap, source RO,
network/device none. Parent must approve the exact successor archive before run.

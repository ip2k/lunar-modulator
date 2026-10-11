# Private raw diagnostic construction

[verified: source and Hera tests, 2026-10-11] The new offline
`tools/jieli/build_raw_diagnostic.py` replaces the exact app bytes and their
directory CRC/length fields in the recorded FM-1_092 raw image, retaining the
original unused app tail and all protected allocations. It recomputes the
independent raw-target validation before emitting anything. It implements no
device transport or flash operation, and grants no hardware approval.

[verified: independent source review] SDK applications remain rejected by
this initial builder. A distinct SDK ELF/image profile and its recovery/startup
review are required before constructing the selected SDK diagnostic. A passing
inert-image fixture does not establish the safety of an SDK image.

[verified: interruption checks] Output must be a new private directory
(0700, files 0600). The target file and directory are synced before writing the
receipt. Complete receipt bytes are written and synced under a pending name;
an exclusive hard link publishes `receipt.json` without replacing another
file. A partial receipt write or receipt fsync failure leaves no final marker.
An incomplete directory cannot be reused. Consumers must check target hashes
and the complete receipt; a later unlink/directory-fsync failure can leave a
complete marker while the operation reports failure, and does not establish
confirmed power-loss durability.

## Focused verification

[verified: Hera container receipts] Sixteen parallel isolated chunks ran the
builder and independent raw-profile tests against a frozen source snapshot:
**42 passed, one optional private-reference test skipped, zero failures or
errors**. All sixteen containers exited zero, had no OOM, and were removed.
These are synthetic format/durability tests, not device acceptance or exact-head
whole-suite CI. The fixture changes one sector; native SDK multi-sector coverage
remains pending.

| Evidence | SHA-256 |
| --- | --- |
| Source snapshot on base `fc8e3414` | `78c770759dcb813835fc6e50daf69f6b843d5ef006ef030cf76efb8fb5b0d9b7` |
| Builder source | `80c0296aca20eea8ea51aa3ae4a7dedf9dddb5a910e9dbd614e42a852ea24915` |
| Builder tests | `bca12506b5d750c779004b8af17f08fce4427f0f2dff63d2aec8c9e85fef5087` |
| Sixteen-chunk node plan | `495860f6da4e1a0322545621d22aff91121b096659f96010131bd4ea80309a84` |
| Container image | `7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d` |

Saved receipts: local ignored `build/raw-emitter-hera/`; Hera
`/home/claude/mvave-fm1/raw-emitter-20261011/`. Independent initial review is
`build/raw-diagnostic-emitter-review.md` (findings repaired and re-reviewed in
the parent coordination record). The installable-image goal remains active:
native SDK startup/recovery audit, new backups, guarded installation/restoration
and physical execution/panel/recovery evidence are still required.

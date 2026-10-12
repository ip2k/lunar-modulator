# Canonical owned trace-return admission to loader backup and stock restore

This successor stream starts at pushed checkpoint
`ee6d5a1314bfcee06ea8e8b2bc79b5d99a45401a`. Root owns commits, pushes and all
hardware. These new files are closed scaffolds; no hardware operation or returned
recovery authority has been accepted for them [verified: source gates].

The original `fm1_sdk_trace_returned_backup.py` (`885666163ed48a466aafab33a483438af779a6ab3e7ea3cf51f26d25f4fa21a4`)
and `fm1_sdk_trace_stock_restore.py` (`95e7c3ee4b191d515abc95f57ab102c43835a83fbe6182075ba080c9ec1e7e84`)
remain unchanged. Their old closed evidence kernel is not an admission source.

Before implementation: a durable read receipt establishes historical provenance;
it does not establish that the connected ROM session is still unchanged. The
smallest separate path preserves the canonical proof and adds a fresh passive
same-port witness before a single reviewed loader upload. The retained-RAM trace
must already have been read before that upload clobbers its allocation.

`tools/fm1_sdk_trace_admitted_backup.py` uses its own Prepared identity registry,
campaign kind `fm1-sdk-trace-admitted-fixed-loader-target-backup`, distinct
`trace_admitted_backup_*` events, and `.sdk-trace-admitted-loader-{original boot
campaign SHA}.consumed`. The marker is independent of admission JSON encoding and
receipt name. No marker is removed on ambiguity. `PROOF_SOURCE_SHA=None` closes
both the opener factory and completed-evidence helper until the canonical
`fm1_sdk_trace_return_admission.py` successor and genuine runtime are accepted.
The canonical import has the exact tools path and source pin checked before and
after import; its ReturnedProof must have exact class identity and pass its own
registry/check. Python/interpreter and ancestor directories remain trusted.

The backup envelope retains the prior twelve fields: schema/kind/adapter SHA,
returned admission path/SHA, connection witness path/SHA, loader/profile/profile
source paths, active session state and receipt path. Its witness kind is
`fm1-passive-sdk-trace-admitted-backup-connection`, with schema, observed_at,
usb_binding, sg_binding, original_rom_snapshot_sha256, returned_admission_sha256,
and quiet_state. Original snapshot bytes/time/SHA remain unchanged. The witness
must follow the original read terminal and match original USB/SG identity,
including current devnum and descriptor identity. Its 120-second admission/open
freshness is separate from the inherited ten-second first-operation bound and
900-second full dual-read window. Immutable evidence and live FD/sysfs binding
remain checked through the full operation; original snapshot freshness is not
reapplied at publication [verified: reused source checks]. Operator attestation
of no intervening commands is explicit; advisory flock does not exclude unrelated
kernel clients.

The exact `afeefe7b…` private SG body, `f6964845…` dependencies and original reviewed
8757-operation inventory are retained. Only INQUIRY, fixed FC14 uploads, FC0A and
FD05 reads are used. Both independent complete 1 MiB dumps must equal target
`5dbada6531e0ad68b1902b4f0d97cc6f78d7fa338b1360c194f98c1475ad7a3d`.
The completed helper replays every intent/completion, page digest, dual dump and
manifest, preserves the consumed marker, and returns the canonical proof plus
positive/negative evidence. The full original install/boot evidence is included
in the frozen inventory, not only the read receipt.

`tools/fm1_sdk_trace_admitted_stock_restore.py` has a distinct restore schema,
`trace_admitted_stock_restore_*` events and `.sdk-trace-admitted-stock-restore.consumed`.
Both BACKUP_SOURCE_SHA and POLICY_SOURCE_SHA remain None. It pins the exact f583
private policy/transport/replay machinery, registers only freshly created private
objects, and adds its own Prepared registry. The original completed install
journal is saved exclusively before opening SG; only that current mutable journal
is excluded from later immutable checks. Initial full target readback must pass
before any erase; thirty protected-plan sectors restore stock
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`, with directory
0x4000 last, exact aligned 4 KiB erases and CRC-sealed 256-byte programs. Final
full stock readback, completed restore journal and strict transcript replay are
required. The completed helper reconstructs original install using the preserved
journal and returns `_proof` plus exact `_absent_paths` for downstream drift
checks. No upload, reset, read retry or partial-NOR admission is added.

After implementation: the original evidence-only factory is now the sole proposed
provenance source; the new witness cannot refresh it. This is source architecture,
not CPU/SPL recovery proof. Warm reset with corrupt/partial application and USB_KEY
availability remain separate physical questions. No physical fault injection is
authorized in this lane.

Pending: closed mechanics tests on Hera in thirty chunks; independent source
review; final canonical admission/native/reader literal acceptance; genuine new
backup→restore composition and completed-helper/preserved-journal/post-intent drift
checks; root-only concrete fresh witness, image/recovery packet and hardware review.

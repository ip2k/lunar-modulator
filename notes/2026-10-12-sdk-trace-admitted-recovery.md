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
900-second full dual-read window. Live FD/sysfs binding, source pins and negative
evidence are checked per operation. Full positive evidence is rechecked before
ROM operations and publication, rather than reread for every FD05 page. Original
snapshot freshness is not reapplied at publication [verified: reused source
checks]. Operator attestation
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

Final closed mechanics gate: V3 passed 56 unique planned cases in thirty Hera
chunks, plus one witness smoke, with no failures, errors or skips [verified:
retained XML and author replay]. All 32 collection/smoke/shard containers used
image `sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
two CPUs and 2 GiB memory; Docker's combined memory/swap allowance was 4 GiB.
Source/jobs mounts were read-only, evidence writable, network disabled, no device
or GPU requests, and no privileged execution. Every exit was zero, no container
was OOM-killed, every named removal succeeded, and the retained structured
exact-label lookup was empty.

The archive contains 1,759 pinned regular files. Its SHA is
`f46d1dd949186f4460b9dfd7c39503f28dabc2eba261903e077d6154aea2db2b`;
runner `d2733a951ae8399d704f7e5080aea9af1eb27147b49f4d3c682029eef4e9729e`;
plan `fa8ed1e63ac41bf9ab9ad6d01a2bfc85e623ff889675d9acc15a17c5214390a7`.
The exact tested backup source is
`6f50c4d849382cf73b66bab75e04f1c6dc754a1e982ceb10599cc48fe70d9296`;
restore `41ef264d07c45d0e7fab347849139797f57fd5fdac6598f6240c8f343ba2da71`;
unit tests `8c1173dfb39864610b5073d4730795e3064d0f91422147325afa26626f509c3c`
and `0d131da25e570683cd692b0088d96a77d734f571ad449e095b88c1c45c47a051`.
Author replay `build/sdk-trace-admitted-recovery-hera/author-check-v3.json` is
`ae77fefe5086963dedebdf830d33a9f2ad1cfb65b6f4998d291cac1ed7ac7372`;
artifact index `756c2e9250e0c29e0031d4a8abc0ebbf5732e4e0e039e8b9407d916dc2a00b61`.

Failure provenance is retained: V1 stopped at collection because the ignored
runner omitted tools from PYTHONPATH. V2 corrected only that runner setting and
passed 55/56 cases; its source-contract case detected a private import of the new
admission module. V3 changed only the backup's canonical import/path/source-pin
check; the other 1,758 archive files are byte-identical to V2. No factory pins or
registries were replaced. Parent checkpoint `81a91f1f0da9cef74d598edfbba975eaaac61296`
preserves the original WIP bytes; V3 and its failure receipts remain distinct.

These cases test closed factories, historical-versus-current witness checks,
one-boot consumption, copied-object rejection, bounded input files, full-target
read-before-write ordering, corruption/latching and injected post-submit-intent
absence drift. The restore registry/transport fixtures are explicitly modeled;
their callback test is not evidence of an actual durable worker intent or a
genuine canonical backup/restore factory. No physical commands ran.

[verified] Root fully read and accepted the independent closed-scope runtime
report `52d2d979c433814dd2b5a1c98b2a99d1a6ee941eaae7d27650232c6031f3bdee`
and check `4e488459c4ff4be84f59db56f3e6d44e7c854d3af28984cd1b80cc00eb520862`.
The canonical-import correction has separate source acceptance; the preceding
source review that missed this contract remains unaccepted. Root acceptance is
saved in the ignored evidence directory and does not activate either factory.

Pending: final canonical returned-admission runtime acceptance; genuine new
backup→restore composition and completed-helper/preserved-journal/post-intent drift
checks; root-only concrete fresh witness, image/recovery packet and hardware review.

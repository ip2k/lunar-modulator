# Fixed-loader stock return after the SDK rehearsal

Personal, non-commercial; offline implementation and review only. No hardware
traffic was sent by this lane. This milestone is a separate stock-return gate,
not permission to boot the diagnostic target.

## Fixed scope and evidence

[verified] `tools/fm1_fixed_rehearsal_reset.py` provides an independent campaign
schema, exact-instance factory authority and one-use marker. It preserves
`fm1_fixed_loader_reset.py` (baseline backup/no-later-command gate) unchanged.
It executes the hash-validated baseline adapter's SG binding and single literal
FC0C argument-1 request methods, with an independently authorized constructor.
There are no upload, online, NOR read, erase, program, eFuse or retry paths.

The source pins are baseline reset
`dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116`
and rehearsal
`f696484511754b91d4faf449aa2e4cab3ca910daf05a9acd66daa966bae7d6c4`.
The latter logs SHA-256 of each actual input response. Factory validation seals
that source and every dependency in its literal SOURCES inventory, recomputes
the actual SDK policies and checks both immutable 1 MiB images, the original
private backup manifest and complete 8,757-command backup inventory. This
establishes historical fixed-loader provenance; it does not establish current
RAM provenance independently of the operator's no-later-command attestation.

[verified] Transcript replay requires successful exit 0 supplied by the bench
operator; ordered install then restore; exact durable mutation intent and
return checkpoints; CRC/payload hashes and framed request sizes; clean SG
status/sense/residue; directory sector 0x4000 last in both directions; sector
verification checkpoints; each expected 256-byte read response hash, including
the final 4,096-page baseline readback; exact direction verification and final
completion/result claims; and a complete restore journal with baseline digest.
Timer-driven FC0A requests are allowed only once before a read page. No extra
command, missing completion or subsequent stop event is accepted.

The journal and all evidence bytes are frozen and checked again before SG
opening and request submission. Current connection verification uses the
original recorded SG node/inode/device number and USB/sysfs identity, an open
character-device FD, advisory flock and pre/post-operation checks within the
existing ten-second live binding window. Advisory flock does not exclude
uncooperative tools. No host receipt can prove the absence of another process's
commands; trusted bench operator attestation is an explicit boundary.

## Exact campaign shape

All paths are absolute direct regular files. Receipt is a new child of the
original private backup receipt, not the rehearsal receipt. Hashes describe
actual bytes. The same original backup parent hosts the exclusive durable
`.post-rehearsal-core-reset.consumed` marker, so renaming a receipt cannot retry
this stock-return attempt. An existing baseline reset marker is rejected.

```json
{
  "schema": 1,
  "kind": "fm1-fixed-loader-post-rehearsal-stock-reset",
  "adapter_sha256": "FINAL_NEW_ADAPTER_SHA",
  "rehearsal_adapter_path": "/absolute/tools/fm1_sdk_rehearsal.py",
  "rehearsal_campaign_path": "/absolute/rehearsal-campaign.json",
  "rehearsal_campaign_sha256": "ACTUAL_CAMPAIGN_SHA",
  "rehearsal_commands_sha256": "ACTUAL_REHEARSAL_COMMANDS_SHA",
  "rehearsal_result_sha256": "ACTUAL_REHEARSAL_RESULT_SHA",
  "rehearsal_exit_status": 0,
  "journal_sha256": "ACTUAL_COMPLETE_RESTORE_JOURNAL_SHA",
  "active_session_state": "same-fixed-loader-restored-rehearsal-no-later-commands",
  "usb_binding": "EXACT_ORIGINAL_BACKUP_USB_OBJECT",
  "sg_binding": "EXACT_ORIGINAL_BACKUP_SG_OBJECT",
  "receipt_path": "/absolute/original-backup-receipt/post-rehearsal-reset"
}
```

The USB/SG placeholders above mean the original full JSON objects, not strings.
The schema deliberately provides no target-state field or alternate direction.
A diagnostic boot trial needs a distinct, explicitly authorized target-state
campaign and implementation; this stock-return factory rejects install-only or
altered-baseline evidence.

After independent review and the parent's concrete physical gate:

```sh
python3 tools/fm1_fixed_rehearsal_reset.py --campaign /absolute/post-reset-campaign.json
```

[verified] Native FC0C argument-1 assurance is conditional on the reviewed
zero-context fixed-loader path: it sets JL_POWER bit 4 at 0x10000 and spins;
reset can precede the ordinary reply. See
`notes/2026-10-11-fixed-loader-baseline-reset.md` and the separate NOR native
review. External initializer 0x01e00428 remains unclosed. A lost reply,
detach, re-enumeration, persistence or close failure consumes/closes the
attempt; it is not proof of reset or boot and must not trigger retry.

Accept reset request completion only with successful process exit and the
complete durable receipt. Independent normal enumeration, FM-1_092 identity
and owner's visible behavior are required to claim stock boot. No device read
is performed here to replace those observations.

## Verification and handoff

Frozen adapter SHA is
`743ac876a9906cb19a28b82b09b6a60f96117b9fdbdbc80beaf63b8bd65080f6`;
tests SHA is
`2ebf29e6cc920de4f465ae86ffd425bdd6e5cff04a256670131558da9b43819e`.
Independent review found an intent-to-ioctl file-drift gap; the frozen repair
rechecks all file evidence inside each binding check, including after the
intent callback, and a negative test requires a consumed, closed attempt with
zero SG_IO submissions on evidence drift.

Hera frozen-source verification is running in
`/home/claude/mvave-fm1/fixed-post-reset-20261011`; local recovery artifacts are
`build/fixed-post-reset-hera/`. Archive SHA is
`7b353c798b4c78950743ecd3016ad5e2f5d26a96d4a2455b079c5ddf636c9307`.
Collection found 107 unique nodes: 59 new post-rehearsal tests and 48 unchanged
baseline-reset tests, with 16 chunks (eleven of seven and five of six). Actual
private image/ELF/backup inputs are mounted read-only, then copied to each
disposable container; SG operations are mocked. The initial harness collection
failure from bare sibling-test imports is retained under evidence-v1; the v2
harness supplies the test/tools PYTHONPATH without changing frozen source.
All final checks and independent acceptance are pending. Parent owns commit/push and hardware activation.
Branch `feature/2026-10-11@installable-firmware`; inherited checkpoint
`a64c0b381285222ed68969779619ee5ffc3b4671`. This lane creates no commit and makes
no pushed claim for its uncommitted new files.

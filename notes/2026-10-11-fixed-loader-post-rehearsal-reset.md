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

[verified] Hera frozen-source verification completed in
`/home/claude/mvave-fm1/fixed-post-reset-20261011`. Recovery artifacts, runner,
XML/logs and Docker inspections are saved locally in
`build/fixed-post-reset-hera/`. Archive SHA is
`7b353c798b4c78950743ecd3016ad5e2f5d26a96d4a2455b079c5ddf636c9307`;
snapshot SHA is
`5ed7c9619e63b2c0776971ad033285b9a2b7cfb72955a322e0cfc0a1ffee6622`.
The archive contains 535 source/test/configuration files. Every archived file
was checked against the snapshot inventory before collection; the independent
reviewer also verified that inventory.

Collection and independently parsed XML match all **107 unique nodes**, with
zero duplicates, failures, errors or skips: 59 new post-rehearsal tests and 48
unchanged baseline-reset tests. Sixteen parallel chunks contain eleven groups
of seven and five groups of six. A preceding actual-private-fixture smoke test
also passed; the same scenario passed again in its assigned shard. It loads
the actual private ELF/app/backup/profile/audit inputs, performs a modeled
install plus restore with the production rehearsal adapter, accepts the full
receipt through the new production reset factory, and rejects a re-hashed
forged success result. Each test container copies its read-only private inputs
to a disposable model directory. All SG operations are mocked: this establishes
software/evidence acceptance, not physical flash, loader, reset or boot behavior.

The fixed image is
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
(`lunar-recovery-pytest:20261011`, Python 3.11.2). Collection, smoke and sixteen
shards all exited 0 and reported OOMKilled=false. Each container had 2 CPUs,
2 GiB memory/equal swap, docker-batch.slice, network=none, no devices and no
privilege. All eighteen containers were removed; an independent final
`docker ps -a` campaign-label check found none remaining. The first harness's
bare sibling-test import collection failure (exit 2, no OOM) is retained under
`evidence-v1/`; its container was removed. The v2 harness supplied the
`tests/tools` PYTHONPATH without changing frozen source. The parent's later
pytest configuration fix in `52b4802193fe808dc326b586eaa96a65bd7d51a8` provides
the sibling-test path for ordinary collection; that configuration change is
outside the frozen archive, while the adapter/tests and all literal runtime
policy dependencies remain byte-identical.

Evidence pins relative to `build/fixed-post-reset-hera/`:

| Artifact | SHA-256 |
| --- | --- |
| `plan-v2.json` | `b85deceec7cbd794ca6b4c634f40b194788c20a3c70de97d7064b32167d199bc` |
| `aggregate-v2.json` | `75175e2beface18e821e8d7b4766c8a8463fbab396336a97c121bda47d215fde` |
| `independent-evidence-check.json` | `28d0e18f838541ba6e0c0cc04bf46d9306643e8d03d7cbc2d091c36f877f0519` |
| `container-removal-check.json` | `25a9f96bd0a757af2b390c1a4bfd99ccc6a29ba9da7205d2ef5a3fe4945a68d7` |
| `run.py` | `f400d0d4ebaed1643bfce913b259f953597307dae705886a48f99d8bfcccd1d8` |
| `verify_evidence.py` | `baceb53b7fe94adfa6acf4564c07171409e3ab4706cb1c99c5ad40ca06cc2208` |
| `evidence-v2/5/post-reset-factory-accepted.json` | `113910be3bdde7d08e7cfb9290360d7b07e1c960473a0aa76379cda6cff54308` |

[verified] The independent reviewer accepted source `743ac876…` and tests
`2ebf29e6…` after the intent-boundary repair, with no remaining material source
blocker. Final independent source/test/evidence acceptance is saved in
`build/fixed-rehearsal-reset-review.md`, SHA
`c978a80195893ce65ff568c80eedf77f8add134d716d1758ebfc5c025462e8e9`.
The conditional native FC0C assurance and explicit operator/exclusivity
boundary above remain unchanged.

Parent owns commit/push and hardware activation. Branch
`feature/2026-10-11@installable-firmware`; source/tests entered parent checkpoint
`6188d8fc7c7920f9948d5103e25aa37510461b13`, pushed with remote SHA verified by
the parent. The latest inherited pushed checkpoint is
`52b4802193fe808dc326b586eaa96a65bd7d51a8`; this final note update is pending
parent commit/push. This lane creates no commit and sent no hardware traffic.

[reported: parent and independent reviewer; saved reports inspected here]
The physical SDK rehearsal subsequently completed. Independent review of
`build/sdk-rehearsal-physical/` accepted all 45,100 events through the exact
frozen replay, both full image readbacks, the completed restore journal and
21,498 ordered vendor commands in bounded usbmon capture. Parent observed the
outer wrapper process exit 0. This lane sent no device traffic and does not
claim its own physical observation. The capture proves bounded framing and
prefixes, while full page content is established by the separately logged
readback hashes. The diagnostic application was never booted in this rehearsal.
Actual log SHA is
`20a28322c032858d01da0b9c5ca8b4d45023fecebe8dcd49c948061aa4f8caac`;
result SHA is
`229894c81b9207d50c6fe9bebebdbc385d745bf1595704aa841f6ad64c9aa4fc`;
completed journal SHA is
`5a684c7d63ba88dfb33469822c452d0f606fb8bee9ab6e9da716c3f35cfd00f6`.
See the independent scope/limitations in `build/sdk-rehearsal-review.md`.

**Next dependency:** root creates the fourteen-field stock-return campaign
from the accepted actual physical log/result/journal and original USB/SG
objects, attests no later command in the same fixed-loader session, and runs
the actual-file factory preflight. Recheck the original live FD/sysfs binding
and pass the parent's concrete physical gate before the single reset request.
Actual reset, normal enumeration/identity and owner-visible stock boot remain
unobserved by this lane. A separate diagnostic boot trial still requires its
own target-state gate.

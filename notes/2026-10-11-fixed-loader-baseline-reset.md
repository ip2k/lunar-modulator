# Fixed-loader active-session baseline core reset

2026-10-11. Prepared offline on branch
`feature/2026-10-11@installable-firmware`, observed source checkpoint
`6e024411651335617204bbb9267043896e3a9158` (parent reports it pushed).
This lane made no commit, push or hardware request. Parent owns independent
source review, the concrete physical decision, checkpoint/push and observation.
The overall installable-diagnostic goal remains active.

The new [adapter](../tools/fm1_fixed_loader_reset.py) and
[tests](../tests/test_fixed_loader_reset.py) implement a separate policy for
one FC0C argument-1 request from an already-active exact fixed-loader backup
session. Existing `fm1_loader_reset.py`, `fm1_fixed_loader_backup.py` and
`fm1_uboot_read.py` remain unchanged. [verified: source inspection and hashes]

## Native command review

The actual patched vendor listing is
`/tmp/lunar-loader-config-20261011/loader.patched.vendor-disasm.txt`, SHA256
`f8aeedf382158f17627ce119b01e451ab5611b6cafed485dca385a226334776e`.
Its independent full-image byte check, vendor objdump pin and configuration
review are in ignored `build/loader-config-native-review.md`. The decoded
candidate SHA256 is
`a228c6fa2dd733802723099dab8216edbfbdfcef1dc155ffcd8ac2b96fd480af`.
[verified: local private file hashes; prior independent vendor listing review]

In that actual listing, FC table index3 at 0x01c042cc selects 0x01c0477c.
The entry clear at 0x01c02004 clears 2,000 bytes starting at 0x01c09600,
including context 0x01c09700+16. The command's zero-flag branch skips its
optional configuration callback. FC16 can set the flag; the admitted backup
inventory and this reset envelope contain no FC16. [verified: actual native
listing; bounded direct command path]

FC0C changes USB control registers, normalizes arguments below decimal100 to
zero delay, logs through UART polling and branches
0x01c047e8 → 0x01c04b6e → 0x01c0292c. That final routine ORs bit4 at 0x10000
and spins. The primary SDK identifies this register as `JL_POWER->CON` /
`JL_CLOCK->PWR_CON`, and `dbg.config` identifies bit4 as soft reset, as recorded
in [the original reset review](2026-10-11-loader-run-app-reset.md).
[verified: actual candidate listing and previously checked primary SDK]

Independent original/candidate byte comparisons found these spans unchanged:

| Half-open native span | SHA256 of decoded span |
| --- | --- |
| 0x01c042c6–0x01c042ce, dispatch table | `007a00648c17fd3d2daddf435e2841e64bb41774953d24ae64301476153f1323` |
| 0x01c0477c–0x01c047ea, handler | `1d64d35cbf69d6818934ba554874a7e49452c972863eea0e0bd8acdcdb316011` |
| 0x01c04b6e–0x01c04b72, reset call | `14346b52e8774ea1962caa4f7ebafd2cf95fdc7dac7a004983f5fd27838d983c` |
| 0x01c0292c–0x01c02936, reset routine | `0f0113c68f495794f2170fac4aea090d1c8c7720b6675c3b871403ef2b0d2600` |
| 0x01c023e0–0x01c0244c, logger span | `c260ef482c04ec0b51700be106ebd963209d9ea0d1182fe3c37cf730f4140229` |
| 0x01c0354e–0x01c03560, delay helper | `599722614c40d655b00eeffc6f51b607873fea97787dc992be5a235fd9ca786e` |

[verified: whole-file hashed decoded inputs, bounded span comparisons]

This is a core-reset request. The native handler reaches reset before the
common normal response path; an ordinary reply is not guaranteed. UART,
transport stalls, recovery-mailbox retention and the eventual ROM/SPL boot
path remain separate limits. The traced reset command does not reach flash
programming or eFuse handlers. This narrow statement does not certify all
earlier loader initialization or external operation implementations.
[verified: traced native path; unknown external/ROM behavior]

## Exact policy and receipt boundary

Factory preparation reads each input once through a bounded regular-file,
NOFOLLOW/CLOEXEC/NONBLOCK descriptor. It validates the exact backup adapter and reader
source before compiling their already-hashed bytes into isolated namespaces.
The candidate, profile and profile-source pins remain fe6d1bd…, 3c03e413… and
9664e132… respectively; original-loader provenance remains d41da612….
[verified: adapter source]

Only exact factory-created PreparedReset instances are accepted by the transport
and runner. Copies, replacements and direct reconstruction are rejected before
discovery/open. NONBLOCK makes FIFO rejection possible without waiting for a
writer. These independent-review repairs have seven focused negative cases.
[verified: source; Hera r3 tests]

The factory independently hashes both full 1MiB dumps, checks all 17,516
backup log events, all 8,757 alternating intents/completions and their exact
inventory digest, rejects failed/extra events, and validates the original
FM-1_092 entry at the recorded backup completion time. Historical preparation
has no current-age cap. It neither discovers sysfs nor opens hardware.
[verified: source; offline positive/negative tests]

The root-reviewed campaign must assert successful backup exit0 and
`active_session_state="matching-backup-no-later-commands"`. These are trusted
operator assertions, not independent process-exit or exclusive-device proof.
Any later command or flash mutation invalidates this baseline policy. A reset
after installation or restore needs its own accepted exact flash-state policy;
this adapter does not imply that gate is satisfied. [verified: schema; policy]

The new reset receipt must be a direct child of the pinned private backup
receipt. Its fixed `.baseline-core-reset.consumed` marker is exclusive and
durable before device discovery/open, preventing reuse by changing reset
receipt names. All reset log events are flushed/fsynced, with directory fsync.
Failed/partial receipts are never success evidence. [verified: source/tests]

The opened SG descriptor must match the entire recorded USB/SG/sysfs mapping,
character-device inode and `/sys/dev/char` mapping, checked before and after
the operation. A 10-second monotonic live budget starts at discovery; SG_IO
timeout is 3 seconds. Flock is advisory, and these checks cannot independently
prove current RAM execution or exclude another kernel client. No status probe,
upload, memory access, flash command or retry is admitted. [verified: source]

The sole CDB is `fc0c00000001ffffffffffffffffffff`, with 16-byte input and no
output payload. Its durable intent precedes the sole syscall. Any binding
change, disconnect, status/sense/residue/error, echo mismatch or close failure
consumes and closes the attempt. A fully accepted reply records request
completion only; both `core_reset_observed` and `boot_observed` stay false.
Root must independently observe the resulting device/stock behavior. Expected
disconnect is still an ambiguous host completion and cannot authorize retry.
[verified: source/tests; hardware behavior untested by this lane]

## Campaign shape and next step

The exact schema accepts only these fields:

```json
{
  "schema": 1,
  "kind": "fm1-fixed-loader-baseline-reset-campaign",
  "adapter_sha256": "dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116",
  "backup_adapter_path": "/absolute/stage/tools/fm1_fixed_loader_backup.py",
  "backup_manifest_path": "/absolute/attempt-001/manifest.json",
  "backup_manifest_sha256": "root-reviewed actual manifest hash",
  "backup_campaign_path": "/absolute/campaign.json",
  "backup_campaign_sha256": "root-reviewed actual campaign hash",
  "backup_commands_sha256": "root-reviewed actual commands.jsonl hash",
  "backup_exit_status": 0,
  "active_session_state": "matching-backup-no-later-commands",
  "usb_binding": {"path":"3-2","busnum":"3","devnum":"23","vid":"4c4a","pid":"8057"},
  "sg_binding": "copy the complete actual manifest object here",
  "receipt_path": "/absolute/attempt-001/core-reset-once"
}
```

This is a schema illustration, not an executable campaign. Root's actual
private evidence copy is `build/fixed-backup-physical/`; the actual manifest
hash is `1ab5e38943648080d9fde9fa86197607aa7a0e01c19da62cd20f24e8f11280cf`,
campaign hash `79000ac37e0f312d6edf30e810acd09ce551c51c061fcf48aede212d86f61a6e`,
commands hash `e626e30e6ea58d3ee6c01aa199af1b678c75615439429ec54dcd8f905525628e`.
Root reported exit0 and no later commands; this lane did not independently
observe that bench exit or live session. [reported: parent; verified local
copied manifest values]

After review and checkpoint/push, root stages the frozen source alongside
both pinned dependency files and seals its actual campaign. The only CLI is
`python3 tools/fm1_fixed_loader_reset.py --campaign /absolute/reset-campaign.json`.
Preparation can be reviewed independently through `prepare_campaign(path)`
without running `run_campaign`. This lane did neither against hardware.

## Offline verification

Frozen adapter SHA256:
`dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116`.
Tests SHA256:
`8bca419d40b3a96c98ea98a98f69cfc18e6bc65d5156ed4c0124ad66cc4e6283`.
The shared-source snapshot archive SHA256 is
`f5957b655900df226921214524fc2fe5a0e92829de4fa28bd0e2d9cdd9b154c3`;
source manifest SHA256 is
`63e2d7cdbdd1ff3ea061fd7a4259b7f435873fac478a0fc1d5d9194024321945`.
[verified: generated/read back local and Hera artifacts]

Hera directory `/home/claude/mvave-fm1/fixed-reset-20261011-r3`, mirrored to
ignored `build/fixed-reset-hera-r3/`. Pinned image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`
(`lunar-recovery-pytest:20261011`, Python3.11.2). Sixteen parallel containers
used 2 CPUs, 512MiB, equal memory-swap limit, `docker-batch.slice`, network
disabled, no privilege or device mounts. The actual original private loader
fixture was mounted read-only; no vendor binary enters tracked source.
[verified: runner scripts/container inspections]

Exactly 185 unique collected nodes passed once: 48 new reset tests, 53 fixed
backup tests and 84 existing old reset tests. Shard counts were
12,12,12,12,12,12,12,12,12,11,11,11,11,11,11,11. No skip, failure or error;
JUnit identities matched the plan with no missing/duplicate nodes. All16 exit0,
OOM false, removed; final session-specific `docker ps -a` was empty. Initial
unused collection snapshot `fixed-reset-20261011` started no shard containers;
the final r3 source above is the tested source. [verified: saved receipts]

Plan SHA256 `25c5a23953d78f1902f91835c225933857ed3c32195636941baf12b6701e65c8`;
aggregate SHA256 `0cb6b9d573193bb4d5c626ab77edb94ed30afd03548eac149199a18d5cea367a`;
container-summary SHA256
`2d6cc73e51887a8c9f1c77ce45b726ceb3e09d71cb6d9f2522c3df613b49af8c`.
Independent repaired-source review `build/fixed-loader-reset-review.md`, SHA256
`67b505cba2a2e47a4b14770e660f09b598e30e452cd3653d118cc9aaa3376333`,
found no remaining actionable source defect and independently checked all185
XML identities/16 container receipts. Its native assurance retains the external
initializer/entry-supplied-operation limits. Syntax parsing and `git diff --check`
also passed. No heavy local test, physical
reset, observed boot, whole-image restore or installation claim is made.

Semantic-tool limitation carries forward: Rarefaction/Serena select the primary
checkout, not this shared worktree. This lane used actual source, known tests
and native listing inspection, and did not change shared selection or restart
servers. Root's next dependencies are independent review acceptance, concrete
baseline-session assertion and physical observation after a single request.

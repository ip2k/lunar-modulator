# Exact fixed-loader read-only backup adapter

This is offline implementation evidence for the personal, non-commercial Lunar
project. No hardware operation was performed by this lane. The separate adapter
does not change the original loader guard or `fm1_uboot_read.Reader`.

## Frozen review inputs

- Adapter: `tools/fm1_fixed_loader_backup.py`, SHA-256
  `79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb`.
- Mock tests: `tests/test_fixed_loader_backup.py`, SHA-256
  `6ed202c85f7c78b1302af3139589d94452eac5eff8e229e1582c5814b123a99c`.
- Exact encrypted candidate: `fe6d1bd36c8ffe4674e4a05ee748fe87480b5867fac58230b14ff089d411012c`,
  24,064 bytes. Private artifact:
  `/tmp/lunar-loader-config-final-20261011/loader.patched.encrypted.bin`.
- Candidate profile: `3c03e413b9df29d85e4c07d886d9bfb9b3ab2fc66845d5220f82998dd44f4afe`;
  private `profile.json` in that directory.
- Profile source: `tools/jieli/loader_config_profile.py`,
  `9664e1329d8259362da78c047ce2d6003dfe8df2850f02703f98e8b6bf277cd8`.
- Framing/SG layout dependency: `tools/fm1_uboot_read.py`,
  `28317ee56a489e0bb38de981fe0d0c4260384be570349795741fdb9a98d6ae57`.
  The factory reads its pinned bytes once and executes those bytes in an isolated
  module namespace. It never instantiates its original `Reader`.
- Original private loader, used by `FM1_LOADER_PRIVATE` focused tests:
  `/Users/likwid/Developer/mvave-fm1-firmware/reference/jl-uboot-tool/data/loaderblobs/usb/wl82loader.bin`,
  24,064 bytes, `d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376`.
  Tests requiring this variable need that encrypted original, not the patched or
  decoded candidate; the root owns its private Hera/container staging.

## Sealed command envelope

There are exactly 8,757 operations. Canonical request inventory SHA-256:
`f99b6e738d19d24442ad4d056985e6f4dc200d0b09059b80428f4ff989838017`.
It seals phase, CDB, label, outgoing payload hash and lengths for every operation.
The device constructor checks the digest before discovery/open.

1. ROM inquiry, requiring WL82 / UBOOT1.00.
2. Exactly 47 FB06 uploads of the pinned candidate, 512 bytes each, beginning at
   `0x01c02000`; every upload is checked against the pinned profile inventory.
3. One FB08 jump to `0x01c02000`, with the pinned ROM framing's argument.
4. FC14 buffer query, then FC0A online query.
5. For each of two 1 MiB dumps: FC0A before every group of 16 FD05 pages, 256 bytes
   per page from flash offsets zero through `0xfff00`, then FC0A at pass end.

There is no erase, flash program, reset, eFuse or caller-selected command/range.
The ROM-to-loader phase advances only after a successful jump completion. Any
syscall, binding, residue, status, masked/message status, sense, echo, inquiry or
flash-identity ambiguity consumes the operation, latches failure and closes the
descriptor. Re-enumeration is ambiguous even if the jump returned a reply. The
adapter never reacquires or retries.

## Campaign and receipt contract

The exact campaign schema below has no additional keys. All paths are absolute
private staged paths. The bench owner supplies the fresh entry hash and current
USB topology; historical or test devnums are not campaign evidence.

```json
{
  "schema": 1,
  "kind": "fm1-fixed-loader-backup-campaign",
  "adapter_sha256": "79bbe99ce923daaf8af2c701a65ec39a015191313de79676e36622cb8db00afb",
  "loader_path": "/PRIVATE/candidate.encrypted.bin",
  "profile_path": "/PRIVATE/profile.json",
  "profile_source_path": "/CHECKOUT/tools/jieli/loader_config_profile.py",
  "entry_log_path": "/PRIVATE/fresh-softkey.jsonl",
  "entry_log_sha256": "FRESH_REVIEWED_ENTRY_SHA256",
  "usb_binding": {
    "path": "CURRENT_ROOT_PORT",
    "busnum": "CURRENT_BUS_NUMBER",
    "devnum": "CURRENT_ROM_DEVICE_NUMBER",
    "vid": "4c4a",
    "pid": "8057"
  },
  "receipt_path": "/PRIVATE/FIXED_CAMPAIGN_PARENT/NEW_RECEIPT"
}
```

Entry validation requires one each of the actual five ordered probe events:
`before`, `sending_identity`, `identity`, `sending_soft_key`,
`uboot_enumerated`. It requires the same-port normal `4c4a:c755` observation,
the exact identity request, the exact captured owner's known FM-1_092 reply
(SHA-256 `7679e7be907c6cc32b3c1f27c48cc8ce6daa865852e8021e2207cdeae223217d`),
the exact soft key, and the projected five-key ROM USB binding. Genuine probe
`product`/`speed` fields are accepted. Failure/stopped events, duplicate steps,
wrong raw identity, another port, or timestamps older than 600 seconds reject
before hardware open. Freshness is checked again immediately before open.

The receipt parent must be a direct private directory with mode 0700. Root must
keep one fixed campaign parent: the durable exclusive `.entry-HASH.consumed`
marker blocks reuse within that parent, including another receipt name. It is
an operator boundary, not a global anti-replay service; copying an entry into
another campaign parent is not independently prevented.

The factory bounds reads, refuses final-component symlinks, and verifies every
source/artifact hash before SG discovery/open. Before and after each command,
the adapter checks USB topology/devnum and the descriptor/sysfs ancestry,
direct character node, major/minor mapping and inode identities. Its advisory
flock does not establish kernel exclusivity. Passive USB capture and ownership
of the bench session remain external responsibilities.

Receipt files are exclusive 0600, directory 0700. Upload/jump intents and source
provenance are durable before the syscall; ordinary read/online records flush
without a per-command fsync. Both complete dumps and the completion manifest
are fsynced, directories synced, and each durable dump independently re-read
and hashed. The durable completed log precedes final manifest publication.
Failure attempts to remove the success manifest and writes an ambiguous stop;
a storage failure may prevent either action. Acceptance requires successful
process exit, a completed event with no later stop, and the matching parsed
manifest; a filename or completed event alone is insufficient.

Exact completion manifest keys:
`schema`, `kind`, `loader_sha256`, `original_loader_sha256`,
`loader_profile_sha256`, `profile_source_sha256`, `adapter_sha256`,
`dependency_sha256`, `campaign_sha256`, `request_inventory_sha256`,
`entry_log_sha256`, `unit_identity`, `usb_binding`, `sg_binding`, `flash_bytes`,
`dumps`, `identical`, `command_completions`, `commands`, `flash_readback_only`,
`physical_recovery_verified`, `kernel_exclusivity`.
Schema is 1, kind `fm1-fixed-loader-backup`; each dump has only `file`, `bytes`,
`sha256`, `complete`. `dependency_sha256` maps `fm1_uboot_read.py` to its pin.
The SG binding records discovered paths and node/class/device/USB identity
triples. `commands` is 8757; `flash_bytes` is 1048576. `identical`,
`command_completions`, `flash_readback_only` are true; recovery/exclusivity are
false. Completion means accepted SG completions and the documented semantic
checks, not execution tracing of vendor internals or proof of absent device
side effects. Root's distinct `raw.profile_dump_fixed_loader` must preserve
the original-loader API and literal-pin candidate provenance, this adapter,
request inventory, entry hash and USB binding.

The authorized invocation, for the root bench owner after review, is:

```sh
python3 tools/fm1_fixed_loader_backup.py --campaign /PRIVATE/campaign.json
```

This note is not authorization to run that command. The lane did not run it.

## Checks, limits and next dependency

AST parsing and `git diff --check` passed on the frozen source. Mock tests cover
actual-shaped receipts, negative entry/status/echo/binding cases, single-use
envelopes, dual full reads, mismatched reads, storage faults and actual sysfs
discovery logic through a synthetic filesystem/character-node harness. The
root owns full-suite execution and independent source review. No local pytest
or live SG operation was used by this lane. The exact Hera focused results are
recorded below. Root reported acceptance of the frozen source/tests after
reading the complete adapter and reviewing the independent findings; root
requires checkpoint/push before the separate hardware campaign.

Rarefaction and Serena were checked; both selected the original checkout, not
this shared worktree. Parent prohibits changing another session's selection or
restarting servers. Worktree source inspection was the fallback; no semantic
worktree correctness claim is made.

The adapter leaves the loader active and cannot reset or restore. Root must
separately review the concrete reset/recovery transition; ROM upload cannot be
assumed available while this loader is active. USB_KEY remains physically
untried. Native candidate review verified the fixed selector and decode-call
changes, but external initializer `0x01e00428` and supplied operations remain
unverified; matching dumps do not close that question. Flash installation needs
fresh matching backups, concrete bounded write/readback/restore evidence and
retained SPL/OTA/cfg/partition safeguards. Display/boot acceptance remains a
separate physical goal.

Shared branch: `feature/2026-10-11@installable-firmware`; observed HEAD during
this handoff `54037db3fbe9c411b9cbf60dd75ee78d7586e979`. This lane made no commit
or push; root owns backup and integration. Next: finish root full-suite checks
and checkpoint/push, generate the fresh concrete campaign and separate raw profile,
then root alone decides/executes the reviewed read-only bench campaign.

## Exact Hera focused verification

At root's request, this lane verified the frozen snapshot on Hera
(`claude@192.168.1.48`) in 16 parallel isolated Docker chunks. All **80 tests
passed**, zero failures/errors/skips. Unique collected counts:
`tests/test_fixed_loader_backup.py` 53, `tests/test_loader_config_profile.py` 10,
`tests/test_ram_recovery_upload.py` 11, `tests/test_uboot_read.py` 6. The last is
the actual filename, rather than `test_fm1_uboot_read.py`. Each shard 00–15
collected, executed and passed exactly 5 nodes; aggregation asserts precise
JUnit node identity including parameter values, 80 unique nodes, no duplicate
assignment/execution and no missing nodes. The private original-loader test
ran and passed: the independently hashed actual d41d… fixture was mounted
read-only at `/private/original-loader.bin` with `FM1_LOADER_PRIVATE` set.

Minimal closed 11-file working-tree source archive SHA-256:
`345bd9ba554823e96b32fe07c0d44e3a92e757a2d46ad39e14cfa5a6079733cd`.
It includes exactly the four test modules, conftest and source dependencies,
including the frozen adapter/tests pinned above; no vendor binary enters the
archive. Observed HEAD `54037db3fbe9c411b9cbf60dd75ee78d7586e979` is explicitly
working-tree snapshot context, not a claim these changes were committed.
Full per-file source manifest SHA-256:
`e274e053d282d3de9054c50653fc45edc6ff6e1f24e654c95c42b6ea2585bbb6`.
Collection digest:
`736e537e31cb6f97e98401900cf45493a6e4510ab680aec08682f392c72a8718`.
Plan SHA-256:
`1ccf647f92dd07ca54c2ae4f663b903e9b52a0e6467c588dfec18663da138c4c`.

Verified image `lunar-recovery-pytest:20261011`, immutable Docker ID
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`;
all execution commands used the immutable ID after checking the tag. Python
3.11.2 verified. Containers used `docker-batch.slice`, 2 CPU/512 MiB limits and
equal memory/swap limit, network `none`, no device mounts, no privileged mode.
All 16 exits were zero, all OOMKilled flags false, and all 16 containers removed;
session-filtered final `docker ps -a` was empty. Collection/plan/aggregation and
version-check helper containers used `--rm`. No host infrastructure or other
session's container was changed.

Remote evidence: `/home/claude/mvave-fm1/fixed-reader-20261011`.
Local ignored mirror: `build/fixed-reader-hera`, including archive, source,
collection, plan, launch/finish scripts, per-shard log/XML/receipt, complete
container inspect/exit/removal receipts and aggregate. Aggregate SHA-256:
`91f87c78c30c83318ec5af7106f7bce6b55a3ab3a967332256bdeaeecb07d9f5`.
Container summary SHA-256:
`207aa60bd2afdbd8d1932f4573d86fe186d6df45e553fa4c17cf3403eba3e9b7`.
Execution-hash record SHA-256:
`f4d4fe0b6711de7f7d4b6c568eb838d3c25ded14e963710884bd7c970def5d69`.
These focused offline checks do not establish full-suite/CI, physical loader
startup, recovery, install, restore or display proof.

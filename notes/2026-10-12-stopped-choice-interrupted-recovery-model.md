# Stopped-choice interrupted NOR recovery model

Status: V4 isolated Hera model verification passed: 16 unique cases in 16
single-node chunks and one separate actual-file intent smoke. Independent final
review accepted this model scope. No hardware fault or frozen production source
change occurred.

Before this extension, the actual-file stopped-choice tests exercised complete
restore and a provenance change before the first mutation. The earlier generic
transaction tests exercised torn NOR operations, but did not combine them with
the actual one-use stopped-choice factory and its failed receipt.

The new `tests/test_stopped_choice_interrupted_recovery.py` uses the actual
physical RAM evidence and private SDK/stock files to construct the unchanged
backup c1b0 and restore 26f factories. Its SG ABI model injects interruption after
durable intent, partial erase, 13/127-byte page programming, acknowledgment loss,
and an acknowledged extra 1-to-0 bit change. It preserves the failed receipt and
consumed marker, and requires the old one-shot factory/worker and completed
helper to reject reuse. [verified: source and V4 isolated runtime]

The recovery half is deliberately an injected experiment: two fresh complete
1 MiB acquisitions must match, and all bytes outside the sealed writable ranges
must equal the baseline. A fresh generation of the persistent NOR model then
uses the already validated SDK transaction policy to reconstruct differing
sectors, with `0x4000` last, and verifies the full stock hash. It tests disagreement,
protected SPL/tail damage, modified plan/images, copied authority and foreign
binding. The injected recovery-session oracle supplies ROM/loader availability;
this is not a CPU, SPL or USB enumeration emulator. [verified: source and V4
isolated runtime]

The frozen physical restore remains fail closed after an interrupted attempt:
its initial full-target check cannot admit partially restored NOR, and its
one-use marker cannot be replayed. Tests and this procedure do not grant such
admission. [verified: 26f factory and f583 transport]

For an actual interruption: preserve campaign, wrapper/capture, failed command
log, consumed marker and incomplete durable journal; stop all vendor traffic.
Establish a separately reviewed ROM/loader route without booting a mixed app,
then acquire two fresh full dumps on a new bound session. Compare both complete
dumps and protected regions with the preserved stock baseline; disagreement or
protected-byte changes block mutation. A distinct partial-NOR recovery successor
must bind that acquisition, original immutable images/SDK evidence, failed intent
and receipt, current connection and fresh one-use marker. Rebuild whole differing
authorized sectors rather than treating an intent or torn page as a cursor;
commit the application directory last and require complete stock readback before
any separately reviewed reset. [inferred: proposed production procedure]

Outstanding physical premises include reliable mask-ROM entry after a partial
application/directory update and survival of the stock SPL/recovery route. The
NOR state machine cannot prove them. No automatic reset, stale receipt replay,
new production opener or hardware fault injection is provided here.

Owned paths: this note, the new test file, and ignored
`build/stopped-choice-interrupted-recovery/`. Parent owns review, commits and push.
Worktree branch `feature/2026-10-11@installable-firmware`; starting pushed SHA
`d4ddb022ec92e7ac0dd8ee2f596034239759b9c8`.

Semantic tools remain selected to a different/ambiguous shared checkout. Their
read-only status/config were inspected; no server was retargeted or restarted.
File inspection supplies this bounded Python analysis.

## Completed V4 gate and evidence

The takeover found V4 already complete on Hera and retrieved its existing
receipts without rerunning passing work. The frozen test source is
`0ed71e707828387e8e0acae7c36a581d4598f26fde113c14843b47dded1fe8b7`.
The exact archive contains 1,705 regular source files; archive SHA is
`87c6f52e0c6d0280cdbe04e27309a8d6296e1fa25337bb087ce137b56d92ad57`,
snapshot SHA is
`1774a944772e1e56b164a80f0cd7de836c9e8c680ead971de17dc183174ee3c8`.
The unchanged production factories remain backup
`c1b0f5539f2f47eb70300ba8ba19e35ec9e3b822dc00a792070cd34a31406798`
and restore
`26f9117c4e6ccd9b2ed765596db2c065abe00c6ef98b98e88b96f1353b7bfc4c`.
[verified: archive, current focused sources and retained receipts]

All 16 planned nodes appear exactly once in shard XML: 16 passed, zero failures,
errors or skips. The separate intent smoke also passed. The eight restore fault
cases are intent interruption, partial erase, erase acknowledgment loss, 13-byte
and 127-byte torn programming, program acknowledgment loss, acknowledged bit
corruption, and partial directory erase. Three acquisition cases reject dump
disagreement or protected SPL/tail damage; five policy cases reject changed
plan/target/baseline, copied authority or foreign binding. [verified: plan and XML]

All 18 containers (collection, smoke, 16 shards) used exact image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`,
4 CPU, 4 GiB memory and swap limits, `docker-batch.slice`, no network, devices,
extra capabilities or privileged mode, and read-only source/jobs/private fixture
mounts. Every process/container exited zero, none was OOM-killed, and each owned
container was removed successfully. Both the original cleanup receipt and a new
structured label lookup report zero remaining containers. The 16 concurrent
shards took 260.859 seconds after collection and smoke. [verified: inspections,
run receipts, named removal receipts and fresh lookup]

The retained eight fault cases plus smoke independently replay against their
private artifacts: all 4,096 initial target-page completion hashes match the
complete target; failed journals retain the restore intent and consumed marker;
failed immutable files match their recorded hashes; both fresh 1 MiB dumps match
the damaged NOR; protected bytes match the original target; final journals are
complete/restore with directory sector `0x4000` last and stock SHA
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Each fresh dual acquisition records 8,192 modeled reads. The model asserts full
stock bytes after reconstruction; no physical acquisition or CPU/SPL behavior is
claimed. [verified: retained artifact replay and exact test assertions]

Local private evidence is under `build/stopped-choice-interrupted-recovery/`:
`source-v4.tar.gz`, `snapshot-v4.json`, `plan-v4.json`, `aggregate-v4.json`,
`evidence-v4/`, `fresh-removal-v4.json`, and the read-only verifier
`verify-v4.py` with `verification-v4.json`. Remote evidence remains under
`/home/claude/mvave-fm1/stopped-choice-interrupted-recovery-20261012`.
Aggregate SHA is
`2c73079f85dcc9de2ff27145ec6f3b27b20ede5b9f81c914d9295e134a51a604`;
author verification SHA is
`bd558ae619428e325e478160843e6f7fba59b531ece9caa0ecffd6496877e833`;
fresh cleanup SHA is
`e41b88e7bf876a99d038127fedfeecf2d5b574c7c49cc6598522cfef553e3cd5`.
The retrieved private evidence archive SHA is
`ad9aeb7eab7ddd30072d1161582156309d2ce1a2691d2e71a2081211e6b08f93`.
V1 empty-mount, V2 incorrect `SGHeader.cmdp`, and V3 incorrect `Prepared.campaign`
failures remain preserved with their archives, XML/logs and removal receipts.
V4 uses actual `cmd` and `config`; these are test-owned repairs. [verified]

This is a historical source snapshot. At author replay, five current paths differ
through parent-owned work: `HANDOFF.md`, `firmware/recovery/request.c`,
`firmware/sdk-diagnostic/app_main.c`, the stock-reset packet note, and
`tools/jieli/build-sdk-diagnostic.py`. They are not covered by this gate. The
focused frozen test and production factories match their archived pins.
Takeover HEAD was `580b098efacf373a2fd1e5b383586dd557ae92ac`; parent owns the
new test/note checkpoint and its verified push. [verified: current source hashes]

Next production dependency: an independently reviewed distinct interrupted-NOR
acquisition/admission/restore successor, binding the failed command prefix and
journal, preserved immutable images, current loader lineage, two new full dumps
and protected-byte comparison. The existing 26f factory continues to reject
partial NOR. Reliable warm recovery after a corrupted app/directory remains a
separate physical premise. The model supplies loader entry and cannot close it.

Independent final V4 acceptance is retained in
`build/stopped-choice-interrupted-recovery/independent-review-v4.md`, SHA
`231ff38069c41ed4fc2a768633fc7663e33cfcc6032218ca4c0b498d98a73386`.
The reviewer separately verified 1,705 archive pins, 16 unique shard XML cases,
smoke, all isolation/cleanup receipts and nine retained fault-page cases.
There is no retained final full-NOR dump: complete stock bytes are asserted by
the executed exact model and recorded by its summary/final journal. This does
not upgrade modeled ROM/provenance to CPU/SPL or physical recovery and does not
authorize partial-NOR production admission. [verified: independent review]

At final handoff, local HEAD and the remote feature branch both matched
`ca55cde72b5aab0041f61d3f8ceb329cb8d1a1c1`; these new test/note paths still
await the parent's focused checkpoint and push. No commit was made by this lane.

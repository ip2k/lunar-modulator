# Verified installable diagnostic firmware goal

[reported: owner, 2026-10-11] Make the installable firmware milestone the active
goal and continue recovery and verification until a working image is verified.
The agreed first image is a diagnostic: it boots on the owner's FM-1, displays
the panel probe and retains recovery. Playable Lunar is a later milestone.

## Completion criteria

- A concrete reproducible native application, installable image and exact
  artifact hashes, with startup/link/package and protected-partition checks.
- A reviewed installation and restoration procedure, based on fresh matching
  complete backups and an exact device/port/image allowlist. Preserve the stock
  SPL, configuration, OTA and partition safeguards; no blanket erase or eFuse.
- Physical evidence that the installed diagnostic executes, produces the
  intended display and returns to usable recovery. A USB enumeration, host
  mock, NOR model, static audit or successful build alone does not establish
  these observations.
- Recovery software tested against interrupted/corrupted application writes,
  with durable journals, readback and documented limits. Physical broken-app
  recovery remains a separate gate from simulated recovery.
- Changes independently reviewed, appropriately tested, documented, committed
  and pushed with matching remote SHAs; integrate the completed stream through
  required review and CI gates. Checkpoints do not complete this goal.

## Owner constraints and current evidence

[reported: owner] Use Hera for heavy builds and tests while aeon is under
maintenance. Parallelizable tests run in sixteen isolated chunks. Continue
without Cynthion for now; its possible future USB disconnect role is recorded
in [the recovery runbook](../docs/17-recovery.md). The owner is away from the
desk and authorizes leaving the FM-1 in UBOOT or hung while useful independent
work continues.

[verified: goal-creation bench SSH/lsusb snapshot, 2026-10-11] The FM-1 was on
bench01 as `4c4a:c755`, bus 003 device 022. The earlier single reviewed RAM
core-reset experiment restored normal USB and a fresh `FM-1_092` identity
without an owner power cycle; see [the receipt](2026-10-11-fm1-core-reset-bench.md).
That consumed adapter is not reusable and the experiment did not restore a
corrupted application.

[verified: saved software receipts] Source `38a7d53c` passes the full sixteen
Hera shards and all thirteen required CI jobs; see [the entry and bring-up
receipt](2026-10-11-offline-entry-and-bringup.md). Documentation head at goal
creation was `fc8e3414bef97041611bbf7463f0b277d4141185`, verified on origin.
No diagnostic package or physical Lunar application acceptance existed at goal
creation. Later evidence below supersedes this historical device snapshot.

## Current verification boundary

[verified: independent physical receipt review] The private C-only SDK
diagnostic app `991b569d…`, ELF `8832aa46…`, and reproducible raw NOR target
`df6c963e…` exist. A complete install/readback/stock-restore/readback rehearsal
passed; a separate reset returned restored stock operation and the exact
`FM-1_092` identity without a physical power cycle. Fresh matching stock backups
then preceded a separate diagnostic install, whose full 1 MiB readback matches
the target. Protected bytes and directory-last sector order passed independent
replay. One subsequent target reset was transmitted on the device-25 loader
connection and lost its reply on detach. About 22 seconds later, the same port
enumerated as device 26 in ROM. The original reset capture contains no later
vendor command. The immediate stage chooser stopped before launching its
probe, because its historical capture guard rejected one ordinary SCSI
media-lock command. This is a boot attempt, not accepted diagnostic execution,
visible display or post-boot recovery evidence. The retained diagnostic RAM
record was subsequently retrieved by a distinct reviewed successor: exactly two
native successful reads, coherent stage6/result0/elapsed20000/heartbeat1976 and
the native pointer. This supports diagnostic execution conditionally; visible
pixels, retention and recovery cause remain unproved. See
[the actual RAM read](2026-10-11-diagnostic-first-ram-read.md). A distinct recovery
admission for that terminal capture is required before loader upload or NOR
mutation. Do not replay the consumed reset, chooser or RAM read, or refresh
the original ROM snapshot.

[verified: independently accepted software receipts] The final shared
successful/detached stage probe passed 101 unique cases in sixteen Hera chunks
plus one strict actual-private modeled smoke. The returned-ROM backup/restore
gate passed 182 unique cases with three genuine private-factory models; its
bound stock-reset gate passed 58 cases plus the genuine composed smoke. The
closed stock-reset bench template passed 60 unique cases, including one
genuine composed preparer/wrapper model. These are source/private-input and
modeled transport checks, not additional physical operations. The old returned
backup route inherits the historical guard that rejected the actual media lock;
its accepted software receipts do not authorize bypassing that stop. A distinct
returned-proof successor is needed after the retained RAM read.

The closed interrupted-restore replay kernel separately passed 55 cases in
sixteen Hera chunks. It tracks the union of attempted-write uncertainty until
matching readback resolves it; erase/program syscall return alone is not flash
success. It has no hardware opener, and its campaign factory always refuses
execution. Its separate original-lineage evidence helper passed 33 unique cases
in sixteen Hera chunks, including one genuine private-input interrupted program
model; final independent review accepted only its closed evidence scope. Owned
terminal capture, live partial-flash acquisition and executable recovery remain
separate work. The original 6,389-case complete Python snapshot finished all
16 chunks: 6,352 passed, 35 skipped and two expected failures, zero failures or
errors. It does not include the newer probe or returned-ROM sources.

Current remote-SHA-verified checkpoint:
`c29726c4d39a07df6b262b51845788fad5ebe8ea` on the feature branch below.
The source-only stock-return template is staged with its execution policy still
closed. Its future concrete binding must follow actual fresh backup and
completed restore evidence. See [the boot trial](2026-10-11-diagnostic-boot-trial.md),
[stage probe](2026-10-11-diagnostic-stage-probe.md), and
[returned-ROM design](2026-10-11-returned-rom-recovery-design.md) for exact pins,
limits and next dependencies. This remains an active unfinished goal.

[verified: current GitHub query] All thirteen jobs passed in run 38199299324
at exact checkpoint `20284ce7ed0543038c5861e935f345e7b4257a2c`.
All thirteen jobs also passed at exact a6bce57a in run38201658769.
Run38202646517 at aca0e686 has ten successful jobs and three running;
run38203747490 at c29726c4 is pending. New successor sources are outside
those CI snapshots. No CI or model result
upgrades the physical boot, display or interrupted-write acceptance gates.

## Active dependency plan

1. Preserve the completed private C-only diagnostic build, its pinned V1.2.13
   libraries, Apache boot-info bridge, single-core configuration and GPL-off
   profile. The raw target and exact protected geometry are verified; the
   independently permissive runtime remains a later path.
2. Completed: the distinct read-only stopped-chooser successor passed source,
   sixteen-chunk Hera and concrete-packet review, then exactly two physical
   reads. Its actual receipt/capture and bounded native interpretation were
   independently accepted. The post-read admission passed95 unique cases
   in16 Hera chunks plus genuine actual-file smoke; visible pixels, retention
   and reset cause remain separate observations.
3. Bind a distinct returned-ROM backup/restore route to that accepted actual
   proof and the current connection. Take fresh matching complete dumps, restore
   exact stock, verify all flash, and verify responsive stock operation through
   a separately bound reset and identity query.
4. Complete original-lineage interrupted-write evidence, fresh partial-flash
   acquisition and recovery verification. Record diagnostic execution, visible
   panel and recovery evidence; finish integration only after required physical
   acceptance, independent review and exact-head CI.

Worktree: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`. Main-thread ownership covers
hardware traffic, concrete manifests and integration. Independent investigations
save their reports in ignored `build/`; important conclusions and artifact pins
are promoted to tracked notes at each coherent checkpoint.

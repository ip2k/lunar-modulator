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

[verified: live read-only bench SSH/lsusb, 2026-10-11] The FM-1 remains on
bench01 as `4c4a:c755`, bus 003 device 022. The earlier single reviewed RAM
core-reset experiment restored normal USB and a fresh `FM-1_092` identity
without an owner power cycle; see [the receipt](2026-10-11-fm1-core-reset-bench.md).
That consumed adapter is not reusable and the experiment did not restore a
corrupted application.

[verified: saved software receipts] Source `38a7d53c` passes the full sixteen
Hera shards and all thirteen required CI jobs; see [the entry and bring-up
receipt](2026-10-11-offline-entry-and-bringup.md). Documentation head at goal
creation was `fc8e3414bef97041611bbf7463f0b277d4141185`, verified on origin.
No diagnostic package or physical Lunar application acceptance exists yet.

## Active dependency plan

1. Build a private, C-only diagnostic with the pinned V1.2.13 SDK's matching
   dual-core runtime and the Apache boot-info bridge, with GPL engines off.
   [inferred: source reviews] This closes more startup dependencies than a new
   custom entry contract; native startup/exception and P33 recovery audits
   remain required. The independently permissive runtime remains a later path.
2. Close the RAM loader's retained-configuration/NOR-status initialization
   boundary before fresh physical backups. Keep the historical scratch-sector
   writer allowlist intact; wider writes require a separate exact manifest.
3. Build the concrete diagnostic on Hera, construct and independently validate
   an offline raw target against the actual FM-1_092 geometry, and review the
   bounded installation/restoration campaign before device mutation.
4. Run the hardware campaign and record execution, panel and recovery evidence;
   continue fault verification and finish integration only after acceptance.

Worktree: `/Users/likwid/.codex/worktrees/installable-firmware/mvave-fm1-firmware`.
Branch: `feature/2026-10-11@installable-firmware`. Main-thread ownership covers
hardware traffic, concrete manifests and integration. Independent investigations
save their reports in ignored `build/`; important conclusions and artifact pins
are promoted to tracked notes at each coherent checkpoint.

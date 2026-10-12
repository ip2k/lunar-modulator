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
replay. The current installed target remains on the original device-25 recovery
loader connection; target reboot, diagnostic execution, visible display and
post-boot recovery are still pending.

[verified: software gates] Exact injected ROM stage probe passed 126 tests in
16 Hera chunks plus an actual-private modeled smoke and independent review.
Its separate native SG transport passed 79 tests and its actual-private modeled
smoke; independent retained-evidence review accepted both. The static successful-only probe
packet is staged without execution. A separately reviewed transmitted-but-
detached reset policy, fresh binding and returned-ROM stock-restoration adapter
are being developed; old guards and consumed markers remain intact.
GitHub CI passed all thirteen jobs at selector checkpoint `22cae292…`.
The strict-private selector gate passed 287 tests in 16 Hera chunks, with no
skips; public CI behavior passed 244 with 43 explicit private-fixture skips.
Later source checkpoints require fresh CI. The original 6,389-case complete
Python snapshot finished all 16 chunks: 6,352 passed, 35 skipped and two expected
failures, zero failures/errors. It does not include the newer probe or returned-ROM
sources. The new stock-reset scaffold separately passed 56 injected cases plus
one smoke. The composed fixture then exposed a mismatch with the actual SG
identity schema; the source correction and expanded 58-case gate are pending
composed runtime acceptance. Its production factory remains closed pending a
genuine reviewed completed-restore helper. The final shared successful/detached
probe gate passed 101 unique cases in sixteen Hera chunks plus one strict
actual-private modeled smoke; independent review accepted report `cd990cc8…`.

Current remote-SHA-verified checkpoint:
`f45a2b016d5629fc76dbb85b5a4bcfba7145c023` on the feature branch below.
The returned-ROM backup/restore/reset checkpoints remain unaccepted WIP;
their complete shared provenance and genuine private-factory gates are pending.
Do not activate them. See [the boot trial](2026-10-11-diagnostic-boot-trial.md),
[stage probe](2026-10-11-diagnostic-stage-probe.md), and
[returned-ROM design](2026-10-11-returned-rom-recovery-design.md) for exact pins,
limits and next dependencies. This remains an active unfinished goal.

[verified: latest CI] Run 38192936943 at `6b8ed4b2…` finished with twelve jobs
passing and macOS Python failing in sixty Linux SG syscall mocks that retained
Darwin's platform. Production transport correctly rejected them. The test-only
mock-platform repair passed its focused 79-case Hera gate plus actual-private
modeled smoke; independent final evidence review accepted `0fb814d9…`.
Fresh CI is pending. No production
guard is weakened or hardware gate upgraded by that repair.

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

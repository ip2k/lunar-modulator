# Workbench reuse pilot — active implementation

Personal Lunar Modulator work, authorized by the owner on 2026-10-17.

## Endpoint

Complete the offline selective-reuse milestone from the workbench plan: pinned
source/licence and recovery-asset inventory, native seam and board comparison,
one useful source-only format adapter with explicit losses and independent
synthetic tests, attribution, review and CI integration. Select later UI/board
changes from evidence; do not fabricate a native fix to fill a work package.
Hardware acceptance remains a separate owner/coordinator gate. No device
traffic or upstream contact belongs to this task.

## Bases and ownership

Implementation branch: `feature/2026-10-17@workbench-reuse-pilot`, based on
reviewed documentation head `0b3f377c1175df729591c221fa39de435ff5a8ce` (PR #150).
This adds host tooling to published main; the native reference remains
`1f12ad5b8d6a865268af94179a3442183a680602`. The native stream is not merged as a
side effect. The coordinator will review adapter compatibility with both state
contracts before integration.

Workers own isolated Aeon worktrees and atomic claims:

- Luna `workbench-inventory`: inventory, provenance and offline verifier.
- Sol `workbench-native`: native seam/board evidence; propose any justified fix.
- Sol `workbench-formats`: format matrix, adapter and synthetic fixture generator.
- Independent tests/review follow the agreed adapter interface.

Aeon received exact base/reference refs through Git and the public kit ZIP
through SCP. No active checkout or credentials were copied. Light source
inspection/stdlib tests need no heavy containers; any heavy tests use the LAN
batch slice and explicit resource limits. Hera remains unused under the native
project's exclusion even though newer infrastructure notes report maintenance
complete. Worker commits are pushed to the Aeon exchange repository, then
backed up by the Mac coordinator to GitHub with exact SHA verification.

## Navigation limits

Rarefaction and Serena currently select the original absolute checkout,
`/Users/likwid/Developer/mvave-fm1-firmware`, not these new worktrees.
Rarefaction's bounded `check_package` query matched source and its caller;
Serena resolved `engines/seq/seq_engine.c:87` after correcting the file path.
Known callers exist in the host tool and simulator. Shared servers were not
retargeted over other sessions. Branch/worker claims use exact Git objects and
direct source checks; no native ABI or complete cross-language index is claimed.

## Current status

Workers active; no implementation or hardware acceptance claimed yet. PR #150
has a separate live integration worker. Next: review W1–W4 evidence, select the
format slice, add independent tests, and integrate only reviewed passing work.

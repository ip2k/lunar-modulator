# Two-stage Cynthion recovery-key profile (offline)

[verified: source and Amaranth simulation] Added explicit `staged-operation`:
physical USER preflights disconnected K/J/SE0/SE1, then state 9 READY is high-Z.
Only a fresh steady release after READY and second press starts the unchanged
bounded KEY/WAIT_DP/SOF path. A held button cannot advance. All four self-test
bits and no failure are required. Interlock loss, including explicit PHY fault,
latches FAULT; restoring gates cannot rearm. Reset clears readiness and mask.
Existing state IDs 0–8 and original modes' protocol paths are preserved.

Layout 7 appends staged-profile bit 15 to status register 3, so SAFE/READY and
terminal profiles are distinguishable. READY does not freeze terminal receipts
or event history. CONTROL power remains explicit; staged recovery recipe selects
CONTROL-to-TARGET-A only, TARGET-C/AUX/discharge off. See scoped README staging.

[verified] Focused suites: 28 passed using existing test interpreter and Cynthion
site-packages; covers original modes, staged successful two presses, held first
press, high-Z READY, each gate loss/no rearm, reset, mismatch/no KEY and invalid
automatic staged configuration. Only dependency deprecation/unused-elaboratable
warnings. Final source guard strengthening rerun recorded in handoff below.

Semantic startup: Rarefaction and Serena both reported the original absolute
checkout, not this isolated worktree. Did not retarget global shared servers
while other sessions work. Source inspection used instead; no semantic practical
evaluation claimed for this worktree. Main repo .venv lacks Amaranth; initial
throwaway /tmp/lunar-staged-key-venv ran 26 passing checks before the coordinator
provided the established interpreter, then established interpreter ran 28.
No global dependencies changed.

No SSH, FPGA build/load, device traffic, FM-1 writes or hardware acceptance.
Connected/unpowered-target failure cause remains unproven. This source preparation
does not relax dump-and-byte-identical-restore gate or authorize an attempt.

Handoff: branch `fix/2026-10-18@cynthion-staged-key-preflight`, isolated checkout
`/Users/likwid/.codex/worktrees/cynthion-staged-key/mvave-fm1-firmware`, exact base
`01f7df96`. Coordinator must review/integrate, teach its read-only reader explicit
layout7/bit15/state9 identity, and separately authorize/build/load the exact image.

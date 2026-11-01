# MATRIX destination stack reduction

Assigned baseline b831724fcf413720aaa036dac742a382cdfaa93c. Personal offline work;
no device operations. Branch `fix/2026-11-01@matrix-ui-stack` in
`/Users/likwid/.codex/worktrees/lunar-matrix-stack-20261101`.

WIP: replace the three 774-entry destination arrays with an immutable metadata
snapshot of at most 23 groups. Keep public enumeration order/capped count,
pre-commit snapshot semantics, popup names/tags and slot mutation semantics.
No mutable shared scratch or arena. Validation pending: baseline differential,
existing MATRIX tests, ASan/UBSan, and measured per-function stack frames.
This change does not establish whole-target-stack acceptance.

Rarefaction status/orient/scope and Serena current config/find_symbol checked
against main source: both select the main checkout; no global root change.
External worktree lookup is unsupported; exact owned source was read directly.
C index lacks a compilation database, so source and compiler checks remain needed.

Scratch: own `scratch/matrix-stack-20261101`, remote
`/home/likwid/datasets/lunar/matrix-stack-20261101`; reproducible binaries/staging
will be removed after results are recorded. Small logs retained. Mac free space
1119 GiB at start.

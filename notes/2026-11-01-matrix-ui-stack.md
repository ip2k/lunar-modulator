# MATRIX destination stack reduction

Assigned baseline b831724fcf413720aaa036dac742a382cdfaa93c. Personal offline work;
no device operations. Branch `fix/2026-11-01@matrix-ui-stack` in
`/Users/likwid/.codex/worktrees/lunar-matrix-stack-20261101`.

Implemented: replace the three 774-entry destination arrays with an immutable metadata
snapshot of at most 23 groups. Keep public enumeration order/capped count,
pre-commit snapshot semantics, popup names/tags and slot mutation semantics.
No mutable shared scratch or arena. Validation passed: baseline differential, existing MATRIX tests and ASan/UBSan.
Host and pinned pi32 compiler frame evidence is recorded below.
This change does not establish whole-target-stack acceptance.

Rarefaction status/orient/scope and Serena current config/find_symbol checked
against main source: both select the main checkout; no global root change.
External worktree lookup is unsupported; exact owned source was read directly.
C index lacks a compilation database, so source and compiler checks remain needed.

Scratch: own `scratch/matrix-stack-20261101`, remote
`/home/likwid/datasets/lunar/matrix-stack-20261101`; reproducible binaries/staging
will be removed after results are recorded. Small logs retained. Mac free space
1119 GiB at start.

## Evidence [verified]

- `sim/web/test/fm1_mod_ui_diff.c` + `mod-ui-differential.py`: link a
  function-renamed baseline from `git show b831724f:sim/web/src/fm1_mod_ui.c`
  alongside the current object. 986 layouts, 492,640 events pass at -O2
  (0.894 CPU seconds) and -O1 ASan+UBSan (5.478 CPU seconds). Compare every
  output byte including unused popup bytes, emitted script lines, entire UI
  and runtime memory, all slots, kinds and parameters after every event.
- Layout coverage: every registered engine descriptor in every sink; every
  registered module kind in every rack position; every destination output cap
  from -1 through total+1; every kind-only destination index and signed jump
  boundary; dense mixed list every index including -1/total, every current
  sound/fallback and deltas -24..24; 256 deterministic mixed layouts with
  1024 random events each, including KIND-to-DEST transitions. This is not
  exhaustive over the enormous Cartesian product of all engine/kind choices.
- Existing `tests/test_sim_mod.py`: all 49 tests pass.
- Clang -O2 x86_64 `-fstack-usage` frame bytes before → after: knob
  6296 → 664, algorithm 6248 → 600, commit 6248 → 616. Helper dest_list
  56 and say_dest 56; these are separate local frames, not total call depth.
- Pinned actual pi32v2 compiler (toolchain/current mounted read-only) compiled
  both sources with `-target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding
  -fno-builtin -ffunction-sections -fdata-sections -std=c99
  -isystem /opt/jieli/pi32v2/include`. Assembly prologue local allocations
  before → after: knob 6472 → 652 bytes; algorithm 6204 → 376; commit
  6212 → 404. Register-save pushes are additional: before knob/commit
  `{rets,r11-r4}`, algorithm `{rets,r12-r4}`; after knob/commit
  `{rets,r15-r4}`, algorithm `{rets,r9-r4}`. This is actual target code
  generation evidence for these local frames, not an executed whole-stack
  high-water measurement. App precommits most picker transitions, so nested
  knob→commit arrays represented API call-frame potential, not an observed
  ordinary panel overflow.

Enumeration is linear in metadata size. The public bulk API performs two
linear passes; internal lookups scan up to 23 groups and one group's bounded
parameter list. Popup rendering repeats lookup only for the fixed visible row
count. Group navigation scans at most 23 groups and handles delta in constant
time thereafter. No quadratic traversal over the full destination list, no heap,
no mutable static scratch. The metadata snapshot is 376 bytes on pi32v2.

Reproduction: build the native harness with sim.mk; then
`CC=clang CXX=clang++ FLAGS='-O2 -fstack-usage' python3
sim/web/test/mod-ui-differential.py <native-build> <baseline-source>`.
Sanitizer build uses OPT=-O1 and
`EXTRA='-g -fsanitize=address,undefined -fno-omit-frame-pointer -fstack-usage'`;
use those same flags in FLAGS for the differential runner.

All heavy checks ran on Aeon CPU8-11, max4CPU/6GiB, docker-batch.slice,
project/session labels, --rm containers. No full WASM build: fm1_mod_ui.c
source hash changes require the coordinator's next integration rebuild.
FM6 descriptor identity is an additional authorized follow-up, not included
in this stack behavior comparison.

## Incremental FM6 identity regression [verified]

The app uses an app-owned copy of the `dx7` descriptor to supply live bank
names. Registry pointer comparison failed for it. Switching from FM6
Brightness (UID2) to Macro left that ON cable active at Macro's unrelated
Harmonics UID2. `registry_index` now recognizes stable engine IDs as well as
registry pointers; name matching still reads the live descriptor passed in.

The focused harness uses actual `fm1_app_init`/`fm1_app_select`, asserts FM6's
app-owned descriptor differs from its registry pointer, and proves:

- ON Brightness switches OFF and remembers FM6 identity on Macro selection;
- originally OFF Brightness remains OFF across Macro and the return to FM6;
- shared Volume maps FM6 UID5 → Macro UID7 → FM6 UID5;
- returning to FM6 clears remembered identity and restores the original ON
  state and destination UID, preserving amount.

Red check before the fix failed at the required OFF-state assertion. Green
checks: normal differential (986 layouts / 492,640 events, 1.297 CPU seconds),
ASan+UBSan differential (same events, 3.366 CPU seconds), live FM6 app
regression, and all 49 existing modulation tests. No hardware or audio output.
Rarefaction orient/scope and Serena find_symbol confirmed the pointer-only
helper before editing; Rarefaction fallback C type/caller indexing was incomplete
and slow (65/106 seconds), so exact source/runtime tests supplied the evidence.

This incremental fix also changes fm1_mod_ui.c and requires the coordinator's
next complete WASM source-hash rebuild. No generated hashes were edited.

## Handoff and lifecycle

Implementation/test head `2aa61d98335475c9285f5ab20624296b693ae994` pushed
and verified on origin `fix/2026-11-01@matrix-ui-stack`; preceding coherent
commits are `c3f05e1b` and `3f5c10f3`. Final fixture recompilation/rerun and
actual pi32 compilation pass after the identity fix; the three pi32 local
allocations remain 652/376/404 bytes.

Remote task stage was deleted after checking no task-labelled container was
running. No container/build output remains there. Owned local scratch retains
28 KiB of logs and the target compilation command only, under
`scratch/matrix-stack-20261101`; baseline source/assembly intermediates were
removed. Worktree stays registered for coordinator integration and must be
removed after merge. Mac free space: 1121 GiB at handoff.

Next: coordinator reviews/cherry-picks this branch, performs the required full
WASM build/parity/hash generation on the integrated source, and runs project
review/CI gates. There is no whole-target-stack execution or device acceptance
claim, and no remaining owner decision for these fixes.

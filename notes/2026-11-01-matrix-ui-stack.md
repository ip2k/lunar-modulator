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

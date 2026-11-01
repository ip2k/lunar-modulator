# Refuse after pipeline clock-hook poison — 2026-11-01

[verified] Independent review of offline CPU1 source c9ddf99e767aa9e6593d528814b326dc48c6007b
found a synchronous hook-order defect: the candidate millisecond hook observes
backend failure/raw fault and poisons the common core, but worker still admitted a
SEALED job's consume callback. wait_check also returned success after that hook.
A raw clock could likewise poison before consume, work publication, or output
publication. This is a source ordering guarantee, not an atomic silicon grant.

The focused common-core correction rechecks permanent poison after clock hooks,
at worker_step entry and immediately before consume. Startup stops after a failed
initial millisecond sample. Refusal keeps the first error and permanently retains
producer/consumer/output slots and context; no retry, replay, free, READY/DONE
publication, or hardware-path admission is added.

Nine directed actual-candidate fixture modes exercise backend.failed and both raw
fault-claimed words' target native_ms condition, raw-clock poison before/after
consume, wait ticket preservation, no work publication, and direct poisoned step.
The host hook mirrors the target's two poison conditions; it does not execute the
target MMIO, fault assembly or target volatile-word memory model. Actual candidate
C, actual native adapter and actual common worker execute; static SEALED setup
makes the fault ordering deterministic rather than racing injection with a thread.

[verified] All nine modes failed against exact c9dd parent core substituted in an
owned temporary source tree, both normal and ASan/UBSan (18 causal failures).
The corrected three focused suites passed 27 tests in 33.10 s: 542 candidate modes
x2, 24 common protocol modes x4, and 21 lifecycle modes x2 = 1,222 executions,
plus compile/default/negative-selection tests. Apple ASan has no LeakSanitizer;
these fixtures own no heap. Logs: scratch/cpu1-candidate-20261101/logs/
clock-poison-{red,red-modes,green,final}.log. Temporary products are owned by that
scratch lane and will be removed after the source-bound evidence is recorded.

Rarefaction orient/scope rejected this absolute external worktree outside its
fixed root; direct exact source was used. Shared Serena selection belongs to the
WASM lane and was not changed. Neither provides actual pi32 ABI/device proof.
Independent review and refreshed source-bound target compile/listings remain
required. No target/device execution occurred; hardware_admitted stays zero.

# Pipeline clock-hook poison correction — 2026-11-01

[verified] Common-core-only integration from coordinator base
9537ae55: identical production core bytes to offline candidate correction
1c5a1f41f99f301797ea42775546df4b67f292e0. No candidate source, headers, tests,
native adapter changes, target build, SDK changes, or device execution imported.

Clock hooks can synchronously latch permanent poison. Recheck after initial
startup ms, wait ms/raw clocks, producer publication clock, worker ms and entry,
consume-start clock immediately before callback, and consume-end clock before
READY/DONE. Existing first error wins, slots/context stay permanently retained;
no retry/replay/free, callback or output acceptance after observed poison. These
are synchronous hook-order guards, not atomic admission against concurrent
physical corruption or target memory-model proof.

Directed existing actual protocol fixture tests run raw-clock cases through both
SDK wrapper and atomic host adapter, plus failing-ms/startup tests through actual
host_core. Five shared modes and three host-only modes assert no callback after
poison, no work/output publication, retained exact states/context/counts, no wait
ticket mutation, first-error preservation, and no startup wake/launch after a
failed initial sample. Static SEALED setup controls scheduling while invoking the
real worker; there is no duplicate worker implementation. Supplemental real
candidate failed/raw-fault-condition evidence remains on its separate branch.

[verified] All 26 new directed executions fail against the exact 9537 parent
core, normal and ASan/UBSan. After the correction, the focused protocol suite
passes 12 pytest cases: 122 normal/sanitized SDK/host protocol executions plus
header/default/build inventory checks. Evidence is lane-owned
scratch/pipeline-clock-poison-20261101/logs/{red,red-modes,green}.log; test products
are removed after logs are recorded. No native_lifecycle/sdk_shim files changed.

Rarefaction cannot select the absolute external worktree outside its fixed root;
shared Serena is owned by the concurrent WASM lane and was not re-rooted. Direct
exact Git source inspection is the fallback; no target ABI claim follows.
Independent exact-pin review and coordinator CI remain integration gates.

# First-format analysis for reserved-tail project slots — 2026-10-14

## Result

[verified: retained SPL analysis] The proposed storage48 scatter map covers 24
4 KiB sectors, each with an 80-byte stock SPL trailer candidate at sector
offset +0xF00. The same 80-byte location is inspected by the retained Felucca
cleanup loop. The byte-verified SPL/cleanup predicates and exact map intersection
are documented in notes/2026-10-14-spl-record-scan-proof.md and
notes/2026-10-14-spl-record-window-mapper.md. The underlying SPL listing was
rechecked against the pinned binary by the earlier worker; this task did not
rerun the vendor disassembler.

[verified: offline implementation and tests] Added
tools/native/tail_migration_plan.py and tests/test_native_tail_migration_plan.py.
Given two complete identical 1 MiB snapshots, a matching explicit SHA-256 pin,
and a matching target-identity assertion, the helper enumerates every candidate
and evaluates the retained outer SPL and cleanup predicates. It does not read
devices, create evidence receipts, or authorize writes.

The conservative pre-format rule is exact: **every mapped sector's entire
final 256-byte page must already be 0xFF in the identical pinned input snapshot**.
If even one byte differs, the helper reports that sector and returns no erase
sequence, even when the current 80-byte contents fail both record predicates.
Under a monotonic NOR erase model, an already-erased page cannot transiently
become a record as the containing sector is erased. The model is an explicit
assumption, not a measurement of interrupted physical erase behavior. For an
all-erased input fixture, the helper marks this record-page precondition as
satisfied under the model. It still emits no erase sequence because this
analyzer does not validate the separate migration, rollback, or recovery gates.

## Admission and migration limits

[verified: current repository receipts and code] A matching pair and digest
prove only equality and byte identity within this function's inputs. The
identity string is caller-supplied; this analyzer does not authenticate the
device observation or the acquisition log. It does not validate that the pair
is fresh/current, prove storage ownership, decode opaque stock VM/USR data,
verify semantic migration, or prove a stock restore or independent recovery
route.

[verified: source review] Formatting either slot erases sectors containing
opaque stock VM/USR state. A raw archive preserves bytes but does not itself
establish a tested rollback route or semantic migration. The storage48 plan's
existing migration, restore and recovery prerequisites remain necessary. Even when the trailer pages are all erased and the record-page condition
is satisfied, application behavior after partial loss of VM/USR, physical erase
interruption, and target-specific recovery remain unresolved.

The generated result hard-codes
semantic_migration_verified=false, physical_rollback_verified=false,
hardware_admitted=false, physical_writer_ready=false, and hardware_operations=0.
It is an offline hazard analysis, not first-format admission, a device-write
plan, SAVE binding, or installability evidence. No hardware or device operation
was performed.

## Validation

[verified] In the pinned Hera container lunar-preload-tests:20261014
(image SHA-256
1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313),
with network disabled, docker-batch.slice, 2 CPUs, 3 GiB memory/swap, and
256 pids, the focused planner tests pass: 10 passed. Cases cover the full
24-sector map, precondition result for all-erased pages, refusal for a
non-erased page even when invalid as a record, both distinct SPL/cleanup
predicate outcomes, and missing/mismatched snapshots, digest and identity.

[reported: semantic tooling] Rarefaction/Serena remained selected for the Mac
checkout and were not retargeted to this isolated Hera worktree. The small
Python helper was navigated and checked directly against the cited source and
test contracts.

# Reserved SPL trailer windows in the storage48 scatter map

2026-10-14. Offline design analysis only. No production code, device state, or admission flags changed.

## Result

[verified] The 12 sectors in each proposed slot contain one conditional stock SPL trailer candidate at physical sector offset +0xF00. On the documented 1 MiB profile these addresses are also inside the retained cleanup loop's candidate interval. All 24 candidates intersect both scans.

[inferred] The simplest persistent-state invariant is to keep the full 80-byte candidate window erased (0xFF) in every journal sector. Then no serialized journal bytes can form either the SPL signature/CRC predicate or the broader loader-cleanup predicate. Preserving only signature bytes +6..+7 blocks both predicates, but the full window is easier to audit and leaves no dependence on how the other fields evolve.

[verified: arithmetic] Each 4 KiB sector would expose 4,016 packed data bytes if the 80-byte window is reserved. Twelve sectors yield 48,192 packed bytes; after the existing 32-byte journal header the payload ceiling is 48,160 bytes. This exceeds the conservative 43,130-byte collector bound by 5,030 bytes. This is capacity arithmetic, not allocator ownership or flash acceptance.

## Why the current adapter does not implement this safely

[verified] `project_store.h` models a slot as a contiguous byte range whose size is a multiple of 4096. It erases at logical offsets 0, 4096, 8192, and so on. Its serialized/hash stream is contiguous. `extent_io.h` maps sector-aligned extents and requires erase requests to identify one aligned 4096-byte sector; reads/programs translate linearly across those extents.

[inferred] A mapper that simply rejects accesses into each physical +0xF00..+0xF4F window cannot satisfy the current store contract: the store serializes and hashes contiguous bytes that can span those locations. Returning synthetic 0xFF bytes would also make readback hashes differ unless a separate framing layer strips the reservation consistently.

[verified: arithmetic and interface analysis] A 48,192-byte packed capacity is not itself a valid logical slot size because it is not a multiple of project_store's 4096-byte erase unit. However, this does not require a new journal format: exposing eleven logical sectors gives 45,056 logical bytes (45,024 payload after the header), while a specialized adapter maps each logical range across 4,016-byte physical fragments and erases every overlapped physical sector. That mapping has less convenient alignment and more overlap cases than the 3,840-byte-fragment option, but the adapter can preserve the journal's contiguous read/hash stream. Per-sector framing would be another design and would change serialized/hash semantics; it is not required by the current interface.

## Recommended design boundary

[inferred] Evaluate the full-256-byte-page reservation first. Use a dedicated packed-slot adapter over twelve physical sectors with eleven logical 4 KiB units. Its erase callback must erase every physical sector overlapping the logical 4 KiB range, with the invariant that begin() completes every inactive-slot erase before any program. Its read/program callbacks pack 3,840-byte fragments and skip the 256-byte tail page. This preserves the existing journal stream/hash semantics and fits the conservative payload bound. Lock callback ordering and active-slot exclusion with tests.

[verified: interface boundary] extent_io alone is linear and sector-aligned, so it cannot skip tail pages. The adapter must also prevent page-sized programs from overlapping any reserved tail and reject invalid geometry before I/O. The 80-byte candidate-window design remains a higher-capacity alternative. It can preserve the existing journal format with the same 45,056-byte logical slot and a specialized 4,016-byte-fragment mapper, but has tighter/more complex erase-overlap mapping than the full-page reservation.

## Initialization and interrupted-operation invariant

[inferred] “Window remains FF” is a post-initialization invariant, not automatically true while importing arbitrary preexisting flash. A sector erase changes bits from 0 to 1 and may transiently create the exact signature pattern from unknown old bytes. Therefore a safe initialization argument needs both (a) a known and externally retained prior state, and (b) no stock SPL/cleanup path being invoked during the destructive transition. This repository analysis does not establish that transition as physically safe or authorized for a particular device.

[verified: current host model only] The existing fake-NOR journal tests inject prefix erase/program failures and complete-operation-then-error cases. Those are useful software fault models, not characterized flash-chip power-cut behavior. A test-only container prototype now asserts the reserved full 256-byte page stays all-FF across every modeled failure and checks the signature gate used by each stock-record predicate at all 24 physical candidates.

The prototype uses the explicit 24-sector candidate map from the migration plan: Slot A [0xD9000,0xE0000), [0xE5000,0xE9000), [0xEA000,0xEB000); Slot B [0xEB000,0xF7000). It places a deterministic sentinel over the 1 MiB modeled flash outside these ranges and verifies those bytes remain unchanged. Both distinct replacement generations carry a full 43,130-byte payload. The sweep faults every translated physical erase/program mutation in both 0-to-1 and 1-to-2 replacement, with partial-operation and complete-operation-then-error modes. It checks byte-for-byte preservation of the active physical slot, exact journal recovery of the prior or committed body, all 24 reserved 256-byte pages and each slot's unused 1,024-byte packed suffix remaining 0xFF, and malformed ranges rejected before mutation. The SPL and cleanup checks are only their common +6 signature gate; they do not evaluate outer CRC, SPL's nonzero field, or downstream checks. This does not model physical flash timing or power loss.

## Scope and acceptance limits

[verified] The address-set arithmetic and adapter contract were inspected offline. tests/native/storage_tail_pages.c demonstrates a test-only 256-byte-tail mapper around the unchanged project_store interface; it is not production code or a storage ownership decision.

[inferred] The reserved-window approach appears to fit the documented 43,130-byte bound, but exact production integration, imported-data versioning, flash erase behavior, stock-loader interactions, sector ownership, migration and rollback are unresolved. It does not establish sector availability, update safety, SPL runtime behavior, SAVE admission, hardware acceptance, or installability.

## Compatible candidate: reserve the full final 256-byte page

[verified: project_store contract and arithmetic] A coarser reservation can fit the existing journal's logical erase geometry more naturally. Reserve the entire physical page [sector+0xF00, sector+0x1000) in every sector, leaving 3,840 data bytes per 4 KiB sector. Twelve physical sectors provide 46,080 packed bytes. Expose eleven logical 4 KiB units (45,056 bytes) to project_store; after the 32-byte header, the payload ceiling is 45,024 bytes, 1,894 above the conservative 43,130-byte bound. The remaining 1,024 packed bytes are unused. This is less capacity than the 80-byte window scheme, but it preserves the store's 4 KiB logical slot size and keeps every candidate's complete 80-byte scan window erased.

[inferred] A test-only dedicated slot adapter can map the contiguous 45,056-byte logical stream into physical fragments of 3,840 bytes, skipping each final 256-byte page. Reads reconstruct the packed stream. Programs split at the 3,840-byte physical-fragment boundary and at physical 256-byte page boundaries, never reaching the reserved page. The adapter erase callback receives an aligned 4 KiB logical offset, finds every physical sector whose packed-data interval overlaps that logical 4 KiB range, and erases those physical sectors. The current lunar_project_begin() calls erase for every logical sector before setting the store active; thus duplicate physical erases and overlap into the next packed fragment happen before any new payload program. That ordering is a necessary part of this candidate's contract and should be locked by tests before reuse. No erase call may target the active slot.

[verified: interface boundary] This still needs a specialized packed-slot adapter; extent_io alone is linear and sector-aligned, so it cannot skip pages. Unlike the 80-byte packing proposal, the 256-byte candidate leaves logical slot size a multiple of 4096 and preserves the existing journal hash/CRC stream semantics. This test-only prototype evaluates that mapping; its host success is not a physical initialization or migration proof.

[verified: test-only host harness] The C harness exercises logical erase ordering and mapped physical mutations. Pytest compiles it with repository host sanitizer flags and runs it under a bounded Hera container (2 CPUs, 4 GiB memory/swap, network disabled); the focused test passed with 43,130-byte payloads. This validates the model against project_store on the host only, not flash-controller behavior, complete SPL/cleanup predicate execution, or physical power-cut behavior.

[unresolved] This post-format invariant only protects replacement of an already formatted slot whose reserved pages are known 0xFF. It does not prove that the initial transition from unknown stock VM/USR bytes to the invariant is safe: a partial erase of an arbitrary old sector could transiently form a candidate record before erase completes. Existing ownership/migration, SPL behavior during that transition, and physical interruption behavior remain outside this offline design result. The initial data must not be assumed blank or safe merely because the target format will reserve the page afterward.

# Reserved SPL trailer windows in the storage48 scatter map

2026-10-14. Offline design analysis only. No production code, device state, or admission flags changed.

## Result

[verified] The 12 sectors in each proposed slot contain one conditional stock SPL trailer candidate at physical sector offset +0xF00. On the documented 1 MiB profile these addresses are also inside the retained cleanup loop's candidate interval. All 24 candidates intersect both scans.

[inferred] The simplest persistent-state invariant is to keep the full 80-byte candidate window erased (0xFF) in every journal sector. Then no serialized journal bytes can form either the SPL signature/CRC predicate or the broader loader-cleanup predicate. Preserving only signature bytes +6..+7 blocks both predicates, but the full window is easier to audit and leaves no dependence on how the other fields evolve.

[verified: arithmetic] Each 4 KiB sector would expose 4,016 packed data bytes if the 80-byte window is reserved. Twelve sectors yield 48,192 packed bytes; after the existing 32-byte journal header the payload ceiling is 48,160 bytes. This exceeds the conservative 43,130-byte collector bound by 5,030 bytes. This is capacity arithmetic, not allocator ownership or flash acceptance.

## Why the current adapter does not implement this safely

[verified] `project_store.h` models a slot as a contiguous byte range whose size is a multiple of 4096. It erases at logical offsets 0, 4096, 8192, and so on. Its serialized/hash stream is contiguous. `extent_io.h` maps sector-aligned extents and requires erase requests to identify one aligned 4096-byte sector; reads/programs translate linearly across those extents.

[inferred] A mapper that simply rejects accesses into each physical +0xF00..+0xF4F window cannot satisfy the current store contract: the store serializes and hashes contiguous bytes that can span those locations. Returning synthetic 0xFF bytes would also make readback hashes differ unless a separate framing layer strips the reservation consistently.

[inferred] A 48,192-byte logical slot is not a direct fit either. It is not a multiple of the store's 4096-byte erase unit, and logical erase boundaries drift relative to physical boundaries if 4,016-byte data chunks are packed consecutively. Treating each 4 KiB physical sector as a 4 KiB logical block avoids erase drift only if the journal format includes 80 bytes of per-sector framing/padding. That changes the serialized format and its hash semantics.

## Recommended design boundary

[inferred] If implementation proceeds, introduce an explicit sector-container layer rather than bending the generic extent mapper. Keep the physical contract sector-index based: the container owns a fixed ordered list of 12 physical sectors, erases exactly one listed sector by index, and maps a logical stream of 4,016-byte data fragments over each sector while skipping the 80-byte tail. Reads reconstruct the packed stream; writes split at fragment boundaries; candidate windows are never writable and must read as 0xFF. The journal's payload/header/hash contract should remain over the reconstructed packed bytes. Version this container format separately from the journal content schema.

[inferred] An alternative is to store 4 KiB logical blocks with 80 bytes of explicit container framing per physical sector. That is easier to align with `project_store` erase offsets, but wastes 80 bytes per block and requires the reader/writer to distinguish container bytes from journal bytes. Do not treat padding as journal payload or include it inconsistently in CRC/hash calculations.

The existing `extent_io` mapper is useful for bounds/protection and physical extent translation, but it cannot by itself provide this packing behavior. A minimal future interface should separate `erase_sector(index)` from logical byte offsets and expose logical capacity independently of physical slot bytes. This note proposes the boundary; it does not implement it.

## Initialization and interrupted-operation invariant

[inferred] “Window remains FF” is a post-initialization invariant, not automatically true while importing arbitrary preexisting flash. A sector erase changes bits from 0 to 1 and may transiently create the exact signature pattern from unknown old bytes. Therefore a safe initialization argument needs both (a) a known and externally retained prior state, and (b) no stock SPL/cleanup path being invoked during the destructive transition. This repository analysis does not establish that transition as physically safe or authorized for a particular device.

[verified: current host model only] The existing fake-NOR journal tests inject prefix erase/program failures and complete-operation-then-error cases. Those are useful software fault models, not characterized flash-chip power-cut behavior. Future container tests should assert the 80-byte reservation stays all-FF across every modeled failure and independently run both the SPL predicate and loader-cleanup predicate over every sector after each operation.

Meaningful cases include: initialize every candidate window; fail erase partway through each of the 12 sectors; fail erase after the physical erase but before success is reported; fail program immediately before and after each fragment boundary; reject any write overlapping a reserved window before mutation; cross-extent logical reads/writes; verify reconstructed payload and journal hashes; verify old committed generation after interrupted replacement; and run the two distinct record predicates on all 24 physical candidates.

## Scope and acceptance limits

[verified] The address-set arithmetic and the current adapter contracts were inspected offline. No test-only container prototype was added because the current store's erase-unit/logical-stream coupling requires choosing and reviewing a new format boundary first.

[inferred] The reserved-window approach appears to fit the documented 43,130-byte bound, but exact production integration, imported-data versioning, flash erase behavior, stock-loader interactions, sector ownership, migration and rollback are unresolved. It does not establish sector availability, update safety, SPL runtime behavior, SAVE admission, hardware acceptance, or installability.

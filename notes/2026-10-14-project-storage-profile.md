# Native project storage admission profile — 2026-10-14

Status: standalone geometry/admission helper and host tests added. This change
does not enable NOR I/O, identify a flash map, bind the SAVE service, or grant
ownership of any physical byte range.

## API boundary

`firmware/native/project_storage_profile.h` accepts an explicit caller-owned
profile containing the observed/expected JEDEC value, flash and operation
geometry, a `layout_verified == 1` marker, non-empty allowed extents, and
explicit protected extents. There are no default extents or inferred storage
regions. The caller must derive the marker and extents from a separately verified
layout and keep the descriptor immutable while using it; the marker is an
admission precondition, not cryptographic provenance. The helper cannot
enforce either provenance or immutability because both the marker and extent
arrays are caller-owned. The adversarial test mutates a valid profile's
allowed extent while leaving `layout_verified == 1`; revalidation then admits
the new caller-supplied range and rejects the old one. This demonstrates the
API boundary rather than a supported way to change a verified layout.

The helper currently recognizes only JEDEC `0x856014`, 1 MiB capacity, 4096 B
erase sectors and 256 B program pages. The JEDEC and runtime driver's command
geometry are pinned-source facts in `notes/2026-10-14-native-nor-hal-audit.md`;
they do not establish the installed part's actual capacity, NOR protection
state, or application ownership. Every range is validated as a non-empty
half-open interval using subtraction before any end calculation. Admission
rejects unverified/unknown profiles, invalid or overflowing ranges, sector
misalignment, duplicate/overlapping allowed extents, overlapping protected
extents, and allowed/protected intersections. Per-operation checks additionally
require erases to be whole aligned sectors and programs to stay within one
256-byte page and one allowed extent.

The helper is intentionally not included by `project_save_service.h` and does
not set `storage_admitted`. That service still requires an independently
installed `storage_admitted == 1` and a complete I/O binding. No code path in
this patch calls the physical HAL.

## Verification

`tests/native/project_storage_profile_test.c` checks 45 assertions covering
valid lower/tail boundaries, no implicit extent, the exact verifier marker,
recognized and matching JEDEC values, geometry mismatch, null/missing arrays,
excessive extent counts, integer-overflow/out-of-flash extents, sector
misalignment, protected zero-length/out-of-bounds/overflow extents, reordered
disjoint extent arrays, reverse-ordered exact adjacency, allowed/protected
conflicts including a one-byte edge intersection, erase range containment,
page-edge programs, page crossing and out-of-range program requests. It also
demonstrates that a caller-controlled `layout_verified` bit does not establish
profile provenance or prevent mutation of caller-owned extent arrays.

Run with `python3 tests/native/project_storage_profile_hera.py`. The runner
uploads only this header and C test into a unique Hera directory, then compiles
and runs with GCC ASan/UBSan in the existing pinned image
`sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d`.
The container uses `--network none`, UID 1001, 1 CPU, 512 MiB fixed memory and
swap, `docker-batch.slice`, a read-only root filesystem and read-only source.
The successful run on 2026-10-14 reported 45 assertions passed,
`container_exit=0`, `oom=false`. Source hashes:

- Header: `110aacfaa57c1fbce68107d638a020a24c7902e1cd34424c6ece1cef4d8c80c1`
- Test: `5a193ff6fd8180dc1b5e816b2b0f2a299d62d9309f2c694c7c074988f80c8922`

The two earlier failed runs were assertion failures in the test's synthetic
protected ranges, corrected before the recorded successful run; neither reached
hardware or made a write. The successful expanded-run output remains at
`/home/claude/mvave-fm1/project-storage-profile-20261014T094852Z-b69c4d0c/out`.

## Limits and next dependency

This is geometric admission logic only; it does not prove profile provenance,
board identity, nor flash capacity from the JEDEC value, and it does not
protect against descriptor mutation or concurrent writes. It has no read/write
transport and does not prove the HAL's XIP-off call graph, interrupt policy,
watchdog servicing, completion/readback or power-failure behavior. No device,
USB or flash operation was performed.

Next integration requires an independently reviewed expanded raw-flash map
with exact extents and protected intervals, reproducible source/package
evidence and immutable-profile ownership. Then a separate adapter change can
convert that verified layout into this descriptor and feed successful
admission to the still-closed service binding. It must preserve SAVE's audio,
display and retry constraints and add fault-injected transaction/readback
verification before any physical acceptance gate. Parent reviewed the geometry implementation and adversarial evidence before
checkpointing. No commit was made by the delegate; coordinator backs up the
reviewed files on the installable-firmware branch.

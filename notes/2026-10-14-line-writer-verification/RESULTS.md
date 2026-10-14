# Compact sequencer-line writer verification

[verified] Compact binary output streams each encoded SEQS line directly,
accumulates the chunk CRC, and retains the existing 48 KiB chunk cap,
16 KiB raw-line cap and header-last commit. Other chunks remain buffered.
Writer scratch is 39,176 host bytes, previously 71,936: 32,760 bytes saved.
Pinned pi32v2 compilation with Werror emits a 39,132-byte size getter.
This is an isolated workspace measurement, not complete firmware RAM fit.

[verified] 169 tests pass in 30 Hera containers (source-v3/output-v3):
64 sequencer export cases, 75 binary streaming/parity/boundary cases and
30 project-store streaming cases, using ASan/UBSan. All thirty logs,
23 source hashes, zero process/container exits and no OOM/skips were checked.
Nine fixture outputs match the normal writer byte-for-byte. All 276 normal
and 304 compact FIRSTORBIT callback failure positions refuse safely.
Actual sequencer/binary cases inject 10,830 binary write failures.
Boundary cases accept exact line/chunk/destination capacity and reject each
one-byte overflow without writing a final header. Tests enforce no repeated
programming of a destination byte and no writes after completion/refusal.

The first campaign failed because its archive omitted the firmware header
needed by the project-store harness and the new synthetic SET omitted its
required opening movy1 record. Both fixtures were corrected; complete v3
supersedes v1, whose full failed logs are retained privately. Source-v2 was
staged but not tested. Target command correction: -mfprev1 and the pinned
compiler system-header directory are required; earlier malformed options and
missing-header attempts failed before producing target assembly.

Full logs/assembly: ignored build/native-line-writer-20261014/v3/.
Public launcher, collection, hashes, container results and target measurement
are alongside this report. No hardware operation or physical SAVE acceptance.
Native workspace allocation, collector/SAVE wiring, read-only validation,
flash capacity, migration, physical rollback, all13 acceptance, installer,
custom builder, licensing and review/CI/integration remain outstanding.

Semantic tool limits: Serena resolved the absolute worktree size getter;
Rarefaction resolved only the older primary checkout, with fallback flags and
no callers. Neither semantic index proves pi32v2 ABI or hardware behavior.

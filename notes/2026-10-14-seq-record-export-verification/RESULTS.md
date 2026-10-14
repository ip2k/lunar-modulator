# Sequencer to project-record adapter verification, 2026-10-14

[verified] `engines/state/state_seq_export.h` emits SET LINE records directly
from sequencer fragments, with FIRST/LAST boundaries and no whole-set or line
buffer. Record refusal propagates through the callback exporter; no subsequent
callbacks occur. Caller must discard a failed enclosing transaction.

[verified] 64 cases in 30 Hera containers passed with ASan/UBSan: 15 fixture
sets plus a dense eight-track set, in both compatibility modes, through both
raw text and project-record paths. 38,664 injected failures include zero,
partial and complete fragment consumption followed by refusal. Fixture faults
exercise every callback; dense faults sample boundaries and every 1024th
callback. Output matches the buffered formatter and sequencer bytes remain
unchanged. Both seq_persist.c and a wrapper instantiating the real adapter
compile with the pinned pi32v2 compiler in every chunk.

Evidence: verification.json, source-hashes.json, collection.txt and
case-metrics.json. All 30 full logs are private under
build/native-seq-record-export-20261014/hera-results-v2/. Eight pinned hashes,
64 metrics and all exits/no-OOM checked after retrieval. SSH session34186
completed with exit0. Failed v1 staged source omitted fm1_json.h; v2 includes
state dependencies and target adapter compile. No v1 success is claimed.

Limits: record tests reconstruct text and check boundary semantics; they do
not yet compare actual binary-writer output. No application collector/SAVE
integration, complete firmware link, RAM/flash allocation, migration, physical
operation or hardware persistence verification occurred. Next: binary-codec
parity and collector integration, followed by bounded workspace/storage design.
Shared semantic tools remain selected on the primary checkout; the earlier
bounded exporter navigation does not prove this worktree's device ABI.

## Actual binary codec verification

[verified] source-v3/out-v3, session55383 terminal0: 64 cases pass in 30 Hera
containers. The 32 record-mode cases additionally compare actual compact binary
writer output against whole-line input byte for byte, validate the resulting
container with the CRC-checking reader, and refuse all 10,208 binary write
callback failure positions without emitting a header. Thirteen hashes and all
logs/exits/no-OOM checked after retrieval. binary-case-metrics.json records sizes
and cuts. Full logs under the private hera-results-v3 directory.

This still uses desktop scratch allocation. Target compilation covers exporter
and adapter; full firmware link and device workspace fit are not established.

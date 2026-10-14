# Direct project collector verification

[verified] Application project records now have a dedicated public collector
`fm1_app_state_collect_project`. It emits HEAD through END synchronously,
uses streaming sequencer records and propagates sink refusal. It does not
use the desktop JSON/file/whole-set staging buffers. Existing PROJECT saves
share the extracted collector implementation.

[verified] 76 tests passed in 30 concurrent Hera containers, output
`project-collector-v1`, source `project-collector-source-v1`. All thirty full
logs, seventeen source hashes, zero process/container exits and no OOM/skips
were independently checked. The project round-trip helper additionally saves
through the dedicated collector and random-access binary writer, reloads that
file, and compares the entire canonical project byte-for-byte with the existing
JSON and binary routes. This covers the start chain, FIRSTORBIT example and
the rich session exercised by the existing helper; it is not an exhaustive
maximum-size project proof. Desktop test harness suffix `.stream.lunarb` selects
the direct path. The harness allocates writer scratch on the desktop heap.

[verified] The complete application-state source compiles with the pinned
pi32v2 compiler using external arenas, Oz, freestanding/no-builtin, function/data
sections and Wall/Wextra/Werror. The initial compile lacked engines/host in
its include search path; adding that existing header directory succeeded.
This is compilation, not a firmware link or proof of ABI/runtime operation.

Native sequencer cases (64) use ASan/UBSan; application cases (12) are desktop
O2. The supplemental jsonschema dependency directory is as documented in the
previous seq-collector receipt and is not a hermetic dependency lockfile.
Full logs and target object remain under the ignored local build directory.

Limits: no new hardware operation. Compact binary writer workspace, native
SAVE binding, read-only full project validator memory, flash allocation,
migration and physical rollback remain unresolved. The legacy desktop global
buffers still exist; no firmware RAM saving has been measured. Record provenance
still follows the simulator collector and must be adapted for firmware use.
Sink refusal is structurally sticky; exhaustive public-collector failure tests
remain to be added separately from the existing binary writer fault campaign.

Semantic navigation: Serena resolved the stream writer from the absolute
worktree source. Rarefaction bare-symbol orientation did not resolve it and
searched only a bounded fallback index in the primary checkout; neither result
was treated as target linker or hardware evidence.

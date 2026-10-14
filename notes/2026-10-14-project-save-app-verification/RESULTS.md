# Actual application SAVE adapter verification — 2026-10-14

[verified] `project_save_app.h` forwards actual project records to the bounded
SAVE bridge, overriding only producer metadata to firmware. Caller-exclusive
app ownership and affirmative audio/drawing/display-read stop flags remain
required. The adapter does not establish flash ownership or implement scheduling.

[verified] Initial v1 ran thirty cases in thirty Hera containers. All failed
one incorrect assertion: the simulator re-export was expected to retain firmware
producer metadata. `head_out` emits fresh simulator metadata on each simulator
save. No container was OOM-killed. Complete failed logs are retained privately in
`build/native-project-save-app-20261014/v1/`. The correction checks native binary
writer ID and info metadata with the independent Python binary reader, then
compares fresh-app reload state with the original simulator export.

[verified] Corrected v2 passes all thirty cases under ASan/UBSan in thirty
concurrent Hera containers. All thirty logs, successful process/container exits,
OOM flags and thirteen exact source hashes were checked. Private complete logs:
`build/native-project-save-app-20261014/v2/`.
Cases cover thirteen engines with two unit configurations, FIRST ORBIT in two
configurations, a DX7 user voice and the default chain. Each exercises two SAVE
transactions, inactive slot selection, admission refusal without I/O and redraw
following framebuffer workspace release. The target adapter is compiled with
pinned pi32v2 clang. This is host-modeled storage, not a full firmware link or
physical SAVE test.

[verified] Source inspection rules out a proposed bound based on adding each
chunk type's cap once: `FM1_REC_UNIT` opens a separate UNIT chunk per instance.
The streaming directory also reserves all sixty-four entries. No smaller
maximum project bound or physical flash allocation has been established.

[verified] Serena resolved this worktree's `head_out` by absolute path.
Rarefaction oriented the primary checkout's corresponding symbol using fallback
flags, which matched the inspected metadata behavior; its checkout and index
are not proof of native ABI or this worktree's full call graph. No shared MCP
project selection was changed. No device command occurred in this continuation.

Next: finish this campaign; integrate and measure native SAVE scheduling/link;
resolve physical storage ownership/capacity; watched all13 boot, settings
migration and physical rollback; web installer/builder and release gates.

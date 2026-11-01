# Corrected combined native diagnostic fit

Personal, non-commercial. [verified] Fresh target build source
`e267d7cd58efef29afb2c0c38562f4878e8106f5`; no source/profile/budget change.
This supersedes the historical9440b081 diagnostic sizing only for the exact
selected profile below. It does not establish aggregate full-product fit.

## Actual target result

[verified] Unchanged `sdk-free-single-fm6-diagnostic-v1` built127 fresh objects
and linked successfully with pi32v2/r3/fprev1 `-Oz`, external engine arenas,
modules dx7/arp/lfo/env/chance, trunc12 sine, one65536B engine arena and
8-voice runtime limit. No SDK libraries, object cache, workspace flag, or
pipeline define. Native link and unchanged original audit_link both exit0;
the standalone audit reports12 pass,0 fail,0 pending. No hardware action.

| Target allocation | Bytes | Address / limit |
| --- | ---: | --- |
| app (includes UI/events/seq/mod/MIDI-effect storage) |239360|0x01c18020|
| sound arena |65536|0x01c08020|
| external arena descriptors |112|0x01c52728|
| .text |210800|0x02000120|
| .data |4|0x01c08000|
| total .bss |306768|0x01c08010|
| .noinit crash record |64|0x01c7c000|
| flat flash image (.text+.data) |210804|stock-sized XIP ceiling unchanged|
| _guard0 - _bss_end |135584|0x01c52e60 →0x01c74000|
| user stack reservation |24320|0x01c74100 →0x01c7a000|
| supervisor stack reservation |7936|0x01c7a100 →0x01c7c000|

App/sound/descriptors are already included in total BSS; do not add them
again. Alignment gaps and linker section accounting remain in the map.
Guard intervals0x01c74000–0x01c74100 and0x01c7a000–0x01c7a100 are reserved;
this run did not implement/measure guard checks, stack high-water or maximum
call-depth/interrupt nesting. Linker retained ceiling0x01c7fd50 passed.
Compared with the historical9440 build, app and total BSS each grew6528B,
headroom fell6528B, and flash grew440B. These are measured artifact differences.

[verified] Separate read-only target C99 const-size object probe, using the
same compiler/flags/includes (never executed and not linked into candidate),
confirms pointer4B, app239360B, event36B, panel UI660B at app offset13260,
sequencer arena32768B, event array9792B at offset199616, modulation arena26880B
and MIDI-effect arenas3072B. UI/event/arena quantities here are app members,
not additional allocations. This does not size full product display or pipeline
working buffers. Retained audio halves1024B and LCD fill buffer480B appear
separately in the map; merged-global aliases must not be double-counted.

## State workspace and source binding

[verified] No `FM1_APP_STATE_EXTERNAL_WORKSPACE` override was needed. The
actual map's Discarded input sections include `.bss.g_default_workspace`
(size0xe0020 =917536B), state_save and edit_state_hash. Final symbol table has
no default workspace, state save/load/check/pack, edit hash/dump, g_plan or
pipeline work/start symbols. Both map placement and linked ELF were inspected;
a text match somewhere in a map alone would not prove reachability. Native
persistence remains unavailable and the large explicit workspaces remain
unallocated/unusable in this diagnostic.

[verified]745 source-manifest entries match both frozen exported source and
the local exact-source worktree; all127 recorded object hashes checked before
cleanup.189 original and189 configured libc++ header hashes checked; only
configured __config differs (the existing deterministic no-pthread change).
Actual extracted toolchain tree matched the approved archive in full, before
compiler execution, and remained unchanged after build:

- archive SHA256 `f686586bcfb45e0f0bb27fd2b39c7a7f313cb4f0e88a66a14da621ffa8225958`
- tree SHA256 `851733550499eca33cd737b2343bf48a1c846e0fe7246054d8372d43e7cfa066`
- canonical source-manifest SHA256 `24374d6fc467602458cc8d9c78be95c918c9265e33332642e706d58c9ffc632c`
- source Git export SHA256 `95ca5f5e514bdd47f4318f5ee8558774119657f4fcb294be22b2afddfe28855a`
- native ELF SHA256 `764eeb0ad83461a9966f0d093999b1860b6249d20e047afa5f5f83ca60475008`
- flat app SHA256 `4ad5b65285b22725be02312d2e45f71ab5802d3bb403214c5464afef544c40b8`

[verified] Focused pure-Python suites test_native_diagnostic.py,
test_audit_link.py and test_rom_witness.py:95 passed,1 expected skip (no new
ROM-witness native bundle requested). The diagnostic target result and actual
artifact binding were verified separately as above. Existing unchanged ROM
witness was not rebuilt; its prior exact bundle remains historical evidence.

## Execution and limits

Owned Aeon stage `/home/likwid/datasets/lunar/native-combined-20261101t123431z`.
CPU8–11,4CPU6GiB/memory-swap6GiB, docker-batch.slice; immutable existing image
`sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`.
Read-only root/source/toolchain/archive/headers, network none, UID/GID1003,
cap-dropALL,no-new-privileges,pids256,/tmp128MiB; local logs max-size1m/max-file1
compress=false, labels and --rm. Outer wall limit1200s TERM+15s KILL, exact
owned-container cleanup. Both main build and size-probe containers exited0
and were removed; CPU8–11 released. No downloads/vendor unpack/device/loader,
package, service/listener activation, or infrastructure changes.

Current diagnostic does not link native renderer lifecycle/core and does not
define FM1_APP_RENDER_PIPELINE. It cannot establish pipeline/CPU1 fit, full
module configurations, persistence or complete application fit. Fixed FM6,
notes/four parameter encoders and blank LCD are the selected adapter; no full
controls, master ADC, USB/MIDI transport, interactive screen, bootguard or
fail-open recovery application. Compilation is not exercise of every corrected
Capture/MATRIX/engine/state branch. No target audio/PCM/deadline/perceptual
acceptance. `hardware_admitted=false`, `release_candidate=false`; package and
public-distribution gates remain closed.

Navigation: existing Rarefaction/Serena primary-root readiness verified;
external-worktree semantic access remains limited. No shared-root switch. Exact
source/build/map reads and fresh target artifacts supplied this bounded proof;
no whole-code audit claim (the repository-wide audit remains overdue).

## Private evidence and lifecycle

Private local evidence: this worktree
`scratch/native-combined-20261101t123431z/evidence/` with receipt, size JSON,
ELF/app, map/listing, full symbol table, audit JSON/log, container configuration,
source/object/header verification and sizeof-probe source/JSON. Test logs, exact
launch/build/probe/verification commands and inventory are in the enclosing
scratch directory. Candidate ELF/app remain private for exact review only.
No binary/vendor material is committed. Shared pinned SDK/toolchain/headers
remain unchanged. Cleanup and final source/push status are recorded below.

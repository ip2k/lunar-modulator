# Retained native SAVE link measurement

[verified] One offline full LTO link ran on Hera, retaining
`native_project_save_target` alongside the pinned all-thirteen-engine FIRST
ORBIT/Shapes12 diagnostic baseline. All 281 original linked object hashes and
baseline ELF hash were checked. Three objects were replaced by current
application collector, sequencer persistence and compact binary codec objects;
the SAVE target harness was added as an explicit linker root. Thirty identical
links would not add distinct coverage, so this dependent measurement used one
container. Existing SAVE logic coverage remains in the thirty-chunk campaigns.

[verified] Link exited zero; all 37 compiler-reported source/header dependencies
match the current worktree. SDK-free/eFuse audit passed with zero pending checks.
Independent artifact flattening passed entry, stack reservations, section/load
geometry and unresolved-symbol checks. `native_project_save_target` is retained
as 0x4D4 bytes of executable code. Whole firmware link has no unresolved symbols.

[verified] Application bytes: 860,188, an increase of 14,272 over the installed
baseline. The physical app origin is 0x4120; the executable XIP entry 0x02000120
is not a raw-flash origin. Remaining raw tail is 11,972 bytes, of which 3,324
bytes remain reserved for configuration records: link budget margin is 8,648
bytes. Globals/arenas still end at 0x01C736C0, leaving 2,368 bytes before the
stack guard. This is not free heap or observed stack margin. An initial local
receipt calculation mistakenly used 0x1120; it failed JSON serialization before
writing a receipt and was corrected using the shared flash-layout constants.

[verified] New ELF SHA256:
`9f727255daa42b5f8a6cae321f973560cbb8b2fa44b12347bd6344239d3616c1`.
Flattened application SHA256:
`daf32e3ee7a92a2294ab493501205ecc67d40c031a8750b28b6f1d5fb21ca7b0`.
Private ELF/map/compile/dependency/link outputs are under
`build/native-project-save-link-20261014/v1/`; receipts, scripts, dependency
hashes, audit and section sizes are saved here. Reproduce collection with
`python3 notes/2026-10-14-project-save-link/collect.py` when private inputs exist.

This is a retained-code footprint experiment, not a fresh complete release
build. The test harness supplies guard flags; it does not establish actual
runtime scheduling or flash ownership. No SAVE event wiring, physical write,
boot, migration or rollback occurred. Baseline callback/stack evidence does not
transfer automatically to this changed ELF. The smaller flash tail increases
storage pressure; safe maximum-capacity project allocation remains unresolved.

[verified] Serena resolved this worktree's `lunar_project_save_app` definition
by absolute path. Rarefaction oriented primary-checkout `head_out` and its old
`collect` caller with fallback flags. Shared project selection was preserved;
that old index is not used as proof of this worktree's full graph or native ABI.

Next: native SAVE scheduling/validator/HAL integration, maximum-project storage
allocation and stock migration; watched all13 boot and physical rollback;
web installer/selectable builder, licensing, review/CI and release integration.

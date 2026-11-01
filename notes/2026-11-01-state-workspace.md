# Explicit state workspace: bounded first step

Personal, non-commercial. Base fcd2e934524fb2a918cb68ce4029a98b430ecd6e;
branch feature/2026-11-01@state-workspace. Own sim/web/src/fm1_app_state.c/h,
focused workspace tests, this note. No app.c/h, engine codec, pipeline/browser
or hardware changes. Parent approved CPU12–15,4CPU6GiB isolated containers.

## Read-only storage and lifetime map (before source edits)

[verified] C11 host probe: pointer8, plan11792, JSON reader1752, record168,
app4960112. Six arrays exactly983045 bytes: writer/rate491520, clip32770,
JSON262145, binary98304, set65538, scratch sequencer32768.

Save: canonical writer and JSON coexist; project/clip/set collection holds set
text. JSON is retained through canonical read into binary writer. Writer and
binary writer already share one aligned arena. Binary output stays buffered
until all encoding/limit checks succeed, preserving all-or-nothing output.
Pack: canonical writer→JSON→binary writer, same JSON and binary lifetime.
Load/check: plan survives pass1→validated clip merge→FM6 sweep→pass2→apply.
Set remains live; clip copy and scratch sequencer coexist while validating the
merged set. All engine rate_ok calls precede sequencer/clip validation, so its
writer/rate arena may overlap the clip+seq pair. Clip merge heap output is
retained until check returns or live apply completes; never allocate a merge
after mutations start. Existing JSON and binary readers use stack workspaces.

Calls: web save/check/load/pack and MIDI-map wrappers; edit state_hash→save.
Load disables app on_mod/on_mfx/on_cmd callbacks during apply. edit note_loaded
and enter/leave do not save. Public rd/put may reenter; existing global scratch
is nonreentrant. New busy guard must refuse nested operations before scratch,
output or live app changes. MIDI-map setter shares plan, so it needs the guard.

## Concrete implementation plan sent to parent before edits

Existing codecs/formats/caps remain. Add operation-size query and explicit
caller-owned aligned `_with_workspace` save/pack/check/load entrypoints.
SAVE917536B, PACK851984B, CHECK/LOAD557072B including 16-byte padding; the latter
overlays rate scratch with clip+seq after rate checks finish. Keep static plan
for now and serialize use. Host legacy wrappers retain aligned default scratch;
FM1_APP_STATE_EXTERNAL_WORKSPACE=1 removes that default and legacy calls refuse.
No native UI exposure or native persistence-fit claim: even the ~476KB JSON
writer alone exceeds current diagnostic headroom. Codec compaction/streaming,
reader stack and clip-helper heap remain release blockers beyond this lane.

Refuse missing/undersized/misaligned/overflowing/busy storage; detect overlap
with live app and external unit arenas, opts/report and known memory sources
before callbacks/output/mutation. Custom rd/put contexts are opaque; their
nonaliasing and synchronous ownership must be explicit caller contracts, since
unreported allocation extents cannot be mechanically discovered.

Tests: normal+ASan equivalence (host-default vs explicit workspace JSON/binary,
pack/check/load, malformed refusal), guard/canary/overlap/busy/atomic output
checks and host C11/pi32 object storage sizing separately. Preserve all format
limits and validation. Actual target link/hardware not claimed.

Lifecycle: unique local scratch/state-workspace-20261101 and Aeon
/home/likwid/datasets/lunar/state-workspace-20261101. Keep small reports/logs;
remove generated binaries/objects/venv/caches/staged source after results.
Keep unmerged source worktree for review; parent removes after integration.
Commit/push explicit refs and verify SHA; no worker PR/merge. Shared claim
lunar--state-workspace-20261101, atomic handoff on exit. Mac1121GiB free.

Navigation: Rarefaction scope and Serena symbols agree with bounded state.c
reads; Rarefaction primary checkout lacks root compile DB and cross-file
callers are incomplete. Current shared Serena selection ready, unchanged.
External worktree examined directly at exact base. Callback/codec/clip and
build-source checks supplement semantic results; no whole-index claim.

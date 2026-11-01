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

[verified] Actual pi32v2 baseline C11 object (vendor clang -target pi32v2
-mcpu=r3 -mfprev1, no link/hardware): pointer4, plan11596, JSON reader1584,
record164, arrays983045, default app4957952. Read values from emitted const
size table using vendor common/bin/objdump, ELF32-pi32v2, not host sizeof.
Toolchain archive hash freshly checked f686586b...25958; extracted compiler
is existing SDK-v1213-gpl-int/toolchain/current (internal20250324.1 directory).
Installer lane independently owns actual archive/tree-binding verification.

## Implementation checkpoint

[verified] The first focused normal harness run passed against an exact
pre-change state.c snapshot as well as the modified default/external builds:
all seven state kinds × four save modes, check/load, JSON pack and PCM hashes
agree. Added storage span/alignment/app/engine/source/report/descriptor overlap,
undersize/missing and nested callback guards, canaries and malformed-release
checks. Review then found and fixed larger load-report tail overlap: an error
must not write even the codec prefix when any part of that report aliases
scratch. The new regression and sanitizer run remain pending at this checkpoint.
The first sanitizer build's staging source was updated during its run; its
result will not be accepted as final evidence. A fresh stable-source rerun is
required. No target fit claim; target object/storage proof remains pending.

Independent review found the attached host-owned edit object's extent is known
and live across project loads. Reject overlap with a->edit as well as app and
unit arenas; added a real fm1_edit_attach regression checking full edit/app
bytes and zero output. Source freeze for final evidence includes this fix.
The first GCC ASan baseline executable stayed at one CPU for more than five
minutes and was stopped; it is inconclusive. Final sanitizer verification will
use the existing clang ASan image, with per-executable 180-second timeouts.

## Final verification (production behavior frozen at d3330cf5)

[verified] Stable-source normal GCC and Clang AddressSanitizer (including leak
checking, halt_on_error) runs passed the focused test. Four independently linked
configurations in each run: exact fcd2 state TU baseline, current host default,
external state workspace, and external state workspace + external engine arenas.
All eight executable outputs were `state-workspace 6cb92c98`. The baseline TU
was obtained with `git show fcd2e934524fb2a918cb68ce4029a98b430ecd6e:sim/web/src/fm1_app_state.c`;
SHA256664c459f316b9107b79e160855a895cc8c166cb7ac497209e13c77a2148e9024.
Other source stayed at the named base plus this lane's state files/tests.

Coverage: seven kinds (project/sound/FX/mods/clip/set/settings), four save modes
(JSON or raw movy1, compressed/plain/no-view binary), successful check/load,
canonical re-save and JSON packing, identical post-project-load PCM, full-size
workspace canaries; missing/short/misaligned/wrapping storage, app/external unit/
attached edit/opts/report/descriptor/known source aliasing, larger report tail
aliasing, synchronous put/read callback reentry (including shared MIDI-map
plan), malformed refusal and ownership release. Invalid preflight produced no
output and preserved live app/edit bytes. A native-flag legacy call refused
before callback or mutation; host legacy saved bytes matched explicit calls.
Opaque callback backing allocations remain a documented caller nonaliasing
contract; concurrent threads require external exclusion. No format cap changed.

Commands from a checkout (pytest build products are placed in the lane-owned
`--basetemp`, removed after collecting logs):

```sh
FM1_WORKSPACE_BASELINE_SOURCE=/lane/baseline_state.c python3 -m pytest tests/test_state_workspace.py -q --basetemp=/lane/test-normal-final
FM1_WORKSPACE_BASELINE_SOURCE=/lane/baseline_state.c FM1_SIM_CC=clang FM1_SIM_CXX=clang++ FM1_SIM_EXTRA='-fsanitize=address -fno-omit-frame-pointer -g' ASAN_OPTIONS=detect_leaks=1:halt_on_error=1 python3 -m pytest tests/test_state_workspace.py -q --basetemp=/lane/test-asan-final
```

[verified] Separate actual ELF32-pi32v2 C11 compile/object proof, with
FM1_APP_EXTERNAL_ARENAS=1 in both state variants (no target link or execution):

| Quantity | Target bytes |
| --- | ---: |
| Pointer / plan / JSON reader / record | 4 / 11596 / 1584 / 164 |
| SAVE / PACK / CHECK+LOAD workspace query | 917536 / 851984 / 557072 |
| Host-default state TU BSS | 929512 |
| External-workspace state TU BSS | 11976 |
| Default array removed by external flag | 917536 |
| External app struct, independent of workspace | 239360 |
| JSON writer / binary writer | 481244 / 289496 |
| Binary reader state / source window / inflater / accumulator | 52 / 100 / 4920 / 168 |

BSS is the sum of emitted BSS sections: plan11596 and merged globals380,
plus default917536 only for flag0. The private size probe includes the actual
state source and emits const tables; vendor objdump reads those values. Host
C11 compilation with `-Wall -Wextra -Werror` passed both flags; a separate Mac
C11 assembly probe emits JSON writer481272. Older hardcoded size comments were
stale and are corrected without changing behavior. Host sizeof is not target
proof. Link-time reachability, stack high-water and target deadlines remain
unmeasured here.

Target command shape (the full exact script/probes stay with private evidence):

```sh
/opt/jieli/common/bin/clang -target pi32v2 -mcpu=r3 -mfprev1 -std=c11 -Oz -ffreestanding -fno-builtin -ffunction-sections -fdata-sections -isystem /opt/jieli/pi32v2/include -Iengines/include -Iengines/state -Iengines/host -Iengines/mod -Isim/web/src -DFM1_APP_STATE_EXTERNAL_WORKSPACE=1 -DFM1_APP_EXTERNAL_ARENAS=1 -c /lane/current_sizes.c -o /lane/current-1.o
/opt/jieli/common/bin/objdump -s -j .rodata.fm1_workspace_sizes /lane/current-1.o
/opt/jieli/common/bin/objdump -h /lane/current-1.o
```

All heavy jobs used approved CPU12–15,4CPU6GiB (no swap beyond6GiB),
docker-batch.slice, --rm, project=lunar/session=state-workspace-20261101 labels.
Images: normal/target `lunar-jieli-check:bookworm` immutable ID
sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495;
Clang ASan image ID is retained in `asan-image.log`. Existing toolchain mounted
read-only at /opt/jieli; no archive/toolchain/source-vendor binaries in Git.

Independent review: service_security_review confirmed the corrected production
source at d3330cf5 using actual-source helper checks normal+ASan/UBSan, verified
whole and partial attached-edit overlap refusal, flag1 default-array omission,
and read the mirrored final equivalence logs. Its report is under performance
scratch `audit-20261101/state-workspace-review.md`; coordinator owns acceptance.

This completes explicit ownership and optional static arena removal only.
**Native persistence still cannot fit:** even JSON writer481244 exceeds current
headroom, and LOAD557072 leaves no feasible native budget. Future codec
compaction/streaming must preserve full caps and output/load atomicity. Clip
merge heap ownership and target reader/caller stack still require separate work.
No app.c/h, engine JSON/codec, pipeline, browser, UI, hardware or native diagnostic
link was changed; hardware_admitted=false. Parent must keep persistence hidden
until a separately reviewed usable native implementation fits and passes target
acceptance.

Small evidence: worktree `scratch/state-workspace-20261101/evidence/` and Aeon
`/home/likwid/datasets/lunar/state-workspace-20261101/evidence/`. Reproducible
build/staged-source/Python package/object products are removed on lane exit;
small logs/scripts/probe source retained. Unmerged clean worktree remains for
coordinator review/integration, then coordinator removes it.

## Proposed next bounded implementation (no codec rewrite begun)

The smallest useful next slice is an **app-only canonical record replay path for
binary save**, retaining the existing binary writer and host JSON/pack paths.
It removes both the 481244-byte whole-document JSON writer and 262145-byte JSON
staging buffer from binary app save. This does not solve native fit: a conservative
actual-target layout is binary writer aligned289504 + staged final binary98304
+ full set text aligned65552 = **453360 bytes**, plus a small fixed canonical
walker/validation context (budget4096), so a concrete first acceptance ceiling is
**457456 bytes**. All existing modes/caps remain on legacy paths until exact
parity and validation are proved; do not silently route an unsupported mode.

Files: sim/web/src/fm1_app_state.c/h (new internal ordered app walker and explicit
profile gate), focused app-save fixtures; a small reusable count-only canonical
JSON formatter/validator factored from engines/state/state_json_write.c and
fm1_state.h in coordination with its codec owner. Keep the existing arbitrary-
record whole-document JSON API and host behavior. No app.c/h or UI change needed.

Direct collect→binary is insufficient: unit_out currently interleaves per-pad
values by parameter, whereas canonical JSON/read emits global parameters first,
then pads, each by ascending UID. Canonical JSON also supplies defaults, normalizes
values/names, validates references and changes omission/presence behavior. The
new app walker must mirror that order exactly: head/info, session, each sound's
unit/global params/pads/level/inserts/MIDI effects, masters, sorted FM6 slots,
modules/UIDs/data/cables, set lines, view, MIDI-map bindings, end. Use repeated
bounded table scans for next UID (max32 engine/module parameters), avoiding a
whole-document param table. Reuse the current partial-state modulation selection
and remapping rather than inventing another dependency rule. The app is the
replay source, not an arbitrary imported document; arbitrary JSON pack remains
on the existing path.

Preserve validation/caps by running the canonical count-only JSON formatter and
semantic checks over this same replay before any binary bytes are handed out;
retain the project262144, clip32768, set65536, binary98304, parameter/data/chunk
limits and existing failure codes. Then feed the proven canonical records into
the unchanged binary writer, retaining the final binary buffer until all encode/
compression checks pass. Compression stays byte-identical because it receives
identical records/chunk bytes in identical order and the same version/flags.
Save requires the owning thread to hold app/control-state exclusion through all
replays; neither rd/put callbacks nor an audio/control ISR may change saved bases,
patterns, set or mappings. A generation check alone cannot undo mutation after
output begins. Validate this contract before native UI exposure.

Proof: capture the old canonical JSON reader's emitted record trace and compare
new walker records, canonical count and final compressed/plain/no-view bytes
across all seven kinds, full rich FM6/pad/pattern/MIDI-map fixtures, shuffled UID
tables, boundary/over-limit documents and randomized valid app states. Verify
all refusal cases produce zero output and identical reports; run normal+ASan,
actual pi32 C11 size/object proof and link/RAM audit. A mismatch keeps the old
route active. The bound is a design acceptance ceiling based on measured target
objects, not an executed new implementation or a deadline/fit result.

A later genuinely native-sized path must also replace the 289496-byte binary
writer: count/CRC each chunk in a dry replay, freeze the directory, then emit
header/directory and replay payloads without retaining the whole body. Exact
compressed bytes require adapting the current deterministic deflater as well;
its 64KiB input/output arrays plus32KiB scratch preclude pretending that a simple
callback wrapper fits. An explicitly named uncompressed-only native save profile
could be a smaller subsequent slice, but preserving fail-before-output requires
complete preflight plus stable replay and full format/cap validation. Do not
start that broader codec work or claim a <=128KiB bound without measuring its
line/data/sequence/MIDI and compression lifetimes first.

Lifecycle close: verified no lane containers running, removed all owned Aeon
staged source/build/Python/object products, retained only112KiB evidence, and
explicitly released CPU12–15 directly to sound_state_fixes for its unique stage.

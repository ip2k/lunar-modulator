# Cleared sound chains and FM6 sound restore

Personal, non-commercial Lunar work. Base: `b831724fcf413720aaa036dac742a382cdfaa93c`.
Branch: `fix/2026-11-01@sound-state-fixes`. Coordinator owns integration; this lane
does not open a PR, merge, run a device operation or change native adapters.

## Evidence and behavior

[verified] Audit findings A2/A3 were reproduced before source edits using the
extended `sim/web/test/fm1_edit_check.c` and the unchanged application sources.
The normal host `--edit-check` returned failure with 135 failed assertions:
unchanged FM6 restore lost the held note, all 128 continuation blocks differed
from the control and the restored output was silent; clearing Sound 4 left its
two insert instances, RAM accounting and missing insert-clear editor notices.
The regression checkpoint is `defe86dfdf2467126e8c526b809bc05f223f2668`, pushed
and its remote SHA verified. Small raw logs are in the lane's ignored evidence
directory (below). The source audit itself was source-only; these are subsequent
executed host results.

[verified-source] Clearing a nonprimary sound now releases its insert instances,
rebinds their modulation sinks, clamps the current FX page and emits the insert
clear records before the parent clear. This is a bounded loop without recursive
application selection. Normal engine replacement retains the insert chain.
The existing sound-note release path, sequencer routes, mix levels and other
sounds' notes retain their existing behavior.

[verified-source] RESTORE_SOUND now compares a live unit's canonical registry
identity via its stored index. It keeps the actual live FM6 descriptor, parameter
table, patch names and sizing data. Complete-parameter eligibility remains a
separate prerequisite. Ordinary imports, genuinely different engines and sparse
sound files retain their recreate/default behavior. No codec version, schema,
parameter UID, audio algorithm, sample rate or event scheduling change is made.

The focused regression covers repeated Macro/FM6 restore with a held note,
exact 128-block FM6 continuation versus a control, FM6's live parameter metadata
and sizing, replacement and sparse-import behavior, cleared insert allocation
and RAM, editor records, preserved routes/levels/other notes, and JSON/binary
round trips of the intentional empty sound state. Its audio cases use 44,118 Hz;
msfa initializes process-global rate state, so switching a single test process
from 44,118 to 48,000 Hz is not a valid multi-rate test.

## Validation and handoff

[verified] Final normal and ASan/UBSan `--edit-check` runs both returned exit 0,
`failed: 0`: 380 parameters, 28,621 steps, 47 hands, 40 sweeps, 900 lock
blocks, 30 telemetry fills and 12,774 fuzz operations. Sanitizers used
`-fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer`
(the existing legacy shift exclusion) and halt-on-error; no sanitizer diagnostic.

[verified] The broader host suite passed: **145 passed, 5 skipped**, exit 0,
81.63 s. It covers app state, codec, state render, editor, arenas and renderer
pipeline tests, including normal/ASan PCM continuity and fault refusal cases.
Command: `CC=clang CXX=clang++ FM1_GPL_MODS=1 FM1_SIM_CC=clang
FM1_SIM_CXX=clang++ python3 -m pytest -o addopts= -q -ra
tests/test_app_state.py tests/test_state_codec.py tests/test_state_render.py
tests/test_sim_edit.py tests/test_sim_arenas.py tests/test_app_renderer_pipeline.py`.
Three skips need jsonschema, one needs the optional JSONTestSuite checkout and
one needs node. Browser parity, a final integrated WASM rebuild and hardware
acceptance remain coordinator dependencies.

The first broader attempt lacked `g++` and failed fixture setup; explicit clang
compiler selection resolved it. A permissive-profile attempt had three example
codec failures because those checked-in songs require GPL-only comet. Repeating
with the declared GPL-enabled profile passed all three. No pass is claimed for
either failed attempt.

The preapproved lan-compute workflow is used. Aeon was verified to have online
CPUs 0–15, so CPU16–19 was refused; the coordinator assigned this lane exclusive
CPU12–15. Every container uses `--rm`, `docker-batch.slice`, CPU12–15, at most
4 CPUs and 6 GiB memory/swap, with project/session labels. Image:
`lunar-asan:ubuntu-24.04`, ID
`sha256:54edd6544fdc41ef5573ae26f7aa8e7d1f594e5e4b9b54e2ad2f427f33e392a1`.
No new image, service or infrastructure configuration is installed.

Rarefaction status and Serena initial instructions/current configuration were
checked. Both select `/Users/likwid/Developer/mvave-fm1-firmware`, not this isolated
worktree. Selection was intentionally left untouched for concurrent sessions.
Rarefaction cannot reach this worktree outside its fixed root. A bounded
position-based orient/scope on main found `fm1_app_select`, its expected wrapper
callers and release/rebind callees; a bare-name query hit its 200-file search cap.
Serena found the same symbol and wrapper callers. These queries establish only
bounded navigation, not complete cross-file coverage. Authoritative edits/read
checks use the pinned worktree source and explicit caller searches. There is no
root compile database, and no pi32 ABI/stack or hardware correctness claim.

Evidence location on Mac:
`scratch/sound-state-fixes-20261101/`; on Aeon:
`/home/likwid/datasets/lunar/sound-state-fixes-20261101/`.
The source stage, binaries, pytest intermediates and caches were removed after
copying final results; only small logs and source-hash receipts remain (732 KiB
on Aeon). No lane container remained running at cleanup. The worktree remains until coordinator integration, then
remove it using `git worktree remove` after verifying no uncommitted work.
Mac data-volume free space at start: 1,123 GiB; at this checkpoint: 1,120 GiB
(above the 500 GiB floor).

## Declared browser rebuild inputs

These three changed files belong to `sim/web/tools/source_hash.py`'s sim inputs;
the engine inputs are unchanged. This lane does not update a stale WASM record
without rebuilding it. The coordinator must rebuild the final integrated tree
and rerun browser parity; additional integrated edits will change the final hash.

At this lane's current source:

- Engine source hash, before/after:
  `872562d992cbe9f0c07f523eef9852ca6a250955e2e98e01a966f9a46d0dd58a`.
- Sim source hash at base:
  `a75ce3f4d69d2f9c33f7abb2f7c0139d1f3e03f28fb58afb1e262e2be8d7093e`.
- Sim source hash after this lane:
  `e78b23ce97459b2bb2186e8ac851ab0302e0ce3fb5401de6996d6ee807b2cd9f`.
- `fm1_app.c`: `33ae5a1799def480a72d1a8945db7ac104ecba4bdc6719439f9d83b5a6c08825`
  → `5ffeafb74316cb0fdb296ed9378b726fcdab5f12b09615b2545b9602569f6116`.
- `fm1_app_state.c`: `350cbdd589a55dc0e25f8271626f90d26ae58de973846f299346cf75aa60480d`
  → `0ed13125172c18145b163d210bc77146f4b465a9ff87e07770940486daad2e1c`.
- `fm1_edit_check.c`: `37bf68b09485a8757efad4fc9667c0122d0461ceb4b04cc36a1340c3fe2d6f47`
  → `16eaf5196c82fc8c89ac318dcfcb96a4ae5a0bf5464d55dd3aab28cf884383a4`.

## Follow-up A6/A7 (in progress)

The coordinator authorized two further app-state audit fixes after independent
A2/A3 checkpoint `64d499ed5750d7364447d99d25db0937b8d020c2`.
[verified] Focused RED checks on that unchanged application source returned
392 failures: six invalid headers changed the whole live app, all 384 PCM
continuation blocks differed from controls, and a real allocation refusal in the
second clip merge still reported success without inserting the clip. The
fault-only harness wraps the merge and realloc at link time; it fails realloc
inside the chosen real merge, rather than replacing application behavior.
First-merge allocation refusal already preserved app state. Source fixes and
final validation remain pending at this regression checkpoint.

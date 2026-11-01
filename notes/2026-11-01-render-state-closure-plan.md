# Host saved-state modulation dependency closure

Personal, non-commercial. Base b831724fcf413720aaa036dac742a382cdfaa93c;
branch fix/2026-11-01@render-state-closure. Own engines/host/render_state.cc,
a focused dependency fixture/test and this note only. Sound-state app worker
owns sim/web/src/fm1_app.c and fm1_app_state.c; no changes there.

Reproduce LFO -> Calc -> sound/FX upstream loss before editing. Retain the
transitive upstream source/via dependencies of every retained sink cable,
including incoming module parameter/gate cables, disabled routes and cycles.
Preserve collector order and original rack/cable IDs; exclude outgoing routes
to unrelated sinks and disconnected modules/cycles. Full project/mods unchanged.
Use a bounded monotone closure over eight module positions, no recursion.

Tests: fail baseline for sound and FX; records/parameters/data/cable IDs match
expected closure and JSON/binary reload; deterministic PCM matches original
where unrelated closure is inaudible; long chain/cycle/via/gate cases. Existing
state-render regressions if feasible. No hardware/SDK. Aeon CPU4-7,4CPU/6GiB
in docker-batch.slice --rm, unique /home/likwid/datasets/lunar/render-state-closure-20261101.
Preserve logs/small reports, remove generated WAV/state/build/venv/staged copies
when recorded; keep unmerged source worktree for review then remove on integration.
Mac free-space floor500GiB. No PR/merge by worker; commit/push explicit branch
ref and verify SHA, atomic shared handoff and claim release on completion.

Navigation: Rarefaction exact primary ModRecs scope found Save/Add and sourcefile;
clangd fallback lacks compile database/cross-file completeness. Serena primary
ModRecs lookup agrees with source. Shared selection unchanged, external-worktree
reads bounded; no complete semantic-index claim. Existing session instructions
and current config reviewed. No graph built.

[verified] Baseline: all six chain cases (sound1, sound2, FX × JSON/binary)
fail because rack [2] replaces expected [1,2]. First complete fixed run passes
20/30; the remaining sound2 cases exposed a test CLI typo (save uses sound2,
load uses s2), now corrected. No source failure observed in these 20 cases.
Nine-pass monotone source/via closure implemented; final verification pending.
Evidence stage/evidence/baseline.log, baseline-chain.log, fixed.log.

## Final evidence and handoff

[verified] Corrected-test baseline at exact b831724f: all six chain cases
(sound1/sound2/FX × JSON/binary) fail with rack [2] versus [1,2].
`baseline-corrected-test.log` records this source-level behavioral reproduction.
The first sound2 test draft used the wrong save prefix; corrected before this
baseline rerun. No production CLI change was needed.

[verified] Final test command:
`python3 -m pytest tests/test_render_state_dependencies.py tests/test_state_render.py -o addopts= -q`
Result: **41 passed in 1.89s** (30 new cases, 11 existing state-render cases).
The renderer fixture runs `make -C engines -j4` with default all modules,
GPL_MODS=1, C++11 and trunc12. Existing unrelated compiler warnings remain.
New cases cover sound1/sound2/FX, JSON/binary, eight-position reverse chains,
reachable/disconnected cycles, nested via, module gate/parameter inputs,
disabled incoming routes, system-only sources, remapping, stable positions and
cable IDs/order, unrelated outgoing exclusion, a nondefault Register pattern
`1234567810`, and byte-identical 0.2-second PCM after reload.
Existing project/mods/direct-preset checks pass. This is offline host evidence,
not target stack/deadline, browser or hardware acceptance. App sound-state
source was not changed. No SDK or device actions.

[verified] Aeon container image lunar-jieli-check:bookworm,
sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495,
--rm, project=lunar/session=render-state-closure-20261101,
--cpuset-cpus 4-7 --cpus 4 --memory 6g --memory-swap 6g
--cgroup-parent docker-batch.slice. The image has no pytest/ensurepip; copied
pure-Python pytest9.1.1 and dependencies from existing project venv into this
lane only, disabled plugin autoload/bytecode, no image/infrastructure changes.

A deliberate baseline/fixed source swap preserved an older mtime on restore,
so an intermediate run reused the baseline object (24 expected dependency
failures, 17 passes). Touched the restored staged source, rebuilt, and obtained
the final 41 passes above. Final local/staged source hashes match:
render_state.cc a4ba294531d425ef4a47c2cfa06f18b07e52582b5f509c47a1576aa651c018a8;
test file ffd86a28a927bd08b91cb0b9b1b0416753cf27358ff71d5728bd1c32ccb77f6b.
Authoritative final log: evidence/final-rebuilt-verification.log.

Only first-party MIT host/test code added. Full project/mods path bypasses
closure filtering as before; preset path computes monotone incoming reachability
without recursion, adding at most eight positions and a final cable scan.
The final emitter preserves original collection order and existing remappers.

Branch fix/2026-11-01@render-state-closure. Parent must review/integrate through
required CI; no worker PR or merge. No unresolved implementation blocker.
Keep this unmerged worktree for review; parent removes it after integration.
Owned generated source/build/WAV/state/test/cache/Python copies are removed
after recording evidence. Keep small logs under ignored local
scratch/render-state-closure-20261101/evidence and Aeon lane/evidence.
Mac free space before/after: 1121 GiB (above 500 GiB floor).

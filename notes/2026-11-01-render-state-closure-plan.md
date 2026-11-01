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

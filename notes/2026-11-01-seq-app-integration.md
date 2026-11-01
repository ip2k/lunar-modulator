# Immutable sequencer event targets in the app

Personal, non-commercial Lunar work. Exact base:
`ba080c86c188d8be25a4f29dbea58c875ca5f59e`; branch
`fix/2026-11-01@seq-app-integration`. Coordinator owns integration and the
combined source WASM build. No device operations or native adapter edits here.

[verified] The app now resolves queued effect/mixer LOCKs from each event's
immutable `label` and `lane_base`. Block-boundary comparison and knob base edits
still resolve the current lane. `seq_auto_release` is unchanged: it restores
configured values through captured engine/unit/index targets before reset/import.

[verified] The new app probe queues audition, release, then optional lane reuse
before one render. It checks core event identity and the ordered old-target
boundary restore/audition/reset writes for inserts, master slots and mixer level.
It checks reused-lane targets/bases and the next clear. With old dispatch retained
and new event ABI scaffolding, the final regression fails `old_writes == 3 &&
new_writes == reuse`; the snapshot dispatch passes. Test rendering uses one frame
after queued edits so an unrelated next-step reset does not obscure these writes.
The manual test LOCK constructor follows the core snapshot contract. The probe's
Makefile now reads its generated dependency file because it includes `fm1_app.c`;
without that, app-only changes could run a stale probe binary.

[verified] Budget: 272 events * 36 B = 9,792 B, up 6,528 B from 12 B/event.
The eight-track instance is 32,080 B inside its unchanged 32,768 B arena; instance,
events, pending command 240 B, UI bound 1,024 B and click 20 B total 43,156 B
within the revised 45,056 B (44 KiB) implementation budget, a coordinator-approved
routine implementation choice. Aggregate target fit remains unproven.
The desktop app guard grows by the
8 KiB implementation budget delta to 4,968,192 B, rather than matching exact sizeof.
The two conditional `static PipelineSlot pipeline_work_storage[2]` event arrays
add 13,056 B together; this is static storage, not stack. No new large local array
is introduced. Actual target link/RAM fit remains a separate integration gate.

The first focused normal run exposed a test setup assumption: with the revised
budget, the default 96 kHz chain plus a second Macro hits RAM preflight before
Macro can refuse the rate. The RATE test now clears its default first master
effect to leave room. Production refusal priority and engine rates are unchanged.
[verified] Final focused native checks: **10 passed, 2 deselected** normal and
**9 passed, 2 deselected** ASan/UBSan, with explicit clang compilers and the
MIT/BSD module profile. The deselections are existing browser-WASM parity and
stored edit-storm metadata tests; no fresh WASM was built in this lane. Native
edit check reports failed=0, 380 parameters/28,621 steps, 47 hands, 40 sweeps,
900 lock blocks, 30 telemetry fills and 12,774 fuzz operations. Sanitizers use
`-fsanitize=address,undefined -fno-sanitize=shift -fno-omit-frame-pointer`,
halt-on-error and Linux's normal leak detection; no sanitizer diagnostic.

[verified] Both normal and ASan/UBSan pipeline tests completed successfully:
baseline, immediate and delayed renders are byte-identical per mode, each
22,581,248 float PCM bytes over 44,104 blocks; all seven fault modes refuse with
exit 72. The first aggregate runner subsequently failed its evidence-printing
`rg` command (not installed in the image), after pipeline pytest had exited 0.
The final evidence uses `awk`; final focused runner exits 0. No broader suite
was repeated because the parent already validated that integration scope.

[verified] Linux clang 64-bit host `sizeof(fm1_app_t)` is **4,960,112 B** with
embedded 4,718,592 B engine arenas, and **241,520 B** with
`FM1_APP_EXTERNAL_ARENAS=1`. These describe host layout, not pi32v2 ABI or target
fit. The coordinator's pre-SS2 desktop measurement was 4,953,584 B; event-array
growth accounts for the exact +6,528 B. `nm -S` measures the conditional static
`pipeline_work_storage` at 60,640 B total (two slots), of which 19,584 B is the
new event arrays: their former 6,528 B gives the exact +13,056 B delta. The
snapshot app adaptation adds no local event array or heap allocation.

[verified] Final source checkpoint is
`a141882a6f32fd5e3a52b0bc06ca7bed50c4d06d`, pushed and remote SHA verified.
Source hashes from `sim/web/tools/source_hash.py` at that checkpoint:
`sim=3a16c2665c24b08310a24eb4511c3d5130d17e17e88102c70b88a564b3b0ba19`,
`engines=6b2b2dbbb94e5660700ea8a723c0a3a5f24b1f5231ba943f09f0908ef1e1900a`.
Coordinator must compute combined hashes after integrating its other lanes;
this note follow-up changes neither source hash.

Rarefaction status/orient/scope and Serena initial/config/symbol checks succeeded
on shared main, including `seq_auto_target` and its event caller. Their fixed root
is `/Users/likwid/Developer/mvave-fm1-firmware`, outside this isolated worktree;
no global project activation/restart was performed. Rarefaction on-open clangd
has no compilation database and missed begin/base callers. Pinned source and
explicit call searches in this worktree remain authoritative.

Aeon online CPUs 0–15 verified; exclusive CPU12–15 assigned by coordinator.
Preapproved lan-compute workflow: Docker `--rm`, `docker-batch.slice`, cpuset12–15,
4 CPUs, 6 GiB memory/swap, project=lunar/session=seq-app-integration-20261101.
Evidence/scripts: ignored local `scratch/seq-app-integration-20261101/` and remote
`/home/likwid/datasets/lunar/seq-app-integration-20261101/`. Reproducible stage and
builds will be removed after recording results; small logs retained. Worktree stays
for coordinator review, then normal removal after integration. No WASM regenerated.

[verified] Cleanup complete: reproducible remote source, normal build, all five
pytest work directories and helper binary removed after checking no lane container
was running. No containers remain with this lane label. Evidence/scripts retained:
144 KiB each in the local and remote paths above. Mac Data volume has 1,120 GiB
available, above the 500 GiB floor. The isolated worktree and pushed branch remain
for coordinator review; the original sound-state worktree/branch are untouched.
Next dependency: coordinator review/cherry-pick, combined WASM source batch,
aggregate native memory/link acceptance and existing release gates. No blocker or
new owner decision in this lane; no timing, hardware or physical acceptance claim.

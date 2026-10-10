# Repeat bounded source review

Reviewed immutable pushed checkpoint 3425f4ebf23c7091405f783bf667c960d02f71ae read-only, 2026-10-09. Working tree was actively changed by implementer; git-show snapshot is the evidence. No hardware traffic, no worktree edits.

## Confirmed findings

1. Dry release endpoint corrupts dry output. engines/src/fx_repeat.cc:139 SetWet, :170 BeginRelease, :279 StepRamps. SetWet(0) when wet==0 creates zero-step ramp; immediate FinishRelease does not cancel wet_left. Endpoint assigns wet=1 because wet_step>=0, even with held=0. At default Mix=.5 and .5 DC, START/STOP/RESET or initial HoldOff outputs .25 after 221 frames at 44118 Hz instead of .5. Correct explicit endpoint/settled ramp cancellation; cover dry transport and repeated HoldOff.
2. Mix repeated target resets ongoing smoothing. SetMix at :124 always rewrites mix_left/step once rendered. Independent probe sets target1, renders5, repeats target1; at original deadline no-repeat mix1,left0 vs repeated .988947,left5. Existing tests/test_engine_smooth.py repeated-write gate is appropriate and must remain. Correct target equality guard.

[verified: native] Independent gcc:12 C++11 -O2 probe on LAN Docker batch slice (2CPU/1GiB), immutable source and headers. Probe /tmp/lunar-repeat-review-3425/probe.cc; LAN /home/claude/mvave-fm1/repeat-review-3425. Transcript below. Findings sent to implementer/root; no source patch made by reviewer.

```
ev=2 n=221 wet=1 held=0 armed=0 last=0.25
ev=1 n=221 wet=1 held=0 armed=0 last=0.25
ev=8 n=221 wet=1 held=0 armed=0 last=0.25
ev=0 n=221 wet=1 held=0 armed=0 last=0.25
repeat_mix a=1 left=0 b=0.988947 left=5
```

3. Immediate beat after quick re-hold can latch the unchanged released segment, contrary to the code comment at SetParam. Established held loop -> HoldOff -> 5 frames -> HoldOn during release -> remaining216 frames -> next-call BEAT: capture_head/ring_write remain1, no input was recorded; held0/armed1 becomes held1 with same window. Native exact-source probe confirms it. This is a semantic/comment mismatch requiring the implementer to choose whether fresh capture is required; it is not a memory-safety defect or a proposed hardware change.

## Other bounded checks

[verified: source] Explicit rate guard admits finite8–192k, tempo20–300 fallback. Cap halving reaches1/256 at192k20BPM9000frames (<16384); only bounded conversions after guards. Initialized aligned 65536B ring counted by instance_size, full-ring readiness documented2.048s8k. Held reads end at frozen write head; seam meets sample0 exactly and avoids OOB. Generic NaN/inf, split and repeated-write tests added without exclusions. Current direct tests cover states but omitted dry-output assertions on dry transport paths, which let finding1 pass eight focused tests.

[verified: source] Tempo/window change is frozen-window crossfade, not earlier proposed varispeed; current note accurately states final implementation. RESET direct test does not claim host emitsRESET. Full initial readiness and cap policy disclosed. No runtime/hardware/CPU-fit claim.

Tooling: Serena activated engines worktree and returned exact StepRamps body. Rarefaction invocation used wrong cpp profile then corrected to c; shared fx_host symbol was not found and fixed primary root does not index new Repeat branch, so exact git source fallback used. No binary/device ABI claim from semantic tooling.

Pending: implementer fixes plus focused/generic/native+Wasm validation at final actual combined head; review new code if requested. This review is backed up on a separate documentation branch; it does not update any pending implementation CI head. Fixes remain the implementer's stream.

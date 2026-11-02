# 2026-11-01: release and performance handoff

## Source and release state

- Current source: `main` merge commit `a1b7823ba768d7657474f9be432d7584998b1501`, which merges PR #160 (`feature/2026-10-28@perf-levers`).
- The 320 MHz performance images were built from `cddf3ded` on that feature stream; the soak's `cap8-trunc12` image used the same source with `--cycles 57` instead of 3.
- Owner decisions recorded 2026-10-29: guarantee eight voices for release; keep twelve as a stretch goal; use trunc12 as the default DX7 sine after the owner A/B'd cases 0–3 and reported no audible difference.

## Dev-kit evidence

The 30-minute buffered run on the AC79 dev kit lasted 1,823.4 seconds (30.4 minutes) and produced, harvested, and submitted 1,256,964 blocks. Faults, backend errors, DAC-late events, and DAC gaps were zero. All 228 case hashes and the fold matched host replay. Producer mean was 22,970 ticks (66.0%); consumer mean was 28,848 ticks (82.8%), under the 29,604-tick mean limit. Two producer blocks exceeded the 34,829-tick block budget (34,978 and 34,850), but the queue covered them and the DAC did not run short. The documented eight-slot queue latency is 11.61 ms; with the three-window DMA ring it is 15.96 ms.

The worst block was at a case-segment start and spent 21,112 of its 34,978 ticks in `dispatch`. A source audit found `voices[c]` note-ons injected at exact `CASE_BLOCKS` boundaries in `renderer_live.c`; no per-case program change was found. This identifies a coincident event and a measured cost, not a confirmed cause. The cause remains unresolved.

The analog capture passed the listed detector screen, including the planted 16-block dropout calibration. That screen is not listening or owner acceptance. The soak was not listened to. The run used the dev kit's internal DAC, not the FM-1 ALNK0/external-codec path; no Lunar application was run on the physical FM-1. The minimum in-run queue depth was not measured: the available `ready_min` sample is taken before acquire and end-of-run drain forces it to 1. The 360 MHz figure remains an estimate by scaling 320 MHz measurements, not a 360 MHz run.

Source evidence: [`notes/2026-10-29-devkit-soak30.md`](2026-10-29-devkit-soak30.md), [`notes/2026-10-29-devkit-perf-levers-320.md`](2026-10-29-devkit-perf-levers-320.md), and [`firmware/devkit/renderer_live.c`](../firmware/devkit/renderer_live.c) in PR #160. The code-audit finding was relayed by the parent agent; no separate audit report path was supplied for this handoff. Raw bench receipts are in the ignored `scratch/bench-2026-10-29/` directory and were not copied into this branch.

## Remaining acceptance work

- Measure minimum queue depth in a fresh buffered run if queue margin is required as a release metric.
- Obtain owner listening/acceptance for the soak workload.
- Validate the release candidate on the physical FM-1 through the authorized staged hardware process, including its ALNK0/external-codec audio path. Dev-kit results and scaled timing do not satisfy those gates.

## Validation of this handoff

Documentation-only change. Checked that the referenced notes and source file exist, the cited base is the PR #160 merge commit, and the edited Markdown links are repository-relative. No firmware tests, device commands, or device writes were run.

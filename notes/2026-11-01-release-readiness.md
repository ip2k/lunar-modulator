# Lunar release and installation readiness — 2026-11-01

## Owner objective and current baseline

Owner resumed work and authorized parallel implementation lanes, then set the
objective: get Lunar Modulator ready for release and installation, including
missing firmware, the web-based installer and customization. This supersedes
the paused lane's narrower fixed12 optimization priority. This is a personal,
non-commercial project; existing licensing, device and publication gates apply.

[verified] Starting integration base is origin/main
`a1b7823ba768d7657474f9be432d7584998b1501`, PR #160 merged. Its required CI
jobs completed successfully (the PR deployment job was skipped). Eight voices
are the owner's release target; twelve is a stretch goal. The owner approved
trunc12 by A/B listening; the fixed-eight dev-kit soak passed the documented
buffered rule. See the October 29 performance and soak notes. Those results
are not physical FM-1, owner soak listening or distribution acceptance.

The old private V225/V226 work is preserved in
`/Users/likwid/.codex/worktrees/devkit-performance-20261022/scratch/devkit-20261023/`.
Its board-current statements are historical, superseded by later bench work.
Do not install an old candidate, retry any consumed reset or infer current
hardware state from those notes. No hardware action has occurred on this resume.

## Completion criteria

- Firmware and browser source integrate through required review and exact-head
  CI. Release defaults implement the owner-approved eight-voice policy.
- A coherent customization flow validates engine/effect/project selections,
  reports resource and licensing constraints, and binds build results to the
  exact selected configuration. Reuse existing installer work before adding more.
- The web installer accepts only compatible, admitted artifacts and has truthful
  progress/errors, disconnect handling and a documented recovery path. Diagnostic
  or build-only receipts must never imply installation or device acceptance.
- Storage, boot/fail-open, update and rollback gates are resolved under the
  current physical-unit recovery policy. Actual FM-1 audio, controls, display,
  persistence and update round trips require fresh hardware evidence.
- Release packaging and user instructions match demonstrated behavior; proprietary
  SDK/raw captures stay private, and distribution respects the selected licenses.
- Listening, hardware and publication requirements remain explicit until met.
  Do not call source tests or a dev-kit soak a completed product release.

## Active lanes and file ownership

| Lane | Worktree / branch | Deliverable |
|---|---|---|
| Coordinator | lunar-tonight-20261101 / feature/2026-11-01@milestone-integration | Review, integration, release gates and sole hardware coordination |
| Queue margin | lunar-queue-margin-20261101 / feature/2026-11-01@queue-margin | Running-only queue minimum plus receipt/parser tests |
| Release handoff | lunar-release-handoff-20261101 / chore/2026-11-01@release-handoff | Current HANDOFF status with acceptance limits |
| DX7 bank export | lunar-dx7-export-20261101 / feature/2026-11-01@dx7-bank-export | Browser VMEM download using existing core exporter |
| MIDI clock | lunar-midi-clock-20261101 / feature/2026-11-01@midi-clock | Existing sequencer realtime input wired into browser scheduling |
| Installer audit | Existing installer branches read-only initially | Gap map and first bounded installer/customization implementation |
| Onset audit | Private report in historical performance scratch | Trace actual segment-start critical work and propose measured fixes |
| Algorithm1 proof | Private V226 scripts/reports | Directed complete-state proof; optional twelve-voice stretch, no target claim |

Independent lanes use isolated worktrees, push explicit refs and verify SHA.
Coordinator reviews results before integration. No worker may use USB/MIDI,
flash, reset or power hardware. UI/bridge lanes coordinate overlapping functions.
Heavy work uses bounded containers with cleanup: Aeon CPU0–3 bank export,
8–11 state proof,12–15 MIDI; queue tests use4–7 if needed. Hera was unreachable
through IPv4 and the documented IPv6 path on resume; no power action was taken.
Use the reachable Aeon fallback rather than assume the cause of that failure.

## Immediate next dependencies

1. Review installer audit before starting new installer architecture; the
   existing continuous-installer-service stream contains substantial unmerged
   work and historical hardware receipts that must not be replayed.
2. Review and integrate the small returned source lanes with real tests and
   required CI. Preserve dirty owner files in the primary checkout.
3. Replace the old note-on/case-change guess with actual source tracing before
   another performance change. Queue telemetry is evidence, not a speedup.
4. Establish the exact next physical-FM-1 milestone from current recovery and
   installer handoffs, then prepare a concrete bounded test under that policy.

## Persistence and cleanup

Automation `continue-lunar-dev-board-audio-performance` is ACTIVE again, named
"Continue Lunar release readiness"; it reads this file and reports meaningful
milestones or blockers only. Save lane handoffs, small reports and receipts;
remove owned reproducible build/test artifacts. Retain worktrees until reviewed
and integrated, then remove them through git. Do not clean another session's
files. Built-in disk free space on resume:1,129GiB (floor500GiB).

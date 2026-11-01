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

## Current integration and acceptance

[verified] Foundation branch `feature/2026-11-01@milestone-integration` is
pushed at `b831724fcf413720aaa036dac742a382cdfaa93c`. PR #161 is open;
exact-head CI run 41296360365 succeeded, as did Pages build 41296360432.
Deployment was skipped for the PR. Full actual WASM rebuild passed 108 parity
scenarios, metadata/edit parity, SysEx, routing and MIDI realtime checks;
the 30-second edit storm had zero late quanta or resynchronizations.

The foundation supplies complete DX7 bank export, ordered MIDI realtime input,
queue-margin telemetry, offline customization/catalogue and a strict shared
request contract. The public page exports requests and inspects packages;
it does not build or install firmware or claim resource fit.

Real-Chrome visual review remains pending. The owner approved chrome-browser,
but browser access was disabled in Work settings when checked. An owner prompt
is pending. Do not bypass that setting. Preview is loopback-only at
`http://127.0.0.1:8767/installer.html`, owned exec session 63121 in the
foundation checkout. Stop it after review or before pausing.

PR #151 has a separately reviewed WebKit action-lock fix at `ca6f3c14`.
Its exact-head CI 41296941683 is still being checked. Preserve this change
when combining later sequencer browser fixes; never overwrite action().

## Release corrections stream

Current coordinator checkout is
`/Users/likwid/.codex/worktrees/lunar-release-corrections-20261101`, branch
`fix/2026-11-01@release-state-corrections`, based on the approved foundation.
Integrated and pushed corrections include:

- MATRIX destination enumeration uses bounded metadata snapshots. Differential
  tests cover 492,640 events; actual pi32 local frame allocations fell from
  roughly 6 KiB each to 652/376/404 bytes. This is not whole-stack acceptance.
- FM6 copied descriptors retain stable engine identity for modulation routes
  and unchanged SOUND restore; held-note PCM continuation is preserved.
- Clearing a nonprimary sound releases its owned inserts and emits notices.
  Replacing an engine still retains its insert chain.
- Edit text indices reject nonfinite/out-of-range float conversions before
  casting. Sixteen focused sanitizer cases pass.
- BAD dropped files remain dismissible; Solo is bound to project identity and
  observed state; view replacement rejects stale snapshots; reconnect cancels
  pending edits and rejects old-port acknowledgments. Independent review
  approved the four fixes. Reconnect tests inject lifecycle events rather
  than proving a complete physical/audio power cycle.
- Browser-state regressions are wired into each browser CI job.

A combined full WASM rebuild is required after the current source-fix batch;
individual host proofs do not make the old generated module current.
Do not hand-edit generated acceptance hashes.

## Other active lanes and dependencies

- Private installer service extraction is independently approved at
  `d62044bc`. Dedicated integration branch
  `feature/2026-11-01@installer-service-integration` adds real service CI
  dependencies. Production native capability remains unavailable; no daemon,
  native build, Docker execution or hardware acceptance follows from API tests.
- SDK-free fixed FM6 diagnostic is pushed at `5add9c0d`, with eight voices,
  trunc12 and permanent external arenas. Actual pi32 link and unchanged audit
  pass: flash 210,364 bytes, BSS 300,240. Hardware admission remains false;
  bootguard, stack bounds, timing and general interactive runtime remain open.
- Stackless RAM execution witness is pushed at `fd0b33d6` and independently
  reviewed, with 72 tests passing. PA2 physical ownership, inherited ROM state,
  optical timing and watchdog/capture bounds remain unresolved. No execution
  or hardware admission has occurred.
- New sequencer/modulation fixes are in isolated lanes: offset-loop Capture,
  immutable queued lock targets, Acid Gen STOP/origin, Divide chronology,
  Compare crossings and transitive modulation dependencies in sound/FX saves.
  Application import rejection and state-load merge allocation are being fixed
  in the existing app-state lane. Keep file ownership separate.
- Buffered soak parser is being tightened to distinguish terminal failure
  reasons. Exact historical Oct29 source and raw receipt were checked: its
  line-370 failure follows successful finish/invariant guards and is consistent
  with the two allowed producer-late blocks. No evidence that accepted soak
  was falsely accepted has been found. New unrelated failures must not pass.
- Python state-reader byte limits and offline browser OTA transport/controller
  are separate lanes. Package admission stays closed, no MIDI/device traffic.

## Audit and resources

The full audit threshold was exceeded on main. Source partitions are being
read fully with pinned hashes and reports in the performance checkout's
`scratch/devkit-20261023/audit-20261101/`. Engine core/effects, app core,
browser source, sequencer/state, modulation/host, firmware/tools and engine C
checks are covered. Browser and Python test partitions are still being
reviewed; aggregate and changed-head reconciliation remain pending. Do not
claim a completed whole-repository audit or remove uncertain legacy guards.

Aeon has CPUs 0–15. Current heavy lanes use exclusive sets of four CPUs,
6 GiB, docker-batch.slice and owned lifecycle stages: app-state 12–15 and
render-state dependency closure 4–7. Ask the coordinator before another heavy
job; completed browser/matrix/WASM stages are removed. Mac coordinator alone
owns hardware. No hardware traffic has occurred on this resume.

## Next integration gates

1. Finish and independently review the current correction batch, rebuild
   actual WASM once for the combined source, run full host and browser gates.
2. Merge completed PRs only after exact-head CI/review and their applicable
   visual gates; use merge commits, preserve branch backups, verify main SHA.
3. Integrate the private service separately, retaining unavailable native and
   public-install gates. Continue the reviewed SDK-free runtime rather than
   merging the historical installer branch wholesale.
4. Resolve native boot/fail-open, RAM/stack, current interactive CPU1 backend,
   package/update/recovery and physical FM-1 acceptance before release.
5. Preserve owner listening and publication gates; tests are not a release.

## Persistence and cleanup

The release-readiness heartbeat remains ACTIVE until verified completion or
owner pause. Save exact source refs, useful logs and actionable handoffs;
remove owned reproducible stages. Keep worktrees until reviewed/integrated,
then remove through git without force. Never clean owner or sibling data.
Latest Mac free space is over 1,120 GiB, above the 500 GiB floor. The loopback
preview noted above is the only coordinator-owned live local server.

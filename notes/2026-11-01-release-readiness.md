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
pushed at `e80ac1788d2968e9779577a7a7d66aa13c2a37c5`. PR #161 is open.
Exact CI 41300110158 at the earlier `6606c1d0` head succeeded. Reviewed
service PR #162, native foundation PR #163 and OTA transport PR #164 then
passed their own exact-head CI and merged into this foundation. The new
combined head still requires its own CI and visual review.
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

PR #151 merged after its separately reviewed `ca6f3c14` passed exact-head CI
41296941683. Remote main is verified at
`8d790e3060643ab4e4f8404a7dbf52505ec9b303`. Foundation and corrections
include that merge. Preserve action() when integrating browser fixes.

## Latest combined candidate checkpoint

[verified] Corrections PR #165 contains the foundation above and reviewed
source through `7843ede8ab6496c71f0ab55f8925026793cdda5b`, pushed with remote
SHA verified. This is an integration candidate, not a release or deployment.
The final combined WASM rebuild and exact-head CI remain outstanding.

- CI 41302493347 exposed a GCC scene-decode warning, stopped-ARP fixture
  duration and RAM-edge fixture failures. Reviewed corrections gate launch on
  successful scene decoding, let the fixture finish all six swing intervals
  and note releases, and remove an unused Ensemble from a chain that exceeded
  RAM by 612 bytes. The original oversized-chain refusal remains covered;
  production RAM limits and ARP behavior are unchanged.
- WebKit can lose a transport click when unchanged label text is replaced
  between pointer down and up. Preserving the existing label node fixes the
  actual-app reproduction. A held-press regression fails on the old source
  and passes all three browsers; it crosses a real transport update and
  retains the original timeout. This is not the pending real-Chrome review.
- The reviewed build wrapper isolates remote stages and claims each canonical
  output directory, including aliases. Independent actual-wrapper fake tests
  cover concurrency and partial-claim cleanup. All eight cases also pass in
  the combined checkout. Real LAN acceptance will use the next combined build.
- Explicit aligned state workspaces preserve host behavior; normal and Clang
  sanitizer comparisons pass in four configurations. Actual pi32 object
  evidence removes a 917,536-byte default arena in native external-workspace
  mode. The 481,244-byte JSON writer still cannot fit the native headroom:
  full native persistence requires further work, not a larger memory budget.
- The shared renderer protocol is extracted behind explicit platform ports;
  existing SDK wake behavior is preserved. Independent and coordinator
  protocol/fault checks pass. Native CPU1 launch remains disabled.

[verified] One deeper Capture issue remains open: a first take can construct
a loop beyond the format's 256-step addressable window, drop notes and fail to
roundtrip unchanged. The original Movy compatibility witness is retained.
A separate native transactional-refusal correction is being prepared; valid
Capture growth must remain intact. Do not turn this into an unlabelled skip
or claim the combined candidate is green.

Private authoritative continuation state is
`scratch/release-coordinator-checkpoint-20261101.md`, atomically mirrored to
the owned Aeon coordinator dataset. Detailed failure logs and lane receipts
stay private. No hardware operation or public service was started.

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
- Rejected sequencer imports preserve app/PCM state; merged clip text stays
  allocated through application, avoiding a fallible allocation after mutation.
- Queued locks carry immutable target labels and base values through app dispatch.
  Focused checks pass 10 normal and 9 sanitizer tests; both pipeline variants
  pass three-way 22,581,248-byte PCM comparisons and seven fault refusals.
  Two static event arrays grow by 13,056 bytes; aggregate target fit is unproven.
- Offset-loop Capture, two-edge Compare crossings, Acid STOP/origin ownership,
  Divide output chronology and transitive sound/FX save dependencies are fixed.
- Typed buffered-soak terminal reasons reject unrelated failures; Python state
  readers enforce byte limits. Browser negative witnesses reject nonfinite PCM
  and missing required controls rather than silently accepting incomplete checks.
- Dongle LED indication follows ACK release/SOF and final PC handoff, removing
  a 300 ms delay from that critical path. Sixteen model/source tests pass;
  physical dongle timing is not established by those checks.

A combined full WASM rebuild is required after the current source-fix batch;
individual host proofs do not make the old generated module current.
Do not hand-edit generated acceptance hashes.

## Other active lanes and dependencies

- Private installer service extraction is independently approved at
  `d62044bc`. Dedicated integration branch
  `feature/2026-11-01@installer-service-integration` adds real service CI
  dependencies. Draft PR #162 is pushed at `9601311b`; CI 41300128269 is
  pending after incorporating the reviewed WebKit fix. Production native capability remains unavailable; no daemon,
  native build, Docker execution or hardware acceptance follows from API tests.
- SDK-free fixed FM6 diagnostic is pushed at `5add9c0d`, with eight voices,
  trunc12 and permanent external arenas. Actual pi32 link and unchanged audit
  pass: flash 210,364 bytes, BSS 300,240. Hardware admission remains false;
  bootguard, stack bounds, timing and general interactive runtime remain open.
- Stackless RAM execution witness is pushed at `fd0b33d6` and independently
  reviewed, with 72 tests passing. PA2 physical ownership, inherited ROM state,
  optical timing and watchdog/capture bounds remain unresolved. No execution
  or hardware admission has occurred.
- Draft native foundation PR #163 is pushed at `9440b081`; reviewed binding
  source `f736bf4b` binds the toolchain tree to the pinned archive. Independent
  checks pass 24 focused plus six additional synthetic cases; combined checks
  pass 95 with one optional retained-output skip. CI 41300396882 is pending.
  Actual archive compatibility/native build and all hardware gates remain open.
- A platform-independent extraction of the existing MIT queue protocol is now
  assigned for implementation with atomic host-adapter and directed fault tests.
  No reviewed SDK-free CPU1 launcher was found. A shim alone cannot admit live
  editing or make the fixed-arrangement pipeline a general interactive runtime.
- Buffered soak parser now distinguishes terminal failure
  reasons. Exact historical Oct29 source and raw receipt were checked: its
  line-370 failure follows successful finish/invariant guards and is consistent
  with the two allowed producer-late blocks. No evidence that accepted soak
  was falsely accepted has been found. New unrelated failures must not pass.
- Offline browser OTA transport/controller review found a truncated chunk-length
  encoding at full-size chunks; correction and independent re-review are pending.
  Package admission stays closed. No MIDI/device traffic has occurred.

## Audit and resources

The full audit threshold was exceeded on main. Source partitions are being
read fully with pinned hashes and reports in the performance checkout's
`scratch/devkit-20261023/audit-20261101/`. Engine core/effects, app core,
browser source, sequencer/state, modulation/host, firmware/tools and engine C
checks are covered. Browser and Python test partitions have returned reports;
aggregate and changed-head reconciliation remain pending. Do not
claim a completed whole-repository audit or remove uncertain legacy guards.

Aeon has CPUs 0–15. Current heavy lanes use exclusive sets of four CPUs,
6 GiB, docker-batch.slice and owned lifecycle stages: combined WASM reserves
0–3; queue extraction may use 4–7. App-state 12–15 is released. Ask the coordinator before another heavy
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

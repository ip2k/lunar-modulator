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

## Integrated foundation and active lanes

[verified] Integration branch `feature/2026-11-01@milestone-integration` is
pushed at `1294fc54cc8f51ad82315bac6578838610ad4746`, with remote SHA
matching. Completed source lanes are queue-margin telemetry, current release
handoff, DX7 complete-bank export, browser MIDI realtime input, offline
customization UI/catalogue, and the strict shared build-request contract.
Independent reviews approved their source changes. No release PR or merge has
occurred for this foundation yet.

- The customization page exports a validated request; it does not install
  firmware or claim a resource fit. Historical twelve-voice allocator estimates
  no longer gate the current eight-voice runtime. Generated catalogue deployment
  and contract tests are included in CI.
- Complete 32-slot DX7 banks use the core VMEM exporter. Partial banks visibly
  refuse rather than inventing missing voices.
- MIDI realtime input preserves message order, Link gating and saved project
  generation. The first integrated build passed 108 parity scenarios, 19 SysEx
  tests and five routing tests, then exposed an inaudible test fixture. Selecting
  its engine before sequencer reset and waiting for the first tick corrected
  the fixture; sustained sound and Stop silence assertions were strengthened.
  Actual rebuilt WASM passes all four runtime groups. Full build remains pending.
- Private installer API/service extraction is active in isolated
  `lunar-installer-service-20261101`, branch
  `feature/2026-11-01@installer-service`. It reuses the existing unmerged service,
  consumes the shared request contract and keeps public installation disabled.
  Production native build assets and physical acceptance remain separate gates.
- Astra's source audit is preparing the smallest observable RAM-only FM-1
  experiment. Existing flash application startup is not a RAM-only payload.
  No device operation is authorized merely by a source review or run receipt.
- Optional V226 algorithm1 state proof passed normal and sanitizer runs against
  both msfa and trunc12 main baselines. It is twelve-voice stretch research,
  not required for the eight-voice release and not a target timing result.

Workers use isolated worktrees, explicit pushed refs and exact SHA checks.
Mac coordinator alone owns hardware. Aeon CPU0–3 runs the full integration
WASM build in stage `release-integration-r2-20261101`, limited to four CPUs and
6 GiB; service tests may use CPU4–7. Hera was unreachable on resume; no power
or infrastructure changes were made.

## Immediate next dependencies

1. Complete the full integrated WASM build from exact source `1294fc54`,
   including metadata, edit storm and generated record. Return generated
   artifacts only after all gates pass; never hand-edit acceptance hashes.
2. Review the final CI/Pages/source-hash integration, then open a foundation
   PR and require exact-head CI and review before its merge commit.
3. Finish and independently review the extracted private installer service,
   then bind its results to the same canonical customization request.
4. Real-Chrome visual/interaction review is pending: the owner approved the
   chrome-browser skill, but local browser access is disabled in Work settings.
   Owner has been directly prompted to enable it or leave that gate pending.
   Loopback preview is running at `http://127.0.0.1:8767/installer.html` from
   this checkout, owned exec session 63121. Stop it after review or before pause.
5. Review the fresh RAM-readiness plan before preparing any physical FM-1
   experiment. No hardware traffic has occurred on this resume. Do not replay
   historical reset receipts or installer/hardware commands.

## Persistence and cleanup

Automation `continue-lunar-dev-board-audio-performance` is ACTIVE again, named
"Continue Lunar release readiness"; it reads this file and reports meaningful
milestones or blockers only. Save lane handoffs, small reports and receipts;
remove owned reproducible build/test artifacts. Retain worktrees until reviewed
and integrated, then remove them through git. Do not clean another session's
files. Built-in disk free space at latest checkpoint: 1,122 GiB (floor 500 GiB).
Build staging and temporary module copies from the failed build were removed;
small reports/logs are retained. Lane worktrees remain until integration.
The loopback preview above is the only coordinator-owned live local server.

# Demo-song readiness ledger — 2026-10-10

Read-only reconciliation of the existing audit, song brief, current `origin/main`
and combined effects candidate PR #140. No source, example asset, browser profile
or device was changed. PR #140 was open at `5d9fa46f2ae27f12d26c472813b1f4b0d3716b0c`
when checked; all 14 checks were queued or running, so its evidence is candidate
evidence, not merged-main evidence.

## Song contract and current coverage

The project schema already supports four sound slots, two master-effect slots,
modulation, DX7 voices, a sequencer set, and a panel session/view. The sequencer
supports eight tracks, named scenes, an ordered song chain and manual scene
takeover. These are sufficient for the four-song brief; no new project schema
or playback API is currently justified. When the four assets are added, bundle
the small test-fixture generalization in `tests/test_state_schema.py`: its
authority-example filename assertion hardcodes every project to
`first-orbit.lunar`. Permit descriptive project stems while retaining the
existing kind-specific `.sound`, `.fx`, `.rack` and other suffix checks. At
the same time, update that module's docstring, which still says nothing reads
or writes these example files.

Existing checks establish useful pieces, not the final assets:

- `tests/test_seq_song.py::test_the_four_minute_song_plays_through_and_stops`
  checks a 116-bar chain, scene order, a definite stop and no hung notes;
  `test_the_four_minute_song_through_fm1_render` compares sequencer and renderer
  event logs for that test-sine fixture.
- `tests/test_state_whole.py` checks canonical project save/load/save and a
  six-second JSON/binary audio-equivalence case. The native renderer omits the
  panel session, so it cannot establish lossless browser panel-session
  persistence.
- `sim/web/test/files.mjs` exercises First Orbit loading, project/sound export,
  IndexedDB SAVE, failed-write unsaved reporting, autosave retry/restore, Recent
  and undo. Its whole-project byte-equality checks preserve the existing First
  Orbit `session`/`view` fields through link and autosave restore, but do not
  deliberately change those panel fields before save/reload; it also does not
  exercise the four future assets or manual scene takeover.
- `sim/web/test/scenarios.json` has a four-second First Orbit
  `project-load-play` parity leg. Extend this existing leg per new project to
  cover its whole chain; assert `load.ok`, result code and zero omitted/skipped
  content, not only process exit status. Existing song/parity evidence is not a
  full-song native/Wasm receipt.

After the assets exist, the acceptance gates are: canonical authority and served
copies byte-match; project schema/canonical roundtrip preserves the session;
the integrated registry admits each four-sound/effects combination without
refusals or omissions; native and actual Wasm render the entire arrangement and
tail with finite audio, bounded peaks, expected duration/events, no drops or
hung notes, and deterministic seeds; the browser completes load/play/stop,
save/reload and scene takeover in an isolated profile; then the full mix and
transitions receive human listening review. Exact PR #140 CI/Pages and normal
merge remain the gate for treating its candidate features as integrated.

## Audit disposition for composition

- PSX Verb interpolation's alternating-sample defect is corrected in candidate
  commit `0e897f1c`; candidate receipts report the fixed reference tests and
  108-scenario simulator matrix. It is not an outstanding song defect if that
  exact candidate clears CI and merges.
- X0X negative-exponent bit construction uses defined unsigned arithmetic in
  merged-main commit `815cd99f`; the old batch-137 audit paragraph is historical,
  not an unfixed defect.
- IndexedDB false durable-save, Picks redo/history and stale Search cable-target
  issues are integrated on main through PRs #103, #118 and #99. Audit
  remediation also fixes malformed sequencer-lane reads, non-finite modulation
  script integer conversions and Comet's hit-latched kit/drive selection.
- Confirmed robustness findings remain open and are not blanket-closed: Sophie
  phase wrapping can fail at 8 kHz for its 18 kHz frequency limit; Gate's
  510-frame cap falls below advertised 5 ms only above roughly 102 kHz; and
  Mutable `mi_fx` maps a NaN parameter to its minimum instead of its declared
  default. These affect unusual sample-rate or invalid/non-finite input paths,
  not ordinary finite authored projects rendered at the FM-1's ~44.1 kHz rate.
  Keep them in the audit backlog; they do not currently justify blocking song
  composition. Do not claim the full audit is closed.
- Firmware install, full-image restore, broken-app recovery and device audio
  remain separate hardware gates. They are not prerequisites to authoring and
  validating browser/native demo songs. The owner's reported Sound 2 switch
  crackle still requires the documented listening retest; automated checks do
  not resolve that report.

## Bounded First Orbit browser workflow plan

Purpose: confirm the existing panel-session/load/save path without running a
full CI suite, changing the user's stored project, or treating First Orbit as
one of the requested songs. Use the existing page and Playwright harness in an
isolated temporary browser context/profile; do not clear or reuse a normal
profile's IndexedDB/autosave. The current `sim/web/test/files.mjs` already
automates the persistence/error branches, so avoid rerunning the full browser
matrix while PR #140 CI is active.

1. Before launch, compare
   `engines/state/examples/first-orbit.lunar` with
   `sim/web/www/examples/first-orbit.lunar`; parse the project and record its
   `session`/`view` fields and canonical bytes.
2. Serve the current integrated `sim/web/www` from localhost as documented in
   `sim/web/README.md`, open it in the isolated browser context, explicitly load
   First Orbit, power on, start playback and verify transport/audio activity.
   Stop, then manually select another named scene and confirm takeover works.
3. Save a project download and confirm it is canonical, schema-valid and
   retains the expected panel `session`/`view`. Reopen that downloaded copy in a
   fresh isolated context and verify the same panel state and playable set.
4. In the original isolated context, exercise the panel SAVE action, confirm
   the saved project appears in that context's library/Recent, reload the page
   and confirm restore. Do not use the native renderer as evidence for panel
   session persistence.
5. Record browser/version, exact source checkout, screenshots or concise
   observable assertions, and distinguish this First Orbit smoke result from
   later per-song full-chain checks and the owner's Sound 2 listening report.

The browser workflow above is a proposed bounded check, not a run receipt.
While PR #140 checks are queued, only lightweight asset/hash/schema inspection
and review of existing test coverage are useful; avoid duplicating its build,
Wasm regeneration, full parity matrix or all-browser CI.

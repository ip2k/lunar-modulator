# Remaining work ledger — 2026-10-09

Initial reconciliation was against `origin/main` at `e76392b` (PR #104 merged).
The integration reconciliation at the end supersedes all earlier snapshots. This is a
prioritized status record, not a blanket closure of the audit. It does not
repeat the parent envelope-graph implementation.

## Initial snapshot evidence

- **Dead-code/full-code source review is complete; remediation is not.** `CLAUDE.md` records the 2026-10-08
  baseline `d7111a985d5d6262767d6af49ba26caf0e1b9453`: 501 first-party
  source/build files and 178,989 physical lines, with 225 vendored files /
  81,114 lines separately tiered. Coverage and exclusions are in
  `notes/2026-10-07-full-code-audit-coverage.md`; detailed findings and
  unimplemented candidates remain in `notes/2026-10-07-full-code-audit.md`.
  The next audit is due after about 10,000 added source lines. Do not restart
  a redundant audit from the older d781f07 baseline.
- **PR #100 is merged** at `3c7b6a0ad153eff2f80444af9b2830da2c280538`;
  check run `37890685197` passed all CI jobs. The previous sentence in
  `notes/2026-10-08-audit-remediation.md` saying the rebuilt commit still
  requires CI and instructing continuation on its old branch is stale.
- **PR #104 is merged** at `e76392b8a962e938e99ea4d13bdac2c7893822ba`.
  `notes/2026-10-09-linked-diagnostic.md` records an independently authored,
  SDK-free, linked pi32v2 diagnostic (200-byte flat image, 4,144-byte RAM
  reservation, zero link-audit failures/pending checks). It has not been run on
  the dev kit or FM-1; this advances the linked-diagnostic gate but is not
  runtime, audio, hardware, or install evidence.
- **PR #99** remains open/draft at
  `a0dc7c070a1e5158beb46fd7b837a62d4d03e21c`. It includes the four deferred
  §29 editor decisions and the stale
  Search cable-target identity guard. Its refreshed Wasm passed local
  `build-on-aeon.sh` checks, including editor-v1 99/99, page suites, 104
  parity scenarios and the long Chromium storm. Latest GitHub CI was queued at
  this snapshot. The captured WAV/live Safari A-B listening judgment remains
  pending; physical FM-1 touch/MIDI behavior is untested. The README claim
  review is recorded in `notes/2026-10-09-readme-claim-review.md` on that
  branch; none of it establishes hardware readiness.
- **PR #103** (`fix/2026-10-09@editor-save-durability`,
  `b6a6b58acbbe167eae2bcf7424aacf4c554b6220`) addresses the IndexedDB false-save
  P2: durable writes fail visibly instead of silently falling back to memory,
  failed saves retain dirty state, and retry remains possible. Focused
  Chromium storage-failure regressions passed locally. It has since merged as
  PR #103 into `main` at `ebc6690`; the fix is now part of the current baseline.
- **PR #102** recovery-status wording is open and needs current CI review. Its
  Chromium page suite failed the 30-second storm with two underruns reported
  as `0.02` by playbackStats. That field is in seconds, despite the test's
  `_ms` output suffix, so the reported duration is 20 ms, not 0.02 ms;
  the original CI job did not capture audio-service traces. The other reported matrix jobs passed. Do not call
  its PR checks green based
  only on the prior successful targeted tests. The staged recovery evidence
  remains bounded sector write/restore plus matching full-image comparisons;
  whole-image rewrite, recovery from a nonbooting app, and Lunar execution on
  the device remain unverified.

## Prioritized remaining work

1. **Close the open PR streams on evidence, without treating local checks as
   CI or hardware proof.** Use the final reconciliation below for merged/open
   status, then check each live head and its CI/review state before acting.
   Local source review, focused regressions and older-head CI cannot verify
   a newly integrated branch. Each remaining stream retains its own scope.
2. **Continue device bring-up safely.** PR #104's linked diagnostic is not
   executed on native hardware. Follow `notes/2026-10-08-device-bringup-plan.md`
   and `firmware/diagnostic/README.md`; follow the current staged recovery
   policy in `AGENTS.md` and docs/07 §4. Compare backups before erase/program,
   preserve stock boot/package safeguards, and evaluate each concrete image
   and recovery plan. A prior full-image restore is not a prerequisite for
   recovery entry, reads or prototype preparation. Do not infer runtime stack/audio
   capacity or recovery from a host link/map.
3. **Retain the audit remainder explicitly.** The full-code audit still has
   unresolved P3 candidates and state-validation findings. The targeted fixes
   in PR #100/#105 do not blanket-resolve them; track each finding against its
   original batch and evidence before closing it.
4. **Keep licensing/mobile choices as open decisions.** The SDK runtime
   recommendation is not an approved runtime/licence change. Preserve current
   GPL boundaries (`notes/2026-10-07-sdk-runtime-evaluation.md`). iPhone
   advanced editing remains deferred until installable firmware; no app, relay,
   BLE stack or hardware protocol is selected (`notes/2026-10-07-mobile-advanced-editor.md`).

## GitHub snapshot

This was the historical merged baseline `origin/main`
`e76392b8a962e938e99ea4d13bdac2c7893822ba` at initial reconciliation.
Open PR heads at reconciliation time: #99 `a0dc7c0`, #101 `a994088`, #102
`275f8b3`, #103 `b6a6b58`, #105 `ba7ab93`, #106 `18035e0`, #107 `e1201e9`,
and #108 `dcd5c67`. This status is deliberately point-in-time; verify GitHub
before integrating or reporting final CI state.

Live check snapshot (2026-10-09): PR #22's full check matrix passed, but the
branch is `DIRTY` against current main. PR #58 is also `DIRTY`; its editor and
engine checks passed, while `build the site and the manual` failed. PR #99's
current checks were pending, #101 and #103 had pending jobs, and #102's
Chromium storm still failed (the other completed browser jobs passed). Checks
for #105–108 were pending. These states can change after this note.

## Older documentation PRs: superseded work and remaining facts

- **PR #22 (`82f4235`) is superseded as a HANDOFF snapshot.** Current main's
  `HANDOFF.md` already contains the audit-remediation and 2026-10-07 hardware
  updates, current FM-1_092 identity, changed staged-recovery evidence, and
  updated reading order. PR #22 instead describes the 2026-10-05 state: no
  project flash/write, kit/updater merely on order, old object/test counts,
  old audit due point, and the prior dump/restore prerequisite. Its broad
  rewrite and historical claims should not be merged wholesale. Its
  `CHANGELOG.md` addition is a dated, unreleased summary but includes now
  obsolete facts (including “this project has flashed nothing” and the old
  recovery prerequisite); do not port it as written. No unique factual
  correction needs porting from #22.
- **PR #58 (`3629a35`) is mostly superseded, but three exact factual edits
  remain useful.** Its correction in `docs/02-stock-firmware.md` says V15
  (`FM-1_015`) ran on the owner's unit until FM-1+VA was installed and the
  unit identified as `FM-1_092`; current main still incorrectly says
  “Running on the owner's unit.” Its Movy correction distinguishes commit
  `5627d51` from the v0.31.0 tag `675054f`, and identifies `9190e79` as a
  later main commit rather than v0.34.0 tag `7539028`; current main's
  `docs/06` still uses the old tag/commit wording, although `docs/13` records
  the refutation. Its `manual/chapters/11-updating-and-recovery.md` wording
  accurately says the open dongle firmware is simulated but no board has
  been assembled or used; current manual still calls the “open design”
  complete and says no dongle has been used. If ported, that manual passage
  must also be reconciled with the later staged-recovery bench record and
  must not restore the old whole-image restore gate.
- The remainder of #58 is a dated 2026-10-05 fact sweep. Current main has
  since accumulated newer hardware, engine, sequencer, recovery and audit
  evidence, so do not transplant its counts, “on order” states, old gates,
  license framing or broad snapshot wholesale. The three corrections above
  are candidates for a small follow-up factual-docs change, not a reason to
  revive the conflicted branch. Current source pointers are
  `notes/2026-09-29-baudgirl-fm1va-and-pcb-photos.md` §4, `docs/13`'s Movy
  claims table, and `notes/2026-10-07-fm1-softkey-bench.md`.

PR #110 ports the three verified factual corrections in a focused branch and
records evidence in `notes/2026-10-09-factual-doc-corrections.md`; its CI and
review remain pending. The audit-remediation note also now reports the
`0.01` playbackStats value as 10 ms, not 0.01 ms.

## Product metadata and audit status corrections

The repository description was read back from GitHub as: “Lunar Modulator —
INTERGALACTIC MODULATION STATION. Open firmware for the M-VAVE FM-1: sound
engines, a sequencer and a playable browser simulator. Preview: Lunar has not
run on an FM-1 yet.” This accurately avoids claiming the project itself has
run on the device while describing the browser simulator.

The full-code/dead-code audit is not overdue: current `CLAUDE.md` records the
2026-10-08 baseline `d7111a9`, 501 first-party source/build files / 178,989
physical lines and a separately tiered vendor count. The audit notes still
retain unresolved P3 candidates; PR #100/#105 are targeted fixes, not blanket
closure. PR #104 is merged, but its SDK-free diagnostic has not been run on
native hardware.

## Live update — 2026-10-09, `origin/main` `ebc6690c7595469359336b145cf1d7c0b4fe333a`

This section supersedes the earlier point-in-time GitHub snapshot above.

- **Merged baseline and editor durability:** `origin/main` is still
  `ebc6690c7595469359336b145cf1d7c0b4fe333a`; PR #103 save durability is
  merged. PR #104's SDK-free linked diagnostic is also merged but still has not
  run on the dev kit or FM-1. Firmware runtime, native audio, and FM-1 behavior
  remain unverified.
- **Combined editor/envelope verification:** the owner reports the combined
  LAN browser run passed at PR #101 head
  `506b76459be4e96b83f487aa08f3c45ca2e8681d`. GitHub checks for PR #101 are
  still pending. The captured-WAV A/B comparison still needs a by-ear judgment;
  do not infer a listening pass from automated waveform/browser checks.
- **PR #108 stock inspector:** the independent review finding about false
  stock/no-op classification is resolved at `0a7407d81419f82481d4959946fca3278f1aa6e5`:
  `app.bin`, `cfg_tool.bin`, and `eq_cfg_hw.bin` are each byte-bound to the
  guarded reference, with repaired-CRC regressions. PR #110 records that
  bounded re-review at commit `0a2c8b8f13c064d7d4c8060301ae6439c259975f`.
  The independent synthetic suite passed 14 tests; one optional real-stock test
  was skipped because its private inputs were unavailable. PR #108 has since
  advanced to `2807f732481facc58d91bc7da604c463913af9eb`; its owner reports an
  added entry-placement guard and 100 focused checks including actual V15
  no-op validation. This is report-level evidence, not device execution or a
  review of that later change. PR #108 remains open with GitHub checks pending.
- **New bounded audit fixes:** PR #112 (`7e3c600`) rejects non-finite and
  oversized room-oracle rates/frame counts before conversion or allocation;
  capped-container evidence reports infinity/NaN, oversized inputs and a valid
  32-frame render covered by focused regressions. PR #113 (`d87c7cf`) emits
  ordered MID pulses when modulation crosses the whole band in a single tick;
  the bounded build/test reports 1,240,305 checks plus filter/fill/fuzz cases.
  PR #114 (`e954c03`) checks Movy oracle run-length arithmetic before replay;
  bounded debug/release regressions passed, maximum-frame CLI repros now fail
  safely, and 24 curated event logs/sets regenerated byte-identically. All
  three PRs are open; their GitHub checks were pending at this update. No
  device traffic was involved.
- **PR #110 and the older docs PRs:** PR #110 is open at
  `0a2c8b8f13c064d7d4c8060301ae6439c259975f`, currently dirty against main, and
  GitHub reports no checks for its branch. Its three factual ports cover the
  FM-1_015/FM-1_092 ownership chronology, Movy commit-versus-tag identity, and
  the simulated-but-unassembled recovery dongle; the evidence index is
  `notes/2026-10-09-factual-doc-corrections.md`, with the PR108 re-review in
  `notes/2026-10-09-pr108-review.md`. PR #22 remains a superseded HANDOFF
  snapshot (all its reported checks pass, but it is dirty against main). PR #58
  remains a superseded broad fact sweep (editor/engine checks pass, but its
  site/manual build failed; it is also dirty against main). No edits are needed
  on either old branch: #22 contains no unique current correction, and #58's
  only three still-useful claims are already ported in #110. The remaining
  question is review/integration of #110, not resurrection of #22/#58.
- **Still-open audit and product gates:** targeted fixes do not close the
  remaining P3 candidates or state-validation findings in
  `notes/2026-10-07-full-code-audit.md`; use
  `notes/2026-10-07-full-code-audit-coverage.md` for scope. The completed
  2026-10-08 dead-code audit/count remains the baseline in `CLAUDE.md`; no
  replacement audit is due absent another ~10,000 first-party source lines.
  The SDK runtime/licensing recommendation remains unapproved; preserve the
  existing GPL boundary and consult
  `notes/2026-10-07-sdk-runtime-evaluation.md`. The mobile advanced editor is
  still deferred until installable firmware; no native bridge, relay, BLE
  stack, or hardware protocol is selected; see
  `notes/2026-10-07-mobile-advanced-editor.md`.

## Checkpoint — PR rebase and current gate evidence (2026-10-09)

Both documentation branches are now rebased by merge onto the fetched
`origin/main` `ebc6690c7595469359336b145cf1d7c0b4fe333a`, with their focused
changes retained. PR #109 is at `bccf2c3df322883d10973e6e6a3cc4f711e084b3`;
its exact-head pull-request CI run `37986003488` is queued. PR #110 is at
`e8e818732bb79652dca45a48b9711f46637474b5`; exact-head pull-request CI
`37986034260` is queued and Pages run `37986034297` is in progress. A manual
CI/Pages dispatch was also started on that same exact PR #110 head
(`37986057082`, `37986060318`) before the automatic runs appeared; these are
duplicates, not stale-head checks. The old PR #109 run on
`ab706468be23f1a348cf4bc742b1b5cf0374cf03` and old PR #110 dispatch CI on
`0a2c8b8f13c064d7d4c8060301ae6439c259975f` were cancelled; old-head Pages
success does not validate the current head. Neither PR is merged.

[verified: current owner instructions] The earlier policy conflict is resolved:
the owner-supplied instructions and checked-out `AGENTS.md` / `CLAUDE.md`
agree on the 2026-10-07 staged policy. It supersedes the blanket full-image
restore prerequisite. The audit's documentation finding at report line 1012
must be checked against current text and later recovery-doc changes, rather
than treated as blocked on an unanswered policy decision. This ledger does
not authorize new hardware operations or claim full-image recovery is proven.

The remaining P2 list should be reconciled against the live source before new
implementation: #912 was addressed by PR #112; #920 by PR #114; editor save
reliability (#70) merged in PR #103; cable target identity (#173) is present on
PR #99 but is still subject to its integration/CI gate. Audit-specific P3s
remain explicitly open; targeted fixes do not imply blanket closure. The next
useful audit step is a source/status pass over the remaining P2s after those
branch outcomes settle, rather than rerunning the whole audit.

### Repeated-picks audit follow-up

The full audit's P2 for repeated “Make B from the picks” undo/redo mismatch
(batch 39, finding at `notes/2026-10-07-full-code-audit.md:156`) remains the
item tracked by open PR #118, not an unassigned implementation task. At the
reconciled baseline, main `project.js` still merges structural edits by the shared `ab:`
target while `redoPicks` reuses `entry.info.reload`; PR #99's source diff adds
the captured-cable identity check for stale Search batches, but does not change
this picks/history payload. A small regression can perform two same-scope picks
loads inside the history merge window, then assert undo restores the exact
pre-first state and redo restores the second selection. If assigned, fix the
history grouping/payload at the editor history boundary and test the history
semantics without needing hardware or a browser build. Review PR #118's
implementation and integration gate before duplicating that work.

## Integration reconciliation — 2026-10-09

[verified: GitHub and source] This branch incorporates `main` at
`32b321ff5674f5375e8a8ef1127150b8242909d3`. At this snapshot, PRs #99, #100,
#101, #103, #104, #106, #108, #111, #115, #119, #122 and #124 are merged.
PRs #102, #105, #107, #109, #110, #112–114, #116–118, #120, #121 and #123
remain open. Further foreground merges can change
this list; it is evidence at this named baseline, not a standing live status.
PR #117's updated head `a973087d3eab736e25b487ab8011f69d882fb6a1` preserves
panel-follow tests, external audio loopback/Pulse setup and scheduling capture;
its exact-head CI run `38023257104` and Pages run `38023257065` are queued.

[verified: source] The audit's batch-68 dead-import candidates have already
been removed: `Fraction` in `tools/lunar_state.py`, `GPL_MODS` in
`tests/test_app_state.py` / `tests/test_gpl_switch.py`, `Path` in
`tests/test_engine_acid_bass.py`, `rms` in `tests/test_engine_drums.py`,
`run_script` in `tests/test_seq_song.py`, and `pytest` in `tests/test_tools.py`.
A bounded Python AST check at this baseline finds no import binding or Name
node for those names in their respective files. The older audit is a baseline
record, not evidence that these candidates remain open.

[verified: source] Other optional dead-state candidates remain: the
`ShaperInstance.gain_db` field and its frame-local load/store in
`engines/src/fx_shaper.cc`, and Sophie's unwritten `error[96]` field plus
`sophie_error` / `get_error` callback in its vendored source. No removal is
made here; follow the original audit's behavior/provenance constraints before
changing them. These source checks do not close the other P3 defects,
state-validation findings or test gaps, and do not constitute a new full audit.

[verified: review] Direct diffs/source and Git merge results establish these
statuses. Shared Serena/Rarefaction selection was not changed. Their earlier
C fallback index returned an incorrect `int *` typedef expansion for
`ParseSysex` and omitted callers visible in `dx7_voice.cc` / `msfa_dx7.cc`;
those navigation results do not establish this worktree's index, target ABI,
firmware code generation or complete call graph. No hardware was used.

[verified: local validation] The reconciled documentation passes `git diff --check`;
all seven relative Markdown file links in the three changed documents resolve.
The merge adds no source changes beyond its named main baseline. Fresh exact-head
CI must still pass before integration; earlier green checks do not cover this merge.

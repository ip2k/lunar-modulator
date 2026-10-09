# Remaining work ledger — 2026-10-09

Reconciled with current `origin/main` at `e76392b` (PR #104 merged), open PRs,
tracked audit notes, and the editor/recovery branches. This is a prioritized
status record, not a blanket closure of the audit. It does not repeat the
parent envelope-graph implementation.

## Completed and current evidence

- **Dead-code/full-code audit is complete.** `CLAUDE.md` records the 2026-10-08
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
  §29 editor decisions, repeated-picks history correction, and the stale
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
  Chromium storage-failure regressions passed locally. PR is open; CI/review
  remain pending. This is not yet on main.
- **PR #102** recovery-status wording is open and needs current CI review. Its
  Chromium page suite failed the 30-second storm with two underruns reported
  as `0.02` by playbackStats. That field is in seconds, despite the test's
  `_ms` output suffix, so the reported duration is 20 ms (traced events were
  10–20 ms), not 0.02 ms; the other reported matrix jobs passed. Do not call
  its PR checks green based
  only on the prior successful targeted tests. The staged recovery evidence
  remains bounded sector write/restore plus matching full-image comparisons;
  whole-image rewrite, recovery from a nonbooting app, and Lunar execution on
  the device remain unverified.

## Prioritized remaining work

1. **Close the open PR streams on evidence, without treating local checks as
   CI or hardware proof.** PR #99 editor, PR #101 envelope graph, PR #102
   recovery-status docs, PR #103 save durability, PR #105 test-server path
   containment, PR #106 resampler CLI bounds, PR #107 verified stock-SPL
   handover docs, and PR #108 guarded offline stock-package inspection are
   open as of this snapshot. Check each live CI/review state before acting.
   PR #101's envelope work belongs to its owner stream; it is not duplicated
   in this ledger. PR #105's sibling traversal, outside-symlink escape and
   malformed-URL regressions reportedly pass the actual HTTP checks, but its
   CI is still running. PR #106–108 remain separate streams; inspect their
   evidence and CI before labeling complete.
2. **Continue device bring-up safely.** PR #104's linked diagnostic is not
   executed on native hardware. Follow `notes/2026-10-08-device-bringup-plan.md`
   and `firmware/diagnostic/README.md`; keep the dump/byte-identical-restore
   rule in `AGENTS.md` as the write gate. Do not infer runtime stack/audio
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

The merged baseline is `origin/main` `e76392b8a962e938e99ea4d13bdac2c7893822ba`.
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

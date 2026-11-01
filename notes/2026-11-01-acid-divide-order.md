# Acid Gen STOP/origin and Divide chronology

Personal, non-commercial Lunar release audit follow-up. Base:
`b831724fcf413720aaa036dac742a382cdfaa93c`. Branch:
`fix/2026-11-01@acid-divide-order`. No devices, MIDI, USB, flashing or resets.

[verified: source and focused runtime checks] Acid Gen did not handle STOP,
retained no key/output origins and read origin metadata as velocity on a
zero-velocity NOTE_ON. It now keeps live and sequencer instances of the same
held key separate, retains the last key's origin during explicit Latch,
marks Run output sequencer-owned, and preserves origin on slides and deferred
offs. STOP forgets sequencer keys and ends their active/latched generation at
the event's frame. Live held keys and live latch keep playing. The generator
remains one monophonic line; ending its final owning source also ends that
line's sounding slide, using each sounded note's recorded origin.

[verified: source and focused runtime checks] Divide used to process all input
edges before draining scheduled output. A later reset or Mult clock could
therefore erase a trigger earlier in the same tick. Output now drains strictly
before each input frame group. Same-frame input precedence, RESET-before-CLOCK,
future cancellation, RNG draws and the bounded output edge policy remain intact.

The renderer JSON MIDI log now masks velocity metadata. This corrects the
oracle when Acid Gen Run starts preserving its sequencer origin; it does not
change audio delivery or musical velocity. The existing Run oracle explicitly
checks velocities 72/118.

## Checks and limits

- RED before edits: focused public-API harnesses compiled the exact base source;
  seven of eleven cases fail (origin/STOP/deferred/zero-velocity and Divide
  earlier clock/reset, delayed output/reset and Mult restart). Preserved cases:
  live latch, same-key coexistence, future reset cancellation, coincident reset.
- GREEN: 11 focused cases with local Clang address/undefined-behavior sanitizers.
  GPL=0: 5 Divide cases pass, 6 Acid Gen cases skipped. Acid Gen remains GPL-gated.
- An initial Mult x4 assertion exceeded FM1_MOD_EDGES=4; corrected to x1 so the
  regression isolates chronology within the existing edge budget. The original
  broader multiplier oracle remains the acceptance check for x4/x16 behavior.
- Local Python 3.15 has no pytest; used the existing main checkout .venv Python.
- Rarefaction status: shared main checkout, C profile lacks compile database;
  scope rejects external worktree paths. Did not change shared root. Serena
  current config remains main; absolute worktree ag_process symbol navigation
  succeeded and matched source. Direct exact-worktree source/caller/test reads
  are the fallback. These tools do not verify pi32v2 ABI or firmware generation.
- LAN renderer and kinds oracles pending at this checkpoint; no hardware claim.

Evidence and cleanup: own worktree `scratch/acid-divide-order/` retains small
RED/GREEN logs. Reproducible binaries, baseline source copies and pytest temp
directories are removed after results are recorded. Aeon gets a unique stage,
CPU 8-11 / max 4 CPU / 6 GiB batch container with --rm, removed after logs return.
Keep the isolated worktree until parent review/integration; remove after merge.

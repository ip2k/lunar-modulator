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

Origins remain intact between MIDI-effect slots, so a downstream latched arp
can forget Acid Gen Run notes on Stop. The host already removes origin metadata
before sound output (`mfx_host.c`), so render.cc needs no change. The renderer
Run oracle explicitly checks MIDI velocities 72/118. Same-pitch slide ties keep
the sounded note's original owner and do not retrigger when the newest input
changes origin. STOP and RESET update Run state for subsequent ticks inside
the current block; the context describes transport at the block's beginning.

## Checks and limits

- RED before edits: focused public-API harnesses compiled the exact base source;
  seven of eleven cases fail (origin/STOP/deferred/zero-velocity and Divide
  earlier clock/reset, delayed output/reset and Mult restart). Preserved cases:
  live latch, same-key coexistence, future reset cancellation, coincident reset.
- GREEN: 13 focused cases with local Clang address/undefined-behavior sanitizers.
  GPL=0: 5 Divide cases pass, 8 Acid Gen cases skipped. Acid Gen remains GPL-gated.
- Two additional checkpoint regressions reproduced and fixed same-block Run
  STOP/RESET and cross-origin same-pitch ties.
- Aeon full existing Acid Gen oracle suite plus focused harnesses: 34 passed,
  1 skipped (uncloned upstream reference), 3.44 s after compilation. A new
  Acid Gen Run -> latched arp chain regression fails against the exact base
  Acid Gen and passes fixed, with no output after STOP and no hung notes.
- Existing modulation kinds oracle: 1,245,985 checks, 135 filter responses,
  16 kinds filled, 32 fuzzed, zero failures. Linux renderer/kinds build used
  existing lunar-asan:ubuntu-24.04 image, Clang/Clang++, -O2; focused harnesses
  explicitly used sanitizers. The image name alone is not sanitizer evidence.
- An initial Mult x4 assertion exceeded FM1_MOD_EDGES=4; corrected to x1 so the
  regression isolates chronology within the existing edge budget. The original
  broader multiplier oracle remains the acceptance check for x4/x16 behavior.
- Local Python 3.15 has no pytest; used the existing main checkout .venv Python.
- Rarefaction status: shared main checkout, C profile lacks compile database;
  scope rejects external worktree paths. Did not change shared root. Serena
  current config remains main; absolute worktree ag_process symbol navigation
  succeeded and matched source. Direct exact-worktree source/caller/test reads
  are the fallback. These tools do not verify pi32v2 ABI or firmware generation.
- LAN staging initially omitted the renderer fixture's mailbox header closure;
  after staging those three files, the checks passed. No hardware claim.

Evidence and cleanup: own worktree `scratch/acid-divide-order/` retains small
RED/GREEN logs. Reproducible binaries, baseline source copies and pytest temp
directories are removed after results are recorded. Aeon gets a unique stage,
CPU 8-11 / max 4 CPU / 6 GiB batch container with --rm. Its exact stage
`/home/claude/mvave-fm1/acid-divide-20261101-659a55c3` was removed after logs
returned. Existing container images were retained. Local built-in Data volume
had 1119 GiB available before this bounded run and 1121 GiB after cleanup.
Keep the isolated worktree until parent review/integration; remove after merge.

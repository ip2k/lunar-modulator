# Audited DSP boundary fixes — 2026-10-10

This focused branch corrects the Sophie phase-wrap, Mutable-derived effect
NaN-default, and Gate timing-documentation findings. It does not close the
full-code audit or establish hardware behavior.

## Changes and evidence

- Sophie’s pinned MIT source had a one-turn-only wrap at `sophie.c:87-91`,
  although its oscillator path permits up to 18 kHz and ratios through 17.8.
  This fails at ordinary 44,118 Hz host rate for oscillator settings above
  about 2.48 kHz at the largest ratio; at 8 kHz it fails above about 449 Hz.
  The correction preserves the original one-turn arithmetic as the common
  fast path, then uses bounded quotient reduction only if the phase remains
  outside the cycle. `UPSTREAM.md` records the local change and exact source
  hash `6a43cd14ca377e3ce9d0bf3e63e121a9f04146252bf21b8a5ccea2b09fc1e1b1`.
  The dedicated C regression compares 30,000 steps per rate, 60,000 total, at
  44,118 and 8,000 Hz across three ratios to a double-precision modulo oracle;
  it checks one-turn arithmetic and ±40-turn boundaries. The original source
  fails its multi-turn boundary check; current source passes.
- The Plate, Ensemble and Diffuse wrapper had a private clamp that mapped NaN
  to the minimum instead of the parameter default. It now uses the shared
  `fm1_param_clamp`. The regression renders all float parameters as NaN and
  compares the result with declared defaults. On the original production
  wrapper, the same check fails for all three effects; the bounded Linux
  renderer probe reported `NaN matches declared defaults=False` for each.
- Gate’s buffer remains capped at 510 frames. The manual now states the
  requested maximum is 5 ms, while the effective duration is `510 / rate`
  above 102 kHz (about 2.66 ms at 192 kHz). This is a documentation correction;
  the algorithm and memory budget did not change.

Focused validation passed on the corrected source on aeon in the documented
8 GiB / 8 CPU container: `tests/test_engines_schwung.py`,
`tests/test_engines_mi_fx.py`, and `tests/test_engines_gate.py` — 167 passed.
The Sophie C phase regression reported `60000` steps and passed. Root also
independently compiled and ran that C regression on macOS: pass, with two
pre-existing vendor warnings. `git diff --check` passed before this note was
added.

The bounded aeon simulator build produced 108/108 passing parity scenarios,
108 identical-to-JS and 108 identical-to-musl results; 105 were identical to
glibc, with one exact scenario differing by at most one LSB. Wasm SHA-256 is
`4667498f919529ba0f1059f127ea02e60c2c2a76ee5bc16983cfeabbb96b76ec`
(1,561,532 bytes). Its record hashes match the current working sources:
engines `85ef296b6c95a666389312314c3e08450a493a0ba93defa16a672f3eafa51e7d`,
simulator `4d861adaacdcbd3454fb125fd4c5d19330aa1223d47959a65148020a85fe4377`.
The build’s 30-second edit storm recorded 10,341 quanta, zero late quanta and
no resyncs. The build used `--no-screenshot`; it is not browser-page evidence.

## Current readiness boundary

The current main is `40c94300428acfc5688a203c2c928723ed98270a`: PR #140 and PR
#118 are merged, and the picks undo/redo fix is on main. This branch’s three
changes and regenerated Wasm are not yet on main. PR #141 remains open; at the
time of this note its exact head `9ecd5ad2373ad0bd15106f31a44f50d68bc9c28e`
had a completed Chromium page-test failure and an ASan/UBSan job still
running. That failed check remains recorded; it is not waived by this focused
branch.

The correction addresses real behavior for selectable effects, but it does
not create or validate the four requested songs. Song acceptance still needs
the integrated main candidate, complete authority/library assets, actual
admission and full-chain native/Wasm renders, browser load/play/stop/save/
reload and scene-takeover checks, and listening. Owner listening and any
hardware execution are distinct evidence. Tool-only oracle CLI bounds, other
state-validation and audit-removal findings remain open and are not automatic
song blockers; this note claims no blanket audit closure.

The repository’s Rarefaction/Serena semantic-selection workflow was not used:
the configured project roots were not verified for this isolated worktree, and
changing an agent-global shared semantic project would disturb other active
work. Source, callers and tests were inspected directly instead. No device
traffic, MMIO, flashing, or installation occurred.

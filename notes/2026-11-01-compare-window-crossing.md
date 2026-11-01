# Compare Window crossings within one tick

Personal Lunar Modulator work. Baseline:
`b831724fcf413720aaa036dac742a382cdfaa93c`; modulation-host audit finding 4.
Only Compare source, focused tests and this note changed. [verified]

## Behavior and fix

The old Window gate inspected only endpoint magnitude, missing complete
outside-to-outside traversal and choosing an entry boundary from the endpoint
sign. A direct public-kind-ABI probe reproduced both defects. Ten initial
regression cases failed and three closed-band controls passed on baseline.
[verified]

The Window path now picks the entry boundary from the starting side and can
emit entry then exit during one tick. A local helper publishes each Gate,
Not and Rise/Fall trigger together. Width <= Hyst/2 still has no open entry
band; strict boundary comparisons, existing interpolation/truncation/clamping,
trigger duration and the separate Above/Mid/Below logic remain intact.
[verified]

Width=.25/Hyst=0, -.5 to +.5 now emits Gate high at frame 8 and low at frame
24; reverse traversal matches. -.5 to +.125 enters at frame 12. With Hyst=.25,
full traversal enters at 12 and exits at 28. [verified]

## Verification

- Focused `tests/test_mod_compare_window.py`: **15 passed**, compiling the
  actual Compare translation unit with ASan/UBSan, `-O2 -ffp-contract=off`.
  Tests check both directions, opposite-sign partial entry, hysteresis,
  Gate/Not/Rise/Fall exact frames, Above/Mid/Below exact frames, equality,
  closed entry bands and matching trigger falls on the following tick.
  Initial pre-fix run had 10 failed/3 passed; next-tick cases were added
  after that reproduction. [verified]
- Existing `fm1-mod-kinds-test`: **1,245,985 checks, failed=0**, 135 filter
  responses, 16 filled kinds and 32 fuzzed-kind runs. Built single-threaded
  in this lane's scratch folder, without the engine bank. [verified]
- A bounded ASan/UBSan differential compiled the baseline descriptor under
  another name and the changed descriptor side by side: **340,000 exact
  port/tick comparisons** passed. Randomized parameters covered 20,000 ticks
  per mode: all seven ports in A>B/Trend and Above/Mid/Below in every mode,
  comparing float outputs and full gate records. This establishes unaffected
  behavior within that sample; it does not claim new Window output equals
  the defective baseline. [verified]
- `git diff --check` passed. No device operations, hardware/perceptual tests,
  PR or merge. Full application/browser CI remains coordinator integration
  work; this hashed-source change requires the full WASM batch rebuild.
  [verified]

Reproduction commands:

```sh
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest -q tests/test_mod_compare_window.py
make -C engines -j1 BUILD="$PWD/scratch/compare-window-crossing/kinds-build" "$PWD/scratch/compare-window-crossing/kinds-build/fm1-mod-kinds-test"
scratch/compare-window-crossing/kinds-build/fm1-mod-kinds-test
```

## Tools and lifecycle

Rarefaction status/orient/scope and Serena config/find_symbol were checked
without switching shared Serena. Both still select the primary checkout
`/Users/likwid/Developer/mvave-fm1-firmware`, not this external worktree.
Serena found the matching Compare source range. Rarefaction found the body
and crossing/gate callees but misrepresented the io type with fallback flags
and found no callback callers; explicit source inspection verified registry
and runtime dispatch. No semantic completeness or target-ABI claim. [verified]

Worktree: `/Users/likwid/.codex/worktrees/lunar-compare-window-20261101`.
Branch: `fix/2026-11-01@compare-window-crossing`. Small private logs and the
local differential source remain in ignored `scratch/compare-window-crossing`.
Probe executables/source copies and the 820 KiB kinds build are removed after
results are saved; own pytest/Python caches are removed too. Data volume:
1120 GiB free at final check, above 500 GiB. Coordinator should review/integrate
the pushed commit, run required CI/WASM checks, and remove this worktree after
integration. [verified]

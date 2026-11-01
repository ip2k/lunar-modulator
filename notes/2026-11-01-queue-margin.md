# Playback queue-margin telemetry — 2026-11-01

Outcome: implemented offline; ready for coordinator review/integration. [verified]
Personal, non-commercial Lunar work. No device, USB, MIDI, flash, reset or
native image installation commands were run. [verified]

## Source and interpretation

Base: `a1b7823ba768d7657474f9be432d7584998b1501`.
Branch: `feature/2026-11-01@queue-margin`.
Checkout: `/Users/likwid/.codex/worktrees/lunar-queue-margin-20261101`.
The dirty primary and the performance checkout were left untouched. [verified]

`firmware/devkit/renderer_pipeline_dac.c` now emits
`ready_running_min` and `ready_running_samples` in the existing end receipt.
The observer runs at the existing music-only pre-acquire sampling point, after
preroll and completed-output checks. It samples the new fields only while
`produced < TOTAL`; the completed-producer count is volatile for CPU0 task/IRQ
visibility. The original `ready_min` still samples every music output acquire,
including the terminal output drain, with its existing initialization. [verified]

The running value counts ready output slots before acquisition, including the
slot about to be consumed; it excludes the DMA ring. It is a sampled minimum,
not a continuous queue low-water mark. A zero sample count means no running
measurement: the raw minimum remains zero, and the parser reports null derived
running minimum/milliseconds. An actual observed empty running queue has min=0
with a positive sample count. [verified]

`tools/devkit_pipeline_result.py` adds `running_samples`,
`running_min_ready_slots` and `running_min_margin_ms` to `buffered.queue_latency`
only when the new paired fields and queue geometry are available. It validates
partial/invalid new fields. Legacy receipt summaries, original min fields and
release verdicts stay unchanged. No DSP, queue protocol or worst-stage recorder
logic changed. [verified]

## Validation

59 targeted checks passed with the existing primary project's Python 3.13 venv:

```
PYTHONDONTWRITEBYTECODE=1 /Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python \
  -m pytest -q tests/test_devkit_pipeline_worst.py \
  --basetemp=scratch/queue-margin-tests -p no:cacheprovider
```

Includes real C observer execution normally and with ASan/UBSan; drain-only,
last live producer block, complete/draining, genuine empty queue, and no-sample
cases; parser old/new receipt compatibility, new-field validation, no-sample
null values, SDK timestamped split-line continuation; and the existing four DAC
driver syntax policies, recorder and buffered-rule tests. `git diff --check`
passed. [verified]

Initial attempts found system Python 3.15 lacks pytest and the worktree scratch
parent did not yet exist; rerunning with the existing venv and explicit scratch
parent passed. No packages were installed. [verified]

No target build, hardware run, overhead timing or audio acceptance was performed.
The observer adds bounded work per sampled music block (two stored counters;
no allocation or logging in the IRQ); its target timing cost remains unmeasured.
A new run is needed to establish actual playback margin. [verified]

## Code-intelligence coverage

Rarefaction status verified its absolute root as the primary checkout; C uses
fallback compilation flags without a root compilation database, and Python
advises explicit interpreter configuration. Orient/scope for C `ready_min`
found `copy_output`, `lunar_pipeline_dac_run` and `fill103`, confirmed against
actual source. Python `buffered_rule` orient/scope found its `parse` caller and
`pct` callee but missed tests. Scope's co-change files were checked narrowly.
Serena initial instructions/config verified the same primary absolute root;
find_symbol located C `copy_output` and Python `buffered_rule` at the actual
baseline locations. [verified]

Neither shared MCP root was switched to this outside-root worktree. Queries
were baseline navigation only; worktree edits and behavioral/syntax checks were
done directly. Neither tool proves JieLi ABI/code generation or target timing.
[verified]

## Lifecycle and next dependency

Test binaries/temp fixtures were confined to this worktree's
`scratch/queue-margin-tests` and removed in the runner's `finally` block.
No reproducible test outputs remain there. Mac data volume had 1,129 GiB free
at the validation checkpoint, above the 500 GB floor. [verified]

Coordinator: review the branch, run required CI and integrate with a merge
commit; no PR or merge was performed by this lane. Build/performance acceptance
and any later device run belong to the coordinator under the existing gates.
Keep the branch backup and remove this worktree after integration when no
process uses it. The commit and verified pushed SHA are in the parent exit
report; this note is part of that commit. [verified]

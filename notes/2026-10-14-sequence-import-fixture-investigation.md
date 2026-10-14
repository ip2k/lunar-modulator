# Sequence import fixture investigation: malformed event fields

Date: 2026-10-14
Worktree branch: `codex/2026-10-14-macos-flags-fixture`
Source commit during repro: `dc6894d978efcf1262ec3f5bfb184c6bfa4ce3f9`

## Repro captured before correcting the fixture

The deterministic `_max_project_set` input has 8 tracks, 8 clip descriptors per
track, and 24 note rows per clip: 1,536 rows total. It uses CP `1 1 0 0`,
valid locks and triggers, but the generated note tuple was incorrectly written
as `tick:pitch:gate:velocity:step`. The project format is
`tick:gate:pitch:velocity:step` (see `engines/seq/seq_persist.c` import and
export); therefore long gate values occupied the pitch field and were outside
the 0..127 pitch domain. Some gate values were also zero. The source ticks
`25 + 10*i` also reused step indices.

In that malformed run, the first simulator JSON export retained 82 note rows
from 1,536 input rows. The following simulator JSON import and SAVE export
produced a compact body with 66 note rows. The body measured 22,503 bytes and
had SHA-256
`808c753a13e77914f4d7c37ec12e1546d92412e9a05d1de9b522cbc80dd9462d`.

This was not evidence of a product event-loss bug: the fixture used the wrong
field order and repeated steps. The drop began before project JSON export, but
malformed input is not required to round-trip. The mistaken case is retained
here to prevent mistaking that experiment for a parser regression.

## Corrected fixture and verification

The fixture now writes `tick:gate:pitch:velocity:step`, chooses gates within
the 256-step clip, uses MIDI pitches 0..127 and velocities 1..127, and places
the 24 notes in each clip on distinct steps. CP is `1 1 0 0`. It asserts that
the first simulator JSON retains 1,536 notes, 1,536 locks and 256 triggers,
then compares every `cl`, `cp`, `lk`, and `tg` payload between the source,
initial JSON, and final native SAVE body, in addition to checking per-clip
totals.

The generated body was 34,263 bytes with SHA-256
`186fee2b92df805d18d1071640a14b37a4f963a76233fb86e095e69af13366c0`.
The focused two-geometry shard passed, including field-for-field event
comparisons and fixture completeness assertions. The full three-file focused
suite is being rerun after adding those comparisons; see the host-flags note
for its final result.

This corrected result resolves the apparent loss as test-fixture malformation;
it does not claim general lossless behavior for malformed input.

No production source or hardware is involved.

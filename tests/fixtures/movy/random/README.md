# Seeded random scripts with Movy's traces

Ten scripts from `tools/movy-oracle/gen_scripts.py --no-undo` and, gzipped,
what Movy's `seq-core` (schwung-movy by megadake, MIT, at `9190e79`) made of
them through the oracle on aeon: `<stem>.jsonl.gz` (events, block-start
frames), `<stem>.out.movy1.gz` (the set after the run) and
`oracle-summary.jsonl`. The scripts are ours. `tests/test_seq_oracle.py`
replays them through the C core in compat mode and checks events and set
line for line; in the FM-1 default mode it checks that they run to the end
under the checking build with every note closed.

They come from the differential run of 2026-10-01 (9,500 undo-free scripts,
all identical in compat). Each was picked, smallest trace first, because it
catches a mutant of the C core that the curated fixtures miss:

| Script | Generator options | Catches |
| --- | --- | --- |
| `rand-601-00353` | seed 601 (8 tracks, 44,118 Hz, 128-frame blocks) | pre-roll of 11 ticks instead of 12 |
| `rand-601-00377` | seed 601 | pad mute tested on the stored pitch, not the transposed one |
| `rand-601-00732` | seed 601 | pre-roll; scale accumulator, swing and record-anchor mutants too |
| `rand-602-00033` | seed 602, `--no-d5` | probability compared with `<=` |
| `rand-602-00098` | seed 602, `--no-d5` | pad mute on the stored pitch |
| `rand-603-00031` | seed 603, `--capture --tracks 4 --block 64` | pre-roll |
| `rand-603-00069` | seed 603, `--capture --tracks 4 --block 64` | pad mute on the stored pitch |
| `rand-603-00165` | seed 603, `--capture --tracks 4 --block 64` | probability `<=`; it also reaches Movy's D5 nudge panic (line 161), which compat reproduces |
| `rand-604-00035` | seed 604, `--no-d5 --rate 48000 --block 7` | RNG, gate order, scale accumulator and anchor mutants at 7-frame blocks |
| `rand-604-00159` | seed 604, `--no-d5 --rate 48000 --block 7` | probability `<=` |

Regenerate: `gen_scripts.py --seed <s> --count <n+1> --no-undo [options]
--out DIR`, keep `rand-<s>-<n>.verbs`, run `run-on-aeon.sh --movy1` on them
and `gzip -9 -n` the `.jsonl` and `.out.movy1` files.

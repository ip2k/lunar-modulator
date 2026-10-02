# Movy oracle fixtures

Golden traces generated from **Movy** ([schwung-movy](https://github.com/DimaDake/schwung-movy),
by megadake, MIT, "Copyright (c) 2026 megadake") at commit
`9190e79a2f461e71d2bf0a9fa77042011945021e`: its `seq-core` crate, unmodified,
driven through our scripts by the oracle in `tools/movy-oracle/` (docs/13
stage M3). They pin Movy's exact behaviour, which the C sequencer core
reproduces in compat mode. The scripts and `20-movy1-import.in.movy1` are
ours; no Movy source or data is copied here, only what its engine output.

Regenerate everything with `tools/movy-oracle/regen-fixtures.sh` (needs ssh
to aeon; Movy is built and run only in a container there). The formats are
specified in `tools/movy-oracle/README.md`;
`tests/test_movy_oracle_fixtures.py` checks that every file here follows
them, and `tests/test_seq_oracle.py` runs the C core against them.

| File | What |
| --- | --- |
| `<stem>.verbs` | The script: Movy `cmd` verbs at absolute frames |
| `<stem>.jsonl` | Movy's events. Every event's frame is its block's start, as in Movy and in compat mode |
| `<stem>.d1.jsonl` | For scripts marked `# D1 trace:`: the same events, each tick at its own frame inside the block (`--frames tick`), which the FM-1 default mode should produce for these scripts |
| `<stem>.out.movy1` | Movy's `persist::serialize` after the run. It lists all 16 of Movy's tracks; an FM-1 build compares the lines for its own |
| `<stem>.in.movy1` | A set loaded before block 0, as movy-dsp's `state` param |
| `oracle-summary.jsonl` | Per script: blocks run, events, the final master tick, and each panic Movy caught |
| `random/` | Seeded random scripts with Movy's traces, gzipped (below) |
| `movy-chains.movy1`, `schwung-tracks.movy1`, `device-set.movy1` | Not oracle output: three of Movy's own set fixtures, copied from schwung-movy at 9190e79 under its MIT licence (`LICENSE`, `UPSTREAM.md` beside them), which the C core loads and re-exports byte for byte (`tests/test_seq_core.py`) |

Runs are at 44,118 Hz in 128-frame blocks unless the header says otherwise,
on 4 tracks (8 in 02, 1 in 22, 2 in 23 and 24; 48 kHz in 64-frame blocks in
23 and 24).

| Fixture | docs/13 | What it pins |
| --- | --- | --- |
| `01-clock-tempo` | R1, R2 | F8 every fourth master tick, Start and Stop edges, tempo changes keeping the accumulator, clamping to 20-300 BPM, tick 0 one tick period after Play |
| `02-clock-rate48k-block7` | R1, R2 | The same clock at 48 kHz in 7-frame blocks, 300 BPM (100 frames a tick); track 7 |
| `03-notes-gates` | R3 c, R4 a-b, R10 | Chord gates leaving in swap_remove order, a same-pitch retrigger, mute flushing a track, a bar stop flushing a gate before step_tick, Stop flushing all |
| `04-locks-latch` | R8, R9 | The latch on an 8-step clip, change-only CCs, carry over the wrap, `abase` against `abaseq`, quiet and auditioned `aset`, an unassigned lane, freeing a lane, `aclr` |
| `05-locks-first-step` | D2, D6 | A step-0 lock after its note-on, after Play and after a bar launch; the outgoing clip's look-ahead lock before a launch; Stop leaving lanes at their last lock |
| `06-conditions` | R7 | A:B with invert, pitch rows before whole-step rows, a chord's shared decision, 4:7 on cycles 4, 11, 18, an impossible 5:3; Play while playing resetting cycles and sending no new Start |
| `07-probability` | R7 | The free-running xorshift64* across Stop and Play, a chord's shared roll, rolls only when the condition passes, `prob 0` consuming a roll |
| `08-quantise-swing` | R5, R6 | Off-grid notes under quantise 0, 50 and 100, swing 66 and 80, a swung note wrapping past the loop end, swing in real 16ths at 2X (steps 2 and 6) and none at 1/2 |
| `09-scale` | R3 f | Scales 2/1, 1/2, 3/4 and a change mid-run; slow clips starting a tick late; a note entered while playing queuing its slot; the accumulator kept over a bar launch |
| `10-loop-window` | R4 c, R13 | An offset window, a hidden-tail press refused, Double Loop, a window shrunk under the playhead; notes up to one length past the loop end playing folded back |
| `11-transpose-drum` | R7 | Clip transpose on emit and its clamp to 0, step entry storing pitch less transpose, a drum track ignoring transpose, pad mute and solo flushing gates, `etrn` |
| `12-launch-session` | R11 | Bar-quantised launches, an empty slot and `stoptrk` stopping at the bar, a launch from stopped restarting a track whose playing slot survived Stop |
| `13-scenes-song` | R11 | `song` and `songadd`: a repeated scene as one two-bar entry, arming a bar early, an empty scene ending the song in silence, Play restarting it |
| `14-record-countin` | R12, D3 | Count-in clicks, step 0 at master tick 383, a pre-roll note, swung anchors with a tie, a first take growing a bar, suppression until the wrap, playback of the take |
| `15-record-overdub` | R12, D4 | Punch-in, a last-half-step note growing the clip a bar, a note held over the wrap, a tail after Rec off, a first take queued to the bar with pre-roll |
| `16-edits` | R13 | Length caps at the next same-pitch note and the clip end, nudge limits, velocity clamps, `addp` joining footprints, `del` by range and pitch, `ltog` joining a chord, clearing a chord |
| `17-copy-paste` | R13 | Step copy with locks but not trig rows, paste replacing the span, whole-clip copy across tracks, duplicate, `clipdel` freeing a lane |
| `18-undo` | — | `usnap`, `ucommit` (kept and dropped), undo and redo with `uswap`, tempo in the snapshot, and the playhead wrapped below an offset window (a Movy defect) |
| `19-nudge-panic` | D5 | Movy's nudge panic, in an offset window and in a clip shortened under its notes, and the length cap collapsing a gate to 1 tick |
| `20-movy1-import` | R14 | Loading `20-movy1-import.in.movy1` (clamps, an unknown line, a legacy note, the saved length winning, a selection on an empty slot) and playing its song, pad solo, muted track, locks, rows and off-grid notes |
| `21-capture-optional` | §10 q5 | Capture while stopped (tempo search, candidate select) and while playing (bar phase kept, launch at the bar). Optional, as Capture is in the FM-1 port |
| `22-nudge-panic-order` | D5 | The panic's order, minimised from a random script: of three matched notes in insertion order, the one before the panicking note keeps the nudge and the one after it does not |
| `23-ext-clock-follow` | §6 clock in | MIDI clock in (`rt` lines): FA anchoring bar 0 while we play, following at 125 BPM, the tempo EMA through a slow-down and a speed-up, FA again restarting both transports, FC handing back to the internal clock at Move's tempo with Start re-sent on our next bar |
| `24-ext-clock-stale` | §6 clock in | Clock without FA (joined mid-song): our transport restarts at Move's next bar, follows, then goes stale 0.5 s after the last F8 and reverts to the internal clock |

Notes for the C core's tests:

- **19's and 22's panics.** Movy's `nudge` hits `clamp(lo, hi)` with
  `lo > hi` and panics; movy-dsp catches it and plays on. The notes before
  the offending one, in insertion order, keep the nudge, and the rest of that
  command is lost. Compat mode reproduces this by stopping the edit at the
  first note whose clamp fails (22 pins the order). `oracle-summary.jsonl`
  names the command lines.
- **18 is an expected failure** until undo is ported (docs/13 M4).
- **23 and 24's F8s fall on block starts** (every 960, 1024 or 896 frames at
  64-frame blocks, and a staleness point 24,000 frames after the last), so
  the oracle's frame-by-frame run, which attributes each event to its tick,
  fires at most one tick per frame and goes stale in the same block as the
  whole-block run.
- **21 is optional**, and Movy scores its tempo candidates in `f64`. Capture
  stamps input with the frame of the block it lands on, so its results also
  depend on the block size.
- **Track counts.** Movy has 16 tracks; the scripts only address the tracks
  their header declares, and no event names a higher one.

## random/

`rand-<seed>-<n>.verbs` from `tools/movy-oracle/gen_scripts.py --no-undo`
(undo is not ported yet), with Movy's traces gzipped: `<stem>.jsonl.gz`,
`<stem>.out.movy1.gz` and `oracle-summary.jsonl`. They were picked from the
differential run of 2026-10-01 so that each one kills a mutant of the C
core that the curated fixtures do not; `README.md` there lists them.

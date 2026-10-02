# Movy oracle (docs/13 stage M3)

A differential oracle for the FM-1 sequencer. It replays a timed script of
Movy's own `cmd` verbs through Movy's `seq-core`, driven the way Movy's
`movy-dsp` plugin drives it, and writes every output event as JSON Lines.
The C core (`fm1_seq`, docs/13 §6) must produce the same log in compat mode.

Movy is [schwung-movy](https://github.com/DimaDake/schwung-movy) by megadake,
MIT ("Copyright (c) 2026 megadake"). The oracle pins commit
`9190e79a2f461e71d2bf0a9fa77042011945021e` and uses `seq-core` unmodified.
No Movy source is committed here. Movy is cloned, built and run only inside a
Rust container on aeon (the owner approved this, docs/13 §10), never on the
Mac.

| File | What |
| --- | --- |
| `driver/` | The Rust driver, our code (MIT). `Cargo.toml` depends on `seq-core` by path, `../schwung-movy/engine/crates/seq-core`, which `run-on-aeon.sh` checks out beside it |
| `run-on-aeon.sh` | One command: syncs the driver to aeon, checks Movy out at the pinned commit (refusing a dirty tree), builds in `rust:1.98.1-bookworm` with no network, runs every `*.verbs` in a directory on all of aeon's CPUs and copies the logs back |
| `regen-fixtures.sh` | Regenerates `tests/fixtures/movy/` |
| `gen_scripts.py` | Seeded random scripts for the differential test |

## Running it

```bash
tools/movy-oracle/regen-fixtures.sh                     # the curated fixtures
python3 tools/movy-oracle/gen_scripts.py --seed 1 --count 1000 --out /tmp/rand
tools/movy-oracle/run-on-aeon.sh --movy1 /tmp/rand /tmp/rand-out
tools/movy-oracle/run-on-aeon.sh --clean                # delete the work directory on aeon
```

`run-on-aeon.sh [--frames block|tick] [--movy1] IN_DIR OUT_DIR` writes
`OUT_DIR/<stem>.jsonl` for each `IN_DIR/<stem>.verbs`, `<stem>.out.movy1`
with `--movy1`, `summary.jsonl` (one line per script: rate, block, tracks,
blocks run, events, final master tick, and every panic Movy caught) and
`errors.txt` if a script could not be run. It needs `ssh claude@192.168.1.25`
(override with `MOVY_ORACLE_HOST`); containers carry the labels
`project=mvave-fm1-firmware` and `session=movy-oracle-or-virtual-fm1`. The
work directory on aeon, `/home/claude/mvave-fm1/oracle`, holds the checkout
(35 MB) and the build; each job's files are deleted when it ends.

On aeon, `movy-oracle run SCRIPT.verbs [-o OUT] [--frames block|tick]
[--state SET.movy1] [--movy1-out FILE]` runs one script, and `batch` and
`files` run many.

`gen_scripts.py` writes `rand-<seed>-<nnnnn>.verbs`; the same seed and
options give the same scripts. Each one sets a few tracks up while stopped
(about 50 commands), starts the transport one of four ways (play, a launch,
a recording with its count-in, a song), then sends about 120 more commands
at random frames over 4 to 16 seconds
(toggles, chords, locks, conditions, probability, quantise, swing, scale,
transpose, loop windows, live recording and overdubs, launches, scenes and
songs, nudges, copy and paste, undo and redo, mutes and pad mutes, tempo
changes, stops and restarts) and ends with `stop`. It never sends `link` or
`minject`. `--capture` adds Capture phrases. `--no-d5` makes every script
either nudge or reshape clips, never both, with windows at step 0, so none
reaches Movy's nudge panic (below).

## The shared formats

Both the C core and the oracle use exactly these.

### Verb script (`*.verbs`)

UTF-8 text, one command per line: `@<absolute_frame> <verb and arguments>`,
the verb and arguments exactly as Movy's `command.rs` parses them. Blank
lines and lines starting with `#` are ignored. A header line
`#! rate=<Hz> block=<frames> tracks=<n>` sets the run (defaults 44118, 128,
8) and must come before the first command; no other keys exist.

- Commands are applied at the start of the first block whose start frame is
  at or after the command's frame, before that block is advanced, in file
  order. Each line is one Movy `cmd` batch.
- Frames never decrease. A command may not contain `;` (it would split
  Movy's batch) or start with `#` (Movy's resend tag).
- **The run ends with the block in which the last command is applied**: blocks
  `0 ..= ceil(last_frame / block)` are run. Scripts end with `stop`, so a
  run ends with every gate flushed.
- `tracks=<n>` is the FM-1 build's track count. Movy always has 16; a script
  addresses only tracks `0..n-1`, and the oracle fails a run that emits an
  event on a higher track.
- A `<stem>.in.movy1` beside a script is loaded before block 0, as movy-dsp's
  `state` param does (`persist::load`, then `dirty = false`).

### Event log (`*.jsonl`)

One object per output event, in emission order, with exactly these keys in
this order: `{"block", "frame", "tick", "kind", "track", "a", "b"}`. The
oracle writes them compact (no spaces); compare parsed objects.

| kind | track | a | b |
| --- | --- | --- | --- |
| `on` | 0-based | pitch | velocity |
| `off` | 0-based | pitch | null |
| `cc` | 0-based | 102 + lane (Movy's lock CC) | value |
| `click` | null | accent, 1 or 0 | null |
| `start`, `stop`, `clock` | null | null | null |

- `block`: the index of the block the event belongs to. A command's events
  belong to the block it is applied before.
- `frame`: in Movy and in compat mode, the block's start frame
  (`block × block size`) for every event, since Movy has no sample offsets.
  `--frames tick` instead gives each tick's events the frame inside the block
  where that tick fell, which is the FM-1 default mode's D1 offset
  `k − 1`; command events and a block's Start or Stop stay at its start.
- `tick`: Movy's `master_tick` **before** the `service_tick` that emitted the
  event, so the first tick after Play is tick 0: its F8, its click, the bar
  resolution, gate flushes and every `step_tick` event of that master tick,
  including those after Movy's `master_tick += 1`. Events emitted outside a
  tick (a command's, a Start or Stop at a block's start) carry the number of
  ticks serviced so far. The count restarts at 0 on Play, a launch from
  stopped, and a Capture while stopped.

Within a block, a command's events come first, then the block's: Start or
Stop, then per tick its F8, then `service_tick`'s output. That is
movy-dsp's order: `set_param("cmd")` leaves its events in the instance's
`out` buffer, and `render` appends `advance_block`'s and then drains it.

### Sets (`*.movy1`)

Movy's own text format (`persist.rs`). `<stem>.out.movy1` is
`persist::serialize` after the run. Movy writes a `tk` line for each of its
16 tracks; an FM-1 build compares the lines for its own tracks.

## How the driver drives Movy

It mirrors `engine/crates/movy-dsp/src/lib.rs` at the pinned commit:

- `Instance::new` builds `Engine::new(rate, DEFAULT_BPM_X100)`, 120.00 BPM.
- `set_param("cmd", line)` is `command::apply_batch`, one call per line.
- `render` is `advance_block(block)`, then the events are drained.
- Every movy-dsp entry point runs under `catch_unwind` and the instance plays
  on after a panic. The driver does the same for commands and lists each
  panic in the summary; the rest of that command line is lost, as on the
  device. A panic inside `advance_block` stops the run with an error
  instead: movy-dsp would drain that block's events a block late, and no
  script has reached one.
- The release profile has overflow checks off, as Movy's does, so integer
  overflow wraps.

`master_tick` is private. The driver reads it from `Engine::status()`
(`tick=`), and runs a second engine through the same script one frame per
`advance_block` call (at most one master tick can fire in one frame) to
attribute every event to its tick and frame. Every block, it checks that the
second engine produced exactly the whole-block run's events, and that both
agree on the tick count; any difference stops the run with an error. The
whole-block run is the one reported.

## Validation

Seeds 11-14, 4,300 random scripts, about 28 hours of audio and 3.2 million
events, ran on aeon in 48 s [verified 2026-10-01]: 2,000 default scripts, 1,500
with `--no-d5`, 500 with `--capture` at 4 tracks and 64-frame blocks, and 300
with `--no-d5` at 48 kHz in 7-frame blocks. No run failed, so the
whole-block and frame-by-frame runs agreed on every block. 59 commands
panicked, all `enudge` at `clip.rs:674` (D5), 47 of the 2,000 default
scripts and 10 of the 500 Capture ones; none with `--no-d5`.

## What running Movy showed against docs/13

Each item names the fixture that pins it. Marks as in CLAUDE.md.

1. **D5 is wider than an offset window** [verified: fixture 19, random runs].
   `nudge` panics whenever a matched note's anchor is two or more steps past
   the clip's `length_ticks`, which also happens with `loop_start` 0 after
   `clen` or `loop` shortens a clip under its notes. In an offset window a
   +1 nudge on the window's first step moves the note *back* to
   `length_ticks − 1`, outside the window, before any panic. After a panic
   the notes earlier in insertion order keep the nudge and the rest do not;
   compat mode can reproduce that exactly by stopping the edit at the first
   note whose clamp fails.
2. **Undo has the same length-for-end bug** [verified: fixture 18].
   `Engine::undo_restore` wraps each playhead with `pos %= length_ticks`
   (`engine.rs` 2531-2536). With `loop_start` > 0 the playhead lands
   below the window and plays the notes there until it reaches the loop end.
   docs/13 D5 lists only `clip.rs`; this belongs with it or as a D8.
3. **Notes past the loop end still play, folded back** [verified: fixture 10].
   R5's "if fire ≥ loop_end, subtract length once" applies to every note,
   not only to one quantised onto the loop end. After `clen` or `loop`
   shortens a window, a note up to one window length past the end plays at
   its tick less the length. Only notes before the window, or further past
   it, are silent. A candidate deviation: skip notes outside the window.
4. **Play while playing sends no new Start** [verified: fixture 06].
   `play()` resets the master tick to 0, but `emitting_clock` stays set, so
   no 0xFA goes out and F8 jumps from …, 84 back to 0. R2 and §3.3 say Play
   restarts; neither says a clock follower is left out of phase. A candidate
   deviation: Stop and Start (or a Song Position Pointer) on a restart.
5. **Tick 0 is one tick period after Play** [verified: fixtures 01, 02].
   The accumulator starts at 0 and a tick fires when it reaches the
   threshold, so step 0's notes and the first F8 come 229.8 frames after
   Play at 120 BPM and 44,118 Hz, in a later block than the Start. R1
   implies this; D1's formula gives frame 229 for tick 0. The C core must not
   fire tick 0 at the Play frame.
6. **A bar launch sends the outgoing clip's look-ahead lock first**
   [verified: fixture 05]. The old clip wraps at master tick N−1 and emits
   its step-0 locks one tick early as usual; at N the launch resets the
   carry and the new clip's step-0 locks follow its note-ons (D2). A launch
   therefore sends two values in two ticks, the first for a step that never
   plays. D2's fix alone leaves that first value; suppressing look-ahead on
   a track with a launch due at the bar removes it.
7. **Slow clips start late** [verified: fixture 09]. With `num < den`, the
   first `step_tick` runs when the accumulator first reaches `den`: master
   tick 1 for 1/2 and for 3/4, not tick 0.
8. **`aclr` does not free a lane the way R9 describes** [verified: reading
   `engine.rs` 2342-2351, fixture 04]. It unassigns the lane but keeps its
   base and carried value, unlike `free_unused_lanes` (base 0, carry −1). A
   lane labelled again resumes from the stale carry.
9. **A scene press is a song** [verified: `src/seq/song.ts`, `command.rs`].
   Movy has no scene-launch verb: the UI sends `song <s>` for the first scene
   of a Loop hold and `songadd <s>` for the rest, so a single scene is a
   one-entry song that repeats. docs/13 §4's scene launch maps to `song`.
10. **Recording details that hold as docs/13 says** [verified: fixtures 14,
    15]: D3 (step 0 at master tick 383, the click at 384), D4 (which repeats:
    a draft of fixture 15 with a second note in the last half-step of the
    grown two-bar clip grew it to three),
    the 12-tick pre-roll before a count-in's end and before a queued take's
    bar, swung anchors with ties to the later step, and a first take growing
    a bar at each loop end until Rec is turned off.
11. **Capture depends on the block size** [verified by reading `capture_push`].
    Live input is stamped with `frame_now`, which advances once per block,
    so a take's onsets, and the tempo the f64 search picks from them, are
    quantised to the host block. Fixture 21 uses 128-frame blocks.
12. **docs/13 §5's Rust sizes are right** [verified: `size_of` on x86-64 in
    the container]: `Note` 16 B, `Lock` 4 B, `Trig` 8 B. Also `Clip` 80 B and
    `Track` 352 B before their vectors, and `CapEvent` 24 B: Movy's Capture
    ring is 512 events, 12,288 B, plus a frozen copy of the take (up to
    another 12,288 B) while the tempo selector is open.

Confirmed as written: R1's clamping (`bpm 999999` and `bpm -5` clamp to 300
and 20 BPM), R3's bar order, R4's off-before-on retrigger and swap_remove
off order, R6's swing in real 16ths under scale (no swing at all at 1/2),
R7's condition vectors (4:7 plays cycles 4, 11, 18) and that `prob 0` still
consumes a roll, R8's latch, D2 after Play and after a launch, D6, R11's
launch from stopped restarting a track whose playing slot survived Stop,
R13's caps, R14's clamping and fallbacks on load.

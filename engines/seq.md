# engines/seq — the sequencer core (docs/13, stage M1)

A C99 sequencer that replays [Movy](https://github.com/DimaDake/schwung-movy)'s
`seq-core` (MIT, megadake) tick for tick, plus the FM-1 changes the owner
asked for (docs/13 §10): deviations D1–D7 on by default, 4–8 routed tracks,
about half of docs/13's 72 KiB, 7-bit locks behind one typedef, Capture as an
optional switch. Desktop only: nothing here runs on, or is sent to, any FM-1
or MIDI device. Pinned to Movy commit `9190e79`; what was read is listed in
[third_party/movy/UPSTREAM.md](third_party/movy/UPSTREAM.md).

```bash
make -C engines                                   # build/fm1-seq, build/fm1-seq-check, build/fm1-render
engines/build/fm1-seq --sizes                     # fm1_seq_size() for 1-16 tracks
engines/build/fm1-seq --cmd song.txt --log song.jsonl --state song.json
engines/build/fm1-render --engine macro --cmd song.txt --log-events song.jsonl --out song.wav
engines/build/fm1-render --engine macro --seq set.movy1 --seconds 8 --out set.wav
python -m pytest tests/test_seq*.py               # 200 tests
```

## Files

| Path | What |
| --- | --- |
| `include/fm1_seq.h` | The API of docs/13 §6: `fm1_seq_size/create/advance/apply/note_in/realtime_in/export_movy1/import_movy1`, the limits struct, typed commands, events, read-only getters, routing |
| `seq/seq_int.h` | The instance layout: no pointers, offsets into one block |
| `seq/seq_clip.c` | The pools and Movy's `Clip` methods (clip.rs); the fire-tick index |
| `seq/seq_engine.c` | Clock, transport, launches, scenes, song, recording, `step_tick`, the lock latch, external clock (engine.rs, clock.rs, track.rs) |
| `seq/seq_cmd.c` | The verb parser and dispatcher (command.rs) |
| `seq/seq_persist.c` | `movy1` export and import (persist.rs) |
| `seq/seq_capture.c` | Capture, the retroactive record (capture.rs and engine.rs's capture functions) |
| `host/seq_script.[ch]` | Desktop only: the timed verb-script reader and the JSON Lines event log, shared by the two tools |
| `host/seq_tool.c` | `fm1-seq`: runs the core alone and dumps state as JSON; `fm1-seq-check` is the same tool on a core built with `-DSQ_CHECK_INDEX` |
| `host/render.cc` | `fm1-render --cmd/--seq/--log-events/--compat/--tracks/--route` |
| `mk/seq.mk` | The build fragment |

## Design

**One block, no heap.** `fm1_seq_size(&limits)` gives the bytes;
`fm1_seq_create` builds the instance in caller memory (8-byte aligned,
contents irrelevant: the tests run with fills of 0, 0xA5 and 0xFF and get
identical output). The instance holds no pointers, only offsets, and orders
its fields so that 32- and 64-bit builds lay it out alike: the sizes below are
the same on this Mac (clang, 64-bit) and under GCC 12 with `-m32` [verified:
`fm1-seq --sizes` in a Docker container on aeon]. The core's objects import
no allocator and no stdio [verified: `nm -u`, tests/test_seq_core.py].

**Pools instead of `Vec`s (D7).** Notes, locks and trig rows each live in one
global pool. Every clip owns a packed slice of each, slices in clip order, so
a clip's items stay contiguous and in Movy's insertion order, which Movy's
scan order, `swap_remove` order and `movy1` output all depend on. Growing a
slice moves the items after it (a `memmove` of at most the pool); a `retain`
compacts in place and cuts once. Two extra clips per instance hold the step
clipboard (`cpy`/`pst`) and the clip clipboard. Movy's per-clip caps (512
notes, 1,024 locks, 1,024 trig rows) still apply on top.

| Item | Bytes | Movy (Rust, [inferred] from its field types) |
| --- | --- | --- |
| Note: tick, gate, step and two pass flags, cached fire tick, index entry, pitch, velocity | 12 | 16 |
| Lock: step, lane, value | 3 | 4 |
| Trig row: step, pitch or whole step, probability with the invert bit, A, B | 5 | 8 |
| Clip header: three slices, length, loop start, scale, transpose, quantise, flags | 20 | |
| Track: slots, playhead, cycle, scale accumulator, latch state, 8 lane bases and 23-character labels, routing; plus 16 bytes of pad mutes | 240 + 16 | |
| Gate (sounding note) | 6 | 8 |
| Capture event | 20 | 24 |

**The fire-tick index.** Movy recomputes every note's fire tick (R5, R6) on
every clip tick, which docs/13 §5 puts at up to 147 % of the FM-1's core at
the worst case. Here each note caches its fire tick, and each clip keeps its
note numbers sorted by (fire tick, insertion order), so `step_tick` binary
searches to the notes due and visits them in exactly Movy's order, consuming
the RNG identically. Any edit that can move a fire tick (a note, quantise,
scale, the loop window, swing) marks the clip's index stale; the next scan
rebuilds it with an in-place heapsort. `fm1-seq-check` traps if a scan ever
finds a cached fire tick that differs from Movy's formula or an unsorted
index; random scripts run through it (tests/test_seq_core.py), and removing
one invalidation makes them fail [verified, by mutation].

**Events.** `fm1_seq_ev_t` is 12 bytes: the master tick, the frame offset in
the block, kind, track, two arguments. At one frame the order is Movy's
emission order: gate note-offs, then (D2) the locks of a step starting there,
then note-ons, then the locks of the step the playhead enters.

**Commands.** `fm1_seq_cmd_t` is Movy's `cmd` op as a typed record: the verb
and up to 26 integer arguments parsed exactly as command.rs parses them (an
`i64` per token, an unparseable token absent), then clamped and truncated
exactly as Movy does (`as u16` in `loop`, `as i32` in the edit deltas,
wrapping adds as in Movy's release build). `fm1_seq_apply_text` is
`apply_batch`, `#<seq>` tags included. A UI builds the records directly; the
single-producer ring docs/13 §6 describes is stage M4's.

## Movy's rules, and where they live

| Rule (docs/13 §3.2) | Here | Tests |
| --- | --- | --- |
| R1 clock | `fm1_seq_advance` | clock.rs ×4, `test_no_drift_over_ten_thousand_steps` |
| R2 F8 and Start/Stop edges | `fm1_seq_advance` | `clock_emits_start_then_24ppqn_ticks` and two more |
| R3 `service_tick` | `service_tick` | launches, clicks, scale |
| R4 `step_tick` | `step_tick`, `scan_notes` | playback, mute, gates |
| R5, R6 fire tick, swing | `note_fire`, `sq_swing_delay` | quantise and swing table (11 cases) |
| R7 trig decision, RNG | `scan_notes`, `roll_pct` | conditions, probability, chords, truth table |
| R8 lock latch | `emit_automation` | four automation tests, the `effective_at` oracle |
| R9 lock edits, lane release | `seq_cmd.c`, `sq_free_unused_lanes` | command.rs automation tests |
| R10 transport | `sq_play`, `sq_stop` | play, stop, restart |
| R11 launch, scenes, song | `sq_launch_clip`, `sq_launch_scene`, `song_bar`, `song_try_arm` | launch, scene and song tests |
| R12 recording | `sq_toggle_record`, `commit_rec_note`, `expire_rec_tail` | recording, tail, pre-roll and punch-in tests |
| R13 edits | `seq_clip.c` | clip.rs and command.rs edit tests |
| R14 `movy1` | `seq_persist.c` | persist.rs tests, Movy's three fixtures byte-identical |

## The deviations (docs/13 §3.3)

All on by default; `limits.compat = 1` (`--compat`) turns every one off.

| # | Movy at 9190e79 | FM-1 default | Test |
| --- | --- | --- | --- |
| D1 | A block's events all at its start | Each tick at its own frame: tick *j* of a block falls in frame ⌈(*j*·thr − accum)/(bpm×100·96)⌉ − 1 | `test_d1_events_fall_on_their_own_frame`, block-size identity at 1, 7, 64 and 128 frames |
| D2 | The first step after Play or a launch sends its locks after its note-ons | Before them, as every later step does | `test_d2_first_step_locks_come_before_its_notes` |
| D3 | After a count-in, step 0 plays on master tick 383 | On 384, the bar | `test_d3_count_in_starts_on_the_bar` |
| D4 | An overdub note in the last half-step anchors on the loop end and grows the clip by a bar | Clamped to the last step; a first take still grows | `test_d4_overdub_at_the_loop_end_keeps_the_length` |
| D5 | Nudge and length caps use `length_ticks`: with a loop start past 0 the nudge panics and gates collapse to 1 tick | `loop_end_ticks` | `test_d5_nudge_and_length_use_the_loop_end` |
| D6 | Stop leaves lanes at their last lock | Each lane whose last value differs from its base is sent back to it, after the note-offs | `test_d6_stop_reverts_locked_lanes` |
| D7 | Unbounded lists | Fixed pools; a full pool refuses the edit and counts it in `fm1_seq_stats_t.refused` (the UI's toast); a full gate pool ends its oldest note first | `test_d7_*` |

Where Movy would panic (D5's nudge, `cpy` with s0 > s1 in a debug build),
compat mode skips the input and counts it in `compat_divergence`.

**Other differences, in both modes** [verified unless marked]:

- The gate pool is a limit even in compat (255 there); Movy's is unbounded.
- `tog` takes at most 12 pitches (Movy: unbounded); lane labels keep 23 bytes.
- Ticks and gates are 16-bit. Only a loaded `movy1` can exceed 65,535; such
  values saturate. Locks and trig rows past step 255, which no playhead
  reaches in Movy, are refused rather than stored.
- Pad mutes: 16 per track, songs 64 entries, held recording notes 16, and
  Capture off (limits). The tools' `--compat` runs use larger limits so that
  Movy's scripts fit (255 gates and song entries, 64 held notes, 128 pad
  mutes, pools of 16,384 notes and locks) and Movy's 512-event Capture ring.
- The external clock's tempo smoothing and Capture's tempo search run in
  float, not f64. A result can differ from Movy's only at a near-tie
  [inferred].
- Not ported: the Move transport link and MovePlay inject (`minject` is
  stored and ignored, so `play` always starts at once), the undo ring (the
  `usnap`…`uclr` verbs are accepted and do nothing), status strings.
- FM-1 additions Movy ignores: the verb `route` and the `movy1` line `rt`
  (written only outside compat mode, only for non-default routes).

## Memory [verified: `fm1-seq --sizes`, tests/test_seq_core.py]

Default limits per track: 192 notes, 192 locks and 32 trig rows in the
global pools; 64 gates, 64 song entries and 16 recording notes per instance.

| Tracks | Bytes | Of the half budget (36,864 B) | Of the stock gap (387,924 B) |
| --- | --- | --- | --- |
| 4 | 14,984 | 41 % | 3.9 % |
| 8 | 28,808 | 78 % | 7.4 % |
| 8, Capture 256 events | 33,928 | 92 % | 8.7 % |
| 16 (docs/13 §5's pools) | 56,456 | | 14.6 % |

Each track adds 3,456 bytes: 2,304 of notes, 576 of locks, 160 of trig rows,
160 of clip headers, 240 of track state and 16 of pad mutes. The fixed part
is 1,160 bytes. Capture costs 20 bytes per event (256 events, about 128
notes over Movy's 8-bar window: 5,120 bytes) plus about 1.3 KB of stack while
a stopped capture searches its tempo. Docs/13 §5 estimated 73,320 bytes for
16 tracks with the same pools; the measured 56,456 leaves out its undo ring
(12,288) and Capture (3,072), and packs locks and trig rows tighter (3,584
bytes less), while 23-byte lane labels make each track larger.

Not instance memory: one `fm1_seq_cmd_t` is 240 bytes and one event 12.

## CPU [verified on the desktop only: Apple M1 Max, -O2; pi32v2 is stage B]

Time in `fm1_seq_advance`, from `fm1-seq --state` (`advance_ns_per_block`,
`advance_ns_max`), 64-frame blocks at 44,118 Hz (1.451 ms each), three runs
each (the generating scripts are not committed; each case is a few lines of
`tog`/`ltog`/`aset` verbs):

| Case | Mean per block | Worst block | Mean, share of a block |
| --- | --- | --- | --- |
| 4 tracks × 16 notes, 2 locked lanes each, 120 BPM | 50 ns | 3–30 µs (scheduler noise) | 0.003 % |
| 8 tracks, every pool full (1,536 notes, 1,536 locks, 256 trig rows), 16-bar clips at 4X and 300 BPM, swing, quantise 50 | 1.7 µs | 75–87 µs | 0.12 % |
| one 512-note clip whose quantise changes every bar | 55 ns | 29–31 µs | |

The worst blocks are fire-tick index rebuilds: the first scan after Play
builds every clip's index, and a quantise, swing, scale or loop change
rebuilds that clip's, here about 30 µs for 512 notes on the M1. pi32v2 runs
at 240 MHz with a narrower core, so the same rebuild could take a sizeable
part of one 64-frame block there [inferred]; stage B measures it. If it does,
the remedies are cheap: rebuild in the control task and swap the index in,
spread the rebuild over a few blocks (the old index stays valid for notes the
edit did not touch), or update the index incrementally for single-note edits,
which are most edits. Applying commands runs on the audio task too; a burst
of thousands of verbs in one block (a set built by script) took about 1 ms
here, while a UI sends a handful per block.

## Routing (docs/13 §10, answer 2)

Each track carries a route: an engine slot (0–7) or a USB-MIDI channel
(1–16). The default is MIDI channel *track*+1. `route <t> <0|1> <ch|slot>`
sets it, `fm1_seq_set_route` from C, and a `movy1` set stores it as
`rt <t> <kind> <index>`. The events are the same either way: routing is the
host's to act on.

`fm1-render` sends a track routed to the engine to `note_on`/`note_off` at the
event's own frame, by rendering the block in pieces split at each event; with
no `--route` and no routes in the set, track 0 plays the engine. A lock on such
a track sets the engine parameter its lane's label names: the part of
`synth:Timbre` after the last `:`, matched by name without case. FLOAT
parameters scale 0..127 onto min..max; ENUM parameters use Movy's planned bins
⌊v·n/128⌋. A label that names no parameter is ignored. MIDI-routed tracks are
only logged. Output is byte-identical at host blocks of 1, 7 and 64 frames for
Test Sine, Macro and Six-Op [verified: tests/test_seq_render.py].

## The shared formats

The verb script and the event log (`host/seq_script.h`) are shared with the
Movy oracle (stage M3). Two additions here, both invisible to a reader that
does not know them: the header key `end=<frames>` (the run length; both tools
otherwise stop after the block in which the last command applies) and test
lines `#?@<frame> <label>`, which ask `fm1-seq` for a state dump at that
point among the commands. A lock is logged as kind `cc` with
`a = 102 + lane` in both modes. `tick` is the master tick being serviced
(0-based from the last transport start); events from commands and Start/Stop
carry the number of ticks serviced so far.

## Tests (200, all passing)

- `tests/test_seq_movy.py` (136): Movy's own tests transcribed into verb
  scripts in compat mode, each naming its source test and line: clock.rs,
  engine.rs (transport, playback, automation, quantise and swing, recording,
  launches, scenes, song, Capture), clip.rs, command.rs, persist.rs. Skipped:
  the Move link and inject tests, status strings, undo.
- `tests/test_seq_core.py` (51): D1–D7 against compat, block-size identity,
  10,000 steps without drift, the memory figures, no heap, fill
  independence, 24 random scripts through the checking build, the verb
  parser's integer rules, Movy's three fixtures, routing.
- `tests/test_seq_render.py` (13): routing through `fm1-render`, notes and
  locks at their own frame, FLOAT and ENUM lock mapping, block-size identity
  of the audio, the renderer's log equal to `fm1-seq`'s, plain renders
  unchanged.

Run on: macOS clang (the whole suite), clang ASan + UBSan (the sequencer and
engine tests: 923 passed, 1 expected failure), GCC 12 64-bit and `-m32` in a
container on aeon (the sequencer tests, and with `-m32` the engine tests too).

## What M2 and later still need

- **Engine API v2** (docs/13 §6): a stable `uint16_t uid` per parameter so a
  lane names its target by uid rather than by label text, and flags LATCH,
  SMOOTH and NOLOCK (Macro's Model refused as NOLOCK is M2's exit test). Today
  the label match and the bins live in `fm1-render`.
- `FM1_KIND_MIDI_FX` for per-track MIDI effects.
- The command ring between the UI and audio tasks, and undo (binary
  per-clip snapshots in a byte budget, docs/13 §5) with the UI, stage M4.
- External clock: F2/FB handling beyond Movy's, and the oracle's check of the
  float smoothing.
- Stage M3, the oracle: random scripts against Movy's `seq-core`, every
  difference mapped to a row above.

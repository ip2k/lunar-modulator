# engines/seq — the sequencer core (docs/13, stage M1)

A C99 sequencer that replays [Movy](https://github.com/DimaDake/schwung-movy)'s
`seq-core` (MIT, megadake) tick for tick, plus the FM-1 changes the owner
asked for (docs/13 §10): deviations D1–D13 on by default, 4–8 routed tracks,
about half of docs/13's 72 KiB, 7-bit locks behind one typedef, Capture
(record-after) on by default in a ring of 256 packed events. Desktop only:
nothing here runs on, or is sent to, any FM-1 or MIDI device. Pinned to Movy
commit `9190e79`; what was read is listed in
[third_party/movy/UPSTREAM.md](third_party/movy/UPSTREAM.md).

```bash
make -C engines                                   # build/fm1-seq, build/fm1-seq-check, build/fm1-render, build/fm1-seq-host-test
engines/build/fm1-seq --sizes                     # fm1_seq_size() for 1-16 tracks
engines/build/fm1-seq --cmd song.txt --log song.jsonl --state song.json
engines/build/fm1-seq --compat --cmd s.verbs --log s.jsonl   # Movy exactly (--compat-frames: with D1 frames)
engines/build/fm1-render --engine macro --cmd song.txt --log-events song.jsonl --out song.wav
engines/build/fm1-render --engine macro --seq set.movy1 --seconds 8 --out set.wav
python3 tools/seq_bench.py --out DIR --run        # the worst-case scripts for stage B, timed
python -m pytest tests/test_seq*.py               # the sequencer tests
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
| `seq/seq_capture.c` | Capture, the retroactive record (capture.rs and engine.rs's capture functions), in 12-byte events |
| `include/fm1_seq_host.h`, `seq/seq_host.c` | The host bridge: the per-block code every host shares (commands into the event buffer, advance, split renders into a sound engine, lane labels resolved to parameter uids, NOLOCK refusals); C99, no heap, no stdio, like the core (below, Host contract) |
| `host/seq_script.[ch]` | Desktop only: the timed verb-script reader (Movy verbs and `rt` realtime input), the JSON Lines event log, and `fm1_seq_cmd_format`, a typed command as text that `fm1_seq_parse` reads back to the same record (the virtual FM-1's harness logs its panel's commands so, for `fm1-render` to replay) |
| `host/seq_tool.c` | `fm1-seq`: runs the core alone and dumps state as JSON; `fm1-seq-check` is the same tool on a core built with `-DSQ_CHECK_INDEX` |
| `test/seq_host_test.c` | `fm1-seq-host-test`: the host bridge's own checks, where `fm1-render` does not reach it (typed commands, realtime input and live notes against text lines; every sink call at its event's frame) |
| `host/render.cc` | `fm1-render --cmd/--seq/--log-events/--compat/--tracks/--route/--events`, through the host bridge |
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
| Capture event (below) | 12 | 24 |

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

**Capture, packed.** Capture keeps every note played in a ring (Movy's
`CapEvent`, 24 bytes in Rust), and each field is only as wide as what Movy
does with it needs; `seq_capture.c` gives the reasoning in full:

| Field | Bits | Why that loses nothing |
| --- | --- | --- |
| Pitch | 7 | `non`, `nof` and `fm1_seq_note_in` take 0–127 only |
| Velocity, which also tells the kind | 7 | a note-on's is clamped to 1–127, a note-off's is 0, so it says which the event is (Movy's `on`), as in MIDI |
| Track | 4 | at most 16; input for a track past the instance's is refused before it is stamped |
| Playhead (clip tick) | 14 | below the clip's loop end, at most (255 + 256) steps × 24 = 12,264: a take written into an empty clip whose loop starts late makes it 256 steps long from there |
| Frame | 25, from a base | only differences between events of the ring (or of a frozen take) are used, and the 8-bar window keeps those within 96 s at 20 BPM: 4,235,328 frames at 44,118 Hz, below 2^25 up to 349,525 Hz. The base moves onto the oldest event when the newest would not fit; the newest event's frame is Movy's `last_frame` |
| Master tick | 16 and a flag | below 2^16 as it is, above as an offset from a base. The ring's ticks above 2^16 all come from one transport run and lie within 96 s at 300 BPM (46,080 ticks) of each other; after a restart that keeps the ring (a MIDI Start while playing) the new ticks are small again |
| Cycle | 20 and a flag | only compared for equality with the track's cycle now, for events at most 104 s old (window and gap; the gap rule is applied first, so older events are gone before any comparison): a 1-step loop at Movy's 255X and 300 BPM wraps 530,400 times in that, more than 2^19 and below 2^20 − 1, and the flag tells a cycle of 2^20 or more (hours of looping before a restart) from any cycle reached since |
| Used | 1 | a commit's scratch: this note-off already ends a note |

The two bases take the place of two fields the 20-byte layout had, so the
instance did not grow. A push moves a base only when an offset would
overflow, every few minutes of unbroken playing, and then repacks the ring
(256 events). Outside the ranges above, at a sample rate above 349,525 Hz
with a slow tempo, or when a clock drives more than 65,535 master ticks
through one window (only an external clock averaging above about 426 BPM
can), the ring drops its oldest events until the new one packs, which Movy
would not; such a clock can also wrap a 1-step loop at compat's 255X 2^20
times within window and gap, and the stale rule then keeps notes Movy
drops. The checking build keeps every value unpacked beside the packed one
and traps on any difference, after every push and on every read, and in
that fallback.

Movy applies Capture's gap rule (silence ends the phrase) after its stale
rule (a note played over an earlier pass's note clears the ring); the core
applies it first. Either order clears the ring when the gap is exceeded and
changes nothing when it is not, so the outcome is Movy's, but the stale rule
then never compares a cycle with one from before the silence, however long
the silence was: with it second, the checking build trapped on a note-on
after 206 s of silence over a one-step loop at 254X, whose cycle had moved
exactly 2^20 [verified: tests/test_seq_core.py, the Movy oracle].

**Events.** `fm1_seq_ev_t` is 12 bytes: the master tick, the frame offset in
the block, kind, track, two arguments. At one frame the order is Movy's
emission order: gate note-offs, then (D2) the locks of a step starting there,
then note-ons, then the locks of the step the playhead enters.

**A full event buffer never leaves a note sounding.** Each call writes into
the caller's buffer and keeps room in it for the note-off of every sounding
gate: a note-on that does not fit is dropped whole (no gate, so no note-off
later), a lock that does not fit is not marked as sent (the latch sends it at
a later step), a clock tick or click is lost; each counts in
`dropped_events`. A buffer of `fm1_seq_min_events(&limits)` (the gates plus
8) always holds every note-off, Start and Stop. How many events one block
can carry has no small bound: every note in the pools can fall due on one
tick. The worst case measured, tools/seq_bench.py's burst (8 tracks of
12-note chords on every step, 8 locked lanes, 300 BPM, 4X), peaks at 193
events in one 64-frame block (2.3 KB of events) [verified, desktop].

**Commands.** `fm1_seq_cmd_t` is Movy's `cmd` op as a typed record: the verb
and up to 26 integer arguments parsed exactly as command.rs parses them (an
`i64` per token, an unparseable token absent), then clamped and truncated
exactly as Movy does (`as u16` in `loop`, `as i32` in the edit deltas,
wrapping adds as in Movy's release build). `fm1_seq_apply_text` is
`apply_batch`, `#<seq>` tags included. Where Movy panics (D5's nudge),
compat mode does what movy-dsp's `catch_unwind` leaves: the edit stops at the
note that panics, the op neither re-seeds empty clips nor marks the set
dirty, and the rest of its batch is dropped. A UI builds the records
directly; the single-producer ring docs/13 §6 describes is stage M4's, and
its record should be compact (one `fm1_seq_cmd_t` is 240 bytes, so 32 of
them would be 7.5 KB): a verb, a track and a few small arguments, with a
chord's pitches passed some other way.

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

All on by default; `limits.compat` (`--compat`) turns every one off.
`FM1_SEQ_COMPAT_MOVY_FRAMES` (`--compat-frames`) is Movy's behaviour with D1's
frames, which the Movy oracle's `--frames tick` traces are compared with.

| # | Movy at 9190e79 | FM-1 default | Test |
| --- | --- | --- | --- |
| D1 | A block's events all at its start | Each tick at its own frame: tick *j* of a block falls in frame ⌈(*j*·thr − accum)/(bpm×100·96)⌉ − 1; following an external clock, the frame at which the follow target reaches the tick | `test_d1_events_fall_on_their_own_frame`, block-size identity at 1, 7, 64 and 128 frames, the oracle's D1 traces (`test_golden_d1_frames`) |
| D2 | The first step after Play or a launch sends its locks after its note-ons | Before them, as every later step does | `test_d2_first_step_locks_come_before_its_notes` |
| D3 | After a count-in, step 0 plays on master tick 383 | On 384, the bar | `test_d3_count_in_starts_on_the_bar` |
| D4 | An overdub note in the last half-step anchors on the loop end and grows the clip by a bar; a 16-bar first take's stays on step 256 | Clamped to the last step; a first take that can still grow keeps Movy's growth | `test_d4_*` |
| D5 | Nudge and length caps use `length_ticks`: with a loop start past 0 the nudge panics and gates collapse to 1 tick; Capture clamps anchors to `len_steps − 1` | `loop_end_ticks`, and the window's last step | `test_d5_*` |
| D6 | Stop, a track's stop on the bar and a lane's release leave a lane at its last lock | Each lane whose last value differs from its base is sent back to it, after the note-offs | `test_d6_*` |
| D7 | Unbounded lists | Fixed pools; a full pool refuses the edit, whole (a chord, `addp`, `asetr`, Double Loop, step copy and paste, a trig range), and counts it in `fm1_seq_stats_t.refused` (the UI's toast); a full gate pool ends its oldest note first | `test_d7_*` |
| D8 | Clip speed 1/255X to 255X | 1/8X to 4X, Movy's UI range | `test_d8_*` |
| D9 | A bar launch or stop sends the outgoing clip's look-ahead lock first | Not when the launch or stop is already queued | `test_d9_no_lock_for_a_step_that_never_plays` |
| D10 | A recorded or captured note keeps its played tick, so playback adds the swing twice | Its tick less its anchor's swing | `test_d10_recorded_ticks_are_stored_without_the_swing` |
| D11 | Notes anchored up to a window length past the loop end fold back and play; an early note on an offset window's first step is lost | Notes outside the window are silent; none fires before the loop start | `test_d11_*` |
| D12 | Play while playing sends neither Stop nor Start | Stop, then Start on the next block | `test_d12_play_while_playing_sends_stop_and_start` |
| D13 | `aclr` keeps the lane's base and carried value | Resets both | `test_d13_aclr_resets_base_and_carry` |

`fm1_seq_stats_t.movy_faults` counts the inputs on which Movy's code faults
(D5's nudge panic, and `cpy` with s0 > s1, whose `u16` span wraps in a release
build and panics in a debug one), in both modes: compat replays the release
build, the default skips them.

**Other differences, in both modes** [verified unless marked]:

- The gate pool is a limit even in compat (255 there); Movy's is unbounded.
- `tog` takes at most 12 pitches (Movy: unbounded); lane labels keep 23 bytes.
- Ticks and gates are 16-bit. Only a loaded `movy1` can exceed 65,535; such
  values saturate. Locks and trig rows past step 255, which no playhead
  reaches in Movy, are refused rather than stored.
- Pad mutes: 16 per track, songs 64 entries, held recording notes 16, and a
  Capture ring of 256 events (limits; Movy's holds 512). The tools'
  `--compat` runs use larger limits so that Movy's scripts fit (255 gates and
  song entries, 64 held notes, 128 pad mutes, pools of 16,384 notes and
  locks) and Movy's 512-event Capture ring.
- Capture's events are packed into 12 bytes, exactly within the ranges
  under Design; beyond them (above 349,525 Hz at a slow tempo, an external
  clock averaging above about 426 BPM) the ring drops its oldest events
  early, and with a 1-step loop at compat's 255X the stale rule can keep
  notes Movy drops.
- The external clock's tempo smoothing and Capture's tempo search run in
  float, not f64. A result can differ from Movy's only at a near-tie
  [inferred]; none has in the oracle's scripts.
- Not ported: the Move transport link and MovePlay inject (`minject` is
  stored and ignored, so `play` always starts at once), the undo ring (the
  `usnap`…`uclr` verbs are accepted and do nothing; docs/13 keeps D14 for
  when it is), status strings.
- Live input's frame offset (`fm1_seq_note_in`) reaches Capture's stamps
  only. Recording stamps the playhead at the block's start, as Movy does: at
  the FM-1's 64-frame blocks that is the tick the note was played on or the
  one before [inferred]. Placing it exactly would mean applying input between
  ticks inside `fm1_seq_advance`; that belongs with the UI's input path (M4).
- FM-1 additions Movy ignores: the verb `route` and the `movy1` line `rt`
  (written only outside compat mode, only for non-default routes).

## Memory [verified: `fm1-seq --sizes`, tests/test_seq_core.py]

Default limits per track: 192 notes, 192 locks and 32 trig rows in the
global pools; 64 gates, 64 song entries, 16 recording notes and a Capture
ring of 256 events per instance (the owner's choice of 2026-10-01, docs/13
§10; `limits.capture` changes it, 0 leaves Capture out).

| Tracks | Bytes | Of the half budget (36,864 B) | Of the stock gap (387,924 B) |
| --- | --- | --- | --- |
| 4 | 18,056 | 49 % | 4.7 % |
| 8 | 31,880 | 86 % | 8.2 % |
| 8, Capture off | 28,808 | 78 % | 7.4 % |
| 16 (docs/13 §5's pools) | 59,528 | | 15.3 % |

Each track adds 3,456 bytes: 2,304 of notes, 576 of locks, 160 of trig rows,
160 of clip headers, 240 of track state and 16 of pad mutes. The fixed part
is 1,160 bytes, and Capture 3,072: 256 events of 12 bytes, about 128 notes
over Movy's 8-bar window (at 20 bytes an event, as first built, it was
5,120), plus about 1.3 KB of stack while a stopped capture searches its
tempo. Docs/13 §5 estimated 73,320 bytes for 16 tracks with the same pools;
the measured 59,528 leaves out its undo ring (12,288) and packs locks and
trig rows tighter (3,584 bytes less), while 23-byte lane labels make each
track larger.

Not instance memory: one `fm1_seq_cmd_t` is 240 bytes and one event 12.

## CPU [verified on the desktop only: Apple M1 Max, -O2; pi32v2 is stage B]

Time in `fm1_seq_advance`, from `fm1-seq --state` (`advance_ns_per_block`,
`advance_ns_max`), 64-frame blocks at 44,118 Hz (1.451 ms each), three runs
each. tools/seq_bench.py writes the two worst-case scripts.

| Case | Mean per block | Worst block | Mean, share of a block |
| --- | --- | --- | --- |
| 4 tracks × 16 notes, 2 locked lanes each, 120 BPM | 50 ns | 3–30 µs (scheduler noise) | 0.003 % |
| 8 tracks, every pool full (1,536 notes, 1,536 locks, 256 trig rows), 16-bar clips at 4X and 300 BPM, swing, quantise 50 | 1.7 µs | 75–87 µs | 0.12 % |
| one 512-note clip whose quantise changes every bar | 55 ns | 29–31 µs | |
| seq_bench burst: 8 tracks of 12-note chords on every step, 8 locked lanes on every step, 300 BPM, asked for at 255X (D8: 4X) | 4.1–4.4 µs | 81–83 µs | 0.3 % |
| the same in compat, at Movy's 255X | 139–145 µs | 367–373 µs | 9.7 % |
| seq_bench edit: `addp`, `asetr` and Double Loop over 256 steps against a nearly full note pool | 0.5 µs | 63–67 µs | |

The worst blocks are fire-tick index rebuilds: the first scan after Play
builds every clip's index, and a quantise, swing, scale or loop change
rebuilds that clip's, here about 30 µs for 512 notes on the M1. pi32v2 runs
at 240 MHz with a narrower core, so the same rebuild could take a sizeable
part of one 64-frame block there [inferred]; stage B measures it, with the
seq_bench scripts. Work still on the audio task that stage B must time or
move [inferred costs]:

- **Index rebuilds.** Rebuild in the control task and swap the index in,
  spread a rebuild over a few blocks (the old index stays valid for notes
  the edit did not touch), or update it incrementally for single-note edits,
  which are most edits.
- **Pool inserts.** Each insert moves the rest of its pool (`memmove`) and
  every later clip's offset; a range edit (`addp`, `asetr`, Double Loop,
  paste) does that once per item. Batching an edit's inserts into one move
  is the remedy.
- **Commands.** A burst of thousands of verbs in one block (a set built by
  script) took about 1 ms here, while a UI sends a handful per block.
  Capture's stopped tempo search (211 tempos × the take's note-ons, with
  `logf`) runs inside the `cap` command and needs about 1.55 KB of stack;
  on the device it belongs in the control task.
- **32-bit arithmetic.** The per-tick path keeps the bar phase in a 16-bit
  counter (no 64-bit `%`), counts ticks by subtraction (no 64-bit `/`) and
  computes D1's frame in 32 bits whenever it fits, which it always does at
  64-frame blocks (64 × 2,880,000 < 2³²). The clock accumulator stays 64-bit,
  for sample rates and block sizes the desktop tools allow; at the FM-1's it
  would fit in 32 bits (docs/13 §5).

## Routing (docs/13 §10, answer 2)

Each track carries a route: an engine slot (0–7) or a USB-MIDI channel
(1–16). The default is MIDI channel *track*+1. `route <t> <0|1> <ch|slot>`
sets it, `fm1_seq_set_route` from C, and a `movy1` set stores it as
`rt <t> <kind> <index>`. The events are the same either way: routing is the
host's to act on.

`fm1-render`, through the host bridge (below), sends a track routed to the
engine to `note_on`/`note_off` at the event's own frame, by rendering the
block in pieces split at each event; with no `--route` and no routes in the
set, track 0 plays the engine. A lock on such
a track sets the engine parameter its lane's label names: the part of
`synth:Timbre` after the last `:`, matched by name without case and resolved
to the parameter's uid (engine API v2) when the lane is labelled. FLOAT
parameters scale 0..127 onto min..max; ENUM parameters use Movy's planned bins
⌊v·n/128⌋. A label that names no parameter is ignored, and a lock on a
NOLOCK parameter (Macro's Model) is refused and counted. MIDI-routed tracks
are only logged. Output is byte-identical at host blocks of 1, 7 and 64 frames for
Test Sine, Macro and Six-Op [verified: tests/test_seq_render.py].

## Host contract (`include/fm1_seq_host.h`)

Every host of the core runs the same per-block code, `seq/seq_host.c`:
`fm1-render`, the virtual FM-1's app layer (sim/web, since docs/15 stage
S2) and the firmware's audio task next. It was extracted from `fm1-render` with no change in behaviour: over
810 runs of the old and new renderer and `fm1-seq` (the 34 oracle scripts
with no engine, Test Sine, and Macro and Six-Op at 44,118 Hz or Shapes at
48 kHz, in both modes at 64-frame blocks and at each script's own; the
renderer tests' scripts; Movy's three sets; errors and refusals), every
WAV, event log, exported set, state dump and error is byte-identical, and so
is every summary less its timing and its three new fields; only the usage
text gains `[--events N]` [verified 2026-10-02, Apple clang]. A review ran
7,016 more on two clean builds, old and new, with the same result
[verified 2026-10-02, Apple clang]: Sophie and Macro Heavy as well; blocks
from 1 to 256 frames; 60 seeded random scripts with Capture, lanes renamed
onto each engine's parameters, `route` verbs that move tracks between the
engine and MIDI mid-play, and `rt` lines; 16 sets with `rt` lines, played
alone and under commands; `--route`, `--fx`, `--input`, `--fault`,
`--note`, `--param-at`, `--bend` and `--seconds` beside the sequencer; and
`fm1-seq` and `fm1-seq-check` over every script. It is C99
with no heap and no stdio, in `SEQ_SRC` beside the core, so `nm -u` checks
it with the core's objects [verified: tests/test_seq_core.py].

**Per block of n frames:**

1. The host's own controls and live notes go straight to the engine
   (`fm1-render`: `--param-at` and `--bend`, then `--note` offs before ons).
2. Commands due now: `fm1_seq_host_line` (a script or UI line: Movy ops, or
   `rt F8|FA|FB|FC` realtime input) or `fm1_seq_host_cmd` (a typed record).
   Each appends its events (a stop's note-offs, an auditioned lock) at frame
   0. `fm1-render`'s implicit `play` for `--seq` alone goes through it too.
3. Live input at frame 0: `fm1_seq_host_note_in` (recording and Capture) and
   `fm1_seq_host_realtime` (MIDI clock and transport).
4. `fm1_seq_host_advance(h, n)`: the block's own events, after those.
5. A test harness logs `ev[0..n)` here. `fm1-render --log-events` and
   `fm1-seq --log` write the same bytes for every oracle script, in both
   modes, at 64-frame blocks and at the script's own [verified:
   tests/test_seq_render.py].
6. `fm1_seq_host_dispatch(h, n, block, &sink)` renders the sound engine in
   pieces split at the frame of each note-on, note-off and lock of a track
   routed to the engine, in emission order (at one frame: offs, locks, ons),
   and empties the buffer. A lock whose lane names no parameter of the
   engine is skipped before any split, and so is a lock on a NOLOCK
   parameter, which is counted (below). Clicks, clock, Start, Stop and
   MIDI-routed tracks are the host's to send elsewhere; `fm1-render` only
   logs them. A NULL sink only empties the buffer (`fm1-render` with no
   engine).
   `fm1_seq_host_dispatch_ticks(h, n, block, &sink, &hook)` does the same
   and also runs a control-rate hook, the modulation runtime's tick
   (docs/16 stage MG1, `include/fm1_mod_host.h`): it hands the hook every
   event at its frame, runs each tick at its own frame (at one frame:
   note-offs and locks, the tick and its writes, then note-ons, docs/16's
   rule M6), passes each lock's value through the hook (a lock moves a
   routed parameter's base, rule M1), and splits the render only at a tick
   that writes to the engine. With nothing routed a tick writes nothing, so
   the audio is what plain dispatch gives [verified: engines/mod/README.md,
   "No render changed"]. The sink's `pitch_bend`, new with it, carries the
   host's PITCH and may be NULL.
7. Effects, the limiter and the output, which are the host's own.

A lane's label names a parameter by the part after its last `:`, compared
without ASCII case (`fm1_seq_lane_param`), and a 7-bit value maps onto it
by `fm1_seq_lock_value`: min + range·v/127 for FLOAT, the bins ⌊v·n/128⌋ for
an ENUM of n values. Both are the expressions `fm1-render` had.

**Where locks resolve (engine API v2, docs/15 stage S7a).** A lock targets
the parameter's uid (engines/README.md, "Parameters"), not its index, so a
reordered parameter table cannot move it. Labels stay text in the core and
in `movy1` sets (`synth:<Name>`, the owner's choice, O13); the bridge turns
each into a uid (`fm1_seq_lane_uid`) and keeps one per lane, 16 tracks × 8
lanes × 2 bytes in `fm1_seq_host_t`:

- **When a lane is labelled:** a line holding `alabel` through
  `fm1_seq_host_line`, or a typed `alabel` through `fm1_seq_host_cmd`,
  resolves as it is applied.
- **When a set is imported:** `fm1_seq_host_import` (what hosts import
  through; `fm1-render --seq` does).
- **When the engine changes:** dispatch binds `sink->engine` if it is not
  the bound one, and `fm1_seq_host_bind` does it explicitly (`fm1-render`
  binds its sound engine before importing).
- **A released lane** (`aclr`, a deleted clip, D13) loses its label in the
  core; `fm1_seq_host_lane_uid` reads the label's first byte and gives 0.
  Only `alabel` and an import give a lane a label, and through the bridge
  both resolve it, so the stored uid equals a fresh resolution of the label
  against the bound engine. engines/test/seq_host_test.c checks that after
  every block of a script that labels, relabels and releases lanes
  mid-play, through text and typed commands alike.
- **A label set past the bridge** (an import or `alabel` on the core
  directly, as a host may do): `fm1_seq_host_lane_uid` uses the stored uid
  only while its parameter still has the name the label gives, and
  resolves the label afresh otherwise, so such a lane's locks still reach
  the parameter it names (one name lookup per lock, as before API v2),
  until `fm1_seq_host_bind` stores it again. Names are unique without case
  in every engine [verified: tests/test_engine_params.py], so the check
  and a fresh resolution agree.

At dispatch a lock goes to `fm1_param_index(engine, uid)`. A lock on a
NOLOCK parameter is refused there: it is counted in `locks_refused`
(`fm1-render`'s `seq_locks_refused`), never reaches the engine and splits
nothing, so the audio is that of the same script without the lane
[verified: tests/test_seq_render.py, Macro's and Macro Heavy's Model,
Shapes' Shape and Sophie's Pad]. A lane on a NOLOCK parameter still resolves
to its uid, so a lock UI can say why its locks are refused. Resolution
changes no output: of 1,458 renders before and after the change, only the
38 that lock a NOLOCK parameter differ (engines/README.md, "Parameters").

**Event room.** Commands, live input and advance share one buffer per
block. One command can cause up to `fm1_seq_cmd_max_events(&limits)` = gates
+ 8 × tracks + 1 events: every gate's note-off, a D6 base revert on every
lane of every track, and a Start or Stop (`play` while playing sends a
Stop, D12). That is 129 at 8 tracks and 64 gates. A stop at full load sends
128 (64 note-offs, 64 base reverts), and the block's advance adds the
transport's Stop, so that block holds 129 [verified: tests/test_seq_render.py;
the 128 counted on the core directly, 2026-10-02]. Advance needs
`fm1_seq_min_events(&limits)` of the
buffer to keep every note-off, Start and Stop. So a host applies a command
only while `fm1_seq_host_room(h)` is at least `fm1_seq_cmd_max_events` +
`fm1_seq_min_events`, and holds it for the next block otherwise. The bound
is per op: a text line may hold several. 256 events (3 KB, the virtual
FM-1's buffer) take that full stop with nothing dropped; `fm1-render`'s
default 65,536 never come near the rule, and `--events N` runs it at a
device's size. In the default mode at 64-frame blocks no oracle script puts
more than 7 events in one block [verified]. The virtual FM-1 enforces the
rule (sim/web/src/fm1_app.c): a script line goes in op by op and its rest
waits a block when the room runs out; a typed command waits in one pending
record, and a second one meanwhile is refused (BUSY) for the sender to
repeat. The core's own reserve is separate: beside a block's events it keeps
room for the note-off of every sounding gate, so a block of e events needs
about e + 64. tools/seq_bench.py's burst reaches 193 events in a block and
so needs 257: at 256 it drops 400 of 76,800 note-ons, whole, and hangs
nothing [verified 2026-10-02: `fm1-render --events`].

**Routing is the host's policy.** The bridge acts on each track's route;
setting the routes is up to the host. The default-route rule is one bridge
function, `fm1_seq_default_route`, which `fm1-render` and the virtual FM-1
both call: track 0 goes to the engine only when the host routes nothing
itself (`fm1-render`: no `--route`), the set has no `rt` lines (every track
still on MIDI channel t+1, `fm1_seq_routes_default`) and an engine is
loaded. Moving it out of `fm1-render` changed nothing: 788 runs of the
renderer before and after (the 34 oracle scripts with no engine, Test Sine,
and Macro and Six-Op or Shapes, in both modes at both block sizes; scripts
with `route` verbs; Movy's sets and sets with `rt` lines, alone and under
commands, at 8 and 16 tracks; each with and without `--route`) gave
byte-identical WAVs, event logs and summaries less timing [verified
2026-10-02, Apple clang]. Importing a set (`fm1_seq_import_movy1`) first
resets every route to MIDI channel t+1, and an export writes only routes
other than that, so a host applies its default again after an import.

**`fm1-render`'s summary** carries the bridge's counters:
`seq_notes_to_engine`, `seq_locks_to_engine`, `seq_locks_refused` (locks on
NOLOCK parameters), `seq_splits` (render calls that start inside a block),
`seq_max_block_events` (the most events one block held) and `seq_dropped`
(the core's `dropped_events`). The WAV alone cannot
show a split: an engine's output does not depend on how a block is cut into
render calls [verified for Test Sine, Macro and Six-Op at 1, 7 and 64
frames], so `seq_splits` is what shows that a skipped lock did not split
its block.

## The shared formats

The verb script and the event log (`host/seq_script.h`) are shared with the
Movy oracle (tools/movy-oracle/README.md has the specification). Both sides
read the header key `end=<frames>` (the run length: whole blocks, the last
one shorter, and a command due at the end frame applied after them; without
it the run stops after the block in which the last command applies) and the
line `@<frame> rt F8|FA|FB|FC`, MIDI realtime input (`fm1_seq_realtime_in`;
Movy's `Engine::on_external_realtime`), delivered like a command. Test lines
`#?@<frame> <label>` are this repository's only: comments to the oracle, they
ask `fm1-seq` for a state dump at that point among the commands. A lock is
logged as kind `cc` with `a = 102 + lane` in both modes. `tick` is the master
tick being serviced (0-based from the last transport start); events from
commands and Start/Stop carry the number of ticks serviced so far.

## Tests

- `tests/test_seq_movy.py` (136): Movy's own tests transcribed into verb
  scripts in compat mode, each naming its source test and line: clock.rs,
  engine.rs (transport, playback, automation, quantise and swing, recording,
  launches, scenes, song, Capture), clip.rs, command.rs, persist.rs. Skipped:
  the Move link and inject tests, status strings, undo.
- `tests/test_seq_oracle.py`: the C core against Movy's own output, from the
  oracle (tests/fixtures/movy/, which comes with tools/movy-oracle; without
  it the module skips). Every curated fixture through `fm1-seq --compat` and
  `fm1-render --compat` (events and the exported set), the D1 traces through
  `--compat-frames` and the default mode (with the D-rows they reach), and a
  dozen seeded random scripts. 18-undo is an expected failure.
- `tests/test_seq_core.py`: D1–D13 against compat, compat's panic, block-size
  identity, 10,000 steps without drift, the memory figures, no heap, fill
  independence, a short event buffer, 24 random scripts through the checking
  build, the verb parser's and the `movy1` loader's integer rules, Movy's
  three set fixtures, routing, and Capture's packing, through both builds:
  a note on cycle 2^20 + k against one on cycle k after a restart, a
  25-minute run whose take must equal a 16-bar run's, a full ring that
  wraps while both bases move, and each field at the edge of its range
  (tracks 9 and 15 of 16, a take led by a stray note-off, a 96-s window at
  349,525 Hz, 46,080 master ticks of offsets, a playhead at 8,448, notes
  103.2 s and 2^19 cycles apart, the gap rule before the stale rule).
  Movy's outcome for each edge script was checked through the oracle.
- `tests/test_seq_render.py` (62): routing through `fm1-render`, notes and
  locks at their own frame, FLOAT and ENUM lock mapping (the ENUM case on
  Six-Op's Patch since API v2), locks on NOLOCK parameters refused and
  counted with the audio of the script without the lane, block-size identity
  of the audio, the renderer's log equal to `fm1-seq`'s, plain renders
  unchanged. The host bridge: lane labels (case, the last `:`, an unknown
  label sent and skipped), a float lock equal to the parameter set directly,
  an unknown label adding no split, a lane on a MIDI-routed track that never
  reaches the engine, no engine (events logged, the input untouched), every
  oracle script logged as `fm1-seq` logs it with nothing dropped, a full
  8-track stop in a 256-event buffer, a 16-track block of more than 256
  events in the default buffer, and `fm1-seq-host-test`: typed commands,
  realtime input (an external Start that ends sounding notes, then MIDI
  clock) and live notes give the events and the set their text lines give;
  the sink receives every engine-routed note and lock at its own frame and
  in order, with no empty render, and nothing from a MIDI-routed track; a
  hand-made event past the block plays at its end; every 7-bit lock
  value on ranges such as -24..24, where the expression's parenthesisation
  shows; and API v2: the flag helpers (NOLOCK over MOD), every lane's uid
  equal to a fresh resolution of its label after every block, a lock sent
  to its uid's parameter where the
  index is not uid − 1, NOLOCK locks refused, counted and splitting
  nothing, a new engine, an import, a typed `alabel` and a released lane
  each re-resolving, and a label set on the core directly, past the bridge,
  still reaching its parameter. Twenty-nine mutants of the bridge and of `fm1-render`'s use of it
  each fail at least one of these [verified 2026-10-02]: label case, the
  last `:`, a label compared only to the shorter name, a lock resolved after
  its split, MIDI-routed locks sent, the first parameter never locked, the
  frame clamp, an empty tail render, splits miscounted, note-offs counted as
  notes, inputs at `ev[0]`, a buffer never emptied, the room one short, no
  `max_n`, float locks over 128, the float expression reparenthesised, ENUM
  bins of n−1, live velocity or note-offs lost, realtime or typed events
  not kept, a realtime line at frame 1, trailing blanks refused, the room
  bound without its transport event, the log after dispatch, a 256-event
  default, a sink with no engine, `seq_dropped` from the wrong counter, and
  the loader's `rt` check a byte short.

Run on [verified 2026-10-01, with the oracle's fixtures in place]: macOS
clang, the whole suite, and under clang ASan + UBSan; GCC 12 in a container
on aeon, 64-bit (the sequencer and oracle tests) and `-m32` (those and the
engine tests), with no warnings and the same instance sizes. With the host
bridge [verified 2026-10-02]: the engine, sequencer and Movy tests (1,481
passed, 18-undo's 2 expected failures) under clang ASan + UBSan, and under
GCC 13 in a container on aeon at 64 bits and with `-m32`, with no warnings;
`fm1-seq-host-test` gives the same counts on all three. With engine API v2
[verified 2026-10-02]: the whole suite on macOS clang (2,037 passed, 2
skipped, 2 expected failures); the engine, sequencer and Movy tests (1,968)
and the app layer's under clang ASan + UBSan, with no report or failure;
GCC 12 in a container on aeon at 64 bits and with `-m32` (1,965 passed, 1
skipped, the 2 expected failures; the app layer's 33 passed), with no
warnings; `fm1-seq-host-test` the same counts on all of them; and JieLi's
pi32v2 compiler over all 67 objects in four profiles.

## The oracle's verdict (stage M3)

No unexplained difference [verified 2026-10-01, Movy 9190e79 run by
tools/movy-oracle on aeon, the C core on the Mac]:

- **Curated fixtures** (24): every one identical through `fm1-seq --compat`
  and `fm1-render --compat`, events and exported set, except 18-undo (undo
  is not ported). The six D1 traces are identical through `--compat-frames`,
  external-clock follow included (23, 24). In the default mode 01, 02, 03
  and 23 are identical; 06 differs only by D12's Stop and Start, 24 only by
  D2's order and D6's base at Stop.
- **Random scripts:** 9,500 undo-free scripts (2,000 new from
  `gen_scripts.py --no-undo`, seeds 601-604, and 7,500 from the review), 7.48
  million events and 32 hours of audio, with 225 of Movy's D5 panics in 217
  of them: 9,500 identical in compat, events and sets. Through `fm1-render
  --compat`, 1,020 of 1,020 identical. With D1's frames (`--compat-frames`
  against the oracle's `--frames tick`), 1,300 of 1,300 identical, 200 of
  them at 48 kHz in 7-frame blocks.
- **The default mode** runs all 9,500 under the checking build (`fm1-seq-check`,
  which traps on a stale fire-tick index) with every note-on closed by its
  note-off; 2,000 of them, in both modes, under ASan and UBSan without a
  report.
- **Mutants:** 47 single changes to the core (the review's 31, two of them
  rewritten for the new code, and 16 for D1 under an external clock, D4-D13,
  compat's panic, the event buffer and the `movy1` integers); the suite fails
  on every one.
- **Capture, packed (2026-10-01):** 2,300 new random scripts with Capture
  (`gen_scripts.py --capture --no-undo`, seeds 901–905: 2, 4, 8 and 16
  tracks, 44,118 and 48,000 Hz, blocks of 7, 64 and 128; 3,061 `cap`
  commands, of which 225 stopped and 911 playing captures wrote a take) and
  the long-cycle test's script: identical to Movy, events and sets, from
  Apple clang under ASan and UBSan and from GCC 12 at 64 and 32 bits. 121
  stress scripts aimed at the packing (runs of up to 27 minutes that move
  both bases, MIDI clock restarts that keep the ring, tempo changes that
  stretch a window over 44,000 ticks, cycles past 2^20, full rings, 44.1 to
  384 kHz at 20 BPM): identical to the 20-byte layout in all three modes but
  for the 384 kHz one, the documented limit. 71 of them run through the
  oracle (the other 50 restart the transport without a clock, which its
  whole-block and frame-by-frame cross-check refuses): 70 identical to
  Movy. Four mutants of the packing (the cycle flag, the tick base, and
  either base's repacking) each fail the new tests.
- **Capture, reviewed (2026-10-01):** the 2,301 scripts above rerun through
  the oracle, and the 9,500 of the random-script verdict (1,732 of them
  with Capture: 290 stopped and 928 playing captures that wrote a take),
  identical to Movy through `fm1-seq` and `fm1-seq-check`; the 2,301 also
  from Apple clang under ASan and UBSan and from GCC 12 at 64 and 32 bits,
  with no warnings. Six mutants passed the first tests: the frame, master
  tick, playhead and cycle each one bit narrower, the track 3 bits, and a
  take timed from its first event rather than its first note-on. The edge
  tests (above) fail on each, and the suite on 15 more mutants of the
  packing and the ring (pitch and velocity one bit narrower, no cycle flag,
  no used bit, either base not repacked, the tick base on the newest event,
  either base never moved, absolute ticks only, the gap rule against the
  oldest event, the gap rule after the stale rule (in the checking build),
  no gap rule, a full ring that does not drop, the window's boundary off by
  one). The edge tests' scripts, through the oracle, are identical to
  Movy.

## What M2 and later still need

- **Engine API v2** (docs/13 §6): done in part (docs/15 stage S7a). Every
  parameter has a stable uid, flags (LATCH, SMOOTH, NOLOCK, MOD, INPUT), a
  unit and an abbreviation; lanes resolve to uids; Macro's Model is refused
  as NOLOCK (M2's exit test). Still to come: SMOOTH's ramp inside the
  engines (S7b), tempo and a beat position in `fm1_host_t`, and the virtual
  FM-1 showing uids and flags in its catalogue.
- `FM1_KIND_MIDI_FX` for per-track MIDI effects.
- The command ring between the UI and audio tasks, and undo (binary
  per-clip snapshots in a byte budget, docs/13 §5) with the UI, stage M4;
  D14 with it.
- External clock: F2/FB handling beyond Movy's.
- Stage B: the cycle budget on pi32v2 with tools/seq_bench.py's scripts, and
  the moves listed under CPU.

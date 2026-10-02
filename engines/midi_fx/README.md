# engines/midi_fx/ — MIDI effects: the arpeggiator core

`fm1_arp` is the arpeggiator of Lunar Modulator, open firmware for the
M-VAVE FM-1. It is a heap-free C99 library on note events: held keys and
clock ticks go in, note-ons and note-offs with frame offsets come out. It is
the core that the options note
([`notes/2026-10-01-arp-modulation-effects-options.md`](../../notes/2026-10-01-arp-modulation-effects-options.md)
§2) recommends:
- after Yarns' `ClockArpeggiator` (Emilie Gillet, MIT): directions, octave
  range, Yarns' 22 rhythm masks, Euclidean length, fill and rotate, gate in
  clock ticks, latch;
- with the extra note orders and the trig-stepped rate of MCL's
  `ArpSeqTrack` (Justin Mammarella, BSD-3);
- with seeded, loopable random modifiers after Super Arp (Handcrafted Media,
  MIT).

It reimplements those designs; it compiles no upstream code. Its randomness
is its own seeded generator, never stmlib's global `Random`, so Macro's
reference renders stay untouched. Sources, lines and notices are in
[CREDITS.md](CREDITS.md).

**Status.** It is built and tested on the desktop
(`tests/test_engine_arp.py`) and is **not wired** into `fm1-render`, the
simulator or the FM-1 app yet. That needs the MIDI-effect contract of API v2
(docs/13 M2). The intended contract is described below.

```bash
make -C engines build/fm1-arp
engines/build/fm1-arp --list                       # parameters, names, rates, rhythm tables (JSON)
printf 'clock 0 100 1 192\n@0 set mode up-down\n@0 set octaves 2\n@0 on 60 100\n@0 on 64 100\n@0 on 67 100\n' \
  | engines/build/fm1-arp                          # one JSON line per note event
python -m pytest tests/test_engine_arp.py
```

## Files

| Path | What |
| --- | --- |
| `fm1_arp.h` | The API: events, parameters, enums, `fm1_arp_process()` |
| `fm1_arp.c` | The core: held keys, note orders, steps, chance, the note ledger |
| `arp_rhythm.c` | Yarns' 22 rhythm masks (regenerated, with Yarns' MIT notice) and the Euclidean generator |
| `arp_tool.c` | `fm1-arp`, the desktop test tool: a timed script in, JSON lines out |
| `CREDITS.md` | Design sources and their notices |
| `../mk/midi_fx.mk` | The build fragment |

## The API

```c
void *mem = /* fm1_arp_size() bytes, 8-byte aligned, any contents */;
fm1_arp_t *arp = fm1_arp_create(mem, 96);           /* host ticks per quarter: 24, 48 or 96 */
fm1_arp_set_param(arp, FM1_ARP_P_MODE, FM1_ARP_MODE_UP_DOWN);
/* each block: input events and tick frames, both ascending */
uint32_t n = fm1_arp_process(arp, in, n_in, ticks, n_ticks, out, 64);
```

- **Inputs**, as `fm1_arp_ev_t {frame, kind, a, b}`:
  - `NOTE_ON` (key, velocity; velocity 0 is a note-off) and `NOTE_OFF`;
  - `SUSTAIN` (the hold pedal);
  - `STEP` (one step, in RATE TRG);
  - `RESET` (restart the pattern: the next tick is step 0);
  - `FLUSH` (note-offs for everything sounding);
  - `PANIC` (FLUSH, and forget every key);
  - `PARAM` (id, value).
- **Ticks** are the frames of the host's clock ticks in this block.
- **At one frame**, input events come before the tick, so a key pressed on a
  tick plays on it.
- **Outputs** are `NOTE_ON` and `NOTE_OFF`, ascending by frame. At one frame
  the order is: note-offs whose gate ran out, then the step's note-offs and
  note-ons. A note that would start while the same key sounds ends it first.
- **No tempo inside.** The core counts ticks, never samples. Each output
  carries the frame of the event or tick that caused it, so the output is the
  same whatever the host's block size [verified: tests at blocks of 1, 7, 64,
  128, 500, 1,000 and 65,535 frames].
- **Memory.** 728 bytes on a 64-bit desktop [verified: `fm1-arp --list`].
  The instance holds no pointers, so a 32-bit build is the same: 728 bytes,
  and the three golden streams byte for byte [verified: GCC 12 in an i386
  Debian container, 2026-10-02; CI's 32-bit job runs the whole test file].
  No allocation: the tests check the objects' symbols. Output does not
  depend on the memory's prior contents [verified].

## The note ledger

Every note-on the core sends gets exactly one note-off, whatever happens in
between: parameters changed mid-note, keys released, latch toggled, the
rate switched to TRG and back, PANIC, RESET.
- The ledger holds the pitch actually sent, up to 32 notes. When it is full,
  the oldest note is ended to make room (`stolen` in the stats).
- With an output buffer of at least `FM1_ARP_OUT_MIN` (64), nothing is
  deferred in normal use. With less, a note-off that does not fit is sent at
  the start of the next call, and a note-on that does not fit is dropped and
  counted.
- The host must send `FLUSH` when the transport stops or the arp is bypassed,
  because gates count down only on ticks.
- A seeded fuzz test (40 scripts) checks this at block sizes 1–500 and output
  buffers of 1, 2 and 64 events [verified].

## Parameters

Values are integers in each parameter's own range. A host maps 7-bit
sequencer locks onto them (the options note wants every arp parameter
lockable).

| Id | Name | Range (default) | What |
| --- | --- | --- | --- |
| 0 | `mode` | 0–21 (up) | Note order; see below |
| 1 | `order` | pitch, played, reverse (pitch) | How held keys are listed before the order runs |
| 2 | `octaves` | 1–4 (1) | |
| 3 | `oct_mode` | span, up, down, up-down, random (span) | How octaves combine with the order |
| 4 | `rate` | trg, 1/32t … 1/1 (1/16) | Step length; TRG takes steps from the host |
| 5 | `gate` | 1–200 % (50) | Of the step; over 100 overlaps the next note |
| 6 | `swing` | 50–80 % (50) | Odd steps start (swing − 50) × step / 60 ticks late, fm1_seq's formula (docs/13 R6) |
| 7 | `pattern` | 0–22 (0) | 0 plays every step; 1–22 are Yarns' masks 0–21 |
| 8 | `euclid_len` | 0–32 (0) | 0 off; otherwise Euclid replaces `pattern`, as in Yarns |
| 9 | `euclid_fill` | 0–32 (0) | Onsets, at most the length |
| 10 | `euclid_rotate` | 0–31 (0) | |
| 11 | `latch` | 0–1 (0) | |
| 12 | `join` | now, next pass (now) | When keys added to a playing chord join it |
| 13 | `sync` | free, key (key) | Key: the first key into an empty chord restarts the pattern |
| 14 | `repeat` | 1–8 (1) | Steps per note before the order moves on |
| 15 | `ratchet` | 1–4 (1) | Notes inside one step |
| 16 | `ratchet_prob` | 0–100 % (100) | Chance that a step ratchets |
| 17 | `prob` | 0–100 % (100) | Chance that a step plays; a silent step still moves the order |
| 18 | `chord_prob` | 0–100 % (0) | Chance that a step plays the whole chord |
| 19 | `oct_jump` | 0–100 % (0) | Chance of one octave up |
| 20 | `velocity` | 0–127 (0) | 0 as played; otherwise fixed |
| 21 | `vel_spread` | 0–127 (0) | A seeded offset within ± this |
| 22 | `gate_spread` | 0–100 (0) | A seeded offset within ± this many gate points |
| 23 | `loop` | 0–64 (0) | The phrase restarts every LOOP steps, random draws included |
| 24 | `seed` | 0–65535 (0) | Saved with the preset |

Rates, in ticks at 96 PPQN: 1/32t 8, 1/32 12, 1/16t 16, 1/16 24, 1/8t 32,
1/16d 36, 1/8 48, 1/4t 64, 1/8d 72, 1/4 96, 1/2t 128, 1/4d 144, 1/2 192,
1/1t 256, 1/2d 288, 1/1 384. All are multiples of 4, so a 24 PPQN clock
(external MIDI) gives the same step times [verified: tests].

## Note orders

On four held keys s0 < s1 < s2 < s3, one octave. These are the golden orders
of `test_each_mode_order`.

| Mode | One pass | From |
| --- | --- | --- |
| up | s0 s1 s2 s3 | Yarns, MCL |
| down | s3 s2 s1 s0 | Yarns, MCL |
| up-down | s0 s1 s2 s3 s2 s1 | Yarns, MCL (ends once) |
| down-up | s3 s2 s1 s0 s1 s2 | MCL |
| up&down | s0 s1 s2 s3 s3 s2 s1 s0 | MCL "up-n-down" (ends twice) |
| down&up | s3 s2 s1 s0 s0 s1 s2 s3 | MCL |
| converge | s0 s3 s1 s2 | MCL |
| diverge | s2 s1 s3 s0 | converge reversed: inside out |
| conv-div | s0 s3 s1 s2 s1 s3 | MCL: in, then back out, ends once |
| thumb-up | s0 s1 s0 s2 s0 s3 | the lowest key between the others |
| thumb-down | s0 s3 s0 s2 s0 s1 | |
| pinky-up | s0 s3 s1 s3 s2 s3 | the highest key between the others |
| pinky-down | s2 s3 s1 s3 s0 s3 | |
| up-top-oct | up; each extra octave lifts only the last note | MCL "UPP" |
| down-low-oct | down; each extra octave lifts only the last note | MCL "DOWNP" |
| up-alt-oct | up; each extra octave lifts every other note | MCL "UP2" |
| down-alt-oct | down; the same | MCL "DOWN2" |
| crawl | s0 s2 s1 s3 s2 s3 | each key, then the one two above |
| random | any key, each step | Yarns, MCL "RND2" |
| shuffle | each key once per pass, in a seeded order | options note §2.2 |
| walk | a seeded step to a neighbour | options note §2.2 |
| chord | every key at once | Yarns |

**Octaves.**
- `span` (the default) runs the order over every octave as one list, as
  Yarns does: up-down over two octaves is s0 … s3, s0+12 … s3+12, then back
  down.
- `up`, `down` and `up-down` play one pass per octave, in that octave order,
  as MCL does.
- `random` plays each pass in a seeded octave.
- The four `*-oct` modes have their own octave rule and ignore `oct_mode`.
- Notes above 127 fold down by octaves, as in Yarns.

**Yarns parity.** With `oct_mode span`, the modes up, down and up-down, and
up with `order played` (Yarns' AS_PLAYED) play exactly Yarns' notes and
rests. The test checks this step for step against a Python rewrite of
`ClockArpeggiator`: 1–5 keys, 1–4 octaves, four of the 22 masks and random
Euclidean settings, 100 cases [verified]. The masks and Euclidean tables
equal Yarns' generated tables [verified against `reference/mi-eurorack` at
08460a6].

**Where this differs from the sources, on purpose:**
- Yarns' pattern numbers are shifted by one, because pattern 0 here plays
  every step; Yarns has no such pattern, and its pattern 0 plays every other
  step.
- A mode change keeps the position in the pass, as Yarns keeps its note
  index when the direction changes (`part.cc` 704–707), but here the pass is
  rebuilt for the new order at the next step.
- MCL's code gives PINKUP and THUMBUP the same order and uses the low key
  for PINKDOWN. Here thumb is the lowest key and pinky the highest, as the
  names say.
- MCL's RND draws one random sequence per chord and loops it. Here that is
  `random` with `loop` set to the sequence length. MCL's DIV is converge
  started from the top; here `diverge` runs from the middle out.

## Rhythm, timing and chance

- **Steps.** In a rate mode a step lasts the rate's ticks, adjusted by swing.
  The rhythm counter advances on every step and reads one bit of the mask.
  The note order advances only on steps that play, as in Yarns.
- **Gate** is a percentage of the step, or of the ratchet's share of it,
  counted in ticks, with at least one tick.
- **Ratchets** split the step evenly in ticks. When the step has fewer ticks
  than ratchets, the count drops to the tick count.
- **Repeat** holds each note of the order for that many played steps.
- **RATE TRG** (after MCL's `ARP_RATE_TRIG`): `STEP` events start steps, so
  `fm1_seq`'s swung trigs can drive the arp; this is the swing hook.
  - Gates and ratchets use the measured ticks between the last two steps.
  - Until two steps have been seen, each note lasts until the next step.
- **Randomness.**
  - Each draw is a pure function of (seed, purpose, step index): a
    splitmix64 finalizer, then one xorshift64* round, the generator of
    `fm1_seq` (docs/13 R7).
  - So the same seed replays the same arp, and no draw depends on how many
    came before it.
  - With `loop` set, the step index wraps every `loop` steps, and the note
    position, octave pass, rhythm counter, walk and shuffle restart with it.
    The whole phrase repeats exactly; the options note's LOOP is Super
    Arp's modifier loop and Deluge's LOCK in one control.
- **Golden streams.** Three scripts are pinned in
  `tests/fixtures/arp/golden.json`, so a seed replays the same notes on
  every build and after any refactor. `FM1_ARP_REGOLD=1` rewrites them,
  deliberately.

## Latch, hold, join and sync

- **Latch**, as in Yarns (`part.cc` 82–95):
  - released keys keep playing;
  - the next key pressed drops every latched key that is no longer down;
  - keys pressed while others are down join them.
  - So a chord played after every key is up replaces the old one.
- Turning latch off drops the released keys at once (Yarns waits for the
  next key).
- **The hold pedal** keeps released keys like latch, but new keys join
  instead of replacing. Lifting it drops the released keys.
- **Join, next pass**: a key added to a chord that is already playing waits
  until the current pass ends (after Bogaudio's behaviour, as the options note
  describes it [reported]). Keys of one chord that arrive before its first
  step all join at once.
- **Sync, key**: the first key into an empty chord restarts the pattern; it
  plays at the next tick, at most one tick late (5.2 ms at 120 BPM and 96
  PPQN [inferred]). **Sync, free**: the grid runs on, and the key waits for
  the next step. `RESET` rejoins the grid on the host's Play or bar.

## The intended host contract (not built yet)

This is how the core is meant to sit in the host once API v2 exists (docs/13
M2; options note §2.3; DEVELOPERS.md, "MIDI effects").
- **Placement.** Panel keys, USB-MIDI in and `fm1_seq` NOTE events go into
  the arp. The arp's output goes to the engine's `note_on` and `note_off`.
  It is the first `FM1_KIND_MIDI_FX` (reserved in `fm1_engine.h`), so ARP
  and SEQ can run together.
- **Calls.** The slot gets one `process()` per block. It takes the block's
  frame-stamped input events, the block's tick frames, and at least 64
  output slots. Note-offs are never dropped.
- **The clock** is `fm1_seq`'s 96 PPQN master tick, each tick at its own
  frame (D1). External MIDI clock comes in through `fm1_seq`. While the
  transport is stopped, the host keeps ticking from its tempo accumulator,
  so the arp free-runs.
- **Transport.** The host sends `RESET` at Play, so the arp rejoins the
  bar, and `FLUSH` at Stop and on bypass.
- **Order at one frame:** note-offs, reverts, locks (parameter events), then
  the arp's steps and note-ons (docs/12 line 281).
- **Parameters** become API v2 typed parameters with uids. A sequencer lane
  locks them per step through 7-bit values mapped onto each range.
- **Recording** stores the keys before the arp, so the arp replays them;
  "print arp" can come later. The arp's notes stay off MIDI out unless asked.
- **Modulation** (stage S4): the step index and the step's random value
  become matrix sources.

## Not done yet

- Super Arp's pattern strings, accent velocity patterns and progression
  presets.
- The keyboard transposing a latched arp; Loom's JUMP and GRID modes.
- Stock's seven arp modes as named presets (options note §8, question 7).
- The ARP pages on the panel (options note §2.4) and the screen labels.
- Cycle counts on pi32v2: the arp is control-rate work, about 1 % of a core
  or less [inferred], unmeasured until the dev board (docs/14).

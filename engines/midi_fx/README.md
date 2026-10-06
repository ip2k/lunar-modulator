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

**Status.** Built and tested on the desktop (`tests/test_engine_arp.py`),
and since 2026-10-06 a MIDI effect of engine API v3, `arp`
(`arp_engine.c`), which fm1-render (`--mfx`) and the virtual FM-1 (its ARP
button and pages) run in front of a sound ([In the hosts](#in-the-hosts)).
Nothing runs on an FM-1 yet.

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
| `arp_engine.c` | The core as the MIDI effect `arp` (engine API v3, `FM1_KIND_MIDI_FX`): its parameters on the ARP pages, `process()` on the host's ticks |
| `registry.c` | The MIDI effects' registry (`fm1_midi_fxs`, `fm1_midi_fx_find`); the GPL ones under `#if FM1_GPL_MODS` |
| `acid_gen.c` | Acid Gen, fm1-x0x's TB-3PO as a MIDI effect: built only with the GPL switch on ([below](#acid-gen-gpl)) |
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
  - `NOTE_ON` (key, velocity; velocity 0 is a note-off) and `NOTE_OFF`,
    with the note's origin in the velocity's high byte (`FM1_MIDI_EV_B`:
    0 played live, `FM1_MIDI_SRC_SEQ` a sequencer track);
  - `SUSTAIN` (the hold pedal);
  - `STEP` (one step, in RATE TRG);
  - `RESET` (restart the pattern: the next tick is step 0);
  - `FLUSH` (note-offs for everything sounding);
  - `PANIC` (FLUSH, and forget every key);
  - `STOP` (the sequencer stopped: forget its keys and end their notes);
  - `PARAM` (id, value).
- **Ticks** are the frames of the host's clock ticks in this block.
  `fm1_arp_process_at` also takes the host sequencer's transport: while it
  runs, which of its ticks the first one is, counted from its Start, so the
  steps lock to its grid ([Locked to the beat](#locked-to-the-beat)).
- **At one frame**, input events come before the tick, so a key pressed on a
  tick plays on it.
- **Outputs** are `NOTE_ON` and `NOTE_OFF`, ascending by frame. At one frame
  the order is: note-offs whose gate ran out, then the step's note-offs and
  note-ons. A note that would start while the same key sounds ends it first.
  A note made by a key only the sequencer gave carries the sequencer's
  origin; any other is live.
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
| 6 | `swing` | 50–80 % (50) | Odd steps start (swing − 50) × step / 60 ticks late, fm1_seq's formula (docs/13 R6). Not an engine parameter: the host sets it from the set's swing every call (`fm1_midi_fx_ctx_t.swing`; owner, 2026-10-06) |
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
  - A `STEP` on a tick's frame runs that tick's gates first, so the notes
    they end go out before the step's note-ons, as at a rate's step.
  - In the hosts, the stage sends one `STEP` at each frame where the
    sequencer starts notes for the sound, after them; keys alone send none.
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
- **Origins** (owner, 2026-10-06). Each held key remembers whether it was
  played live or given by the sequencer, and whether each still holds it
  down. A key latches against the later keys of its own origin only: the
  sequencer's next note replaces its own latched notes, a new chord played
  by hand replaces the hand's, and the arp plays the two together. A key
  both played and given stays until both let go.
- **STOP** (the sequencer's Stop) takes back what the sequencer gave: its
  keys leave the chord, held or latched, and the notes they made end at
  once, with what was left of the step's ratchets from them; a note
  waiting for a STEP ends too, since no trig comes while stopped. Keys
  played live, held or latched, play on.
- Turning latch off drops the released keys at once (Yarns waits for the
  next key).
- **The hold pedal** keeps released keys like latch, but new keys join
  instead of replacing. Lifting it drops the released keys.
- **Join, next pass**: a key added to a chord that is already playing waits
  until the current pass ends (after Bogaudio's behaviour, as the options note
  describes it [reported]). Keys of one chord that arrive before its first
  step all join at once.
- **Sync, key**: the first key into an empty chord restarts the pattern
  (its rhythm counter, Loop and chances); with the host's sequencer
  stopped it plays at the next tick, at most one tick late (5.2 ms at 120
  BPM and 96 PPQN [inferred]), and while it runs at the next step of its
  grid. **Sync, free**: the pattern runs on, and the key waits for the next
  step: the grid's while the sequencer runs (so a Euclidean rhythm stays
  on the bar from Play), the arp's own while it is stopped. Either way a
  new chord's notes start from the first. `RESET` rejoins the grid on the
  host's Play or bar.

## Locked to the beat

Owner, 2026-10-06: whenever the host's sequencer runs, the arp's steps fall
on its grid. `fm1_arp_process_at` gets the transport with each block: while
it runs, the tick the block's first one is, counted from the sequencer's
Start (tick 0, its first downbeat).
- **The grid.** A step of the rate starts where that tick is a multiple of
  the step's length (24 ticks for a 1/16 at 96 PPQN); swing starts the odd
  ones (swing − 50) × step / 60 ticks later, fm1_seq's formula, by their
  place on the grid. Straight and triplet rates divide the bar; a dotted
  rate or 1/1T meets the bar line again after a few bars (1/16D every
  three).
- **A key between steps waits** for the grid's next step, Sync or not; so
  does an arp switched on mid-bar. Its pattern's own count (note order,
  rhythm, Loop) is as Sync leaves it: at free it counts the steps it
  played, so its rhythm keeps to the bar when the arp has been on since
  Play; one switched on later (or off and on again) counts on from where it
  stood, and the next Play puts it back on the bar.
- **A rate change** takes the new rate's grid at once: its next step.
- **Stopped**, the steps run on from the last one, as before; a first key
  with Sync at key starts at the next tick.
- **Cost.** One 64-bit remainder a block (the tick by `GRID_PERIOD`, 4,608,
  a multiple of every rate's pair of steps), then 32-bit arithmetic a tick;
  no new state, so the instance is still 728 bytes [verified: `fm1-arp
  --list`].
- **The tool.** `fm1-arp`'s `@FRAME run POS` says the sequencer runs from
  FRAME with its tick POS next, and `@FRAME halt` that it stopped; `on` and
  `off` take `seq` for the sequencer's notes, and `@FRAME stop` is STOP.

## In the hosts

Since 2026-10-06 the core runs in fm1-render and the virtual FM-1 through
engine API v3's MIDI-effect contract (`engines/include/fm1_engine.h`,
"MIDI effects"; DEVELOPERS.md, "MIDI effects"; engines/README.md, "MIDI
effects").
- **The wrapper** (`arp_engine.c`) is an `fm1_midi_fx_t`: the core's 25
  parameters as engine parameters, each with a uid (the core's id plus 1,
  pinned in `tests/fixtures/param-uids.json`), in knob order on seven pages
  (below), and `process()`, which hands the block's events and ticks to
  `fm1_arp_process`. A list's value is its entry from 0, so Octaves,
  Ratchet and Repeat read one less than the core's count; a number rounds
  half up and NaN is its default. The events are one type
  (`fm1_arp_ev_t` is `fm1_midi_ev_t`, `include/fm1_midi_ev.h`), with the
  same codes. The instance is 736 bytes (the core's 728, to 16).
- **Placement.** The host stage (`include/fm1_mfx_host.h`,
  `seq/mfx_host.c`) keeps a chain of up to four MIDI effects in front of
  each sound unit. While the arp is on, the keys, MIDI IN, fm1-render's
  `--note` and the sequencer's notes for that sound go into it; its output
  reaches the sound's `note_on` and `note_off` at its own frames, merged
  into the block the bridge dispatches. So ARP and SEQ run together.
- **The clock** is `fm1_seq`'s 96 PPQN master tick, each tick at its own
  frame (D1), from the sequencer's integer clock as the block began. While
  the transport is stopped the clock's sum runs on at the set tempo, so the
  arp free-runs on the same grid; without a sequencer the stage runs its own
  at fm1-render's `--tempo`. An external MIDI clock (off the grid) puts the
  block's ticks at its first frame.
- **Swing** is the set's (owner, 2026-10-06): the stage reads the
  sequencer's `swing` every block and hands it to the arp in the context
  (`fm1_midi_fx_ctx_t.swing`), which sets the core's `swing`; without a
  sequencer it is fm1-render's `--swing` (50 without it). The arp has no
  Swing parameter of its own: its uid 7 is retired, and its last name stays
  in `engines/aliases.json`'s `retired`, so a file that names it reads to the
  same records as before (the value passes by uid, as `#7`) and the arp
  drops it.
- **Transport.** Start reaches the arp as `RESET` and Stop as `STOP`, at
  their frames (with `FLUSH` after it in the sequencer's compat mode,
  whose clock gives no tick while stopped; after an external clock's Stop
  the clock runs on at the tempo). While the sequencer plays the
  stage gives the arp its tick position, so the steps lock to the beat. A
  bypass sends `PANIC` at once, between blocks, and its note-offs go
  straight to the sound; so do a new engine on the sound, a panic, and a
  sequencer reset or import.
- **Origins.** The stage marks the sequencer's notes as such, and hands the
  sounds the bare velocity.
- **Notes are never left hanging.** A note-off follows its note-on: into the
  arp when the arp took the note-on, else straight to the sound.
- **Recording** stores the keys before the arp (owner, 2026-10-05), so the
  arp plays a recorded part again; "print arp" can come later. The arp's
  notes stay off MIDI out.
- **The pages** (the options note §2.4, and three more for the rest):

  | Page | KNOB1 | KNOB2 | KNOB3 | KNOB4 |
  | --- | --- | --- | --- | --- |
  | PLAY | Mode | Rate | Gate | Octaves |
  | RHYTHM | Pattern | Fill | Rotate | Length |
  | CHANCE | Chance | Ratchet | Vel Spread | Loop |
  | FEEL | Oct Mode | Velocity | Join | |
  | MORE | Order | Repeat | Chord % | Oct Jump |
  | KEYS | Latch | Sync | Ratchet % | Gate Sprd |
  | SEED | Seed | | | |

  Fill, Rotate and Length are the Euclidean parameters, Chance is `prob`,
  Vel Spread `vel_spread` and Gate Sprd `gate_spread`.
- **Stock's presets.** The virtual FM-1's ALGORITHM steps the stock FM-1's
  arp modes as presets of Mode and Order (owner, 2026-10-05): Up, Down,
  Up/Down, Down/Up, Random and Played [reported: AL-255's FM-1-RE,
  `docs/io/05-midi.md` §6.3; stock's Random shuffles the held notes once a
  pattern, so it is Shuffle here; the seventh, off, is ARP].

## Acid Gen (GPL)

`acid_gen.c` is a second MIDI effect, **Acid Gen** (`acid-gen`): TB-3PO,
the generator of 303 lines in fm1-x0x by Charles Vestal, which ports
schwung-tb3po and, through it, the `TB_3PO` applet of the Phazerville
Hemisphere Suite (djphazer and contributors). The generator is vendored in
`../third_party/fm1-x0x/seq/` (GPL-3.0-only, `UPSTREAM.md`), so Acid Gen is
**built only while the GPL switch is on** (`FM1_GPL_MODS`; its sources in
`../mk/fm1-x0x.mk`, its registry line under `#if FM1_GPL_MODS`). It is made
for Acid Bass and plays in front of any sound.

- **The line** is a function of the parameters alone: TB-3PO writes up to
  32 steps from Seed (rests by 1 − Density, notes of the scale within
  Octaves octaves, the root often on the beat, accents and slides by their
  chances, no slide into a rest), then re-rolls about a quarter of them
  Mutations times, continuing the line's own random stream. A project saves
  it as numbers. Any change of the line's settings rebuilds it from the same
  seed at the next step. Mut Every re-rolls once more every that many
  passes while it plays (X0X's auto-mutate), until Start or a rebuild.
- **Playing it**, as fm1-x0x's sequencer plays a 303 part (`fire_bass`): a
  step every 24, 16, 12 or 32 ticks (1/16, 1/16T, 1/32, 1/8T), forward,
  reverse, ping-pong or random; a note holds half its step; a step that
  slides holds into the next, whose note-on comes first, and the held note
  ends one tick later, so a bass that slides on legato (Acid Bass) slides;
  a slide into the same note is a tie. Accents are velocity 118, plain notes
  72 (TB-3PO's numbers; Acid Bass accents from 100).
- **The keys.** Keys = Transpose: the line plays while a key is held, from
  step 1 when the first key goes down, with its root note moved to the
  newest key; letting go stops it unless Latch is on. Keys = Run: it plays
  while the transport runs, from step 1 at Start, transposed by a held key
  (the sequencer's notes for the sound count as keys). The keys never sound
  themselves. Root and Scale may follow the project key (`ctx.key_root`,
  `key_scale`): Major, else Minor.
- **The contract** as the arp's: ticks, never samples; every note-on gets one
  note-off (a note-off that does not fit goes out first in the next call);
  FLUSH, PANIC and RESET as `fm1_engine.h` says. No allocation, stdio or
  libm. 256 bytes an instance (248 of state, no pointers, so the same on
  32 bits) [verified 2026-10-06: `sizeof`]; on pi32v2 its code and TB-3PO's
  take 5.9 KB at `-O2`, 4.6 KB at `-Oz` [verified: the JieLi compile check,
  2026-10-06].

| Page | KNOB1 | KNOB2 | KNOB3 | KNOB4 |
| --- | --- | --- | --- | --- |
| LINE | Density, 0–100 %, 70 | Accent, 0–100 %, 40 | Slide, 0–100 %, 25 | Octaves, 1–3, 2 |
| KEY | Root: Project, C … B; A | Scale: Project, Minor, Phrygian, Harm Minor, Min Pent, Dorian, Major; Minor | Octave (the root's), 0–4, 1 (A1) | Keys: Transpose, Run |
| PLAY | Rate: 1/16, 1/16T, 1/32, 1/8T | Length, 1–32 steps, 16 | Direction: Forward, Reverse, Ping-Pong, Random | Latch: Off, On |
| SEED | Seed, 0–65,535, 48,879 (TB-3PO's 0xBEEF) | Mutations, 0–255, 0 | Mut Every, 0–16 passes (0 off) | |

Every list is LATCH; the numbers LATCH and MOD (no route reaches a MIDI
effect yet). In the virtual FM-1, ALGORITHM on the ARP pages puts it in the
sound's MIDI-FX slot, after the stock presets.

**Checks** (`tests/test_engine_acid_gen.py`) [verified 2026-10-06]: the
notes it plays are TB-3PO's line (`test/tb3po_line.c`, built against the
vendored file) as fm1-x0x plays it, tick for tick, for three settings, every
rate, reverse and ping-pong, and Mut Every; the vendored generator writes
fm1-x0x's own lines (with `reference/fm1-x0x`); a key transposes; Latch;
Run with the transport; the project key; the same output at host blocks of
1, 7, 64 and 448; every note-on has its note-off; a bypass ends the note.

## Not done yet

- Sequencer locks and modulation routes on the arp's parameters; the step
  index and the step's random value as matrix sources (options note S4).
- Super Arp's pattern strings, accent velocity patterns and progression
  presets.
- The keyboard transposing a latched arp; Loom's JUMP and GRID modes.
- Using the project key (the context's `key_root` and `key_scale`, which
  the global page sets since 2026-10-06): the arp reads none of it.
- More MIDI effects in the other three slots of each chain (chord, scale,
  repeat), and their panel.
- Cycle counts on pi32v2: the arp is control-rate work, about 1 % of a core
  or less [inferred], unmeasured until the dev board (docs/14).

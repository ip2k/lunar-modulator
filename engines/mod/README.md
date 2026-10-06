# engines/mod — modulation: the runtime and its primitives

Two layers, both heap-free C99 with no libm:

- **The runtime** (docs/16 stage MG1): a rack of up to 8 modulation
  modules inside a 32-slot matrix of 1:1 cables, run once per control tick
  of 32 frames. Module outputs are sources and module parameters and gate
  inputs are destinations, so a chain A → B → C → D is three ordinary
  slots. `include/fm1_mod.h` is its API, `include/fm1_mod_host.h` puts it on
  the sequencer's host bridge, and `fm1-render --mod` plays it. The first
  three module kinds are **LFO**, **Envelope** and **Chance**; stage MG2
  adds thirteen more, documented in [kinds.md](kinds.md): Function, Bounce,
  Register, Coin, Divide, Burst, Slew, Quantize, Compare, Logic, Calc, Mix
  and Filter. The virtual FM-1 hosts it, with the RACK, MATRIX and CHAIN
  pages (docs/16 MG3; sim/web/README.md, "Modulation"), and the user
  manual's chapter 8 describes them.
- **The primitives** (`fm1_mp.h`): an LFO, a multistage envelope, a slew
  limiter, sample-and-hold, a Turing-machine register and a clock
  divider/multiplier, after §3–§5 of the arpeggiator, modulation and effects
  options note of 2026-10-01. The module kinds wrap them.

```bash
make -C engines                                  # fm1-render, fm1-mod-core-test, fm1-mod
engines/build/fm1-render --list-mod              # the kinds, system sources and host parameters (JSON)
printf 'mod 1 lfo rate=0.6\nslot 1 lfo1 > snd:Timbre amt=20\n' > /tmp/a.mod
engines/build/fm1-render --engine macro --note 0:60:100:1.5 --seconds 2 --mod /tmp/a.mod \
    --log-mod /tmp/a.jsonl --out /tmp/a.wav     # one JSON line per tick in the log
python -m pytest tests/test_engines_mod_runtime.py   # the runtime's tests
python -m pytest tests/test_engines_mod.py       # the primitives' tests
python -m pytest tests/test_engines_mod_kinds.py # the MG2 kinds' tests (kinds.md)
python3 engines/mod/gen_curves.py                # regenerate mod_curves.c (--check: verify)
python3 engines/mod/gen_tables.py                # regenerate mp_tables.c (--check: verify)
```

## The runtime

### Files

| Path | What |
| --- | --- |
| `../include/fm1_mod.h` | The API: the module kind contract, slots, the runtime, its clock and its state, prefix `fm1_mod_` |
| `../include/fm1_mod_host.h` | The glue that makes a runtime the bridge's control-rate hook (`fm1_mod_glue_t`) |
| `mod_int.h` | The state's layout and the helpers the core and the kinds share (not API) |
| `mod_core.c` | Creation, the rack and its 8 KB arena, bases (rule M1), system sources, the tick |
| `mod_plan.c` | The planner: which slots run, the module order, delayed cables |
| `mod_registry.c` | The kinds, the system sources and the host unit's parameters |
| `mod_curves.c`, `gen_curves.py` | The 8 slot curves as 33-point tables, and the script that writes them |
| `mod_glue.c` | The bridge hook (`fm1_mod_host.h`) |
| `kinds/mod_lfo.c`, `mod_env.c`, `mod_chance.c` | LFO, Envelope and Chance |
| `kinds/mod_function.c` … `mod_filter.c`, `kinds/kinds_int.h` | MG2's thirteen kinds and the helpers they share ([kinds.md](kinds.md)) |
| `mod_mi.c`, `.h`, `mod_mi_tables.c`, `gen_mi_tables.py` | C ports of Peaks' bouncing ball, pulse shaper and randomizer and Braids' quantizer, their tables, and the script that writes them from the vendored originals |
| `../host/mod_script.c`, `.h` | `fm1-render`'s text format for racks and slots (desktop only) |
| `../test/mod_core_test.c` | `fm1-mod-core-test`: the planner fuzz, chains, feedback, fills, NaN, M1–M4 |
| `../test/mod_kinds_test.c`, `mod_mi_ref.cc` | `fm1-mod-kinds-test` (the MG2 kinds) and `fm1-mod-mi-ref` (the ports against the originals) |
| `../../tests/test_engines_mod_runtime.py` | The runtime through `fm1-render` and the C test |
| `../../tests/fixtures/mod-uids.json` | Every kind's uids and ports, the system source ids, pinned |
| `../../tests/test_engines_mod_kinds.py`, `fixtures/mod-golden.json` | The MG2 kinds' tests and golden traces |

### Time

- **Ticks.** Tick k (k ≥ 1) runs at absolute frame t(k) = 32k (1,378.7 Hz
  at 44,118 Hz, 0.725 ms) and covers frames [t(k−1), t(k)). The first runs
  at frame 32 [verified: `fm1-mod-core-test`].
- **Edges keep their frame.** A gate edge carries its offset inside the
  tick, so a module triggered at offset 13 has run 19 frames by t(k). An
  edge a module produces (an LFO's wrap, an envelope's end) sits at the
  boundary after the sample that caused it, so a period of P whole samples
  wraps every P frames: a tempo-synced LFO at 1/4 and 120 BPM wraps every
  22,059 frames exactly, starting at the sequencer's Start [verified:
  `test_a_synced_lfo_wraps_on_the_beat`]. One that falls on the tick's own
  end goes to frame 0 of the next tick.
- **Events.** An event at frame f reaches the first tick after it, at
  offset f − t(k−1). A note-off at a tick's own frame belongs to the next
  tick even though the bridge hands it over before that tick runs (rule
  M6); the runtime keeps two windows of pending events for that [verified:
  `edge_frames` in the C test].
- **Writes.** Each tick computes every routed destination and writes a
  value only when its bits changed. The bridge splits a unit's render at a
  tick only when that tick writes to it.
- **Transport.** A kind flagged TRANSPORT reads the sequencer's tempo,
  whether the transport ran at the tick's start (RUN's level there, set by
  Start and Stop at their frames, not per block) and the frame of a Start
  inside the tick.
- **Block sizes.** All of this runs on absolute frames, so the WAV and the
  tick log are byte-identical at host blocks of 1, 7 and 64 frames with
  routes active on Macro, Test Sine and Six-Op, an effect, PITCH and AMP
  [verified: `test_audio_and_ticks_are_the_same_at_host_blocks_of_1_7_and_64`].

### Slots and the value a destination receives

A slot is 12 bytes (`fm1_mod_slot_t`, docs/16 §2.4): source, VIA, unit,
flags (ON, polarity, GATE_DST, curve), destination uid or gate index,
amount and offset in Q1.14 (16,384 is 1.0), and a uid reserved for locks
on the slot's own depth (MG6). For each enabled slot, in ascending slot
order:

```
s = source value          CV, or a gate's level (0 or 1); non-finite reads as 0
s = polarity(s)           AUTO keeps it; UNI maps -1..1 to 0..1; BI maps 0..1 to -1..1;
                          INV is -s for a bipolar source and 1 - s otherwise
s = curve(clamp(s, -1, 1))   LIN, SQUARE, CUBE, ROOT, CBRT, EXP, LOG or S, sign-preserving
s = s + offset
s = s x VIA               VIA read as 0..1 (a bipolar VIA is mapped), when set
c = amount x s x (max - min)          a parameter, as a share of its range
c = amount x s                        an INPUT parameter: 100 % passes the signal
c = amount x round(s x 61,440) / 1,024   SEMI into SEMI: semitones on a 1/1,024 grid
final = clamp(base + (c1 + c2 + ...)), an ENUM rounded

a LOG destination (engine API v3; docs/16 §2.3):
c = amount x s x log2(max / min)              octaves, the same share of its knob
c = amount x (round(s x 61,440) / 1,024) / 12  from a SEMI source: the octave rule
final = clamp(base x 2^(c1 + c2 + ...))
```

- **LOG destinations** (engine API v3, 2026-10-05) sum in octaves and scale
  the base, so NOTE at 100 % into a cutoff keytracks exactly: twelve
  semitones are one octave and 2^1 is 2 to the bit [verified:
  tests/test_engine_api_v3.py]. A sum of 0 leaves the base's bits as they
  are, so a route at zero amount still writes nothing. The 2^x is
  `fm1_exp2f` (include/fm1_math.h), libm-free like the rest.

- **Two deviations from docs/16 §2.4**, both deliberate:
  - An INPUT (a bare signal input, such as Chance's IN) takes amount × s,
    not amount × s × 2: a chain link at 100 % passes its source unchanged.
  - SEMI into SEMI is rounded to 1/1,024 semitone (0.1 cent), so whole
    notes stay whole. NOTE at 100 % on a SEMI parameter adds exactly 7.0
    semitones for a G above middle C; plain float gives 7.0000005
    [verified: `rules` in the C test].
- **Refused slots.** A slot that is on but whose source or destination does
  not exist, or whose destination is NOLOCK, or an ENUM without MOD, is
  refused: it writes nothing and splits nothing, and `fm1-render` counts it
  (`mod_refused`) [verified: Macro's Model and LPG].
- **Rule M1.** A knob, a lock, a revert or the MIDI bend sets a
  destination's base through `fm1_mod_set_base`, which returns what the host
  sends: the value itself when nothing routes there, else base plus the
  last tick's offset. A destination that stops being routed goes back to
  its base at the next tick. A zero amount writes nothing at all, even over
  a base set out of range or to NaN, which the runtime holds clamped as the
  engine does [verified: `test_a_zero_amount_writes_nothing`,
  `gate_continuity` in the C test].

### Sources and destinations

| Ids | Sources (MG1) |
| --- | --- |
| 0 VEL, 1 NOTE, 2 RAND | velocity / 127 and (note − 60) / 60 (SEMI) of the last note on the sound; a seeded random value drawn at each note-on |
| 16 KEY, 17 TRIG | high while a note is held on the sound (legato); a trigger at each note-on |
| 23 RTRG | KEY retriggered: high while a note is held, falling and rising again at each note-on that comes while it is high, once a frame (docs/16 MG3: the virtual FM-1's default envelope cables) |
| 18 CLOCK, 19 BEAT, 20 BAR | triggers each sequencer step, beat and bar, from its 24-PPQN clock |
| 21 RUN, 22 START | high while the transport runs; a trigger at Start |
| 24–31 SEQ1–8, 32–39 SQV1–8 | high while sequencer track 1–8 sounds a note (any route); its last velocity / 127 |
| 64 + 8 × position + port | module outputs |

The gaps are reserved for the later sources (docs/16 §2.4): mod wheel,
aftertouch, bend, CC A and B, MACRO 1–4, the previous block's level and
keys held (3–15), and the arpeggiator's step and gate. They need MIDI input
and the macros in a host, which MG1 has not. "The sound" means notes that
reach the sound engine: the sequencer's tracks routed to it and live notes.

| Unit | Destinations |
| --- | --- |
| 0 SOUND, 1 FX1, 2 FX2 | the first 32 parameters of the bound engine that take modulation |
| 17–19 sound units 2–4, 20 + 4k + j sound unit k + 1's insert j + 1 (j 0, 1) | the same, for the virtual FM-1's multi-sound (docs/16 MG3); 16 and 40–41 are aliases of 0, 1 and 2, kept as those; 4–7, 36–39, inserts 3 and 4 and 42 on name nothing yet |
| 3 HOST | PITCH (uid 1, ±48 semitones; its base is the MIDI bend, sent through `pitch_bend`) and AMP (uid 2, a gain 0–2 before the limiter, ramped linearly over each tick) |
| 8 + position | a module's MOD and INPUT parameters by uid, and with GATE_DST its gate inputs by index |

### Gate cables

- **Gate into gate.** Edges keep their frames. Below 100 % each rising
  edge passes with probability = amount, drawn from the slot's own
  generator (seeded by the runtime's seed and the slot number), and its
  falling edge passes with it. One draw per rise at any amount, so turning
  it never shifts the stream [verified:
  `test_a_gate_cable_is_a_seeded_probability`].
- **CV into gate.** A comparator rising at 0.5 and falling below 0.25,
  seen at tick resolution: its edge sits at the tick's first frame.
- **Several cables into one gate input** combine by OR; edges at one frame
  go in slot order.
- **Normalled inputs.** A gate input with no cable reads its kind's
  `normal` source: the Envelope's GATE reads KEY and the LFO's RESET reads
  TRIG, so with no cable the Envelope follows the keys, as the options
  note's paraphonic C1 envelope did. `gate_connected` still says "no
  cable", as a eurorack module senses a jack.
- **A gate input never jumps.** Each tick it starts where the last one
  ended. Patching a cable in, pulling one out or breaking a normal changes
  its level between ticks, and the module sees that as an edge at the
  tick's first frame, as a jack would give it; so an envelope held open
  is released when its gate goes, and a newly placed module whose input is
  already high sees a rise. Placing a module (a new kind, or the same one
  again) restarts its outputs low and every gate cable from it with them,
  so a module it held open sees a fall [verified: `gate_continuity` in the
  C test, `test_editing_or_repatching_a_gate_never_strands_it`].
- **Editing a cable keeps it.** An edit that keeps a slot's ends (source,
  VIA, unit, destination, GATE_DST), such as turning its amount, keeps the
  cable's state: a gate cable stays high or low and its probability stream
  runs on, so an envelope it holds open still sees the key's release. New
  ends make a new cable, low, with its stream from the seed.

### The planner

On any edit the next tick rebuilds the plan (`mod_plan.c`, docs/16 §2.5):
Tarjan's strongly connected components over the module-to-module cables
(rack order, slot order), Kahn over the components with the lowest first
position winning a tie, rack order inside a component. A cable is delayed
when both ends are in one component and its source sits at or below its
destination: inside a loop, the cable that runs up the rack, and every
self-cable. It reads the previous tick, exactly one tick late.

- **Chains.** D ← C ← B ← A, entered with A at the bottom of the rack,
  runs A, B, C, D and moves Timbre in the same tick as a direct cable from
  A: the WAVs are identical [verified:
  `test_a_chain_entered_backwards_arrives_in_one_tick`].
- **Feedback.** Chance tracking its own HELD plus a 10 % offset climbs by
  the offset each tick [verified]. Moving a loop's lower module to the top
  of the rack moves the delay to the other cable [verified].
- **Fuzzed.** Over 3,000 random racks and tables (1,838 with loops), a
  rebuild gives the same plan, any permutation of the slot table runs the
  same modules in the same order and delays the same cables, every cable
  that is not delayed runs after its source, and every delayed one is
  inside a loop running up the rack [verified: `fm1-mod-core-test`].

### The kinds

**LFO** (`lfo`, LFO). After the options note's LFO: shapes from Schwung's
`lfo_common.h` (Charles Vestal, MIT) and Peaks (Emilie Gillet, MIT), modes
after Elektron's; on `fm1_mp_lfo_t`.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Rate | 0–1 | 0.01–100 Hz on an exponential scale; 0.5 is 1 Hz |
| 2 | Shape | Sine, Triangle, Saw Up, Saw Down, Square, Smooth, S&H, Walk | MOD: a cable picks the shape, rounded |
| 3 | Depth | −1–1 | scales the output |
| 4 | Mode | Free, Trig, Hold, One, Half | Free restarts only on a patched RESET; Trig on every RESET (unpatched: every note-on); Hold samples its output at RESET; One and Half run a cycle or half one from Phase after each RESET, and wait for the first |
| 5 | Phase | 0–1 | where a restart starts |
| 6 | Sync | Off, 4 Bars … 1/32, triplets, dotted | follows the sequencer's tempo instead of Rate; Start restarts the cycle |
| 7 | Width | 0–1 | the square's pulse width |

Gate input RESET (normal TRIG). Outputs OUT (−1..1) and WRAP (a trigger at
each cycle start, a restart included).

**Envelope** (`env`, ENV). After Peaks' multistage envelope (Emilie Gillet,
MIT), on `fm1_mp_env_t`.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1–4 | Attack, Decay, Sustain, Release | 0–1 | times on Peaks' knob curve, 0.5 ms–8 s; Sustain a level |
| 5 | Curve | Linear, Expo, Quartic | Peaks' curves |
| 6 | Loop | Off, AD, ADR | repeats while the gate is high |
| 7 | Mode | Gate, Trigger | Gate: an ADSR on the gate; Trigger: Peaks' AD, each rise restarts it, the fall is ignored |
| 8 | Level | 0–1 | scales the output |

Gate input GATE (normal KEY). Outputs ENV (0..1), EOC (a trigger where the
envelope ends or a loop pass completes) and ACT (high from a start until the
end).

**Chance** (`chance`, CHN). After DaisySP's SampleHold (Electrosmith, Paul
Batchelor, MIT) and Music Thing Modular's Workshop System Computer card 106
(Matt Allison, MIT); no code from either. On `fm1_mp_lfo_t`'s random shapes,
`fm1_mp_slew_t` and the generator.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Mode | S&H, T&H, Smooth, Drift | S&H: a new value at each clock (IN if patched, else a random draw); T&H: follows IN (or one fresh draw a tick) while TRIG is high, unpatched counts as high; Smooth: glides to each new draw over a clock period; Drift: a random walk |
| 2 | Rate | 0–1 | the internal clock when TRIG is unpatched, 0.01–100 Hz |
| 3 | Slew | 0–1 | SMTH's glide: 0 off, else 0.5 ms–8 s for a full-scale move |
| 4 | Level | −1–1 | scales HELD |
| 5 | Walk | 0–1 | Drift's largest step |
| 6 | In | INPUT | the signal to sample |

Gate input TRIG (no normal). Outputs HELD, SMTH (HELD through the slew) and
STEP (a trigger at each new value).

**Instance sizes:** LFO 112 B, Envelope 124 B, Chance 160 B on 64-bit arm64,
and 100, 124 and 152 B with `gcc -m32` [verified: `fm1-render --list-mod`];
under 256 B everywhere but MG2's Burst, 312 B, which ports Peaks' 32-pulse
buffer whole [verified: test]. The default rack (LFO, LFO, Envelope,
Envelope, Chance) takes 640 B of the 8 KB arena.

**MG2's kinds** (Function, Bounce, Register, Coin, Divide, Burst, Slew,
Quantize, Compare, Logic, Calc, Mix, Filter) have their own page:
[kinds.md](kinds.md).

### Hosting

**The bridge.** `fm1_seq_host_dispatch_ticks(h, frames, block, sink, hook)`
(`include/fm1_seq_host.h`) runs a control-rate hook inside the block:
- it feeds every event (notes, clock, Start, Stop) at its frame;
- at one frame it runs note-offs and locks, then the tick and its writes,
  then note-ons (rule M6; checked against a pretend hook in
  `fm1-seq-host-test`);
- it splits the sound's render only at a tick that writes to it;
- a lock's value goes through the hook (`fm1_mod_set_base`, rule M1).

`fm1_mod_glue_t` (`include/fm1_mod_host.h`) is that hook for a runtime; it
hands writes to the effects and AMP to the host, which renders each effect
split at its own writes. With several sound units,
`fm1_seq_host_dispatch_slots_ticks` runs the same hook over every slot in
one pass: slot k is sound unit k, a tick's write goes to the slot it names
and splits only that slot's render, a lock on slot k moves sound unit k's
base (`lock_slot`), and each slot's calls come in the order
`dispatch_ticks` would give it alone [verified: `hooked_slots` in
`fm1-seq-host-test`]. Plain `fm1_seq_host_dispatch` is the hook-less
case; the virtual FM-1 runs this glue as `fm1-render` does (MG3), on every
chain since its lab switch went (2026-10-05). A bridge initialised with
no sequencer runs only ticks, which is how `fm1-render` modulates without
`--cmd`.

**`fm1-render --mod FILE`** (`host/mod_script.h`). One line each:

```
seed 77                                 # the runtime's seed
rack default                            # LFO, LFO, Envelope, Envelope, Chance at 1-5
mod 6 chance mode=smooth rate=0.7       # a kind at a position, with parameter bases
set 1 rate=0.62 shape=triangle          # bases of the module at a position
slot 1 lfo1 > snd:Timbre amt=30         # a cable; amt and ofs in percent
slot 2 seq2 > env4.gate amt=70          # a gate cable at 70 %
slot 3 lfo1 > lfo2.rate amt=20 via=vel pol=uni curve=square
@44118 slot 1 off                       # @FRAME: at the first block starting there
```

Sources are system names (vel, note, rand, key, trig, clock, beat, bar,
run, start, rtrg, seq1–seq8, sqv1–sqv8) or a module's output (`lfo1`,
`lfo1.wrap`, `env3.2`, `mod5.held`). Destinations are `snd:` (sound unit 1,
also `snd1:`), `snd2:`–`snd4:`, `sndK.fxJ:` (sound unit K's insert J;
`snd.fxJ:` for sound unit 1's), `fx1:` and `fx2:` (the master slots),
`host:pitch`, `host:amp`, or a module's parameter or gate input
(`lfo2.rate`, `env3:gate`); a `:` ends the unit when there is one, else the
first `.`. The sound units and inserts need the slots flags (`--sound`,
`--insert`): every unit loaded is bound, its first two inserts too.
`--param-at`, `--sound-param-at`, `--fx-param-at` and `--bend` go through
the bases.

**`--log-mod FILE.jsonl`**: one line per tick, with `k` (the tick), `t`
(its absolute frame), `m` (each module's effective parameters `v`, outputs
`o` and gate edges `e` as [port, frame, level]), `g` (system gate edges as
[id, frame, level]), `s` (each routed sink's base `b` and value `v`) and
`w` (the tick's writes).

**`--list-mod`**: the kinds with every parameter's uid and flags, their
ports, the system sources and the host parameters, as JSON.

**The summary** adds `mod_bytes`, `mod_ticks`, `mod_writes` (and the sound's
and the others' share), `mod_active`, `mod_refused`, `mod_delayed`,
`mod_splits`, `mod_edges_dropped` and `mod_nonfinite`, only with `--mod`.

### Determinism and memory

- **No heap, no stdio, no libm** in the runtime's objects or the bridge
  [verified: `nm -u` in the tests]. 2^x for the rate knobs is a 7th-order
  Taylor series on the fraction and exponent bits; the curves are tables.
- **`-ffp-contract=off`** on every file, from `mk/mod.mk`.
- **Seeds.** One seed per runtime: each instance gets a mix of it and its
  position, each slot one of it and its number, RAND its own.
- **Any memory.** Built in memory filled with 0x00, 0xA5 or 0xFF, the
  runtime writes the same values, bit for bit [verified: the C test and
  `test_any_fill_renders_the_same_across_fills`].
- **NaN and infinity** in sources, bases, amounts and offsets never reach
  a write: sources read as 0, bases clamp (NaN to the default), Q1.14
  amounts clamp to ±1 [verified: the C test].
- **Zero routes, zero change.** A rack with no slot on, or only zero
  amounts, renders byte for byte what the same render without `--mod`
  gives, with the same splits, through the sequencer or not, effects
  included [verified: `test_zero_route_identity`]. The bridge change
  itself changed no render: see "No render changed" below.
- **Size.** `fm1_mod_size()` is 23,520 B since glide (23,200 B since Gate,
  22,368 B in MG3, 20,016 B in MG1): the 8,192 B arena and 15,328 B of fixed state, the same in 32- and 64-bit
  builds (no pointers, every 64-bit member 8-aligned) [verified: pinned in
  the tests, which CI's `-m32` job runs]. MG3's sound units and inserts
  share a pool of 188 parameter records (HOST takes two; 160 in MG3, 180
  from Gate's thirteen parameters, 188 from Macro Heavy's fourteen with
  glide) instead of 32 for
  each of fifteen units, which would have cost about 12 KB more; binding
  an engine that needs more records than are left fails (its cables are
  refused), which today's engines never reach: four sound units and ten
  effects need at most 188 with HOST's two [verified: `test_the_record_pool_holds_every_chain`].
  RTRG added 48 B. The MG1 figures below are MG1's. docs/16 §4.1 estimated 4,480 B of fixed state. The difference is
  mostly copies: each effect and the sound's parameter ranges (1,920 B, so
  the state needs no pointer to an engine), bases, sent values and offsets
  per sink parameter (1,536 B), effective module parameters for the UI and
  logs (1,024 B), the write list (784 B) and both tick buffers of gate
  edges (1,536 B). It is 5.2 % of the 387,924 B gap, against the estimate's
  3.3 %; the system-source arrays (768 B) and the per-parameter offsets
  could shrink if the budget needs it [inferred].
- **On pi32v2** [verified 2026-10-02: `tools/jieli/compile-check.sh`,
  compile only, 83 of 83 objects in all four profiles, no warning from our
  code]: `struct fm1_mod` lays out the same as on i386 and x86-64, and
  `fm1_mod_size()` is 20,016 B on all three. The runtime and its three
  kinds are 29,988 B of text at `-O2` (25,920 B of code) and 19,016 B at
  the SDK's `-Oz`; the primitives add 9,224 B and 7,614 B. The deepest
  stack frames are `fm1_mod_tick` (920 B, the gate merge's scratch),
  `mod_plan_build` (812 B) and `fm1_mod_move` (736 B), inside the SDK's
  2,560 B limit. Cycles per tick wait for the dev board (docs/14 stage B).

### What MG1 leaves for later

- **The simulator** (MG3, built 2026-10-02 behind a lab switch, public
  since 2026-10-05): RACK,
  MATRIX, CHAIN and the routing gesture; the app hosts the glue
  (docs/16 §8, "MG3, as built").
- **Locks on module parameters and slot depths** (MG6). Locks on the
  sound's parameters already move the base (rule M1).
- **`fm1_host_t` is unchanged.** Tempo and the transport reach the kinds
  through the bridge's hook (the sequencer's tempo and Start), which is
  all LFO's Sync needs. A beat position joins when Orbit (Tides 2's
  external ramp) needs one [inferred].
- **The double-buffered plan** of docs/16 §2.5 step 5: in MG1 everything
  runs on one task and an edit takes effect at the next tick. The firmware's
  control task needs the two buffers.
- **Changing a kind switches off the slots that touch it** (docs/16:
  disabled, never deleted); the simulator's RACK switches them on again on
  a change back (MG3, `sim/web/src/fm1_mod_ui.c`).

### No render changed

[verified 2026-10-02, Apple clang, clean builds of the base commit's
`fm1-render` and this one] The bridge now runs the hook inside dispatch and
the sink gained `pitch_bend`; no existing render changed. Over 272
command lines, each run by both renderers and once more by the new one with
a zero-route `--mod` rack (816 runs):
- the 34 Movy oracle scripts on Test Sine, Macro and Six-Op, in both modes;
- the host-block script at 1, 7 and 64 frames on all six sound engines;
- every sound engine with notes, `--param-at`, `--bend`, a 0xA5 fill and
  7-frame blocks, and with two effects;
- every effect on noise, an impulse and a sine, and after a NaN fault.

Every WAV, event log, exit code and error is byte-identical between the two
renderers, and so is every summary less its timing; the zero-route runs
match too. 251 of the 272 render; the other 21 are refused the same way by
both (Macro and Six-Op refuse the 48 kHz scripts, Sophie has no pitch bend).
The virtual FM-1's own parity scenarios run in `sim/web/build-on-aeon.sh`.

## The primitives

### Rules every primitive keeps

- **No heap, no stdio, no libm.** The caller owns each struct, and `init`
  sets every field, so prior memory contents never matter. The tests check
  the objects' undefined symbols for allocators, stdio and libm, and run a
  script from memory filled with `0x00`, `0xA5` and `0xFF` [verified:
  `tests/test_engines_mod.py`]. The sine is a polynomial, and the curves
  and times are tables. The one double operation is in the LFO's rate
  setter.
- **One timing convention.** `process(n)` advances n samples and returns
  the value after the last one. `render(out, n)` writes the value after
  each sample, so its `out[n-1]` equals what `process(n)` returns. `value()`
  reads the current value without advancing. Events such as a gate, a
  reset or a sync happen between calls.
- **Block-size independence.** The LFO, envelope, slew and S&H give
  bit-identical values however a span is split into calls, provided events
  fall on the same samples. The tests compare every value that a chunked
  `process` returns (blocks of 7 and 64, and random splits) with the
  per-sample `render` at that sample [verified].
  - The LFO and the envelope advance integer phases, so a call costs O(1),
    plus one step per wrap or segment crossed.
  - The slew's linear mode is O(1); its exponential mode loops per sample.
- **NaN safety.** Every setter maps NaN and ±inf to a documented value, and
  every signal input ignores non-finite values. No output is ever NaN or
  infinite [verified: tests].
- **Determinism per seed.** Each random source owns its own PRNG.
  - It never touches `stmlib::Random`'s global: the reference tests depend
    on that (options note §2.3).
  - The draws are integers mapped to multiples of 2^-23, so a seed gives the
    same values on every platform. The tests pin golden values for seed 1
    [verified on arm64 macOS clang, and on Linux gcc with `-m32`].
- **`-ffp-contract=off`.** This is docs/14's ladder profile: macOS arm64
  clang would otherwise fuse multiply-adds.

## LFO (`fm1_mp_lfo_t`)

A uint32 phase accumulator with a 32.32 increment. Output is bipolar,
−1..1; phase 0 starts a cycle.

| Shape | Value at phase x (0..1) |
| --- | --- |
| `SINE` | sin 2πx, from an 11th-order Taylor polynomial on the folded quarter wave (error under 6e-8 [verified: tests compare with `math.sin` to 2e-6]) |
| `TRIANGLE` | 0 → 1 → −1 → 0, in phase with the sine |
| `SAW_UP`, `SAW_DOWN` | 2x − 1, 1 − 2x |
| `SQUARE` | +1 while x < pulse width, else −1; widths 0 and 1 give constant −1 and +1 |
| `SMOOTH_RANDOM` | glides from the previous draw to this cycle's draw (smoothstep) |
| `SAMPLE_HOLD` | this cycle's draw, held |
| `RANDOM_WALK` | glides to a target that moves by up to `walk` × [−1, 1) each cycle, reflected at ±1 |

- **Rate as a ratio.** The rate is `hz = base_hz × ratio`, clamped to
  0..rate/2. Free-running, `base_hz` is the rate and `ratio` a multiplier.
  Tempo-synced, `base_hz` is BPM/60 and `ratio` is cycles per beat.
  - The increment is rounded up to 2^-64 of a cycle per sample. A period
    that is a whole number of samples therefore wraps on its last sample.
    At 120 BPM, one cycle per bar wraps after exactly 88,236 samples
    [verified: test].
- **Modes.** `FREE` runs on. `ONE_SHOT` runs one cycle from the start phase
  and holds at its last phase. `HALF` does the same for half a cycle.
  These cover Elektron's free, trig, one and half modes [reported:
  options note §3.1] once the module calls `reset` on a note.
- **`reset`** retriggers. The phase goes to the start phase, a one-shot
  runs again, and random shapes draw a new cycle.
- **`sync(phase)`** moves the phase the shorter way round, to lock the LFO
  to `fm1_mp_clkdiv_phase` or to a tick count without drift.
  - A forward move across the wrap draws.
  - A backward move across it owes a draw instead, so jitter around the
    wrap point never draws twice in one cycle [verified: test].
  - The tests lock an LFO to a one-bar clock for 30 bars; it starts exactly
    one cycle per bar [verified].

**The S&H wrap fix.** Schwung's `src/host/lfo_common.h` (Charles Vestal,
MIT) re-rolls its S&H only when phase < 0.05. Once a block advances more
than 0.05 of a cycle it misses wraps, and a held 0.0 counts as unset
[reported: options note §3.1, lines 173–178 at `ba3b39d`; not re-read
here].
- **What this LFO does instead.** A wrap is a carry out of the 64-bit sum
  of phase and increments. Each carry draws exactly once, however many fall
  in one call. The random state is kept up to date for every shape, so it
  is never unset.
- **The numbers.** At 30 Hz in 128-frame blocks, a block is 0.087 of a
  cycle. Over 2,000 blocks, the 0.05 rule on the same phases catches 99 of
  174 wraps (57 %); this LFO draws on all 174 [verified:
  `test_lfo_sample_hold_draws_on_every_wrap`].
- **Several wraps in one call** draw several times, the same draws as
  per-sample processing [verified].

**The random state.** Each cycle makes two draws, always in the same order:
one for S&H and smooth random, one for the walk. Changing the shape
therefore never shifts the random sequence.

## Envelope (`fm1_mp_env_t`)

A C99 reimplementation of Peaks' `MultistageEnvelope` (Emilie Gillet, MIT):
`peaks/modulations/multistage_envelope.h` and `.cc` in
[pichenettes/eurorack](https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/peaks/modulations)
at `08460a6`, the commit `engines/third_party/mutable` pins. The structure
is Peaks':
- up to 8 segments, each with an end level, a time and a curve;
- a sustain point, held while the gate is high, that the gate's fall jumps
  to;
- a loop from `loop_end` back to `loop_start`;
- a uint32 phase per segment, whose overflow moves on and drops the
  overshoot;
- retrigger from the current value, or from the first level with hard
  reset on.

**Curves** come from Peaks' formulas in `peaks/resources/lookup_tables.py`
lines 122–129:

| Curve | Formula | Shape |
| --- | --- | --- |
| `LINEAR` | t | straight |
| `EXPO` | (1 − e^−4t)/(1 − e^−4) | fast, then settling: the RC charge and discharge |
| `QUARTIC` | t^3.32 | slow, then fast |

Synths disagree on what to call these. Some label EXPO's shape "log" on a
rising segment, and QUARTIC's "exponential"; the names here are Peaks'.
Values come from 257-point tables, as in Peaks. Interpolation error is
under 4e-5 [verified: `test_env_curves_are_peaks`].

**Presets.**
- `set_adsr(a, d, s, r, curve, loop)`:
  - `LOOP_OFF` is ADSR.
  - `LOOP_AD` repeats 0 → 1 → 0 while the gate is high.
  - `LOOP_ADR` repeats 0 → 1 → s → 0 while the gate is high.
  - Every mode releases from the current value in `r` when the gate falls.
- `set_ad(a, d, curve, loop)` is Peaks' AD: the gate's fall is ignored.
  With `loop` it is Peaks' free-running AD loop.
- `configure` and `set_segment` build any other shape.
- `fm1_mp_env_time_from_knob` is Peaks' knob-to-time curve, 0.5 ms to 8 s
  (`lookup_tables.py` 55–68), within 0.2 % [verified: test].

**Differences from Peaks**, all deliberate:
1. **Units.** Levels are float, −1..1, and times are in seconds. Peaks uses
   int16 levels and 16-bit time codes through a 48 kHz increment table, so
   any sample rate works here.
2. **Curve tables.** They use the plain ramp t = i/256. Peaks' ramp repeats
   its 256th point, so its curves reach 1 one step early. Interpolation
   uses a 24-bit fraction, against Peaks' 16.
3. **Output timing.** Output is the value after each advance; Peaks writes
   it before. So the sample on which a segment overflows outputs that
   segment's end level exactly, and a retrigger or release starts from the
   value "now" with no repeated sample.
4. **Finished envelopes.** A gate falling after the envelope has finished
   does nothing. Peaks reruns the release from the final level.
5. **Loop presets.** `LOOP_AD` and `LOOP_ADR` repeat while the gate is high
   and release on its fall. Peaks' loop presets have no sustain point and
   ignore the fall. `set_ad(…, loop=1)` keeps Peaks' behaviour.
6. **Segment length.** A segment lasts at least 2 samples, the uint32
   increment cap. Peaks' shortest time is 0.5 ms.
7. **Reshaping.** A reshape that removes the running segment finishes the
   envelope at its current value; a finished envelope stays finished.
   Peaks restarts at segment 0 with value 0.
8. **Curves per preset.** One curve applies to all of a preset's segments.
   Peaks' ADSR mixes a quartic attack with an exponential decay and
   release; `set_segment` can rebuild that.
9. **Gates.** Gates are events between calls, not per-sample flags.

## Slew limiter (`fm1_mp_slew_t`)

- **Linear:** at most 1/(time × rate) per sample. `rise` and `fall` are the
  seconds a full 0 → 1 or 1 → 0 change takes.
- **Exponential:** a one-pole lag with the time constant `rise` going up and
  `fall` going down (63 % of a step).
  - The coefficient comes from the [2/2] Padé approximant of e^−x, within
    0.1 %.
  - Each step moves at least one LSB, so it lands exactly on the target. A
    float one-pole with a long time constant stalls a few ulps short.
- **The state** is integer, Q4.28: values are quantised to 2^-28 and limited
  to −8..8.
- **Time 0** passes the input through. Non-finite inputs leave the target
  as it was.

## Sample-and-hold (`fm1_mp_sah_t`)

- **`SAMPLE`** takes the input on a rising gate.
- **`TRACK`** follows the input while the gate is high and holds while it is
  low.
- **Non-finite inputs** are never taken.
- **The modes** are DaisySP's `SampleHold` modes (Electrosmith, Paul
  Batchelor, MIT) [reported: options note §5]; written from the behaviour.
- **Random voltages:** the LFO's S&H shape is the clocked random source.
  This primitive holds any signal.

## Turing-machine register (`fm1_mp_turing_t`)

After Tom Whitwell's Turing Machine (Music Thing Modular), from its
published behaviour.
- **Each clock** brings back the bit shifted in `length` clocks ago (1..32)
  and inverts it with probability `flip`:
  - 0 locks a loop of `length` steps;
  - 1 gives a loop of twice the length, its second half inverted;
  - 0.5 is fresh random [verified: tests].
- **Output** is the low 8 bits as 0..1, like the module's 8-bit DAC, and bit
  0 as a gate.
- **One draw per clock** whatever `flip` is, so turning it never shifts the
  stream.
- **Length 32 is safe.** No mask is built from the length, so length 32 has
  none of the shift-by-32 undefined behaviour of O_C's `util_turing.h`
  (`notes/upstream-candidates.md`).
- **Card 20.** Workshop Computer card 20 (Chris Johnson, MIT) is the
  implementation the options note lists. This one was not written from it.

## Clock divider and multiplier (`fm1_mp_clkdiv_t`)

`mul` pulses per `div` periods of `ref` input ticks: `ref` 96 is one beat
at `fm1_seq`'s 96 PPQN.
- **Where pulses fall.** Pulse k falls on tick ⌈k · ref · div / mul⌉,
  counting from the first tick after a reset, so pulses are spread as
  evenly as whole ticks allow and never drift.
  - Fifths of a beat land on ticks 0, 20, 39, 58, 77 and 96 [verified:
    test].
- **`advance(ticks)`** equals that many `tick()` calls [verified: test].
- **`phase()`** gives the position in the output period, for
  `fm1_mp_lfo_sync`.

## Sizes and cost

| Struct | Bytes |
| --- | --- |
| `fm1_mp_lfo_t` | 88 |
| `fm1_mp_env_t` | 96 |
| `fm1_mp_slew_t` | 40 |
| `fm1_mp_sah_t` | 8 |
| `fm1_mp_turing_t` | 32 |
| `fm1_mp_clkdiv_t` | 16 |

- **Sizes** are from `fm1-mod --sizes` on 64-bit arm64 macOS [verified]. A
  gcc `-m32` build passes every test; there `uint64_t` aligns to 4, so its
  sizes are the same or smaller [verified].
- **Read-only tables:** 3 × 257 floats, about 3 KB.
- **Cost.** A control-rate call is tens of operations. The exceptions are
  the exponential slew, at about 5 operations per sample, and the LFO's
  rate setter, which divides in double.
  - Not measured on pi32v2; that waits for the dev board (docs/14)
    [inferred].

## Credits and licences

All code here is this repository's, MIT. The primitives are written from
these MIT sources and published behaviours, and copy none of their code
(`mod_mi.c`, which ports Peaks and Braids code under its MIT notice, is
described in [kinds.md](kinds.md)):

- **Emilie Gillet**, Mutable Instruments Peaks: the envelope's structure,
  presets, curve formulas and time curve.
- **Charles Vestal**, Schwung's `lfo_common.h`: the shape set, and the S&H
  behaviour fixed here.
- **Electrosmith and Paul Batchelor**, DaisySP `SampleHold`: the two S&H
  modes.
- **Tom Whitwell**, Music Thing Modular's Turing Machine: the register's
  behaviour.
- **Sebastiano Vigna**: xorshift64* and splitmix64.

Mutable module names appear only as credited sources (CLAUDE.md).

# 16 — Modulation: a rack of modules inside the matrix

The owner's request (2026-10-02): "get something like the Mutable Stages and
an arbitrary function generator plus other 'fun' Eurorack utilities into the
mix as configurable modules that could serve as modulation sources in the mod
matrix. We can develop other modulation modules further down the line too as
long as the architecture allows for it. Maybe this should be part of the
modulation matrix, and maybe we can explore not just allowing destination A->B
but also allowing the creation of modulation chains eg A->B->C->D — it could
still be 1:1 mappings but just exposing both inputs and outputs on the SRC and
DEST sides of the modulation matrix." The request also asks how Disting,
Ornament & Crime (O_C) and Mutable Instruments' modules fit.

This document builds on two plans merged in PR #26:
- the options note,
  [notes/2026-10-01-arp-modulation-effects-options.md](../notes/2026-10-01-arp-modulation-effects-options.md),
  whose §3–§5 chose two LFOs, two envelopes, a CHANCE source and a 16-slot
  matrix (its stage C1), and set the rules M1–M7 (a lock writes a base,
  modulation adds an offset);
- [docs/15](15-sequencer-in-simulator.md), whose stage S7a brings engine API v2
  (parameter uids and the LATCH, SMOOTH and NOLOCK flags; docs/13's M2).

**What this changes in the options note** [inferred, proposed]:

| Options note | This document |
| --- | --- |
| LFO1–2, ENV1–2 and CHANCE are fixed sources in `fm1_mod` | They are module kinds in a rack of 8 positions. The default rack holds those five, so C1's behaviour is the default preset |
| 16 slots of 6 bytes: `{source, unit, destination uid, int8 amount, flags}` | 32 slots of 12 bytes. Sources include every module output; destinations include every module parameter and gate input |
| Modulators' own settings are a MOD unit (rule M3) | Each module is its own unit, `MOD1`–`MOD8` |
| Grid of 16 or 32 frames, owner's choice | Unchanged; 32 is recommended here (§2.6) |
| Rules M1–M7 | Kept as written, and extended to module parameters (§6.1) |

**How it was made.** Four lanes read sources on 2026-10-02: Mutable
Instruments; O_C (Phazerville), monome Teletype and crow, and the Music Thing
Workshop System Computer cards; Expert Sleepers' Disting and the classic
function generators; and the architecture of other modulation systems. This
document is the synthesis. Nothing third-party was built or run. Upstream code
was read at these commits:

| Source | Commit or version |
| --- | --- |
| `pichenettes/eurorack` (local clone `reference/mi-eurorack`) | `08460a6` (2023-08-16), the commit `engines/` vendors |
| `pichenettes/stmlib` (`reference/mi-stmlib`) | `e3bd7c9` |
| `djphazer/O_C-Phazerville` | `195932a` (2026-08-10) |
| `qiemem/eurorack` (Stages multi-mode fork) | tag `v1.3.0` |
| `monome/teletype`, `monome/crow`, `TomWhitwell/Workshop_Computer`, `chrisgjohnson/Utility-Pair` | `main`, read 2026-10-02 |
| `expertsleepersltd/distingNT_API` | `6975a63` |
| Disting manuals | mk4 4.27, EX 1.26, NT 1.1 (the 1.18 PDF is over 10 MB and would not fetch) |
| VCV Rack, Surge XT, Vital, Deluge, Schwung | `061ccf6`, `348cfb3`, `636ca0e`, `62a516c`, `ba3b39d` |
| This repository | main `2c53435` |

**Marks.**
- [verified]: read in the file named, at the commit named, in this run.
- [reported]: a manual, web page or summary says so; not re-read here.
- [inferred]: our estimate or proposal.

**No CPU figure in this document is measured on pi32v2.** All of them stay
[inferred] until the AC79 dev kit (docs/14, stage B).

**The one rule.** Nothing here runs on, writes to, or is sent to an FM-1
(CLAUDE.md). Everything below is built and tested on a desktop and in the
browser simulator.

**Contents**
1. [Short answer](#1-short-answer)
2. [The modulation graph](#2-the-modulation-graph): dataflow, the module
   contract, ports, the matrix, evaluation order, rates, determinism
3. [The module catalogue](#3-the-module-catalogue): function generators,
   LFOs, segment generators, random, sequencing sources, utilities,
   followers, what is left out, and where each disting algorithm lands
4. [Budgets](#4-budgets): RAM, CPU, flash, presets
5. [The UI](#5-the-ui): RACK, MATRIX, CHAIN and PATCH
6. [How it fits the rest](#6-how-it-fits-the-rest): sequencer locks, the
   sequencer as a source, per-voice modulation, the arpeggiator
7. [Extensibility: adding a module kind](#7-extensibility-adding-a-module-kind)
8. [Staged plan](#8-staged-plan): MG0–MG9
9. [Owner decisions](#9-owner-decisions)
10. [Sources](#10-sources)

## 1. Short answer

**The design** [inferred]:
- **One system, not two.** A rack of up to 8 configurable modulation
  modules lives inside the modulation matrix.
  - The matrix's **sources** are the system sources (velocity, note, MIDI
    controllers, macros, the sequencer's gates and clock) plus **every module
    output**.
  - Its **destinations** are the sound's, the effects' and the host's
    parameters plus **every module parameter, module signal input and module
    gate input**.
- **A module's CV inputs are its parameters.** On a eurorack module a CV
  jack adds to its knob. Here a cable into a module parameter adds to the
  parameter's base value, which is the options note's rule M1. So most module
  inputs need no ports of their own. Only gates, clocks and bare signal inputs
  (a slew's input, a comparator's two inputs) are ports.
- **32 slots of 1:1 cables**, 12 bytes each. A source can feed many slots, and
  many slots can sum into one destination.
- **Chains are ordinary slots.** A→B→C→D is three slots, plus one more to
  reach a sound parameter (worked example below).
- **Order is computed, not typed.** On every edit the graph is sorted, so a
  chain without a loop has no added latency whatever order the rack shows.
  Loops are allowed: inside a loop, the cable that runs up the rack reads the
  previous tick's value, exactly one tick late, and the screen marks it `~`.
- **A fixed control grid.** Modules run once per tick of 32 frames
  (1,378.7 Hz, 0.725 ms), on absolute sample time. Triggers inside a module
  stay sample-accurate. Output is byte-identical at host blocks of 1, 7 and 64
  frames, and the browser equals native `fm1-render`.
- **Panel.** LFO opens the RACK, EDIT opens the MATRIX, and ENV latches PATCH:
  arm a module output, then turn any knob on any page to route it there.

**A chain, as slots.** The rack holds 1 LFO, 2 Function (after Maths),
3 Segments (after Stages) and 4 Chance:

| Slot | Cable | What it does |
| --- | --- | --- |
| 1 | LFO1.OUT → FUN2.RISE | the LFO stretches Function's rise time |
| 2 | FUN2.EOC → SEG3.GATE1 | each end of Function's cycle starts a Segments group |
| 3 | SEG3.OUT1 → CHN4.TRIG | Segments' first output, through the gate input's comparator, clocks Chance |
| 4 | CHN4.HELD → Sound.Timbre | the held random value moves the sound |

All four cables run in the same tick. If slot 5, CHN4.HELD → LFO1.RATE, closes
a loop, that one cable is read a tick late and shows `~`.

**The catalogue (§3).** Every first-wave module is MIT code, ported or our
own:
- **Function generators:** Segments (after Mutable's Stages), Function (after
  Make Noise's Maths and Joranalogue's Contour 1), Curves (an arbitrary
  function generator on the 16 white keys), Envelope, Bounce (Peaks' bouncing
  ball).
- **Cyclers and random:** LFO, Chance (sample-and-hold, smooth random),
  Register (a looping shift register).
- **Gates:** Coin (a Bernoulli gate after Branches), Divide (clock divider,
  probability, Euclid), Burst (ratchets after Peaks).
- **Utilities that make chains useful:** Calc, Mix, Slew, Compare, Logic,
  Quantize, and Filter (a resonant control-rate filter, the owner's
  addition of 2026-10-02).

Later waves add Orbit (Tides 2), Dice (Marbles), Swirl (Frames' poly LFO),
Scenes, Motion, Chaos, Tangle, Bits, Grooves (a Grids-like groove generator
with our own maps) and the audio followers.

**Where the owner's references land:**
- **Mutable Instruments.** The STM32 code of Stages, Tides 2, Marbles, Peaks,
  Frames and Streams is MIT [verified: file headers at `08460a6`], so it can
  be ported anywhere, including the public simulator. Branches and Grids are
  GPL-3 AVR code [verified], so we write our own versions; the GPL originals
  could only ever go in a personal build.
- **O_C (Phazerville).** Most applets are MIT, file by file [verified], and
  several are worth porting: the vector oscillator behind Curves, Relabi
  (Tangle), Scenery (Scenes), RunglBook and Cumulus (Bits), random walk,
  integer sequences. Its input mapping, where any applet input can read
  another applet's output, is the working precedent for chains.
- **Disting.** Its algorithms are closed firmware, so they are ideas only.
  §3.9 maps each useful one to the module that covers it. The disting NT is
  the other working precedent for chains: every algorithm input and output
  is a bus selection, and CV mappings add to a parameter's stored value. Its
  plug-in API is MIT [verified] and gives our module contract its shape.

**Cost** [inferred]: about 4.5 KB of fixed state plus an 8 KB module arena,
3.3 % of the 387,924 B free in the stock layout. A typical rack takes about
1–2 % of a 240 MHz core at the 32-frame grid.

**Order of work (§8).** Stages MG1–MG9 follow docs/15's S7a (API v2). The
core and the small modules are desktop-only and can be built in parallel with
docs/15's UI stages; the simulator pages follow S2.

## 2. The modulation graph

### 2.1 Dataflow

```
system sources: VEL NOTE MW AT BEND CC MACRO1-4 | gates: KEY NOTE SEQ T1-8 CLOCK BEAT BAR RUN START
        |
        |  slots (32 x 12 B)
        v
+-------------------------------+       slots        +------------------------------------+
| rack: up to 8 module          | -----------------> | module parameters, signal inputs   |
| instances, run in plan order  |                    | and gate inputs (the rack itself)  |
+-------------------------------+                    +------------------------------------+
        |
        |  slots
        v
sinks: SOUND, FX1 and FX2 parameters (set_param) | HOST PITCH (+ MIDI bend) | HOST AMP
```

The rack is both a source and a destination of the same slot list. Nothing
else carries modulation.

### 2.2 The module contract: `engines/include/fm1_mod.h`

A module **kind** is a struct of function pointers, like an engine in
`fm1_engine.h`. It follows the engine conventions [verified: `fm1_engine.h`]:
the host asks for the instance size and provides memory, the kind constructs
itself there, and it never allocates. It must behave the same whatever the
memory held before. A module **instance** is a kind placed at a rack position.

Proposed header (MG1) [inferred]:

```c
#define FM1_MOD_MAGIC 0x464D314Du      /* "FM1M" */
#define FM1_MOD_API_VERSION 1u
#define FM1_MOD_TICK 32u               /* frames per control tick; owner decision: 32 or 16 */
#define FM1_MOD_EDGES 4u               /* gate edges per output port per tick */

typedef enum { FM1_PORT_CV_BI, FM1_PORT_CV_UNI, FM1_PORT_GATE } fm1_port_kind_t;
typedef enum { FM1_UNIT_NONE, FM1_UNIT_SEMI } fm1_port_unit_t;   /* SEMI: semitones / 60 */

typedef struct { const char *name; uint8_t kind, unit; } fm1_port_t;  /* name <= 5 chars */
typedef struct { uint8_t frame, high; } fm1_edge_t;                   /* frame < FM1_MOD_TICK */
typedef struct { uint8_t level_at_start, n; const fm1_edge_t *ev; } fm1_gate_in_t;
typedef struct { uint8_t n; fm1_edge_t ev[FM1_MOD_EDGES]; } fm1_gate_out_t;

typedef struct fm1_mod_io {
  uint64_t tick;                  /* k: this call covers frames [t(k-1), t(k)) */
  const float *p;                 /* effective parameters: base + routes, clamped */
  uint32_t routed;                /* bit i: parameter i has an enabled slot */
  const fm1_gate_in_t *gate;      /* one per gate input */
  uint32_t gate_connected;        /* bit j: gate input j has an enabled slot */
  const fm1_transport_t *tp;      /* tempo, running, sequencer position at t(k-1) */
  float *out;                     /* every output's value at t(k); gates 0 or 1 */
  fm1_gate_out_t *gout;           /* edges inside this tick, per gate output */
} fm1_mod_io_t;

typedef struct fm1_mod_kind {
  uint32_t magic, api_version;
  const char *id;                 /* "seg" */
  uint32_t guid;                  /* 4 characters, saved in presets */
  const char *name, *abbr;        /* "Segments", "SEG" (3 characters) */
  const char *credits;            /* who and what it is after */
  const fm1_param_t *params; uint16_t n_params;        /* API v2 parameters, <= 32 */
  const fm1_port_t *gate_in; uint8_t n_gate_in;        /* <= 8 */
  const fm1_port_t *out; uint8_t n_out;                /* <= 8 */
  uint32_t flags;                 /* POLY_OK, TRANSPORT, AUDIO_TAP */
  uint16_t data_bytes;            /* pattern data saved with presets; 0 if none */
  size_t (*instance_size)(const fm1_host_t *);
  void *(*create)(void *mem, const fm1_host_t *, uint32_t seed);
  void (*destroy)(void *);
  void (*reset)(void *, uint32_t why);                 /* START, STOP, PRESET */
  void (*process)(void *, const fm1_mod_io_t *);
  void (*get_data)(const void *, uint8_t *buf);        /* NULL when data_bytes is 0 */
  int  (*set_data)(void *, const uint8_t *buf, uint16_t n, uint8_t version);
  const void *(*view)(const void *);                   /* read-only state for drawing */
} fm1_mod_kind_t;
```

**Why these choices.**
- **Parameters are API v2 `fm1_param_t`s with uids** (docs/15 S7a), so a
  sequencer lane can lock any module parameter and a preset survives a
  reordered table. Kinds keep to 32 parameters, the app's mirror size
  (`FM1_APP_MAX_PARAMS` 32) [verified: `sim/web/src/fm1_app.h` 55].
- **Two new parameter flags**, requested from S7a:
  - **MOD**: the parameter accepts modulation. It is on by default for FLOAT.
    ENUM needs it explicitly and is then rounded. NOLOCK implies not MOD
    (options note M4).
  - **INPUT**: a bare signal input (Slew's IN, Compare's A and B, Mix's
    IN1–4). It is hidden from the knob pages, its base is 0 and its range
    −1..1.
- **Two new parameter fields**, also for S7a: `abbr` (up to 6 characters, for
  matrix rows; 5 when a unit prefix is added) and `unit` (SEMI, ms, Hz, %,
  degrees).
- **Built.** The owner approved both (§9, question 7), and S7a added the
  flags and the fields to every engine and effect [verified:
  engines/README.md, "Parameters"; `fm1_unit_t` numbers NONE 0 and SEMI 1
  as `fm1_port_unit_t` above, so the two can share it].
- **Gates are separate** because they carry edges with frame offsets. That is
  what keeps a trigger sample-accurate inside a module.
- **`routed` and `gate_connected`** tell a module what is patched, as a
  eurorack module senses a plugged jack. Segments needs this: on Stages, a
  patched gate starts a segment group [verified: `stages/chain_state.cc`,
  `ChainState::Configure`].
- **Pattern data** (`data_bytes`, `get_data`, `set_data`) holds what is not
  a parameter: Curves' 16 stages, Draw's 16 bins, Scenes' snapshots, Motion's
  recordings. It is versioned and saved with the preset.
- **`view`** gives the app a read-only struct to draw (playhead, current
  stage, group map). Kinds never draw.
- **The core holds no pointers**: kinds by registry index, instances by
  arena offset. So `fm1_mod_size()` is the same in 32- and 64-bit builds, as
  `fm1_seq_size()` is. A vendored kind's own instance may differ between
  builds; the arena check covers that.

**Precedents** [verified at the commits above]:
- The disting NT API (MIT, © 2025 Expert Sleepers): a 4-character guid,
  memory declared before construction, `parameterChanged`, and inputs and
  outputs that are themselves parameters.
- Phazerville's Hemisphere applets (MIT): one controller call per tick and a
  whole applet's settings in 64 bits.
- VCV Rack's `isConnected` (GPL-3.0+, design only).

### 2.3 Ports and signal types

| Kind | Range | Carried as | Example |
| --- | --- | --- | --- |
| CV_BI | −1..+1 | the value at the tick's end | LFO OUT, Chance HELD |
| CV_UNI | 0..1 | the value at the tick's end | Envelope ENV, Segments OUT |
| GATE | 0 or 1 | the level at the tick's end, plus up to 4 edges with frame offsets | Function EOC, Coin A, Divide OUT |

A trigger is a GATE that falls after a fixed length, one tick by default
(Phazerville's trigger is 1 ms [verified: `HSUtils.h` 25]).

**Units.** Wrappers convert each upstream's volts to these ranges:
- Mutable's unipolar 0–8 V and bipolar ±5 V become 0..1 and ±1.
- O_C's 1,536 counts per volt [verified: `ONE_OCTAVE = 12 << 7`] and the
  disting's ±10 V are rescaled the same way.
- A pitch output declares the unit SEMI: semitones / 60, so ±1 is ±5 octaves
  (1 V per octave with 1.0 = 5 V). A SEMI source into a SEMI destination at
  amount +100 % adds its semitones exactly, so a quantiser plays in tune
  (§2.4).

**Conversions on a cable** [inferred]:

| From → to | Rule |
| --- | --- |
| CV → gate input | A comparator: rises at 0.5, falls at 0.25. The crossing is seen at tick resolution, so its edge sits at the tick frame |
| Gate → parameter | 0 or 1 |
| Gate → gate input | Edges keep their frame offsets. Several cables into one gate input combine by OR |
| Gate → gate, amount below 100 % | Each rising edge passes with probability = amount, from the slot's own seeded generator, with its falling edge. A "probability cable", Coin built into every gate cable (an idea from the Mutable lane) |

### 2.4 The matrix: slots, sources and destinations

**A slot** (12 bytes):

| Field | Type | Values |
| --- | --- | --- |
| `src` | u8 | 0–63 system sources; 64 + 8 × position + port for module outputs |
| `via` | u8 | a source id, or 0xFF for none |
| `dst_unit` | u8 | 0 SOUND, 1 FX1, 2 FX2, 3 HOST, 8 + position for a module |
| `flags` | u8 | ON; polarity (AUTO, UNI, BI, INV); CURVE (8 tables); GATE_DST; VOICE (later) |
| `dst_uid` | u16 | the parameter's uid, or the gate input's index when GATE_DST |
| `amount` | i16 | Q1.14, −1..+1 of the destination's range |
| `offset` | i16 | Q1.14, added to the source before scaling |
| `uid` | u16 | base uid for the slot's own AMT and OFS, so a sequencer lane can lock a cable's depth |

**The value a destination receives** [inferred]:

```
s = read(src)                  CV value, or a gate's level (0 or 1)
s = polarity(s)                AUTO keeps the port's kind; UNI, BI and INV convert
s = curve[c](s)                33-entry sign-preserving tables, linearly interpolated, built offline
s = s + offset
if via:  s = s * read_uni(via)
contrib = amount * s * (max - min)          (SEMI into SEMI: amount * s * 60 semitones)
final = fm1_param_clamp(p, base + sum of contrib over enabled slots, in ascending slot order)
```

- **A destination with no enabled slot is never written**, so every existing
  render stays byte-identical. This is the zero-route identity test.
- **ENUM destinations** are rounded, and accepted only when flagged MOD.
  NOLOCK destinations are refused (options note M4).
- **VIA** is the Deluge's "source modulating a cable's depth" [verified:
  `params/param_descriptor.h` at `62a516c`] and Shruthi's mod-wheel slot.
- **Changing a module's kind disables the slots that touch it** rather than
  deleting them, so changing it back restores the patch.

**System sources** (ids 0–63):
- **CV:** velocity, note number, mod wheel, aftertouch, bend, CC A and CC B
  (MIDI-learned), MACRO 1–4 (lockable parameters of the host), random value
  per note, audio level (the previous block's peak), keys held.
- **Gates:** key gate, note trigger, SEQ track 1–8 gate and velocity, CLOCK
  (a step), BEAT, BAR, RUN and START, with exact frames from `fm1_seq`'s
  events. The arp's step and gate join when the arpeggiator lands (§6.4).

**Module outputs** are ids 64–127. Their screen label is the kind's `abbr`,
the rack position and, for a module with more than one output, the port:
`LFO1`, `SEG3.2`.

**Destinations:**
- **SOUND, FX1, FX2:** every parameter flagged MOD (docs/15 S7a gives each
  its uid).
- **HOST:** PITCH (semitones, summed with MIDI bend into `pitch_bend`) and AMP
  (a gain before `fm1_mix_limiter`, which gives tremolo). MACRO 1–4 are
  sources only: they read their base (a knob or a lock), so no loop can pass
  through the host.
- **MOD1–MOD8:** every MOD parameter of the module at that position, every
  INPUT parameter, and every gate input (GATE_DST).

**One list, two views.** Phazerville stores routing on each input instead
(a source byte and an attenuverter per applet input) [verified:
`CVInputMap.h` at `195932a`]. That is equivalent in power, but it would put
cables in two places. Here the RACK page shows the cables into and out of the
selected module, which is a filtered view of the same 32 slots (§5.2).

### 2.5 Evaluation order and feedback

**When the graph changes** (a slot edited, a kind changed, the rack
reordered), the control task rebuilds the plan [inferred]:
1. Find the strongly connected components (Tarjan), visiting modules in
   display order and cables in slot order. Only module-to-module cables
   count: system sources and sinks cannot be in a loop.
2. Order the components (Kahn). Ties go to the component whose first member
   sits highest in the rack. Inside a component, modules go in display
   order.
3. Mark a cable **delayed** when both its ends are in the same component
   and the source sits at or below the destination in the rack. Only
   self-cables and cables that run up the rack inside a loop qualify; a cable
   between components is never delayed, whatever the rack order.
4. Build each destination's slot list in ascending slot order.
5. Publish the plan at the next tick boundary (two buffers and an index).

**On each tick k**, at frame t(k) = k × G:
1. Sample the system CV sources. Give the system gates the edges queued for
   [t(k−1), t(k)), with offsets from t(k−1).
2. Swap the current and previous output buffers.
3. For each module in plan order: sum its parameters' bases and
   contributions (a delayed cable reads the previous buffer), merge its gate
   edges by frame (ties by slot), and call `process`.
4. For each routed sink parameter, compute the final value. Write it at
   t(k) only if its bits changed.

**Worked example.** Display order: 1 LFO1, 2 LFO2, 3 SEG3, 4 CHN4.

| Slot | Cable | Delayed? |
| --- | --- | --- |
| 1 | LFO1.OUT → LFO2.RATE | no |
| 2 | LFO2.OUT → SEG3.LEVEL2 | no |
| 3 | SEG3.OUT1 → Sound.Timbre | no (a sink) |
| 4 | SEG3.EOC → CHN4.TRIG | no |
| 5 | CHN4.HELD → LFO1.RATE | **yes**: it runs from position 4 up to position 1 inside the loop {1, 2, 3, 4} |

- If the owner moves CHN4 to the top of the rack, slot 4 becomes the delayed
  cable instead. Its edges arrive at the same offsets, G frames later.
- A chain D ← C ← B ← A shown in the order D, C, B, A has no loop, so it
  still runs A, B, C, D with no added latency.
- A self-cable (LFO1.OUT → LFO1.RATE) reads the previous tick.

**Why a sort rather than plain rack order.** The disting NT, Axoloti and
Phazerville run modules in their visible order, and a backward cable reads
last tick's value [reported for the NT and Axoloti; inferred for Phazerville
from `Quadrants.h` 593–598]. That is simple, but a chain entered "backwards"
then gains a tick per hop, and reordering with four knobs is tedious. A
uniform one-tick delay on every module cable, which is Surge's effective
behaviour [verified order: `SurgeVoice.cpp` at `348cfb3`; consequence
inferred], needs no sort, but a clock → divider → envelope chain drifts by
2 × 0.725 ms. It stays as the fallback if the planner is ever cut. Refusing
loops (Surge refuses self-modulation [verified: `isValidModulation`]) was
rejected: feedback is half the fun of a eurorack, and the owner asked for
chains. The plan costs under 1,000 cycles per edit, off the audio path
[inferred].

### 2.6 Rates and the tick

All rows but the first three are [inferred].

| | G = 32 (recommended) | G = 16 |
| --- | --- | --- |
| Tick rate | 1,378.7 Hz | 2,757.4 Hz |
| Tick period | 0.725 ms | 0.363 ms |
| Ticks per 64-frame block | 2 | 4 |
| Extra render calls per routed unit per block | 1 | 3 |
| Typical rack CPU (§4) | about 1–2 % of a core | about 2–4 % |
| Shortest clean stage | about 2–3 ms | about 1–1.5 ms |

- **Latency.** An event reaches a parameter at most G frames late. A gate
  chain adds nothing per hop when it has no loop.
- **Sample-accurate triggers.** A module receives each edge's frame offset.
  An envelope triggered at offset 13 has run for G − 13 frames at t(k).
- **Steps are hidden** by S7b's SMOOTH ramp (2–3 ms) inside the engines. PITCH
  can additionally be ramped in 8-frame sub-splits if a test shows zipper
  noise [inferred].
- **Renders are split only where needed.** The host splits a unit's render
  at a tick frame only when that tick writes to the unit [inferred]. A unit
  with no routed parameter renders in one call, as today.
- **Host order at one frame** (options note M6, consistent with D2 in
  `engines/seq.md`): note-offs, D6 reverts, locks (to the base), the mod
  tick's writes, then note-ons. A retriggered envelope starts from the step's
  locked values.
- **No audio rate in the graph, version 1.** Audio-rate FM and
  sample-and-hold stay inside engines and effects (Plaits' FM models, the
  CRUSH effect). A per-sample lane between two modules that both opt in is
  deferred to API v2 of `fm1_mod`.

**Vendored code with a fixed rate** follows one of three strategies [native
rates verified at `08460a6`]:

| Strategy | Used for | How |
| --- | --- | --- |
| (a) Rate-free code at the grid | Tides 2 `PolySlopeGenerator`, Marbles' T and X/Y generators, Frames' `PolyLfo`, Streams' Lorenz generator | Tides takes frequency in cycles per sample from the caller; Marbles takes the sample rate in `Init`; Frames' increments (from a 24 kHz table) and Lorenz's `dt` (31,089 Hz) are rescaled by the wrapper |
| (b) Native rate through an integer accumulator | Peaks' bouncing ball and pulse processors (48 kHz, blocks of 4), Streams' vactrol (31,089 Hz), the vendored Stages oracle (31,250 Hz, blocks of 8) | Tick k runs n(k) = ⌊k·G·r/44,118⌋ − ⌊(k−1)·G·r/44,118⌋ native samples, exact in 64-bit integers: 22.67 Stages samples per tick at G = 32 on average. An edge at frame f lands at native sample ⌊f·r/44,118⌋ of the chunk. This extends the 2026-10-01 native-rate decision to modulators |
| (c) Audio-rate analysis | Streams' follower and compressor | Runs on the tapped audio at the host rate, or decimated by 2 (§3.7) |

### 2.7 Determinism and parity

The browser simulator must stay sample-identical to native `fm1-render`
(docs/14: bit-exact wherever both sides do the same arithmetic) [verified:
docs/14 line 17]. Rules for the core and every kind [inferred]:
- **No libm.** Only tables and polynomials. The glibc parity gap today comes
  from Sophie's `sinf`, `expf` and `powf` [verified: `sim/web/README.md`,
  "Parity"]. Stages' segment generator already uses only `lut_*` tables
  [verified by grep].
- **`-ffp-contract=off`** on these sources, so no build fuses multiply-adds.
- **A fixed summation order** (ascending slots) and **plans that depend only
  on saved state** (slots and display order).
- **Seeded randomness per instance.** Each kind gets a xorshift seeded from
  the preset and its position; never `rand()`.
  - Vendored Stages and Peaks code draws from `stmlib::Random`, one static
    generator that Plaits and Braids also use [verified:
    `stmlib/utils/random.h`: static `rng_state_`, with `Seed()` and
    `state()`]. Stages draws at `segment_generator.cc` 273, 641 and 649
    [verified]. The wrapper calls `Random::Seed(inst->rng)` before a vendored
    call and stores `Random::state()` after, so each instance has its own
    stream and upstream files stay byte-identical.
  - Marbles takes randomness through an injectable `RandomStream` with a
    fallback generator. The wrapper never calls `Write()`, so every draw comes
    from the preset-seeded generator [verified: Mutable lane,
    `random_stream.h`].
- **Gate overflow** beyond 4 edges per output per tick is dropped and
  counted, deterministically.
- **Integer cores** (Peaks, Streams, the vector oscillator, the bit machines)
  are bit-exact by construction. Float kinds are bit-exact under the rules
  above, or fall into docs/14 §2.3's tolerance classes with a named cause.

**Tests for the core, run in every stage that touches it:**
- zero-route identity against today's WAVs;
- byte identity at host blocks of 1, 7 and 64 frames, with routes active;
- plan rebuild idempotent; plans equal under any permutation of an
  equivalent slot table (fuzz);
- a chain test (A→B→C→D arrives in one tick) and a feedback test (A→A one tick
  late);
- any-fill construction; NaN in sources, amounts and offsets survived;
- `nm -u` shows no `malloc`, stdio or libm;
- native against wasm parity on new scenarios;
- the uids of every kind pinned in `tests/fixtures/mod-uids.json`.

## 3. The module catalogue

**Naming.** Lunar modules get their own plain names. Product names (Stages,
Maths, Marbles, Turing Machine, Just Friends, disting) appear only in
credits, as "after Mutable Instruments' Stages", following Mutable's request
in `UPSTREAM.md`. Each kind's `credits` string and the simulator footer name
the authors.

**Columns.**
- **Code**: *Port* = upstream code taken under its licence (MIT unless
  stated). *Own* = our code, written from published behaviour or manuals,
  because the original is closed, GPL or hardware. *Own+* = our code that
  adapts MIT code with its notice.
- **In**: gate inputs, then INPUT parameters. Every MOD parameter is a
  destination too and is not repeated.
- **Cost**: RAM per instance, cycles per tick at the grid, flash for tables.
  All [inferred] unless marked.
- **Wave**: 1 = stages MG1–MG5; 2 = MG7; 3 = MG8 or later (§8).

### 3.1 Envelopes and function generators

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Function** (FUN) | Make Noise Maths, Joranalogue Contour 1, Serge DUSG, Befaco Rampage | Own. Rampage's VCV code is GPL-3.0+ [verified LICENSE.md], read only | TRIG, GATE, CYCLE, HOLD; IN (slew target or floor) | OUT, INV, RISING, FALLING, EOR, EOC | RISE, FALL, SHAPE (log–lin–exp), MODE (AD, AR, cycle, slew, gated cycle); LEVEL, FLOOR, RETRIG (when a retrigger is accepted, 0..1), SYNC (total time in steps) | 24 B; 30–60 cycles; a shared 1 KB curve table | 1 |
| **Quad** (QUA) | Intellijel Quadrax, Buchla 281, the Maths SUM/INV/OR busses | Own (four Functions) | TRIG1–4, GATE1 | CH1–4, SUM, INV, OR, EOC4 | per channel RISE, FALL, SHAPE, LINK (none, previous trigger, EOR, EOC); MODE (independent, quadrature, burst) | about 100 B; 150–250 cycles | 2 |
| **Envelope** (ENV) | Mutable Peaks' multistage envelope; disting EX Quad Envelope and mk4 E-1 | Own+: Peaks' curve tables (MIT, Gillet 2013) and Piqued's extra shapes (MIT, Phazerville); stepped at the grid. The vendored Peaks envelope is the test oracle | GATE, CLOCK | ENV, EOC, ACTIVE | ATK, DEC, SUS, REL; DELAY, HOLD, CURVE A, CURVE D; TRIG MODE (gate, trigger, looping, by clock), CLOCK MODE (no stretch, stretch all, stretch sustain), VEL→AMT, VEL→ATK; a JOINT TIME macro | under 64 B; 40–100 cycles; about 1.5 KB tables | 1 |
| **Curves** (CRV) | an arbitrary function generator: Buchla 248 MARF, disting NT Envelope Sequencer, crow's ASL, Phazerville's VectorEG and EnvSeq | Own+: the segment engine of Phazerville's `HSVectorOscillator.h` (MIT, Jason Justian 2018, reworked by Bryan Head), with its fixed 16,666 Hz rate replaced by the grid. ASL (GPL-3.0) and the MARF give semantics only. EnvSeq (MIT, Daniel Gorgan 2026) is the spec for per-stage probability and repeats | TRIG/GATE, CLOCK, RESET; ADDRESS | OUT, STAGE (a trigger on entering a stage), EOC, INDEX | pattern data: 16 stages, one per white key, each LEVEL, TIME (ms or steps), SHAPE (step, linear, exp, log, sine, over, under, rebound), FLAGS (sustain, loop start, loop end, stop, pulse), PROB, REPEAT. Parameters: MODE (envelope, LFO, clocked, addressed), LENGTH, TIME SCALE, LEVEL SCALE, OFFSET, QUANTISE, RANDOMISE, SNAPSHOT | about 100 B per pattern, 8 snapshots about 800 B; 30–50 cycles | 1 |
| **Draw** (DRW) | Nick Yablon's Cessna AWG; disting mk4 K-2 and K-4 | Own+ after Cessna AWG (MIT, © 2025 Nick Yablon [verified LICENSE]): bins, Hermite smoothing, the travelling Ripple and Kink | CLOCK, TRIG | OUT, EOC, STEP | pattern data: 16 bins on the white keys. RATE or SYNC, SMOOTH, MODE (LFO, one-shot, stepped), LEVEL; MOD MODE (ripple, kink), AMOUNT, SPEED, MORPH (between snapshots) | 16–128 B; 20–40 cycles | 2 |
| **Bounce** (BNC) | Mutable Peaks' bouncing ball | Port, byte-identical (MIT, Gillet 2013), at 48 kHz through the accumulator. Phazerville's four-ball Dialectic Ping Pong (MIT) is the precedent | TRIG | OUT, HIT (a trigger at each bounce; ours) | GRAVITY, BOUNCE, HEIGHT, VELOCITY | 24 B; about 700 cycles per block (0.2 %); 514 B `lut_gravity` | 1 |
| **Vactrol** (VAC) | Mutable Streams' vactrol and envelope | Port (MIT, Gillet 2014) at 31,089 Hz through the accumulator | EXCITE; IN | GAIN, CUTOFF | ATTACK, DECAY, AMOUNT, MODE (gate, pluck) | about 60 B; about 45 samples × 60 cycles per block (0.8 %); about 3 KB | 3 |
| **Accent** (ACC) | the TB-303 accent circuit, via the disting NT's accent sweep and the Devil Fish write-up | Own (a one-pole charge model) | TRIG | OUT | DECAY, CHARGE, SHAPE, LEVEL | 8 B; under 15 cycles | 2 |
| **Slopes** (SLP) | Mannequins Just Friends | Own. The firmware repository has only binaries and the Technical Map has no licence [verified tree and licence] | TRIG (cascades down unpatched slopes); RUN | 1–6, MIX | TIME, INTONE (speed ratios 1/n..n), RAMP, CURVE; MODE (transient, sustain, cycle), RUN, SYNC, LEVEL | about 60 B; 180–300 cycles; 1 KB curve table | 2 |

**Function** is the slope core every classic function generator shares: a
slew limiter that can drive its own target to full scale [verified: the Maths
and Contour 1 manuals' text]. Its retrigger policy is one control, because
the originals differ: Maths accepts a reset only while falling, Just Friends
ignores triggers while active, and Contour 1 restarts from zero [verified:
manuals and the Technical Map].

**Curves versus Segments.** Curves draws one function from a list of stages,
edited on the keys. Segments (§3.3) builds envelopes, LFOs and sequencers from
six segments whose grouping changes with what is patched. They overlap on
purpose: Curves is the "arbitrary function generator", Segments is the
"something like Stages".

### 3.2 LFOs and cyclers

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **LFO** (LFO) | the options note's LFO: Schwung's `lfo_common.h` semantics, Elektron's modes, Peaks' LFO shapes; disting mk4 B-5 (one SHAPE axis) and NT LFO (wave mix, phase lock) | Own+: shapes from Peaks' LFO (MIT); Schwung (MIT) rewritten, avoiding its S&H wrap bug [verified in the options note] | RESET | OUT, QUAD (90° behind), WRAP (a trigger) | RATE or SYNC, SHAPE (or MORPH), DEPTH, PHASE; MODE (free, trig, hold, one, half), FADE, MULT, WAVE MIX | about 32 B; 60–150 cycles | 1 |
| **Orbit** (ORB) | Mutable Tides (2018) | Port, byte-identical (MIT, Gillet 2017), at the grid. The wrapper passes the sequencer's phase as Tides' external ramp, so sync is sample-exact with no PLL [verified: `Render` takes a ramp pointer] | TRIG, CLOCK | OUT1–4, EOA, EOR (gates in GATES mode) | FREQ or RATIO, SLOPE, SHAPE, SMOOTH; SHIFT, RAMP MODE (AD, cycle, AR), OUT MODE (gates, amplitude, phase, frequency), RANGE | about 0.3 KB; 150–250 cycles; 37,948 B of tables [verified sizes] | 2 |
| **Swirl** (SWL) | Mutable Frames' poly LFO; Phazerville's Quadraturia | Port (MIT, Gillet 2013), increments rescaled from 24 kHz to the grid; Quadraturia's per-channel ratios and AM chain (MIT) as later options | RESET | OUT1–4 | RATE, SHAPE, SPREAD, COUPLING; SHAPE SPREAD | about 40 B; about 150 cycles; about 5.3 KB [verified: `wt_lfo_waveforms` 4,626 B plus `lut_increments`] | 2 |
| **Tangle** (TGL) | John Berndt's relabi, via Phazerville's Relabi | Port (MIT, Samuel Burt 2024 with Jason Justian [verified header]) | RESET | LFO1–3, GATE1–3 | per LFO FREQ, XFM, PHASE, THRESH; global RATE × num ÷ den | about 60 B; light float | 2 |
| **Scenes** (SCN) | Phazerville's Scenery; Mutable Frames' keyframer | Own+: our `Evaluate` and easing after `keyframer.cc` (MIT); Scenery (MIT, Nicholas J. Michalek 2023 [verified header]) for jumps and bias. Not `keyframer.cc` whole: it needs STM32 storage | JUMP, STEP | OUT1–4, NEAR (gate) | pattern data: 16 snapshots × 4 values. POSITION, EASING per channel (step, linear, in-quartic, out-quartic, sine, bounce), SLEW, BIAS | about 150 B; negligible | 2 |
| **Motion** (MOT) | disting EX's knob recorder; Workshop card 90 Pantograph | Own+ after Pantograph (MIT, Kenny Shen 2026 [verified LICENSE; its `info.yaml` is blank]) | — (the knob being recorded) | OUT1–4, END | LENGTH (1–4 bars, locked to the sequencer), SPEED (bipolar: freeze, reverse, faster), SMOOTH, MODE (loop, one-shot) | pattern data 256 B per knob per bar (7-bit, 1/16 step); up to 4 KB | 3 |

**Phase lock between LFOs** is a cable, not a setting: LFO1.WRAP → LFO2.RESET
with LFO2's PHASE set gives the disting NT's locked pairs, and QUAD gives
quadrature inside one LFO.

**Motion** records a knob turned while REC is held in RACK and plays it back
as an offset on that knob's parameter, so rule M1 holds. It overlaps
sequencer locks on purpose: locks are per step, Motion is continuous.
Workshop card 14 CVMod (MIT, Chris Johnson 2025) adds four read heads on one
loop; a later MODE.

### 3.3 Segment generators

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Segments** (SEG) | Mutable Instruments' Stages | Two paths, both MIT (Gillet 2017 [verified headers]): (a) `segment_generator.cc` vendored byte-identical at 31,250 Hz as the desktop **oracle**; (b) our control-rate rewrite of `Configure` and the process functions, with `chain_state.cc`'s grouping, as the **device kind**, checked against (a) within a stated tolerance | GATE1–6 | OUT1–6, EOC, STEP | per segment TYPE (ramp, step, hold), LOOP, PRIMARY (level or time), SECONDARY (shape, glide, time or probability); RANGE. 25 parameters | (a) about 3 KB per generator, 18 KB for Stages' six; 2–8 % of a core; 23,556 B of tables [verified sizes]. (b) under 0.5 KB, plus 1,152 B per group that uses a hold-delay; 300–600 cycles | 1 |

**How Segments behaves**, as Stages does [verified: `process_fn_table_` in
`segment_generator.cc` 875–899 and `ChainState::Configure`]:
- A segment whose gate input has a cable starts a group; unpatched segments
  to its right extend it; unpatched segments before any patched one run
  alone.
- A lone segment is, by type and loop: a ramp (a free LFO when looped, a
  decay envelope when gated, a tap-tempo LFO when gated and looped); a step
  (slew when ungated, sample-and-hold when gated); a hold (a CV delay
  ungated, a timed pulse gated, a probabilistic gate gated and looped).
- A group whose first segment is not a looped step, followed by at least two
  steps, is a step sequencer whose direction the first segment's knob picks
  (up, down, up-down, alternating, random, random without repeat,
  addressable).
- Patching in the matrix therefore reconfigures the module, as patch cables
  do on the hardware. Ranges: ramps from 1 ms to 16 s; free LFOs 0.128–32.7 Hz;
  glide 0.1 ms–4 s [verified arithmetic from `lookup_tables.py`].
- Stages' audio-rate oscillator mode and its hidden additive oscillator are
  engine material, not modulation, and are left out.

**Wrapper rules for path (a)** [verified at `08460a6`]:
- `PortamentoRateToLPCoefficient` (line 138) has no clamp, so a secondary of
  1.0 reads `lut_portamento_coefficient[512]`, one past its 512 entries. Clamp
  the secondary below 1.0.
- `RateToFrequency` clamps to `LUT_ENV_FREQUENCY_SIZE`, 4,096, on a 4,096-entry
  table, so index 4,096 is one past. Clamp the primary at 1.999995, as
  Stages' own CV reader does.
- `Configure()` resets to the sentinel segment, so call it only when a type,
  loop flag or gate routing changes.
- Wrap each call in the `stmlib::Random` save and restore (§2.7).
- It needs stmlib's `gate_flags.h` and `delay_line.h` and Tides 2's
  `ramp_extractor` and `ratio.h`, not vendored yet; all MIT [verified].

**Later segment types** from the `qiemem/eurorack` v1.3.0 fork, whose
`segment_generator.*` carry Gillet's MIT header [verified]: Turing, random
LFO, Chen and Thomas attractors, rise-and-fall slew, attenuverter. Its
`stages/envelope.*` and `modes.h` have no header and the repository has no
licence [verified: GitHub licence API], so the six-envelope mode is an idea
only.

### 3.4 Random and chaos

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Chance** (CHN) | the options note's CHANCE: DaisySP `SampleHold`, Workshop card 106's fluctuating and quantised random voltages; disting mk4 B-1 and EX H-2 | Own+ (MIT: DaisySP, Electrosmith; card 106, Matt Allison, MIT in `info.yaml` only, so we write the notice). Plaits' clocked noise and smooth random are vendored | TRIG; IN (internal noise when unpatched) | HELD, SMOOTH, NOISE | MODE (sample-and-hold, track-and-hold, smooth, drift), COLOUR (violet, white, pink, red), SLEW UP, SLEW DOWN; OFFSET (samples after the step's locks), NOISE MIX, LEVEL | under 100 B; 20–60 cycles | 1 |
| **Register** (REG) | Music Thing Modular's Turing Machine; disting mk4 F-5 to F-8 | Own+: Workshop card 20's `turingmachine.h` (MIT, Chris Johnson; `info.yaml` only), Phazerville's `util_turing.h` (MIT, Patrick Dowling 2016) and TwoRings (MIT) | CLOCK, MODIFY (forces a flip) | CV, BIT (gate or trigger), PITCH (SEMI) | CHANGE (bipolar: locked, random, locked double-length inverse), LENGTH, LEVEL, OUT MODE; DIRECTION, SLEW, OFFSET, SCALE | 8–32 B; under 20 cycles | 1 |
| **Dice** (DIC) | Mutable Marbles | Port, byte-identical (MIT, Gillet 2015), T and X/Y generators at the grid; no UI, scale recorder or register mode. Seeded per preset, so its loops repeat | CLOCK, RESET | T1, T2, T3, X1, X2, X3, Y | T: RATE, BIAS, JITTER, MODEL (coin toss, clusters, drums, independent, divider, three states, Markov); X: SPREAD, BIAS, STEPS, SCALE; LOOP: DÉJÀ VU, LENGTH, X RANGE, CONTROL MODE | about 5.6 KB; about 0.25 % of a core at G = 32 plus clock events; 72,744 B of tables [verified: counted arrays; the options note's 96 KB was high] | 3 |
| **Bits** (BIT) | Rob Hordijk's rungler, via Phazerville's RunglBook; the Schlappi Nibbler, via Cumulus | Port: RunglBook (MIT, Jason Justian 2018) and Cumulus (MIT, Jakob Zerbian 2024) [verified headers]; Bastl Kastle 2's rungler (MIT) as reference | CLOCK, FREEZE, RANDOMISE; SIGNAL | LOW3, HIGH3 (CV), BIT A, BIT B (gates) | MODE (rungler, accumulator), THRESHOLD, OPERATION, K | under 16 B; trivial | 2 |
| **Walk** (WLK) | Phazerville's RndWalk; Teletype's DRUNK | Port: RndWalk (MIT, Alessio Degani 2022 [verified header]). Teletype is GPL-2.0, ideas only | CLOCK, Y CLOCK | X, Y | RANGE, STEP, SMOOTH, Y DIVIDE | under 32 B; trivial | 2 |
| **Chaos** (CHS) | Mutable Streams' Lorenz generator; Phazerville's Low-rents (Lorenz and Rössler); disting NT Chaos; Teletype's CHAOS | Port: Streams and Low-rents generators (MIT, Gillet 2014 with Tim Churches 2016), int64 Q24, bit-exact. Own: logistic, cubic, Hénon, Aizawa and Thomas maps (textbook equations; Teletype and the NT are ideas only) | RESET, FREEZE | X, Y, Z | ATTRACTOR, SPEED, PARAM A (ρ), PARAM B (β); LEVEL X, Y, Z, SEED, RESET ON BAR | about 64 B; 50–100 cycles; about 1 KB rate table | 2 |
| **Numbers** (NUM) | Phazerville's Quantermain sources and Pigeons | Port: `util_integer_sequences.h` (MIT, Tim Churches 2016 [verified header]): π, Van Eck, Nørgård's infinity series and others; `util_logistic_map.h`; Pigeons (MIT, Michalek 2023) | CLOCK, RESET | CV, PITCH (SEMI) | SEQUENCE, MODULUS, LOOP START, LENGTH, STRIDE, BROWNIAN % | tiny | 3 |

**Chaos** at the grid needs its step scaled by 31,089 / tick rate. A large
step makes Euler integration unstable, so the top rate is capped or the
generator takes 2–4 sub-steps per tick [inferred].

**An owner decision for later:** Workshop card 62 BioMimicry (Andy Jenkinson,
2026) has six "ecosystem" engines, among them coupled oscillators that drift
between sync and swarm, and leaky buckets that overflow into each other. It is
CC BY 4.0 [verified LICENSE]: adaptation with credit is allowed, including
commercially, but it is not a software licence. A **Swarm** module would need
the owner to accept CC BY code.

### 3.5 Sequencing sources

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Coin** (COI) | Mutable Branches | Own, from the manual's behaviour. `branches.cc` is GPL-3 [verified], not copied. MIT references: Marbles' coin-toss T model, Phazerville's Brancher | IN | A, B | PROB, MODE (direct, toggle), LATCH | 4 B; event rate | 1 |
| **Divide** (DIV) | Phazerville's ClockDivider, ProbDiv, Shuffle and GateDelay; Piqued's Euclidean filter | Own+ after those applets (MIT: Justian, Michalek, Rosenbach, Kyme [verified headers]) | CLOCK, RESET | OUT1, OUT2 | per channel MODE (divide, multiply, Euclid, probability), VALUE, FILL or PROB, ROTATE; SWING, DELAY | under 32 B; trivial | 1 |
| **Burst** (BST) | Mutable Peaks' pulse shaper and randomiser; Phazerville's Burst; Just Friends' VOLLEY; disting NT Delayed Function | Port: Peaks' `pulse_shaper` and `pulse_randomizer` (MIT, Gillet 2013) at 48 kHz in Peaks' 4-sample blocks, since their counters count calls; plus Burst (MIT, Justian 2018) | TRIG, CLOCK | OUT (triggers), GATE (while bursting), DONE | MODE (burst, delay, random), COUNT, SPACING or DELAY, ACCEL; JITTER, ACCEPT %, REPEAT %, LENGTH | 64–256 B; tens of cycles per block | 1 |
| **Grooves** (GRV) | Mutable Grids | Own: the algorithm (bilinear blend of the 4 nearest of 25 drum maps, per-part random perturbation, density thresholds, accent, a Euclidean mode, swing) with **maps we author**, for example from Marbles' 18 MIT drum patterns. Every `grids/*` file is GPL-3, and so are the map headers Phazerville's DrumMap includes [verified] | CLOCK, RESET | BD, SD, HH, ACCENT | MAP X, MAP Y, CHAOS, MODE; BD, SD, HH density, SWING | about 2.4 KB of maps; negligible | 2 |
| **Field** (FLD) | Phazerville's Shredder; Teletype's turtle | Own+ after Shredder (MIT); the turtle (GPL-2.0) as an idea | CLOCK | CV, X, Y | SEED, SIZE, X, Y, SPEED, HEADING, WRAP | 64–256 B | 3 |
| **Life** (LIF) | Conway's Game of Life, via Phazerville's GameOfLife | Own (the applet has no header [verified]) | CLOCK, DRAW | DENSITY, LOCAL | CELL WEIGHT, X, Y | about 1.3 KB | 3 |

**Grooves' GPL original** can go only into a personal build behind
`FM1_GPL_MODS`, never into the public simulator (CLAUDE.md licence rule).
Marbles' drum model in Dice already gives an MIT groove source.

### 3.6 Utilities

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Slew** (SLW) | disting mk4 B-2; Phazerville's Slew; Just Friends' STRATA (six time constants from one input) | Own | DEFEAT; IN | OUT, OUT2–6 when spread | UP, DOWN, TYPE (linear, exponential), SPREAD | about 10 cycles per output | 1 |
| **Quantize** (QNT) | Mutable Braids' quantiser, as Phazerville's Quantermain uses it | Port: `braids/quantizer.*` and its scales (MIT, Gillet 2015 [verified header]; not vendored yet) | CLOCK (optional); IN | PITCH (SEMI), CHANGED (trigger) | SCALE, ROOT, RANGE, TRANSPOSE | small; scale tables a few KB | 1 |
| **Compare** (CMP) | disting mk4 A-7; Phazerville's Compare, Schmitt and Trending; Utility Pair's window comparator; Contour 1's slope gates | Own+ (MIT: Phazerville, Justian; Utility Pair, Chris Johnson 2025 [verified LICENSE]) | A, B | GATE, NOT, RISE, FALL (triggers), ABOVE, INSIDE, BELOW | MODE (A > B, window, trend), THRESHOLD, HYSTERESIS, WIDTH | under 10 cycles | 1 |
| **Logic** (LOG) | disting NT Logic; Phazerville's Logic and TL Neuron | Own+ (MIT: Justian) | A, B | OUT, NOT | OP (AND, OR, XOR, NAND, NOR, XNOR, SR flip-flop, D flip-flop, toggle) | trivial | 1 |
| **Calc** (CLC) | Mutable Kinks and Links (analog, no code); disting mk4 A-1 to A-5; Phazerville's Calculate; Workshop card 107 Scintillator | Own+ (MIT: Calculate, Justian; card 107, Matt Allison, MIT in `info.yaml` only). Logarithm and square root by table, no libm | A, B | OUT, INV | OP (sum, difference, product, min, max, mean, \|A\|, half-wave, −A, crossfade, log, root, square, slope), OFFSET (semitone-quantisable), AMOUNT | under 30 cycles; under 1 KB tables | 1 |
| **Mix** (MIX) | Mutable Links and Shades (analog); disting EX Matrix Mixer; Phazerville's AttenuateOffset and Combin8 | Own | IN1–4 | SUM, AVG, INV | GAIN1–4 (±200 %), OFFSET | trivial | 1 |
| **Switch** (SWI) | Phazerville's Switch and Xfader | Own+ (MIT: Justian, Michalek) | STEP, GATE; IN1–4 | OUT | MODE (sequential, gated, crossfade), RATE, SPRING | trivial | 2 |
| **Filter** (FLT) | the owner's request of 2026-10-02; the trapezoidal state-variable filter as Andrew Simper (Cytomic) published it | Own | PING; IN | OUT (blend), LP, BP, HP | CUTOFF (0.05–409.6 Hz, log), RES (to undamped: rings for ever when struck), BLEND (LP–BP–HP), LEVEL, STRIKE | 40 B [verified]; about 30 operations per tick | 1 (built in MG2) |

**Filter versus Slew.** Slew limits the rate of change or lags with one
pole; it never overshoots and knows no frequency. Filter is
frequency-selective: LP smooths at 12 dB per octave and can ring, BP and HP
take out the slow part of a signal, and a gate into PING strikes it into a
decaying sine at its cutoff, a resonant "wobble" source (engines/mod/kinds.md).

Sample-and-hold lives in Chance (its IN input), so there is no separate S&H.
**TO NOTES**, a sink that turns a pitch CV and a gate into notes on the sound
unit, and **TAP** sources, which expose a destination's final value as a
source, come later (§6.4).

### 3.7 Followers (from audio)

The FM-1's two jacks are stereo audio out and MIDI in [verified: docs/01, jacks
row], so a follower listens to an internal tap (USB audio from a computer is a
possible later source, untested): the sound before its effects, FX1's output,
FX2's output, or the master bus. A kind flagged AUDIO_TAP makes the host split
the tapped unit's render at tick frames, so a tick reads the audio of the
interval it closes [inferred].

| Module | After | Code | In | Out | Key parameters | Cost | Wave |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Follow** (FOL) | Mutable Streams' follower; Ears (analog); disting mk4 B-3 | Port: `streams/follower.*` and `svf.*` (MIT, Gillet 2014). Never `streams/ui.h`, which includes GPL-3 `stmlib/ui/event_queue.h` [verified]. The gate is ours | — (TAP parameter) | ENV, BRIGHT, GATE | TAP, ATTACK, DECAY, THRESHOLD | about 0.15 KB; 100–150 cycles per audio sample: 1.8–2.8 % of a core, half when decimated by 2; about 6 KB | 3 |
| **Duck** (DCK) | Mutable Streams' compressor | Port (MIT) | — (TAP and KEY parameters) | REDUCTION | TAP, KEY, THRESHOLD, RATIO | as Follow | 3 |

Streams' coefficient tables are for 31,089 Hz, so at 44,118 Hz its time
constants and band splits move by 1.42×. That is acceptable for a follower;
decimating the tap by 2 brings it close [inferred].

### 3.8 Not modules: left out, ideas only

| Source | Licence | Use |
| --- | --- | --- |
| monome Teletype (CHAOS, DRUNK, EVERY, patterns, turtle) | GPL-2.0 [verified LICENSE] | ideas for Chaos, Walk, Field and retrigger conditions |
| monome crow's ASL (`to`, `loop`, `held`, `lock`, `dyn`; shapes over, under, rebound) | GPL-3.0 [verified] | the vocabulary for Curves, clean-room |
| monome Ansible (Meadowphysics' cascading counters) | GPL-2.0 [verified] | idea: a counter whose wrap is an event |
| Mutable Branches and Grids (AVR) | GPL-3 [verified] | Coin and Grooves are our own; originals only behind `FM1_GPL_MODS` |
| Phazerville's `DrumMap.h` | MIT itself, but includes GPL-3 Grids map headers [verified] | not taken |
| Phazerville's `EbbAndLfo.h`, `tideslite.*`, `GameOfLife.h`, `ShiftGate.h`, `MiniSeq.h`, `Ponglet.h`, `waveform_library.h`; `DuoTET.h` (a copyright line only) | no licence text [verified] | ideas only; redraw the vector presets |
| Bytebeat equations in Phazerville (Equation Composer, BitWiz) | Equation Composer has no licence [verified]; BitWiz's permission was given to O_C | not taken; a bytebeat source would need our own equations |
| The Schwung port of TB-3PO | GPL-3.0 [verified] | not taken (Phazerville's own `TB3PO.h` is MIT, for the arp lane) |
| Just Friends, Maths, Contour 1, Buchla 281 and 248, Serge DUSG, Quadrax | closed firmware or hardware | ideas for Function, Quad, Slopes, Curves |
| Disting mk4, EX and NT algorithms | closed firmware | ideas (§3.9) |
| `thorinside/nt_helper` | no licence [verified] | facts about NT algorithms only |
| Befaco Rampage (VCV), Bogaudio, Count Modula, Audible Instruments, 4ms MetaModule core modules | GPL-3.0(+) [verified] | not needed |
| Vult modules | no source in the repository [verified] | none |
| Workshop cards 03, 06, 15, 21, 29, 41, 74, 78, 82, 93 (GPL-3), 666 (GPL-2), 13 (CC BY-NC-SA) | [verified `info.yaml`] | not taken; MIT equivalents exist |
| Workshop card 67 | `info.yaml` says CC0, `LICENSE.md` says CC BY-NC-SA 4.0 [verified] | treated as non-commercial |
| Workshop cards 04, 07, 09, 23, 99 | no licence [verified] | ideas only |

### 3.9 Disting algorithms and where they land

The disting firmware is closed, so each useful algorithm is an idea for one
of our modules [verified from the manuals' text unless marked]:

| Disting algorithm | Lunar module |
| --- | --- |
| mk4 A-1 Precision Adder, A-2 Four Quadrant Multiplier, A-3 Full-wave Rectifier, A-4 Min/Max | Calc |
| mk4 A-7 Comparator; NT Logic and Slope Detector [reported: nt_helper] | Compare, Logic |
| mk4 B-1, EX H-2, NT Sample and Hold | Chance |
| mk4 B-2 Slew; NT Slew [reported] | Slew |
| mk4 B-3 envelope tracker; NT Envelope Follower [reported] | Follow |
| mk4 B-5 and B-6 LFO; NT LFO (wave mix, phase lock, stepped versus linear quality) | LFO |
| mk4 E-1 AR envelope (joint time), F-1 to F-4 clockable AD; EX Quad Envelope (shared shapes, clock stretch, EOC and active outputs); NT Envelope (DAHDSR) [reported] | Envelope |
| mk4 F-5 to F-8 shift-register randoms | Register |
| mk4 H-6 delayed pulses; NT Delayed Function [reported] | Burst (delay mode) |
| mk4 K-2 and K-4 clockable wavetable LFO and envelope | Draw |
| EX Matrix Mixer | Mix |
| EX and NT knob recorders | Motion |
| NT Envelope Sequencer [reported] | Curves (clocked mode) |
| NT Chaos (Lorenz, Rössler, Aizawa, Arneodo, Thomas) [reported] | Chaos |
| NT Accent sweep [reported] | Accent |

**What is open around the disting** [verified licences]: the NT plug-in API
(MIT, © 2025 Expert Sleepers), the NT's Lua scripts (MIT or Unlicense, file by
file), NerdRoger's NT plug-ins (MIT; a window comparator and a directional
sequencer with a modulation matrix), and `thorinside/nt_emu` (MIT), which
runs the same plug-in source in VCV Rack. The last is the same pattern as our
native and browser parity: one C source per module, built for both.

## 4. Budgets

All figures are [inferred] unless marked. The 64-frame block at 44,118 Hz is
348,160 cycles at 240 MHz, and the stock layout leaves 387,924 B of SRAM
[verified: docs/11 §2; `FM1_APP_RAM_BUDGET`]. The sequencer's half budget is
full at 8 tracks (36,216 of 36,864 B, docs/15 §2.6), so modulation needs a
budget line of its own.

### 4.1 Fixed state (8 positions, 32 slots)

| Item | Arithmetic | Bytes |
| --- | --- | --- |
| Slots | 32 × 12 | 384 |
| Module parameter bases | 8 × 32 × 4 | 1,024 |
| Outputs, current and previous | 8 × 8 × 4 × 2 | 512 |
| Gate edges, current and previous | 8 × 8 × (1 + 4 × 2) × 2 | 1,152 |
| Plan, two buffers | order, per-destination slot lists, delayed mask | ≤ 512 |
| Routed sink bases | 32 × (unit, index, uid, value) = 32 × 8 | 256 |
| System sources | 64 × 4 | 256 |
| Pending system gate edges | 64 × 4 | 256 |
| Instance table | 8 × 16 | 128 |
| **Total** | | **4,480** |

**Measured in MG1** [verified 2026-10-02: `fm1-render --list-mod`, at 32 and
64 bits]: 11,824 B of fixed state, so `fm1_mod_size()` is 20,016 B with the
8 KB arena, 5.2 % of the 387,924 B gap. The estimate left out copies that a
state without pointers needs: each bound unit's parameter ranges (1,920 B),
bases, sent values and offsets per sink parameter (1,536 B), effective
module parameters (1,024 B) and a tick's write list (784 B).
engines/mod/README.md, "Determinism and memory", has the breakdown.

### 4.2 Module arena

Instances live in one arena owned by the host. Per-kind sizes are in the
catalogue. Almost every kind is under 256 B. The exceptions are Dice (about
5.6 KB), Segments with hold-delays (1,152 B per group), Life (1.3 KB), Motion
(up to 4 KB) and the vendored Segments oracle (about 18 KB, desktop only).

**The default rack** (LFO, LFO, Envelope, Envelope, Chance, Segments,
Function, Calc):

| | Bytes |
| --- | --- |
| LFO × 2 | 64 |
| Envelope × 2 | ≤ 200 |
| Chance | ≤ 100 |
| Segments (device kind, no hold-delay) | ≤ 512 |
| Function | 24 |
| Calc | 16 |
| **Total** | **≤ 916** |

**Recommended arena: 8 KB.** It holds the default rack plus a Dice, or
Segments with one hold-delay group and a Motion. Fixed state plus arena is
4,480 + 8,192 = 12,672 B, **3.3 % of the 387,924 B gap**. A 16 KB arena makes
it 20,864 B, 5.4 %.

### 4.3 CPU

Per tick, in cycles: a slot 30–60; a destination about 20, plus `set_param`
when its value changed (about 50, engine-dependent); kinds as in the
catalogue.

**The default rack with 16 slots in use:**

| Item | Cycles per tick |
| --- | --- |
| LFO × 2 | 120–300 |
| Envelope × 2 | 80–200 |
| Chance | 20–60 |
| Segments (device kind) | 300–600 |
| Function | 30–60 |
| Calc | 10–30 |
| 16 slots | 480–960 |
| about 10 destinations, about 6 changed | 500 |
| **Total** | **about 1,540–2,710** |

- **At G = 32**, 2 ticks per block: 3,080–5,420 cycles, **0.9–1.6 % of a
  block**. With all 32 slots in use, 1.2–2.1 %.
- **At G = 16**, 4 ticks per block: 1.8–3.1 %, or 2.3–4.2 % with 32 slots.
- **Render splits.** Each routed unit takes one more render call per block at
  G = 32, three more at G = 16. The cost of a call on pi32v2 is unknown until
  stage B.

**Heavier kinds, per instance:**

| Kind | Cost per block | Share of a core |
| --- | --- | --- |
| Segments oracle, 6 groups at 31,250 Hz | 45.33 samples × 6 × 25–100 cycles | 2.0–7.8 % |
| Follow, at the host rate | 64 × 100–150 | 1.8–2.8 % |
| Vactrol, 31,089 Hz | about 45 × 60 | about 0.8 % |
| Bounce, 48 kHz | about 70 × 10 | about 0.2 % |
| Dice, at the grid | | about 0.25 % plus clock events |
| Orbit, at the grid | 2 × 150–250 | under 0.15 % |

The two vendored oracles (Segments, the Peaks envelope) run only in desktop
tests. On the device the control-rate kinds are used.

### 4.4 Flash

| Item | Bytes |
| --- | --- |
| Core, planner and the first-wave kinds' code | about 20–40 KB |
| First-wave tables (curves, Peaks shapes, `lut_gravity`, Peaks delay times, quantiser scales) | about 5–10 KB |
| Segments device kind: an exp2 table in place of Stages' 16 KB `lut_env_frequency` | about 1–2 KB |
| Orbit (Tides 2) | 37,948 [verified] |
| Dice (Marbles) | 72,744 [verified] |
| Swirl (Frames) | about 5.3 KB [verified sizes] |
| Follow, Duck, Vactrol, Chaos (Streams subset) | about 6–14 KB |
| Everything in the catalogue | about 165 KB of tables, plus code |

For scale: the app area is about 852 KB in FM-1+VA's layout [verified:
docs/11 §2], and the desktop build already carries 74.7 KB of Plaits tables and
56.4 KB of Braids tables [verified by the Mutable lane: `size -m` on the
objects]. Peaks' 36,824 B `wav_digits` table must be dropped by the linker
(`-fdata-sections`, `--gc-sections`).

### 4.5 Presets and the simulator

- **Presets:** 8 positions × (guid 4 B + 32 parameters × 2 B) + 384 B of slots
  + 8 B of display order = 936 B, plus pattern data: Curves about 800 B with 8
  snapshots, Scenes about 150 B, Draw up to 128 B, Motion up to 4 KB (owner
  decision: Motion's recordings saved with the preset or the set).
- **The simulator:** `fm1_app_t` (1,168,288 B natively today [verified:
  `sim/web/README.md` 144]) grows by about 4.5 KB plus the arena. `fm1.wasm`
  (391,277 B [verified: docs/15 §2.6]) grows by about 20–40 KB of code, more
  as the big tables arrive (Dice adds about 73 KB). All of it fits the
  module's fixed 8 MiB. The on-screen RAM figure adds `fm1_mod_size()` plus
  the arena.

## 5. The UI

### 5.1 Buttons

ENV, LFO and EDIT open the "not in the simulator yet" popup today, and
docs/15 §3.12 keeps them unassigned [verified]. Proposed [inferred]:

| Button | Function |
| --- | --- |
| **LFO** | RACK: the modules, one page at a time |
| **EDIT** | MATRIX: the slot list. SEL in MATRIX opens CHAIN |
| **ENV** | PATCH: a tap arms the selected module's output 1, then 2, and so on, then off. While armed, a KNOB1–4 turn on HOME, FX or RACK sets the amount of a cable from the armed output to that knob's parameter, creating the slot if needed. Holding ENV and turning a knob does the same for that one turn (the options note's quick assign) |
| **SEL** | In RACK, a tap grabs the module so SELECT moves it in the rack, as SEL does in FX mode. Held, it turns the white keys into stage, bin or scene selectors on modules with pattern data |

LEDs: LFO lit in RACK, EDIT lit in MATRIX, ENV blinking at 0.25 s while PATCH
is armed (the simulator's two blink periods [verified: docs/15 §3.13]).

### 5.2 RACK (LFO)

FX mode's geometry [verified: `fm1_app.c` constants: content from y 28, rows
36 px apart, bars 22 px below each row and 7 px tall, bottom bar at y 216, 4 px
gaps]:
- **Title bar:** the module's name, e.g. `Segments`.
- **y 28–46:** one graphic box with 8 cells of 26 px (2 px apart), one per
  rack position. Each fills to its module's first output; the selected cell
  is outlined; an empty position is hollow.
- **y 50:** a text line, e.g. `3 SEG  >2 <1 ~1`: position, kind, cables out,
  cables in, delayed cables.
- **From y 72:** four parameter rows; the last bar ends at y 209, 7 px above
  the bottom bar.
- **Bottom bar:** `2/7 Mod3`, the page and the rack position.

| Control | Action |
| --- | --- |
| SELECT | walks (module, page) pairs |
| ALGORITHM | opens the kind picker for this position (a 3-line popup, as PRESETS uses); it commits after 1 s idle |
| KNOB1–4 | the page's parameters |
| SEL (tap) | grab, then SELECT reorders; this matters only inside loops |
| SEL (held) + white key | on Curves, Draw and Scenes: select stage, bin or scene N. The key does not sound |

RACK and MATRIX treat SEL as FX mode does: docs/15 (O2) makes SEL the SHIFT
key in the other modes, and these two pages need no SHIFT functions.

**Module views.** A kind with a `view` gets a first page drawn from it,
between y 28 and y 209:
- Segments: six cells with group brackets, loop arcs and a moving dot;
- Curves and Draw: the curve, with the playhead and the selected stage;
- Orbit and Swirl: four overlaid traces;
- Chaos: an X–Y trace;
- Scenes: four bars and the snapshot markers.

### 5.3 MATRIX (EDIT)

Eight text lines fit between y 28 and the bottom bar at 22 px apart
[verified: `LINE_PITCH` 22, 18 px text]. Seven are slot rows and the eighth is
a hint line:

```
 LFO1  >2Rise   +40
 FUN2.6>3Gate1 +100
 SEG3.1>4Trig  +100
 CHN4  >Timbre  +60
 CHN4  ~1Rate   +12
 LFO1  >F1Mix   -25
-CHN4  >Pitch   +10
Slot 5 to LFO1 Rate
```

These are the §1 chain's slots, plus two more.
- A row is a state column (`-` when the slot is off), the source (6
  characters), `>` (or `~` for a delayed cable), the destination (6
  characters) and the amount (5 characters): 19 characters, one line's worth
  [verified: `LINE_CHARS` 19]. The selected row is drawn inverted.
- A destination on another unit is prefixed: `2Rise` is module 2's RISE,
  `F1Mix` is FX1's mix. A sound parameter needs no prefix.
- The hint line shows the selected slot in full, or the field being turned.
- SELECT moves the row.
- **Page A:** K1 source, K2 destination, K3 amount, K4 offset. K2 opens the
  destination picker (3 lines, as PRESETS); while it is open, ALGORITHM jumps
  between groups (SND, FX1, FX2, HOST, MOD1–MOD8). It commits after 1 s idle.
- **Page B** (ALGORITHM with the picker closed): K1 VIA, K2 CURVE, K3
  POLARITY, K4 ON.

### 5.4 CHAIN (SEL in MATRIX)

Eight lines that alternate node and cable along the longest path through the
selected slot (ties by slot number), with `+2` where a node has two more
branches:

```
LFO1
 +40 >2 Rise
FUN2 EOC
+100 >3 Gate1
SEG3 Out1
+100 >4 Trig
CHN4 Held  +1
 +60 >Timbre
```

`+1` says CHN4 has one more cable out (slot 5, back to LFO1). A delayed
cable's line ends in `~`.

### 5.5 Every parameter page

On HOME, FX and RACK pages, a routed parameter gets a marker by its label, a
bracket of ± its total amount on the bar, and a 1 px tick at the live
effective value. The 4 px gaps stay. Labels come from `abbr`, or are cut
without it.

**Layout check.** Every new screen joins the layout sweep: the longest names
and values; 0, 1, 7 and 32 slots; a loop with `~`; an armed PATCH; each module
view. 0 faults and at most 96 logged boxes per screen [verified limit:
`FM1_TFT_MAX_BOXES` 96]. The geometry above is [inferred] until that sweep
passes.

## 6. How it fits the rest

### 6.1 Sequencer locks: a base plus an offset

The options note's rules M1–M7 hold unchanged. Restated for modules:
- **A lock writes a base, never an offset** (M1). It can now target a module
  parameter (`mod3:Level2`) or a slot's depth (`mtx:12.amt`) as well as an
  engine parameter (`synth:<Name>`, S7a). A lock on an unrouted engine
  parameter still goes straight to `set_param` at its frame, as today.
- **So a step can reshape a modulator**: Segments' level on this step, Curves'
  time scale on that one, a cable's depth on a third, as Elektron locks LFO
  depth.
- **D6's revert at Stop restores bases** (M2). Modules keep their mode: a
  free LFO keeps running, a triggered one waits.
- **The 8-lane cap and 7-bit values are unchanged.** A 7-bit lock maps
  v to (v − 64) / 64 on a slot's amount.
- **MACRO 1–4** are lockable host parameters read as sources, so any
  sequencer lane becomes a modulation source without new sequencer code (M3).
- **Order at one frame** is M6 (§2.6).

### 6.2 The sequencer as a source

- **Gates and clocks:** SEQ track 1–8 gate and velocity, CLOCK, BEAT, BAR,
  RUN and START are system sources with the exact frames `fm1_seq` emits.
- **Transport:** kinds flagged TRANSPORT get tempo, running state and the
  sequencer's position at the start of each tick. That needs tempo and a beat
  position in `fm1_host_t`, planned with API v2 in the options note but not
  yet in S7a's scope (MG1 adds them if nothing else has). Orbit uses it as
  Tides' external ramp; LFO, Function, Divide and Curves use it for SYNC.
- **START** calls `reset(START)` on TRANSPORT kinds, so synced phases begin
  together.

### 6.3 Per-voice modulation later

The options note's stage C2 still applies [inferred]:
- kinds flagged POLY_OK (Envelope, LFO in trig mode, Curves one-shot,
  random on note) get one instance per voice from the arena;
- VOICE-scoped slots run per active voice and reach engines through an API v2
  `set_param_mod(index, key, offset)`;
- poly to mono cables are refused, as Surge's `canModulateMonophonicTarget`
  does [verified at `348cfb3`]; mono to poly is allowed;
- per-voice sources never reach effects or engine-wide parameters.

Cost: about 12 × the per-instance cost for each poly kind in use [inferred].

### 6.4 The arpeggiator and MIDI effects

- **From notes:** key gate, note trigger, velocity, note number and a random
  value per note are system sources, from the panel and USB-MIDI.
- **From the arp** (the first `FM1_KIND_MIDI_FX`, options note §2): its step
  trigger, gate and random value become system sources when it lands.
- **Into notes, later:** a TO NOTES sink takes a pitch CV and a gate (for
  example Register → Quantize → TO NOTES) and plays notes on the sound unit,
  exactly one tick late, before the arp. That closes the eurorack loop of
  generative melody.
- **Grooves' gates** can drive a sequencer drum track only through TO NOTES or
  a later MIDI_FX kind.

## 7. Extensibility: adding a module kind

**One kind, one pull request** [inferred]:
1. Write `engines/mod/kinds/mod_<id>.c` (or a C++ wrapper around vendored
   code, as `engines/src/mi_*.cc` wrap Plaits and Braids).
2. Add one line to the registry (`engines/mod/registry.c`), like
   `engines/src/registry.cc`.
3. Add its uids to `tests/fixtures/mod-uids.json` and a golden trace
   (`fm1-render --mod` with `--log-mod` JSONL).
4. The generic tests pick it up: any-fill, NaN, block-size identity, `nm -u`,
   and the native against wasm parity scenario.
5. Update the kind's `credits`, `UPSTREAM.md` if code was vendored, the
   simulator footer, the manual and CHANGELOG.md in the same PR.

**Helpers for vendored code** live in the core: the native-rate accumulator
and edge placement (§2.6), the `stmlib::Random` save and restore, and volt to
range conversion.

**Licence placement.**
- Vendored MIT or BSD code goes under `engines/third_party/<name>/` with
  `UPSTREAM.md`; Mutable code joins `engines/third_party/mutable/` through
  `vendor.py`'s `ROOTS` (adding stmlib's `gate_flags.h`, `delay_line.h`,
  `ring_buffer.h` and `pattern_predictor.h`, all MIT [verified]).
- GPL-derived kinds register only under `-DFM1_GPL_MODS`, in personal builds.
  The public simulator leaves them out: a GPL kind there would make the page's
  wasm a GPL work. LXR never goes in the simulator (CLAUDE.md).
- Test folders of Mutable modules are GPL-3 [verified] and are never vendored.

**Compatibility.**
- Presets store each position as `{guid, values by uid}` plus pattern data
  with its version. An unknown uid is ignored and a missing one takes its
  default, so old presets survive new parameters.
- `FM1_MOD_API_VERSION` gates the kind struct. New fields go at the end.

**Later:**
- A kind is a struct of function pointers, so docs/11's RAM-loaded tier can
  load kinds as it loads engines.
- A shim that runs Hemisphere applets unmodified (their controller called
  about 12 times per tick at 16.7 kHz, integer CV) looks feasible but would
  carry their Arduino `random()` calls and heap; porting chosen applets is
  cleaner [inferred].
- A scripted kind belongs to docs/11 §5's scripting tier. The owner wants
  Berry (MIT, under 40 KB of code) explored for it, so that people can write
  simple modulation modules with a few knobs (DEVELOPERS.md, "Research to
  do", item 8). Teletype's and ASL's languages are the other models.

**Upstream candidates** (for `notes/upstream-candidates.md`; drafts only, and
nothing is sent without the owner's sign-off, per CLAUDE.md):
- Stages: clamp the two table indexes in `segment_generator.cc` (one line
  each). Low value: the hardware never reaches them, and the repository has
  had no push since 2023-12-13 [verified].
- Phazerville: ask Bryan Head and the maintainers for licence headers on
  `EbbAndLfo.h` and `tideslite.*`.
- Workshop Computer: card 67's `info.yaml` and `LICENSE.md` disagree; card
  63's LICENSE names BioMimicry.

## 8. Staged plan

Every stage is one GitHub-Flow branch and PR, with the three-part description
and a CHANGELOG entry. Every stage passes:
- **parity:** native `fm1-render` against the wasm module, exact against
  musl, on new scenarios;
- **block-size identity** at 1, 7 and 64 frames with routes active;
- **zero-route identity** against the existing WAVs;
- **layout:** 0 faults and at most 96 boxes on every new screen (UI stages);
- **the staleness gate:** `fm1.wasm` rebuilt on aeon and committed when a
  hashed input changes (docs/15 §6.5).

| Stage | Work | Depends on | Exit |
| --- | --- | --- | --- |
| **MG0** | This document; owner decisions (§9) recorded | — | answers recorded here |
| **MG1** (built 2026-10-02) | `fm1_mod.h`, the core, the planner, the hook in docs/15's host bridge (`engines/seq/seq_host.c`). `fm1-render --mod FILE` (lines such as `mod 1 lfo rate=0.3`, `slot 1 lfo1.out > snd:Timbre amt=40`) and `--log-mod`. Kinds LFO, Envelope and Chance, so the default rack reproduces C1 | docs/15 S1 (the bridge, merged in PR #25) and S7a (uids, plus the MOD and INPUT flags, `abbr`, `unit`); tempo and a beat position in `fm1_host_t`, planned with API v2 in the options note but not in S7a's scope, which MG1 adds if nothing else has | all §2.7 core tests; M1–M7 host tests (a zero amount is a no-op, NOLOCK refused, a lock moves the base while the LFO swings round it, D6 with modulation running) |
| **MG2** (built 2026-10-02) | The glue kinds: Calc, Mix, Slew, Compare, Logic, Coin, Divide, Burst, Bounce, Quantize, Register, Function; and Filter (the owner's addition) | MG1 | golden traces per kind; the chain and feedback tests; Bounce and Burst against upstream Peaks |
| **MG3** | The simulator hosts `fm1_mod`: RACK, MATRIX, CHAIN, PATCH; routed markers on every page; manual chapter; README stub text | MG1–MG2; docs/15 S2 (the app hosts the bridge) | parity scenarios with routes; the layout sweep; panel traces replay through `fm1-render` byte for byte |
| **MG4** | Segments: Stages vendored as the desktop oracle (stmlib and Tides 2 headers added), and the device kind; its view | MG3 | the device kind within a stated tolerance of the oracle over a scripted patch set; the clamp tests at secondary 1.0 and primary 2.0; the group-forming table from `chain_state.cc` reproduced |
| **MG5** | Curves; the pattern-data API in presets; SEL held + white keys as stages | MG3 | pattern round trip; Curves' ENVELOPE, LFO, CLOCKED and ADDRESSED golden traces; layout of the curve view |
| **MG6** | Locks on module parameters and slot amounts; SEQ sources; MACRO 1–4; Motion | docs/15 S8 (locks) and transport | a lock on `mod3:Level2` and on `mtx:12.amt` replays identically; Motion's loop is identical at any block size |
| **MG7** | Second wave: Draw, Orbit, Swirl, Scenes, Tangle, Chaos, Bits, Walk, Quad, Slopes, Accent, Switch, Grooves (our maps) | MG3 | Orbit and Swirl against upstream renders at the grid; Chaos bit-exact native against wasm |
| **MG8** | Heavy and audio: Dice, Follow, Duck, Vactrol; Numbers, Field, Life; TO NOTES and TAP sources; the `FM1_GPL_MODS` switch if the owner wants it | MG3 | Dice's patterns repeat per seed; follower taps identical at any block size; the flash total reported |
| **MG9** | Per-voice (options note C2) | API v2 `set_param_mod` | zero-offset identity per voice; poly to mono refused |

**MG1, as built** (engines/mod/README.md, "The runtime", has the detail
and the tests) [verified 2026-10-02]:
- `include/fm1_mod.h` (the kind contract, slots, the runtime) and
  `include/fm1_mod_host.h` (the bridge glue); `engines/mod/mod_*.c` and
  `kinds/` (LFO, Envelope, Chance on `fm1_mp`).
- The bridge gained `fm1_seq_host_dispatch_ticks`, a control-rate hook with
  the M6 order at one frame, and the sink a `pitch_bend`. Plain dispatch is
  unchanged, so the virtual FM-1 is too until MG3: 816 renders before and
  after are byte-identical.
- Sources: VEL, NOTE, RAND, KEY, TRIG, the sequencer's CLOCK, BEAT, BAR,
  RUN, START and track gates and velocities. Sinks: SOUND, FX1, FX2 (in
  `fm1-render`), HOST PITCH and AMP. MIDI controllers and MACRO 1–4 wait
  for a host that has them.
- `fm1_host_t` is unchanged: tempo and Start reach the kinds through the
  hook, which is all LFO's Sync needs; a beat position waits for Orbit.
- `fm1_mod_size()` is 20,016 B (8,192 B arena and 11,824 B of state), the
  same at 32 and 64 bits; §4.1's 4,480 B estimate left out copies the
  pointer-free state needs (engine ranges, sent values, offsets).
- Differences from §2.2–§2.4: an INPUT parameter takes amount × signal (100 %
  passes the signal); SEMI into SEMI is rounded to 1/1,024 semitone so whole
  notes stay whole; an edge a module makes sits at the boundary after the
  sample that caused it; a gate input can be normalled to a system gate
  (the Envelope's GATE to KEY, the LFO's RESET to TRIG), and a gate input
  carries on from tick to tick, so a cable patched or pulled is an edge at
  the tick's first frame; changing a kind switches its slots off, and
  switching them on again after a change back is the UI's (MG3); in MG1 an
  edit takes effect at the next tick on one task, without §2.5's double
  buffer.

**MG2, as built** (engines/mod/kinds.md has every kind's parameters and
the tests) [verified 2026-10-02]:
- Thirteen kinds in `engines/mod/kinds/`, on MG1's runtime unchanged: the
  twelve above and **Filter**, which the owner asked for on 2026-10-02: a
  resonant trapezoidal state-variable filter at the tick rate whose LP, BP
  and HP are sources and which a gate strikes into ringing.
- **Bounce, Burst and Quantize run ports**, not wrappers: `mod_mi.c` is C,
  statement for statement Peaks' bouncing ball, pulse shaper and pulse
  randomizer and Braids' quantizer, at Peaks' rates (48 kHz per sample for
  the ball, 12 kHz per call for the pulse processors) through §2.6's
  accumulator. `fm1-mod-mi-ref` compiles the vendored originals (added
  through `vendor.py`) into a test tool and finds every output identical:
  2.9 million ball samples, 4.5 million calls each of the shaper and the
  randomizer, 1.2 million of the quantiser, and Bounce and Burst as kinds
  over the same timeline as upstream.
- **Differences from §3:** Burst adds ACCEL and a clocked spacing (both off
  leave it Peaks'); Bounce adds HIT; Quantize drops its held note on a scale
  change; Function's segments keep their time rather than their slope;
  Divide's SWING and DELAY are per module, its outputs triggers; Slew has
  six outputs and a THRU gate (the table's DEFEAT); Coin's IN and Burst's
  and Bounce's TRIG are normalled to the note trigger, Divide's CLOCK and
  Register's CLOCK to the sequencer's.
- **Sizes:** 4 B (Mix) to 312 B (Burst, Peaks' 32-pulse buffer) on arm64,
  the same or less with `gcc -m32`; all sixteen kinds add up to 1,412 B, so
  any rack fits the 8 KB arena. `fm1_mod_size()` is unchanged.
- **Tests:** a golden trace per kind (the same on clang arm64, gcc x86-64,
  gcc `-m32` and the sanitizer build), block-size identity at 1, 7 and 64
  and any fill with two racks of the new kinds, a chain of glue modules
  entered backwards arriving in the tick a direct cable does, feedback
  exactly one tick late, the Filter's response and ringing against its
  transfer function and poles, and every kind fuzzed with random and
  extreme parameters.

**Interleaving.** MG1 and MG2 are desktop-only and touch no UI, so they can
proceed alongside docs/15's S3–S6 once S7a has merged. MG3 needs S2. MG6 needs
S8. This plan replaces the options note's modulation stages (its S1 and S4);
its Plaits-envelope, arp and effects stages are unaffected.

**On the dev board (stage B, docs/14):** measure the cycles per tick of each
kind, the cost of a render split, and pi32v2's 64-bit multiply (Streams and
the Lorenz core use int64); confirm G.

**Size and the dead-code audit.** The core and planner are about 1,500 lines,
each small kind 50–200, the UI about 1,500 and the tests about 2,000: roughly
8,000–10,000 lines over MG1–MG8 [inferred]. Together with the sequencer work
since the 7,463-line mark (2026-09-30), CLAUDE.md's dead-code audit will fall
due during this plan; check the mark at MG3.

## 9. Owner decisions

1. **One system.** The rack inside the matrix, with module ports on both sides
   (recommended), or a separate rack whose inputs each pick a source, as
   Phazerville does? **Answered (2026-10-02): one system, the rack inside
   the matrix.** Module outputs are sources; module parameters, INPUT
   parameters and gate inputs are destinations; chains are ordinary 1:1
   slots. Built in MG1.
2. **Tick length G.** 32 frames (recommended: half the cost and half the
   render splits) or 16 (snappier modulation envelopes)? **Answered
   (2026-10-02): G = 32 frames.** Built in MG1.
3. **Sizes.** 8 rack positions and 32 slots (recommended), or 48 slots?
   **Answered (2026-10-02): 8 positions and 32 slots of 12 bytes, with
   16-bit amounts and offsets (Q1.14) as §2.4 says.** Built in MG1.
4. **Loops.** Allowed, with the up-the-rack cable one tick late and marked `~`
   (recommended), or refused? **Answered (2026-10-02): allowed; the cable
   that runs up the rack inside a loop is exactly one tick late and marked
   delayed.** Built in MG1.
5. **Order.** Computed by the planner with rack order breaking ties
   (recommended), or plain rack order? **Answered (2026-10-02): computed by
   the planner (Tarjan, then Kahn), rack order breaking ties.** Built in
   MG1.
6. **Inputs.** Module CV inputs as parameters, plus INPUT parameters and gate
   ports (recommended)? **Answered (2026-10-02): yes. A module's CV inputs
   are its MOD parameters, base plus offset (the options note's rule M1).**
   Built in MG1.
7. **S7a additions.** Ask S7a now for the MOD and INPUT flags and the `abbr`
   and `unit` fields? **Answered (2026-10-02): yes; built in S7a.**
8. **Buttons.** LFO = RACK, EDIT = MATRIX, ENV = PATCH, SEL held + white key
   for stages in RACK? **Answered in part (2026-10-02): in the simulator
   (MG3), LFO opens the rack at the LFOs and ENV at the envelopes.** EDIT,
   PATCH and SEL are still open.
9. **Arena.** 8 KB (recommended) or 16 KB? **Answered (2026-10-02): 8 KB.**
   Built in MG1.
10. **Segments on the device.** The control-rate rewrite, checked against the
    vendored oracle on the desktop (recommended), or the vendored code at
    31,250 Hz everywhere (exact to upstream, 2–8 % of a core)?
11. **Curves.** 16 stages as pattern data edited on the white keys, with only
    its global parameters as destinations (recommended), or 8 stages as
    parameters that can each be locked and modulated?
12. **Gate cables.** Use a gate cable's amount as a pass probability?
    **Answered (2026-10-02): yes.** Below 100 % each rising edge passes with
    that probability, from the slot's own seeded generator. Built in MG1.
13. **Names.** Function, Quad, Envelope, Curves, Draw, Bounce, Vactrol, Accent,
    Slopes, LFO, Orbit, Swirl, Tangle, Scenes, Motion, Segments, Chance,
    Register, Dice, Bits, Walk, Chaos, Numbers, Coin, Divide, Burst, Grooves,
    Field, Life, Slew, Quantize, Compare, Logic, Calc, Mix, Switch, Follow,
    Duck, Filter: are these right? **Answered in part (2026-10-02): LFO,
    Envelope and Chance**, the three kinds MG1 built. MG2 built thirteen
    more under the names above; renaming one before MG3 shows it costs a
    string, since presets store guids and uids.
14. **First wave.** The 17 kinds of MG1, MG2, MG4 and MG5?
15. **GPL kinds.** Allow `FM1_GPL_MODS` in personal builds (the Grids and
    Branches originals), never in the public simulator (recommended), or keep
    the modulation tree MIT and BSD only?
16. **CC BY 4.0.** Accept BioMimicry-derived code (Swarm) with its credit?
17. **Motion's recordings.** Saved with the preset, with the set, or not at
    all?
18. **Upstream candidates.** Log the three in §7 in
    `notes/upstream-candidates.md`, as drafts?

## 10. Sources

**This repository** [verified at `2c53435` unless noted]:
- `engines/include/fm1_engine.h` (kinds 41–47, `fm1_param_t`);
  `engines/include/fm1_seq.h`; `engines/seq.md` (D1, D2, D6);
  `engines/README.md`; `engines/third_party/mutable/UPSTREAM.md` and
  `vendor.py`; `engines/third_party/mutable/stmlib/utils/random.h`.
- `sim/web/src/fm1_app.h` (keys, buttons, `FM1_APP_MAX_PARAMS`,
  `FM1_APP_RAM_BUDGET`), `sim/web/src/fm1_app.c` (geometry), `fm1_tft.h`
  (96 boxes), `sim/web/README.md` (parity, limits).
- docs/11 §2 and §5; docs/13 §4, §6, §9; docs/14 §2.3; docs/15 and the options
  note (merged in PR #26).
- `reference/mi-eurorack` at `08460a6`: `stages/segment_generator.{h,cc}`,
  `stages/chain_state.cc`, `stages/io_buffer.h`, `stages/resources.h`,
  `tides2/`, `peaks/`, `marbles/`, `frames/`, `streams/`, `braids/quantizer.*`,
  `branches/branches.cc`, `grids/`; `reference/mi-stmlib` at `e3bd7c9`.

**Upstream code** [verified at the commits in the introduction]:
- https://github.com/djphazer/O_C-Phazerville: `software/src/vector_osc/HSVectorOscillator.h`,
  `applets/` (Relabi, EnvSeq, RunglBook, Cumulus, RndWalk, Burst, Trending,
  Compare, Schmitt, Logic, Calculate, Slew, ClockDivider, ProbabilityDivider,
  Shuffle, GateDelay, Switch, Xfader, AttenuateOffset, Combin8, Pigeons,
  Shredder, GameOfLife, EbbAndLfo, DrumMap), `apps/` (Scenery, Quadraturia,
  BBGEN, Lorenz, Piqued, QQ), `util/util_integer_sequences.h`,
  `util/util_turing.h`, `CVInputMap.h`, `HSIOFrame.h`, `Quadrants.h`.
- https://github.com/qiemem/eurorack/releases/tag/v1.3.0
- https://github.com/monome/teletype, https://github.com/monome/crow,
  https://github.com/monome/ansible
- https://github.com/TomWhitwell/Workshop_Computer (cards 14, 20, 25, 62, 67,
  90, 106, 107, 174 and the `info.yaml` survey),
  https://github.com/chrisgjohnson/Utility-Pair
- https://github.com/expertsleepersltd/distingNT_API,
  https://github.com/expertsleepersltd/distingNT,
  https://github.com/NerdRoger/disting_nt_plugins,
  https://github.com/thorinside/nt_emu, https://github.com/nwy73/CessnaAWG
- https://github.com/VCVRack/Rack (`src/engine/Engine.cpp`),
  https://github.com/surge-synthesizer/surge (`SurgeSynthesizer.cpp`,
  `SurgeVoice.cpp`), https://github.com/mtytel/vital
  (`synth_parameters.cpp`), https://github.com/SynthstromAudible/DelugeFirmware
  (`patch_cable_set.h`, `param_descriptor.h`),
  https://github.com/charlesvestal/schwung
- https://github.com/VCVRack/Befaco, https://github.com/bogaudio/BogaudioModules,
  https://github.com/countmodula/VCVRackPlugins,
  https://github.com/VCVRack/AudibleInstruments,
  https://github.com/4ms/metamodule-core-modules,
  https://github.com/modlfo/VultModules (licences only)

**Manuals and pages:**
- [verified, text read] Disting mk4 4.27, EX 1.26 and NT 1.1 user manuals:
  https://www.expert-sleepers.co.uk/downloads/manuals/
- [verified, text read] Make Noise Maths manual (2013):
  https://www.makenoisemusic.com/wp-content/uploads/2024/03/MATHSmanual2013.pdf;
  Joranalogue Contour 1 manual:
  https://www.analoguehaven.com/joranalogue-audio-design/contour-1/manual.pdf;
  the Just Friends Technical Map:
  https://github.com/whimsicalraps/Mannequins-Technical-Maps
- [reported] Mutable Instruments manuals (Stages, Stages "secrets", Tides
  2018, Kinks, Links, Ears):
  https://pichenettes.github.io/mutable-instruments-documentation/modules/
- [reported] `thorinside/nt_helper` algorithm metadata (NT 1.18 algorithms);
  Intellijel Quadrax (https://eurorackref.com/modules/intellijel/quadrax/);
  Tiptop Buchla 281t and 248t MARF (perfectcircuit.com); Serge DUSG
  (https://serge-modular.com/docs/RandomSource_Serge_DUSG.pdf).
- [reported] Axoloti user guide; Bitwig's modulators; Elektron Digitone II
  manual p. 117; Ableton Live 12 manual, Max for Live devices; the Orac wiki.

**Credits.** The modules above build on the work of:
- Emilie Gillet (Mutable Instruments: Stages, Tides 2, Marbles, Peaks, Frames,
  Streams, Braids);
- the Ornament & Crime and Phazerville authors: Jason Justian, Bryan Head,
  Patrick Dowling, Tim Churches, Max Stadler, Nicholas J. Michalek, Samuel
  Burt, Daniel Gorgan, Jakob Zerbian, Alessio Degani, and the other applet
  authors named in each file;
- Charles Vestal (Schwung);
- Chris Johnson, Matt Allison, Kenny Shen and Andy Jenkinson (Workshop System
  Computer cards);
- Nick Yablon (Cessna AWG); Electrosmith and Paul Batchelor (DaisySP); Bastl
  Instruments (Kastle 2); Expert Sleepers (the disting NT API).

Ideas, with no code taken, come from Make Noise, Joranalogue, Serge, Buchla,
Intellijel, Befaco, Mannequins (Whimsical Raps), monome, Music Thing Modular,
Expert Sleepers' disting firmware, Rob Hordijk and John Berndt.

# 12 — An Elektron-style sequencer with parameter locks: feasibility

The question (2026-10-01): could the open FM-1 firmware have an Elektron-style
sequencer with per-step parameter locks? Does
[schwung-movy](https://github.com/DimaDake/schwung-movy) already do this? What
do the [Eloquencer updater](https://github.com/enoughframes/ELOQUENCER___UPDATER),
[LMN-3](https://github.com/FundamentalFrequency/LMN-3-DAW) and the
[Elektronauts Arduino thread](https://www.elektronauts.com/t/arduino-open-source-step-sequencer-elektron-style/10971)
offer, and what else is open source?

**Update 2026-10-01.** The owner wants to replicate Movy's sequencer as
closely as possible. docs/13 is the port plan. Where Movy and Elektron
differ, docs/13 supersedes this document's recommendations: Movy's latch
(a lock holds until the next step with notes) and its sparse lock lists
replace the Elektron revert rule of §2 and §5.5 and the MCL lock store of
§5.2. §5.6's hold-time claim is corrected below.

Four research lanes ran on 2026-10-01: the named sources, Movy, a sweep of
about 30 open-source sequencers, and the FM-1 fit. A verification pass
followed. Sources were read through the GitHub API, raw files and web pages.
Nothing was cloned, built, run or sent to any device. Licences come from
LICENSE files, file headers or the API. The working notes are not kept in
the repository.

**What the verification pass re-read:**

| Lane claim | Result |
| --- | --- |
| Movy has hold-step p-locks. A lock holds until the next step with notes, which restores the base value | **confirmed**: MANUAL.md "Step parameters — per-trig locks"; `clip.rs` `Lock` and `effective_at` at `9190e79`. `engine.rs` `emit_automation` was not re-read because the fetch truncated |
| Sweep lane: Movy's logic is JavaScript (`.mjs`) | **refuted**: the engine is Rust `seq-core`. The `.mjs` files are under `browser-test/`, beside `mock-engine.mjs` |
| MCL: per-step lock mask, value pool indexed by popcount, `cond_plock`, kit value re-sent on an unlocked trig, 52 conditions | **confirmed**: `MDSeqTrackData.h`, `MDSeqTrack.cpp`, `SeqDefines.h` |
| plock is "MIT OR Apache-2.0", event-scoped, with no trigless locks | **confirmed**: README and both LICENSE files. This settles the sweep lane's doubt (the API reports only Apache) |
| hexatrack's 34-byte lock set; Schwung's `step_chance.h`; Eloquencer's per-step fields and MOD events | **confirmed** |
| Licences marked [verified] in §6 | **confirmed**, except Polaron: GitHub detects no licence and its README could not be fetched |
| FM-1 lane: memory table (16 rows) and timing figures | **confirmed** by recomputation |
| fm1-render applies events at block boundaries; Macro's Model rebuilds all voices; Six-Op reads Patch at note-on | **confirmed** in `engines/` |
| FM-1+VA: 16 × 64 steps, 9-note chords, the per-step list, no CC or clock out | **confirmed** by re-reading the manual. "No locks" rests only on the manual not mentioning them |

## 1. Short answer

| Question | Answer |
| --- | --- |
| Feasible on the FM-1? | **Yes** [inferred]. The sequencer logic takes under 0.1 % of a core. Sixteen 64-step patterns with locks take about 19 KB, 5 % of the stock SRAM gap (§5.2). The real work is the controls, sample-accurate timing and four additions to the engine API (§5). |
| Does Movy already do it? | **Yes, on the Ableton Move.** Hold a step that has notes and turn a module knob. The lock is stored for that step only, is not heard while you set it, and plays when the step plays [verified]. Movy also has per-step velocity, length, probability, A:B and invert. It has no retrigs, slides, sound locks or FILL/PRE/NEI/1ST. It is Rust and TypeScript on aarch64 Linux, so it cannot run on the FM-1 (docs/06). It is MIT, so it can serve as a spec and a desktop test oracle, and a C rewrite is allowed if its notice is kept. |
| Code we can use? | **MCL** (BSD-3, C++ on AVR and RP2040): an allocation-free lock store and the full Elektron condition set, already running on microcontrollers. Also Schwung's `step_chance.h` (MIT, C). GPL and LXR code is allowed in personal builds since the owner's licence policy of 2026-10-01, but not in a firmware binary that is shared while it links JieLi's closed libraries (§6). |
| The named sources? | **Eloquencer:** updater binaries and PDFs only, no source and no licence. It is a good design reference. **LMN-3:** a GPL-3 Raspberry Pi DAW whose sequencer is an on/off grid without locks. **The Elektronauts thread:** an Arduino sequencer with 3 CC + 1 program-change locks per step; its code was never published. |
| What gates it? | Nothing on the desktop: stage A can start now in `engines/`. On the device, the one rule (CLAUDE.md) applies: no writes, and no MIDI beyond the identity query, until a dump and a byte-identical restore have been shown. |

## 2. What Elektron-style p-locks are

The behaviour to reproduce, [reported] from the sources named:

- **Trigs and locks.**
  - A note trig plays a note. A lock trig (trigless lock) carries locks but
    no note.
  - Hold one or more trigs and turn a knob: that parameter gets a value on
    those trigs only. The value applies from when the trig fires until the
    track's next trig, where every unlocked parameter returns to the track's
    value.
  - A lock trig counts as a trig. One placed under a long note returned the
    note to the track's values (Elektronauts
    [45702](https://www.elektronauts.com/t/trigless-changes-long-notes-p-locks-to-default-values/45702)).
- **Reach and budget.** Locks act on the track's sound, so a cutoff or pan
  lock also changes notes still sounding from earlier trigs (Elektronauts
  238027). The lock budget per pattern counts distinct (track, parameter)
  pairs: Digitakt 72, Digitakt II 80, Analog Four 128 (Elektronauts 212518;
  A4 manual p.33).
- **Conditions.**
  - Probability; FILL, PRE, NEI and 1ST with their negations; A:B, which is
    true on pass A of every B loops.
  - "If the condition is false, the trig is ignored" ([Digitakt manual
    p.36](https://www.manualslib.com/manual/2166470/Elektron-Digitakt.html?page=36)).
    That its locks are dropped too is [inferred].
  - Conditions can themselves be locked.
- **Timing.** Micro-timing of ±23/384 of a note (Octatrack MKII manual p.75).
  Retrigs from 1/1 to 1/80, with a length and a velocity curve (Digitakt
  p.31). Swing 51–80 %.
- **Slides and sound locks.** A slide trig ramps locked values towards the
  next trig's values (Octatrack MKII p.67). Holding a trig and turning
  LEVEL/DATA picks another sound for that step (Digitakt p.36; A4 p.33).

The implementations differ in edge cases, so the FM-1 has to pick a rule:

| | Lock lasts until | Condition false | Lock-only step |
| --- | --- | --- | --- |
| Elektron | the track's next trig | trig ignored [reported]; its locks too [inferred] | counts as a trig: unlocked parameters revert |
| Movy | the next step with notes, or the next lock [verified] | lock still sent [inferred from code, Movy lane] | a lock on an empty step; other lanes keep their values |
| MCL | the next trig, which re-sends the kit value [verified] | a per-step bit, `cond_plock`, decides [verified] | supported |
| plock | the fired trig only (event-scoped) [verified] | locks dropped [verified] | not supported |

**Recommendation** [inferred]: Elektron's rule, plus MCL's per-step bit.

## 3. What the stock FM-1 sequencer does

**Stock** [verified: [M-VAVE manual](https://m.media-amazon.com/images/I/A1WOydif9HL.pdf),
read by the FM-1 lane; docs/02 §6 reported]:

- 16 patterns × 16 steps; step entry with REC; PLAY/STOP.
- One global Gate (20–100 %), Swing 50–75 %, Rate, Tempo 30–300 BPM.
- SAVE writes patterns to flash.
- The keys show the steps: solid for a step with notes, blinking for the
  playing step.
- ARP and SEQ cannot run at the same time.
- It follows F8 clock: FA starts from step 0, FB also starts, FC stops.
- V15 adds Chain, Step, Voice, Sync and Transpose pages.
- Steps hold only notes and velocity, and the unit sends notes only.

**FM-1+VA** (Baud Girl, `FM-1_093`) [reported:
[manual](https://baudgirl.com/work/FM-1+VA/manual)]:

- "16 patterns of up to 64 steps", each step "a chord of up to nine notes".
- Per step: Length 1/1–1/32T, Ratchet off/2/3/4, Gate, Chance (Always to
  5 %), Transpose ±24, Accent, Tie & Slide.
- Step and real-time recording, and chains per pattern.
- It sends "no controllers, Program Changes, pitch bend, or clock".

**The bar.** Keep both feature sets. Then add:

- p-locks and lock-only trigs;
- the full set of conditions, and micro-timing;
- slides and sound locks;
- clock out and CC out;
- more than one track;
- ARP running on the sequencer's output.

## 4. Prior art

The named sources and Movy come first, then the rest in order of usefulness.
The evidence for each licence is in §6.

| Project | Licence | Platform | P-lock model | For the FM-1 |
| --- | --- | --- | --- | --- |
| [Eloquencer updater](https://github.com/enoughframes/ELOQUENCER___UPDATER) (Winter Modular) | none, and no source | Eurorack CV/gate; the repo holds binaries and PDFs | Fixed per-step fields (CV, gate, length, ratchet), each with value, variation-probability and range layers. MOD steps: events PREV/NPRE/PTRK/NPTK/1ST/A:B, actions GATE/MUTE/TRAN/ADD. Hold step(s) and turn (manual v1.4.0 pp.5–6, 23–24) [verified] | design reference |
| [LMN-3 DAW](https://github.com/FundamentalFrequency/LMN-3-DAW) (Fundamental Frequency) | GPL-3.0 | JUCE + Tracktion Engine on a Raspberry Pi 4, with a Teensy controller | On/off grid of 24 pitch rows × 16 steps at velocity 127, editable only while stopped [verified, lane: `StepSequencerViewModel.cpp` 106–114, 302–321]. The iamdey fork adds 4 velocity levels. No locks | nothing to take |
| [Tracktion Engine](https://github.com/Tracktion/tracktion_engine) `StepClip` | GPL-3+ / commercial | C++ | Per-step velocity, gate and probability arrays; no locks | data-model reference |
| klerc's Arduino sequencer ([Elektronauts 10971](https://www.elektronauts.com/t/arduino-open-source-step-sequencer-elektron-style/10971), 2015) | none; the code was never posted | Arduino, 2 tracks × 16 steps | 3 CC + 1 program change per step, plus a MIDI channel per step | design point: fixed lock slots |
| [schwung-movy](https://github.com/DimaDake/schwung-movy) (DimaDake / megadake) | MIT | Rust `seq-core` + TypeScript on Schwung (Ableton Move) | Hold a step and turn a knob. 8 lanes per track. Sparse (lane, step, 7-bit) locks, up to 1,024 per clip, which latch until the next step with notes. 16 tracks × 8 clips of 1–256 steps; 24 ticks per step [verified] | spec and oracle; a C rewrite is allowed |
| [Schwung host](https://github.com/charlesvestal/schwung/tree/main/src/host) (Charles Vestal) | MIT | C, on the Move | Breakpoint lanes addressed by time; a lock is a hold point spanning one step. `step_chance.h`: 100 %, Elektron's 21-step ladder from 99 to 1 %, A:B up to 8:8, no allocation [verified] | `step_chance.h` as code |
| [MCL](https://github.com/jmamma/MCL) (Justin Mammarella, Yatao Li, Manuel Odendahl) | BSD-3 | C++ on AVR MegaCommand, RP2040, RP2350 | 8 lockable parameter ids per track. Per step: an 8-bit lock mask, a trig bit, `cond_plock` and a 6-bit condition. A 256-byte value pool indexed by popcount. 52 conditions, int8 micro-timing, slides. About 481 B per 64-step track [verified; size inferred] | **code**: lock store, conditions |
| [plock](https://github.com/gordonbrander/plock) (Gordon Brander) | MIT OR Apache-2.0 | Rust (std) | 16 tracks × 1–128 steps. Up to 80 lock lanes per pattern, event-scoped. Conditions, micro ±23, retrigs, deterministic. Ships a 46 KB spec and golden traces | spec, test traces |
| [hexatrack](https://github.com/audiodestrukt/hexatrack) (Dan Newcome) | MIT | Rust | Per-step lock set of a u32 mask plus 30 values, 34 B. YAML specs of the Octatrack hold-and-turn gestures | lock encoding, UI specs |
| [picoTracker](https://github.com/xiphonics/picoTracker) (xiphonics, after Discodirt) | BSD-3 | C++ on RP2040 and STM32 | A tracker rather than locks: 2 command columns per row (chance, delay, retrig, CC, slides) [reported] | another paradigm |
| [OMX-27](https://github.com/okyeron/OMX-27) (okyeron); [mss-nava-firmware](https://github.com/Modularsoundsystems/mss-nava-firmware) (Modularsoundsystems, zabox) | none; "no licence of its own" | Teensy; ATmega1284 | OMX-27: 4 CC lock slots per step, and the knob value is re-sent on an unlocked trig. NAVA: conditions, links between voices, length per lane | reference only |
| [LXR](https://github.com/SonicPotions/LXR) (Sonic Potions); [MIDIbox SEQ V4](https://github.com/midibox/mios32) (Thorsten Klose) | non-commercial | STM32 (+ AVR) | LXR: 2 (parameter, value) pairs per step. MIDIbox: parameter layers per track | LXR: code in personal builds (§6); MIDIbox: only with the author's permission |
| [Deluge](https://github.com/SynthstromAudible/DelugeFirmware) (Synthstrom and community); zynseq (Zynthian); kria (monome); PGB-1 (Wee Noise Makers) | GPL-3; GPL-3; GPL-2; GPL-3 | C++; C++; C; Ada | Deluge: sparse automation nodes. zynseq: CC events with ramps. kria: dense lanes per parameter. PGB-1: 4 CC locks per step | code in personal builds (§6) |
| Polaron (zueblin); sektron (emprcl); takt (itsyourbedtime) | Polaron: MIT per README [reported], none per GitHub; sektron: MIT; takt: none | Teensy; Go; norns Lua | Dense per-step parameter sets; per-step overrides that fall back to the track | reference only |

The sweep also looked at about ten more (O_C Hemisphere, Ambika, uClock,
aciduino, Plinky, TŒRN and others). None of them has per-step locks
[reported: sweep lane].

**docs/06 is out of date.** It does not mention Movy's p-locks. Movy's
`main` was at `9190e79` on 2026-10-01, 299 commits past the v0.34.0 tag
(`7539028`), with `module.json` still at 0.34.0 [verified: docs/13]. Movy's latest plans (direct `set_param` lanes,
32 lanes, enum locks) are not in its code yet [reported: Movy lane]. They
match the model §5 starts from.

## 5. Design for the FM-1 [inferred unless marked]

### 5.1 Where it sits

- **A host component, `fm1_seq`, not a plugin.**
  - It owns the transport, the patterns and the UI state.
  - It sends events, each with a frame offset, to the engines, the FX slots
    and MIDI out.
  - The API has `set_param` but no getter (`fm1_engine.h` 99) [verified].
    The host sets every value itself, so it can keep the base values.
- **The reserved `FM1_KIND_MIDI_FX`** (`fm1_engine.h` 46) [verified] becomes
  the slot between the sequencer (or the keys) and an engine, for arpeggio,
  chord and scale effects.
  - Events go in and out, with at least 32 outputs per call. Schwung caps it
    at 16 (docs/11 §3.1).
  - Stock's ARP becomes the first one, so ARP and SEQ can run together.

### 5.2 Data model and memory

```c
typedef struct {          /* 8 bytes per step per track */
  uint8_t flags;          /* TRIG, LOCK_TRIG, SLIDE, ACCENT; low nibble: extra chord notes 0..8 */
  uint8_t note, velocity;
  uint8_t length;         /* code; one value means tie */
  int8_t  micro;          /* -23..+23 in 1/384 notes */
  uint8_t cond;           /* bit 7: locks obey the condition; 0..127: condition code */
  uint8_t retrig_rate;    /* 0 = off; rate code plus velocity curve */
  uint8_t retrig_len;
} fm1_step_t;

typedef struct {          /* MCL's scheme, per track and pattern: 416 bytes */
  uint16_t target[16];    /* stable parameter uid per slot, 0 = unused */
  uint16_t mask[64];      /* per step: which slots it locks */
  uint8_t  pool[256];     /* values in step order; index = popcount of earlier masks */
} fm1_locks_t;
```

Without locks, a pattern takes 800 B:

- a 16 B pattern header;
- a 16 B track header;
- 64 steps × 8 B;
- a 128-note chord pool at 2 B per note.

Adding locks for 16 lockable parameters per track:

| Lock layout | Lock bytes | Pattern | 16 patterns | Of 387,924 B |
| --- | --- | --- | --- | --- |
| dense, 64 × 16 × 1 B | 1,024 | 1,824 | 29,184 | 7.5 % |
| Elektron-like rows, 16 × (4 + 64) | 1,088 | 1,888 | 30,208 | 7.8 % |
| sparse list, 128 × 4 B | 512 | 1,312 | 20,992 | 5.4 % |
| **MCL mask + pool** | **416** | **1,216** | **19,456** | **5.0 %** |
| 4 tracks × 64 steps, an MCL store for each | 1,664 | 4,048 | 64,768 | 16.7 % |

**Why MCL's layout.**

- It is the smallest of the four.
- Its size is fixed: inserting a value moves at most 256 B.
- It already runs on AVRs.
- It is BSD-3.

**Its limits.**

- 16 locked parameters per track per pattern, which is generous next to
  Elektron's 72–128 shared by all tracks.
- 256 values per track per pattern.
- Values are 8-bit across each parameter's range. Pitch or fine-tune may
  need 16-bit values, which would add 256 B per track (§8).

Undoing one gesture means keeping one pattern copy (1.2 KB). Start with one
polyphonic track (FM-1+VA parity plus locks) and leave room for four.

### 5.3 Parameters and engines

- **Targets.** A target is 16 bits: a 4-bit space and a 12-bit index. The
  spaces are engine parameter, trig parameter, FX slot 1–6, MIDI CC and
  bend. Storage uses a stable uid, a new `fm1_param_t` field, so reordering
  a parameter table between versions does not move locks.
- **Each engine decides what a lock means** [verified in `engines/src`]:
  - **Macro.** `set_param(Model)` calls `BuildEngines()`, which
    re-initialises all 12 voices and clears gate and active (`mi_macro.cc`
    146–157, 175–201). A Model lock would cut every note. Macro reads its
    other parameters per block, for all voices.
  - **Six-Op FM** reads Patch per voice at note-on (`mi_sixop.cc`,
    `Instance::NoteOn`).
    A Patch lock is therefore a per-note sound lock at no extra cost.
  - **msfa** (the stock engine) copies the patch into the voice at note-on,
    as Dexed's `dx7note` does [reported: FM-1 lane].
- **Parameter flags (API v2):**
  - **LATCH:** read at note-on, so locks apply per note by construction.
  - **SMOOTH:** the engine ramps a change, not the host (docs/15 S7b,
    `engines/include/fm1_smooth.h`) [verified: tests/test_engine_smooth.py].
    - **The ramp:** 2.5 ms of the engine's own native samples, in equal
      steps of its own control block, landing exactly on the new value: 10
      blocks of 12 samples at 47,872.34 Hz in Macro and Macro Heavy, 8 of
      16 in Six-Op, 10 chunks of 24 at 96 kHz in Shapes, and every sample
      (110 at 44,118 Hz) in Test Sine and the effects. The blocks sit at
      fixed native samples, never at render calls, so the output is the
      same at host blocks of 1, 7 and 64 and with any split.
    - **A lock at frame f:** the bridge splits the render at f and calls
      `set_param` there (§5.4). The ramp starts with the engine's first
      control block not yet rendered at f, which is where an unsmoothed
      change used to land, and ends 2.5 ms later. A lock-only trig under a
      held note does not click: a Volume lock of 0 → 127 on Test Sine moves
      the output by at most the sine's own slope plus 1/110 of its
      amplitude per sample.
    - **While nothing sounds** (no voice active), and before an effect's
      first render, a change applies at once. A lock on the trig of a note
      that starts a silent engine therefore plays that note at the locked
      value from its first sample. While a tail still sounds, the new note
      starts on the ramp, since the ramp is the engine's, not the voice's.
      A voice with a per-note offset (`set_param_note`) plays the ramped
      base plus its offset; the offset itself is not ramped
      (engines/README.md, "SMOOTH").
    - **Several writes at one frame** (a D6 revert, then a lock) make one
      ramp, from where the value stands to the last one. A write equal to
      the target already set changes nothing, so a resent base is free.
    - **Modulation** (docs/16) writes every tick (0.725 ms at G = 32). Each
      write restarts the ramp from where it stands, so a route follows its
      source through a lag of about one ramp, and its steps are not heard.
    - **Effects that already glide** keep their own glide: Fold (5 ms),
      Echo (5 ms gains, 0.1 s Time and Wow), Drive, Filter, Comp and the
      Limiter (5 ms each). A new effect may do the same if its glide is
      keyed to samples;
      anything else uses `fm1_smooth.h`, as Echo's Tone does, which had no
      glide.
  - **NOLOCK:** destructive parameters such as Macro Model and Shapes Shape.
- **Sound locks** pick a preset per trig on LATCH engines. Caching the
  presets in use costs 16 × 156 B ≈ 2.5 KB. On Macro and Shapes a sound lock
  is a batch of parameter locks.
- **Engine type** cannot be locked. To change engine on a step, route the
  trig to another track.
- **Per-voice locks** on continuous parameters would need a voice-scoped
  call. Wait until Elektron's behaviour is known (§8).

### 5.4 Timing

At 44,118 Hz a 1/16 step is 661,770 / BPM samples, and a micro tick is 1/24
of a step:

| Tempo | Step | Micro tick | Ticks per 64-frame block |
| --- | --- | --- | --- |
| 30 BPM | 22,059 samples, 500 ms | 919 samples, 20.8 ms | 0.07 |
| 120 BPM | 5,514.75 samples, 125 ms | 229.8 samples, 5.21 ms | 0.28 |
| 300 BPM | 2,205.9 samples, 50 ms | 91.9 samples, 2.08 ms | 0.70 |

- **Sample offsets.**
  - Today fm1-render applies notes, bends and `--param-at` only at block
    boundaries: controls first, then note-offs, then note-ons (`render.cc`
    11–12, 278–295) [verified]. At 300 BPM an event can land up to 70 % of
    a micro tick late.
  - The fix needs no engine change: split each render call at event
    offsets. The API already allows calls shorter than `max_frames`
    (`fm1_engine.h` 10) [verified].
  - Onsets are then quantised only inside each engine: 12 samples in Macro,
    16 in Six-Op, and 24 at 96 kHz in Shapes [verified: engines/README.md,
    `mi_sixop.cc` `kBlock`].
- **Order at one offset:** note-offs, reverts, locks, note-ons, so LATCH
  parameters see the lock. For comparison, Movy sends a lock one tick before
  its notes, and Schwung evaluates lanes one block early [reported: lanes].
- **Tempo.**
  - Keep tempo in a fractional accumulator. Rounding 5,514.75 samples to
    5,515 drifts 57 ms per 10,000 steps (21 minutes at 120 BPM).
  - CHOMPI's `clockManager` drops each step's overshoot
    (notes/2026-10-01-chompi-evaluation.md line 107) [verified]; do not copy
    it.
  - Negative micro-timing needs one step of look-ahead.
  - Compute swing and retrigs in samples. For scale, 51 % swing moves the
    off-beat by 110 samples at 120 BPM.
- **Clock in.**
  - 6 F8 messages per step, each timestamped against the sample counter.
  - The clock period is smoothed over about one beat.
  - USB's 1 ms frames bound the jitter.
  - Add FB (Continue) with F2 (Song Position); stock treats FB as a start.
- **Clock out:** 24 PPQN from the same scheduler.

### 5.5 Playback rules (the tests pin these)

Each track has base values B and a set A of locks currently applied.

1. **A trig whose condition is true**, at offset τ, runs in order:
   1. note-offs;
   2. set B[p] for each p in A that this step does not lock;
   3. set the step's locks;
   4. A := what this step locks;
   5. note-ons.

   A lock-only trig counts as a trig.
2. **A false condition.** With `cond` bit 7 set (the default), a false trig
   changes nothing. With the bit clear, the locks apply but the note does
   not play. Empty steps change nothing, so a lock holds until the next
   trig.
3. **A knob turned with no step held** updates B. The change is heard at once
   only if p is not in A.
4. **Stop, a pattern change, mute or a sound change** revert everything in A.
5. **Slides** ramp to the next trig's lock or base value over the gap
   between trigs. **Retrig sub-trigs** reuse the first sub-trig's locks.
6. **Probability** uses a seeded generator. A:B counts each track's loops.
   NEI is evaluated in track order.

### 5.6 Controls

The 27 keys run from F3 to G5 (manual p.10), which gives exactly 16 naturals
and 11 accidentals.

- **GRID mode.** The 16 white keys are steps. The black keys are functions:
  four step pages (64 steps), a TRIG page, tracks, copy and FILL.
- **KEYS mode** keeps stock playing and step recording.

| Gesture | Effect |
| --- | --- |
| Tap a step | toggles a note trig |
| Hold step(s), turn KNOB1–4 on any page | lock |
| Hold a step, turn PRESETS | sound lock |
| Hold a step, turn SELECT | trig pages: note, velocity, length, condition; micro, retrig rate, retrig length, velocity curve |
| SEL + step | lock-only trig |
| Hold step + SEL, turn a knob | clears that lock (Movy clears by touching a knob; the FM-1's encoders cannot sense touch) |
| Turn a knob in live REC | locks the current step |

- **Hold time.** Correction (docs/13): in Movy, holding one step and turning
  a knob locks at once. The 300 ms `STEP_AUTO_MS` only promotes the display,
  and with two or more steps held a turn edits the patch [verified:
  `src/seq/step-edit.ts` 49, 103–126, 219–225, at `9190e79`].
- **Undo** reverses one whole gesture.
- **The TFT** shows 4 × 16 cells: filled for a note trig, outlined for a
  lock-only trig, a corner dot for a step with locks. While a step is held,
  locked values show in an accent colour over grey base values.
- **Key LEDs:** solid for a trig, slow pulse for a lock-only trig, blink for
  the playhead.

### 5.7 Storage under the one rule, and CPU

- **Before a dump and byte-identical restore,** patterns exist only in
  desktop and dev-board builds. A desktop sequencer could drive the stock
  unit in principle (notes, and FX CCs on channel 2, docs/02 §6). But notes
  and CC are outside the allowed traffic, so that is the owner's call.
- **In the open firmware,** patterns live in RAM, with SysEx export and
  import. Flash storage comes last:
  - a dedicated partition, with A/B copies in 4 KB sectors;
  - a header holding magic `FM1P`, version, length, sequence and CRC32;
  - written only on SAVE;
  - 16 patterns take 5–8 sectors per copy;
  - kept apart from the VM and USR regions that stock and FM-1+VA use
    (docs/01 §2).

  Importing stock or FM-1+VA patterns needs their flash formats, which only
  a dump will show.
- **CPU.** Each step costs about 300–800 cycles per track. Four tracks at
  300 BPM come to about 64,000 cycles/s, 0.03 % of a 240 MHz core. MCL and
  the NAVA firmware run this kind of logic on 8-bit AVRs [verified:
  READMEs].

## 6. Licences [verified texts unless marked; consequences inferred, not legal advice]

**Owner's policy (2026-10-01).** This is a personal, non-commercial project,
and GPL code may be brought in when it is needed (CLAUDE.md). The GPL was
never excluded for commercial reasons. It, and LXR's licence, require anyone
who *distributes* a binary to supply the complete source of everything linked
into it, and the FM-1 firmware is expected to link JieLi's closed SDK
libraries (docs/11 §7) [inferred]. So:

- **Personal builds**, flashed by the owner and not shared: GPL and LXR code
  is fine. Their obligations start on distribution.
- **Source in this repository**: fine, with each file keeping its own licence
  in its own directory (`third_party/<name>/`, as for Mutable's code).
- **A shared firmware binary** (a release, or one sent to anyone else) must
  leave GPL and LXR code out while it links JieLi's closed libraries. Keep
  such code behind a build switch, so the MIT/BSD build stays shareable.
- **GPL and LXR in one shared work** are incompatible with each other: the GPL
  forbids LXR's "may not be sold" restriction.
- **Desktop tools** (fm1-render, test oracles) link nothing closed, so GPL code
  there is fine; such a binary is GPL as a whole.

**The GPL switch (owner, 2026-10-05).** GPL modules go behind one build
switch, `FM1_GPL_MODS`, which is **on by default, in every build, while we
test** (the owner: "gated with a switch but ON by default, everywhere while
we test"). Consequences [inferred, not legal advice]:

- **No shared firmware image while it is on.** An image that links JieLi's
  closed libraries with GPL code in it is never released or sent to anyone;
  one that leaves the owner's hands is built with the switch off.
- **The public simulator is offered under the GPL's terms** while its
  WebAssembly module carries GPL modules: the page names the licence, links
  the complete corresponding source (this repository at the module's
  commit) and keeps every licence notice. It links nothing closed, so the
  GPL can be met there.
- **Bare metal later.** A build without JieLi's libraries is to be explored
  later; under the GPL as a whole, it could be shared.
- **How the switch is built** (2026-10-06) [verified: the build and
  `tests/test_gpl_switch.py`]:
  - `FM1_GPL_MODS ?= 1` in `engines/Makefile`, 0 or 1, and nothing else.
    fm1-render, the virtual FM-1's native and WebAssembly builds
    (`sim/web/mk/sim.mk`, `build.sh`, `build-on-aeon.sh`) and the JieLi
    compile check (`tools/jieli/objects.mk`, `compile-check.sh`) all build
    through that Makefile, so one variable turns them all.
  - A GPL module's code sits in its own `engines/third_party/<name>/`, with
    its licence and an `UPSTREAM.md`. Its fragment (`engines/mk/<name>.mk`)
    adds its sources only when the switch is on, its C objects to
    `GPL_OBJ`, and its registry entry (`src/registry.cc`,
    `midi_fx/registry.c`) sits under `#if FM1_GPL_MODS`.
  - The licence table beside the registry (`fm1_licences`,
    `fm1_engine_licence` in `fm1_engine.h`) names the licence of every
    module whose code is not all MIT. `fm1-render --list`, the simulator's
    catalogue and its build record (`fm1.wasm.json`) carry it, and
    `fm1-render --build-info` says how a build was made.
  - **The page.** While the module carries a GPL module, the simulator's
    page names each one and offers the module under the GPL, version 3. It
    links the licence's text (`sim/web/www/licences/GPL-3.0.txt`) and the
    complete source: this repository at the commit the site was built from
    (`source.json`, written by the site's build). With no GPL module in it,
    the page says nothing.
  - **CI** runs every test with the switch on, and the engine, sequencer
    and simulator tests again with it off (`engines-mit`). In both,
    `tests/test_gpl_switch.py` builds the switch-off programs and fails if
    any compiles a GPL file, links a symbol a GPL object defines, or lists
    a GPL module.
- **GPL code in the tree** [verified, 2026-10-06]:
  `engines/third_party/felucca/` (Felucca by Leo Kuroshita, Hügelton
  Instruments, GPL-3.0-only): the sound engines Drawbar, Trio and Phase
  Bend (`notes/2026-10-06-fm1-x0x.md` §3, §6). fm1-x0x's 303 bass and its
  TB-3PO generator come on their own branch.

**Usable as code in every build (docs/11 §7):**

- **MCL: BSD-3.** The licence "applies to code, documentation or material in
  this repository, created by the above authors" (Mammarella, Li,
  Odendahl). File headers carry only a copyright line, so check each file's
  provenance before taking it. Leave out its dependencies (arduino-pico,
  MegaCore, SdFat, Adafruit GFX).
- **Movy: MIT**, "Copyright (c) 2026 megadake".
- **Schwung: MIT**, "Copyright (c) 2025-2026 Charles Vestal". Its
  THIRD_PARTY_LICENSES.md was not read.
- **plock:** "MIT OR Apache-2.0".
- **hexatrack: MIT** (Dan Newcome).
- **picoTracker: BSD-3.** Its third-party table includes WTFPL, Unlicense and
  font licences, so take first-party files only.

**Usable as code in personal builds only (see the policy above):**

- **GPL:** LMN-3, Tracktion Engine and Deluge; also zynseq, kria, PGB-1 and
  Mosaic [reported: sweep lane].
- **LXR** [verified: LICENSE.txt]: "may not be sold, nor may it be used in a
  commercial product or activity", and modified redistributions "must include
  the complete source code, including the source code for all components used
  by a binary". The second clause has the same effect as the GPL's.

**Needs the author's permission:** MIDIbox ("personal non-commercial use
only" [reported: sweep lane]). Vendoring it into a public repository is
redistribution, which those words do not clearly allow; ask Thorsten Klose
first.

**Design reference only, because there is no licence at all:** Eloquencer,
klerc's sequencer, OMX-27, mss-nava-firmware, Polaron as GitHub sees it, and
takt [reported: sweep lane].

**The SDK and the FM-1 community firmware (added 2026-10-05,
`notes/2026-10-05-community-repos.md` §2):**

- **JieLi's AC79 SDK is not GPL-free** [verified: SDK at `e30b1ee`]. Its
  `system.a` holds a modified FreeRTOS V9 kernel (the TCB adds `cpu_id`),
  and the FreeRTOS V9 headers are GPLv2 with the FreeRTOS linking exception.
  `uac_audio.h` and `uac_audio_v2.h` (SPDX GPL-2.0, the SDK's only USB-MIDI
  constants), the sdio headers and `usbnet.h` are GPL-2.0. The rest is
  Apache-2.0; the closed `.a` files and tools carry no licence. Our reading
  [inferred, not legal advice]: the kernel is JieLi's distribution under the
  exception, which our app does not modify; never include the GPL-2.0
  headers, and write the USB-MIDI descriptors from the USB-MIDI 1.0 spec.
- **Felucca and SLOOP are GPL-3.0-only**: facts and ideas only, restated in
  our words with credit. Felucca's exceptions are usable as code:
  `firmware/src/fm6_core.c` (Apache-2.0, an integer msfa port) and
  `phys_dsp.c`/`phys_symp.c` (MIT). Its `eng_phase.c` and Hügelton's samples
  are GPL-3.0.
- **fm1-nes** is Apache-2.0 at the root (board, keyscan, volume, power,
  `boot_compat`, packager, planner), with GPL-3.0-only USB audio and packet
  code and MIT `jl_formats.py` routines and guard patch. Its board constants
  are copied from stock FM-1_010, so they serve as cross-checks only.
- **FM-1-transporter** is MIT.

**Manuals** (Elektron, Winter Modular, M-VAVE, Baud Girl) are behaviour
references: summarise and cite them, never copy. Call the feature "parameter
locks" and keep Elektron product names out of the UI.

## 7. Staged plan

| Stage | Where | Work | Exit |
| --- | --- | --- | --- |
| A-seq — desk | any computer | `engines/include/fm1_seq.h` + `src/seq.c`: C99, no heap, a fixed pattern arena, the MCL lock store with its BSD notice, and a scheduler that is a pure function of (pattern, transport, seed). API v2: transport, events with frame offsets, parameter flags and uids, the MIDI_FX contract. fm1-render gains `--pattern FILE`, renders split at event offsets, `--log-calls FILE.jsonl`, `--clock-in`, `--midi-out` and `--seed` | pytest pins §5.5: lock at the trig's sample, revert at the next trig, hold across empty steps, lock-only trigs, both `cond` modes, A:B, seeded probability, FILL. Positions exact to the sample at 30–300 BPM and swing 50–80, with no drift over 10,000 steps; micro ±23; retrig spacing. Byte-identical output at host block sizes of 1, 7 and 64. A bounded sample-to-sample step on smoothed locks. Macro Model refused as a lock. F8 with ±1 ms jitter followed within 1 ms rms. Differential runs against Movy's `seq-core` and plock's traces where the semantics agree |
| B — bench | JieLi AC79 dev board | A-seq built for pi32v2; cycle counts for the scheduler and split renders; USB-MIDI clock in and out measured from a second machine | a cycle table, clock-jitter figures, a decision on msfa's block size |
| C — FM-1 | only after docs/07's dump and restore | GRID and KEYS modes, LEDs, TFT views, RAM patterns, SysEx export and import | stock's feature floor plus locks, playable; patterns survive an export and import round trip |
| D — FM-1 | after C | the flash pattern partition | an A/B save survives a power cut mid-write |

A `--pattern` file has one line per step, for example
`step 3 note=63 cond=1:2 micro=+6 lock.Brightness=0.8`, or
`step 5 lock.Brightness=0.2` for a lock-only trig.

## 8. Open questions

1. **Elektron edge cases**, to settle before §5.5 is frozen:
   - Does a trig whose condition is false drop its locks?
   - On the Digitone, are locks per voice or per track?
   - Does every Elektron model revert other parameters on a lock-only trig?
2. **Values and ids.** Are 8-bit values enough for pitch and fine-tune? Should
   the stable uid be a hash of `engine/param`, or a field each engine
   declares?
3. **Hardware.**
   - Can the 74HC595 key-LED drivers dim?
   - Are KNOB1–4's push switches readable?
   - Which keys does stock light as steps?
   - What is the key-scan rate?
4. **Timing and tracks.** Can msfa's block size drop from 64 to 16 samples
   (stage B)? Should BLE-MIDI clock be supported? One polyphonic track, or
   four sharing 12 voices?
5. **Sources.**
   - Which MCL files are purely by its three authors? (MIDICtrl is
     Odendahl's.)
   - Would jmamma welcome an extracted library?
   - Read Schwung's THIRD_PARTY_LICENSES.md before taking any of its code.
   - Pin any Movy oracle to one commit.
6. **Owner.** Should the one rule keep covering all MIDI traffic? docs/06
   also needs updating for Movy's p-locks.
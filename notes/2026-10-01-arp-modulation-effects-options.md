# Arpeggiators, modulation and eurorack-type effects: options (2026-10-01)

**Scope.** The owner asked for four things:
- open-source arpeggiators to implement and put in the simulator;
- configurable LFOs and envelopes;
- a modulation matrix;
- fun eurorack-type effects such as sample-and-hold, starting from open eurorack modules.

**How the candidates were checked.** Six lanes read about 90 candidates: projects already vetted here, Mutable Instruments, other eurorack firmware, arpeggiators at large, effects, and modulation design. They read through the GitHub API, raw files and the local clones `reference/mi-eurorack` (at `08460a6`, the commit `engines/` vendors) and `reference/mi-stmlib`. A verifier pass then re-read every licence and file named here at its pinned commit. Nothing third-party was built, run or added to the repo. This note is the synthesis. I re-checked the repo-local facts myself, plus four upstream ones:
- Yarns' MIT header and `ClockArpeggiator` at `part.cc` 366;
- Super Arp's MIT licence;
- DaisySP's licence and `samplehold.h` header;
- Schwung's S&H code.

**Marks.**
- [verified]: the licence or file was read at the pinned commit in this run.
- [reported]: a page, manual or lane says so, not re-read.
- [inferred]: our estimate.

**No CPU figure in this note is measured on pi32v2.** All of them stay [inferred] until the dev board (docs/14).

## Cores: stock uses two; ours runs on none yet

This answers the question that started the run. Nothing this project builds runs on the FM-1 yet, so it uses no cores there. The stock firmware does use both (corrected 2026-10-02; see below).

- **Nothing runs on the device.** Nothing from this project has been flashed (CLAUDE.md, "The one rule") [verified]. `engines/`, `sim/`, `dongle/` and `tools/` run on a desktop or in WebAssembly.
- **Our code is written for one core.**
  - The engine contract has one control task and one audio task (`engines/include/fm1_engine.h` 19–23) [verified].
  - The browser simulator runs the whole firmware in one AudioWorklet, "as the FM-1 runs UI and audio on one core" (`sim/web/www/worklet.js` 1–2). It draws the screen on that same thread (`sim/web/README.md` 242–243) [verified].
  - The only threads in the project's own code are in the desktop ThreadSanitizer probe for the Schwung shim, `engines/test/schwung_race.cc` [verified: `git grep`].
- **Stock firmware uses both cores** (corrected 2026-10-02; this note first said one).
  - It renders the msfa voices on cpu1. The cpu1 entry polls a flag and calls `dx7note_compute_block`, its only call site [verified: V13 disassembly, file `0x86AD6`–`0x86B3E`]. That this entry runs on cpu1 is [reported: AL-255's symbol names; inferred from `cpu1_run_flag`].
  - cpu0 runs the effects chain and the output.
  - The earlier reading, "boots cpu1 but runs its work on cpu0", came from AL-255's `02-rtos.md` and `01-boot.md`. docs/11 §2 is corrected on main.
- **The second core is an open question, not yet a plan.**
  - "Whether an SDK build can put audio on the second core" is unknown 3 in docs/11 §8 [verified].
  - Whether *our* SDK build can use cpu1 the same way is the second-core probe in docs/14's first week on the AC79 dev kit.

**What it means for this note** [inferred]:
- The arpeggiator, LFOs, envelopes and matrix are control-rate work, about 1 % of a core. They should stay on the audio task beside `set_param`, so their timing stays sample-exact.
- If cpu1 becomes usable, the candidates to move there are the buffer-heavy effects (echo, repeat, pitch shift) and TFT drawing.
- Workshop Computer card 45 (Bends) is an open precedent: it runs its DSP stage on the RP2040's second core (`bends.cpp` 400, multicore lockout 263–313) [verified].

## 1. Short answer

| Category | Pick | Licence | Why |
| --- | --- | --- | --- |
| Arpeggiator | Our own C core, `fm1_arp`, built as the first `FM1_KIND_MIDI_FX`, between keys, MIDI and SEQ and the engine. It follows Yarns' `ClockArpeggiator` (directions, 22 rhythm masks, Euclid), adds MCL's extra orders and its trig-stepped rate, and adds Super Arp's seeded modifiers | MIT (Yarns, Super Arp), BSD-3 (MCL) | Integer and event-rate, with no heap. The core is about 80 lines at the eurorack commit we already pin. ARP and SEQ can run together, which stock cannot do (docs/12 line 103) |
| LFOs | 2 global LFOs in a host modulation runtime, `fm1_mod`. Elektron-style pages: WAVE, SPD, MULT, DEP, then DEST, MODE, SPH, FADE. Modes free, trig, hold, one-shot and half. Synced to `fm1_seq`'s tick. Shapes follow Schwung's `lfo_common.h`, plus smooth random. 2 key-triggered LFOs come in stage C2 | MIT (Schwung, rewritten); Plaits' DX7 LFO is already vendored | It matches Movy's host (Schwung) and costs tens of bytes |
| Envelopes | 2 ADSR envelopes with curve (lin, exp, quartic) and loop, after Peaks' `MultistageEnvelope`. Before that, expose Plaits' own per-voice envelope to FREQ, TIMBRE and MORPH in Macro | MIT (Peaks; Plaits vendored) | Plaits' envelope gives polyphonic envelopes in about 40 lines, before any API change |
| Modulation matrix | Option C (hybrid), in two stages. C1 is a host-side global bus: 16 slots of `{source, unit, destination uid, int8 amount, flags}`. C2 adds per-note sources through an API v2 `set_param_mod(index, key, offset)` | Our code. Design after Shruthi and Ambika (GPL, design only), CLAP and Schwung (MIT) | It works with every engine and effect today. C1 needs under 0.6 KB and about 0.35 % of a block; C2 about 1.7 KB and 1.1 % [inferred] |
| Sample-and-hold and random | A CHANCE source: stepped S&H, smooth random, a Turing register and drift. After DaisySP `SampleHold`, Workshop Computer card 106 (QRV, FRV) and card 20's Turing register. Stages functions come later, with Marbles as the deluxe version | MIT | Tiny, integer or light float, and seeded so a pattern's random repeats |
| Effects, first wave | CRUSH (Plaits `SampleRateReducer` plus bit depth: audio-rate S&H), S&H FILTER (clocked random into stmlib `Svf`), FOLD, CHORUS (Junologue). ECHO and REPEAT on one shared buffer come once tempo exists | MIT | All small. CRUSH, S&H FILTER and FOLD reuse vendored code or need a few dozen lines |

Every pick is MIT or BSD, so each is fine in the public web simulator and in a shareable FM-1 binary. The GPL sources (Deluge, Shruthi-1, Ambika, Ansible, Grids) serve as design references only.

## 2. Arpeggiators

### 2.1 Options

| # | Option | Licence | What it has | Size | Fit | Effort |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **Yarns `Part::ClockArpeggiator`** (Emilie Gillet). Port it to C | MIT [verified: `yarns/part.cc` header; eurorack README "Code (STM32F projects): MIT license"] | Directions UP, DOWN, UP_DOWN, RANDOM, AS_PLAYED and CHORD. Octave range. 22 16-bit rhythm masks, Euclidean length, fill and rotate, clock division, gate, latch. Swing is in `internal_clock.h` [verified: `part.h` 45–53, `part.cc` 366–446] | Arp loop about 80 lines. stmlib `note_stack.h` 217 lines, **not vendored yet** (`engines/third_party/mutable/stmlib` has only `dsp/`, `system/`, `utils/`) [verified]. Tables: 44 B of patterns and 4,096 B of Euclid | The best first core. Line 390 calls the global `stmlib::Random::GetSample()`, so reimplement that path with our own PRNG (§2.3) | 1–2 days with golden tests |
| 2 | **Super Arp** (Handcrafted Media, a Schwung MIDI FX). Port natively | MIT [verified: LICENSE, API] | Modes up, down, as played, leap inward and outward, chord, pattern strings. 40 progression and 40 rhythm presets. Rate 1/32–1/4 with triplets, swing, gate, octave, latch. Seeded modifiers (drop, velocity, gate, octave, note), each with its own seed and a loop length [verified] | 2,026 lines. Strip `calloc` (1478), the `malloc`/`fopen` JSON reader (168–174), the debug log (206) and double-precision timing | The best source for the random and modifier layer, and the closest to Movy's world | 2–3 days |
| 3 | **Loom arpeggiator** (Chris Rogers' Yarns firmware). Port in phase 2 | MIT on the headed files; `sequencer_step.h` has no header, so its licence is unknown [verified] | LINEAR, BOUNCE, RANDOM, JUMP and GRID. JUMP and GRID read sequencer notes as movements through the held chord [verified: `part.h` 66–73, MANUAL.md] | `arpeggiator.cc` 191 lines + `.h` 64, coupled to Loom's `Part` | The cleanest "sequencer plays the arp" design. Movy has nothing like it (docs/13) | About 1 day |
| 4 | **MCL `ArpSeqTrack`** (Justin Mammarella). Lift the mode list and the trig rate | BSD-3-Clause for the named authors' code [verified: LICENSE] | 19 modes: up, down, up-down, down-up, up-n-down, down-n-up, converge, diverge, conv-div, pinky up and down, thumb up and down, up-pinky, down-pinky, up2, down2, random, random2. States off, on, latch, lock. `ARP_RATE_TRIG` advances on sequencer trigs. 48 notes [verified: `ArpSeqTrack.h` 12–36] | `.h` 145 + `.cpp` 428 lines | Shareable. docs/12's A-seq plan already named MCL's lock store, with its BSD notice (line 438); no MCL code is in the tree yet [verified: `git grep`] | 1–2 days |
| 5 | **Deluge community firmware arpeggiator**. Reimplement the documented behaviour | GPL-3.0-or-later [verified: headers] | Octave mode separate from note mode; Walk 1–3; 50 rhythms; ratchets; note, bass, swap, glide and chord probability; a randomizer LOCK [verified: `arpeggiator.h`, website `features/arpeggiator.mdx`] | `arpeggiator.cpp` 2,022 lines, tied to Deluge models | Design only: the richest specification of a performance arp | 2–3 days to reimplement |

**Considered, not chosen as the base:**
- **Plaits' `Arpeggiator`** (MIT, already vendored, 133 lines): UP, DOWN, UP_DOWN and RANDOM, with no rhythm, gate or latch [verified]. A traversal kernel only.
- **Schwung's built-in arp** (Charles Vestal, MIT, 616 lines) [verified]: too basic to ship. It is a good test fixture for the MIDI_FX contract.
- **Eucalypso** (Handcrafted Media, MIT, 1,835 lines) [verified]: four Euclidean lanes over held notes. A ready "Euclid" mode, or a second MIDI FX, later.
- **monome libavr32 arp**, behind Ansible (GPL-2.0, no "or later" found) [verified]: very good Euclidean players and per-repeat transpose. Design only.
- **CHOMPI TEMPO's arp** (MIT): rest masks and octave-jump probability. Reimplement it; the defects are in notes/2026-10-01-chompi-evaluation.md.
- **Smaller permissive ideas:**
  - Midier (Raz Rotenberg, MIT): one "style" knob that ranks every note order by permutation.
  - Axoloti `cpwitz/midi/arpeggiator.axo` (Peter Witzel, CC0): recall the last latch.
  - Amalgamated Harmonics Arp31 and Arp32 (John Hoar, BSD-3): crab and crawl, converge and diverge index sequences.
  - Ardour `simple_arp.lua` (Albert Gräf, MIT): meter-aware accents and ratio swing.

  All four licences [verified].

### 2.2 Recommended feature set

The arp is built from orthogonal stages, so a few knobs give many behaviours. Deluge, Count Modula and Bogaudio all split it this way; we reimplement the idea, not their code [verified licences; designs reported].

1. **Order of the held notes:** by pitch, as played, or reversed as played.
2. **Note mode:**
   - Up and Down.
   - Up-Down inclusive and exclusive (with or without repeated ends).
   - Converge and Diverge.
   - Crawl: +2 then −1.
   - Walk: a random step to a neighbour.
   - Shuffle: each note once per cycle.
   - Random.
   - Pedal: the low or high note between the others.
   - Chord: all notes at once.
   - Pattern: a short index string after Super Arp's notation.
3. **Octaves:** a range of 1–4, and an octave mode (Up, Down, Up-Down, Alternate, Random) separate from the note mode.
4. **Rhythm:**
   - Yarns' 22 masks, or Euclid length, fill and rotate.
   - A sequence length, and step repeat.
5. **Rate:** synced divisions from 1/1 to 1/32, with dotted and triplet values. **TRG** advances one step per sequencer trig, after MCL.
6. **Gate:** 1–200 %. Over 100 % overlaps the next note (legato).
7. **Swing:** reuse `fm1_seq`'s `swing_pct` (`engines/include/fm1_seq.h` 208), which is 50–80 % as in Movy (docs/13 line 57) [verified].
8. **Ratchet:** 1–4 repeats per step, with a probability.
9. **Chance:**
   - Note skip, octave jump, velocity and gate spread, chord probability.
   - One seed per arp, and a LOOP length after which the draws repeat.
   - LOOP is Super Arp's modifier loop and Deluge's LOCK in one control.
10. **Velocity:** as played, fixed, or an accent pattern.
11. **Latch:**
    - Hold keeps the arp playing after release.
    - A chord played after every key is up replaces the old one.
    - Keys added while any key is held join the chord, either now or at the cycle restart (Bogaudio).
    - The keyboard transposes a latched arp.
    - The sustain pedal also latches (Axoloti).
12. **Clock:**
    - From `fm1_seq`'s master tick: 96 PPQN, each tick at its own frame per D1 (`fm1_seq.h` 33; `engines/seq.md` line 175) [verified].
    - From an external MIDI clock through `fm1_seq_realtime_in`.
    - While stopped, the arp free-runs from the same tempo accumulator and rejoins on the bar at Play.
    - Yarns' 24 PPQN logic runs from every fourth tick [inferred].

Stock firmware has an arp with seven modes, patterns, octaves and random [reported: docs/02 line 187]. Keep its mode names as presets where they map, so stock users recognise them. Every arp parameter is 0..127, so the sequencer's 7-bit locks can lock the arp per step.

### 2.3 Where it sits

```
panel keys (fm1_app_key) --+
USB-MIDI in ---------------+--> ARP (FM1_KIND_MIDI_FX) --> per-note mod pool (C2) --> engine note_on / note_off
fm1_seq NOTE events -------+        ^ clock and transport from fm1_seq
```

- **The slot already exists.** `FM1_KIND_MIDI_FX = 3` is reserved (`fm1_engine.h` 46) [verified]. docs/12 §5.1 (lines 168–173) makes stock's ARP its first user "so ARP and SEQ can run together" [verified].
- **Prerequisites, from API v2** (docs/12 A-seq row, line 438) [verified]:
  - transport and tempo in `fm1_host_t`, which today holds only `api_version`, `sample_rate` and `max_frames` (`fm1_engine.h` 70–74);
  - events with frame offsets;
  - the MIDI_FX contract.

  Allow 32 or more output events per call. Schwung's `midi_fx_api_v1.h` caps it at 16 [verified].
- **Order at one frame:** note-offs, reverts, locks, then the arp's step and note-ons. This follows docs/12 line 281.
- **Recording:** record the held notes before the arp by default, so the arp replays them at playback, as Elektron does [inferred]. A later "print arp" can write its output into a clip.
- **MIDI out:** the arp's notes stay off MIDI out unless asked, as in Yarns [reported: modulation lane].
- **Modulation:** the arp's step index and its random value are matrix sources, after Ambika's ARP_STEP idea.
- **Randomness:**
  - The arp gets its own seeded PRNG, an xorshift64* as in Movy's R7 (docs/13 line 84) [verified].
  - It never draws from `stmlib::Random`, a single global [verified: `engines/third_party/mutable/stmlib/utils/random.h`]. Macro's random engines match upstream because both sides seed that global alike (`engines/README.md`, reference table) [verified]; an arp sharing it would break those reference tests.

### 2.4 The ARP page on four knobs

Tap ARP to toggle; hold ARP to latch. SELECT moves between pages, and ALGORITHM scrolls MODE.

| Page | KNOB1 | KNOB2 | KNOB3 | KNOB4 |
| --- | --- | --- | --- | --- |
| PLAY | MODE | RATE | GATE | OCT |
| RHYTHM | PATTERN (22 masks or Euclid) | FILL | ROTATE | LENGTH |
| CHANCE | SKIP | RATCHET | SPREAD | LOOP |
| FEEL | OCT MODE | VELOCITY | SWING | JOIN (now or restart) |

The seed is saved with the preset. The screen holds about 19 characters a line at 2× text [reported: modulation lane], so labels stay short. The new pages must pass `fm1_tft_check_layout`'s 4 px gap test (`FM1_APP_LAYOUT_GAP`, `sim/web/src/fm1_app.h` 60) [verified].

## 3. LFOs and envelopes

### 3.1 Options

| Source | Licence | What it gives | Fit |
| --- | --- | --- | --- |
| **Schwung `src/host/lfo_common.h`** (Charles Vestal) | MIT [verified] | 2 LFOs; shapes sine, triangle, saw, square, S&H and "swishy"; 27 sync divisions. Synced phase is `fmod(beat_position/beats, 1)`. Retriggers on the first held note [verified] | The spec for Movy-compatible LFOs. Rewrite it; don't copy. It uses a double phase and a shared static LCG (1103515245, 12345). Its S&H also has a bug: it re-rolls only when phase < 0.05 (lines 173–178), so it misses wraps once the increment per block exceeds 0.05, and a held 0.0 counts as unset [verified, re-read for this note]. A candidate upstream fix (below) |
| **Plaits DX7 LFO and envelopes**, vendored | MIT [verified: `engines/third_party/mutable/UPSTREAM.md`] | `fm/lfo.h` (192 lines), `fm/envelope.h` (258: operator and pitch envelopes), `envelope.h` (130: LPG and decay) [verified] | Nothing new to vendor. Needs an adapter from DX7's 0–99 units |
| **Plaits' internal voice modulation**, vendored | MIT [verified] | When unpatched, the decay envelope drives the FREQ, TIMBRE and MORPH attenuverters; it also drives the LPG (`plaits/dsp/voice.cc`, 272 lines) [reported: line ranges by lane] | About 40 lines in `mi_macro.cc` and `mi_macro_heavy.cc`. Polyphonic envelopes before any API change |
| **Peaks `Lfo` and `MultistageEnvelope`** (Gillet) | MIT [verified] | int16 fixed point; 8 segments; linear, exponential or quartic. Presets ADSR, AD, ADR, AR, ADSAR, ADAR and looping variants. LFO in sine, triangle, square, steps and noise, with shape, parameter and phase. `Configure()` takes four values, one per knob [verified] | Tens of bytes of state. Tables are generated at 48 kHz, one block at 6 kHz. Skip `wav_digits` (36,824 B). Needs stmlib `pattern_predictor.h` (not vendored) for tap sync |
| **Stages `SegmentGenerator`** (Gillet), plus Bryan Head's `qiemem` fork | MIT on `segment_generator.*` [verified]. The fork's headerless `stages/envelope.*` is licence unknown | One generator that is an envelope, LFO, S&H, slew or sequencer by configuration. The fork adds track-and-hold, Turing, random LFO, logistic and attractors [verified function list] | An advanced mode for later. Fixed 31,250 Hz, 8-sample blocks. Depends on `delay_line.h` and `gate_flags.h` (not vendored), `tides2/ramp/ramp_extractor.h` and `variable_shape_oscillator.h` [verified]. 2–3 days |
| **Tides 2 `PolySlopeGenerator`**; **Frames `PolyLfo`** and `Keyframer` | MIT [verified] | Four correlated slopes from one page; four LFOs from one rate; a keyframe morph | Later. Tides 2 carries a 24.6 KB wavetable; Frames about 16.5 KB of tables [verified sizes] |
| **4ms MiniPEG** (Dan Green) | BSD-2-Clause for "SinglePingable source code" [verified] | A pingable envelope with one SHAPE knob over 5 skew and curve regions, and 19 divide or multiply ratios [verified: `envelope_calcs.h`] | A tempo-following envelope. Take only the envelope files, not the ST HAL trees |
| **DaisySP `Adsr`, `AdEnv`** (Electrosmith) | MIT [verified] | Float, simple | The fallback if Peaks proves awkward |
| **schwung-mono** (Tim Cox) | MIT [verified: LICENSE, README] | A clean-room, Elektron-style LFO and arp inside a Schwung instrument | An MIT behaviour reference for the LFO modes |
| **Elektron Digitone manual** | Proprietary manual, no code | Eight LFO parameters: SPD, MULT, FADE, DEST, WAVE, SPH, MODE (free, trig, hold, one, half), DEP [reported: Digitone manual p. 44–45, 51] | The UI spec: two pages of four knobs |

### 3.2 Recommended design

**Counts:**
- Stage C1 has 2 global LFOs, 2 envelopes and 1 CHANCE source (§5).
- Stage C2 makes the envelopes per-note and adds two key-triggered LFOs, LFO3 and LFO4, for engines that opt in (§4).

**LFO:**
- **Shapes:** SIN, TRI, SAW, RAMP, SQR, EXP, S&H and SMOOTH, the stepped and smooth random taken from the CHANCE generator. That is Schwung's six plus ramp and exponential, covering Elektron's set [reported].
- **Speed:** SPD × MULT, Elektron-style. Free in Hz, or synced to the tempo.
  - Synced phase comes from `fm1_seq`'s master tick and resets on Start.
  - Free phase integrates in samples.
- **Modes:** FRE (free-running), TRG (restart on a note), HLD (free-running, sampled at a note), ONE (one cycle) and HLF (half a cycle).
- **Also:** SPH (start phase), FADE (in or out) and DEP (bipolar).
- **Pages:** WAVE, SPD, MULT, DEP, then DEST, MODE, SPH, FADE. ALGORITHM picks LFO 1–2, and SELECT pages.
- **Scope strip:** one cycle, with the fade and a moving phase dot.

**Envelope:**
- **Pages:** ATK, DEC, SUS, REL, then DEST, AMT, CURVE, LOOP. Times are exponentially mapped [inferred].
- **CURVE:** linear, exponential or quartic, as in Peaks.
- **LOOP:** off, AD loop or ADSR loop.
- **Also:** a velocity amount, and the trigger: every note, legato, or first note only.

**Global versus per-voice.**
- `set_param` is engine-wide [verified: `fm1_engine.h`], so in C1 the envelopes are paraphonic: any note triggers them, with a legato option.
- Truly polyphonic envelopes come from two places:
  - Plaits' own envelope, exposed now;
  - stage C2.
- Six-Op FM keeps its DX7 envelopes and LFO inside the engine.

**Rates.** Mutable code with a fixed native rate keeps its rate:
- The wrapper advances it by the native-rate sample count per grid tick, through a fractional accumulator. For example, 64 × 48,000 / 44,118 ≈ 69.6 Peaks samples per host block.
- It reads the output at control rate.
- Upstream files stay byte-identical and time constants stay exact. This extends the 2026-10-01 native-rate decision to modulators [inferred].

**Upstream candidate.** The Schwung S&H wrap bug, with its fix (detect a wrap by comparing phase with the previous phase, and keep a separate "has value" flag), goes on `notes/upstream-candidates.md`. Per CLAUDE.md, anything sent upstream is a draft only and needs the owner's sign-off.

## 4. Modulation matrix

### 4.1 What the code already implies

- **No parameter getter.** The host already mirrors every value, in `fm1_app_unit_t`'s `float value[FM1_APP_MAX_PARAMS]` (32), in `sim/web/src/fm1_app.h` 102 [verified]. That mirror is where a base value can live.
- **No voice handle.** `note_on(key, vel)` returns none, and `pitch_bend` is global. Per-voice modulation from the host therefore needs key addressing, or code inside the engine [verified: `fm1_engine.h`].
- **Unsafe destinations.**
  - Macro's Model rebuilds every voice, so it is NOLOCK (docs/12 line 250) and must also be NOMOD.
  - Six-Op reads its patch at note-on, so it is LATCH (docs/12 line 247) [verified].
- **Constraints from the sequencer.**
  - Locks are 7-bit, with 8 lanes per track.
  - D6 sends each lane back to its base at Stop (`engines/seq.md` line 180).
  - Output is byte-identical at host blocks of 1, 7 and 64 frames (docs/12 line 438; `engines/seq.md` D1) [verified].

  Modulation must keep all three.
- **No panel performance controls.**
  - The FM-1's panel has no wheels; the "wheels" in docs/01 are SDK ADC names, mapped to nothing verified [reported: modulation lane].
  - Mod wheel, aftertouch and bend therefore come only from USB-MIDI in.
  - Whether the keys sense velocity is still open (docs/13 line 450) [verified].

### 4.2 Architecture options

A 64-frame block at 44,118 Hz lasts 1.451 ms, which is 348,160 cycles at 240 MHz (5,440 per sample, docs/11 §2) [verified]. Every cost below is [inferred]; pi32v2's real cost per operation is unknown until stage B.

| | A. Host-side global bus | B. Per-voice inside each engine | C. Hybrid (recommended) |
| --- | --- | --- | --- |
| What | `fm1_mod.c`: C99, no heap, host-supplied memory, like `fm1_seq`. Sources are computed on a fixed grid. For each routed destination: `final = fm1_param_clamp(base + Σ amount/64 · source · (max − min))`, then `set_param` only if the value changed | A shared header, `fm1_voice_mod.h`, with per-voice ADSR, LFO and random, and a small source × destination grid. Each engine applies it where it reads its parameters | C1 is A, unchanged. C2 adds a per-note source pool, indexed by key, triggered from the notes the host already routes (after the arp). It also adds an optional API v2 `set_param_mod(self, index, int16 key, float offset)`, where key −1 means global, as in CLAP's `PARAM_MOD` |
| Memory | 4 LFOs about 96 B; envelopes 50–100 B; 16 slots × 6 B = 96 B; destination accumulators about 256 B. **Under 0.6 KB.** About 160 B per preset | About 72 B per voice, so about 0.9 KB per 12-voice engine, plus the grid in each engine's parameters | 0.6 KB + a 12 × 56 B note pool + up to 0.4 KB inside an engine (Macro: 12 voices × 4 parameters × 4 B = 192 B). **About 1.7 KB** |
| CPU per tick | About 1,200 cycles: 0.35 % at one tick per block, about 1.4 % on a 16-frame grid | About 150 cycles per voice per update: 0.5 % once per host block, about 3 % once per Plaits block (3,989 Hz) | About 3,800 cycles, so about 1.1 % at one tick per block |
| For | Works with every engine today, Schwung modules and effects included. Fills the simulator's LFO, ENV and EDIT stubs at once. Precedents: Schwung's slot LFOs, Elektron's per-track LFOs | Truly polyphonic; the best sound | Global reach now, polyphonic where an engine opts in. Precedent: Ambika computes its LFOs once per part and runs envelopes and the matrix per voice [reported: lanes; its constants verified in `common/patch.h` 238–276] |
| Against | One envelope and one LFO phase for all 12 voices | Every engine does the work; parameter pages bloat; cannot reach effects or Schwung modules; a different UI per engine | Needs API v2 and an opt-in per engine. Per-note sources can never reach effects or non-per-key parameters, a rule Surge has too [reported] |

Audio-rate modulation for every slot is not recommended now. At 12 voices × 64 samples × 8 slots it would take about 18 % of a block [inferred]. Audio-rate FM belongs inside engines (Plaits' FM models, Six-Op).

### 4.3 Locks and modulation: a base plus an offset

The proven instruments agree on one rule: modulation is an offset from a base value, and a lock or automation replaces the base, not the offset. CLAP states it as "The value heard is: param_value + param_mod" [verified: `include/clap/events.h` 94–109]. Schwung's modulation bus resolves the base, then the lane override, then a sum of offsets [verified: `chain_mod.c` 160, 259]. Proposed rules for docs/12 and `engines/seq.md`:

- **M1.** A lock, a lane base or a knob turn writes the parameter's base in the host mirror. The host sends `clamp(base + offsets)`. With no route on a parameter, the final value equals the base, so every existing sequencer render test stays byte-identical.
- **M2.** D6's revert at Stop restores the base. LFOs keep their mode: FRE keeps running, while TRG, ONE and HLF wait for the next note.
- **M3.** The modulators' own settings are typed parameters with uids, in a MOD unit. They include LFO speed, depth and fade, envelope times, slot amounts, and MACRO A and B. So a sequencer lane can lock "LFO depth on this step", as Elektron does, or lock a cable's depth, as the Deluge's automatable cables do. MACRO A and B, locked by lanes and read as matrix sources, give "sequencer lanes as modulation sources" (Shruthi's SEQ1/2, Ambika's SEQ_1/2) with no new sequencer code.
- **M4.** NOLOCK implies NOMOD. An ENUM destination needs an explicit MOD flag, and is quantised and rate-limited.
- **M5.** LATCH parameters are sampled once at note-on, base plus offset at that moment, so modulation acts per note.
- **M6.** Order at one frame: note-offs, reverts, locks (to the base), the modulation tick, then note-ons. A retriggered envelope or LFO then starts from the step's locked values. This is consistent with D2 (`engines/seq.md` line 176) [verified].
- **M7.** Locks stay 7-bit and offsets sum in float. The SMOOTH flag's 2–3 ms ramp (docs/12 line 248) [verified] hides both the 128-step lock grid and the control-rate steps.

### 4.4 Control grid and determinism

- **A fixed grid.** Evaluate modulation on a fixed grid of absolute sample time, not once per render call. 16 frames is 2,757 Hz; 32 frames is 1,379 Hz. The host splits renders at grid points, as `fm1-render` already splits them at events (D1). Output then stays byte-identical at host blocks of 1, 7 and 64 frames.
- **Other instruments' rates** [reported: lanes]: Ambika 976 Hz, Schwung 344 Hz, schwung-mono every 8 samples, Surge per 32-sample block with interpolation.
- **Pitch** is the most zipper-prone destination: ramp it on every tick.
- **Random sources** each get their own xorshift, seeded from the preset or set; never `stmlib::Random`.
- **Replace every `rand()`.** Three DaisySP classes call `rand()`: `SmoothRandom` (`smooth_random.h` 57), `ClockedNoise` (`clockednoise.cpp` 25) and `PitchShifter` (`myrand`) [verified]. Replace them with the project PRNG so the simulator and device stay bit-exact (docs/14).

### 4.5 Slots, sources and destinations

**A slot** is 6 bytes:

| Field | Type | Values |
| --- | --- | --- |
| source | u8 | |
| unit | u8 | sound, FX1, FX2 or host |
| destination | u16 | parameter uid |
| amount | s8 | −64..+63, as Elektron's DEP |
| flags | u8 | polarity, curve, via |

Sixteen slots take 96 B per preset.

**Sources:**
- **Global:**
  - LFO1–2, ENV1–2 (paraphonic in C1), and CHANCE (S&H, smooth, Turing, drift);
  - MACRO A and B;
  - the arp's step and its random value;
  - the SEQ gate;
  - MIDI CC, mod wheel, aftertouch and bend, from USB-MIDI;
  - a constant.
- **Per note (C2):** ENV1–2, LFO3–4 (key-triggered), velocity, note number, a per-note random value, and poly aftertouch.
- **Default polarity:**
  - Bipolar: LFOs, bend, note number and random.
  - Unipolar: everything else, as in Shruthi.
  - A slot flag overrides the default, as in the Deluge and Vital [reported].

**Destinations:**
- any parameter flagged MOD in the sound slot or either effect slot;
- the host's PITCH (±24 semitones at full scale, summed with MIDI bend into `pitch_bend`);
- the host's AMP, a multiply before `fm1_mix_limiter`, which gives tremolo;
- the modulators' own parameters, for example LFO2 speed from ENV1.

**Scaling** is linear in parameter space. Most of our parameters are 0–1 macros that the engines map exponentially inside themselves.

**Free extras:**
- **VIA:** an amount × another source, like the mod wheel on Shruthi's last slot.
- **CURVE:** a power curve, as in MrHyde and Vital.

### 4.6 Editing a slot with four knobs on 240×240

- **The EDIT page** shows the matrix as a list of 5–6 rows of at most 18 characters, for example `1 LFO1>Timbre  +32`.
  - SELECT moves the row.
  - KNOB1 is the source and KNOB3 the amount; KNOB4 is VIA or CURVE.
  - KNOB2 is the destination. It opens a list on the first detent and commits on a press or after 1 s idle, the list behaviour docs/13 line 151 gives SELECT [verified].
- **Quick assign.** Hold LFO or ENV and turn KNOB1–4 on any HOME or FX page. That sets the held source's amount on the parameter under that knob, creating or reusing a slot.
  - It is Plinky's per-parameter modulation row and Movy's "hold a step, turn a knob" lock gesture, rebuilt for encoders without touch.
  - docs/13 line 153 already moved Movy's LFO assign "on the engine and FX pages" [verified]; this is where it lands.
- **Parameter bars:** a dot marks a routed parameter (as docs/13 does for lanes), a bracket shows ± the amount, and a tick shows the live value. Keep the 4 px gaps.

**Recommendation:** option C. Build C1 first, because it needs no engine change and fills three stub buttons. Add C2 once API v2's uids and flags exist, starting with Macro.

## 5. Sample-and-hold and other eurorack-type effects

The shortlist is ranked by sound per line of code. "Modulator" means a matrix source; "audio" means an `FM1_KIND_AUDIO_FX` on the stereo bus. RAM and CPU classes are [inferred] unless marked.

| # | Unit (page name) | Kind | From | Licence | CPU / RAM | What it adds |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | **CHANCE**: stepped S&H, smooth random, drift | modulator | Our own C, after DaisySP `SampleHold` (Electrosmith, Paul Batchelor) and card 106's QRV and FRV (Matt Allison); Plaits `clocked_noise.h` and `smooth_random_generator.h` are vendored | MIT [verified: DaisySP header and LICENSE; card 106 `info.yaml`] | tiny, under 100 B | Classic eurorack random to any destination, clocked by `fm1_seq`, and repeatable per seed |
| 2 | **TURING** and **RUNGLER** | modulator | Workshop Computer card 20 `turingmachine.h` (Chris Johnson, 53 lines); Bastl Kastle 2 `KastleRungler.hpp` (106 lines) | MIT [verified: card 20 `info.yaml` only; Kastle 2 LICENSE and headers] | tiny | Looping random melodies and modulation, with length and flip probability |
| 3 | **CRUSH**: sample rate and bit depth | audio | Plaits `fx/sample_rate_reducer.h` (vendored, 136 lines, polyBLEP-smoothed) plus a bit-depth stage; DaisySP `Decimator` | MIT [verified] | tiny, tens of bytes | Audio-rate sample-and-hold: aliasing and lo-fi grit |
| 4 | **S&H FILTER** | audio + modulator | CHANCE clocking random cutoffs into the vendored stmlib `Svf` | MIT [verified: vendored stmlib] | tiny | The burbling random filter, synced to the sequencer |
| 5 | **FOLD** and drive | audio | DaisySP `Wavefolder` (Nick Donaldson); the wavefolders in Workshop Utility Pair (Chris Johnson) and card 106 (Buchla-style); Plaits `Overdrive` is vendored | MIT [verified] | tiny to light | West-coast harmonics on any engine |
| 6 | **CHORUS** | audio | Junologue Chorus (Peter Allwin; Schwung port by Charles Vestal) | MIT [verified]. Keep the upstream "Copyright 2020 Peter Allwin" notice | light; 512 floats (2 KB) per delay line | Juno-60 modes I and II; a different colour from our Ensemble |
| 7 | **WARP**: ring mod, fold, frequency shift, bitcrush, Chebyshev | audio | Warps cross-modulator (Gillet) with Matthias Puech's Parasite modes | MIT [verified] | medium (6× oversampling at 96 kHz); 5–57 KB by mode | Eurorack's best-known meta-modulator, against its own internal carrier |
| 8 | **ECHO**: ping-pong with wow | audio | Our own code on stmlib `DelayLine` (121 lines, not vendored yet), with Flutter2-style wow (Airwindows, Chris Johnson) | MIT [verified] | light; 88 KB for 1 s mono int16 | Tempo-synced delay. Stock has a Delay [reported: docs/02], so this restores it |
| 9 | **REPEAT**: beat repeat, stutter, reverse, tape stop | audio | The repeat, stutter and brake functions in Schwung Performance FX (chaolue; Charles Vestal's repo) | MIT on `perf_fx_dsp.*` [verified]. Skip the bundled Bungee (MPL-2.0) and `pfx_revsc.h` (Csound lineage) | light; shares ECHO's buffer | Performance glitches locked to SEQ |
| 10 | **SHIFT**: octave, detune, shimmer feed | audio | Clouds `PitchShifter` (Gillet) | MIT [verified] | light; 8 KB | Pitch effects in 8 KB. Diff Clouds' `fx_engine.h` against the vendored one first |

**Later modulators** (all MIT [verified]):
- Marbles' X and T generators with déjà vu, the deluxe CHANCE, about 96 KB of flash tables [inferred];
- Streams' Lorenz (CHAOS) and vactrol envelope;
- Peaks' bouncing ball;
- Frames' keyframer as a MORPH macro over KNOB1–4.

**Constraints:**
- **Memory.**
  - The stock layout leaves a gap of 387,924 bytes, part of it stock's heap [inferred: docs/11 §2]. Plate takes 65,632 B and PSX Verb 134,208 B on 32-bit (`engines/README.md`) [verified].
  - So the time effects (ECHO, REPEAT, a looper) share one host-owned int16 arena, and only one big time effect is active at a time [inferred].
  - Sizes at 44,118 Hz: 1 s mono is 88 KB, 0.5 s stereo 88 KB, 0.75 s per side 132 KB.
- **Tempo.** ECHO, REPEAT, the S&H clock and synced tremolo need tempo and a beat position in `fm1_host_t`. The Schwung shim answers `get_bpm` with 120 and `get_beat_position` with −1 today (`engines/schwung.md` line 47) [verified].
- **No audio input.** The FM-1 has no audio input jack, so WARP and ring modulation run against an internal carrier or another engine. Whether the device consumes USB audio from the host is untested [inferred].
- **Left out:**
  - DaisySP-LGPL (its ReverbSc alone is 98,936 floats, about 396 KB, and LGPL);
  - Schwung Space Delay, derived from the unlicensed `cyrusasfa/TapeDelay`;
  - DaisySP's 128 KB `PitchShifter` and Airwindows GlitchShifter and TapeDelay2 (about 1 MB and up);
  - full Clouds (about 180 KB) [verified sizes].

## 6. Licences

**Usable anywhere** (the public web simulator and a shareable FM-1 binary) [verified unless noted]:
- **Mutable's STM32 code** (MIT): Yarns, Peaks, Stages, Marbles, Tides 2, Frames, Streams, Warps, Clouds and Plaits. stmlib is MIT except `ui/event_queue.h`, which `UPSTREAM.md` already excludes.
- **Schwung and Schwung modules** (MIT): Schwung itself, Super Arp, Eucalypso, MrHyde, Denis, schwung-mono, Junologue Chorus and Performance FX's own files.
- **Other MIT:** Loom's headed files; DaisySP (`daisyaudio/DaisySP` only); Workshop Computer cards 14, 20, 26, 45, 54, 57, 58, 59 and 106; Utility Pair; Kastle 2; 4ms PEG-v2; Plinky's software; CLAP (semantics only); Airwindows; Midier; Ardour `simple_arp.lua`.
- **BSD:** MCL (BSD-3), Amalgamated Harmonics (BSD-3), ML Modules (BSD-3 and MIT), 4ms MiniPEG and QPLFO (BSD-2).
- **Public-domain equivalents:** Axoloti `cpwitz` objects (CC0) and Pd ELSE (WTFPL).

**Notices to handle when vendoring:**
- **Keep every file's own header.** Carry MCL's BSD-3 notice with anything lifted from it, as docs/12 line 438 planned for its lock store.
- **Write the MIT notice ourselves for cards 20, 57 and 106.** They declare MIT only in `info.yaml`, with no LICENSE text; credit Chris Johnson, Andy Jenkinson and Matt Allison.
- **Junologue:** keep upstream's "Copyright 2020 Peter Allwin". The port's LICENSE dates it 2024.
- **Licence unknown, so don't copy:** Loom's `sequencer_step.h`, Phazerville's headerless `EbbAndLfo.h` and `tideslite.*`, and `qiemem/eurorack`'s `stages/envelope.*`.
- **Phazerville** says it includes "some GPLv3 bits". Take only files with MIT headers.
- **MiniPEG:** take only the envelope files, not the ST HAL trees.
- **Names and credits.**
  - Do not use Mutable module names, Plinky, CHOMPI, MicroFreak or Elektron names in the UI (eurorack README; `UPSTREAM.md`).
  - Credit authors by name in each engine's `credits` string and in the simulator footer: Emilie Gillet, Charles Vestal, Handcrafted Media, Chris Rogers, Justin Mammarella, Matthias Puech, Bryan Head, Electrosmith and Paul Batchelor, Chris Johnson, Matt Allison, Bastl Instruments, Dan Green (4ms), Peter Allwin, chaolue and Tim Cox.

**Personal builds only:** GPL-family code, in `third_party/<name>/` behind a build switch [verified licences]. This covers:
- Deluge (GPL-3.0-or-later);
- Mutable's AVR firmware (Shruthi-1, Ambika, Midipal, Anushri, Grids, Branches; GPL-3.0-or-later);
- monome libavr32 and Ansible (GPL-2.0, read as GPL-2.0-only) [inferred reading];
- crow (GPL-3.0) and Teletype (GPL-2.0);
- preenfm3, Surge, Vital, Squinktronix, Bogaudio, Count Modula, Odin 2, Helm, QMidiArp, LMMS and the MOD arpeggiator;
- DaisySP-LGPL (LGPL-2.1, with a relink duty against JieLi's closed libraries).

Its effects on what we ship:
- **The public simulator.** GPL code there makes the page's wasm a GPL work, with source offered. That is feasible, since the repo is public.
- **GPL-2.0-only code** (Ansible) also cannot be combined with Apache-2.0 msfa or with GPL-3-only code in one build [inferred].
- **A shared firmware that links JieLi's SDK** must not contain any of it (CLAUDE.md).

**None of the recommendations needs GPL code.** Every role above has an MIT or BSD source.

**LXR** is not GPL: its terms forbid commercial use and require full source for modified redistributions [verified: `lfo.h` header]. Project policy (CLAUDE.md) treats it like GPL for shared builds and keeps it out of the simulator.

**Inspiration only:**
- Elektron, Roland, Arturia and Korg manuals [reported];
- arpie (no licence);
- MIDIbox SEQ ("personal non-commercial use only", and it needs Thorsten Klose's permission);
- Befaco Noise Plethora (CC BY-NC-SA 3.0);
- the Schwung Space Delay upstream (no licence);
- Beads (source not published).

## 7. Getting it into the simulator

**Today:** ENV, LFO, EDIT, SAVE, ARP, SEQ, PLAY/STOP and REC each open a "not in the simulator yet" popup (`sim/web/README.md` line 97) [verified]. The sequencer core is built but not yet wired to PLAY/STOP, REC and SEQ (lines 237–238) [verified]. The work below fits after that integration. Each stage is one branch and one PR, native and wasm together.

| Stage | What | Simulator result | Gate |
| --- | --- | --- | --- |
| S0 | The sequencer integration under way: API v2 transport and tempo in `fm1_host_t`, parameter uids and flags (LATCH, SMOOTH, NOLOCK, plus a new MOD), PLAY/STOP, REC and SEQ wired | Sequencer buttons live | docs/12 A-seq pins |
| S1 | `fm1_mod` C1: 2 LFOs, 2 envelopes, CHANCE, a 16-slot global matrix, quick assign | **LFO** and **ENV** pages | M1–M7 tests (below) |
| S2 | Plaits' internal envelope exposed in Macro and Macro Heavy (can run beside S1) | Polyphonic pitch, timbre and morph envelopes | Reference tests against upstream `voice.cc` |
| S3 | The MIDI_FX contract and `fm1_arp` (Yarns core, latch, Euclid, swing from `fm1_seq`) | **ARP** page; ARP and SEQ together | Golden event streams at 30–300 BPM, no drift over 10,000 steps, seeded and reproducible, block-size identity |
| S4 | The matrix list and the remaining sources: arp step and random, TURING, S&H FILTER | **EDIT** page | Layout check; slot edits round-trip |
| S5 | Audio FX, first wave: CRUSH, FOLD, CHORUS | FX list grows | Render against upstream where one exists |
| S6 | C2: `set_param_mod` and MOD_PER_KEY in Macro first; the arp's CHANCE page (Super Arp's modifiers) and ratchets | Per-voice envelopes on chords | Zero-offset identity per voice |
| S7 | Time effects on the shared arena (ECHO, REPEAT), then WARP and SHIFT; Marbles, Tides 2 and Frames extras; Loom's JUMP and GRID | The rest | Arena budget test |

**Every stage passes these:**
- **Parity.** `fm1-render` (native) and the simulator's wasm give the same output for the same pattern and seed. Integer paths match byte for byte; float paths stay within docs/14's tolerance classes.
- **Determinism.** Output is byte-identical at host blocks of 1, 7 and 64 frames, with routes active.
- **Layout.** New screens pass `fm1_tft_check_layout`'s 4 px gap test.
- **Host contracts.** These follow `tests/test_engine_host.py`:
  - a zero amount is an exact no-op;
  - a NOLOCK parameter is refused as a destination;
  - a lock moves the base and the LFO still swings around it;
  - D6 Stop works with modulation running;
  - `fm1_mod_create` does not depend on the memory's prior contents;
  - NaN in a source or amount is survived;
  - a golden trace of the LFO modes (FRE, TRG, HLD, ONE, HLF).
- **Licence.** `UPSTREAM.md`, `credits` strings and the simulator footer are updated in the same PR.

**On the dev board (stage B, docs/14):**
- Measure the cycles of each stage on the AC79.
- Answer the second-core question, and with it whether the effects move to cpu1.

These stages add roughly 3,000–5,000 lines of our own source [inferred]. With Capture and the sequencer added since the 7,463-line mark, check whether CLAUDE.md's dead-code audit falls due during this work.

## 8. Owner decisions needed

1. **Matrix architecture.** Option C, with C1 first?
2. **Counts.** 2 global LFOs, 2 key-triggered LFOs in C2, 2 envelopes and 16 slots?
3. **Control grid.** 16 frames (2,757 Hz) or 32 frames (1,379 Hz)?
4. **Amount resolution.** 7-bit (−64..+63, which locks can drive), or finer?
5. **Arp base.** Our own C core after Yarns plus Super Arp's modifiers (recommended), or a native port of Super Arp whole?
6. **Arp recording.** Record before the arp (recommended), or after it?
7. **Stock names.** Keep stock's arp mode names as presets?
8. **Gestures.** Tap ARP to toggle and hold to latch; hold LFO or ENV and turn a knob to assign. Are these right for the panel?
9. **GPL in this area.** Keep the arp, modulation and effects tree MIT and BSD only (recommended), or allow GPL code such as Grids or Ansible in personal builds behind a switch?
10. **Effects memory.** One big time effect at a time on a shared int16 arena: 88 KB (1 s mono) or 132 KB (0.75 s stereo)?
11. **MACRO A and B.** Put them on the GLO page as knobs and matrix sources?
12. **Page names.** ARP, LFO, ENV, CHANCE, TURING, CRUSH, FOLD, CHORUS, WARP, ECHO, REPEAT, SHIFT, with no Mutable module names. Are these right?

## 9. Sources

**This repository, read for this note** [verified]:
- CLAUDE.md
- `engines/include/fm1_engine.h` (19–23, 42–46, 70–74)
- `engines/include/fm1_seq.h` (33, 192, 208)
- `engines/README.md` (memory table, reference tests)
- `engines/seq.md` (D1, D2, D6)
- `engines/schwung.md` (line 47)
- `engines/mi-fx.md`
- `engines/src/sw_psxverb.cc`
- `engines/test/schwung_race.cc`
- `engines/third_party/mutable/` (stmlib tree; `plaits/dsp/engine2/arpeggiator.h`)
- `sim/web/www/worklet.js` (1–2)
- `sim/web/README.md` (97, 236–246)
- `sim/web/src/fm1_app.h` (55–60, 102)
- docs/01 (124–125), docs/02 (187–189), docs/08 (116), docs/11 (§2, §8), docs/12 (103, 168–173, 247–250, 281, 438), docs/13 (57, 84, 151–153, 450), docs/14
- notes/2026-10-01-chompi-evaluation.md
- `reference/mi-eurorack` at `08460a6` (`yarns/part.cc` header and line 366)

**Upstream, at the pinned commits** [verified by this run's lanes and verifier]:
- Yarns: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/yarns/part.cc
- stmlib `note_stack.h`: https://github.com/pichenettes/stmlib/tree/e3bd7c9cc00e4364166f9905c0509b6ffd0535ec/algorithms
- Super Arp: https://github.com/handcraftedcc/schwung-superarp/blob/6eefd02af91823e330f7ce86883dc097b634ecc1/src/dsp/superarp.c
- Loom: https://github.com/rcrogers/yarns-loom/blob/7d49fdec18b032513fbb27f37d4664355e11f671/yarns/arpeggiator.cc
- MCL: https://github.com/jmamma/MCL/tree/693a410017833a732c24412db5fcce9049e78642/src/mcl/Drivers/Generic/Sequencer
- Deluge: https://github.com/SynthstromAudible/DelugeFirmware/tree/62a516c2b98804e50602477c4772c19a99cc6329/src/deluge/modulation
- Schwung built-in arp: https://github.com/charlesvestal/schwung/blob/ba3b39d3c61d42c662fdaed054b6ab96f55ab0eb/src/modules/midi_fx/arp/dsp/arp.c
- Schwung LFOs: https://github.com/charlesvestal/schwung/blob/ba3b39d3c61d42c662fdaed054b6ab96f55ab0eb/src/host/lfo_common.h
- Eucalypso: https://github.com/handcraftedcc/schwung-eucalypso/blob/f0ff525/src/dsp/eucalypso.c
- monome libavr32 arp: https://github.com/monome/libavr32/blob/5eca040f889c632f81d7931d08adcc403ec626c0/src/arp.c
- Peaks modulations: https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/peaks/modulations
- Stages: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/stages/segment_generator.cc
- Stages fork (Bryan Head): https://github.com/qiemem/eurorack/blob/2b07022a714125362e3cb4625a29e4972a6eb880/stages/segment_generator.cc
- Marbles: https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/marbles/random
- Tides 2: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/tides2/poly_slope_generator.h
- Frames: https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/frames
- Streams: https://github.com/pichenettes/eurorack/tree/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/streams
- Plaits voice: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/plaits/dsp/voice.cc
- Plaits sample-rate reducer: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/plaits/dsp/fx/sample_rate_reducer.h
- Clouds pitch shifter: https://github.com/pichenettes/eurorack/blob/08460a69a7e1f7a81c5a2abcc7189c9a6b7208d4/clouds/dsp/fx/pitch_shifter.h
- Warps with Parasites: https://github.com/mqtthiqs/parasites/tree/32fa66f5acce1bff2f0a7bdd041e29bad3222557/warps/dsp
- Shruthi-1: https://github.com/pichenettes/shruthi-1/blob/56bfe78a27cd7430ab4531439d4efc2834353b17/shruthi/voice.cc
- Ambika: https://github.com/pichenettes/ambika/blob/2c4a6908f373ea0d4191ef7355929691b87941ef/common/patch.h
- CLAP: https://github.com/free-audio/clap/blob/a47f6ba/include/clap/events.h
- MrHyde: https://github.com/handcraftedcc/schwung-mrhyde/blob/3c47f35a69fa82c8554ee62c402064d6bad0a3c7/src/dsp/plaits_move_engine.h
- schwung-mono: https://github.com/timncox/schwung-mono/tree/ce37774
- Plinky: https://github.com/plinkysynth/plinky_public/tree/ee4a340fe66fd2705299b4c15381acec44008f42/sw/Core/Src
- DaisySP: https://github.com/daisyaudio/DaisySP/tree/2c72eaf9eac5fc0dca1919d65d606da907832618/Source
- Workshop Computer: https://github.com/TomWhitwell/Workshop_Computer/tree/7919c1f/releases (cards 20, 45, 106)
- Utility Pair: https://github.com/chrisgjohnson/Utility-Pair/blob/5d0b8df/src/main.cpp
- Kastle 2: https://github.com/bastl-instruments/kastle2/tree/a4a7a04/code/src/common
- 4ms MiniPEG: https://github.com/4ms/minipeg/tree/a53fcd8/src
- Junologue Chorus port: https://github.com/charlesvestal/schwung-junologue-chorus/blob/463bdef/src/dsp/junologue_chorus.c
- Performance FX: https://github.com/charlesvestal/schwung-performance-fx/blob/914d9ee0dd236dafb1baa0646f30836100d52ae3/src/dsp/perf_fx_dsp.c
- stmlib `delay_line.h`: https://github.com/pichenettes/stmlib/blob/e3bd7c9cc00e4364166f9905c0509b6ffd0535ec/dsp/delay_line.h
- Airwindows: https://github.com/airwindows/airwindows/tree/d22a25b/plugins/LinuxVST/src
- Schwung Space Delay (excluded): https://github.com/charlesvestal/schwung-space-delay/blob/aae4c5e/src/dsp/spacecho.c
- DaisySP-LGPL (excluded): https://github.com/daisyaudio/DaisySP-LGPL/tree/c89d380/Source

**Reported:**
- AL-255 `02-rtos.md` and `01-boot.md`, via docs/11 §2;
- Elektron Digitone manual, LFO pages: https://www.manualslib.com/manual/1359411/Elektron-Digitone.html?page=51
- Surge XT modulation routing (manual).

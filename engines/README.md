# engines/ — the FM-1 engine platform, stage A

Swappable sound engines and effects behind one C API, built and tested on a
desktop first (docs/11 §8, stage A). Nothing here runs on the FM-1 yet. The
same sources are meant to build with JieLi's toolchain for the AC79 dev board
(stage B) and, later, the FM-1.

```bash
make -C engines                                  # build/fm1-render (+ the Schwung selftest)
engines/build/fm1-render --list                  # engines, effects, parameters and enum names (JSON)
engines/build/fm1-render --engine macro --param Model=4 \
    --note 0:57:100:1 --note 0:60:100:1 --note 0:64:100:1 \
    --fx ensemble --fx plate --fx-param Mix=0.3 \
    --seconds 3 --out chord.wav                  # A minor, "VA Pair", through two effects
python -m pytest tests/test_engine*.py           # the engine tests
```

## What is here

| Id | Name | Kind | Voices | Built from | Notes |
| --- | --- | --- | --- | --- | --- |
| `macro` | Macro | sound | 12 | Plaits' 8 light engines | [reference-plaits.md](reference-plaits.md); keeps the LPG on Chiptune, which upstream bypasses |
| `shapes` | Shapes | sound | 12 | Braids' 47 shapes | [reference-braids-fx.md](reference-braids-fx.md) |
| `macro-heavy` | Macro Heavy | sound | 4 | Plaits' other 13 engines (strings, modal, speech, particle, drums…) | [plaits-heavy.md](plaits-heavy.md) |
| `sixop` | Six-Op FM | sound | 8 | Plaits' DX7-style engine and its 96 patches | [plaits-heavy.md](plaits-heavy.md) |
| `dx7` | FM6 | sound | 12 | msfa, the FM core of Google's music-synthesizer-for-android (Apache-2.0), the stock FM-1's core; 32 voices of our own and DX7 SysEx | [msfa.md](msfa.md); [below](#fm6) |
| `sw-sophie` | Sophie | sound | 12 | a Schwung module (Matt Estela, MIT), through the shim | [schwung.md](schwung.md) |
| `drums` | Drums | sound | 12 | Plaits' drum classes (Emilie Gillet, MIT), and a rim shot, clap, cowbell and cymbal of this repository's own | [below](#drums); a 16-pad kit on notes 36–51 with two sets of voicings, Deep and Punch |
| `test-sine` | Test Sine | sound | 12 | this repository | tests the host and the analysis |
| `plate` | Plate | effect | – | Rings' reverb, with Elements' Freeze | [mi-fx.md](mi-fx.md) |
| `ensemble` | Ensemble | effect | – | Plaits' ensemble | [mi-fx.md](mi-fx.md) |
| `diffuse` | Diffuse | effect | – | Plaits' diffuser | [mi-fx.md](mi-fx.md) |
| `sw-psxverb` | PSX Verb | effect | – | a Schwung module (Charles Vestal, MIT), through the shim | [schwung.md](schwung.md) |
| `crush` | Crush | effect | – | this repository, after DaisySP's Decimator and Bitcrush (Electro-Smith, MIT) | [below](#crush); a bitcrusher and sample-rate reducer |
| `fold` | Fold | effect | – | this repository | a wavefolder with anti-aliasing; [below](#fold) |
| `drive` | Drive | effect | – | this repository | overdrive and saturation: Soft, Tube, Diode, Fuzz and Tape, anti-aliased; [below](#drive) |
| `echo` | Echo | effect | – | this repository | a stereo ping-pong delay, 10–1,000 ms; [below](#echo) |
| `filter` | Filter | effect | – | this repository | six filter types (SVF, ladder, diode ladder, Sallen-Key, mixed-input Sallen-Key, formant), zero-delay feedback; [below](#filter) |
| `comb` | Comb | effect | – | this repository, after Zölzer's universal comb (*DAFX*) | a tuned comb filter, peaks to notches; Filter's seventh type until 2026-10-05; [below](#comb) |
| `comp` | Comp | effect | – | this repository, after Giannoulis, Massberg and Reiss (JAES 2012) | a feed-forward compressor: peak or RMS, soft knee, parallel mix; [below](#comp) |
| `limit` | Limiter | effect | – | this repository, after Geraint Luff's look-ahead limiter design | a look-ahead brickwall limiter, 0–5 ms; [below](#limiter) |
| `djfilter` | DJ Filter | effect | – | this repository, a trapezoidal SVF after Simper and Zavalishin | one knob: low-pass left of centre, high-pass right, the input bit for bit in between; [below](#dj-filter) |
| `tilt` | Tilt | effect | – | this repository | a tilt equaliser, dark to bright about a pivot; [below](#tilt) |
| `sat` | Master Sat | effect | – | this repository; curve coefficients from Airwindows (Chris Johnson, MIT) | gentle band-limited saturation for the master bus, with Glue; [below](#master-sat) |
| `isolator` | Isolator | effect | – | this repository | a three-band kill EQ with Linkwitz-Riley crossovers; [below](#isolator) |
| `eq` | EQ | effect | – | this repository, on Andrew Simper's trapezoidal SVF (public domain maths) | a low shelf, a bell and a high shelf, exact at 0 dB; [below](#eq) |
| `room` | Room | effect | – | Clouds' reverb and diffuser | a small Dattorro room in 40 KB; [below](#room) |
| `hall` | Hall | effect | – | this repository | a hall reverb on an eight-line feedback delay network, with Freeze; [below](#hall) |
| `gate` | Gate | effect | – | this repository; controls after the Drawmer DS201 and DS301 manuals | a noise gate with a Duck mode, key filters, Listen, Lockout and 0–5 ms look-ahead; [below](#gate) |
| `squash` | Squash | effect | – | Airwindows Pop3, Pressure4 and ButterComp2 (Chris Johnson, MIT), ported by this repository | three compressors: Snap (with a gate), Mu (variable-mu) and Split (half-wave glue); [below](#squash) |
| `shaper` | Transient | effect | – | this repository | a transient shaper: attack and sustain up or down; [below](#transient) |
| `test-gain` | Test Gain | effect | – | this repository | a gain stage for tests |
| `test-ext` | Test Ext | effect | – | this repository | marks the tempo, beats and transport events engine API v3 hands an effect, for tests; [below](#engine-api-v3) |

The Mutable Instruments engines are credited to Emilie Gillet in each
engine's `credits` string and named without MI's trademarks
(`third_party/mutable/UPSTREAM.md`).

### FM6

`src/msfa_dx7.cc` plays DX7 voice data on msfa, Google's FM core,
vendored byte-identical in `third_party/msfa/`; [msfa.md](msfa.md) has the
whole account. In short:

- **msfa's parts, our voice:** msfa's envelopes, pitch envelope, LFO,
  algorithms, kernels, table lookups and note set-up, compiled unmodified
  inside `namespace fm1_msfa` with its NEON switch (`synth.h`) replaced, so
  every build runs the integer kernels, and its tables made ahead of time as
  const data (flash on the FM-1; `tools/msfa_tables.py`). Ours: the LFO's amplitude modulation
  (msfa reads neither AMD nor AMS), the feedback loops of algorithms 4 and
  6 (marked in msfa's table, not run by its `FmCore`; `src/dx7_loop.cc`,
  msfa's own kernels to the bit), the voice's transpose, twelve voices,
  and four macros.
- **Parameters:** Patch (32 built-in voices, then User 1–32; LATCH, MOD),
  Brightness (the modulators' level, ±24 dB), Env Time (an envelope clock,
  8× to 1/8×), Feedback (−7..+7 on the voice's) and Volume, all four
  SMOOTH, MOD and POLY; Glide and Voice Mode ([below](#glide-and-voice-modes)).
- **Voices:** the built-in ones are ours (`tools/dx7_bank.py`, MIT); the user
  slots take single-voice and 32-voice SysEx dumps through
  `include/fm1_dx7.h` (`fm1-render --sysex FILE`, and the simulator's Load
  DX7 patches), every value clamped.
- **Name:** borrowed, with thanks, from Felucca's FM6 engine (hugelton),
  whose Apache-2.0 `fm6_core.c` is the test oracle; the engine itself is
  Google's msfa.
- **Rate:** msfa runs at the host's rate in 64-sample blocks, its envelope
  clocked by 44,118 / rate (one step a block at the FM-1's rate); its rate
  units are set by the first create, and another rate is refused, as is
  any below 16,385 Hz, where msfa's frequency table overflows.
- **Checked** against Felucca's Apache-2.0 port of the same core
  (`third_party/felucca-fm6/`, `fm1-dx7-oracle`), test only: all 32
  algorithms within 0.3 dB of envelope and 28–40 dB SNR, and the rest in
  tests/test_engines_dx7.py.
- **Cost:** 15,848 bytes an instance at 44,118 Hz on 64-bit, 32-bit and
  pi32v2 alike (no pointers); at another rate 4,100 more, its own frequency table.
  msfa's tables are 20 KB of const data (flash on the FM-1), no longer
  28.7 KB of shared RAM (msfa.md, "Tables in flash"). Twelve voices take
  0.36–0.64 % of a block on this desktop, about a third of Macro's twelve.

### Macro and Macro Heavy, page 3: the envelope and the gate

Plaits' `Voice` (Emilie Gillet, MIT) runs a decay envelope that every
trigger restarts. With TRIG patched it reaches FREQ, TIMBRE and MORPH through
the three attenuverters, and the low-pass gate is driven one of three ways
depending on what is patched. Both wrappers run that envelope per voice and
expose it on a third page, after the existing parameters, so earlier indices
keep their meaning (`src/mi_plaits_env.h`, shared by both). Decay and Colour,
on page 2 since stage A, set the envelope's and the gate's times.

| Parameter | Range, default | What it does |
| --- | --- | --- |
| Env Pitch | −1..1, 0 | The FM attenuverter: the note moves by amount × env² × 48 semitones, where amount is Plaits' curve (a ±0.05 dead band, then a square law to ±0.9975), so ±0.5 is ±11.3 semitones at the note-on. On Speech it also sets the prosody amount, as on the module |
| Env Timbre | −1..1, 0 | The TIMBRE attenuverter: amount × env added to Timbre, clamped to 0..1. On Macro's Chip it sets the chiptune engine's own envelope instead (shorter as \|value\| rises), as on the module |
| Env Morph | −1..1, 0 | The MORPH attenuverter, as Env Timbre. On Speech the envelope's reach on the note and Morph fades out as Harmonics enters the word banks (Voice's scaling); Word Speed stays its own parameter |
| LPG | Gate, Ping, Off; Gate | **Gate**: LEVEL patched, the gate follows the key at the note's velocity (stage A's only behaviour). **Ping**: TRIG alone, each note-on pings the gate, which closes over Decay whether the key is held or not; the self-enveloped Heavy models then ring out without the key-up release. **Off**: the gate is bypassed, as Plaits does for its self-enveloped models, and the key gates a plain gain released with the gate's own curve. On Ping and Off the velocity's accent, 1.3v / (0.3 + v), scales the voice, since LEVEL no longer carries it (1 at velocity 127) |

- **Defaults change nothing** [verified]: at the page's defaults both engines
  write the same bytes as before it existed, across 338 before/after renders
  (every model, chords past the cap, bends, knob turns, both rates, host
  blocks of 7, 12 and 64, instance fills 0xA5 and 0xFF), and the reference
  suite is unchanged and passes.
- **Against upstream** [verified: tests/test_engines_plaits_env.py], sample
  for sample at 47,872.34 Hz and within 1 LSB at 44,118 Hz: the
  attenuverters on all 21 slots the two engines wrap (speech prosody and
  Chip's own envelope included); Ping as the module with TRIG alone on the
  14 slots that are always under the gate (not Chip, whose gate upstream
  bypasses, nor Speech and the self-enveloped models, which read the accent
  upstream fixes at 0.8 there); Off, while the key is held, as the module
  with nothing patched on the 11 of those that do not read TRIG.
- **Six-Op FM** has no page 3: its engine is self-enveloped (no gate), and
  its DX7 envelopes are its own.
- Changing the LPG mode while notes sound does not restart them. A note held
  under Off has no gate state to ping from, so it ends when switched to Ping.

### Shapes: where Braids is held

Braids' code (vendored unmodified, `third_party/mutable/braids/`) shifts by
a negative count or by 32, or reads past a table, at some edges of pitch and
Timbre. ASan and UBSan found them; on a given build each gave some output,
but not one any C++ compiler promises, and Wave Line's depended on what the
linker put after its table. The wrapper (`src/mi_shapes.cc`) holds every
voice inside what the code handles, in Braids' own units (1/128 semitone;
Timbre as the int16 0..32,767 the knob becomes):

| Edge | What Braids does past it | Held at | What changes |
| --- | --- | --- | --- |
| The pitch, key + bend + pitch offset, above MIDI 127.99 | Flute (31) reads its 128-entry body filter table past the end (`digital_oscillator.cc:1404`). The filter shapes (17–20) at a high Timbre wrap their int16 shifted pitch from MIDI 136 and shift by 32 in `ComputePhaseIncrement`. Sqr Sync and Saw Sync (7, 8) wrap the synced oscillator's pitch from MIDI 192 at Timbre 1 (`analog_oscillator.cc:64`), reachable only with a pitch offset on a bend | 0..16,383 (MIDI 0..127.99), where `braids.cc` holds its own pitch before `set_pitch` at the default octave; it was 0..32,767 | A note above MIDI 127.99 plays as at 127.99, on every shape. Braids' oscillators already stopped rising at MIDI 128 (both phase-increment tables end there), but what follows the pitch (3x's intervals, the filter shapes' cutoff, Bell's and Drum's partials, Digital's data rate) kept moving |
| Comb (15): the comb's own pitch, key + (Timbre − 0.5) × 64 semitones, below MIDI −16 (Timbre 0 on keys 0–47; below 0.375 on key 0) | `ComputeDelay` shifts by a negative count (`digital_oscillator.cc:90`) | Timbre at 16,384 + 2 × (−2,048 − pitch) or above, so the comb stays at MIDI −16 or above | Nothing steady: the comb's delay is at its longest (8,192 samples, 11.7 Hz at 96 kHz) from MIDI 6.2 down, which the build's shift had mostly landed on too (within 1 LSB in the renders compared). Only the comb's own glide out of that region (a one-pole over 16 Braids blocks, about 4 ms) starts nearer |
| Wave Line (39): Timbre above 32,255 (0.9844) | The scan reads `wave_line[64]`, one past the line's 64 waves (`digital_oscillator.cc:1637`) | Timbre at 32,255 at most | The last 1.6 % of Timbre plays the line's last wave; this build had played a stray one there, up to 42,000 LSB away |

- **Inside those ranges nothing changed** [verified 2026-10-05: 2,162
  renders byte for byte against the build before: all 47 shapes, keys 0–127
  with bends to 127.99, Timbre 0–0.98 and Color 0–1, and Timbre and Color
  turned while notes held, as fm1-render's 16-bit WAVs; and in the
  engine's float output, a reviewer's 282 random scripts of 300 events
  inside the ranges (six a shape; notes, knobs, bends, pitch and
  Timbre/Color offsets turning), rendered at blocks of 64 and 7 from memory
  filled 0x00 and 0xA5, gave the same bits from both builds]. The reference
  suite's points are all inside and pass unchanged.
- **No report under ASan and UBSan** [verified 2026-10-05, Apple clang 21:
  `tests/test_engines_shapes_edges.py`, one render per shape over every key
  at Timbre and Color 0, ½ and 1 with the note from MIDI −96 to 223, and a
  sweep of 8,460 renders, every shape, key, Timbre and Color at 0, 0.001,
  0.37, 0.5, 0.985 and 1, and bends from −48 to +48]. The build before the
  clamps fails the test on shapes 7, 8, 15, 17–20, 31 and 39, and the
  per-note extremes test ([below](#per-note-offsets)) now takes every shape
  on keys 0 and 127.
- **At an edge Shapes plays upstream at the value it holds** [verified:
  `tests/test_engines_reference_braids_fx.py`, Comb on keys 0 and 30 at
  Timbre 0, Wave Line at Timbre 1, Flute and the filter shapes on key 127
  bent up 48, within 0.55 LSB of upstream's oscillator at the clamped pitch
  or Timbre].
- **The clamps hold under turning knobs, bends and per-note offsets, and
  between the knob ends** [verified 2026-10-05: `fm1-shapes-hostile`
  (`test/shapes_hostile.cc`, run by `tests/test_engines_shapes_hostile.py`).
  On every shape, a random script within the engine API (knobs anywhere,
  NaN and infinities included, bends and pitch offsets anywhere in ±48,
  per-note Timbre and Color offsets, Shape switched while notes sound)
  gives the same bits at blocks of 64, 1, 7 and random sizes and from any
  memory fill, and no report under ASan and UBSan. Every voice above MIDI
  127.99 plays the bits of the same script held at 127.9921875; Comb with
  Timbre turning below the clamp, and Wave Line above it, play the bits of
  Timbre held at the clamp. The build before the clamps fails the last
  three on 23 shapes, Comb and Wave Line, and halts under the sanitizers.
  A reviewer's own sweep of 60 such seeds (all 47 shapes, 47,000
  scripted events each) gave no report either].
- The cost is a few integer compares a voice per 24-sample block; no
  table, no libm.
- The module reaches these edges too [inferred: `braids.cc` adds the octave
  setting, up to +2 octaves, after its own clamp, and the LFO range takes
  the pitch below 0]: an upstream candidate, as Plaits' speech read is.

## Drums

A 16-pad drum kit after the classic analogue drum machines, on MIDI notes
36–51: General MIDI's drum keys, in the order and with the labels Sophie
uses (`src/drums.cc`, `src/drum_voices.h`). The engine says so in the API
(`pad_first_note` 36, `pad_count` 16, [Pad kits](#pad-kits)), so the virtual
FM-1 plays its pads on the white keys.

**Where the sounds come from.**

| Model | Code | Used for (Deep / Punch) |
| --- | --- | --- |
| Analog Drum | Plaits `AnalogBassDrum` (its 808-style bridged-T model) | the kick and six toms / – |
| Punch Drum | Plaits `SyntheticBassDrum` ("inadvertently 909-ish" upstream) | – / the kick and six toms |
| Snare | Plaits `AnalogSnareDrum` | Snare / Snare 2 |
| Snap Snare | Plaits `SyntheticSnareDrum`, with a one-pole Tone of ours after it | Snare 2 / Snare |
| Hat | Plaits `HiHat<SquareNoise, SwingVCA, true, false>`: six square waves | the three hi-hats / – |
| Ring Hat | Plaits `HiHat<RingModNoise, LinearVCA, false, true>`: ring-modulated pairs, two-stage envelope | – / the three hi-hats |
| Cymbal | ours: six squares (the hat's bank), two bands, two swing VCAs, after Werner, Abel and Smith's TR-808 cymbal model (ICMC/SMC 2014) | crash and ride |
| Clap | ours: band-passed noise, three short bursts and a longer fourth, and a decaying tail, after the 808 clap's circuit as Baratatronix describes it [reported] | clap |
| Rim | ours: two band-passes (a mode 3.66 times the fundamental) pinged by a 0.1 ms pulse, clipped, after the 808 rim shot's two oscillators [reported] | rim |
| Cowbell | ours: two squares at f and 1.4815 f, duty 0.4798, a two-stage envelope, a swing VCA and a fourth-order band-pass near 880 Hz, after Werner, Abel and Smith's TR-808 cowbell model (AES 137, paper 9207) | on any pad by its Model; none by default |

The Plaits classes are header-only and vendored byte-identical, and called
directly, one object per sounding voice: Macro Heavy's models 10–12 go
through Plaits' `BassDrumEngine`, `SnareDrumEngine` and `HiHatEngine`,
which render both of their classes every block for one output. Our four
voices follow each analysis's structure; their constants are ours, and none
of the papers' or the blog's text or figures is reproduced. The machines
that inspired the kits are named only as credit.

**The kit.** Each pad has a voicing per kit: a model, a pitch, the model's
decay, tone, snap and sweep at the knobs' middle, a drive and a level
(`kKits`). Toms take their pitch from their key, a fourth up (41 sounds as
46, 116.5 Hz, up to 50 as 55); the kick is A1 (55 Hz) in Deep and A#1 in
Punch; the hats and cymbals use the bank Plaits' 808 hat uses (414 Hz and
up), and the clap's band-pass sits near 1 kHz. A pad given another model by
its Model knob plays that model's own voicing (`kModelVoicing`), so a
cowbell on a tom's pad is a cowbell. The cowbell stays an option of Model,
with no pad of its own (the owner's decision, 2026-10-06: no pad swap;
General MIDI puts it on 56, outside the kit's 36–51).

| | Deep | Punch |
| --- | --- | --- |
| Kick | Analog Drum, about 1.7 s to −40 dB, a slight pitch sigh | Punch Drum, a drop from about 230 Hz at the attack to 58 Hz within 60 ms (one cycle's pitch: 125 Hz at 9 ms, 88 at 19, 68 at 32), about 0.27 s to −40 dB, a little drive |
| Toms | Analog Drum, 0.45–0.6 s | Punch Drum, swept, 0.19 s |
| Snares | Snare (808-style, two modes), Snap Snare | Snap Snare, Snare (with all five modes) |
| Hi-hats | Hat: closed 0.09 s, pedal 0.23 s, open 0.65 s; most of their energy at 5–8 kHz | Ring Hat: 0.075, 0.125 and 0.36 s; 5–12 kHz |
| Snares, clap, rim | 0.26 and 0.35 s, 0.29 s, 0.04 s | 0.35 and 0.21 s, 0.28 s, 0.03 s |
| Cymbals | crash 3.1 s, ride 2.3 s | the same lengths, brighter |

Times are to −40 dB under the loudest 5 ms, struck at full velocity,
measured with `fm1-render` [verified 2026-10-05]; nothing here has been
judged by ear yet, and the voicings are a first set. The review moved the
hats' Tone up (Deep 0.6 to 0.85, pedal 0.8; Punch 0.65 to 0.92, pedal
0.88): the first set put the Deep hats' band-pass at 1.8 kHz, with 45 % of
their energy under 2 kHz, two octaves under the 808's hat band (its
band-pass near 7.1 kHz and high-pass, energy at about 5–7 kHz [reported:
Baratatronix]). Their levels in the kit keep their RMS over the first
50 ms, and `kModelGain` still makes each model's own voicing peak at the
same level [verified 2026-10-05: `fm1-render`].

**Parameters.** Pad chooses which pad the per-pad parameters edit, as on
Sophie; every pad keeps its own set. The knobs are relative to the pad's
voicing, so one default fits all sixteen pads and a fresh kit shows true
values whichever pad is focused (Sophie's table can only show pad 1's).

| Page | Parameter | Range, default | What it does |
| --- | --- | --- | --- |
| 1 | Pad | 1 Kick … 16 Ride | the pad the per-pad knobs edit (not a sound: lockable, no MOD, as Sophie's) |
| 1 | Tune | ±24 semitones, 0 | the pad's pitch |
| 1 | Decay | 0..1, 0.5 | the model's decay: 0.5 is the voicing's, 0 and 1 the model's ends |
| 1 | Level | 0..1, 0.8 | the pad's level |
| 2 | Tone | 0..1, 0.5 | brightness: the kicks' and snares' tone, the hats' band-pass, our voices' filters; Snap Snare, which has none, gets a one-pole low-pass |
| 2 | Snap | 0..1, 0.5 | the attack: the kicks' click (Analog Drum's attack FM, Punch Drum's FM envelope depth), the snares' wires, the hats' noise against metal, the cymbal's noise wash, the clap's bursts (14 ms apart down to 6), the rim's click, the cowbell's first stage |
| 2 | Sweep | 0..1, 0.5 | the pitch sweep: Analog Drum's self-FM, Punch Drum's FM envelope length, Snap Snare's FM; on the other models a pitch envelope of ours, up to 24 semitones from above (above the middle) or below (under it), falling back over about 20 ms |
| 2 | Drive | 0..1, 0 | added to the voicing's drive: the signal itself at 0, then more of a soft clip of it pushed up to 8 times |
| 3 | Model | Kit, Analog Drum … Cowbell | Kit: the voicing's model; otherwise that model with its own voicing |
| 3 | Kit | Deep, Punch | the whole kit's set of voicings |
| 3 | Accent | 0..1, 0.5 | the whole kit's velocity sensitivity: at 0 every hit plays as Plaits' unpatched accent (0.8) at full level; at 1 the class's accent is the velocity and the level its square |
| 3 | Volume | 0..1, 0.7 | the kit's level |

- **Twelve parameters.** When Drums was written, the modulation runtime's
  180 shared records (`FM1_MOD_SINK_PARAMS`) held four sound units of the
  engine with the most parameters beside ten of the effect with the most
  (13) and the host's two: 4 × 12 + 10 × 13 + 2 = 180
  (`tests/test_engines_mod_runtime.py`). Drums has twelve, as Macro Heavy
  had. A per-pad choke group and a kit-wide decay were written and
  dropped for it: the hats' choke is the voicings' (the open hat's pad stays
  in it whatever model it plays), and a pad's Decay is its own. Since glide
  ([below](#glide-and-voice-modes), 2026-10-06) Macro Heavy has fourteen
  and the records are 192 with HOST's six since MG9 (320 bytes more
  [verified: `fm1_mod_size()`]), so Drums could take two back: an open
  question below.

- **Flags.** Every FLOAT is SMOOTH, MOD and POLY. A per-pad knob's ramp
  runs in the pad's own values, only while that pad sounds (a change to a
  silent pad applies at once), and keeps going on its pad when Pad moves
  on; the kit's knobs ramp while any voice sounds. Model and Kit are read
  when a pad is struck (LATCH, and MOD: a route is rounded), so a sounding
  hit keeps what it started with. Uids 1–12, in table order.
- **Voices.** Twelve. A pad struck while it sounds is struck again in its
  own voice: the Plaits classes are excited again, not restarted, as the
  circuits are. Otherwise it takes a free voice, else the one furthest into
  a choke, else the quietest: each voice's block peaks, held with a 30 ms
  fall so a low kick near a zero crossing still counts as loud; a hit not
  yet rendered counts as loudest, and the oldest goes among equals. A steal
  cuts what it takes, so it takes what is least heard (the oldest hit can
  be a crash still ringing loud). A hi-hat marks its choke before it takes
  a voice, so with all twelve busy a closed hat takes the open hat's voice
  instead of stealing a pad that would have rung on. Note-offs are
  ignored, and so are notes outside 36–51: a hit rings for its decay. A
  voice ends once it has stayed under −80 dBFS for 10 ms; a choked one
  fades over 4 ms and ends.
- **Per-note offsets.** A hit's offsets ride on its pad's values (ramped)
  and on the kit's; the pitch offset moves it after Tune and the bend.
  Notes are pads, so `set_param_note` reaches the hit on that pad's note.
- **Rate.** As Macro and Macro Heavy (the owner's rule for Mutable code,
  2026-10-01): the classes run at Plaits' 47,872.34 Hz in its 12-sample
  blocks, with Plaits' own time constants, and the mono mix goes through
  one `fm1_resampler.h` to the host. Our voices run there too. Hosts above
  47,872.34 Hz are refused, as for the other Plaits engines. (Running at
  44,118 Hz would save the resampler and stretch the classes' times by
  8.8 %: an open question below.)
- **Noise.** The Plaits classes draw from stmlib's one global generator.
  Each pad has a state of its own, swapped in around its voice's render and
  the global one put back after, and our voices draw from the same state.
  So a pad's noise depends only on its own hits: two pads struck together
  are the two struck apart, summed, and no other engine moves our noise, or
  we theirs.
- **No libm in the render** [verified: `nm -u` on `drums.o`, a test]:
  stmlib's tables (`SemitonesToRatio`, `lut_sine`), polynomial tangents,
  `SoftClip`, and the synthetic snare's two `sqrtf` a block, which are
  correctly rounded everywhere. The browser's module renders the same
  samples (parity, `sim/web`).
- **Velocity.** The class's accent shapes each hit (pulse height, attack,
  brightness) and Accent scales the level.

**Cost** [measured 2026-10-05: this Mac (Apple clang, `-O2`), `fm1-render`,
best of five; desktop figures, which say nothing of pi32v2]:

| Load, per 64-frame block (1,451 µs at 44,118 Hz) | Drums | Macro |
| --- | --- | --- |
| Instance, 64-bit and 32-bit (GCC 12 `-m32` in a container) | 7,616 and 7,424 B | 32,448 and 19,584 B |
| Twelve voices sounding (twelve pads at Decay 1 struck at once) | 25.0 µs Deep, 15.7 µs Punch | 24.7–26.7 µs (twelve held notes, VA Pair and VA+Filter) |
| Twelve pads re-struck every 0.4 s | 22.8 µs Deep, 14.1 µs Punch | |
| One pad re-struck, by model | 2.8 µs (Rim, mostly silent) to 4.8 µs (Analog Drum, Snare) | |
| Silent | 2.6 µs, the resampler alone | 2.5 µs |

So at twelve voices Drums costs about what Macro does with the Deep kit
(0.94–1.01 of it) and about 0.6 of it with the Punch kit, in a quarter of
Macro's memory on 64-bit and two fifths on 32-bit. Re-measured after the
review's changes (the quietest-voice steal, the hats' voicings), best of
seven, same Mac and method: 24.7 µs Deep and 16.0 µs Punch at twelve
voices, 2.6 µs silent, 7,616 bytes (the steal's level fits in the voice's
padding); Macro with twelve held notes 25.6 µs on VA Pair and 27.3 µs on
VA+Filter, and from 19.5 µs (Chip) to 84 µs (2-op FM) over its eight
models [measured 2026-10-05]. Neither figure includes the cost of
denormals: Plaits' own drum classes (their pulse and filter states) run
into them as a long hit rings, which Apple's cores handle at full speed
and an FPU without flush-to-zero may not; stage B should measure with and
without flush-to-zero on pi32v2 [inferred].

On pi32v2 nothing is measured yet. This stream's research compiled the
classes with JieLi's clang and counted their per-sample loops: about 200
instructions a sample for Analog Drum, 270 for Punch Drum, 370 for Snare,
210 for Snap Snare, 130 for Hat and 470 for Ring Hat, upper bounds that
put a dense hit (kick, snare, hat, clap and a tom) at 18–35 % of the
5,440 cycles a sample one 240 MHz core has, at 1 to 2 cycles an
instruction [inferred]. The hats share a choke group, so at most one Ring
Hat rings at a time, but for a choked one's 4 ms. Stage B measures it.

**Tests** (`tests/test_engine_drums.py`): every pad of both kits and every
model sounds cleanly; the deep kick holds 55 Hz and rings over a second,
the punch kick sweeps and ends inside 0.5 s; Sweep moves the kick's drop;
the toms rise with their keys within 35 cents; closed, pedal and open hats
are short, middle and long, and bright (an RMS frequency over 5.5 kHz in
both kits, above the snares' and the clap's); the cowbell rings at 800 Hz; the closed and
pedal hats choke the open one within 5 ms, also when its pad plays another
model, and nothing else is cut; velocity and Accent, Volume, Level, Decay,
Tune and the bend act; twelve voices hold and a thirteenth pad
steals the quietest, sparing an older, louder crash; with every voice
busy a closed hat takes the open hat's voice; a pad struck 24 times takes
one voice; voices end and
the output returns to zero; the per-pad knobs edit only the focused pad;
Kit and Model are read when a pad is struck; Drive saturates; the output is
the same at host blocks of 1, 7 and 64 and from any instance fill; two pads
together are the two apart; no transcendental libm call; and per-note
offsets as the other engines take them (zero is a no-op, an offset on a
lone hit is a base change, a pitch offset is a bend, an offset reaches only
its hit, a new hit starts at none, NaN, infinities, ignored indices and
silent keys, extremes finite on every model and kit). The engine also runs
through `tests/test_engine_host.py`, `test_engine_params.py` and
`test_engine_smooth.py` with every other engine, and its three parity
scenarios through the virtual FM-1. Also run [verified 2026-10-05, in
containers on the build host]: the Drums, host, smooth and per-note tests
under ASan and UBSan (clang 19.1, no report) and in a 32-bit build (GCC
12.2 `-m32`, no warning).

**Open questions** (for the owner):
1. Plaits' rate and a resampler (as now, the 2026-10-01 rule) or the
   host's rate, with no resampler and the classes' times 8.8 % long?
2. The hats' and cymbals' bank: Plaits' (the paper's four fixed oscillators
   an octave up), as now, or the schematic's own frequencies? A table swap,
   best decided by ear.
3. The Punch kit's hats and cymbals: the machine that inspired it played
   samples there; these are synthetic. Keep them, or add a small sample set
   of our own (or CC0)?
4. A circuit-level model of the 808 kick (Werner, Abel and Smith, DAFx-14)
   as a later model, or is Plaits' Analog Drum enough?
5. The voicings were set by measurement, not by ear: the owner is giving
   them a listening pass (2026-10-06).
6. The modulation records grew from 180 to 192 (HOST's four new records in
   MG9, then Macro Heavy's fourteen parameters with glide), so a sound
   engine can now have fourteen at no further cost: give Drums back a
   per-pad choke group and a kit-wide decay in that room, or keep it at
   twelve?

## Crush

`src/fx_crush.cc` is our own code (MIT): an audio-rate sample-and-hold
followed by a quantiser, the pairing of DaisySP's `Decimator` and `Bitcrush`
(Electro-Smith, MIT). No DaisySP code is used, and none of Plaits' vendored
`SampleRateReducer` either, which the roadmap had proposed: ours adds jitter
and fractional bits. Per frame, with one hold clock for both channels:

    guard -> hold (Rate, Jitter) -> quantise (Bits) -> low-pass (Tone) -> x Level = wet
    out = dry x (1 - Mix) + wet x Mix

| Page | Knob | Range, default | What it does |
| --- | --- | --- | --- |
| 1 | Bits | 1–16, 8 | Quantiser step 2^(1 − Bits), the step of a Bits-bit converter spanning ±1; fractional values sweep smoothly. Mid-tread (round to the nearest step): zero is a level, so silence stays silent and no DC appears. Quiet input falls under the first step at low Bits: at 1 bit the levels are −1, 0 and +1, and the host's ±0.5 noise comes out silent |
| 1 | Rate | 0–1, 0.75 | The hold rate on a log scale, 100 Hz × (host rate / 100 Hz)^Rate: 100 Hz at 0, 9,626 Hz at the default (a hold of 4.58 samples at 44,118 Hz), every sample at 1. Holds of a fractional length alternate between its floor and ceiling and average to it exactly |
| 1 | Jitter | 0–1, 0 | Each hold's length × (1 + 0.9 × Jitter × u), u uniform in [−1, 1), at least one sample. The mean rate is kept wherever the hold is 10 samples or longer (Rate up to about 0.62); faster, the one-sample floor lengthens it (by 22.5 % at Rate 1, Jitter 1). u comes from the instance's own xorshift32, seeded alike in every `create`, so renders repeat exactly |
| 1 | Mix | 0–1, 1 | A linear crossfade; 0 is the dry signal exactly |
| 2 | Tone | 0–1, 1 | A one-pole low-pass on the wet signal, coefficient k₀^(1 − Tone) with k₀ for 150 Hz: about 150 Hz at 0, 1.1 kHz at 0.5, 8 kHz at 0.9, and no filter at 1 |
| 2 | Level | 0–2, 1 | The wet signal's gain |

The input passes the same guard as the Mutable effects' (NaN reads as 0,
anything beyond ±16 is clamped, dry path included), and the hold clock never
looks at the samples, so bad input cannot latch the effect: once the next
hold is taken the output is the clean render's again [verified:
tests/test_engines_crush.py]. The low-pass state is flushed to zero below
10^-20 so a tail never goes subnormal on pi32v2. An instance is 176 bytes on
a 64-bit desktop and on 32-bit, all floats, `uint32_t`s and one flag (96
before the SMOOTH ramps) [verified: the 32-bit build, 2026-10-05]. On this desktop (Apple M1 Max) it took 400–500 ns per 64-frame block,
about 0.03 % of the block, against Plate's 900 ns in the same run
[verified: fm1-render's `ns_per_block`, 20 s of noise].

## Fold

A wavefolder (`src/fx_fold.cc`, our own code, MIT): the input is amplified,
offset and folded back on itself each time it passes a fold point, as the
Serge and Buchla folders do [reported]; Mutable Instruments Warps
(cross-folding, [reported]) and Plaits (its waveshaping engine's wavefolder,
[verified: `third_party/mutable/plaits/dsp/engine/waveshaping_engine.cc`])
do it digitally. No code is taken from any of them. Stereo in, stereo out,
each channel folded on its own.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Fold | 0–1 (0.4) | Gain into the folder, 1× to 16× (2^(4 × Fold)). At 0 a signal within ±1 is not folded at all |
| 1 | Symmetry | −1 to +1 (0) | An offset added before folding, in units of the folder's input (fold points at ±1). Away from 0 the folds are uneven and even harmonics appear; at ±1 a quiet signal is rectified |
| 1 | Shape | 0–1 (0) | 0 folds with a triangle (straight segments, sharp corners: bright), 1 with a sine (rounded corners: softer), a blend between |
| 1 | Mix | 0–1 (1) | Dry to wet. At 0 the input passes through unchanged |
| 2 | Tone | 0–1 (0.8) | A 12 dB/octave low-pass on the wet signal, 200 Hz to 19.4 kHz (at most 0.45 of the host's rate) |
| 2 | Level | 0–1 (0.7) | The wet signal's gain |

- **The path:** input guard (NaN reads as 0, ±16 clamp, as the Mutable
  effects) → gain and offset → fold → minus the fold of silence → DC blocker
  (10 Hz) → Tone → Level → Mix. Subtracting the fold of silence, computed by
  the same code on the same values, makes silence in exact silence out at
  any setting and keeps a moving Symmetry from stepping the output
  (tests/test_engines_fold.py).
- **Anti-aliasing: first-order ADAA** (antiderivative anti-aliasing; Parker,
  Zavalishin and Le Bivic, DAFx-16, 2016; applied to wavefolders by Esqueda,
  Pöntynen, Parker and Bilbao, 2017 [reported]) rather than oversampling.
  Each output is the mean of the curve between the previous input and this
  one. The sine's mean has a closed form, sin(πm/2) · sinc(πd/4) for
  midpoint m and step d; the triangle's is computed piecewise for small
  steps, so neither divides a small difference by a small step and there is
  no epsilon. Against a plain per-sample fold of the renderer's 440 Hz sine
  (triangle, Tone open), aliases below 5 kHz are 21–23 dB lower: −75 against
  −52 dB at Fold 0.5, −50 against −29 dB at Fold 1 [verified:
  tests/test_engines_fold.py]. The sine shape of a 440 Hz sine makes nothing
  that aliases. The price: a half-sample delay and a gentle roll-off of the
  wet path (−0.6 dB at 5 kHz, −3 dB at 11 kHz before any folding).
- **Cost:** about 65–80 floating-point operations and at most one divide per
  sample and channel, at most about 10,000 operations and 128 divides per
  64-frame stereo block, worst case and average alike: about 1.4 streams of
  the native-rate resampler ([resampler.md](resampler.md)). 2x oversampling
  with short half-band filters would cost about as much and gain less on a
  heavy fold [inferred]. Desktop: 1.8 µs per block (0.12 % of it, below).
- **Glide:** every control moves to a new value over about 5 ms, sample by
  sample, so output does not depend on block size; values set before the
  first block apply from its first sample. Filter states below 1e-20 flush to
  zero, so long tails never run in subnormals.
- **Memory:** 160 bytes, no delay lines; the struct holds no pointers, so
  the same on a 32-bit build [inferred].
- fm1-render sets an effect's parameters only before the first block, so
  `build/fm1-fold-test` (`test/fold_test.cc`) drives Fold directly: every
  parameter changed mid-stream to any value, NaN and infinities included,
  between blocks of 1–64 frames; the glide; and the host rates it accepts
  (8–384 kHz).

## Drive

Overdrive and saturation (`src/fx_drive.cc`, our own code, MIT): five
curves, chosen by Type, that the sound is driven into, each anti-aliased.
No code is taken from anywhere; the anti-aliasing is Parker, Zavalishin and
Le Bivic's (DAFx-16), as Fold's. Stereo in, stereo out, each channel shaped
on its own.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Type | Soft, Tube, Diode, Fuzz, Tape (Soft) | The curve (below). A change crossfades over 5 ms; a second change waits for the first to finish |
| 1 | Drive | −12 to +36 dB (+12) | Gain into the curve. At −12 dB the renderer's 0.5 sine stays within 0.5 % of linear on Soft |
| 1 | Tone | 0–1 (0.5) | A tilt about 800 Hz: 0.5 is flat; towards 0 the highs fall, by up to 18 dB (a first-order shelf from 800 Hz to 6.4 kHz); towards 1 the lows below 800 Hz fall the same way |
| 1 | Mix | 0–1 (1) | Dry to wet. At 0 the input passes through unchanged |
| 2 | Bias | −1 to +1 (0) | An offset at the curve's input, in its units (Soft saturates at ±2.5): the clipping becomes uneven and even harmonics appear (−14.5 dB second harmonic at ±0.5, Drive 12) |
| 2 | Gate | 0–1 (0) | A dead zone at the curve's input, ±0.5 at 1, after Drive: what stays inside comes out silent, what passes is shifted towards zero. Crossover distortion on every Type, a sputtering, starved fuzz on decays. Being after Drive, more Drive opens it |
| 2 | Level | −24 to +12 dB (0) | The wet signal's gain |
| 2 | Auto | Off, On (On) | On divides the wet signal by what the curve does to a reference sine's level (0.5 peak), so Drive changes the character and not the loudness |

Drive and Level are in decibels: `FM1_UNIT_DB` since engine API v3
(2026-10-05), `none` before.

- **The path:** input guard (NaN reads as 0, ±16 clamp, as the Mutable
  effects) → pre-emphasis (Tape) → × Drive → dead zone (Gate) → + Bias →
  curve, anti-aliased → minus the same of silence → de-emphasis (Tape) → DC
  blocker (10 Hz) → tilt (Tone) → × Level × Auto → Mix. Subtracting the
  shaper of silence, computed by the same code on the same values, makes
  silence in exact silence out at any setting, and keeps moving Bias, Gate
  or Type from stepping the output [verified: tests/test_engines_drive.py].
- **The curves.** Each Type is a C2 piecewise quintic, Hermite between
  knots where its value, slope and curvature are given, and constant beyond
  its outer knots. `python -m tests.test_engines_drive` generates the
  coefficient table from the knots, and the tests check the source against
  them, the continuity, and that no curve ever falls [verified]:

  | Type | Knots: value (slope, curvature) | Character |
  | --- | --- | --- |
  | Soft | −1 at −2.5, 0 at 0 (slope 1), +1 at +2.5 | tanh-like, within 0.047 of tanh; odd harmonics only |
  | Tube | −0.8 at −1.6, 0 at 0 (slope 1, curvature 0.3), +1 at +2.2 | uneven: a second harmonic at every level (−27 dB at Drive 12), the negative side compressing earlier and lower [inferred: the usual reading of triode curves; no circuit model] |
  | Diode | linear to ±0.6, then ±1 at ±1.35 | a hard knee, as a pair of diodes to ground; capped, where a real pair keeps rising logarithmically [inferred] |
  | Fuzz | a hard clip at ±1 (corners, C0) | with its own offset of 0.25 (asymmetric: −19 dB second harmonic at Drive 12) and dead zone of 0.04 (gated), added to Bias and Gate |
  | Tape | Soft at twice the scale: ±2 at ±5 | 6 dB more headroom, inside a first-order pre-emphasis (+12 dB above 3.2 kHz, the 50 µs record time constant) and its exact inverse after |

- **Tape's emphasis:** quiet signals pass flat, loud highs saturate first
  and come out softened [reported: tape's record and replay equalisation;
  no code taken]. Measured on sines, Auto off: at 0.05 and −12 dB Tape
  equals Soft at 200 Hz and at 5 kHz within 0.005 dB; at 0.5 and +24 dB
  Soft's 5 kHz comes out 0.2 dB under its 200 Hz and Tape's 10.5 dB under
  [verified: `fm1-drive-test`]. For the other Types the emphasis amount is
  0 and both filters are exactly the identity; it glides in and out with a
  change of Type.
- **Anti-aliasing: first-order ADAA for every Type.** Each output is the
  mean of the shaper (dead zone, offset and curve together) over the
  segment from the previous input to this one. For a piecewise polynomial
  the mean needs no division by a small step: within a piece, in local
  coordinates, the mean of tᵏ over [a, b] is h₍ₖ₊₁₎(a, b)/(k + 1), with
  hₙ = (bⁿ − aⁿ)/(b − a) computed by the recurrence hₙ = s·hₙ₋₁ − p·hₙ₋₂
  (s = a + b, p = ab), and across pieces the means are weighted by length.
  No epsilon, no fallback; a step of zero gives the curve itself. Against
  Simpson's rule in double, 3,000 random steps per Type from 0.01 to 30
  wide and steps of 10⁻⁶ to 10⁻³ at the knots are within 1.4·10⁻⁶ [verified].
  The price is Fold's: a half-sample delay and −0.6 dB at 5 kHz, −3 dB at
  11 kHz on the wet path.

  Aliases of a 0.5 sine against its fundamental, ADAA against the same
  path with the curve applied plainly per sample [verified:
  `fm1-drive-test`, 2026-10-02]:

  | | Below 5 kHz | Whole band |
  | --- | --- | --- |
  | All 26 cases that alias above −120 dB (five Types; 440 and 1,760 Hz; Drive 12, 24, 36 dB) | 20.6–29.3 dB lower | 4.8–10.5 dB lower |
  | Fuzz, Drive 24, 440 Hz | −76.3 against −51.4 dB | −49.4 against −42.4 dB |
  | Worst: any Type, Drive 36, 1,760 Hz | −47.6 to −51.3 dB, against −22.0 to −24.5 | −23.9 to −29.6, against −15.8 to −19.1 |
  | Soft, Drive 24, 440 Hz | −130.1 against −106.4 dB | −88.7 against −83.5 dB |

  ADAA averages over one sample, so it removes little of what folds to just
  under Nyquist. **2x oversampling was measured and not taken** [verified:
  scratch build, the shaper alone between near-ideal 255-tap filters, the
  19 cases at Drive 24 and 36 dB that alias above −120 dB]: against the
  plain curve at the host rate, the plain curve at 2x lowers the aliases
  below 5 kHz by 7.5–37 dB and across the band by 11–46 dB; ADAA at 2x by
  40–71 and 28–60 dB (ADAA at 1x: 21–26 and 5–8). With the resampler's own pieces (its
  123-tap decimating low-pass and a matching interpolator) it would cost
  about 185 multiply-adds per sample and channel plus a second curve
  evaluation, about three times Drive's whole cost, and the filters' delay
  would have to be the same for every Type to keep the crossfade and Mix
  clean [inferred]. The choice is the same for all five Types because
  ADAA's gain is: 21–29 dB below 5 kHz whatever the curve. A short
  half-band pair could make 2x affordable; that is a candidate for later,
  after listening on the dev board.
- **Auto:** the wet signal is divided by the reference sine's level over
  the AC level the static shaper makes of it, a 64-point quadrature (16
  values of |sin| at four phases each), clamped to −36…+18 dB and computed
  when a parameter changes, at the next block. From Drive −12 to +36 dB the
  renderer's 440 Hz sine comes out within 0.1 dB of its own level on Soft,
  Tube, Diode and Fuzz, and within 1.6 dB on Tape, whose de-emphasis
  lowers the harmonics the curve makes, which a static quadrature does not
  see. Off, Drive raises the level by up to 8.5 dB [verified:
  tests/test_engines_drive.py].
- **Glide and switching:** every control moves to a new value over about
  5 ms, sample by sample, so the output does not depend on the block size
  (1, 7 and 64 frames give the same bytes, every Type); values set before
  the first block apply from its first sample. A Type change crossfades
  the two curves over 5 ms (both evaluated on the same input): on a sine at
  Drive 24 the largest step between samples at a change is no larger than
  in steady playing (0.190 against 0.196), where switching at once would
  make 0.435 [verified: `fm1-drive-test`]. Type and Auto take locks and
  modulation (rounded): switched every third block, faster than the
  crossfade, they step the output no more than holding either value does
  [verified: tests/test_engines_fx_switches.py]. Filter states below 10⁻²⁰
  flush to zero.
- **Determinism:** no libm beyond `floorf`, `fabsf` and `sqrtf`, which IEEE
  754 defines exactly; 2^x, sine and cosine for the controls are
  polynomials in the file. A `#pragma STDC FP_CONTRACT OFF` keeps clang
  from fusing multiply-adds, which Apple clang otherwise does (96 fused
  operations in this file; Fold has 64) [verified: `objdump`]; GCC ignores
  the pragma, so a GCC build for a target with a fused instruction needs
  docs/14's `-ffp-contract=off`. `fm1-drive-test
  hash`, the bits of 2 s of output per Type with every parameter moving,
  is the same from Apple clang on arm64, GCC 12 on x86-64 and GCC 12 at
  `-m32 -msse2 -mfpmath=sse` [verified, 2026-10-02], and with Type and
  Auto turned every third block the same again, and from Emscripten 6.0.10
  under Node [verified, 2026-10-02]; x87 arithmetic
  (`-m32` alone) differs, as its excess precision does everywhere. JieLi's
  clang 4.0.1 compiles the file for pi32v2 without a warning at `-O2` and
  `-Oz`, with identical code at `-ffp-contract=off` and `=fast` [verified].
- **Memory and cost:** 240 bytes per instance on x86-64, i386 and pi32v2
  (the struct is 232, no pointers) [verified: fm1-render's `fx_bytes`, CI's
  i386 flags, JieLi clang]; 4.9 KB of code and 1.3 KB of tables on pi32v2
  [verified: section sizes at `-O2`]. Per sample and channel: the guard,
  two one-pole filters for the emphasis, one piece of a curve (two short
  searches and about 25 operations; up to three pieces and one divide when
  a step crosses knots or the dead zone's edges), the DC blocker, the tilt
  and the mix, about 75 operations: about 10,000 per 64-frame stereo block,
  twice the curve work during a Type crossfade [inferred]. On the desktop
  (Apple M1 Max, noise in) a block takes 2.6 µs at the defaults (0.18 % of
  the 1.451 ms block; Fold 1.8 µs), 3.8–4.3 µs at Drive 30 with Bias and
  Gate, and 5.5 µs while switching Type every 8 blocks [verified:
  `fm1-render`'s `ns_per_block` and `fm1-drive-test bench`].
- fm1-render sets an effect's parameters only before the first block, so
  `build/fm1-drive-test` (`test/drive_test.cc`, which includes the effect's
  source to reach its curves) drives Drive directly: every parameter
  changed mid-stream to any value, NaN and infinities included, between
  blocks of 1–64 frames; the glide and the crossfade; silence while Type,
  Drive, Bias and Gate move; the anti-aliased mean against quadrature;
  aliasing against a plain curve; the emphasis; and the host rates it
  accepts (8–384 kHz).

## Echo

A stereo ping-pong delay written here (`src/fx_echo.cc`, MIT). It shares no
code with anything vendored. Ideas credited in the source: the ping-pong
topology is the textbook one (Zölzer, *DAFX*), the slowing clock comes from
bucket-brigade echoes, and the 16-bit truncating delay word is the format of
Emilie Gillet's FxEngine in Rings and Clouds.

| Page | Parameter | Range | Default | What it does |
| --- | --- | --- | --- | --- |
| 1 | Time | 10–1,000 | 300 | Delay in milliseconds. Turning it glides the delay over about 0.1 s, so what is in the line bends in pitch, as on a tape echo |
| 1 | Feedback | 0–1 | 0.4 | Loop gain: 1 is 0.95, never 1 or more |
| 1 | Ping-pong | 0–1 | 1 | 0: two straight delays, one per side. 1: the mono sum enters the left line and each line feeds the other, so the repeats go left, right, left. In between, both crossfade |
| 1 | Mix | 0–1 | 0.35 | Dry at full level up to 0.5, echoes at full level from 0.5. Mix 0 passes the input through bit for bit |
| 2 | Tone | 0–1 | 0.6 | Low-pass inside the loop, 400 Hz at 0 rising six octaves to 1. The first echo is undamped; each repeat is filtered once more |
| 2 | Wow | 0–1 | 0.1 | Slow modulation of the delay, up to ±3 ms: a 0.55 Hz sine plus a smoothed random walk from a fixed seed, so renders stay deterministic. About ±20 cents at 1 |
| 2 | Level | 0–1 | 1 | How much of the input enters the echo. Turn it down to let the echoes ring out while new playing stays dry |

How it works [verified: tests/test_engines_echo.py and
`build/fm1-echo-selftest`, 2026-10-02, unless marked]:

- **Memory:** 16,384 cells per side of 16-bit words (64 KiB), plus 208 bytes
  of state (192 before Tone's SMOOTH ramp): 65,744 bytes, whatever the host
  rate. The 32-bit figure equals the 64-bit one because the instance holds
  no pointers [inferred; CI's 32-bit job reports it]. The words hold ±2.0, 6 dB of headroom over full
  scale. A soft clip before the store is linear up to ±1 and bends towards
  ±2.
- **Time beyond the line:** up to 16,380 cells (371 ms at 44,118 Hz) the line
  runs at the host rate, and the echo lands within 0.02 samples of Time.
  Beyond that the cell count stays fixed and the line's clock slows, as in a
  bucket-brigade delay. At 1,000 ms the cells run at 16.4 kHz. Two one-pole
  low-passes in series on the way in, and two on the way out, with their
  cutoff tied to the clock, limit the aliasing. Long echoes keep their level (a 440 Hz sine
  -0.19 dB at 1,000 ms) but lose their highs, and land up to 0.13 ms late.
- **Stability:** every element of the loop is a convex combination (linear
  interpolation, the one-pole filters, the cross-feed), so none gains above
  1, and the loop gain is at most 0.95. Interpolation is linear, not
  all-pass or cubic, because it has no feedback of its own and never exceeds
  its inputs under any modulation. Maximum feedback on ten seconds of noise
  peaks at 1.42 at most and settles (at 10 and 372 ms; a 1,000 ms loop is
  still filling after ten passes).
- **Silence:** the store truncates towards zero, so no small signal can
  recirculate for ever (there is no dead band). With the input silent, the
  line decays to exact zeros (1.3 s at 10 ms and full feedback, after
  full-scale noise). The float filter states are flushed below 1e-15, so no
  subnormal is left in the loop or the output.
- **Contracts:** the input guard of `mi_fx.cc` (NaN to 0, clamp to ±16, dry
  path included). Parameters go through `fm1_param_clamp`. Gains glide over
  5 ms against zipper noise. Before the first render every glide snaps, so
  parameters set at load apply from the first sample. Rendering is per
  sample, so any block size gives the same output. The selftest turns every
  parameter to any value, NaN and infinities included, hundreds of times
  while bad input is mixed in. It sweeps Time end to end every 20 ms at
  three host rates, and refuses host rates outside 1 kHz–1 MHz.
- **Cost, desktop only:** about 2.2 µs per 64-frame block on an M1 Max, 0.15 %
  of the block, against Plate's 0.06 %. Stage B measures pi32v2.
- **Not yet:** tempo sync, which waits for the host to expose tempo, and a
  reset call to drop the tail without re-creating the 64 KiB instance (the
  host feature listed below).

## Filter

A multimode filter (`src/fx_filter.cc`, our own code, MIT) with six
types, every one of whose parameters is a modulation target. No code is
taken from anywhere; the designs are credited below and in the source.
Stereo in, stereo out. Comb was its seventh type until 2026-10-05 and is an
effect of its own now ([Comb](#comb)): its delay lines made every Filter
18 KB. Formant moved from Type 6 to 5; nothing had been released, so
nothing is migrated, and every other type renders byte for byte as before
[verified: `tests/fixtures/comb-split.json`].

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Type | SVF, Ladder, Diode, Sallen-Key, SK Mixed, Formant (Ladder) | The filter. A change starts the new type from rest, unheard, with its input faded in over 5 ms, then crossfades into it over 5 ms more |
| 1 | Cutoff | 20 Hz–18 kHz, LOG (2 kHz) | The corner, or the resonance: where each type self-oscillates. Never above 0.45 of the host rate (3.6 kHz at 8 kHz). Moves in ratios: a detent is 1.2 semitones, and a route moves it in octaves ([LOG](#the-log-law)) |
| 1 | Resonance | 0–1 (0.25) | Up to self-oscillation for SVF, Ladder, Diode, Sallen-Key and SK Mixed (from about 0.93–0.96); Formant's bandwidth |
| 1 | Drive | 0–1 (0) | Input gain 1× to 16× into the filter's saturating curves, output down by its square root: quiet signals up to 12 dB louder, loud ones saturate |
| 2 | Mode | 0–3, continuous (0) | Per type, below; between whole numbers the two neighbours are blended |
| 2 | Morph | 0–1 (0) | Spread for the five analogue-style types (left channel up to an octave down, right up); the vowel for Formant |
| 2 | Mix | 0–1 (1) | Dry to wet. At 0 the input passes through unchanged |
| 2 | Level | 0–2 (1) | The wet signal's gain |

| Type | After | Mode 0 / 1 / 2 / 3 | Notes |
| --- | --- | --- | --- |
| SVF | Andrew Simper's (Cytomic) trapezoidal state-variable filter | low-pass / band-pass / high-pass / notch | Linear but for its self-oscillation: the damping goes slightly negative at the top of Resonance and an energy term (bp² + lp², last sample) holds the oscillation at a fixed, sinusoidal level |
| Ladder | the transistor ladder (Huovilainen, DAFx-04; Zavalishin ch. 5) | 24 / 18 / 12 / 6 dB/octave (taps on the 4th to the 1st stage) | One saturating curve where the feedback meets the input. Self-oscillates from k = 4 |
| Diode | a TB-303-style diode ladder: four coupled capacitors, written here from the node equations | as Ladder | The coupled stages make a tridiagonal system. Analysed here: it oscillates at k = 18.39 and 1.195× its integrators' frequency, and with no feedback it is already −3 dB at 0.119× [verified: tests and a numerical scan]. Its tuning follows a fitted curve between the two, so Cutoff is near −3 dB with no resonance and the pitch at full resonance |
| Sallen-Key | a Sallen-Key low-pass with positive feedback through a one-pole high-pass, after the Korg-35 filter of the later Korg MS-20 (Zavalishin ch. 5; Will Pirkle's application note on the Korg35) | low-pass / band-pass / high-pass / notch | H = 1/(s² + (2 − k)s + 1); the feedback through the saturating curve. Self-oscillates from k = 2 |
| SK Mixed | a mixed-input Sallen-Key: an equal-component Sallen-Key whose inputs, not outputs, are mixed, after the Steiner-Parker Synthacon filter | low-pass in / band-pass in / high-pass in / notch (L, −2B, H) | y (s² + (3 − K)s + 1) = L + sB + (s² + 2s)H, from its node equations (written here), so its high-pass input has a 6 dB/octave skirt below the corner. Both resistors are diodes, whose current saturates, and the feedback passes an asymmetric clip |
| Formant | three band-passes at the first three formants of A, E, I, O, U | voice: men 0, women 1.5, children 3 | Formant frequencies from Peterson and Barney (JASA 24, 1952, Table II, averages for the vowels of hod, head, heed, hawed and who'd) [reported]. Morph sweeps A–E–I–O–U; Cutoff shifts every formant by half its distance from 1 kHz, in octaves; Resonance narrows them |

How it works:

- **Zero-delay feedback** (Zavalishin, *The Art of VA Filter Design*,
  rev. 2): trapezoidal integrators, the bilinear transform's frequency
  prewarped so the resonance lands on Cutoff. A saturating curve inside a
  loop is replaced by its secant gain (curve ÷ input) at the previous
  sample's operating point, the loop is solved as a linear system, and the
  true curve is then applied once to the solution, so every state stays
  bounded however hard the loop is driven (the "cheap non-linear
  zero-delay filter" Teemu Voipio published on the KVR forum, 2012
  [reported]). SVF, Ladder and Diode solve once per sample. Sallen-Key and
  SK Mixed take the secant again at that first solution and solve a second
  time: a fixed single refinement, never a convergence loop. Without it
  Sallen-Key's self-oscillation drifted 16 cents sharp at 5 kHz and SK
  Mixed's up to a semitone [verified].
- **The curve** is v − v³/6.75 up to |v| = 1.5, where it reaches ±1 with
  zero slope: no divide below its knee.
- **Resonance compensation.** Ladder and Diode lose bass as their feedback
  rises (DC gain 1/(1 + k)), so their input, and Diode's output, rise with
  k. The others keep their pass band and their output falls as the peak
  grows. Near self-oscillation the Ladder and Diode taps above the 4th
  stage are scaled down, since they swing further than it. At Resonance 0.9
  and Cutoff 2 kHz the pass band sits 4.3 dB (Ladder) to 7.4 dB (SVF) down;
  self-oscillation peaks at 0.35–0.65 (−9 to −4 dBFS) on every type and
  Mode, the notches excepted, which cancel it [verified].
- **Measured** [verified: tests/test_engines_filter.py, 2026-10-02]:
  - SVF at Resonance 0 is a Butterworth: −3.01 dB at Cutoff (at 8, 44.1,
    96 and 384 kHz alike), 12 dB/octave; the notch is −118 dB deep.
  - Ladder at Resonance 0: −3.01 dB per pole at Cutoff, and 6.0, 12.0,
    18.0 and 24.0 dB/octave on the four taps.
  - Sallen-Key and SK Mixed at Resonance 0: −6.02 and −9.54 dB at Cutoff
    (two coincident poles; Sallen-Key Q 1/3). SK Mixed's high-pass input
    falls 5.7 dB per octave below its corner, Sallen-Key's high-pass 11.7.
  - Self-oscillation, over 110 Hz–5 kHz at 44,118 Hz and at 440 Hz at
    8, 96 and 384 kHz: SVF within 0.01 cent of Cutoff, Ladder and Diode
    within 1, Sallen-Key within 2.5; SK Mixed a steady 19–23 cents flat
    (its diodes load the oscillation). None oscillates at Resonance 0.85.
  - Formant: at a vowel's formants the gain is 8–33 dB above that at the
    other vowel's.
  - Drive 1 raises the 3rd harmonic of a 0.5 sine from −62 to −112 dB
    (Drive 0) to −10 to −27 dB. SK Mixed makes a 2nd harmonic (−64 dB at
    Drive 0) where Sallen-Key makes none, and a louder input darkens it
    (2 kHz falls 2 dB further than 250 Hz) where Sallen-Key's tilt holds.
- **Type changes.** The new type starts from rest, runs unheard for 5 ms
  with its input faded in from silence, and only then is crossfaded in over
  5 ms, both types running throughout. A type started from rest rings up
  (a resonance) or, as Comb did, arrives late (a first echo, a delay after
  it starts): faded straight in, as before 2026-10-02, that start was heard
  and stepped the output by up to 24 times the crossfade's own allowance
  when Type was turned every few blocks (30 random settings, the method of
  tests/test_engines_fx_switches.py, on the old build); with its input
  faded in it swells instead, and is mostly over before it is heard (130
  random settings within the allowance) [verified, 2026-10-02]. Across all 30 ordered
  pairs (42 with Comb), a 440 Hz sine's largest step between neighbouring samples at a
  switch is at most 0.9 % above either type's own (4 % before) [verified:
  `fm1-filter-test`]. A change asked for meanwhile waits for the crossfade
  to end, so a change takes 10 ms to complete.
- **Glide and control rate:** Cutoff, Resonance, Drive, Mode and Morph
  glide (5 ms) and the coefficients follow every 8 samples, counted from
  `create`, so any block size gives the same output. Mix and Level glide
  every sample. Values set before the first block apply from its first
  sample.
- **Determinism.** No libm anywhere in the effect: 2^x, log2 and tan are
  polynomials (tan in the file, 2^x and log2 in `src/fx_filter_dsp.h`,
  which it shares with Comb), beside fabsf, floorf and sqrtf, which IEEE 754
  rounds exactly. 24 renders (every type with every parameter moved, at full
  resonance and drive from an impulse, at 96 kHz, two chains of two filters
  after Macro, host blocks of 7) are byte-identical from GCC with glibc,
  GCC with musl and Emscripten under Node [verified: containers on the LAN
  build host, 2026-10-02]. A `#pragma STDC FP_CONTRACT OFF` keeps clang from
  fusing multiply-adds (Apple clang fused 218 operations in this file before
  the review added it, 2026-10-02 [verified: `objdump`]), so the Mac's
  native build computes the same bits too [verified: a hash of the output
  bits of every type with its parameters moving, Apple clang arm64 against
  GCC 12 x86-64 and i686 with SSE, 2026-10-02]. With Type turned every
  third block (the warm-up and the input fade), the same again, and the
  same from Emscripten 6.0.10 under Node [verified, 2026-10-02].
- **Contracts:** the input guard of `mi_fx.cc`; `fm1_param_clamp`; every
  field set in `create`; silence in gives exact silence out from rest at any
  setting, self-oscillating ones included; tails flush to exact zero within
  0.2 s (states below 1e-15 flush, so no subnormals). Host rates 8–384 kHz;
  10 s of random parameter changes (NaN and infinities included) and noise
  bursts at the guard's limit stay finite at 8, 44.1, 96 and 384 kHz, and
  every type at Resonance 1, Drive 1 and Level 2 under that noise stays
  below 2.0 [verified].
- **Memory:** 656 bytes at any rate, the same on i386, since the instance
  holds no pointers [verified: `fm1-filter-test`, and GCC −m32 in a
  container]. It was 18,368 at 44,118 Hz with Comb's two delay lines, 688
  of them state.
- **Cost** per 64-frame stereo block on the desktop (Apple M1 Max, best of
  seven, noise in), against Plate's 0.89 µs and Fold's 1.8 µs in the same
  runs: Comb (then a type) 0.8, Formant 0.9, SVF 1.4, Ladder 2.2, Diode 2.4, Sallen-Key
  3.2 and SK Mixed 3.6–4.8 µs; with Cutoff and Resonance moved twice a
  block and Spread on, up to 4.9 µs (SK Mixed), 0.34 % of the block
  [verified: `fm1-filter-test --bench` and `fm1-render`]. A Type change
  costs both types for 10 ms. By operation count, SK Mixed's worst case is
  about 1.4 Folds and the others less [inferred]; stage B measures pi32v2.
- **Names.** The types are named for their circuits, never for a maker, a
  person or a part number (owner, 2026-10-02): Sallen-Key and SK Mixed (a
  mixed-input Sallen-Key) were "K35" and "Steiner" until then. What each
  is after is credited above: Sallen-Key the Korg-35 filter of the later
  MS-20, SK Mixed the Steiner-Parker Synthacon's, Diode the TB-303's diode
  ladder, Ladder the transistor ladder. Neither M-VAVE nor any synth maker
  is involved. The uids did not change, so locks and routes on Type keep
  their meaning.
- **Type's flags: MOD.** Since a change warms the new type up and
  crossfades, nothing is cut: the sequencer may lock it and a modulation
  route may step it (rounded), however fast. Turned every third block,
  faster than a change completes, it steps the output no more than holding
  any type does [verified: tests/test_engines_fx_switches.py]. NOLOCK (a
  destructive change) and LATCH (read at note-on; an effect has none) would
  both misdescribe it (the ENUM table below).
- `build/fm1-filter-test` (`test/filter_test.cc`) drives Filter, and Comb
  as the type `comb`, where fm1-render cannot: changes mid-stream, the
  crossfade, host rates, sine sweeps and self-oscillation. `--gain` and
  `--osc` print one measurement; `--bench` the cost.

## Comb

A comb filter (`src/fx_comb.cc`, our own code, MIT): Zölzer's universal
comb (*DAFX*, ch. 2), one delay line of fs / Cutoff samples read with linear
interpolation, with feedback and feedforward, its loop through the Filter's
saturating curve. It was the Filter's seventh type until 2026-10-05 (owner's
decision; notes/2026-10-02-filters-dynamics-options.md, FD0), and keeps that
type's code, parameters and memory: it renders what a Filter set to Comb
from its first block rendered, sample for sample [verified:
`tests/test_engines_comb.py` against renders pinned at main `d538f1e`,
`tests/fixtures/comb-split.json`]. Stereo in, stereo out.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Cutoff | 20 Hz–18 kHz, LOG (2 kHz) | The comb's pitch: the delay is fs / Cutoff, at least 2.22 samples |
| 1 | Resonance | 0–1 (0.25) | The loop gain, 0.25–0.98 |
| 1 | Drive | 0–1 (0) | As the Filter's: input 1× to 16× into the loop's curve, output down by its square root |
| 2 | Mode | 0–3, continuous (0) | Feedback (peaks) at 0 to feedforward (notches) at 3, blended between |
| 2 | Morph | 0–1 (0) | The polarity: 0 positive (peaks at multiples of Cutoff), 0.5 none, 1 negative (odd multiples of Cutoff/2: an octave lower, hollow) |
| 2 | Mix | 0–1 (1) | Dry to wet |
| 2 | Level | 0–2 (1) | The wet signal's gain |

- **Uids.** The Filter's, for the same parameters (Cutoff 2 … Level 8), so a
  Filter that was set to Comb maps onto Comb uid for uid and value for value
  (its Type, uid 1, dropped). Uid 1 is retired in Comb
  (`tests/fixtures/param-uids.json`), so it can never mean anything else.
  The names stay the Filter's for the same reason; Mode and Morph keep
  their 0–3 and 0–1 ranges.
- **Measured** [verified: tests/test_engines_filter.py, which drives it
  through `fm1-filter-test`]: peaks 21 dB above its troughs at Resonance
  0.8; feedforward notches −34 dB at Resonance 1; tails flush to exact
  silence in 0.03 s; at Resonance 1, Drive 1 and Level 2 under noise at the
  guard's limit it stays below 2.0.
- **Glide, determinism, contracts:** the Filter's (above): the controls
  glide every 8 samples counted from `create`, the delay moves sample by
  sample between those steps, no libm (`src/fx_filter_dsp.h`), no fused
  multiply-adds, the input guard, NaN-safe parameters, silence in gives
  silence out.
- **Memory:** 160 bytes of state plus two delay lines of fs/20 Hz + 4
  floats: 17,840 bytes at 44,118 Hz (3,392 at 8 kHz, 153,792 at 384 kHz),
  the same on i386. The lines are never cleared: `create` marks them empty,
  and reads beyond what was written since return 0.
- **Cost:** as the Filter's Comb type, 0.8 µs per 64-frame block on the
  desktop [verified: `fm1-filter-test --bench`].

## Comp

A feed-forward compressor written here (`src/fx_comp.cc`, MIT). The design
is the one laid out by Giannoulis, Massberg and Reiss, "Digital Dynamic
Range Compressor Design — A Tutorial and Analysis" (*JAES* 60(6), 2012)
[reported: the paper]: a static curve with a quadratic soft knee, its
reduction smoothed in dB by one-pole "branching" or "decoupled" stages, and
automatic makeup from the curve. No code is taken from anywhere; the
Airwindows compressors (MIT) were not used. Stereo-linked: one detector
reads the louder channel at each frame, and both channels get one gain.

    guard -> level (peak or RMS, the louder channel) -> dB -> curve -> smoothing in dB
          -> [Auto Gain: a frame its lift would take over 0 dBFS gives back what it must]
          -> gain = Makeup (+ Auto Gain's) - reduction;   out = dry x (1 - Mix) + dry x gain x Mix

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Threshold | −60 to 0 dB (−18) | Where the reduction starts: the middle of the knee |
| 1 | Ratio | 1–21 (4) | 1:1 (nothing) to 20:1 above the knee: slope S = 1 − 1/Ratio. From 20 to 21 the slope goes on from 0.95 to 1, so 21 is ∞:1, a limiter's flat line |
| 1 | Attack | 0–100 ms (10) | The time constant of the reduction rising: with Peak, 63 % of a step after Attack. 0 is instant |
| 1 | Release | 10–2,000 ms (150) | The time constant of it falling back |
| 2 | Knee | 0–24 dB (6) | The soft knee's width around Threshold, a quadratic blend from no reduction into the slope. 0 is a hard corner |
| 2 | Makeup | −12 to +24 dB (0) | Gain after the reduction. With Auto Gain, a trim on the automatic makeup |
| 2 | Mix | 0–1 (1) | Parallel compression: dry × (1 − Mix) + compressed × Mix. 0 is the input bit for bit, 1 the compressed signal exactly |
| 2 | Character | Peak, RMS, Glue, Punch (Peak) | Presets of detector and curve (below) |
| 3 | Auto Rel | Off, On (Off) | Programme-dependent release (below) |
| 3 | Auto Gain | Off, On (Off) | Adds the curve's reduction at 0 dBFS to Makeup, at most 24 dB, so a steady full-scale signal stays at full scale (22.5 dB at −30 dB and 4:1), and keeps every input at or under 0 dBFS at or under 0 dBFS, onsets included, touching only the samples it would otherwise take over (below) |

| Character | Detector | Smoothing | Curve |
| --- | --- | --- | --- |
| Peak | peak, max(\|L\|, \|R\|) | one stage: Attack rising, Release falling | as set |
| RMS | RMS over 10 ms | as Peak | as set |
| Glue | RMS over 30 ms | decoupled: the first stage catches at once and falls by Release, the second follows it both ways by Attack, so recovery is rounder and slower | Knee + 6 dB |
| Punch | peak | two attack stages of Attack / 2 in series: the reduction starts with zero slope, so the front of a hit passes, and reaches 63 % at 1.07 × Attack; Release as set | as set |

- **Level.** As power: the peak squared, or a one-pole mean of 2 max(L²,
  R²). The factor 2 calibrates RMS to a sine, so a sine reads its peak level
  in both detectors: on the renderer's sine RMS and Glue sit within 0.05 dB
  of the curve, as Peak does with Attack 0. In dB, 10 log10 of the power,
  floored at −200 dB.
- **The curve:** d = level − Threshold, W = Knee; no reduction for 2d ≤ −W,
  S·d for 2d ≥ W, and S·(d + W/2)²/(2W) between (the paper's soft-knee
  gain computer), continuous at both ends.
- **Auto Rel.** A slow envelope with Release as its time constant follows
  the first stage, which then releases five times faster, and the larger of
  the two applies. After a short peak the reduction lets go quickly; after
  long compression, slowly. One more one-pole per frame.
- **Auto Gain** (redesigned 2026-10-02, at the owner's request: "cap it to
  something sensible; ideally real auto-gain would avoid clipping"). Two
  parts:
  - *The makeup* is A = the curve's reduction at 0 dBFS, capped at 24 dB,
    the manual Makeup's top. Uncapped, Threshold −60 dB at 21:1 asked for
    60 dB, and with Makeup's own 24 a total of 84. Now a full-scale steady
    sine comes out at full scale when the curve asks for 24 dB or less
    (−0.06 dBFS at −20 dB and 4:1: RMS's ripple and the margin below), and
    24 dB under the curve's reduction when it asks for more (−36.08 dBFS at
    −60 dB and 21:1) [verified: `fm1-comp-test`].
  - *The bound* (loosened 2026-10-05, owner: "touch only would-be
    overs"). With the lift L in force (A, or A x Auto Gain's share while it
    glides), a frame comes out at xp + L + M − r dB, xp being its peak
    (the louder channel's |sample|), r the smoothed reduction and M the
    Makeup knob, counted only while it cuts (a boost is the player's own
    lift, below; a cut keeps samples under full scale, so it counts:
    review 2026-10-06, when it did not, Makeup −6 dB made the bound clip a
    steady −3 dBFS sine's peaks at −6 dBFS). Only if that would pass 0 dBFS
    (less a margin of 10⁻⁴ dB for float rounding) does the bound act, and then on that frame
    alone: the reduction applied rises by just enough to bring it to the
    margin under 0 dBFS, by at most L (and the margin). So an input at or
    under 0 dBFS comes out at or under 0 dBFS (with Makeup at or under
    0 dB; a positive Makeup lifts that by itself), and a louder input no
    louder than with Auto Gain off. Before the bound (until 2026-10-02) an
    onset met the full makeup before the reduction caught up: the
    renderer's sine at Threshold −24 dB, 21:1 and Attack 100 ms came out at
    +18 dBFS; now at 0 dBFS at most [verified:
    tests/test_engines_comp.py].
  - *What the bound does to the sound.* Everything that stays under full
    scale is untouched: a frame the same makeup set by hand keeps under
    0.99998 comes out with Auto Gain on in the same bits, steady tones
    included [verified: `fm1-comp-test`'s `loose`, 744 renders at six
    settings, two with Makeup cut, every Character: 504 steady sines from
    −40 to −3 dBFS, 60 Hz–3 kHz, and the ten hostile signals; no untouched
    frame differs, and the 492 sines whose settled peak stays under full
    scale are the same bits from 100 ms on, 2026-10-06]. Where it acts it clips those frames at the
    margin: the overs of an onset, for about the Attack time, and the tips
    of a loud tone the detectors read under its peaks. From 2026-10-02 to
    2026-10-05 it held every frame to the curve's gain at its own peak,
    which rounded the peaks of steady tones too (24–28 dB down on a sine
    with Peak and Punch); that is gone. For clean onsets with Auto Gain,
    use a short Attack; for a clean ceiling with lookahead, the Limiter.
  - *Mix and Character keep it.* Every Character's reduction passes the
    bound, including while it hands over. Parallel Mix adds the dry signal,
    which is within 0 dBFS when the input is, and has the same sign as the
    compressed one: the output stays within (1 − Mix) + Mix ×
    10^(Makeup/20), so within 0 dBFS. On a grid of 144 extreme settings
    (Threshold −60 dB, 21:1, no knee; every Attack, Release, Character, Auto
    Rel and Mix), 128 at the tight corner (the curve asking for no more than
    the cap, so the bound alone holds a full-scale input at full scale:
    −24 dB at 21:1 with no knee, and 0 dBFS on a gentler slope and inside a
    knee; half of them with Auto Gain switched) and 160 random ones, a
    quarter of them with Auto Gain switched every third block, over
    full-scale squares (50 Hz, 1 kHz, Nyquist), impulses on silence and on
    a quiet bed, burst onsets, full-scale noise, DC steps, one channel loud
    and one quiet, and a swell through the knee, nothing passes it; the
    tight corner reaches 0.999989 of full scale, the margin [verified:
    `fm1-comp-test`'s `autogain`, 2026-10-05].
  - *Switching it* glides its share w, and with it L and the bound, in and
    out together over 5 ms. The bound only ever takes back the part of the
    lift in force, so it holds part-way, and at w = 0 it is not computed.
  - *Auto Gain off is unchanged:* the static curve, the time constants and
    every output bit (108 renders of three inputs at 36 settings, with and
    without changes mid-stream, byte-identical before and after
    [verified, 2026-10-02]; the two Auto-Gain-off hashes below did not
    move, then or when the bound was loosened on 2026-10-05).
- **No libm.** The logarithm and the exponential are polynomials written
  here (`src/fx_comp_math.h`): log2 within 2.1 ulp of its result (1.9e-7
  on [1/16, 16]: under 1e-6 dB near 0 dBFS), exp2 within 2.4e-7 relative.
  Everything else is +, −, ×, ÷ and comparisons, and floating-point
  contraction is off for the file under clang (`#pragma STDC FP_CONTRACT
  OFF`). Without the pragma Apple clang's arm64 build fuses multiply-adds
  and its output differs.
- **Bit-identical across builds** [verified, 2026-10-02]: every float of
  three 2.9-second renders with parameters changed mid-stream hashes the same
  from Apple clang on arm64 (default and `-ffp-contract=off`), GCC on i386
  (SSE) and x86-64, and Emscripten 6.0.10's WebAssembly under Node
  (`fm1-comp-test`'s `hash`, pinned in tests/test_engines_comp.py, so CI's
  Linux, macOS and 32-bit jobs check it too). The first of the three runs
  with Auto Gain on and was pinned again for its redesign, after the same
  check on all four builds [verified, 2026-10-02], and again when its bound
  was loosened (2026-10-05; the browser's parity scenario
  `dyn3-round-autogain` checks the WebAssembly build). `-ffp-contract=fast` differs,
  as it must. With JieLi's clang for pi32v2
  the file compiles without a warning in four profiles (`-O2` with
  contraction off, on and fast, and `-Oz`), and `fast` emits the same code
  as `off` (nothing fused).
- **Measured** [verified: tests/test_engines_comp.py and
  `build/fm1-comp-test`, 2026-10-02]:
  - The static curve: 3,168 points (thresholds −40, −20 and 0 dB; ratios
    1–21; knees 0–24 dB; levels −60 to +20 dB) match the formula within
    4e-6 dB at the accessor and 8e-6 dB in the output.
  - Time constants on exact steps: Peak's attack and release within 1 % of
    the setting (2, 10, 50 and 50, 200, 1,000 ms); Punch's attack 1.073 ×.
    RMS and Glue add their averaging (RMS release on a step: 111, 266,
    1,123 ms; Glue 246, 383, 1,227 ms).
  - Auto Rel at Release 500 ms: 100 ms after a 10 ms burst, 603 ms after
    2 s of compression; Off: 500 ms after both.
  - A steady sine 24 dB over the threshold: the reduction ripples 0.02 dB
    (440 Hz) and 0.09 dB (100 Hz) with Peak, under 0.01 dB with RMS and
    Glue. Peak with a 10 ms attack catches only part of each peak and
    settles about 1 dB under the curve; with Attack 0 it sits on it.
  - Silence after loud noise: exact zeros out (18 dB of makeup and Auto
    Gain on), and the reduction falls without ever rising, to exactly 0.
  - Changing Character or Auto Rel mid-compression moved the reduction 8
    and 15 dB, at most 0.073 dB from one frame to the next: the step
    between the old smoothing and the new becomes an offset that decays in
    5 ms. Character, Auto Rel and Auto Gain switched every third block step
    the output no more than holding either value does [verified:
    tests/test_engines_fx_switches.py].
- **Contracts:** the input guard of `mi_fx.cc` (NaN to 0, clamp to ±16);
  parameters through `fm1_param_clamp`; Threshold, Ratio, Knee, Makeup, Mix,
  Auto Gain's share and the detector's crossfade glide over 5 ms, sample by
  sample, so any
  block size gives the same output; values set before the first render
  apply at once. Silence in is exact silence out. A fault does not latch: a
  second after it the output is the clean render's within one 16-bit step.
  States flush to zero (power below 1e-20, reductions below 1e-6 dB).
- **Memory:** 208 bytes on x86-64 and i386 [verified: GCC 12 in Linux
  containers, 2026-10-02], and so on pi32v2, since it holds no pointers
  [inferred; 192 before Auto Gain's redesign, verified then with JieLi's
  clang]. Code for pi32v2 before the redesign: 3.6 KB at `-O2`, 2.1 KB at
  `-Oz`, and 0.8 KB of constant data.
- **Cost:** about 75 operations, one divide (the logarithm) and one
  exponential per stereo frame; Auto Gain adds the curve once more, and
  for RMS and Glue a second logarithm (the bound needs the peak's level)
  [inferred: by count]. Desktop (Apple M1 Max, `fm1-comp-test --cost`,
  noise): 1.5 µs per 64-frame block with Peak, 2.0 µs with Glue, Auto Rel
  and Auto Gain (1.6 before the bound), 2.2 µs while a parameter glides:
  0.10–0.15 % of the 1.451 ms block, about Fold's [verified, 2026-10-02;
  the same with the loosened bound, 2026-10-05].
- **Gain reduction for modulation:** `fm1_comp_reduction_db(instance)`
  (`include/fm1_comp.h`) returns the smoothed reduction of the last frame,
  in dB (0 or more, finite, makeup not included). It is smoothed by Attack
  and Release, so a source reading it once per block or tick does not
  alias; Auto Gain's bound, which follows the waveform, is not in it. It is not part of `fm1_engine_t`: a host checks that the unit's
  engine is `comp` first. It is the REDUCTION output docs/16 §3.7 plans for
  Duck, here from a compressor in the chain rather than a tap.
- **Units.** Attack and Release are in ms. Threshold, Knee and Makeup are in
  dB, `FM1_UNIT_DB` since engine API v3 (2026-10-05; bare numbers before).
  Release moves on the LOG law ([below](#the-log-law)).
- **Not yet: sidechain.** The detector takes a level per frame, so a key
  signal only changes where that level comes from. The plan, in order: a
  high-pass on the detector's input, inside the effect (one more one-pole;
  stops low notes pumping the mix); then a key from elsewhere in the chain,
  which needs the host to hand an effect a second buffer. That is either
  docs/16 §3.7's audio tap, or an engine API addition (a key buffer next to
  `render`'s); neither exists yet. Lookahead, which needs a delay line, is
  not planned.

## Limiter

A look-ahead brickwall limiter (`src/fx_limit.cc`, our own code, MIT), for
the master or for one sound. Its gain path follows Geraint Luff's design
("Designing a straightforward limiter", Signalsmith Audio, 2022
[reported]): a moving minimum of the gain each frame needs, then moving
averages whose lengths add up to the minimum's window, ahead of a delay of
the same length. No code is taken from the article or from Signalsmith's
library. Mutable's stmlib has a `Limiter`, a peak follower with no
lookahead [verified: `third_party/mutable/stmlib/dsp/limiter.h`]; it is
not used. Mode Round (2026-10-05) ports the loop of Airwindows ClipOnly2
(Chris Johnson, MIT; `third_party/airwindows/`).

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Ceiling | −24 to 0 dB (−1) | The most the output reaches. In dB: `FM1_UNIT_DB` since engine API v3 |
| 1 | Drive | −12 to +24 dB (0) | Gain before the limiter: push a sound into it for loudness, or turn it down |
| 1 | Release | 1–1,000 ms (100) | How fast the gain comes back: the time constant of its recovery, after a hold as long as the lookahead |
| 1 | Lookahead | 0–5 ms (2) | How far ahead the gain sees peaks coming. It is also the effect's latency: 88 frames at 2 ms and 44,118 Hz. At 0 there is no delay, and a soft clip catches what the attack misses (below). A change crossfades to the new delay over 5 ms, each delay with its own gain, so it can be locked and modulated |
| 2 | Mode | Brickwall, Soft Clip, Round (Brickwall) | Brickwall: nothing above the ceiling, nothing changed below it. Soft Clip: peaks up to +12 dB over the ceiling are rounded off by a curve from 6 dB below it. Round: peaks up to +3 dB over the ceiling are replaced by ClipOnly2's interpolated values; everything under the ceiling passes untouched (below). A change glides the stage over 5 ms, frame by frame as the audio leaves the line (below), so it can be locked and modulated (rounded) |
| 2 | Link | 0–1 (1) | Stereo link. Each channel's detector takes the larger of its own peak and Link × the other's: at 1 one gain moves both channels, so the stereo image holds; at 0 each channel is limited on its own |
| 2 | Mix | 0–1 (1) | Blends the delayed dry input back in (parallel limiting). Below 1 the output can pass the ceiling, by design |

How it works [verified: tests/test_engines_limit.py and
`build/fm1-limit-test`, 2026-10-02, unless marked]:

- **The path:** input guard (NaN reads as 0, ±16 clamp, as the Mutable
  effects) → Drive → the lookahead line, and the detector: the gain each
  frame needs (Ceiling / peak, or 1), an envelope that follows a deeper
  need at once and recovers with Release → a minimum over the last D + 1
  frames → two box filters whose lengths add up to D → the gain for the
  frame leaving the line D frames later → the output stage → Mix.
- **Why it never passes the ceiling:** every value the boxes average at
  frame n is a minimum over a window that contains frame n − D, so their
  mean is never above the gain frame n − D needed, and that frame's audio
  is what leaves the line. The gain path is integer arithmetic: the
  envelope's gain is rounded down to 22 fractional bits, and the minimum
  and both sums are exact, so nothing drifts and a run of unity gains is
  exactly 1.0. A final clamp to ±Ceiling covers the last float rounding.
  On 11 hostile signals (full-scale square waves at 50 Hz, 1 kHz, 11 kHz
  and Nyquist, impulses up to ±16, full-scale and clamped noise, DC steps,
  onsets, a chirp) under 1,320 settings, in random host blocks, no output
  sample is above the ceiling, and before the clamp the envelope alone is
  at most 1.2 × 10⁻⁷ over (one float step). The ceiling is the effect's own
  float value of 10^(Ceiling/20), within 2 × 10⁻⁷ of it.
- **Transparent below the ceiling:** noise under the ceiling comes out bit
  for bit, delayed by the lookahead, in every mode (under the stage's knee
  at Lookahead 0 and in Soft Clip). After 0.3 s of limiting at +12 dB, with
  Release 50 ms, the output is exact again 747 ms later, once the reduction
  is under the gain path's step (2⁻²²); the envelope works in reduction
  (1 − gain), so its recovery never stalls a float step short of unity.
- **Latency is the lookahead,** rounded to a frame: 0, 22, 88 and 221
  frames for 0, 0.5, 2 and 5 ms at 44,118 Hz, checked at 44.1, 48, 96 and
  192 kHz.
- **Release:** after a burst at +12 dB, the gain makes up 63 % of the way
  back in the Release time plus half the lookahead (the hold and the boxes
  centre the gain curve D/2 late): 101.0 ms for Release 100 at 2 ms,
  500.0 ms for 500 at Lookahead 0.
- **Lookahead 0:** no delay, so no ramp. An instant attack would flatten
  the leading edge of every louder peak at the ceiling, a hard clip;
  instead the envelope attacks over 1 ms and aims 1 dB under the ceiling,
  and a soft clip from there towards the ceiling catches what the attack
  lets through. The output stays under the ceiling (measured at most
  0.99999 of it); below −1 dB re the ceiling the signal is untouched.
- **Soft Clip:** the envelope lets peaks reach four times the ceiling, and
  the curve y = c − (c − K)² / (|v| − K + (c − K)) above the knee K = c/2
  rounds them: slope 1 at the knee, approaching c and never reaching it,
  so the output tops out at 15/16 of the ceiling (−0.56 dB). It adds odd
  harmonics: the renderer's 440 Hz sine at +6 dB into a −3 dB ceiling
  comes out with its third harmonic at −16 dB, against −124 dB through
  Brickwall, whose gain barely moves within a cycle.
- **Round** (2026-10-05, owner: "a gentle final rounding clip"), after
  Airwindows ClipOnly2 at `e718c9b` (MIT): the envelope lets peaks reach
  3 dB over the ceiling c, and the stage, ClipOnly2's loop scaled to c,
  leaves every frame within ±c as it came, bit for bit, and replaces each
  over by c h + (the frame before) s, h = 0.7390851 (the root of x =
  cos x) and s = 1 − h, so an over lands between its neighbour and the
  ceiling; the last frame of an over is then put right once the frame
  after is known (towards it if lower, else on towards c). ClipOnly2 gives
  each frame out a sample late for that look ahead; here the stage reads
  the next frame from the line (its input times this frame's gain), so
  Round adds no delay and Lookahead is the latency in every Mode. With the
  gain still, the output is ClipOnly2's recurrence to float rounding: a
  +1.9 dB sine with noise into a 0 dB ceiling matches it, written out in
  double in the test, within 7 × 10⁻⁸ at Lookahead 2, 0.02 and 5 ms, every
  frame under the ceiling bit for bit; and against Airwindows' own loop run
  in a container, −140 dB of residual [verified: `fm1-limit-test`'s
  `round`; tests/test_engines_squash.py with
  tests/fixtures/squash-oracle.json]. At Lookahead 0 there is no next
  frame: each over is rounded on the way in and given out at once.
  Against Brickwall on the renderer's sine at +2 and +12 dB of Drive into
  −6 dB, it adds odd harmonics (over ten times Brickwall's third) and is
  louder by over 1 dB, keeping the body of the wave where Brickwall turns
  all of it down. The line stores Round's share beside Soft Clip's, and the
  envelope's aim moves to +3 dB only once Mode has reached Round. Not
  taken: ClipOnly2's spacing above 88.2 kHz (it looks 2–16 samples ahead
  there); Round looks one frame ahead at any rate.
- **Changes:** Ceiling, Drive, Link and Mix glide over 5 ms, sample by
  sample, so any block size gives the same output (checked at 64, 7 and 1
  frames with every parameter moving, Lookahead and Mode included). The
  line stores Drive and Ceiling with each frame, so a turned Ceiling
  reaches the detector and the delayed audio together and the ceiling
  holds while it glides. A Lookahead change crossfades from the old delay
  to the new over 5 ms (a 440 Hz sine shows no larger step than its own);
  another change waits for the crossfade to finish. Mode glides its output
  stage over 5 ms. Both can be locked and modulated: turned every third
  block (Mode also every 64th, so its glide completes) while a swelling
  sine is limited, they step the output no more than holding any value
  does plus a crossfade's allowance (2c/220): at most 0.2 of it in
  `fm1-limit-test`'s `modulated`, 0.8 in tests/test_engines_fx_switches.py
  (Lookahead through 0 in Soft Clip) [verified, 2026-10-02].
- **Turning Lookahead or Mode while it limits** leaves the ceiling to the
  gain path, never to the final clamp, and never steps the output (both
  fixed on 2026-10-02: in review, the clamp had flattened peaks of up to 41
  times the ceiling, +32 dB; then, with Lookahead and Mode made lockable
  and modulatable, a Lookahead turned every few blocks stepped the output
  by up to 16 times a crossfade's allowance, and the stage passed the
  ceiling by 18 % before the clamp). Each tap of a Lookahead crossfade has
  a gain path of its own: the old tap keeps its boxes, untouched, and the
  new one gets a second set, its own length, started at the held gain (as
  on `create`) and faded in from nothing, so it starts smoothly however far
  the old gain had ramped. Both sets average the one hold, which spans the
  longer delay plus one frame while the taps fade, so every value either
  set averages is a minimum over a window holding its own tap's frame. A
  longer lookahead replays frames the old hold has forgotten; the hold
  takes their need from the line (recomputed from the stored input, Drive,
  Ceiling and Mode: one divide per loud frame, once per change). When the
  crossfade ends the new set is the only one, and a shorter hold simply
  forgets sooner, which its boxes smooth. Lookahead 0 has its own envelope
  (1 ms attack), run only while a tap with no delay is heard: a fade to 0
  starts it from the lookahead envelope's reduction, and a fade from 0
  restarts the hold from the line, so the path faded in has been running
  since the fade began. The line stores Mode with each frame, so a frame
  leaves through the stage its gain was made for, and the envelope aims at
  four times the ceiling only once Mode has reached Soft Clip (part-way,
  the blend of the two stages with a +12 dB gain would pass the ceiling).
  Checked in `fm1-limit-test` with 27,325 Lookahead turns (0 included), and
  Mode and Link turned too, on bursts at 8, 44.1, 96 and 384 kHz, and with
  Lookahead and Mode turned every few blocks on a swelling sine: before the
  clamp the envelope and the stage stay within 1.2 × 10⁻⁷ of the ceiling
  [verified on the Mac, 2026-10-02]. With Lookahead and Mode turned every
  third block, the output's bits are the same from Apple clang arm64, GCC
  12 x86-64 and i686 (SSE) and Emscripten 6.0.10 under Node [verified: a
  hash of the four new effects with their switches turned, 2026-10-02].
  With Round among the Modes (in turn, every 64th block, and at random
  with Lookahead), no step beyond the allowance either, and the ceiling
  held [verified: `fm1-limit-test`'s `modulated` and `round_move`,
  2026-10-05].
- **The host's bus limiter stays.** `include/fm1_mix_limiter.h` runs after
  every chain: a peak follower with an instant attack, a 100 ms release and
  a fixed 0.98 ceiling, and the guard that turns non-finite samples into
  silence. It is the only stage that sees everything that reaches the DAC,
  so it remains the last line of defence. This effect is optional and adds
  what the bus limiter cannot: lookahead (no flattened onsets), a ceiling
  of your own, drive, release, stereo link and a soft-clip mode. With
  Ceiling at −0.18 dB or lower (0.98) and nothing louder after it, the bus
  limiter has nothing left to do.
- **True peak: not implemented.** Peaks between samples can pass the
  ceiling after the DAC's reconstruction, typically by well under 1 dB and
  by up to about 3 dB on pathological signals [inferred]; the default
  −1 dB ceiling leaves room for that. A true-peak option would detect on a
  4× oversampled copy (a polyphase interpolator of about 12 taps per phase,
  about 100 multiply-adds per stereo frame) and add the interpolator's
  delay to the latency [inferred].
- **Memory:** grows with the host rate, fixed at `create`: 5 ms of frames,
  at most 510. Per frame of lookahead: 24 bytes of line (the input and the
  four controls), 12 for the two hold deques and about 16 for the two
  sets of box filters. 11,952 bytes at 44,118 Hz, 12,928 at 48 kHz, 25,408
  at 96 kHz and 29,008 at 102 kHz and above, where the cap makes the
  longest lookahead shorter than 5 ms (2.66 ms at 192 kHz) [verified:
  `fm1-limit-test`, 2026-10-05; Round's share in the line added 4 bytes a
  frame: 11,008 and 26,912 before]. The instance holds no pointers, so a 32-bit build has
  the same sizes [verified: GCC 12 i686 in a Linux container,
  2026-10-02].
- **Cost, desktop only:** 1.0 µs per 64-frame block on an Apple M1 Max
  with no gain reduction, 1.2 µs limiting hard, 1.1 µs at Lookahead 0 and
  1.4 µs in Soft Clip at +12 dB (their curve divides): 0.07–0.10 % of the
  block (20 s of noise, best of five, `fm1-render`, 2026-10-02, after the
  gain path per tap; Lookahead 0 no longer runs the hold and the boxes).
  Two divides per frame in the detector while it limits, and two more in a
  soft clip; the hold's deque is amortised, one push and at most one pop
  per frame on average. A Lookahead change adds one pass over the line (at
  most 510 frames, a divide per loud one) to the block it lands in, and
  runs the boxes (and at 0, Lookahead 0's envelope) twice for the 5 ms of
  the crossfade. Stage B measures pi32v2.
- **Determinism:** no libm. 2^x (for dB) and the one-pole coefficients are
  polynomials written here, and the gain path is integers. A 32-bit and a
  64-bit Linux build with `-ffp-contract=off` give identical results in
  every check of `fm1-limit-test`. A `#pragma STDC FP_CONTRACT OFF` keeps
  clang from fusing multiply-adds (Apple clang fused 44 operations here
  before the review added it, 2026-10-02 [verified: `objdump`]), so the
  Mac's native build computes the same bits as well [verified: an output
  hash against GCC 12 x86-64 and i686 with SSE, 2026-10-02].
- `build/fm1-limit-test` (`test/limit_test.cc`) reads the float output with
  no WAV and no bus limiter after it, and links the effect built once more
  with `FM1_LIMIT_PROBE`, which only records how far the envelope alone
  comes to the ceiling. It covers the ceiling, latency, transparency,
  release, Link, changes mid-stream, the crossfades, silence, a 20 s sweep
  of every parameter to any value (NaN and infinities included) with bad
  input mixed in, and the host rates it accepts (8–384 kHz).

## DJ Filter

One knob for the end of a chain: turned left of centre it low-passes, turned
right it high-passes, and around the centre it leaves the sound untouched
(`src/fx_djfilter.cc`, our own code, MIT). It is the first of the master-bus
effects in notes/2026-10-02-delay-reverb-eq-gates-options.md (§4.3, §5).
Until the host has a master chain, put it in the last effect slot (FX2),
which is the master of a one-sound app; the note's order puts it after the
Comp and before the limiters, so its sweeps do not pump the Comp's detector
and its resonant peaks meet a limiter.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Sweep | −1 to +1 (0) | Left of the dead zone the low-pass, right of it the high-pass. With u the travel past the dead zone (0–1), the cutoff falls from 20 kHz to 60 Hz (low-pass) or rises from 20 Hz to 8 kHz (high-pass), equal octaves for equal travel, never above 0.45 of the host rate |
| 1 | Resonance | 0–1 (0.2) | Q = 0.707 + Resonance × 7.29 × 4u(1 − u): Q 8 (+18 dB at the cutoff) at mid travel and Resonance 1, none at either end of the travel, so the open end never whistles and the far end never booms |
| 1 | Slope | 12 dB, 24 dB (12 dB) | 24 dB adds a second filter of the same cutoff at Q 0.707 after the first, which alone resonates. A change crossfades the two over 5 ms, so it can be locked and modulated (rounded) |
| 1 | Mix | 0–1 (1) | The filtered sound against the dry. 0 is a bypass |
| 2 | Dead Zone | 0–0.2 (0.05) | How far either side of centre the knob passes the input untouched |
| 2 | Range | 0.1–1 (1) | How much of the sweep the knob reaches, in octaves: at 0.5 the low-pass stops at 1.1 kHz and the high-pass at 400 Hz |

Where the knob puts the cutoff at Range 1 and the default dead zone:

| Sweep (±) | 0.1 | 0.25 | 0.5 | 0.75 | 1 |
| --- | --- | --- | --- | --- | --- |
| Low-pass | 14.7 kHz | 5.9 kHz | 1.28 kHz | 277 Hz | 60 Hz |
| High-pass | 27 Hz | 71 Hz | 342 Hz | 1.65 kHz | 8 kHz |
| Q at Resonance 0.2 / 1 | 1.0 / 2.2 | 1.7 / 5.6 | 2.2 / 8.0 | 1.8 / 6.4 | 0.71 / 0.71 |

How it works [verified: tests/test_engines_djfilter.py and
`build/fm1-djfilter-test`, 2026-10-03, unless marked]:

- **The filter** is the trapezoidal state-variable filter of Andrew Simper
  (Cytomic) and Vadim Zavalishin, the form of stmlib's `Svf`, written out
  here because entering a side sets its states, which `stmlib::Svf` keeps
  private. Its states are integrator charges, so new coefficients change the
  filter's future, not its stored energy: it sweeps without the transients
  of a direct-form biquad. At 24 points across the sweep, both slopes,
  Range and Dead Zone, the response is the analytic one (the bilinear
  transform of the analog filter) within 0.0001 dB.
- **Exact bypass.** In the dead zone, and at Mix 0 anywhere, the filter does
  not run and the output is the input bit for bit, negative zero and
  subnormals included (the guard leaves anything within ±16 alone). Back at
  the centre after a visit to either side, the output is the input again
  21 ms (from the left) and 22 ms (from the right) after the knob moves.
- **Entering and leaving a side.** The travel u in force starts at 0 (the
  open end), with the states where they would be had the filter been
  running there: the low-pass's low-pass integrator holds the input, the
  high-pass's states are zero. The wet share fades in by a smoothstep over
  the first 8 % of u, which u crosses in no less than 3 ms, and u covers the
  rest no faster than 0 to 1 in 10 ms. Leaving, u returns to 0 the same way;
  crossing to the other side goes through 0 and the bypass. On a 0.8 sine
  at 60 Hz, each of 12 transitions (entering, leaving and crossing sides,
  with and without a dead zone, the slope switching both ways, Mix from 0)
  adds at most −72 dB above 4 kHz, on the fastest crossings (−85 dB or less
  entering a side), and at the default Resonance none thumps: the output
  stays within 10 % of the note's level.
- **Smoothing.** Every 16 frames, on the instance's own frame count, a
  control tick glides the knobs (Sweep through two 5 ms one-poles in series,
  the rest through one), moves u and works out the coefficients; they ramp
  linearly to them over the next 16 frames, with h and the wet share
  recomputed every frame. A sweep written every 32 frames (as the modulation
  matrix will) leaves −82 dB (low-pass) and −116 dB (high-pass) at the
  places zipper noise would land, against −45 and −78 dB for the same filter
  with its coefficients stepped at each write. Changes mid-stream give the
  same output at host blocks of 64, 12, 7 and 1, from any instance fill.
- **No libm.** 2^x is `CompExp2` (`src/fx_comp_math.h`, shared with Comp
  and Tilt; until the pack's review the file kept an identical copy) and
  tan(πx) a polynomial in the file, and
  floating-point contraction is off for it, so the bits are the same from
  Apple clang (arm64, −O0 and −O2), GCC (x86-64, also with FMA available,
  and i386 with SSE) and Emscripten, with parameters moving at three host
  rates; without the pragma Apple clang's differ. `nm -u` lists nothing.
- **Contracts:** the input guard of `mi_fx.cc` (NaN reads as 0, ±16 clamp,
  dry path included), `fm1_param_clamp`, host rates 8–384 kHz, states
  flushed below 1e-20. Twenty seconds of every parameter jumping to any
  value, NaN and infinities included, between blocks of 1–64 frames: finite,
  peak 1.33 on noise of ±0.5, and back to the exact bypass at the defaults.
  After full-scale noise into the most resonant settings, silence comes out
  as exact zeros within 0.5 s.
- **Memory and cost:** 224 bytes, no delay lines; no pointers in the
  struct, and the same on 32-bit builds [verified: `instance_size` compiled
  by clang for i386 and wasm32, 2026-10-05]. About 30 operations a
  frame at 12 dB and 50 at 24 dB while filtering; a moving sweep adds a
  divide per filter per frame and a control tick (2^x, tan, two divides)
  every 16 frames; the dead zone costs the guard alone. Desktop (Apple M1
  Max, 20 s of noise, best of three; fm1-render's `ns_per_block`): 62 ns
  per 64-frame block in the dead zone, 742 ns at 12 dB, 1,011 ns at 24 dB,
  against Plate's 1,088 ns and Fold's 2,707 ns in the same run; 1.3 µs at
  24 dB with Sweep written every block (`fm1-djfilter-test --bench`). The
  note's estimate for pi32v2 is 1–1.5 % of a core [inferred]; the dev kit
  will measure it.

Where it departs from the research note, and why:

- **The cutoff law is exponential in frequency, not in g.** The note's
  g = g_a·(g_b/g_a)^u spends a third of the low-pass side's travel between
  20 kHz and 7 kHz, because tan() stretches the top octaves. Equal octaves
  per travel cost one polynomial tan() per control tick.
- **Slope is lockable and modulatable** (owner's policy of 2026-10-02:
  switches that change cleanly), not NOLOCK as the note had it.
- **The high-pass starts from zero states**, not the input's DC steady
  state: measured on a bass note, that doubled what entering added above
  4 kHz and overshot by 15 % when crossing with no dead zone. The low-pass
  does start from the input; from zero it added 100 times more when 24 dB
  starts.
- **The fade is a smoothstep, evaluated every frame, with u rate-limited.**
  A linear fade tied to u alone, evaluated per tick, left 25 times more
  above 4 kHz on a fast crossing.
- **Range** is the share of the sweep's octaves the knob reaches, at both
  ends; the note named it without defining it.

## Tilt

A tilt equaliser written here (`src/fx_tilt.cc`, MIT), as designed in
`notes/2026-10-02-delay-reverb-eq-gates-options.md` §4.2. One knob turns the
whole spectrum about a pivot: to the right the highs rise and the lows fall
by as much (brighter), to the left the reverse (darker), and the pivot stays
at 0 dB. It is meant for the master bus; until there is a master chain it
goes in the last effect slot. The ideas come from Airwindows' ToneSlant
(MIT) and Faust's `fi.spectral_tilt` (STK-4.3), which approximates a
constant slope with staggered first-order sections [reported, not read];
no code is taken from either.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Tilt | −9 to +9 dB (0) | The gain at the top of the spectrum (the Nyquist frequency); the bottom (DC) gets the opposite. At 0 the input passes bit for bit |
| 1 | Pivot | 200–5,000 Hz (1,000) | The frequency left at 0 dB. Held below 0.45 of the host's rate, which only matters below 11.1 kHz |
| 1 | Curve | Shelf, Slope (Shelf) | Shelf: one section, steepest at the pivot, levelling into shelves within about two octaves. Slope: two sections 1.5 octaves either side of the pivot, half the tilt each: a gentler, straighter slope. A change glides, so it can be locked and modulated (a route is rounded) |
| 1 | Level | −24 to +12 dB (0) | The output's gain |

Tilt +9 dB about 1 kHz, in dB [verified: `build/fm1-tilt-test`, float]:

| Curve | 20 Hz | 100 Hz | 200 Hz | 500 Hz | 1 kHz | 2 kHz | 5 kHz | 10 kHz | 20 kHz |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Shelf | −8.99 | −8.67 | −7.83 | −4.39 | 0.00 | +4.41 | +7.91 | +8.77 | +9.00 |
| Slope | −8.97 | −8.23 | −6.63 | −2.80 | 0.00 | +2.81 | +6.76 | +8.45 | +8.99 |

How it works [verified: tests/test_engines_tilt.py and
`build/fm1-tilt-test`, 2026-10-05, unless marked]:

- **The filter.** One section is H = T − (T − 1/T)·LP: 1/T at DC and T at
  Nyquist, with T the gain at the top. In the analogue prototype LP has its
  pole at T times the pivot, so H has a pole at T·w and a zero at w/T, and
  its dB response is odd about the pivot, 0 dB there. LP here is the
  trapezoidal (TPT) one-pole with g = T·tan(π·fp/fs): the bilinear transform
  prewarped at the pivot, so the digital pivot is exactly 0 dB, and turning
  Tilt needs no tan (g scales with T). Slope's two sections, each with
  √T, take g = √T·g_p/2^1.5 and √T·g_p·2^1.5 under the same prewarp, and
  their gains at the pivot cancel: exactly 0 dB again. The effect's
  response, from its impulse response in float, matches a double-precision
  model of these equations within 5e-6 dB at 38 settings and 18
  frequencies each; pivot, DC and Nyquist are within 5e-6 dB of 0, −Tilt
  and +Tilt.
- **Slope against Shelf.** From 200 Hz to 5 kHz about 1 kHz at ±9 dB, Slope
  stays within 0.12 dB of a straight line, 2.9 dB an octave; Shelf strays
  by 1.1 dB, 3.85 dB an octave at its steepest. 1.5 octaves is the stagger
  that keeps Slope straightest over that band (searched from 0.6 to 2
  octaves; the test reruns the search on the model).
- **Exact bypass.** At Tilt 0 both sections have T = 1, so T − 1/T = 0 and
  each returns its input itself (not 1·x − 0·lp, which can turn −0 into +0),
  and Level 0 dB is a gain of exactly 1. So the defaults, and Tilt 0 at any
  Pivot and Curve, pass the input bit for bit: random floats, ±0,
  subnormals and values near the guard, at random block sizes. After Tilt
  and Level have moved and come back to 0, the output is the input again,
  bit for bit, 35 ms later, when the glide lands. The low-passes run
  underneath, so leaving 0 starts from a settled filter.
- **Glide.** Every control, Curve included, glides sample by sample through
  two one-poles in series (2.5 ms each, about 5 ms in all), so any block size
  gives the same output; values set before the first render apply at once.
  Curve glides the sections' gains and section A's pivot: the one-poles'
  states are integrator charges, so new coefficients change the filter's
  future, not its stored energy, and there is nothing to crossfade.
  - *Two stages, not one.* A single one-pole starts at full speed. When
    Tilt jumps end to end over a 100 Hz sine, that corner made the output's
    second difference 47 times the steady sine's; with two stages it is 1.5
    times. A hard switch between the two settings is about 1,400 times.
  - *A snap of 1e-6, not 1e-4.* A glide lands on its target when within
    1e-6 of it, or when its step falls under half an ulp, where a float
    one-pole would stall. With Fold's 1e-4, Tilt swept end to end at 1 Hz
    and set every 32 frames, as the modulation matrix will, snapped near the
    sweep's turns: energy above 1 kHz at −92 dB against −120 dB here. The
    third difference of that sweep is now that of Tilt set every frame (the
    sine's own, −110.7 dB). Fold and the effects that copied its glide may
    want the same change [inferred: not measured on them].
- **Contracts:** the input guard of `mi_fx.cc` (NaN reads as 0, ±16 clamp),
  `fm1_param_clamp`, and Curve rounded to the nearest value. Silence in is
  exact silence out at any setting, while controls move too. Tails flush
  below 1e-20, so no subnormals: the slowest (Tilt −9, Pivot 200, Slope) is
  exact zeros 160 ms after the input stops. 20 s of random parameter
  changes between blocks of 1–64 frames, NaN and infinities included, stay
  finite, the output's peak at most 12.2 times the input's (+9 dB at the
  top, +12 dB of Level and the filters' overshoot). Host rates 8–384 kHz.
- **Determinism:** no libm. dB to gain is `CompExp2` from
  `src/fx_comp_math.h`, the header of Comp's branch, copied byte for byte so
  that the two merge cleanly (the research note's shared libm-free maths).
  The pivot's tan is a ratio of sine and cosine Taylor polynomials, and
  contraction is off for the file under clang (`#pragma STDC FP_CONTRACT
  OFF`, as in Comp). `fm1-tilt-test`'s whole output is the same, bit for bit,
  from Apple clang on arm64, GCC 12 on x86-64 and GCC 12 on i386 with CI's
  `-msse2 -mfpmath=sse`. On i386's x87 only the last bits of the non-flat
  outputs differ, and the bypass holds: the glide's snap tests magnitudes,
  not whether a sum rounded back. JieLi's clang compiles it for pi32v2 at
  `-O2 -ffp-contract=off` without a warning, and it needs nothing but
  `memset` [verified: compile only, the toolchain of
  `tools/jieli/compile-check.sh`].
- **Memory:** 144 bytes on x86-64 and on i386 (no pointers); no delay lines.
- **Cost:** about 25 operations per sample and channel, no divide: about
  3,200 per 64-frame block, and up to about 6,000 and 256 divides while a
  control glides [inferred]. Desktop (Apple M1 Max, noise in, 20 s): 0.61–0.65 µs
  per block, 0.04 % of the 1.451 ms block, flat or tilted, against Fold's
  1.9 µs and Plate's 1.0 µs in the same run (fm1-render's `ns_per_block`);
  about 1.1 µs, 0.08 %, with Tilt moved every block so that it always
  glides (a timing loop of our own, rougher). Stage B measures pi32v2.
- **Decisions against the research note.** Tilt is ±9 dB (the note offered
  ±6 or ±9), because Slope only differs much from Shelf past ±6. The note's
  Sections (1 or 2, NOLOCK) became Curve (Shelf, Slope), lockable and MOD
  under the owner's rule for switches (2026-10-02), which a glide allows.
  Level is −24 to +12 dB, as Drive's. Tilt and Level are in dB with
  `FM1_UNIT_NONE` until `fm1_unit_t` has a dB code (note §7.4).
- **Not yet:** Drive's Tone, a tilt about 800 Hz, could use these
  sections, as the note proposes; it cuts one side instead of turning both.
- fm1-render writes 16-bit samples through the limiter, so
  `build/fm1-tilt-test` (`test/tilt_test.cc`) drives Tilt directly: its response in float, the
  bypass bit for bit, jumps of every control while a sine plays, Tilt swept
  at the matrix's rate, every parameter changed mid-stream to any value,
  silence and tails, and the host rates it accepts.

## Master Sat

Gentle saturation for the master bus (`src/fx_sat.cc`, our own code, MIT),
the design of §6 of
[notes/2026-10-02-delay-reverb-eq-gates-options.md](../notes/2026-10-02-delay-reverb-eq-gates-options.md).
Only the band between Clean Lo and Clean Hi goes through the curve, and
only what the curve adds to it, the part that is not linear, is added to the
dry signal:

    band = low-pass(Clean Hi) of high-pass(Clean Lo) of x;  u = Drive x band
    G = Glue's gain (below);  v = G u
    wet = G x + DC blocker((h(v) - v) / Drive);   out = x + Mix (Level x wet - x)

The dry signal is never split, so the filters' phase cannot comb with it,
and a quiet signal passes unchanged: Drive's gain into the curve is divided
out again. The Drive effect from the same research is the other kind, an
insert that distorts on purpose; this one is meant to be left on the bus.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Drive | 0–18 dB (6) | Gain into the curve, divided out after it: where the bending starts, not how loud the result is |
| 1 | Clean Lo | 20–300 Hz (100) | A 12 dB/octave high-pass before the curve: below it nothing is saturated (no intermodulation of the kick and the bass with the rest), and Glue does not hear it |
| 1 | Glue | 0–1 (0.25) | Turns the drive into the curve and the level of the whole signal down by how hard the curve works, up to 6 dB: a bus compressor keyed by the saturation |
| 1 | Mix | 0–1 (0) | Dry to wet. At 0, the default, the (guarded) input passes bit for bit, whatever else is set |
| 2 | Shape | Smooth, Dense (Smooth) | The curve. Dense bends sooner and tops out lower. A change crossfades over 5 ms |
| 2 | Asymmetry | −1 to +1 (0) | Offsets the curve's input by 0.5 × Asymmetry: one side bends first and even harmonics appear |
| 2 | Clean Hi | 1–20 kHz (6,000) | A 12 dB/octave low-pass before the curve (at most 0.45 of the host's rate): above it nothing is saturated, and fewer harmonics are made to alias |
| 2 | Level | −12 to +12 dB (0) | The wet signal's gain |

- **The curves** are odd polynomials of the 11th degree with Airwindows'
  coefficients (Chris Johnson, MIT; the notice is in the source): Smooth is
  PurestSaturation's, x − x³/8 + x⁵/128 − x⁷/4,096 + x⁹/262,144 −
  x¹¹/33,554,432, and Dense is TapeHack2's, x − x³/6 + x⁵/69 − x⁷/2,530.08
  + x⁹/224,985.6 − x¹¹/9,979,200 [verified: both `*Proc.cpp` files and the
  LICENSE at Airwindows commit `d22a25b`, 2026-10-05]. Airwindows clamps
  them at 2.0326 and 2.3059; we clamp each where its slope reaches zero,
  2.04501 and 1.95801, which makes both monotonic with a C1 plateau
  (Airwindows' PurestSaturation still has a slope of 0.0065 at its clamp, and
  TapeHack2 dips 0.4 % past its peak before its clamp) [verified: bisection
  on the derivative]. Ceilings 1.2212 and 1.0821.
- **Small signals:** the residual h(v) − v is evaluated as a polynomial in v
  about Asymmetry's offset, b₂v² + … + b₁₁v¹¹ (a Taylor shift of the curve,
  done when the offset moves), not as f(v + a) − f(a), which would lose a
  quiet signal to the rounding of v + a and, through Glue's detector, read
  near-silence as full squash. For a −60 dBFS sine at full Drive and Glue
  the output differs from the input by at most −96 dB of its peak (−54 dB
  with Asymmetry at 1, the second harmonic) [verified: fm1-sat-test]. With Asymmetry at 0 the even terms are
  zero and an odd-only sum in v² does half the work.
- **Glue** is the note's idea after Airwindows Compresaturator (MIT; no code
  from it): the curve's own overspill turns its drive down. Here the
  detector is the overspill as a share of the input, the squash
  s = 1 − h(u)/u of the louder channel, through a peak envelope (2 ms
  attack, 200 ms release; stereo-linked, feed-forward from the drive as
  set), and G = 1 − Glue × s / 2. The note asked for the overspill
  |u| − |h(u)| itself; divided by |u| the reduction is bounded (6 dB) and the
  same at any Drive, and the release takes the same time whatever the level
  falls to. Measured on a 440 Hz sine at Drive 12: −0.8 dB of level and
  −3.6 dB of distortion at Glue 1; on a step from 0.05 to 0.5 the reduction
  is half caught within 15 ms, and a second after the step back it is gone
  [verified: tests/test_engines_sat.py]. The envelope is two lines; when the
  shared libm-free maths header of the note's stage B1 lands, it moves there
  with the Comp's smoothing.
- **Asymmetry** subtracts f(a), renormalises the slope at the origin to 1
  and leaves the DC that a lopsided curve makes to a 10 Hz blocker on the
  residual: the second harmonic of a 440 Hz sine at Drive 6 is −27 dB at
  Asymmetry 0.5 and −20 dB at ±1, with the output's mean under 10⁻⁶.
- **Aliasing,** fm1-sat-test's count of every reflected harmonic against
  the fundamental [verified, 2026-10-05]:

  | Case | Master Sat | Plain tanh, same peak |
  | --- | --- | --- |
  | 3 kHz, curve peak about 1.5 (Drive 10), the note's case | −125.8 dB Smooth, −125.0 dB Dense | −66.2 dB |
  | 3 kHz, Drive 18 (clamped), Clean Hi 6 kHz | −49 dB | |
  | 3 kHz, Drive 18, Clean Hi open | −43 dB | |
  | 440 Hz, Drive 18 | −85 dB | |

  Below the clamp the polynomial makes nothing above its 11th harmonic; once
  Drive pushes peaks onto the plateau, the corners make harmonics without
  end. No oversampling and no antiderivative anti-aliasing (the note's
  recommendation for a bus effect); Clean Hi is the guard.
- **Contracts:** the input guard of `mi_fx.cc`; `fm1_param_clamp`; every
  continuous knob glides over 5 ms sample by sample and Shape crossfades, so
  the output is identical at host blocks of 1, 7 and 64, also with knobs
  turned between blocks; values set before the first block apply from its
  first sample. Silence in is exact silence out at any setting and while the
  knobs move (the residual has no constant term). A filter's two states
  flush to zero together once both are below 10⁻²⁰: flushing each alone, as
  Fold does, cut their coupling and left the 20 Hz high-pass decaying with a
  time constant of 5 s at 10⁻¹⁸ [verified]. After loud noise a tail ends in
  exact zeros within 0.66 s.
- **Determinism:** no libm at all (2^x, sine and cosine are polynomials
  written here; `nm -u` lists no maths symbol) and no fused multiply-adds
  (`#pragma STDC FP_CONTRACT OFF`, as in the Comp). fm1-sat-test prints a
  digest of 3 s of output with every knob turned; Apple clang on arm64, GCC
  13 on x86-64 and Emscripten's wasm32 printed the same one [verified,
  2026-10-05, in containers on the LAN build host], and the test pins it.
- **Memory:** 352 bytes (336 before the idle path's counters), no delay
  lines and no pointers: the same on arm64, x86-64 and wasm32 [verified].
- **Cost:** per frame, two two-pole filters, the curve and a DC blocker per
  channel and one divide: about 100 operations with Glue at 0, 130 with
  Glue up (the curve runs again at the lowered drive) and 170 with
  Asymmetry too (ten terms instead of five); both curves during a 5 ms Shape
  crossfade. At one operation per cycle that is 2–5 % of a 240 MHz core
  [inferred], more than the note's 1.5 %, which did not count the filters'
  flush tests, Glue's second curve or the divide. Desktop (Apple M1 Max,
  20 s of noise, the fastest of nine runs, 2026-10-05) [verified:
  fm1-render's `ns_per_block`]: 1.64 µs per 64-frame block with Glue at 0
  (0.11 % of the block), 2.32 µs with Glue at 1 (0.16 %), 3.41 µs with
  Asymmetry as well (0.23 %), against 1.76 µs for Fold and 0.90 µs for
  Plate in the same runs. Mix at 0 cost the same until the idle path: after
  2 s there Master Sat now idles at about 2 % of that, and turning Mix up
  waits 0.19 s while everything warms up from rest
  ([Idle at pass-through](#idle-at-pass-through)).
- **Where it departs from the note:** the knobs it called Bass and Clean
  highs are Clean Lo and Clean Hi, because "Clean Highs 20000" does not fit
  a row of the 240-pixel screen [verified: the simulator's layout check];
  Glue's detector is normalised (above); the clamps sit where the slopes
  reach zero (above); Mix defaults to 0, because the note's master-bus rule
  (§5) gives every master effect an exact-bypass default and a saturator has
  no neutral Drive; and Glue's envelope is not yet shared with the Comp's,
  which is not on this branch. Not taken: a Tape mode (the note keeps tape
  colour in the Drive effect) and the Console sum mode (deferred until
  several units are summed).
- `build/fm1-sat-test` (`test/sat_test.cc`) drives Master Sat directly:
  every parameter changed mid-stream to any value, NaN and infinities
  included, between blocks of 1–64 frames; the glide, the Shape crossfade,
  Glue's envelope; float-exact bypass; the host rates it accepts
  (8–384 kHz); the digest; and `fm1-sat-test tone HZ AMP [NAME=VALUE…]`,
  a sine's harmonics, distortion and aliases at 1 Hz resolution, which the
  tests use for what each knob does.

## Isolator

A three-band DJ kill EQ written here (`src/fx_isolator.cc`, MIT), the design
of notes/2026-10-02-delay-reverb-eq-gates-options.md §4.4. The band tree is
Faust's `crossover3LR4` (filters.lib, STK-4.3, `9c42142`), followed for its
structure only; no code is taken. Stereo in, stereo out, each channel
filtered on its own.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Low | 0–1 (0.75) | The low band's gain: 0 is a true zero, 0.75 unity, 1 is +6 dB (×2). Below unity (k / 0.75)³, so the middle of the cut, 0.375, is −18 dB; above it 2^(4 (k − 0.75)) |
| 1 | Mid | 0–1 (0.75) | The mid band's gain, the same law |
| 1 | High | 0–1 (0.75) | The high band's gain, the same law |
| 1 | Kill | None, Low, Mid, Low+Mid, High, Low+High, Mid+High, All (None) | Kills bands whatever their knobs say; un-killing returns them to the knobs' gains. Lockable, and modulated rounded |
| 2 | Low Xover | 80–400 Hz (250) | The low/mid crossover |
| 2 | High Xover | 1,500–5,000 Hz (2,500) | The mid/high crossover. Both crossovers stay under 0.45 of the host's rate |

The defaults are the note's 250 Hz and 2.5 kHz (Mixxx starts its EQ at 246 Hz
and 2,484 Hz [reported in the note: its constants]).

- **The bands.** Fourth-order (24 dB/octave) Linkwitz-Riley crossovers, each
  a pair of Butterworth sections: low = AP2(f2)(LR4-LP(f1)(x)), mid =
  LR4-LP(f2)(LR4-HP(f1)(x)), high = LR4-HP(f2)(LR4-HP(f1)(x)). LR4-LP plus
  LR4-HP at one frequency is a second-order all-pass, so the three bands at
  unity sum to AP2(f1) · AP2(f2) · x: flat in magnitude. Each section is the
  trapezoidal (TPT) state-variable filter in Cytomic's form; one update gives
  low-, band- and high-pass, so a crossover's first section serves both of
  its sides and the all-pass is x − 2k·bp: 7 updates per channel per sample.
- **Measured** [verified: tests/test_engines_isolator.py through
  `build/fm1-isolator-test`, float impulse responses, 2026-10-05], at the
  defaults:
  - the band sum is flat to within 2.7 × 10⁻⁵ dB from 20 Hz to 20 kHz
    (float rounding);
  - each band is −6.02 dB at its crossover, at both ends of both ranges;
  - kill low: −63.7 dB at 40 Hz. Kill high: −80.4 dB at 15 kHz. Kill mid:
    −29.8 dB at 600 Hz, −31.1 dB at 1 kHz, but only −19.0 dB at 1.5 kHz,
    because the mid band is three octaves wide and the crossovers' skirts
    overlap. These are the note's figures;
  - Kill gives the same response as a knob at 0, sample for sample.
- **Unity is bit-exact.** While all three bands ask for exactly unity and
  nothing is killed (the defaults, whatever the crossovers), the output is
  the guarded input, bit for bit, rather than the all-passed band sum, which
  differs from it in phase. The filters keep running, so leaving unity
  crossfades linearly from the input to the band sum over 5 ms, and returning
  crossfades back; 5 ms later the output is the input again, bit for bit.
  Two seconds after that the filters stop until unity is left again
  ([Idle at pass-through](#idle-at-pass-through)).
  During the crossfade the two signals' phase difference makes a brief dip
  around the crossovers: halfway through, for the defaults, −17 dB at f1
  itself and a full null where the all-passes have turned the phase by half
  a cycle, at 228 Hz and 2.73 kHz [verified 2026-10-05: the response with
  the crossfade held at its midpoint]. The alternative, always the
  band sum, is flat within float rounding but never the input itself.
- **Glides:** the band gains and the crossovers glide (one pole, 5 ms)
  sample by sample, so a kill does not click and the output does not depend
  on block size; values set before the first block apply from its first
  sample. The crossovers glide in g = tan(πf/fs), the filters' own
  coefficient, and land on it exactly: a glide also ends when its step is
  under half an ulp of the value, as Tilt's does, since a float one-pole
  stalls there for ever. Without that, 38 % of crossover changes at
  44,118 Hz and all of them at 96 kHz and above stopped up to 10⁻⁴ short,
  recomputing the coefficients every frame from then on [verified
  2026-10-05, the pack's review; `fm1-isolator-test` "landing" and
  `fm1-fx-hostile-test` now check it]. Turning Kill through every mask, the crossovers end to end or
  Low in and out of unity every third block, on a 100 Hz sine, steps the
  output by at most 1.31 times the sine's own largest step [verified]. Filter
  states below 10⁻²⁰ flush to zero, so tails never run in subnormals.
- **No libm.** tan comes from sin and cos polynomials written here, 2^x from
  a polynomial, the glide coefficient from a series; contraction is off for
  the file, so the browser's module computes the same bits [verified:
  `-ffp-contract=off` and Apple clang's default give identical output;
  without the pragma they differ].
- **Cost:** about 103 operations and 28 comparisons per channel and sample,
  about 13,000 and 3,600 per 64-frame stereo block, no divide unless a
  crossover is moving. At one operation per cycle on pi32v2 that is about
  5 % of a 240 MHz core [inferred]. Desktop (Apple M1 Max): 1.8 µs per
  block, 0.12 % of it, and 2.0 µs while the crossovers glide
  (`build/fm1-isolator-test --bench`). After 2 s at unity it idles, at
  about 2 % of that ([Idle at pass-through](#idle-at-pass-through)).
- **Memory:** 256 bytes (240 before the idle path's counters), no delay
  lines; the struct holds no pointers, and it is the same on 32-bit builds
  [verified: `instance_size` compiled by clang for i386 and wasm32,
  2026-10-05].
- `build/fm1-isolator-test` (`test/isolator_test.cc`) drives Isolator
  directly, in float and at any block size: every parameter changed mid-stream to any value, NaN and
  infinities included, between blocks of 1–64 frames; the glides at blocks
  of 64, 7 and 1; the switching; the frequency response in float; and the
  host rates it accepts (8–384 kHz).

## EQ

A three-band parametric equaliser written here (`src/fx_eq.cc`, MIT): a low
shelf, a bell and a high shelf in series, then Level. It follows
notes/2026-10-02-delay-reverb-eq-gates-options.md §4.5. Each band is one
linear trapezoidal state-variable filter in the form Andrew Simper (Cytomic)
published, whose maths is public domain [reported: that note, §1 and §4.1],
with the shelf and bell mixes from the same paper. No code is taken from
anywhere. One page per band; Level fills the last.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Low Freq | 20–1,000 Hz (100) | The low shelf's corner: half its gain (in dB) is reached here |
| 1 | Low Gain | −15 to +15 dB (0) | The gain far below the corner |
| 1 | Low Q | 0.3–2 (0.7071) | The shelf's slope: 0.7071 is the steepest that does not overshoot; above it a bump and a dip appear either side of the corner, below it the slope widens |
| 2 | Mid Freq | 20–18,000 Hz (1,000) | The bell's centre |
| 2 | Mid Gain | −15 to +15 dB (0) | The gain at the centre, exactly |
| 2 | Mid Q | 0.3–10 (1) | The bell's width; a cut is as narrow as a boost of the same Q |
| 3 | High Freq | 1,000–18,000 Hz (8,000) | The high shelf's corner |
| 3 | High Gain | −15 to +15 dB (0) | The gain far above the corner (at Nyquist, exactly) |
| 3 | High Q | 0.3–2 (0.7071) | As Low Q |
| 3 | Level | −15 to +15 dB (0) | Output gain, for make-up after boosts |

No band is tuned above 0.45 of the host's rate. Gains and Level are in dB
(`FM1_UNIT_DB` since engine API v3, as Comp's); the frequencies carry
`FM1_UNIT_HZ` and move on the LOG law ([below](#the-log-law)).

How it works [verified: tests/test_engines_eq.py and `build/fm1-eq-test`,
2026-10-05, unless marked]:

- **The response is the cookbook's.** Transformed, Simper's bell and shelves
  are exactly the RBJ Audio EQ Cookbook's peakingEQ, lowShelf and highShelf
  (shelves with Q), prewarped at the band's frequency. The measured response
  (the DFT of each impulse response, in float) agrees with the cookbook's
  biquads in double precision within 0.001 dB from 20 Hz to 21 kHz in all
  eleven measured settings, the three bands together included; the worst is
  8e-4 dB, a 60 Hz bell at Q 10. A +9 dB bell measures 9.0000 dB at its
  centre. The cookbook serves only as the reference: its direct-form biquads
  hold a history that is wrong for new coefficients, so they are not the
  structure to modulate.
- **0 dB is exact.** At 0 dB a band's mixing coefficients are exactly 0 (A =
  2^0 = 1 exactly), and the band then passes its input itself. With every
  gain and Level at 0 dB the output is the guarded input bit for bit,
  negative zero and subnormals included, at any frequency and Q and while
  they glide. Turned up and back to 0 dB, a band is exact again about 60 ms
  later: the glide lands on 0 rather than approaching it. Its integrators
  keep running while it is flat, so turning it up starts from a settled
  filter; once every gain and Level have sat at 0 dB for 2 s, EQ stops
  them and idles ([Idle at pass-through](#idle-at-pass-through)).
- **Modulation.** Each band's frequency (as log2 Hz), gain (dB) and Q (as log2
  Q) glide one step per 8 samples, counted from create (1 − e^(−8 / (5 ms ×
  rate)) of the way per step, a 5 ms time constant), and the band's
  coefficients are recomputed at each step. The integrators carry their charge across a change, so the filter's
  future changes, not what it holds; the mixing coefficients ramp linearly
  across the 8 samples, so a gain change never steps the output. Level
  glides every sample. A 100 Hz sine through a band whose frequency, gain or
  Q jumps between extremes every 50 ms (set at once by the host) bends the
  waveform 52–280 times less, by its largest second difference, than
  switching between the two settled filters would; what remains is the bend
  of the 5 ms fade itself. The output does not depend on the block size (1,
  7 or 64 frames, changes on and off the 8-sample grid).
- **Determinism.** No libm at all: 2^x, log2 and tan are polynomials in
  `src/fx_eq_math.h` (2^x to 8.7e-8 relative, log2 to 1.0e-6 absolute, tan
  to 6.5e-7 relative up to 0.45π, against libm in double), and clang fuses no
  multiply-add in these files. A hash of every output float of three renders
  with bands moving is the same from Apple clang on arm64, GCC 14 on x86-64
  and on i386 (`-msse2 -mfpmath=sse`, as CI's 32-bit job) and Emscripten
  6.0.10's WebAssembly under Node [verified: containers on the LAN build
  host], so the browser plays it sample for sample. JieLi's pi32v2 clang
  compiles it without a warning with `tools/jieli/in-container.sh`'s flags
  at -O2 and -Oz; its only external symbol is `memset`, and
  `-ffp-contract=fast` gives the same object as `off` [verified: compiled,
  not run].
- **Contracts:** no heap; every field set in create; parameters through
  `fm1_param_clamp`; the input guard of `mi_fx.cc` (NaN to 0, ±16 clamp), so
  bad input cannot latch it: a second after a fault the output is the clean
  render's within one LSB. Silence in gives exact silence out from any prior
  memory and setting. A band's two integrator states flush to zero together
  once both are below 1e-15: flushing them one at a time left a low band's
  tail leaking away through its tiny a3 term at −115 dB for minutes. Now the
  slowest tail (every band at its lowest frequency and highest Q, boosted 15
  dB, after a second of noise; the 20 Hz bell's pole Q is 23.7) reaches
  exact zeros after 12.3 s, the same settings cut after 2.0 s. Host rates
  from 8 to 384 kHz; at each, a +9 dB bell at 1 kHz peaks at +9.00 dB.
- **Memory:** 416 bytes on 64-bit and on 32-bit (368 before the idle
  path's counters) [verified: `instance_size`, Apple clang arm64 and GCC
  i386], no tables and no delay lines.
- **Cost:** about 60 floating-point operations per sample and channel, flat
  or not, about 7,700 per 64-frame block; while bands glide, about 130 more
  and 2 divides per band every 8 samples. Desktop (Apple M1 Max, noise in):
  1.86 µs per block with the bands flat or set, 2.6 µs with all three
  gliding all the time, against Plate's 0.93 µs in the same run: 0.13 % and
  0.18 % of the 1.451 ms block. At one operation per cycle on pi32v2 that
  is about 2.2 % of a 240 MHz core [inferred]; stage B measures it. Idle at
  pass-through, about 2 % of that ([Idle at pass-through](#idle-at-pass-through)).
- **Where it departs from the note:** the note proposed the vendored
  `stmlib::Svf` and stmlib's `SemitonesToRatio` tables for 10^(dB/40). The
  filter is written here instead, in the C subset like Fold, because the
  flat bypass and the mixing ramps need its two outputs and states directly;
  the maths is the same. The gains come from the 2^x polynomial, which is
  exactly 1 at 0 dB by construction, needs no table memory and is accurate
  to 1e-6 dB rather than 0.004 dB steps. The note's shared header for
  Tilt, DJ Filter, Isolator and EQ (the bell and shelf mixes, the knob law)
  is left to stage B1: the pack's integration (2026-10-05) kept each
  effect's own maths, whose bits its tests pin; `fx_eq_math.h` is a
  candidate.
- **Knobs:** the hosts turn a parameter in even steps of its range (a
  hundredth per detent in the virtual FM-1), so a frequency in Hz moves by
  180 Hz a detent on Mid Freq and a modulation route sweeps it in Hz, not in
  octaves; the multimode Filter's Cutoff has the same issue [verified:
  its branch, before it merged]. A logarithmic taper for
  `FM1_UNIT_HZ` parameters belongs in the hosts, so a lock or a preset keeps
  storing Hz.

## Idle at pass-through

EQ, Isolator and Master Sat each have settings at which their output is
their guarded input, bit for bit: EQ with every gain and Level at 0 dB (at
any frequency and Q), Isolator with Low, Mid and High at unity and nothing
killed (at any crossover), and Master Sat with Mix at 0 (whatever else is
set). Until 2026-10-06 their filters kept running there, so that leaving
the setting started from settled filters, and a parked effect cost as much
as a busy one. Now they idle there (owner's decision, 2026-10-05;
`include/fm1_fx_idle.h`):

- **Rest.** Once the effect has sat at its pass-through settings for 2 s,
  with every glide and crossfade landed, it idles: its filter states are
  cleared and a block is only the input guard (NaN to 0, ±16 clamped), whose
  output is the one it gave before, bit for bit. The two seconds keep
  rhythmic moves, a kill and back within a bar or a lock every few steps,
  from ever waiting for a wake. After a longer rest a move waits for the
  warm-up below, and a lock that leaves pass-through and comes back within
  the warm-up is not heard at all: a Master Sat Mix lock on one 16th step
  at 120 BPM (125 ms, under its 191 ms), an Isolator kill shorter than
  11 ms, an EQ Low Gain lock shorter than its 27 ms [verified:
  `fm1-idle-test` "short_lock", 2026-10-06]. The old build plays each.
- **Wake.** A setting that leaves pass-through wakes it at the next render,
  where every `set_param` change arrives. The filters start from rest and
  run on the input while the knobs that left pass-through are held where
  they were, so the output is still the input, bit for bit, for the
  warm-up: the time the slowest mode of the filters at the new settings
  takes to decay by e^−12 (−104 dB). Knobs turned while it was idle
  (frequencies, Qs, crossovers, Drive, Shape and the rest) land where they
  were set without a glide: nothing played them.
- **Fade.** Then the held knobs are released and glide or crossfade exactly
  as they always have, from filter states within that residue of the ones
  they would have held had they never stopped. The knob answers a warm-up
  later; there is no click and no jump.

| Effect | Held during the warm-up | The warm-up | At the defaults |
| --- | --- | --- | --- |
| EQ | each band's gain at 0 dB, each band for its own warm-up; Level glides at once (it needs no filter) | the band's section at 0 dB, at its frequency and Q | 27.2 ms for the low shelf (100 Hz), 3.9 ms for the bell (1 kHz), 0.5 ms for the high shelf (8 kHz); 77 ms for a shelf at 35 Hz |
| Isolator | the gains at unity and the crossfade at the input | the slower crossover's Butterworth sections | 10.8 ms (250 Hz); 33.8 ms with Low Xover at 80 Hz |
| Master Sat | Mix at 0 | the 10 Hz DC blocker on the residual; it also lets Glue's envelope catch up | 191 ms, at any setting and rate |

- **The warm-up's length** comes from a lower bound on the decay of a
  trapezoidal state-variable section's slowest mode (g = tan(πf/fs), k =
  1/Q; the bilinear transform's poles): g·k/(1 + g²) nepers per sample for
  k < 2, and 2·min(g/k, k/2g, g·k/2, 1/g·k) above. Over g from 10⁻⁴ to 10
  and k from 0.05 to 4 it never exceeds the exact decay and is within a
  factor of 3.3 of it [verified: `fm1-idle-test` "bound"], so a warm-up is
  never too short and at most about three times longer than it needs to
  be. The lengths are integers computed with single-precision +, −, × and
  ÷ only, so every build agrees on them, sample for sample.
- **Master Sat waits longer** because a shorter warm-up, the band filters'
  own 27 ms, left the residual's DC (Asymmetry) and Glue's envelope on bass,
  which ratchets up over several cycles, still settling as Mix rose: −30 dB
  of the input at Glue 1, Drive 18 dB and Asymmetry 1, against −74 dB after
  the DC blocker's 191 ms [verified 2026-10-06]. A Mix knob turned after a
  rest of seconds is not a performance gesture.
- **EQ settings that would need more than 0.1 s** (a band below about 27 Hz
  at Q 0.71, a bell below about 380 Hz at Q 10) never idle: EQ runs there
  as it always has, and tuning a band there while EQ is idle wakes it. That
  wake holds the bands for at most 0.1 s, not for their full warm-up (the
  bound gives 1.9 s for a bell at 20 Hz and Q 10), so that a gain turned
  soon after is not kept waiting; a gain turned then starts from a filter
  that began at the wake instead of one carried over from the old tuning.
  Both are
  still settling into the new tuning, so the output differs from the old
  build's as two transients do, not by a click: −23 dB of the peak for a
  30 Hz bell at Q 10 on a 30 Hz sine with the gain 0.12 s after the
  retune, −38 dB for a 20 Hz shelf at Q 0.3 on DC, with the output's
  largest second difference no larger than the old build's [verified:
  `fm1-idle-test` "hostile", 2026-10-06].
- **Away from pass-through nothing changes:** the same operations in the
  same order. `FM1_FX_IDLE=0` builds the effects without the idle path,
  which is the code as it was (checked against the sources before it, 40
  random 6 s streams per effect, rests included, bit for bit).

Measured [verified: `build/fm1-idle-test` and tests/test_engines_idle.py,
2026-10-06], against the same effects built with `FM1_FX_IDLE=0`:

- away from pass-through, 12 random 6 s streams per effect: the same output,
  bit for bit;
- 10 s at pass-through, idle from 2 s, on input with −0, subnormals,
  FLT_MIN, ±16, 1e30, NaN and infinities, every other knob turned to its
  ends while idle: the guarded input, bit for bit;
- wakes, 22 cases after 3 s at pass-through: until the release the input
  bit for bit; then the old output with the knob turned at the release,
  within −92.5 dB of the input's peak at worst (a +15 dB bell at 500 Hz,
  Q 10, on a 500 Hz sine; the others −109 to −156 dB), and bit for bit the
  same again within 1.2 s (15 of the 22 within 0.1 s). Master Sat's Glue envelope
  starts from rest: it attacks in 2 ms, but the 200 ms release of a peak
  older than the wake is missing, −96.6 dB at the defaults and −73.8 dB at
  Glue 1, Drive 18 dB and Asymmetry 1 on steady input. After a loud
  passage that ends just before the wake it is more: a 220 Hz burst at 0.9
  ending 5 ms before it, then the tone at 0.05, gives −43.0 dB of the
  burst's peak (about −18 dB of the quiet tone), a level difference that
  fades with the 200 ms release, not a click;
- hostile wakes (review, 2026-10-06): a band retuned lower and narrower
  64 frames into its own warm-up (−92.2 dB at worst, a 100 Hz bell at
  Q 10 on a 100 Hz sine), DC at 0.9 and full-scale sines at the slowest
  settings that still idle (−95.4 dB at worst, a 400 Hz bell at Q 10), and
  the cases above: in every one the output's largest second difference
  around the release is the old build's within 1 %, so no click; every
  knob re-sent every block at pass-through, and EQ's Mid Freq swept at
  Q 10 in and out of the settings that never idle, leave the input bit for
  bit; rests and wakes at 8, 96 and 384 kHz give the same bits at any
  block size and fill, and exact silence on silence;
- the same move after 1 s at pass-through, before the effect idles: the old
  output bit for bit, at once;
- rests and wakes at blocks of 1, 7, 64 and 4,096 frames and from any memory
  fill: the same bits; silence stays exact silence;
- a hash of each effect through rests, wakes and busy settings: the same
  from Apple clang (arm64), GCC 12 and 13 (x86-64), GCC 14 (i386, SSE) and
  Emscripten 6.0.10 (wasm32, Node) [verified, the last four in containers
  on the LAN build host], and clean under ASan and UBSan.

**The CPU saved,** per 64-frame stereo block of noise (`fm1-idle-test
--cost`, the best of ten 20 s runs, 2026-10-06, on a machine busy with
other work), at the defaults before and idle, and at a busy setting before
and after:

| Effect | At pass-through, before | Idle | Saved | Busy, before / after |
| --- | --- | --- | --- | --- |
| EQ | 1.89 µs | 0.031 µs | 98 % | 1.90 / 1.90 µs |
| Isolator | 1.95 µs | 0.031 µs | 98 % | 1.94 / 1.81 µs |
| Master Sat | 2.12 µs | 0.030 µs | 99 % | 2.30 / 2.30 µs |

That is Apple M1 Max with Apple clang; aeon (Ryzen 9 7940HS, GCC 12, in a
container) gave 0.62, 1.92 and 2.12 µs before and 0.07 µs idle. Busy, the
idle path's bookkeeping (a counter and a flag per frame, or per 8 frames in
EQ) is within the noise. On pi32v2 the guard is two comparisons and a store
per sample, about 400 operations per block, against about 7,700 for EQ,
13,000 and 3,600 comparisons for Isolator and 8,300 for Master Sat at its
defaults: about 2 %, 5 % and 2 % of a 240 MHz core freed while they sit at
pass-through [inferred]. A chain's budget still counts them busy, since a
knob can wake them at any time.

- **Memory:** the counters add 48 bytes to EQ (416), 16 to Isolator (256)
  and 16 to Master Sat (352), the same on 32-bit builds.
- **Not done:** EQ idles as a whole, not band by band: a flat band among
  busy ones keeps running, so the output away from pass-through stays the
  old one bit for bit. Tilt at 0 and Comp at Mix 0 keep their filters and
  detectors running too and are candidates for the same path (DJ Filter
  already skips its filter in the dead zone); not measured.

## Room

The reverb of Mutable Instruments Clouds, fed by the stereo diffuser Clouds
runs before it: `src/fx_room.cc` wraps `clouds::Diffuser` and
`clouds::Reverb` (Emilie Gillet, MIT), vendored unmodified in
`third_party/mutable/clouds/` (its `UPSTREAM.md`). It is the port that
notes/2026-10-02-delay-reverb-eq-gates-options.md §3.2 recommends. The
reverb is the Griesinger/Dattorro loop that Plate (Rings' copy) also uses,
smaller: 16,384 12-bit words (32 KB) against Plate's 32,768 16-bit words,
and a longest delay of 4,782 samples, 108 ms at 44,118 Hz against Plate's
143 ms.

    guard -> Blur (the diffuser: four all-passes a side) -> the reverb (L+R in,
             stereo out, full wet) -> Width = wet
    out = dry + Mix x (wet - dry)

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Mix | 0–1 (0.3) | Dry to wet, Plate's law. At 0 the input passes through bit for bit |
| 1 | Decay | 0–1 (0.5) | The loop gain per pass, 0.98 × Decay²: from none (the all-passes' own ring) to Clouds' longest |
| 1 | Damping | 0–1 (0.4) | The in-loop one-pole low-pass, coefficient 0.97 − 0.67 × Damping: Clouds' brightest (0.97) at 0, its darkest (0.6) at 0.55, darker beyond |
| 1 | Diffusion | 0–1 (0.8) | The all-pass coefficient 0.5 + 0.25 × Diffusion, as Plate's; 0.8 is Clouds' fixed 0.7 |
| 2 | Blur | 0–1 (0.5) | How much of the input passes Clouds' diffuser before it enters the room: the attack is smeared and the onset thickens |
| 2 | Width | 0–1 (1) | The wet's stereo width: 1 is the reverb's two outputs exactly, 0 their mean on both sides, exactly mono |

Every parameter is SMOOTH and MOD. Tail lengths at the defaults otherwise,
to −60 dB (T30 after a noise burst, 44,118 Hz) [verified, 2026-10-05]:

| Decay | 0 | 0.25 | 0.5 | 0.75 | 0.9 | 1 |
| --- | --- | --- | --- | --- | --- | --- |
| RT60 | 0.88 s | 0.94 s | 1.23 s | 2.4 s | 4.7 s | 16.5 s |

- **Where it departs from Clouds, and why.**
  - Decay is a square law from 0. Clouds' own range starts at 0.35, which
    already rings for 1.5 s: a hall, not a room. The square spends the
    lower half of the knob on room-sized tails. Its top is Clouds' 0.98.
  - Damping goes darker than Clouds' 0.6, to 0.3.
  - Clouds' reverb crossfades from the diffuser's output, at 0.54 × its
    Reverb knob, with a 1.2 post gain. Room runs it at full wet and
    crossfades from its own input, so Blur colours only the wet and Mix 0
    is a bypass. Width is ours.
- **Rate.** Clouds ran at 32,000 Hz, and the classes keep every delay and LFO
  in samples. At 44,118 Hz the room is 0.725 times the size and the LFOs run
  1.38 times as fast (0.69 and 0.41 Hz). As in Plate, the wrapper keeps what
  it owns in seconds: the loop gain becomes g^(32,000 / host) and the
  damping 1 − (1 − k)^(32,000 / host). Measured against the classes at
  32 kHz, a burst's tail decays at 1.04, 1.08, 1.20 and 1.49 times Clouds'
  dB per second at Decay 0.95, 0.8, 0.5 and 0 (1.38 uncompensated)
  [verified: tests/test_engines_reference_room.py]. Where the loop gain is
  small, the all-passes' own ring sets the tail, and it is not rescaled
  (nor is it in Plate), so a short room is that much shorter.
- **Without libm, the same bits everywhere.** The powers come from
  `src/fx_room_math.h` (a log2, an exp2 and a pow written here, within
  1.5e-6 of libm; `g^1` is `g` exactly). Contraction is off for the file
  under clang (`#pragma STDC FP_CONTRACT OFF`), the vendored code included.
  This matters more than in most effects: the loop stores 12-bit words, so
  a coefficient or a sample one ulp off sooner or later flips a truncation,
  and the tail then differs by whole LSBs. Without the pragma, Apple clang
  on arm64 fused multiply-adds and a 3 s render differed by up to 355 LSB
  from sample 1,346 on. With it, five renders (three host rates, blocks of
  64 and 7, every knob moved) hash the same from Apple clang on arm64, GCC
  14.2 on x86-64 (static musl) and Emscripten 6.0.10's WebAssembly under
  Node [verified, 2026-10-05, in containers on the LAN build host]; the
  browser module's parity scenarios agree (below).
- **Glide.** Mix and Width glide every frame (one pole, 5 ms) and land
  exactly on their targets. The classes' four coefficients glide on an
  8-frame grid counted from `create`, each step at most 3.6 % of the
  remaining distance (inaudible [inferred]); while one glides the classes
  run grid cell by grid cell, and once settled the rest of the block in one
  call (running them frame by frame while gliding took 2.5 µs per block
  rather than 1.8). The output does not depend on the host's block size
  (1, 7 and 64 frames, parameters changed mid-stream, in
  `build/fm1-room-test`).
- **Guard and silence.** The input guard of `mi_fx.cc` (NaN reads as 0,
  ±16 clamp, dry path included) keeps non-finite values out of the loop and
  the vendored float-to-int32 store far inside its range. The 12-bit store
  truncates towards zero, so with silent input the delay memory decays to
  zeros. The reverb's two damping states are private: below a coefficient
  of 0.5 one can stop on the smallest subnormal, which never reaches the
  memory (it did at Damping 0.8 and 1 after a minute of silence, two
  subnormal operations a sample [verified, 2026-10-05]). The wrapper
  flushes the wet below 1e-20, so the output reaches exact zeros, 0.9–3.1 s
  after full-scale noise stops [verified].
- **The diffuser's memory is swept.** Its all-passes store floats, and an
  all-pass holding the smallest subnormal writes back 0.625 of it, which
  rounds to the same subnormal: left alone, all 2,048 cells held a
  subnormal for good once a tail had gone, so every sample did subnormal
  arithmetic (slow on x86 without flush-to-zero; unknown on pi32v2). The
  memory is the wrapper's, so every 64 frames counted from `create`, between
  two runs of the classes, it sets the next 64 cells below 1e-20 to zero: the
  whole memory every 46 ms, the same at any block size, and no subnormal
  left after the tail. Output moves by at most 6e-17 (−325 dB), and only in
  tails whose diffuser cells have fallen below 1e-20; the glide hash, the
  reference renders and the parity scenarios are unchanged [verified:
  `diffuser_tiny` in `build/fm1-room-test` and a before/after comparison of
  five 40 s renders, 2026-10-05, found in review].
- **Reference renders.** `build/fm1-ref-room` (`test/ref_room.cc`) drives
  the two classes as Clouds' granular processor does (diffuser, then reverb,
  in place, in 32-frame blocks), with contraction off as in Room. Within
  quantisation (0.5 LSB): at 32 kHz with Blur 0, 0.5 and 1, with Clouds' own
  Reverb and Feedback settings at Clouds' own amount, Mix and Width against
  their model, at 44,118 Hz with the rate rule (the reference calls the same
  functions), and after Plate's stereo output. A test constant typed in
  double precision instead of float moved one coefficient by one ulp and
  missed by 4.4 LSB, so these matches are exact up to the 16-bit rounding.
- **Memory:** 41,200 bytes on a 64-bit desktop, 41,184 on 32-bit (clang
  laying the struct out for i386; 41,168 before the sweep's two counters)
  [verified]: 32,768 bytes of reverb words, 8,192 of diffuser floats, and
  the classes and the glide state. Rings
  shares one buffer among its effects; a host that allows one reverb at a
  time could do the same.
- **Cost, desktop only** (Apple M1 Max, noise in): 1.6 µs per 64-frame
  block, 0.11 % of the block, and 1.8 µs while a coefficient glides; Plate
  took 0.9 µs and Echo 2.1 µs in the same runs. The diffuser is 0.3 µs of
  it [verified, 2026-10-05]. About 1.8 × Plate, against the research's
  1 × estimate [inferred for pi32v2]; stage B measures it.
- **Browser:** the parity scenarios `room-chord-blurred` (every knob turned
  while a chord rings) and `plate-freeze-into-room` (after Plate, with
  Plate's Freeze and Room's Decay and Blur turned)
  (`sim/web/test/scenarios.json`) render the same, sample for sample, in
  fm1-render, the native app harness, the browser module under Node and
  render.js [verified: `sim/web/build-on-aeon.sh`, 2026-10-05].
- **Not yet:** a Freeze (Elements' recipe, notes §3.2, applies here too)
  and a measurement of the 12-bit loop's noise floor, which should sit
  above Plate's 16-bit one [inferred].

## Hall

A stereo hall reverb written here (`src/fx_hall.cc`, MIT): Jot's feedback
delay network (Jot and Chaigne, AES 90th Convention, 1991 [reported]) with
eight lines, as notes/2026-10-02-delay-reverb-eq-gates-options.md §3.2
recommends. That note's models for the structure were schwung-work's
"Voidspace" (MIT) and Geraint Luff's Signalsmith `basics` library (MIT); no
code is taken from either, nor from any other reverb. The input all-passes
are Schroeder's, with the coefficients Dattorro gives for his plate's input
diffusers (JAES 1997 [reported]); the 16-bit delay words follow Emilie
Gillet's FxEngine in Rings and Clouds, as Echo's do.

| Page | Parameter | Range | Default | What it does |
| --- | --- | --- | --- | --- |
| 1 | Decay | 0–1 | 0.5 | Decay time (to −60 dB) of the lows and mids, 0.2 s at 0 to 20 s at 1 on a log scale (0.2 × 100^Decay): 2 s at the default. Size does not change it |
| 1 | Size | 0–1 | 0.7 | Every line's length, × 1/4 at 0 to × 1 at 1 on a log scale: the first reflection after 7.4–29.5 ms, the lines 29.5–65.3 ms at 1. Turning it glides the lengths (0.1 s), which bends the pitch of the tail |
| 1 | Damping | 0–1 | 0.4 | How much faster the highs decay: up to 32 × at 1, above a crossover that falls from 10 kHz (0) to 1 kHz (1). At 0 the highs decay with the lows, less what the interpolation of moving delays takes (below) |
| 1 | Mix | 0–1 | 0.3 | Dry at full level up to 0.5, the reverb at full level from 0.5 (Echo's law). Mix 0 passes the input through bit for bit |
| 2 | Pre-delay | 0–150 ms | 20 | Delay before the reverb starts. Turning it glides (0.1 s) |
| 2 | Diffusion | 0–1 | 0.7 | The four input all-passes' coefficients, 0 to 0.75/0.625: at 0 the onset is a few distinct reflections, at 1 a smooth wash |
| 2 | Mod | 0–1 | 0.3 | Each line's length wanders on its own slow random walk (new targets at 0.73–1.37 Hz, smoothed at 1 Hz), up to ±1 ms at 1: a chorused, less metallic tail. Seeded, so renders repeat |
| 2 | Freeze | Off, On | Off | Holds the tail: the input fades out and the decay becomes an hour, over about 75 ms. Off lets the tail decay at Decay's rate |
| 3 | Width | 0–1 | 1 | 1: the two sides come from different lines, uncorrelated. 0: their sum on both sides, mono |
| 3 | Low Cut | 0–1 | 0.2 | A one-pole high-pass on the reverb's input, 10 Hz (0) to 1 kHz (1) on a log scale; 25 Hz at the default. It also keeps DC out of the lines |

How it works [verified: tests/test_engines_hall.py and
`build/fm1-hall-selftest`, 2026-10-05, unless marked]:

- **Signal path:** the input guard of `mi_fx.cc` → the mono sum → Low Cut →
  × (1 − Freeze) → pre-delay → four Schroeder all-passes in series (113,
  167, 263 and 401 samples) → into all eight lines with a fixed sign
  pattern. Each line is read with linear interpolation, passes a
  first-order shelf (its gain at DC for Decay, at Nyquist for Damping),
  and the eight are mixed by the 8 × 8 Hadamard matrix (a fast
  Walsh-Hadamard transform, scaled by 1/√8) and written back with the
  input added. The left output is lines 0, 2, 5 and 7, the right lines 1,
  3, 4 and 6, with alternating signs: no line is on both sides, so the
  sides are uncorrelated (−0.05 measured) and their sum, at Width 0, has
  all eight.
- **Lines:** 1,301 to 2,879 samples at Size 1 (primes about 12 % apart,
  15,986 in all), scaled by the host's rate over 44,118. Each line's gain
  is set from its length, 2^(−9.97 × length / (T60 × rate)), so every line
  loses the same decibels per second and the decay does not depend on the
  line. The Hadamard mix makes every line feed every other with the same
  weight, so the echo density grows faster than with an eight-line
  Householder matrix, which keeps three quarters of each line on its own
  path; the normalised echo density (Abel and Huang) reaches 0.9 by about
  0.1 s and stays near 1 [verified: a script on fm1-render's impulse
  response].
- **Decay is what it says.** Measured by Schroeder's backward integral
  between −5 and −25 dB after a burst of low-passed noise: 0.49, 2.03, 7.83
  s for 0.5, 2.0 and 7.96 s; 1.97 and 2.01 s at Size 0 and 1; 1.99 s at 96
  kHz. Within 2 %.
- **Stability:** the Hadamard mix is orthogonal, each shelf's gain is at
  most its DC gain g < 1 at every frequency (a first-order filter with a
  real pole and zero has a monotonic magnitude), and linear interpolation
  is a convex combination, so the loop gain is below 1 at every setting,
  Freeze included (an hour, not infinity), and every g is capped at
  1 − 2^−16. The 16-bit words saturate at ±2.0, 6 dB over full scale, as
  FxEngine's stores do, so nothing can grow without bound even while Size
  or Mod move the delays: ten seconds of noise into Decay 1, Size 1,
  Damping 0 and Mod 1 peak at 1.65 and settle; turning every parameter to
  any value, NaN and infinities included, with bad input mixed in, stays
  within the dry clamp plus 8 (four words a side).
- **16-bit words and the tail.** Truncating every store would lose half a
  word per pass and shorten long decays (8 s measured 6.9 s), so words of
  four or more round to nearest. Smaller words truncate towards zero, so
  nothing small recirculates for ever: after full-scale noise the tail
  reaches exact zeros (3.3 s at Decay 0.6; 12–22 s at Decay 1 across Size,
  Mod and Damping), with no subnormals. The cost: below about −57 dBFS a
  tail stops following Decay and fades out within a second or two (from a
  full-scale start at Decay 1, 53 dB of clean decay) [verified: probes of
  the tail's level per second, 2026-10-05].
- **Moving delays and the highs.** The lines read between samples whenever
  Size is not 1 or Mod moves them, and linear interpolation then dulls the
  highs on every pass: a built-in air absorption above about 5 kHz, which
  Damping adds to. Echo's reasons for linear interpolation hold here: it
  has no feedback of its own and never exceeds its inputs under any
  modulation (the research note's rule for delays, §2.3).
- **Freeze** fades the input out, lengthens the decay to an hour, sets
  each line to a whole number of samples that its walk no longer moves (no
  interpolation loss) and makes every store round to nearest, all as one
  glide: 95 % there in 75 ms, exactly there by 0.3 s. From then on the input
  gain is exactly zero: nothing played reaches the tail (two renders with
  different input after that point are identical). The held tail lost 0.17 dB in 10 s; a
  switch on or off makes no jump larger than the wash's own. Off, the tail
  decays at Decay's rate.
- **Determinism:** no libm (`nm` shows no math symbols, only `bzero`): the one exponential
  needed for coefficients is a polynomial in the file, every operation is a
  single IEEE add, multiply or divide, and `#pragma STDC FP_CONTRACT OFF`
  stops clang fusing them (without it, arm64 output differs). The output is
  bit-identical across -O0, -O2, -O3 and -Os and between arm64 and x86-64
  builds [verified: a hash of 3,000 blocks with parameter changes,
  2026-10-05]. Slow controls update every 16 samples, counted from create,
  and delays ramp sample by sample between updates; Mix and Width glide
  per sample. Any block size gives the same output, and values set before
  the first block apply from its first sample.
- **Memory:** two rings of 16-bit words whose sizes are powers of two, so
  every access is one mask, as in FxEngine: 16,384 words for the lines
  (15,986 plus each line's ±1 ms of modulation) and 8,192 for the
  pre-delay and the all-passes, sized for the host's rate. 49,888 bytes at
  44,100 and 44,118 Hz, 736 of them state; the state holds no pointers and
  is 736 bytes on i686, armv7 and x86-64 alike [verified: cross-compiled].
  At 48 kHz both rings need the next power of two: 99,040 bytes.
- **Cost, desktop only:** about 3.0 µs per 64-frame block on an M1 Max
  (best of 15 under load), against Plate's 0.9 µs and Echo's 2.1 µs: 34,500
  instructions and 9,100 cycles per block against Plate's 13,200 and 2,700.
  About 2.6 Plates by instructions, where the research note guessed one.
  The eight interpolated reads, the eight rounding stores and the four
  all-passes make most of it. Running the lines at half the rate (the
  research note's "derez" idea) would roughly halve both the cost and the
  lines' memory, at the price of the top octave [inferred]. Stage B
  measures pi32v2.
- **Not yet:** a reset call to drop the tail without re-creating the
  instance, and a tempo-synced pre-delay; both wait on the host.

## Gate

A noise gate with a Duck mode (`src/fx_gate.cc`, our own code, MIT), for
taming a sound's tail, gating a reverb, or pulling one sound down while a
key plays. Its controls follow the operator manuals of Drawmer's DS201 and
DS301 gates [reported: notes/2026-10-02-delay-reverb-eq-gates-options.md
§7.1]: Threshold, Attack, Hold, Decay, Range, a Duck mode, key filters with
Listen, and the DS301's retrigger inhibit (Lockout here). Drawmer is
credited as the inspiration only: no circuit or code is taken, the
algorithm is ours, and no control is named for a maker. Return
(hysteresis) and Lookahead are additions neither manual has. Stereo-linked:
one detector and one gain for both channels.

    key (the input itself, or a key buffer) -> guard -> Key HP -> Key LP (per channel)
        -> Link -> level (a peak: instant up, 4 ms down) -> Schmitt trigger
        -> the gate (Lockout, Attack, Hold, Decay) -> attenuation in dB -> gain (Mode)
    input -> guard -> look-ahead line -> x gain = gated;   out = gated, or the key (Listen)

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Threshold | −80 to 0 dB (−40) | The key level that opens the gate |
| 1 | Attack | 0–1,000 ms (0.5) | How fast it opens: the attenuation falls 80 dB per Attack, linear in dB, so from Range −80 dB the gate is open after Attack. 0 is one frame (22.7 µs; two frames from Range −90). A started attack always completes |
| 1 | Hold | 2–2,000 ms (50) | How long it stays open after the key has fallen below Threshold − Return. It reloads while the key stays above |
| 1 | Decay | 2–4,000 ms (150) | How fast it closes: the attenuation rises 80 dB per Decay, so from Range −40 dB it closes in half the Decay |
| 2 | Range | −90 to 0 dB (−80) | The closed level. −90 is off: silence. 0 leaves the signal untouched, bit for bit, in either Mode |
| 2 | Return | 0–12 dB (4) | Hysteresis: the gate opens above Threshold and the key counts as gone only below Threshold − Return, so a key hovering at the threshold does not chatter |
| 2 | Mode | Gate, Duck (Gate) | Duck turns the gain over: the key pulls the signal down to Range over Attack, and it comes back over Decay after Hold. A change crossfades the two gains over 5 ms |
| 3 | Key HP | 20 Hz–10 kHz (20: out) | A 12 dB/octave high-pass on the key only, so low spill (a kick under a snare) does not open the gate. At 20 Hz it is out of the path |
| 3 | Key LP | 200 Hz–20 kHz (20 k: out) | A 12 dB/octave low-pass on the key only (hi-hat spill). At 20 kHz it is out |
| 3 | Listen | Off, Key (Off) | Key sends the filtered key to the output, to hear what the gate is listening to while setting the filters. Crossfades over 5 ms |
| 4 | Lockout | 0–5,000 ms (0) | After the gate opens, a new rise of the key cannot re-open it for this long (rises while it is still open keep it open). Stops a ringing drum or a flam retriggering it |
| 4 | Lookahead | 0–5 ms (0) | Delays the audio, not the key, so the gate opens before the transient that opens it arrives. It is also the effect's latency: 88 frames at 2 ms and 44,118 Hz. A change crossfades to the new delay over 5 ms, as the Limiter's does |
| 4 | Link | Max, Sum, Left (Max) | What the detector hears of a stereo key: the louder channel (Max; anti-phase content still opens it, and Comp detects the same way), the mono sum 0.5 (L + R) (Sum), or the left only (Left, the DS201's link). Listen hears the same: the key in stereo, or the mono sum or left on both channels. Glides over 5 ms |

How it works [verified: tests/test_engines_gate.py and `build/fm1-gate-test`,
2026-10-05, unless marked]:

- **Detection.** The key passes the input guard, then Key HP and Key LP:
  Zavalishin's trapezoidal state-variable filter, Q = 1/√2 (Butterworth),
  its cutoff prewarped so −3 dB falls on it exactly. Measured through
  Listen at 91 points from 20 Hz to 16 kHz on seven settings, the pair is
  within 4 × 10⁻⁵ dB of the bilinear Butterworth formula down to −70 dB, and
  sample by sample within 1.6 × 10⁻⁷ of a float64 reference of the two
  filters (the note's §7.10 test 4). The level is a peak follower, instant
  up and falling with a 4 ms time constant, so a low note's waveform does
  not read as gaps: a key that stops dead takes 4 ms × ln(level / (Threshold
  − Return)) to count as gone, 771 frames (17.5 ms) for −6 dBFS at the
  defaults.
- **The key LP delays the trigger,** as the DS201's manual says: a key step
  crossed a −6 dB threshold 3, 10 and 40 frames late through 4 kHz, 1 kHz
  and 250 Hz, within a frame of the float64 reference and of the filter's
  group delay at DC, √2 / (2π fc) (2.5, 9.9 and 39.7 frames).
- **The gate's states:** closed (at Range), attack, open, decay. A rise of
  the Schmitt trigger re-opens a closed or decaying gate, unless it comes
  within Lockout of the last opening; then that whole key episode is
  ignored (until the key falls and rises again). A rise while the gate is
  open only keeps it open. Hold counts down from the moment the key falls
  below Threshold − Return and reloads while it is above; the decay starts
  when it runs out, and an attack under way completes first.
- **Ramps in dB.** "Decay 4 s" is 80 dB in 4 s, from wherever the gain is,
  as a gain cell's exponential response makes it; the gain is 10^(−a/20)
  for the attenuation a, exactly 1 when open and exactly 0 at Range −90
  when closed. A ramp is computed from where it started (start ± frames ×
  rate), not by adding a step each frame, so a 4-second decay ends on its
  frame. Measured: Attack 0.5, 2, 10 and 100 ms open in 23, 89, 442 and
  4,412 frames (⌈Attack × fs⌉), −60 dB a quarter of the way and −40 dB half
  way; Hold 2, 50 and 500 ms hold 88, 2,206 and 22,059 frames; Decay 100
  and 400 ms close from −80 dB in 4,412 and 17,648 frames, and from −40 dB
  in 8,824.
- **Chattering.** A 200 Hz tone decaying at 50 dB per second through the
  −40 dB threshold over noise peaking near it opened the gate 9 times with
  Return 0 and Hold 2 ms; Return 4 dB, Hold 50 ms or Lockout 300 ms bring
  that to 1, 1 and 2.
- **Look-ahead** delays only the audio, in a line of 5 ms of frames, so the
  gate's gain leads the audio by the delay: a burst after silence at Range
  −90 and Attack 0.5 ms comes out whole, bit for bit, with Lookahead 2 ms,
  and with its first half millisecond cut without. The latency is the
  delay rounded to a frame, checked at 44.1, 48, 96 and 192 kHz (capped at
  510 frames: 2.66 ms at 192 kHz), and `fm1_gate_state` reports it for the
  panel. The gate's OPEN state and its KEY level run on the key's time,
  the delay ahead of the audio.
- **Bit-exact where it can be.** With Range 0 the output is the input, bit
  for bit, whatever the key and Mode; an open gate's gain is exactly 1, so
  the renderer's noise passes untouched once the 0.5 ms attack is over;
  silence in is exact silence out at any setting.
- **Guards.** The input and the key pass the Mutable effects' guard (NaN
  reads as 0, ±16 clamps), so nothing non-finite reaches a state. 100
  frames of NaN in the key never open the gate; infinities and 1e30 are
  clamped to 16 and close it on the very frame a clean key of 16 does: no
  latched hold or level. With the key filters out, half a second after a
  fault in the renderer the output is the clean render's, bit for bit;
  with them in, within one 16-bit step.
- **Changes.** Threshold, Return, Range, the key filters' cutoffs (in
  octaves) and their in/out, Mode, Listen and Link glide over 5 ms, sample
  by sample; a glide lands on its target once within 10⁻⁶ of it, so its
  landing is under −100 dB (Fold's and Comp's 10⁻⁴ would be −60 dB on
  Range, which a route retargeting every tick would repeat as zipper
  noise). Attack, Decay, Hold and Lockout are rates and counts that take a
  new value at once (a ramp restarts from where it is, a running count is
  cut to the new length), and Lookahead crossfades its delay. Any block
  size gives the same output (64, 7 and 1 frames, with all 13 parameters
  changed mid-stream), and Mode, Listen, Link and Lookahead turned every
  third block step the output no more than holding them does, plus a 5 ms
  crossfade's allowance (the owner's switch rule, through
  tests/test_engines_fx_switches.py's harness).
- **Determinism.** No libm: 2^x and log2 are `fx_comp_math.h`'s (Comp's
  polynomials, the start of the shared libm-free maths the note asks for),
  tan is a polynomial in the file (sin and cos by their series, within
  6.1 × 10⁻⁷ of libm's on [0, 0.45π]), and `#pragma STDC FP_CONTRACT OFF`
  keeps clang from fusing multiply-adds. The object calls nothing outside
  itself but `memset` (`bzero` on macOS). Three 2-second renders with every parameter changed
  mid-stream hash the same from Apple clang on arm64, GCC 12 on i686 (SSE)
  and x86-64, and Emscripten 6.0.10's WebAssembly under Node [verified,
  2026-10-05; pinned in tests/test_engines_gate.py].
- **Memory:** a 368-byte struct with no pointers, then 5 ms of line (8
  bytes a frame, at most 510 frames): 2,144 bytes at 44,118 Hz, 2,304 at
  48 kHz, 4,224 at 96 kHz and 4,464 at 102 kHz and above, the same on i686
  and x86-64 [verified: GCC 12 in a Linux container, 2026-10-05]. The note
  estimated 2.2 KB.
- **Cost, desktop only** (Apple M1 Max, `fm1-gate-test --cost`, noise
  bursts so the gate opens and closes, best of three): 0.51 µs per 64-frame
  block at the defaults, 0.99 µs with both key filters in and 2 ms of
  look-ahead, 1.7 µs while Threshold glides every block (two exponentials
  per frame): 0.04–0.12 % of the 1.451 ms block; Plate took 0.90 µs in the
  same run [verified, 2026-10-05]. Steady, the gate computes no
  exponential at all; while it ramps, one per frame (two while Mode
  crossfades). For pi32v2, JieLi's clang compiles it without a warning to
  5.9 KB of code at `-O2` (3.6 KB at `-Oz`) and 0.8 KB of constant data,
  and emits the same code with contraction off and fast (nothing fused)
  [verified: compile only, 2026-10-05].
- `build/fm1-gate-test` (`test/gate_test.cc`) renders frame by frame and
  reads the state, for the timing, Range, Return, Duck, Lockout, latency,
  the onset, the filters, Link, the key LP's delay, chattering, bad keys
  and an external key; plus a 20 s sweep of every parameter to any value
  (NaN and infinities included) between random blocks, a quarter of them
  keyed from a separate noise, and the host rates (8–384 kHz). It links
  the effect built once more with `FM1_GATE_PROBE`, which adds an entry
  point to its tan for the check against libm.

**Hooks for the key and modulation stages** (note §7.3–§7.4; nothing in
the hosts uses them yet). Today every host keys the Gate from its own
input.

- **An audio key:** `fm1_gate_render_key(instance, io_lr, key_lr, frames)`
  (`include/fm1_gate.h`) renders with `key_lr` as the key: stereo,
  read-only, valid for the call, never stored (the instance holds no
  pointer, so 32- and 64-bit sizes stay equal). It has the signature the
  note's `fm1_fx_ext_t.render_key` has, so that struct can point at it.
  `key_lr` NULL keys from the input: `render_key(NULL)` is `render`, bit
  for bit, and so is a key that is a copy of the input [verified: the
  note's §7.10 test 1]. Listen hears the key given. A click track as the
  key opens the gate on noise for each click and leaves it at Range (−60
  dB here) between them.
- **A matrix trigger:** the Schmitt trigger's output (`key_high` and its
  rise) is where a gate input joins, in one place in `GateProcess`: Trig
  "Gate" would replace it, "Either" OR into it, so Hold, Attack, Decay and
  Lockout apply to a trigger as to the key (note §7.3). Trig and Key, the
  note's other two controls, take uids 14 and 15 when a host can feed them
  (Trig on page 2's free knob, Key on page 3).
- **The state, for modulation sources and the panel:** `fm1_gate_state`
  reads the gain the last frame got, the envelope (0 closed to 1 open,
  linear in dB, in either Mode: the note's ENV), the detector's level
  (0..1: KEY), the OPEN gate (from a trigger until Hold runs out), the
  Schmitt trigger's state, and the latency in frames. Read on the audio
  task between renders, after the last piece of a split block.

## Squash

Three small compressors in one effect (`src/fx_squash.cc`), ports of Chris
Johnson's Airwindows plug-ins Pop3, Pressure4 and ButterComp2 (MIT,
`third_party/airwindows/`, pinned at `e718c9b`) into single precision with
no libm (owner decisions, 2026-10-05; notes/2026-10-02-filters-dynamics-options.md
§3 and decision 9). Comp's Threshold, Ratio, Attack and Release do not fit
Pressure4 or ButterComp2, which have no timing knobs, so they are Types of
a separate effect rather than Characters of Comp. The Types are named for
what they do, after the 2026-10-02 naming rule: **Snap** (after Pop3),
**Mu** (after Pressure4) and **Split** (after ButterComp2). Each knob is the
plug-in's own, as a time or a level where the plug-in's 0..1 knob maps onto
one, with the same arithmetic underneath; Output and Mix are ours, for every
Type.

    guard -> the Type's gain per channel (Snap, Mu or Split; two while a Type fades)
          -> out = dry x (1 - Mix) + dry x gain x Output x Mix

| Page | Knob | Range (default) | Snap | Mu | Split |
| --- | --- | --- | --- | --- | --- |
| 1 | Type | Snap, Mu, Split (Snap) | | | |
| 1 | Squash | 0–1 (0.5) | threshold (1 − Squash)⁴: −24 dB at 0.5 (Pop3's A = 1 − Squash) | threshold t = 1 − 0.95 Squash (Pressure) | lift into the detector 14 × Squash dB (Compress) |
| 1 | Attack | 1–200 ms (25.5) | towards T/\|x\| over this time (C Atk: 11.3–125 ms) | – | – |
| 1 | Release | 1–3,000 ms (46.8) | back towards 1 over this time (C Rls: 11.3–1,145 ms) | the release when quiet: Speed, release = this × rate samples (B = 0.2 is 1,092 ms) | – |
| 2 | Ratio | 0–1 (0.5) | how far the gain follows the state: R = 1 − (1 − Ratio)² (C Ratio) | – | – |
| 2 | Shape | −1 to 1 (1) | – | Mewiness: the gain c² blended with c above 0, √c below | – |
| 2 | Output | −24 to +24 dB (0) | after the compressor | (Output Gain) | (Output, which reached +6 dB) |
| 2 | Mix | 0–1 (1) | dry and compressed | | (Dry/Wet) |
| 3 | Gate | −80 to 0 dB (−80: off) | a sample over it opens the gate (Thresld E: E⁴) | – | – |
| 3 | Gate Depth | 0–1 (0.5) | how far it closes: Q = 1 − (1 − Depth)² (G Ratio) | – | – |
| 3 | Hold | 0–1 (0.5) | the gate's state starts at π/2 (Hold + 1)⁴ and closes under π/2, so Hold and Gate Rel set how long it stays open (G Sust) | – | – |
| 3 | Gate Rel | 10–12,000 ms (365.6) | how fast that state falls (G Rls: 11.3 ms–11.4 s) | – | – |

- **Snap** (Pop3): per channel, a state p moves towards T/|x| by the
  attack while |x| is over the threshold T, and towards 1 by the release
  otherwise; the gain is (1 − R) + p R. A stereo link pulls the higher state
  down by the attack (Pop3's order: the left first, then the right if it is
  now the higher). A gate shared by both channels: any sample over Gate sets
  its state to the sustain, which then decays by Gate Rel; under π/2 the gain
  is multiplied by (1 − Q) + sin(state) Q, a quarter-sine close. It can only
  turn the sound down.
  - *The link in float.* With the left state just above the right (within
    one pull), Pop3 pulls both on every frame: the gap shrinks by
    (1 − attack) a frame, and the release balances the pull at
    p = rel / (atk + rel), so the gain holds there (−6 dB at a fast
    attack and release) until the two states are equal. In double that takes
    as long as the gap needs to reach the last bits of p (then it can stall
    on a double's rounding). Kept as two floats it never ended: each state
    stalled on a fixed point of its own float rounding, a few ulps apart, and
    the gain stayed at the hold for good [verified: a float32 emulation
    against double, 2026-10-05]. So Snap keeps the lower state m and the gap
    d ≥ 0, which keeps its precision when tiny, and a gap under 10⁻¹⁴ m is
    equality: the hold ends about where a double's would.
- **Mu** (Pressure4): one gain for both channels. sense = max(|L|, |R|) / t
  is compared with t; above it the state c moves towards max(t / sense, t)
  by a one-pole of √speed samples, under it towards 1 by one of speed²
  samples; speed follows sense × release + √release, so after a loud passage
  Mu recovers slowly (Pressure4's programme-dependent "bloom"). The gain is
  Shape's curve of c. Pressure4 lifts the input by 1/t before its detector
  and leaves it lifted, then saturates the result with a sine; Mu detects the
  same way but divides the lift out again and has no sine (the note's
  verdict: the lift raised quiet passages and the noise floor by up to
  26 dB, and the sine was its guard against the overs that made). So, like
  Snap, Mu only turns down, and turns down a lot at high Squash: a −6 dBFS
  sine loses 6.8 dB at Squash 0.5, 17.9 at 0.75 and 49 at 1 (Shape 1 is
  Pressure4's Mewiness 1, the gain c²); Output brings it back.
  Pressure4's steps, (c (n − 1) + target) / n, are written c + (target −
  c) / n: the same in exact arithmetic, and in float they keep the target's
  share where n (speed², up to 10¹⁵) would swallow it.
- **Split** (ButterComp2): per channel, the input lifted by 10^(14 Squash /
  20) feeds two one-pole targets, the mean of (1 + x)² for the positive side
  and (1 − x)² for the negative, and two gains that follow 1 / target² by the
  same pole, each only while the input is on its side, in two sets used on
  alternate samples (ButterComp2's "flip"). The gain applied blends the
  positive and negative gains of the set in turn by where the sample sits
  between −1 and 1, and is divided by 1 + (lift − 1) / 1.5. The pole is
  0.012 Squash / 135 / (1 + |last output|) per 44.1 kHz sample: no timing
  knobs, and slower while the output is loud. It lifts a little at low
  settings (+0.4 dB at 0.25 on a −6 dBFS sine, at most +2.7 dB on bursts).
  Its targets are held at 0.25 or more (gains of 16 or less): under a
  negative offset beyond −1 the positive target runs towards 0 and its gain
  to infinity in ButterComp2; ordinary audio never reaches the floor.
  - *Squash 0 is a bypass* (ours, review 2026-10-06). The pole is
    proportional to Squash, so at 0 ButterComp2 freezes its gains wherever
    they are: Split turned from Squash 1 to 0 stayed 5 dB down for good,
    and a lock of Type Split with Squash 0 while Mu held a sine 32 dB down
    kept it there for good (Split starts from the gain in force, below).
    Under Squash 0.05 the gain applied is blended towards 1 by Squash / 0.05
    and the states are pulled to rest over 20 ms × 0.05 / (0.05 − Squash):
    Squash 0 passes the input bit for bit whatever came before, from the end
    of the knob's ramp and the Type's fade, and turned up again Split starts
    afresh (−0.002 dB against a new instance) [verified: `fm1-squash-test`'s
    `split_low`]. From 0.05 up this does not run.
- **Taken out** (the porting rules of the note, §3): the plug-ins' denormal
  dither on every sample and ButterComp2's "live air" residue, whose state is
  function-static (shared by every instance). So silence in gives exact
  silence out; the states flush to 0 under 10⁻²⁰. sin, pow and sqrt are a
  Taylor polynomial (within 6 × 10⁻⁸ on 0..π/2), multiplications, and a
  square root from the float's bits with three Newton steps and one more on
  the root.
- **Against the upstream loops** [verified, 2026-10-05]: the four plug-ins'
  loops, copied into `third_party/airwindows/oracle/airwindows_oracle.cc` in
  double with only the noise removed (and Mu's two changes above), run in
  the gcc:12 container on aeon (`run-on-aeon.sh`; nothing of theirs runs on
  a developer's machine), give tests/fixtures/squash-oracle.json: every
  61st frame of 1.5 s of drums, a stepped sine and a hot two-tone mix at
  44,100 Hz. tests/test_engines_squash.py holds ours to them. The residual
  (RMS of the difference over the RMS of theirs): Mu −102.5 and −117.3 dB,
  Split −104.1 and −116.2 dB (float against double), Snap −62.9 and
  −78.2 dB, and −29.2 dB for a third Snap case with a fast attack and
  release, where Pop3's link holds (above) end at different times in
  double and here; the Limiter's Round mode −140 dB against ClipOnly2.
- **Type changes.** A new Type starts from the gain the old one was
  applying (its state set to give that gain: Snap's p and an open gate, Mu's
  c through Shape's curve with its speed at rest, Split's four gains and two
  targets), the two run together, and the output crossfades from the old to
  the new over 5 ms; a change asked for meanwhile waits for the fade's end.
  So Type is lockable and modulated (rounded) without a step: changed every
  1,984 frames on a loud sine and on bursts, no step between samples larger
  than with any Type held (0.44 against 2.13), and turned every third block
  by tests/test_engines_fx_switches.py.
- **Contracts:** the input guard of `mi_fx.cc` (NaN to 0, clamp to ±16);
  parameters through `fm1_param_clamp`; every FLOAT SMOOTH through
  `fm1_smooth.h` (a 2.5 ms ramp, a step a frame), so any block size gives
  the same output; values set before the first render apply at once.
  Silence in is exact silence out at every Type, through Type changes.
  Hostile input (NaN, infinities, 10³⁰, +32 dBFS noise) stays finite and
  bounded. Renders with every parameter and the Type changing at fixed
  frames give the same bits in blocks of 64, 1, 7 and random sizes and from
  memory filled four ways [verified: `fm1-squash-test`; the browser's parity
  scenario `dyn3-squash-transient` runs the WebAssembly build, identical to
  the native ones].
- **Memory:** 400 bytes (no pointers, so the same on 32-bit builds
  [inferred]). **Cost** (Apple M1 Max, noise, `fm1-squash-test --cost`):
  1.4 µs per 64-frame block for Snap with its gate, 1.1 µs for Mu, 2.0 µs
  for Split; 0.08–0.14 % of the block [verified, 2026-10-05]. Per frame,
  Snap divides twice when over its threshold, Mu three times and takes one
  or two square roots, Split divides six times; two Types run for the 5 ms
  of a fade. Stage B measures pi32v2.

## Transient

A transient shaper of our own (`src/fx_shaper.cc`, MIT), on the
differential-envelope principle: two followers of the level that disagree
only where it changes (owner decisions, 2026-10-05; the note's FD3). The
law, two followers, is the one the note took from legsmechanical's Bus
Driver (MIT, `36b6788`); its measured tables of a commercial unit were not
used, and no code was taken from it or anywhere. Stereo-linked.

    guard -> x = max(|L|, |R|) -> fast follower F of x (at once up, 40 ms down)
                               -> slow follower S of F (Window up, Tail down)
          -> D = 20 log10(F / S), clamped to +/-12 dB
          -> gain dB = Attack x D where D > 0, Sustain x (-D) where D < 0, + Output
          -> out = dry x (1 + Mix (gain - 1))

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Attack | −100 to +100 % (0) | How much the onsets are lifted (+) or softened (−) |
| 1 | Sustain | −100 to +100 % (0) | How much the decays are lifted (+) or cut (−) |
| 1 | Window | 5–100 ms (20) | The slow follower's rise: how long an onset counts as the attack |
| 1 | Tail | 50–2,000 ms (400) | The slow follower's fall: how long a decay counts as the sustain |
| 2 | Output | −24 to +12 dB (0) | Gain after the shaper |
| 2 | Mix | 0–1 (1) | Parallel: 1 + Mix (gain − 1) |

- **The law, in dB.** At an onset F runs ahead of S; in a decay F falls
  under it; on a steady sound they agree. At +100 % Attack an onset comes out
  at x + (F − S), so it rises twice as steeply against the slow envelope; at
  −100 % at about S, as slowly as Window lets the slow follower rise. At
  +100 % Sustain a decay comes out at about S, falling as slowly as Tail; at
  −100 % about twice as fast. The clamp keeps either share within 12 dB
  (an onset out of silence would ask for 100).
- **S follows F, not x** (review, 2026-10-06). On a steady tone x swings
  from 0 to the peak every half cycle, and a follower of x settles where
  its rise and fall balance, which depends on its own two times: with S on
  x, Window 100 ms and Tail 50 ms sat 4.8 dB under F, so Attack +100 %
  lifted every steady tone by 4.8 dB (2 dB at Window 20, Tail 50). F is
  already near the peaks, so S on F settles on F whatever Window and Tail
  are, and only F's ripple is left. F rises at once (it rose over 1 ms):
  after a held tail, with S still high, Sustain's lift then ends as soon as
  a new note passes S, rather than lifting the note's first millisecond by
  up to 12 dB, over its own peak.
- **Measured** [verified: `fm1-squash-test`'s `shaper`, 2026-10-06]: on a
  60 Hz hit with a 1 ms rise and a 150 ms decay at −6 dBFS, Attack +100 %
  lifts the first 10 ms by 7.6 dB and −100 % softens them by 7.3 dB,
  leaving the tail (100–300 ms) alone; Sustain +100 % lifts the tail by
  6.8 dB and −100 % cuts it by 5.6 dB, leaving the onset alone. A steady
  sine at both knobs +100 % moves by 0.02 dB at 1 kHz and 0.14 dB at
  100 Hz; anywhere on Window and Tail (both ends), at 40 Hz to 1 kHz with
  either knob at either end, by 0.31 dB at most, at 40 Hz (F's ripple).
- **The centre is a bypass.** Attack and Sustain at 0 and Output at 0 dB
  give a gain of 2^0, exactly 1, and 1 + Mix × 0: the input bit for bit at
  any Window, Tail and Mix, and again once turned knobs have come back. The
  followers keep running, so a turned knob starts from where the music is.
- **Contracts and determinism** as Squash's: the guard, every parameter
  SMOOTH (`fm1_smooth.h`), any block size and memory fill the same bits,
  silence to silence, finite on hostile input; log2 and 2^x from
  `include/fm1_math.h`, contraction off, no libm.
- **Memory and cost:** 144 bytes; 1.3 µs per 64-frame block on an Apple M1
  Max with both knobs away from the centre (two follower steps, a divide, a
  log2 and a 2^x a frame), 0.09 % of the block; at the centre the log and
  the exponential are skipped [verified, 2026-10-05].

## Parameters (engine API v2 and v3)

Since API v2 (docs/15 stage S7a, docs/13 M2), `fm1_param_t` carries four
more fields after its name, type, range, default, enum names and page
(`include/fm1_engine.h`). API v3 (2026-10-05, [below](#engine-api-v3))
widened `flags` to 16 bits, keeping every v2 bit, and added LOG and the dB
unit:

| Field | What it is |
| --- | --- |
| `uid` | 1–4,095, unique in its engine and never changed or reused. It is what a sequencer lock, a modulation route (docs/16) or a preset stores, so reordering or extending a table moves nothing. A uid means something only together with its engine's id |
| `flags` | 16 bits (8 in v2): `FM1_PARAM_LATCH`, `SMOOTH`, `NOLOCK`, `MOD`, `INPUT`, `POLY` and `LOG`, below; 0x80 is kept for KEYSRC (the side-chain stage) |
| `unit` | `FM1_UNIT_NONE`, `SEMI`, `MS`, `HZ`, `PCT`, `DEG` or `DB` (v3): the unit the value itself is in |
| `abbr` | Up to 6 characters, for matrix rows (docs/16 §5.3). Distinct within an engine, and still distinct cut to 5, for rows that add a unit prefix |

**Uids.** Native engines and effects number their parameters from 1, in the
order they first shipped; a new parameter takes the next free uid. Macro
Heavy keeps Macro's uids for the 11 parameters both have (Word Speed is 12),
so a lane survives a swap between the two; its table is the one where a uid
is not the index plus 1, which catches a host that uses one for the other.
The Schwung adapters derive each uid from the module's own key for the
parameter: 0x800 plus the key's 32-bit FNV-1a hash folded to 11 bits
(`KeyUid` in `src/schwung_shim.h`, a C++11 `constexpr`, so the tables stay
constant data). A module that reorders or extends its parameters keeps every
uid, and the two ranges never meet. `tests/fixtures/param-uids.json` pins
every uid and flag, the Schwung modules' hidden parameters included, and
`tests/test_engine_params.py` fails when one changes. A removed parameter
moves to the fixture's `retired` list, so its uid is never given out again.

**Flags.** They describe the parameter; hosts act on them.

| Flag | Meaning | What a host does |
| --- | --- | --- |
| LATCH | The engine reads it at note-on: a change reaches the notes that start after it, never a sounding one | Nothing more: at one frame, locks come before note-ons (D2, engines/seq.md) |
| SMOOTH | Continuous and read every block | Nothing: the engine ramps a change over 2.5 ms ([below](#smooth-the-ramp-inside-the-engines)) |
| NOLOCK | A change is destructive: it rebuilds voices, clears a buffer or moves the edit focus | A lock on it is refused and counted (engines/seq.md, Host contract); never a modulation destination |
| MOD | Accepts modulation (docs/16 §2.2). Every FLOAT has it by default; an ENUM only when it says so, and is then rounded. Never with NOLOCK | The modulation matrix, from docs/16 stage MG1 |
| INPUT | A bare signal input: FLOAT, −1..1, default 0, hidden from the knob pages | Modulation modules only; no engine has one |
| POLY | Takes a per-note offset: the engine keeps one per sounding voice ([below](#per-note-offsets)). FLOAT only, always with MOD | Per-voice modulation (docs/16 §6.3, stage MG9) sends it with `set_param_note` |
| LOG (v3) | Pitch- or time-like: a FLOAT in Hz or ms with 0 < min < max. Stored, shown and saved in its unit, but it moves on a log scale ([the LOG law](#the-log-law)) | Knob detents, bars, 7-bit locks and modulation work on its position, in ratios and octaves; the engine sees values in its unit as before |

Every FLOAT parameter here is SMOOTH and MOD (`FM1_PARAM_CONTINUOUS`),
except Sophie's, which are LATCH and MOD: a triggered voice copies its pad's
patch (`sophie.c`, `trigger_voice`), so Sophie reads all of them at note-on.
The Limiter's Lookahead is SMOOTH and MOD like any FLOAT: it sets the
effect's latency, but a change crossfades between two delays, each with a
gain path of its own, so no change steps the output ("Limiter"). It was
NOLOCK until 2026-10-02.

**The rule for switch-like controls** (owner, 2026-10-02): a switch-like
control that changes cleanly, because the engine crossfades, glides or
hands over every change so that no change, however fast, steps the output,
is lockable and modulatable (MOD; an ENUM is rounded when modulated, docs/16
§2.2). Only a destructive change is NOLOCK. The effects' switches follow it:
Filter's Type, Drive's Type and Auto, Comp's Character, Auto Rel and Auto
Gain, the Limiter's Mode and Lookahead, DJ Filter's Slope, Tilt's Curve,
Master Sat's Shape, Isolator's Kill, the Gate's Mode, Listen, Link and
Lookahead, and Squash's Type are all lockable and MOD, and
`tests/test_engines_fx_switches.py` (the Gate's cases are in
`tests/test_engines_gate.py`, through the same harness) turns each of them
every third block (faster than its crossfade) on a steady sine and on sharp
onsets, checking that the output stays finite, keeps the effect's ceiling
and steps no more than with the control held at any of its values, plus the
bound a 5 ms crossfade allows (2P/220 for outputs of peak P). Where that
check first failed, the effect was made clean rather than the control left
NOLOCK: the Filter's new type now warms up unheard before its crossfade,
and the Limiter's Lookahead crossfade got a gain path per tap.
`fm1_param_lockable`, `fm1_param_modulatable` and `fm1_param_index(engine,
uid)` are the helpers. `fm1-render --list` prints each parameter's uid,
flags (by name), unit and abbreviation, and each engine's `per_note` and `pads`. The four fields make `fm1_param_t`
36 bytes on pi32v2 and i386 (28 before) and 48 on x86-64 (40) [verified:
`tools/jieli/compile-check.sh`, 2026-10-02, 67 of 67 objects compiled in
all four profiles]: 8 bytes more of read-only data per parameter, 2,040
bytes for the 255 the registry defines [counted with `fm1-render --list`,
2026-10-06, with dynamics pack 3, glide's ten and the arpeggiator's 25; 88
when the sizes were measured]. The 16-bit flags of v3 sit in
what was padding after `uid`, so the sizes did not change, nor did the
modulation runtime's 22,368 bytes, whose records widened the same way
[verified: `tools/jieli/compile-check.sh`, 2026-10-05: 36 bytes on pi32v2
and i386, 48 on x86-64; 114 of 114 objects compiled in all four
profiles].

**The ENUM parameters** [verified against each engine's code, 2026-10-02].
docs/15's table had eight; Macro's and Macro Heavy's LPG came with their
third page; Drive's Type and Auto, Comp's Character, Auto Rel and Auto
Gain, Filter's Type and the Limiter's Mode with their effects, DJ
Filter's Slope, Tilt's Curve, Master Sat's Shape and Isolator's Kill with
the master-bus pack, Hall's and Plate's Freeze on 2026-10-05, and Squash's
Type with dynamics pack 3 (the Limiter's Mode gained Round then).

| Engine | Parameter | Flags | Why |
| --- | --- | --- | --- |
| macro | Model | NOLOCK | `set_param` rebuilds all 12 voices (`BuildEngines`), cutting every note |
| macro | LPG | none | Read every block, and a change leaves notes sounding, so it can be locked. No MOD: a rounded route could end a note held under Off by switching to Ping |
| macro-heavy | Model, LPG | as Macro's | the same code |
| drums | Pad | none | The edit focus, as Sophie's: lockable, no MOD |
| drums | Model | LATCH, MOD | Read when a pad is struck; a sounding hit keeps its model |
| drums | Kit | LATCH, MOD | The voicings a hit starts with; a sounding hit keeps them |
| shapes | Shape | NOLOCK | Sets every voice's oscillator at once |
| sixop | Patch | LATCH, MOD | Read per voice at note-on, so a lock or a route picks the patch of the next notes |
| dx7 | Patch | LATCH, MOD | As Six-Op's: a voice takes its data, built-in or from a user slot, at note-on |
| sw-sophie | Pad | none | The module's edit focus, not a sound: it picks the pad the other parameters edit. NOLOCK in S7a, since a lock on it changes what the locks after it mean; lockable since docs/15 S8 (the owner's decision, 2026-10-02): a Pad lock moves the focus at its step, so the locks after it in lane order, there and later, edit the pad it names. A change leaves sounding voices intact. No MOD: a list that moves the focus is no modulation target |
| sw-sophie | Model | LATCH, MOD | Each voice keeps a copy of its pad's patch, so a change leaves sounding voices intact |
| sw-sophie | Filter Type | LATCH, MOD | The same. Hidden for now: its page is not exposed (schwung.md) |
| sw-psxverb | Model | NOLOCK | A new preset clears the 128 KB work area, cutting the tail. Effect slots are not lockable yet anyway (docs/15 O14, answered 2026-10-02) |
| filter | Type | MOD | A change warms the new type up from rest, unheard, then crossfades into it over 5 ms, so nothing is cut: lockable, and a rounded route steps through the types, however fast. Neither NOLOCK nor LATCH (an effect has no note-on) describes it |
| drive | Type | MOD | A change crossfades the two curves over 5 ms (the rule above) |
| drive | Auto | MOD | Its gain glides like any other (the rule above) |
| comp | Character, Auto Rel, Auto Gain | MOD | Read every frame; Character and Auto Rel hand the smoothing over through an offset that decays in 5 ms and Character crossfades the detector, Auto Gain glides its makeup and its bound in, so no change steps (the rule above). Not effects of a note, so no LATCH. Until 2026-10-02 they took no MOD |
| limit | Mode | MOD | A change glides the output stage over 5 ms, frame by frame as the line delivers them (each frame carries the Mode its gain was made for), Round's share beside Soft Clip's since 2026-10-05. NOLOCK until 2026-10-02 |
| djfilter | Slope | MOD | Crossfades the 12 and 24 dB filters over 5 ms (the rule above). The research note had it NOLOCK |
| tilt | Curve | MOD | Glides from one curve's coefficients to the other's through two 2.5 ms stages (the rule above). The note's Sections switch was NOLOCK |
| sat | Shape | MOD | Crossfades over 5 ms, so a lock or a rounded route is clean however fast (the owner's switch rule, 2026-10-02) |
| isolator | Kill | MOD | The killed bands' gains glide over 5 ms, so a change is clean however fast: lockable, and a route is rounded |
| hall | Freeze | MOD | Crossfades over about 75 ms (the input fades out as the decay lengthens) and keeps the tail, so it can be locked, and a route rounds it |
| plate | Freeze | MOD | Off/On, appended as uid 5 on Plate's second page (2026-10-05). It ramps the loop over 5 ms, so a lock or a rounded route switches it cleanly (the owner's policy for switches; mi-fx.md, "Freeze") |
| gate | Mode, Listen, Link | MOD | Mode crossfades the Gate and Duck gains, Listen the gated audio and the filtered key, and Link the detector's and Listen's weights, each over 5 ms, so no change steps the output (the rule above) |
| squash | Type | MOD | The new Type starts from the gain the old one applies and the two crossfade over 5 ms, so no change steps the output (the rule above) |

### The LOG law

LOG (API v3; owner decisions 2 and 3 of
notes/2026-10-02-filters-dynamics-options.md) is for pitch- and time-like
parameters. The value stays what is stored, shown and saved (Hz, ms); what
moves is the knob's position u = log2(v / min) / log2(max / min), 0..1
(`fm1_param_pos`, `fm1_param_at` in `include/fm1_engine.h`; any other FLOAT's
position is (v − min) / (max − min)):

- **A knob detent** moves u by 1/100: a ratio of (max/min)^(1/100), 1.2
  semitones on a 20 Hz–18 kHz cutoff, 7 % on a 1–1,000 ms release. The ends
  are reached exactly. The panel's bars show u. Values show three significant
  figures or more down to 1 (2143 Hz, 21.4 Hz, 1.07 ms).
- **A 7-bit sequencer lock** is u = v7 / 127, so its 128 values are a
  geometric grid, min exactly at 0 and max at 127, and every value comes back
  to itself (`fm1_seq_lock_value`, `fm1_seq_value7`).
- **A modulation route** adds amount × signal × log2(max/min) octaves (the
  same share of the knob a linear parameter moves), and the value is base ×
  2^(sum), clamped. **The octave rule:** a SEMI source (NOTE, a quantizer's
  pitch) moves a LOG destination by amount × signal × 60 semitones, as it
  moves a SEMI one, so NOTE at +100 % into a cutoff tracks the keys one
  octave per octave, exactly (docs/16 §2.3). A ±50 % LFO on Cutoff now
  swings ±4.9 octaves round the base instead of ±8,990 Hz pinned at the
  ends.
- **Per-note offsets** on a LOG parameter (none is POLY yet) will be sent
  as the final value less the base, in the parameter's unit, so engines
  need no knowledge of logs (per-voice modulation, MG9).
- All of it is libm-free (`include/fm1_math.h`, the base-2 log and
  exponential Comp used, now shared), so native and WebAssembly builds agree
  bit for bit.

The parameters with LOG [verified: tests/test_engine_params.py holds LOG to
every FLOAT in Hz or ms whose range starts above 0, and only there]:
Filter and Comb Cutoff, Echo Time, Comp Release, Limiter Release, Tilt
Pivot, Master Sat's Clean Lo and Clean Hi, Isolator's Low and High Xover,
EQ's three frequencies, Gate's Hold, Decay, Key HP and Key LP, Squash's
Attack, Release and Gate Rel, Transient's Window and Tail, Sophie's Ring
Time, and the Glide of Macro, Macro Heavy, Six-Op FM, FM6 and Shapes
([below](#glide-and-voice-modes)). Comp Attack, the Limiter's Lookahead, Gate's Attack, Lockout and
Lookahead and Room's and Hall's Pre-delay start at 0 and stay linear, and the modulation kinds'
times are 0..1 knobs with laws of their own. **dB** (`FM1_UNIT_DB`) marks
Comp's Threshold, Knee and Makeup, Drive's Drive and Level and the
Limiter's Ceiling and Drive (the owner's list), and EQ's gains and Level,
Tilt's Tilt and Level, Master Sat's Drive and Level and Gate's Threshold,
Range and Return, whose sources said dB already, and Squash's Output and
Gate and Transient's Output (2026-10-05). Units change nothing but what a screen may print.

### SMOOTH: the ramp inside the engines

Since docs/15 stage S7b, a change to a SMOOTH parameter while an engine
sounds ramps inside the engine (the owner's choice, docs/13 §10). The shared
code is `include/fm1_smooth.h`, plain C99:

- **2.5 ms of the engine's own native samples,** in equal steps of its own
  control block, landing exactly on the new value. A ramp turned mid-way
  starts again from where it stands.
- **Keyed to samples.** The control blocks sit at fixed native samples,
  rendered as the resampler or the effect's own loop needs them, never at
  render calls. The output is therefore the same at any host block size and
  with any split of a block.
- **At once when there is nothing to ramp:** while no voice is active, and
  before an effect's first render. A lock on the trig of a note that starts
  a silent engine plays that note at the locked value from its first sample,
  and settings made at load apply from sample 0.
- **A write equal to the target already set changes nothing.**
- **Exact on every build** (docs/14): no libm, and nothing a compiler could
  contract into a fused multiply-add. A step is `(target − value) / steps`,
  added once per block and clamped so it never passes the target, and the
  last block stores the target itself. A render with no change while
  sounding is the render without the ramp, bit for bit (below).

| Engine | Control block | Steps | Ramp | What ramps |
| --- | --- | ---: | --- | --- |
| Macro, Macro Heavy | 12 samples at 47,872.34 Hz | 10 | 2.51 ms | every FLOAT, read once per block as before |
| Drums | 12 samples at 47,872.34 Hz | 10 | 2.51 ms | every FLOAT: a per-pad one in its pad's own values, only while that pad sounds; the kit's while any pad does |
| Six-Op FM | 16 samples at 47,872.34 Hz | 8 | 2.67 ms | Brightness, Envelope, Volume, Glide |
| FM6 | 64 samples at the host rate (msfa's block) | 2 at 44,118 Hz | 2.9 ms | Brightness, Env Time, Feedback, Volume, Glide; Volume also glides across each block, sample by sample |
| Shapes | 24 samples at 96 kHz | 10 | 2.5 ms | Timbre, Color, Attack, Release, Volume, Glide |
| Test Sine | 1 sample at the host rate | 110 at 44,118 Hz | 2.49 ms | Volume |
| Plate, Ensemble, Diffuse, Crush, Test Gain | 1 sample at the host rate | 110 at 44,118 Hz | 2.49 ms | what each runs on; see below |
| PSX Verb (through the Schwung shim) | the module's block, 64 frames on the FM-1 | 2 | 2.9 ms | Decay, Mix, Level, Input, sent as strings before each module call |
| Echo's Tone | 1 sample at the host rate | 110 at 44,118 Hz | 2.49 ms | the loop filter's coefficient, derived once per change |
| Fold, Drive, Filter, Comp, Limiter, and Echo but its Tone | their own glides | – | 5 ms one-pole (Filter's controls in steps of 8 samples); Echo's Time and Wow 0.1 s | unchanged |

- **Effects ramp what they run on, not the knob.** Plate's loop gain and
  damping, Diffuse's loop gain and tone coefficient, and Crush's quantiser
  step, hold interval and low-pass pole are derived from the knob once per
  change, with libm as before, and the derived value ramps. No libm runs
  in a render. During a Bits ramp Crush's inverse step is `1 / step`, and
  exp2f's value again at the end. While a ramp runs, the vendored effects
  render one frame at a time so that each frame gets its step.
- **The rule for effects that already glide.** An effect that glides its
  parameters itself, keyed to samples and snapping before its first render,
  keeps its own glide: Fold (5 ms one-pole) and Echo (5 ms gains, 0.1 s
  Time and Wow), and the second effects pack, which came with glides of its
  own: Drive (5 ms, sample by sample), Filter (5 ms, its filter controls
  in steps of 8 samples counted from create, Mix and Level per sample),
  Comp (5 ms; Attack and Release are time constants) and the Limiter (5 ms,
  and a crossfade for Lookahead). That glide gives what SMOOTH promises. A
  new effect may do the same; anything else uses `fm1_smooth.h`, as Echo's
  Tone does: its loop filter's coefficient had no glide and jumped, which
  steps the repeats, so it takes the shared ramp. The master-bus pack (DJ
  Filter, Tilt, Master Sat, Isolator, EQ) came with glides of its own too,
  keyed to samples and applied at once before the first render (their
  sections above), and keeps them; `tests/test_engine_smooth.py` drives
  all five like every other unit [verified 2026-10-05, after merging S7b].
- **The Schwung shim** ramps the first eight SMOOTH parameters of a module
  (`kMaxRamps`), in the module's own blocks, from its first render on.
  `tests/test_engine_params.py` checks that no module has more. Sophie's
  parameters are LATCH, so only PSX Verb's ramp.
- **A lock or a modulation write at frame f.**
  - The ramp starts with the engine's first control block not yet rendered
    at f, which is where an unramped change used to land.
  - A D6 revert and a lock at one frame make one ramp, to the lock's value.
  - A modulation route writes every tick (0.725 ms, docs/16 §2.6). Each
    write restarts the ramp from where it stands, so the parameter follows
    its source through a lag of about one ramp, and the steps are not heard.
  - docs/12 §5.3 has the sequencer's view.
- **Per-note offsets ride on the ramp** (answered when S7b merged with
  them, 2026-10-05). The ramp is the engine's, one per parameter, shared by
  every voice. A voice with a per-note offset
  ([below](#per-note-offsets)) plays the ramped base plus its offset,
  clamped, at every control block: the code that computes a voice's
  controls reads the same ramped values as the engine-wide code. The
  offset itself is not ramped: it applies at the next internal block, as
  it did before S7b.
  - Why: a ramp per voice would cost 12 bytes per POLY parameter and the
    pitch in every voice (Macro 1,440 bytes, Shapes 864, Macro Heavy 528,
    Six-Op 384), and a voice whose offset moved would recompute its
    controls every block for the ramp's length. A knob, a lock or a route
    on the base still ramps for every voice.
  - So a per-voice source must be smooth itself. MG9's per-voice instances
    write every control tick (0.725 ms, docs/16 §2.6, §6.3); a source that steps
    by much in one tick (a square LFO, a fast envelope's attack on Volume)
    steps the voice by as much. Whether that is heard, and whether MG9 then
    slews its writes or the engines ramp offsets after all, is MG9's to
    measure [inferred].
  - Test: a base ramping under a sounding offset is, byte for byte, the
    base ramping over the same sums with no offset
    (`tests/test_engine_note_params.py`).
- **What it does not do.** While a tail still sounds, a note that starts
  with a lock begins on the ramp, since the ramp is the engine's. Under
  Macro Heavy's Speech the word bank follows Harmonics' new value at
  once, while the voices' Harmonics ramps, so a ramp across several banks
  parses one bank, as before the ramps, not each one it passes
  (plaits-heavy.md). Shapes still derives its envelope coefficients with
  `expf` and `powf` once per chunk, as before, so an Attack or Release ramp
  feeds libm values in between.
- **Cost.** 12 bytes per parameter plus a few per instance (Crush 96 → 176
  bytes, Macro +128), and one test per parameter per control block while
  nothing moves. While a ramp runs, Plate, Ensemble and Diffuse call their
  vendored class once per frame instead of once per 32; a parameter
  modulated every tick would keep them there. Stage B measures what that
  costs on pi32v2 [inferred: small beside the classes' per-sample work].

**Tests** (tests/test_engine_smooth.py, `build/fm1-smooth-test`, which drives
any engine or effect with changes at any frame where fm1-render cannot):
- every engine and effect renders the same, bit for bit, with every
  parameter changed mid-note and mid-ramp, and with NaN, infinity and
  out-of-range values, at render calls cut at 64, 1, 7 or random frames;
- a repeated write changes nothing;
- Test Gain's ramp is 110 samples at 44,118 Hz (120 at 48 kHz, 55 at
  22,050 Hz), monotonic, and exact at its end;
- a Volume lock of 0 → 127 under a held A4 stays within the sine's slope
  plus 1/110 of its amplitude per sample, where a jump would be a
  full-scale click, and from its 110th sample the output equals Volume 127
  throughout;
- a lock on a silent engine's trig plays from the note's first sample;
- a per-note offset rides on a ramping base (above).

**What changed in sound** [verified 2026-10-05, Apple clang, main against
this branch on one machine, with a third build that reports every ramp it
starts]: 2,141 runs of `fm1-render` and the virtual FM-1's native harness,
the same kinds as API v2's check below. They cover:
- the 34 oracle scripts on all six sound engines in both modes, at both
  block sizes;
- 28 `movy1` sets;
- every sound parameter as a lock lane, at blocks of 64 and 7, and locked
  on the trigs of short notes;
- 36 seeded lock scripts in both modes;
- the host-block script at 1, 7 and 64 frames;
- every parameter at its minimum, middle and maximum, set at the start,
  turned mid-note, and turned while silent;
- every effect parameter at the same values, at blocks of 64 and 7;
- instance fills, 48 kHz, bends;
- the 25 parity scenarios through both hosts.

**The result:**
- All 1,891 runs that start no ramp are byte-identical: every WAV, event
  log, exit code, error and summary less its timing and its instance sizes.
  That includes the 52 that exit with the same error as before: the
  Plaits-based engines refusing 48 kHz, and Sophie's lack of a pitch bend.
- Of the 250 that start one, 209 changed their audio. The other 41 started
  ramps that made no difference in 16-bit output.
- Of the parity scenarios, only `seq-panel-play-stop` changes its audio:
  the panel turns knobs while Macro plays. The others change only their
  RAM figures.

**After merging main** (per-note offsets, the second effects pack,
multi-sound and S5–S8) [verified 2026-10-05, Apple clang, main at
`bd3d6da` against the merge, the same three builds]: 2,640 runs of the same
kinds, the new effects and the 47 parity scenarios included.
- All 2,376 that start no ramp are byte-identical, the 52 that exit with
  the same error as before among them.
- Of the 264 that start one, 223 changed their audio.
- Nine parity scenarios sound different, each because a knob or a lock
  turns while something sounds: `seq-panel-play-stop`, `seq-panel-locks`,
  `multi-panel`, `multi-four-sounds-seq`, the four `fx-turns-*` and
  `drive-fuzz-gated` (its Plate Decay turn; Drive keeps its own glide).
  `macro-lpg-ping-env` starts a ramp that makes no difference in 16-bit
  output. The others change only their RAM figures.

**Units and abbreviations.** Echo's Time, Hall's Pre-delay, Comp's Attack
and Release, Sophie's Ring Time, the Limiter's Release and Lookahead and the
Gate's Attack, Hold, Decay, Lockout and Lookahead, Squash's Attack,
Release and Gate Rel and Transient's Window and Tail are in ms, Filter's and
Comb's Cutoff, Tilt's Pivot, Master Sat's Clean Lo and Clean Hi, Isolator's
crossovers, EQ's frequencies and the Gate's Key HP and Key LP in Hz,
Sophie's Tune in semitones and its 0–100 knobs in %. Sophie's Decay is in
seconds, and Drive's Drive and Level, Comp's Threshold, Knee and Makeup, the
Limiter's Ceiling and Drive, Tilt's Tilt and Level, Master Sat's Drive and
Level, EQ's gains and Level, the Gate's Threshold, Range and Return,
Squash's Output and Gate and Transient's Output in dB (Transient's Attack
and Sustain are in %), which had no unit code until engine API v3 added `FM1_UNIT_DB`
(2026-10-05; [The LOG law](#the-log-law) lists them). Every other
parameter is a bare number (the 0–1 knobs, gains, bits, indices, EQ's Qs).

**No sound changed** [verified 2026-10-02, Apple clang, before and after on
one machine, clean builds]: 1,458 runs of `fm1-render` and the virtual
FM-1's native harness. They cover:
- the 34 oracle scripts on all six sound engines in both modes, at 64-frame
  blocks and at each script's own (the Plaits-based engines refuse the five
  48 kHz scripts, the same way before and after);
- 28 `movy1` sets played alone (four sets and the oracle's 24 end states);
- every sound parameter as a lock lane, at blocks of 64 and 7;
- 72 seeded scripts that lock four random parameters per engine, relabel
  one lane and release another while playing, in both modes;
- the host-block script at 1, 7 and 64 frames on every engine;
- every parameter of every engine and effect at its minimum, middle and
  maximum and turned mid-note; instance fills 0xA5 and 0xFF; 48 kHz;
- the simulator's 18 parity scenarios, through both hosts.

Every WAV, event log, exit code and error is byte-identical, and so is
every summary less its timing and the new `seq_locks_refused`, in every run
that refuses no lock. The 38 that do (8 of the sweep, 30 of the seeded
scripts) are the only ones that differ: their locks on Macro's and Macro
Heavy's Model and Shapes' Shape are refused, which changes their audio,
and on Sophie's Pad, which changes only their counters (Pad alone makes no
sound).

### Per-note offsets

The owner decided on 2026-10-02 that per-voice modulation is essential:
each note gets its own envelopes and LFOs, which move only that note
(docs/16 §6.3, stage MG9). This is the engine side of it: a host can move
one sounding note's parameters and pitch without touching the other notes.
The modulation that drives it is MG9's.

**The entry.** `set_param_note(self, key, index, offset)` is the last member
of `fm1_engine_t` (`include/fm1_engine.h`), optional within API v2: NULL
means no per-note offsets, as `pitch_bend` may be NULL. The version stays 2,
since no v2 engine has shipped outside this tree. It follows the contract
below.

| Question | Rule |
| --- | --- |
| What may be offset | A parameter flagged POLY (`fm1_param_poly`), or the note's pitch: index `FM1_PARAM_NOTE_PITCH` (0xFFFF), in semitones, added after the key and the bend. Any other index (a non-POLY parameter, an ENUM, one past the table) is ignored |
| What the voice plays | `fm1_param_note_value`: base + offset, clamped as `set_param` clamps. The base is the engine's value, ramped while a SMOOTH change runs ([SMOOTH](#smooth-the-ramp-inside-the-engines)); a base that moves, ramp and all, keeps the offset on top |
| What a call does | Replaces that voice's previous offset for that index; offsets do not add up. A host sends the sum of the note's routes |
| NaN and infinities | `fm1_param_note_offset`: NaN is 0, no offset (as NaN is the default for `set_param`). An offset is cut to the parameter's span (max − min), past which the sum is at an end whatever the base, so ±inf pin the parameter at its maximum or minimum, as through `set_param`. A pitch offset is cut to ±48 semitones (`FM1_NOTE_PITCH_MAX`), the pitch bend's range |
| Which voice | Every voice sounding the key, held or releasing. The engines retrigger a key in its own voice (Drums: a pad), so there is one |
| Lifetime | The offsets belong to the voice. `note_on` starts the key's voice at 0, so a host sends a new note's offsets after its note-on, at the same frame. `note_off` keeps them: the release is moved too. A voice that is stolen or ends drops them. A call for a key no voice sounds is ignored, not kept for a later note |
| When | Where `set_param` would take effect: the next internal block (12 or 16 samples at 47,872 Hz, 24 at 96 kHz), at once: an offset is not ramped, where a SMOOTH change of the base is. So the output does not depend on the host's block size |
| Thread | The audio task, like `set_param` |

Two choices differ from docs/16 §6.3's sketch, `set_param_mod(index, key,
offset)`. The name says what is offset, a note, not where it comes from,
and the key comes first because it picks the voice, as in `note_on`. The
pitch is a reserved index rather than an entry of its own, so a per-voice
route's destination is always an index, and one function pointer covers
both. The pitch has no uid: a route stores it as a system destination
(MG9's to name).

**The engines.**

| Engine | POLY parameters | How |
| --- | --- | --- |
| `macro` | all nine FLOATs: Harmonics, Timbre, Morph, Decay, Colour, Volume, Env Pitch, Env Timbre, Env Morph | A voice with an offset computes its controls (Plaits' parameters, the decay envelope's and the gate's times, its gain, the attenuverter amounts, Chip's own envelope) from its own values, with the function that computes the engine's |
| `macro-heavy` | all ten FLOATs (Macro's and Word Speed) | As Macro. On Speech, Harmonics stays engine-wide: it picks the word bank all voices share (one parse, not four), and the envelope's reach with it, so its offset is ignored there |
| `sixop` | Brightness, Envelope, Volume | Each voice already passes the first two to its `fm::Voice`, and Volume is its gain. Patch stays a note-on choice (LATCH). A pitch offset at the note's first block is the note `fm::Voice` samples for keyboard and rate scaling, as a played note's would be |
| `dx7` | Brightness, Env Time, Feedback, Volume | Each voice sets its operators' levels (Brightness), its feedback and its gain every block, and runs its own envelope clock (Env Time). Patch stays a note-on choice (LATCH). A pitch offset joins the bend in the voice's pitch; keyboard level and rate scaling stay the key's, set at note-on |
| `shapes` | Timbre, Color, Attack, Release, Volume | Each voice already sets its oscillator's parameters and runs its own envelope. Shape stays engine-wide (NOLOCK) |
| `drums` | all nine FLOATs: the seven per-pad ones (Tune .. Drive), Accent and Volume | A hit computes its controls every block from its pad's values and the kit's, plus its offsets; notes are pads, so the offset reaches the hit on that pad's note. Model and Kit stay note-on choices (LATCH) |
| `sw-sophie` | none (NULL) | The module keeps its voices to itself (each copies its pad's patch at the trigger, `sophie.c`), and the shim reaches only the module's global `set_param`. Per-note offsets would mean changing the vendored module, which stays byte-identical |
| `test-sine` | none (NULL) | Kept without them: the engine a host's tests use for the NULL case |
| effects | none (NULL) | No notes |

**Memory.** Per voice, one float per POLY parameter, one for the pitch and a
32-bit mask of which are not 0 (`src/note_offsets.h`), inside the instance;
no heap. Instance sizes before and after [verified 2026-10-05: gcc 12
x86-64 and `-m32` in a container, and JieLi's clang for pi32v2, which equals
i386 for all four]:

| Engine | Voices | 64-bit | 32-bit (i386, pi32v2) |
| --- | ---: | --- | --- |
| Macro | 12 | 31,744 → 32,320 (+576) | 19,072 → 19,456 (+384) |
| Shapes | 12 | 207,080 → 207,368 (+288) | 206,212 → 206,548 (+336) |
| Macro Heavy | 4 | 71,104 → 71,296 (+192) | 70,896 → 71,088 (+192) |
| Six-Op FM | 8 | 12,528 → 12,720 (+192) | 10,796 → 10,956 (+160) |

Voice alignment pads or absorbs some of it: Macro's offsets are 44 bytes a
voice, and its 16-byte-aligned voice grows by 48 on x86-64 and 32 on i386.
`fm1_engine_t` gains a pointer: 4 bytes on pi32v2 for each of the 18
registered engines and effects.

**Cost.** A voice without offsets tests one mask per internal block. A voice
with offsets recomputes its controls each block: for Macro, two
`SemitonesToRatio` and three attenuverter amounts per 12 samples
[inferred; stage B measures pi32v2]. Shapes' Attack and Release cost a
`powf` and an `expf` each, so a voice computes its own coefficient only for
an offset on that parameter, and takes the engine's otherwise (the same
number): a Timbre, Color, Volume or pitch offset costs no transcendental.

**No sound changed without offsets** [verified 2026-10-05, before and
after, clean builds, on Apple clang (arm64), gcc 12 x86-64 and gcc 12
`-m32`]: 1,900 runs of `fm1-render` on each. They cover the 24 Movy
oracle scripts, the simulator's 7 sequencer scripts and the 30 panel-trace
scripts on all six sound engines in both modes (the oracle's at 64-frame
blocks too); the 28 `movy1` sets on three engines; a lock lane on every sound
parameter at blocks of 64 and 7; a chord past every voice cap with bends
at host blocks of 1, 7 and 64, fills 0xA5 and 0xFF and 48 kHz; every
parameter at its minimum, middle and maximum and turned mid-note; every
model, shape, patch and pad; 72 seeded scripts of notes and parameter
moves; every effect at each parameter's minimum, middle and maximum; and
the 37 parity scenarios of the simulator that `fm1-render` plays alone
(not the two driven from the panel). Every WAV,
event log, exit code and error is byte-identical, and so is every summary
less its timing and `instance_bytes`. A voice computes the engine's values
until it has an offset, so this holds by construction; the runs check it.

**With offsets** [verified: `tests/test_engine_note_params.py`, all four
engines]:
- 0 and −0 on every POLY parameter and the pitch, on every note, render
  what no call renders.
- For a note sounding alone, an offset from the note-on is the base moved
  by as much, byte for byte, through the release (each POLY parameter; all
  at once on every Macro and Macro Heavy model, a sample of shapes and
  patches), and a pitch offset is a pitch bend. Mid-note, where a base
  change would ramp and an offset does not, a later offset and an offset
  back to 0 are compared with the same moves against a base that holds the
  first offset.
- A base set under an offset gives the sum, and a sum past the range is
  clamped, byte for byte as the base set to it. A base that ramps under a
  sounding offset is the base ramping over the same sums alone, byte for
  byte: the offset rides on the ramp.
- Two notes with offsets on one render as the two notes rendered apart,
  summed (to 3 LSB at 16 bits), while either offset alone moves its note
  by more than 300 LSB: the other note is untouched.
- An offset survives note-off and one sent during the release moves it; a
  retrigger, a steal and a voice's end drop the offsets; calls for a silent
  key or a non-POLY index change nothing.
- NaN is no offset, ±inf pin a parameter at its ends, and a pitch offset
  is cut to ±48.
- Instance fills 0, 0xA5 and 0xFF and host blocks of 1, 7 and 64 give the
  same bytes when the calls land on the same frames.
- Every POLY parameter at an end with the pitch at ±48 over a ±48 bend, on
  keys 0 and 127, on every model and every fifth patch, every shape
  included, renders finite output, also under ASan and UBSan (Shapes holds
  Braids at its edges: [above](#shapes-where-braids-is-held)).

**In `fm1-render`**: `--note-param-at T:KEY:NAME=OFFSET` (a POLY parameter;
`#INDEX=OFFSET` sends any index, to test what an engine ignores) and
`--note-pitch-at T:KEY:SEMITONES`, applied at block boundaries after that
block's note-ons. The renderer refuses them for an engine without
`set_param_note` and NAME for a parameter that is not POLY.

### Glide and voice modes

The owner decided on 2026-10-05 that glide lives in the engines, as a
per-note pitch slew (scratch decisions, "Arp and MIDI effects"), so that
mono and legato playing and portamento work with any host, the
arpeggiator and the sequencer included. `src/glide.h` holds it, shared by
the five pitched engines. Two parameters, appended to each table:

| Engine | Glide | Voice Mode | Page |
| --- | --- | --- | --- |
| `macro`, `macro-heavy` | uid 13 | uid 14 | 4, a page of their own (Macro Heavy's three are full; Macro's matches it, so a lane survives a swap) |
| `shapes` | uid 7 | uid 8 | 2, after Release and Volume |
| `sixop` | uid 5 | uid 6 | 2, after Volume |
| `dx7` | uid 6 | uid 7 | 2, after Volume |

- **Glide**: 1–5,000 ms on the [LOG law](#the-log-law), default 1 ms,
  which is **Off**: no glide starts. SMOOTH and MOD, and engine-wide, not
  POLY: a glide is the move between two notes, not a property of one.
- **Voice Mode**: Poly (the default), Mono, Legato. LATCH and MOD: read at
  note-on and note-off, so a lock or a rounded route changes how the next
  note is played, and no change cuts a sounding voice (the owner's rule for
  switches).

**What glides.** Fingered (legato) portamento: a note struck while another
key is held starts at the pitch the held note sounds, glide included, and
moves to its own in a straight line in semitones, arriving after the Glide
time whatever the interval (constant time). A note struck with no key held
starts on its own pitch. "The held note" is the newest voice whose key is
down and which has a pitch to glide from: it has rendered a block since its
note-on, or is gliding itself. So the notes of a chord struck in one control
block never glide from each other; struck over a held note, each glides
from it.

**How.** A glide is a pitch offset in semitones that the voice adds after
the key and the bend, beside its per-note pitch offset
([above](#per-note-offsets)): the same path, at the same place in each
engine (Plaits' note, Braids' pitch, `fm::Voice`'s note, msfa's Q24 pitch
modulation). It moves once per control block, at the engine's native
samples, so the output is the same at any host block size. The first block
plays the pitch it starts from; each block takes `block_ms / Glide` off the
share still to go, and the offset is the start's interval times that share,
exactly 0 at the end, after which the voice adds nothing. The time is read
every block, so a glide under way follows a turn of Glide, ramped as any
SMOOTH change. No libm, a division a block and a product a gliding voice,
and no multiply-add in one expression, so native and WebAssembly builds give
the same bits.

**The voice modes.**

| Mode | A key while another is held | Letting go of the sounding key, others held |
| --- | --- | --- |
| Poly | A voice of its own, as before; it glides from the newest held note | That voice releases, as before |
| Mono | The one voice (the newest sounding) takes the key and restarts its envelopes, gliding from where it was | The voice moves back to the newest key still held, gliding, without restarting |
| Legato | The voice takes the key without restarting anything; it keeps the first note's velocity | As Mono |

- A key struck in Mono or Legato with no key held restarts the newest
  voice in place, as a retriggered key does in Poly, or takes a free one.
- The keys held are kept in every mode (16 at most, the oldest dropped), so
  a switch of mode finds them as they are; a switch leaves every sounding
  voice alone. A return never moves a voice onto a key another held voice
  already sounds (a chord held in Poly, then a switch to Mono): that voice
  releases instead, so no key sounds twice.
- A voice that moves to another key is a new note for its per-note offsets:
  they restart at 0 (`fm1_engine.h`, `set_param_note`).
- **Macro Heavy:** a Legato move leaves a self-enveloped model ringing (a
  string is not plucked again, a word goes on); Mono strikes it again.
- **Six-Op FM:** a Legato move gives `fm::Voice` no gate edge, so its
  envelopes go on and its keyboard and rate scaling stay the first note's.
  A Mono note restarts them, and samples the scaling at its first block,
  which is the pitch it glides from.
- **FM6:** a Legato move keeps the envelopes and the LFO running and moves
  the operators that follow the key (ratio mode) by the difference of the
  two keys' msfa log frequencies: integers, so to the bit where a note-on
  on the new key would put them. Keyboard level and rate scaling stay the
  first note's.
- **Shapes:** a Legato move does not strike the oscillator again; the
  voice's envelope goes on.

**Not on Drums, Sophie or Test Sine.** A kit's notes are pads, not pitches
(each note plays its own drum, `pad_count`), and both kits ignore note-off,
so there is nothing to glide between and no key to hold: Drums' Tune and
Sweep and the per-note pitch offset move a hit's pitch. Sophie's voices are
the vendored module's own, out of the shim's reach (as for per-note
offsets). Test Sine stays the plain engine the hosts' tests use.

**Not offered yet.** Full-time portamento (every note glides from the last
one, held or not; the stock firmware lists "Fingered" and "Full Time"
[verified: its strings, notes/2026-09-06-bench.md]), a constant-rate law,
and per-voice glide memory in Poly (each voice from its own last pitch).
Each would be one more Voice Mode value or a third parameter.

**Cost.** Per voice, 16 bytes (`glide::Slew`), and per instance the held
keys (17 bytes) and two floats; no heap. Instance sizes on 64-bit (Apple
clang, arm64) before and after [verified 2026-10-06]: Macro 32,448 →
32,704, Macro Heavy 71,456 → 71,568, Six-Op FM 12,776 → 12,960, FM6
15,844 → 16,144, Shapes 207,448 → 207,696; on 32-bit, after (gcc 12
`-m32` in a container, as CI's job): 19,840, 71,360, 11,192, 16,144 and
206,872. The browser module grew from 813,115 to 829,405 bytes on glide's
branch, from 890,975 to 907,256 bytes merged with main's per-voice
modulation, FM6 user bank and idle paths, and from 922,439 to 938,723
merged with the arpeggiator. Macro Heavy now has 14
parameters, so the modulation runtime's shared records grew from 184 to
192 to hold four of it beside ten of the largest effect and HOST's six
(4 × 14 + 10 × 13 + 6 = 192, `FM1_MOD_SINK_PARAMS`; [Drums](#drums)), and
`fm1_mod_size()` from 26,192 to 26,512 bytes (from 23,200 to 23,520 on
glide's branch, before MG9). CPU: a division per control block, and per
voice a test, plus a subtraction and a product while it glides.

**No sound changed at Glide Off and Poly** [verified 2026-10-06, Apple clang
arm64, against a build of main `ffb0796`]: 1,141 runs of `fm1-render`
byte-identical (WAV, exit code, errors and summary less timing,
`instance_bytes` and the runtime's size; the runtime was then 23,520 bytes at
32 and 64 bits alike): the 63 fm1-render legs of the
parity scenarios (all but the panel-driven ones); the 24 Movy oracle and 15
simulator sequencer scripts on all eight sound engines and in compat mode; on every sound engine, a
16-note chord past every voice cap with bends at host blocks of 1, 7 and 64
and fills 0, 0xA5 and 0xFF, overlapping and retriggered notes at 32, 44.1
and 48 kHz and at blocks of 7, every parameter at its minimum, middle and
maximum and turned mid-note, every model, shape, patch and kit, and 12
seeded scripts of notes, parameter moves and per-note pitch offsets; the
three modulation scripts on every sound engine; and every effect on noise.

**Tests** (`tests/test_engine_glide.py`, all five engines, exact unless
said): a glide, in Poly and in Mono, is the same notes without glide with
the glide's offsets sent as per-note pitch offsets, one per control block,
computed in single precision in the test as `glide.h` does, and it arrives
within one control block of its time (the host runs at the engine's own
rate in its control blocks, so a call lands on every block); a return to
a held key in Mono and Legato, gliding back down, likewise; a turn of
Glide mid-glide, ramped, likewise; a note with no key held, a chord, and a
note after a key let go do not glide; a chord over a held note glides from
it, each note on its own; Mono's and Legato's key changes and returns are
the first key's voice with the interval as its pitch offset (Macro, Macro
Heavy, Six-Op FM, Shapes); FM6's Legato keeps its envelopes and lands
within half a cent of the key's pitch; host blocks of 1, 7 and 64 and fills
0, 0xA5 and 0xFF give the same bytes through Poly, Mono and Legato with
switches and turns mid-glide; NaN and ±inf clamp as `set_param` clamps;
and, measured at 44,118 Hz on Macro's sine, a 200 ms octave passes its
middle at 101.6 ms and arrives at 202.3 ms (the output follows the key by
about 1.5 ms: the next block and the resampler). A review added (exact
unless said): a stack of three keys in Mono and Legato, the middle one let
go first; a glide cut short by a third key, which starts from where the
glide had reached, under a moving bend; Glide just above Off (1.01 ms);
a chord held in Poly, then a switch to Mono or Legato, which ends every
note as Poly does (it had moved the newest voice onto a key already
sounding); twenty keys held in Mono, past the sixteen the list keeps; a
velocity-0 note-on as the note-off; Legato's second note-on for the key
already down; a Poly glide through Macro Heavy's voice steal; FM6 keys
above 127, which its note-off now clamps as its note-on does (the voice
and the held keys had kept a key no note-off ended); and, measured, a
5,000 ms octave on time within 5 ms. Three parity scenarios
(`macro-glide-legato-mono`, `macro-heavy-glide-poly-mono`,
`dx7-glide-legato`) hold the browser's module to the same bytes: 75 of 75
pass on glide's branch and 86 of 86 merged with main, the three identical
to musl, render.js and glibc [verified
2026-10-06: `sim/web/www/fm1.wasm.json`]. In containers, as CI's jobs
[verified 2026-10-06]: the engine, sequencer and Movy tests at 32 bits
(gcc 12 `-m32`, 3,390 passed, and the app layer's 391), and the glide,
per-note, SMOOTH, parameter, page-3, FM6 and modulation-runtime tests
under ASan and UBSan (clang 18, 495 passed).

## Engine API v3

`FM1_ENGINE_API_VERSION` is 3 since 2026-10-05 (owner decision 6 of
notes/2026-10-02-delay-reverb-eq-gates-options.md, and FD1 of the filters
note). Both hosts refuse any other version, so a v2 engine built out of tree
must be rebuilt; nothing a v2 engine does changes, and every engine and
effect here renders byte for byte as before [verified: every parity
scenario's fm1-render leg and every engine and effect at defaults against a
build of main `d538f1e`: 70 of 72 identical; the other two set the Filter
to Comb or Formant by Type number, and remapped, the one that keeps Comb's
settings renders the same bytes again, while the one that switches types
every few milliseconds now cycles through six]. What v3 adds:

- **16-bit flags, LOG, dB** ([above](#parameters-engine-api-v2-and-v3),
  [the LOG law](#the-log-law)).
- **The effect extension**, `fm1_fx_ext_t`: what a host tells an effect
  about the piece of a block it renders, besides the audio. An effect sets
  `fx_wants` and provides `render_ext` (two fields appended to
  `fm1_engine_t`, 0 and NULL for none); the host then calls `render_ext`
  in place of `render`, with the extension filled for the piece:

  | Field | What it is |
  | --- | --- |
  | `key_lr` | The key (side-chain) input: stereo, valid for exactly this call's frames, read-only, never aliasing the audio, never kept. NULL: the effect's own input is its key, and the output is then what a copy of the input as the key gives, bit for bit. Every host passes NULL until the side-chain stage gives an effect a key source (the delays note, §7.3) |
  | `bpm` | The sequencer's tempo, running or not (the set tempo while stopped), or the host's own without one (fm1-render `--tempo`, default 120; the app's 120) |
  | `beat`, `phase` | The sequencer's position at the piece's first frame: whole beats since Start, and how far into that beat, 0 ≤ phase < 1, exact from its integer clock. A beat starts where the sequencer services master tick 96 k, the frame its step-0 notes and its metronome sound on. 0 before the first tick and while stopped |
  | `running` | 1 while the transport runs |
  | `events` | At the piece's first frame: STOP, START, BEAT (in that order at one frame), and RESET (drop every tail; no host sends one yet) |

  `fx_wants`: TEMPO splits the effect's render at the first frame of every
  beat, marked BEAT; TRANSPORT at every Start and Stop, marked; KEY says
  the effect reads `key_lr`. Every field is filled whatever the effect asked
  for, but events only carry what it asked for, always at a piece's first
  frame, so they land on the same frames at any block size. An effect that
  acts at a beat uses BEAT, never a phase it runs forward itself, which
  would round differently with the pieces. `render`, called directly,
  behaves as `render_ext` with no key, no events and the transport stopped.
- **The host side** (`include/fm1_fx_host.h`, `seq/fx_host.c`, in the
  sequencer's objects): `fm1_fx_render` renders one piece of an effect's
  block, calling a v2 effect's `render` once, exactly as before, and an
  extended one in the pieces it asked for. fm1-render and the virtual FM-1
  call it for every insert and master effect, inside their existing splits
  at the modulation's writes, so both hosts give an effect the same pieces.
  Beats come from the sequencer's clock as the block began (`fm1_seq_clock_t`,
  `fm1_seq_get_clock`, which the bridge keeps in `fm1_seq_host_t.clock`):
  integers, so a piece starting at a given frame gets the same bits at any
  block size. Following an external MIDI clock, or in Movy's compat mode,
  ticks are not on that grid: the position is the block's start, with no
  beat splits.
- **Test Ext** (`src/test_ext.cc`, id `test-ext`) is the smallest effect
  that uses it, to prove the plumbing: it passes its input (or, with Listen
  Key, its key) and marks Start (+Click), Stop (−Click) and each beat (+Click
  on a downbeat, +Click/2 on the others) with one-sample clicks; Probe Tempo
  adds bpm/1000 to every sample.

Tests [verified, 2026-10-05]: `fm1-fx-ext-test` (`test/fx_ext_test.cc`,
`tests/test_engine_api_v3.py`) drives a real sequencer at 120 and 87.5 BPM
into Test Ext through `fm1_fx_render` in blocks of 64, 7, 13 and 1 frames:
the same samples every time, the beats on exactly the frames the
sequencer's clock events give, Start at 0 and Stop at its frame; the key
rules; a v2 effect called once per piece; position monotonic and exact.
fm1-render and the app render a Test Ext transport the same bytes, and the
parity scenario `api-v3-test-ext-transport` checks the browser's module.

### MIDI effects

`FM1_KIND_MIDI_FX`, reserved since API v1, is live since 2026-10-06, as an
addition to v3: notes in, notes out, before a sound. Nothing in
`fm1_engine_t` changed. A MIDI effect's descriptor is an `fm1_midi_fx_t`,
an `fm1_engine_t` of that kind (its parameters, `create`, `destroy` and
`set_param` as any engine's; `note_on`, `note_off`, `pitch_bend`, `render`
and the v2 and v3 extras NULL) followed by `process()`; `fm1_midi_fx_of`
casts to it. MIDI effects have their own registry (`midi_fx/registry.c`,
`fm1_midi_fxs`), so the sound and effect lists, and every loop over them,
stay as they were; `fm1-render --list` prints them after the engines, kind
`midi_fx`.

- **`process(self, in, n_in, ctx, out, cap)`**, once per effect per block:
  `in` the block's events (`fm1_midi_ev_t`, `include/fm1_midi_ev.h`:
  frame, kind, key, velocity), ascending by frame; `ctx` the block's tick
  frames (96 to the quarter note), its length, the tempo, the transport and
  the project key (`fm1_midi_fx_ctx_t`); `out` at least
  `FM1_MIDI_FX_OUT_MIN` (64) events, ascending, note-offs before note-ons
  at one frame.
- **The rules:** every note-on sent gets exactly one note-off; a note-off
  that does not fit is sent at the start of the next call, a note-on that
  does not fit never; FLUSH ends every sounding note, PANIC also forgets
  every key, RESET restarts the pattern; time is ticks, never samples, so
  the output is the same at any block size; no heap, no libm.
- **The arpeggiator**, `arp` (`midi_fx/arp_engine.c` on the core
  `midi_fx/fm1_arp.c`), is the first: 25 parameters on seven pages,
  [midi_fx/README.md](midi_fx/README.md).
- **The host side** (`include/fm1_mfx_host.h`, `seq/mfx_host.c`, in the
  sequencer's objects): a chain of up to four effects in front of each of
  four sound units, on the bridge (`fm1_seq_host_t.mfx`). While a chain
  has an effect on, the notes for its sound go through it: live notes
  (`fm1_mfx_live_note`, at the next block's first frame) and the
  sequencer's (dispatch takes them out of the block, at their frames); a
  note-off follows its note-on. Dispatch merges the chains' output into the
  block by frame, so a sound's render splits there and the modulation's
  hook hears the notes. The ticks are the sequencer's clock as the block
  began, which runs on at its tempo while stopped (or the stage's own,
  `fm1_mfx_set_tempo`, without a sequencer); Start reaches the effects as
  RESET and Stop as FLUSH, at their frames, and each frame where the
  sequencer starts notes for the sound as one STEP after them (a trig, for
  RATE TRG). A bypass, a removal or `fm1_mfx_flush` flushes at once, the
  note-offs to the host's sink. Switching an effect on while others in its
  chain are on keeps every note-off with its note-on: the effects before it
  end their notes first, and when it becomes the chain's first effect on,
  those after it hear every key the chain took let go.
- **fm1-render:** `--mfx K:ID[:off]`, `--mfx-param K:NAME=VALUE`,
  `--mfx-param-at K[.J]:T:NAME=VALUE`, `--mfx-on-at K[.J]:T:0|1`,
  `--log-mfx FILE.jsonl` (what the chains sent, by frame and unit), and
  `notes_hung` in the summary (engine note-ons still without a note-off at
  the end). The virtual FM-1 runs the same stage (sim/web/README.md, "The
  arpeggiator").

Tests [verified, 2026-10-06]: `tests/test_engine_midi_fx.py` (blocks of 1,
7, 64 and 448 frames, the sequencer's ticks, Start and Stop, a 24-seed fuzz
with no hung note, note-offs following their note-ons, chains of two and
switching either effect, a flood of 128 keys, TRG on the sequencer's trigs,
the flags, no heap, stdio or libm in the stage and the wrapper) and
`tests/test_sim_arp.py`; parity scenarios `arp-*`.

### Pad kits

A drum kit plays one sound per note on a run of keys, whatever their
pitch: Sophie's and Drums' 16 pads on notes 36–51, General MIDI's drum
keys, lie below the FM-1's keys (53–79 at octave 0). Until 2026-10-05 the
virtual FM-1 knew Sophie by its id. Now an engine says so itself, in two
fields at the end of `fm1_engine_t`, after the effect extension's two (API
v3, optional, additive; written for v2 and moved there when v3 landed):

| Field | What it is |
| --- | --- |
| `pad_first_note` | The note pad 1 plays |
| `pad_count` | How many pads, one note each from `pad_first_note`; 0 for any other engine, whose notes are pitches |

- `fm1_engine_pad_note(e, pad)` gives the note pad `pad` (from 0) plays,
  or −1. Notes outside the run play nothing on a kit.
- **The host's side.** A host with a keyboard may lay the pads on its keys;
  MIDI keeps the notes. The virtual FM-1 puts pads 1–16 on its 16 white
  keys at any octave, and its black keys play nothing, for the current
  sound (`key_note` in `sim/web/src/fm1_app.c`; before, Sound 1's only).
  `fm1-render --list` prints `pads` (`first`, `count`, or null), and
  `fm1-smooth-test` plays a kit's pads, its first among them, instead of
  its pitched keys.
- **Every initializer names the fields:** `0, 0` (not a kit) on every other
  engine and effect, Comb and Test Ext included, `36, 16` on Sophie and
  Drums, so a new engine that
  leaves them out gets GCC's and clang's missing-initializer warning. The
  struct grows by 4 bytes on pi32v2 (two bytes and padding after the last
  pointer) and 8 on x86-64.

## Layout

| Path | What |
| --- | --- |
| `include/fm1_engine.h` | The engine API, version 3. C, no heap: the host asks `instance_size`, provides that memory (not zeroed), and the engine constructs itself in it. Typed parameters, four to a page (the FM-1 has four free parameter knobs), each with a stable uid, 16-bit flags, a unit and an abbreviation ([above](#parameters-engine-api-v2-and-v3)); the LOG law ([above](#the-log-law)); `fm1_param_clamp` for NaN-safe ranges; per-note offsets ([above](#per-note-offsets)); the effect extension, MIDI effects and pad kits ([above](#engine-api-v3)); the threading contract |
| `include/fm1_math.h` | `fm1_log2f`, `fm1_exp2f`: base-2 logarithm and exponential without libm, the same bits on every build (the LOG law's, and Comp's, DJ Filter's and Tilt's through `src/fx_comp_math.h`) |
| `include/fm1_fx_host.h`, `seq/fx_host.c` | The effect extension on the host side: the tempo, beats and transport events from the sequencer's clock, and the split renders both hosts share ([below](#engine-api-v3)) |
| `include/fm1_mod.h`, `include/fm1_mod_host.h`, `mod/` | Modulation (docs/16 stage MG1): a rack of up to 8 modules inside a 32-slot matrix, run every 32 frames on absolute time, with the module kinds LFO, Envelope and Chance, and the glue that runs it as the sequencer bridge's control-rate hook. Built on the primitives (an LFO, a Peaks-style envelope, slew, S&H, a Turing register, a tick clock divider). Heap-free C99, no libm; `fm1-render --mod` hosts it, the simulator does not yet ([mod/README.md](mod/README.md)) |
| `include/fm1_seq.h`, `seq/` | The sequencer core: a heap-free C99 port of Movy's sequencer, with 4–8 routed tracks ([seq.md](seq.md), docs/13) |
| `midi_fx/` | The arpeggiator core `fm1_arp`: heap-free C99 after Yarns, MCL and Super Arp, with its test tool `fm1-arp`; its MIDI effect `arp` (engine API v3) and the MIDI effects' registry ([midi_fx/README.md](midi_fx/README.md), [above](#midi-effects)) |
| `include/fm1_mfx_host.h`, `seq/mfx_host.c` | MIDI effects on the host side: a chain in front of each sound, the ticks, live and sequencer notes, the merge into the block ([above](#midi-effects)) |
| `include/fm1_smooth.h` | The SMOOTH ramp every engine runs (above): C99, header-only, no libm |
| `include/fm1_fx_idle.h` | The idle path of EQ, Isolator and Master Sat: the rest and warm-up times and the decay bound they come from, and the `FM1_FX_IDLE` switch that builds the effects without it ([above](#idle-at-pass-through)) |
| `include/fm1_mix_limiter.h` | The host's mix-bus limiter and bus guard. Twelve voices started in phase can exceed full scale; the bus holds the output under 0.98, and non-finite samples become silence |
| `src/registry.cc` | The static engine registry (tier 0 in docs/11 §5.2) |
| `src/mi_*.cc` | The Mutable-derived engines and effects |
| `src/msfa_*`, `src/dx7_*`, `include/fm1_dx7.h` | FM6 on msfa: the engine, how msfa is compiled, voice data and SysEx, the loops of algorithms 4 and 6, the built-in voices ([msfa.md](msfa.md)) |
| `src/note_offsets.h` | A voice's per-note offsets, shared by the six engines that take them |
| `src/glide.h` | Glide and the voice modes Poly, Mono and Legato, shared by the five pitched engines ([above](#glide-and-voice-modes)) |
| `src/drums.cc`, `src/drum_voices.h` | Drums: the kit around Plaits' drum classes, and the rim shot, clap, cowbell and cymbal of our own ([above](#drums)) |
| `src/fx_fold.cc` | Fold, a wavefolder effect of our own ([above](#fold)) |
| `src/fx_*.cc` | Effects written in this repository (Crush, [Drive](#drive), Echo, [Filter](#filter), [Comb](#comb), [Comp](#comp), [Limiter](#limiter), [DJ Filter](#dj-filter), [Tilt](#tilt), [Master Sat](#master-sat), [Isolator](#isolator), [EQ](#eq), [Hall](#hall), [Gate](#gate), [Transient](#transient); [Room](#room) wraps Clouds' classes; [Squash](#squash) ports Airwindows' loops) |
| `src/fx_filter_dsp.h` | The arithmetic Filter and Comb share (2^x, log2, the saturating curve, the guard, the glide) |
| `src/fx_comp_math.h` | `CompExp2` and `CompLog2`, now `include/fm1_math.h`'s base-2 exponential and logarithm without libm (the same bits on every build) under the names Comp, Tilt, DJ Filter and the Gate use |
| `src/test_sine.cc`, `src/test_gain.cc`, `src/test_ext.cc` | Test engines: a sine voice, a gain stage, and Test Ext, the smallest effect with the API v3 extension ([below](#engine-api-v3)) |
| `src/fx_eq_math.h` | EQ's libm-free maths ([above](#eq)) |
| `src/fx_room_math.h` | Room's libm-free maths ([above](#room)) |
| `include/fm1_comp.h` | Comp's gain-reduction accessor, for a later modulation source ([above](#comp)) |
| `include/fm1_gate.h` | The Gate's hooks: `fm1_gate_render_key` (a key other than the input) and `fm1_gate_state` (its OPEN, ENV and KEY outputs and its latency), for the key and modulation stages ([above](#gate)) |
| `src/schwung_*`, `src/sw_*.cc` | The Schwung v2 shim and one adapter per module ([schwung.md](schwung.md)) |
| `host/render.cc` | `fm1-render`: plays a note script through an engine and an effect chain in 64-frame blocks at 44,118 Hz, applies the bus limiter, writes a WAV, prints JSON; with `--sound`, `--insert`, `--level` (and `--slots`) up to four sound units, each through its own inserts and level, mixed before the effect chain, as the virtual FM-1's multi-sound plays them (seq.md, Host contract) |
| `test/` | The reference renderers (`fm1-ref-plaits`, `fm1-ref-braids-fx`, `fm1-ref-room`: upstream Mutable code driven as the modules drive it), the Schwung selftest and its ThreadSanitizer race harness, the effects' own test tools, `fm1-smooth-test`, which drives any engine or effect with parameter changes at any frame, `fm1-idle-test`, which holds the idle paths to the effects built without them ([above](#idle-at-pass-through)), `fm1-fx3-hostile`, a reviewer's checks that hold Room, Hall, Gate and Plate's Freeze to one standard (random schedules of every parameter at any block pattern, memory fill and three rates; the Gate never amplifying; tails at the longest settings reaching exact zeros; tests/test_engines_fx3_hostile.py), and `fm1-shapes-hostile`, a reviewer's checks of Shapes at Braids' edges (random scripts on every shape at any block pattern and memory fill; the pitch, Comb and Wave Line clamps holding bit for bit; tests/test_engines_shapes_hostile.py) |
| `mk/*.mk` | Build fragments, one per stream of engines |
| `sanitizers/` | Exemptions for vendored code under ASan/UBSan (below) |
| `third_party/mutable/` | Mutable Instruments code, MIT, unmodified; see `UPSTREAM.md` |
| `third_party/msfa/` | Google's msfa, Apache-2.0, unmodified; see `UPSTREAM.md` |
| `third_party/felucca-fm6/` | Felucca's `fm6_core.c`, Apache-2.0, unmodified: FM6's test oracle only |
| `third_party/schwung*/` | Schwung's ABI headers and the two modules, MIT, unmodified; see each `UPSTREAM.md` |

### The renderer's test options

| Option | What it is for |
| --- | --- |
| `--input silence\|impulse\|noise\|sine` | The source when there is no sound engine |
| `--fx ID [--fx-param NAME=VALUE]...` | Effects, applied in order after the source |
| `--frames N`, `--rate HZ` | Host block and rate (64 and 44,118 by default) |
| `--bend T:SEMITONES` | A pitch-bend event (finite, within ±48), at a block boundary like notes |
| `--param-at T:NAME=VALUE` | Turn a sound engine's parameter during the render |
| `--note-param-at T:KEY:NAME=OFFSET`, `--note-pitch-at T:KEY:SEMITONES` | Per-note offsets for the voice sounding KEY, after that block's note-ons ([above](#per-note-offsets)); `#INDEX` in place of NAME sends any index |
| `--fx-param-at T:K:NAME=VALUE` | Turn a parameter of the K-th effect (the first `--fx` is 1) during the render, at a block boundary like `--param-at`; the parity scenarios' `fx_param_at` |
| `--fill BYTE` | What instance memory holds before `create`; every engine must render byte-identically from any fill |
| `--fault T[..T1]:VALUE` | Overwrite the bus after the source with `nan`, `inf` or any value, for one frame or a span, to test recovery |
| `--mod FILE`, `--log-mod FILE.jsonl` | Modulation: a rack and slots from a text file, and one JSON line per control tick ([mod/README.md](mod/README.md#hosting)) |
| `--list-mod` | The modulation kinds with their parameters' uids and flags, their ports, the system sources and the host parameters, as JSON |
| `--sysex FILE.syx` | DX7 voices into FM6's user slots (`--engine dx7`), before the first block; repeatable ([msfa.md](msfa.md)) |
| `--tempo BPM` | The tempo effects with the API v3 extension hear without a sequencer (20–300, default 120); with `--cmd` or `--seq` they hear the sequencer's ([above](#engine-api-v3)) |

## Build and checks

Build flags match the FM-1 toolchain profile: `-std=c++11 -fno-exceptions
-fno-rtti`. Vendored Mutable code also gets `-fwrapv`: Braids and stmlib
rely on wrapping signed arithmetic, as they did under ARM GCC on the modules,
and `-fwrapv` makes that defined, so no optimiser can exploit it. Keep it in
the JieLi build.

CI runs three engine jobs:

- the full test suite on Linux and macOS;
- a 32-bit (`-m32`) build that runs every engine test and prints every
  instance size, to catch pointer-size assumptions before pi32v2 does;
- ASan + UBSan over every engine test, halting on the first report.

The sanitizer run, locally (clang, because the ignorelist is a clang flag):

```bash
make -C engines clean
make -C engines CC=clang CXX=clang++ OPT=-O1 \
    EXTRA="-fsanitize=address,undefined -fno-omit-frame-pointer -g -fsanitize-ignorelist=sanitizers/ignorelist.txt"
UBSAN_OPTIONS=suppressions=$PWD/engines/sanitizers/ubsan.supp:halt_on_error=1 \
    python -m pytest tests/test_engine*.py
make -C engines clean
```

Use a recent clang: on a kernel with 32 bits of mmap randomness, clang
14's ASan runtime segfaults at random in Macro and Drums alike, with no
report [verified 2026-10-05: the build host's Linux 7.0 kernel has
`vm.mmap_rnd_bits` 32; Debian bookworm's clang 14.0.6 crashed in a
container there, and trixie's 19.1.7 runs clean].

Each exemption in `sanitizers/` names one vendored file and the quirk it
covers: Braids' and stmlib's wrapping integer arithmetic, Plaits' six-op
`Pow2Fast` negative shift, and Plaits' LPC speech out-of-bounds read (an
upstream candidate). Our own code gets none. msfa needs none: its wrapping
phases and left shifts of negative values are built with `-fwrapv`, under
which neither Apple's clang nor clang 18 on Linux reports them [verified,
2026-10-05: FM6's tests under ASan + UBSan, with no exemption].

`build/fm1-fx-hostile-test` (`test/fx_hostile_test.cc`, run by
`tests/test_engines_fx_hostile.py`) puts the five master-bus effects (DJ
Filter, Tilt, EQ, Isolator, Master Sat) through the same hostile checks of
the host contracts: parameters changed at any frame in blocks of 1 to 4,096
frames, instance memory filled with NaNs, infinities or random bytes,
seconds of garbage parameters and input followed by one setting (the output
must then be a fresh instance's), the pass-through settings on input with
−0, subnormals and ±16, parameters thrown between their ends every frame,
tails, host rates 8–384 kHz, every glide landing at four rates, and indices
past the table. It found the Isolator's stalled crossover glide
([above](#isolator)); a new effect for the master bus takes a line in it.

## What stage A has found

- **Tuning survives the rate change.** The Mutable engines stay within
  ±5 cents at A2, A4 and A6 at 44,118 Hz without touching their sources.
  Effects written for 48 kHz get their loop gains and damping rescaled; their
  delay lengths and LFOs run 8–9 % long and slow (mi-fx.md).
- **Memory decides the voice caps.** Instance sizes, on the 64-bit desktop
  and on a 32-bit (`-m32`) build like pi32v2's [verified 2026-10-05: this
  Mac, and GCC 12 `-m32` in a container on aeon]:

  | Engine | 64-bit bytes | 32-bit bytes | Why |
  | --- | --- | --- | --- |
  | Shapes, 12 voices | 207,448 | 206,624 | each Braids oscillator carries ~17 KB of physical-model state |
  | PSX Verb | 134,400 | 134,368 | a fixed 128 KB work area, as upstream |
  | Sophie, 12 voices | 78,080 | 78,048 | ring delays per voice |
  | Macro Heavy, 4 voices | 71,456 | 71,248 | ~17 KB per voice (Particle and String arenas) |
  | Plate | 65,728 | 65,728 | 32,768 16-bit delay words, as Rings; Freeze added 16 and 32 bytes (2026-10-05, measured with clang for x86-64 and i386 after merging main) |
  | Echo | 65,744 | 65,744 | 16,384 stereo cells of 16-bit words |
  | Macro, 12 voices | 32,448 | 19,584 | mostly pointer tables, which halve on 32-bit |
  | Diffuse | 18,912 | 18,912 | |
  | Comb | 17,840 | 17,840 | two delay lines, fs / 20 Hz each (the Filter's until 2026-10-05, when it took 18,368) |
  | FM6, 12 voices | 15,848 | 15,848 | msfa's state, 32 user voices, no pointers; at 44,118 Hz (4,100 more at other rates, the frequency table); msfa's tables are const data, flash on the FM-1 ([msfa.md](msfa.md), "Tables in flash") |
  | Six-Op FM, 8 voices | 12,776 | 11,008 | |
  | Limiter | 11,008 | 11,008 | 5 ms of lookahead at 44,118 Hz; 26,912 at 102 kHz and above |
  | Drums, 12 voices | 7,616 | 7,424 | a 224-byte model object per voice (Ring Hat's), 16 pads' values and ramps, one resampler |
  | Ensemble | 4,752 | 4,736 | |
  | Filter | 656 | 656 | since Comb left it (2026-10-05) |

  The figures include the native-rate resamplers (about 1.3 KB each), the
  six engines' per-note offsets ([above](#per-note-offsets)) and the
  SMOOTH ramps (12 bytes per parameter; 176 bytes in each Schwung instance
  on 64-bit and 160 on 32-bit, for eight ramps, Sophie's unused),
  measured after S7b merged with main (32-bit: GCC 12.2 in Debian). The
  master-bus effects are small and hold no pointers: DJ Filter 224 bytes,
  Tilt 144, Master Sat 336, Isolator 240 and EQ 368, on 64-bit and 32-bit
  builds alike [verified: `fm1-render`'s `fx_bytes`, and `instance_size`
  compiled by clang for i386 and wasm32, 2026-10-05]; the idle path
  (2026-10-06) took Master Sat to 352, Isolator to 256 and EQ to 416.

  The stock layout leaves a gap of 387,924 bytes, part of it stock's heap
  (docs/11 §2, [inferred]). Most engine-plus-two-effects chains fit in it;
  Shapes at 12 voices takes more than half on its own, and Shapes with PSX
  Verb and Plate (406,720 bytes on 32-bit) does not fit. Shapes needs a lower cap on the
  FM-1, or its physical-model shapes split into a smaller engine.
- **Host contracts, now tested for every engine** (tests/test_engine_host.py):
  output does not depend on instance memory's prior contents; any
  parameter value, NaN included, is survived; the bus limiter recovers from
  NaN, infinities and huge samples. The limiter used to stop limiting for
  good after one NaN, and NaN parameters reached undefined float-to-int
  conversions in the first engines; both are fixed.
- **Schwung modules port through the shim unchanged**, with three
  conditions the API now states: a module's init runs once (a second init
  rewrote tables another instance was rendering through), int16 effects need
  headroom so overs reach the limiter instead of clipping, and `atof`/`strtod`
  go to a heap-free parser because newlib's can allocate (schwung.md).
- **Upstream bugs and quirks**, all worked around in our wrappers with the
  vendored files unmodified: Plaits' `WavetableEngine` arena overrun, the
  LPC speech out-of-bounds read, Six-Op's divide by zero on zero-length
  renders, and more (plaits-heavy.md, `notes/upstream-candidates.md`).
- **Relative cost, desktop only** (Apple M1 Max, all voices sounding, share
  of the 1.451 ms block):

  | Engine | Share of block |
  | --- | --- |
  | Macro, most models (12 voices) | 1.0–1.8 % |
  | Macro, 2-op FM (12) | 4.9 % |
  | Macro Heavy, most models (4) | 0.5–0.9 % |
  | Macro Heavy, Particle (4) | 1.75 % |
  | Six-Op FM (8) | 0.75 % |
  | FM6 (12) | 0.36–0.64 %; 0.9–1.15 % on algorithms 4 and 6 with feedback |
  | Shapes (12) | 0.2–0.6 % |
  | Each Mutable effect | 0.03–0.06 % |
  | Fold | 0.12 % |
  | Drive | 0.17–0.23 % |
  | Filter | 0.06–0.26 % (Formant to SK Mixed) |
  | Comb | 0.05 % |
  | Comp | 0.11–0.15 % |
  | Limiter | 0.07–0.10 % |
  | DJ Filter | 0.004 % in the dead zone, 0.05–0.07 % filtering (12 to 24 dB) |
  | Tilt | 0.04 % |
  | Master Sat | 0.15–0.16 % |
  | Isolator | 0.13 % |
  | EQ | 0.13 % |

  The four effects of the second pack: noise in, best of five 20-second
  runs of `fm1-render`, Fold 0.13 % and Plate 0.06 % in the same run
  [verified, 2026-10-02]. The five of the master-bus pack the same way,
  Fold 0.13 % and Plate 0.06 % again in the same run [verified,
  2026-10-05]. Tilt, Master Sat and EQ cost as much at their bypass
  settings (Tilt and EQ flat, Master Sat at Mix 0) as when working: their
  filters keep running so a change fades in.

  pi32v2 is a much narrower core and these figures do not transfer; stage B
  measures the real ones. They do rank the engines for the voice caps.

## The exit test: renders against upstream

Stage A's exit test (docs/11 §8) is that our engines render what upstream
Mutable code renders, within a tolerance. Three reference renderers compile
the vendored upstream code on its own and drive it as the modules' firmware
does: `plaits::Voice` every 12 samples at 47,872 Hz, and
`braids::MacroOscillator` every 24 samples at 96 kHz, with Rings' reverb and
Plaits' ensemble and diffuser at their native rates, and (since 2026-10-05,
`fm1-ref-room`) Clouds' diffuser and reverb for Room. The tests render both
sides and compare [verified: tests/test_engines_reference_*.py, 487 tests on
2026-10-05; 427 on 2026-10-01, before Room]:

| Engine | At the upstream rate | Details |
| --- | --- | --- |
| Macro, Macro Heavy (21 of Plaits' 24 slots) | sample for sample, to within fm1-render's 16-bit rounding (-87 to -88.5 dBFS); the random engines too, since both sides seed stmlib's generator alike | [reference-plaits.md](reference-plaits.md) |
| Six-Op FM (3 slots) | close, not identical: correlation ≥ 0.98, from its 16-sample envelope blocks against upstream's staggered 24-sample chunks | [reference-plaits.md](reference-plaits.md) |
| FM6 (32 algorithms, six voices) | against Felucca's port of the same core (not upstream msfa itself, which has no polyphonic host here): 28–40 dB SNR and 0.3 dB of envelope on the algorithms, within 0.7 dB of envelope where the two step pitch at different blocks | [msfa.md](msfa.md) |
| Shapes (47 shapes) | within 0.52 LSB, physical models and random shapes included | [reference-braids-fx.md](reference-braids-fx.md) |
| Plate, Ensemble, Diffuse | within 0.5 LSB | [reference-braids-fx.md](reference-braids-fx.md) |
| Room | within 0.5 LSB, at Clouds' 32 kHz and at 44,118 Hz | [below](#room) |

The comparison checks our wrappers. The engine DSP is the same object code on
both sides, so a test pins the 129 vendored Plaits files it compiles by hash.
Reviewers mutation-tested both lanes: 50 of 51 Plaits mutants and all but one
Braids/effects mutant now fail a test. The one survivor is a Six-Op
envelope block change inside the intended tolerance; the other, Shapes
ignoring pitch bend, fails the bend tests since the renderer gained `--bend`.

It found one real bug: **Shapes split each 64-frame host block into 24 + 24 +
16** while Braids only ever renders 24. Twenty-two shapes drifted (Bell and
Drum decayed 9–16 % fast, Comb, Vowel and Wave Line glitched), output depended
on the host's block size, and 11 shapes crashed on odd-sized calls (a heap
overflow under ASan). Shapes now renders exactly 24-sample blocks and buffers
them, as Macro does with 12.

**Native rates (2026-10-01, the owner's decision).** The Mutable engines
now run at their modules' own rates whatever the host's rate: Shapes runs
Braids at 96 kHz, and Macro, Macro Heavy and Six-Op run Plaits at
47,872.34 Hz. Each engine resamples its mix once with `fm1_resampler.h`
([resampler.md](resampler.md)), which passes samples through bit for bit
when the rates are equal. At the FM-1's 44,118 Hz this removed every
difference pitch-only correction had left: Plaits' envelopes ran 8.5 % long,
Braids' struck shapes rang 1.6–2.8 times as long, TIMBRE-derived rates ran
low (the noise clock by 1.41 semitones), and the string model read -9.5 cents
at A2. Now, against upstream rendered at its own rate and resampled the same
way [verified: tests/test_engines_reference_*.py]:
- 20 of the 21 Macro and Macro Heavy slots match byte for byte, and Chiptune
  to 1 LSB;
- Six-Op matches closely (correlation ≥ 0.988);
- all 47 shapes match within 0.55 LSB, and struck decays at 0.9995–1.006 of
  upstream.

The cost is CPU: Shapes takes 2.5–3× its old time and the Plaits engines
1.1–1.5× (desktop), mostly the extra samples plus about 70–114
multiply-adds per output for the resampler. Hosts above an engine's native
rate are refused. The effects still rescale their loop gains and damping,
keeping decay within 3–4 %.

## Open questions and next steps

- **FM6** has its own list ([msfa.md](msfa.md), "Open questions"): a
  listening pass over its 32 voices, the DX7's envelope holds, AM depths
  measured on a DX7, the user bank in flash on the FM-1. Answered
  2026-10-06: the name stays (borrowed from Felucca's FM6, with msfa
  itself), msfa's tables are const data (flash), and the simulator loads
  `.syx` files.
- **Six-Op FM's patch data** has no stated origin upstream. The 23 patch
  names that are trademarks or a person's name are shown under names of our
  own; `-DFM1_SIXOP_ORIGINAL_NAMES` shows the stored ones in a personal build
  (plaits-heavy.md, "The patch data"). The data itself still needs review
  before anything commercial.
- **Shapes' memory:** 207 KB for 12 voices. A voice cap for the FM-1 build,
  or a split of the physical-model shapes.
- **Resampler cost on pi32v2:** the stronger second stage costs about 114
  multiply-adds per output; the cheaper half-band version (about 70, with
  18–22 kHz unprotected) is commit `f12448c`. The owner's decision
  (2026-10-01): keep Braids at 96 kHz with the full resampler, and decide
  again once stage B measures the cost on pi32v2. Until then two cheaper
  variants stay candidates for build options: the half-band second stage,
  and Braids at twice the host rate (88,236 Hz) with only a half-band
  decimator (about 18 multiply-adds, but Braids' timing about 8 % off).
- **Effects at native rates:** not done. Each effect would need a resampler
  on its input and output; the measured gap is small (decay within 3–4 %,
  delays 8.5 % long).
- **Six-Op's polarity** is inverted relative to Macro and Macro Heavy
  against the same upstream output words. Harmless alone; worth making
  consistent before engines are layered or crossfaded.
- **Host features the streams asked for:** a random seed (`--seed`; stmlib's
  generator is a global in vendored code, so the host cannot seed it without
  depending on one library), an active-voice diagnostic so voice freeing can be tested
  without timing, and a reset call so
  effects can drop their tails without re-creating a 64 KB instance. Also a
  per-file SHA-256 manifest from `vendor.py`, so a test can pin the whole
  vendored tree rather than the files one lane compiles.
- **Wide time ranges on linear knobs.** The Gate's Attack (0–1,000 ms),
  Hold, Decay and Lockout span three decades or more, and the panel steps a
  hundredth of a parameter's range (10 ms of Attack), as it does for every
  parameter here; `fm1_param_t` has no taper field. Presets and locks reach
  any value; a log taper for ms and Hz parameters is a panel decision.
- **Stage B**, on the JL-AC79 dev board: the same sources under JieLi's
  clang, real cycle counts, and whether pi32v2's FPU traps on divide by zero
  or handles subnormals slowly (several upstream quirks rely on it not
  trapping).

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
| `sw-sophie` | Sophie | sound | 12 | a Schwung module (Matt Estela, MIT), through the shim | [schwung.md](schwung.md) |
| `test-sine` | Test Sine | sound | 12 | this repository | tests the host and the analysis |
| `plate` | Plate | effect | – | Rings' reverb | [mi-fx.md](mi-fx.md) |
| `ensemble` | Ensemble | effect | – | Plaits' ensemble | [mi-fx.md](mi-fx.md) |
| `diffuse` | Diffuse | effect | – | Plaits' diffuser | [mi-fx.md](mi-fx.md) |
| `sw-psxverb` | PSX Verb | effect | – | a Schwung module (Charles Vestal, MIT), through the shim | [schwung.md](schwung.md) |
| `crush` | Crush | effect | – | this repository, after DaisySP's Decimator and Bitcrush (Electro-Smith, MIT) | [below](#crush); a bitcrusher and sample-rate reducer |
| `fold` | Fold | effect | – | this repository | a wavefolder with anti-aliasing; [below](#fold) |
| `drive` | Drive | effect | – | this repository | overdrive and saturation: Soft, Tube, Diode, Fuzz and Tape, anti-aliased; [below](#drive) |
| `echo` | Echo | effect | – | this repository | a stereo ping-pong delay, 10–1,000 ms; [below](#echo) |
| `filter` | Filter | effect | – | this repository | seven filter types (SVF, ladder, diode ladder, Sallen-Key, Steiner, comb, formant), zero-delay feedback; [below](#filter) |
| `comp` | Comp | effect | – | this repository, after Giannoulis, Massberg and Reiss (JAES 2012) | a feed-forward compressor: peak or RMS, soft knee, parallel mix; [below](#comp) |
| `test-gain` | Test Gain | effect | – | this repository | a gain stage for tests |

The Mutable Instruments engines are credited to Emilie Gillet in each
engine's `credits` string and named without MI's trademarks
(`third_party/mutable/UPSTREAM.md`).

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
10^-20 so a tail never goes subnormal on pi32v2. An instance is 96 bytes on
a 64-bit desktop, all floats and one `uint32_t`, so the same on 32-bit
[inferred]. On this desktop (Apple M1 Max) it took 400–500 ns per 64-frame block,
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

Drive and Level are in decibels; `fm1_unit_t` has no code for them yet, so
their unit is `none`.

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
  make 0.435 [verified: `fm1-drive-test`]. Type and Auto take locks but no
  modulation: a rounded route would step between Types, not sweep. Filter
  states below 10⁻²⁰ flush to zero.
- **Determinism:** no libm beyond `floorf`, `fabsf` and `sqrtf`, which IEEE
  754 defines exactly; 2^x, sine and cosine for the controls are
  polynomials in the file. A `#pragma STDC FP_CONTRACT OFF` keeps clang
  from fusing multiply-adds, which Apple clang otherwise does (96 fused
  operations in this file; Fold has 64) [verified: `objdump`]; GCC ignores
  the pragma, so a GCC build for a target with a fused instruction needs
  docs/14's `-ffp-contract=off`. `fm1-drive-test
  hash`, the bits of 2 s of output per Type with every parameter moving,
  is the same from Apple clang on arm64, GCC 12 on x86-64 and GCC 12 at
  `-m32 -msse2 -mfpmath=sse` [verified, 2026-10-02]; x87 arithmetic
  (`-m32` alone) differs, as its excess precision does everywhere. JieLi's
  clang 4.0.1 compiles the file for pi32v2 without a warning at `-O2` and
  `-Oz`, with identical code at `-ffp-contract=off` and `=fast` [verified].
- **Memory and cost:** 240 bytes per instance on x86-64, i386 and pi32v2
  (the struct is 236, no pointers) [verified: fm1-render's `fx_bytes`, CI's
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

- **Memory:** 16,384 cells per side of 16-bit words (64 KiB), plus 192 bytes
  of state: 65,728 bytes, whatever the host rate. The 32-bit figure equals
  the 64-bit one because the instance holds no pointers [inferred; CI's
  32-bit job reports it]. The words hold ±2.0, 6 dB of headroom over full
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

A multimode filter (`src/fx_filter.cc`, our own code, MIT) with seven
types, every one of whose parameters is a modulation target. No code is
taken from anywhere; the designs are credited below and in the source.
Stereo in, stereo out.

| Page | Knob | Range (default) | What it does |
| --- | --- | --- | --- |
| 1 | Type | SVF, Ladder, Diode, K35, Steiner, Comb, Formant (Ladder) | The filter. A change crossfades the old type into the new one over 5 ms; the new one starts from rest |
| 1 | Cutoff | 20 Hz–18 kHz, log (2 kHz) | The corner, or the resonance: where each type self-oscillates. Never above 0.45 of the host rate (3.6 kHz at 8 kHz) |
| 1 | Resonance | 0–1 (0.25) | Up to self-oscillation for SVF, Ladder, Diode, K35 and Steiner (from about 0.93–0.96); Comb's loop gain; Formant's bandwidth |
| 1 | Drive | 0–1 (0) | Input gain 1× to 16× into the filter's saturating curves, output down by its square root: quiet signals up to 12 dB louder, loud ones saturate |
| 2 | Mode | 0–3, continuous (0) | Per type, below; between whole numbers the two neighbours are blended |
| 2 | Morph | 0–1 (0) | Spread for the five analogue-style types (left channel up to an octave down, right up); polarity for Comb; the vowel for Formant |
| 2 | Mix | 0–1 (1) | Dry to wet. At 0 the input passes through unchanged |
| 2 | Level | 0–2 (1) | The wet signal's gain |

| Type | After | Mode 0 / 1 / 2 / 3 | Notes |
| --- | --- | --- | --- |
| SVF | Andrew Simper's (Cytomic) trapezoidal state-variable filter | low-pass / band-pass / high-pass / notch | Linear but for its self-oscillation: the damping goes slightly negative at the top of Resonance and an energy term (bp² + lp², last sample) holds the oscillation at a fixed, sinusoidal level |
| Ladder | the transistor ladder (Huovilainen, DAFx-04; Zavalishin ch. 5) | 24 / 18 / 12 / 6 dB/octave (taps on the 4th to the 1st stage) | One saturating curve where the feedback meets the input. Self-oscillates from k = 4 |
| Diode | a TB-303-style diode ladder: four coupled capacitors, written here from the node equations | as Ladder | The coupled stages make a tridiagonal system. Analysed here: it oscillates at k = 18.39 and 1.195× its integrators' frequency, and with no feedback it is already −3 dB at 0.119× [verified: tests and a numerical scan]. Its tuning follows a fitted curve between the two, so Cutoff is near −3 dB with no resonance and the pitch at full resonance |
| K35 | the Korg35 Sallen-Key low-pass of the later Korg MS-20 (Zavalishin ch. 5; Will Pirkle's application note) | low-pass / band-pass / high-pass / notch | H = 1/(s² + (2 − k)s + 1); the feedback through the saturating curve. Self-oscillates from k = 2 |
| Steiner | the Steiner-Parker Synthacon's filter: an equal-component Sallen-Key with mixed inputs | low-pass in / band-pass in / high-pass in / notch (L, −2B, H) | y (s² + (3 − K)s + 1) = L + sB + (s² + 2s)H, from its node equations (written here), so its high-pass input has a 6 dB/octave skirt below the corner. Both resistors are diodes, whose current saturates, and the feedback passes an asymmetric clip |
| Comb | Zölzer's universal comb (*DAFX*, ch. 2) | feedback (peaks) … feedforward (notches) | One delay of fs / Cutoff samples, linear interpolation; Resonance is the loop gain, 0.25–0.98; Morph 0 positive (peaks at multiples of Cutoff), 0.5 none, 1 negative (odd multiples of Cutoff/2: an octave lower, hollow) |
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
  [reported]). SVF, Ladder and Diode solve once per sample. K35 and Steiner
  take the secant again at that first solution and solve a second time: a
  fixed single refinement, never a convergence loop. Without it K35's
  self-oscillation drifted 16 cents sharp at 5 kHz and Steiner's up to a
  semitone [verified].
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
  - K35 and Steiner at Resonance 0: −6.02 and −9.54 dB at Cutoff (two
    coincident poles; Sallen-Key Q 1/3). Steiner's high-pass input falls
    5.7 dB per octave below its corner, K35's high-pass 11.7.
  - Self-oscillation, over 110 Hz–5 kHz at 44,118 Hz and at 440 Hz at
    8, 96 and 384 kHz: SVF within 0.01 cent of Cutoff, Ladder and Diode
    within 1, K35 within 2.5; Steiner a steady 19–23 cents flat (its
    diodes load the oscillation). None oscillates at Resonance 0.85.
  - Comb: peaks 21 dB above its troughs at Resonance 0.8; feedforward
    notches −34 dB at Resonance 1. Formant: at a vowel's formants the
    gain is 8–33 dB above that at the other vowel's.
  - Drive 1 raises the 3rd harmonic of a 0.5 sine from −62 to −112 dB
    (Drive 0) to −10 to −27 dB. Steiner makes a 2nd harmonic (−64 dB at
    Drive 0) where K35 makes none, and a louder input darkens it (2 kHz
    falls 2 dB further than 250 Hz) where K35's tilt holds.
- **Type changes** crossfade over 5 ms with both types running, so no
  switch clicks: across all 42 ordered pairs, a 440 Hz sine's largest step
  between neighbouring samples at the switch is at most 4 % above either
  type's own [verified]. A change asked for during a crossfade waits for
  its end.
- **Glide and control rate:** Cutoff, Resonance, Drive, Mode and Morph
  glide (5 ms) and the coefficients follow every 8 samples, counted from
  `create`, so any block size gives the same output; Comb's delay moves
  sample by sample between those steps, so it never jumps. Mix and Level
  glide every sample. Values set before the first block apply from its
  first sample.
- **Determinism.** No libm anywhere in the effect: 2^x, log2 and tan are
  polynomials in the file, beside fabsf, floorf and sqrtf, which IEEE 754
  rounds exactly. 24 renders (every type with every parameter moved, at full
  resonance and drive from an impulse, at 96 kHz, two chains of two filters
  after Macro, host blocks of 7) are byte-identical from GCC with glibc,
  GCC with musl and Emscripten under Node [verified: containers on the LAN
  build host, 2026-10-02]. The browser module is not rebuilt here.
- **Contracts:** the input guard of `mi_fx.cc`; `fm1_param_clamp`; every
  field set in `create`; silence in gives exact silence out from rest at any
  setting, self-oscillating ones included; tails flush to exact zero within
  0.2 s (states below 1e-15 flush, so no subnormals). Host rates 8–384 kHz;
  10 s of random parameter changes (NaN and infinities included) and noise
  bursts at the guard's limit stay finite at 8, 44.1, 96 and 384 kHz, and
  every type at Resonance 1, Drive 1 and Level 2 under that noise stays
  below 2.0 [verified].
- **Memory:** 688 bytes of state plus Comb's two delay lines of fs/20 Hz + 4
  floats: 18,368 bytes at 44,118 Hz (3,920 at 8 kHz, 154,320 at 384 kHz).
  The same on i386, since the instance holds no pointers [verified: GCC
  −m32 in a container]. The lines are never cleared: a type reset marks
  them empty and reads beyond what was written since return 0.
- **Cost** per 64-frame stereo block on the desktop (Apple M1 Max, best of
  seven, noise in), against Plate's 0.89 µs and Fold's 1.8 µs in the same
  runs: Comb 0.8, Formant 0.9, SVF 1.4, Ladder 2.2, Diode 2.4, K35 3.2 and
  Steiner 3.6–4.8 µs; with Cutoff and Resonance moved twice a block and
  Spread on, up to 4.9 µs (Steiner), 0.34 % of the block [verified:
  `fm1-filter-test --bench` and `fm1-render`]. A crossfade costs both types
  for 5 ms. By operation count, Steiner's worst case is about 1.4 Folds and
  the others less [inferred]; stage B measures pi32v2.
- **Names.** The types are named for their circuits, not their products:
  K35 is the MS-20-style filter, Diode the 303-style one; neither M-VAVE nor
  any synth maker is involved.
- **Type's flags: MOD.** Since a change crossfades, nothing is cut: the
  sequencer may lock it and a modulation route may step it (rounded).
  NOLOCK (a destructive change) and LATCH (read at note-on; an effect has
  none) would both misdescribe it (the ENUM table below).
- `build/fm1-filter-test` (`test/filter_test.cc`) drives Filter where
  fm1-render cannot: changes mid-stream, the crossfade, host rates, sine
  sweeps and self-oscillation. `--gain` and `--osc` print one measurement;
  `--bench` the cost.

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
          -> gain = Makeup - reduction;   out = dry x (1 - Mix) + dry x gain x Mix

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
| 3 | Auto Gain | Off, On (Off) | Adds the curve's reduction at 0 dBFS to Makeup, so a steady full-scale signal stays at full scale: 22.5 dB at −30 dB and 4:1 |

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
  Linux, macOS and 32-bit jobs check it too). `-ffp-contract=fast` differs,
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
    5 ms.
- **Contracts:** the input guard of `mi_fx.cc` (NaN to 0, clamp to ±16);
  parameters through `fm1_param_clamp`; Threshold, Ratio, Knee, Makeup, Mix
  and the detector's crossfade glide over 5 ms, sample by sample, so any
  block size gives the same output; values set before the first render
  apply at once. Silence in is exact silence out. A fault does not latch: a
  second after it the output is the clean render's within one 16-bit step.
  States flush to zero (power below 1e-20, reductions below 1e-6 dB).
- **Memory:** 192 bytes (`sizeof` 188) on x86-64, i386 and pi32v2: no
  pointers [verified: gcc and JieLi's clang, 2026-10-02]. Code for pi32v2:
  3.6 KB at `-O2`, 2.1 KB at `-Oz`, and 0.8 KB of constant data.
- **Cost:** about 75 operations, one divide (the logarithm) and one
  exponential per stereo frame [inferred: by count]. Desktop (Apple M1
  Max, `fm1-comp-test --cost`, noise): 1.5 µs per 64-frame block with Peak,
  1.6 µs with Glue, Auto Rel and Auto Gain, 1.8 µs while a parameter
  glides: 0.10–0.12 % of the 1.451 ms block, about Fold's.
- **Gain reduction for modulation:** `fm1_comp_reduction_db(instance)`
  (`include/fm1_comp.h`) returns the reduction applied to the last frame,
  in dB (0 or more, finite, makeup not included). It is already smoothed by
  Attack and Release, so a source reading it once per block or tick does not
  alias. It is not part of `fm1_engine_t`: a host checks that the unit's
  engine is `comp` first. It is the REDUCTION output docs/16 §3.7 plans for
  Duck, here from a compressor in the chain rather than a tap.
- **Units.** Attack and Release are in ms. Threshold, Knee and Makeup are in
  dB, which `fm1_unit_t` has no code for yet (`FM1_UNIT_DB` would be the
  addition), so they show as bare numbers.
- **Not yet: sidechain.** The detector takes a level per frame, so a key
  signal only changes where that level comes from. The plan, in order: a
  high-pass on the detector's input, inside the effect (one more one-pole;
  stops low notes pumping the mix); then a key from elsewhere in the chain,
  which needs the host to hand an effect a second buffer. That is either
  docs/16 §3.7's audio tap, or an engine API addition (a key buffer next to
  `render`'s); neither exists yet. Lookahead, which needs a delay line, is
  not planned.

## Parameters (engine API v2)

Since API v2 (docs/15 stage S7a, docs/13 M2), `fm1_param_t` carries four
more fields after its name, type, range, default, enum names and page
(`include/fm1_engine.h`):

| Field | What it is |
| --- | --- |
| `uid` | 1–4,095, unique in its engine and never changed or reused. It is what a sequencer lock, a modulation route (docs/16) or a preset stores, so reordering or extending a table moves nothing. A uid means something only together with its engine's id |
| `flags` | `FM1_PARAM_LATCH`, `SMOOTH`, `NOLOCK`, `MOD` and `INPUT`, below |
| `unit` | `FM1_UNIT_NONE`, `SEMI`, `MS`, `HZ`, `PCT` or `DEG`: the unit the value itself is in |
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
| SMOOTH | Continuous and read every block | The engine ramps a change, from docs/15 stage S7b; until then the flag is a hint |
| NOLOCK | A change is destructive: it rebuilds voices, clears a buffer or moves the edit focus | A lock on it is refused and counted (engines/seq.md, Host contract); never a modulation destination |
| MOD | Accepts modulation (docs/16 §2.2). Every FLOAT has it by default; an ENUM only when it says so, and is then rounded. Never with NOLOCK | The modulation matrix, from docs/16 stage MG1 |
| INPUT | A bare signal input: FLOAT, −1..1, default 0, hidden from the knob pages | Modulation modules only; no engine has one |

Every FLOAT parameter here is SMOOTH and MOD (`FM1_PARAM_CONTINUOUS`),
except Sophie's, which are LATCH and MOD: a triggered voice copies its pad's
patch (`sophie.c`, `trigger_voice`), so Sophie reads all of them at note-on.
`fm1_param_lockable`, `fm1_param_modulatable` and `fm1_param_index(engine,
uid)` are the helpers. `fm1-render --list` prints each parameter's uid,
flags (by name), unit and abbreviation. The four fields make `fm1_param_t`
36 bytes on pi32v2 and i386 (28 before) and 48 on x86-64 (40) [verified:
`tools/jieli/compile-check.sh`, 2026-10-02, 67 of 67 objects compiled in
all four profiles]: 704 bytes more of read-only data for the 88 parameters
the registry defines.

**The ENUM parameters** [verified against each engine's code, 2026-10-02].
docs/15's table had eight; Macro's and Macro Heavy's LPG came with their
third page, Drive's Type and Auto with the effect.

| Engine | Parameter | Flags | Why |
| --- | --- | --- | --- |
| macro | Model | NOLOCK | `set_param` rebuilds all 12 voices (`BuildEngines`), cutting every note |
| macro | LPG | none | Read every block, and a change leaves notes sounding, so it can be locked. No MOD: a rounded route could end a note held under Off by switching to Ping |
| macro-heavy | Model, LPG | as Macro's | the same code |
| shapes | Shape | NOLOCK | Sets every voice's oscillator at once |
| sixop | Patch | LATCH, MOD | Read per voice at note-on, so a lock or a route picks the patch of the next notes |
| sw-sophie | Pad | NOLOCK | The module's edit focus, not a sound: it picks the pad the other parameters edit, so a lock on it would change what every other lane's locks mean. A change does leave sounding voices intact, the condition docs/15's table gave for lockable; the focus decided it |
| sw-sophie | Model | LATCH, MOD | Each voice keeps a copy of its pad's patch, so a change leaves sounding voices intact |
| sw-sophie | Filter Type | LATCH, MOD | The same. Hidden for now: its page is not exposed (schwung.md) |
| sw-psxverb | Model | NOLOCK | A new preset clears the 128 KB work area, cutting the tail. Effect locks wait for docs/15's O14 anyway |
| filter | Type | MOD | A change crossfades the old type into the new over 5 ms (the new from rest), so nothing is cut: lockable, and a rounded route steps through the types. Neither NOLOCK nor LATCH (an effect has no note-on) describes it |
| drive | Type | none | A change crossfades the two curves over 5 ms, so a lock is clean. No MOD: a rounded route would step between Types, not sweep |
| drive | Auto | none | Its gain glides like any other, so it can be locked |
| comp | Character, Auto Rel, Auto Gain | none | Read every frame, and a change hands over or glides without a step, so they can be locked. Not effects of a note, so no LATCH. No MOD: a rounded route would flip the detector or the release at control rate |

**Units and abbreviations.** Echo's Time, Comp's Attack and Release and
Sophie's Ring Time are in ms, Filter's Cutoff in Hz, Sophie's Tune in
semitones and its 0–100 knobs in %. Sophie's Decay is in seconds, and
Drive's Drive and Level and Comp's Threshold, Knee and Makeup in dB, for
which there are no unit codes yet, so they have none. Every other parameter
is a bare number (the 0–1 knobs, gains, bits, indices).

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

## Layout

| Path | What |
| --- | --- |
| `include/fm1_engine.h` | The engine API, version 2. C, no heap: the host asks `instance_size`, provides that memory (not zeroed), and the engine constructs itself in it. Typed parameters, four to a page (the FM-1 has four free parameter knobs), each with a stable uid, flags, a unit and an abbreviation ([above](#parameters-engine-api-v2)); `fm1_param_clamp` for NaN-safe ranges; the threading contract |
| `mod/` | Modulation primitives: an LFO, a Peaks-style envelope, slew, S&H, a Turing register and a tick clock divider. Heap-free C99, not wired in yet ([mod/README.md](mod/README.md)) |
| `include/fm1_seq.h`, `seq/` | The sequencer core: a heap-free C99 port of Movy's sequencer, with 4–8 routed tracks ([seq.md](seq.md), docs/13) |
| `midi_fx/` | The arpeggiator core `fm1_arp`: heap-free C99 after Yarns, MCL and Super Arp, with its test tool `fm1-arp`. Not wired into the renderer yet ([midi_fx/README.md](midi_fx/README.md)) |
| `include/fm1_mix_limiter.h` | The host's mix-bus limiter and bus guard. Twelve voices started in phase can exceed full scale; the bus holds the output under 0.98, and non-finite samples become silence |
| `src/registry.cc` | The static engine registry (tier 0 in docs/11 §5.2) |
| `src/mi_*.cc` | The Mutable-derived engines and effects |
| `src/fx_fold.cc` | Fold, a wavefolder effect of our own ([above](#fold)) |
| `src/fx_*.cc` | Effects written in this repository (Crush, [Drive](#drive), Echo, [Filter](#filter), [Comp](#comp); `fx_comp_math.h` is Comp's log2 and exp2 without libm) |
| `include/fm1_comp.h` | Comp's gain-reduction accessor, for a later modulation source ([above](#comp)) |
| `src/schwung_*`, `src/sw_*.cc` | The Schwung v2 shim and one adapter per module ([schwung.md](schwung.md)) |
| `host/render.cc` | `fm1-render`: plays a note script through an engine and an effect chain in 64-frame blocks at 44,118 Hz, applies the bus limiter, writes a WAV, prints JSON |
| `test/` | The reference renderers (`fm1-ref-plaits`, `fm1-ref-braids-fx`: upstream Mutable code driven as the modules drive it), the Schwung selftest and its ThreadSanitizer race harness |
| `mk/*.mk` | Build fragments, one per stream of engines |
| `sanitizers/` | Exemptions for vendored code under ASan/UBSan (below) |
| `third_party/mutable/` | Mutable Instruments code, MIT, unmodified; see `UPSTREAM.md` |
| `third_party/schwung*/` | Schwung's ABI headers and the two modules, MIT, unmodified; see each `UPSTREAM.md` |

### The renderer's test options

| Option | What it is for |
| --- | --- |
| `--input silence\|impulse\|noise\|sine` | The source when there is no sound engine |
| `--fx ID [--fx-param NAME=VALUE]...` | Effects, applied in order after the source |
| `--frames N`, `--rate HZ` | Host block and rate (64 and 44,118 by default) |
| `--bend T:SEMITONES` | A pitch-bend event (finite, within ±48), at a block boundary like notes |
| `--param-at T:NAME=VALUE` | Turn a sound engine's parameter during the render |
| `--fill BYTE` | What instance memory holds before `create`; every engine must render byte-identically from any fill |
| `--fault T[..T1]:VALUE` | Overwrite the bus after the source with `nan`, `inf` or any value, for one frame or a span, to test recovery |

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

Each exemption in `sanitizers/` names one vendored file and the quirk it
covers: Braids' and stmlib's wrapping integer arithmetic, Plaits' six-op
`Pow2Fast` negative shift, and Plaits' LPC speech out-of-bounds read (an
upstream candidate). Our own code gets none.

## What stage A has found

- **Tuning survives the rate change.** The Mutable engines stay within
  ±5 cents at A2, A4 and A6 at 44,118 Hz without touching their sources.
  Effects written for 48 kHz get their loop gains and damping rescaled; their
  delay lengths and LFOs run 8–9 % long and slow (mi-fx.md).
- **Memory decides the voice caps.** Instance sizes, on the 64-bit desktop
  and on a 32-bit (`-m32`) build like pi32v2's [verified: CI's 32-bit job on
  PR #6]:

  | Engine | 64-bit bytes | 32-bit bytes | Why |
  | --- | --- | --- | --- |
  | Shapes, 12 voices | 207,080 | 206,212 | each Braids oscillator carries ~17 KB of physical-model state |
  | PSX Verb | 134,224 | 134,208 | a fixed 128 KB work area, as upstream |
  | Sophie, 12 voices | 77,904 | 77,888 | ring delays per voice |
  | Macro Heavy, 4 voices | 71,104 | 70,880 | ~17 KB per voice (Particle and String arenas) |
  | Plate | 65,648 | 65,632 | 32,768 16-bit delay words, as Rings |
  | Echo | 65,728 | 65,728 | 16,384 stereo cells of 16-bit words |
  | Macro, 12 voices | 31,744 | 18,864 | mostly pointer tables, which halve on 32-bit |
  | Diffuse | 18,848 | 18,848 | |
  | Six-Op FM, 8 voices | 12,528 | 10,796 | |
  | Ensemble | 4,704 | 4,704 | |

  The 32-bit figures include the native-rate resamplers (about 1.3 KB each)
  [verified: CI's 32-bit job on PR #12]. Page 3 (2026-10-02) added 16 bytes
  to Macro and to Macro Heavy on the 64-bit build [verified]; their 32-bit
  figures predate it and grow by a similar few bytes [inferred].

  The stock layout leaves a gap of 387,924 bytes, part of it stock's heap
  (docs/11 §2, [inferred]). Most engine-plus-two-effects chains fit in it;
  Shapes at 12 voices takes more than half on its own, and Shapes with PSX
  Verb and Plate (404,672 bytes on 32-bit) does not fit. Shapes needs a lower cap on the
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
  | Shapes (12) | 0.2–0.6 % |
  | Each Mutable effect | 0.03–0.06 % |
  | Fold | 0.12 % |
  | Comp | 0.10–0.12 % |

  pi32v2 is a much narrower core and these figures do not transfer; stage B
  measures the real ones. They do rank the engines for the voice caps.

## The exit test: renders against upstream

Stage A's exit test (docs/11 §8) is that our engines render what upstream
Mutable code renders, within a tolerance. Two reference renderers compile the
vendored upstream code on its own and drive it as the modules' firmware does:
`plaits::Voice` every 12 samples at 47,872 Hz, and `braids::MacroOscillator`
every 24 samples at 96 kHz, with Rings' reverb and Plaits' ensemble and
diffuser at their native rates. The tests render both sides and compare
[verified: tests/test_engines_reference_*.py, 427 tests on 2026-10-01]:

| Engine | At the upstream rate | Details |
| --- | --- | --- |
| Macro, Macro Heavy (21 of Plaits' 24 slots) | sample for sample, to within fm1-render's 16-bit rounding (-87 to -88.5 dBFS); the random engines too, since both sides seed stmlib's generator alike | [reference-plaits.md](reference-plaits.md) |
| Six-Op FM (3 slots) | close, not identical: correlation ≥ 0.98, from its 16-sample envelope blocks against upstream's staggered 24-sample chunks | [reference-plaits.md](reference-plaits.md) |
| Shapes (47 shapes) | within 0.52 LSB, physical models and random shapes included | [reference-braids-fx.md](reference-braids-fx.md) |
| Plate, Ensemble, Diffuse | within 0.5 LSB | [reference-braids-fx.md](reference-braids-fx.md) |

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
  without timing, parameter smoothing (engine-side, the owner's choice: the
  SMOOTH flag is set, the ramp is docs/15 stage S7b), and a reset call so
  effects can drop their tails without re-creating a 64 KB instance. Also a
  per-file SHA-256 manifest from `vendor.py`, so a test can pin the whole
  vendored tree rather than the files one lane compiles.
- **Stage B**, on the JL-AC79 dev board: the same sources under JieLi's
  clang, real cycle counts, and whether pi32v2's FPU traps on divide by zero
  or handles subnormals slowly (several upstream quirks rely on it not
  trapping).

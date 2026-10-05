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
| `echo` | Echo | effect | – | this repository | a stereo ping-pong delay, 10–1,000 ms; [below](#echo) |
| `eq` | EQ | effect | – | this repository, on Andrew Simper's trapezoidal SVF (public domain maths) | a low shelf, a bell and a high shelf, exact at 0 dB; [below](#eq) |
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

No band is tuned above 0.45 of the host's rate. Gains and Level are in dB,
for which `fm1_unit_t` has no code yet (as Comp's); the frequencies carry
`FM1_UNIT_HZ`.

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
  filter.
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
- **Memory:** 368 bytes on 64-bit, and on 32-bit [verified: GCC i386], no
  tables and no delay lines.
- **Cost:** about 60 floating-point operations per sample and channel, flat
  or not, about 7,700 per 64-frame block; while bands glide, about 130 more
  and 2 divides per band every 8 samples. Desktop (Apple M1 Max, noise in):
  1.86 µs per block with the bands flat or set, 2.6 µs with all three
  gliding all the time, against Plate's 0.93 µs in the same run: 0.13 % and
  0.18 % of the 1.451 ms block. At one operation per cycle on pi32v2 that
  is about 2.2 % of a 240 MHz core [inferred]; stage B measures it.
- **Where it departs from the note:** the note proposed the vendored
  `stmlib::Svf` and stmlib's `SemitonesToRatio` tables for 10^(dB/40). The
  filter is written here instead, in the C subset like Fold, because the
  flat bypass and the mixing ramps need its two outputs and states directly;
  the maths is the same. The gains come from the 2^x polynomial, which is
  exactly 1 at 0 dB by construction, needs no table memory and is accurate
  to 1e-6 dB rather than 0.004 dB steps. The note's shared header for
  Tilt, DJ Filter, Isolator and EQ (the bell and shelf mixes, the knob law)
  is left to whoever joins those effects; `fx_eq_math.h` is a candidate.
- **Knobs:** the hosts turn a parameter in even steps of its range (a
  hundredth per detent in the virtual FM-1), so a frequency in Hz moves by
  180 Hz a detent on Mid Freq and a modulation route sweeps it in Hz, not in
  octaves; the multimode Filter's Cutoff (fx pack 2, not yet on main) has
  the same issue [verified: its branch]. A logarithmic taper for
  `FM1_UNIT_HZ` parameters belongs in the hosts, so a lock or a preset keeps
  storing Hz.

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
third page.

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

**Units and abbreviations.** Echo's Time and Sophie's Ring Time are in ms,
Sophie's Tune in semitones and its 0–100 knobs in %. Sophie's Decay is in
seconds, for which there is no unit code yet, so it has none. Every other
parameter is a bare number (the 0–1 knobs, gains, bits, indices).

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
| `src/fx_*.cc` | Effects written in this repository (Echo, EQ and its libm-free `fx_eq_math.h`) |
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

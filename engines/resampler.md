# resampler: an engine's own rate down to the host's

Mutable Instruments' code counts its time constants in samples at its own
rate: Braids at 96 kHz, Plaits at 47,872.34 Hz, Rings at 48 kHz. Run at the
FM-1's 44,118 Hz with only the pitch corrected, those constants stretch:
Braids' struck shapes rang 1.6–2.8 times as long as on the module
(reference-braids-fx.md) [verified there]. The owner's decision of
2026-10-01: **Shapes runs Braids at its native 96 kHz, in Braids' own
24-sample blocks, whatever the host's rate, and the voice mix is resampled
to the host's rate.** This file is the resampler that makes that possible
and the measurements of Shapes through it.

| File | What |
| --- | --- |
| `include/fm1_resampler.h` | the resampler: plain C99 (also C++11), `static inline`, no heap, state in a fixed-size struct, coefficients `const` |
| `src/mi_shapes.cc` | Shapes, now at 96 kHz with its mix through one resampler |
| `test/resampler_test.cc` → `build/fm1-resampler-test` | measurements and contract checks, one JSON line per run |
| `mk/resampler.mk` | builds it as part of `all` |
| `tests/test_engines_resampler.py` | 146 tests, about 8 s on an M1 Max; also the generator of the coefficient tables |

```bash
make -C engines
engines/build/fm1-resampler-test sweep --in-rate 96000 --out-rate 44118 --step 250
engines/build/fm1-resampler-test bench --in-rate 47872.34
python -m tests.test_engines_resampler          # prints the header's two tables
python -m pytest tests/test_engines_resampler.py
```

## Use

```c
#include "fm1_resampler.h"

fm1_resampler_t rs;                                /* 720 B on 64-bit, 716 B on i386 */
if (!fm1_resampler_init(&rs, 96000.0f, host->sample_rate)) /* refuse the host */;

/* per output sample */
uint32_t need;
while ((need = fm1_resampler_needed(&rs)) > 0)
  fm1_resampler_push(&rs, next_input_samples, need);       /* or fewer at a time */
float y = fm1_resampler_pop(&rs);
```

- **Ratios.** Any real ratio input/output from 1 to 4; equal rates pass
  samples through bit for bit (`fm1_resampler_delay` is then 0). Anything
  else, and any rate that is not a positive finite number, is refused: `init`
  returns 0 and the instance takes and gives nothing [verified:
  `test_unsupported_ratios_are_refused`, from memory filled with 0xA5].
  Upsampling is not supported (below).
- **Pull, not push.** The resampler asks for input only as each output needs
  it; `push` never takes more than `needed` reports. An engine that renders
  its own fixed blocks on demand therefore produces the same output whatever
  block size the host asks for [verified: `test_output_does_not_depend_on_chunking`,
  25 input/output chunk patterns bit-identical at three ratios; Shapes below].
  `fm1_resampler_process` does the same over arrays.
- `pop` with input still needed returns 0 and changes nothing; a refused
  instance's `needed` is 0.
- `init` writes every field, so the instance does not depend on what its
  memory held before.

## Design

Two stages [verified: the header]:

1. **A polyphase windowed-sinc interpolator from the input rate to twice the
   output rate** (88,236 Hz for the FM-1). Its kernel is sinc(u) times a
   Kaiser window (β 11), 12 intermediate samples wide (±6), cut off at the
   intermediate rate's Nyquist, which is the output rate. One half of it is
   tabulated at 128 phases per intermediate sample (769 floats) and
   linearly interpolated between phases. Each intermediate sample is the
   sum of the inputs the kernel reaches, each weighted by the kernel at its
   distance scaled by ρ = 2 f_out / f_in; positions are 32.32 fixed point,
   table positions 16.16, so any ratio works from the one table and timing
   is exact over hours (the step's rounding is below 2⁻³³ input samples per
   intermediate sample) [inferred from the arithmetic].
2. **A 67-tap half-band FIR decimating by two** (Kaiser, β 9.5): 17 stored
   coefficients, applied to pre-added symmetric pairs, plus the centre tap
   of 0.5; every other tap is zero. Its side taps are scaled to sum to 0.25,
   so its gain is exactly 1 at DC and 0 at the intermediate Nyquist.

Why two stages: the first stage only has to keep 0 to 0.408 f_out
(0–18 kHz at 44,118 Hz) free of aliases at the intermediate rate. What it
lets through between 0.408 and 1.592 f_out lands in the half-band's stopband
or its slope, so its transition band is wide (18 to 70.2 kHz) and 12
intermediate samples of kernel suffice: about 12/ρ = 13 input taps per
intermediate sample at 96 kHz. The sharp cut is the half-band's, cheap
because half its taps are zero and the rest symmetric [inferred from the
design; the sweep below verifies the result].

Alternatives considered, at the same 90 dB, for 96,000 → 44,118 Hz (Kaiser
length estimates, [inferred]):

| Design | Multiply-adds per output | Coefficient table |
| --- | --- | --- |
| **this one** | **≈ 70**: 26 kernel taps × 2 (interpolating the phase costs one) + 18 half-band | **3,144 B** |
| single-stage polyphase sinc straight to 44,118 Hz, transition 18–26.1 kHz | ≈ 136 (68 taps at 96 kHz, × 2) | ≈ 35 KB at 128 phases |
| the same with its stopband at the output's Nyquist (22.06 kHz) | ≈ 270 | ≈ 70 KB |
| two-stage with a full low-pass (not half-band) second stage, stopband at 22.06 kHz | ≈ 115 | ≈ 3.5 KB |

The coefficient tables are generated by `kernel_table()` and
`halfband_table()` in `tests/test_engines_resampler.py` (standard library
only; `python -m tests.test_engines_resampler` prints them as C), and
`test_tables_are_the_documented_design` checks the header's against them
[verified]. They are `static const` in the header, so each translation unit
that uses them carries its own 3,144 B copy [inferred: C semantics]; two
engines using the resampler would want one shared definition.

The parameters were chosen by measurement with a prototype [verified,
scratch]: a 10-wide kernel (β 9.5) let 25.7 kHz alias at −84 dB; 64 phases
gave −100 dB in-band spurs against −109 dB at 128; a 63-tap half-band
(β 9) reached only −89.6 dB, 67 taps at β 9.7 −87.3 dB (its transition too
wide for the 26.1 kHz edge) and at β 9.5 about −95 dB.

## Measured quality

Unit sines through a fresh resampler, the output component at the expected
frequency fitted by least squares over 16,384 output samples, the rest by a
Kaiser-windowed FFT (β 20) of what the fit leaves
(`fm1-resampler-test sweep`) [verified: tests and sweeps, macOS arm64]:

| | 96,000 → 44,118 Hz | 47,872.34 → 44,118 Hz |
| --- | --- | --- |
| Passband, 50 Hz–18 kHz | −0.00018 to +0.00010 dB | −0.00018 to +0.00010 dB |
| Group delay | 16 output samples (0.363 ms), constant within 0.00003 samples: linear phase | the same |
| Above the passband | −0.05 dB at 19 kHz, −0.49 at 20, −2.06 at 21, −5.72 at 22 (the half-band's slope) | the same |
| Spurs in 0–18 kHz from an in-band sine | ≤ −108.9 dB | ≤ −99.8 dB |
| Anything in 0–18 kHz from a sine above 22,059 Hz | ≤ **−95.1 dB** (worst at 26,314 Hz, the half-band's stopband edge) | ≤ −109.9 dB |
| Main alias of 22.06–26.1 kHz, landing in 18–22.06 kHz | −7.4 dB at 22.3 kHz input, −43.1 at 25.05, −87 at 26.05 | −6.3 dB at 22.1 kHz input to −22.4 at 23.9 (the input's band ends at 23.94 kHz) |
| Other components in 18–22.06 kHz | ≤ −69.8 dB (inputs above 26.1 kHz, through the first stage's slope); ≤ −110.7 from in-band sines | ≤ −70.1 dB from in-band sines above about 14 kHz; from inputs above 22.06 kHz their image, −67 dB at 22.1 kHz rising to −23 at 23.9 (a sine and its image meet at the input's Nyquist) |

At 48 kHz in, the passband spurs are −101.2 dB; at exact 2:1 and 4:1 the
first stage samples its kernel at whole or half phases and the spurs are
below −150 dB; aliases into 0–18 kHz are −95.0 to −95.1 dB at every ratio
whose input reaches the half-band's stopband edge [verified: sweeps at
48,000, 88,236 and 176,472 Hz].

**The band above 18 kHz is not protected.** Content between the output's
Nyquist and 26.1 kHz folds into 18–22.06 kHz, attenuated only by the
half-band's slope; and at ratios below 2 (Plaits, Rings) the input's images
of content above about 14 kHz reach the same band at up to −70 dB. That is
the price of the half-band: a stopband from 22.06 kHz would need a full
low-pass second stage, ≈ 115 multiply-adds instead of ≈ 70 (table above).
The requirement was a flat passband to 18 kHz and the band below it clean;
18–22 kHz is above it and above most adults' hearing [inferred].

**Why 90 dB is enough.** fm1-render writes 16-bit samples, 1 LSB being
−90.3 dBFS: a full-scale component above the Nyquist leaves at most
−95 dBFS in 0–18 kHz, below one LSB [inferred from the measurement]. The
sources themselves are not that clean: at 96 kHz Braids' CSaw at 8.4 kHz
carries its own aliases at −61 to −72 dBFS next to −14 dBFS harmonics
[verified: the CSaw render below], 30 dB or more above what the resampler
adds.

**Other contracts** [verified, each a test]:

- Equal rates: 100,000 floats of every kind except NaN (zeros of both signs,
  subnormals, infinities, the largest) come out bit for bit, one at a time
  and through `fm1_resampler_process`.
- Extreme input: the worst-case gain is the kernel's L1 norm (1.49–2.09
  over the ratios tested) times the half-band's (1.68), 2.50–3.51 in all;
  the half-band's pre-added pairs can overflow at twice the kernel's. Inputs
  up to the largest float over the larger of the two (8 × 10³⁷ to
  1.1 × 10³⁸ by ratio) never overflow; the largest gain seen in those runs
  is 1.12–1.38. Five samples of NaN and infinities spoil 40–43 consecutive
  outputs, after which the output is the clean run's bit for bit: a FIR has
  no memory beyond its taps.

### Cost

Per output sample at 96,000 → 44,118 Hz: on average 26.1 kernel taps (two
intermediate samples of 12/ρ = 13.06), each two table loads, a subtraction,
an integer-to-float conversion, two multiply-adds and a sample load; then
17 half-band multiplies on pre-added pairs and the centre tap
[verified: the code; tap count from ρ]. At Plaits' rate, 13.0 kernel taps.

| | Desktop, Apple M1 Max, best of seven over 2²⁰ outputs |
| --- | --- |
| 96,000 → 44,118 Hz | 31.7 ns per output (1.40 ms per second of audio) |
| 47,872.34 → 44,118 Hz | 22.3 ns per output |

[verified: `fm1-resampler-test bench`.] The desktop core is latency-bound
on the accumulator chains (two per stage, interleaved; one chain cost
36.2 ns). On pi32v2 the FM-1 has about 5,440 cycles per output sample for
everything (240 MHz / 44,118 Hz); at one to three cycles per operation the
resampler's ≈ 70 multiply-adds and their loads would take 200–600 cycles,
4–11 % [inferred: no pi32v2 cycle counts exist yet; stage B measures].
Memory: 3,144 B of `const` tables (flash), 720 B of state (716 B on
i386).

## Shapes through it

`src/mi_shapes.cc` [verified: the code]:

- Every voice is one `braids::MacroOscillator` rendered at 96 kHz in exactly
  24-sample blocks, the pitch uncorrected (Braids' own); the summed mono
  mix of the 24-sample chunk is buffered, and each output sample pulls from
  it what the one resampler needs, rendering the next chunk when the buffer
  runs out. The mix is resampled once, not per voice.
- The wrapper's attack/release envelope runs per 96 kHz sample, so its times
  are the same at any host rate.
- At a 96 kHz host the resampler passes the mix through: every exact
  96 kHz comparison in reference-braids-fx.md still passes, bit for bit.
- Hosts below 24 kHz or above 96 kHz are refused (`create` returns NULL)
  [verified: `test_shapes_refuses_host_rates_the_resampler_cannot_serve`].

### Results at 44,118 Hz

| | Result |
| --- | --- |
| Every shape against upstream | all 47 shapes × 2 timbre/colour points × A2 and A6, 0.1 s: fm1 is upstream Braids at 96 kHz, through the wrapper's envelope and gain and the same resampler, within 0.55 LSB worst and 0.35 LSB rms, random shapes included (a lone voice's stream) [verified: `test_shape_at_host_rate_is_braids_resampled`] |
| Struck shapes' decay | Bell 0.9999–1.0000 and Drum 0.9999–1.0000 of upstream's dB/s at A4, 0.5/0.5, energy-decay times to 10/20/30 dB, fm1 less the resampler's 16-sample delay; Kick 0.9995–1.0058. Was 0.458–0.468 for Bell and Drum. Over three timbre/colour points and A3/A4, 4 s: Bell and Drum 0.9997–1.0000, Kick 0.974–1.008 [verified: `test_struck_shapes_at_host_rate_decay_as_upstream`; scratch probe for the wider set] |
| Pitch | the tuning and bend tests pass unchanged: Braids at its own rate needs no correction [verified: `tests/test_engines.py`, `tests/test_engine_host.py`] |
| Envelope | velocity 64, Attack 0.2 (5.25 ms) and Release 0.3 (12.0 ms), modelled at 96 kHz, match fm1 at 44,118 Hz within quantisation [verified] |
| Host block | 1, 7 and 64 frames per call byte-identical over 13,235 frames with a second note and a note-off mid-render, for the 17 block-sensitive and two-per-pass shapes [verified] |
| Instance memory | the existing `--fill` test (0, 0xA5, 0xFF) passes for Shapes at 44,118 Hz [verified: `tests/test_engine_host.py`] |
| Any parameter value, knobs mid-note | the existing tests pass, also under ASan + UBSan [verified] |
| A high note's aliases | below |

**Note timing.** A note now lands on Braids' next unrendered 24-sample
block at 96 kHz (0.25 ms granularity, was 24 samples at 44,118 Hz,
0.54 ms). The resampler adds its group delay, 16 output samples
(0.363 ms), and pulls about 3 output samples ahead of it (the kernel's
reach plus one input). From a note's arrival to the centre of its onset:
**0.430–0.680 ms** (18.96–29.99 output samples) over every arrival sample,
was 0–0.521 ms [verified: the model in `inputs_pulled`, checked exactly by
`test_note_on_at_host_rate_starts_on_a_braids_block`; the range computed
from it]. On average about 0.3 ms later than before [inferred from the two
ranges].

**A high note's aliases.** CSaw at MIDI 120 (8,372 Hz), timbre and colour
0: at 96 kHz its harmonics 3–5 and Braids' own aliases of harmonics 6–8
lie above 22,059 Hz (25.1, 29.0, 33.5, 37.4, 41.9 and 45.8 kHz, −32 to
−49 dBFS). At 44,118 Hz, at each frequency where one of them would alias
into 0–18 kHz, fm1's output reads −130 to −146 dBFS, at the 16-bit
render's measurement floor and no more than the 96 kHz render holds there;
for the three sources above −45 dBFS that is 94–108 dB below the source.
The 25.1 kHz harmonic aliases to 19.0 kHz, above the passband, 44.7 dB
down (the half-band's slope). The two in-band harmonics keep their level
within 0.05 dB [verified: `test_high_note_aliases_are_below_the_measurement_floor`].

### Cost and memory

Twelve voices held, 3 s, best of five, desktop (Apple M1 Max), share of the
1.451 ms block [verified: `fm1-render` built from the base commit and from
this change]:

| Shape | Before, 44,118 Hz | After, 44,118 Hz | × |
| --- | --- | --- | --- |
| 0 CSaw | 3.68 µs (0.25 %) | 10.19 µs (0.70 %) | 2.77 |
| 12 3x Sine | 5.42 µs (0.37 %) | 13.98 µs (0.96 %) | 2.58 |
| 26 FB FM | 8.75 µs (0.60 %) | 20.54 µs (1.42 %) | 2.35 |
| 33 Drum | 4.70 µs (0.32 %) | 12.60 µs (0.87 %) | 2.68 |
| 40 Wave x4 | 6.60 µs (0.45 %) | 16.43 µs (1.13 %) | 2.49 |

The Braids part grows by the sample ratio, 2.18; the resampler adds a flat
1.40 ms per second of audio on this core, the rest of the factor (a
quarter of the total for CSaw, the cheapest shape) [inferred from the same
runs at a 96 kHz host: 5.55 → 5.81 ms/s for CSaw]. On pi32v2 the
resampler's share should be smaller, the oscillators' per-sample work being
the larger part there [inferred].

Instance: 205,800 → **206,512 B** on the 64-bit desktop
[verified: `instance_bytes`], 204,932 → **205,640 B** on i386
[verified: clang `-target i386-apple-macos10.13 -fsyntax-only`, sizes read
from a template diagnostic]: the resampler's 720 (716) B less the two
floats that held the host rate and the pitch correction.

## Using it in another engine

Plaits, for instance (47,872.34 Hz, 12-sample blocks): run `plaits::Voice`
at its own rate with no pitch or time-constant correction, keep a
12-sample mix buffer, and pull as Shapes does:

```c
fm1_resampler_init(&rs, 47872.34f, host->sample_rate);
/* per output sample: while needed, push from the 12-sample buffer,
 * rendering the next block when it runs out; then pop. */
```

At that ratio the kernel spans 6.5 input samples and an output costs about
13 kernel taps and the half-band's 17, 22 ns on the desktop [verified:
bench; tap count from ρ]. Its passband and 0–18 kHz are as clean as Braids'
(table above); its 18–22 kHz band carries images of content above about
14 kHz at up to −70 dB [verified: sweep]. A stereo engine needs one
instance per channel.

## Limits

- **No upsampling.** An engine slower than the host (a 32 kHz one on a
  44,118 Hz host) would need a first stage whose kernel cuts at the input's
  Nyquist, a narrow transition and about 32 input taps; `init` refuses the
  ratio rather than image [inferred: the design].
- The band from 18 kHz to the output's Nyquist is not protected (above).
- Desktop timing only; pi32v2's cycle counts and its flash-read cost for
  the 3 KB table (XIP through a cache) are stage B's to measure.
- Sweeps and timings were run on macOS arm64 (Apple clang); the CI jobs run
  the same tests on Linux, 32-bit and under ASan + UBSan.
- `test_header_is_warning_free_c99_and_cxx11` compiles the header with the
  system's `cc` and `c++` and `-Werror`; GCC was not run here [inferred:
  the header uses nothing GCC treats differently].

## For the shared files (outside this lane)

- `engines/README.md`: list `include/fm1_resampler.h` and
  `fm1-resampler-test` in the layout and this file in the docs; Shapes' row
  ("Braids at 96 kHz, resampled"); its instance sizes (206,512 / 205,640 B)
  and costs; the cost table (Shapes 12 voices 0.70–1.42 % of the block);
  "What stage A has found" and "The exit test": Shapes now matches upstream
  at 44,118 Hz too, Braids' time constants included; remove the "Shapes at
  the FM-1 rate" open question (chosen: native 96 kHz, resampled), and
  note that Plaits could follow (above).
- `CHANGELOG.md`, Unreleased: Shapes runs Braids at its native 96 kHz and
  resamples, so its struck shapes ring as long as on the module at any host
  rate (they rang about twice as long at 44,118 Hz); it costs about 2.2–2.8
  times the CPU, 712 B more per instance, and 0.43–0.68 ms from a note to
  its onset (was 0–0.52 ms); hosts below 24 kHz or above 96 kHz are refused.
- `docs/11` §8: stage A's exit test for Shapes is now met at the FM-1's
  rate as well as at Braids' own.
- `third_party/mutable/UPSTREAM.md`: nothing (no vendored file changed).
- CI: nothing; the new test file matches `tests/test_engine*.py` and the
  tool is part of `all`.

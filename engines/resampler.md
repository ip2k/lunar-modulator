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
| `tests/test_engines_resampler.py` | 152 tests, about 14 s on an M1 Max; also the generator of the coefficient tables |

```bash
make -C engines
engines/build/fm1-resampler-test sweep --in-rate 96000 --out-rate 44118 --step 250
engines/build/fm1-resampler-test bench --in-rate 47872.34
engines/build/fm1-resampler-test window         # the input ring's contract and read window
python -m tests.test_engines_resampler          # prints the header's two tables
python -m pytest tests/test_engines_resampler.py
```

## Use

```c
#include "fm1_resampler.h"

fm1_resampler_t rs;                                /* 1,288 B on 64-bit and on i386 */
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
  Upsampling is not supported (Limits, below).
- **Pull, not push.** The resampler asks for input only as each output needs
  it; `push` never takes more than `needed` reports, and an output never
  reads an input it did not ask for [verified:
  `test_an_output_reads_only_the_inputs_it_asked_for`, below]. An engine
  that renders its own fixed blocks on demand therefore produces the same
  output whatever block size the host asks for [verified:
  `test_output_does_not_depend_on_chunking`, 25 input/output chunk patterns
  bit-identical at three ratios; Shapes below]. `fm1_resampler_process`
  does the same over arrays.
- `pop` with input still needed returns 0 and changes nothing; a refused
  instance's `needed` is 0.
- `init` writes every field, so the instance does not depend on what its
  memory held before.

## Design

Two stages [verified: the header]:

1. **A polyphase windowed-sinc interpolator from the input rate to twice the
   output rate** (88,236 Hz for the FM-1). Its kernel is c·sinc(c·u) times a
   Kaiser window (β 11), 12 intermediate samples wide (±6), with c = 0.96: a
   low-pass at 0.96 of the intermediate rate's Nyquist, which is the output
   rate. One half of it is tabulated at 128 phases per intermediate sample
   (769 floats) and linearly interpolated between phases. Each
   intermediate sample is the sum of the inputs the kernel reaches, each
   weighted by the kernel at its distance scaled by ρ = 2 f_out / f_in;
   positions are 32.32 fixed point, table positions 16.16, so any ratio
   works from the one table and timing is exact over hours (the step's
   rounding is below 2⁻³³ input samples per intermediate sample) [inferred
   from the arithmetic].
2. **A 123-tap linear-phase low-pass FIR decimating by two** (Kaiser,
   β 9.3, cut at 0.4522 f_out, 19,950 Hz at 44,118 Hz): flat to 18 kHz,
   its stopband from the output's Nyquist, 22,059 Hz. 62 stored
   coefficients, applied to pre-added symmetric pairs plus the centre tap;
   scaled to unity gain at DC. Its centre is 30 output samples back, the
   group delay.

**Why two stages.** The first stage need not be sharp: it only has to keep
0–18 kHz flat and stop what would fold into the output's band at the
intermediate rate, 66.2 kHz (1.5 f_out) and up. What its wide transition lets
through lands between 22.06 and 44.1 kHz at the intermediate rate, which the
second stage stops, so 12 intermediate samples of kernel suffice: about
12/ρ = 13 input taps per intermediate sample at 96 kHz. The sharp cut, from
18 kHz to the Nyquist, is made once, at the intermediate rate, by a filter
whose symmetric taps are computed only for the samples the decimation keeps
[inferred from the design; the sweeps below verify the result].

**Why a full low-pass and not a half-band.** The first version of this
change (commit f12448c) used a 67-tap half-band as the second stage: 17
multiplies, but a half-band is 6 dB down at the output's Nyquist by
construction, so content between 22.06 and 26.1 kHz folded into
18–22.06 kHz, down only 7.4 dB at a 22.3 kHz input and 43 dB at 25.05 kHz.
On Shapes that let CSaw's 25.1 kHz harmonic through to 19.0 kHz 44 dB down
(−78 dBFS at MIDI 120, −69.5 dBFS at MIDI 127), and at ratios below 2 it
let the first stage's images of content above about 15 kHz into the same
band at up to −69.7 dB [verified: sweeps and renders of that build]. The
requirement was about 90 dB against everything above the output's Nyquist,
so this version pays about 44 more multiply-adds per output for a stopband
that starts at the Nyquist.

Alternatives, for 96,000 → 44,118 Hz at about 93 dB (Kaiser length
estimates unless measured, [inferred]):

| Design | Multiply-adds per output | Coefficient tables | 18–22 kHz |
| --- | --- | --- | --- |
| **this one**: polyphase stage to 2 f_out, 123-tap low-pass | **≈ 114**: 26 kernel taps × 2 (interpolating the phase costs one) + 62 [verified: the code] | **3,324 B** [verified] | protected, ≥ 93 dB [verified] |
| the same with an equiripple (Parks–McClellan) low-pass, 0.0035 dB ripple | ≈ 104: about 101 taps by Herrmann's estimate, 103 as 4 D + 3, so 52 multiplies; delay 25 samples | ≈ 3.3 KB | protected |
| f12448c: polyphase stage to 2 f_out, 67-tap half-band | ≈ 70 | 3,144 B | not protected (above) [verified] |
| single-stage polyphase sinc straight to 44,118 Hz, stopband from 22.06 kHz | ≈ 280: a kernel 64 output samples wide, 140 input taps × 2 | ≈ 16.5 KB as a half table at 128 phases per output sample | protected |
| the same, stopband from 26.1 kHz | ≈ 140 | ≈ 8.2 KB, half table | not protected |

The coefficient tables are generated by `kernel_table()` and
`lowpass_table()` in `tests/test_engines_resampler.py` (standard library
only; `python -m tests.test_engines_resampler` prints them as C), and
`test_tables_are_the_documented_design` checks the header's against them
[verified]. They are `static const` in the header, so each translation unit
that uses them carries its own 3,324 B copy [inferred: C semantics]; two
engines using the resampler would want one shared definition.

The parameters were chosen with an analytic model of both stages (the
kernel's continuous spectrum and the low-pass's response, folded as the
resampler folds them) and confirmed by the sweeps below [verified, scratch].
With the kernel cut at the intermediate Nyquist (c = 1, the half-band
version's), its images of 66–70 kHz reach 18–22 kHz through the low-pass's
transition at −86 dB; c = 0.96 moves its transition down and gives −107 dB
at the same 12-sample span (c = 0.97: −103 dB; a 10-sample span at best
−92 dB). For the low-pass, 119 taps reach −92.4 dB with a 0.010 dB droop at
18 kHz, 123 taps −93.1 dB with 0.004 dB, 127 taps −94.8 dB; the length is
4 D + 3 so that the delay D is a whole number of output samples.

## Measured quality

Unit sines through a fresh resampler, the output component at the expected
frequency fitted by least squares over 16,384 output samples, the rest by a
Kaiser-windowed FFT (β 20) of what the fit leaves
(`fm1-resampler-test sweep`): every 50 Hz to 18 kHz, every 10 Hz from there
to the Nyquist, every 23 Hz above it at 96 kHz (7 Hz at Plaits' rate) and
every 1 Hz across the stopband's first sidelobe; sines within 20 Hz of the
output's Nyquist, or aliasing to within 20 Hz of it or of DC, cannot be
fitted and are skipped [verified: tests and sweeps, macOS arm64]:

| | 96,000 → 44,118 Hz | 47,872.34 → 44,118 Hz |
| --- | --- | --- |
| Passband, 50 Hz–18 kHz | −0.0043 to +0.0001 dB (the low-pass's droop at 18 kHz the most) | the same |
| Group delay | 30 output samples (0.680 ms), constant within 0.000001 samples: linear phase | the same, within 0.00003 |
| From 18 kHz to the Nyquist | −0.004 dB at 18 kHz, −0.74 at 19, −6.5 at 20, −24.4 at 21, −79.7 at 22 (the low-pass's transition) | the same |
| A sine above 22,059 Hz: its alias, wherever it lands below the Nyquist | ≤ **−93.3 dB** (worst at 22,174 Hz, the stopband's first sidelobe); ≤ −103.2 dB into 0–18 kHz | ≤ −93.3 dB (22,173 Hz); all of them land above 18 kHz |
| …and everything else it leaves below the Nyquist | ≤ −107.5 dB | ≤ −98.3 dB |
| Spurs from a sine in 0–18 kHz, anywhere below the Nyquist | ≤ −111.6 dB | ≤ −101.2 dB |
| Spurs from a sine in 18–22.06 kHz | ≤ −108.0 dB | ≤ −100.9 dB |

At 48 kHz in, the spurs are −108.1 dB from in-band sines and −102.2 dB from
18–22 kHz ones, the aliases −93.3 dB; at exact 2:1 and 4:1 the first stage
samples its kernel at whole or half phases and the spurs are below −147 dB,
the aliases again −93.3 dB (−101.9 dB into 0–18 kHz at 4:1); at 44,119 Hz in
(a ratio of 1.00002) the spurs are −104.2 dB [verified: sweeps at 48,000,
88,236, 176,472 and 44,119 Hz]. The spurs at ratios other than 2:1 and 4:1
are the phase interpolation's: 128 phases, linearly interpolated, which
the tests hold to 95 dB.

**Why 90 dB is enough.** fm1-render writes 16-bit samples, 1 LSB being
−90.3 dBFS: a full-scale component above the Nyquist leaves at most
−93 dBFS anywhere below it, under one LSB [inferred from the measurement].
The sources themselves are not that clean: at 96 kHz Braids' CSaw at 8.4 kHz
carries its own aliases at −61 to −72 dBFS next to −14 dBFS harmonics
[verified: the CSaw render below], 20 dB or more above what the resampler
adds.

**Other contracts** [verified, each a test]:

- Equal rates: 100,000 floats of every kind except NaN (zeros of both signs,
  subnormals, infinities, the largest) come out bit for bit, one at a time
  and through `fm1_resampler_process`.
- The input ring: after every push, NaN goes into the slot the next push
  will fill, which holds the oldest input and whose second copy sits where
  the input not yet received would be. At 3,006 ratios from just above 1 to
  4, 3,000 outputs each, every output stays finite. Keeping fewer of the
  newest inputs, every older slot poisoned too, finds the read window: 27
  consecutive inputs at the 4:1 limit, of the ring's 32. Removing the
  one-input margin from `lead`, or rounding `needed` down, makes an output
  read the input not yet received, and the test fails
  [`test_an_output_reads_only_the_inputs_it_asked_for`; mutants run].
- Extreme input: the worst-case gain is the kernel's L1 norm (1.46–2.06 over
  the ratios tested) times the low-pass's (2.11), 3.08–4.34 in all; the
  low-pass's pre-added pairs can overflow at twice the kernel's. Inputs up to
  the largest float over the larger of the two (7.8 × 10³⁷ to 1.1 × 10³⁸ by
  ratio) never overflow; the largest gain seen in those runs is 1.30–1.37.
  Five samples of NaN and infinities spoil 68–70 consecutive outputs, after
  which the output is the clean run's bit for bit: a FIR has no memory
  beyond its taps.

### Cost

Per output sample at 96,000 → 44,118 Hz: on average 26.1 kernel taps (two
intermediate samples of 12/ρ = 13.06), each two table loads, a subtraction,
an integer-to-float conversion and a multiply by 2⁻¹⁶ (the phase fraction;
clang folds these two into one `ucvtf` on arm64, a pi32v2 compiler may not),
two multiply-adds and a sample load; then the low-pass's 61 pre-added pairs
(two sample loads, an add, a coefficient load and a multiply-add each) and
its centre tap [verified: the code; tap count from ρ]. That is 114
multiply-adds (140 counting the phase-fraction multiplies). Compiled for
arm64 (Apple clang -O2) the loops execute about 14 instructions per kernel
tap and 6.25 per low-pass pair, about 800 per output with the loop overhead
[verified: the assembly, counted by hand]. At Plaits' rate, 13.0 kernel taps.

| | Desktop, Apple M1 Max, best of seven over 2²⁰ outputs |
| --- | --- |
| 96,000 → 44,118 Hz | 45.0 ns per output (1.99 ms per second of audio); the half-band version 32.1 |
| 47,872.34 → 44,118 Hz | 35.7 ns per output; the half-band version 21.8 |

[verified: `fm1-resampler-test bench`, best of three runs of each build.]
The loops keep two accumulators in the kernel and four in the low-pass so
that the desktop's multiply-add chains overlap [inferred: the code; not
timed separately]. On pi32v2 the FM-1 has about 5,440 cycles per output
sample for everything (240 MHz / 44,118 Hz); if it needs about as many
instructions as arm64 and retires one per cycle, the resampler takes about
800 cycles, 15 % of that (the half-band version, about 520 instructions on
arm64, 10 %) [inferred: no pi32v2 cycle counts exist yet; stage B
measures; the arm64 counts verified from the assembly]. Two ways to
cut it if stage B needs to [inferred]: store the kernel as pre-scaled
(value, difference × 2⁻¹⁶) pairs, which drops the subtraction and the scale
multiply from every kernel tap (about 52 operations per output) for 3 KB
more flash; and design the low-pass as equiripple (table above), 10 fewer
multiply-adds and 5 samples less delay, at the cost of a Remez design in the
generator. Memory: 3,324 B of `const` tables (flash), 1,288 B of state.

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
| Every shape against upstream | all 47 shapes × 2 timbre/colour points × A2 and A6, 0.1 s: fm1 is upstream Braids at 96 kHz, through the wrapper's envelope and gain and the same resampler, within 0.525 LSB worst and 0.295 LSB rms (the test allows 0.55 and 0.35), random shapes included (a lone voice's stream) [verified: `test_shape_at_host_rate_is_braids_resampled`; worst and rms from a scratch run of the same comparison] |
| Struck shapes' decay | Bell 0.9999 and Drum 0.9999–1.0000 of upstream's dB/s at A4, 0.5/0.5, energy-decay times to 10/20/30 dB, fm1 less the resampler's 30-sample delay; Kick 0.9995–1.0062. Was 0.458–0.468 for Bell and Drum. Over three timbre/colour points and A3/A4, 4 s: Bell 0.9997–1.0000, Drum 0.9998–1.0000, Kick 0.974–1.008 [verified: `test_struck_shapes_at_host_rate_decay_as_upstream`; scratch probe for the wider set] |
| Pitch | the tuning and bend tests pass unchanged: Braids at its own rate needs no correction [verified: `tests/test_engines.py`, `tests/test_engine_host.py`]. They, and the decay test, resolve the rate to about 0.1 %; the per-shape comparison above is the exact guard (a native rate 0.03 % off fails it) [verified: mutants] |
| Envelope | velocity 64, Attack 0.2 (5.25 ms) and Release 0.3 (12.0 ms), modelled at 96 kHz, match fm1 at 44,118 Hz within quantisation [verified] |
| Host block | 1, 7 and 64 frames per call byte-identical over 13,235 frames with a second note and a note-off mid-render, for the 17 block-sensitive and two-per-pass shapes [verified] |
| Instance memory | the existing `--fill` test (0, 0xA5, 0xFF) passes for Shapes at 44,118 Hz [verified: `tests/test_engine_host.py`] |
| Any parameter value, knobs mid-note | the existing tests pass, also under ASan + UBSan [verified] |
| A high note's aliases | below |

**Note timing.** A note now lands on Braids' next unrendered 24-sample
block at 96 kHz (0.25 ms granularity, was 24 samples at 44,118 Hz,
0.54 ms). The resampler adds its group delay, 30 output samples
(0.680 ms), and pulls about 3 output samples ahead of it (the kernel's
reach plus one input). From a note's arrival to the centre of its onset:
**0.747–0.997 ms** (32.96–43.99 output samples, 0.872 ms on average) over
every arrival sample; it was 0–0.521 ms with Braids at the host's rate,
and 0.430–0.680 ms with the half-band [verified: the model in
`inputs_pulled`, checked exactly by
`test_note_on_at_host_rate_starts_on_a_braids_block`; the range computed
from it over 200,000 arrival samples].

**A high note's aliases.** CSaw at MIDI 120 (8,372 Hz) and 127
(12,544 Hz), timbre and colour 0. At 96 kHz MIDI 120's harmonics 3–5 and
Braids' own aliases of 6–8 lie above 22,059 Hz (25.1, 29.0, 33.5, 37.4, 41.9
and 45.8 kHz, −32 to −49 dBFS); MIDI 127's second harmonic is at 25,088 Hz,
−25.5 dBFS. At 44,118 Hz, at every frequency where one of the components
above −75 dBFS aliases, anywhere below the Nyquist, fm1's output reads
−132 to −157 dBFS for MIDI 120, at the 16-bit render's measurement floor
(about −135 dBFS), and −117 to −123 dBFS for MIDI 127, at or below the
96 kHz render's own content at those frequencies (about −116 dBFS).
Where the floor leaves room to see it, each alias is 99–106 dB below its
source: the 25.1 kHz harmonic at 19.0 kHz −99.2 dB (the half-band version:
−44.7 dB), 33.5 kHz −105.5 dB, 41.9 kHz −103.3 dB. MIDI 127's 25,088 Hz
reads −120.2 dBFS at 19,030 Hz (the half-band version: −69.5 dBFS). The
in-band harmonics keep their level within 0.05 dB [verified:
`test_high_note_aliases_are_below_the_measurement_floor`, both notes; the
half-band figures from the same probe on that build].

### Cost and memory

Twelve voices held, 3 s, desktop (Apple M1 Max), best of ten (two runs of
five), share of the 1.451 ms block [verified: `fm1-render` built from the
base commit, from the half-band version and from this one]:

| Shape | Before, 44,118 Hz | After, 44,118 Hz | × | Half-band version |
| --- | --- | --- | --- | --- |
| 0 CSaw | 3.60 µs (0.25 %) | 10.87 µs (0.75 %) | 3.02 | 10.29 µs |
| 12 3x Sine | 5.31 µs (0.37 %) | 14.74 µs (1.02 %) | 2.78 | 14.30 µs |
| 26 FB FM | 8.28 µs (0.57 %) | 20.99 µs (1.45 %) | 2.54 | 20.06 µs |
| 33 Drum | 4.67 µs (0.32 %) | 13.21 µs (0.91 %) | 2.83 | 12.26 µs |
| 40 Wave x4 | 6.45 µs (0.44 %) | 17.02 µs (1.17 %) | 2.64 | 16.24 µs |

The Braids part grows by the sample ratio, 2.18; the resampler adds a flat
2.0 ms per second of audio on this core (45 ns per output), the rest of the
factor: about a quarter of CSaw's cost after the change (the cheapest shape,
7.5 ms/s) and a seventh of FB FM's (14.5 ms/s) [inferred from the same runs
at a 96 kHz host, where the resampler passes through: 5.81 ms/s for CSaw,
13.1 for FB FM]. On pi32v2 its share could be larger or smaller; stage B
measures [inferred].

Instance: 205,800 → **207,080 B** on the 64-bit desktop
[verified: `instance_bytes`], 204,932 → **206,212 B** on i386
[verified: clang `-target i386-apple-macos10.13 -fsyntax-only`, sizes read
from a template diagnostic]: the resampler's 1,288 B less the two floats
that held the host rate and the pitch correction. The half-band version's
were 206,512 and 205,640.

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
13 kernel taps and the low-pass's 62 multiplies, 36 ns on the desktop
[verified: bench; tap count from ρ]. Its passband is as flat as Braids',
its spurs 101 dB down and its aliases 93 dB down, the band from 18 kHz to
the Nyquist included (table above). A stereo engine needs one instance per
channel.

## Limits

- **No upsampling, so Shapes refuses hosts above 96 kHz and below 24 kHz.**
  An engine slower than the host (Braids' 96 kHz on a 192 kHz host) needs a
  kernel cut at the *input's* Nyquist: the images of everything up to
  48 kHz fall between 48 and 96 kHz, inside a 192 kHz host's band, and
  stopping them takes a narrow transition at the input rate, a second table
  and several times the taps [inferred: the design]. Ratios above 4 (hosts
  below 24 kHz for Braids) need only a larger input ring and more kernel
  taps per output, but nothing uses them [inferred]. `init` refuses both rather than
  image or overrun, so Shapes renders nothing at those rates instead of
  rendering the wrong timing. The FM-1's 44,118 Hz is well inside the range
  [verified: `test_unsupported_ratios_are_refused`,
  `test_shapes_refuses_host_rates_the_resampler_cannot_serve`].
- Desktop timing only; pi32v2's cycle counts and its flash-read cost for
  the 3.3 KB of tables (XIP through a cache) are stage B's to measure.
- Sweeps and timings were run on macOS arm64 (Apple clang); the CI jobs run
  the same tests on Linux, 32-bit and under ASan + UBSan.
- `test_header_is_warning_free_c99_and_cxx11` compiles the header with the
  system's `cc` and `c++` and `-Werror`; GCC was not run here [inferred:
  the header uses nothing GCC treats differently].

## For the shared files (outside this lane)

- `engines/README.md`: list `include/fm1_resampler.h` and
  `fm1-resampler-test` in the layout and this file in the docs; Shapes' row
  ("Braids at 96 kHz, resampled"); its instance sizes (207,080 / 206,212 B)
  and costs; the cost table (Shapes 12 voices 0.75–1.45 % of the block);
  "What stage A has found" and "The exit test": Shapes now matches upstream
  at 44,118 Hz too, Braids' time constants included; remove the "Shapes at
  the FM-1 rate" open question (chosen: native 96 kHz, resampled), and
  note that Plaits could follow (above). Two choices the owner may want to
  revisit, recorded here and worth a line there: the resampler costs about
  114 multiply-adds per output (more than the "tens" aimed for) so that
  everything above the output's Nyquist is 93 dB down; the half-band
  version of commit f12448c costs about 70 and leaves 18–22 kHz
  unprotected. And Shapes refuses host rates outside 24–96 kHz (Limits).
- `CHANGELOG.md`, Unreleased: Shapes runs Braids at its native 96 kHz and
  resamples, so its struck shapes ring as long as on the module at any host
  rate (they rang about twice as long at 44,118 Hz); the resampler keeps
  0–18 kHz flat within 0.005 dB and everything above the output's Nyquist
  at least 93 dB down; it costs about 2.5–3.0 times Shapes' CPU, 1,280 B
  more per instance, and 0.75–1.00 ms from a note to its onset (was
  0–0.52 ms); hosts below 24 kHz or above 96 kHz are refused.
- `docs/11` §8: stage A's exit test for Shapes is now met at the FM-1's
  rate as well as at Braids' own.
- `third_party/mutable/UPSTREAM.md`: nothing (no vendored file changed).
- CI: nothing; the new test file matches `tests/test_engine*.py` and the
  tool is part of `all`.

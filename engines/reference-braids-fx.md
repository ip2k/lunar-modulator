# reference-braids-fx: Shapes and the three effects against upstream

Stage A's exit test (docs/11 §8) asks that the engines' renders match
upstream Mutable Instruments "within tolerance". This lane checks four of
them against the vendored classes they wrap (`third_party/mutable/`, MIT,
unmodified): **Shapes** against `braids::MacroOscillator`, **Plate** against
`rings::Reverb`, **Ensemble** against `plaits::Ensemble` and **Diffuse**
against `plaits::Diffuser`.

| File | What |
| --- | --- |
| `test/ref_braids_fx.cc` → `build/fm1-ref-braids-fx` | the upstream side: each class driven as its own firmware drives it, nothing of ours in the path |
| `mk/ref-braids-fx.mk` | builds it as part of `all`, from the vendored objects only |
| `tests/test_engines_reference_braids_fx.py` | 170 tests, about 7 s on an M1 Max |

```bash
make -C engines
engines/build/fm1-ref-braids-fx braids --shape 32 --pitch $((57*128)) \
    --timbre 8191 --color 24575 --out bell.wav          # raw int16, 96 kHz
engines/build/fm1-ref-braids-fx fx --effect plate --input noise \
    --damping 0.5 --brightness 0.5 --amount 1 --out plate.wav
python -m pytest tests/test_engines_reference_braids_fx.py
```

## Verdict

| Engine | Upstream class | At its native rate | At 44,118 Hz |
| --- | --- | --- | --- |
| Shapes | `braids::MacroOscillator`, 96 kHz | all 47 shapes match within the renderer's quantisation, **after a fix in this lane**: before it, 22 of 47 did not in the FM-1's 64-frame host blocks | not compared sample for sample; pitch is corrected, time constants are not (below) |
| Plate | `rings::Reverb`, 48 kHz | identical within quantisation | identical to `rings::Reverb` with its loop gain and damping rescaled; decays at 0.961–0.970 of the native rate |
| Ensemble | `plaits::Ensemble`, 47,872 Hz | identical within quantisation at Width 0; the defaults are upstream plus the documented Width and mix law | identical sample for sample: nothing is compensated, delays and LFOs run 8.5 % long and slow |
| Diffuse | `plaits::Diffuser`, 47,872 Hz | identical to upstream plus the documented wet gain, tone filter, decorrelator and mix | identical to `plaits::Diffuser` with its loop gain rescaled; decays at 0.961 of the native rate |

All [verified] by the tests below. "Within quantisation" means that no sample
of fm1-render's 16-bit output lies further than 0.51–0.55 LSB from the
reference scaled as the wrapper scales it, and that the residual has the rms
of rounding alone (about 0.29 LSB).

## The reference tool

`fm1-ref-braids-fx` has two modes and prints one line of JSON per run.

**`braids`** follows `RenderBlock` in `braids/braids.cc` (read in the pinned
upstream checkout) [verified]: 96 kHz, one 24-sample block at a time,
`set_shape`, `set_parameters(timbre, color)` and `set_pitch` (1/128 semitone)
before every block, `Strike()` before block 0 as a trigger would, the sync
buffer all zero, the oscillator in static storage as Braids' global `osc` is.
It writes the oscillator's raw int16. Braids' firmware stages after the
oscillator (AD envelope and VCA, bit and rate reduction, the signature
waveshaper, the inverted DAC write) are not part of the comparison. `--seed`
starts `stmlib::Random` elsewhere; the JSON reports the generator's state
before and after, which is how the shapes that draw on it were found.

**`fx`** runs one effect class on a mono input fed to both channels, set up
as its upstream caller sets it up [verified: the callers' sources]:

| Effect | Caller | Settings from the caller's knob | Block |
| --- | --- | --- | --- |
| plate | `rings/dsp/part.cc`, string-and-reverb model | `--damping d --brightness b`: amount 0.1 + 0.5 d, time 0.35 + 0.63 d, lp 0.3 + 0.6 b, diffusion 0.625, input gain 0.2 | 24 |
| ensemble | `plaits/dsp/engine2/string_machine_engine.cc` | `--timbre t`: amount 2 \|t − 0.5\|, depth 0.35 + 0.65 t | 12 |
| diffuse | `plaits/dsp/engine/particle_engine.cc` | `--morph m`: d = (2 \|m − 0.5\|)² below m = 0.5, else 0; amount 0.8 d², rt 0.25 + 0.5 d | 12 |

Any setting can be overridden (`--amount 1` gives full wet). `--compensate
HOST` applies engines/mi-fx.md's rate rule to the loop settings, and
`--right-delay N` feeds the right channel the input N samples late. The
classes have no sample rate; `--rate` only sets the sample count, the sine's
frequency and the WAV header. The impulse, noise and sine inputs are
fm1-render's, sample for sample [verified: identical outputs where the two
sides should agree]. Output is 32-bit float stereo.

## Method

- **Resolution.** fm1-render writes 16-bit WAV after its bus limiter, so
  that is the resolution of every comparison. The limiter only acts above
  0.98; every effect render adds a Test Gain of 0.5 after the effect (exact
  in float) and asserts a raw peak under 0.98. Shapes at Volume 1 and
  velocity 127 scale the oscillator's int16 by 0.25/32768, so the WAV holds
  it at a quarter of its own resolution.
- **Shapes** render at `--rate 96000` in the FM-1's 64-frame host blocks,
  Attack 0 (a 1 ms one-pole, modelled in double precision; it settles a few
  parts per million under 1 in float) and the note held. Every shape, at
  timbre/colour 0.25/0.75 and 0.75/0.25, at A2 and A6 (between them every
  pitch-dependent branch: above MIDI 80, 90 and 92), 0.1 s from the first
  sample, attack included.
- **Effects** run at the class's native rate with the knobs inverted to the
  *exact* float coefficients the caller computes. The wrappers' mappings are
  different float expressions (Plate's `0.9 − 0.6 x` against Rings'
  `0.3 + 0.6 b`), so the obvious knob value lands one or two ulps away; the
  test searches float32 knob values for one that reproduces the coefficient
  whether or not the compiler fuses the multiply-add. Inputs impulse, noise
  and sine; full wet and the caller's own amount; the wrapper's additions
  modelled in Python.
- **Mutation check** [verified]: the tests fail for the unfixed Shapes
  wrapper (54 failures) and for each of eleven mutants of `mi_fx.cc`: Plate's
  input gain, time or damping compensation removed, diffusion slope;
  Ensemble's offset line at 130 samples, its dry law; Diffuse's rate
  compensation removed, wet gain 0.55, decorrelator coefficient 0.45 or
  length 240, tone corner 260 Hz. That includes the Plate damping
  compensation, which engines/mi-fx.md lists as not covered by its tests.
- **Sanitizers** [verified]: the whole file, and every other engine test,
  pass under the ASan + UBSan build (README) with `halt_on_error=1`.

## Shapes

### Result

All 188 cases (47 shapes × 2 points × 2 pitches) are within quantisation:
worst sample 0.522 LSB, residual rms 0.035–0.313 LSB [verified]. That
includes the physical and percussive models, which depend on the strike:
the wrapper's note-on calls `Strike()` before the voice's first block, as
Braids' trigger does, and its `Init` meets the same zeroed oscillator a
freshly booted Braids does (value-initialised instance, static storage)
[verified: the match, and the code].

### Found and fixed: Braids must render in 24-sample blocks

Before this lane the wrapper rendered each host block in pieces of at most
24 samples: 24 + 24 + 16 for the FM-1's 64 frames. Braids' firmware only
ever renders 24, and several shapes advance once per block rather than per
sample, so 22 of the 47 shapes left upstream's output [verified: the tests
against the unfixed wrapper]: 0–3, 5–12, 15, 17–20, 22, 32, 33, 39 and 44.

- **Struck models decayed faster.** Bell's and Drum's envelopes step once
  per block; with a block every 21.3 samples instead of 24, Bell decayed
  9.4–9.6 % and Drum 15.8 % faster in dB/s (A2 and A4) [verified].
- **Analog shapes drifted.** `BEGIN_INTERPOLATE_PHASE_INCREMENT` computes a
  falling step as `~((previous − current) / size)`, one's complement rather
  than negation, so a steady pitch walks the phase increment down 1 per
  sample in one block and back up in the next [verified: code reading]. The
  average depends on the block sizes: CSaw at A2 sat 0.005 cents off
  upstream and its residual grew from −57 dB in the first 0.1 s to −33 dB
  after 1 s [verified]. Harmless in itself; an upstream quirk, not a
  candidate worth sending.
- **Comb, Vowel and Wave Line** differed by up to 15,000 LSB at some
  samples (Comb's residual reached −20 dB in one case), **Granular**
  throughout, its random draws out of step; Triple Triangle/Sine and the
  four digital filters moved by 1–2 LSB [verified figures; the mechanisms of
  these were not traced].
- The output therefore **depended on the host block size**; at 24 frames it
  matched [verified], at any multiple of 24 it would have [inferred].

The fix (`src/mi_shapes.cc`): every voice renders exactly 24 samples per
chunk into a mix buffer that `Render` hands out across host calls, as the
Macro wrapper already does with Plaits' 12-sample blocks. Consequences:

- Output is bit-identical for host blocks of 1, 7, 24, 64 and 100 frames
  (`test_shapes_output_does_not_depend_on_the_host_block`) [verified].
- A note, parameter or bend now takes effect at the next 24-sample boundary,
  up to 23 samples late (0.52 ms at 44,118 Hz) [inferred from the code; one
  case, 8 samples, verified by
  `test_note_on_starts_the_voice_at_a_braids_block_boundary`].
- Cost unchanged: 12 voices at 44,118 Hz take 3.63 µs per 64-frame block
  for CSaw (3.73 µs before), 3.72 for Vowel (3.83), 6.52 for Bell (6.52),
  Apple M1 Max, best of five [verified]. A first version that accumulated
  straight into the member buffer cost 26–55 % more: the compiler must
  assume a member float array may alias `v.env`; the mix stays on the stack.
- The instance grows by the 24-float buffer and its counter: 205,696 →
  205,800 bytes on the 64-bit desktop [verified: `instance_bytes`].

### Random shapes

Thirteen shapes draw on `stmlib::Random`: Swarm, Vowel, Pluck, Blown, Flute,
Drum, Snare, Wave ×4, Filtered Noise, Twin Peaks, Clocked Noise, Granular and
Particle (14, 22, 28, 30, 31, 33, 36, 40–45) [verified: generator state
before and after a render]. They match exactly, not statistically: the
generator is one global, it starts at 0x21 in both programs, and nothing in
fm1-render draws from it before the voice does [verified]. Started
elsewhere (`--seed 1`) the same shapes differ by more than 2 LSB, so the
exact match does depend on the numbers [verified]; Clocked Noise uses its
seed only when its timbre-set period wraps, which at timbre 0.25 takes over a
second, so its test uses timbre 0.75.

In a chord the voices share that generator and interleave their draws, so no
voice sees upstream's sequence [inferred from the code]. Statistically it
makes no difference: over one second, fm1's level and brightness (rms of the
first difference over rms) lie within 1 dB and 10 % of the range of five
other upstream seeds in 38 of 39 cases (13 shapes × A2, A4, A6); the
exception, Pluck at A6, is one random excitation per note whose brightness
varies from 0.26 to 0.46 between seeds [verified]. The test holds each shape
at A4 within 2 dB and 25 % of the mean of three seeds.

### Not compared here: Shapes at 44,118 Hz

The wrapper corrects pitch for the rate and nothing else. Measured on the
struck shapes at A4, 44,118 Hz against Braids at 96 kHz, the decay in dB/s
is 0.64 of upstream's for Bell, 0.46 for Drum and 0.36 for Kick: they ring
1.6–2.8 times as long on the FM-1 [verified, scratch probe]. Anything else
fixed in samples (formant and filter frequencies not derived from pitch,
per-block envelopes, delay-line lengths) sits at 44,118/96,000 = 0.46 of its
upstream frequency or 2.18 times its duration [inferred]. That is a design
question for Shapes (render at 96 kHz and decimate, or accept it), not
something this comparison can fix.

### Intentional differences

- The wrapper's own envelope, velocity and Volume (gain 0.25/32768 at
  Volume 1), and twelve voices where Braids has one.
- No sync: Braids' ISR also writes a detected trigger into the sync buffer,
  which resets the phase of shapes that honour sync, unless one of the AD
  modulation settings is non-zero, in which case `RenderBlock` clears it
  [verified: `braids.cc`]. The reference and Shapes both render with a zero
  sync buffer.
- Voices start from their state when the note arrives (a fresh voice from
  `Init`), where Braids' one oscillator runs continuously between triggers.

## Plate

Rings' reverb, set as `part.cc` sets it. Plate's knobs map to it as Mix =
amount, Decay = Rings' damping (the same `0.35 + 0.63 x`), Damping ≈ 1 −
brightness and Diffusion 0.5 = 0.625 [verified: the code].

| Case | Worst | Rms |
| --- | --- | --- |
| 48 kHz: 3 inputs × Rings (damping, brightness) (0.3, 0.8), (0.5, 0.5), (0.7, 0.4) × {full wet, Rings' amount}, knobs giving Rings' exact coefficients | 0.500 LSB | 0.285–0.290 |
| the same at full wet with the obvious knobs (Damping = 1 − brightness: lp one or two ulps off) | 1.86 LSB | 0.287–0.305 |
| 44,118 Hz, impulse and noise, damping 0.3/0.5/0.7, against `rings::Reverb` with time and lp rescaled | 0.500 LSB | 0.285–0.289 |

[verified]. At 44,118 Hz the wrapper changes exactly two settings, time
0.539 / 0.665 / 0.791 → 0.510 / 0.642 / 0.775 and lp 0.600 → 0.631, and the
output is otherwise upstream's sample for sample [verified]. So every delay
and LFO keeps its length in samples: 8.8 % longer and slower in seconds,
LFOs 0.5 → 0.460 Hz and 0.3 → 0.276 Hz, the loop's modulated taps at 4,460
and 6,261 samples 92.9 → 101.1 ms and 130.4 → 141.9 ms [verified: sample
identity and the class's constants].

**Decay rate** (impulse tail, Schroeder slope over 0.05–0.6 s, fm1 at
44,118 Hz against the class at 48 kHz): 0.961 / 0.967 / 0.970 at Rings
damping 0.3 / 0.5 / 0.7; without compensation (the same upstream samples
read at 44,118 Hz) 0.915 / 0.921 / 0.927 [verified]. That reproduces
mi-fx.md's 0.96–0.97 and 0.914–0.926. On the residual 3 %, mi-fx.md names
the loop's 16-bit truncation [inferred there]. Probes with the reference
tool [verified figures]: with lp = 1 (no damping filter) the ratio is still
0.968 / 0.973 / 0.976, so the damping filter's imperfect rescaling is a
small part; at damping 0.5, doubling the loop's level (input gain 0.4) moves
it only from 0.967 to 0.973, and by window it is 0.962 (0.05–0.3 s), 0.972
(0.3–0.6 s) and 0.952 (0.6–1.0 s), not the steady fall with level that
truncation alone would give. Truncation may
contribute; a per-pass loss the rule does not rescale is a likelier main
cause, such as the linear interpolation of the two modulated loop delays,
which low-passes on every pass by an amount set by the fractional delay
[inferred; not separable without modifying the vendored class].

Upstream details not reproduced, none of them in the class [verified:
`part.cc`]: Rings crossfades the string's two outputs into the reverb and
negates the right output afterwards. Plate's input guard does nothing to
finite input within ±16.

## Ensemble

The string machine's ensemble. Depth is upstream's depth directly; the
wrapper runs the class at amount 1, recovers the wet as `out − in/2` and
applies Plaits' own law, `wet × mix + dry × (1 − mix/2)`, against the
undelayed dry [verified: the code].

| Case | Worst | Rms |
| --- | --- | --- |
| 47,872 Hz, 3 inputs × string-machine timbre 0 / 0.5 / 1 (depth 0.35 / 0.675 / 1), full wet, Width 0 | 0.500 LSB | 0.003–0.289 |
| defaults (Mix 0.5, Depth 0.5, Width 1), impulse and noise, against the class fed the input 131 samples late on the right, remixed by the documented law | 0.500 LSB | 0.005–0.289 |
| 44,118 Hz, noise, Depth 0 and 1, Width 0 | 0.500 LSB | 0.289 |

[verified]. Nothing in the Ensemble is rate-compensated, and at 44,118 Hz
it is the class sample for sample. Its impulse response at Depth 0 is one
tap of 0.99 (three taps of 0.33) at exactly 192 samples: 4.011 ms at Plaits'
rate, 4.352 ms at 44,118 Hz [verified]. The LFOs advance 67,289 and 589,980
per sample on a 32-bit phase: periods of 63,829 and 7,280 samples, 0.750 and
6.576 Hz at 47,872 Hz, 0.691 and **6.060** Hz at 44,118 Hz [verified:
constants and sample identity]. mi-fx.md's 6.05 Hz scales the header
comment's rounded 6.57 Hz.

## Diffuse

The particle engine's diffuser. Time maps to upstream's rt (`0.25 + 0.65 x`
against the engine's `0.25 + 0.5 d`, searched to the exact float); the
wrapper runs the class at amount 1 on the mono sum and then adds, in order:
wet × 0.5; per side a Schroeder all-pass (241 / 349 samples, g 0.5) blended
in by Width; a one-pole low-pass at Tone; and the crossfade from the dry by
Mix [verified: the code, and the model below matching].

| Case | Worst | Rms |
| --- | --- | --- |
| 47,872 Hz, 3 inputs × morph 0.5 / 0.25 / 0 (rt 0.25 / 0.375 / 0.75), Mix 1, Width 0, Tone 1 modelled | 0.501 LSB | 0.210–0.289 |
| defaults (Mix 0.5, Tone 0.75, Width 1), rt 0.375, impulse and noise, all four additions modelled | 0.500 LSB | 0.285–0.289 |
| 44,118 Hz, noise, rt 0.75 and 0.375, against the class with rt rescaled (0.7319, 0.3450) | 0.500 LSB | 0.289 |

[verified]. Tone 1 is not a bypass: its coefficient is 0.985 at 47,872 Hz,
only −0.26 dB at Nyquist, but its phase lag leaves the output −36 dB from
the unfiltered wet, so the tests model it [verified]. Tone 0.75, the
default, puts the one-pole's nominal corner at 9.5 kHz (mi-fx.md's "about
9.5 kHz"); its −3 dB point is 11.1 kHz at 47,872 Hz and 11.5 kHz at
44,118 Hz [verified: computed from the coefficient].

**Decay rate** at 44,118 Hz (impulse, 0.05–0.5 s, rt 0.75, upstream's
longest): 0.961 of the class at its own rate, 0.917 without compensation;
0.965 when both sides go through the tone filter, as in mi-fx.md's 0.967
[verified]. At rt 0.375 the ratio is 0.926 (0.878): that tail reaches the
12-bit floor within the window [verified figures; cause inferred]. The
in-loop damping (0.75) and the LFO are fixed upstream: the LFO's constant
`0.3 / 48000` gives 0.299 Hz at Plaits' own rate and 0.276 Hz at
44,118 Hz, and the 3,070-sample loop tap goes from 64.1 to 69.6 ms
[verified: constants and sample identity].

Upstream's amount crossfades inside the class; the wrapper crossfades after
its additions, so at the same Mix its wet is 6 dB lower than upstream's at
the same amount (the documented wet gain) [verified: code and model].

## Limits

- fm1-render's inputs are mono. The Ensemble's stereo path is exercised only
  through the Width probe; Plate and Diffuse sum their inputs anyway.
- 16-bit output: differences below about 10⁻⁵ of full scale are invisible,
  and Shapes are seen at a quarter of the oscillator's resolution.
- No parameter changes during a note (fm1-render has none), and one voice at
  a time for the exact Shapes comparison.
- Shapes are compared at 96 kHz only; the effects at their native rates and
  at 44,118 Hz.
- Run here on macOS arm64 (Apple clang) only. The CI's Linux, 32-bit and
  sanitizer jobs will run the file; the knob search accepts only values that
  give the upstream coefficient with and without a fused multiply-add, so
  x86's unfused arithmetic should give the same knobs [inferred].

## For the shared files (outside this lane)

- `third_party/mutable/UPSTREAM.md`, "Block size": Braids too; Shapes now
  renders in exactly 24-sample blocks and buffers them out.
- `engines/README.md`: list this file; Shapes' instance is now 205,800
  bytes (Shapes + PSX Verb + Plate 405,672); Shapes at 44,118 Hz rings
  1.6–2.8 times longer on the struck shapes (open question).
- `engines/mi-fx.md`: the residual decay cause (above), 6.06 Hz for the
  Ensemble's fast LFO, Tone 0.75's −3 dB point, and Plate's damping
  compensation now covered here.
- `docs/11` §8: stage A's exit test met for Shapes, Plate, Ensemble and
  Diffuse. `CHANGELOG.md`: the Shapes fix.

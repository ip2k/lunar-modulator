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
| `tests/test_engines_reference_braids_fx.py` | 226 tests, about 14 s on an M1 Max |

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
| Shapes | `braids::MacroOscillator`, 96 kHz | all 47 shapes match within the renderer's quantisation, **after a fix in this lane**: before it, 22 of 47 did not in the FM-1's 64-frame host blocks, and odd-sized renders crashed | since Shapes runs Braids at 96 kHz and resamples ([resampler.md](resampler.md)), all 47 shapes match upstream through the same resampler within quantisation, and Bell and Drum decay at upstream's rate (0.9999–1.0000). Before that, pitch was corrected and time constants were not: Bell and Drum decayed at 0.46 of upstream's dB/s (below) |
| Plate | `rings::Reverb`, 48 kHz | identical within quantisation | identical to `rings::Reverb` with its loop gain and damping rescaled; decays at 0.961–0.970 of the native rate |
| Ensemble | `plaits::Ensemble`, 47,872 Hz | identical within quantisation at Width 0; the defaults are upstream plus the documented Width and mix law | identical sample for sample: nothing is compensated, delays and LFOs run 8.5 % long and slow |
| Diffuse | `plaits::Diffuser`, 47,872 Hz | identical to upstream plus the documented wet gain, tone filter, decorrelator and mix | identical to `plaits::Diffuser` with its loop gain rescaled; decays at 0.961 of the native rate |

All [verified] by the tests below. "Within quantisation" means that no sample
of fm1-render's 16-bit output lies further than 0.51–0.55 LSB from the
reference scaled as the wrapper scales it, and that the residual has the rms
of rounding alone (about 0.29 LSB; up to 0.34 for Shapes, whose output sits
on a quarter-LSB grid).

For the random shapes "match" has two meanings, kept apart below: exact
against the oscillator given the same random numbers, and statistical
against Braids' firmware, whose numbers are not the same.

## The reference tool

`fm1-ref-braids-fx` has two modes and prints one line of JSON per run.

**`braids`** follows `RenderBlock` in `braids/braids.cc` (read in the pinned
upstream checkout) [verified]: 96 kHz, one 24-sample block at a time,
`set_shape`, `set_parameters(timbre, color)` and `set_pitch` (1/128 semitone)
before every block, the sync buffer all zero, the oscillator in static
storage as Braids' global `osc` is. It writes the oscillator's raw int16.
Braids' firmware stages after the oscillator (AD envelope and VCA, bit and
rate reduction, the signature waveshaper, the inverted DAC write) are not
part of the comparison.

- `--strike-block B`, repeatable, calls `Strike()` before block B (block 0
  when none is given), as a trigger does. Block 0 is struck whatever the
  option says: `DigitalOscillator::Init` sets the strike flag, and
  `set_shape` strikes when the shape changes from the zeroed one [verified:
  code, and `--strike-block` renders].
- `--block` must be even. Eleven of Braids' digital renderers write two
  samples per loop pass (Vowel FOF, Harmonics, Pluck, Bowed, Bell, Drum,
  Kick, Snare, Wave ×4, Twin Peaks, Particle), and an odd size runs off the
  end of the buffer; the first version of this tool crashed (SIGBUS) for all
  eleven whenever the last block was odd [verified]. A `--samples` that is
  not a multiple of the block now ends with a whole block rendered into
  scratch and cut short, so a render is a prefix of any longer one
  [verified: `test_reference_renders_whole_even_blocks`].
- `--seed S` starts `stmlib::Random` elsewhere; the JSON reports the
  generator's state before and after, which is how the shapes that draw on
  it were found.
- `--jitter-draw 1` adds the one `Random::GetWord()` per block that
  `RenderBlock` makes for its VCO jitter source before the oscillator
  renders, whatever the drift setting (`braids.cc` line 244,
  `vco_jitter_source.h` line 58) [verified: code]. Off by default, because
  fm1-render has no such draw (see "Random shapes").

**`fx`** runs one effect class on a mono input fed to both channels, set up
as its upstream caller sets it up [verified: the callers' sources]:

| Effect | Caller | Settings from the caller's knob | Block |
| --- | --- | --- | --- |
| plate | `rings/dsp/part.cc`, string-and-reverb model | `--damping d --brightness b`: amount 0.1 + 0.5 d, time 0.35 + 0.63 d, lp 0.3 + 0.6 b, diffusion 0.625, input gain 0.2 | 24 |
| ensemble | `plaits/dsp/engine2/string_machine_engine.cc` | `--timbre t`: amount 2 \|t − 0.5\|, depth 0.35 + 0.65 t | 12 |
| diffuse | `plaits/dsp/engine/particle_engine.cc` | `--morph m`: d = (2 \|m − 0.5\|)² below m = 0.5, else 0; amount 0.8 d², rt 0.25 + 0.5 d | 12 |

Any setting can be overridden (`--amount 1` gives full wet, `--diffusion`
sets the plate's all-pass coefficient). `--compensate HOST` applies
engines/mi-fx.md's rate rule to the loop settings. `--right-delay N
[--right-width W]` replaces the right channel x with x + W (late − x), late
being x N samples later: the line Ensemble's Width builds. `--input-file`
reads a mono or stereo 32-bit float WAV instead of a generated input, for
the stereo output of an effect earlier in a chain. The classes have no
sample rate; `--rate` only sets the sample count, the sine's frequency and
the WAV header. The impulse, noise and sine inputs are fm1-render's, sample
for sample [verified: identical outputs where the two sides should agree].
Output is 32-bit float stereo.

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
  modelled in Python, at more than one setting each (Width 0, 0.5 and 1;
  Plate's Diffusion 0, 0.5 and 1).
- **Stereo inputs.** fm1-render's inputs are mono, but Plate's output is
  not (its two sides differ by up to 14,394 LSB on noise). Plate followed by
  Ensemble, and Plate followed by Diffuse, at 44,118 Hz, compared against
  upstream's plate whose output is fed to upstream's ensemble and, summed as
  the wrapper sums it, to upstream's diffuser [verified: within 0.500 LSB].
- **Mutation check** [verified]. Each of these fails at least one test:
  the unfixed Shapes wrapper; the eleven mutants of `mi_fx.cc` from the
  first round (Plate's input gain, time or damping compensation removed,
  diffusion slope; Ensemble's offset line at 130 samples, its dry law;
  Diffuse's rate compensation removed, wet gain 0.55, decorrelator
  coefficient 0.45 or length 240, tone corner 260 Hz) and, from the review
  of this lane, Ensemble's and Diffuse's Width squared, Plate's diffusion
  `0.525 + 0.2 x`, Diffuse's wet taken from the left input alone, Shapes'
  note-on without `Strike()`, its release ignored and its velocity squared.
  Which tests catch which is in the table at the end. Shapes' pitch bend is
  not tested: fm1-render cannot send one (requested below).
- **Sanitizers** [verified]: the whole suite (611 tests, this file's 226
  included) passes under the ASan + UBSan build (README) with
  `halt_on_error=1`.

## Shapes

### Result

All 188 cases (47 shapes × 2 points × 2 pitches) are within quantisation:
worst sample 0.522 LSB, residual rms 0.035–0.313 LSB [verified].

**The strike.** Every first note is struck whatever the wrapper does,
because a fresh oscillator's `Init` sets the strike flag and the first
`set_shape` strikes on the change from shape 0 (above); the 188 cases
therefore do not test the wrapper's own `Strike()`. What does is a retrigger:
the same key again while it is held reuses its voice, and the note-on
strikes the running oscillator, as a Braids trigger strikes its one
oscillator. Against the reference struck at blocks 0 and 1,203, 16 shapes
are within quantisation (worst 0.522 LSB, rms 0.108–0.339); the strike
changes 12 of them by 1,478–14,336 LSB (Swarm, Vowel, Pluck, Bowed, Blown,
Flute, Bell, Drum, Kick, Snare, Wave ×4, and Clocked Noise at timbre 0.75),
and the other four not at all [verified:
`test_retrigger_strikes_the_running_voice`, which fails for 12 shapes with
the note-on `Strike()` removed].

**The envelope.** The wrapper's own velocity and release around the
oscillator are modelled too: velocity 64 sets the target to 64/127, and
Release 0.3 is a 12.0 ms one-pole from the note-off, which lands at a chunk
boundary (worst 0.504–0.517 LSB, rms 0.288–0.291, CSaw and Bell) [verified].

### Found and fixed: Braids must render in 24-sample blocks

Before this lane the wrapper rendered each host block in pieces of at most
24 samples: 24 + 24 + 16 for the FM-1's 64 frames. Braids' firmware only
ever renders 24, and several shapes advance once per block rather than per
sample, so 22 of the 47 shapes left upstream's output [verified: the tests
against the unfixed wrapper]: 0–3, 5–12, 15, 17–20, 22, 32, 33, 39 and 44.

- **Struck models decayed faster.** Bell's and Drum's partial amplitudes
  step once per render call. Three calls per 64 samples instead of 64/24 =
  2.67 makes a per-call decay 12.5 % faster in dB/s [inferred from the
  code]. Measured with the energy-decay curve (the time until the energy
  still to come is 10, 20 and 30 dB below the total; 4 s renders at 96 kHz;
  A2, A3 and A4; timbre/colour 0.25/0.75, 0.5/0.5 and 0.75/0.25; upstream
  through the same 1 ms attack), the unfixed wrapper decayed 11.6–13.6 %
  faster than upstream for Drum and 7.4–27.9 % for Bell, whose partials beat
  against each other; the same method gives 0.0–0.7 % on the fixed wrapper,
  which is sample-identical [verified, scratch probe]. An earlier figure
  here (Bell 9.4–9.6 %, Drum 15.8 %) came from a short-window fit whose
  method was not recorded, and is withdrawn.
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
- **Odd-sized renders crashed.** The eleven two-samples-per-pass shapes
  (above) overran the voice's buffer whenever a render call's size was odd,
  and with `size_t` wrapping ran away until the process died. The unfixed
  fm1-render exits on SIGBUS for all eleven with `--frames 7`, and for Drum
  at the default 64 frames with `--seconds 1.5` at 44,118 Hz (66,177 frames,
  a last block of 1); ASan reports a heap-buffer-overflow in
  `RenderStruckBell` (`digital_oscillator.cc:915`, called from
  `mi_shapes.cc:134`) [verified]. The engine API allows any render size up
  to `max_frames`; a host that always renders 64 frames would not have met
  it [inferred], but fm1-render's last partial block did. The fix removes
  it, since the oscillators now only ever see 24
  [verified: `test_shapes_output_does_not_depend_on_the_host_block` renders
  4,801 frames in blocks of 1, 7, 24, 64 and 100 for these eleven shapes and
  the block-sensitive ones, and fails on the unfixed wrapper].

The fix (`src/mi_shapes.cc`): every voice renders exactly 24 samples per
chunk into a mix buffer that `Render` hands out across host calls, as the
Macro wrapper already does with Plaits' 12-sample blocks. Consequences:

- Output is bit-identical for host blocks of 1, 7, 24, 64 and 100 frames,
  odd totals included [verified].
- A note, parameter or bend now takes effect at the next 24-sample boundary,
  up to 23 samples late (0.52 ms at 44,118 Hz when Braids ran at the host's
  rate; 0.24 ms now that it runs at 96 kHz, plus the resampler's delay:
  0.43–0.68 ms from a note to its onset, resampler.md) [inferred from the
  code; two cases verified at 96 kHz: a note-on 8 samples late in
  `test_note_on_starts_the_voice_at_a_braids_block_boundary`, and a
  retrigger 8 samples late in `test_retrigger_strikes_the_running_voice`;
  the 44,118 Hz case in `test_note_on_at_host_rate_starts_on_a_braids_block`].
- Cost unchanged: 12 voices at 44,118 Hz took 3.63 µs per 64-frame block
  for CSaw (3.73 µs before), 3.72 for Vowel (3.83), 6.52 for Bell (6.52),
  Apple M1 Max, best of five [verified, with Braids at the host's rate; at
  96 kHz and resampled it is 2.35–2.77 times that, resampler.md]. A first
  version that accumulated straight into the member buffer cost 26–55 %
  more: the compiler must assume a member float array may alias `v.env`;
  the mix stays on the stack.
- The instance grows by the 24-float buffer and its counter: 205,696 →
  205,800 bytes on the 64-bit desktop [verified: `instance_bytes`]; the
  resampler later took it to 206,512 (resampler.md).

### Random shapes

Thirteen shapes draw on `stmlib::Random`: Swarm, Vowel, Pluck, Blown, Flute,
Drum, Snare, Wave ×4, Filtered Noise, Twin Peaks, Clocked Noise, Granular and
Particle (14, 22, 28, 30, 31, 33, 36, 40–45) [verified: generator state
before and after a render].

**Exact, against the oscillator given the same numbers.** A lone Shapes
voice matches the reference within quantisation (worst 0.499–0.519 LSB, rms
0.110–0.324) because both draw from the one global generator from its
initial state, 0x21, with nothing else drawing [verified]. That is a
convention of the comparison, not what Braids' firmware does. Started
elsewhere (`--seed 1`) the same shapes differ by more than 2 LSB, so the
exact match does depend on the numbers [verified]; Clocked Noise uses its
seed only when its timbre-set period wraps, which at timbre 0.25 takes over a
second, so its tests use timbre 0.75.

**Statistical, against Braids' firmware.** The firmware's `RenderBlock`
draws one word per block for its VCO jitter before the oscillator renders
(above), and the draws run from power-on, so the generator's state at a
trigger depends on how long the module has been running [inferred from the
code]. No fixed seed reproduces the firmware; with the draw added
(`--jitter-draw 1`, from 0x21) the output is more than 2 LSB from the lone
voice's within 0–46 samples for 10 of the 13 shapes (Flute at sample 436,
Particle 1,950, Clocked Noise 3,969; A4) [verified]. Against the firmware from three starting states, over one
second at A4, fm1's level lies within −0.45 to +0.53 dB and its brightness
(rms of the first difference over rms) within −9.0 to +6.6 % of their mean
[verified]. In a chord the voices share the generator and interleave their
draws, so neither sees a lone voice's numbers [verified: a two-voice chord,
A4 and E5, differs from the sum of the two lone voices by more than 2 LSB].
Statistically that makes no difference either: against the sum of two
firmware voices from three pairs of starting states, the chord lies within
−0.90 to +0.95 dB and −6.9 to +0.7 % [verified]. The tests allow 2 dB and
25 %.

### At 44,118 Hz

Shapes now runs Braids and its own envelope at 96 kHz whatever the host's
rate and resamples the voice mix to the host's rate (resampler.md, the
owner's decision of 2026-10-01). At 44,118 Hz every shape matches upstream
at 96 kHz, through the wrapper's envelope and gain and the same resampler,
within quantisation: 47 shapes × 2 timbre/colour points × A2 and A6, worst
0.55 LSB, rms 0.35, random shapes included [verified:
`test_shape_at_host_rate_is_braids_resampled` in
`tests/test_engines_resampler.py`]. The struck shapes decay at upstream's
rate: energy-decay times to 10, 20 and 30 dB, 2 s at A4, 0.5/0.5, fm1 less
the resampler's 16-sample group delay, give Bell 0.9999–1.0000, Drum
0.9999–1.0000 and Kick 0.9995–1.0058 of upstream's [verified:
`test_struck_shapes_at_host_rate_decay_as_upstream`]; over all three
timbre/colour points at A3 and A4, 4 s, Bell and Drum 0.9997–1.0000 and
Kick 0.974–1.008, its loosest ratios while the strike's excitation sounds
[verified, scratch probe].

**Before** (Braids at the host's rate with the pitch corrected by
12 log2(96,000 / rate) semitones), measured the same way at A4, 4 s
[verified, scratch probe; the 0.5/0.5 point was held by the test]:

| Shape | 0.25/0.75 | 0.5/0.5 | 0.75/0.25 |
| --- | --- | --- | --- |
| Bell | 0.459 / 0.460 / 0.458 | 0.468 / 0.466 / 0.458 | 0.458 / 0.458 / 0.460 |
| Drum | 0.465 / 0.464 / 0.462 | 0.466 / 0.463 / 0.462 | 0.467 / 0.463 / 0.461 |
| Kick | 1.04 / 1.56 / 1.02 | 1.03 / 1.02 / 1.02 | 1.39 / 0.98 / 1.00 |

Bell and Drum rang 2.1–2.2 times as long, as their per-block decays
predict (44,118/96,000 = 0.460) [inferred from the code, matching the
measurement]. Kick rang as long as upstream's: a band-pass resonator of
fixed resonance tuned to the pitch, which was corrected [inferred from the
code]. Its outliers (1.56, 1.39) fell in the first 10–20 dB, while the
strike's excitation still sounded (the first 7–11 ms at 0.25/0.75, 53–74 ms
at 0.75/0.25) [verified figures; not traced]. Anything else fixed in samples (formant and filter frequencies not
derived from pitch, per-block envelopes, delay-line lengths) sat at 0.46 of
its upstream frequency or 2.18 times its duration [inferred]; at 96 kHz
none of it moves.

### Intentional differences

- The wrapper's own envelope, velocity and Volume (gain 0.25/32768 at
  Volume 1), and twelve voices where Braids has one.
- No VCO jitter draw: fm1-render draws nothing from the generator between a
  voice's renders, where Braids' `RenderBlock` draws once per block (above).
  The reference omits it by default so that the random shapes can be
  compared exactly; `--jitter-draw 1` restores it.
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
brightness and Diffusion = the all-pass coefficient `0.5 + 0.25 x`, 0.625 at
0.5 as upstream fixes it [verified: the code].

| Case | Worst | Rms |
| --- | --- | --- |
| 48 kHz: 3 inputs × Rings (damping, brightness) (0.3, 0.8), (0.5, 0.5), (0.7, 0.4) × {full wet, Rings' amount}, knobs giving Rings' exact coefficients | 0.500 LSB | 0.285–0.290 |
| the same at full wet with the obvious knobs (Damping = 1 − brightness: lp one or two ulps off) | 1.86 LSB | 0.287–0.305 |
| 48 kHz, impulse and noise, Diffusion 0 and 1 against diffusion 0.5 and 0.75 | 0.500 LSB | 0.285–0.289 |
| 44,118 Hz, impulse and noise, damping 0.3/0.5/0.7, against `rings::Reverb` with time and lp rescaled | 0.500 LSB | 0.285–0.289 |

[verified]. At 44,118 Hz the wrapper changes exactly two settings, time
0.539 / 0.665 / 0.791 → 0.510 / 0.642 / 0.775 and lp 0.600 → 0.631, and the
output is otherwise upstream's sample for sample [verified]. So every delay
and LFO keeps its length in samples: 8.8 % longer and slower in seconds,
LFOs 0.5 → 0.460 Hz and 0.3 → 0.276 Hz, the loop's modulated taps at 4,460
and 6,261 samples 92.9 → 101.1 ms and 130.4 → 141.9 ms [verified: sample
identity and the class's constants].

**Decay rate** (impulse tail, 2 s renders, Schroeder slope over 0.05–0.6 s,
fm1 at 44,118 Hz against the class at 48 kHz): 0.961 / 0.967 / 0.970 at
Rings damping 0.3 / 0.5 / 0.7; without compensation (the same upstream
samples read at 44,118 Hz) 0.914 / 0.921 / 0.927 [verified]. That
reproduces mi-fx.md's 0.96–0.97 and 0.914–0.926. On the residual 3 %,
mi-fx.md names the loop's 16-bit truncation [inferred there]. Probes with
the reference tool, the compensated class against the native one [verified
figures]: with lp = 1 (no damping filter) the ratio is still 0.968 / 0.973 /
0.976, so the damping filter's imperfect rescaling is a small part; at
damping 0.5, doubling the loop's level (input gain 0.4) moves it only from
0.967 to 0.973, and by window it is 0.962 (0.05–0.3 s), 0.972 (0.3–0.6 s)
and 0.952 (0.6–1.0 s; 0.950 in fm1's 16-bit output, where the tail nears
its floor), not the steady fall with level that truncation alone would
give. Truncation may contribute; a per-pass loss the rule does not rescale
is a likelier main cause, such as the linear interpolation of the two
modulated loop delays, which low-passes on every pass by an amount set by
the fractional delay [inferred; not separable without modifying the vendored
class].

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
| Mix 0.5, Depth 0.5, Width 1 and 0.5, impulse and noise, against the class fed on the right x + Width (x 131 samples late − x), remixed by the documented law | 0.500 LSB | 0.005–0.289 |
| 44,118 Hz, noise, Depth 0 and 1, Width 0 | 0.500 LSB | 0.289 |
| 44,118 Hz, Plate's stereo output (impulse, noise) into the defaults, each side against its own line and dry | 0.500 LSB | 0.287–0.288 |

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
wrapper runs the class at amount 1 on the mono sum 0.5 (L + R) and then
adds, in order: wet × 0.5; per side a Schroeder all-pass (241 / 349 samples,
g 0.5) blended in by Width; a one-pole low-pass at Tone; and the crossfade
from that side's dry by Mix [verified: the code, and the model below
matching].

| Case | Worst | Rms |
| --- | --- | --- |
| 47,872 Hz, 3 inputs × morph 0.5 / 0.25 / 0 (rt 0.25 / 0.375 / 0.75), Mix 1, Width 0, Tone 1 modelled | 0.501 LSB | 0.210–0.289 |
| Mix 0.5, Tone 0.75, Width 1 and 0.5, rt 0.375, impulse and noise, all four additions modelled | 0.500 LSB | 0.285–0.290 |
| 44,118 Hz, noise, rt 0.75 and 0.375, against the class with rt rescaled (0.7319, 0.3450) | 0.500 LSB | 0.289 |
| 44,118 Hz, Plate's stereo output (impulse, noise) into the defaults at rt 0.375: the class fed the mono sum, each side crossfaded from its own dry | 0.500 LSB | 0.285–0.290 |

[verified]. Tone 1 is not a bypass: its coefficient is 0.985 at 47,872 Hz,
only −0.26 dB at Nyquist, but its phase lag leaves the output −36 dB from
the unfiltered wet, so the tests model it [verified]. Tone 0.75, the
default, puts the one-pole's nominal corner at 9.5 kHz (mi-fx.md's "about
9.5 kHz"); its −3 dB point is 11.1 kHz at 47,872 Hz and 11.5 kHz at
44,118 Hz [verified: computed from the coefficient].

**Decay rate** at 44,118 Hz (impulse, 2 s renders, 0.05–0.5 s, rt 0.75,
upstream's longest): 0.961 of the class at its own rate, 0.916 without
compensation; 0.965 when both sides go through the tone filter, as in
mi-fx.md's 0.967 [verified]. At rt 0.375 the ratio is 0.926 (0.878): that
tail reaches the 12-bit floor within the window [verified figures; cause
inferred]. The in-loop damping (0.75) and the LFO are fixed upstream: the
LFO's constant `0.3 / 48000` gives 0.299 Hz at Plaits' own rate and
0.276 Hz at 44,118 Hz, and the 3,070-sample loop tap goes from 64.1 to
69.6 ms [verified: constants and sample identity].

Upstream's amount crossfades inside the class; the wrapper crossfades after
its additions, so at the same Mix its wet is 6 dB lower than upstream's at
the same amount (the documented wet gain) [verified: code and model].

## Limits

- fm1-render's own inputs are mono; stereo reaches Ensemble and Diffuse
  only from Plate, in the two chain tests. Plate's own stereo input is
  upstream's concern: the class sums the two sides itself.
- 16-bit output: differences below about 10⁻⁵ of full scale are invisible,
  and Shapes are seen at a quarter of the oscillator's resolution.
- No parameter changes during a note (fm1-render has none), and no pitch
  bend. Chords are compared statistically only; the exact Shapes
  comparisons are one voice at a time.
- Shapes are compared sample for sample at 96 kHz here, and at 44,118 Hz
  through the resampler in `tests/test_engines_resampler.py`, where the
  comparison also depends on the resampler being the same on both sides.
  The effects at their native rates and at 44,118 Hz.
- Run here on macOS arm64 (Apple clang) only. The CI's Linux, 32-bit and
  sanitizer jobs will run the file; the knob search accepts only values that
  give the upstream coefficient with and without a fused multiply-add, so
  x86's unfused arithmetic should give the same knobs [inferred].

## Which tests catch which mutant

Each row is one change to a wrapper, the whole suite run against it
[verified]:

| Mutant | Tests that fail |
| --- | --- |
| Shapes before the 24-sample fix | 80: the 188-case match, host-block independence, note-on timing, retrigger, velocity and release, the exact random-stream match, the host-rate decay |
| Shapes: note-on without `Strike()` | 12: the retrigger, one per struck shape |
| Shapes: release ignored (`k = attack`) | 2: velocity and release |
| Shapes: velocity squared | 2: velocity and release |
| Shapes: pitch bend ignored | **none**: fm1-render cannot bend (requested below) |
| Ensemble: Width squared | 2: Width and mix at Width 0.5 |
| Diffuse: Width squared | 2: the defaults at Width 0.5 |
| Plate: diffusion `0.525 + 0.2 x` | 4: Diffusion 0 and 1 |
| Diffuse: wet from the left input alone | 2: the stereo input from Plate |
| Plate: input gain 0.21 | 32 |
| Plate: time not rate-compensated | 12 (2 in `test_engines_mi_fx.py`) |
| Plate: damping not rate-compensated | 10 |
| Plate: diffusion `0.5 + 0.24 x` | 30 |
| Ensemble: offset line 130 samples | 6 |
| Ensemble: dry law `1 − 0.45 mix` | 18 |
| Diffuse: rt not rate-compensated | 6 (1 in `test_engines_mi_fx.py`) |
| Diffuse: wet gain 0.55 | 17 |
| Diffuse: decorrelator coefficient 0.45 | 6 |
| Diffuse: left all-pass 240 samples | 6 |
| Diffuse: tone corner 260 Hz | 17 |

The last eleven are the first round's; each still fails after this lane's
changes to the tests.

## For the shared files (outside this lane)

- `third_party/mutable/UPSTREAM.md`, "Block size": Braids too. Shapes now
  renders in exactly 24-sample blocks and buffers them out, and Braids
  needs even render sizes: eleven digital renderers write two samples per
  loop pass and run off an odd-sized buffer.
- `engines/README.md`: list this file; Shapes' instance is now 205,800
  bytes (Shapes + PSX Verb + Plate 405,672); at 44,118 Hz Bell and Drum ring
  2.1–2.2 times as long as upstream's and Kick as long (open question:
  render at 96 kHz and decimate, or accept). Since answered: Shapes renders
  at 96 kHz and resamples (resampler.md).
- `engines/mi-fx.md`: the residual decay cause (above), 6.06 Hz for the
  Ensemble's fast LFO, Tone 0.75's −3 dB point, and Plate's damping
  compensation, Width and Diffusion now covered here.
- `docs/11` §8: stage A's exit test met for Plate, Ensemble and Diffuse at
  their native rates and at 44,118 Hz; for Shapes met at Braids' native
  96 kHz only. At the FM-1's rate Shapes' time constants differ (Bell and
  Drum decay at 0.46 of upstream's rate): open question, render at 96 kHz
  and decimate, or accept. Since answered: Shapes renders at 96 kHz and
  resamples, and matches upstream at 44,118 Hz too (above, resampler.md).
- `CHANGELOG.md`: the Shapes fix, which also removes a crash (a heap
  overflow under ASan) for odd-sized render calls on the eleven
  two-samples-per-pass shapes.
- `engines/host/render.cc`: a `--bend T:SEMITONES` event, so Shapes' pitch
  bend can be tested (a mutant that ignores bend survives every test); then
  in `tests/test_engines.py` (or this file) a bend test against the
  reference at the bent pitch.

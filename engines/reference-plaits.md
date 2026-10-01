# reference-plaits: Macro, Macro Heavy and Six-Op FM against upstream Plaits

Stage A's exit test is "renders match upstream MI within tolerance"
(docs/11 §8). This stream builds the upstream side for the three engines made
from Plaits, and compares every one of Plaits' 24 engine slots with the fm1
engine that wraps it.

- **Macro** (`src/mi_macro.cc`) wraps 8 slots.
- **Macro Heavy** (`src/mi_macro_heavy.cc`) wraps 13.
- **Six-Op FM** (`src/mi_sixop.cc`) wraps the 3 six-op banks.

The upstream side is Plaits' own `Voice`, vendored and unmodified in
`third_party/mutable/`. Plaits is Emilie Gillet's code (Mutable Instruments,
MIT); see `third_party/mutable/UPSTREAM.md`.

## The result

**At Plaits' own rate (47,872.34 Hz), 21 of the 24 slots match sample for
sample** [verified: tests/test_engines_reference_plaits.py]:

- **How close.** At every tested point the error is −87.3 to −88.5 dBFS. That
  is the size of the 16-bit rounding the fm1 side adds (−88.6 dBFS), and
  nothing else. Under it, the wrappers' DAC words are `Voice`'s bit for bit
  once the reference gets LEVEL as the wrapper's own float (velocity / 127
  as a 32-bit float); the harness used to round it to six decimals, another
  float, and 10 of 28,723 words came out 1 off in the case checked
  [verified: a scratch harness printing the wrapper's words, slot 8 at
  velocity 60; with the exact float, 0 of 28,723; and for every exact slot
  indirectly, by the identical samples at 44,118 Hz below].
- **Every knob that reaches the wrapper.** The three test points vary
  Harmonics, Timbre, Morph, Decay, Colour and velocity, each over three
  values.
- **In the FM-1's host blocks too.** fm1-render in 64-frame blocks writes the
  same bytes as in Plaits' 12-frame blocks, for all 24 slots in all six
  cases. So the wrappers' re-blocking adds nothing.
- **Random engines included.** The seven slots with internal randomness match
  too, because both programs draw from the same generator from the same
  state. An fm1 render from another generator state is no outlier among
  upstream renders with other seeds, on level, envelope, spectrum and pitch.
- **Chiptune** matches once the low-pass gate has opened (from 10 ms). The
  wrapper keeps a gate that upstream bypasses for this engine.

**The three Six-Op slots match closely:** NCC 0.9937 or more, with the fm1
render 35–38 samples ahead [verified]. The two remaining differences are the
wrapper's by design. The spread over all 96 patches is traced to them below.

**At the FM-1's rate (44,118 Hz)**, where since 2026-10-01 the wrappers run
Plaits at its own 47,872.34 Hz and resample the mix with
`fm1_resampler.h` (the owner's decision; plaits-heavy.md, "Rate")
[verified]:

- **Against upstream resampled the same way** (`fm1-ref-plaits
  --host-rate 44118`), at every native-rate point and note: 20 of the 21
  Macro and Macro Heavy slots write the same 16-bit samples as the
  reference, random slots included (0 of 158,820 differ per slot; 317,640
  for the string machine's two channels). Chiptune differs by 1 LSB in 23
  of 76,962, compared from 10 ms as at the native rate, where its error is
  also the highest of the exact slots (−87.3 dBFS): the wrapper keeps a
  low-pass gate that upstream bypasses, transparent there only to within
  float rounding [inferred]. Six-Op matches closely: NCC 0.9885 or more,
  lag −32 to −35 samples.
- **Against upstream at its own rate, unresampled:** pitch within
  0.007 cents on every slot, envelope stretch 1.000–1.001, level within
  0.02 dB. The tests hold pitch to 0.1 cent and the stretch to 1 ± 0.02.
- **Host blocks** of 1, 7 and 64 frames write the same bytes, and a note
  lands on the 12-sample block that the resampler's pulls predict.
- **What went.** Before the change the wrappers ran Plaits at the host's
  rate with the pitch raised by 1.414 semitones: envelopes ran 8.5 % long
  (stretch 1.073–1.092), the pitch table left every tonal engine 0.37 cents
  flat, the noise engine's clock ran 1.41 semitones low (a strict xfail),
  particle and swarm densities 8.5 % low, and the string model was
  −9.5 cents at A2 (findings 2–4). All of that is gone; what is left is the
  resampler's band limit (flat to 18 kHz, a roll-off above, nothing above
  the Nyquist; resampler.md) and its delay (intentional difference 10).

**What the comparison covers.** Both programs link the same compiled
vendored objects (`build/tp/*.o`) and include the same headers. So the render
comparison checks the wrapper layer:

- parameter mapping, gains and polarity, velocity;
- the low-pass gate, the decay envelope and the post-processor as driven;
- trigger timing and re-blocking.

The engine DSP is the same object code on both sides. A local change to a
vendored file, or to its compile flags, would move both sides together
[verified: a scratch copy with `VirtualAnalogEngine`'s 7.01 interval changed
to 5.01 passed every render comparison]. The exceptions compare an
adaptation: Speech (upstream `SpeechEngine` against the wrapper's
`SpeechVoiceEngine`) and Six-Op (`SixOpEngine` against the wrapper's own
`FMVoice` handling). The vendored DSP is therefore pinned instead:

- **By hash.** `test_vendored_plaits_code_is_pinned` hashes the 129 vendored
  files that `fm1-ref-plaits` compiles and that it and the three wrappers
  include.
- **Against upstream.** All 129 are byte-identical to local clones of
  eurorack `08460a69` and stmlib `e3bd7c9c` [verified: file comparison,
  2026-09-30].

So for the Plaits-derived engines the exit test is met for the wrapper
layer, at Plaits' rate and at the FM-1's, and the engine code is upstream's
own, pinned.

**No wrapper code was changed by the comparison itself.** Nothing found at
the native rate is a defect in a wrapper. The findings (below) are:

1. a polarity inconsistency between the engines;
2. frequencies set from TIMBRE, not from the note, that the rate compensation
   missed (verified for the filtered-noise model);
3. the same for the low-pass gate's filter [inferred];
4. the string model's tuning depended on the rate at low notes;
5. documentation: two intentional differences the existing notes did not
   describe, and two statements that do not hold.

Findings 2–4 were consequences of running Plaits at the host's rate. The
change of 2026-10-01 (Plaits at its own rate, resampled) removed all three
[verified: "At 44,118 Hz", under Results].

## Files and commands

| File | What |
| --- | --- |
| `test/ref_plaits.cc` | `build/fm1-ref-plaits`: renders upstream `plaits::Voice`, at its own rate or resampled to a host's (`--host-rate`), and compares two WAVs (`--compare`) |
| `mk/ref-plaits.mk` | Builds it. It adds `voice.cc` and Plaits' `SpeechEngine` for this binary only; fm1-render is unchanged |
| `../tests/test_engines_reference_plaits.py` | 185 tests; about 35 s on an M1 Max with 8 worker threads, about 105 s under ASan+UBSan. Also the `--report`, `--calibrate` and `--sixop-sweep` modes that print this file's tables |

```bash
make -C engines
# upstream: slot 19 (StringEngine), A3, TRIG and LEVEL patched, note held 0.6 s
engines/build/fm1-ref-plaits --engine 19 --note 57 --harmonics 0.2 --timbre 0.5 \
    --morph 0.8 --seconds 0.6 --out ref.wav
# the same through the wrapper, at Plaits' rate and block size
engines/build/fm1-render --engine macro-heavy --param Model=8 --param Harmonics=0.2 \
    --param Timbre=0.5 --param Morph=0.8 --param Volume=1 --note 0:57:100:0.6 \
    --seconds 0.6 --rate 47872.34 --frames 12 --out fm1.wav
engines/build/fm1-ref-plaits --compare ref.wav fm1.wav --gain 0.25
# at the FM-1's rate: upstream resampled as the wrapper resamples, at fm1's
# scale (LEVEL as the wrapper's float, 100/127), against fm1-render's defaults
# (44,118 Hz, 64 frames); the left channels are identical (the reference's
# right channel is AUX, which this model does not use)
engines/build/fm1-ref-plaits --engine 19 --note 57 --harmonics 0.2 --timbre 0.5 \
    --morph 0.8 --level 0.787401556968689 --seconds 0.6 --host-rate 44118 --out ref44.wav
engines/build/fm1-render --engine macro-heavy --param Model=8 --param Harmonics=0.2 \
    --param Timbre=0.5 --param Morph=0.8 --param Volume=1 --note 0:57:100:0.6 \
    --seconds 0.6 --out fm144.wav
python -m pytest tests/test_engines_reference_plaits.py
python tests/test_engines_reference_plaits.py --report        # the tables below
python tests/test_engines_reference_plaits.py --calibrate     # the statistical factors
python tests/test_engines_reference_plaits.py --sixop-sweep   # all 96 Six-Op patches
python tests/test_engines_reference_plaits.py --sixop-sweep --render other/fm1-render
                                                              # the same, another build
```

## The reference: `plaits::Voice` as the module drives it

**What it runs.** `fm1-ref-plaits` links the vendored `plaits/dsp/voice.cc`
with all 24 engines, including Plaits' own `SpeechEngine` (Macro Heavy runs an
adaptation of it). It links no wrapper source. The driving is set up as the
module sets it up:

- **One shared arena.** One static `Voice` is initialised in one 16,384-byte
  buffer. That is the arena size the module's firmware passes
  [reported: upstream `plaits/plaits.cc`, not vendored; plaits-heavy.md]. It
  is also the particle engine's single allocation [verified: code]. Every slot
  renders under ASan, so every allocation fits [verified].
- **Block by block.** `Voice::Render` is called with a `Patch` and
  `Modulations` every `kBlockSize` = 12 frames at `kCorrectedSampleRate` =
  47,872.34 Hz [verified: `plaits/dsp/dsp.h`]. That the module's audio
  callback delivers 12-frame blocks is [reported: upstream `plaits.cc`].
- **Output.** The WAV holds the frames `Voice` fills, the module's DAC words:
  OUT left, AUX right. The header says 47,872 Hz, and compare mode reads that
  as 47,872.34.

**How the knobs and inputs are set:**

| Upstream input | Reference | Why |
| --- | --- | --- |
| Engine | `patch.engine` = slot index, CV 0 | The engine quantizer returns the index unchanged [verified: `HysteresisQuantizer2`] |
| Note | `patch.note` = the MIDI note, V/OCT CV 0 | `Voice` averages the V/OCT CV with the previous block's; the knob's note is used as is |
| HARMONICS, TIMBRE, MORPH | `patch.*` | The wrappers pass the same values |
| Decay, LPG colour | `patch.decay`, `patch.lpg_colour` | The wrappers' Decay and Colour |
| Attenuverters (FM, TIMBRE, MORPH) | 0 | The wrappers apply no internal-envelope modulation. At 0 the attenuverters also set speech prosody 0, word speed 0 and the chiptune envelope shape 0 |
| TRIG, LEVEL | both patched; TRIG 1 and LEVEL = velocity/127 while the note is held, both 0 after | As the wrappers drive their engines (plaits-heavy.md). `--mode ping` (TRIG only) and `--mode free` are there too |

**Trigger timing.** `Voice` writes TRIG into a `DelayLine` and reads it at
`kTriggerDelay` = 5. `DelayLine::Read(d)` returns the sample written d − 1
writes ago, so the engines see TRIG 4 blocks late: 48 samples, the "1 ms" of
`voice.cc` [verified: code, and
`test_trigger_reaches_the_engine_48_samples_late`]. LEVEL is not delayed. The
wrappers trigger on the note-on block.

By default the reference therefore:

- raises TRIG 4 blocks early, so the engine sees the edge at t = 0;
- selects the engine at t = 0, rendering those 4 blocks on `GrainEngine`,
  which is silent with LEVEL at 0, uses no arena and draws no random numbers.

Its `Reset()` then falls where the wrapper's note-on reset does.
`--literal` gives the module's own timing instead: engine selected from the
first block, TRIG and LEVEL together.

**Randomness.** `stmlib::Random` is one global generator whose state starts
at 0x21. `--seed N` sets it after `Voice::Init`. Unseeded, the generator is
still at 0x21 when the note starts, as it is in fm1-render: seeding 0x21
explicitly gives byte-identical output
[verified: `test_shared_seed_is_stmlibs_initial_state`].

**Six-Op.** `--delay-blocks N` starts the note N blocks later. The reference
also reports the patch HARMONICS selects, with its transpose and key-sync
flag.

**At a host's rate (`--host-rate HZ`).** What the wrappers deliver to a host
at that rate, since they run Plaits at 47,872.34 Hz and resample
[verified: the code]:

- **The same `Voice` blocks.** `Voice` renders the same 12-sample blocks
  at 47,872.34 Hz, with the aligned TRIG lead above.
- **Events on the block the wrapper uses.** fm1-render applies a note-on or
  note-off at the start of the first host block (`--host-frames N`, 64 by
  default) at or after its time; the wrapper acts on it in the first block
  it renders after that. The reference finds that block by a dry run of
  `fm1_resampler.h` itself, fed zeros one sample at a time as
  `fm1_resampler_needed` asks, counting the samples pulled before each host
  sample. `--at S` starts the note at S seconds (default 0); `--gate S` is
  its length. The tests check the dry run against an independent model of
  the resampler's arithmetic (`inputs_pulled`) and against a render.
- **Silence before the note.** Blocks before the note's block are written as
  silence (the wrapper has no voice yet), and the engine is selected at the
  note's block, so its `Reset()` again falls where the wrapper's does.
- **Resampled at fm1's scale.** The DAC words times `--host-gain G` (0.25:
  Volume 1, one voice; the tests pass −0.25 for Six-Op, whose polarity is
  the opposite) over 32,768 are exactly the floats a wrapper voice mixes
  (word × 2⁻¹⁷). Each channel goes through its own `fm1_resampler.h`
  instance, and the result is written as fm1-render writes its output
  (× 32,767, rounded, clamped). So the reference does not clip where
  upstream's words are at full scale and the resampler overshoots it
  (8 of the 24 slots reach full scale, and up to 1.09 times it once
  resampled [reported: the adversarial review of this change's design,
  F2]), and fm1 compares with it at gain 1.
- **Refused rates.** A host above 47,872.34 Hz or below a quarter of it is
  refused, as the wrappers refuse it. `--literal` and `--delay-blocks` do
  not combine with it.

## Mapping

Out and aux gains, and the enveloped flag, are as `Voice::Init` registers
them. A negative gain means the limiter runs at that pre-gain [verified:
`voice.cc`]. The fm1 parameters are the wrapper's.

| # | Upstream engine | Gains out / aux, enveloped | fm1 engine | fm1 parameters |
| --- | --- | --- | --- | --- |
| 0 | `VirtualAnalogVCFEngine` | 1.0 / 1.0 | macro | Model 0 "VA+Filter" |
| 1 | `PhaseDistortionEngine` | 0.7 / 0.7 | macro | Model 1 "PhaseDist" |
| 2 | `SixOpEngine`, bank 1 | 1.0 / 1.0, yes | sixop | Patch 0–31 (HARMONICS' patch = Patch) |
| 3 | `SixOpEngine`, bank 2 | 1.0 / 1.0, yes | sixop | Patch 32–63 |
| 4 | `SixOpEngine`, bank 3 | 1.0 / 1.0, yes | sixop | Patch 64–95 |
| 5 | `WaveTerrainEngine` | 0.7 / 0.7 | macro | Model 2 "Terrain" |
| 6 | `StringMachineEngine` | 0.8 / 0.8 | macro-heavy | Model 0 "Str Machine" (OUT and AUX as L and R) |
| 7 | `ChiptuneEngine` | 0.5 / 0.5 (enveloped when clocked) | macro | Model 3 "Chip" |
| 8 | `VirtualAnalogEngine` | 0.8 / 0.8 | macro | Model 4 "VA Pair" |
| 9 | `WaveshapingEngine` | 0.7 / 0.6 | macro | Model 5 "Shaper" |
| 10 | `FMEngine` | 0.6 / 0.6 | macro | Model 6 "2-op FM" |
| 11 | `GrainEngine` | 0.7 / 0.6 | macro-heavy | Model 3 "Formant" |
| 12 | `AdditiveEngine` | 0.8 / 0.8 | macro-heavy | Model 4 "Additive" |
| 13 | `WavetableEngine` | 0.6 / 0.6 | macro | Model 7 "Wavetable" |
| 14 | `ChordEngine` | 0.8 / 0.8 | macro-heavy | Model 1 "Chords" |
| 15 | `SpeechEngine` | −0.7 / 0.8 (words enveloped) | macro-heavy | Model 2 "Speech" (`SpeechVoiceEngine`) |
| 16 | `SwarmEngine` | −3.0 / 1.0 | macro-heavy | Model 5 "Swarm" |
| 17 | `NoiseEngine` | −1.0 / −1.0 | macro-heavy | Model 6 "Filt Noise" |
| 18 | `ParticleEngine` | −2.0 / 1.0 | macro-heavy | Model 7 "Particle" |
| 19 | `StringEngine` | −1.0 / 0.8, yes | macro-heavy | Model 8 "String" |
| 20 | `ModalEngine` | −1.0 / 0.8, yes | macro-heavy | Model 9 "Modal" |
| 21 | `BassDrumEngine` | 0.8 / 0.8, yes | macro-heavy | Model 10 "Bass Drum" |
| 22 | `SnareDrumEngine` | 0.8 / 0.8, yes | macro-heavy | Model 11 "Snare" |
| 23 | `HiHatEngine` | 0.8 / 0.8, yes | macro-heavy | Model 12 "Hi-Hat" |

Every upstream parameter maps one to one:

- HARMONICS, TIMBRE and MORPH → Harmonics, Timbre, Morph.
- Six-Op: HARMONICS' patch scan → Patch, TIMBRE → Brightness,
  MORPH → Envelope.
- Decay → Decay, LPG colour → Colour.
- LEVEL → the note's velocity.

Checks on the mapping [verified]:

- `test_every_upstream_slot_is_mapped_once` covers the slots, each fm1 model
  and bank exactly once, the engines' class names and `Voice`'s active engine.
- `test_sixop_patch_scan_maps_to_patch_names` checks the patch HARMONICS
  selects upstream against the wrapper's Patch entry of the same name, for
  all 96 patches.

## Method

**Test points.** The same three points and two notes are used for every
slot:

| Point | Harmonics, Timbre, Morph | Decay, Colour | Velocity (LEVEL) |
| --- | --- | --- | --- |
| 1 | 0.2, 0.5, 0.8 | 0.2, 0.8 | 100 (0.787) |
| 2 | 0.5, 0.8, 0.2 | 0.5, 0.2 | 60 (0.472) |
| 3 | 0.8, 0.2, 0.5 | 0.8, 0.5 | 120 (0.945) |

- Each of the five knobs takes 0.2, 0.5 and 0.8 once, with the others
  elsewhere: two Latin squares over the same three points.
- Velocity 127 is avoided: at LEVEL 1 upstream's six-op reads one past the
  end of `lut_cube_root` (plaits-heavy.md, quirk 3).
- The notes are A2 (45) and A4 (69), two octaves apart.
- For Six-Op, HARMONICS 0.2, 0.5 and 0.8 select slots 6, 16 and 26 of each
  bank. Decay and Colour do not reach it on either side.

**Renders.** Six cases per slot, 0.6 s each:

- **Velocity** compresses to the same accent on both sides (0.941 at 100).
- **Gain.** Volume 1, so each fm1 voice is 0.25 of the DAC word. The expected
  fm1-to-reference gain is +0.25, and −0.25 for Six-Op (finding 1).
- **Note length.** Models under the low-pass gate (LPG) are released at
  0.30075 s, so the release is compared too. That puts the note-off on
  sample 14,400 = 75 × 192 in the reference, and at a block boundary in
  fm1-render with 12- or 64-frame blocks (192 is their least common
  multiple). Self-enveloped models are held for the whole render
  (intentional difference 8 says why).
- **Native side.** fm1-render runs at `--rate 47872.34 --frames 12`, and
  again with `--frames 64`: 64 = 5 × 12 + 4, so every host block ends inside
  one of the wrapper's 12-sample blocks (Six-Op's 16). The resampler passes
  samples through at this rate.
- **At the FM-1's rate.** The same six cases per slot, fm1-render at its
  defaults (44,118 Hz, 64 frames), against the reference with
  `--host-rate 44118`. The note-off falls on host sample 13,312, which the
  wrappers act on at 47,872.34 Hz sample 14,460 (block 1,205).
- **LEVEL** is passed as `repr` of the 32-bit float velocity / 127, the
  wrapper's own value (0.787401556968689 for 100).

**The measures.** `fm1-ref-plaits --compare` reports all of them. Each one
targets an error it would catch:

| Measure | What it is | Catches |
| --- | --- | --- |
| Error, dBFS | RMS of fm1/gain − reference at the best lag | anything, when the waveforms should match |
| NCC, lag, least-squares gain | normalised cross-correlation at the best lag (±1 ms, ±2 ms for Six-Op) | a wrong engine or mapping; gain staging and polarity |
| Level, dB | RMS against the expected gain | a broken post-processor, velocity or volume |
| Envelope distance, dB | the largest and mean difference of windowed RMS (10 ms; 50 ms for the statistics), over windows within 40 dB of the peak and above −70 dBFS | a mis-enveloped voice: Decay, Colour, release |
| Pitch shift, cents | the log-frequency shift that best correlates the two magnitude spectra, on a 1-cent grid with parabolic interpolation | mistuning; works for chords, detuned and inharmonic spectra |
| Spectral-envelope shift, cents | the same, on spectra smoothed over ±1/24 octave, in dB | a mistuned filter or resonance under noise |
| Centroid shift, cents | the shift of the power-weighted mean log-frequency | the same, coarser |
| Log-spectral distance, dB | RMS difference of 1/6-octave band powers, 50 Hz–16 kHz, each spectrum normalised. Floors: 50 dB under the louder spectrum's peak, and the quantisation noise | a wrong timbre mapping or filter |
| Stretch | the time scale that best maps one envelope (20 ms windows) onto the other after an event, level offset removed | envelope timing (the rate check) |
| Decay-rate ratio | the ratio of the slopes of lines through each envelope's first 30 dB of fall | the same, for fast releases (Six-Op) |

A measure the tool cannot take (a silent segment) is reported as null. The
exact and Six-Op criteria count a null as a failure.

**Criteria.** Each slot is held to the criteria its differences allow:

- **Exact** (20 slots, and Chiptune from 10 ms: 132 cases with the string
  machine's AUX). The error must be at most −80 dBFS, with no lag.
  - Both sides carry the Voice's own 16-bit words. fm1-render rounds them
    again after the 0.25 volume. Rounding word/4 errs by 0, 1/4, 1/2 or 1/4
    of an fm1 LSB, which is 1.5 LSB² of the reference: RMS √1.5 LSB,
    −88.6 dBFS [verified: arithmetic; measured −88.5]. The limit is 8.6 dB
    above it.
  - The other measures only restate that error. Their limits against the
    worst of the 132 cases [verified: `--report`]:

    | Measure | Worst | Limit | Ratio |
    | --- | --- | --- | --- |
    | Error | −87.3 dBFS | −80 dBFS | 7.3 dB |
    | Gain | 0.0032 dB | 0.01 dB | 3.1 |
    | Envelope | 0.121 dB | 0.25 dB | 2.1 |
    | Pitch | 0.013 cents | 0.05 cents | 3.9 |
    | LSD | 0.161 dB | 0.25 dB | 1.6 |

  - The random points are held to the same criteria, on the shared seed.
  - **64-frame host blocks:** the 64-frame render must be byte-identical to
    the 12-frame one, for every slot and case.
- **Close** (Six-Op, 3 slots).
  - Limits: NCC ≥ 0.981, lag −40 to −32 samples, gain ±0.35 dB, envelope
    0.7 dB, pitch ±0.22 cents, LSD 2.25 dB.
  - Each limit is three times the worst of the 18 cases, rounded up
    (for NCC, three times 1 − NCC): 1 − NCC 0.0063, gain 0.114 dB,
    envelope 0.225 dB, pitch 0.071 cents, LSD 0.743 dB [verified:
    `--report`]. "Six-Op" below traces the differences.
- **Statistical** (6 random slots).
  - **The candidate.** fm1-render has no seed option, so its plain render is
    the shared-seed realisation the exact test already matches. The
    candidate is made another one: fm1-render first plays a pre-note (a
    fifth up, velocity 1, two blocks), which draws from the generator and
    has died away (at most 1 LSB) 2.005 s later, when the held candidate
    note starts. The part from its note-on is compared. The test checks it
    is not the shared-seed realisation (−16 to −48 dBFS from it, against
    −88 for a match) [verified].
  - The candidate, 1.5 s, joins five upstream renders with other seeds as a
    sixth member. It must not be the outlier: its median distance to the
    others may exceed the largest leave-one-out median of any upstream
    member by a factor, plus a floor.
  - An unmeasurable distance (null, a silent segment) puts the candidate
    infinitely far; between upstream renders it is left out. A silent
    candidate and white noise at the candidate's level both fail at every
    statistical point [verified:
    `test_statistical_criteria_reject_silence_and_noise`].
  - Particle at (0.8, 0.2, 0.5) is left out: at TIMBRE 0.2 it makes about
    two grains a second [verified: code arithmetic, `ParticleEngine::Render`'s
    density], so upstream renders differ so much that silence passed as one
    of them. It is compared sample for sample only.
  - **Calibration** (`--calibrate`) [verified]. Each of eight upstream seeds
    in turn was the candidate against five of the other seven, in all 34
    statistical cases (slot, note and point). The largest factors a genuine
    upstream render needed: level 2.91, envelope 1.43, LSD 1.73, centroid
    5.04, envelope shift 4.25; pitch stayed within its 0.5-cent floor.
  - The factors are 1.5 times those: 4.4, 2.2, 2.6, 7.6 and 6.4, and 2.0 for
    pitch (string only). The fm1 candidate's own largest needs were 1.91,
    1.30, 1.25, 1.79 and 0.98: inside upstream's own spread on every
    measure.
- **At the FM-1's rate, against upstream resampled** (44,118 Hz, the six
  cases per slot; `test_matches_upstream_resampled_at_the_fm1_rate`).
  - **Within 1 LSB** of fm1-render's 16-bit output at every sample, and
    0.1 LSB RMS (`HOST_LSB`), the lengths equal and the reference's peak
    above 100 LSB. Both sides resample the same floats with the same header
    code and write them the same way, so the WAVs are expected to be
    identical, and are, except Chiptune's 23 samples (above). The 1 LSB
    leaves room for a compiler that evaluates the resampler's float
    expressions differently in the two programs (contracting a
    multiply-add in one and not the other): that moves a sample by a float
    rounding and can flip its 16-bit rounding by one, never more
    [inferred]. Every wrapper error this comparison exists for moves many
    samples by more (the negative controls below).
  - **Six-Op, closely** (`SIXOP_HOST`): the native-rate limits, with the lag
    window scaled by 44,118 / 47,872.34 to −37..−29 (the native lag of −35
    to −38 samples is −32.3 to −35.0 at 44,118 Hz), and a lag search of
    ±1 ms: ±2 ms reaches the next period of A4 (100 samples), which in one
    case correlated better by a hair (lag +67). NCC drops to 0.9885 on a
    bright A4 case (0.9937 at the native rate): the 36-sample native lag is
    33.2 samples at 44,118 Hz, and the best whole-sample lag leaves up to
    half a sample of misalignment, which costs correlation where the
    spectrum is bright [inferred].
- **At the FM-1's rate, against upstream unresampled** (rate points; tests
  `test_fm1_rate_pitch_matches_upstream` and
  `test_fm1_rate_envelope_timing_matches_upstream`). This is what a wrong
  ratio, a missing resampler or a pitch offset left in a wrapper would move
  even if a reference made the same mistake.
  - Aligned in time: fm1 less the resampler's 30-sample group delay (its
    first 30 frames cropped), and the reference's note-off on the
    12-sample block the wrapper's lands on (Six-Op: the first at or after
    its 16-sample block).
  - **Pitch** 0 within ±0.1 cent, every slot. A pitch offset left in a
    wrapper reads +141 cents, a missing resampler −141, a resampler told
    48 kHz +4.6, and the old pitch table −0.37.
  - **Envelope stretch** 1 ± 0.02 after the note-off (or note-on), by
    envelope fit, every slot but Chiptune (whose LPG upstream lacks); for
    Six-Op by decay-rate ratio, since DX7 releases can fall 30 dB in 30 ms,
    too fast for a 20 ms window fit. The old code gave 1.085.
  - Rate points: (0.5, 0.5, 0.5), a 1 s render, Decay 0.3. FM uses TIMBRE 0
    (a sine, no beating). Six-Op uses patches whose release falls 30 dB
    within the render. Chiptune uses Colour 1 and velocity 127 and compares
    10 ms to the note-off, as at the native rate.
  - The random slots, Chords and the string are held too now: both sides
    draw the same random numbers at the same rate on the shared seed.
- **Host blocks and note timing at the FM-1's rate.** 1, 7 and 64 frames
  per call byte-identical over 13,235 frames with a second note and a
  note-off mid-render, for an LPG model, the string machine, Noise, String
  and Six-Op; a note at 0.0503 s starts on the 12-sample block at
  47,872.34 Hz sample 2,436, as the resampler's arithmetic predicts, with
  exact silence before the first output that reads it.

**Which slots are random**, found by seeding the reference with 0x21, 1 and
2 and comparing OUT [verified]:

| Random at | Slots |
| --- | --- |
| every point | Swarm, Noise, Particle, String (excitation noise), Snare, Hi-Hat |
| one point | Chiptune, at TIMBRE 0.8: the arpeggiator's random mode picks the first note |
| AUX only | Bass Drum's synthetic drum; OUT, the analog one, is deterministic |
| none | the other 16, Speech included: the LPC noise did not reach these points |

Chiptune's randomness is a discrete choice of note, not a distribution, so it
is checked on the shared seed only.

## Results

`python tests/test_engines_reference_plaits.py --report` prints these tables
[verified].

### At Plaits' rate (worst of 6 cases per slot)

| # | Upstream | fm1 | Criteria | Error dBFS / NCC, lag | Gain dB | Env max dB | Pitch cents | LSD dB | 64-frame host |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | macro Model 0 | exact | −88.5 | 0.0008 | 0.050 | 0.000 | 0.009 | identical |
| 1 | PhaseDistortionEngine | macro Model 1 | exact | −88.5 | 0.0007 | 0.027 | 0.000 | 0.002 | identical |
| 2 | SixOpEngine bank 1 | sixop | close | 0.9993, −36 | 0.0131 | 0.222 | 0.002 | 0.205 | identical |
| 3 | SixOpEngine bank 2 | sixop | close | 0.9937, −38..−35 | 0.1140 | 0.225 | 0.071 | 0.743 | identical |
| 4 | SixOpEngine bank 3 | sixop | close | 0.9957, −37..−36 | 0.0358 | 0.086 | 0.002 | 0.103 | identical |
| 5 | WaveTerrainEngine | macro Model 2 | exact | −88.5 | 0.0008 | 0.040 | 0.000 | 0.003 | identical |
| 6 | StringMachineEngine | macro-heavy Model 0 | exact, L and R | −88.5 | 0.0029 | 0.085 | 0.000 | 0.022 | identical |
| 7 | ChiptuneEngine | macro Model 3 | exact from 10 ms, shared seed | −87.3 | 0.0005 | 0.001 | 0.000 | 0.003 | identical |
| 8 | VirtualAnalogEngine | macro Model 4 | exact | −88.2 | 0.0005 | 0.030 | 0.000 | 0.005 | identical |
| 9 | WaveshapingEngine | macro Model 5 | exact | −88.5 | 0.0006 | 0.037 | 0.000 | 0.002 | identical |
| 10 | FMEngine | macro Model 6 | exact | −88.5 | 0.0006 | 0.029 | 0.000 | 0.001 | identical |
| 11 | GrainEngine | macro-heavy Model 3 | exact | −87.4 | 0.0010 | 0.062 | 0.000 | 0.002 | identical |
| 12 | AdditiveEngine | macro-heavy Model 4 | exact | −88.5 | 0.0032 | 0.118 | 0.000 | 0.010 | identical |
| 13 | WavetableEngine | macro Model 7 | exact | −88.5 | 0.0010 | 0.049 | 0.000 | 0.004 | identical |
| 14 | ChordEngine | macro-heavy Model 1 | exact | −87.8 | 0.0015 | 0.077 | 0.000 | 0.006 | identical |
| 15 | SpeechEngine | macro-heavy Model 2 | exact | −88.5 | 0.0015 | 0.109 | 0.000 | 0.008 | identical |
| 16 | SwarmEngine | macro-heavy Model 5 | exact, shared seed | −88.5 | 0.0012 | 0.045 | – | 0.006 | identical |
| 17 | NoiseEngine | macro-heavy Model 6 | exact, shared seed | −88.5 | 0.0020 | 0.121 | – | 0.014 | identical |
| 18 | ParticleEngine | macro-heavy Model 7 | exact, shared seed | −88.5 | 0.0012 | 0.029 | – | 0.099 | identical |
| 19 | StringEngine | macro-heavy Model 8 | exact, shared seed | −88.5 | 0.0031 | 0.060 | 0.000 | 0.025 | identical |
| 20 | ModalEngine | macro-heavy Model 9 | exact | −88.5 | 0.0007 | 0.033 | 0.003 | 0.110 | identical |
| 21 | BassDrumEngine | macro-heavy Model 10 | exact | −88.5 | 0.0011 | 0.056 | 0.013 | 0.161 | identical |
| 22 | SnareDrumEngine | macro-heavy Model 11 | exact, shared seed | −88.3 | 0.0010 | 0.054 | – | 0.064 | identical |
| 23 | HiHatEngine | macro-heavy Model 12 | exact, shared seed | −88.5 | 0.0015 | 0.087 | – | 0.023 | identical |

Margins [verified]:

- **The error** has 7–9 dB in hand everywhere. Levels, envelopes, spectra and
  release curves are the same to the last rounding step, so the gain
  staging, the post-processors, the LPG, its Decay and Colour, velocity and
  the parameter mappings all match.
- **Six-Op's** margins against its limits: NCC 0.9937 against 0.981, gain
  0.11 dB against 0.35, envelope 0.23 dB against 0.7, pitch 0.071 cents
  against 0.22.
- **Pitch** is "–" for the noise-like slots, which have no pitch.

### Random engines, statistically (the point nearest its limit)

fm1's median distance / the limit, and the candidate's error against the
shared-seed realisation:

| # | Upstream | Level dB | Envelope dB | LSD dB | Centroid cents | Envelope shift cents | Pitch cents | From shared seed, dBFS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | SwarmEngine | 0.57 / 2.35 | 2.2 / 5.5 | 8.9 / 24 | 111 / 456 | 150 / 957 | – | −16.0 |
| 17 | NoiseEngine | 1.45 / 5.2 | 3.8 / 8.0 | 1.33 / 3.9 | 27 / 101 | 6.0 / 58 | – | −27.9 |
| 18 | ParticleEngine | 2.4 / 8.1 | 3.1 / 6.3 | 1.30 / 4.4 | 55 / 923 | 14 / 213 | – | −21.3 |
| 19 | StringEngine | 5.1 / 11.7 | 5.5 / 9.1 | 4.2 / 8.4 | 669 / 2,980 | 0.02 / 5.2 | 0.02 / 0.52 | −34.5 |
| 22 | SnareDrumEngine | 0.42 / 2.1 | 0.28 / 0.82 | 0.88 / 2.55 | 7.2 / 37 | 7.0 / 42 | – | −35.2 |
| 23 | HiHatEngine | 0.40 / 1.0 | 0.46 / 0.67 | 2.1 / 5.7 | 43 / 536 | 1.3 / 14 | – | −47.6 |

Every fm1 median is under 70 % of its limit, and the calibration puts fm1
inside upstream's own spread. Upstream renders of the same note differ
widely where the process is sparse or random in frequency, so some measures
carry little information:

- **Swarm's envelope shift.** It meets the ±150-cent search limit between
  two upstream seeds.
- **Particle's centroid.** At TIMBRE 0.5 the cloud is about 11 grains a
  second, each at a random pitch, so the centroid of 1.5 s moves between
  seeds [inferred; the density is code arithmetic].

### At 44,118 Hz, against upstream resampled the same way

fm1-render at 44,118 Hz in 64-frame blocks against `fm1-ref-plaits
--host-rate 44118`, the six native-rate cases per slot, in 16-bit LSB of
fm1-render's output (the string machine on both channels; Chiptune from
10 ms to the note-off). Six-Op: the close measures, worst of the six
[verified: `--report`]:

| # | Upstream | Largest difference | RMS | Samples differing |
| --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | 0 LSB | 0 | 0 of 158,820 |
| 1 | PhaseDistortionEngine | 0 | 0 | 0 of 158,820 |
| 2 | SixOpEngine bank 1 | NCC 0.9943, lag −33 | gain 0.043 dB, envelope 0.320 dB | pitch 0.015 cents, LSD 0.264 dB |
| 3 | SixOpEngine bank 2 | NCC 0.9924, lag −35..−32 | gain 0.116 dB, envelope 0.310 dB | pitch 0.076 cents, LSD 0.867 dB |
| 4 | SixOpEngine bank 3 | NCC 0.9885, lag −34..−33 | gain 0.097 dB, envelope 0.127 dB | pitch 0.003 cents, LSD 0.140 dB |
| 5 | WaveTerrainEngine | 0 | 0 | 0 of 158,820 |
| 6 | StringMachineEngine | 0 | 0 | 0 of 317,640 |
| 7 | ChiptuneEngine | 1 | 0.034 | 23 of 76,962 |
| 8 | VirtualAnalogEngine | 0 | 0 | 0 of 158,820 |
| 9 | WaveshapingEngine | 0 | 0 | 0 of 158,820 |
| 10 | FMEngine | 0 | 0 | 0 of 158,820 |
| 11 | GrainEngine | 0 | 0 | 0 of 158,820 |
| 12 | AdditiveEngine | 0 | 0 | 0 of 158,820 |
| 13 | WavetableEngine | 0 | 0 | 0 of 158,820 |
| 14 | ChordEngine | 0 | 0 | 0 of 158,820 |
| 15 | SpeechEngine | 0 | 0 | 0 of 158,820 |
| 16 | SwarmEngine | 0 | 0 | 0 of 158,820 |
| 17 | NoiseEngine | 0 | 0 | 0 of 158,820 |
| 18 | ParticleEngine | 0 | 0 | 0 of 158,820 |
| 19 | StringEngine | 0 | 0 | 0 of 158,820 |
| 20 | ModalEngine | 0 | 0 | 0 of 158,820 |
| 21 | BassDrumEngine | 0 | 0 | 0 of 158,820 |
| 22 | SnareDrumEngine | 0 | 0 | 0 of 158,820 |
| 23 | HiHatEngine | 0 | 0 | 0 of 158,820 |

Measured on macOS arm64 (Apple clang 21), where both programs make the same
floating-point choices; the limit allows one LSB elsewhere ("Criteria").

### At 44,118 Hz, against upstream at its own rate (A2 / A4)

fm1 at 44,118 Hz less the resampler's 30-sample delay, against the native
reference unresampled, at the rate points [verified: `--report`]:

| # | Upstream | Pitch cents | Stretch (method) | Level dB | LSD dB |
| --- | --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.04 / 0.01 |
| 1 | PhaseDistortionEngine | −0.000 / +0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 2 | SixOpEngine bank 1 | −0.001 / +0.001 | 1.001 / 1.001 (slope) | +0.003 / +0.000 | 0.15 / 0.17 |
| 3 | SixOpEngine bank 2 | −0.001 / +0.007 | 1.000 / 0.999 (slope) | +0.003 / +0.000 | 0.07 / 0.05 |
| 4 | SixOpEngine bank 3 | −0.001 / −0.000 | 1.001 / 1.000 (slope) | +0.004 / +0.004 | 0.08 / 0.01 |
| 5 | WaveTerrainEngine | +0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 6 | StringMachineEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.03 / 0.01 |
| 7 | ChiptuneEngine | +0.001 / −0.001 | not held (its LPG) | −0.010 / −0.016 | 0.00 / 0.00 |
| 8 | VirtualAnalogEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 9 | WaveshapingEngine | +0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 10 | FMEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.04 / 0.01 |
| 11 | GrainEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 12 | AdditiveEngine | −0.000 / +0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.00 / 0.00 |
| 13 | WavetableEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.05 / 0.01 |
| 14 | ChordEngine | +0.000 / +0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.01 / 0.00 |
| 15 | SpeechEngine | +0.000 / +0.000 | 1.000 / 1.000 (fit) | −0.001 / −0.001 | 0.04 / 0.01 |
| 16 | SwarmEngine | +0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.04 / 0.00 |
| 17 | NoiseEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.03 / 0.03 |
| 18 | ParticleEngine | +0.005 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.07 / 0.04 |
| 19 | StringEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.17 / 0.00 |
| 20 | ModalEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.16 / 0.00 |
| 21 | BassDrumEngine | −0.000 / +0.000 | 1.000 / 1.000 (fit) | −0.000 / −0.000 | 0.04 / 0.02 |
| 22 | SnareDrumEngine | +0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.003 / −0.011 | 0.08 / 0.02 |
| 23 | HiHatEngine | −0.000 / −0.000 | 1.000 / 1.000 (fit) | −0.013 / −0.015 | 0.03 / 0.03 |

What the tables show [verified unless marked]:

- **The same sound, delayed and band-limited.** Pitch, envelope timing and
  level agree with upstream at its own rate to the measurement's
  resolution on every slot. The LSD that is left (up to 0.17 dB) is the
  resampler's band limit: flat to 18 kHz, a roll-off from there to the
  Nyquist, where upstream at 47,872.34 Hz keeps its content to 23.9 kHz
  [inferred: resampler.md's measured response]. The levels of Snare and
  Hi-Hat, −0.003 to −0.015 dB, are the same: their energy reaches highest.
- **Without the alignment** (fm1 not cropped by the group delay, the
  reference's note-off where the native tests put it), the bass drum at A2
  reads 0.10 cents and the others within 0.035: the 0.68 ms delay shifts the
  analysed segment along the drum's pitch sweep [verified: a first run of
  the same comparison; inferred mechanism]. The alignment takes that out.
- **Random slots, Chords and the string** compare like the others now: both
  sides draw the same random numbers at the same rate on the shared seed,
  and the chord's beating is in the same phase.
- **The noise engine's clock** follows: `test_noise_clock_follows_the_rate`,
  the strict xfail of finding 2, passes. Its spectral-envelope shift, the
  median against five seeded upstream renders, is −2.3 and −0.1 cents at A2
  and A4 (was −139 and −140); with the clock at the top of its range
  (TIMBRE 1), −7.3 and +1.9 (was +7 and 0). Both are held within 20 cents:
  these are other random realisations than fm1's, so a few cents is their
  spread [verified: the two tests' measure, printed].

### Before 2026-10-01: Plaits at the host's rate

Until 2026-10-01 the wrappers ran Plaits at the host's rate with the pitch
raised by 12·log2(47,872.34 / rate) semitones, and the tests held what the
code predicted for that. The prediction (`rate_expected`,
`string_stretch_cents`, `test_rate_prediction_arithmetic`) went with the
change; the parent commit, 2bf4133, has it. The table as it then was
(A2 / A4), fm1 at 44,118 Hz against the native reference unresampled, with
the LEVEL then rounded to six decimals and no alignment:

| # | Upstream | Pitch cents (predicted) | Stretch (method, range) | Level dB | LSD dB |
| --- | --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | −0.46 / −0.43 (−0.37) | 1.083 / 1.079 (fit, 1.065–1.105) | +0.05 / +0.03 | 0.24 / 0.16 |
| 1 | PhaseDistortionEngine | −0.39 / −0.34 (−0.37) | 1.081 / 1.085 (fit) | +0.03 / −0.07 | 0.49 / 0.49 |
| 2 | SixOpEngine bank 1 | +0.00 / +0.00 (0) | 1.001 / 1.000 (slope, 0.98–1.02) | +0.02 / +0.02 | 0.73 / 1.78 |
| 3 | SixOpEngine bank 2 | +0.00 / +0.01 (0) | 1.000 / 1.001 (slope) | +0.01 / +0.02 | 0.11 / 0.06 |
| 4 | SixOpEngine bank 3 | −0.00 / −0.00 (0) | 1.001 / 1.001 (slope) | +0.02 / +0.02 | 0.09 / 0.02 |
| 5 | WaveTerrainEngine | −0.42 / −0.37 (−0.37) | 1.083 / 1.083 (fit) | +0.04 / −0.02 | 0.59 / 0.49 |
| 6 | StringMachineEngine | −0.40 / −0.36 (−0.37) | 1.085 / 1.081 (fit) | +0.01 / −0.10 | 0.55 / 0.51 |
| 7 | ChiptuneEngine | −0.35 / −0.33 (−0.37) | not held (the LPG differs) | −0.02 / −0.12 | 1.20 / 2.61 |
| 8 | VirtualAnalogEngine | −0.45 / −0.42 (−0.37) | 1.080 / 1.079 (fit) | +0.05 / +0.03 | 0.65 / 0.58 |
| 9 | WaveshapingEngine | −0.40 / −0.37 (−0.37) | 1.081 / 1.081 (fit) | +0.03 / +0.06 | 0.40 / 2.09 |
| 10 | FMEngine | −0.48 / −0.43 (−0.37) | 1.082 / 1.081 (fit) | +0.05 / +0.03 | 0.16 / 0.11 |
| 11 | GrainEngine | −0.43 / −0.43 (−0.37) | 1.078 / 1.079 (fit) | +0.07 / −0.35 | 1.32 / 0.45 |
| 12 | AdditiveEngine | −0.36 / −0.33 (−0.37) | 1.073 / 1.084 (fit) | −0.05 / −0.53 | 0.28 / 0.10 |
| 13 | WavetableEngine | −0.40 / −0.37 (−0.37) | 1.079 / 1.079 (fit) | +0.04 / −0.05 | 0.40 / 0.50 |
| 14 | ChordEngine | −0.41 / −0.38 (−0.37) | not held (1.002 / 1.022) | +0.19 / +0.08 | 0.98 / 0.89 |
| 15 | SpeechEngine (words) | −0.18 / −0.16 (−0.37) | 1.080 / 1.091 (fit) | +0.84 / +0.05 | 3.20 / 4.34 |
| 16 | SwarmEngine | not held (−4.2 / −3.9) | not held | +0.47 / +0.52 | 2.02 / 1.45 |
| 17 | NoiseEngine | not held (−137 / −142) | not held | −1.22 / −4.59 | 3.08 / 4.98 |
| 18 | ParticleEngine | not held (−141 / −141) | not held | +0.05 / +0.11 | 1.21 / 1.69 |
| 19 | StringEngine | −9.51 / +0.33 (−9.06 / −0.37) | not held (1.006 / 1.270) | −0.18 / +1.18 | 1.59 / 1.31 |
| 20 | ModalEngine | −0.38 / −0.37 (−0.37) | 1.002 / 1.052 (fit, 0.98–1.105) | +0.42 / +0.47 | 0.59 / 0.58 |
| 21 | BassDrumEngine | −0.12 / +0.13 (−0.37) | 1.083 / 1.083 (fit) | −0.07 / +1.21 | 0.36 / 0.31 |
| 22 | SnareDrumEngine | −0.23 / −0.37 (−0.37) | 1.084 / 1.092 (fit) | +0.74 / +0.71 | 1.29 / 0.67 |
| 23 | HiHatEngine | −0.37 / −0.35 (−0.37) | 1.085 / 1.081 (fit) | −0.01 / +0.45 | 1.63 / 1.71 |

What that table showed [verified unless marked, at the time]:

- **The flat third of a cent** on the Plaits engines is Plaits' own pitch
  table. `stmlib::SemitonesToRatio` truncates the fractional semitone to
  1/256. The rate offset of +1.41390 semitones leaves a fraction of 0.414,
  read as 105/256: 0.374 cents flat [verified: `stmlib/dsp/units.h` and
  arithmetic, `test_rate_prediction_arithmetic`]. The measured −0.33 to
  −0.48 cents on the tonal engines is that, plus the measurement's own
  error. Speech words (−0.17) and the bass drum (−0.12 / +0.13) sit up to
  0.5 cents above it; both change over the note (phonemes, the drum's pitch
  sweep), and their timing runs 8.5 % slower [inferred]. Six-Op computes
  its own frequencies and shows none.
- **The string model** is 9.5 cents flat at A2 against upstream at its own
  rate, and +0.33 at A4. The A2 figure is its own rate dependence
  (finding 4): the code predicts −8.69 cents, −9.06 with the pitch table.
  Upstream renders with three other seeds give −9.47 to −9.62 against the
  same fm1 render, so it is not the excitation noise [verified]. Why A4
  reads 0.7 cents above the prediction was not traced.
- **Envelopes** set per sample or per 12-sample block run 1.073–1.092 times
  long. The rate ratio is 1.085, as UPSTREAM.md and `mi_macro.cc` state.
  - Modal's resonators decay by Q, a number of periods, which does not change
    with the rate: 1.00–1.05 [inferred mechanism, verified figures].
  - Six-Op's FMVoice runs at the host rate: 1.000–1.001. Over the 38 patches
    whose release runs at 30–400 dB/s at both notes, 0.976–1.016
    [verified: `--sixop-sweep`].
- **Not held, and why:**
  - **Chiptune's timing:** the fm1 note has an LPG, the upstream one none.
  - **Chords:** its held level beats by about ±1 dB with a period near 0.3 s,
    in a different phase at each rate, which no time stretch follows. The
    beat comes from the engine's own wavetable layer, detuned 0.4 % against
    its divide-down layer (`note_f0 * 1.004f`) [verified: code, envelope
    listing]. Why the phase differs was not traced.
  - **String timing:** its random excitation shapes the decay. Stretches
    between upstream seeds alone span the whole 0.8–1.3 search range.
  - **Swarm and Particle:** one render per rate cannot show a random
    process's timing.
  - **Particle's pitch column (−141 cents)** is not a pitch error. Both
    renders draw the same grains from the shared seed, and at 44,118 Hz the
    whole grain pattern plays 8.5 % slower, which the spectral correlation
    reads as a shift [verified: pitch correlation 0.994 at −140.6 cents;
    under 0.001 cents at the native rate].
  - **Noise:** finding 2.
- **Level and LSD** at 44,118 Hz are reported, not held.
  - Level: the LPG and every per-sample filter sit 8.5 % lower in frequency
    (finding 3).
  - LSD: Speech and Noise are 3–5 dB. Speech words play 8.5 % slower, so the
    analysed segment holds other phonemes [inferred]; for Noise see
    finding 2.


### Six-Op, across all 96 patches

The 18 cases above sit well inside the Six-Op limits. The whole bank set
spreads much wider. The sweep: 96 patches × 2 notes × 3 (TIMBRE, MORPH)
pairs, (0.5, 0.5), (0.8, 0.2) and (0.2, 0.8), at velocity 100: 576 cases
[verified: `--sixop-sweep`].

Beside fm1 against upstream are three yardsticks: upstream against itself
with one timing detail moved.

| | fm1 against upstream | Upstream, note one block later | Upstream, note one chunk (24 samples) later | Upstream, note-off one block later |
| --- | --- | --- | --- | --- |
| Residual (1 − NCC²), median / worst | −32.6 / −0.6 dB | identical / −8.0 dB | −49.5 / −25.3 dB | identical |
| Envelope, median / worst | 0.13 / 4.2 dB | 0 / 1.8 dB | 0 / 5.3 dB | 0 |
| Pitch, median / worst | 0.003 / 31 cents | 0 / 0.55 cents | 0.001 / 19 cents | 0 |
| Gain, median / worst | 0.006 / 9.0 dB | 0 / 0.84 dB | 0.0001 / 0.05 dB | 0 |
| Identical (error under −100 dBFS) | 0 of 576 | 388 of 576 | 180 of 576 | 576 of 576 |

What the yardsticks show [verified: `--sixop-sweep`]:

- **Upstream's onsets are quantised to 24-sample chunks.** `SixOpEngine`
  renders one of its two voices per call, for two blocks
  (`voice_[rendered_voice_].Render(temp_buffer_, size * kNumSixOpVoices)`,
  `kNumSixOpVoices` = 2) [verified: code]. So a note one block later mostly
  sounds on the same sample: 388 of 576 cases are byte-identical. A
  note-off one block later, from block 1,200 to 1,201, changes nothing.
- **Moving the note a whole chunk** moves the onset by 24 samples, which
  the comparison's best lag takes out. What remains is −49.5 dB median, 180
  cases still identical: free-running operator phases and the LFO meet the
  note at another point [inferred].
- **Correction.** An earlier version of this file used "note one block
  later" as the only yardstick, with the note-off at 0.3 s (block 1,197).
  Its −49.9 dB median came mostly from the note-off moving into the next
  chunk: moving the note-off alone, from block 1,197 to 1,198, gives
  −54.3 dB [verified: scratch check at the old note-off; the sweep mode
  reproduces the other columns]. With the note-off on block 1,200 the
  note-on move alone leaves 388 of 576 cases identical.

The fm1 render sits further from upstream than upstream sits from itself a
chunk later. The worst cases are all at Envelope 0.2 and A4: `B.DRM-SNAR`
(residual −0.6 dB, gain −9.0 dB), then `INSERT 1`, `CLAV    3`,
`*Vocoder 2` and `BR TRUMPET` (residual −4.3 to −4.9 dB, gain −1.8 to
−2.0 dB). Two intentional differences account for the spread:

1. **Envelope block size.** The wrapper steps envelopes and the LFO every 16
   samples. Upstream steps them every 24 samples per voice, staggered.
   - A scratch build of Six-Op with 24-sample blocks (`kBlock = 24` in a copy
     of `mi_sixop.cc`, run with `--sixop-sweep --render`) moves the key-sync
     patches' median residual from −34.1 to −48.0 dB. Upstream a chunk later
     is −57.3 dB for the same patches [verified: scratch build, not in the
     repo; the harness is].
   - At Envelope 0.2, attack and decay rates run 5.3 times faster
     (`ad_scale = 2^((0.5 − 0.2) × 8)`) [verified: `plaits/dsp/fm/voice.h`],
     and the block size shows most.
2. **The note-on renders.** The wrapper renders one sample with the gate low
   before every note (plaits-heavy.md, "Note-on"). That moves the
   free-running operator phases on by a sample.
   - Patches with oscillator key sync reset their phases at the note-on, so
     they are unaffected.
   - The 174 cases without key sync keep a −29 dB median residual at either
     block size (−29.3 at 16, −29.7 at 24), against −41.6 dB for upstream a
     chunk later [verified: `--sixop-sweep`, and the same scratch build].
   - plaits-heavy.md measured this as windowed RMS within 0.04 dB.

The upstream staggering also puts the first sound 36 samples after the
trigger: the new voice's first 24-sample chunk comes one block after the
trigger and is spent in `Setup()` [inferred: code; the measured lag is 35–38
samples in the 18 cases, and onsets are chunk-quantised, above]. The wrapper
sounds from the note-on. Its phases then follow the free-running history,
which on a DX7 without key sync is arbitrary anyway [inferred].

### What the criteria reject

The negative controls are tests too, at point 2 with Decay 0.5, Colour 0.5
and velocity 100, at A3 [verified: `--report`]. Each fails on the measures
listed:

| Control | Fails on |
| --- | --- |
| VA Pair rendered as Shaper | error −7.5 dBFS, gain −13.6 dB, LSD 11.5 dB |
| Additive rendered as Swarm (next Macro Heavy model) | error −17 dBFS, gain −42 dB, envelope 39 dB, LSD 28 dB |
| Timbre and Morph swapped | error −10 dBFS, gain −39 dB, LSD 12.8 dB |
| Reference 1 cent sharp | error −25 dBFS, pitch −0.78 cents |
| Decay 0.55 for 0.5 | error −36 dBFS, envelope 1.9 dB |
| Colour 0.55 for 0.5 | error −45 dBFS |
| Volume 0.99 | error −56 dBFS, gain −0.09 dB |
| Six-Op, the next patch | NCC 0.009, pitch, envelope 57 dB |
| Six-Op, Envelope 0.25 for 0.2 | NCC 0.970, gain +1.3 dB, envelope 17 dB |
| Six-Op, Brightness 0.45 for 0.5 (`BASS    1`) | NCC 0.950, gain −0.8 dB, envelope 1.05 dB |
| Six-Op, Brightness and Envelope swapped | NCC 0.32, envelope 62 dB |
| Six-Op, reference 2 cents sharp | pitch −1.98 cents |
| Noise, a semitone sharp (statistical) | 4 of 30 point-measures: centroid, envelope shift |
| String, a semitone sharp (statistical) | 17 of 36: centroid, LSD, pitch, envelope shift |
| Particle, an octave sharp (statistical) | 7 of 20: centroid, LSD |
| Swarm rendered as Noise (statistical) | 17 of 30 |
| Hi-Hat rendered as Snare (statistical) | 28 of 30 |
| Silence, and white noise at the candidate's level (statistical) | every point |
| At 44,118 Hz: fm1 at 44,100 Hz against the reference resampled to 44,118 Hz (a ratio 0.04 % off), compared sample for sample | 4,260 LSB, 26,379 of 26,460 samples differ; lengths differ |
| At 44,118 Hz: Volume 0.99 | 65 LSB, 26,224 of 26,470 |
| At 44,118 Hz: the reference's note-off in 7-frame host blocks against fm1's 64 (it lands 4 blocks earlier) | 96 LSB, 12,491 of 26,470 |
| At 44,118 Hz: Noise a semitone sharp (shared seed) | 1,408 LSB, 26,388 of 26,470 |

The wrapper mutations a review ran against these tests are listed under
"Review" below.

Where the criteria stop [verified: `--report`]:

- **Six-Op, Brightness.** How small a Brightness error the close criteria see
  depends on the patch. At the 9 test points (A3), a 0.05 error fails on 5,
  a 0.1 or a 0.2 error on 6.
  - `ENTRIX` does not respond to Brightness at all, and `PIPES   3` barely
    (NCC 0.9999 with 0.2 less).
  - On `XYLOPHONE` at Envelope 0.2, the patch's own intentional differences
    (NCC 0.9919) are about as large as what 0.2 of Brightness adds
    (0.9853).
- **Particle, a semitone.** The statistical comparison cannot see a Particle
  cloud a semitone sharp in 1.5 s (0 of 20 point-measures): each grain is
  scattered randomly around the note. The shared-seed sample-exact test
  does see it.

### Review

A review of this stream mutated the wrappers and the vendored code in a
scratch copy, one change at a time, and ran this file against each: wrong
models, gains, polarity, velocity curves, LPG and rate handling, parameter
swaps, re-blocking errors and Six-Op patch, LFO and block changes
[verified: scratch harness, not in the repo]. Before the fixes above, 8 of
51 changes survived. Afterwards 50 of 51 fail at least one test; the tests
now catch these:

| Change | Caught now by |
| --- | --- |
| Macro and Macro Heavy re-blocking: each host block restarts at the 12-sample block's start | the 64-frame test |
| Macro re-blocking: a one-sample glitch at each partial copy | the 64-frame test |
| Macro and Macro Heavy: the LPG's release tail ignores Colour | the exact test (Colour now varies) |
| Macro Heavy: the LPG filter's Colour fixed at 0.5 | the exact test |
| Macro and Macro Heavy rate offset 3 % too large (+3.8 cents at 44,118 Hz) | the rate pitch test (±1 cent) |
| A vendored DSP constant changed (`VirtualAnalogEngine`'s 7.01 interval) | the pin test |

One change still survives: Six-Op's envelope and LFO block of 32 samples
instead of 16. At the 18 test points it stays inside the close criteria,
which allow for the 16-against-24 difference by design; the sweep's
key-sync residual is where a block size shows (Six-Op, above).

**The native-rate change (2026-10-01).** Seventeen scratch mutants of the
three wrappers, one change each, built and run against this file,
`test_engines_plaits_heavy.py`, `test_engines.py` and `test_engine_host.py`
(459 tests) [verified: scratch harness, not in the repo]. 16 fail:

| Change | Fails |
| --- | --- |
| Macro's resampler told 48 kHz in | 29 tests: exact at both rates, pitch, refusals |
| Macro's resampler told a rate 0.03 % high | 28: the same |
| Macro without a resampler (native samples straight out) | 27: resampled comparison, pitch, timing, tuning |
| Macro decimating by dropping samples, unfiltered | 9: resampled comparison, note timing |
| Macro with the old pitch offset left in | 29: exact at both rates, pitch, tuning |
| Macro Heavy's resampler told 48 kHz in | 49 |
| Macro Heavy with the old pitch offset left in | 70 |
| Macro Heavy without resamplers | 60: resampled comparison, pitch, timing, the noise clock |
| Macro Heavy's right resampler not copied on entering the string machine | 2: `test_string_machine_entered_later_renders_as_if_created_in_it` |
| Macro Heavy's right resampler fed the left mix | 5: the string machine's AUX at both rates, stereo, model change |
| Six-Op's FMVoice at the host's rate, resampled | 15: resampled comparison, pitch, timing, tuning |
| Six-Op without a resampler | 15: the same |
| Six-Op decimating by dropping samples | 3: resampled comparison |
| A resampler per voice, by size (Macro, Macro Heavy, Six-Op: unused arrays of them; resampling is linear, so the renders could not tell) | 1 each: the instance-size bounds |

The survivor: Macro Heavy's silent-voice timers counted at the host's
rate rather than Plaits'. They only decide when a voice already below
−80 dBFS is freed (plaits-heavy.md, "Limits").

## Intentional differences

Each is by design in a wrapper. Each is either measured here or accounted
for in the comparison.

1. **Gain staging.** Each fm1 voice is Volume × 0.25 of the DAC word; the
   Six-Op mix is Volume × 0.25 of `SoftClip(x × 0.25)`. Accounted for as the
   expected gain.
   - fm1-render's second 16-bit rounding is the −88.6 dBFS residual
     [verified].
   - At one voice the bus limiter does not act: the fm1 peak is at most a
     quarter of full scale, −12 dBFS, against the limiter's 0.98 [verified:
     sample-exact results].
2. **Velocity → level.** The wrappers compress velocity/127 exactly as
   `Voice` compresses LEVEL [verified: code, sample-exact results at
   velocities 60, 100 and 120].
   - Macro Heavy holds the note's accent after note-off, where upstream's
     accent follows LEVEL on every block. That matters only for speech words
     (item 8).
3. **Stereo.** Macro, Macro Heavy and Six-Op put OUT on both channels, except
   the string machine, whose OUT and AUX are its L and R. Compared on both
   channels [verified]. The other slots' AUX signals are not used by the
   wrappers and not compared.
4. **An engine instance per voice.** Each note on a free voice starts from a
   freshly reset engine and LPG. On the module, `Reset()` runs only when the
   engine changes. The aligned reference selects the engine at the note, so
   the two coincide.
5. **Trigger timing.** The wrappers trigger on the note-on block; `Voice`
   48 samples later. Accounted for by the aligned reference [verified].
6. **Shared speech word bank.** Output identical for held parameters
   (plaits-heavy.md). Speech is sample-exact at all six points here: phonemes
   at HARMONICS 0.2, and two word banks at 0.5 and 0.8 [verified].
7. **Chiptune keeps the LPG.** Upstream, the clocked chiptune reports itself
   enveloped (`*already_enveloped = clocked`), so `Voice` bypasses the LPG.
   Its own envelope then follows the TIMBRE attenuverter; at 0 the note holds
   at full level until the next trigger.
   - Macro sets `NO_ENVELOPE` and runs every model through the LPG, so
     velocity, Decay and Colour shape the chip note, and key-up releases it
     [verified: code, `test_chiptune_keeps_the_low_pass_gate`].
   - Compared with Colour 1 (no LPG filter) and velocity 127 (gain settles to
     1), from 10 ms to the note-off, at both rates.
   - Not described before this stream.
8. **Added release for the self-enveloped models.** (plaits-heavy.md.) The
   comparison holds these notes. What upstream does after LEVEL falls
   [verified: `test_added_release_after_note_off`]:
   - **Drums and strings** read the accent at the trigger and ring on.
   - **Speech words** use the accent as the word's gain on every block, so
     the word stops at once. plaits-heavy.md says "the module has no
     note-off"; with LEVEL patched, a word's is immediate.
9. **Six-Op.** Described under "Six-Op, across all 96 patches":
   - the patch transpose Plaits ignores [verified:
     `test_sixop_applies_the_patch_transpose_plaits_ignores`];
   - 16-sample blocks;
   - one-sample note-on renders;
   - no staggering (a 36-sample lead);
   - its own LFO stepping.
10. **Rate.** Since 2026-10-01 the wrappers run Plaits at its own
    47,872.34 Hz on any host and resample the mix (plaits-heavy.md, "Rate"),
    so no time constant or frequency differs from upstream's. What differs
    is what the resampler adds: a band limit (flat to 18 kHz, a roll-off
    to the host's Nyquist) and its delay, 0.76–1.01 ms from a note to the
    centre of its onset at 44,118 Hz (0.76–1.09 ms for Six-Op), where it was
    0–0.25 ms (0–0.34 ms) [verified: the pull arithmetic, checked against a
    render]. Both are measured above and in plaits-heavy.md. Until then the
    wrappers corrected pitch only and left every time constant and fixed
    frequency per sample (UPSTREAM.md); the consequences are kept above as
    history.

## Findings

1. **Polarity differs between the engines.** `Voice`'s post-processor writes
   the DAC word as `−32767 × x`. The module's inverting output stage
   presumably turns it back [inferred from the sign].
   - Macro and Macro Heavy pass those inverted words on, so their output is
     the engine signal inverted.
   - Six-Op mixes `SoftClip()` output directly, so its output is not
     inverted.
   - So a note from Six-Op and the same waveform from Macro would be opposite
     in polarity [verified: least-squares gain +0.25 against −0.25 in every
     case].
   - This is inaudible for one engine. It matters only if two engines are
     ever mixed or crossfaded.
   - Not changed here: which sign is right depends on the output stage,
     which is not verified. Suggested fix: negate `voice_gain` in
     `mi_macro.cc` and `mi_macro_heavy.cc`, so all three are the engine
     signal.
2. **TIMBRE-derived frequencies escape the rate compensation.**
   - `NoiseEngine`'s clock is `NoteToFrequency(timbre × 152 − 24)`, which
     does not depend on the note. The wrappers' pitch offset therefore does
     not reach it, and at 44,118 Hz the clock runs 1.41 semitones low.
   - Measured: with TIMBRE 0.5 the spectral envelope shifts by −139 and −140
     cents at A2 and A4. With TIMBRE 1, where the note-tracking filter shapes
     the spectrum, it shifts by +7 and 0 cents.
   - [verified: `test_noise_clock_follows_the_rate`, a strict xfail that
     passes when the clock is fixed; `test_noise_filter_follows_the_rate`
     passes.]
   - The same holds, by code, for `ParticleEngine`'s grain density
     (`NoteToFrequency(60 + timbre² × 72)`) and `SwarmEngine`'s
     (`NoteToFrequency(timbre × 120)`). Both run 8.5 % sparse at 44,118 Hz
     [inferred: code; one render per rate cannot measure a density].
   - Suggested fix, per model in `mi_macro_heavy.cc`: raise TIMBRE by the
     offset's share of the mapping, so that its note rises by the rate
     offset. For Noise that is + offset/152. For Swarm it is + offset/120. For
     Particle it is T' = √(T² + offset/144), because the density goes with
     the square of `NoteToFrequency`. Each loses the top ~1 % of its range to
     clamping.
   - Not done: it changes what the knob does, and should be decided with the
     other uncompensated rates (findings 3 and 4).
   - **Resolved 2026-10-01** by running Plaits at its own rate: the clock is
     upstream's at any host rate (−2.3 and −0.1 cents at A2 and A4, the
     xfail now an ordinary test), and Particle and Swarm, compared sample
     for sample at 44,118 Hz through the resampler, are upstream's, densities
     included [verified: "At 44,118 Hz", above].
3. **The LPG's filter is not rate-compensated either.**
   `LPGEnvelope::frequency()` is a per-sample frequency, so the gate's
   low-pass sits 1.41 semitones lower at 44,118 Hz [inferred: code]. It is a
   likely part of the 44,118 Hz LSD and level differences on the LPG models
   (0.05–2.1 dB) [inferred]. The same is true of every fixed per-sample
   filter or delay inside the engines, which the wrappers cannot reach
   without changing vendored code.
   - **Resolved 2026-10-01** with finding 2: the gate and every per-sample
     filter now run at upstream's rate; level at 44,118 Hz is within
     0.02 dB of upstream at its own rate on every slot, and the 20 LPG and
     self-enveloped slots compare sample for sample through the resampler
     [verified: "At 44,118 Hz", above].
4. **The string model's tuning depends on the rate at low notes.**
   - **Where:** with dispersion (HARMONICS above 0.26),
     `String::ProcessInternal` shortens its main delay by
     `ap_delay × (0.408 − 0.308 × stretch_point) × stretch_correction` to
     make up for the dispersion all-pass. `stretch_correction =
     (160 / kSampleRate) × delay`, clamped to [1, 2.1], is a function of the
     loop's length in samples (`string.cc:126`) [verified: code].
   - **Effect:** at 44,118 Hz the same pitch is a loop 1.085 times shorter.
     Below about 160 Hz (a loop over 300 samples at the native rate) the
     correction comes out smaller, the loop longer and the note flat. At A2
     with HARMONICS 0.5 the arithmetic gives −8.69 cents, and with the
     pitch table −9.06; measured −9.5 against upstream at its own rate, for
     every seed [verified: `string_stretch_cents` in the test,
     `test_rate_compensation_holds_pitch`]. At A4 the correction is clamped
     at 1 at both rates [verified: arithmetic].
   - This is a rate effect, so it corrects plaits-heavy.md item 9, which
     says the string's tuning error is "not the rate change". That holds
     for item 9's own conditions (structure 0.25, where there is no
     dispersion, and A3 and up), not in general.
   - Not changed: only the wrapper could compensate it, by raising the note
     by the predicted amount per note and HARMONICS. An owner decision, with
     findings 2 and 3.
   - **Resolved 2026-10-01** with findings 2 and 3: at 44,118 Hz the string
     at A2 reads 0.000 cents against upstream at its own rate, and is
     upstream's sample for sample through the resampler [verified: "At
     44,118 Hz", above]. (`string_stretch_cents` and the pitch test cited
     above were removed with the change.)
5. **Documentation.**
   - plaits-heavy.md's "the module has no note-off" does not hold for speech
     words with LEVEL patched (intentional difference 8).
   - plaits-heavy.md item 9 (finding 4).
   - UPSTREAM.md's "Envelope times scale by the same ratio" holds for the LPG, the
     drums and speech. It does not hold for Six-Op (exact) or Modal
     (1.00–1.05). The string's decay depends on its random excitation.
     Since 2026-10-01 it holds for none of the Plaits wrappers: their
     envelope times are upstream's at any host rate.
   - Chiptune's LPG (intentional difference 7) was not described.
   - These go in files outside this stream (requests below).
6. **Nothing else differs at Plaits' own rate.** Every mapping, gain, LPG,
   post-processor and envelope in Macro and Macro Heavy is sample-exact
   against `Voice`, at three Decay, Colour and velocity settings, and in
   12- and 64-frame host blocks. So are the random engines on the shared
   seed: no wrapper draws from `stmlib::Random` where `Voice` does not
   [verified].

## Limits of this comparison

- **The engine DSP is shared object code** ("What the comparison covers").
  The render comparison cannot see a change to it; the pin test can.
- **One note, fixed parameters.** Not covered: parameter changes during a
  note, pitch bend, retriggers, and several voices at once (voice stealing,
  Six-Op's shared LFO, the speech voices' shared bank under a Harmonics
  move). A timed-parameter host feature would allow them
  (plaits-heavy.md's requests).
- **Idealised inputs.** The module's UI and CV reader (`ui.cc`,
  `cv_reader.cc`: pot smoothing, CV calibration, V/OCT scaling) are not
  vendored and not modelled. The reference feeds `Voice` exact values.
- **Parameters left at their defaults.** Word Speed (0) and Macro Heavy's
  prosody (0) are compared at those values only. Velocity 127 is compared
  on Chiptune only (Method).
- **32-bit and other compilers.** Measured on arm64 macOS (Apple clang 21)
  and under ASan+UBSan. The CI 32-bit and Linux jobs run this file through
  `tests/test_engine*.py`, not run locally. The shared-seed exact matches,
  and the identical samples at 44,118 Hz, rely on the same floating-point
  results in both programs on one platform, not across platforms; the
  44,118 Hz limit leaves one LSB for a compiler that rounds the resampler's
  arithmetic differently in the two. The pin test hashes file contents, so
  it does not depend on the platform.
- **The resampler is the same code on both sides.** The 44,118 Hz
  comparison checks that the wrappers feed it the right samples at the
  right time and at the right ratio, not the resampler itself;
  resampler.md and `tests/test_engines_resampler.py` measure that. The
  comparison with upstream unresampled (pitch, timing) is the guard
  against a ratio both sides would share.
- **A resampler per voice** renders the same samples as one per channel
  (resampling is linear), so no render comparison can see it; the instance
  size bounds do (plaits-heavy.md, "Tests") [verified: scratch mutants,
  "Review"].

## Requests outside this stream's files

1. **engines/README.md**, **docs/11 §8** and **third_party/mutable/UPSTREAM.md**:
   link this file.
   - For the Plaits-derived engines, the exit test's render comparison is
     met for the wrapper layer: sample for sample at Plaits' rate (Six-Op
     closely), in 12- and 64-frame host blocks, and at the FM-1's 44,118 Hz
     against upstream resampled the same way (20 of 21 slots identical,
     Chiptune within 1 LSB, Six-Op closely), with pitch, envelope timing and
     level equal to upstream at its own rate. The engine DSP is the same
     object code on both sides, pinned by hash to the upstream files.
   - Record finding 1 with it; findings 2–4 are resolved by running Plaits
     at its own rate (2026-10-01).
   - Correct "envelope times scale by the same ratio" (finding 5): for the
     Plaits wrappers it no longer applies at all.
   - README's exit-test paragraph ("At the FM-1's 44,118 Hz only pitch is
     corrected ... Plaits' envelopes run 8.5 % long ... a strict xfail ...
     −9.5 cents at A2") and its open question "Plaits at the FM-1 rate"
     (per-model TIMBRE offsets) describe the old behaviour; both are settled.
     Its instance-size table: Macro 31,728 / 18,864 B, Macro Heavy 71,088 /
     70,880 B, Six-Op 12,528 / 10,796 B (64-bit / 32-bit). Its cost table:
     Macro 1.1–2.2 % (2-op FM 5.5 %), Macro Heavy, most models, 0.6–1.1 %
     (Particle 1.9 %), Six-Op 1.0 % (plaits-heavy.md, "Voice cap").
2. **CHANGELOG.md**, Unreleased: Macro, Macro Heavy and Six-Op FM run
   Plaits at its own 47,872.34 Hz and resample to the host's rate, so at the
   FM-1's 44,118 Hz their envelopes, the noise engine's clock, particle and
   swarm densities and the string's low notes are as on the module (they
   were 8.5 % long, 1.41 semitones low, 8.5 % sparse and 9.5 cents flat);
   they cost 13–55 % more desktop CPU (Speech, the cheapest model, 2.3
   times as much), 1,224–2,576 B more per instance, and
   0.76–1.09 ms from a note to its onset (was 0–0.34 ms); hosts above
   47,872.34 Hz are refused.
3. **Owner decisions:** polarity (finding 1). The uncompensated rates of
   findings 2–4 were decided (2026-10-01: native rate, resampled).
4. **third_party/mutable/vendor.py and a test:** write a per-file SHA-256
   manifest of everything it copies, and check the whole tree against it,
   as the Schwung tests do for theirs. This stream's pin test covers only
   the 129 files the Plaits comparison compiles and includes, as one
   digest, so it cannot name the file that changed.
5. **fm1-render `--seed N`** (optional): seeding `stmlib::Random` before the
   first render would replace the statistical test's pre-note with a plain
   seed.
6. **CI:** this file runs in every engine job through `tests/test_engine*.py`.
   It takes about 35 s here with 8 threads, and about 105 s under the
   sanitizers. CI's runners have fewer cores, so expect longer. If that
   is too much, the statistical tests are the heavy half.
7. **Upstream candidate** (minor): `stmlib::SemitonesToRatio` truncates the
   fractional semitone to 1/256, up to 0.39 cents flat, where rounding would
   halve the error. It no longer touches the FM-1's rate (the wrappers add
   no fractional offset now), only pitch bends and other fractional notes.
   Worth a line in `notes/upstream-candidates.md`.

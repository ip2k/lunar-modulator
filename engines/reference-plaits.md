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
  nothing else.
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

**At the FM-1's rate (44,118 Hz)** [verified]:

- **Pitch.** Every tonal slot is within 0.7 cents of what the code predicts
  (16 of the 21 within 0.1), and the tests hold it to 1 cent. The
  prediction is 0.37 cents flat for the Plaits engines (the pitch table), 0
  for Six-Op, and for the string model at A2 also its own rate dependence:
  predicted −9.1 cents, measured −9.5 (finding 4).
- **Envelopes** run as long as the rate ratio (1.085) predicts wherever they
  are set per sample or per block (measured 1.073–1.092). Six-Op's run exactly
  (1.000–1.001).

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
layer, and the engine code is upstream's own, pinned.

**No wrapper code was changed.** Nothing found at the native rate is a defect
in a wrapper. The findings (below) are:

1. a polarity inconsistency between the engines;
2. frequencies set from TIMBRE, not from the note, that the rate compensation
   misses (verified for the filtered-noise model);
3. the same for the low-pass gate's filter [inferred];
4. the string model's tuning depends on the rate at low notes;
5. documentation: two intentional differences the existing notes did not
   describe, and two statements that do not hold.

## Files and commands

| File | What |
| --- | --- |
| `test/ref_plaits.cc` | `build/fm1-ref-plaits`: renders upstream `plaits::Voice`, and compares two WAVs (`--compare`) |
| `mk/ref-plaits.mk` | Builds it. It adds `voice.cc` and Plaits' `SpeechEngine` for this binary only; fm1-render is unchanged |
| `../tests/test_engines_reference_plaits.py` | 125 tests; about 30 s on an M1 Max with 8 worker threads, about 90 s under ASan+UBSan. Also the `--report`, `--calibrate` and `--sixop-sweep` modes that print this file's tables |

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
  one of the wrapper's 12-sample blocks (Six-Op's 16).

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
- **Rate** (44,118 Hz).
  - **Pitch** within ±1 cent of what the code predicts (finding 4 and
    "What the table shows"):
    - −0.374 cents for the Plaits engines;
    - 0 for Six-Op;
    - for the string, also its stretch correction: −9.06 cents in all at A2
      and −0.37 at A4.
  - Envelope stretch must be within 0.02 of what the engine's time base
    predicts:
    - 1.0851 for the LPG, per-sample drums and speech words;
    - 0.98 to 1.105 for Modal;
    - 1.00 ± 0.02 for Six-Op, by decay-rate ratio. DX7 releases can fall
      30 dB in 30 ms, too fast for a 20 ms window fit.
  - Rate points: (0.5, 0.5, 0.5), a 1 s render, Decay 0.3. FM uses TIMBRE 0
    (a sine, no beating). Six-Op uses patches whose release falls 30 dB
    within the render. Chiptune uses Colour 1 and velocity 127 and compares
    10 ms to the note-off, as at the native rate: before that change its LPG,
    which upstream lacks, biased the pitch estimate to −0.80 cents at A2.

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

### At 44,118 Hz (A2 / A4)

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

What the table shows [verified unless marked]:

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
10. **Rate.** The wrappers correct pitch only, and leave every time constant
    and fixed frequency per sample (UPSTREAM.md). The consequences are measured
    above.

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
3. **The LPG's filter is not rate-compensated either.**
   `LPGEnvelope::frequency()` is a per-sample frequency, so the gate's
   low-pass sits 1.41 semitones lower at 44,118 Hz [inferred: code]. It is a
   likely part of the 44,118 Hz LSD and level differences on the LPG models
   (0.05–2.1 dB) [inferred]. The same is true of every fixed per-sample
   filter or delay inside the engines, which the wrappers cannot reach
   without changing vendored code.
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
5. **Documentation.**
   - plaits-heavy.md's "the module has no note-off" does not hold for speech
     words with LEVEL patched (intentional difference 8).
   - plaits-heavy.md item 9 (finding 4).
   - UPSTREAM.md's "Envelope times scale by the same ratio" holds for the LPG, the
     drums and speech. It does not hold for Six-Op (exact) or Modal
     (1.00–1.05). The string's decay depends on its random excitation.
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
  `tests/test_engine*.py`, not run locally. The shared-seed exact matches
  rely on the same floating-point results in both programs on one platform,
  not across platforms. The pin test hashes file contents, so it does not
  depend on the platform.

## Requests outside this stream's files

1. **engines/README.md**, **docs/11 §8** and **third_party/mutable/UPSTREAM.md**:
   link this file.
   - For the Plaits-derived engines, the exit test's render comparison is
     met for the wrapper layer: sample for sample at Plaits' rate (Six-Op
     closely), in 12- and 64-frame host blocks, and within 1 cent of the
     predicted pitch and the documented envelope timing at 44,118 Hz. The
     engine DSP is the same object code on both sides, pinned by hash to
     the upstream files.
   - Record findings 1–4 with it.
   - Correct "envelope times scale by the same ratio" (finding 5).
2. **engines/plaits-heavy.md**:
   - correct the speech-word note-off sentence;
   - note Chiptune's LPG in Macro's notes;
   - correct item 9: the string's tuning also depends on the rate below
     about 160 Hz with dispersion, −9.5 cents at A2 with HARMONICS 0.5
     (finding 4).
3. **Owner decisions:** polarity (finding 1), and the uncompensated rates:
   TIMBRE frequencies, the LPG filter and the string (findings 2–4).
4. **third_party/mutable/vendor.py and a test:** write a per-file SHA-256
   manifest of everything it copies, and check the whole tree against it,
   as the Schwung tests do for theirs. This stream's pin test covers only
   the 129 files the Plaits comparison compiles and includes, as one
   digest, so it cannot name the file that changed.
5. **fm1-render `--seed N`** (optional): seeding `stmlib::Random` before the
   first render would replace the statistical test's pre-note with a plain
   seed.
6. **CI:** this file runs in every engine job through `tests/test_engine*.py`.
   It takes about 30 s here with 8 threads, and about 90 s under the
   sanitizers. CI's runners have fewer cores, so expect longer. If that is
   too much, the statistical tests are the heavy half.
7. **Upstream candidate** (minor): `stmlib::SemitonesToRatio` truncates the
   fractional semitone to 1/256, up to 0.39 cents flat, where rounding would
   halve the error. Worth a line in `notes/upstream-candidates.md`.

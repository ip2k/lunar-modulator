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

- **How close.** At every tested point the error is −87 to −89 dBFS. That is
  the size of the 16-bit rounding the fm1 side adds, and nothing else.
- **Random engines included.** The seven slots with internal randomness match
  too, because both programs draw from the same generator from the same
  state. Without that shared seed they also pass a statistical comparison
  against independent upstream renders.
- **Chiptune** matches once the low-pass gate has opened (from 10 ms). The
  wrapper keeps a gate that upstream bypasses for this engine.

**The three Six-Op slots match closely:** NCC 0.9924 or more, with the fm1
render 36 samples ahead [verified]. The two remaining differences are the
wrapper's by design. The spread over all 96 patches is traced to them below.

**At the FM-1's rate (44,118 Hz)** [verified]:

- **Pitch.** Every tonal slot is within half a cent of upstream, except the
  string model, which is 9.5 cents flat at A2. The documented tolerance for
  the string is ±12 cents.
- **Envelopes** run as long as the rate ratio (1.085) predicts wherever they
  are set per sample or per block (measured 1.075–1.092). Six-Op's run exactly
  (1.000).

**No wrapper code was changed.** Nothing found at the native rate is a defect
in a wrapper. The findings (below) are:

1. a polarity inconsistency between the engines;
2. frequencies set from TIMBRE, not from the note, that the rate compensation
   misses (verified for the filtered-noise model);
3. the same for the low-pass gate's filter [inferred];
4. documentation: two intentional differences the existing notes did not
   describe, and one statement that does not hold.

## Files and commands

| File | What |
| --- | --- |
| `test/ref_plaits.cc` | `build/fm1-ref-plaits`: renders upstream `plaits::Voice`, and compares two WAVs (`--compare`) |
| `mk/ref-plaits.mk` | Builds it. It adds `voice.cc` and Plaits' `SpeechEngine` for this binary only; fm1-render is unchanged |
| `../tests/test_engines_reference_plaits.py` | 97 tests; about 25 s on an M1 Max with 8 worker threads, 80 s under ASan+UBSan |

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
python tests/test_engines_reference_plaits.py --report     # the tables below
```

## The reference: `plaits::Voice` as the module drives it

**What it runs.** `fm1-ref-plaits` links the vendored `plaits/dsp/voice.cc`
with all 24 engines, including Plaits' own `SpeechEngine` (Macro Heavy runs an
adaptation of it). The driving is set up as the module sets it up:

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

**Test points.** The same (HARMONICS, TIMBRE, MORPH) points and notes are used
for every slot:

- The points are (0.2, 0.5, 0.8), (0.5, 0.8, 0.2) and (0.8, 0.2, 0.5), a
  Latin square: each knob takes 0.2, 0.5 and 0.8 once, with the other two
  elsewhere.
- The notes are A2 (45) and A4 (69), two octaves apart.
- For Six-Op, HARMONICS 0.2, 0.5 and 0.8 select slots 6, 16 and 26 of each
  bank.

**Renders.** Six cases per slot, 0.6 s each:

- **Velocity** 100 on the fm1 side, and LEVEL 0.787 upstream; both compress
  it to an accent of 0.941.
- **Gain.** Volume 1, so each fm1 voice is 0.25 of the DAC word. The expected
  fm1-to-reference gain is +0.25, and −0.25 for Six-Op (finding 1).
- **Note length.** Models under the low-pass gate (LPG) are released at
  0.3 s, so the release is compared too. Self-enveloped ones are held for the
  whole render (intentional difference 8 says why).
- **Native side.** fm1-render runs at `--rate 47872.34 --frames 12`.

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

**Criteria.** Each slot is held to the criteria its differences allow:

- **Exact** (20 slots, and Chiptune from 10 ms). The error must be at most
  −80 dBFS, with no lag.
  - Both sides carry the Voice's own 16-bit words. fm1-render rounds them
    again after the 0.25 volume, so the expected error is that rounding:
    ±2 LSB of the reference, an RMS of −89 dBFS. The limit is 9 dB above it.
  - The other measures only restate that error. Their limits are about 1.5
    times the worst of the 144 cases: gain ±0.01 dB, envelope 0.25 dB, pitch
    0.05 cents, LSD 0.25 dB.
  - The random points are held to the same criteria, on the shared seed.
- **Close** (Six-Op, 3 slots).
  - Limits: NCC ≥ 0.977, lag −40 to −32 samples, gain ±0.4 dB, envelope
    0.95 dB, pitch ±0.25 cents, LSD 2.3 dB.
  - Each limit is three times the worst of the 18 cases (for NCC, three times
    1 − NCC). "Six-Op" below traces the differences.
- **Statistical** (6 random slots, independent of the seed). The fm1 render
  of a 1.5 s held note joins five upstream renders with other seeds as a
  sixth member. It must not be the outlier:
  - Its median distance to the others may exceed the largest leave-one-out
    median of any upstream member by a factor, plus a floor.
  - The factors come from a calibration. Each of eight upstream seeds in turn
    was the candidate against five others, at all 36 random points. The
    largest factors a genuine upstream render needed were: level 2.91,
    envelope 1.43, LSD 1.73, centroid 5.04, envelope shift 4.25; pitch stayed
    within its 0.5-cent floor.
  - The limits are 1.5 times those: 4.5, 2.2, 2.6, 7.5 and 6.5, and 2.0 for
    pitch (string only). The fm1 render's own largest factors were 1.48,
    1.04, 1.07, 2.38 and 1.25.
- **Rate** (44,118 Hz). Pitch within ±5 cents, and ±12 for the string. Those
  are the documented tolerances (README, plaits-heavy.md).
  - Envelope stretch must be within 0.02 of what the engine's time base
    predicts:
    - 1.0851 for the LPG, per-sample drums and speech words;
    - 0.98 to 1.105 for Modal;
    - 1.00 ± 0.02 for Six-Op, by decay-rate ratio. DX7 releases can fall
      30 dB in 30 ms, too fast for a 20 ms window fit.
  - Rate points: (0.5, 0.5, 0.5), a 1 s render, Decay 0.3. FM uses TIMBRE 0
    (a sine, no beating). Six-Op uses patches whose release falls 30 dB
    within the render.

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

| # | Upstream | fm1 | Criteria | Error dBFS / NCC, lag | Gain dB | Env max dB | Pitch cents | LSD dB |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | macro Model 0 | exact | −88.5 | 0.0006 | 0.003 | 0.000 | 0.005 |
| 1 | PhaseDistortionEngine | macro Model 1 | exact | −88.5 | 0.0004 | 0.004 | 0.000 | 0.002 |
| 2 | SixOpEngine bank 1 | sixop | close | 0.9993, −36 | 0.0176 | 0.308 | 0.001 | 0.266 |
| 3 | SixOpEngine bank 2 | sixop | close | 0.9924, −38..−35 | 0.1288 | 0.295 | 0.084 | 0.759 |
| 4 | SixOpEngine bank 3 | sixop | close | 0.9957, −37..−36 | 0.0338 | 0.120 | 0.002 | 0.151 |
| 5 | WaveTerrainEngine | macro Model 2 | exact | −88.5 | 0.0009 | 0.009 | 0.000 | 0.009 |
| 6 | StringMachineEngine | macro-heavy Model 0 | exact, L and R | −88.5 | 0.0021 | 0.025 | 0.000 | 0.015 |
| 7 | ChiptuneEngine | macro Model 3 | exact from 10 ms, shared seed | −87.3 | 0.0005 | 0.001 | 0.000 | 0.003 |
| 8 | VirtualAnalogEngine | macro Model 4 | exact | −88.0 | 0.0005 | 0.003 | 0.000 | 0.006 |
| 9 | WaveshapingEngine | macro Model 5 | exact | −88.5 | 0.0005 | 0.003 | 0.000 | 0.003 |
| 10 | FMEngine | macro Model 6 | exact | −88.5 | 0.0004 | 0.007 | 0.000 | 0.002 |
| 11 | GrainEngine | macro-heavy Model 3 | exact | −87.5 | 0.0012 | 0.006 | 0.000 | 0.002 |
| 12 | AdditiveEngine | macro-heavy Model 4 | exact | −88.5 | 0.0015 | 0.015 | 0.000 | 0.002 |
| 13 | WavetableEngine | macro Model 7 | exact | −88.5 | 0.0008 | 0.010 | 0.000 | 0.004 |
| 14 | ChordEngine | macro-heavy Model 1 | exact | −88.2 | 0.0009 | 0.016 | 0.000 | 0.003 |
| 15 | SpeechEngine | macro-heavy Model 2 | exact | −88.5 | 0.0016 | 0.029 | 0.000 | 0.006 |
| 16 | SwarmEngine | macro-heavy Model 5 | exact, shared seed | −88.5 | 0.0010 | 0.030 | – | 0.003 |
| 17 | NoiseEngine | macro-heavy Model 6 | exact, shared seed | −88.5 | 0.0030 | 0.165 | – | 0.011 |
| 18 | ParticleEngine | macro-heavy Model 7 | exact, shared seed | −88.5 | 0.0010 | 0.029 | – | 0.030 |
| 19 | StringEngine | macro-heavy Model 8 | exact, shared seed | −88.5 | 0.0031 | 0.050 | 0.000 | 0.003 |
| 20 | ModalEngine | macro-heavy Model 9 | exact | −88.5 | 0.0008 | 0.039 | 0.002 | 0.029 |
| 21 | BassDrumEngine | macro-heavy Model 10 | exact | −88.2 | 0.0011 | 0.048 | 0.015 | 0.160 |
| 22 | SnareDrumEngine | macro-heavy Model 11 | exact, shared seed | −88.3 | 0.0010 | 0.059 | – | 0.069 |
| 23 | HiHatEngine | macro-heavy Model 12 | exact, shared seed | −88.5 | 0.0014 | 0.082 | – | 0.023 |

Margins [verified]:

- **The error** has 7–9 dB in hand everywhere. Levels, envelopes, spectra and
  release curves are the same to the last rounding step, so the gain
  staging, the post-processors, the LPG and the parameter mappings all match.
- **Six-Op's** margins against its limits: NCC 0.9924 against 0.977, gain
  0.13 dB against 0.4, envelope 0.31 dB against 0.95, pitch 0.084 cents
  against 0.25.
- **Pitch** is "–" for the noise-like slots, which have no pitch.

### Random engines, statistically (the point nearest its limit)

fm1's median distance / the limit:

| # | Upstream | Level dB | Envelope dB | LSD dB | Centroid cents | Envelope shift cents | Pitch cents |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 16 | SwarmEngine | 0.27 / 1.6 | 1.9 / 5.0 | 2.3 / 6.3 | 147 / 450 | 150 / 980 | – |
| 17 | NoiseEngine | 0.54 / 2.8 | 8.4 / 18.1 | 1.5 / 4.1 | 8.7 / 100 | 2.3 / 8.9 | – |
| 18 | ParticleEngine | 0.29 / 1.7 | 3.1 / 6.3 | 11.7 / 32.9 | 2,020 / 16,700 | 36 / 216 | – |
| 19 | StringEngine | 2.6 / 7.6 | 4.4 / 12.2 | 2.6 / 6.1 | 24 / 106 | 0.05 / 5.2 | 0.03 / 0.53 |
| 22 | SnareDrumEngine | 0.20 / 1.4 | 0.39 / 1.05 | 0.87 / 2.6 | 21 / 234 | 12 / 42 | – |
| 23 | HiHatEngine | 0.30 / 1.15 | 0.27 / 0.66 | 1.7 / 4.7 | 40 / 285 | 29 / 177 | – |

Every fm1 median is under half its limit. Upstream renders of the same note
differ widely where the process is sparse or random in frequency, so some
measures carry little information:

- **Particle's centroid.** One to three grains per second at TIMBRE 0.2,
  scattered up to ±31 semitones by HARMONICS 0.8.
- **Swarm's envelope shift.** It meets the ±150-cent search limit between
  two upstream seeds.

### At 44,118 Hz (A2 / A4)

| # | Upstream | Pitch cents (limit) | Stretch (method, range) | Level dB | LSD dB |
| --- | --- | --- | --- | --- | --- |
| 0 | VirtualAnalogVCFEngine | −0.46 / −0.43 (±5) | 1.082 / 1.081 (fit, 1.065–1.105) | +0.04 / +0.02 | 0.23 / 0.16 |
| 1 | PhaseDistortionEngine | −0.39 / −0.35 (±5) | 1.082 / 1.087 (fit) | +0.02 / −0.08 | 0.33 / 0.49 |
| 2 | SixOpEngine bank 1 | +0.03 / +0.00 (±5) | 0.999 / 1.000 (slope, 0.98–1.02) | +0.02 / +0.01 | 0.61 / 1.31 |
| 3 | SixOpEngine bank 2 | −0.00 / +0.01 (±5) | 1.000 / 1.000 (slope) | +0.01 / +0.01 | 0.09 / 0.07 |
| 4 | SixOpEngine bank 3 | −0.00 / −0.00 (±5) | 1.000 / 1.000 (slope) | +0.01 / +0.01 | 0.09 / 0.02 |
| 5 | WaveTerrainEngine | −0.42 / −0.37 (±5) | 1.082 / 1.084 (fit) | +0.02 / −0.03 | 0.34 / 0.49 |
| 6 | StringMachineEngine | −0.40 / −0.36 (±5) | 1.086 / 1.081 (fit) | −0.00 / −0.11 | 0.55 / 0.51 |
| 7 | ChiptuneEngine | −0.80 / −0.06 (±5) | not held (the LPG differs) | −6.09 / −9.11 | 3.01 / 1.62 |
| 8 | VirtualAnalogEngine | −0.45 / −0.42 (±5) | 1.088 / 1.080 (fit) | +0.04 / +0.02 | 0.58 / 0.59 |
| 9 | WaveshapingEngine | −0.41 / −0.37 (±5) | 1.083 / 1.081 (fit) | +0.02 / +0.04 | 0.23 / 2.10 |
| 10 | FMEngine | −0.48 / −0.44 (±5) | 1.081 / 1.081 (fit) | +0.04 / +0.02 | 0.21 / 0.11 |
| 11 | GrainEngine | −0.44 / −0.43 (±5) | 1.091 / 1.079 (fit) | +0.05 / −0.37 | 1.23 / 0.42 |
| 12 | AdditiveEngine | −0.36 / −0.33 (±5) | 1.075 / 1.083 (fit) | −0.06 / −0.54 | 0.05 / 0.12 |
| 13 | WavetableEngine | −0.40 / −0.37 (±5) | 1.079 / 1.080 (fit) | +0.02 / −0.06 | 0.30 / 0.49 |
| 14 | ChordEngine | −0.41 / −0.38 (±5) | not held (1.002 / 1.026) | +0.18 / +0.06 | 0.88 / 0.88 |
| 15 | SpeechEngine (words) | −0.18 / −0.16 (±5) | 1.080 / 1.091 (fit) | +0.84 / +0.05 | 3.20 / 4.34 |
| 16 | SwarmEngine | not held (−4.2 / −3.8) | not held | +0.46 / +0.51 | 2.03 / 1.46 |
| 17 | NoiseEngine | not held (−137 / −142) | not held | −1.22 / −4.60 | 3.11 / 5.01 |
| 18 | ParticleEngine | not held (−141 / −141) | not held | +0.05 / +0.11 | 1.21 / 1.69 |
| 19 | StringEngine | −9.51 / +0.33 (±12) | not held (1.006 / 1.270) | −0.18 / +1.18 | 1.59 / 1.31 |
| 20 | ModalEngine | −0.38 / −0.37 (±5) | 1.002 / 1.052 (fit, 0.98–1.105) | +0.42 / +0.47 | 0.59 / 0.58 |
| 21 | BassDrumEngine | −0.12 / +0.13 (±5) | 1.083 / 1.083 (fit) | −0.07 / +1.21 | 0.36 / 0.31 |
| 22 | SnareDrumEngine | −0.23 / −0.37 (±5) | 1.084 / 1.092 (fit) | +0.74 / +0.71 | 1.29 / 0.67 |
| 23 | HiHatEngine | −0.37 / −0.35 (±5) | 1.085 / 1.081 (fit) | −0.01 / +0.45 | 1.63 / 1.71 |

What the table shows [verified unless marked]:

- **The flat third of a cent** on the tonal Plaits engines is Plaits' own
  pitch table. `stmlib::SemitonesToRatio` truncates the fractional semitone
  to 1/256. The rate offset of +1.4139 semitones leaves a fraction of 0.414,
  which truncates 0.37 cents flat [verified: `stmlib/dsp/units.h` and
  arithmetic]. The measured −0.33 to −0.48 cents is that, plus the
  measurement's own error. Six-Op computes its own frequencies and shows none.
- **Envelopes** set per sample or per 12-sample block run 1.075–1.092 times
  long. The rate ratio is 1.085, as UPSTREAM.md and `mi_macro.cc` state.
  - Modal's resonators decay by Q, a number of periods, which does not change
    with the rate: 1.00–1.05 [inferred mechanism, verified figures].
  - Six-Op's FMVoice runs at the host rate: 1.000. Over the 38 patches whose
    release runs at 30–400 dB/s at both notes, 0.984–1.016.
- **Not held, and why:**
  - **Chiptune:** the fm1 note has an LPG, the upstream one none.
  - **Chords:** its held level beats by about ±1 dB with a period near 0.3 s,
    in a different phase at each rate, which no time stretch follows. The
    beat comes from the engine's own wavetable layer, detuned 0.4 % against
    its divide-down layer (`note_f0 * 1.004f`) [verified: code, envelope
    listing]. Why the phase differs was not traced.
  - **String:** its random excitation shapes the decay. Stretches between
    upstream seeds alone span the whole 0.8–1.3 search range.
  - **Swarm and Particle:** one render per rate cannot show a random
    process's timing.
  - **Noise:** finding 2.
- **The string model** is 9.5 cents flat at A2 at 44,118 Hz, against
  upstream at its own rate. This is its rate dependence, within the ±12
  cents plaits-heavy.md allows. At A4 it is +0.3.
- **Level and LSD** at 44,118 Hz are reported, not held.
  - Level: the LPG and every per-sample filter sit 8.5 % lower in frequency
    (finding 3).
  - LSD: Speech and Noise are 3–5 dB. Speech words play 8.5 % slower, so the
    analysed segment holds other phonemes [inferred]; for Noise see
    finding 2.

### Six-Op, across all 96 patches

The 18 cases above sit well inside the Six-Op limits. The whole bank set
spreads much wider. The sweep: 96 patches × 2 notes × 3 (TIMBRE, MORPH)
pairs, (0.5, 0.5), (0.8, 0.2) and (0.2, 0.8), 576 cases [verified: scratch
harness].

| | fm1 against upstream | upstream against itself, note one block later |
| --- | --- | --- |
| Residual (1 − NCC²), median / worst | −31.8 / −0.6 dB | −49.9 / −8.0 dB |
| Envelope, median / worst | 0.16 / 7.9 dB | 0.05 / 6.4 dB |
| Pitch, median / worst | 0.003 / 31 cents | 0.002 / 3.9 cents |
| Gain, median / worst | 0.009 / 9.0 dB | 0.003 / 0.8 dB |

The right-hand column is the yardstick. It is upstream against itself when
the note lands on the other half of `SixOpEngine`'s staggered 24-sample
chunks (`--delay-blocks 1`). Even upstream is that sensitive on feedback,
drum and pitch-envelope patches. The worst cases, like `B.DRM-SNAR`,
`SYNDM 25.8` and `*Mark III` at Envelope 0.2, are chaotic or fast enough to
diverge from one-block differences.

The fm1 render sits further from upstream than upstream sits from itself.
Two intentional differences account for it [verified: scratch builds and
sweeps]:

1. **Envelope block size.** The wrapper steps envelopes and the LFO every 16
   samples. Upstream steps them every 24 samples per voice, staggered.
   - A scratch build of Six-Op with 24-sample blocks moves the key-sync
     patches' median residual from −33.2 to −43.7 dB. Upstream against itself
     is −50.3 dB.
   - At Envelope 0.2, attack and decay rates run 5.3 times faster, and the
     block size shows most. Bass patches such as `ELEC BASS` then differ by
     up to 1.2 dB in level.
2. **The note-on renders.** The wrapper renders one sample with the gate low
   before every note (plaits-heavy.md, "Note-on"). That moves the
   free-running operator phases on by a sample.
   - Patches with oscillator key sync reset their phases at the note-on, so
     they are unaffected.
   - The 174 cases without key sync keep a −29 dB median residual at either
     block size, against upstream's −47.5.
   - plaits-heavy.md measured this as windowed RMS within 0.04 dB.

The upstream staggering also puts the first sound 36 samples after the
trigger: the new voice's first 24-sample chunk comes one block after the
trigger and is spent in `Setup()` [inferred: code; the measured lag is 35–38
samples in the 18 cases]. The wrapper sounds from the note-on. Its phases then
follow the free-running history, which on a DX7 without key sync is
arbitrary anyway [inferred].

### What the criteria reject

The negative controls are tests too [verified]. Each fails on the measures
listed:

| Control | Fails on |
| --- | --- |
| VA Pair rendered as Shaper | error −7.5 dBFS, gain −13.6 dB, LSD 11.5 dB |
| Additive rendered as Swarm (next Macro Heavy model) | error −17 dBFS, gain −42 dB, envelope 39 dB, LSD 28 dB |
| Timbre and Morph swapped | error −10 dBFS, gain −39 dB, LSD 12.9 dB |
| Reference 1 cent sharp | error −25 dBFS, pitch −0.78 cents |
| Decay 0.55 for 0.5 | error −36 dBFS, envelope 1.9 dB |
| Colour 0.55 for 0.5 | error −46 dBFS |
| Volume 0.99 | error −56 dBFS, gain −0.09 dB |
| Six-Op, the next patch | NCC 0.009, pitch, envelope 57 dB |
| Six-Op, Envelope 0.25 for 0.2 | NCC 0.970, gain +1.3 dB, envelope 17 dB |
| Six-Op, Brightness 0.45 for 0.5 (`BASS    1`) | NCC 0.949, gain −0.8 dB, envelope 1.0 dB |
| Six-Op, Brightness and Envelope swapped | NCC 0.32, envelope 62 dB |
| Six-Op, reference 2 cents sharp | pitch −1.98 cents |
| Noise, a semitone sharp (statistical) | 5 of 30 point-measures: centroid, envelope shift |
| String, a semitone sharp (statistical) | 17 of 36: centroid, LSD, pitch, envelope shift |
| Particle, an octave sharp (statistical) | 7 of 30: centroid, LSD |
| Swarm rendered as Noise (statistical) | 17 of 30 |
| Hi-Hat rendered as Snare (statistical) | 28 of 30 |

Where the criteria stop [verified]:

- **Six-Op, Brightness.** How small a Brightness error the close criteria see
  depends on the patch. At the 9 test points (A3), a 0.05 error fails on 4,
  a 0.1 or a 0.2 error on 6.
  - `ENTRIX` does not respond to Brightness at all.
  - On `XYLOPHONE` at Envelope 0.2, the patch's own intentional differences
    (NCC 0.9918) exceed what even 0.2 of Brightness adds (0.9848).
- **Particle, a semitone.** The statistical comparison cannot see a Particle
  cloud a semitone sharp in 1.5 s: each grain is scattered randomly around
  the note. The shared-seed sample-exact test does see it.

## Intentional differences

Each is by design in a wrapper. Each is either measured here or accounted
for in the comparison.

1. **Gain staging.** Each fm1 voice is Volume × 0.25 of the DAC word; the
   Six-Op mix is Volume × 0.25 of `SoftClip(x × 0.25)`. Accounted for as the
   expected gain.
   - fm1-render's second 16-bit rounding is the −89 dBFS residual [verified].
   - At one voice the bus limiter does not act: the fm1 peak is at most a
     quarter of full scale, −12 dBFS, against the limiter's 0.98 [verified:
     sample-exact results].
2. **Velocity → level.** The wrappers compress velocity/127 exactly as
   `Voice` compresses LEVEL [verified: code, sample-exact results].
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
     1), from 10 ms.
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
     other uncompensated rates (finding 3).
3. **The LPG's filter is not rate-compensated either.**
   `LPGEnvelope::frequency()` is a per-sample frequency, so the gate's
   low-pass sits 1.41 semitones lower at 44,118 Hz [inferred: code]. It is a
   likely part of the 44,118 Hz LSD and level differences on the LPG models
   (0.05–2.1 dB) [inferred]. The same is true of every fixed per-sample
   filter or delay inside the engines, which the wrappers cannot reach
   without changing vendored code.
4. **Documentation.**
   - plaits-heavy.md's "the module has no note-off" does not hold for speech
     words with LEVEL patched (intentional difference 8).
   - UPSTREAM.md's "Envelope times scale by the same ratio" holds for the LPG, the
     drums and speech. It does not hold for Six-Op (exact) or Modal
     (1.00–1.05). The string's decay depends on its random excitation.
   - Chiptune's LPG (intentional difference 7) was not described.
   - These go in files outside this stream (requests below).
5. **Nothing else differs at Plaits' own rate.** Every mapping, gain, LPG,
   post-processor and envelope in Macro and Macro Heavy is sample-exact
   against `Voice`. So are the random engines on the shared seed: no wrapper
   draws from `stmlib::Random` where `Voice` does not [verified].

## Limits of this comparison

- **One note, fixed parameters.** Not covered: parameter changes during a
  note, pitch bend, retriggers, and several voices at once (voice stealing,
  Six-Op's shared LFO, the speech voices' shared bank under a Harmonics
  move). A timed-parameter host feature would allow them
  (plaits-heavy.md's requests).
- **Idealised inputs.** The module's UI and CV reader (`ui.cc`,
  `cv_reader.cc`: pot smoothing, CV calibration, V/OCT scaling) are not
  vendored and not modelled. The reference feeds `Voice` exact values.
- **Parameters left at their defaults.** Word Speed (0) and Macro Heavy's
  prosody (0) are compared at those values only.
- **32-bit and other compilers.** Measured on arm64 macOS (Apple clang 21)
  and under ASan+UBSan. The CI 32-bit and Linux jobs run this file through
  `tests/test_engine*.py`, not run locally. The shared-seed exact matches
  rely on the same floating-point results in both programs on one platform,
  not across platforms.

## Requests outside this stream's files

1. **engines/README.md**, **docs/11 §8** and **third_party/mutable/UPSTREAM.md**:
   link this file.
   - For the Plaits-derived engines, the exit test's render comparison is
     met: sample for sample at Plaits' rate (Six-Op closely), and within the
     documented pitch and envelope tolerances at 44,118 Hz.
   - Record findings 1–3 with it.
   - Correct "envelope times scale by the same ratio" (finding 4).
2. **engines/plaits-heavy.md**: correct the speech-word note-off sentence;
   note Chiptune's LPG in Macro's notes.
3. **Owner decisions:** polarity (finding 1) and the TIMBRE-rate compensation
   (findings 2–3).
4. **CI:** this file runs in every engine job through `tests/test_engine*.py`.
   It takes about 25 s here with 8 threads, and about 80 s under the
   sanitizers. CI's runners have fewer cores, so expect longer. If that is too
   much, the statistical tests are the heavy half.
5. **Upstream candidate** (minor): `stmlib::SemitonesToRatio` truncates the
   fractional semitone to 1/256, up to 0.39 cents flat, where rounding would
   halve the error. Worth a line in `notes/upstream-candidates.md`.

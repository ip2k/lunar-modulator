# plaits-heavy: Macro Heavy and Six-Op FM

This stream adds the remaining Plaits engines from docs/11 §4 as two FM-1
engines. The code is Emilie Gillet's (Mutable Instruments Plaits, MIT),
vendored unmodified in `third_party/mutable/` (`UPSTREAM.md`). The wrappers
are ours.

| id | Name | Source | Voices | Instance, 64-bit host | Instance, 32-bit targets |
| --- | --- | --- | --- | --- | --- |
| `macro-heavy` | Macro Heavy | `src/mi_macro_heavy.cc` | 4 | 71,088 B | 70,880 B |
| `sixop` | Six-Op FM | `src/mi_sixop.cc` | 8 | 12,528 B | 10,796 B |

Both run Plaits at its own 47,872.34 Hz and resample to the host's rate
since 2026-10-01 (below, "Rate"). That added 2,576 B to Macro Heavy (two
resamplers) and 1,224 B to Six-Op (one); before, they were 68,512 / 68,304 B
and 11,304 / 9,572 B.

How the sizes were measured:

- **64-bit:** the renderer's `instance_bytes` on macOS arm64 [verified].
- **32-bit:** `sizeof` of each `Instance`, read from a template diagnostic
  of `clang++ -target i386-apple-macos10.13 -fsyntax-only` over the
  wrapper's source [verified, compile only]. The same probe on the earlier
  sources gives the earlier figures, which were read from the assembly for
  `i386-apple-macos10.13` and `armv7-apple-ios9` (both targets agreed).
  pi32v2 should match if it is ILP32 with 4-byte float alignment
  [inferred]. CI's `-m32` job renders every engine and prints its size
  (`.github/workflows/ci.yml`).

Sources are added in `mk/plaits-heavy.mk`. The fragment appends a
third-party file only when no other fragment lists it already.

```bash
make -C engines
engines/build/fm1-render --engine macro-heavy --param Model=8 --param Harmonics=0.25 \
    --note 0:57:100:1 --note 0:64:100:1 --seconds 3 --out string.wav
engines/build/fm1-render --engine sixop --param Patch=32 \
    --note 0:57:100:1 --note 0:61:100:1 --note 0:64:100:1 --seconds 3 --out epiano.wav
python -m pytest tests/test_engines_plaits_heavy.py      # 183 tests
```

## Rate: Plaits at its own rate, resampled

The owner's decision of 2026-10-01: the Plaits-derived engines (Macro, Macro
Heavy, Six-Op FM) run Plaits at its native rate, `kCorrectedSampleRate` =
47,872.34 Hz, whatever the host's rate, and resample their voice mix to the
host's rate with `include/fm1_resampler.h` (resampler.md), as Shapes does with
Braids at 96 kHz [verified: the code].

- **Blocks.** Macro and Macro Heavy render Plaits' own 12-sample blocks,
  Six-Op its 16-sample ones, at 47,872.34 Hz. Each output sample pulls from
  the current block what the resampler needs and renders the next block when
  it runs out, so the output does not depend on the host's block size
  [verified: 1, 7 and 64 frames byte-identical,
  `test_fm1_rate_output_does_not_depend_on_the_host_block` and
  `test_output_is_independent_of_host_block_size`].
- **One resampler per output channel per instance, never per voice.** Macro
  and Six-Op are mono: one. Macro Heavy has two, for the string machine's L
  and R. In its 12 mono models both channels' mixes are the same floats, so
  after a change out of the string machine the right resampler runs on, fed
  the mono mix and ringing out the string machine's AUX, only until its
  state is the left one's bit for bit (checked once per 12-sample block:
  81 output samples at 44,118 Hz, 79 at 44,100 Hz and 71 at 11,968 Hz in
  the case measured, at most a block at 47,872.34 Hz [verified: a scratch
  build printing the count]). From there the right channel is the left's
  samples, which is what the right resampler would give. On a change into
  the string machine it takes a copy of the left one's state, unless it is
  still running. So the output is
  what two resamplers running all along would give, at one resampler's
  cost in 12 of the 13 models [verified: the wrapper at 44,118 Hz against
  itself at 47,872.34 Hz resampled per channel, the string machine left and
  entered again after 8,000 and after 64 samples, within the 16-bit rounding
  of the native render (reference-plaits.md); and from silence,
  `test_string_machine_entered_later_renders_as_if_created_in_it`]. Until
  a review of this change (reference-plaits.md, "Review") the right
  resampler stopped at the change, which cut the AUX tail to the left
  channel (1,046 LSB at 44,118 Hz) and, at 47,872.34 Hz, put the left
  channel's samples into the rest of the string machine's last block when
  the change came mid-block. Running on costs nothing measurable: four
  voices at 44,118 Hz in 64-frame blocks take 15.3–15.8 µs a block in the
  string machine, 13.2–13.7 in Additive, 14.2–14.5 in String and 12.1 in
  Snare, and 6.1–6.3 with a change in and out of the string machine every
  0.1 s, before and after, within the desktop's run-to-run spread of about
  3 % [verified: `ns_per_block`, best of 7, Apple M1 Max].
- **No pitch or time correction.** The pitch offset
  12·log2(47,872.34 / rate) that these wrappers used to add is gone
  [verified: the code], and every time constant, TIMBRE-derived rate and
  per-sample filter is upstream's at any host rate [inferred: the engines
  run at upstream's rate in upstream's blocks; verified for every slot by
  the comparison below]. At 44,118 Hz this removed the envelopes' 8.5 %
  stretch (now 1.000–1.001), the noise clock's 1.41-semitone error (its
  strict xfail now passes), the string model's −9.5 cents at A2 and the
  pitch table's −0.37 cents on every tonal engine (now within 0.007 cents)
  [verified: reference-plaits.md, "At 44,118 Hz"]; and the particle and
  swarm densities' 8.5 % shortfall [verified: Particle and Swarm write
  upstream's samples through the resampler, 0 of 158,820 differing, so
  their grain timing is upstream's; the 8.5 % figure itself was inferred
  from the rates].
- **At a 47,872.34 Hz host** the resampler passes samples through bit for
  bit [verified: 25 models and patches with three notes, note-offs, a bend
  and a knob move, at 12-, 64- and 7-frame blocks, byte-identical to the
  wrappers before this change; every native-rate reference test passes
  unchanged]. So does a Macro Heavy render that leaves and re-enters the
  string machine mid-block, at 1-, 7-, 12- and 64-frame blocks, since the
  right resampler runs on after the string machine [verified: against
  2bf4133's wrapper; `test_string_machine_block_keeps_its_aux_after_a_model_change`].
- **Refused hosts.** The resampler converts down by a ratio of 1 to 4, so a
  host above 47,872.34 Hz or below a quarter of it (11,968.085 Hz) is
  refused: `create` returns NULL, as Shapes does outside 24–96 kHz
  [verified: `test_refuses_host_rates_the_resampler_cannot_serve`]. The
  FM-1's 44,118 Hz is inside the range. No test renders these engines above
  the native rate, apart from that test's refused rates [verified: grep of
  the tests].
- **Latency.** A note-on or note-off reaches the next block rendered at
  47,872.34 Hz. The resampler adds its group delay of 30 output samples
  and pulls about 4 input samples ahead of output time. From a note's
  arrival to the centre of its onset, over every arrival sample at
  44,118 Hz: 33.4–44.5 output samples (0.758–1.008 ms, mean 0.883 ms) for
  Macro and Macro Heavy, 33.4–48.2 (0.758–1.092 ms, mean 0.925 ms) for
  Six-Op. Before, a note waited for the wrapper's next block at the host's
  rate: 0–11 samples (0–0.249 ms, mean 0.125 ms) and 0–15 (0–0.340 ms)
  [verified: computed from the resampler's pull arithmetic
  (`inputs_pulled` in tests/test_engines_reference_plaits.py), which
  `test_note_lands_on_the_next_native_block` checks against a render]. So
  about 0.76 ms more on average; in the FM-1's 64-frame blocks, where every
  event arrives on a block boundary, 0.79 ms more for Macro and Macro Heavy
  and 0.93 ms for Six-Op, whose 16-sample blocks used to divide 64.
- **CPU and memory**, below and in the table at the top.

## Macro Heavy

### Parameters and models

| Page | Parameters |
| --- | --- |
| 0 | Model, Harmonics, Timbre, Morph (Plaits' three main knobs) |
| 1 | Decay, Colour (the low-pass gate, as in Macro), Volume, Word Speed |

The 13 models, with Plaits' own post-processing for each. The gains come from
`Voice::Init`; a negative out gain means Plaits' limiter runs at that
pre-gain.

| # | Model | Plaits engine | Out gain | Aux gain | Envelope | Arena | Engine object, 64-bit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | Str Machine | `StringMachineEngine` | 0.8 | 0.8 | LPG | 4,332 B | 304 B |
| 1 | Chords | `ChordEngine` | 0.8 | 0.8 | LPG | 236 B | 376 B |
| 2 | Speech | `SpeechVoiceEngine` (ours, from `SpeechEngine`) | -0.7 | 0.8 | LPG for vowels; words bypass it (per block) | 14,656 B in voice 0 (the shared word bank), 192 B in the others | 432 B |
| 3 | Formant | `GrainEngine` | 0.7 | 0.6 | LPG | 0 | 136 B |
| 4 | Additive | `AdditiveEngine` | 0.8 | 0.8 | LPG | 144 B | 200 B |
| 5 | Swarm | `SwarmEngine` | -3.0 | 1.0 | LPG | 512 B | 32 B |
| 6 | Filt Noise | `NoiseEngine` | -1.0 | -1.0 | LPG | 96 B | 136 B |
| 7 | Particle | `ParticleEngine` | -2.0 | 1.0 | LPG | **16,384 B** | 248 B |
| 8 | String | `StringEngine` | -1.0 | 0.8 | its own | 15,520 B | 432 B |
| 9 | Modal | `ModalEngine` | -1.0 | 0.8 | its own | 96 B | 336 B |
| 10 | Bass Drum | `BassDrumEngine` | 0.8 | 0.8 | its own | 0 | 192 B |
| 11 | Snare | `SnareDrumEngine` | 0.8 | 0.8 | its own | 0 | 296 B |
| 12 | Hi-Hat | `HiHatEngine` | 0.8 | 0.8 | its own | 192 B | 336 B |

### What the wrapper does

**Voices.** The layout is Macro's: one engine object per voice, built by
placement new, with Plaits' 12-sample blocks at Plaits' own rate and the
mix resampled ("Rate", above).

- **Arena.** Each voice gets its own 16 KB arena, which is the size of
  Plaits' single shared arena. It has to be that large: the particle
  diffuser alone takes all 16 KB and the string model 15.2 KB. Speech's
  word bank (14.3 KB) sits in voice 0's arena and serves all four voices.
- **Clean start.** A model change clears every arena before `Init()`, so no
  engine reads what the previous model left behind (see the six-op finding
  below).

**Allocation check.** `kArenaNeed[]` restates every upstream `Allocate<>()`
call, one for one. A `static_assert` holds them to the arena size, so no
allocation can fail. After `Init()`, `Create()` checks that exactly the
expected number of bytes was handed out.

- `BufferAllocator` returns NULL on failure without consuming anything. So
  "exactly the expected bytes" means every allocation succeeded and the
  table matches upstream.
- On a mismatch the model is disabled and stays silent. It never writes
  through NULL. Speech voices 1-3 expect only their two temp buffers, and
  are disabled with voice 0, whose arena holds the bank they all read.
- A re-vendor that changes an allocation therefore fails
  `test_every_heavy_model_sounds_cleanly`.

**Self-enveloped models.** These are string, modal, the three drums, and
speech words. As in `Voice::Render`, the low-pass gate is bypassed, and the
LPG is re-initialised while bypassed.

- **Accent.** The accent is the note's velocity, compressed as Plaits
  compresses LEVEL, for the whole life of the note. Drums and strings read
  it at the trigger, and speech uses it as the word's gain. The LPG's level
  still drops to zero at note-off.
- **Release after note-off.** This is our addition, not Plaits behaviour.
  The module has no note-off for drums and strings, which ring on after
  LEVEL falls; for speech words with LEVEL patched, upstream uses the
  compressed LEVEL as the gain every block, so a word stops as soon as LEVEL
  falls, where Macro Heavy holds the accent and fades [verified:
  engines/reference-plaits.md]. The fade uses the same curve as the LPG's
  vactrol release and is set by the same Decay and Colour. It makes a
  keyboard's key-up count even at Morph = 1, where the string and modal
  models ring forever inside the engine.
- **Freeing voices.** A voice is freed when its release gain falls below
  1e-4, or when its output stays below about -80 dBFS for 50 ms after
  key-up. It is also freed after 1 s of silence while the key is still held,
  so a held drum key does not keep a voice busy.
- **Retriggers.** A retrigger during the release ramps the gain back up
  over one block.

**Speech special cases** (from `Voice::Render`, engine index 15):

- **Prosody and speed.** With TRIG patched, Plaits takes the prosody amount
  from the FM attenuverter and the word speed from the MORPH attenuverter.
  Here prosody is fixed at 0, which keeps words on the played pitch. Word
  Speed (-1..1, Plaits' units) is a parameter; it changes the playback
  length of a word by up to 4x either way.
- **`already_enveloped`.** Speech reports it per block. It is true for word
  playback (HARMONICS above about 0.44, where a word bank is selected) and
  false for vowels and phonemes below that.
- **Envelope scaling.** Plaits' `internal_envelope_amplitude` scaling is
  moot here: like Macro, this wrapper applies no internal-envelope
  modulation (all modulation amounts are 0).

**One word bank for all speech voices.** Plaits' `SpeechEngine` keeps its
own LPC word bank and parses it (up to 4.8 KB of bitstream into 926
frames) inside `Render()` whenever HARMONICS selects another bank. With one
engine per voice, four voices parsed the same data four times in one audio
block, and so did a chord struck after a bank change or a model change.

- **Measured** [verified: scratch timing harness, M1 Max, 4 held voices,
  64-frame blocks]:

  | Case | Before | Shared bank |
  | --- | --- | --- |
  | First block after Harmonics moves into bank 4 | 62–70 µs | 18–21 µs |
  | Chord note-on after a bank change made while idle | 15–17 µs | 3.6–4.2 µs (no parse) |
  | Chord right after switching the model to Speech | 15 µs | 7–9 µs |
  | Ordinary word-mode block | 3.3–3.8 µs | 3.2–3.8 µs |

- **How.** The speech model runs `SpeechVoiceEngine`, our adaptation of
  `SpeechEngine` (MIT, credited in the source). Its `Render()` is
  upstream's line for line, except that the word bank index comes from one
  shared quantizer. `UpdateWordBank()` runs that quantizer once per
  12-sample block, as upstream runs it, and loads the shared bank before any
  voice renders. So a bank change costs one parse, in the next block,
  whether or not notes are sounding, and a note-on never parses. Harmonics
  changes only between render calls, so at most one parse falls in a host
  block. `plaits/dsp/engine/speech_engine.cc` is no longer built.
- **Output.** For constant parameters the output is byte-identical to the
  per-voice `SpeechEngine` [verified: 12 Harmonics values across the
  naive, SAM, phoneme and all word-bank ranges, 6 staggered notes each, plus
  the Word Speed, release and 7-frame cases].
- **One deviation, at a bank change.** Upstream, each controller whose own
  `Load()` succeeds drops the word it was playing, but first finishes the
  frame it is on (25 ms at normal word speed). Here `RestartPlayback()`
  re-initialises every voice's controller. The voices leave the word at
  once, and their LPC synth restarts from silence with a 12-sample fade-in.
  - **After the change** both scan the new bank identically [verified:
    per-block RMS of 4 held voices across Harmonics 0.5 → 0.9 → 0.6 → 0.1 →
    0.75 → 1.0; old and new converge within ~40 blocks and match exactly
    from then on].
  - **At the change** the largest sample-to-sample step within 128 samples
    was 0.007–0.12 of full scale, against 0.03–0.08 upstream. The speech
    signal's own steps reach 0.16 in the same segments, so the restart
    makes no outsized click.
- **Stage B.** One bank-4 parse is ~15 µs here. A core 15–20× narrower
  would take ~0.25–0.3 ms of the 1.45 ms block for it, once per bank change
  [inferred]. Measure it on pi32v2. If it is too much, the parse can be
  spread over several blocks, one word per block.

**Stereo.** The string machine's OUT and AUX are the two sides of its
ensemble (`out = 0.66 l + 0.33 r` and the mirror image) [verified: code], so
this model renders them as L and R, each through its own resampler. Every
other model is mono, from OUT, through the left one.

### Voice cap: 4

RAM sets the cap. Four voices of 17.1 KB (arena, engine, post-processors
and buffers) come to 67 KB, plus 2.5 KB for the two resamplers, out of the
roughly 387 KB free in the stock layout (docs/11 §2).

CPU is unknown until stage B measures it:

- Plaits was built to use most of a 72 MHz Cortex-M4F for one voice
  [reported: docs/11 §2, from MI's notes].
- The FM-1 has about 5,440 cycles per output sample for everything
  [inferred: arithmetic].

Desktop cost, for scale only. These are Apple M1 Max figures at 44,118 Hz
in 64-frame blocks, as a share of the 1.451 ms block, with every voice held
for 3 s (keys 48, 51, 54…, velocity 100), the best of 20 runs of the base
commit and of 15 of this one, in the same session [verified: `fm1-render`'s
`ns_per_block`, both builds]:

| Engine / model | Voices | Before: Plaits at the host's rate | After: at 47,872.34 Hz, resampled | × |
| --- | --- | --- | --- | --- |
| Macro Heavy, String Machine (two resamplers) | 4 | 0.69 % | 1.06 % | 1.55 |
| Macro Heavy, ten other models | 4 | 0.43–0.77 % | 0.62–1.00 % | 1.29–1.45 |
| Macro Heavy, Particle | 4 | 1.70 % | 1.91 % | 1.13 |
| Macro Heavy, Speech (Harmonics 0.5 / 0.9) | 4 | 0.13 / 0.15 % | 0.31 / 0.32 % | 2.3 / 2.2 |
| Six-Op FM (patches 0, 32, 89) | 8 | 0.73–0.75 % | 0.96–0.99 % | 1.32 |
| Macro, seven models | 12 | 0.95–1.85 % | 1.09–2.17 % | 1.16–1.24 |
| Macro, 2-op FM | 12 | 4.87 % | 5.52 % | 1.13 |

The change adds about 2.3 µs per resampler per block, the resampler's
36 ns per output (resampler.md), and 8.5 % more engine samples: 2.6–3.5 µs
for a mono Macro Heavy model, 5.5 µs for the string machine, 3.4 µs for
Six-Op, 2.1–4.7 µs for Macro (9.4 µs for 2-op FM) [verified: the same
runs; the split inferred from the bench figure]. An earlier session's
figures for the old code (0.50–0.92 % for most heavy models, 1.75 % for
Particle, 0.39–0.91 % for Speech at other settings) differ from this run's;
compare the before and after columns with each other, not with them.

So on the desktop, four heavy voices still cost less than Macro's twelve
light ones, and particle is still the heaviest heavy model. On pi32v2 the
resampler may weigh more: resampler.md estimates about 800 cycles per
output, 15 % of the FM-1's budget per resampler, and the string machine
runs two [inferred: no pi32v2 cycle counts yet]. pi32v2 is a much narrower
core (engines/README.md), so these ratios need not hold there [inferred].
Raising the cap is a one-line change once stage B has numbers.

## Six-Op FM

### Outer polyphony versus `kNumSixOpVoices`

Plaits' `SixOpEngine` is a mono engine with two `FMVoice`s of its own
(`kNumSixOpVoices = 2`). Each trigger moves to the other one, so the
previous note can release. It renders them staggered, one voice for 24
samples per call.

Wrapping one `SixOpEngine` per FM-1 voice would double the CPU per note. It
would also cost about 11.5 KB per voice on a 64-bit host: the engine with
its own `fm::Algorithms<6>` table (4.6 KB; 3 KB on 32-bit), plus an arena
holding a whole unpacked bank.

This wrapper takes the other route:

- **The outer allocator replaces the internal pair.** Each FM-1 voice is
  one Plaits `FMVoice` (an `fm::Voice<6>` plus its LFO) with its own
  unpacked `fm::Patch` of 156 B.
- **Shared table.** One `fm::Algorithms<6>` is shared by all voices. It is
  read-only after `Init`, and Plaits shares it between its own two voices.
- **Cost.** One FM voice of CPU per sounding note, and 792 B per voice
  (768 B on 32-bit).
- **Tails.** The previous note's tail comes from the outer allocator: a new
  key takes a free voice, or else the oldest released one.

What is kept from `SixOpEngine::Render`, triggered mode:

- **Brightness** is Plaits' TIMBRE: modulator levels ±16 dB. At 0.5 the
  patch plays as programmed.
- **Envelope** is Plaits' MORPH.
  - Attack and decay rates scale by 2^((0.5 − e)·8), and release rates by
    2^(−|e − 0.3|·8). So no value is neutral.
  - The default 0.5 plays attacks and decays as programmed, with releases
    about three times longer.
- **Velocity** is the compressed accent, as Plaits derives it from LEVEL.
- **Output** is `SoftClip(x · 0.25)` with out gain 1.0 and no low-pass gate:
  the engine is registered `already_enveloped`.
- **LFO.** The most recently triggered voice's LFO runs. Voices on the same
  patch follow it (the DX7 has one LFO), and voices still sounding another
  patch run their own.

What differs, deliberately:

- **Patch selection.** HARMONICS' hysteresis scan over the 32 patches of one
  bank becomes a single **Patch** list of all 96 patches.
  - Entries are named `"<bank> <name>"` from the patch data, for example
    `2 E.PIANO 1`.
  - The API's enum names are static, so a separate Bank parameter could not
    show the voice names of the bank it selects (see the API request below).
  - `test_patch_names_match_the_banks` re-reads `resources.cc` and checks
    the table.
- **Transpose.** The patch's own transpose is applied (DX7 "C3" = 24).
  - Plaits unpacks it but never reads it [verified: grep].
  - 47 of the 96 patches are transposed, most of them an octave down.
  - The tests hold three patches (none, −12 and +12) to ±5 cents.
  - The transposed note is also what the patch's keyboard and rate scaling
    see.
- **Rate.** `FMVoice::Init` takes the sample rate. It now gets Plaits'
  47,872.34 Hz, as upstream's `SixOpEngine::Init` passes it, and the mix
  is resampled to the host's rate ("Rate", above) [verified: code]. Until
  2026-10-01 it got the host's rate. Either way there is no pitch offset
  and DX7 envelope and LFO times are exact; at Plaits' rate its samples are
  also upstream's, so it compares with upstream at 44,118 Hz as the other
  two wrappers do (reference-plaits.md).
- **Blocks.** Internal blocks are 16 samples at 47,872.34 Hz (0.33 ms).
  Envelopes and the LFO update once per block; Plaits updates every 24
  samples per voice, staggered.
- **Note-on.** Each note-on does two one-sample renders with the gate low,
  into scratch, and discards them.
  - The first runs a new patch's `Setup()`, which otherwise returns without
    rendering and would swallow the note's first block (a 16-sample blank).
    With no new patch it renders one sample of release.
    `test_sixop_note_sounds_from_its_first_block` fails with the renders
    removed. It checks the first 16 samples at Plaits' own rate, where the
    resampler passes the blocks through; at 44,118 Hz its 30-sample delay
    leaves the first 16 outputs silent either way.
  - The second drops `fm::Voice`'s gate, so a voice stolen or retriggered
    while held still sees a note-on edge and attacks again. Without it a
    stolen held voice stays silent; `test_sixop_stolen_held_voice_attacks_again`
    fails with the renders removed.
  - **Why one sample, not zero.** Until this review they were zero-length
    renders. `RenderOperators` computes `1.0f / float(size)` (`operator.h`),
    so a zero-length render divided by zero. That is harmless where the FPU
    does not trap, but only a port can reach it (Plaits never renders zero
    samples). The one-sample renders cost at most two samples of one voice
    per note-on. The output differs from the zero-length version only in
    operator phase: windowed RMS matches within 0.04 dB [verified: E.PIANO
    1, two notes].
- **Freeing.** A voice is freed 50 ms after key-up once its output is below
  about −80 dBFS. Held voices are never freed: a slow DX7 attack can stay
  under that threshold for a long time.

### Voice cap: 8

The FM-1's stock msfa plays 12 six-op voices plus effects on one pi32v2 core
[reported: AL-255, docs/11 §2]. msfa is fixed point, with its hot loops
copied to RAM.

Plaits' float operators should cost the same order per voice [inferred].
Eight leaves room for the effect chain. On the desktop, eight Six-Op voices
cost half of Macro's twelve light voices. RAM is not a constraint, so twelve
is a one-line change if stage B allows it.

### The patch data

The three banks are the `syx_bank_0..2` arrays in Plaits' `resources.cc`,
under Plaits' MIT header:

| Bank | Contents |
| --- | --- |
| 1 | Basses and synths |
| 2 | Electric pianos, keys, mallets and percussion |
| 3 | Organs, pads, strings and brass |

Their names match well-known DX7 factory and third-party patches (`E.PIANO
1`, `*PPG*Vol.1`, `CS 80`). The source does not say where they came from.
The names are shown as they are stored, and some carry third-party
trademarks or a person's name: `FENDER 1`, `STEINWAY`, `*Hammond 1`,
`*PPG*Vol.1/2`, `FAIRLIGHT`, `*Fairl. 3`, `CS 80`, `JX-33-P`, `M1 PADS`,
`Mooger Low`, `VANGELIS 1`. The credits string therefore says "DX7 patch
banks as distributed with Plaits" rather than claiming them as MIT code.
See the open issue below.

## Tests

`tests/test_engines_plaits_heavy.py` has 183 tests:

| Group | Tests | What they check |
| --- | --- | --- |
| Registry | 1 | Ids and names avoid Mutable Instruments' names; pages, name lengths and credits |
| Patch names | 1 | The patch-name table matches `resources.cc` |
| Every model and patch | 13 + 96 | One note each: no non-finite samples, no raw clipping, audible |
| Macro Heavy tuning | 18 | At A3, A4 and A5, after a low-pass that leaves the fundamental (eight one-pole passes for modal, whose second partial is 5.5 dB above its first at A4, four for the rest). ±5 cents for additive, formant, swarm, speech vowels and modal (structure 0.25); ±12 cents for string |
| Six-Op tuning | 6 | ±5 cents for three patches with transposes of none, −12 and +12 |
| Chords under the limiter | 16 + 8 | At the voice cap and past it (stealing): no clipping, peak ≤ 0.98 |
| Releases | 7 | Releases end (LPG, self-enveloped at Morph = 1, speech words, Six-Op) |
| Voice freeing | 3 | Freeing, as render cost: released chords cost 2–6 % of held ones on the desktop, and the test allows 50 %; it fails when freeing is disabled |
| Wrapper behaviour | 10 | Stereo string machine; the string machine entered by a model change renders as one created in it (64- and 7-frame blocks); the string machine's last block keeps its AUX after a model change mid-block (at Plaits' rate); Word Speed; a stolen held voice attacks again; a Six-Op note sounds from its first block (2 patches, at Plaits' rate); all four speech voices speak from the shared word bank; output identical at host blocks of 64, 7 and 1 frames |
| Determinism | 3 | Particle, string and Six-Op render the same bytes twice |
| Instance sizes | 1 | The sizes stay within the bounds above, each less than one resampler (1,288 B) above the size: the only test that sees a resampler per voice instead of per output channel |

Where tuning is not checked, and why:

- **Chords and string machine** play four or five notes per key.
- **Drums, noise and particle** have no stable fundamental.
- **A2** is left out: the low-passed fundamental of the physical models is
  too weak there.

What the tests cannot reach through `fm1-render`, and how it was checked
instead:

- **Parameter changes during a render.** The host applies `--param` once,
  before the first block. Two cases were checked with scratch C++ harnesses
  only:
  - a Harmonics move across word banks (the timing and transition figures
    above);
  - a Patch change while all eight Six-Op voices are held, then a ninth key
    [verified]. The stolen voice attacks: RMS 0.0017 in the 0.2 s before,
    0.028 after. With only one note-on render it stays silent (0.00017),
    because `Setup()` uses the render and the gate never drops. So both
    renders are needed, and no host-level test covers the second one in
    this case.
- **Voice freeing** is judged by render time, the one timing-based
  assertion in the file. The margin is wide (2–6 % measured against a 50 %
  bound, best of 3), and it is mutation-tested. A host diagnostic that
  reports active voices would make it exact (requests below).
- **Mutation checks** [verified]:
  - With both note-on renders removed from Six-Op, the first-block test (2)
    and the stolen-voice test fail.
  - With speech voices 1-3 made to fail their arena check, only
    `test_speech_voices_all_read_the_shared_word_bank` fails: the chord
    carries 0.45 of the four single notes' energy, against 0.94–1.0 when all
    four voices speak.

## Upstream quirks found

The first entry was already known. None of these is fixed in the vendored
files, which stay byte-identical. Where a wrapper works around one, it says
so.

1. **`WavetableEngine` arena overrun** (Macro's, known).
2. **`LPCSpeechSynthController` reads `phonemes_[15]`,** one past the
   15-entry table.
   - **When:** in LPC phoneme mode (HARMONICS between 1/6 and about 0.44), a
     trigger picks consonant `5 + r % 10`, and `PlayFrame(frames, 14, false)`
     reads `frames[15]` as the interpolation partner.
   - **Effect:** the blend weight is exactly 0, so the value is unused and
     the harm is nil; it is still an out-of-bounds read.
   - **Evidence:** [verified: ASan global-buffer-overflow in
     `LPCSpeechSynth::PlayFrame`, with `--param Model=2 --param
     Harmonics=0.25 --param Timbre=0.375 --param Morph=0 --note
     0:57:100:0.3`; the sweep below also hits it at Harmonics 0.2, 0.3 and
     0.4]. These are ordinary knob positions, so the read is in shipped code
     paths. It stays in `LPCSpeechSynthController`, which
     `SpeechVoiceEngine` calls unchanged.
   - **Why it stays.** No wrapper-side fix exists without changing which
     consonant plays. The read stays inside the program's constant data, and
     the fetched fields are integers turned into floats and multiplied by 0,
     so no NaN can come of it.
   - **Upstream fix.** When `interpolate` is false,
     `LPCSpeechSynth::PlayFrame(frames, frame, interpolate)` should not read
     `frames[frame_integral + 1]` (pass the same frame twice). It is listed in
     `notes/upstream-candidates.md`.
3. **`fm::NormalizeVelocity(1.0)` reads `lut_cube_root[17]`,** one past the
   17-entry table.
   - **Cause:** `stmlib::Interpolate` reads `index + 1`. Plaits passes a
     velocity of exactly 1.0 whenever LEVEL is fully up, because the
     compressed level is clamped to 1.
   - **Evidence:** [verified: ASan]. Six-Op caps its accent at 0.9999.
4. **`fm::Pow2Fast` left-shifts a negative integer.**
   - **Where:** `r.w += x_integral << 23` in `dx_units.h`. This is undefined
     in C++11 and C++14 (defined since C++20).
   - **Effect:** it does what was intended on GCC and Clang.
   - **Evidence:** [verified: UBSan `shift-base` on every Six-Op render].
     It is the only report the sanitizer sweep below gets from Six-Op.
5. **`SixOpEngine`'s `temp_buffer_` is sized for 12-sample calls only.**
   - **Sizes:** it allocates `kMaxBlockSize * 4` = 96 floats, but
     `fm::Voice::Render(temp, 2 * size)` uses 3 × 2 × size floats, which is
     144 at `size = kMaxBlockSize` (24).
   - **Effect:** at 24 samples the patches whose algorithm uses the third
     buffer write 48 floats past it, into `acc_buffer_[24..48)`. Only the
     allocation order keeps that harmless: that half of `acc_buffer_` is
     unused with two voices.
   - **Evidence:** [verified: 11 of 96 patches, scratch harness]. Plaits
     only calls with 12. Six-Op does not use `SixOpEngine`.
6. **`SixOpEngine` never clears `acc_buffer_`.**
   - **Effect:** the first block after the engine is selected mixes in
     whatever the previous engine left in the shared arena, bounded by
     `SoftClip`, so at worst a click.
   - **Evidence:** [verified: an arena pre-filled with 3.0f gives 0.645 on
     the first block with no trigger, then 0]. Macro Heavy clears arenas on
     model change.
7. **The naive and SAM speech synths never see a trigger under `Voice`.**
   - **Cause:** `SpeechEngine` tests `parameters.trigger ==
     TRIGGER_RISING_EDGE`. `Voice` sets `RISING_EDGE | HIGH` on a rising
     edge, so the value is 5, not 1.
   - **Effect:** the naive synth's 50 ms consonant click and SAM's trigger
     never fire on the module.
   - **Evidence:** [verified: code]. The wrapper passes triggers as `Voice`
     does, and `SpeechVoiceEngine` keeps the `==` tests as they are, so it
     sounds like the module.
8. **`SwarmEngine::Reset` computes `n = (kNumSwarmVoices - 1) / 2` in
   integer arithmetic.**
   - **Effect:** that gives 3, not 3.5, so the eight grains' ranks run from
     −1 to +1.33 rather than ±1, and the detune spread is lopsided.
   - **Evidence:** [verified: code]. Harmless.
9. **The string model reads 6–9 cents sharp** with structure 0.25, Morph
   0.8 and a medium brightness.
   - **Evidence:** it does so at Plaits' own 47,872 Hz as well as at
     44,118 Hz [verified: rendered at both rates]. The cause is the
     Karplus-Strong loop's tuning compensation, not the rate change.
   - **Correction (reference renders):** that holds for these conditions,
     at A3 and above. Below about 160 Hz with dispersion the stretch
     correction depends on the loop length in samples, so the rate change
     matters: -9.5 cents at A2 with Harmonics 0.5 against upstream [verified:
     engines/reference-plaits.md, finding 4].
   - **Since 2026-10-01** the string runs at Plaits' rate on any host, so
     that rate dependence is gone: at 44,118 Hz the A2 note is upstream's,
     sample for sample through the resampler, and its pitch against
     upstream unresampled reads 0.00 cents [verified: reference-plaits.md,
     "At 44,118 Hz"]. The 6–9 cents of this item remain: they are
     upstream's.
10. **Plaits never applies a patch's transpose** (above).
11. **Allocation audit.** Everything else in the wrapped engines allocates
    what it uses [verified: code, with ASan over the sweep below]. The
    tightest case is the LPC word banks:

    | | Largest bank | Allocated |
    | --- | --- | --- |
    | Frames | 926 (bank 4) | 1,024 |
    | Words | 26 | 31 |

    That is about 10 % headroom [verified: scratch harness].
12. **`String::ProcessInternal` divides by a zero `f0`.**
    - **Where:** `float delay = 1.0f / f0;` (`string.cc:90`). On a trigger,
      `StringEngine` hands the string it leaves `f0_delay_.Read(14)`, which
      is 0 until the 16-sample delay has 14 writes. Upstream reaches it on
      the first trigger after the engine is selected. Here every note on a
      free voice reaches it, because `Reset()` clears the delay.
    - **Effect:** the result is +inf, which `CONSTRAIN` clamps to the longest
      delay, on a string that was just reset and is silent. Harmless on IEEE
      hardware that does not trap.
    - **Evidence:** [verified: UBSan `float-divide-by-zero`, `fm1-render
      --engine macro-heavy --param Model=8 --note 0:60:100:0.3`, via
      `StringEngine::Render`; every String render in the sweep].

**Assumption for stage B.** Quirk 12 relies on the FPU returning inf, not
trapping, on a float divide by zero. That is IEEE 754's default handling
and the usual reset state of desktop and ARM FPUs [inferred; not checked
here], and it is unverified on pi32v2. Check it there. Our own code no
longer divides by zero (the Six-Op note-on renders, above).

## Sanitizer run

Builds:

- **Standard:** `make -C engines EXTRA="-fsanitize=address,undefined
  -fno-omit-frame-pointer -g" OPT=-O1`.
- **Float division:** the same with `float-divide-by-zero` added to the
  list, which Clang's `undefined` group leaves out.

The sweep (230 renders per build, after the review fixes) covered:

- every Macro Heavy model at default, all-zero and all-one parameters, with
  keys 0, 24, 108 and 127 at velocities 1 and 127;
- every model with a chord past the voice cap, at 64- and 7-frame host
  blocks;
- speech at 12 Harmonics values across all its ranges, each with 4 Timbre
  values;
- all 96 Six-Op patches at keys 0, 57 and 127;
- 7 Six-Op patches with chords past the cap at the parameter extremes, and
  at 7- and 1-frame host blocks;
- this test file, run against the sanitizer binary: 180 passed.

Results:

- **Our code:** clean in both builds.
- **Vendored code:** quirk 2 (4 renders, Harmonics 0.2–0.4 at Timbre
  0.375), quirk 4 (117 renders, every Six-Op render) and, in the
  float-division build only, quirk 12 (5 renders, every String render).
- **Fixed:** the `operator.h:90` division by zero that the old zero-length
  Six-Op renders caused no longer appears.
- **After the native-rate change (2026-10-01):** every engine test
  (`tests/test_engine*.py`, 938 tests) passed against the ASan + UBSan build
  of `engines/README.md` (clang, `-O1`, the repository's ignorelist and
  suppressions, `halt_on_error=1`), in 204 s [verified].

The first pass of this stream also built the tree with GCC 15.2 on x86-64
Linux, with `-Wall -Wextra`. These files gave no warnings, and renders gave
the same peaks as on macOS. That was not re-run after the review fixes.

### 32-bit coverage

- **What CI does.** The `engines-32bit` job builds everything with `-m32
  -msse2 -mfpmath=sse`, runs `python -m pytest -v tests/test_engine*.py`
  against that build, and its "Report instance sizes" step renders every
  engine in the registry [verified: `.github/workflows/ci.yml`, 2026-10-01].
  (When this stream began it ran only `tests/test_engines.py` and sized only
  `macro` and `shapes`; request 1 below asked for this.)
- **Why it matters.** A 32-bit-only arena mismatch would disable a model
  silently; `test_every_heavy_model_sounds_cleanly` would now fail on it.
- **Why it is unlikely** [inferred]. `kArenaNeed` uses the same `sizeof`
  expressions as the upstream `Allocate<>()` calls, and `BufferAllocator`
  adds no padding. So the table can only disagree on one target if an
  upstream type changes size on that target alone.
- **Not run locally.** This Mac is arm64 and its Docker VM is aarch64 with
  no multilib image; installing one would mean downloading packages.
- **Fix.** Done in CI (request 1 below).

## Limits and open questions

- **Changing the model** rebuilds every voice and cuts sounding notes, as
  in Macro.
- **Chords and string machine** play a chord per key, so four keys can mean
  up to 20 oscillators.
- **Speech prosody** is fixed at 0. Only Word Speed is exposed, because
  there is no ninth knob on two pages.
- **`stmlib::Random`** is one global generator shared by every instance and
  voice. Output is deterministic per process, not per instance.
- **Patch data provenance and names.** The DX7 patch data carries Plaits'
  MIT header but no provenance. Its patch names, shown in the UI, include
  third-party trademarks and a person's name (listed under "The patch
  data"). For a commercial build, have the three banks and their names
  reviewed, or ship user banks instead.
- **Pi32v2 cost** is unmeasured; see stage B. So are one speech word-bank
  parse (above), the resamplers' share ("Voice cap") and the FPU's
  divide-by-zero behaviour.
- **The resampler's price** ("Rate", above): 0.76 ms more from a note to its
  sound at 44,118 Hz, 2.3 µs per resampler per desktop block, 1,288 B each,
  and hosts above 47,872.34 Hz are refused rather than upsampled (no
  upsampling resampler exists here; resampler.md, "Limits").
- **Silent-voice timers** count 12- or 16-sample blocks at 47,872.34 Hz, so
  their 50 ms and 1 s are the same at any host rate. Getting the rate wrong
  there only moves when a voice below −80 dBFS is freed, which no comparison
  with upstream can see. Two cases of the comparison of each wrapper with
  itself at its own rate do (reference-plaits.md, "Method"): Six-Op's
  E.PIANO 1, which has no key sync, replayed after its voice was freed
  starts from the operator phases the voice stopped at; and a Macro Heavy
  snare freed before another is played has drawn a different number of
  random numbers [verified: scratch mutants with the host's rate in either
  wrapper's timers fail them by 9,251 and 8,203 LSB; before those cases
  both passed every test]. Macro Heavy's 1 s timer for held keys is
  derived from the same rate and not exercised on its own.

## Requests outside this stream's files

This stream may not edit `.github/` or `engines/host/render.cc`, so these
go to the orchestrator and owner:

1. **CI, 32-bit job.** Run `python -m pytest -v tests/test_engines*.py`
   against the `-m32` binary, not only `tests/test_engines.py`. The
   render-time test `test_released_voices_are_freed` may need a skip or a
   looser bound there. Add `--engine macro-heavy` and `--engine sixop` to
   "Report instance sizes". Done since [verified: `.github/workflows/ci.yml`].
2. **Host: timed parameter events.** For example `--param-at
   T:NAME=VALUE`. That would let tests cover Harmonics moves across speech
   word banks and Patch changes under held Six-Op voices, which only
   scratch harnesses cover now. Done since: `fm1-render --param-at`
   [verified: `engines/host/render.cc`], used by
   `test_every_parameter_can_move_while_notes_sound` and
   `test_string_machine_entered_later_renders_as_if_created_in_it`.
3. **Host: an active-voice diagnostic.** For example an optional engine
   callback, or a summary field, reporting how many voices are active at
   the end. `test_released_voices_are_freed` could then assert freeing
   directly instead of through render time.

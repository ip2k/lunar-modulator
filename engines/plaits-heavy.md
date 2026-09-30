# plaits-heavy: Macro Heavy and Six-Op FM

This stream adds the remaining Plaits engines from docs/11 §4 as two FM-1
engines. The code is Emilie Gillet's (Mutable Instruments Plaits, MIT),
vendored unmodified in `third_party/mutable/` (`UPSTREAM.md`). The wrappers
are ours.

| id | Name | Source | Voices | Instance, 64-bit host | Instance, 32-bit targets |
| --- | --- | --- | --- | --- | --- |
| `macro-heavy` | Macro Heavy | `src/mi_macro_heavy.cc` | 4 | 68,640 B | 68,448 B |
| `sixop` | Six-Op FM | `src/mi_sixop.cc` | 8 | 11,312 B | 9,576 B |

How the sizes were measured:

- **64-bit:** the renderer's `instance_bytes` on macOS arm64 [verified].
- **32-bit:** `sizeof(Instance)` compiled for `i386-apple-macos10.13` and
  `armv7-apple-ios9`. Both targets give the same numbers [verified, compile
  only]. pi32v2 should match if it is ILP32 with 4-byte float alignment
  [inferred].

Sources are added in `mk/plaits-heavy.mk`. The fragment appends a
third-party file only when no other fragment lists it already.

```bash
make -C engines
engines/build/fm1-render --engine macro-heavy --param Model=8 --param Harmonics=0.25 \
    --note 0:57:100:1 --note 0:64:100:1 --seconds 3 --out string.wav
engines/build/fm1-render --engine sixop --param Patch=32 \
    --note 0:57:100:1 --note 0:61:100:1 --note 0:64:100:1 --seconds 3 --out epiano.wav
python -m pytest tests/test_engines_plaits_heavy.py      # 177 tests
```

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
| 2 | Speech | `SpeechEngine` | -0.7 | 0.8 | LPG for vowels; words bypass it (per block) | 14,656 B | 472 B |
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
placement new, with Plaits' 12-sample blocks and the pitch offset
12·log2(47,872.34 / rate).

- **Arena.** Each voice gets its own 16 KB arena, which is the size of
  Plaits' single shared arena. It has to be that large: the particle
  diffuser alone takes all 16 KB, the string model 15.2 KB and speech
  14.3 KB.
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
  through NULL.
- A re-vendor that changes an allocation therefore fails
  `test_every_heavy_model_sounds_cleanly`.

**Self-enveloped models.** These are string, modal, the three drums, and
speech words. As in `Voice::Render`, the low-pass gate is bypassed, and the
LPG is re-initialised while bypassed.

- **Accent.** The accent is the note's velocity, compressed as Plaits
  compresses LEVEL, for the whole life of the note. Drums and strings read
  it at the trigger, and speech uses it as the word's gain. The LPG's level
  still drops to zero at note-off.
- **Release after note-off.** This is our addition, not Plaits behaviour:
  the module has no note-off. The fade uses the same curve as the LPG's
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
- **No `Reset()` at note-on.** `SpeechEngine::Reset()` only discards the
  parsed LPC word bank, and `Render()` would then parse up to 4.8 KB of
  bitstream inside an audio block. So the wrapper does not call `Reset()` at
  note-on for speech.

**Stereo.** The string machine's OUT and AUX are the two sides of its
ensemble (`out = 0.66 l + 0.33 r` and the mirror image) [verified: code], so
this model renders them as L and R. Every other model is mono, from OUT.

### Voice cap: 4

RAM sets the cap. Four voices of 17.1 KB (arena, engine, post-processors
and buffers) come to 67 KB, out of the roughly 387 KB free in the stock
layout (docs/11 §2).

CPU is unknown until stage B measures it:

- Plaits was built to use most of a 72 MHz Cortex-M4F for one voice
  [reported: docs/11 §2, from MI's notes].
- The FM-1 has about 5,440 cycles per output sample for everything
  [inferred: arithmetic].

Desktop cost, for scale only. These are Apple M1 Max figures, as a share of
the 1.451 ms block, with every voice sounding, best of five:

| Engine / model | Voices | Share of block | Per voice |
| --- | --- | --- | --- |
| Macro Heavy, most models | 4 | 0.50–0.92 % | 0.12–0.23 % |
| Macro Heavy, Particle | 4 | 1.75 % | 0.44 % |
| Macro Heavy, Speech (vowels / words) | 4 | 0.39–0.91 % / 0.25 % | 0.06–0.23 % |
| Macro VA+Filter (reference) | 12 | 1.49 % | 0.12 % |
| Macro 2-op FM (reference) | 12 | 4.96 % | 0.41 % |
| Six-Op FM | 8 | 0.74–0.77 % | 0.09 % |

So on the desktop, four heavy voices cost less than Macro's twelve light
ones, and particle is the heaviest model by 2x. pi32v2 is a much narrower
core (engines/README.md), so these ratios need not hold there [inferred]. Raising
the cap is a one-line change once stage B has numbers.

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
- **Native rate.** `FMVoice::Init` takes the sample rate, so it runs at the
  host's rate. There is no pitch offset, and DX7 envelope and LFO times are
  exact, not 8.5 % long as in the other Plaits wrappers.
- **Blocks.** Internal blocks are 16 samples, which divides 64. Envelopes
  update once per block; Plaits updates every 24 samples.
- **Note-on.** Each note-on does two zero-length renders with the gate low.
  - The first runs a new patch's `Setup()`, which otherwise returns without
    rendering and would swallow the note's first block.
  - The second drops `fm::Voice`'s gate, so a voice stolen or retriggered
    while held still sees a note-on edge and attacks again. Without it a
    stolen held voice stays silent; `test_sixop_stolen_held_voice_attacks_again`
    fails with the renders removed.
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
See the open issue below.

## Tests

`tests/test_engines_plaits_heavy.py` has 177 tests:

| Group | Tests | What they check |
| --- | --- | --- |
| Registry | 1 | Ids and names avoid Mutable Instruments' names; pages, name lengths and credits |
| Patch names | 1 | The patch-name table matches `resources.cc` |
| Every model and patch | 13 + 96 | One note each: no non-finite samples, no raw clipping, audible |
| Macro Heavy tuning | 18 | At A3, A4 and A5, after a low-pass that leaves the fundamental. ±5 cents for additive, formant, swarm, speech vowels and modal (structure 0.25); ±12 cents for string |
| Six-Op tuning | 6 | ±5 cents for three patches with transposes of none, −12 and +12 |
| Chords under the limiter | 16 + 8 | At the voice cap and past it (stealing): no clipping, peak ≤ 0.98 |
| Releases | 7 | Releases end (LPG, self-enveloped at Morph = 1, speech words, Six-Op) |
| Voice freeing | 3 | Freeing, as render cost: released chords cost 2–6 % of held ones on the desktop, and the test allows 50 %; it fails when freeing is disabled |
| Wrapper behaviour | 4 | Stereo string machine; Word Speed; a stolen held voice attacks again; output identical at host blocks of 64, 7 and 1 frames |
| Determinism | 3 | Particle, string and Six-Op render the same bytes twice |
| Instance sizes | 1 | The sizes stay within the bounds above |

Where tuning is not checked, and why:

- **Chords and string machine** play four or five notes per key.
- **Drums, noise and particle** have no stable fundamental.
- **A2** is left out: the low-passed fundamental of the physical models is
  too weak there.

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
     0:57:100:0.3`]. No wrapper-side fix without changing behaviour.
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
     The sanitizer run below suppresses exactly this check in exactly this
     file.
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
     does, so it sounds like the module.
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
10. **Plaits never applies a patch's transpose** (above).
11. **Allocation audit.** Everything else in the wrapped engines allocates
    what it uses [verified: code, with ASan over the sweep below]. The
    tightest case is the LPC word banks:

    | | Largest bank | Allocated |
    | --- | --- | --- |
    | Frames | 926 (bank 4) | 1,024 |
    | Words | 26 | 31 |

    That is about 10 % headroom [verified: scratch harness].

## Sanitizer run

Command: `make -C engines EXTRA="-fsanitize=address,undefined
-fno-omit-frame-pointer -g" OPT=-O1`.

The sweep covered:

- every Macro Heavy model at default, all-zero and all-one parameters;
- keys 0, 24, 108 and 127 at velocities 1 and 127;
- chords past the voice cap, and 7-frame host blocks;
- 17 Six-Op patches under the same conditions;
- this test file, run against the sanitizer binary.

Results:

- **Our code:** clean.
- **Vendored code:** quirks 2 (with the parameters given there) and 4 above.

The same tree also built with GCC 15.2 on x86-64 Linux, with `-Wall
-Wextra`. These files gave no warnings, and renders gave the same peaks as on
macOS. The 32-bit (`-m32`) build was not run locally; CI runs it.

## Limits and open questions

- **Changing the model** rebuilds every voice and cuts sounding notes, as
  in Macro.
- **Chords and string machine** play a chord per key, so four keys can mean
  up to 20 oscillators.
- **Speech prosody** is fixed at 0. Only Word Speed is exposed, because
  there is no ninth knob on two pages.
- **`stmlib::Random`** is one global generator shared by every instance and
  voice. Output is deterministic per process, not per instance.
- **Patch data provenance.** The DX7 patch data carries Plaits' MIT header
  but no provenance. For a commercial build, have the three banks reviewed,
  or load user banks instead.
- **Pi32v2 cost** is unmeasured; see stage B.
